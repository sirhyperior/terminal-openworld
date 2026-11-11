"""Interleave frozen/current engines per frame with a shared live audio process.

Freeze ascii3d/ before editing, then pass its parent with --before-source.
Reports retain source hashes, both frame distributions and every failed scene.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS, resolve_camera
from ascii3d.events import GameEvent
from ascii3d.sound import Audio


def load_engine(root, alias):
    package = root / "ascii3d"
    spec = importlib.util.spec_from_file_location(alias, package / "__init__.py",
                                                 submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return {name: importlib.import_module(f"{alias}.{name}")
            for name in ("world", "player", "renderer", "combat", "soundscape")}


def variant(engine, width=120, height=40):
    start = time.perf_counter()
    world = engine["world"].build_world()
    built = time.perf_counter()
    renderer = engine["renderer"].Renderer(world)
    created = time.perf_counter()
    renderer.frame(engine["player"].Player(), width, height)
    primed = time.perf_counter()
    return {"engine": engine, "world": world, "renderer": renderer,
            "soundscape": engine["soundscape"].Soundscape(world),
            "startup": {"build_ms": round((built - start) * 1000, 2),
                        "renderer_init_ms": round((created - built) * 1000, 2),
                        "first_frame_ms": round((primed - created) * 1000, 2)}}


def prepare(state, name, position):
    engine, world = state["engine"], state["world"]
    player = engine["player"].Player(**position)
    combat, definitions = world.combat, engine["combat"]
    training, casting = name == "training", name == "fireballs"
    combat.held_item = definitions.WeaponPickup(0, 0) if training else None
    combat.fireballs.clear()
    combat.bursts.clear()
    for enemy in combat.enemies:
        enemy.hp = enemy.max_hp
        enemy.down_remaining = enemy.hit_remaining = 0.0
        if enemy.behavior is not None:
            enemy.x, enemy.y, enemy.z = enemy.home
            enemy.state = "idle"
            enemy.attack_remaining = enemy.attack_cooldown = 0.0
            enemy.walk_phase = 0.0
            enemy.facing = -math.pi / 2
            enemy._step_distance = enemy._steer_remaining = 0.0
    for pickup in combat.pickups:
        pickup.collected = training
    if casting:
        combat.held_item = definitions.WeaponPickup(0, 0, weapon=definitions.FIRE_STAFF)
    combat.cooldown = combat.swing_remaining = 0.0
    state.update(player=player, yaw=player.yaw, timings=[], frame=0,
                 training=training, casting=casting, walking=name in ("terrace_walk", "stair_walk"))


def frame(state, name, audio, width, height, *, measured):
    player, world = state["player"], state["world"]
    index = state["frame"]
    player.yaw = state["yaw"] if state["walking"] else state["yaw"] + math.sin(index * 0.06) * 0.35
    start = time.perf_counter()
    if state["training"] or state["casting"] or state["walking"] or name == "warden":
        events = []
        for _ in range(3):
            if state["walking"]:
                player.update(world, {"w"}, 1 / 120)
                events.extend(player.events)
            events.extend(world.combat.update(1 / 120, world, player))
        if (state["training"] or state["casting"]) and index % 20 == 0:
            events.extend(world.combat.attack(world, player))
        if audio:
            for event in events:
                # Frozen dataclasses belong to a private import namespace and
                # must not leak into the spawned audio process's pickle stream.
                audio.emit(GameEvent(event.name, event.x, event.y, event.strength, event.surface))
    if audio:
        audio.listener = player.x, player.y, player.yaw
        if state.get("elevated_audio"):
            audio.ambient = state["soundscape"].at(player.x, player.y, player.yaw, player.z)
        else:
            audio.ambient = state["soundscape"].at(player.x, player.y, player.yaw)
        if not state["walking"] and index % 12 == 0:
            audio.emit(GameEvent("step_grass" if name == "grass_close" else "step_stone"))
        if not state["walking"] and index % 60 == 1:
            audio.emit(GameEvent("door_open", player.x + 2, player.y))
    state["renderer"].frame(player, width, height, time_seconds=index / 40,
                             show_map=name in ("map", "highland_map"))
    elapsed = (time.perf_counter() - start) * 1000
    if measured:
        state["timings"].append(elapsed)
    state["frame"] += 1


def summarize(state):
    timings = state["timings"]
    ordered = sorted(timings)
    return {"mean_ms": round(statistics.mean(timings), 3) if timings else None,
            "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3) if timings else None,
            "sample_count": len(timings),
            "samples_ms": [round(value, 4) for value in timings],
            "scenery": dict(state["renderer"].scenery.stats)}


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / "ascii3d").glob("*.py"))}


def save_report(path, report, *, initial=False):
    """Reserve an unused report, then atomically update only this run's file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report, indent=2) + "\n"
    if initial:
        with path.open("x", encoding="utf-8") as destination:
            destination.write(content)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as destination:
            temporary = Path(destination.name)
            destination.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def audio_health(audio):
    return {"available": bool(audio.available), "buffers": audio.blocks_rendered,
            "underruns": audio.underruns, "max_write_gap_ms": round(audio.max_write_gap_ms, 2),
            "recoveries": audio.recoveries, "error": audio.error}


def run(args, *, before=None, after=None, audio_factory=Audio,
        prepare_scene=prepare, run_frame=frame):
    """Keep partial evidence if preparation, rendering or device cleanup fails.

    Scene checkpoints are outside frame timers. The current partial samples are
    also saved during exception handling; incomplete scenes never receive a pass.
    """
    current_root = Path(__file__).resolve().parents[1]
    report = {"method": "per-frame ABBA, five warmups, equal samples per variant; shared native mixer",
              "python": platform.python_version(), "platform": platform.system(),
              "machine": platform.machine(), "processor": platform.processor(),
              "width": args.width, "height": args.height, "frames": args.frames,
              "audio": args.audio, "threshold_percent": 15.0,
              "ambient_sampling": {"before": "elevated" if args.before_elevated_audio else "flat",
                                   "after": "elevated"},
              "before_hashes": hashes(args.before_source.resolve()), "after_hashes": hashes(current_root),
              "cameras": {**SCENARIOS, **EXTRA_SCENARIOS}, "terrain_cameras": dict(TERRAIN_SCENARIOS),
              "scenarios": {}, "new_scenarios": {}, "preflight": {}, "errors": [], "failed": [],
              "status": "preparing", "complete": False, "passed": False,
              "phase": "startup", "current_scene": None, "current_variant": None}
    report["scenarios"] = {name: {"status": "pending", "passed": False} for name in report["cameras"]}
    report["new_scenarios"] = {name: {"status": "pending", "passed": None}
                                for name in report["terrain_cameras"]}
    save_report(args.save, report, initial=True)
    audio = audio_context = None
    entered_audio = False
    measurements_complete = False
    current_entry = None
    current_states = {}

    def failure(error, phase=None):
        report["errors"].append({"type": type(error).__name__, "message": str(error),
                                 "phase": phase or report["phase"],
                                 "scene": report["current_scene"],
                                 "variant": report["current_variant"]})
        if "exception" not in report["failed"]:
            report["failed"].append("exception")

    def partial_samples():
        if current_entry is None or current_entry.get("status") == "complete":
            return
        for label, state in current_states.items():
            if "timings" in state:
                current_entry[label] = summarize(state)

    try:
        if before is None:
            before = variant(load_engine(args.before_source.resolve(), "before_ascii3d"), args.width, args.height)
        before["elevated_audio"] = args.before_elevated_audio
        if after is None:
            after = variant({name: importlib.import_module(f"ascii3d.{name}")
                             for name in before["engine"]}, args.width, args.height)
        after["elevated_audio"] = True
        states = {"before": before, "after": after}
        report["world_sizes"] = {label: [state["world"].width, state["world"].depth, state["world"].height]
                                 for label, state in states.items()}
        report["startup"] = {label: state["startup"] for label, state in states.items()}
        # Validate every role before opening a device or measuring any scene.
        # Historical castle cameras retain their fixed poses in each engine.
        report["phase"] = "preflight"
        resolved = {}
        for name, camera in report["cameras"].items():
            report["current_scene"] = name
            resolved[name] = {}
            report["preflight"][name] = resolved[name]
            for label, state in states.items():
                report["current_variant"] = label
                resolved[name][label] = resolve_camera(state["world"], name, camera,
                                                       player_type=state["engine"]["player"].Player)
        terrain = {}
        for name, camera in report["terrain_cameras"].items():
            report["current_scene"], report["current_variant"] = name, "after"
            terrain[name] = resolve_camera(after["world"], name, camera, natural=True,
                                           player_type=after["engine"]["player"].Player)
            report["preflight"][name] = {"after": terrain[name]}
        report.update(status="running", current_scene=None, current_variant=None, phase="audio_start")
        save_report(args.save, report)
        if args.audio:
            audio_context = audio_factory(volume=0.25)
            audio = audio_context.__enter__()
            entered_audio = True
            if not audio.available:
                raise OSError(audio.error or "Audio output unavailable")
        for name in report["cameras"]:
            report.update(current_scene=name, current_variant=None, phase="warmup")
            current_entry = {"status": "running", "passed": False}
            report["scenarios"][name] = current_entry
            current_states = states
            for state in states.values():
                state["timings"] = []
            for label, state in states.items():
                report["current_variant"] = label
                prepare_scene(state, name, resolved[name][label])
                for _ in range(5):
                    run_frame(state, name, audio, args.width, args.height, measured=False)
            report["phase"] = "measurement"
            for _ in range(args.frames // 2):
                for label in ("before", "after", "after", "before"):
                    report["current_variant"] = label
                    run_frame(states[label], name, audio, args.width, args.height, measured=True)
            old, new = summarize(before), summarize(after)
            mean = (new["mean_ms"] / old["mean_ms"] - 1) * 100
            p95 = (new["p95_ms"] / old["p95_ms"] - 1) * 100
            passed = max(mean, p95) <= 15.0
            if not passed:
                report["failed"].append(name)
            current_entry.update(status="complete", before=old, after=new,
                                 mean_change_percent=round(mean, 2), p95_change_percent=round(p95, 2),
                                 passed=passed)
            save_report(args.save, report)
            print(f"{name:18} mean {mean:+6.2f}% p95 {p95:+6.2f}% {'PASS' if passed else 'FAIL'}", flush=True)
        for name, camera in terrain.items():
            report.update(current_scene=name, current_variant="after", phase="warmup")
            current_entry = {"status": "running", "camera": camera, "passed": False}
            report["new_scenarios"][name] = current_entry
            current_states = {"after": after}
            after["timings"] = []
            prepare_scene(after, name, camera)
            for index in range(args.frames + 5):
                report["phase"] = "measurement" if index >= 5 else "warmup"
                run_frame(after, name, audio, args.width, args.height, measured=index >= 5)
            current_entry.update(status="complete", passed=None, **summarize(after))
            save_report(args.save, report)
        measurements_complete = True
    except (Exception, KeyboardInterrupt) as error:
        partial_samples()
        if report["phase"] == "preflight":
            scenes = report["scenarios"] if report["current_scene"] in report["scenarios"] else report["new_scenarios"]
            scenes[report["current_scene"]]["status"] = "invalid_camera"
        if current_entry is not None and current_entry.get("status") != "complete":
            current_entry["status"] = "incomplete"
        failure(error)
    finally:
        if args.audio and audio_context is not None:
            try:
                report["audio_health"] = audio_health(audio if audio is not None else audio_context)
            except Exception as error:
                failure(error, "audio_health")
        if entered_audio:
            try:
                audio_context.__exit__(None, None, None)
            except (Exception, KeyboardInterrupt) as error:
                failure(error, "audio_cleanup")
        if args.audio and audio_context is not None:
            try:
                final_health = audio_health(audio if audio is not None else audio_context)
                report["audio_health_after_cleanup"] = final_health
                # Closing an output intentionally makes available false. Keep
                # the measured availability while retaining final counters.
                if "audio_health" in report:
                    report["audio_health"].update({key: value for key, value in final_health.items()
                                                   if key != "available"})
                else:
                    report["audio_health"] = final_health
            except Exception as error:
                failure(error, "audio_health_after_cleanup")
        health = report.get("audio_health")
        if args.audio and (not health or not health["available"] or health["underruns"]
                           or health["recoveries"] or health["error"]):
            report["failed"].append("audio_health")
        report["complete"] = measurements_complete and not report["errors"]
        report["passed"] = report["complete"] and not report["failed"]
        report["status"] = "incomplete" if not report["complete"] else ("passed" if report["passed"] else "failed")
        save_report(args.save, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-source", type=Path, required=True)
    parser.add_argument("--save", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--width", type=int, default=120)
    parser.add_argument("--height", type=int, default=40)
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--before-elevated-audio", action="store_true",
                        help="sample listener height in a frozen control that supports elevated ambience")
    args = parser.parse_args(argv)
    if args.frames < 20 or args.frames % 2 or not (60 <= args.width <= 300 and 20 <= args.height <= 120):
        parser.error("use an even frame count >=20 and dimensions from 60x20 to 300x120")
    if args.save.exists():
        parser.error("--save must name an unused report path")
    report = run(args)
    print("Saved", args.save, report["status"], "failures:", report["failed"])
    for error in report["errors"]:
        print(f"{error['phase']}: {error['type']}: {error['message']}", file=sys.stderr)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

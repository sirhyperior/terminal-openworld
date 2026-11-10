"""Interleave frozen/current engines per frame with a shared live audio process.

Freeze ascii3d/ before editing, then pass its parent with --before-source.
Reports retain source hashes, both frame distributions and every failed scene.
"""

import argparse
from contextlib import nullcontext
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS
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
    return {"mean_ms": round(statistics.mean(timings), 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
            "samples_ms": [round(value, 4) for value in timings],
            "scenery": dict(state["renderer"].scenery.stats)}


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / "ascii3d").glob("*.py"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-source", type=Path, required=True)
    parser.add_argument("--save", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--width", type=int, default=120)
    parser.add_argument("--height", type=int, default=40)
    parser.add_argument("--audio", action="store_true")
    args = parser.parse_args()
    if args.frames < 20 or args.frames % 2 or not (60 <= args.width <= 300 and 20 <= args.height <= 120):
        parser.error("use an even frame count >=20 and dimensions from 60x20 to 300x120")
    current_root = Path(__file__).resolve().parents[1]
    before = variant(load_engine(args.before_source.resolve(), "before_ascii3d"), args.width, args.height)
    after = variant({name: importlib.import_module(f"ascii3d.{name}")
                     for name in before["engine"]}, args.width, args.height)
    after["elevated_audio"] = True
    report = {"method": "per-frame ABBA, five warmups, equal samples per variant; shared native mixer",
              "python": platform.python_version(), "platform": platform.system(),
              "machine": platform.machine(), "processor": platform.processor(),
              "width": args.width, "height": args.height, "frames": args.frames,
              "audio": args.audio, "threshold_percent": 15.0,
              "before_hashes": hashes(args.before_source.resolve()), "after_hashes": hashes(current_root),
              "world_sizes": {label: [s["world"].width, s["world"].depth, s["world"].height]
                              for label, s in (("before", before), ("after", after))},
              "startup": {"before": before["startup"], "after": after["startup"]},
              "cameras": {**SCENARIOS, **EXTRA_SCENARIOS}, "scenarios": {}, "new_scenarios": {}}
    failed = []
    with Audio(volume=0.25) if args.audio else nullcontext(None) as audio:
        if audio and not audio.available:
            raise OSError(audio.error)
        for name, position in report["cameras"].items():
            for state in (before, after):
                prepare(state, name, position)
                for _ in range(5):
                    frame(state, name, audio, args.width, args.height, measured=False)
            for _ in range(args.frames // 2):
                for state in (before, after, after, before):
                    frame(state, name, audio, args.width, args.height, measured=True)
            old, new = summarize(before), summarize(after)
            mean = (new["mean_ms"] / old["mean_ms"] - 1) * 100
            p95 = (new["p95_ms"] / old["p95_ms"] - 1) * 100
            passed = max(mean, p95) <= 15
            if not passed:
                failed.append(name)
            report["scenarios"][name] = {"before": old, "after": new,
                                         "mean_change_percent": round(mean, 2),
                                         "p95_change_percent": round(p95, 2), "passed": passed}
            print(f"{name:18} mean {mean:+6.2f}% p95 {p95:+6.2f}% {'PASS' if passed else 'FAIL'}", flush=True)
        for name, camera in TERRAIN_SCENARIOS.items():
            position = dict(camera)
            position.setdefault("z", after["world"].surface_height(position["x"], position["y"]))
            if after["world"].collides(position["x"], position["y"], position["z"]):
                raise ValueError(f"Terrain benchmark camera intersects geometry: {name}")
            prepare(after, name, position)
            for i in range(args.frames + 5):
                frame(after, name, audio, args.width, args.height, measured=i >= 5)
            report["new_scenarios"][name] = {"camera": position, **summarize(after)}
        if audio:
            report["audio_health"] = {"buffers": audio.blocks_rendered, "underruns": audio.underruns,
                                       "max_write_gap_ms": round(audio.max_write_gap_ms, 2),
                                       "recoveries": audio.recoveries, "error": audio.error}
            if audio.underruns or audio.error or audio.recoveries:
                failed.append("audio_health")
    report["failed"] = failed
    report["passed"] = not failed
    args.save.parent.mkdir(parents=True, exist_ok=True)
    args.save.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Saved", args.save, "failures:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

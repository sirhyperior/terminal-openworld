"""Repeatable camera benchmarks; compare JSON results on the same machine."""

import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ascii3d.combat import FIRE_STAFF, WeaponPickup
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.soundscape import Soundscape
from ascii3d.world import build_world, river_center


SCENARIOS = {
    "indoors": dict(x=55.5, y=30.5, yaw=math.pi / 2),
    "courtyard": dict(x=55.5, y=42.5, yaw=math.pi / 2),
    "meadow": dict(x=55.5, y=18.5, yaw=math.pi / 2, pitch=-0.06),
    "grass_close": dict(x=12.5, y=31.5, yaw=math.pi / 2, pitch=-0.35),
    "bridge": dict(x=24.5, y=86.5, yaw=math.pi / 2, pitch=-0.1),
    "river": dict(x=8.5, y=river_center(8.5), z=0.12, yaw=0, pitch=-0.1),
}

EXTRA_SCENARIOS = {
    "ruins": dict(x=56.5, y=95, yaw=math.pi / 2, pitch=-0.06),
    "lodge": dict(x=90, y=47.5, yaw=0, pitch=-0.06),
    "east_bridge": dict(x=86.5, y=86.5, yaw=math.pi / 2, pitch=-0.1),
    "watchstones": dict(x=18.5, y=97, yaw=math.pi / 2, pitch=-0.06),
    "warden": dict(x=18.5, y=99.5, yaw=math.pi / 2, pitch=-0.06),
    "staff": dict(x=53.5, y=101.5, yaw=math.pi / 2, pitch=-0.06),
    "fireballs": dict(x=42.5, y=40.5, yaw=math.pi / 2),
    "map": dict(x=55.5, y=42.5, yaw=math.pi / 2),
    "training": dict(x=42.5, y=46.2, yaw=math.pi / 2),
    "tree_close": dict(x=12.5, y=34.0, yaw=math.pi / 2, pitch=-0.35),
    "tree_canopy": dict(x=12.5, y=33.95, z=2.25, yaw=math.pi / 2, pitch=0.65),
    "river_diagonal": dict(x=70.5, y=river_center(70.5), z=0.12, yaw=math.pi / 4, pitch=-0.25),
    "river_upstream": dict(x=70.5, y=river_center(70.5), z=0.12, yaw=math.pi, pitch=-0.25),
    "castle_exterior": dict(x=20.5, y=16.5, yaw=0.6, pitch=0.08),
    "great_hall": dict(x=55.5, y=65.5, yaw=math.pi / 2, pitch=0.12),
    "wall_walk": dict(x=35.5, y=45.5, z=6, yaw=math.pi / 2, pitch=-0.15),
    "west_meadow": dict(x=12.5, y=58.5, yaw=math.pi / 2, pitch=-0.1),
    "east_meadow": dict(x=100.5, y=68.5, yaw=math.pi / 2, pitch=-0.1),
}



def run(frames=90, width=120, height=40, with_audio=False, extra_scenes=False):
    world = build_world()
    renderer = Renderer(world)
    soundscape = Soundscape(world)
    results = {}
    with ExitStack() as stack:
        audio = None
        if with_audio:
            from ascii3d.sound import Audio
            from ascii3d.events import GameEvent
            audio = stack.enter_context(Audio(volume=0.25))
            if not audio.available:
                raise OSError(audio.error)
        scenes = {**SCENARIOS, **EXTRA_SCENARIOS} if extra_scenes else SCENARIOS
        for name, position in scenes.items():
            player = Player(**position)
            training = name == "training"
            world.combat.held_item = WeaponPickup(0, 0) if training else None
            world.combat.fireballs.clear()
            world.combat.bursts.clear()
            for enemy in world.combat.enemies:
                enemy.hp = enemy.max_hp
                enemy.down_remaining = enemy.hit_remaining = 0.0
                if enemy.behavior is not None:
                    enemy.x, enemy.y, enemy.z = enemy.home
                    enemy.state = "idle"
                    enemy.attack_remaining = enemy.attack_cooldown = 0.0
                    enemy.walk_phase = 0.0
                    enemy.facing = -math.pi / 2
                    enemy._step_distance = enemy._steer_remaining = 0.0
            for pickup in world.combat.pickups:
                pickup.collected = training
            casting = name == "fireballs"
            if casting:
                world.combat.held_item = WeaponPickup(0, 0, weapon=FIRE_STAFF)
            world.combat.cooldown = world.combat.swing_remaining = 0.0
            base_yaw = player.yaw
            timings = []
            for frame in range(frames + 5):
                player.yaw = base_yaw + math.sin(frame * 0.06) * 0.35
                start = time.perf_counter()
                if training or casting or name == "warden":
                    events = []
                    for _ in range(3):
                        events.extend(world.combat.update(1 / 120, world, player))
                    if (training or casting) and frame % 20 == 0:
                        events.extend(world.combat.attack(world, player))
                    if audio:
                        for event in events:
                            audio.emit(event)
                if audio:
                    audio.listener = (player.x, player.y, player.yaw)
                    audio.ambient = soundscape.at(player.x, player.y, player.yaw)
                    if frame % 12 == 0:
                        audio.emit(GameEvent("step_grass" if name == "grass_close" else "step_stone"))
                    if frame % 60 == 1:
                        audio.emit(GameEvent("door_open", player.x + 2, player.y))
                renderer.frame(player, width, height, time_seconds=frame / 40, show_map=name == "map")
                if frame >= 5:
                    timings.append((time.perf_counter() - start) * 1000)
            ordered = sorted(timings)
            results[name] = {
                "mean_ms": round(statistics.mean(timings), 3),
                "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
                "fps": round(1000 / statistics.mean(timings), 1),
            }
            stats = getattr(renderer.scenery, "stats", None)
            if stats is not None:
                results[name]["scenery"] = dict(stats)
    report = {"python": platform.python_version(), "platform": platform.system(),
            "machine": platform.machine(), "processor": platform.processor(),
            "width": width, "height": height, "frames": frames, "audio": with_audio, "ambient_sampling": "world" if with_audio else "off",
            "world_size": [world.width, world.depth, world.height],
            "cameras": scenes, "scenarios": results}
    if audio:
        report["audio_health"] = {"buffers": audio.blocks_rendered, "underruns": audio.underruns,
                                  "max_write_gap_ms": round(audio.max_write_gap_ms, 2),
                                  "recoveries": audio.recoveries, "error": audio.error}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--width", type=int, default=120)
    parser.add_argument("--height", type=int, default=40)
    parser.add_argument("--save", type=Path, help="write results as JSON")
    parser.add_argument("--compare", type=Path, help="check mean and p95 frame times against a previous JSON run")
    parser.add_argument("--max-regression", type=float, default=15.0, help="allowed percent increase (default: 15)")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    parser.add_argument("--audio", action="store_true", help="include live ambient/effects mixing; needs a Windows audio device")
    parser.add_argument("--extra-scenes", action="store_true", help="also measure expansion landmarks, combat, staff/fireballs, close trees and river views")
    args = parser.parse_args()
    if args.frames < 20 or not (60 <= args.width <= 300 and 20 <= args.height <= 120):
        parser.error("use at least 20 frames and dimensions between 60x20 and 300x120")
    if not math.isfinite(args.max_regression) or args.max_regression < 0:
        parser.error("--max-regression must be a finite, nonnegative percentage")
    try:
        report = run(args.frames, args.width, args.height, args.audio, args.extra_scenes)
    except OSError as error:
        parser.error(str(error))
    failed = []
    if args.audio and (report["audio_health"]["underruns"] or report["audio_health"]["error"]):
        failed.append("audio playback")
    if args.compare:
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        keys = ("width", "height", "frames", "python", "platform", "machine", "processor", "audio", "ambient_sampling")
        if any(report[key] != baseline[key] for key in keys if key in baseline):
            parser.error("baseline frame count, dimensions, Python version, and platform must match")
        for name, result in report["scenarios"].items():
            if name not in baseline["scenarios"]:
                continue  # New scenes have measurements but no historical reference.
            previous = baseline["scenarios"][name]["mean_ms"]
            change = (result["mean_ms"] / previous - 1) * 100
            result["change_percent"] = round(change, 1)
            p95_change = (result["p95_ms"] / baseline["scenarios"][name]["p95_ms"] - 1) * 100
            result["p95_change_percent"] = round(p95_change, 1)
            if max(change, p95_change) > args.max_regression:
                failed.append(name)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report))
    else:
        print(f"{args.width}x{args.height}, {args.frames} measured frames per scene; terminal output excluded")
        for name, result in report["scenarios"].items():
            change = (f"  mean {result['change_percent']:+.1f}% / p95 {result['p95_change_percent']:+.1f}%"
                      if "change_percent" in result else "")
            print(f"{name:12} {result['fps']:6.1f} FPS  mean {result['mean_ms']:6.2f} ms  "
                  f"p95 {result['p95_ms']:6.2f} ms{change}")
        if args.audio:
            health = report["audio_health"]
            print(f"Audio: {health['underruns']} underruns, {health['recoveries']} recoveries, "
                  f"{health['max_write_gap_ms']:.1f} ms maximum refill interval. {health['error']}")
        if failed:
            print("Frame-time regression: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

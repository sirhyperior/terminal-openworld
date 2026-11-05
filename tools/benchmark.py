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

from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import build_world, river_center


SCENARIOS = {
    "indoors": dict(x=14.5, y=4.5, yaw=math.pi / 2),
    "courtyard": dict(x=16.5, y=20.5, yaw=math.pi / 2),
    "meadow": dict(x=10.5, y=37.0, yaw=1.03, pitch=-0.06),
    "grass_close": dict(x=24.5, y=34.5, yaw=math.pi / 2, pitch=-0.35),
    "bridge": dict(x=16.5, y=46.5, yaw=math.pi / 2, pitch=-0.1),
    "river": dict(x=7.5, y=46.5, z=0.12, yaw=0.0, pitch=-0.1),
}

EXTRA_SCENARIOS = {
    "ruins": dict(x=37.5, y=67, yaw=math.pi / 2, pitch=-0.06),
    "lodge": dict(x=52.5, y=12, yaw=math.pi / 2, pitch=-0.06),
    "east_bridge": dict(x=51.5, y=46.5, yaw=math.pi / 2, pitch=-0.1),
    "watchstones": dict(x=15.5, y=73, yaw=math.pi / 2, pitch=-0.06),
    "training": dict(x=18.2, y=36.5, yaw=0),
    "tree_close": dict(x=5.5, y=34.0, yaw=math.pi / 2, pitch=-0.35),
    "tree_canopy": dict(x=5.5, y=33.95, z=2.25, yaw=math.pi / 2, pitch=0.65),
    "river_diagonal": dict(x=32.5, y=river_center(32.5), z=0.12, yaw=math.pi / 4, pitch=-0.25),
    "river_upstream": dict(x=32.5, y=river_center(32.5), z=0.12, yaw=math.pi, pitch=-0.25),
}


def run(frames=90, width=120, height=40, with_audio=False, extra_scenes=False):
    world = build_world()
    renderer = Renderer(world)
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
            world.combat.has_sword = training
            for pickup in world.combat.pickups:
                pickup.collected = training
            base_yaw = player.yaw
            timings = []
            for frame in range(frames + 5):
                player.yaw = base_yaw + math.sin(frame * 0.06) * 0.35
                start = time.perf_counter()
                if training:
                    events = world.combat.update(1 / 40)
                    if frame % 20 == 0:
                        events.extend(world.combat.attack(world, player))
                    if audio:
                        for event in events:
                            audio.emit(event)
                if audio:
                    audio.listener = (player.x, player.y, player.yaw)
                    audio.ambient = (0.08, 0.08 if name in ("meadow", "river", "bridge") else 0)
                    if frame % 12 == 0:
                        audio.emit(GameEvent("step_grass" if name == "grass_close" else "step_stone"))
                    if frame % 60 == 1:
                        audio.emit(GameEvent("door_open", player.x + 2, player.y))
                renderer.frame(player, width, height, time_seconds=frame / 40)
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
            "width": width, "height": height, "frames": frames, "audio": with_audio, "scenarios": results}
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
    parser.add_argument("--extra-scenes", action="store_true", help="also measure expansion landmarks, combat, close trees and river views")
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
        keys = ("width", "height", "frames", "python", "platform", "machine", "processor", "audio")
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

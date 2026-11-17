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


SCENARIOS = {'indoors': {'x': 128.5, 'y': 76.5, 'yaw': 1.5707963267948966, 'z': 1},
 'courtyard': {'x': 128.5, 'y': 88.5, 'yaw': 1.5707963267948966, 'z': 1},
 'meadow': {'x': 128.5, 'y': 64.5, 'yaw': 1.5707963267948966, 'pitch': -0.06, 'z': 1},
 'grass_close': {'x': 85.5, 'y': 77.5, 'yaw': 1.5707963267948966, 'pitch': -0.35, 'z': 1},
 'bridge': {'x': 88.5, 'y': 218.5, 'yaw': 1.5707963267948966, 'pitch': -0.1, 'z': 1},
 'river': {'x': 8.5, 'y': 212.41284764356448, 'z': 0.12, 'yaw': 0, 'pitch': -0.1}}

EXTRA_SCENARIOS = {'ruins': {'x': 71.5, 'y': 240, 'yaw': 1.5707963267948966, 'pitch': -0.06, 'z': 1},
 'lodge': {'x': 289.5, 'y': 132.5, 'yaw': 0, 'pitch': -0.06, 'z': 7},
 'east_bridge': {'x': 304.5, 'y': 207.5, 'yaw': 1.5707963267948966, 'pitch': -0.1, 'z': 1},
 'watchstones': {'x': 41.5, 'y': 239, 'yaw': 1.5707963267948966, 'pitch': -0.06, 'z': 1},
 'warden': {'x': 41.5, 'y': 246.5, 'yaw': 1.5707963267948966, 'pitch': -0.06, 'z': 1},
 'staff': {'x': 68.5, 'y': 246.5, 'yaw': 1.5707963267948966, 'pitch': -0.06, 'z': 1},
 'fireballs': {'x': 115.5, 'y': 86.5, 'yaw': 1.5707963267948966, 'z': 1},
 'map': {'x': 128.5, 'y': 88.5, 'yaw': 1.5707963267948966, 'z': 1},
 'training': {'x': 115.5, 'y': 92.2, 'yaw': 1.5707963267948966, 'z': 1},
 'tree_close': {'x': 85.5, 'y': 80.0, 'yaw': 1.5707963267948966, 'pitch': -0.35, 'z': 1},
 'tree_canopy': {'x': 85.5, 'y': 79.95, 'z': 2.25, 'yaw': 1.5707963267948966, 'pitch': 0.65},
 'river_diagonal': {'x': 70.5,
                    'y': 217.02662981949743,
                    'z': 0.12,
                    'yaw': 0.7853981633974483,
                    'pitch': -0.25},
 'river_upstream': {'x': 70.5,
                    'y': 217.02662981949743,
                    'z': 0.12,
                    'yaw': 3.141592653589793,
                    'pitch': -0.25},
 'castle_exterior': {'x': 93.5, 'y': 62.5, 'yaw': 0.6, 'pitch': 0.08, 'z': 1},
 'great_hall': {'x': 128.5, 'y': 111.5, 'yaw': 1.5707963267948966, 'pitch': 0.12, 'z': 1},
 'wall_walk': {'x': 108.5, 'y': 91.5, 'z': 6, 'yaw': 1.5707963267948966, 'pitch': -0.15},
 'west_meadow': {'x': 85.5, 'y': 104.5, 'yaw': 1.5707963267948966, 'pitch': -0.1, 'z': 1},
 'east_meadow': {'x': 164.5, 'y': 114.5, 'yaw': 1.5707963267948966, 'pitch': -0.1, 'z': 1}}

TERRAIN_SCENARIOS = {'ridge_approach': {'x': 289.5, 'y': 132.5, 'z': 7, 'yaw': 0, 'pitch': 0.05},
 'ridge_upper': {'x': 304.5, 'y': 132.5, 'z': 12, 'yaw': 0, 'pitch': -0.1},
 'ridge_roof': {'x': 304.5, 'y': 132.5, 'z': 22, 'yaw': 0.8, 'pitch': -0.15},
 'highlands': {'x': 320.5, 'y': 170.5, 'yaw': 1.4, 'pitch': -0.15},
 'ravine': {'x': 310.5, 'y': 306.5, 'z': 9, 'yaw': 3.141592653589793, 'pitch': -0.25},
 'citadel_approach': {'x': 394.5, 'y': 436.5, 'z': 12, 'yaw': 0, 'pitch': 0.06},
 'citadel_roof': {'x': 420.5, 'y': 436.5, 'z': 27, 'yaw': 3.141592653589793, 'pitch': -0.2},
 'highland_map': {'x': 420.5, 'y': 436.5, 'z': 27, 'yaw': 3.141592653589793},
 'terrace_walk': {'x': 277.5, 'y': 132.5, 'yaw': 0},
 'stair_walk': {'x': 296.5, 'y': 121.5, 'z': 7, 'yaw': 1.5707963267948966}}

# Camera roles follow the same authored transforms as walls, floors and stairs.
from ascii3d.terrain import LANDMARKS
for name, group in (("lodge", EXTRA_SCENARIOS), ("ridge_approach", TERRAIN_SCENARIOS),
                    ("ridge_upper", TERRAIN_SCENARIOS), ("ridge_roof", TERRAIN_SCENARIOS),
                    ("terrace_walk", TERRAIN_SCENARIOS), ("stair_walk", TERRAIN_SCENARIOS)):
    camera = group[name]
    camera["x"], camera["y"] = LANDMARKS[0].to_world(camera["x"], camera["y"])
    camera["yaw"] += LANDMARKS[0].angle


def resolve_camera(world, name, camera, *, natural=False, player_type=Player):
    """Validate a pose before timing; only unraised natural poses follow ground.

    Authored Z values and the original castle roles retain their exact poses.
    Natural terrain cameras without Z use circular support, not point height.
    """
    position = dict(camera)
    if natural and "z" not in position:
        position["z"] = world.surface_height(position["x"], position["y"])
        support_query = getattr(world, "walk_support", None)
        if support_query is not None:
            support = support_query(position["x"], position["y"], position["z"])
            if support is not None:
                position["z"] = support[0]
    player = player_type(**position)
    position.setdefault("z", player.z)
    if world.collides(player.x, player.y, player.z):
        raise ValueError(f"Benchmark camera intersects geometry: {name} at "
                         f"({player.x}, {player.y}, {player.z})")
    return position



def run(frames=90, width=120, height=40, with_audio=False, extra_scenes=False, terrain_scenes=False):
    world = build_world()
    renderer = Renderer(world)
    soundscape = Soundscape(world)
    results = {}
    scenes = {**SCENARIOS, **EXTRA_SCENARIOS} if extra_scenes else dict(SCENARIOS)
    if terrain_scenes:
        scenes.update(TERRAIN_SCENARIOS)
    scenes = {name: resolve_camera(world, name, camera, natural=name in TERRAIN_SCENARIOS)
              for name, camera in scenes.items()}
    with ExitStack() as stack:
        audio = None
        if with_audio:
            from ascii3d.sound import Audio
            from ascii3d.events import GameEvent
            audio = stack.enter_context(Audio(volume=0.25))
            if not audio.available:
                raise OSError(audio.error)
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
            walking = name in ("terrace_walk", "stair_walk")
            if casting:
                world.combat.held_item = WeaponPickup(0, 0, weapon=FIRE_STAFF)
            world.combat.cooldown = world.combat.swing_remaining = 0.0
            base_yaw = player.yaw
            timings = []
            for frame in range(frames + 5):
                player.yaw = base_yaw if walking else base_yaw + math.sin(frame * 0.06) * 0.35
                start = time.perf_counter()
                if training or casting or walking or name == "warden":
                    events = []
                    for _ in range(3):
                        if walking:
                            player.update(world, {"w"}, 1 / 120)
                            events.extend(player.events)
                        events.extend(world.combat.update(1 / 120, world, player))
                    if (training or casting) and frame % 20 == 0:
                        events.extend(world.combat.attack(world, player))
                    if audio:
                        for event in events:
                            audio.emit(event)
                if audio:
                    audio.listener = (player.x, player.y, player.yaw)
                    audio.ambient = soundscape.at(player.x, player.y, player.yaw, player.z)
                    if not walking and frame % 12 == 0:
                        audio.emit(GameEvent("step_grass" if name == "grass_close" else "step_stone"))
                    if not walking and frame % 60 == 1:
                        audio.emit(GameEvent("door_open", player.x + 2, player.y))
                renderer.frame(player, width, height, time_seconds=frame / 40,
                               show_map=name in ("map", "highland_map"))
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
    parser.add_argument("--terrain-scenes", action="store_true", help="also measure elevated terrain, upper floors, rooftops and the highland map")
    args = parser.parse_args()
    if args.frames < 20 or not (60 <= args.width <= 300 and 20 <= args.height <= 120):
        parser.error("use at least 20 frames and dimensions between 60x20 and 300x120")
    if not math.isfinite(args.max_regression) or args.max_regression < 0:
        parser.error("--max-regression must be a finite, nonnegative percentage")
    if args.save and args.save.exists():
        parser.error("--save must name an unused report path")
    try:
        report = run(args.frames, args.width, args.height, args.audio, args.extra_scenes, args.terrain_scenes)
    except (OSError, ValueError) as error:
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
        with args.save.open("x", encoding="utf-8") as destination:
            destination.write(json.dumps(report, indent=2) + "\n")
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

"""Optional hardware-GPU static-geometry prototype, independent of game launch.

This is a feasibility/accuracy experiment, not a replacement renderer or FPS
acceptance benchmark. It excludes dynamic panels, actors, vegetation and HUD.
GPU timings include dispatch and synchronous readback. Float32 candidates are
also refined in Python's float64 and compared with the existing CPU renderer.
"""

import argparse
from array import array
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import struct
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ascii3d.gpu_renderer import StaticGPU, camera_rays, voxel_data, decode, refine, choose_raw
from ascii3d.combat import CombatState
from ascii3d.events import GameEvent
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.sound import Audio
from ascii3d.soundscape import Soundscape
from ascii3d.world import WATER, WATER_LEVEL, build_world
from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS, resolve_camera
from tools.benchmark_pair import audio_health, hashes, save_report
















def exact_static_hit(world, origin, direction):
    """Independent exact voxel DDA plus the shared analytic reference.

    Used only for accuracy checks, outside both rendering timing intervals.
    Trees/panels/actors belong to separate passes and are excluded by design.
    """
    cell = [math.floor(value) for value in origin]
    step = [1 if value >= 0 else -1 for value in direction]
    delta = [abs(1 / value) if abs(value) > 1e-12 else 1e30 for value in direction]
    side = [((cell[a] + 1 - origin[a]) if step[a] > 0 else (origin[a] - cell[a])) * delta[a]
            for a in range(3)]
    voxel = None
    for _ in range(110):
        axis = 0 if side[0] <= side[1] and side[0] <= side[2] else (1 if side[1] <= side[2] else 2)
        distance = side[axis]
        side[axis] += delta[axis]
        cell[axis] += step[axis]
        if distance > 48 or not (0 <= cell[0] < world.width and 0 <= cell[1] < world.depth and 0 <= cell[2] < world.height):
            break
        material = world.get(*cell)
        if material == WATER:
            water = (WATER_LEVEL - origin[2]) / direction[2] if direction[2] < -1e-12 else -1
            if distance - 1e-8 <= water <= min(side) + 1e-8:
                distance = water
            else:
                material = 0
        if material:
            voxel = distance, material, None
            break
    analytic = world.geometry_hit(origin, direction, min(48, voxel[0] + 1e-8) if voxel else 48)
    if analytic is not None and (voxel is None or analytic.distance <= voxel[0] + 1e-8):
        return analytic.distance, analytic.material, analytic.normal
    return voxel


def glyphs(hits, width, height):
    # Deliberately simple prototype presentation; production textures, panels,
    # actors, vegetation, HUD and lighting remain in the CPU game renderer.
    ramp = ' .,:;!+=*#%@'
    characters = []
    for hit in hits:
        distance, material = hit[:2]
        if not material:
            characters.append(' ')
        elif material in (5, 9):
            characters.append('.' if material == 5 else ',')
        elif material == WATER:
            characters.append('~')
        else:
            characters.append(ramp[max(1, min(len(ramp) - 1, int(9 - distance * 0.12)))])
    return [''.join(characters[y * width:(y + 1) * width]) for y in range(height)]


def summary(values):
    ordered = sorted(values)
    return {'mean_ms': statistics.mean(values), 'p95_ms': ordered[math.ceil(len(ordered) * 0.95) - 1],
            'samples_ms': values}


def main():
    cameras = {**SCENARIOS, **EXTRA_SCENARIOS, **TERRAIN_SCENARIOS}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes', nargs='+', choices=tuple(cameras), default=['warden', 'highlands', 'ridge_upper', 'stair_walk'])
    parser.add_argument('--all-scenes', action='store_true')
    parser.add_argument('--width', type=int, default=120)
    parser.add_argument('--height', type=int, default=40, help='full frame height; five HUD rows reserved for comparison')
    parser.add_argument('--frames', type=int, default=60)
    parser.add_argument('--backend', choices=('Vulkan', 'D3D12'))
    parser.add_argument('--audio', action='store_true')
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--save', type=Path)
    args = parser.parse_args()
    if not (60 <= args.width <= 300 and 20 <= args.height <= 120) or args.frames < 1:
        parser.error('use dimensions from 60x20 to 300x120 and a positive frame count')
    if args.all_scenes:
        args.scenes = list(cameras)
    if args.snapshot and args.save:
        parser.error('--snapshot prints one frame; omit --save')
    if not args.snapshot and args.save is None:
        parser.error('--save is required for a benchmark')
    report = {'method': 'static-geometry GPU feasibility only; query timing includes synchronous readback',
              'scope': 'no dynamic doors, actors, vegetation, HUD or production texture/lighting parity',
              'python': platform.python_version(), 'width': args.width, 'height': args.height,
              'frames': args.frames, 'audio': args.audio, 'scenes': {}, 'errors': [], 'complete': False,
              'hashes': hashes(Path(__file__).resolve().parents[1]),
              'prototype_hashes': {name: hashlib.sha256((Path(__file__).with_name(name) if name.endswith('.py') else Path(__file__).resolve().parents[1] / 'ascii3d' / name).read_bytes()).hexdigest()
                                   for name in ('gpu_prototype.py', 'gpu_static.wgsl')}}
    if args.save:
        save_report(args.save, report, initial=True)
    gpu = None
    try:
        started = time.perf_counter()
        world = build_world()
        # Isolate the same static scene for both paths. No game state is saved.
        world.doors, world.combat = [], CombatState()
        cpu = Renderer(world, combat_depth_prepass=False)
        cpu.prepare_world()
        gpu = StaticGPU(world, args.backend)
        report.update(adapter=dict(gpu.adapter.info), wgpu=gpu.wgpu.__version__,
                      setup_ms=(time.perf_counter() - started) * 1000)
        soundscape = Soundscape(world)
        with ExitStack() as stack:
            audio = stack.enter_context(Audio(volume=0.25)) if args.audio else None
            if audio is not None and not audio.available:
                raise OSError(audio.error or 'Audio output unavailable')
            for name in args.scenes:
                position = resolve_camera(world, name, cameras[name], natural=name in TERRAIN_SCENARIOS)
                player = Player(**position)
                yaw = player.yaw
                metrics = {key: [] for key in ('gpu_query_readback', 'decode', 'refine', 'ascii', 'cpu_static_scene')}
                checks = {'pixels': 0, 'coverage_mismatches': 0, 'material_mismatches': 0, 'normal_mismatches': 0,
                          'cpu_reference_depth_mismatches': 0, 'raw_depth_errors_over_1e_7': 0,
                          'refined_depth_errors_over_1e_7': 0, 'invalid_candidates': 0,
                          'max_raw_depth_error': 0.0, 'max_refined_depth_error': 0.0,
                          'cpu_field_fallbacks': 0, 'examples': []}
                entry = {'status': 'running', 'position': position, 'checks': checks}
                entry['partial_samples_ms'] = metrics
                report['scenes'][name] = entry
                gpu.resize(args.width, args.height - 5)
                for index in range(args.frames + 5):
                    walking = name in ('terrace_walk', 'stair_walk')
                    player.yaw = yaw if walking else yaw + math.sin(index * 0.06) * 0.35
                    if walking:
                        for _ in range(3):
                            player.update(world, {'w'}, 1 / 120)
                            if audio:
                                for event in player.events:
                                    audio.emit(event)
                    if audio:
                        audio.listener = player.x, player.y, player.yaw
                        audio.ambient = soundscape.at(player.x, player.y, player.yaw, player.z)
                        if not walking and index % 12 == 0:
                            audio.emit(GameEvent('step_stone'))
                    start = time.perf_counter()
                    data = gpu.query(player, args.width, args.height - 5)
                    queried = time.perf_counter()
                    hits = decode(data)
                    decoded = time.perf_counter()
                    directions = list(camera_rays(player, args.width, args.height - 5))
                    origin = player.x, player.y, player.eye_z
                    refined = [refine(world, origin, direction, hit) for direction, hit in zip(directions, hits)]
                    refined_at = time.perf_counter()
                    lines = glyphs([value if value is not None else (1e30, 0) for value in refined],
                                   args.width, args.height - 5)
                    shaded = time.perf_counter()
                    if args.snapshot:
                        print('\n'.join(lines))
                        return 0
                    depths = []

                    def capture(pixels, buffer, *rest):
                        depths.extend(value for row in buffer for value in row)

                    with patch.object(cpu.scenery, 'draw', side_effect=capture):
                        cpu.scene(player, args.width, args.height - 5, index / 40)
                    ended = time.perf_counter()
                    if index >= 5:
                        for key, elapsed in zip(metrics, (queried - start, decoded - queried, refined_at - decoded,
                                                         shaded - refined_at, ended - shaded)):
                            metrics[key].append(elapsed * 1000)
                    if index in (5, 20, args.frames + 4):
                        for pixel, (hit, exact, expected) in enumerate(zip(hits, refined, depths)):
                            checks['cpu_field_fallbacks'] += (hit[6] & 255) == 5
                            hit = choose_raw(hit)
                            reference = exact_static_hit(world, origin, directions[pixel])
                            checks['pixels'] += 1
                            covered, wanted = bool(hit[1]), math.isfinite(expected)
                            if covered != wanted:
                                checks['coverage_mismatches'] += 1
                            if bool(reference) != wanted or (wanted and abs(reference[0] - expected) > 1e-7):
                                checks['cpu_reference_depth_mismatches'] += 1
                            if reference is not None and exact is not None:
                                checks['material_mismatches'] += reference[1] != exact[1]
                                normal, chosen = reference[2], exact[2]
                                if (normal is None) != (chosen is None) or (normal is not None and chosen is not None
                                        and any(abs(a - b) > 1e-7 for a, b in zip(normal, chosen))):
                                    checks['normal_mismatches'] += 1
                            if covered and wanted:
                                raw_error = abs(hit[0] - expected)
                                checks['max_raw_depth_error'] = max(checks['max_raw_depth_error'], raw_error)
                                checks['raw_depth_errors_over_1e_7'] += raw_error > 1e-7
                            if covered and exact is None:
                                checks['invalid_candidates'] += 1
                            if wanted and exact is not None:
                                error = abs(exact[0] - expected)
                                checks['max_refined_depth_error'] = max(checks['max_refined_depth_error'], error)
                                checks['refined_depth_errors_over_1e_7'] += error > 1e-7
                            if len(checks['examples']) < 8 and (covered != wanted or (wanted and (exact is None or abs(exact[0] - expected) > 1e-7))):
                                checks['examples'].append({'frame': index, 'pixel': pixel, 'gpu': hit[:5],
                                                          'refined': exact, 'cpu_depth': expected if wanted else None})
                entry.update(status='complete', timings={key: summary(values) for key, values in metrics.items()},
                             geometry_accuracy_passed=not any(checks[key] for key in
                                 ('coverage_mismatches', 'refined_depth_errors_over_1e_7', 'invalid_candidates',
                                  'material_mismatches', 'normal_mismatches', 'cpu_reference_depth_mismatches')))
                del entry['partial_samples_ms']
                print(name, json.dumps({key: round(value['mean_ms'], 3) for key, value in entry['timings'].items()}),
                      'accuracy', entry['geometry_accuracy_passed'], flush=True)
                save_report(args.save, report)
            if audio:
                report['audio_health'] = audio_health(audio)
        if audio:
            report['audio_health_after_cleanup'] = audio_health(audio)
            report['audio_health'].update({key: value for key, value in report['audio_health_after_cleanup'].items()
                                           if key != 'available'})
        report['complete'] = True
    except (Exception, KeyboardInterrupt) as error:
        report['errors'].append({'type': type(error).__name__, 'message': str(error)})
        print(type(error).__name__, str(error), file=sys.stderr)
    finally:
        if gpu is not None:
            try:
                gpu.close()
            except Exception as error:
                report['complete'] = False
                report['errors'].append({'type': type(error).__name__, 'message': str(error), 'phase': 'gpu_cleanup'})
        health = report.get('audio_health')
        report['passed'] = (report['complete'] and all(entry.get('geometry_accuracy_passed') for entry in report['scenes'].values())
                            and (not args.audio or bool(health and health['available'] and not health['underruns']
                                                       and not health['recoveries'] and not health['error'])))
        if args.save:
            save_report(args.save, report)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

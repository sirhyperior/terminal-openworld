"""Compare current CPU rendering and terrain rays against explicit frozen source.

Retains the smooth-geometry diagnostic: shared simulated world/presentation,
four evolving poses plus wide/tall views per role, and seeded standalone rays.
These exact comparisons diagnose correctness, not performance acceptance.
"""

import argparse
import hashlib
from pathlib import Path
import random
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ascii3d import combat, combat_render, player, renderer, soundscape, world
from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS, resolve_camera
from tools.benchmark_pair import frame, hashes, load_engine, prepare, save_report, variant


def main(argv=None):
    cameras = {**SCENARIOS, **EXTRA_SCENARIOS, **TERRAIN_SCENARIOS}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-source', type=Path, required=True)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--reference-label', default='explicit frozen source')
    parser.add_argument('--scenes', nargs='+', choices=tuple(cameras), default=list(cameras))
    parser.add_argument('--rays-per-scene', type=int, default=1024)
    args = parser.parse_args(argv)
    if args.rays_per_scene < 0:
        parser.error('--rays-per-scene must be nonnegative')
    args.before_source = args.before_source.resolve()
    if not (args.before_source / 'ascii3d' / '__init__.py').is_file():
        parser.error('--before-source must contain the frozen ascii3d package')
    if args.save.exists():
        parser.error('--save must name an unused report path')
    report = {'method': 'same simulated world, shared combat presentation and Door type; exact CPU frames and pre-scenery depths',
              'reference': args.reference_label, 'before_source': str(args.before_source),
              'before_hashes': hashes(args.before_source), 'after_hashes': hashes(Path(__file__).resolve().parents[1]),
              'scenes': args.scenes, 'rays_per_scene': args.rays_per_scene, 'ray_seed': 92638,
              'pairs': [], 'failures': [], 'errors': [], 'rays': 0,
              'phase': 'startup', 'complete': False, 'passed': False}
    save_report(args.save, report, initial=True)
    current = reference = None
    try:
        frozen = load_engine(args.before_source, 'verify_geometry_before_ascii3d')
        frozen['renderer'].draw_combat = combat_render.draw_combat
        frozen['renderer'].large_opaque_enemy = combat_render.large_opaque_enemy
        frozen['renderer'].Door = renderer.Door
        state = variant(dict(world=world, player=player, renderer=renderer, combat=combat, soundscape=soundscape))
        current = state['renderer']
        reference = frozen['renderer'].Renderer(state['world'])

        def compare(*values, **keywords):
            outputs, depths = [], []
            for render in (reference, current):
                original = render.scenery.draw

                def capture(pixels, buffer, *rest):
                    depths.append([row[:] for row in buffer])
                    return original(pixels, buffer, *rest)

                with patch.object(render.scenery, 'draw', side_effect=capture):
                    outputs.append(render.frame(*values, **keywords))
            entry = {'scene': scene, 'frame': state['frame'], 'width': values[1], 'height': values[2],
                     'pitch': state['player'].pitch, 'yaw': state['player'].yaw,
                     'image_equal': outputs[0] == outputs[1], 'depth_equal': depths[0] == depths[1],
                     'image_sha256': hashlib.sha256('\n'.join(outputs[1]).encode()).hexdigest()}
            report['pairs'].append(entry)
            if not entry['image_equal'] or not entry['depth_equal']:
                report['failures'].append(entry)
            return outputs[1]

        class ComparingRenderer:
            def frame(self, *values, **keywords):
                if state['frame'] in (0, 5, 35, 64):
                    return compare(*values, **keywords)

        state['renderer'] = ComparingRenderer()
        report['phase'] = 'frame_comparison'
        for scene in args.scenes:
            report['current_scene'] = scene
            position = resolve_camera(state['world'], scene, cameras[scene], natural=scene in TERRAIN_SCENARIOS)
            prepare(state, scene, position)
            for _ in range(65):
                frame(state, scene, None, 120, 40, measured=False)
            for width, height, pitch_delta in ((160, 40, 0.25), (80, 60, -0.25)):
                state['player'].pitch = position.get('pitch', 0) + pitch_delta
                compare(state['player'], width, height, time_seconds=state['frame'] / 40)
            save_report(args.save, report)
            print(scene, flush=True)
        if args.rays_per_scene:
            report['phase'] = 'terrain_ray_comparison'
            field = state['world'].heightfield
            frozen_field = frozen['world'].HeightField(field.width, field.depth, field.heights)
            frozen_field.enabled[:] = field.enabled
            frozen_field.materials[:] = field.materials
            rng = random.Random(report['ray_seed'])
            for scene in args.scenes:
                report['current_scene'] = scene
                position = resolve_camera(state['world'], scene, cameras[scene], natural=scene in TERRAIN_SCENARIOS)
                origin = position['x'], position['y'], position['z'] + 1.6
                for index in range(args.rays_per_scene):
                    direction = rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), rng.uniform(-1.5, 1.5)
                    hits = [item.ray_hit(origin, direction, 48) for item in (frozen_field, field)]
                    values = [None if hit is None else (hit.distance, hit.material, hit.normal) for hit in hits]
                    report['rays'] += 1
                    if values[0] != values[1]:
                        report['failures'].append({'scene': scene, 'ray': index, 'results': values})
                save_report(args.save, report)
        report['complete'] = True
    except (Exception, KeyboardInterrupt) as error:
        report['errors'].append({'type': type(error).__name__, 'message': str(error),
                                 'phase': report['phase'], 'scene': report.get('current_scene')})
        print(f"{report['phase']}: {type(error).__name__}: {error}", file=sys.stderr)
    finally:
        for render in (current, reference):
            close = getattr(render, 'close', None)
            if close is not None:
                try:
                    close()
                except Exception as error:
                    report['errors'].append({'type': type(error).__name__, 'message': str(error), 'phase': 'cleanup'})
                    report['complete'] = False
        report['passed'] = report['complete'] and not report['failures'] and not report['errors']
        save_report(args.save, report)
    print('pairs', len(report['pairs']), 'rays', report['rays'], 'failures', len(report['failures']))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

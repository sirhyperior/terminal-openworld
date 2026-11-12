"""Verify complete GPU/CPU game frames, retaining partial or failed evidence."""

import argparse
import hashlib
import math
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ascii3d import combat, player, renderer, soundscape, world
from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS, resolve_camera
from tools.benchmark_pair import frame, hashes, prepare, save_report, variant


def main(argv=None):
    cameras = {**SCENARIOS, **EXTRA_SCENARIOS, **TERRAIN_SCENARIOS}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--scenes', nargs='+', choices=tuple(cameras), default=list(cameras))
    args = parser.parse_args(argv)
    if args.save.exists():
        parser.error('--save must name an unused report path')
    report = {'method': 'same live simulated world, complete production frames; GPU vs CPU',
              'hashes': hashes(Path(__file__).resolve().parents[1]), 'scenes': args.scenes,
              'pairs': [], 'failures': [], 'errors': [], 'phase': 'startup',
              'complete': False, 'passed': False}
    save_report(args.save, report, initial=True)
    reference = current = state = None

    def compare(*values, **keywords):
        outputs, buffers = [], []
        for render in (reference, current):
            original = render.scenery.draw

            def capture(pixels, depths, *rest):
                buffers.append([row[:] for row in depths])
                return original(pixels, depths, *rest)

            with patch.object(render.scenery, 'draw', side_effect=capture):
                outputs.append(render.frame(*values, **keywords))
        coverage = sum(math.isfinite(a) != math.isfinite(b) for left, right in zip(buffers[0], buffers[1])
                       for a, b in zip(left, right))
        error = max((abs(a - b) for left, right in zip(buffers[0], buffers[1]) for a, b in zip(left, right)
                     if math.isfinite(a) and math.isfinite(b)), default=0)
        entry = {'scene': scene, 'frame': state['frame'], 'width': values[1], 'height': values[2],
                 'pitch': state['player'].pitch, 'yaw': state['player'].yaw,
                 'image_equal': outputs[0] == outputs[1], 'depth_bitwise_equal': buffers[0] == buffers[1],
                 'max_depth_error': error, 'coverage_mismatches': coverage,
                 'gpu_stats': current.ray_backend.last_stats if current.ray_backend else None,
                 'image_sha256': hashlib.sha256('\n'.join(outputs[1]).encode()).hexdigest()}
        if not entry['image_equal']:
            entry['image_differences'] = [(y, x, a, b) for y, (left, right) in enumerate(zip(*outputs))
                                          for x, (a, b) in enumerate(zip(left, right)) if a != b][:20]
        report['pairs'].append(entry)
        if not entry['image_equal'] or coverage or error > 1e-7:
            report['failures'].append(entry)
        return outputs[1]

    class ComparingRenderer:
        def frame(self, *values, **keywords):
            if state['frame'] in (0, 5, 35, 64):
                return compare(*values, **keywords)

    try:
        state = variant(dict(world=world, player=player, renderer=renderer, combat=combat, soundscape=soundscape))
        reference = state['renderer']
        current = renderer.Renderer(state['world'], backend='gpu')
        if current.backend_name != 'gpu':
            raise RuntimeError('GPU verification unavailable: ' + current.backend_error)
        report['adapter'] = current.ray_backend.adapter_info
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
        if current.backend_name != 'gpu' or current.backend_error:
            raise RuntimeError('GPU fell back during verification: ' + current.backend_error)
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
                    report['complete'] = False
                    report['errors'].append({'type': type(error).__name__, 'message': str(error), 'phase': 'cleanup'})
        report['passed'] = report['complete'] and not report['failures'] and not report['errors']
        save_report(args.save, report)
    print('pairs', len(report['pairs']), 'failures', len(report['failures']))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

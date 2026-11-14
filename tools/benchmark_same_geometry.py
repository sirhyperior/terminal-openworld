"""Compare frozen/current engines only after validating identical static geometry.

This diagnostic includes all terrain roles as matched pairs. It does not replace
the original historical performance control or relax benchmark_pair's gates.
"""

import argparse
import hashlib
import importlib
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import benchmark_pair as pair
from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS, TERRAIN_SCENARIOS, resolve_camera


def geometry_hash(world):
    """Retain the original CPU diagnostic's voxel/field/solid fingerprint."""
    field = world.heightfield
    if field is None:
        raise ValueError('same-geometry terrain comparisons require a heightfield in both engines')
    digest = hashlib.sha256(world.cells)
    digest.update(field.heights.tobytes())
    digest.update(field.enabled)
    digest.update(field.materials)
    digest.update(repr([(box.x0, box.y0, box.z0, box.x1, box.y1, box.z1, box.material,
                        getattr(box, 'stair', False), getattr(box, 'vertices', ()), getattr(box, 'faces', ()))
                        for box in world.solids]).encode())
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-source', type=Path, required=True)
    parser.add_argument('--save', type=Path, required=True)
    parser.add_argument('--reference-label', default='explicit frozen source')
    parser.add_argument('--before-renderer', choices=('cpu', 'gpu'), default='cpu')
    parser.add_argument('--after-renderer', choices=('cpu', 'gpu', 'auto'), default='cpu')
    parser.add_argument('--frames', type=int, default=60)
    parser.add_argument('--width', type=int, default=120)
    parser.add_argument('--height', type=int, default=40)
    parser.add_argument('--audio', action='store_true')
    args = parser.parse_args(argv)
    if args.frames < 20 or args.frames % 2 or not (60 <= args.width <= 300 and 20 <= args.height <= 120):
        parser.error('use an even frame count >=20 and dimensions from 60x20 to 300x120')
    if args.save.exists():
        parser.error('--save must name an unused report path')
    args.before_source = args.before_source.resolve()
    if not (args.before_source / 'ascii3d' / '__init__.py').is_file():
        parser.error('--before-source must contain the frozen ascii3d package')
    args.before_elevated_audio = True
    before = after = None
    report = {'method': 'same-geometry preflight followed by benchmark_pair ABBA',
              'control': args.reference_label, 'complete': False, 'passed': False,
              'phase': 'startup', 'status': 'preparing', 'errors': [],
              'before_hashes': pair.hashes(args.before_source),
              'after_hashes': pair.hashes(Path(__file__).resolve().parents[1])}
    save_owned_report = pair.save_report
    save_owned_report(args.save, report, initial=True)

    def update_reserved_report(path, value, *, initial=False):
        # This helper already reserved this run's unused path before setup.
        # benchmark_pair may update that reservation, never another run's file.
        if Path(path).resolve() != args.save.resolve():
            raise ValueError('paired benchmark attempted to write outside its reserved report')
        save_owned_report(path, value)

    phase = 'startup'
    try:
        before = pair.variant(pair.load_engine(args.before_source, 'same_geometry_before_ascii3d'),
                              args.width, args.height, renderer_backend=args.before_renderer)
        after = pair.variant({name: importlib.import_module(f'ascii3d.{name}') for name in before['engine']},
                             args.width, args.height, renderer_backend=args.after_renderer)
        phase = 'geometry_preflight'
        fingerprints = {label: geometry_hash(state['world'])
                        for label, state in (('before', before), ('after', after))}
        sizes = [(state['world'].width, state['world'].depth, state['world'].height)
                 for state in (before, after)]
        if sizes[0] != sizes[1] or fingerprints['before'] != fingerprints['after']:
            raise ValueError('frozen/current static geometry differs; use the historical paired benchmark instead')
        cameras = {}
        for name, camera in {**SCENARIOS, **EXTRA_SCENARIOS, **TERRAIN_SCENARIOS}.items():
            poses = [resolve_camera(state['world'], name, camera, natural=name in TERRAIN_SCENARIOS,
                                    player_type=state['engine']['player'].Player) for state in (before, after)]
            if poses[0] != poses[1]:
                raise ValueError(f'frozen/current camera poses differ: {name}')
            cameras[name] = poses[0]
        phase = 'paired_measurement'
        with patch.object(pair, 'SCENARIOS', cameras), patch.object(pair, 'EXTRA_SCENARIOS', {}), \
                patch.object(pair, 'TERRAIN_SCENARIOS', {}), \
                patch.object(pair, 'save_report', side_effect=update_reserved_report):
            report = pair.run(args, before=before, after=after)
        report['control'] = f'{args.reference_label}; same-geometry diagnostic, not historical acceptance'
        report['geometry_sha256'] = fingerprints
        report['geometry_hash_fields'] = ['voxel cells', 'field vertices/enabled/materials',
                                         'solid bounds/materials/stair markers/vertices/faces']
        save_owned_report(args.save, report)
    except (Exception, KeyboardInterrupt) as error:
        report.update(complete=False, passed=False, phase=phase, status='incomplete')
        report['errors'].append({'type': type(error).__name__, 'message': str(error), 'phase': phase})
        print(f'{phase}: {type(error).__name__}: {error}', file=sys.stderr)
    finally:
        for state in (before, after):
            close = getattr(state['renderer'], 'close', None) if state is not None else None
            if close is not None:
                try:
                    close()
                except Exception as error:
                    report.update(complete=False, passed=False, status='incomplete')
                    report['errors'].append({'type': type(error).__name__, 'message': str(error), 'phase': 'cleanup'})
        save_owned_report(args.save, report)
    print('Saved', args.save, report['status'], report.get('failed', []))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

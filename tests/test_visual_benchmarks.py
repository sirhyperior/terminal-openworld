"""Visual comparisons retain backend identity and explicit changed-map poses."""

from array import array
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ascii3d.player import Player
from tools import benchmark_pair as pair
from tools.benchmark_same_geometry import geometry_hash


class VisualBenchmarkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'ascii3d').mkdir()
        (self.root / 'ascii3d' / 'world.py').write_text('# frozen\n', encoding='utf-8')
        self.args = SimpleNamespace(before_source=self.root, save=self.root / 'result.json',
                                    frames=4, width=120, height=40, audio=False,
                                    before_elevated_audio=True, before_renderer='cpu', after_renderer='cpu')
        self.prepared = []

    def state(self, label, backend='cpu'):
        world = SimpleNamespace(width=20, depth=20, height=10,
                                collides=lambda x, y, z: False)
        return {'label': label, 'world': world, 'engine': {'player': SimpleNamespace(Player=Player)},
                'startup': {}, 'renderer': SimpleNamespace(backend_name=backend, backend_error='',
                                                           scenery=SimpleNamespace(stats={}))}

    def prepare(self, state, name, pose):
        self.prepared.append((state['label'], name, pose))
        state['timings'] = []

    @staticmethod
    def frame(state, name, audio, width, height, *, measured):
        if measured:
            state['timings'].append(10.0)

    def run_pair(self, before=None, after=None, frame=None):
        with patch.object(pair, 'SCENARIOS', {'indoors': {'x': 2, 'y': 3, 'z': 1}}), \
                patch.object(pair, 'EXTRA_SCENARIOS', {}), patch.object(pair, 'TERRAIN_SCENARIOS', {}), \
                patch('sys.stdout', io.StringIO()):
            return pair.run(self.args, before=before or self.state('before'), after=after or self.state('after'),
                            prepare_scene=self.prepare, run_frame=frame or self.frame)

    def manifest(self, roles):
        path = self.root / 'roles.json'
        path.write_text(json.dumps({'version': 1, 'roles': roles}), encoding='utf-8')
        return path

    def test_explicit_before_gpu_rejects_silent_cpu_before_any_measurement(self):
        self.args.before_renderer = 'gpu'
        frame = Mock()
        report = self.run_pair(frame=frame)
        frame.assert_not_called()
        self.assertFalse(report['complete'] or report['passed'])
        self.assertIn('before_backend', report['failed'])
        self.assertEqual(report['before_renderer_health']['backend'], 'cpu')

    def test_gpu_to_gpu_records_both_actual_and_requested_backends(self):
        self.args.before_renderer = self.args.after_renderer = 'gpu'
        report = self.run_pair(self.state('before', 'gpu'), self.state('after', 'gpu'))
        self.assertTrue(report['passed'])
        self.assertEqual(report['requested_renderers'], {'before': 'gpu', 'after': 'gpu'})
        self.assertEqual(report['renderer_backends'], {'before': 'gpu', 'after': 'gpu'})

    def test_before_device_loss_after_measurement_invalidates_complete_result(self):
        self.args.before_renderer = 'gpu'
        before = self.state('before', 'gpu')

        def frame(state, *args, **keywords):
            self.frame(state, *args, **keywords)
            if keywords['measured'] and len(state['timings']) == 4 and state is before:
                state['renderer'].backend_name = 'cpu'
                state['renderer'].backend_error = 'device lost'

        report = self.run_pair(before=before, frame=frame)
        self.assertFalse(report['passed'] or report['complete'])
        self.assertEqual(report['scenarios']['indoors']['before']['sample_count'], 4)
        self.assertIn('before_backend', report['failed'])

    def test_changed_map_manifest_uses_separate_explicit_poses_and_labels_comparison(self):
        roles = {'indoors': {'before': {'x': 2, 'y': 3, 'z': 1},
                              'after': {'x': 12, 'y': 13, 'z': 4, 'yaw': 1.2}}}
        self.args.role_manifest = self.manifest(roles)
        report = self.run_pair()
        self.assertTrue(report['passed'])
        self.assertIn('changed geometry', report['comparison'])
        self.assertEqual(report['preflight']['indoors'], roles['indoors'])
        self.assertEqual([pose['x'] for _, _, pose in self.prepared], [2, 12])
        self.assertEqual(report['new_scenarios'], {})
        self.assertEqual(report['threshold_percent'], 15.0)
        self.assertEqual(len(report['role_manifest']['sha256']), 64)

    def test_manifest_rejects_missing_z_nonfinite_values_and_unknown_roles(self):
        cases = [
            {'indoors': {'before': {'x': 2, 'y': 3}, 'after': {'x': 2, 'y': 3, 'z': 1}}},
            {'indoors': {'before': {'x': float('nan'), 'y': 3, 'z': 1},
                         'after': {'x': 2, 'y': 3, 'z': 1}}},
            {'invented': {'before': {'x': 2, 'y': 3, 'z': 1}, 'after': {'x': 2, 'y': 3, 'z': 1}}},
        ]
        for roles in cases:
            with self.subTest(roles=roles), self.assertRaises(ValueError):
                pair.load_role_manifest(self.manifest(roles))

    def test_cli_defaults_before_to_cpu_and_accepts_explicit_gpu(self):
        result = {'passed': True, 'status': 'passed', 'failed': [], 'errors': []}
        for backend in ('cpu', 'gpu'):
            arguments = ['--before-source', str(self.root), '--save', str(self.args.save)]
            if backend == 'gpu':
                arguments += ['--before-renderer', 'gpu']
            with patch.object(pair, 'run', return_value=result) as run, patch('sys.stdout', io.StringIO()):
                self.assertEqual(pair.main(arguments), 0)
                self.assertEqual(run.call_args.args[0].before_renderer, backend)

    def test_geometry_fingerprint_distinguishes_convex_shapes_with_equal_bounds(self):
        field = SimpleNamespace(heights=array('d', [1, 1, 1, 1]), enabled=bytearray([1]),
                                materials=bytearray([5]))
        shape = SimpleNamespace(x0=0, y0=0, z0=0, x1=1, y1=1, z1=1, material=2,
                                stair=False, vertices=((0, 0, 0), (1, 1, 1)), faces=((0, 1),))
        world = SimpleNamespace(heightfield=field, cells=bytearray([2]), solids=[shape])
        original = geometry_hash(world)
        shape.vertices = ((0, 0, 1), (1, 1, 0))
        self.assertNotEqual(geometry_hash(world), original)


if __name__ == '__main__':
    unittest.main()

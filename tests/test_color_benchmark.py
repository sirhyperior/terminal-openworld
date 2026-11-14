"""Styled benchmarks measure serialization explicitly and retain raw payloads."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ascii3d.player import Player
from tools import benchmark_pair as pair, benchmark_same_geometry as same


class ColorBenchmarkTests(unittest.TestCase):
    @staticmethod
    def frame_state(presentation='styled', mode='color', encoded=None):
        rows = ['\x1b[38;2;1;2;3mx\x1b[97;40m', '  '] if encoded is None else encoded
        renderer = SimpleNamespace(frame=Mock(),
            styled_frame=Mock(return_value=SimpleNamespace(ansi_rows=Mock(return_value=rows))),
            scenery=SimpleNamespace(stats={}))
        player = Player(x=2, y=3, yaw=0)
        return dict(player=player, world=SimpleNamespace(), frame=0, yaw=0,
                    training=False, casting=False, walking=False, timings=[], serialized_bytes=[],
                    renderer=renderer, presentation=presentation, color_mode=mode)

    def test_styled_path_serializes_inside_timer_and_counts_only_measured_frames(self):
        state = self.frame_state()
        with patch.object(pair.time, 'perf_counter', side_effect=(10, 10.006, 20, 20.007)):
            pair.frame(state, 'indoors', None, 60, 20, measured=False)
            pair.frame(state, 'indoors', None, 60, 20, measured=True)
        state['renderer'].frame.assert_not_called()
        self.assertEqual(state['renderer'].styled_frame.call_count, 2)
        self.assertEqual(state['renderer'].styled_frame.call_args.kwargs['color_mode'], 'color')
        self.assertEqual(state['renderer'].styled_frame.return_value.ansi_rows.call_count, 2)
        self.assertAlmostEqual(state['timings'][0], 7)
        expected = sum(len(row) for row in state['renderer'].styled_frame.return_value.ansi_rows.return_value)
        self.assertEqual(state['serialized_bytes'], [expected])

    def test_plain_path_preserves_original_render_call_and_omits_payload_metrics(self):
        state = self.frame_state(presentation='plain')
        pair.frame(state, 'indoors', None, 60, 20, measured=True)
        state['renderer'].frame.assert_called_once()
        state['renderer'].styled_frame.assert_not_called()
        self.assertEqual(state['serialized_bytes'], [])
        self.assertNotIn('serialized_row_bytes', pair.summarize(state))

    def test_mono_fallback_list_is_timed_without_ansi_method(self):
        state = self.frame_state(mode='mono')
        state['renderer'].styled_frame.return_value = ['abc', 'def']
        pair.frame(state, 'indoors', None, 60, 20, measured=True)
        self.assertEqual(state['serialized_bytes'], [6])
        self.assertEqual(state['renderer'].styled_frame.call_args.kwargs['color_mode'], 'mono')

    def test_payload_summary_preserves_raw_samples_mean_and_p95(self):
        state = self.frame_state()
        state['timings'] = [10, 20, 30, 40]
        state['serialized_bytes'] = [100, 400, 200, 300]
        self.assertEqual(pair.summarize(state)['serialized_row_bytes'], {
            'mean_bytes': 250, 'p95_bytes': 400, 'sample_count': 4,
            'samples_bytes': [100, 400, 200, 300]})

    def test_cli_defaults_keep_plain_historical_mode_and_accept_styled_modes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            args = ['--before-source', directory, '--save', str(Path(directory) / 'report.json')]
            result = dict(passed=True, status='passed', failed=[], errors=[])
            for flags, expected in (([], ('plain', 'gray', 'color')),
                    (['--presentation', 'styled', '--before-color-mode', 'mono', '--after-color-mode', 'gray'],
                     ('styled', 'mono', 'gray'))):
                with patch.object(pair, 'run', return_value=result) as run, redirect_stdout(io.StringIO()):
                    self.assertEqual(pair.main(args + flags), 0)
                actual = run.call_args.args[0]
                self.assertEqual((actual.presentation, actual.before_color_mode, actual.after_color_mode), expected)

    def test_styled_report_keeps_explicit_modes_and_raw_payloads_per_variant(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root / 'ascii3d').mkdir()
            (root / 'ascii3d' / 'world.py').write_text('# frozen\n')
            args = SimpleNamespace(before_source=root, save=root / 'report.json', frames=4,
                width=120, height=40, audio=False, before_elevated_audio=True,
                presentation='styled', before_color_mode='gray', after_color_mode='color')
            states = []
            for label in ('before', 'after'):
                states.append(dict(label=label, engine={'player': SimpleNamespace(Player=Player)},
                    world=SimpleNamespace(width=20, depth=20, height=10, collides=lambda *a: False),
                    renderer=SimpleNamespace(styled_frame=Mock(), scenery=SimpleNamespace(stats={})), startup={}))

            def prepare(state, *args):
                state['timings'] = []

            def frame(state, *args, measured):
                if measured:
                    state['timings'].append(10)
                    state['serialized_bytes'].append(100 if state['color_mode'] == 'gray' else 150)

            with patch.object(pair, 'SCENARIOS', {'indoors': {'x': 2, 'y': 3, 'z': 1}}), \
                    patch.object(pair, 'EXTRA_SCENARIOS', {}), patch.object(pair, 'TERRAIN_SCENARIOS', {}), \
                    redirect_stdout(io.StringIO()):
                report = pair.run(args, before=states[0], after=states[1], prepare_scene=prepare, run_frame=frame)
            self.assertTrue(report['passed'])
            self.assertEqual(report['threshold_percent'], 15)
            self.assertIn('no terminal writes', report['method'])
            self.assertEqual(report['presentation']['color_modes'], {'before': 'gray', 'after': 'color'})
            for label, size in (('before', 100), ('after', 150)):
                self.assertEqual(report['scenarios']['indoors'][label]['serialized_row_bytes']['samples_bytes'], [size] * 4)
            self.assertEqual(json.loads(args.save.read_text()), report)

    def test_same_geometry_wrapper_propagates_styled_flags(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root / 'ascii3d').mkdir()
            (root / 'ascii3d' / '__init__.py').write_text('')
            states = [dict(engine={'player': SimpleNamespace(Player=Player)},
                           world=SimpleNamespace(width=20, depth=20, height=10),
                           renderer=SimpleNamespace(close=lambda: None)) for _ in range(2)]
            args = ['--before-source', str(root), '--save', str(root / 'report.json'),
                    '--presentation', 'styled', '--before-color-mode', 'gray', '--after-color-mode', 'color']
            report = dict(passed=True, complete=True, status='passed', failed=[], errors=[])
            with patch.object(pair, 'variant', side_effect=states), patch.object(pair, 'load_engine', return_value={}), \
                    patch.object(same, 'geometry_hash', return_value='identical'), \
                    patch.object(same, 'resolve_camera', return_value={'x': 2, 'y': 3, 'z': 1}), \
                    patch.object(same, 'SCENARIOS', {'indoors': {'x': 2, 'y': 3, 'z': 1}}), \
                    patch.object(same, 'EXTRA_SCENARIOS', {}), patch.object(same, 'TERRAIN_SCENARIOS', {}), \
                    patch.object(pair, 'run', return_value=report) as run, redirect_stdout(io.StringIO()):
                self.assertEqual(same.main(args), 0)
            parsed = run.call_args.args[0]
            self.assertEqual((parsed.presentation, parsed.before_color_mode, parsed.after_color_mode),
                             ('styled', 'gray', 'color'))


if __name__ == '__main__':
    unittest.main()

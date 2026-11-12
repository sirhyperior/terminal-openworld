"""Startup percentages advance on completed phases and keep headless output clean."""

from contextlib import ExitStack
import io
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ascii3d.app import main
from ascii3d.loading import LoadingProgress, STARTUP_STAGES
from ascii3d.player import Player
from ascii3d.terminal import Keys
from ascii3d.world import FLOOR, World


class TTYText(io.StringIO):
    def isatty(self):
        return True


class LoadingProgressTests(unittest.TestCase):
    def test_completed_stages_reach_100_once_without_timer_progress(self):
        stream = TTYText()
        loading = LoadingProgress(stream, True)
        loading.start()
        initial = stream.getvalue()
        self.assertIn('0%', initial)
        self.assertNotIn('100%', initial)
        for _ in STARTUP_STAGES:
            loading.advance()
        loading.advance()
        loading.close()
        self.assertEqual([int(value) for value in re.findall(r'(\d+)%', stream.getvalue())],
                         [0, 16, 33, 50, 66, 83, 100])
        self.assertIn('100% | MONOLITH: Ready', stream.getvalue())
        self.assertTrue(stream.getvalue().endswith('\n'))

    def test_interrupted_load_ends_the_line_without_claiming_completion(self):
        stream = TTYText()
        loading = LoadingProgress(stream, True)
        loading.start()
        loading.advance()
        loading.close()
        self.assertNotIn('100%', stream.getvalue())
        self.assertTrue(stream.getvalue().endswith('\n'))

    def test_disabled_display_writes_nothing(self):
        stream = TTYText()
        loading = LoadingProgress(stream, False)
        loading.start()
        for _ in STARTUP_STAGES:
            loading.advance()
        self.assertEqual(stream.getvalue(), '')

    def test_narrow_terminal_keeps_percent_and_avoids_autowrap_column(self):
        stream = TTYText()
        with patch('ascii3d.loading.os.get_terminal_size', return_value=SimpleNamespace(columns=16)):
            stream.fileno = lambda: 1
            loading = LoadingProgress(stream, True)
            loading.start()
            loading.advance()
            loading.close()
        for line in stream.getvalue().strip('\n').split('\r')[1:]:
            self.assertLessEqual(len(line), 15)
            self.assertIn('%', line)


class AppLoadingTests(unittest.TestCase):
    def run_app(self, args=(), *, fail_prepare=False, tty=True):
        output = TTYText() if tty else io.StringIO()
        observed, captures = [], []
        world = World.empty(18, 18, 8)
        world.box(0, 0, 0, 18, 18, 1, FLOOR)
        live_player = Player(x=8.5, y=4.5)
        renderer_closed = []

        def observe(stage):
            observed.append((stage, output.getvalue()))

        def build():
            observe('world')
            return world

        class FakeRenderer:
            def __init__(self, *rest, **kwargs):
                observe('renderer')

            def prepare_world(self):
                observe('surfaces')
                if fail_prepare:
                    raise OSError('preparation failed')

            def frame(self, *rest, **kwargs):
                return ['ASCII frame']

            def close(self):
                renderer_closed.append(True)

        class FakeSoundscape:
            def __init__(self, *rest):
                pass

            def at(self, *rest):
                if not any(stage == 'ambience' for stage, _ in observed):
                    observe('ambience')
                return 0.0, 0.0, 0.0

        class FakeTerminal:
            def __init__(self, *rest):
                self.keyboard = self
                self.mouse_captured = False
                self.mouse_error = ''

            def __enter__(self):
                observe('terminal')
                return self

            def __exit__(self, *rest):
                pass

            def poll(self):
                return Keys(set(), set())

            def size(self):
                return 60, 20

            def set_mouse_capture(self, active):
                captures.append(active)

            def draw(self, lines):
                observe('frame')

        class FakeAudio:
            available = enabled = True

            def __init__(self, *rest):
                pass

            def __enter__(self):
                observe('audio')
                return self

            def __exit__(self, *rest):
                if captures and captures[-1]:
                    raise AssertionError('Mouse must release before audio drains')

            def pause(self, *rest):
                pass

            def emit(self, *rest):
                pass

        clock = iter(index * 0.001 for index in range(100))
        with ExitStack() as stack:
            for name, value in (('sys.stdout', output), ('sys.stderr', io.StringIO()),
                                ('build_world', build), ('spawn_player', lambda outside: live_player),
                                ('Renderer', FakeRenderer), ('Soundscape', FakeSoundscape),
                                ('Terminal', FakeTerminal), ('Audio', FakeAudio),
                                ('time.perf_counter', lambda: next(clock)), ('time.sleep', Mock())):
                stack.enter_context(patch('ascii3d.app.' + name, value))
            status = main(['--renderer', 'cpu', '--keyboard-look', '--frames', '1', *args])
        return status, output.getvalue(), observed, renderer_closed

    def test_interactive_load_reports_each_real_completed_stage_before_play(self):
        status, output, observed, closed = self.run_app()
        self.assertEqual(status, 0)
        expected = [('world', 0), ('renderer', 16), ('surfaces', 33), ('ambience', 50),
                    ('terminal', 66), ('audio', 83), ('frame', 100)]
        self.assertEqual([stage for stage, _ in observed], [stage for stage, _ in expected])
        for (stage, text), (_, percent) in zip(observed, expected):
            with self.subTest(stage=stage):
                self.assertEqual(int(re.findall(r'(\d+)%', text)[-1]), percent)
        self.assertEqual(len(closed), 1)

    def test_failed_preparation_does_not_reach_100_or_start_terminal_audio(self):
        status, output, observed, closed = self.run_app(fail_prepare=True)
        self.assertEqual(status, 1)
        self.assertNotIn('100%', output)
        self.assertTrue(output.endswith('\n'))
        self.assertEqual([stage for stage, _ in observed], ['world', 'renderer', 'surfaces'])
        self.assertEqual(len(closed), 1)

    def test_headless_snapshot_and_benchmark_never_emit_loading_text(self):
        for args in (('--snapshot',), ('--benchmark', '2')):
            with self.subTest(args=args):
                status, output, observed, closed = self.run_app(args)
                self.assertEqual(status, 0)
                self.assertNotIn('Loading', output)
                self.assertNotIn('%', output)
                self.assertEqual(len(closed), 1)
        self.assertEqual(self.run_app(('--snapshot',))[1], 'ASCII frame\n')

    def test_redirected_interactive_output_has_no_progress(self):
        status, output, observed, closed = self.run_app(tty=False)
        self.assertEqual(status, 0)
        self.assertEqual(output, '')

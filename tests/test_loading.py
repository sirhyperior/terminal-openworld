"""Startup percentages advance on completed phases and keep headless output clean."""

from contextlib import ExitStack
from contextlib import contextmanager
import io
import re
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ascii3d.app import main
from ascii3d.loading import (LoadingProgress, STARTUP_STAGES, TIP_INTERVAL,
                             ANIMATION_INTERVAL, TIPS, COMPACT_TIPS)
from ascii3d.player import Player
from ascii3d.terminal import Keys
from ascii3d.world import FLOOR, World


class TTYText(io.StringIO):
    def isatty(self):
        return True


class LoadingProgressTests(unittest.TestCase):
    def test_playable_sizes_keep_complete_bars_and_untruncated_tips(self):
        for columns in (60, 80, 100, 120, 160):
            with self.subTest(columns=columns):
                stream = TTYText()
                stream.fileno = lambda: 1
                clock = [0.0]
                with patch('ascii3d.loading.os.get_terminal_size', return_value=SimpleNamespace(columns=columns)), \
                        patch('ascii3d.loading.threading.Thread'):
                    loading = LoadingProgress(stream, True, clock=lambda: clock[0])
                    loading.start()
                    loading.advance()
                    loading.advance()
                    for index in range(len(TIPS)):
                        clock[0] = index * TIP_INTERVAL
                        with loading.suspend():
                            loading._draw()
                        frame = stream.getvalue().split('\r')[-1].rstrip()
                        self.assertIn('[####--------]', frame)
                        self.assertLessEqual(len(frame), columns - 1)
                        self.assertNotIn('\x1b', frame)
                        if columns >= 80:
                            self.assertTrue(frame.endswith(TIPS[index]) or frame.endswith(COMPACT_TIPS[index]))
                    loading.clear_line()
                    self.assertEqual(stream.getvalue().split('\r')[-1], '')
                    loading.close()

    def test_animation_rotates_tips_and_spinner_without_advancing_percent(self):
        class ObservedText(TTYText):
            def __init__(self):
                super().__init__()
                self.frames = []
                self.rotated = threading.Event()

            def fileno(self):
                return 1

            def write(self, text):
                result = super().write(text)
                if text.startswith('\r'):
                    self.frames.append(text)
                    if TIPS[1] in text:
                        self.rotated.set()
                return result

        stream = ObservedText()
        clock = [0.0]
        with patch('ascii3d.loading.os.get_terminal_size', return_value=SimpleNamespace(columns=160)):
            loading = LoadingProgress(stream, True, clock=lambda: clock[0])
            try:
                loading.start()
                clock[0] = TIP_INTERVAL + ANIMATION_INTERVAL
                self.assertTrue(stream.rotated.wait(2), 'loading animation did not repaint')
                self.assertEqual(loading.completed, 0)
                self.assertIn(TIPS[0], stream.frames[0])
                self.assertIn(TIPS[1], stream.frames[-1])
                self.assertTrue(all('0%' in frame and '[------------]' in frame for frame in stream.frames))
                first, last = stream.frames[0], stream.frames[-1]
                self.assertNotEqual(first[first.index('[') - 2], last[last.index('[') - 2])
            finally:
                loading.close()
        self.assertFalse(loading._worker.is_alive())
        closed = stream.getvalue()
        loading.close()
        loading.advance()
        self.assertEqual(stream.getvalue(), closed)

    def test_disabled_display_starts_no_thread(self):
        with patch('ascii3d.loading.threading.Thread') as thread:
            loading = LoadingProgress(TTYText(), False)
            loading.start()
            loading.advance()
            loading.close()
        thread.assert_not_called()

    def test_failed_flush_still_stops_worker_before_propagating_error(self):
        stream = TTYText()
        loading = LoadingProgress(stream, True)
        loading.start()
        stream.flush = Mock(side_effect=OSError('output gone'))
        with self.assertRaisesRegex(OSError, 'output gone'):
            loading.close()
        self.assertFalse(loading._worker.is_alive())

    def test_empty_terminal_width_never_wraps_or_emits_ansi(self):
        stream = TTYText()
        stream.fileno = lambda: 1
        with patch('ascii3d.loading.os.get_terminal_size', return_value=SimpleNamespace(columns=0)):
            loading = LoadingProgress(stream, True)
            loading.start()
            loading.advance()
            loading.close()
        self.assertEqual(stream.getvalue(), '\r\r\n')

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
    def run_app(self, args=(), *, fail_prepare=False, fail_audio=False, fail_terminal=False,
                interrupt_world=False, tty=True):
        output = TTYText() if tty else io.StringIO()
        self.last_output = output
        observed, captures = [], []
        world = World.empty(18, 18, 8)
        world.box(0, 0, 0, 18, 18, 1, FLOOR)
        live_player = Player(x=8.5, y=4.5)
        renderer_closed = []
        loading_instances = []

        class ObservedLoading(LoadingProgress):
            terminal_transition = False

            def __init__(self, *rest, **kwargs):
                super().__init__(*rest, **kwargs)
                loading_instances.append(self)

            @contextmanager
            def suspend(self):
                with super().suspend():
                    self.terminal_transition = True
                    try:
                        yield
                    finally:
                        self.terminal_transition = False

        def observe(stage):
            observed.append((stage, output.getvalue()))

        def build():
            observe('world')
            if interrupt_world:
                raise KeyboardInterrupt()
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

            styled_frame = frame

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
                if not loading_instances[-1].terminal_transition:
                    raise AssertionError('Terminal entry must hold the loading output barrier')
                observe('terminal')
                if fail_terminal:
                    raise OSError('terminal startup failed')
                return self

            def __exit__(self, *rest):
                loading = loading_instances[-1]
                if not loading._closed or (loading._worker is not None and loading._worker.is_alive()):
                    raise AssertionError('Loading must stop before terminal restoration')

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
                if fail_audio:
                    raise OSError('audio startup failed')
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
                                ('LoadingProgress', ObservedLoading),
                                ('Terminal', FakeTerminal), ('Audio', FakeAudio),
                                ('time.perf_counter', lambda: next(clock)), ('time.sleep', Mock())):
                stack.enter_context(patch('ascii3d.app.' + name, value))
            try:
                status = main(['--renderer', 'cpu', '--keyboard-look', '--frames', '1', *args])
            finally:
                self.last_loading = loading_instances[-1] if loading_instances else None
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

    def test_audio_entry_failure_stops_animation_before_terminal_restoration(self):
        status, output, observed, closed = self.run_app(fail_audio=True)
        self.assertEqual(status, 1)
        self.assertNotIn('100%', output)
        self.assertEqual(observed[-1][0], 'audio')
        self.assertTrue(self.last_loading._closed)
        self.assertFalse(self.last_loading._worker.is_alive())
        self.assertEqual(closed, [True])

    def test_terminal_entry_failure_stops_animation_without_claiming_ready(self):
        status, output, observed, closed = self.run_app(fail_terminal=True)
        self.assertEqual(status, 1)
        self.assertNotIn('100%', output)
        self.assertEqual(observed[-1][0], 'terminal')
        self.assertTrue(self.last_loading._closed)
        self.assertFalse(self.last_loading._worker.is_alive())
        self.assertEqual(closed, [True])

    def test_interrupted_world_build_stops_animation_without_claiming_ready(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_app(interrupt_world=True)
        self.assertNotIn('100%', self.last_output.getvalue())
        self.assertTrue(self.last_loading._closed)
        self.assertFalse(self.last_loading._worker.is_alive())

"""Gameplay diagnostics observe completed work without changing normal clocks."""

from contextlib import ExitStack
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from ascii3d.app import main
from ascii3d.frame_timing import FrameTiming
from ascii3d.terminal import Keys


class FrameTimingTests(unittest.TestCase):
    def play(self, path, *, collect=True, interrupt_sleep=False):
        clock = 0.0

        def advance(seconds):
            nonlocal clock
            clock += seconds

        def sleep(seconds):
            if interrupt_sleep:
                advance(seconds / 2)
                raise KeyboardInterrupt
            advance(seconds + 0.005)

        def ensure_deferred(*args):
            self.assertFalse(path.exists())

        terminal = MagicMock()
        terminal.__enter__.return_value = terminal
        terminal.__exit__.side_effect = ensure_deferred
        terminal._terminal_size = (240, 80)
        terminal.size.return_value = (160, 50)
        terminal.keyboard.poll.side_effect = iter((Keys(set(), {"f"}), Keys()))
        poll = terminal.keyboard.poll

        def timed_poll():
            advance(0.003)
            return poll()

        terminal.keyboard.poll = timed_poll
        terminal.set_mouse_capture.side_effect = lambda active: advance(0.001)

        def draw(frame):
            ensure_deferred()
            advance(0.002)
            terminal.output_timing = (0.0005, 0.0015, 512)

        terminal.draw.side_effect = draw
        renderer = Mock(backend_name="native", ray_backend=None)
        renderer.styled_frame.side_effect = lambda *args, **kwargs: advance(0.007)
        audio = MagicMock(enabled=True, available=True)
        audio.__enter__.return_value = audio
        audio.__exit__.side_effect = ensure_deferred
        audio.pause.side_effect = lambda paused: advance(0.002)

        def toggle():
            audio.enabled = not audio.enabled
            advance(0.005)

        audio.toggle.side_effect = toggle
        soundscape = Mock()
        soundscape.at.side_effect = lambda *position: advance(0.004)
        world = Mock()
        world.combat.update.return_value = ()
        world.update_doors.return_value = ()
        player = SimpleNamespace(x=8, y=8, z=1, yaw=0, hp=10, events=(),
                                 update=lambda *args, **kwargs: advance(0.001))
        args = ["--keyboard-look", "--frames", "2"]
        if collect:
            args.extend(("--frame-timing", str(path)))
        with ExitStack() as mocks:
            for name, value in (("Terminal", terminal), ("Renderer", renderer), ("Audio", audio),
                                ("Soundscape", soundscape), ("spawn_player", player), ("build_world", world)):
                mocks.enter_context(patch("ascii3d.app." + name, return_value=value))
            mocks.enter_context(patch("ascii3d.app.LoadingProgress"))
            mocks.enter_context(patch("ascii3d.app.sys.stdout", io.StringIO()))
            mocks.enter_context(patch("ascii3d.app.time.sleep", side_effect=sleep))
            now = mocks.enter_context(patch("ascii3d.app.time.perf_counter", side_effect=lambda: clock))
            self.assertEqual(main(args), 0)
            return now.call_count

    def test_reports_real_interval_and_each_phase_after_terminal_restoration(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "timing.json"
            self.play(path)
            report = json.loads(path.read_text(encoding="utf-8"))
        first, last = report["frames"]
        self.assertEqual(report["frames_completed"], 2)
        self.assertEqual(first["viewport"], [160, 50])
        self.assertEqual(first["terminal"], [240, 80])
        self.assertEqual(first["scene_samples"], [160, 45])
        self.assertEqual(first["backend"], "native")
        self.assertFalse(first["sound_on"])
        expected = {"input_ms": 4, "audio_ms": 11, "simulation_ms": 0, "render_ms": 7, "draw_ms": 2,
                    "encode_ms": 0.5, "write_flush_ms": 1.5, "output_bytes": 512,
                    "work_ms": 24, "interval_ms": 30, "cap_requested_ms": 1, "cap_actual_ms": 6}
        self.assertEqual({name: first[name] for name in expected}, expected)
        self.assertEqual(last["simulation_ms"], 3)
        self.assertIsNone(last["interval_ms"])
        self.assertEqual(last["cap_requested_ms"], 0)
        self.assertEqual(report["summary"]["interval_ms"], {"count": 1, "mean": 30, "p95": 30})
        self.assertEqual(report["summary"]["work_ms"], {"count": 2, "mean": 23, "p95": 24})

    def test_controlled_interrupt_retains_completed_draw_and_partial_sleep(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "timing.json"
            self.play(path, interrupt_sleep=True)
            report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["frames_completed"], 1)
        self.assertEqual(report["frames"][0]["cap_actual_ms"], 0.5)
        self.assertIsNone(report["frames"][0]["interval_ms"])

    def test_default_gameplay_still_reads_only_its_existing_clock_points(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(self.play(Path(directory) / "unused.json", collect=False), 4)

    def test_existing_path_is_rejected_before_startup_and_never_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "timing.json"
            path.write_text("preserve", encoding="utf-8")
            with patch("ascii3d.app.sys.stderr", io.StringIO()), patch("ascii3d.app.build_world") as build:
                with self.assertRaises(SystemExit) as error:
                    main(["--frame-timing", str(path)])
                self.assertEqual(error.exception.code, 2)
                build.assert_not_called()
            with self.assertRaises(FileExistsError):
                FrameTiming(path, {}).write(0)
            self.assertEqual(path.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()

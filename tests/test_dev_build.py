"""Exercise developer commands through the interactive game's input loop."""

from contextlib import ExitStack
import io
from itertools import count
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, Mock, patch

from ascii3d.app import main
from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.terminal import Keys
from ascii3d.world import FLOOR, STONE, World


def typed(command):
    return Keys(text_events=(*command, "enter"))


class DevBuildTests(unittest.TestCase):
    def play(self, script, *options):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.box(3, 3, 1, 4, 4, 4, STONE)
        self.terminal = terminal = MagicMock()
        terminal.__enter__.return_value = terminal
        terminal.keyboard.poll.side_effect = script
        terminal.size.return_value = (60, 20)
        terminal._terminal_size = (60, 20)
        terminal.output_timing = (None, None, None)
        terminal.mouse_captured = False
        terminal.mouse_error = ""
        self.audio = audio = MagicMock(enabled=True, available=True)
        audio.__enter__.return_value = audio
        self.renderers = []

        def spawn(outside):
            return Player(x=8.5, y=8.5, hp=6)

        def make_renderer(world, aspect, *, backend):
            renderer = Mock(backend_name="cpu" if backend == "gpu" else backend, ray_backend=None)
            renderer.backend_error = "no GPU"
            renderer.styled_frame.side_effect = lambda player, *args, **kwargs: (
                (player.x, player.y, player.z, player.hp), kwargs["time_seconds"], kwargs["color_mode"])
            self.renderers.append(renderer)
            return renderer

        with ExitStack() as mocks:
            for name, value in (("Terminal", terminal), ("Audio", audio), ("build_world", world)):
                mocks.enter_context(patch("ascii3d.app." + name, return_value=value))
            mocks.enter_context(patch("ascii3d.app.Renderer", side_effect=make_renderer))
            mocks.enter_context(patch("ascii3d.app.spawn_player", side_effect=spawn))
            mocks.enter_context(patch("ascii3d.app.LoadingProgress"))
            mocks.enter_context(patch("ascii3d.app.sys.stdout", io.StringIO()))
            mocks.enter_context(patch("ascii3d.app.time.sleep"))
            mocks.enter_context(patch("ascii3d.app.time.perf_counter", side_effect=count(10., .01)))
            self.assertEqual(main(["--dev", "--renderer", "cpu", "--frames", str(len(script)), *options]), 0)
        self.events = [call.args[0].name for call in audio.emit.call_args_list]
        self.assertTrue(all(name in EFFECTS for name in self.events))
        return [call.args[0] for call in terminal.draw.call_args_list]

    def test_commands_preserve_world_and_freeze_play_across_input_transitions(self):
        frames = self.play([
            Keys(pressed={"console", "attack"}, down={"w"}),
            typed("teleport 3.5 3.5 1"), typed("teleport nan 5 1"),
            typed("teleport 5.5 6.5"), typed("set renderer gpu"),
            typed("set renderer native"), typed("set color-mode gray"),
            typed("set cell-aspect 0.7"), typed("set volume 0.25"), typed("set mute on"),
            Keys(pressed={"escape", "attack"}, down={"w"}), Keys(down={"w"}),
        ])
        text = "\n".join(row for frame in frames[:-2] for row in frame)
        self.assertIn("Destination is obstructed", text)
        self.assertIn("Coordinates must be finite", text)
        self.assertIn("gpu renderer unavailable", text)
        self.assertEqual(frames[-2], ((5.5, 6.5, 1., 6), 0., "gray"))
        self.assertGreater(frames[-1][0][1], 6.5)
        self.assertGreater(frames[-1][1], 0)
        self.assertEqual([call.args for call in self.terminal.keyboard.set_text_input.call_args_list],
                         [(True,), (False,)])
        self.assertTrue(all(call.args == (False,) for call in self.terminal.set_mouse_capture.call_args_list[:-2]))
        self.assertEqual(self.events[:3], ["ui_dev_open", "ui_dev_teleport", "ui_dev_close"])
        self.assertNotIn("attack_empty", self.events)
        self.audio.set_volume.assert_called_once_with(0.25)
        self.audio.set_muted.assert_called_once_with(True)
        self.assertEqual([call.args for call in self.audio.pause.call_args_list], [(True,)] * 11 + [(False,)])
        original, rejected, active = self.renderers
        for renderer in (original, rejected, active):
            renderer.close.assert_called_once()
        rejected.styled_frame.assert_not_called()
        active.set_cell_aspect.assert_called_once_with(0.7)

    def test_live_timing_stops_and_resumes_without_counting_gap(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "quoted path.json"
            self.play([
                Keys(pressed={"console"}), typed(f'set frame-timing "{path}"'), typed("where"),
                typed("set frame-timing off"), typed("where"), typed(f'set frame-timing "{path}"'),
                Keys(pressed={"escape"}), Keys(),
            ])
            data = json.loads(path.read_text(encoding="utf-8"))
        frames = data["frames"]
        self.assertEqual([frame["frame"] for frame in frames], [3, 4, 7, 8])
        self.assertIsNone(frames[1]["interval_ms"])
        self.assertIsNone(frames[0]["scene_samples"])
        self.assertTrue(frames[0]["console_open"])
        self.assertFalse(frames[-1]["console_open"])
        self.assertEqual(frames[-1]["scene_samples"], [60, 15])

    def test_headless_modes_reject_dev_before_building_world(self):
        for options in (("--snapshot",), ("--benchmark", "1"), ("--audio-test",),
                        ("--sound-preview", "unused.wav")):
            with self.subTest(options=options), patch("ascii3d.app.sys.stderr", io.StringIO()), \
                    patch("ascii3d.app.build_world") as build:
                with self.assertRaises(SystemExit) as error:
                    main(["--dev", *options])
                self.assertEqual(error.exception.code, 2)
                build.assert_not_called()

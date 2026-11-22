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
from ascii3d.presentation import StyledFrame
from ascii3d.sound import EFFECTS
from ascii3d.terminal import Keys
from ascii3d.world import FLOOR, STONE, World


def typed(command):
    return Keys(text_events=(*command, "enter"))


class DevBuildTests(unittest.TestCase):
    def play(self, script, *options, sizes=None):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.box(3, 3, 1, 4, 4, 4, STONE)
        self.terminal = terminal = MagicMock()
        terminal.__enter__.return_value = terminal
        terminal.keyboard.poll.side_effect = script
        terminal.size.side_effect = sizes or [(60, 20)] * len(script)
        terminal._terminal_size = (60, 20)
        terminal.output_timing = (None, None, None)
        terminal.mouse_captured = False
        terminal.mouse_error = ""
        self.audio = audio = MagicMock(enabled=True, available=True)
        audio.__enter__.return_value = audio
        self.renderers = []
        self.renders = []

        def spawn(outside):
            return Player(x=8.5, y=8.5, hp=6)

        def make_renderer(world, aspect, *, backend):
            renderer = Mock(backend_name="cpu" if backend == "gpu" else backend, ray_backend=None)
            renderer.backend_error = "no GPU"

            def render(player, width, height, *args, preview=False, time_seconds, color_mode, **kwargs):
                self.renders.append(((player.x, player.y, player.z, player.hp), time_seconds,
                                     color_mode, (width, height), preview))
                rows = [f"{player.x:.1f}, {player.y:.1f}".ljust(width)] + [" " * width] * (height - 1)
                if color_mode == "mono":
                    return rows
                return StyledFrame(width, height, rows, [bytearray([7]) * width for _ in rows],
                                   color_mode=color_mode)

            renderer.styled_frame.side_effect = render
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
        text = " ".join(row[34:].strip() for frame in frames[:-2] for row in frame.rows)
        self.assertIn("Destination is obstructed", text)
        self.assertIn("Coordinates must be finite", text)
        self.assertIn("gpu renderer unavailable", text)
        self.assertEqual(self.renders[-2], ((5.5, 6.5, 1., 6), 0., "gray", (60, 20), False))
        self.assertGreater(self.renders[-1][0][1], 6.5)
        self.assertGreater(self.renders[-1][1], 0)
        self.assertEqual(self.renders[3], ((5.5, 6.5, 1., 6), 0., "color", (33, 20), True))
        self.assertEqual(frames[6].color_mode, "gray")
        self.assertEqual(frames[6].rows[0][:12].strip(), "5.5, 6.5")
        self.assertTrue(frames[6].rows[0][33:].startswith("|DEVELOPER CONSOLE"))
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

    def test_split_reuses_preview_while_typing_and_handles_resize_and_mono(self):
        frames = self.play([
            Keys(pressed={"console"}), Keys(text_events=("s",)), Keys(text_events=("backspace",)),
            typed("set color-mode mono"), Keys(), Keys(), Keys(pressed={"escape"}),
        ], sizes=[(120, 40)] * 4 + [(56, 18), (60, 20), (120, 40)])
        self.assertEqual([render[2:] for render in self.renders], [
            ("color", (79, 40), True), ("mono", (79, 40), True),
            ("mono", (33, 20), True), ("mono", (120, 40), False),
        ])
        first, typing, cleared, mono, tiny, compact, closed = frames
        self.assertEqual(first.rows, cleared.rows)
        self.assertEqual([row[:80] for row in first.rows], [row[:80] for row in typing.rows])
        self.assertIn("> s|", typing.rows[-1])
        self.assertIn("|DEVELOPER CONSOLE", mono[0])
        self.assertTrue(tiny[0].startswith("DEVELOPER CONSOLE"))
        self.assertEqual(compact[0][33], "|")
        self.assertNotIn("DEVELOPER CONSOLE", closed[0])

    def test_live_timing_stops_and_resumes_without_counting_gap(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "quoted path.json"
            self.play([
                Keys(pressed={"console"}), typed(f'set frame-timing "{path}"'), Keys(), typed("where"),
                typed("set frame-timing off"), typed("where"), typed(f'set frame-timing "{path}"'),
                Keys(pressed={"escape"}), Keys(),
            ])
            data = json.loads(path.read_text(encoding="utf-8"))
        frames = data["frames"]
        self.assertEqual([frame["frame"] for frame in frames], [3, 4, 5, 8, 9])
        self.assertIsNone(frames[2]["interval_ms"])
        self.assertIsNone(frames[0]["scene_samples"])
        self.assertEqual(frames[1]["scene_samples"], [33, 15])
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

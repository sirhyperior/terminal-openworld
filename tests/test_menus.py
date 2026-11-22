"""Separate pause/help presentation and current input hints at every viewport."""

import unittest
from textwrap import wrap
from unittest.mock import patch

from ascii3d.dialogue import DialogueView
from ascii3d.npcs import NPC
from ascii3d.palette import UI_ACCENT
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import FLOOR, World


class MenuTests(unittest.TestCase):
    def setUp(self):
        world = World.empty(20, 20, 10)
        world.box(0, 0, 0, 20, 20, 1, FLOOR)
        self.renderer = Renderer(world)
        self.player = Player(x=8.5, y=4.5)

    def test_pause_is_a_small_resume_controls_quit_card_without_guides(self):
        frame = self.renderer.frame(self.player, 60, 20, paused=True,
                                    notice="[E] Collect iron sword")
        text = "\n".join(frame)
        for label in ("PAUSED", "P    resume", "H    controls", "ESC  quit"):
            self.assertIn(label, text)
        for guide in ("WASD", "SHIFT", "MOUSE", "attack", "FIELD GUIDE",
                      "Training", "NORTH GATE", "[E]"):
            self.assertNotIn(guide, text)
        borders = [row for row in frame if "+--------------" in row]
        self.assertEqual(len(borders), 2)

    def test_help_contains_current_controls_and_fits_all_supported_sizes(self):
        for width, height in ((60, 20), (100, 34), (180, 64)):
            with self.subTest(width=width, height=height):
                frame = self.renderer.frame(self.player, width, height, help_open=True,
                                            notice="[E] Collect iron sword")
                text = "\n".join(frame)
                for label in ("CONTROLS", "WASD", "SHIFT / SPACE", "MOUSE",
                              "LEFT CLICK", "E             open", "One held item",
                              "M / TAB", "F sound", "R             return", "H back", "ESC quit"):
                    self.assertIn(label, text)
                for obsolete in ("FIELD GUIDE", "Q ", "NORTH GATE", "TRAINING", "[E]"):
                    self.assertNotIn(obsolete, text)
                self.assertEqual(len(frame), height)
                self.assertTrue(all(len(row) == width for row in frame))
                self.assertTrue(all(32 <= ord(char) <= 126 for row in frame for char in row))

    def test_controls_can_be_read_from_pause_without_repeating_the_pause_card(self):
        text = "\n".join(self.renderer.frame(self.player, 60, 20,
                                              paused=True, help_open=True))
        self.assertIn("CONTROLS", text)
        self.assertIn("LEFT CLICK", text)
        self.assertNotIn("PAUSED", text)

    def test_keyboard_accessibility_mode_updates_help_and_gameplay_footer(self):
        help_text = "\n".join(self.renderer.frame(self.player, 60, 20,
                                                   help_open=True, keyboard_look=True))
        self.assertIn("ARROWS        look / aim", help_text)
        self.assertIn("ENTER         attack", help_text)
        self.assertNotIn("MOUSE", help_text)
        self.assertNotIn("LEFT CLICK", help_text)
        for width in (60, 120):
            footer = self.renderer.frame(self.player, width, 20, keyboard_look=True)[-1]
            self.assertIn("ARROWS look", footer)
            self.assertIn("ENTER attack", footer)
            self.assertNotIn("Q attack", footer)

    def test_gameplay_footer_uses_mouse_and_click_hints(self):
        for width, attack in ((60, "LMB attack"), (120, "LEFT CLICK attack")):
            footer = self.renderer.frame(self.player, width, 20)[-1]
            self.assertIn("MOUSE look", footer)
            self.assertIn(attack, footer)
            self.assertNotIn("ARROWS", footer)
            self.assertNotIn("Q attack", footer)

    def test_talk_prompt_and_separate_dialogue_panel_fit_minimum_and_wide_view(self):
        self.renderer.world.npcs.append(NPC(name="Bell Keeper", x=8.5, y=6.5, z=1, yaw=0,
                                            dialogue=("Hear the bell?",)))
        sentence = ("The bell in the tower only sounds after sunset. Count the strokes before "
                    "you cross the gate and keep your lantern low.")
        with patch.object(self.renderer, "scene",
                          side_effect=lambda player, w, h, t, *, labels: [["."] * w for _ in range(h)]):
            for width, height in ((60, 20), (160, 50)):
                with self.subTest(width=width):
                    def render(**kwargs):
                        return self.renderer.styled_frame(self.player, width, height, **kwargs)

                    normal = render()
                    self.assertIn("[E] Talk to Bell Keeper", "\n".join(normal.rows))
                    turn = render(dialogue=DialogueView("Bell Keeper", None, False))
                    self.assertNotIn("[E]", "\n".join(turn.rows))
                    self.assertEqual(turn.rows[2 + (height - 5) // 2][width // 2], ".")
                    talk = render(dialogue=DialogueView("Bell Keeper", sentence, False), show_map=True)
                    self.assertTrue(all(len(row) == width for row in talk.rows))
                    bottom = height - 1
                    self.assertIn("+-----", talk.rows[bottom])
                    self.assertIn("[E] Continue", talk.rows[bottom - 1])
                    self.assertIn("Bell Keeper", talk.rows[bottom - 5])
                    body = " ".join(row.split("|")[1].strip() for row in talk.rows[bottom - 4:bottom - 1])
                    self.assertEqual(body.strip(), sentence)
                    start = talk.rows[bottom - 1].index("[E]")
                    self.assertEqual(talk.materials[bottom - 1][start], UI_ACCENT)
                    first_row, second_row, *_ = wrap(sentence, min(70, width - 12))
                    reveal = render(dialogue=DialogueView("Bell Keeper", sentence, False,
                                                           len(first_row) + 3))
                    self.assertEqual(reveal.rows[bottom - 4], talk.rows[bottom - 4])
                    self.assertEqual(reveal.rows[bottom - 3].split("|")[1].strip(), second_row[:2])
                    self.assertIn("[E] Reveal", reveal.rows[bottom - 1])
                    finish = render(dialogue=DialogueView("Bell Keeper", "Farewell.", True))
                    self.assertIn("[E] Finish", finish.rows[bottom - 1])
                    pause = render(dialogue=DialogueView("Bell Keeper", sentence, False), paused=True)
                    self.assertIn("PAUSED", "\n".join(pause.rows))
                    self.assertNotIn("[E]", "\n".join(pause.rows))

    def test_long_dialogue_fits_the_smallest_developer_preview(self):
        text = ("There is a fire staff on the timber floor inside. "
                "The Warden keeps to the watchstones west of here.")
        frame = self.renderer.frame(self.player, 30, 12, preview=True,
                                    dialogue=DialogueView("Sister Morwen", text, True))
        self.assertEqual(len(frame), 12)
        self.assertTrue(all(len(row) == 30 for row in frame))
        self.assertIn("Sister Morwen", "\n".join(frame))
        self.assertIn("[E] Finish", frame[-2])
        self.assertTrue(frame[-1].startswith("+---"))


if __name__ == "__main__":
    unittest.main()

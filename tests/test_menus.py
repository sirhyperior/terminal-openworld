"""Separate pause/help presentation and current input hints at every viewport."""

import unittest

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


if __name__ == "__main__":
    unittest.main()

"""Rich material colors retain safe terminal sizing and fallback behavior."""

import io
import re
import unittest
from unittest.mock import patch

from ascii3d.palette import (AIR, ARCANE, BONE, BRIDGE, COLOR_CODES, COLOR_RGB,
                             CRATE, FIRE, FLOOR, GRASS, GRAY_LEVELS, LEAVES, METAL,
                             PATH, STONE, STRAW, UI, WATER, WOOD, color_rgb)
from ascii3d.presentation import GRAY_CODES, StyledFrame, WHITE_ON_BLACK
from ascii3d.terminal import Terminal


ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class ColorPaletteTests(unittest.TestCase):
    def test_shadows_remain_readable_with_fog_and_firelight_without_losing_depth(self):
        self.assertGreaterEqual(GRAY_LEVELS[0], 100)
        self.assertGreaterEqual(GRAY_LEVELS[8] - GRAY_LEVELS[1], 80)
        for material in (STONE, FLOOR, METAL, CRATE, GRASS, WATER, WOOD,
                         LEAVES, PATH, BRIDGE, STRAW, BONE):
            for effects in range(16):
                with self.subTest(material=material, effects=effects):
                    brightness = [sum(channel * weight for channel, weight in
                                      zip(color_rgb(material, level, effects),
                                          (0.2126, 0.7152, 0.0722)))
                                  for level in range(16)]
                    self.assertGreaterEqual(brightness[0], 99)
                    self.assertGreaterEqual(brightness[1], 105)
                    self.assertGreaterEqual(brightness[8] - brightness[1], 40)
                    self.assertEqual(brightness, sorted(brightness))
        grass, water, wood = (color_rgb(material, 2) for material in (GRASS, WATER, WOOD))
        self.assertGreater(grass[1], max(grass[0], grass[2]))
        self.assertGreater(min(water[1], water[2]), water[0])
        self.assertGreater(wood[0], wood[1])
        self.assertEqual(color_rgb(AIR, 15), (0, 0, 0))

    def test_materials_have_recognizable_distinct_hues_and_bounded_intensities(self):
        grass, water, wood, fire, magic = (color_rgb(material, 15)
                                          for material in (GRASS, WATER, WOOD, FIRE, ARCANE))
        self.assertGreater(grass[1], max(grass[0], grass[2]))
        self.assertGreater(min(water[1], water[2]), water[0])
        self.assertGreater(wood[0], wood[1])
        self.assertEqual(fire, (255, 255, 255))
        self.assertGreater(color_rgb(FIRE, 9)[0], color_rgb(FIRE, 9)[1])
        self.assertGreater(magic[2], magic[1])
        for material in (STONE, GRASS, LEAVES, WATER, WOOD, FIRE, ARCANE):
            colors = [color_rgb(material, level) for level in range(16)]
            brightness = [sum(channel * weight for channel, weight in
                              zip(rgb, (0.2126, 0.7152, 0.0722))) for rgb in colors]
            self.assertEqual(brightness, sorted(brightness))
            self.assertTrue(all(value >= expected * 0.80 for value, expected in
                                zip(brightness, GRAY_LEVELS)))
            self.assertTrue(all(0 <= value <= 255 for rgb in colors for value in rgb))
            self.assertGreater(sum(colors[-1]), sum(colors[0]))

    def test_depth_cools_and_softens_color_while_firelight_warms_it(self):
        near = color_rgb(GRASS, 10)
        far = color_rgb(GRASS, 10, 3 << 2)
        warm = color_rgb(GRASS, 10, 3)
        self.assertGreater(far[2] / far[1], near[2] / near[1])
        self.assertLess(max(far) - min(far), max(near) - min(near))
        self.assertGreater(warm[0] / warm[1], near[0] / near[1])
        self.assertNotEqual(color_rgb(STONE, 10, 12), color_rgb(STONE, 10, 15))

    def test_neutral_unknown_materials_and_ui_ignore_scene_effects(self):
        self.assertIs(COLOR_RGB[42], COLOR_RGB[UI])
        self.assertIs(COLOR_CODES[42], COLOR_CODES[UI])
        self.assertEqual(len(COLOR_CODES), 256)
        self.assertTrue(all(len(row) == 256 for row in COLOR_CODES))
        for level in (0, 7, 15):
            expected = (GRAY_LEVELS[level],) * 3
            for material in (42, UI):
                for effects in (0, 3, 12, 15):
                    self.assertEqual(color_rgb(material, level, effects), expected)
        self.assertEqual(color_rgb(AIR, 15), (0, 0, 0))

    def test_lookup_rejects_out_of_range_indices(self):
        for values in ((-1, 4, 0), (256, 4, 0), (STONE, -1, 0),
                       (STONE, 16, 0), (STONE, 4, 16), (STONE, 4, -1),
                       (STONE, 4.5, 0), (True, 4, 0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                color_rgb(*values)


class ColorFrameTests(unittest.TestCase):
    def test_same_glyph_can_show_different_materials_depth_and_light(self):
        frame = StyledFrame(4, 1, ["xxxx"], [bytearray([10] * 4)],
                            [bytearray((GRASS, STONE, GRASS, GRASS))],
                            [bytearray((0, 0, 12, 3))], "color")
        encoded = frame.ansi_rows()[0]
        self.assertEqual(ANSI.sub("", encoded), "xxxx")
        for material, effects in ((GRASS, 0), (STONE, 0), (GRASS, 12), (GRASS, 3)):
            self.assertIn(COLOR_CODES[material][effects * 16 + 10], encoded)
        self.assertTrue(encoded.startswith("\x1b[40m"))
        self.assertTrue(encoded.endswith(WHITE_ON_BLACK))
        self.assertNotIn("\x1b[48;", encoded)

    def test_equal_rgb_coalesces_across_material_ids_and_blank_cells(self):
        frame = StyledFrame(5, 1, ["x   y"], [bytearray((7, 2, 3, 4, 7))],
                            [bytearray((42, GRASS, WATER, FIRE, UI))],
                            [bytearray((0, 0, 0, 0, 15))], "color")
        encoded = frame.ansi_rows()[0]
        self.assertEqual(encoded.count(GRAY_CODES[7]), 1)
        self.assertIn("x   y", encoded)

    def test_absent_metadata_defaults_to_neutral_and_gray_ignores_colored_metadata(self):
        plain = StyledFrame(2, 1, ["xy"], [bytearray((4, 10))])
        neutral = StyledFrame(2, 1, ["xy"], [bytearray((4, 10))], color_mode="color")
        colored_metadata_gray = StyledFrame(2, 1, ["xy"], [bytearray((4, 10))],
                                           [bytearray((FIRE, GRASS))], [bytearray((15, 12))])
        self.assertEqual(plain.ansi_rows(), neutral.ansi_rows())
        self.assertEqual(plain.ansi_rows(), colored_metadata_gray.ansi_rows())

    def test_empty_cells_need_no_foreground_codes(self):
        frame = StyledFrame(3, 1, ["   "], [bytearray((0, 7, 15))],
                            [bytearray((FIRE, WATER, GRASS))], [bytearray((0, 3, 12))], "color")
        self.assertEqual(frame.ansi_rows(), ["\x1b[40m   " + WHITE_ON_BLACK])

    def test_terminal_last_cell_and_plain_followup_preserve_sizes_and_reset(self):
        terminal = Terminal()
        frame = StyledFrame(2, 1, ["xZ"], [bytearray((7, 15))],
                            [bytearray((GRASS, FIRE))], color_mode="color")
        with patch("ascii3d.terminal.sys.stdout", new_callable=io.StringIO) as output:
            terminal.draw(frame)
            self.assertEqual(ANSI.sub("", output.getvalue()), "xZ")
            self.assertTrue(output.getvalue().endswith("Z" + WHITE_ON_BLACK))
            self.assertEqual(terminal.last_size[:2], (2, 1))
            terminal.draw(["ab"])
            self.assertIn(WHITE_ON_BLACK + "\x1b[1;1Hab", output.getvalue())

    def test_invalid_modes_and_effect_buffers_are_rejected(self):
        for effects in ([bytearray((16,))], [bytearray()], [], [[0]], [bytearray(1), bytearray(1)]):
            with self.subTest(effects=effects), self.assertRaises(ValueError):
                StyledFrame(1, 1, ["x"], [bytearray((7,))], effects=effects)
        for mode in ("mono", "auto", "", None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                StyledFrame(1, 1, ["x"], [bytearray((7,))], color_mode=mode)


if __name__ == "__main__":
    unittest.main()

"""Geometry regressions for the sorcerer's robes and closed hood cavity."""

import math
import unittest

from ascii3d.geometry import Camera
from ascii3d.npc_render import _draw_npc
from ascii3d.npcs import NPC
from ascii3d.palette import CLOTH, SKIN
from ascii3d.player import Player
from ascii3d.shading import Shading, ink


class SorcererRenderingTests(unittest.TestCase):
    def setUp(self):
        self.npc = NPC("Sorcerer", 8.5, 8.5, 1, math.pi, ("Welcome.",), "sorcerer")

    def draw(self, width, height, yaw=0.0, time_seconds=0.0, foreground_depth=math.inf):
        distance = 2.45
        player = Player(self.npc.x - distance * math.cos(yaw),
                        self.npc.y - distance * math.sin(yaw), self.npc.z, yaw)
        focal = width / (2 * math.tan(math.radians(41)))
        camera = Camera(player, width, height - 5, focal, 0.5)
        camera.shading = Shading()
        camera.shading.prepare(player)
        pixels = [["~"] * width for _ in range(height - 5)]
        depths = [[foreground_depth] * width for _ in range(height - 5)]
        _draw_npc(self.npc, camera, pixels, depths, time_seconds)
        return camera, pixels, depths

    def test_hood_blocks_the_view_with_recessed_dark_cloth_and_no_skin(self):
        for width, height in ((60, 20), (120, 40)):
            with self.subTest(width=width):
                _, pixels, depths = self.draw(width, height)
                shadow = ink(".", 2, CLOTH)
                recess_depths = [depths[y][x] for y, row in enumerate(pixels)
                                 for x, glyph in enumerate(row) if glyph is shadow]
                self.assertTrue(recess_depths)
                self.assertTrue(all(2.39 < depth < 2.45 for depth in recess_depths))
                self.assertFalse(any(getattr(glyph, "material", None) == SKIN
                                     for row in pixels for glyph in row))

    def test_hood_is_opaque_from_sides_and_back(self):
        for yaw in (-math.pi / 2, math.pi / 2, math.pi):
            with self.subTest(yaw=yaw):
                camera, pixels, depths = self.draw(120, 40, yaw)
                x, y, depth = camera.project(self.npc.x, self.npc.y, self.npc.z + 1.57)
                self.assertNotEqual(pixels[round(y)][round(x)], "~")
                self.assertLess(depths[round(y)][round(x)], depth)
                self.assertFalse(any(glyph is ink(".", 2, CLOTH) for row in pixels for glyph in row))

    def test_sorcerer_moves_with_idle_time_and_stays_behind_foreground(self):
        for width, height in ((60, 20), (120, 40)):
            with self.subTest(width=width):
                _, first, _ = self.draw(width, height)
                _, moved, _ = self.draw(width, height, time_seconds=3.6)
                self.assertNotEqual(first, moved)
                for seconds in (0, 3.6):
                    _, hidden, depths = self.draw(width, height, time_seconds=seconds,
                                                  foreground_depth=2.0)
                    self.assertTrue(all(glyph == "~" for row in hidden for glyph in row))
                    self.assertTrue(all(depth == 2.0 for row in depths for depth in row))


if __name__ == "__main__":
    unittest.main()

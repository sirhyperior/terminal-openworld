"""Render native-cell viewports beyond the former 180-column/64-row caps."""

import math
import unittest

from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import AIR, FLOOR, GRASS, STONE, Tree, World


class LargeViewportTests(unittest.TestCase):
    @staticmethod
    def make_world():
        world = World.empty(28, 28, 16)
        world.box(0, 0, 0, 28, 28, 1, GRASS)
        world.outdoor_bounds = (1, 1, 27, 27)
        world.box(12, 10, 1, 25, 25, 2, FLOOR)
        world.box(12, 10, 2, 13, 25, 10, STONE)
        world.box(24, 10, 2, 25, 25, 10, STONE)
        world.box(12, 24, 2, 25, 25, 10, STONE)
        world.box(12, 10, 9, 25, 25, 10, FLOOR)
        world.box(16, 24, 4, 21, 25, 7, AIR)
        world.box(5, 18, 1, 9, 23, 13, STONE)
        return world

    def assert_frame_size(self, frame, width, height):
        self.assertEqual(len(frame), height)
        self.assertTrue(all(len(row) == width for row in frame))
        self.assertTrue(all(32 <= ord(char) <= 126 for row in frame for char in row))

    def test_large_and_tall_views_match_exact_voxel_traversal(self):
        world = self.make_world()
        accelerated = Renderer(world)
        exact = Renderer(world, skip_empty_space=False)
        poses = (Player(x=18.5, y=14.5, z=2, yaw=math.pi / 2, pitch=0.18),
                 Player(x=9.5, y=7.5, yaw=math.pi / 2, pitch=0.35))
        for width, height in ((240, 80), (320, 100), (80, 160)):
            for player in poses:
                with self.subTest(size=(width, height), pose=(player.x, player.y)):
                    self.assertEqual(accelerated.scene(player, width, height, 2),
                                     exact.scene(player, width, height, 2))

    def test_resize_reuses_projection_and_map_without_stale_cells(self):
        world = self.make_world()
        player = Player(x=9.5, y=7.5, yaw=math.pi / 2)
        renderer = Renderer(world)
        for width, height in ((240, 80), (60, 20), (80, 160), (320, 100), (240, 80)):
            with self.subTest(size=(width, height)):
                frame = renderer.frame(player, width, height, show_map=True, time_seconds=2)
                fresh = Renderer(world).frame(player, width, height, show_map=True, time_seconds=2)
                self.assertEqual(frame, fresh)
                self.assert_frame_size(frame, width, height)
                self.assertIn("N ^", "\n".join(frame))
                self.assertEqual(frame[2 + (height - 5) // 2][width // 2], "+")

    def test_large_help_and_pause_preserve_keyboard_accessibility(self):
        renderer = Renderer(self.make_world())
        player = Player(x=18.5, y=14.5, z=2)
        for width, height in ((240, 80), (320, 100)):
            for keyboard in (False, True):
                with self.subTest(size=(width, height), keyboard=keyboard):
                    frame = renderer.frame(player, width, height, help_open=True,
                                           keyboard_look=keyboard)
                    self.assert_frame_size(frame, width, height)
                    text = "\n".join(frame)
                    for label in ("CONTROLS", "WASD", "E             open / use / collect",
                                  "ARROWS        look / aim" if keyboard else "MOUSE         look / aim",
                                  "ENTER         attack" if keyboard else "LEFT CLICK    attack"):
                        self.assertIn(label, text)
                    paused = renderer.frame(player, width, height, paused=True,
                                            keyboard_look=keyboard)
                    self.assert_frame_size(paused, width, height)
                    for label in ("PAUSED", "P    resume", "H    controls", "ESC  quit"):
                        self.assertIn(label, "\n".join(paused))

    def test_large_foliage_keeps_existing_visibility_and_work_budgets(self):
        world = self.make_world()
        world.trees[8, 12] = Tree(8.5, 12.5)
        renderer = Renderer(world)
        player = Player(x=8.5, y=8.5, yaw=math.pi / 2, pitch=-0.1)
        for width, height in ((240, 80), (320, 100)):
            with self.subTest(size=(width, height)):
                renderer.scene(player, width, height, 2)
                stats = renderer.scenery.stats
                self.assertGreater(stats["grass_drawn"], 0)
                self.assertGreater(stats["tree_samples"], 0)
                self.assertLessEqual(stats["grass_candidates"], width * height // 3)
                self.assertLessEqual(stats["tree_samples"], width * height * 3)
                self.assertLessEqual(stats["grass_chunks"], 81)
                self.assertLessEqual(len(renderer.scenery._chunks), 128)


if __name__ == "__main__":
    unittest.main()

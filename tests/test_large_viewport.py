"""Render native-cell viewports beyond the former 180-column/64-row caps."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import CombatState, Enemy, WeaponPickup
from ascii3d.player import Player
from ascii3d.palette import WATER_CREST
from ascii3d.renderer import Renderer, _expand_scene, _sample_size
from ascii3d.shading import ink
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

    def test_reduced_scene_fills_native_viewport_with_readable_aim_and_interaction_ui(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        pickup = WeaponPickup(8.5, 6.5)
        world.combat = CombatState(pickups=[pickup], enemies=[Enemy("Training dummy", 8.5, 10.5)])
        renderer = Renderer(world)
        self.addCleanup(renderer.close)
        player = Player(x=8.5, y=4.5, z=1)
        width, height, budget = 240, 80, 640
        view_height = height - 5
        with patch.object(renderer, "scene", wraps=renderer.scene) as scene:
            frame = renderer.styled_frame(
                player, width, height, scene_cells=budget, keyboard_look=True)
        scene.assert_called_once()
        sample_width, sample_height = scene.call_args.args[1:3]
        self.assertLessEqual(sample_width * sample_height, budget)
        self.assertEqual((sample_width % 2, sample_height % 2), (1, 1))
        self.assertEqual(scene.call_args.kwargs["output_size"], (width, view_height))
        self.assertEqual(renderer._columns[sample_width // 2], 0.0)
        self.assertEqual(renderer._rows[sample_height // 2], 0.0)
        self.assert_frame_size(frame.rows, width, height)
        self.assertEqual(frame.rows[2 + view_height // 2][width // 2], "+")
        self.assertIn(f"[E] Collect {pickup.name}", frame.rows[view_height])
        self.assertIn("Training dummy [3/3]", "\n".join(frame.rows))
        self.assertIn("ARROWS look  ENTER attack", frame.rows[-1])

        world.box(0, 5, 1, 24, 6, 8, STONE)
        hidden = renderer.styled_frame(player, width, height, scene_cells=budget)
        rendered = "\n".join(hidden.rows)
        self.assertNotIn("[E] Collect", rendered)
        self.assertNotIn("Training dummy", rendered)

    def test_full_scene_budget_matches_native_frame_and_foreground_buffers(self):
        world = self.make_world()
        renderer = Renderer(world)
        self.addCleanup(renderer.close)
        player = Player(x=9.5, y=7.5, yaw=math.pi / 2, pitch=0.15)
        width, height = 143, 43
        full_cells = width * (height - 5)
        settings = {"show_map": True, "time_seconds": 2.75, "color_mode": "color"}
        expected = renderer.styled_frame(player, width, height, **settings)
        renderer.styled_frame(player, width, height, scene_cells=640, **settings)
        for budget in (full_cells, full_cells * 2):
            with self.subTest(budget=budget):
                actual = renderer.styled_frame(
                    player, width, height, scene_cells=budget, **settings)
                self.assertEqual(actual, expected)
                self.assertEqual(actual.ansi_rows(), expected.ansi_rows())

    def test_expansion_keeps_glints_small_and_respects_the_budget_on_extreme_aspects(self):
        for width, height in ((6000, 15), (60, 6000)):
            sample_width, sample_height = _sample_size(width, height, 128)
            self.assertLessEqual(sample_width * sample_height, 128)
        base, flash = ink("~", 9, WATER_CREST), ink("+", 15, WATER_CREST)
        pixels, depths = _expand_scene([[flash, "."], ["X", "."]], [[2, 4], [1, 4]], 8, 6,
                                       [(0, 0, base, flash), (0, 1, base, flash)])
        self.assertEqual(sum(row.count(flash) for row in pixels), 1)
        self.assertEqual(sum(row.count(base) for row in pixels), 11)
        self.assertIs(pixels[1][2], flash)
        self.assertEqual(depths[1][2], 2)
        self.assertEqual(pixels[4][2], "X")

    def test_expanded_foreground_reuse_matches_packing_each_row(self):
        def plain_expansion(*args):
            pixels, depths = _expand_scene(*args)
            return [list(row) for row in pixels], depths

        renderer = Renderer(self.make_world())
        player = Player(x=9.5, y=7.5, pitch=-0.15)
        options = dict(scene_cells=640, show_map=True, notice='[E] Test prompt', time_seconds=3)
        expected = renderer.styled_frame(player, 336, 124, **options)
        with patch('ascii3d.renderer._expand_scene', side_effect=plain_expansion):
            actual = renderer.styled_frame(player, 336, 124, **options)
        self.assertEqual(actual, expected)
        self.assertEqual(actual.ansi_rows(), expected.ansi_rows())

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

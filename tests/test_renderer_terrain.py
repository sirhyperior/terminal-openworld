"""Exact elevated traversal, bounded cache construction and readable local maps."""

import math
import random
import unittest
from unittest.mock import patch

from ascii3d.player import Player
from ascii3d.renderer import Renderer, _clear_rectangles, _overlapping_clear_runs
from ascii3d.world import AIR, FLOOR, GRASS, PATH, STONE, WATER, WOOD, World


class CacheConstructionTests(unittest.TestCase):
    def test_overlapping_runs_match_full_vertical_search_with_linear_reads(self):
        class CountedCells(list):
            reads = 0

            def __getitem__(self, index):
                self.reads += 1
                return super().__getitem__(index)

        width, height = 67, 73
        rng = random.Random(17)
        cells = CountedCells(rng.random() > 0.12 for _ in range(width * height))
        overlaps = list(_overlapping_clear_runs(cells, width, height))
        self.assertLessEqual(cells.reads, width * height * 4)
        for left, row, right, low, high in overlaps:
            expected_low, expected_high = row, row + 1
            while expected_low and all(cells[(expected_low - 1) * width + x] for x in range(left, right)):
                expected_low -= 1
            while expected_high < height and all(cells[expected_high * width + x] for x in range(left, right)):
                expected_high += 1
            self.assertEqual((low, high), (expected_low, expected_high))

    def test_clear_rectangle_partition_has_linear_reads_and_exact_coverage(self):
        class CountedCells(list):
            reads = 0

            def __getitem__(self, index):
                self.reads += 1
                return super().__getitem__(index)

        for width, height in ((31, 47), (128, 128), (256, 256)):
            rng = random.Random(7)
            cells = CountedCells(rng.random() > 0.22 for _ in range(width * height))
            rectangles = _clear_rectangles(cells, width, height)
            self.assertLessEqual(cells.reads, width * height * 3)
            coverage = [0] * len(cells)
            for left, low, right, high in rectangles:
                self.assertLess(left, right)
                self.assertLess(low, high)
                for y in range(low, high):
                    for x in range(left, right):
                        coverage[y * width + x] += 1
            self.assertEqual(coverage, [int(value) for value in cells])

    def test_elevated_terraces_and_stacked_floors_preserve_exact_ray_hits(self):
        world = World.empty(43, 47, 32)
        world.box(0, 0, 0, 43, 47, 1, GRASS)
        for step in range(8):
            world.box(4 + step * 3, 14, 1, 7 + step * 3, 36, 2 + step, STONE)
            world.box(4 + step * 3, 14, 2 + step, 7 + step * 3, 36, 3 + step, GRASS)
        world.box(28, 24, 0, 41, 44, 9, STONE)
        world.box(29, 25, 9, 40, 43, 10, WOOD)
        world.box(29, 25, 15, 40, 43, 16, FLOOR)
        world.box(29, 25, 21, 40, 43, 22, WOOD)
        world.box(28, 24, 9, 29, 44, 22, STONE)
        world.box(40, 24, 9, 41, 44, 22, STONE)
        world.box(28, 43, 9, 41, 44, 22, STONE)
        world.box(31, 43, 12, 36, 44, 14, AIR)
        fast, exact = Renderer(world), Renderer(world, skip_empty_space=False)
        poses = ((7.5, 8.5, 1, math.pi / 2), (17.5, 22.5, 7, 0.2),
                 (35.5, 29.5, 10, math.pi / 2), (35.5, 29.5, 16, -1.0),
                 (35.5, 29.5, 22, -2.2))
        for x, y, z, yaw in poses:
            for pitch in (-0.5, 0, 0.5):
                with self.subTest(pose=(x, y, z, yaw), pitch=pitch):
                    player = Player(x=x, y=y, z=z, yaw=yaw, pitch=pitch)
                    self.assertEqual(fast.scene(player, 60, 22, 2), exact.scene(player, 60, 22, 2))
        self.assertLessEqual(fast.cache_stats["room_union_cells"], fast.cache_stats["room_union_budget"])

    def test_local_sky_ceiling_retains_high_geometry_at_wide_frustum_edges(self):
        world = World.empty(192, 192, 32)
        world.box(0, 0, 0, 192, 192, 1, GRASS)
        # A tall building behind a high terrace and near a wide ray's edge
        # must remain visible even when the rest of the local sky is empty.
        world.box(109, 120, 0, 117, 128, 24, STONE)
        world.box(36, 115, 0, 44, 123, 21, WOOD)
        fast, exact = Renderer(world), Renderer(world, skip_empty_space=False)
        for x, y, yaw in ((76.5, 76.5, math.pi / 2), (76.5, 84.5, 1.1),
                          (80.5, 92.5, 2.0), (184.5, 184.5, -math.pi / 2)):
            for pitch in (0, 0.55, -0.55):
                with self.subTest(pose=(x, y, yaw), pitch=pitch):
                    player = Player(x=x, y=y, z=3, yaw=yaw, pitch=pitch)
                    self.assertEqual(fast.scene(player, 60, 44), exact.scene(player, 60, 44))

    def test_column_atlas_crosses_a_valley_without_distant_side_hill_boundaries(self):
        world = World.empty(96, 96, 16)
        world.box(0, 0, 0, 96, 96, 1, GRASS)
        for y in range(0, 96, 8):
            edge = 50 + (y // 8) % 3 * 8
            world.box(edge, y, 1, 96, y + 8, 8, STONE)
        fast, exact = Renderer(world), Renderer(world, skip_empty_space=False)
        fast._update_chunks()
        chunks_x = 48
        count = chunks_x * 48
        index = count + (10 >> 1) * chunks_x + (30 >> 1)
        across, along = fast._empty_bounds[index], fast._empty_columns[index]
        self.assertGreater(along[3] - along[1], across[3] - across[1])
        for yaw in (0, math.pi / 2, -math.pi / 2):
            player = Player(x=30.5, y=10.5, yaw=yaw)
            self.assertEqual(fast.scene(player, 60, 24), exact.scene(player, 60, 24))

    def test_sky_horizon_preserves_angular_wrap_low_walls_and_camera_cell_edges(self):
        world = World.empty(96, 96, 32)
        world.box(0, 0, 0, 96, 96, 1, GRASS)
        for x, y, top in ((50, 31, 17), (50, 32, 13), (31, 50, 21),
                          (12, 31, 9), (31, 12, 12), (45, 45, 24)):
            world.box(x, y, 1, x + 1, y + 1, top, STONE)
        world.box(40, 20, 1, 41, 40, 2, STONE)
        fast, exact = Renderer(world), Renderer(world, skip_empty_space=False)
        for x, y, z in ((31.001, 31.999, 1), (31.999, 31.001, 1),
                        (31.999, 31.999, 8), (32.001, 31.999, 1)):
            for yaw in (-0.04, 0.04, math.pi / 2, math.pi, -math.pi / 2):
                player = Player(x=x, y=y, z=z, yaw=yaw, pitch=0.35)
                self.assertEqual(fast.scene(player, 60, 30), exact.scene(player, 60, 30))
        player = Player(x=31.1, y=31.1, pitch=0.35)
        fast.scene(player, 60, 30)
        skyline = fast._sky_horizon
        self.assertIsNotNone(skyline)
        player.x, player.y, player.yaw = 31.9, 31.9, 2.3
        self.assertEqual(fast.scene(player, 60, 30), exact.scene(player, 60, 30))
        self.assertIs(fast._sky_horizon, skyline)
        player.x = 32.001
        fast.scene(player, 60, 30)
        self.assertIsNot(fast._sky_horizon, skyline)

    def test_origin_rail_refinement_keeps_clear_sky_and_roof_fallback_exact(self):
        world = World.empty(24, 24, 10)
        world.box(0, 0, 0, 24, 24, 1, GRASS)
        world.box(11, 8, 1, 12, 20, 3, WOOD)
        fast, exact = Renderer(world), Renderer(world, skip_empty_space=False)
        player = Player(x=8.5, y=9.5, yaw=math.pi / 2, pitch=0.3)
        self.assertEqual(fast.scene(player, 60, 24), exact.scene(player, 60, 24))
        self.assertIsNotNone(fast._sky_horizon)
        world.box(8, 8, 4, 10, 10, 5, WOOD)
        self.assertEqual(fast.scene(player, 60, 24), exact.scene(player, 60, 24))
        self.assertIsNone(fast._sky_horizon)


class TerrainMapTests(unittest.TestCase):
    def test_large_world_map_tracks_local_elevation_and_caches_between_boundaries(self):
        world = World.empty(512, 512, 16)
        world.box(220, 220, 0, 300, 300, 1, GRASS)
        world.box(250, 265, 0, 270, 280, 10, GRASS)
        world.box(235, 230, 0, 239, 290, 1, PATH)
        world.box(220, 249, 0, 300, 255, 1, WATER)
        renderer = Renderer(world)
        player = Player(x=256.5, y=256.5)

        def draw():
            pixels = [[" "] * 120 for _ in range(35)]
            renderer._map(pixels, player)
            return pixels

        with patch.object(world, "surface_height", wraps=world.surface_height) as query:
            first = draw()
            initial_queries = query.call_count
            self.assertLess(initial_queries, 12000)
            self.assertTrue(any("LOCAL" in "".join(row) for row in first))
            self.assertTrue(any("^" in row for row in renderer._map_rows))
            self.assertTrue(any("~" in row for row in renderer._map_rows))
            player.x += 5
            self.assertNotEqual(first, draw())
            self.assertEqual(query.call_count, initial_queries)
            player.x += 16
            draw()
            self.assertGreater(query.call_count, initial_queries)
            previous_queries = query.call_count
            world.box(255, 270, 0, 260, 275, 11, GRASS)
            draw()
            self.assertGreater(query.call_count, previous_queries)


if __name__ == "__main__":
    unittest.main()

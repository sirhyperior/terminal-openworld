"""Prepared render queries retain the uncropped exact shape result."""

import random
import unittest
from unittest.mock import patch

from ascii3d.surfaces import HeightField, SolidBox
from ascii3d.world import FLOOR, World


class PreparedGeometryTests(unittest.TestCase):
    def test_solid_tree_matches_grid_with_overlaps_inside_origins_and_coincident_faces(self):
        world = World.empty(64, 64, 32)
        for floor in (1, 7, 13):
            world.add_stair_flight(8, 8, 3, 10, floor, floor + 5)
            world.add_stair_flight(16, 8, 3, 10, floor, floor + 5, direction=-1)
        world.add_solid(SolidBox(8, 8, 1, 11, 9, 2, 3))
        world.add_solid(SolidBox(8, 8, 1, 11, 9, 2, 4))
        query = world.geometry_query((0, 0, 64, 64), ())
        _, chunks, size, tree = world._solid_query_cache
        self.assertIsNotNone(tree)
        rng = random.Random(7381)
        cases = [((7, 8, 1.5), (1, 0, 0), 48), ((8, 8, 1), (0, 0, 1), 48),
                 ((8.5, 8.5, 1.5), (1, 0, 0), 48), ((9, 7, 2), (0, 1, 0), 1)]
        cases += [(tuple(rng.uniform(0, 24) for _ in range(3)),
                   tuple(rng.uniform(-1.5, 1.5) for _ in range(3)), rng.uniform(0, 48))
                  for _ in range(1000)]
        fallbacks = 0
        with patch.object(world, "_solid_hit", wraps=world._solid_hit) as grid:
            for origin, direction, limit in cases:
                entry = tree[0].ray_entry(origin, direction, limit)
                expected = world._solid_hit(origin, direction, limit, chunks, entry, size) if entry is not None else None
                previous_calls = grid.call_count
                with self.subTest(origin=origin, direction=direction, limit=limit):
                    self.assertEqual(query(origin, direction, limit), expected)
                fallbacks += grid.call_count - previous_calls
            self.assertGreater(fallbacks, 0)
        origin, direction = (9, 7, 6.5), (0, 1, 0)
        with patch.object(SolidBox, "ray_hit", autospec=True, side_effect=SolidBox.ray_hit) as exact:
            self.assertIsNone(query(origin, direction, 48))
            tree_calls = exact.call_count
            exact.reset_mock()
            self.assertIsNone(world._solid_hit(origin, direction, 48, chunks, size=size))
            self.assertLess(tree_calls, exact.call_count)

    def test_camera_forward_bound_cannot_exceed_any_selected_hit(self):
        world = World.empty(32, 32, 12)
        world.add_stair_flight(8, 8, 3, 10, 1, 6)
        origin = (1.5, 9, 2)
        query = world.geometry_query((0, 0, 32, 32), ((1, 0, 0, -1.5), (-1, 0, 0, 49.5)))
        self.assertAlmostEqual(query.minimum_depth, 6.5, places=6)
        for dy in (-0.1, 0, 0.1, 0.5):
            for dz in (-0.1, 0, 0.1):
                hit = query(origin, (1, dy, dz), 48)
                if hit is not None:
                    self.assertLessEqual(query.minimum_depth, hit.distance)

    def test_first_and_cached_stair_selection_keep_distant_ground_in_view(self):
        world = World.empty(32, 32, 12)
        world.heightfield = HeightField(32, 32, [1 + 0.1 * x + 0.05 * y
                                                for y in range(33) for x in range(33)])
        world.add_solid(SolidBox(10, 10, 1, 11, 11, 2, FLOOR))
        origin, direction = (2.5, 2.5, 6), (1, 0, -0.1)
        expected = world.geometry_hit(origin, direction, 48)
        self.assertIsNotNone(expected)
        for _ in range(2):
            query = world.geometry_query((0, 0, 32, 32), ())
            self.assertEqual(query(origin, direction, 48), expected)

    def test_fine_stair_index_matches_exact_queries_at_cell_corners(self):
        world = World.empty(64, 64, 16)
        world.add_stair_flight(8, 8, 3, 10, 1, 6)
        query = world.geometry_query((0, 0, 64, 64), ())
        rng = random.Random(396)
        cases = [((7, 7, 1.5), (1, 1, 0)), ((7, 8, 1.5), (1, 0, 0)),
                 ((9, 19, 8), (0, -1, -0.5))]
        cases += [(tuple(rng.uniform(0, 20) for _ in range(3)),
                   tuple(rng.uniform(-1, 1) for _ in range(3))) for _ in range(200)]
        for origin, direction in cases:
            with self.subTest(origin=origin, direction=direction):
                self.assertEqual(query(origin, direction, 48), world.geometry_hit(origin, direction, 48))

    def test_large_shapes_and_later_insertions_preserve_nearest_hits(self):
        world = World.empty(64, 64, 16)
        world.add_solid(SolidBox(8, 0, 1, 64, 64, 2, FLOOR))
        query = world.geometry_query((0, 0, 64, 64), ())
        origin, direction = (1.5, 3.5, 1.5), (1, 0, 0)
        self.assertEqual(query(origin, direction, 48), world.geometry_hit(origin, direction, 48))
        self.assertAlmostEqual(query(origin, direction, 48).distance, 6.5)
        world.add_solid(SolidBox(2, 3, 1, 3, 4, 2, FLOOR))
        refreshed = world.geometry_query((0, 0, 64, 64), ())
        self.assertEqual(refreshed(origin, direction, 48), world.geometry_hit(origin, direction, 48))
        self.assertAlmostEqual(refreshed(origin, direction, 48).distance, 0.5)


if __name__ == "__main__":
    unittest.main()

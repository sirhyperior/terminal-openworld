"""Prepared render queries retain the uncropped exact shape result."""

import random
import unittest

from ascii3d.surfaces import HeightField, SolidBox
from ascii3d.world import FLOOR, World


class PreparedGeometryTests(unittest.TestCase):
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

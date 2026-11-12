"""Shared exact surface queries used by rendering, movement and projectiles."""

import math
import random
import unittest

from ascii3d.surfaces import HeightField, SolidBox, SurfaceHit
from ascii3d.world import AIR, FLOOR, GRASS, PATH, World


class SurfaceTests(unittest.TestCase):
    def test_origin_relative_cache_tracks_moving_and_mutable_ray_origins(self):
        field = HeightField(12, 12, [1 + 0.3 * x + 0.2 * y
                                   for y in range(13) for x in range(13)])
        origin = [3.5, 4.5, 7.0]
        direction = (0.2, 0.1, -1.0)
        length = math.sqrt(1 + 0.3 ** 2 + 0.2 ** 2)
        for pose in ((3.5, 4.5, 7), (3.5, 4.5, 8), (3.7, 4.8, 8), (3.5, 4.5, 7)):
            origin[:] = pose
            hit = field.ray_hit(origin, direction, 12)
            expected = (1 + 0.3 * origin[0] + 0.2 * origin[1] - origin[2]) / (-1 - 0.3 * 0.2 - 0.2 * 0.1)
            self.assertAlmostEqual(hit.distance, expected, places=12)
            for actual, component in zip(hit.normal, (-0.3 / length, -0.2 / length, 1 / length)):
                self.assertAlmostEqual(actual, component, places=12)

    def test_chunked_rays_match_independent_all_triangle_reference(self):
        size = 18
        field = HeightField(size, size, [2 + math.sin(x * 0.7) * math.cos(y * 0.3)
                                         for y in range(size + 1) for x in range(size + 1)])
        rng = random.Random(3251)
        for _ in range(80):
            origin = (rng.uniform(1, 17), rng.uniform(1, 17), 5.0)
            direction = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1.6, -0.15))
            expected = []
            for y in range(size):
                for x in range(size):
                    h00, h10, h01, h11 = field._corners(x, y)
                    for a, b, second in ((h10 - h00, h11 - h10, False),
                                          (h11 - h01, h01 - h00, True)):
                        denominator = direction[2] - a * direction[0] - b * direction[1]
                        if denominator >= -1e-12:
                            continue
                        t = (h00 + a * (origin[0] - x) + b * (origin[1] - y) - origin[2]) / denominator
                        u, v = origin[0] + direction[0] * t - x, origin[1] + direction[1] * t - y
                        if 0 <= t <= 30 and 0 <= u <= 1 and 0 <= v <= 1 and ((v >= u) if second else (v <= u)):
                            expected.append(t)
            actual = field.ray_hit(origin, direction, 30)
            if expected:
                self.assertIsNotNone(actual)
                self.assertAlmostEqual(actual.distance, min(expected), places=7)
            else:
                self.assertIsNone(actual)

    def test_exact_circular_support_on_slopes_matches_collision_and_occlusion(self):
        world = World.empty(12, 12, 10)
        world.heightfield = HeightField(12, 12, [6 + 0.3 * x - 0.4 * y
                                                for y in range(13) for x in range(13)])
        x, y, radius = 5.25, 4.5, 0.22
        top = 6 + 0.3 * x - 0.4 * y + 0.5 * radius
        support = world.walk_support(x, y, top)
        self.assertAlmostEqual(support[0], top)
        self.assertFalse(world.collides(x, y, top))
        self.assertTrue(world.collides(x, y, top - 0.001))
        self.assertEqual(world.contact_material(x, y, top), GRASS)
        point = world.surface_height(x, y)
        self.assertAlmostEqual(world.solid_hit((x, y, point + 2), (0, 0, -1), 3), 2)
        self.assertFalse(world.line_clear((x, y, point + 2), (0, 0, -1), 3))

    def test_authored_voxel_cuts_and_repaints_invalidate_support_and_rays(self):
        world = World.empty(8, 8, 8)
        world.heightfield = HeightField(8, 8, [2.5] * 81)
        self.assertTrue(world.collides(3.5, 3.5, 2.4))
        world.heightfield.paint_cell(3, 3, PATH)
        self.assertEqual(world.contact_material(3.5, 3.5, 2.5), PATH)
        world.box(3, 3, 2, 4, 4, 3, AIR)
        self.assertFalse(world.collides(3.5, 3.5, 2.4))
        self.assertIsNone(world.geometry_hit((3.5, 3.5, 5), (0, 0, -1), 5))
        world.box(3, 3, 0, 4, 4, 4, FLOOR)
        self.assertEqual(world.surface_height(3.5, 3.5), 4)
        self.assertAlmostEqual(world.solid_hit((3.5, 3.5, 5), (0, 0, -1), 5), 1)

    def test_shared_stairs_deduplicate_and_reverse_the_same_geometry(self):
        world = World.empty(20, 20, 8)
        boxes = world.add_stair_flight(2, 3, 3, 10, 1, 6)
        self.assertEqual(len(boxes), 20)
        world.add_stair_flight(2, 3, 3, 10, 1, 6)
        self.assertEqual(len(world.solids), 20)
        world.add_stair_flight(10, 3, 3, 10, 1, 6, direction=-1)
        for step in range(20):
            self.assertEqual(world.surface_height(3, 3.25 + step * 0.5), 1.25 + step * 0.25)
            self.assertEqual(world.surface_height(11, 12.75 - step * 0.5), 1.25 + step * 0.25)

    def test_box_nearest_hit_uses_original_ray_parameter(self):
        world = World.empty(20, 20, 10)
        world.add_solid(SolidBox(3, 3, 1, 4, 4, 2.25, FLOOR))
        hit = world.geometry_hit((0, 3.5, 1.5), (2, 0, 0), 8)
        self.assertAlmostEqual(hit.distance, 1.5)
        self.assertEqual(hit.normal, (-1, 0, 0))
        self.assertTrue(world.collides(3.5, 3.5, 2.2))
        self.assertFalse(world.collides(3.5, 3.5, 2.25))

    def test_fast_box_queries_match_independent_slabs_for_inside_corners_and_limits(self):
        box = SolidBox(2, 3, 1, 4, 6, 5, FLOOR)

        def reference(origin, direction, limit):
            entry, exit = 0.0, limit
            normal = (0.0, 0.0, 1.0)
            for axis, (low, high) in enumerate(((2, 4), (3, 6), (1, 5))):
                o, d = origin[axis], direction[axis]
                if abs(d) < 1e-12:
                    if o < low or o > high:
                        return None
                    continue
                first, last = (low - o) / d, (high - o) / d
                sign = -1.0
                if first > last:
                    first, last, sign = last, first, 1.0
                if first > entry:
                    entry = first
                    normal = tuple(sign if index == axis else 0.0 for index in range(3))
                exit = min(exit, last)
                if entry > exit + 1e-10:
                    return None
            return SurfaceHit(entry, FLOOR, normal) if exit >= 0 else None

        cases = [((3, 4, 2), (1, 0, 0), 10),
                 ((3, 4, 2), (0, -1, 0), 10),
                 ((3, 4, 2), (0, 0, 0), 10),
                 ((2, 3, 1), (1, 1, 1), 10),
                 ((1, 2, 0), (1, 1, 1), 1),
                 ((1, 2, 0), (1, 1, 1), 1 - 2e-10),
                 ((5, 6, 5), (-1, 0, 0), 1),
                 ((1, 3, 2), (1, 1e-13, 0), 10)]
        rng = random.Random(841)
        cases.extend((tuple(rng.uniform(-2, 8) for _ in range(3)),
                      tuple(rng.uniform(-2, 2) for _ in range(3)), rng.uniform(0, 12))
                     for _ in range(250))
        for origin, direction, limit in cases:
            with self.subTest(origin=origin, direction=direction, limit=limit):
                expected = reference(origin, direction, limit)
                self.assertEqual(box.ray_hit(origin, direction, limit), expected)
                self.assertEqual(box.ray_entry(origin, direction, limit),
                                 expected.distance if expected is not None else None)

    def test_ray_cache_repaints_and_cuts_preserve_live_materials_and_support(self):
        field = HeightField(8, 8, [1 + 0.1 * x + 0.2 * y
                                   for y in range(9) for x in range(9)])
        origin, direction = (3.5, 3.5, 6), (0, 0, -1)
        initial = field.ray_hit(origin, direction, 8)
        field.paint_cell(3, 3, PATH)
        repainted = field.ray_hit(origin, direction, 8)
        self.assertEqual(repainted.distance, initial.distance)
        self.assertEqual(repainted.normal, initial.normal)
        self.assertEqual(repainted.material, PATH)
        field.edit_box(3, 3, 1, 4, 4, 3, AIR)
        self.assertIsNone(field.ray_hit(origin, direction, 8))
        self.assertEqual(field.footprint(3.5, 3.5, 0.22), ())

    def test_fine_traversal_retains_chunk_corners_and_minimum_parameter(self):
        field = HeightField(18, 18, [2.5] * 361)
        cases = [((7, 7, 5), (1, 1, -1)),
                 ((9, 9, 5), (-1, -1, -1)),
                 ((8, 8, 5), (0, 0, -1)),
                 ((-2, 8, 5), (2, 0, -0.5)),
                 ((18, 9, 5), (-2, 0, -0.5))]
        for origin, direction in cases:
            distance = (2.5 - origin[2]) / direction[2]
            for minimum in (0.0, distance - 0.1, distance):
                with self.subTest(origin=origin, minimum=minimum):
                    hit = field.ray_hit(origin, direction, distance + 0.1, minimum=minimum)
                    self.assertIsNotNone(hit)
                    self.assertAlmostEqual(hit.distance, distance, places=8)
                    self.assertEqual(hit.normal, (0, 0, 1))

    def test_chunk_envelope_retains_interior_peak_and_rebuilds_after_cuts(self):
        heights = [2.0] * 324
        heights[5 * 18 + 6] = 8.0
        field = HeightField(17, 17, heights)
        origin, direction = (5.9, 4.9, 10), (0, 0, -1)
        expected = 10 - field.height_at(origin[0], origin[1])
        initial = field.ray_hit(origin, direction, 12)
        self.assertAlmostEqual(initial.distance, expected)
        field.paint_cell(5, 4, PATH)
        self.assertEqual(field.ray_hit(origin, direction, 12).material, PATH)
        field.edit_box(5, 4, 1, 6, 5, 9, AIR)
        self.assertIsNone(field.ray_hit(origin, direction, 12))
        # The neighboring triangle still shares the peak vertex. A cut must
        # invalidate the envelope without discarding surviving geometry.
        origin = (6.1, 5.1, 10)
        expected = 10 - field.height_at(origin[0], origin[1])
        self.assertAlmostEqual(field.ray_hit(origin, direction, 12).distance, expected)

    def test_chunk_clipping_preserves_near_parallel_endpoint_hit_and_normal(self):
        field = HeightField(19, 17, [4 + 0.25 * x - 0.125 * y
                                     for y in range(18) for x in range(20)])
        dz = 0.1875 - 2 ** -18
        origin, direction = (6, 7, 5 - 2 * dz), (1, 0.5, dz)
        halo = 2 ** -30
        length = math.sqrt(1 + 0.25 ** 2 + 0.125 ** 2)
        normal = (-0.25 / length, 0.125 / length, 1 / length)
        for minimum in (0, 2 - halo, 2, 2 + halo):
            for limit in (2 - halo, 2, 2 + halo, 2.1):
                with self.subTest(minimum=minimum, limit=limit):
                    hit = field.ray_hit(origin, direction, limit, minimum=minimum)
                    if minimum > limit:
                        self.assertIsNone(hit)
                    else:
                        self.assertEqual(hit.distance, 2)
                        self.assertEqual(hit.normal, normal)

    def test_solid_chunk_corners_and_parallel_boundary_rays_remain_closed(self):
        world = World.empty(20, 20, 10)
        box = world.add_solid(SolidBox(8, 7, 1, 9, 8, 2, FLOOR))
        for origin, direction in (((7, 7, 1.5), (1, 1, 0)),
                                  ((7, 8, 1.5), (1, 0, 0))):
            self.assertEqual(world.geometry_hit(origin, direction, 3), box.ray_hit(origin, direction, 3))


if __name__ == "__main__":
    unittest.main()

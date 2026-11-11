"""Continuous hills and fine stairs share exact opaque renderer depths."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import CombatState, Enemy
from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.surfaces import HeightField, SolidBox
from ascii3d.world import FLOOR, GRASS, PATH, STONE, WATER, WATER_LEVEL, World


class SmoothSurfaceRenderingTests(unittest.TestCase):
    @staticmethod
    def field_world(width=24, depth=24, *, slope_x=0.0, slope_y=0.0, base=1.0,
                    material=GRASS):
        world = World.empty(width, depth, 24)
        world.heightfield = HeightField(width, depth,
                                       [base + x * slope_x + y * slope_y
                                        for y in range(depth + 1)
                                        for x in range(width + 1)], material=material)
        return world

    @staticmethod
    def scene_with_depths(renderer, player, width=60, height=24):
        captured = []

        def capture(pixels, depths, *args):
            captured.append([row[:] for row in depths])

        with patch.object(renderer.scenery, "draw", side_effect=capture):
            pixels = renderer.scene(player, width, height)
        return pixels, captured[0]

    @staticmethod
    def ray(renderer, player, x, y):
        u, v = renderer._columns[x], renderer._rows[y]
        cy, sy = math.cos(player.yaw), math.sin(player.yaw)
        cp, sp = math.cos(player.pitch), math.sin(player.pitch)
        return cy * (cp - v * sp) + u * sy, sy * (cp - v * sp) - u * cy, sp + v * cp

    def test_sloped_plane_matches_analytic_depth_at_every_visible_sample(self):
        world = self.field_world(slope_x=0.17, slope_y=0.09)
        player = Player(x=4.5, y=4.5, z=2, yaw=0.7, pitch=-0.25)
        renderer = Renderer(world)
        pixels, depths = self.scene_with_depths(renderer, player)
        count = 0
        for y, row in enumerate(depths):
            for x, distance in enumerate(row):
                dx, dy, dz = self.ray(renderer, player, x, y)
                denominator = dz - 0.17 * dx - 0.09 * dy
                if abs(denominator) < 1e-10:
                    continue
                expected = (1 + 0.17 * player.x + 0.09 * player.y - player.eye_z) / denominator
                hx, hy = player.x + dx * expected, player.y + dy * expected
                if 0 < expected < 48 and 0 < hx < world.width and 0 < hy < world.depth:
                    count += 1
                    self.assertAlmostEqual(distance, expected, places=6)
                    self.assertIn(pixels[y][x], ".,;\"'")
        self.assertGreater(count, 500)

    def test_upward_hill_hits_survive_voxel_sky_and_empty_space_skips(self):
        world = self.field_world(slope_y=0.7)
        player = Player(x=12.5, y=1.5, z=2.05, yaw=math.pi / 2, pitch=0.2)
        fast, exact = Renderer(world), Renderer(world, skip_empty_space=False)
        pixels, depths = self.scene_with_depths(fast, player, 61, 25)
        self.assertEqual(pixels, self.scene_with_depths(exact, player, 61, 25)[0])
        self.assertLess(depths[12][30], 48)
        self.assertNotEqual(pixels[12][30], " ")

    def test_hillside_normal_changes_turf_light_at_the_same_surface_point(self):
        player = Player(x=12, y=4.5, z=10, yaw=math.pi / 2, pitch=-0.26)
        views = []
        for slope, base in ((0.8, 0.4), (-0.8, 19.6)):
            renderer = Renderer(self.field_world(slope_x=slope, base=base))
            pixels, depths = self.scene_with_depths(renderer, player, 61, 25)
            views.append((pixels[12][30], depths[12][30]))
        self.assertAlmostEqual(views[0][1], views[1][1])
        self.assertNotEqual(views[0][0], views[1][0])

    def test_subvoxel_stair_treads_receive_exact_depth_in_front_of_voxel_floor(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.add_solid(SolidBox(7, 7, 1, 11, 9, 1.25, material=FLOOR))
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2, pitch=-0.5)
        renderer = Renderer(world)
        pixels, depths = self.scene_with_depths(renderer, player, 61, 31)
        tread_samples = 0
        for y, row in enumerate(depths):
            for x, distance in enumerate(row):
                dx, dy, dz = self.ray(renderer, player, x, y)
                if dz >= 0:
                    continue
                expected = (1.25 - player.eye_z) / dz
                hx, hy = player.x + expected * dx, player.y + expected * dy
                if 7 < hx < 11 and 7 < hy < 9:
                    tread_samples += 1
                    self.assertAlmostEqual(distance, expected, places=6)
                    self.assertNotEqual(pixels[y][x], " ")
        self.assertGreater(tread_samples, 20)

    def test_voxel_wall_occludes_analytic_geometry_behind_it(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.box(0, 7, 1, 24, 8, 12, STONE)
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        baseline = Renderer(world).scene(player, 60, 24)
        world.add_solid(SolidBox(0, 9, 1, 24, 10, 11.75, material=GRASS))
        self.assertEqual(baseline, Renderer(world).scene(player, 60, 24))

    def test_opaque_voxel_wall_bounds_queries_for_geometry_behind_it(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.box(0, 7, 1, 24, 8, 12, STONE)
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        baseline = Renderer(world).scene(player, 61, 25)
        world.add_solid(SolidBox(0, 9, 1, 24, 10, 11.75, material=GRASS))
        original = world.geometry_query
        central_limits = []

        def select(bounds, planes):
            query = original(bounds, planes)
            self.assertIsNotNone(query)

            def observe(origin, direction, limit):
                if abs(direction[0]) < 1e-10 and abs(direction[2]) < 1e-10:
                    central_limits.append(limit)
                return query(origin, direction, limit)

            return observe

        with patch.object(world, "geometry_query", side_effect=select):
            self.assertEqual(baseline, Renderer(world).scene(player, 61, 25))
        self.assertEqual(len(central_limits), 1)
        self.assertAlmostEqual(central_limits[0], 2.5, places=7)

    def test_query_minimum_depth_omits_geometry_hidden_by_nearer_voxels(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.box(0, 7, 1, 24, 8, 12, STONE)
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        baseline = self.scene_with_depths(Renderer(world), player, 61, 25)
        world.add_solid(SolidBox(0, 9, 1, 24, 10, 11.75, material=GRASS))
        original = world.geometry_query
        calls = []

        def select(bounds, planes):
            query = original(bounds, planes)

            def observe(origin, direction, limit):
                calls.append(limit)
                return query(origin, direction, limit)

            observe.minimum_depth = query.minimum_depth
            return observe

        with patch.object(world, "geometry_query", side_effect=select):
            self.assertEqual(baseline, self.scene_with_depths(Renderer(world), player, 61, 25))
        self.assertFalse(calls)

    def test_query_minimum_depth_retains_coincident_voxel_analytic_faces(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.box(0, 7, 1, 24, 8, 12, STONE)
        world.add_solid(SolidBox(0, 7, 1, 24, 8, 11.75, material=GRASS))
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        actual = self.scene_with_depths(Renderer(world), player, 61, 25)
        original = world.geometry_query
        calls = []

        def select(bounds, planes):
            query = original(bounds, planes)

            def observe(origin, direction, limit):
                calls.append(limit)
                return query(origin, direction, limit)

            return observe  # A query without metadata remains a valid reference.

        with patch.object(world, "geometry_query", side_effect=select):
            expected = self.scene_with_depths(Renderer(world), player, 61, 25)
        self.assertTrue(calls)
        self.assertEqual(actual, expected)

    def test_analytic_opaque_box_occludes_enemy_body_and_aimed_label(self):
        world = self.field_world(material=FLOOR)
        world.add_solid(SolidBox(6, 6, 1, 12, 6.5, 4.25, material=FLOOR))
        world.combat = CombatState(enemies=[Enemy("Hidden target", 8.5, 8.5)])
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        renderer = Renderer(world)
        hidden = renderer.frame(player, 80, 30)
        self.assertNotIn("Hidden target", "\n".join(hidden))
        world.combat.enemies.clear()
        self.assertEqual(hidden, renderer.frame(player, 80, 30))

    def test_doors_and_analytic_boxes_share_nearest_depth(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.doors.append(Door("Test door", 6, 6, 5, double=False))
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        baseline = Renderer(world).scene(player, 61, 25)
        world.add_solid(SolidBox(7, 7, 1, 10, 8, 3.5, material=STONE))
        self.assertEqual(baseline, Renderer(world).scene(player, 61, 25))
        world.add_solid(SolidBox(7, 5, 1, 10, 5.25, 3.5, material=STONE))
        pixels, depths = self.scene_with_depths(Renderer(world), player, 61, 25)
        self.assertNotEqual(baseline, pixels)
        self.assertAlmostEqual(depths[12][30], 0.5)

    def test_water_plane_wins_only_when_above_continuous_ground(self):
        for ground in (0.12, 0.9):
            with self.subTest(ground=ground):
                world = World.empty(24, 24, 24)
                world.box(0, 0, 0, 24, 24, 1, WATER)
                world.heightfield = HeightField(24, 24, [ground] * 625, material=GRASS)
                player = Player(x=8.5, y=4.5, yaw=math.pi / 2, pitch=-0.5)
                renderer = Renderer(world)
                _, depths = self.scene_with_depths(renderer, player, 61, 31)
                dz = self.ray(renderer, player, 30, 15)[2]
                expected = (max(ground, WATER_LEVEL) - player.eye_z) / dz
                self.assertAlmostEqual(depths[15][30], expected, places=6)

    def test_outside_frustum_geometry_restores_voxel_only_ray_path(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        player = Player(x=8.5, y=8.5, yaw=0)
        baseline = Renderer(world).scene(player, 60, 24)
        world.add_solid(SolidBox(2, 7, 1, 3, 10, 9.25, material=STONE))
        queries = []
        original = world.geometry_query

        def query(bounds, planes):
            result = original(bounds, planes)
            queries.append(result)
            return result

        with patch.object(world, "geometry_query", side_effect=query):
            self.assertEqual(baseline, Renderer(world).scene(player, 60, 24))
        self.assertEqual(queries, [None])

    def test_frustum_culling_matches_unculled_tall_near_shapes_and_slopes(self):
        world = self.field_world(slope_x=0.17, slope_y=0.09)
        world.add_solid(SolidBox(4.6, 4, 1, 5.1, 5, 18.75, material=FLOOR))
        world.add_solid(SolidBox(8, 12, 1, 9, 13, 20.25, material=STONE))
        for width, height, yaw, pitch in ((61, 25, 0, 0.7), (120, 60, 0.8, -0.7),
                                           (60, 80, 1.8, 0.3), (61, 25, -1.1, -0.3)):
            with self.subTest(size=(width, height), yaw=yaw, pitch=pitch):
                player = Player(x=4.5, y=4.5, z=2, yaw=yaw, pitch=pitch)
                culled = self.scene_with_depths(Renderer(world), player, width, height)
                with patch.object(world, "geometry_query", return_value=world.geometry_hit):
                    unculled = self.scene_with_depths(Renderer(world), player, width, height)
                self.assertEqual(culled, unculled)

    def test_sample_ray_endpoints_stay_inside_world_space_culling_bounds(self):
        world = self.field_world()
        player = Player(x=4.5, y=5.5, z=2, yaw=0.8, pitch=0.6)
        renderer = Renderer(world)
        queries = []

        def query(bounds, planes):
            queries.append((bounds, planes))
            return world.geometry_hit

        with patch.object(world, "geometry_query", side_effect=query):
            renderer.scene(player, 61, 35)
        self.assertEqual(len(queries), 1)
        (xmin, ymin, xmax, ymax), planes = queries[0]
        for x, y in ((0, 0), (60, 0), (0, 34), (60, 34), (30, 17)):
            direction = self.ray(renderer, player, x, y)
            for distance in (0, 0.125, 48):
                point = (player.x + direction[0] * distance,
                         player.y + direction[1] * distance,
                         player.eye_z + direction[2] * distance)
                self.assertGreaterEqual(point[0], xmin - 1e-8)
                self.assertLessEqual(point[0], xmax + 1e-8)
                self.assertGreaterEqual(point[1], ymin - 1e-8)
                self.assertLessEqual(point[1], ymax + 1e-8)
                for nx, ny, nz, offset in planes:
                    self.assertGreaterEqual(nx * point[0] + ny * point[1] + nz * point[2] + offset, -1e-8)

    def test_analytic_skyline_omits_proven_sky_queries_without_changing_depth(self):
        world = self.field_world()
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        original = world.geometry_query
        rising_calls = []

        def select(bounds, planes):
            query = original(bounds, planes)

            def observe(origin, direction, limit):
                if direction[2] > 0:
                    rising_calls.append(direction)
                return query(origin, direction, limit)

            return observe

        with patch.object(world, "geometry_query", side_effect=select):
            accelerated = self.scene_with_depths(Renderer(world), player)
        self.assertFalse(rising_calls)
        ordinary = Renderer(world)
        with patch.object(world, "geometry_query", side_effect=select), \
                patch.object(ordinary, "_prepare_analytic_horizon", return_value=None):
            reference = self.scene_with_depths(ordinary, player)
        self.assertTrue(rising_calls)
        self.assertEqual(accelerated, reference)

    def test_analytic_skyline_refines_origin_chunk_and_preserves_wrap_and_near_shapes(self):
        world = World.empty(8, 8, 24)
        heights = [1] * 81
        heights[7 * 9 + 7] = 10
        world.heightfield = HeightField(8, 8, heights, material=GRASS)
        renderer = Renderer(world)
        player = Player(x=1.5, y=1.5, yaw=0, pitch=0.15)
        accelerated = self.scene_with_depths(renderer, player, 80, 40)
        self.assertIsNotNone(renderer._analytic_sky_horizon)
        self.assertTrue(any(math.isfinite(value) for value in renderer._analytic_sky_horizon))
        ordinary = Renderer(world)
        with patch.object(ordinary, "_prepare_analytic_horizon", return_value=None):
            self.assertEqual(accelerated, self.scene_with_depths(ordinary, player, 80, 40))
        world.add_solid(SolidBox(6, 1, 1, 7, 2, 7.25, material=FLOOR))
        for x, y, yaw, pitch, width, height in (
                (1.000001, 1.999999, -1e-7, 0.25, 240, 45),
                (1.999999, 1.000001, math.tau - 1e-7, 0.2, 60, 100),
                (5.999999, 1.5, 0, 0.4, 80, 40),
                (5.2, 1.5, math.pi / 2, -0.35, 100, 60)):
            with self.subTest(pose=(x, y, yaw, pitch), size=(width, height)):
                player = Player(x=x, y=y, yaw=yaw, pitch=pitch)
                ordinary = Renderer(world)
                accelerated = self.scene_with_depths(Renderer(world), player, width, height)
                with patch.object(ordinary, "_prepare_analytic_horizon", return_value=None):
                    self.assertEqual(accelerated, self.scene_with_depths(ordinary, player, width, height))
        world.add_solid(SolidBox(5.7, 1, 1, 5.9, 2, 6.25, material=FLOOR))
        renderer = Renderer(world)
        self.scene_with_depths(renderer, Player(x=5.2, y=1.5, yaw=0))
        self.assertIsNone(renderer._analytic_sky_horizon)

    def test_analytic_skyline_cache_tracks_field_world_eye_and_frustum_extent(self):
        world = self.field_world()
        renderer = Renderer(world)
        player = Player(x=2.2, y=2.3)
        renderer.scene(player, 80, 30)
        cached = renderer._analytic_sky_horizon
        player.x += 0.1
        renderer.scene(player, 80, 30)
        self.assertIs(renderer._analytic_sky_horizon, cached)
        for change in (lambda: world.add_solid(SolidBox(12, 14, 1, 13, 15, 8.25)),
                       lambda: world.heightfield.paint_cell(1, 1, PATH),
                       lambda: setattr(player, "z", player.z + 0.3)):
            cached = renderer._analytic_sky_horizon
            change()
            renderer.scene(player, 80, 30)
            self.assertIsNot(renderer._analytic_sky_horizon, cached)
        player.pitch = 0.6
        renderer.scene(player, 80, 30)
        cached = renderer._analytic_sky_horizon
        renderer.scene(player, 60, 120)
        self.assertIsNot(renderer._analytic_sky_horizon, cached)

    def test_first_geometry_selection_and_cached_frames_have_identical_depths(self):
        world = self.field_world(slope_x=0.17, slope_y=0.09)
        world.add_solid(SolidBox(7, 7, 1, 8, 8, 8.25, material=FLOOR))
        renderer = Renderer(world)
        player = Player(x=4.5, y=4.5, z=2, yaw=0.8, pitch=-0.2)
        first = self.scene_with_depths(renderer, player, 120, 60)
        self.assertEqual(first, self.scene_with_depths(renderer, player, 120, 60))


if __name__ == "__main__":
    unittest.main()

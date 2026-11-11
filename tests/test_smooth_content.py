"""Continuous generated ground, material roads and the shared west staircase."""

import math
import unittest

from ascii3d.player import Player
from ascii3d.scenery import Scenery
from ascii3d.terrain import add_landmarks, build_terrain, terrain_height
from ascii3d.world import AIR, GRASS, PATH, STONE, WOOD, World


class SmoothTerrainContentTests(unittest.TestCase):
    def test_integer_planes_use_exact_voxels_while_fractional_neighbors_keep_shared_vertices(self):
        world = World.empty(150, 80, 32)
        build_terrain(world)
        field = world.heightfield
        for x, y in ((40, 40), (111, 50)):
            self.assertEqual(field.enabled[y * world.width + x], 0)
            self.assertIsNone(field.height_at(x + 0.5, y + 0.5))
            self.assertEqual(world.surface_height(x + 0.5, y + 0.5), 1)
            self.assertEqual(world.surface_material(x + 0.5, y + 0.5), GRASS)
        self.assertEqual(field.enabled[50 * world.width + 112], 1)
        self.assertAlmostEqual(field.height_at(112, 50.5), 1)
        self.assertGreater(field.height_at(112.5, 50.5), 1)
        before = world.surface_height(112.5, 50.5)
        world.box(111, 50, 0, 112, 51, 1, PATH)
        self.assertEqual(world.surface_height(111.5, 50.5), 1)
        self.assertEqual(world.surface_material(111.5, 50.5), PATH)
        self.assertAlmostEqual(world.surface_height(112.5, 50.5), before)
        # Exact integer building pads also fall back to their grass foundation.
        self.assertEqual(field.enabled[50 * world.width + 140], 0)
        self.assertEqual(world.surface_height(140.5, 50.5), 5)

    def test_elevations_vary_below_voxel_scale_and_join_hub_river_and_pads_continuously(self):
        for x, y in ((200.2, 220.3), (320.2, 208.3), (130.2, 30.3)):
            with self.subTest(point=(x, y)):
                height = terrain_height(x, y)
                self.assertGreater(abs(height - round(height)), 1e-4)
                self.assertLess(abs(terrain_height(x + 0.01, y) - height), 0.02)
                self.assertLess(abs(terrain_height(x, y + 0.01) - height), 0.02)
        # Hub edges, supported-pad blend edges and both ravine entrances.
        for x, y in ((112, 50), (50, 112), (112, 112), (114, 52),
                     (132, 52), (310, 250), (310, 330)):
            with self.subTest(boundary=(x, y)):
                for dx, dy in ((1e-5, 0), (0, 1e-5)):
                    self.assertLess(abs(terrain_height(x - dx, y - dy)
                                        - terrain_height(x + dx, y + dy)), 1e-3)

    def test_generated_foundations_stay_below_the_exact_ground_and_roads_keep_its_shape(self):
        world = World.empty(180, 180, 32)
        world.outdoor_bounds = (0, 0, 180, 180)
        build_terrain(world)
        field = world.heightfield
        self.assertIsNotNone(field)
        for x, y in ((122, 30), (124, 52), (170, 150)):
            low, high = field.cell_bounds(x, y)
            foundation = math.floor(low)
            self.assertEqual(world.get(x, y, foundation), AIR)
            self.assertEqual(world.get(x, y, foundation - 1), GRASS)
            if foundation > 1:
                self.assertEqual(world.get(x, y, foundation - 2), STONE)
            for dx, dy in ((0.01, 0.01), (0.5, 0.5), (0.99, 0.99)):
                feet = world.surface_height(x + dx, y + dy)
                self.assertGreaterEqual(feet, low)
                self.assertLessEqual(feet, high)
                exact = field.height_at(x + dx, y + dy)
                if exact is None:
                    self.assertEqual((low, high, feet), (foundation, foundation, foundation))
                else:
                    self.assertAlmostEqual(feet, exact)
        road_height = world.surface_height(124.5, 52.5)
        scenery = Scenery(world)
        self.assertIn((124, 52), [(x, y) for x, y, _ in scenery.grass_chunk(31, 13)])
        world.box(108, 56, 0, 109, 57, 1, WOOD)
        add_landmarks(world)
        self.assertAlmostEqual(world.surface_height(124.5, 52.5), road_height)
        self.assertEqual(world.surface_material(124.5, 52.5), PATH)
        self.assertEqual(world.surface_material(108.5, 56.5), WOOD)
        self.assertNotIn((124, 52), [(x, y) for x, y, _ in scenery.grass_chunk(31, 13)])
        for tree in world.trees.values():
            self.assertAlmostEqual(tree.base_z, world.surface_height(tree.x, tree.y))
            self.assertEqual(world.surface_material(tree.x, tree.y), GRASS)


class WestStairContentTests(unittest.TestCase):
    def test_west_flight_uses_quarter_risers_and_walks_both_directions_with_headroom(self):
        from ascii3d.map_expansion import _castle

        world = World.empty(112, 112, 12)
        world.box(0, 0, 0, 112, 112, 1, GRASS)
        _castle(world)
        # Each half-unit tread increases support by exactly a quarter unit.
        heights = [world.surface_height(35.5, 32.25 + step * 0.5) for step in range(20)]
        self.assertEqual(heights, [1.25 + step * 0.25 for step in range(20)])
        player = Player(x=35.5, y=31, yaw=math.pi / 2)
        for target, yaw, feet in ((43, math.pi / 2, 6), (31, -math.pi / 2, 1)):
            player.yaw = yaw
            events = []
            for _ in range(720):
                player.update(world, {"w"}, 1 / 120)
                events.extend(player.events)
                self.assertFalse(world.collides(player.x, player.y, player.z))
                if (player.y >= target if yaw > 0 else player.y <= target):
                    break
            self.assertLess(abs(player.y - target), 0.04)
            self.assertAlmostEqual(player.z, feet, places=4)
            self.assertIn("terrain_step", [event.name for event in events])
            self.assertTrue(all(event.surface == "stone" for event in events
                                if event.name == "terrain_step"))


if __name__ == "__main__":
    unittest.main()

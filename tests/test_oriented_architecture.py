"""Actual non-cardinal walls, arch openings, stairs and floor contact."""

from dataclasses import replace
import math
import unittest

from ascii3d.architecture import build_landmark
from ascii3d.orientation import transform_direction, transform_point, voxel_cuboids
from ascii3d.player import Player
from ascii3d.sound_surfaces import surface_kind
from ascii3d.terrain import Landmark, stair_routes
from ascii3d.world import AIR, FLOOR, GRASS, STONE, WOOD, World


class OrientedArchitectureTests(unittest.TestCase):
    @staticmethod
    def fixture(name="THORNWATCH", degrees=17):
        landmark = Landmark(name, (40, 40, 68, 68), 4, math.radians(degrees))
        world = World.empty(112, 112, 32)
        world.box(0, 0, 0, 112, 112, 4, GRASS)
        build_landmark(world, landmark)
        return world, landmark

    def test_voxel_merging_keeps_materials_and_every_carved_opening(self):
        source = World.empty(18, 16, 10)
        source.box(2, 2, 0, 16, 14, 2, GRASS)
        source.box(4, 3, 2, 14, 4, 8, STONE)
        source.box(7, 3, 2, 11, 4, 6, AIR)
        source.box(4, 6, 4, 14, 12, 5, WOOD)
        cells = bytes(source.cells)
        rebuilt = World.empty(18, 16, 10)
        for box in voxel_cuboids(source):
            rebuilt.box(box.x0, box.y0, box.z0, box.x1, box.y1, box.z1, box.material)
        self.assertEqual(bytes(rebuilt.cells), cells)
        self.assertEqual(bytes(source.cells), cells)

    def test_real_openings_and_wall_normals_rotate_together(self):
        for degrees in (17, -23):
            world, landmark = self.fixture(degrees=degrees)
            for x, expected in ((54.5, None), (50.5, 3.0)):
                origin = transform_point(landmark, (x, 37, 5.6))
                direction = transform_direction(landmark, (0, 1, 0))
                hit = world.geometry_hit(origin, direction, 4)
                if expected is None:
                    self.assertIsNone(hit)
                else:
                    self.assertAlmostEqual(hit.distance, expected, places=7)
                    normal = transform_direction(landmark, (0, -1, 0))
                    for actual, value in zip(hit.normal, normal):
                        self.assertAlmostEqual(actual, value, places=7)
            x, y = landmark.to_world(54.5, 40.5)
            self.assertFalse(world.collides(x, y, 4))
            x, y = landmark.to_world(50.5, 40.5)
            self.assertTrue(world.collides(x, y, 4))

    def test_rotated_flights_walk_both_directions_with_exact_stair_foley(self):
        for name, degrees in (("THORNWATCH", 17), ("ASTRAL RELIQUARY", -23)):
            world, landmark = self.fixture(name, degrees)
            self.assertEqual(len(world._oriented_stairs), 3)
            self.assertEqual(sum(solid.stair for solid in world.solids), 60)
            for x, start, end, feet in stair_routes(landmark):
                with self.subTest(name=name, feet=feet):
                    wx, wy = landmark.to_world(x, start)
                    player = Player(x=wx, y=wy, z=feet, yaw=math.pi / 2 + landmark.angle)
                    events = []
                    for _ in range(720):
                        player.update(world, {"w"}, 1 / 120)
                        events.extend(player.events)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                        if landmark.to_local(player.x, player.y)[1] >= end:
                            break
                    self.assertGreaterEqual(landmark.to_local(player.x, player.y)[1], end)
                    self.assertAlmostEqual(player.z, feet + 5, places=6)
                    self.assertIn("terrain_step", [event.name for event in events])
                    self.assertTrue(all(event.surface == "stone" for event in events
                                        if event.name == "terrain_step"))
                    player.yaw -= math.pi
                    for _ in range(720):
                        player.update(world, {"w"}, 1 / 120)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                        if landmark.to_local(player.x, player.y)[1] <= start:
                            break
                    self.assertLessEqual(landmark.to_local(player.x, player.y)[1], start)
                    self.assertAlmostEqual(player.z, feet, places=6)

    def test_complete_rotated_build_has_no_axis_grid_walls_and_is_repeatable(self):
        world, landmark = self.fixture()
        count, cells = len(world.solids), bytes(world.cells)
        build_landmark(world, landmark)
        self.assertEqual(len(world.solids), count)
        self.assertEqual(len(world._oriented_stairs), 3)
        self.assertEqual(bytes(world.cells), cells)
        # The authored body uses exact pieces; its former axis-aligned cells
        # contain only the original ground. The same real roof is still solid.
        self.assertEqual(world.get(40, 42, 6), AIR)
        x, y = landmark.to_world(54.5, 54.5)
        self.assertEqual(surface_kind(world, x, y, 4), "stone")
        self.assertEqual(surface_kind(world, x, y, 9), "wood")
        self.assertAlmostEqual(world.surface_height(x, y), landmark.roof, places=7)
        self.assertIn(world.surface_material(x, y), (FLOOR, WOOD))


if __name__ == '__main__':
    unittest.main()

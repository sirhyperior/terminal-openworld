"""Exact empty-room traversal below roofs, with solid/dynamic/water boundaries."""

import math
import unittest

from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import AIR, BRIDGE, FLOOR, WATER, WOOD, World


def roofed_world():
    world = World.empty(37, 43, 12)
    world.box(0, 0, 0, 37, 43, 1, FLOOR)
    world.box(2, 2, 1, 35, 3, 8)
    world.box(2, 40, 1, 35, 41, 8)
    world.box(2, 3, 1, 3, 40, 8)
    world.box(34, 3, 1, 35, 40, 8)
    world.box(2, 2, 7, 35, 41, 8, WOOD)
    return world


class RoomTraversalTests(unittest.TestCase):
    def assert_exact(self, world, poses, pitches=(-0.5, 0, 0.45)):
        fast = Renderer(world)
        reference = Renderer(world, skip_empty_space=False)
        for x, y, z, yaw in poses:
            for pitch in pitches:
                with self.subTest(pose=(x, y, z, yaw), pitch=pitch):
                    player = Player(x=x, y=y, z=z, yaw=yaw, pitch=pitch)
                    self.assertEqual(fast.scene(player, 80, 26, time_seconds=1.5),
                                     reference.scene(player, 80, 26, time_seconds=1.5))

    def test_long_roofed_room_has_exact_floor_ceiling_and_end_walls(self):
        world = roofed_world()
        self.assert_exact(world, ((18.5, 5.5, 1, math.pi / 2),
                                  (31.5, 36.5, 1, -2.0),
                                  (6.5, 21.5, 1, 0.0)))

    def test_holes_pillars_and_raised_floors_do_not_disappear(self):
        world = roofed_world()
        world.box(16, 12, 7, 20, 18, 8, AIR)
        world.box(8, 20, 1, 13, 25, 3, FLOOR)
        world.box(23, 16, 1, 24, 17, 7)
        world.box(10, 10, 0, 14, 14, 1, AIR)
        self.assert_exact(world, ((18.5, 8.5, 1, math.pi / 2),
                                  (10.5, 22.5, 3, 0.25),
                                  (27.5, 18.5, 1, -2.1),
                                  (12.5, 8.5, 1, math.pi / 2)))

    def test_roofed_water_and_raised_bridge_preserve_surface_intersections(self):
        world = roofed_world()
        world.box(3, 3, 0, 34, 40, 1, WATER)
        world.box(3, 20, 3, 34, 26, 4, BRIDGE)
        self.assert_exact(world, ((18.5, 8.5, 0.12, math.pi / 2),
                                  (18.5, 18.5, 1, math.pi / 2),
                                  (18.5, 22.5, 4, 0.7),
                                  (18.5, 22.5, 0.12, 0.0)),
                          pitches=(-0.65, -0.3, 0, 0.5))

    def test_dynamic_door_panels_remain_in_front_of_cached_empty_rooms(self):
        world = roofed_world()
        door = Door("room door", 13, 18, 5)
        world.doors.append(door)
        for openness in (0, 0.45, 1):
            door.openness = openness
            with self.subTest(openness=openness):
                self.assert_exact(world, ((15.5, 7.5, 1, math.pi / 2),
                                          (15.5, 17.7, 1, math.pi / 2),
                                          (18.5, 23.5, 1, -math.pi / 2)))

    def test_partial_edge_chunks_and_tunnel_exits_match_exact_rays(self):
        world = World.empty(37, 43, 12)
        world.box(0, 0, 0, 37, 43, 1, FLOOR)
        world.box(28, 4, 5, 37, 43, 6, WOOD)
        world.box(28, 4, 1, 29, 43, 5)
        world.box(34, 4, 1, 35, 43, 5)
        self.assert_exact(world, ((31.5, 8.5, 1, math.pi / 2),
                                  (31.5, 38.5, 1, -math.pi / 2),
                                  (35.5, 39.5, 1, 0.7)))

    def test_voxel_edits_rebuild_room_cache_without_recreating_renderer(self):
        world = roofed_world()
        player = Player(x=12.5, y=8.5)
        fast = Renderer(world)
        before = fast.scene(player, 80, 26)
        world.box(10, 11, 1, 15, 12, 6)
        blocked = fast.scene(player, 80, 26)
        self.assertNotEqual(before, blocked)
        self.assertEqual(blocked, Renderer(world, skip_empty_space=False).scene(player, 80, 26))
        world.box(10, 11, 1, 15, 12, 6, AIR)
        self.assertEqual(before, fast.scene(player, 80, 26))

    def test_cached_room_prism_contains_only_air_and_stays_below_roof(self):
        world = roofed_world()
        world.box(22, 20, 1, 26, 24, 3, FLOOR)
        world.box(16, 12, 7, 20, 18, 8, AIR)
        renderer = Renderer(world)
        renderer._update_chunks()
        chunks_x = (world.width + 1) // 2
        chunk_count = chunks_x * ((world.depth + 1) // 2)
        prism = renderer._room_bounds[2 * chunk_count + (8 >> 1) * chunks_x + (18 >> 1)]
        self.assertIsNotNone(prism)
        x0, y0, x1, y1, floor, ceiling = prism
        self.assertLessEqual(floor, 2)
        self.assertGreater(ceiling, 2)
        self.assertLessEqual(ceiling, 7)
        self.assertGreater((x1 - x0) * (y1 - y0), 4)
        for z in range(floor, ceiling):
            for y in range(y0, min(y1, world.depth)):
                for x in range(x0, min(x1, world.width)):
                    self.assertEqual(world.get(x, y, z), AIR)


if __name__ == "__main__":
    unittest.main()

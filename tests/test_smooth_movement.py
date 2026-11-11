"""Cylinder support, quarter-unit treads, jumping and contact Foley."""

import math
import unittest

from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.sound_surfaces import surface_kind
from ascii3d.surfaces import HeightField
from ascii3d.world import BRIDGE, CRATE, FLOOR, GRASS, PATH, STONE, WOOD, World, build_world


def slope_world(material=GRASS, dx=0.15, dy=0.0):
    world = World.empty(24, 10, 16)
    heights = [1.0 + dx * x + dy * y
               for y in range(world.depth + 1) for x in range(world.width + 1)]
    world.heightfield = HeightField(world.width, world.depth, heights, material=material)
    return world


def supported_player(world, x=2.5, y=4.5, yaw=0.0):
    support = world.walk_support(x, y, world.surface_height(x, y), max_rise=0.5, max_drop=0.5)
    return Player(x=x, y=y, z=support[0], yaw=yaw)


class SmoothMovementTests(unittest.TestCase):
    def test_point_height_start_settles_to_cylinder_support_without_a_jump(self):
        world = slope_world(dx=0.15, dy=0.08)
        player = Player(x=2.5, y=4.5, z=world.surface_height(2.5, 4.5))
        expected = world.walk_support(player.x, player.y, player.z)[0]
        player.update(world, set(), 1 / 120)
        self.assertAlmostEqual(player.z, expected, places=5)
        self.assertTrue(player.grounded)
        self.assertFalse(world.collides(player.x, player.y, player.z))
        self.assertEqual(player.events, [])

    def test_walking_and_sprinting_follow_slopes_in_both_directions(self):
        for keys in ({"w"}, {"w", "shift"}):
            with self.subTest(keys=keys):
                world = slope_world(dx=0.15, dy=0.08)
                player = supported_player(world)
                events = []
                for yaw in (0, math.pi):
                    player.yaw = yaw
                    for _ in range(100):
                        player.update(world, keys, 1 / 120)
                        events.extend(player.events)
                        expected = (1 + 0.15 * player.x + 0.08 * player.y
                                    + player.RADIUS * math.hypot(0.15, 0.08))
                        self.assertAlmostEqual(player.z, expected, places=5)
                        self.assertTrue(player.grounded)
                        self.assertEqual(player.vertical_speed, 0)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                self.assertTrue(any(event.name == "step_grass" for event in events))
                self.assertFalse({"land", "jump", "terrain_step"} & {e.name for e in events})
                self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_jump_leaves_slope_and_lands_without_reattaching_early(self):
        world = slope_world()
        player = supported_player(world)
        events = []
        highest = player.z
        for index in range(160):
            player.update(world, {"w"}, 1 / 120, jump=index == 0)
            events.extend(player.events)
            highest = max(highest, player.z)
            if 5 <= index <= 30:
                self.assertFalse(player.grounded)
        self.assertGreater(highest, 2.7)
        self.assertTrue(player.grounded)
        self.assertEqual([e.name for e in events].count("jump"), 1)
        self.assertEqual([e.name for e in events].count("land"), 1)
        self.assertEqual(next(e.surface for e in events if e.name == "land"), "grass")

    def test_steep_hills_reject_walking_for_each_tick_and_diagonal_direction(self):
        world = World.empty(16, 10, 32)
        heights = [1 + 2 * max(0, x - 4)
                   for y in range(world.depth + 1) for x in range(world.width + 1)]
        world.heightfield = HeightField(world.width, world.depth, heights, material=GRASS)
        for dt in (1 / 120, 1 / 30, 0.1):
            for keys in ({"w"}, {"w", "d"}):
                with self.subTest(dt=dt, keys=keys):
                    player = Player(x=3.3, y=5.5, yaw=0)
                    for _ in range(round(1 / dt)):
                        player.update(world, keys, dt)
                    self.assertLessEqual(player.x, 4 - player.RADIUS + 1e-5)
                    self.assertAlmostEqual(player.z, 1, places=5)
                    self.assertFalse(world.collides(player.x, player.y, player.z))

    def test_shallow_triangle_walks_when_steep_triangle_misses_the_footprint(self):
        world = World.empty(8, 8, 12)
        heights = [1.0] * 81
        # The lower/right triangle rises at grade 0.5. The steep upper/left
        # triangle shares its cell but is outside this circular footprint.
        heights[3 * 9 + 4] = 1.5
        heights[4 * 9 + 4] = 1.5
        heights[4 * 9 + 3] = 4.0
        world.heightfield = HeightField(8, 8, heights, material=GRASS)
        player = supported_player(world, x=3.65, y=3.1)
        start_x, start_z = player.x, player.z
        for _ in range(4):
            player.update(world, {"w"}, 1 / 120)
            self.assertTrue(player.grounded)
            self.assertFalse(world.collides(player.x, player.y, player.z))
        self.assertGreater(player.x, start_x + 0.1)
        self.assertGreater(player.z, start_z + 0.05)

    def test_authored_bridge_above_steep_ground_keeps_its_flat_support(self):
        world = World.empty(12, 8, 32)
        heights = [1 + 2 * x
                   for y in range(world.depth + 1) for x in range(world.width + 1)]
        world.heightfield = HeightField(world.width, world.depth, heights, material=GRASS)
        world.box(2, 2, 15, 7, 6, 16, BRIDGE)
        world.add_stair_flight(4, 2, 4, 2, 16, 16.5, axis="x", material=FLOOR)
        player = Player(x=5.5, y=4, z=16.5, yaw=math.pi)
        for _ in range(80):
            player.update(world, {"w"}, 1 / 120)
            self.assertTrue(player.grounded)
            self.assertEqual(player.vertical_speed, 0)
        self.assertLess(player.x, 3.5)
        self.assertEqual(player.z, 16)

    def stairs(self, material=FLOOR):
        world = World.empty(20, 10, 12)
        world.box(0, 0, 0, 20, 10, 1, GRASS)
        world.add_stair_flight(4, 2, 4, 6, 1, 3, axis="x", riser=0.25, material=material)
        return world

    def test_quarter_steps_remain_grounded_up_and_down_with_discrete_foley(self):
        for keys in ({"w"}, {"w", "shift"}):
            with self.subTest(keys=keys):
                world = self.stairs()
                player = Player(x=2.5, y=4.5, yaw=0)
                events = []
                for destination, yaw in ((9.5, 0), (3.5, math.pi)):
                    player.yaw = yaw
                    for _ in range(300):
                        player.update(world, keys, 1 / 120)
                        events.extend(player.events)
                        self.assertTrue(player.grounded)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                        self.assertEqual(player.vertical_speed, 0)
                        if (yaw == 0 and player.x >= destination
                                or yaw != 0 and player.x <= destination):
                            break
                    else:
                        self.fail("stair traversal failed to reach its destination")
                    self.assertAlmostEqual(player.z, 3 if yaw == 0 else 1, places=5)
                steps = [e for e in events if e.name == "terrain_step"]
                self.assertEqual(len(steps), 16)
                self.assertTrue(all(e.surface == "stone" for e in steps[:-1]))
                self.assertEqual(steps[-1].surface, "grass")
                self.assertNotIn("land", [e.name for e in events])

    def test_castle_west_flight_walks_both_directions_without_jumping(self):
        world = build_world()
        player = Player(x=35.5, y=31.5, yaw=math.pi / 2)
        events = []
        for destination, yaw, height in ((42.5, math.pi / 2, 6), (31.5, -math.pi / 2, 1)):
            player.yaw = yaw
            for _ in range(600):
                player.update(world, {"w"}, 1 / 120)
                events.extend(player.events)
                self.assertTrue(player.grounded)
                self.assertFalse(world.collides(player.x, player.y, player.z))
                if (yaw > 0 and player.y >= destination
                        or yaw < 0 and player.y <= destination):
                    break
            else:
                self.fail("west stair flight did not reach its landing")
            self.assertAlmostEqual(player.z, height, places=5)
        self.assertNotIn("jump", [e.name for e in events])
        self.assertNotIn("land", [e.name for e in events])
        self.assertEqual(sum(e.name == "terrain_step" for e in events), 40)

    def test_step_support_rejects_low_ceiling_and_non_walkable_materials(self):
        for obstacle in ("ceiling", "crate", "rail"):
            with self.subTest(obstacle=obstacle):
                material = CRATE if obstacle == "crate" else WOOD if obstacle == "rail" else FLOOR
                world = self.stairs(material)
                if obstacle == "ceiling":
                    world.box(3, 2, 3, 8, 7, 4, STONE)
                player = Player(x=3.5, y=4.5, yaw=0)
                for _ in range(100):
                    player.update(world, {"w"}, 1 / 120)
                # The first quarter tread fits below a Z3 ceiling; the next
                # would put the player's head through it.
                edge = 4.75 if obstacle == "ceiling" else 4
                self.assertLessEqual(player.x, edge - player.RADIUS + 1e-5)
                self.assertAlmostEqual(player.z, 1.25 if obstacle == "ceiling" else 1, places=5)

    def test_stepping_off_a_high_tread_falls_instead_of_snapping_to_ground(self):
        world = self.stairs()
        player = Player(x=9.5, y=4.5, z=3, yaw=0)
        airborne = False
        events = []
        for _ in range(150):
            player.update(world, {"w"}, 1 / 120)
            events.extend(player.events)
            airborne |= not player.grounded
        self.assertTrue(airborne)
        self.assertTrue(player.grounded)
        self.assertAlmostEqual(player.z, 1, places=5)
        self.assertEqual([e.name for e in events].count("land"), 1)

    def test_jump_can_land_on_fractional_crate_without_auto_climbing_it(self):
        world = World.empty(16, 10, 10)
        world.box(0, 0, 0, 16, 10, 1, GRASS)
        world.add_stair_flight(4, 2, 3, 1, 1, 1.25, axis="x", material=CRATE)
        player = Player(x=3.2, y=3.5, yaw=0)
        events = []
        for tick in range(160):
            player.update(world, {"w"} if tick < 50 else set(), 1 / 120, jump=tick == 0)
            events.extend(player.events)
        self.assertGreater(player.x, 4)
        self.assertLess(player.x, 5)
        self.assertTrue(player.grounded)
        self.assertAlmostEqual(player.z, 1.25, places=5)
        self.assertEqual(next(e.surface for e in events if e.name == "land"), "wood")

    def test_fractional_support_materials_feed_grass_and_gravel_footsteps(self):
        for material, cue in ((GRASS, "grass"), (PATH, "gravel")):
            with self.subTest(material=material):
                world = slope_world(material)
                player = supported_player(world)
                self.assertEqual(surface_kind(world, player.x, player.y, player.z), cue)
                events = []
                for _ in range(100):
                    player.update(world, {"w"}, 1 / 120)
                    events.extend(player.events)
                self.assertTrue(any(e.name == "step_" + cue for e in events))
                self.assertTrue(all(e.name in EFFECTS for e in events))


if __name__ == "__main__":
    unittest.main()

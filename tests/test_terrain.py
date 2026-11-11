"""Highland elevations, connected routes, occupied floors and usable stairs."""

import math
import unittest

from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.terrain import (LANDMARKS, NEW_BRIDGES, ROUTE_WAYPOINTS, _road_cells,
                             stair_routes, terrain_area_name, terrain_height)
from ascii3d.world import (AIR, BRIDGE, FLOOR, GRASS, METAL, PATH, STONE, WOOD,
                           build_world, river_center)


class TerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The generated world is immutable throughout these checks.
        cls.world = build_world()

    def test_enormous_world_contains_low_valleys_and_continuous_highlands(self):
        world = self.world
        self.assertEqual((world.width, world.depth, world.height), (512, 512, 32))
        self.assertGreater(world.width * world.depth, 20 * 112 * 112)
        samples = [terrain_height(x + 0.5, y + 0.5)
                   for y in range(120, 500, 8) for x in range(120, 500, 8)]
        self.assertLessEqual(min(samples), 2)
        self.assertGreaterEqual(max(samples), 20)
        self.assertGreaterEqual(len(set(samples)), 18)
        for x, y in ((130, 30), (200, 220), (320, 208), (310, 290), (450, 450)):
            feet = world.surface_height(x + 0.5, y + 0.5)
            foundation = math.floor(world.heightfield.cell_bounds(x, y)[0])
            self.assertIn(world.surface_material(x + 0.5, y + 0.5), (GRASS, PATH))
            self.assertEqual(world.get(x, y, foundation), AIR)
            self.assertGreaterEqual(feet, foundation)
            if foundation > 1:
                self.assertEqual(world.get(x, y, foundation - 2), STONE)

    def test_height_generation_is_repeatable_and_keeps_the_original_hub(self):
        points = [(x + 0.5, y + 0.5) for x in range(3, 510, 17) for y in range(3, 510, 19)]
        forward = {point: terrain_height(*point) for point in points}
        reverse = {point: terrain_height(*point) for point in reversed(points)}
        self.assertEqual(forward, reverse)
        for x, y in ((0.5, 0.5), (55.5, 30.5), (105.5, 108.5), (111.5, 111.5),
                     (112, 112), (112, 50), (50, 112)):
            self.assertEqual(terrain_height(x, y), 1)

    def test_continuous_routes_are_walkable_from_the_castle_to_ridge_hall(self):
        roads = _road_cells()
        self.assertGreater(len(roads), 6000)
        for x, y in roads:
            for dx, dy in ((1, 0), (0, 1)):
                if (x + dx, y + dy) in roads:
                    self.assertLessEqual(abs(terrain_height(x + 0.5, y + 0.5)
                                             - terrain_height(x + dx + 0.5, y + dy + 0.5)), 1)
        # The eastern route genuinely climbs above the flat hub without jump.
        player = Player(x=88.5, y=48.5, yaw=0)
        events = []
        for x, y in ROUTE_WAYPOINTS[0][1:]:
            for _ in range(1200):
                if math.hypot(x + 0.5 - player.x, y + 0.5 - player.y) < 0.04:
                    break
                player.yaw = math.atan2(y + 0.5 - player.y, x + 0.5 - player.x)
                player.update(self.world, {"w"}, 1 / 120)
                events.extend(player.events)
            self.assertLess(math.hypot(x + 0.5 - player.x, y + 0.5 - player.y), 0.04)
        self.assertGreater(player.x, 135)
        self.assertAlmostEqual(player.z, LANDMARKS[0].base)
        self.assertFalse(self.world.collides(player.x, player.y, player.z))
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_three_floor_halls_have_open_entrances_and_real_upper_supports(self):
        for landmark in LANDMARKS:
            x0, y0, x1, y1 = landmark.bounds
            x, y = (x0 + x1) // 2 + 0.5, (y0 + y1) // 2 + 0.5
            with self.subTest(landmark=landmark.name):
                self.assertEqual(self.world.area(x, y), landmark.name)
                self.assertEqual(terrain_area_name(x, y), landmark.name)
                self.assertLess(landmark.roof + 2, self.world.height)
                for feet in (*landmark.floors, landmark.roof):
                    self.assertIn(self.world.get(int(x), int(y), feet - 1), (FLOOR, WOOD))
                    self.assertFalse(self.world.collides(x, y, feet))
                self.assertFalse(self.world.collides(x0 + 0.5, y, landmark.base))
                self.assertFalse(self.world.collides(x, y0 + 0.5, landmark.base))
                self.assertEqual(self.world.get(x0, y0 + 4, landmark.base + 2), AIR)
                self.assertEqual(self.world.get(x0, y0 + 4, landmark.base + 7), AIR)
                self.assertEqual(self.world.get(x0, y0 + 4, landmark.base + 12), AIR)

    def test_all_twelve_stair_flights_climb_without_jumping_and_emit_registered_foley(self):
        for landmark in LANDMARKS:
            for x, start_y, end_y, feet in stair_routes(landmark):
                with self.subTest(landmark=landmark.name, feet=feet):
                    player = Player(x=x, y=start_y, z=feet)
                    events = []
                    for _ in range(720):
                        player.update(self.world, {"w"}, 1 / 120)
                        events.extend(player.events)
                        self.assertFalse(self.world.collides(player.x, player.y, player.z))
                        if player.y >= end_y:
                            break
                    self.assertGreaterEqual(player.y, end_y)
                    self.assertAlmostEqual(player.z, feet + 5, places=4)
                    self.assertFalse(self.world.collides(player.x, player.y, player.z))
                    self.assertIn("terrain_step", [event.name for event in events])
                    self.assertTrue(all(event.name in EFFECTS for event in events))
                    player.yaw = -math.pi / 2
                    down_events = []
                    for _ in range(720):
                        player.update(self.world, {"w"}, 1 / 120)
                        down_events.extend(player.events)
                        self.assertFalse(self.world.collides(player.x, player.y, player.z))
                        if player.y <= start_y:
                            break
                    self.assertLessEqual(player.y, start_y)
                    self.assertAlmostEqual(player.z, feet, places=4)
                    self.assertIn("terrain_step", [event.name for event in down_events])
                    self.assertNotIn("jump", [event.name for event in events + down_events])

    def test_roof_and_balcony_guardrails_do_not_auto_step_over_the_edge(self):
        for landmark in LANDMARKS:
            x0, y0, x1, y1 = landmark.bounds
            center_y = (y0 + y1) // 2 + 0.5
            roof = Player(x=x0 + 1.5, y=center_y, z=landmark.roof, yaw=math.pi)
            balcony = Player(x=x1 + 2.5, y=center_y, z=landmark.base + 5, yaw=0)
            for _ in range(160):
                roof.update(self.world, {"w"}, 1 / 120)
                balcony.update(self.world, {"w"}, 1 / 120)
            self.assertGreaterEqual(roof.x, x0 + 1 + roof.RADIUS - 1e-6)
            self.assertAlmostEqual(roof.z, landmark.roof)
            self.assertLessEqual(balcony.x, x1 + 4 - balcony.RADIUS + 1e-6)
            self.assertAlmostEqual(balcony.z, landmark.base + 5)
            self.assertEqual(self.world.get(x0, int(center_y), landmark.roof), METAL)

    def test_every_hall_has_a_continuous_walk_from_ground_arch_to_roof(self):
        for landmark in LANDMARKS:
            x0, y0, x1, y1 = landmark.bounds
            cx, cy = (x0 + x1) // 2 + 0.5, (y0 + y1) // 2 + 0.5
            first, second, third = stair_routes(landmark)
            player = Player(x=x0 - 1.5, y=cy, z=landmark.base, yaw=0)
            points = ((cx, cy), (cx, first[1]), (first[0], first[1]),
                      (first[0], first[2]), (cx, first[2]), (cx, second[1]),
                      (second[0], second[1]), (second[0], second[2]),
                      (cx, second[2]), (cx, third[1]), (third[0], third[1]),
                      (third[0], third[2]))
            for x, y in points:
                with self.subTest(landmark=landmark.name, waypoint=(x, y)):
                    for _ in range(1200):
                        if math.hypot(x - player.x, y - player.y) < 0.04:
                            break
                        player.yaw = math.atan2(y - player.y, x - player.x)
                        player.update(self.world, {"w"}, 1 / 120)
                    self.assertLess(math.hypot(x - player.x, y - player.y), 0.04)
            self.assertAlmostEqual(player.z, landmark.roof, places=4)

    def test_two_new_river_crossings_keep_long_routes_dry(self):
        for x0, y0, x1, y1 in NEW_BRIDGES:
            player = Player(x=(x0 + x1) / 2, y=y0 - 0.5)
            for _ in range(720):
                player.update(self.world, {"w"}, 1 / 120)
                self.assertFalse(player.in_water)
                if y0 + player.RADIUS <= player.y <= y1 - player.RADIUS:
                    self.assertAlmostEqual(player.z, 1, places=6)
                else:
                    self.assertGreaterEqual(player.z, 1)
                    self.assertLess(player.z, 1.1)
                if player.y > y1 + 0.5:
                    break
            self.assertGreater(player.y, y1 + 0.5)
            self.assertEqual(self.world.get(x0 + 1, (y0 + y1) // 2, 0), BRIDGE)
            self.assertIn("BRIDGE", self.world.area(player.x, (y0 + y1) / 2))
        self.assertEqual(self.world.area(200.5, river_center(200.5)), "FLOWING RIVER")

    def test_outer_trees_use_supported_elevations_and_avoid_roads(self):
        roads = _road_cells()
        elevated = [tree for tree in self.world.trees.values() if tree.base_z > 1]
        self.assertGreater(len(elevated), 500)
        self.assertLess(len(self.world.trees), 1800)
        for tree in elevated:
            x, y = int(tree.x), int(tree.y)
            self.assertNotIn((x, y), roads)
            self.assertEqual(self.world.surface_material(tree.x, tree.y), GRASS)
            self.assertAlmostEqual(self.world.surface_height(tree.x, tree.y), tree.base_z)
            self.assertGreater(tree.height, tree.base_z + 3)


if __name__ == "__main__":
    unittest.main()

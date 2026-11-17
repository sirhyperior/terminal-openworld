"""Highland elevations, connected routes, occupied floors and usable stairs."""

import math
import unittest

from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.terrain import (LANDMARKS, RIVER_BRIDGES, RAVINE_BRIDGE, ROUTE_WAYPOINTS, _road_cells,
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
        for x, y in ((130, 30), (200, 220), (320, 170), (310, 320), (470, 450)):
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

    def test_continuous_routes_are_walkable_from_ashgate_to_thornwatch(self):
        roads = _road_cells()
        self.assertTrue(all((round(x), round(y)) in roads for route in ROUTE_WAYPOINTS for x, y in route))
        for x, y in roads:
            for dx, dy in ((1, 0), (0, 1)):
                bx0, by0, bx1, by1, _ = RAVINE_BRIDGE
                below_deck = bx0 - 1 <= x < bx1 and by0 <= y < by1
                if (x + dx, y + dy) in roads and not below_deck:
                    self.assertLessEqual(abs(terrain_height(x + 0.5, y + 0.5)
                                             - terrain_height(x + dx + 0.5, y + dy + 0.5)), 1)
        # The eastern route genuinely climbs above the flat hub without jump.
        player = Player(x=152.5, y=93.5, yaw=0)
        for door in self.world.doors:
            door.openness, door.target_open = 1, True
        events = []
        for x, y in ROUTE_WAYPOINTS[0][1:]:
            for _ in range(4000):
                if math.hypot(x + 0.5 - player.x, y + 0.5 - player.y) < 0.04:
                    break
                player.yaw = math.atan2(y + 0.5 - player.y, x + 0.5 - player.x)
                player.update(self.world, {"w"}, 1 / 120)
                events.extend(player.events)
            self.assertLess(math.hypot(x + 0.5 - player.x, y + 0.5 - player.y), 0.04)
        self.assertGreater(player.x, 300)
        self.assertAlmostEqual(player.z, LANDMARKS[0].base)
        self.assertFalse(self.world.collides(player.x, player.y, player.z))
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_three_floor_halls_have_open_entrances_and_real_upper_supports(self):
        for landmark in LANDMARKS:
            x0, y0, x1, y1 = landmark.bounds
            cx, cy = (x0 + x1) // 2 + 0.5, (y0 + y1) // 2 + 0.5
            x, y = landmark.to_world(cx, cy)
            with self.subTest(landmark=landmark.name):
                self.assertEqual(self.world.area(x, y), landmark.name)
                self.assertEqual(terrain_area_name(x, y), landmark.name)
                self.assertLess(landmark.roof + 2, self.world.height)
                for feet in (*landmark.floors, landmark.roof):
                    self.assertAlmostEqual(self.world.solid_hit((x, y, feet + .25), (0, 0, -1), .5), .25)
                    self.assertFalse(self.world.collides(x, y, feet))
                self.assertFalse(self.world.collides(*landmark.to_world(x0 + .5, cy), landmark.base))
                self.assertFalse(self.world.collides(*landmark.to_world(cx, y0 + .5), landmark.base))
                wx, wy = landmark.to_world(x0 - .5, y0 + 4.5)
                direction = math.cos(landmark.angle), math.sin(landmark.angle), 0
                for feet in landmark.floors:
                    self.assertTrue(self.world.line_clear((wx, wy, feet + 2), direction, 2))

    def test_all_twelve_stair_flights_climb_without_jumping_and_emit_registered_foley(self):
        for landmark in LANDMARKS:
            for x, start_y, end_y, feet in stair_routes(landmark):
                with self.subTest(landmark=landmark.name, feet=feet):
                    wx, wy = landmark.to_world(x, start_y)
                    player = Player(x=wx, y=wy, z=feet, yaw=math.pi / 2 + landmark.angle)
                    events = []
                    for _ in range(720):
                        player.update(self.world, {"w"}, 1 / 120)
                        events.extend(player.events)
                        self.assertFalse(self.world.collides(player.x, player.y, player.z))
                        if landmark.to_local(player.x, player.y)[1] >= end_y:
                            break
                    self.assertGreaterEqual(landmark.to_local(player.x, player.y)[1], end_y)
                    self.assertAlmostEqual(player.z, feet + 5, places=4)
                    self.assertFalse(self.world.collides(player.x, player.y, player.z))
                    self.assertIn("terrain_step", [event.name for event in events])
                    self.assertTrue(all(event.name in EFFECTS for event in events))
                    player.yaw = -math.pi / 2 + landmark.angle
                    down_events = []
                    for _ in range(720):
                        player.update(self.world, {"w"}, 1 / 120)
                        down_events.extend(player.events)
                        self.assertFalse(self.world.collides(player.x, player.y, player.z))
                        if landmark.to_local(player.x, player.y)[1] <= start_y:
                            break
                    self.assertLessEqual(landmark.to_local(player.x, player.y)[1], start_y)
                    self.assertAlmostEqual(player.z, feet, places=4)
                    self.assertIn("terrain_step", [event.name for event in down_events])
                    self.assertNotIn("jump", [event.name for event in events + down_events])

    def test_roof_and_balcony_guardrails_do_not_auto_step_over_the_edge(self):
        for landmark in LANDMARKS:
            x0, y0, x1, y1 = landmark.bounds
            center_y = (y0 + y1) // 2 + 0.5
            rx, ry = landmark.to_world(x0 + 1.5, center_y)
            bx, by = landmark.to_world(x1 + 2.5, center_y)
            roof = Player(x=rx, y=ry, z=landmark.roof, yaw=math.pi + landmark.angle)
            balcony = Player(x=bx, y=by, z=landmark.base + 5, yaw=landmark.angle)
            for _ in range(160):
                roof.update(self.world, {"w"}, 1 / 120)
                balcony.update(self.world, {"w"}, 1 / 120)
            self.assertGreaterEqual(landmark.to_local(roof.x, roof.y)[0], x0 + 1 + roof.RADIUS - 1e-6)
            self.assertAlmostEqual(roof.z, landmark.roof)
            self.assertLessEqual(landmark.to_local(balcony.x, balcony.y)[0], x1 + 4 - balcony.RADIUS + 1e-6)
            self.assertAlmostEqual(balcony.z, landmark.base + 5)
            self.assertEqual(self.world.surface_material(*landmark.to_world(x0 + .5, center_y)), METAL)

    def test_every_hall_has_a_continuous_walk_from_ground_arch_to_roof(self):
        for landmark in LANDMARKS:
            x0, y0, x1, y1 = landmark.bounds
            cx, cy = (x0 + x1) // 2 + 0.5, (y0 + y1) // 2 + 0.5
            first, second, third = stair_routes(landmark)
            wx, wy = landmark.to_world(x0 - 1.5, cy)
            player = Player(x=wx, y=wy, z=landmark.base, yaw=landmark.angle)
            points = ((cx, cy), (cx, first[1]), (first[0], first[1]),
                      (first[0], first[2]), (cx, first[2]), (cx, second[1]),
                      (second[0], second[1]), (second[0], second[2]),
                      (cx, second[2]), (cx, third[1]), (third[0], third[1]),
                      (third[0], third[2]))
            for x, y in points:
                x, y = landmark.to_world(x, y)
                with self.subTest(landmark=landmark.name, waypoint=(x, y)):
                    for _ in range(4000):
                        if math.hypot(x - player.x, y - player.y) < 0.04:
                            break
                        player.yaw = math.atan2(y - player.y, x - player.x)
                        player.update(self.world, {"w"}, 1 / 120)
                    self.assertLess(math.hypot(x - player.x, y - player.y), 0.04)
            self.assertAlmostEqual(player.z, landmark.roof, places=4)

    def test_three_river_crossings_keep_long_routes_dry(self):
        for x0, y0, x1, y1 in RIVER_BRIDGES:
            player = Player(x=(x0 + x1) / 2, y=y0 - 0.5)
            for _ in range(math.ceil((y1 - y0 + 2) * 120 / player.WALK_SPEED)):
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

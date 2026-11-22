"""Static world construction, shared doors and connected landmark routes."""

import math
import unittest

from ascii3d.doors import Door
from ascii3d.map_expansion import (CLOSE_TREE, EXPANDED_DEPTH, EXPANDED_WIDTH,
                                   INDOOR_SPAWN, STAFF_POSITION,
                                   WORLD_HEIGHT, expand_world, expanded_area_name)
from ascii3d.player import Player
from ascii3d.terrain import (LANDMARKS, RIVER_BRIDGES, ROUTE_WAYPOINTS,
                             _road_cells, terrain_height)
from ascii3d.world import AIR, BRIDGE, GRASS, PATH, WOOD, World, build_world, river_center


class MapExpansionTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_rebuilding_scenery_is_repeatable_and_keeps_door_state(self):
        before = bytes(self.world.cells)
        trees = self.world.trees.copy()
        solids = tuple(self.world.solids)
        first = self.world.doors[0]
        first.openness = 0.6
        first.target_open = True
        expand_world(self.world)
        self.assertEqual(bytes(self.world.cells), before)
        self.assertEqual(self.world.trees, trees)
        self.assertEqual(tuple(self.world.solids), solids)
        self.assertIs(self.world.doors[0], first)
        self.assertEqual(first.openness, 0.6)
        self.assertTrue(first.target_open)
        self.assertEqual(len(self.world.doors), 6)

    def test_three_river_bridges_are_dry_and_rails_have_collision(self):
        self.assertEqual(len(RIVER_BRIDGES), 3)
        for bounds in RIVER_BRIDGES:
            with self.subTest(bridge=bounds):
                x0, y0, x1, y1 = bounds
                for x in range(x0, x1):
                    for y in range(y0, y1):
                        self.assertEqual(self.world.get(x, y, 0), BRIDGE)
                x, y = (x0 + x1) / 2, y0 - 1.5
                support = self.world.walk_support(x, y, terrain_height(x, y), walking=True)
                self.assertIsNotNone(support)
                player = Player(x=x, y=y, z=support[0])
                self.assertFalse(self.world.collides(player.x, player.y, player.z))
                for _ in range(1100):
                    player.update(self.world, {"w"}, 1 / 120)
                    self.assertFalse(player.in_water)
                    self.assertTrue(player.grounded)
                    if y0 + player.RADIUS <= player.y <= y1 - player.RADIUS:
                        self.assertAlmostEqual(player.z, 1)
                    if player.y > y1 + 1:
                        break
                self.assertGreater(player.y, y1 + 1)
                player = Player(x=(x0 + x1) / 2, y=(y0 + y1) / 2, yaw=0)
                for _ in range(180):
                    player.update(self.world, {"w"}, 1 / 120)
                self.assertLessEqual(player.x, x1 - player.RADIUS + 1e-6)
                self.assertGreater(player.x, x1 - 0.3)

    def test_six_destinations_have_dry_walkable_routes_with_real_collision_and_height(self):
        for door in self.world.doors:
            door.openness = 1
            door.target_open = True
        self.assertEqual({landmark.name for landmark in LANDMARKS},
                         {'THORNWATCH', 'BLACK ABBEY', 'ASTRAL RELIQUARY', 'MOURNING CITADEL'})
        # Walk continuously from the spawn through all six destinations and
        # back, including the interior passages that join incoming/outgoing
        # roads. Then exercise the shortcuts and local approaches as well.
        roads = ROUTE_WAYPOINTS
        thorn_center = tuple(value - 0.5 for value in LANDMARKS[0].to_world(304.5, 132.5))
        relic_center = tuple(value - 0.5 for value in LANDMARKS[2].to_world(388.5, 284.5))
        loop = ((128, 76), (128, 93), *roads[0], thorn_center, *roads[1],
                relic_center, *roads[2], (420, 436), *roads[3],
                (216, 360), *roads[4], (72, 248), *roads[5],
                (128, 111), (128, 93), (128, 76))
        highest = 1
        for route in (loop, *roads[6:]):
            with self.subTest(route=route):
                x, y = route[0][0] + 0.5, route[0][1] + 0.5
                feet = terrain_height(x, y)
                support = self.world.walk_support(x, y, feet, walking=True)
                self.assertIsNotNone(support, route[0])
                player = Player(x=x, y=y, z=support[0])
                self.assertFalse(self.world.collides(player.x, player.y, player.z), route[0])
                for wx, wy in route[1:]:
                    target_x, target_y = wx + 0.5, wy + 0.5
                    steps = math.ceil(math.hypot(target_x - player.x, target_y - player.y)
                                      * 120 / player.WALK_SPEED) + 60
                    for _ in range(steps):
                        if math.hypot(target_x - player.x, target_y - player.y) < 0.04:
                            break
                        player.yaw = math.atan2(target_y - player.y, target_x - player.x)
                        player.update(self.world, {'w'}, 1 / 120)
                        self.assertTrue(player.grounded, (route, player))
                        self.assertFalse(player.in_water, (route, player))
                        self.assertFalse(self.world.collides(player.x, player.y, player.z), (route, player))
                        self.assertFalse({'jump', 'land'} & {event.name for event in player.events})
                        highest = max(highest, player.z)
                    self.assertLess(math.hypot(target_x - player.x, target_y - player.y), 0.04,
                                    (route, (target_x, target_y), player))
        self.assertGreater(highest, 12)
        self.assertEqual(self.world.get(68, 248, 0), WOOD)
        self.assertEqual(self.world.get(128, 111, 0), WOOD)
        self.assertEqual(self.world.surface_material(128.5, 66.5), PATH)

    def test_riven_vale_shortcut_walks_and_sprints_in_both_directions(self):
        for y in (305.2, 306.5, 307.8):
            for start, end, yaw in ((326.5, 350.5, 0), (350.5, 326.5, math.pi)):
                for keys in ({"w"}, {"w", "shift"}):
                    with self.subTest(y=y, start=start, keys=keys):
                        feet = self.world.surface_height(start, y)
                        support = self.world.walk_support(start, y, feet, walking=True)
                        self.assertIsNotNone(support)
                        player = Player(x=start, y=y, z=support[0], yaw=yaw)
                        speed = player.RUN_SPEED if "shift" in keys else player.WALK_SPEED
                        for _ in range(math.ceil(abs(end - start) * 120 / speed) + 10):
                            player.update(self.world, keys, 1 / 120)
                            self.assertTrue(player.grounded)
                            self.assertFalse(player.in_water)
                            self.assertFalse(self.world.collides(player.x, player.y, player.z))
                            if (player.x - end) * (end - start) >= 0:
                                break
                        else:
                            self.fail(f"Shortcut stalled at {(player.x, player.y, player.z)}")

    def test_every_gate_uses_standard_targeting_and_sound(self):
        approaches = (("Ashgate south gate", 128.5, 70.5, math.pi / 2),
                      ("Ashgate north gate", 128.5, 121.5, -math.pi / 2),
                      ("Ashgate west gate", 101.5, 93.5, 0),
                      ("Ashgate east gate", 154.5, 93.5, math.pi),
                      ("Ashgate hall doors", 128.5, 105.5, math.pi / 2),
                      ("Gravewood chapel doors", 71.5, 240.5, math.pi / 2))
        for name, x, y, yaw in approaches:
            with self.subTest(door=name):
                player = Player(x=x, y=y, yaw=yaw)
                target = self.world.interaction_target(player)
                self.assertIsInstance(target, Door)
                self.assertEqual(target.name, name)
                self.assertEqual(self.world.interact(player)[0].name, "door_open")
                for _ in range(120):
                    self.world.update_doors(player, 1 / 120)
                self.assertEqual(target.openness, 1)

    def test_trees_remain_sparse_and_off_paths_water_and_castle(self):
        roads = _road_cells()
        gravewood_trees = [tree for tree in self.world.trees.values()
                          if 26 <= tree.x < 111 and 219 <= tree.y < 282]
        self.assertGreater(len(gravewood_trees), 30)
        self.assertGreater(len(self.world.trees), 500)
        self.assertLess(len(self.world.trees), 1800)
        self.assertIn((int(CLOSE_TREE[0]), int(CLOSE_TREE[1])), self.world.trees)
        for tree in self.world.trees.values():
            x, y = int(tree.x), int(tree.y)
            self.assertEqual(self.world.surface_material(tree.x, tree.y), GRASS)
            self.assertAlmostEqual(self.world.surface_height(tree.x, tree.y), tree.base_z)
            self.assertEqual(self.world.get(x, y, math.ceil(tree.base_z)), AIR)
            self.assertNotIn((x, y), roads)
            self.assertFalse(101 <= x < 155 and 70 <= y < 122)

    def test_area_names_cover_castle_landmarks_and_material_aware_river(self):
        for point, name in (((128.5, 76.5), "ASHGATE GATEHOUSE"),
                            ((128.5, 111.5), "ASHGATE GREAT HALL"),
                            ((115.5, 94.5), "ASHGATE TRAINING YARD"),
                            ((108.5, 95.5), "ASHGATE CLOISTER"),
                            ((143.5, 96.5), "ASHGATE GARDEN"),
                            (STAFF_POSITION, "GRAVEWOOD CHAPEL"),
                            ((41.5, 250.5), "THE WATCHSTONES"),
                            ((55.5, 265.5), "GRAVEWOOD")):
            self.assertEqual(self.world.area(*point), name)
        for landmark in LANDMARKS:
            x0, y0, x1, y1 = landmark.bounds
            self.assertEqual(self.world.area((x0 + x1) / 2, (y0 + y1) / 2), landmark.name)
        for x0, y0, x1, y1 in RIVER_BRIDGES:
            self.assertIn("BRIDGE", self.world.area((x0 + x1) / 2, (y0 + y1) / 2))
        self.assertIsNone(expanded_area_name(8.5, river_center(8.5)))
        self.assertEqual(self.world.area(8.5, river_center(8.5)), "FLOWING RIVER")
        self.assertEqual(self.world.area(5.5, 40), "ASHGATE MARCHES")

    def test_builder_dimensions_and_independent_generic_fixture_worlds(self):
        self.assertEqual((self.world.width, self.world.depth, self.world.height),
                         (EXPANDED_WIDTH, EXPANDED_DEPTH, WORLD_HEIGHT))
        empty = World.empty(10, 10, 10)
        self.assertFalse(empty.combat.pickups)
        self.assertFalse(empty.doors)
        with self.assertRaises(ValueError):
            expand_world(empty)


if __name__ == "__main__":
    unittest.main()

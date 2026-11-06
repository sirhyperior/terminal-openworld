"""Static world construction, shared doors and connected landmark routes."""

from collections import deque
import math
import unittest

from ascii3d.doors import Door
from ascii3d.map_expansion import (CLOSE_TREE, EAST_BRIDGE_BOUNDS, EXPANDED_DEPTH,
                                   EXPANDED_WIDTH, FIRST_BRIDGE_BOUNDS,
                                   INDOOR_SPAWN, OUTDOOR_SPAWN, STAFF_POSITION,
                                   WORLD_HEIGHT, expand_world, expanded_area_name)
from ascii3d.player import Player
from ascii3d.world import AIR, BRIDGE, GRASS, PATH, WATER, WOOD, World, build_world, river_center


class MapExpansionTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_rebuilding_scenery_is_repeatable_and_keeps_door_state(self):
        before = bytes(self.world.cells)
        trees = self.world.trees.copy()
        first = self.world.doors[0]
        first.openness = 0.6
        first.target_open = True
        expand_world(self.world)
        self.assertEqual(bytes(self.world.cells), before)
        self.assertEqual(self.world.trees, trees)
        self.assertIs(self.world.doors[0], first)
        self.assertEqual(first.openness, 0.6)
        self.assertTrue(first.target_open)
        self.assertEqual(len(self.world.doors), 7)

    def test_both_bridges_are_dry_and_rails_have_collision(self):
        for bounds in (FIRST_BRIDGE_BOUNDS, EAST_BRIDGE_BOUNDS):
            with self.subTest(bridge=bounds):
                x0, y0, x1, y1 = bounds
                for x in range(x0, x1):
                    for y in range(y0, y1):
                        self.assertEqual(self.world.get(x, y, 0), BRIDGE)
                player = Player(x=(x0 + x1) / 2, y=y0 - 1.5)
                for _ in range(680):
                    player.update(self.world, {"w"}, 1 / 120)
                    self.assertAlmostEqual(player.z, 1)
                    self.assertFalse(player.in_water)
                self.assertGreater(player.y, y1 + 1)
                player = Player(x=(x0 + x1) / 2, y=(y0 + y1) / 2, yaw=0)
                for _ in range(180):
                    player.update(self.world, {"w"}, 1 / 120)
                self.assertLessEqual(player.x, x1 - player.RADIUS + 1e-6)
                self.assertGreater(player.x, x1 - 0.3)

    def test_all_landmarks_have_dry_ground_level_routes_from_castle_start(self):
        for door in self.world.doors:
            door.openness = 1
            door.target_open = True
        start = (int(INDOOR_SPAWN[0]), int(INDOOR_SPAWN[1]))
        reachable, frontier = {start}, deque([start])
        while frontier:
            x, y = frontier.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (nx, ny) in reachable:
                    continue
                if not (0 <= nx < self.world.width and 0 <= ny < self.world.depth):
                    continue
                if self.world.get(nx, ny, 0) in (AIR, WATER):
                    continue
                if self.world.collides(nx + 0.5, ny + 0.5, 1):
                    continue
                reachable.add((nx, ny))
                frontier.append((nx, ny))
        for destination in ((55, 20), (42, 46), (55, 65), (53, 103),
                            (98, 47), (24, 86), (86, 86), (18, 101),
                            (12, 50), (99, 68), (55, 10), (71, 103)):
            self.assertIn(destination, reachable)
        self.assertEqual(self.world.get(53, 103, 0), WOOD)
        self.assertEqual(self.world.get(55, 65, 0), WOOD)
        self.assertEqual(self.world.get(98, 47, 0), WOOD)
        self.assertEqual(self.world.get(55, 20, 0), PATH)

    def test_every_gate_uses_standard_targeting_and_sound(self):
        approaches = (("south castle gate", 55.5, 24.5, math.pi / 2),
                      ("north castle gate", 55.5, 75.5, -math.pi / 2),
                      ("west castle gate", 28.5, 47.5, 0),
                      ("east castle gate", 81.5, 47.5, math.pi),
                      ("great hall doors", 55.5, 59.5, math.pi / 2),
                      ("ruin doors", 56.5, 95.5, math.pi / 2),
                      ("lodge doors", 90.5, 47.5, 0))
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
        self.assertEqual(len(self.world.trees), 18)
        self.assertIn((int(CLOSE_TREE[0]), int(CLOSE_TREE[1])), self.world.trees)
        for tree in self.world.trees.values():
            x, y = int(tree.x), int(tree.y)
            self.assertEqual(self.world.get(x, y, 0), GRASS)
            self.assertEqual(self.world.get(x, y, 1), AIR)
            self.assertFalse(28 <= x < 82 and 24 <= y < 76)

    def test_area_names_cover_castle_landmarks_and_material_aware_river(self):
        for point, name in (((55.5, 30.5), "SOUTH GATEHOUSE"),
                            ((55.5, 65.5), "GREAT HALL"),
                            ((42.5, 48.5), "TRAINING YARD"),
                            ((35.5, 49.5), "WEST CLOISTER"),
                            ((70.5, 50.5), "CASTLE GARDEN"),
                            (STAFF_POSITION, "NORTHERN RUINS"),
                            ((98.5, 47.5), "EASTERN LODGE"),
                            ((18.5, 102.5), "THE WATCHSTONES"),
                            ((24.5, 86.5), "WEST BRIDGE"),
                            ((86.5, 86.5), "EAST BRIDGE")):
            self.assertEqual(self.world.area(*point), name)
        self.assertIsNone(expanded_area_name(8.5, river_center(8.5)))
        self.assertEqual(self.world.area(8.5, river_center(8.5)), "FLOWING RIVER")
        self.assertEqual(self.world.area(5.5, 40), "CASTLE MEADOW")
        self.assertEqual(self.world.area(71.5, 103), "NORTH MEADOW")

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

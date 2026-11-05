from collections import deque
import math
import unittest

from ascii3d.doors import Door
from ascii3d.map_expansion import (EAST_BRIDGE_BOUNDS, EXPANDED_DEPTH,
                                   EXPANDED_WIDTH, expand_world,
                                   expanded_area_name)
from ascii3d.player import Player
from ascii3d.world import (AIR, BRIDGE, FLOOR, GRASS, PATH, WATER, WOOD,
                           Tree, World, build_world, river_center)


def expansion_fixture():
    world = World.empty(EXPANDED_WIDTH, EXPANDED_DEPTH, 10)
    world.outdoor_bounds = (1, 1, world.width - 1, world.depth - 1)
    world.box(0, 0, 0, world.width, world.depth, 1, GRASS)
    for x in range(world.width):
        center = river_center(x + 0.5)
        world.box(x, math.floor(center - 2.5), 0,
                  x + 1, math.ceil(center + 2.5), 1, WATER)
    world.box(14, 39, 0, 19, 54, 1, BRIDGE)
    # Original-region sentinels must survive the additive operation unchanged.
    world.box(2, 2, 1, 7, 3, 6)
    world.trees[5, 34] = Tree(5.5, 34.5, seed=1)
    world.doors.append(Door("original door", 3.05, 2.5, 2.9))
    return world


class MapExpansionTests(unittest.TestCase):
    def setUp(self):
        self.world = expansion_fixture()

    def test_expansion_preserves_original_cells_trees_and_doors(self):
        before = bytes(self.world.get(x, y, z)
                       for z in range(10) for y in range(62) for x in range(41))
        original_tree = self.world.trees[5, 34]
        original_door = self.world.doors[0]
        revision = self.world.revision
        expand_world(self.world)
        after = bytes(self.world.get(x, y, z)
                      for z in range(10) for y in range(62) for x in range(41))
        self.assertEqual(before, after)
        self.assertIs(self.world.trees[5, 34], original_tree)
        self.assertIs(self.world.doors[0], original_door)
        self.assertGreater(self.world.revision, revision)
        for x, y in ((14, 6), (15, 35), (20, 36)):
            self.assertEqual(self.world.get(x, y, 0), GRASS)
            self.assertEqual(self.world.get(x, y, 1), AIR)

    def test_new_bridge_is_dry_and_rails_have_collision(self):
        expand_world(self.world)
        x0, y0, x1, y1 = EAST_BRIDGE_BOUNDS
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.assertEqual(self.world.get(x, y, 0), BRIDGE)
        player = Player(x=51.5, y=36.5)
        for _ in range(780):
            player.update(self.world, {"w"}, 1 / 120)
            self.assertAlmostEqual(player.z, 1)
            self.assertFalse(player.in_water)
        self.assertGreater(player.y, 58)
        player = Player(x=51.5, y=46.5, yaw=0)
        for _ in range(240):
            player.update(self.world, {"w"}, 1 / 120)
        self.assertGreater(player.x, x1 - 0.3)
        self.assertLessEqual(player.x, x1 - player.RADIUS + 1e-6)

    def test_landmarks_have_connected_ground_level_routes(self):
        expand_world(self.world)
        self.assert_landmark_routes((16, 58))

    def assert_landmark_routes(self, start):
        for door in self.world.doors:
            door.openness = 1
            door.target_open = True
        reachable = {start}
        frontier = deque([start])
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
        for destination in ((37, 74), (32, 78), (52, 20), (51, 47),
                            (15, 78), (61, 70)):
            self.assertIn(destination, reachable)
        self.assertEqual(self.world.get(32, 78, 0), WOOD)
        self.assertEqual(self.world.get(37, 74, 0), FLOOR)
        self.assertEqual(self.world.get(52, 20, 0), WOOD)
        self.assertEqual(self.world.get(51, 60, 0), PATH)

    def test_standard_doors_use_shared_targeting_and_sound_events(self):
        expand_world(self.world)
        for name, x, y in (("lodge doors", 52.5, 12.5),
                           ("ruin doors", 37.5, 67.5)):
            player = Player(x=x, y=y)
            target = self.world.interaction_target(player)
            self.assertIsInstance(target, Door)
            self.assertEqual(target.name, name)
            self.assertEqual(self.world.interact(player).name, "door_open")
            for _ in range(120):
                self.world.update_doors(player, 1 / 120)
            self.assertEqual(target.openness, 1)
            self.assertFalse(self.world.collides(x, y + 2, 1))

    def test_static_extension_is_repeatable_and_trees_stay_sparse(self):
        expand_world(self.world)
        before = bytes(self.world.cells)
        trees = self.world.trees.copy()
        names = [door.name for door in self.world.doors]
        expand_world(self.world)
        self.assertEqual(bytes(self.world.cells), before)
        self.assertEqual(self.world.trees, trees)
        self.assertEqual([door.name for door in self.world.doors], names)
        new_trees = [tree for tree in trees.values() if tree.seed >= 100]
        self.assertGreaterEqual(len(new_trees), 10)
        self.assertLessEqual(len(new_trees), 16)
        for tree in new_trees:
            x, y = int(tree.x), int(tree.y)
            self.assertTrue(x >= 41 or y >= 62)
            self.assertEqual(self.world.get(x, y, 0), GRASS)
            self.assertEqual(self.world.get(x, y, 1), AIR)

    def test_area_names_defer_original_map_and_ordinary_river(self):
        self.assertIsNone(expanded_area_name(16.5, 46))
        self.assertIsNone(expanded_area_name(16.5, 61))
        self.assertIsNone(expanded_area_name(43.5, 46))
        self.assertEqual(expanded_area_name(37.5, 74), "NORTHERN RUINS")
        self.assertEqual(expanded_area_name(52.5, 20), "EASTERN LODGE")
        self.assertEqual(expanded_area_name(51.5, 46), "EAST BRIDGE")
        self.assertEqual(expanded_area_name(15.5, 78), "THE WATCHSTONES")
        self.assertEqual(expanded_area_name(25.5, 64), "NORTH TRAIL")
        self.assertEqual(expanded_area_name(5.5, 83), "NORTH COMMON")

    def test_live_builder_integrates_expansion_and_connects_original_spawn(self):
        self.world = build_world()
        self.assertEqual((self.world.width, self.world.depth, self.world.height), (65, 86, 10))
        self.assertEqual(len(self.world.doors), 5)
        self.assertEqual(self.world.area(37.5, 74), "NORTHERN RUINS")
        self.assertEqual(self.world.area(52.5, 20), "EASTERN LODGE")
        self.assertEqual(self.world.area(51.5, 46), "EAST BRIDGE")
        self.assertEqual(self.world.area(14.5, 4.5), "SOUTH COURT")
        # Exercise the route search against actual architecture and combat
        # collision, not only the isolated extension fixture.
        self.assert_landmark_routes((14, 4))


if __name__ == "__main__":
    unittest.main()

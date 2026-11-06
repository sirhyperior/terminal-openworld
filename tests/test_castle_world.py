"""Castle silhouette, surrounding meadow, weapons and reusable training targets."""

import math
import unittest

from ascii3d.combat import FIRE_STAFF, SWORD
from ascii3d.map_expansion import (CASTLE_BOUNDS, DUMMY_POSITIONS, INDOOR_SPAWN,
                                   OUTDOOR_SPAWN, STAFF_POSITION, SWORD_POSITIONS)
from ascii3d.player import Player
from ascii3d.world import AIR, GRASS, WATER, build_world, river_center


class CastleWorldTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_castle_is_larger_than_previous_fort_and_has_meadow_on_every_side(self):
        x0, y0, x1, y1 = CASTLE_BOUNDS
        self.assertGreater(x1 - x0, 33)
        self.assertGreater(y1 - y0, 29)
        self.assertGreater(x0, 15)
        self.assertGreater(y0, 15)
        self.assertGreater(self.world.width - x1, 15)
        self.assertGreater(self.world.depth - y1, 15)
        for x, y in ((20, 50), (90, 60), (45, 16), (55, 80)):
            self.assertEqual(self.world.get(x, y, 0), GRASS)
            self.assertEqual(self.world.get(x, y, 1), AIR)

    def test_towers_crenellations_cloister_and_gatehouse_have_real_geometry(self):
        for x, y in ((28, 24), (75, 24), (28, 69), (75, 69)):
            self.assertNotEqual(self.world.get(x, y, 8), AIR)
            self.assertEqual(self.world.get(x + 2, y + 2, 2), AIR)
            self.assertNotEqual(self.world.get(x + 2, y + 2, 7), AIR)
        self.assertNotEqual(self.world.get(55, 30, 5), AIR)
        self.assertNotEqual(self.world.get(36, 50, 5), AIR)
        self.assertEqual(self.world.get(36, 50, 2), AIR)
        for step in range(5):
            self.assertNotEqual(self.world.get(35, 34 + step, 1 + step), AIR)
            self.assertEqual(self.world.get(35, 34 + step, 2 + step), AIR)

    def test_sword_aliases_are_collectable_from_both_spawns_and_staff_from_ruins(self):
        swords = [item for item in self.world.combat.pickups if item.weapon == SWORD]
        self.assertEqual([(item.x, item.y) for item in swords], list(SWORD_POSITIONS))
        for spawn in (INDOOR_SPAWN, OUTDOOR_SPAWN):
            world = build_world()
            player = Player(x=spawn[0], y=spawn[1], z=spawn[2], yaw=math.pi / 2,
                            pitch=-0.06 if spawn == OUTDOOR_SPAWN else 0)
            self.assertFalse(world.collides(player.x, player.y, player.z))
            target = world.interaction_target(player)
            self.assertIsNotNone(target)
            self.assertEqual(target.weapon, SWORD)
            self.assertEqual(world.interact(player)[-1].name, "sword_pickup")
            self.assertTrue(all(item.collected for item in world.combat.pickups if item.weapon == SWORD))
            self.assertFalse(next(item for item in world.combat.pickups if item.weapon == FIRE_STAFF).collected)
        staff = next(item for item in self.world.combat.pickups if item.weapon == FIRE_STAFF)
        self.assertEqual((staff.x, staff.y), STAFF_POSITION)
        player = Player(x=staff.x, y=staff.y - 2, yaw=math.pi / 2)
        self.assertFalse(self.world.collides(player.x, player.y, player.z))
        self.assertIs(self.world.interaction_target(player), staff)
        self.assertEqual(self.world.interact(player)[-1].name, "staff_pickup")

    def test_multiple_dummies_have_clear_approaches_and_independent_hit_state(self):
        targets = [enemy for enemy in self.world.combat.enemies if enemy.behavior is None]
        self.assertEqual([(enemy.x, enemy.y) for enemy in targets], list(DUMMY_POSITIONS))
        for target in targets:
            player = Player(x=target.x, y=target.y - 2.3, yaw=math.pi / 2)
            self.assertFalse(self.world.collides(player.x, player.y, player.z))
            self.assertIs(self.world.combat.aimed_enemy(self.world, player, 2.55), target)
            self.assertTrue(self.world.collides(target.x, target.y, target.z))
        targets[0].hp = 0
        targets[0].down_remaining = 4
        self.assertTrue(all(enemy.hp == 3 for enemy in targets[1:]))

    def test_jumping_up_west_steps_reaches_cloister_roof_without_new_physics(self):
        player = Player(x=35.5, y=33, yaw=math.pi / 2)
        for _ in range(600):
            player.update(self.world, {"w"}, 1 / 120, jump=player.grounded)
            if player.y > 42 and player.z >= 6:
                break
        self.assertGreater(player.y, 42)
        self.assertGreaterEqual(player.z, 6)
        self.assertFalse(self.world.collides(player.x, player.y, player.z))

    def test_river_stays_outside_castle_and_current_follows_its_centerline(self):
        x0, y0, x1, y1 = CASTLE_BOUNDS
        self.assertTrue(all(self.world.get(x, y, 0) != WATER
                            for x in range(x0, x1) for y in range(y0, y1)))
        for x in (4.5, 40.5, 72.5, 103.5):
            center = river_center(x)
            self.assertGreater(center - 3, y1)
            self.assertEqual(self.world.get(int(x), int(center), 0), WATER)
            dx, dy = self.world.current(x)
            derivative = (river_center(x + 0.001) - river_center(x - 0.001)) / 0.002
            self.assertAlmostEqual(dy / dx, derivative, places=6)


if __name__ == "__main__":
    unittest.main()

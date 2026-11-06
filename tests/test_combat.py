"""Playable inventory, shared targeting, attack state and feedback contracts."""

import math
import unittest

from ascii3d.combat import (ATTACK_COOLDOWN, ATTACK_REACH, CombatState, Enemy,
                            WeaponPickup)
from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.world import FLOOR, WATER, Tree, World, build_world


def training_world():
    world = World.empty(20, 20, 10)
    world.box(0, 0, 0, 20, 20, 1, FLOOR)
    world.combat = CombatState(pickups=[WeaponPickup(8.5, 6.5, group="starter"),
                                      WeaponPickup(2.5, 2.5, group="starter")],
                               enemies=[Enemy("Training dummy", 8.5, 8.5)])
    return world


class CombatTests(unittest.TestCase):
    def setUp(self):
        self.world = training_world()
        self.player = Player(x=8.5, y=4.5)
        self.combat = self.world.combat
        self.enemy = self.combat.enemies[0]

    def test_fixture_worlds_have_independent_empty_combat(self):
        first, second = World.empty(2, 2, 2), World.empty(2, 2, 2)
        first.combat.pickups.append(WeaponPickup(1, 1))
        self.assertFalse(second.combat.pickups)
        self.assertFalse(second.combat.enemies)

    def test_e_collects_one_shared_sword_and_emits_feedback(self):
        self.assertIs(self.world.interaction_target(self.player), self.combat.pickups[0])
        self.assertEqual(self.world.interact(self.player)[0].name, "sword_pickup")
        self.assertIsNotNone(self.combat.held_item)
        self.assertTrue(all(item.collected for item in self.combat.pickups))
        self.assertEqual(self.world.interact(self.player)[0].name, "interaction_miss")

    def test_collection_requires_reach_aim_and_voxel_line_of_sight(self):
        for y, yaw, pitch in ((2.0, math.pi / 2, 0), (4.5, 0, 0),
                               (4.5, math.pi / 2, 0.65)):
            with self.subTest(y=y, yaw=yaw, pitch=pitch):
                self.player.y, self.player.yaw, self.player.pitch = y, yaw, pitch
                self.assertEqual(self.world.interact(self.player)[0].name, "interaction_miss")
        self.player.y, self.player.yaw, self.player.pitch = 4.5, math.pi / 2, 0
        self.world.box(8, 5, 1, 9, 6, 4)
        self.assertEqual(self.world.interact(self.player)[0].name, "interaction_miss")
        self.assertIsNone(self.combat.held_item)

    def test_nearest_door_wins_and_its_leaf_blocks_pickup_and_attack(self):
        door = Door("test door", 7.5, 5.5, 2)
        self.world.doors.append(door)
        self.assertIs(self.world.interaction_target(self.player), door)
        self.assertIsNone(self.combat.aimed_enemy(self.world, self.player))
        self.world.interact(self.player)
        for _ in range(120):
            self.world.update_doors(self.player, 1 / 120)
        # The open portal remains targetable for closing. Cross it to collect.
        self.assertIs(self.world.interaction_target(self.player), door)
        self.player.y = 6.0
        self.assertIs(self.world.interaction_target(self.player), self.combat.pickups[0])
        self.assertIs(self.combat.aimed_enemy(self.world, self.player), self.enemy)

    def test_pickup_in_front_of_door_wins(self):
        self.world.doors.append(Door("behind", 7.5, 7, 2))
        self.assertIs(self.world.interaction_target(self.player), self.combat.pickups[0])

    def test_tree_trunk_blocks_both_interaction_and_enemy_targeting(self):
        self.world.trees[8, 5] = Tree(8.5, 5.5)
        self.assertIsNone(self.world.interaction_target(self.player))
        self.assertIsNone(self.combat.aimed_enemy(self.world, self.player))
        self.world.trees.clear()
        self.assertIs(self.combat.aimed_enemy(self.world, self.player), self.enemy)

    def test_voxel_occlusion_detects_short_corner_crossing_and_water_is_clear(self):
        self.world.box(9, 5, 1, 10, 6, 4)
        # The ray only clips the solid cell for 0.014 units: sampling at 0.08
        # would miss it. Both shared interaction paths use exact traversal.
        root = math.sqrt(0.5)
        self.assertFalse(self.world.line_clear((8.99, 5.02, 2), (root, -root, 0), 1))
        self.world.box(9, 5, 1, 10, 6, 4, WATER)
        self.assertTrue(self.world.line_clear((8.99, 5.02, 2), (root, -root, 0), 1))

    def test_q_does_not_turn_and_empty_attacks_have_a_cooldown(self):
        yaw = self.player.yaw
        self.player.update(self.world, {"q"}, 1 / 60)
        self.assertEqual(self.player.yaw, yaw)
        self.assertEqual([e.name for e in self.combat.attack(self.world, self.player)], ["attack_empty"])
        self.assertEqual(self.combat.attack(self.world, self.player), [])
        self.combat.update(0.30, self.world)
        self.assertEqual(self.combat.attack(self.world, self.player)[0].name, "attack_empty")

    def test_attacks_require_range_and_aim_and_emit_miss_feedback(self):
        self.combat.held_item = WeaponPickup(0, 0)
        self.assertEqual([e.name for e in self.combat.attack(self.world, self.player)],
                         ["sword_swing", "sword_miss"])
        self.assertEqual(self.enemy.hp, 3)
        self.player.y = self.enemy.y - self.enemy.radius - ATTACK_REACH - 0.01
        self.combat.update(ATTACK_COOLDOWN, self.world)
        self.assertEqual(self.combat.attack(self.world, self.player)[-1].name, "sword_miss")
        self.player.y += 0.02
        self.combat.update(ATTACK_COOLDOWN, self.world)
        self.assertEqual(self.combat.attack(self.world, self.player)[-1].name, "sword_hit")
        self.combat.update(ATTACK_COOLDOWN, self.world)
        self.player.pitch = 0.65
        self.assertEqual(self.combat.attack(self.world, self.player)[-1].name, "sword_miss")

    def test_attack_cooldown_down_and_reset_emit_once_with_matching_sounds(self):
        self.combat.held_item = WeaponPickup(0, 0)
        self.player.y = 6.5
        events = []
        for hp in (2, 1, 0):
            events.extend(self.combat.attack(self.world, self.player))
            self.assertEqual(self.enemy.hp, hp)
            self.assertEqual(self.combat.attack(self.world, self.player), [])
            if hp:
                self.combat.update(ATTACK_COOLDOWN, self.world)
        self.assertEqual(sum(e.name == "dummy_down" for e in events), 1)
        self.assertIsNone(self.combat.aimed_enemy(self.world, self.player))
        self.assertEqual(self.combat.update(3.99, self.world), [])
        events.extend(self.combat.update(0.01, self.world))
        self.assertEqual(events[-1].name, "dummy_reset")
        self.assertEqual(self.enemy.hp, self.enemy.max_hp)
        self.assertEqual(self.combat.update(10, self.world), [])
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_enemy_hit_has_local_impact_and_a_quieter_whoosh_than_a_miss(self):
        self.combat.held_item = WeaponPickup(0, 0)
        self.player.y = 6.5
        hit = self.combat.attack(self.world, self.player)
        self.assertEqual([event.name for event in hit], ["sword_swing", "sword_hit"])
        self.assertEqual((hit[1].x, hit[1].y), (self.enemy.x, self.enemy.y))
        self.assertEqual(self.enemy.hp, 2)
        self.combat.update(ATTACK_COOLDOWN, self.world)
        self.player.yaw = 0
        miss = self.combat.attack(self.world, self.player)
        self.assertEqual([event.name for event in miss], ["sword_swing", "sword_miss"])
        self.assertLess(hit[0].strength, miss[0].strength)
        self.assertEqual(miss[0].strength, 1)

    def test_pause_sized_zero_updates_do_not_advance_state(self):
        self.combat.held_item = WeaponPickup(0, 0)
        self.player.y = 6.5
        self.combat.attack(self.world, self.player)
        self.enemy.hp, self.enemy.down_remaining = 0, 4
        before = (self.combat.cooldown, self.combat.swing_remaining,
                  self.enemy.down_remaining, self.enemy.hit_remaining)
        for _ in range(100):
            self.assertEqual(self.combat.update(0, self.world), [])
        self.assertEqual(before, (self.combat.cooldown, self.combat.swing_remaining,
                                  self.enemy.down_remaining, self.enemy.hit_remaining))

    def test_dummy_collision_remains_solid_while_down_and_prevents_sprint_tunnelling(self):
        for hp in (3, 0):
            self.enemy.hp = hp
            self.player = Player(x=8.5, y=6.5)
            for _ in range(20):
                self.player.update(self.world, {"w", "shift"}, 0.1)
            self.assertLessEqual(self.player.y, self.enemy.y - self.enemy.radius - Player.RADIUS + 1e-6)
            self.assertFalse(self.world.collides(self.player.x, self.player.y, self.player.z))
        self.assertFalse(self.world.collides(self.enemy.x, self.enemy.y, self.enemy.z + self.enemy.height))

    def test_nearest_enemy_is_hit_and_names_use_longer_reach(self):
        farther = Enemy("Far target", 8.5, 11)
        self.combat.enemies.insert(0, farther)
        self.assertIs(self.combat.aimed_enemy(self.world, self.player), self.enemy)
        self.combat.held_item = WeaponPickup(0, 0)
        self.player.y = 6.5
        self.combat.attack(self.world, self.player)
        self.assertEqual((self.enemy.hp, farther.hp), (2, 3))
        self.world.box(8, 7, 1, 9, 8, 4)
        self.combat.update(ATTACK_COOLDOWN, self.world)
        self.assertEqual(self.combat.attack(self.world, self.player)[-1].name, "sword_miss")

    def test_live_map_has_both_start_pickups_and_training_dummy(self):
        world = build_world()
        self.assertEqual(len(world.combat.pickups), 3)
        self.assertEqual(sum(enemy.behavior is None for enemy in world.combat.enemies), 3)
        self.assertEqual(sum(enemy.behavior is not None for enemy in world.combat.enemies), 1)
        self.assertIsNotNone(world.interaction_target(Player()))
        self.assertFalse(world.collides(55.5, 20.5, 1))
        self.assertTrue(world.collides(42.5, 48.5, 1))


if __name__ == "__main__":
    unittest.main()

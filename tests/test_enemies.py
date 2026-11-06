"""Territorial enemy movement, telegraphed combat and safe fixed-area respawns."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import (FIRE_STAFF, CombatState, Enemy, EnemyBehavior,
                            WeaponPickup)
from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.world import AIR, FLOOR, WATER, Tree, World, build_world


def enemy_world():
    world = World.empty(22, 22, 8)
    world.box(0, 0, 0, 22, 22, 1, FLOOR)
    enemy = Enemy("Test warden", 10.5, 12.5, max_hp=4, hp=4,
                  behavior=EnemyBehavior(), territory=(2, 2, 20, 20),
                  respawn_delay=12)
    world.combat = CombatState(enemies=[enemy])
    return world, enemy, Player(x=10.5, y=7.5)


class EnemyTests(unittest.TestCase):
    def setUp(self):
        self.world, self.enemy, self.player = enemy_world()
        self.combat = self.world.combat

    def advance(self, seconds, player=True):
        count = max(1, math.ceil(seconds * 120))
        events = []
        for _ in range(count):
            events.extend(self.combat.update(seconds / count, self.world,
                                             self.player if player else None))
        return events

    def test_live_warden_is_separate_from_three_passive_dummies(self):
        world = build_world()
        active = [enemy for enemy in world.combat.enemies if enemy.behavior is not None]
        passive = [enemy for enemy in world.combat.enemies if enemy.behavior is None]
        self.assertEqual(len(active), 1)
        self.assertEqual(len(passive), 3)
        warden = active[0]
        self.assertEqual(warden.name, "Watchstone Warden")
        self.assertEqual(world.area(warden.x, warden.y), "THE WATCHSTONES")
        self.assertTrue(warden.can_respawn(world, None))
        self.assertEqual((warden.max_hp, warden.respawn_delay), (4, 12))

    def test_acquisition_needs_range_territory_and_clear_sight(self):
        for kind in ("outside", "far", "wall", "door", "tree"):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == "outside":
                    self.player.y = 1
                elif kind == "far":
                    self.player.y = 3
                elif kind == "wall":
                    self.world.box(10, 9, 1, 11, 10, 5)
                elif kind == "door":
                    self.world.doors.append(Door("blocker", 9.5, 9.5, 2))
                else:
                    self.world.trees[10, 9] = Tree(10.5, 9.5)
                before = (self.enemy.x, self.enemy.y)
                self.assertEqual(self.advance(0.5), [])
                self.assertEqual((self.enemy.x, self.enemy.y), before)
                self.assertEqual(self.enemy.state, "idle")

    def test_chase_closes_distance_and_footsteps_do_not_overlap_player(self):
        events = self.advance(2.6)
        distance = math.hypot(self.enemy.x - self.player.x, self.enemy.y - self.player.y)
        self.assertLess(distance, 1.4)
        self.assertGreaterEqual(distance, self.enemy.radius + self.player.RADIUS)
        self.assertEqual(sum(event.name == "enemy_alert" for event in events), 1)
        steps = [event for event in events if event.name == "enemy_step"]
        self.assertGreater(len(steps), 1)
        self.assertTrue(all(event.surface == "stone" for event in steps))
        self.assertTrue(all(event.name in EFFECTS for event in events))
        self.assertFalse(self.world.collides(self.player.x, self.player.y, self.player.z))

    def test_attacks_are_telegraphed_and_have_recovery(self):
        self.player.y = 11.3
        events = self.combat.update(1 / 120, self.world, self.player)
        self.assertEqual([event.name for event in events], ["enemy_alert", "enemy_attack"])
        self.assertEqual(self.player.hp, 10)
        events += self.advance(0.54)
        self.assertEqual(self.player.hp, 10)
        events += self.advance(0.02)
        self.assertEqual(self.player.hp, 8)
        self.assertEqual(sum(event.name == "player_hurt" for event in events), 1)
        self.advance(1.15)
        self.assertEqual(self.player.hp, 8)
        self.advance(0.65)
        self.assertEqual(self.player.hp, 6)

    def test_windup_can_be_dodged_or_blocked(self):
        for kind in ("distance", "outside", "jump", "wall"):
            with self.subTest(kind=kind):
                self.setUp()
                self.player.y = 11.3
                self.combat.update(1 / 120, self.world, self.player)
                if kind == "distance":
                    self.player.x -= 2
                elif kind == "outside":
                    self.player.x = 1
                elif kind == "jump":
                    self.player.z = 2
                else:
                    self.world.box(10, 11, 1, 11, 12, 5)
                events = self.advance(0.56)
                self.assertEqual(self.player.hp, 10)
                self.assertEqual(sum(event.name == "enemy_miss" for event in events), 1)

    def test_leaving_territory_returns_enemy_home_and_never_crosses_bounds(self):
        self.advance(1)
        self.assertLess(self.enemy.y, self.enemy.home[1])
        self.player.x, self.player.y = 1, 1
        for _ in range(600):
            self.combat.update(1 / 120, self.world, self.player)
            self.assertTrue(self.enemy.inside_territory(self.enemy.x, self.enemy.y,
                                                        self.enemy.radius))
        self.assertEqual(self.enemy.state, "idle")
        self.assertLess(math.hypot(self.enemy.x - self.enemy.home[0],
                                   self.enemy.y - self.enemy.home[1]), 0.03)
        self.assertEqual(self.player.hp, 10)

    def test_movement_respects_pillars_thin_panels_trunks_water_and_ledge_support(self):
        for kind in ("pillar", "door", "tree", "water", "ledge"):
            with self.subTest(kind=kind):
                self.setUp()
                # Acquire first; then put an obstacle on the movement path.
                self.combat.update(1 / 120, self.world, self.player)
                if kind == "pillar":
                    self.world.box(10, 9, 1, 11, 11, 2)
                elif kind == "door":
                    self.world.doors.append(Door("barrier", 2, 10.5, 18))
                elif kind == "tree":
                    self.world.trees[10, 10] = Tree(10.5, 10.5)
                else:
                    self.world.box(2, 9, 0, 20, 11, 1, WATER if kind == "water" else AIR)
                for _ in range(480):
                    self.combat.update(1 / 120, self.world, self.player)
                    self.assertFalse(self.world.collides(self.enemy.x, self.enemy.y,
                                                         self.enemy.z, self.enemy.radius,
                                                         self.enemy.height, ignore_enemy=self.enemy))
                    self.assertTrue(self.enemy._can_stand(self.world, self.player,
                                                          self.enemy.x, self.enemy.y, self.enemy.z))
                self.assertEqual(self.player.hp, 10)

    def test_steering_can_skirt_a_low_pillar(self):
        self.world.box(10, 9, 1, 11, 10, 2)
        self.advance(4)
        self.assertLess(self.enemy.y, 9)

    def test_sword_and_fireball_kills_share_death_and_timed_respawn(self):
        for weapon in (None, FIRE_STAFF):
            with self.subTest(weapon=weapon):
                self.setUp()
                self.player.y = 10.5
                self.enemy.hp = 1
                self.combat.held_item = WeaponPickup(0, 0) if weapon is None else WeaponPickup(0, 0, weapon=weapon)
                events = self.combat.attack(self.world, self.player)
                if weapon is not None:
                    events += self.combat.update(0.3, self.world)
                self.assertEqual(self.enemy.hp, 0)
                self.assertIn("enemy_hurt", [event.name for event in events])
                self.assertIn("enemy_down", [event.name for event in events])
                self.assertNotIn("dummy_down", [event.name for event in events])
                self.assertFalse(self.world.collides(self.enemy.x, self.enemy.y, self.enemy.z))
                self.assertEqual(self.combat.update(11.99, self.world), [])
                self.assertFalse(self.enemy.alive)
                events += self.combat.update(0.01, self.world)
                self.assertEqual(events[-1].name, "enemy_respawn")
                self.assertEqual(self.enemy.hp, 4)
                self.assertEqual((self.enemy.x, self.enemy.y, self.enemy.z), self.enemy.home)
                self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_respawn_waits_for_clear_spawn_and_never_overlaps_player(self):
        self.enemy.x, self.enemy.y = 9, 11
        self.enemy.hp = 1
        self.combat._damage(self.enemy, "sword_hit")
        self.world.box(10, 12, 1, 11, 13, 4)
        self.assertEqual(self.combat.update(12, self.world, self.player), [])
        self.assertFalse(self.enemy.alive)
        self.world.box(10, 12, 1, 11, 13, 4, AIR)
        self.player.x, self.player.y, self.player.z = self.enemy.home
        self.assertEqual(self.combat.update(1, self.world, self.player), [])
        self.assertFalse(self.enemy.alive)
        self.player.y -= 2
        events = self.combat.update(1 / 120, self.world, self.player)
        self.assertEqual([event.name for event in events], ["enemy_respawn"])
        self.assertTrue(self.enemy.alive)
        self.assertEqual((self.enemy.x, self.enemy.y, self.enemy.z), self.enemy.home)

    def test_zero_dt_freezes_windup_movement_and_even_expired_respawns(self):
        self.player.y = 11.3
        self.combat.update(1 / 120, self.world, self.player)
        before = vars(self.enemy).copy()
        for _ in range(20):
            self.assertEqual(self.combat.update(0, self.world, self.player), [])
        self.assertEqual(vars(self.enemy), before)
        self.enemy.hp = self.enemy.down_remaining = 0
        self.assertEqual(self.combat.update(0, self.world, self.player), [])
        self.assertFalse(self.enemy.alive)

    def test_large_ai_dt_has_constant_collision_budget(self):
        with patch.object(self.world, "collides", wraps=self.world.collides) as collision:
            self.combat.update(10000, self.world, self.player)
        self.assertLessEqual(collision.call_count, 10)
        self.assertLessEqual(math.hypot(self.enemy.x - self.enemy.home[0],
                                       self.enemy.y - self.enemy.home[1]), 0.1551)

    def test_every_new_combat_result_has_a_registered_sound(self):
        names = {"enemy_alert", "enemy_step", "enemy_attack", "enemy_miss",
                 "enemy_hurt", "enemy_down", "enemy_respawn", "player_hurt",
                 "player_down", "player_respawn"}
        self.assertTrue(names <= EFFECTS.keys(), names - EFFECTS.keys())


if __name__ == "__main__":
    unittest.main()

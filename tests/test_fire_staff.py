"""Single-item swaps, northern placement and continuous fireball collision."""

import math
import unittest

from ascii3d.combat import (BURST_DURATION, FIREBALL_RANGE, FIREBALL_SPEED,
                            FIRE_STAFF, MAX_FIREBALLS, SWORD, CombatState,
                            Enemy, Fireball, WeaponPickup)
from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.world import FLOOR, Tree, World, build_world


class FireStaffTests(unittest.TestCase):
    def setUp(self):
        self.world = World.empty(40, 40, 10)
        self.world.box(0, 0, 0, 40, 40, 1, FLOOR)
        self.player = Player(x=8.5, y=4.5)
        self.staff = WeaponPickup(8.5, 6.5, weapon=FIRE_STAFF)
        self.enemy = Enemy("Training dummy", 8.5, 14.5)
        self.combat = self.world.combat
        self.combat.pickups = [self.staff]
        self.combat.enemies = [self.enemy]

    def equip_staff(self):
        events = self.world.interact(self.player)
        self.assertEqual(events[-1].name, "staff_pickup")
        self.assertIs(self.combat.held_item, self.staff)
        return events

    def test_live_staff_is_on_accessible_floor_inside_northern_ruins(self):
        world = build_world()
        staff, = [item for item in world.combat.pickups if item.weapon == FIRE_STAFF]
        self.assertEqual(world.area(staff.x, staff.y), "NORTHERN RUINS")
        player = Player(x=staff.x, y=staff.y - 2)
        self.assertFalse(world.collides(player.x, player.y, player.z))
        self.assertFalse(world.collides(staff.x, staff.y, staff.z))
        self.assertIs(world.interaction_target(player), staff)
        self.assertEqual(world.interact(player)[-1].name, "staff_pickup")

    def test_swaps_drop_only_the_held_instance_and_allow_recollection(self):
        sword = WeaponPickup(8.5, 6.5, group="starter")
        alias = WeaponPickup(2.5, 2.5, group="starter")
        self.staff.y = 8.5
        self.combat.pickups = [sword, alias, self.staff]
        events = self.world.interact(self.player)
        self.assertEqual([e.name for e in events], ["sword_pickup"])
        self.assertTrue(sword.collected and alias.collected)
        self.assertFalse(self.staff.collected)
        self.player.y = 6.5
        events += self.equip_staff()
        self.assertEqual([e.name for e in events[-2:]], ["item_drop", "staff_pickup"])
        self.assertFalse(sword.collected)
        self.assertTrue(alias.collected)
        self.assertIsNone(sword.group)
        self.assertAlmostEqual(sword.z, 1)
        self.assertLess(math.hypot(sword.x - self.player.x, sword.y - self.player.y), 0.7)
        self.assertIsNone(self.world.interaction_target(self.player))
        for item in (sword, self.staff) * 6:
            self.player.x, self.player.y = item.x, item.y - 2
            self.assertIs(self.world.interaction_target(self.player), item)
            events += self.world.interact(self.player)
            self.assertIs(self.combat.held_item, item)
            self.assertEqual(sum(not pickup.collected for pickup in self.combat.pickups), 1)
            self.assertEqual(len(self.combat.pickups), 3)
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_drop_avoids_wall_and_settles_from_jump_and_raised_support(self):
        self.world.box(8, 3, 1, 9, 4, 5)  # blocks preferred drop behind player
        sword = WeaponPickup(0, 0, collected=True)
        self.combat.held_item = sword
        self.equip_staff()
        self.assertFalse(self.world.collides(sword.x, sword.y, sword.z, 0.14, 1.60))
        self.assertEqual(sword.z, 1)
        for floor, feet in ((1, 2.0), (3, 3.0)):
            with self.subTest(floor=floor):
                self.world.box(5, 5, 0, 12, 10, floor, FLOOR)
                self.player.x, self.player.y, self.player.z = 8.5, 6.5, feet
                self.staff.x, self.staff.y, self.staff.z = 8.5, 8.5, feet
                self.staff.collected = False
                self.combat.held_item = sword
                self.equip_staff()
                self.assertEqual(sword.z, floor)

    def test_staff_collection_uses_shared_aim_reach_wall_door_and_trunk_checks(self):
        for kind in ("aim", "reach", "wall", "door", "tree"):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == "aim":
                    self.player.yaw = 0
                elif kind == "reach":
                    self.player.y = 2
                elif kind == "wall":
                    self.world.box(8, 5, 1, 9, 6, 4)
                elif kind == "door":
                    self.world.doors.append(Door("blocker", 7.5, 5.5, 2))
                else:
                    self.world.trees[8, 5] = Tree(8.5, 5.5)
                self.assertIsNone(self.combat.held_item)
                self.assertNotIn("staff_pickup", [e.name for e in self.world.interact(self.player)])
                self.assertFalse(self.staff.collected)

    def test_dropped_item_cannot_cross_a_thin_closed_door(self):
        self.world.doors.append(Door("behind player", 7.5, 4.2, 2))
        sword = WeaponPickup(0, 0, collected=True)
        self.combat.held_item = sword
        self.equip_staff()
        self.assertGreater(sword.y, 4.2)
        self.assertFalse(self.world.collides(sword.x, sword.y, sword.z, 0.14, 1.60))

    def test_cast_is_a_travelling_projectile_with_cooldown_and_delayed_damage(self):
        self.equip_staff()
        events = self.combat.attack(self.world, self.player)
        self.assertEqual([event.name for event in events], ["fireball_cast"])
        self.assertEqual(self.enemy.hp, 3)
        self.assertEqual(self.combat.attack(self.world, self.player), [])
        ball, = self.combat.fireballs
        self.combat.update(0.25, self.world)
        self.assertAlmostEqual(ball.y, self.player.y + FIREBALL_SPEED * 0.25)
        events += self.combat.update(0.6, self.world)
        self.assertEqual([e.name for e in events], ["fireball_cast", "fireball_hit"])
        self.assertEqual(self.enemy.hp, 2)
        self.assertFalse(self.combat.fireballs)
        self.assertTrue(self.combat.bursts)
        self.assertEqual(self.combat.update(0.1, self.world), [])
        self.assertEqual(self.enemy.hp, 2)
        self.combat.update(BURST_DURATION, self.world)
        self.assertFalse(self.combat.bursts)
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_fireballs_stop_at_wall_thin_door_or_trunk_before_enemy(self):
        for kind in ("wall", "door", "tree"):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == "wall":
                    self.world.box(8, 9, 1, 9, 10, 5)
                elif kind == "door":
                    self.world.doors.append(Door("blocker", 7.5, 9.5, 2))
                else:
                    self.world.trees[8, 9] = Tree(8.5, 9.5)
                self.equip_staff()
                self.combat.attack(self.world, self.player)
                # A whole-second step crosses the obstacle and the enemy.
                events = self.combat.update(1, self.world)
                self.assertEqual([e.name for e in events], ["fireball_impact"])
                self.assertEqual(self.enemy.hp, 3)
                self.assertFalse(self.combat.fireballs)
                self.assertLess(self.combat.bursts[0].y, 10)

    def test_open_door_allows_projectile_and_nearest_enemy_is_only_hit(self):
        door = Door("open", 7.5, 9.5, 2, openness=1)
        self.world.doors.append(door)
        farther = Enemy("Farther", 8.5, 17)
        self.combat.enemies.insert(0, farther)
        self.equip_staff()
        self.combat.attack(self.world, self.player)
        self.assertEqual(self.combat.update(2, self.world)[0].name, "fireball_hit")
        self.assertEqual((self.enemy.hp, farther.hp), (2, 3))

    def test_pitch_miss_range_expiry_and_no_tunnelling_at_a_short_voxel_corner(self):
        self.equip_staff()
        self.player.pitch = 0.6
        self.combat.attack(self.world, self.player)
        ball, = self.combat.fireballs
        self.assertGreater(ball.direction[2], 0)
        events = self.combat.update(FIREBALL_RANGE / FIREBALL_SPEED + 0.1, self.world)
        self.assertEqual([e.name for e in events], ["fireball_fizzle"])
        self.assertEqual(self.enemy.hp, 3)
        self.world.box(9, 5, 1, 10, 6, 4)
        root = math.sqrt(0.5)
        self.combat.fireballs.append(Fireball(8.99, 5.02, 2, (root, -root, 0)))
        self.assertEqual(self.combat.update(0.1, self.world)[0].name, "fireball_impact")
        self.assertAlmostEqual(self.combat.bursts[-1].x, 9)

    def test_fireball_down_reset_and_all_result_paths_have_sound(self):
        events = self.equip_staff()
        for hp in (2, 1, 0):
            events += self.combat.attack(self.world, self.player)
            events += self.combat.update(1, self.world)
            self.assertEqual(self.enemy.hp, hp)
        self.assertEqual(sum(e.name == "dummy_down" for e in events), 1)
        events += self.combat.update(4, self.world)
        self.assertEqual(self.enemy.hp, 3)
        self.assertEqual(events[-1].name, "dummy_reset")
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_zero_dt_and_swapping_preserve_flight_and_attack_cooldown(self):
        self.equip_staff()
        self.combat.attack(self.world, self.player)
        ball = self.combat.fireballs[0]
        before = (ball.x, ball.y, ball.z, ball.range_left, self.combat.cooldown)
        self.assertEqual(self.combat.update(0, self.world), [])
        self.assertEqual(before, (ball.x, ball.y, ball.z, ball.range_left, self.combat.cooldown))
        sword = WeaponPickup(8.5, 6.5)
        self.combat.pickups.append(sword)
        self.assertEqual(self.world.interact(self.player)[-1].name, "sword_pickup")
        self.assertEqual(self.combat.held_item.weapon, SWORD)
        self.assertEqual(self.combat.attack(self.world, self.player), [])
        self.assertEqual(self.combat.swing_remaining, 0)
        self.assertEqual(self.combat.update(1, self.world)[0].name, "fireball_hit")

    def test_projectile_and_burst_counts_remain_bounded_under_repeated_casts(self):
        self.equip_staff()
        self.player.yaw = 0
        for _ in range(120):
            self.combat.attack(self.world, self.player)
            self.combat.update(1 / 30, self.world)
            self.assertLessEqual(len(self.combat.fireballs), MAX_FIREBALLS)
            self.assertLessEqual(len(self.combat.bursts), MAX_FIREBALLS)


if __name__ == "__main__":
    unittest.main()

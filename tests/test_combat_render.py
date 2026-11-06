"""Depth, labels, animation and small-terminal combat UI regressions."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import (FIRE_STAFF, WARDEN_BEHAVIOR, CombatState, Enemy,
                            FireBurst, Fireball, WeaponPickup)
from ascii3d.combat_render import _draw_equipped, _draw_pickup, draw_combat
from ascii3d.geometry import Camera
from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import FLOOR, Tree, World


class CombatRenderingTests(unittest.TestCase):
    def setUp(self):
        self.world = World.empty(30, 30, 10)
        self.world.box(0, 0, 0, 30, 30, 1, FLOOR)
        self.player = Player(x=8.5, y=4.5)
        self.enemy = Enemy("Training dummy", 8.5, 8.5)
        self.world.combat = CombatState(enemies=[self.enemy])
        self.renderer = Renderer(self.world)

    def make_warden(self):
        warden = Enemy("Watchstone Warden", 8.5, 8.5, radius=0.44, height=2.15,
                       hp=4, max_hp=4, behavior=WARDEN_BEHAVIOR,
                       territory=(1, 1, 29, 29))
        self.world.combat.enemies = [warden]
        return warden

    def test_warden_is_opaque_occluded_and_only_named_when_aimed_at(self):
        self.make_warden()
        text = "\n".join(self.renderer.frame(self.player, 100, 34))
        self.assertIn("Watchstone Warden [4/4]", text)
        self.player.yaw = 0
        self.assertNotIn("Watchstone Warden", "\n".join(
            self.renderer.frame(self.player, 100, 34)))
        self.player.yaw = math.pi / 2
        self.world.box(0, 6, 1, 30, 7, 8)
        hidden = self.renderer.scene(self.player, 100, 29)
        self.world.combat.enemies.clear()
        self.assertEqual(hidden, self.renderer.scene(self.player, 100, 29))

    def test_warden_windup_and_movement_are_deterministic_and_dead_body_vanishes(self):
        warden = self.make_warden()
        idle = self.renderer.scene(self.player, 100, 29)
        warden.state, warden.attack_remaining = "windup", 0.1
        windup = self.renderer.scene(self.player, 100, 29)
        self.assertNotEqual(idle, windup)
        self.assertEqual(windup, self.renderer.scene(self.player, 100, 29))
        warden.hp = 0
        down = self.renderer.scene(self.player, 100, 29)
        self.world.combat.enemies.clear()
        self.assertEqual(down, self.renderer.scene(self.player, 100, 29))

    def test_warden_body_covers_background_from_all_four_sides(self):
        warden = self.make_warden()
        for x, y, yaw in ((8.5, 5.5, math.pi / 2), (8.5, 11.5, -math.pi / 2),
                          (5.5, 8.5, 0), (11.5, 8.5, math.pi)):
            with self.subTest(yaw=yaw):
                self.player.x, self.player.y, self.player.yaw = x, y, yaw
                pixels = [["~"] * 90 for _ in range(30)]
                depths = [[math.inf] * 90 for _ in range(30)]
                draw_combat(self.world.combat, self.world, pixels, depths,
                            self.player, 52, 0.5, 0)
                cam = Camera(self.player, 90, 30, 52, 0.5)
                px, py, _ = cam.project(warden.x, warden.y, warden.z + 1.2)
                self.assertNotEqual(pixels[round(py)][round(px)], "~")
                self.assertLess(depths[round(py)][round(px)], math.inf)

    def test_quad_spans_match_triangle_reference_with_perspective_and_occlusion(self):
        cam = Camera(self.player, 60, 20, 35, 0.5)
        faces = (((5, 8, 1), (12, 8, 1), (12, 8, 4), (5, 8, 4)),
                 ((7, 5, 1), (11, 12, 1), (11, 12, 4), (7, 5, 4)),
                 ((3, 5, 1), (14, 5, 1), (14, 14, 1), (3, 14, 1)),
                 ((7, 4.55, 1), (11, 8, 1), (11, 8, 4), (7, 4.55, 4)))
        for face in faces:
            with self.subTest(face=face):
                points = [cam.project(*point) for point in face]
                reference, actual = [[['~'] * 60 for _ in range(20)] for _ in range(2)]
                first, second = [[[0.5 if x % 5 == 0 else math.inf for x in range(60)]
                                  for _ in range(20)] for _ in range(2)]
                a, b, c, d = points
                cam.triangle(reference, first, a, b, c, '#')
                cam.triangle(reference, first, a, c, d, '#')
                cam.quad(actual, second, a, b, c, d, '#')
                self.assertEqual(actual, reference)
                for row, expected in zip(second, first):
                    for depth, expected_depth in zip(row, expected):
                        if math.isfinite(expected_depth):
                            self.assertAlmostEqual(depth, expected_depth, places=7)
                        else:
                            self.assertEqual(depth, math.inf)

    def test_aimed_enemy_name_is_above_body_and_requires_range_and_aim(self):
        scene = self.renderer.scene(self.player, 120, 35)
        rows = ["".join(row) for row in scene]
        name_row = next(i for i, row in enumerate(rows) if "Training dummy [3/3]" in row)
        self.assertLess(name_row, len(rows) // 2)
        self.assertTrue(any("%" in row for row in rows[name_row + 1:]))
        self.player.yaw = 1.2
        self.assertNotIn("Training dummy", "\n".join("".join(row) for row in self.renderer.scene(self.player, 120, 35)))
        self.player.yaw, self.enemy.y = math.pi / 2, 16
        self.assertNotIn("Training dummy", "\n".join("".join(row) for row in self.renderer.scene(self.player, 120, 35)))

    def test_wall_hides_pickup_dummy_and_label(self):
        self.world.box(0, 6, 1, 30, 7, 8)
        self.world.combat = CombatState()
        before = self.renderer.scene(self.player, 80, 28)
        self.world.combat = CombatState(pickups=[WeaponPickup(8.5, 8)], enemies=[self.enemy])
        self.assertEqual(before, self.renderer.scene(self.player, 80, 28))

    def test_closed_door_hides_target_and_open_door_reveals_it(self):
        door = Door("test", 6, 6.5, 5)
        self.world.doors.append(door)
        closed = self.renderer.scene(self.player, 100, 32)
        self.assertNotIn("Training dummy", "\n".join("".join(row) for row in closed))
        door.openness = 1
        opened = self.renderer.scene(self.player, 100, 32)
        self.assertIn("Training dummy", "\n".join("".join(row) for row in opened))

    def test_trunk_blocks_name_even_with_visible_dummy_shoulders(self):
        self.world.trees[8, 6] = Tree(8.5, 6.5)
        self.assertNotIn("Training dummy", "\n".join(self.renderer.frame(self.player, 100, 34)))

    def test_pickup_prompt_equipment_swing_and_down_pose_are_visible(self):
        self.world.combat.pickups.append(WeaponPickup(8.5, 6.5))
        before = self.renderer.frame(self.player, 100, 34)
        self.assertIn("[E] Collect iron sword", "\n".join(before))
        self.world.interact(self.player)
        idle = self.renderer.frame(self.player, 100, 34)
        self.assertIn("IRON SWORD", idle[0])
        self.assertNotIn("[E] Collect", "\n".join(idle))
        self.world.combat.attack(self.world, self.player)
        self.world.combat.update(0.15, self.world)
        swing = self.renderer.frame(self.player, 100, 34)
        self.assertNotEqual(idle, swing)
        self.assertEqual(swing, self.renderer.frame(self.player, 100, 34))
        self.enemy.hp = 0
        down = self.renderer.frame(self.player, 100, 34)
        self.assertNotEqual(swing, down)
        self.assertNotIn("Training dummy", "\n".join(down))

    def test_help_and_attack_control_fit_minimum_viewport(self):
        frame = self.renderer.frame(self.player, 60, 20, help_open=True)
        text = "\n".join(frame)
        for label in ("CONTROLS", "E", "LEFT CLICK", "MOUSE", "ESC"):
            self.assertIn(label, text)
        self.assertEqual(len(frame), 20)
        self.assertTrue(all(len(row) == 60 for row in frame))

    def test_geometry_is_depth_tested_and_draw_count_is_bounded(self):
        self.world.combat.enemies *= 100
        self.world.combat.pickups = [WeaponPickup(8.5, 8)] * 100
        pixels = [[" "] * 60 for _ in range(20)]
        depths = [[0.1] * 60 for _ in range(20)]
        draw_combat(self.world.combat, self.world, pixels, depths, self.player, 35, 0.5, 0)
        self.assertTrue(all(char == " " for row in pixels for char in row))
        with patch("ascii3d.combat_render._draw_enemy") as enemies, patch("ascii3d.combat_render._draw_pickup") as pickups:
            draw_combat(self.world.combat, self.world, pixels, depths, self.player, 35, 0.5, 0)
        self.assertLessEqual(enemies.call_count, 1200 // 180)
        self.assertLessEqual(pickups.call_count, 1200 // 240)

    def test_pickup_and_equipped_blade_interiors_are_opaque_and_local(self):
        cam = Camera(self.player, 90, 30, 52, 0.5)
        for equipped, sample in ((False, (44, 21)), (True, (65, 18))):
            with self.subTest(equipped=equipped):
                pixels = [["~"] * 90 for _ in range(30)]
                depths = [[math.inf] * 90 for _ in range(30)]
                if equipped:
                    _draw_equipped(CombatState(held_item=WeaponPickup(0, 0)), cam, pixels, depths, self.player)
                else:
                    _draw_pickup(WeaponPickup(8.5, 6.5), cam, pixels, depths, 0)
                x, y = sample
                self.assertEqual(pixels[y][x], "#")
                self.assertLess(sum(char != "~" for row in pixels for char in row), 90 * 30 * 0.08)
                self.assertLess(depths[y][x], math.inf)

    def test_enemy_has_opaque_torso_and_head_from_all_four_sides(self):
        for x, y, yaw in ((8.5, 5.5, math.pi / 2), (8.5, 11.5, -math.pi / 2),
                           (5.5, 8.5, 0), (11.5, 8.5, math.pi)):
            with self.subTest(yaw=yaw):
                self.player.x, self.player.y, self.player.yaw = x, y, yaw
                pixels = self.renderer.scene(self.player, 90, 30)
                self.assertGreater(sum(char == "%" for row in pixels for char in row), 8)
                self.assertGreater(sum(char == "@" for row in pixels for char in row), 2)

    def test_triangle_fill_interpolates_depth_and_respects_foreground(self):
        cam = Camera(self.player, 20, 16, 12, 0.5)
        pixels = [["."] * 20 for _ in range(16)]
        depths = [[math.inf] * 20 for _ in range(16)]
        depths[5][5] = 1
        cam.triangle(pixels, depths, (2, 2, 2), (14, 2, 4), (2, 14, 2))
        self.assertEqual(pixels[5][5], ".")
        self.assertEqual(pixels[6][6], "#")
        self.assertAlmostEqual(depths[6][6], 2.4)
        self.assertEqual(pixels[14][14], ".")

    def test_staff_pickup_held_shape_swap_prompt_and_cast_animation(self):
        staff = WeaponPickup(8.5, 6.5, weapon=FIRE_STAFF)
        combat = self.world.combat
        combat.pickups.append(staff)
        combat.held_item = WeaponPickup(0, 0)
        before = "\n".join(self.renderer.frame(self.player, 100, 34))
        self.assertIn("[E] Collect fire staff (drop iron sword)", before)
        self.world.interact(self.player)
        idle = self.renderer.frame(self.player, 100, 34)
        self.assertIn("FIRE STAFF", idle[0])
        self.assertNotIn("[E] Collect", "\n".join(idle))
        combat.attack(self.world, self.player)
        combat.update(0.15, self.world)
        cast = self.renderer.frame(self.player, 100, 34)
        self.assertNotEqual(idle, cast)
        self.assertEqual(cast, self.renderer.frame(self.player, 100, 34))
        self.assertTrue(all(len(row) == 100 and all(32 <= ord(c) <= 126 for c in row) for row in cast))

    def test_staff_is_opaque_and_readable_from_four_sides(self):
        staff = WeaponPickup(8.5, 8.5, weapon=FIRE_STAFF)
        for x, y, yaw in ((8.5, 6.5, math.pi / 2), (8.5, 10.5, -math.pi / 2),
                           (6.5, 8.5, 0), (10.5, 8.5, math.pi)):
            self.player.x, self.player.y, self.player.yaw = x, y, yaw
            cam = Camera(self.player, 90, 30, 52, 0.5)
            pixels = [["~"] * 90 for _ in range(30)]
            depths = [[math.inf] * 90 for _ in range(30)]
            _draw_pickup(staff, cam, pixels, depths, 0)
            self.assertGreater(sum(char == "#" for row in pixels for char in row), 5)
            self.assertGreater(sum(char == "@" for row in pixels for char in row), 2)
            self.assertLess(sum(char != "~" for row in pixels for char in row), 90 * 30 * 0.08)
            self.assertTrue(all(depths[y][x] < math.inf for y, row in enumerate(pixels)
                                for x, char in enumerate(row) if char != "~"))

    def test_staff_fireballs_and_bursts_respect_foreground_depth_and_walls(self):
        combat = self.world.combat
        combat.pickups = [WeaponPickup(8.5, 8, weapon=FIRE_STAFF)]
        combat.held_item = combat.pickups[0]
        combat.fireballs = [Fireball(8.5, 7.5, self.player.eye_z, (0, 1, 0))]
        combat.bursts = [FireBurst(8.5, 8.5, self.player.eye_z)]
        pixels = [["~"] * 90 for _ in range(30)]
        depths = [[0.1] * 90 for _ in range(30)]
        draw_combat(combat, self.world, pixels, depths, self.player, 52, 0.5, 0)
        self.assertTrue(all(char == "~" for row in pixels for char in row))
        combat.held_item = None
        self.world.box(0, 6, 1, 30, 7, 8)
        blocked = self.renderer.scene(self.player, 90, 30)
        combat.pickups.clear()
        combat.fireballs.clear()
        combat.bursts.clear()
        self.assertEqual(blocked, self.renderer.scene(self.player, 90, 30))

    def test_travelling_fireball_has_an_opaque_core_and_finite_depth(self):
        combat = CombatState(fireballs=[Fireball(8.5, 8.5, self.player.eye_z, (0, 1, 0))])
        pixels = [["~"] * 90 for _ in range(30)]
        depths = [[math.inf] * 90 for _ in range(30)]
        draw_combat(combat, self.world, pixels, depths, self.player, 52, 0.5, 0)
        self.assertTrue(any(char in "@*" for row in pixels for char in row))
        self.assertLess(sum(char != "~" for row in pixels for char in row), 30)
        self.assertTrue(any(value < math.inf for row in depths for value in row))


if __name__ == "__main__":
    unittest.main()

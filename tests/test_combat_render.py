"""Depth, labels, animation and small-terminal combat UI regressions."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import CombatState, Enemy, SwordPickup
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
        self.world.combat = CombatState(pickups=[SwordPickup(8.5, 8)], enemies=[self.enemy])
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
        self.world.combat.pickups.append(SwordPickup(8.5, 6.5))
        before = self.renderer.frame(self.player, 100, 34)
        self.assertIn("[E] Collect iron sword", "\n".join(before))
        self.world.interact(self.player)
        idle = self.renderer.frame(self.player, 100, 34)
        self.assertIn("IRON SWORD", idle[0])
        self.assertNotIn("[E] Collect", "\n".join(idle))
        self.world.combat.attack(self.world, self.player)
        self.world.combat.update(0.15)
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
        for label in ("FIELD GUIDE", "E            use", "Q            attack", "NORTH GATE", "ESC"):
            self.assertIn(label, text)
        self.assertEqual(len(frame), 20)
        self.assertTrue(all(len(row) == 60 for row in frame))

    def test_geometry_is_depth_tested_and_draw_count_is_bounded(self):
        self.world.combat.enemies *= 100
        self.world.combat.pickups = [SwordPickup(8.5, 8)] * 100
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
                    _draw_equipped(CombatState(has_sword=True), cam, pixels, depths, self.player)
                else:
                    _draw_pickup(SwordPickup(8.5, 6.5), cam, pixels, depths, 0)
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


if __name__ == "__main__":
    unittest.main()

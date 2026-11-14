"""Actor material colors follow geometry and retain opaque depth coverage."""

import math
import unittest

from ascii3d.combat import (FIRE_STAFF, WARDEN_BEHAVIOR, CombatState, Enemy,
                            Fireball, WeaponPickup)
from ascii3d.combat_render import _draw_pickup, _ring, _stroke, draw_combat
from ascii3d.geometry import Camera
from ascii3d.palette import ARCANE, BONE, EMBER, FIRE, STRAW
from ascii3d.player import Player
from ascii3d.shading import Ink, Shading
from ascii3d.world import FLOOR, METAL, STONE, WOOD, World


class ActorColorTests(unittest.TestCase):
    def setUp(self):
        self.world = World.empty(24, 24, 12)
        self.world.box(0, 0, 0, 24, 24, 1, FLOOR)
        self.player = Player(x=8.5, y=4.5)

    @staticmethod
    def buffers(depth=math.inf):
        return ([[" "] * 120 for _ in range(40)],
                [[depth] * 120 for _ in range(40)])

    def camera(self):
        camera = Camera(self.player, 120, 40, 69, 0.5)
        camera.shading = Shading()
        return camera

    def render(self, combat, seconds=0.0, depth=math.inf):
        pixels, depths = self.buffers(depth)
        draw_combat(combat, self.world, pixels, depths, self.player,
                    69, 0.5, seconds, labels=False)
        return pixels, depths

    def assert_opaque(self, pixels, depths):
        drawn = [(x, y, char) for y, row in enumerate(pixels)
                 for x, char in enumerate(row) if char != " "]
        self.assertTrue(drawn)
        for x, y, char in drawn:
            self.assertIsInstance(char, Ink)
            self.assertTrue(math.isfinite(depths[y][x]))

    def test_all_warden_parts_use_stone_including_visor_and_arms(self):
        enemy = Enemy("Stone guardian", 8.5, 8.5, radius=0.44, height=2.15,
                      behavior=WARDEN_BEHAVIOR, territory=(1, 1, 23, 23))
        combat = CombatState(enemies=[enemy])
        for state in ("idle", "windup"):
            enemy.state, enemy.attack_remaining = state, 0.15
            with self.subTest(state=state):
                pixels, depths = self.render(combat)
                self.assert_opaque(pixels, depths)
                self.assertEqual({char.material for row in pixels for char in row if char != " "}, {STONE})

    def test_dummy_has_straw_body_bone_head_and_wooden_support_from_every_side(self):
        enemy = Enemy("Training effigy", 8.5, 8.5)
        combat = CombatState(enemies=[enemy])
        for x, y, yaw in ((8.5, 5.5, math.pi / 2), (8.5, 11.5, -math.pi / 2),
                          (5.5, 8.5, 0), (11.5, 8.5, math.pi)):
            self.player.x, self.player.y, self.player.yaw = x, y, yaw
            with self.subTest(yaw=yaw):
                pixels, depths = self.render(combat)
                self.assert_opaque(pixels, depths)
                materials = [char.material for row in pixels for char in row if char != " "]
                self.assertEqual(set(materials), {WOOD, STRAW, BONE})
                self.assertGreater(materials.count(STRAW), 8)
                self.assertGreater(materials.count(BONE), 2)
                cam = self.camera()
                px, py, _ = cam.project(enemy.x, enemy.y, enemy.z + 1.8)
                self.assertEqual(pixels[round(py)][round(px)].material, BONE)

    def test_sword_and_staff_keep_distinct_component_materials(self):
        cam = self.camera()
        for weapon, expected, sample_height, sample_material in (
                (None, {METAL, WOOD, ARCANE}, 1.20, METAL),
                (FIRE_STAFF, {METAL, WOOD, ARCANE}, 0.80, WOOD)):
            pickup = WeaponPickup(8.5, 6.5) if weapon is None else WeaponPickup(8.5, 6.5, weapon=weapon)
            pixels, depths = self.buffers()
            with self.subTest(weapon=pickup.name):
                _draw_pickup(pickup, cam, pixels, depths, 0)
                self.assert_opaque(pixels, depths)
                self.assertEqual({char.material for row in pixels for char in row if char != " "}, expected)
                px, py, _ = cam.project(pickup.x, pickup.y, pickup.z + sample_height)
                self.assertEqual(pixels[round(py)][round(px)].material, sample_material)

    def test_literal_strokes_and_rings_keep_explicit_material_identity(self):
        cam = self.camera()
        for material in (STONE, METAL, WOOD):
            pixels, depths = self.buffers()
            _stroke(cam, pixels, depths, (8.3, 7, 1.5), (8.7, 7, 2.5), "#", material=material)
            self.assert_opaque(pixels, depths)
            self.assertEqual({char.material for row in pixels for char in row if char != " "}, {material})
            self.assertTrue(all(str(char) == "#" for row in pixels for char in row if char != " "))
        pixels, depths = self.buffers()
        _ring(cam, pixels, depths, 8.5, 7, 2, 0.4, 0, 0.4, material=BONE)
        self.assert_opaque(pixels, depths)
        self.assertEqual({char.material for row in pixels for char in row if char != " "}, {BONE})

    def test_fire_core_and_trailing_embers_have_distinct_emission_and_freeze_with_time(self):
        ball = Fireball(8.5, 6.5, self.player.eye_z, (1, 0, 0))
        combat = CombatState(fireballs=[ball])
        first, depths = self.render(combat, seconds=0)
        again, again_depths = self.render(combat, seconds=0)
        later, later_depths = self.render(combat, seconds=math.pi / 11)

        def tokens(pixels):
            return [[(str(char), char.material, char.level, char.effects) if isinstance(char, Ink) else str(char)
                     for char in row] for row in pixels]

        self.assert_opaque(first, depths)
        self.assertEqual(tokens(first), tokens(again))
        self.assertEqual(depths, again_depths)
        self.assertEqual(depths, later_depths)
        self.assertNotEqual(tokens(first), tokens(later))
        fire = [char.level for row in first for char in row if getattr(char, "material", None) == FIRE]
        embers = [char.level for row in first for char in row if getattr(char, "material", None) == EMBER]
        self.assertTrue(fire and embers)
        self.assertGreaterEqual(max(fire), 14)
        self.assertLess(max(embers), max(fire))

    def test_colored_effects_and_weapons_cannot_overwrite_foreground_depth(self):
        combat = CombatState(enemies=[Enemy("Training effigy", 8.5, 8.5)],
                             pickups=[WeaponPickup(8.5, 6.5, weapon=FIRE_STAFF)],
                             fireballs=[Fireball(8.5, 7.5, self.player.eye_z, (1, 0, 0))],
                             held_item=WeaponPickup(0, 0))
        pixels, depths = self.render(combat, seconds=3.2, depth=0.1)
        self.assertTrue(all(char == " " for row in pixels for char in row))
        self.assertTrue(all(value == 0.1 for row in depths for value in row))


if __name__ == "__main__":
    unittest.main()

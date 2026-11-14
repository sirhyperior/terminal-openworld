"""Material relief and tonal range remain coherent within one visible body."""

import math
import unittest
from unittest.mock import patch

from ascii3d.palette import (ASH, DUST, FIRE, GRASS, LEAVES, METAL, STONE,
                             GRAY_LEVELS, UI_ACCENT, color_rgb)
from ascii3d.combat import Fireball
from ascii3d.player import Player
from ascii3d.shading import Shading
from ascii3d.world import World


class SurfaceQualityTests(unittest.TestCase):
    def test_one_coplanar_stone_surface_contains_deep_creases_and_lit_detail(self):
        shading = Shading()
        samples = [shading.surface(STONE, x / 9, y / 9, 2, (0, 0, 1), 2,
                                   texture_position=(x / 9, y / 9, 0),
                                   texture_normal=(0, 0, 1))
                   for y in range(36) for x in range(36)]
        levels = {sample.level for sample in samples}
        self.assertGreaterEqual(len(levels), 10)
        self.assertLessEqual(min(levels), 2)
        self.assertGreaterEqual(max(levels), 13)
        self.assertGreater(GRAY_LEVELS[max(levels)] - GRAY_LEVELS[min(levels)], 190)
        self.assertGreaterEqual(len(set(map(str, samples))), 6)
        self.assertEqual({sample.material for sample in samples}, {STONE})

    def test_light_direction_produces_a_large_readable_range_on_the_same_texture(self):
        shading = Shading()
        toward = (-0.38, -0.48, 0.79)
        length = math.sqrt(sum(value * value for value in toward))
        toward = tuple(value / length for value in toward)
        for material in (STONE, GRASS, LEAVES):
            with self.subTest(material=material):
                bright = shading.surface(material, 1.23, 2.34, 3.45, toward, 1,
                                         texture_position=(0.5, 0.5, 0),
                                         texture_normal=(0, 0, 1))
                dark = shading.surface(material, 1.23, 2.34, 3.45,
                                       tuple(-value for value in toward), 1,
                                       texture_position=(0.5, 0.5, 0),
                                       texture_normal=(0, 0, 1))
                self.assertGreaterEqual(bright.level - dark.level, 6)
                self.assertGreater(GRAY_LEVELS[bright.level], GRAY_LEVELS[dark.level] * 4)

    def test_local_detail_translates_with_object_and_does_not_shimmer_with_time(self):
        shading = Shading()
        player = Player(x=1, y=1)
        values = []
        for seconds, location in ((0, (1, 2, 3)), (11, (1, 2, 3)), (11, (15, 12, 7))):
            shading.prepare(player, seconds)
            token = shading.surface(STONE, *location, (0, 0, 1), 3,
                                    texture_position=(0.73, 1.37, 0),
                                    texture_normal=(0, 0, 1))
            values.append((str(token), token.level, token.material, token.effects))
        self.assertEqual(values, [values[0]] * 3)

    def test_metal_highlight_depends_on_view_without_changing_material(self):
        shading = Shading()
        samples = []
        for side in (1, -1):
            player = Player(x=4 + side * 3.8, y=4 + side * 4.8,
                            z=2 + 7.9 - Player.EYE)
            shading.prepare(player)
            samples.append(shading.surface(METAL, 4, 4, 2, (0, 0, 1), 4,
                                           texture_position=(0.31, 0.67, 0)))
        self.assertGreater(samples[0].level, samples[1].level)
        self.assertEqual(samples[0].material, samples[1].material)

    def test_shadow_hues_and_pale_highlights_are_distinct_from_simple_rgb_scaling(self):
        dark, bright = color_rgb(METAL, 3), color_rgb(METAL, 14)
        self.assertGreater(bright[0] / bright[2], dark[0] / dark[2])
        dark, bright = color_rgb(GRASS, 3), color_rgb(GRASS, 12)
        self.assertGreater(dark[2] / dark[1], bright[2] / bright[1])
        self.assertLessEqual(GRAY_LEVELS[1], 20)
        self.assertGreaterEqual(GRAY_LEVELS[12], 220)

    def test_particle_materials_receive_depth_and_firelight_while_ui_stays_stable(self):
        for material in (DUST, ASH):
            with self.subTest(material=material):
                neutral = color_rgb(material, 8)
                self.assertNotEqual(neutral, color_rgb(material, 8, 12))
                self.assertNotEqual(neutral, color_rgb(material, 8, 3))
                self.assertEqual(Shading().surface(material, 1, 2, 3, (0, 0, 1), 2).material, material)
        self.assertEqual(color_rgb(UI_ACCENT, 8), color_rgb(UI_ACCENT, 8, 15))

    def test_emissive_shell_keeps_dim_edges_next_to_its_own_light(self):
        world = World.empty(12, 12, 8)
        world.combat.fireballs = [Fireball(4, 4, 2, (1, 0, 0))]
        shading = Shading(world)
        shading.prepare(Player(x=2, y=4))
        with patch.object(world, 'line_clear', return_value=True) as line_clear:
            edge = shading.surface(FIRE, 3.86, 4, 2, (1, 0, 0), 2, emission=0.45)
            core = shading.surface(FIRE, 3.86, 4, 2, (1, 0, 0), 2, emission=0.95)
        self.assertGreaterEqual(core.level - edge.level, 5)
        line_clear.assert_not_called()


if __name__ == '__main__':
    unittest.main()

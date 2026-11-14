"""Shared lighting preserves semantic materials, exact hiding and plain text."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import CombatState, Enemy, Fireball
from ascii3d.player import Player
from ascii3d.presentation import StyledFrame
from ascii3d.renderer import Renderer
from ascii3d.shading import Shading, ink
from ascii3d.surfaces import SolidBox
from ascii3d.world import FLOOR, LEAVES, METAL, STONE, WATER, WOOD, Tree, World


class SharedShadingTests(unittest.TestCase):
    @staticmethod
    def world():
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        return world

    def test_normal_and_distance_control_luminance_at_identical_material_sample(self):
        shading = Shading()
        normal = (-0.38, -0.48, 0.79)
        length = math.sqrt(sum(value * value for value in normal))
        normal = tuple(value / length for value in normal)
        toward = shading.surface(STONE, 1.23, 2.34, 3.45, normal, 1)
        away = shading.surface(STONE, 1.23, 2.34, 3.45, tuple(-v for v in normal), 1)
        levels = [shading.surface(STONE, 1.23, 2.34, 3.45, normal, distance).level
                  for distance in (0, 3, 12, 24, 48)]
        self.assertGreater(toward.level, away.level)
        self.assertEqual(levels, sorted(levels, reverse=True))
        self.assertGreater(levels[0], levels[-1])
        self.assertTrue(all(1 <= level <= 15 for level in levels))

    def test_same_literal_glyph_preserves_distinct_material_and_luminance(self):
        shading = Shading()
        for material in (STONE, FLOOR, METAL, WOOD, LEAVES, WATER):
            with self.subTest(material=material):
                token = shading.surface(material, 2.3, 4.1, 1.7, (0, 0, 1), 5, glyph='.')
                self.assertEqual(str(token), '.')
                self.assertEqual(token.material, material)
                self.assertTrue(0 <= token.level <= 15)
        self.assertIs(ink('.', 4, STONE), ink('.', 4, STONE))
        self.assertEqual(ink('.', -100, STONE).level, 0)
        self.assertEqual(ink('.', 100, STONE).level, 15)

    def test_repeated_pose_and_simulation_time_match_glyphs_and_style_buffers(self):
        world = self.world()
        world.trees[10, 9] = Tree(10.5, 9.5, seed=7)
        world.combat.fireballs.append(Fireball(8.5, 8.5, 2.5, (0, 1, 0)))
        renderer = Renderer(world)
        self.addCleanup(renderer.close)
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2, pitch=-0.1)
        first = renderer.styled_frame(player, 60, 24, time_seconds=2.75)
        expected_rows, expected_styles = first.rows[:], [row[:] for row in first.styles]
        second = renderer.styled_frame(player, 60, 24, time_seconds=2.75)
        self.assertEqual(second.rows, expected_rows)
        self.assertEqual(second.styles, expected_styles)
        self.assertGreater(len(set(value for row in second.styles for value in row)), 3)

    def test_styled_frame_dimensions_and_plain_snapshot_remain_independent_of_ansi(self):
        renderer = Renderer(self.world())
        self.addCleanup(renderer.close)
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2, pitch=-0.2)
        for width, height in ((60, 20), (120, 40), (160, 50)):
            with self.subTest(size=(width, height)):
                styled = renderer.styled_frame(player, width, height, time_seconds=1)
                self.assertIsInstance(styled, StyledFrame)
                self.assertEqual((styled.width, styled.height), (width, height))
                self.assertTrue(all(len(row) == width for row in styled.rows))
                self.assertTrue(all(len(row) == width for row in styled.styles))
                plain = renderer.frame(player, width, height, time_seconds=1)
                self.assertEqual(plain, styled.rows)
                self.assertNotIn('\x1b', '\n'.join(plain))
                self.assertTrue(any('\x1b' in row for row in styled.ansi_rows()))
                self.assertEqual(renderer.styled_frame(player, width, height, color_mode='mono',
                                                       time_seconds=1), plain)

    def test_even_blank_dark_surfaces_write_depth_and_hide_enemy_behind_wall(self):
        world = self.world()
        world.box(0, 6, 1, 24, 7, 10, STONE)
        world.combat = CombatState(enemies=[Enemy('Hidden guardian', 8.5, 8.5)])
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        renderer = Renderer(world)
        self.addCleanup(renderer.close)
        depths = []

        def capture(pixels, buffer, *args):
            depths.append([row[:] for row in buffer])

        with patch.object(renderer.shading, 'surface', return_value=ink(' ', 0, STONE)), \
                patch.object(renderer.scenery, 'draw', side_effect=capture):
            hidden = renderer.scene(player, 61, 21)
            world.combat.enemies.clear()
            empty = renderer.scene(player, 61, 21)
        self.assertEqual(hidden, empty)
        self.assertEqual(hidden[10][30], ' ')
        self.assertAlmostEqual(depths[0][10][30], 1.5)
        self.assertEqual(depths[0], depths[1])

    def test_fireball_behind_wall_cannot_illuminate_a_front_surface(self):
        world = self.world()
        world.box(3, 0, 1, 4, 24, 10, STONE)
        player = Player(x=2, y=2)
        shading = Shading(world)
        shading.prepare(player)
        sample = (STONE, 2.0, 2.0, 2.0, (1, 0, 0), 2)
        unlit = shading.surface(*sample)
        world.combat.fireballs.append(Fireball(5, 2, 2, (0, 1, 0)))
        shading.prepare(player)
        blocked = shading.surface(*sample)
        self.assertEqual((blocked, blocked.level), (unlit, unlit.level))
        world.box(3, 0, 1, 4, 24, 10, 0)
        shading.prepare(player)
        self.assertGreater(shading.surface(*sample).level, blocked.level)

    def test_visibility_cache_cannot_share_clearance_across_different_surface_rays(self):
        world = self.world()
        world.add_solid(SolidBox(3, 1.5, 2.7, 3.1, 2.8, 2.85, STONE))
        world.combat.fireballs.append(Fireball(4, 2.1, 4, (0, 1, 0)))
        shading = Shading(world)
        player = Player(x=2, y=2)
        shading.prepare(player)
        shading.surface(STONE, 2.1, 2.1, 2, (0, 0, 1), 2)
        cached = shading.surface(STONE, 2.4, 2.1, 2, (0, 0, 1), 2)
        shading.prepare(player)
        isolated = shading.surface(STONE, 2.4, 2.1, 2, (0, 0, 1), 2)
        self.assertEqual((cached, cached.level), (isolated, isolated.level))

    def test_light_and_visibility_work_remain_bounded(self):
        world = self.world()
        world.combat.fireballs = [Fireball(4 + index * 0.1, 2, 3, (0, 1, 0)) for index in range(8)]
        shading = Shading(world)
        shading.prepare(Player(x=2, y=2))
        self.assertLessEqual(len(shading.lights), shading.MAX_LIGHTS)
        with patch.object(world, 'line_clear', return_value=True) as line_clear:
            for index in range(400):
                shading.surface(STONE, 1 + index * 0.01, 2, 1, (0, 0, 1), 2)
        self.assertLessEqual(line_clear.call_count, shading.MAX_SHADOW_SAMPLES)


if __name__ == '__main__':
    unittest.main()

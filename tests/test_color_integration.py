"""Color changes presentation without changing gameplay visibility or sizing."""

import unittest
from unittest.mock import patch

from ascii3d.combat import Fireball
from ascii3d.palette import (GRASS, LEAVES, STONE, WATER, UI_ACCENT, UI_DANGER,
                             UI_POSITIVE, WATER_CREST, WIND_GRASS, WIND_LEAVES, color_rgb)
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.shading import Shading
from ascii3d.world import Tree, World


class ColorIntegrationTests(unittest.TestCase):
    def world(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, GRASS)
        world.box(3, 8, 1, 20, 9, 7, STONE)
        world.box(1, 15, 0, 23, 19, 1, WATER)
        world.trees[5, 6] = Tree(5.5, 6.5, seed=7)
        return world

    def test_modes_share_glyphs_and_buffers_while_color_changes_foregrounds(self):
        renderer = Renderer(self.world())
        self.addCleanup(renderer.close)
        player = Player(x=12.5, y=4.5, pitch=-0.1)
        color = renderer.styled_frame(player, 80, 30, time_seconds=2)
        gray = renderer.styled_frame(player, 80, 30, time_seconds=2, color_mode='gray')
        self.assertEqual(color.color_mode, 'color')
        self.assertEqual(color.rows, gray.rows)
        self.assertEqual(color.styles, gray.styles)
        self.assertEqual(color.materials, gray.materials)
        self.assertEqual(color.effects, gray.effects)
        self.assertNotEqual(color.ansi_rows(), gray.ansi_rows())
        self.assertEqual(renderer.styled_frame(player, 80, 30, color_mode='mono', time_seconds=2), color.rows)
        self.assertNotIn('\x1b', '\n'.join(renderer.frame(player, 80, 30)))

    def test_fog_tracks_distance_separately_from_material_and_luminance(self):
        shading = Shading()
        near = shading.surface(GRASS, 4, 5, 1, (0, 0, 1), 2)
        far = shading.surface(GRASS, 4, 5, 1, (0, 0, 1), 42)
        self.assertEqual(near.material, far.material)
        self.assertEqual(near.effects >> 2, 0)
        self.assertEqual(far.effects >> 2, 3)
        self.assertGreater(near.level, far.level)
        self.assertNotEqual(color_rgb(GRASS, 8, near.effects), color_rgb(GRASS, 8, far.effects))

    def test_grass_and_crowns_take_their_color_from_the_local_wind(self):
        world = World.empty(32, 32, 16)
        world.outdoor_bounds = (0, 0, 32, 32)
        world.box(0, 0, 0, 32, 32, 1, GRASS)
        world.trees[14, 12] = Tree(14.5, 12.5)
        renderer = Renderer(world, particles=False)
        self.addCleanup(renderer.close)
        player = Player(x=14.5, y=4.5)
        for wind, grass, leaves, absent in (((0, 0), GRASS, LEAVES, WIND_LEAVES),
                                            ((1, 0), WIND_GRASS, WIND_LEAVES, LEAVES)):
            with self.subTest(wind=wind), patch.object(renderer.scenery, 'wind_at', return_value=wind):
                pixels = renderer.scene(player, 90, 32, time_seconds=0.8)
                materials = {getattr(cell, 'material', None) for row in pixels for cell in row}
                self.assertIn(grass, materials)
                self.assertIn(leaves, materials)
                self.assertNotIn(absent, materials)
                # Both the detailed strokes and the distant ground take the gust.
                self.assertTrue(any(cell in "/\\|" and getattr(cell, 'material', None) == grass
                                    for row in pixels for cell in row))
                self.assertTrue(any(cell in ".,;\"'" and getattr(cell, 'material', None) == grass
                                    for row in pixels for cell in row))

    def test_river_color_rides_the_crests_and_repeats_at_frozen_time(self):
        world = World.empty(48, 48, 8)
        world.box(0, 0, 0, 48, 48, 1, WATER)
        renderer = Renderer(world, particles=False)
        self.addCleanup(renderer.close)
        player = Player(x=20.5, y=8.5, pitch=-0.35)
        start = renderer.styled_frame(player, 80, 30, time_seconds=0.5)
        moving = renderer.styled_frame(player, 80, 30, time_seconds=1.5)
        frozen = renderer.styled_frame(player, 80, 30, time_seconds=0.5)
        self.assertEqual(start.ansi_rows(), frozen.ansi_rows())
        swapped = sum({a, b} == {WATER, WATER_CREST} for row, other in
                      zip(start.materials, moving.materials) for a, b in zip(row, other))
        self.assertGreater(swapped, 30)
        self.assertEqual(start.effects, moving.effects)
        self.assertNotEqual(start.styles, moving.styles)

        def glints(frame):
            return {(x, y) for y, row in enumerate(frame.rows) for x, glyph in enumerate(row)
                    if glyph == '+' and frame.materials[y][x] == WATER_CREST
                    and frame.styles[y][x] == 15}

        # Bright points remain a small part of the water and travel with it.
        bright = glints(start)
        self.assertTrue(bright)
        next_bright = glints(moving)
        for points in (bright, next_bright):
            self.assertLessEqual(len(points), 4)
            self.assertTrue(all(abs(x - xx) > 2 or abs(y - yy) > 1
                                for x, y in points for xx, yy in points if (x, y) != (xx, yy)))
        self.assertNotEqual(bright, next_bright)
        # A roof and west wall remove the glints without hiding the river.
        world.box(0, 0, 4, 48, 48, 5, STONE)
        world.box(0, 0, 1, 1, 48, 4, STONE)
        sheltered = renderer.styled_frame(player, 80, 30, time_seconds=0.5)
        self.assertTrue(any(WATER_CREST in row for row in sheltered.materials))
        self.assertFalse(bright & glints(sheltered))

    def test_only_visible_fire_tints_a_surface_and_coincident_offset_is_safe(self):
        world = World.empty(12, 12, 8)
        world.combat.fireballs = [Fireball(4, 2, 2, (0, 1, 0))]
        shading = Shading(world)
        shading.prepare(Player(x=2, y=2))
        sample = (STONE, 2, 2, 2, (1, 0, 0), 2)
        lit = shading.surface(*sample)
        self.assertGreater(lit.effects & 3, 0)
        world.box(3, 0, 0, 4, 12, 8, STONE)
        shading.prepare(Player(x=2, y=2))
        blocked = shading.surface(*sample)
        self.assertEqual(blocked.effects & 3, 0)
        self.assertLess(blocked.level, lit.level)
        shading.lights = ((2., 2., 2.),)
        shading._visibility.clear()
        token = shading.surface(STONE, 1.985, 2., 2., (1, 0, 0), 1)
        self.assertGreater(token.effects & 3, 0)

    def test_ui_health_and_map_retain_semantics_through_resizes_and_pause(self):
        renderer = Renderer(self.world())
        self.addCleanup(renderer.close)
        player = Player(x=12.5, y=4.5)
        for width, height in ((60, 20), (120, 40), (160, 50), (59, 19), (60, 20)):
            with self.subTest(size=(width, height)):
                frame = renderer.styled_frame(player, width, height, show_map=True)
                self.assertTrue(all(len(row) == width for row in frame.rows))
                self.assertTrue(all(len(row) == width for row in frame.materials))
                self.assertTrue(all(len(row) == width for row in frame.effects))
                if width >= 60 and height >= 20:
                    self.assertIn(UI_POSITIVE, frame.materials[0])
                    self.assertTrue(any(UI_ACCENT in row for row in frame.materials[2:-3]))
                    first = frame
                    second = renderer.styled_frame(player, width, height, show_map=True)
                    self.assertEqual(first.materials, second.materials)
                    self.assertEqual(first.effects, second.effects)
        player.hp = 2
        danger = renderer.styled_frame(player, 60, 20, paused=True)
        self.assertIn(UI_DANGER, danger.materials[0])
        self.assertTrue(all(row.endswith('\x1b[97;40m') for row in danger.ansi_rows()))


if __name__ == '__main__':
    unittest.main()

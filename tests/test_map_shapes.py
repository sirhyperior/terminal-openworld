"""Local charts sample real footprints and retain oblique roads and edges."""

import math
import unittest
from unittest.mock import patch

from ascii3d.palette import UI_ACCENT
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.roads import RoadNetwork
from ascii3d.shading import Ink
from ascii3d.surfaces import ConvexSolid
from ascii3d.world import GRASS, LEAVES, PATH, STONE, WATER, Tree, World


BOX_FACES = ((0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7))


class MapShapeTests(unittest.TestCase):
    def world(self, size=64):
        world = World.empty(size, size, 12)
        world.box(0, 0, 0, size, size, 1, GRASS)
        return world

    @staticmethod
    def draw(renderer, player=None, width=120, height=35):
        pixels = [[' '] * width for _ in range(height)]
        renderer._map(pixels, player or Player(x=32, y=32))
        return pixels

    def test_continuous_roads_use_both_diagonal_strokes_and_path_material(self):
        for route, glyph in ((((8, 8), (56, 56)), '/'),
                             (((8, 56), (56, 8)), '\\')):
            with self.subTest(route=route):
                world = self.world()
                roads = RoadNetwork((route,), width=2)
                # This isolates the map's point-sampling contract from the
                # road-to-ground integration tested with the road network.
                with patch.object(world, 'surface_material',
                                  side_effect=lambda x, y: roads.material_at(x, y, GRASS)):
                    renderer = Renderer(world)
                    self.draw(renderer)
                path = [cell for row in renderer._map_rows for cell in row
                        if isinstance(cell, Ink) and cell.material == PATH]
                self.assertGreater(sum(cell == glyph for cell in path), 4)
                self.assertFalse(any(cell == '#' for cell in path))

    def test_real_rotated_solid_keeps_sloping_boundary_and_clear_aabb_corners(self):
        world = self.world()
        angle = math.pi / 4
        vertices = []
        for z in (1, 5):
            for x, y in ((-12, -5), (12, -5), (12, 5), (-12, 5)):
                vertices.append((32 + x * math.cos(angle) - y * math.sin(angle),
                                 32 + x * math.sin(angle) + y * math.cos(angle), z))
        solid = world.add_solid(ConvexSolid(tuple(vertices), BOX_FACES, STONE))
        renderer = Renderer(world)
        self.draw(renderer)
        masonry = [cell for row in renderer._map_rows for cell in row
                   if isinstance(cell, Ink) and cell.material == STONE]
        self.assertTrue(any(cell == '#' for cell in masonry))
        self.assertGreater(sum(cell in ('/', '\\') for cell in masonry), 3)
        self.assertEqual(world.surface_material(solid.x0 + 0.1, solid.y0 + 0.1), GRASS)
        # A whole AABB would cover roughly113 chart cells at this scale;
        # the true tilted rectangle occupies fewer than80 including its edge.
        self.assertLess(len(masonry), 80)

    def test_fixed_fractional_sampling_cache_marker_and_edits_stay_bounded(self):
        world = self.world(512)
        renderer = Renderer(world)
        player = Player(x=256.5, y=256.5)
        with patch.object(world, 'surface_height', wraps=world.surface_height) as sample:
            first = self.draw(renderer, player)
            calls = sample.call_count
            self.assertGreater(calls, 0)
            self.assertLessEqual(calls, 43 * 22 * 9)
            self.assertTrue(any(not float(call.args[0]).is_integer()
                                or not float(call.args[1]).is_integer()
                                for call in sample.call_args_list))
            player.x += 5
            player.yaw += math.pi / 2
            second = self.draw(renderer, player)
            self.assertNotEqual(first, second)
            self.assertEqual(sample.call_count, calls)
            markers = [cell for row in second for cell in row
                       if isinstance(cell, Ink) and cell.material == UI_ACCENT]
            self.assertEqual(len(markers), 1)
            world.box(240, 240, 0, 248, 248, 1, WATER)
            self.draw(renderer, player)
            self.assertGreater(sample.call_count, calls)
            self.assertTrue(any(isinstance(cell, Ink) and cell.material == WATER and cell == '~'
                                for row in renderer._map_rows for cell in row))

    def test_tree_symbol_is_distinct_from_masonry_and_small_views_stay_in_bounds(self):
        world = self.world()
        world.trees[20, 20] = Tree(20.5, 20.5)
        renderer = Renderer(world)
        for width, height in ((60, 20), (120, 35), (160, 50)):
            pixels = self.draw(renderer, width=width, height=height)
            self.assertEqual(len(pixels), height)
            self.assertTrue(all(len(row) == width for row in pixels))
            trees = [cell for row in renderer._map_rows for cell in row
                     if isinstance(cell, Ink) and cell.material == LEAVES]
            self.assertEqual(len(trees), 1)
            self.assertEqual(trees[0], '*')


if __name__ == '__main__':
    unittest.main()

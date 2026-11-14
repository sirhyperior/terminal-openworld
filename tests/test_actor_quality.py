"""Per-character material shading retains exact opaque raster coverage."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import CombatState, Enemy, Fireball, WeaponPickup, WARDEN_BEHAVIOR
from ascii3d.combat_render import _quad, _surface_brush, draw_combat
from ascii3d.geometry import Camera
from ascii3d.palette import FIRE, STRAW
from ascii3d.player import Player
from ascii3d.shading import Ink, Shading, ink
from ascii3d.world import FLOOR, METAL, STONE, World


class ActorQualityTests(unittest.TestCase):
    def camera(self, width=100, height=40):
        camera = Camera(Player(x=8.5, y=4.5), width, height, width * 0.58, 0.5)
        camera.shading = Shading()
        return camera

    @staticmethod
    def buffers(width, height, foreground=False):
        return ([["~"] * width for _ in range(height)],
                [[0.3 if foreground and (x + y) % 5 == 0 else math.inf
                  for x in range(width)] for y in range(height)])

    def test_world_point_reprojects_to_the_exact_sample_at_pitch_and_yaw(self):
        camera = Camera(Player(x=4.2, y=7.1, z=2.3, yaw=0.81, pitch=-0.32), 81, 47, 43, 0.5)
        for x, y, depth in ((0, 0, 0.3), (40, 23, 8.2), (80, 46, 45), (11, 35, 3.1)):
            with self.subTest(sample=(x, y, depth)):
                px, py, actual_depth = camera.project(*camera.world_point(x, y, depth))
                self.assertAlmostEqual(px, x, places=11)
                self.assertAlmostEqual(py, y, places=11)
                self.assertAlmostEqual(actual_depth, depth, places=11)

    def test_shader_changes_only_glyphs_not_depth_coverage_and_skips_hidden_cells(self):
        camera = self.camera(60, 30)
        vertices = tuple(camera.project(*point) for point in
                         ((5, 8, 1), (12, 8, 1), (12, 8, 4), (5, 8, 4)))
        for primitive in ('triangle', 'quad'):
            with self.subTest(primitive=primitive):
                ordinary, reference = self.buffers(60, 30, True)
                shaded, depths = self.buffers(60, 30, True)
                calls = []

                def shader(x, y, z, depth):
                    px, py, actual = camera.project(x, y, z)
                    self.assertAlmostEqual(actual, depth, places=10)
                    self.assertGreater(reference[round(py)][round(px)], 0.3)
                    calls.append((px, py, depth))
                    return ink('.', 4, STONE)

                points = vertices[:3] if primitive == 'triangle' else vertices
                getattr(camera, primitive)(ordinary, reference, *points, '#')
                getattr(camera, primitive)(shaded, depths, *points, '#', shader=shader)
                self.assertEqual(depths, reference)
                self.assertEqual(len(calls), sum(char != '~' for row in ordinary for char in row))
                self.assertTrue(all(char == '~' or isinstance(char, Ink) for row in shaded for char in row))

    def test_stroke_shader_preserves_clipped_radius_depths(self):
        camera = self.camera(60, 30)
        for radius in (0, 0.1):
            with self.subTest(radius=radius):
                ordinary, reference = self.buffers(60, 30, True)
                shaded, depths = self.buffers(60, 30, True)
                a, b = (6, 4.4, 1.8), (10, 12, 3.7)
                camera.stroke_world(ordinary, reference, a, b, radius, '/')
                camera.stroke_world(shaded, depths, a, b, radius, '/',
                                    shader=lambda x, y, z, d: ink('/', min(15, int(d)), METAL))
                self.assertEqual(depths, reference)
                self.assertEqual([[char != '~' for char in row] for row in ordinary],
                                 [[char != '~' for char in row] for row in shaded])

    def test_one_flat_face_contains_many_distinct_tones_and_keeps_material(self):
        camera = self.camera()
        vertices = ((5, 9, 1), (12, 9, 1), (12, 9, 5), (5, 9, 5))
        for material in (STONE, METAL, STRAW):
            with self.subTest(material=material):
                pixels, depths = self.buffers(100, 40)
                _quad(camera, pixels, depths, *vertices, '#', material=material)
                tokens = [char for row in pixels for char in row if isinstance(char, Ink)]
                levels = {char.level for char in tokens}
                self.assertGreater(len(tokens), 100)
                self.assertGreaterEqual(len(levels), 4)
                self.assertGreaterEqual(max(levels) - min(levels), 5)
                self.assertEqual({char.material for char in tokens}, {material})

    def test_surface_texture_moves_with_its_face(self):
        camera = self.camera()

        class LocalTexture:
            def surface(self, material, x, y, z, normal, distance, **options):
                u, v, _ = options['texture_position']
                self.assert_local_normal(options['texture_normal'])
                return ink('.', int(round(u * 3 + v * 2)) % 14 + 1, material)

            @staticmethod
            def assert_local_normal(normal):
                if normal != (0, 0, 1):
                    raise AssertionError(normal)

        camera.shading = LocalTexture()
        vertices = ((5, 9, 1), (12, 9, 1), (12, 9, 5), (5, 9, 5))
        delta = (13, -7, 5)
        moved = tuple(tuple(p[i] + delta[i] for i in range(3)) for p in vertices)
        first = _surface_brush(camera, vertices, (0, -1, 0), STONE, 0)
        second = _surface_brush(camera, moved, (0, -1, 0), STONE, 0)
        for point in ((6.12, 9, 2.17), (8.31, 9, 3.34), (11.23, 9, 4.18)):
            a = first(*point, 5)
            b = second(*(point[i] + delta[i] for i in range(3)), 5)
            self.assertEqual((a, a.level, a.material), (b, b.level, b.material))

    def test_chamfered_warden_remains_opaque_and_has_lit_and_dark_body_detail(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        enemy = Enemy('Stone knight', 8.5, 8.5, radius=0.44, height=2.15,
                      behavior=WARDEN_BEHAVIOR, territory=(1, 1, 23, 23))
        combat = CombatState(enemies=[enemy])
        all_levels = set()
        for x, y, yaw in ((8.5, 6, math.pi / 2), (11, 8.5, math.pi),
                          (8.5, 11, -math.pi / 2), (6, 8.5, 0)):
            with self.subTest(yaw=yaw):
                player = Player(x=x, y=y, yaw=yaw)
                pixels, depths = self.buffers(120, 40)
                draw_combat(combat, world, pixels, depths, player, 69, 0.5, 2, labels=False)
                tokens = [char for row in pixels for char in row if isinstance(char, Ink)]
                self.assertGreater(len(tokens), 50)
                self.assertEqual({char.material for char in tokens}, {STONE})
                levels = {char.level for char in tokens}
                all_levels.update(levels)
                # Moonlit shoulder/helmet bevels remain distinct from carved
                # vertical faces, including the shadow-facing back view.
                self.assertGreaterEqual(max(levels) - min(levels), 6)
                cam = Camera(player, 120, 40, 69, 0.5)
                px, py, _ = cam.project(enemy.x, enemy.y, enemy.z + 1.2)
                self.assertIsInstance(pixels[round(py)][round(px)], Ink)
                self.assertLess(depths[round(py)][round(px)], math.inf)
        self.assertGreaterEqual(max(all_levels) - min(all_levels), 8)

    def test_depth_only_pass_keeps_identical_geometry_without_material_work(self):
        world = World.empty(24, 24, 12)
        enemy = Enemy('Stone knight', 8.5, 8.5, radius=0.44, height=2.15,
                      behavior=WARDEN_BEHAVIOR, territory=(1, 1, 23, 23))
        combat = CombatState(enemies=[enemy], pickups=[WeaponPickup(7, 7)],
                             fireballs=[Fireball(9, 7, 2, (1, 0, 0))])
        player = Player(x=8.5, y=6, pitch=-0.1)
        ordinary, reference = self.buffers(120, 40)
        prepass, depths = self.buffers(120, 40)
        original = Shading.surface
        with patch.object(Shading, 'surface', autospec=True,
                          side_effect=lambda shader, *args, **kwargs: original(shader, *args, **kwargs)) as shade:
            draw_combat(combat, world, ordinary, reference, player, 69, 0.5, 2, labels=False)
            normal_calls = shade.call_count
            shade.reset_mock()
            draw_combat(combat, world, prepass, depths, player, 69, 0.5, 2,
                        labels=False, depth_only=True)
            self.assertEqual(shade.call_count, 0)
        self.assertGreater(normal_calls, 100)
        self.assertEqual(depths, reference)


if __name__ == '__main__':
    unittest.main()

"""Exact C solid queries and the optional backend's Python fallback."""

import math
import os
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import Mock, patch

from ascii3d import native_solids
from ascii3d.native_solids import NativeSolidTree, SolidLibrary
from ascii3d.orientation import rotate_solid
from ascii3d.renderer import Renderer
from ascii3d.surfaces import HeightField, SolidBox
from ascii3d.terrain import Landmark
from ascii3d.world import FLOOR, STONE, World


BOUNDS = (0, 0, 64, 64)


class NativeSolidFallbackTests(unittest.TestCase):
    def test_missing_library_keeps_python_renderer_available(self):
        with patch.object(native_solids, 'CDLL', side_effect=OSError('library unavailable')):
            renderer = Renderer(World.empty(16, 16, 8), backend='native')
        self.assertEqual(renderer.backend_name, 'cpu')
        self.assertIn('library unavailable', renderer.backend_error)
        self.assertIsNone(renderer.solid_library)

    def test_incompatible_abi_is_rejected_before_trace_is_loaded(self):
        incompatible = Mock(spec=['monolith_solid_abi'])
        incompatible.monolith_solid_abi.return_value = 2
        with patch.object(native_solids, 'CDLL', return_value=incompatible):
            with self.assertRaisesRegex(OSError, 'Unsupported MONOLITH solid library ABI'):
                SolidLibrary('wrong-version')

    def test_custom_ray_hit_stays_on_python_path(self):
        class PassThrough(SolidBox):
            def ray_hit(self, origin, direction, limit):
                return None

        world = World.empty(64, 64, 16)
        for y in range(12, 21):
            world.add_solid(SolidBox(8, y, 2, 9, y + 1, 4, FLOOR))
        world.add_solid(PassThrough(4, 8, 2, 6, 9, 4, STONE))
        back = world.add_solid(SolidBox(12, 8, 2, 13, 9, 4, FLOOR))
        library = Mock()
        origin, direction, limit = (2, 8.5, 3), (1, 0, 0), 32
        expected = back.ray_hit(origin, direction, limit)
        for _ in range(2):
            query = world.geometry_query(BOUNDS, (), solid_library=library)
            self.assertEqual(query(origin, direction, limit), expected)
        library.trace.assert_not_called()

    def test_material_outside_native_range_stays_exact(self):
        world = World.empty(64, 64, 16)
        for y in range(12, 21):
            world.add_solid(SolidBox(8, y, 2, 9, y + 1, 4, FLOOR))
        wall = world.add_solid(SolidBox(4, 8, 2, 6, 9, 4, (1 << 31) + 11))
        library = Mock()
        query = world.geometry_query(BOUNDS, (), solid_library=library)
        origin, direction, limit = (2, 8.5, 3), (1, 0, 0), 32
        self.assertEqual(query(origin, direction, limit), wall.ray_hit(origin, direction, limit))
        library.trace.assert_not_called()


class NativeSolidQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suffix = '.dll' if os.name == 'nt' else '.dylib' if sys.platform == 'darwin' else '.so'
        path = Path(native_solids.__file__).with_name('monolith_solid_bvh' + suffix)
        if not path.is_file():
            raise unittest.SkipTest('optional native solid library has not been built')
        cls.library = SolidLibrary(path)

    @staticmethod
    def fixture():
        world = World.empty(64, 64, 24)
        landmark = Landmark('TEST', (4, 4, 32, 32), 1, math.radians(17))
        for z in (2, 8, 12):
            for x in (8, 16, 24):
                for y in (8, 16, 24):
                    box = SolidBox(x, y, z, x + 3, y + 3, z + 2, STONE)
                    world.add_solid(rotate_solid(box, landmark) if x != 16 else box)
            world.add_solid(SolidBox(6, 6, z, 28, 28, z + 0.4, STONE))
            world.add_solid(SolidBox(6, 6, z, 28, 28, z + 0.4, FLOOR))
        return world

    def test_native_tree_matches_python_on_boundary_and_shifted_rays(self):
        world = self.fixture()
        world.geometry_query(BOUNDS, ())
        tree = world._solid_query_cache[-1]
        native = NativeSolidTree(self.library, tree)
        cases = [((4, 6, 2), (1, 0, 0), 2), ((4, 6, 2), (1, 0, 0), 2 - 0.5e-10),
                 ((4, 6, 2), (1, 0, 0), 2 - 1.5e-10), ((6, 6, 2), (0, 0, 1), 48),
                 ((24.25, 8.125, 12.03125), (0.5e-12, -1e-12, 0), 48)]
        generator = random.Random(39281)
        cases.extend((tuple(generator.uniform(0, bound) for bound in (36, 36, 16)),
                      tuple(generator.uniform(-1.5, 1.5) for _ in range(3)),
                      generator.uniform(0, 48)) for _ in range(1500))
        tied_rays = 0
        for origin, direction, limit in cases:
            entry = tree[0].ray_entry(origin, direction, limit)
            if entry is None:
                continue
            expected, tied = world._solid_tree_hit(origin, direction, limit, tree, entry)
            with self.subTest(origin=origin, direction=direction, limit=limit):
                self.assertEqual(native.ray_hit(origin, direction, limit, entry), (expected, tied))
            tied_rays += tied
        self.assertGreater(tied_rays, 0)

    def test_world_query_uses_native_tree_and_preserves_grid_order_for_ties(self):
        world = self.fixture()
        origin, direction, limit = (4, 6, 2), (1, 0, 0), 32
        expected = world.geometry_query(BOUNDS, ())(origin, direction, limit)
        self.assertIsNotNone(expected)
        with patch.object(world, '_solid_tree_hit', side_effect=AssertionError('unused Python tree')), \
                patch.object(world, '_solid_hit', wraps=world._solid_hit) as grid:
            query = world.geometry_query(BOUNDS, (), solid_library=self.library)
            self.assertEqual(query(origin, direction, limit), expected)
            grid.assert_called_once()
            closest = world.add_solid(SolidBox(5, 5, 1, 5.5, 7, 4, STONE))
            changed = world.geometry_query(BOUNDS, (), solid_library=self.library)
            self.assertEqual(changed(origin, direction, limit), closest.ray_hit(origin, direction, limit))
            self.assertEqual(query(origin, direction, limit), expected)

    def test_fused_world_query_preserves_terrain_solid_merge_and_edits(self):
        if self.library.geometry_trace is None:
            self.skipTest('prebuilt library has no fused geometry kernel')
        world = World.empty(32, 32, 24)
        world.heightfield = HeightField(32, 32, [4.0] * 33 ** 2)
        for material in (STONE, FLOOR):
            world.add_solid(SolidBox(5, 5, 2, 8, 8, 4, material))
        shared_face = (6.5, 5.5, 7), (0, 0, -1), 12
        changed_ground = (3.5, 3.5, 7), (0, 0, -1), 12
        cases = [shared_face, changed_ground, (shared_face[0], shared_face[1], math.inf)]
        rng = random.Random(39281)
        cases.extend((tuple(rng.uniform(0, bound) for bound in (28, 28, 16)),
                      tuple(rng.uniform(-1.5, 1.5) for _ in range(3)),
                      rng.uniform(0, 48)) for _ in range(1000))

        for solid_count in (2, 11):
            with self.subTest(solids=solid_count):
                if solid_count == 11:
                    for x in range(15, 24):
                        world.add_solid(SolidBox(x, 8, 3, x + 0.8, 9, 6, STONE))
                with patch.object(self.library, 'geometry_trace', None):
                    control = world.geometry_query(BOUNDS, (), solid_library=self.library)
                fused = world.geometry_query(BOUNDS, (), solid_library=self.library)
                self.assertEqual([fused(*case) for case in cases], [control(*case) for case in cases])
                world.heightfield.paint_cell(3, 3, STONE)
                self.assertEqual(fused(*changed_ground).material, STONE)
                self.assertEqual(fused(*changed_ground), control(*changed_ground))


if __name__ == '__main__':
    unittest.main()

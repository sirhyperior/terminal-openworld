"""Compare exact native terrain rays and cache invalidation with Python."""

import math
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ascii3d import native_solids
from ascii3d.native_solids import NativeHeightField, SolidLibrary
from ascii3d.surfaces import HeightField
from ascii3d.world import AIR, GRASS, PATH


_SUFFIX = '.dll' if os.name == 'nt' else '.dylib' if sys.platform == 'darwin' else '.so'
_LIBRARY_PATH = Path(native_solids.__file__).with_name('monolith_solid_bvh' + _SUFFIX)


class NativeHeightFieldFallbackTests(unittest.TestCase):
    def test_legacy_library_retains_python_terrain_queries(self):
        field = HeightField(8, 8, [2.5] * 81)
        native = NativeHeightField(SimpleNamespace(heightfield_trace=None), field)
        with patch.object(field, 'ray_hit', wraps=field.ray_hit) as query:
            origin, direction = (3.5, 3.5, 5), (0, 0, -1)
            hit = native.ray_hit(origin, direction, 4, minimum=1.5)
            self.assertEqual(hit.distance, 2.5)
            query.assert_called_once_with(origin, direction, 4, minimum=1.5)

    def test_custom_heightfield_is_left_to_python(self):
        class CustomHeightField(HeightField):
            pass

        field = CustomHeightField(8, 8, [2.5] * 81)
        with self.assertRaisesRegex(TypeError, 'built-in heightfield'):
            NativeHeightField(SimpleNamespace(heightfield_trace=None), field)


class NativeHeightFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _LIBRARY_PATH.is_file():
            raise unittest.SkipTest('optional native solid library has not been built')
        cls.library = SolidLibrary(_LIBRARY_PATH)
        if cls.library.heightfield_trace is None:
            raise unittest.SkipTest('prebuilt library has no native heightfield kernel')

    def compare(self, field, cases):
        native = NativeHeightField(self.library, field)
        expected = [field.ray_hit(origin, direction, limit, minimum=minimum)
                    for origin, direction, limit, minimum in cases]
        self.assertGreater(sum(hit is not None for hit in expected), 0)
        self.assertIn(None, expected)
        with patch.object(field, 'ray_hit', side_effect=AssertionError('unexpected Python fallback')):
            for case, hit in zip(cases, expected):
                origin, direction, limit, minimum = case
                with self.subTest(ray=case):
                    actual = native.ray_hit(origin, direction, limit, minimum=minimum)
                    self.assertEqual(actual, hit)
                    if hit is not None:
                        self.assertEqual(actual.distance.hex(), hit.distance.hex())
                        self.assertEqual(tuple(value.hex() for value in actual.normal),
                                         tuple(value.hex() for value in hit.normal))

    def test_matches_python_on_seeded_origins_directions_and_clipping(self):
        field = HeightField(19, 17, [3 + math.sin(x * 0.7) * math.cos(y * 0.3)
                                     for y in range(18) for x in range(20)])
        field.edit_box(7, 3, 0, 10, 9, 8, AIR)
        field.paint_cell(15, 8, PATH)
        rng = random.Random(7921)
        cases = [((8, 8, 7), (0, 0, -1), 8, 0), ((16, 8, 7), (0, 0, -1), 8, 0),
                 ((8, 8, 7), (1e-12, -1e-12, -1), 8, 0), ((19, 17, 7), (-1, -1, -1), 8, 0),
                 ((3.5, 3.5, 0), (0, 0, 0), 1, 0), ((1, 1, 8), (0, 0, 1), 3, 0)]
        for _ in range(3000):
            origin = tuple(rng.uniform(-2, bound) for bound in (21, 19, 9))
            direction = tuple(rng.uniform(-2, 2) for _ in range(3))
            limit = rng.uniform(0, 32)
            cases.append((origin, direction, limit, rng.uniform(0, limit + 0.1)))
        self.compare(field, cases)

    def test_retains_chunk_corners_and_near_parallel_endpoint(self):
        flat = HeightField(18, 18, [2.5] * 361)
        self.compare(flat, [((7, 7, 5), (1, 1, -1), 4, 2.4), ((9, 9, 5), (-1, -1, -1), 4, 2.5),
                            ((-2, 8, 5), (2, 0, -0.5), 5, 0), ((18, 9, 5), (-2, 0, -0.5), 5, 0),
                            ((8, 8, 5), (0, 0, -1), 2.2, 0)])

        slope = HeightField(19, 17, [4 + 0.25 * x - 0.125 * y
                                     for y in range(18) for x in range(20)])
        dz = 0.1875 - 2 ** -18
        origin, direction = (6, 7, 5 - 2 * dz), (1, 0.5, dz)
        halo = 2 ** -30
        self.compare(slope, [(origin, direction, limit, minimum)
                             for minimum in (0, 2 - halo, 2, 2 + halo)
                             for limit in (2 - halo, 2, 2 + halo, 2.1)])

    def test_repaint_and_cut_refresh_live_materials_and_envelopes(self):
        heights = [2.0] * 324
        heights[5 * 18 + 6] = 8.0
        field = HeightField(17, 17, heights)
        native = NativeHeightField(self.library, field)
        origin, direction = (5.9, 4.9, 10), (0, 0, -1)
        self.assertEqual(native.ray_hit(origin, direction, 12).material, GRASS)
        field.paint_cell(5, 4, PATH)
        self.assertEqual(native.ray_hit(origin, direction, 12).material, PATH)
        field.edit_box(5, 4, 0, 6, 5, 9, AIR)
        self.assertIsNone(native.ray_hit(origin, direction, 12))
        neighbor = (6.1, 5.1, 10)
        self.assertEqual(native.ray_hit(neighbor, direction, 12), field.ray_hit(neighbor, direction, 12))

    def test_unbounded_ray_uses_python_fallback(self):
        field = HeightField(8, 8, [2.5] * 81)
        native = NativeHeightField(self.library, field)
        origin, direction = (3.5, 3.5, 5), (0, 0, -1)
        expected = field.ray_hit(origin, direction, math.inf)
        with patch.object(field, 'ray_hit', wraps=field.ray_hit) as query:
            self.assertEqual(native.ray_hit(origin, direction, math.inf), expected)
            query.assert_called_once()


if __name__ == '__main__':
    unittest.main()

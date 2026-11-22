"""Native surface lighting and its shared Python fallback preserve styled frames."""

from array import array
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ascii3d.combat import Fireball
from ascii3d.native_shading import NativeShading
from ascii3d.native_solids import SolidLibrary
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.roads import RoadNetwork
from ascii3d.shading import RAMP, Shading
from ascii3d.world import AIR, GRASS, METAL, PATH, STONE, World


class NativeShadingCompatibilityTests(unittest.TestCase):
    def test_explicit_gpu_uses_available_surface_shader(self):
        def shade(inputs, results, count, *args):
            pass

        device = SimpleNamespace(_native_library=SimpleNamespace(shade_surfaces=shade), close=lambda: None)
        with patch('ascii3d.gpu_renderer.GPUBackend', return_value=device):
            renderer = Renderer(World.empty(8, 8, 4), backend='gpu')
        self.addCleanup(renderer.close)
        self.assertIs(renderer._native_shading._shade, shade)
        self.assertIsNone(renderer.solid_library)

    def test_legacy_kernel_falls_back_for_paths_but_keeps_other_native_results(self):
        def old_kernel(inputs, results, count, *args):
            for index in range(count):
                material = int(inputs[index * 9 + 7])
                results[index] = material << 16 | 7 << 8 | 3

        shading = Shading()
        shading.prepare(Player())
        position = (0.25, 0.30, 1.0)
        normal = (0.0, 0.0, 1.0)
        samples = array("d", [*position, *normal, 5, PATH, 0, *position, *normal, 5, STONE, 0])
        for name in ("monolith_shade_batch", "monolith_shade_cobble_batch"):
            with self.subTest(name=name):
                old_kernel.__name__ = name
                native = NativeShading(old_kernel)
                row = ["", ""]
                native.finish(shading, samples, [(row, 0), (row, 1)])
                self.assertIs(row[0], shading.surface(PATH, *position, normal, 5))
                self.assertEqual(row[1], RAMP[3])
                self.assertEqual(row[1].level, 7)


class NativeShadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            library = SolidLibrary()
        except (AttributeError, OSError):
            raise unittest.SkipTest("optional native solid library has not been built")
        if library.shade_surfaces is None:
            raise unittest.SkipTest("prebuilt library has no native shading kernel")
        cls.shade = library.shade_surfaces

    def test_matches_python_with_cobbles_grass_metal_an_edited_shadow_and_firelight(self):
        world = World.empty(24, 24, 10)
        world.outdoor_bounds = (0, 0, 24, 24)
        world.box(0, 0, 0, 24, 24, 1, GRASS)
        world.roads = RoadNetwork((((11, 0), (11, 24)),))
        world.box(4, 10, 1, 18, 11, 5, STONE)
        world.box(9, 10, 1, 14, 11, 3, METAL)
        control, candidate = Renderer(world), Renderer(world)
        self.addCleanup(control.close)
        self.addCleanup(candidate.close)
        candidate._native_shading = shade = NativeShading(self.shade)
        player = Player(x=11.25, y=6.4, z=1, yaw=math.pi / 2, pitch=-0.12)

        def compare(seconds):
            expected = control.styled_frame(player, 68, 28, time_seconds=seconds)
            actual = candidate.styled_frame(player, 68, 28, time_seconds=seconds)
            self.assertGreater(sum(row.count(PATH) for row in actual.materials), 10)
            self.assertEqual(actual, expected)
            self.assertEqual(actual.ansi_rows(), expected.ansi_rows())

        with patch.object(shade, "finish", wraps=shade.finish) as batch:
            compare(0.8)
            batch.assert_called_once()
            self.assertTrue(batch.call_args.args[1])
            world.box(7, 10, 1, 9, 11, 5, AIR)
            compare(2.3)
            self.assertEqual(batch.call_count, 2)
            world.combat.fireballs.append(Fireball(11.25, 8.7, 2.3, (0, 1, 0)))
            compare(2.9)
            self.assertEqual(batch.call_count, 2)


if __name__ == "__main__":
    unittest.main()

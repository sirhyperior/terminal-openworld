"""Optional GPU candidates keep the CPU reference and expose precision errors."""

import importlib.util
import math
import os
import struct
import unittest
from unittest.mock import patch

from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.surfaces import HeightField, SolidBox
from ascii3d.world import FLOOR, GRASS, STONE, WATER, World
from tools.gpu_prototype import StaticGPU, camera_rays, decode, exact_static_hit, refine, voxel_data


class GPUReferenceTests(unittest.TestCase):
    @staticmethod
    def world():
        world = World.empty(17, 19, 12)
        world.box(0, 0, 0, 17, 19, 1, FLOOR)
        world.heightfield = HeightField(17, 19, [1.2 + 0.03 * x + 0.02 * y
                                                for y in range(20) for x in range(18)], material=GRASS)
        world.box(1, 9, 1, 16, 10, 6, STONE)
        world.box(1, 5, 0, 5, 9, 2, WATER)
        world.add_stair_flight(7, 5, 3, 4, 1.5, 3.5)
        return world

    def test_voxel_upload_preserves_one_material_per_shader_entry(self):
        packed = voxel_data(bytearray([0, 1, 5, 6, 10, 0, 3, 4]))
        self.assertEqual(list(packed), [0, 1, 5, 6, 10, 0, 3, 4])
        self.assertEqual(len(packed.tobytes()), 32)

    def test_flat_readback_preserves_all_three_candidate_records(self):
        record = (1.25, FLOOR, 1 | (2 << 8), 123, 2.5, GRASS, 2, 456, 3.75, STONE, 4, 789)
        self.assertEqual(decode(struct.pack('<f3If3If3I', *record)), [record])

    def test_independent_reference_matches_current_renderer_depths(self):
        world = self.world()
        player = Player(x=8.5, y=2.5, z=1.5, yaw=math.pi / 2, pitch=-0.25)
        renderer = Renderer(world)
        depths = []
        with patch.object(renderer.scenery, 'draw', side_effect=lambda pixels, rows, *rest: depths.extend(
                depth for row in rows for depth in row)):
            renderer.scene(player, 60, 20)
        for direction, expected in zip(camera_rays(player, 60, 20), depths):
            hit = exact_static_hit(world, (player.x, player.y, player.eye_z), direction)
            self.assertEqual(hit is not None, math.isfinite(expected))
            if hit is not None:
                self.assertAlmostEqual(hit[0], expected, places=7)

    def test_refinement_uses_exact_fractional_solid_and_rejects_wrong_triangles(self):
        world = self.world()
        world.add_solid(SolidBox(8, 4, 1.5, 9, 5, 2.125, FLOOR))
        candidate = (0.0, FLOOR, 4, len(world.solids) - 1, 2, 0, 0, 0)
        hit = refine(world, (8.5, 4.5, 4), (0, 0, -1), candidate)
        self.assertEqual(hit, (1.875, FLOOR, (0, 0, 1)))
        candidate = (0.0, GRASS, 2, 0, 2, 0, 0, 0)
        self.assertIsNone(refine(world, (8.5, 4.5, 4), (0, 0, -1), candidate))


@unittest.skipUnless(os.environ.get('MONOLITH_GPU_TESTS') == '1' and importlib.util.find_spec('wgpu'),
                     'optional hardware GPU test: install requirements-gpu.txt and set MONOLITH_GPU_TESTS=1')
class HardwareGPUPrototypeTests(unittest.TestCase):
    def test_hardware_readback_material_depth_and_static_edit_guard(self):
        world = GPUReferenceTests.world()
        gpu = StaticGPU(world)
        self.addCleanup(gpu.close)
        self.assertIn(gpu.adapter.info['adapter_type'], ('DiscreteGPU', 'IntegratedGPU'))
        for player in (Player(x=8.5, y=2.5, z=1.5, yaw=math.pi / 2, pitch=-0.25),
                       Player(x=3.5, y=6.5, z=0.12, yaw=0.4, pitch=-0.3)):
            for width, height in ((60, 20), (63, 27)):
                hits = decode(gpu.query(player, width, height))
                origin = player.x, player.y, player.eye_z
                for raw, direction in zip(hits, camera_rays(player, width, height)):
                    expected = exact_static_hit(world, origin, direction)
                    actual = refine(world, origin, direction, raw)
                    self.assertEqual(actual is not None, expected is not None)
                    if expected is not None:
                        self.assertEqual(actual[1], expected[1])
                        self.assertAlmostEqual(actual[0], expected[0], places=7)
        world.box(1, 1, 1, 2, 2, 2, STONE)
        with self.assertRaisesRegex(RuntimeError, 'Static geometry changed'):
            gpu.query(Player(), 60, 20)

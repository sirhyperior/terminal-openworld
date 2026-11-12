"""Shared presentation, exact CPU fallbacks and optional device integration."""

import importlib.util
import math
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ascii3d.combat import CombatState, Enemy
from ascii3d.doors import Door
from ascii3d.gpu_renderer import GPUBackend
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.surfaces import HeightField
from ascii3d.world import FLOOR, GRASS, PATH, STONE, World


def scene_world():
    world = World.empty(24, 24, 12)
    world.box(0, 0, 0, 24, 24, 1, FLOOR)
    world.heightfield = HeightField(24, 24, [1.2 + 0.02 * y for y in range(25) for x in range(25)])
    world.box(0, 16, 1, 24, 17, 8, STONE)
    world.add_stair_flight(4, 8, 3, 6, 1.5, 4.5)
    world.doors.append(Door('Test door', 10, 10, 4, double=False))
    world.combat = CombatState(enemies=[Enemy('Test target', 15.5, 13.5)])
    return world


class RendererFallbackTests(unittest.TestCase):
    def test_missing_device_uses_identical_cpu_frames(self):
        world = scene_world()
        with patch('ascii3d.gpu_renderer.GPUBackend', side_effect=RuntimeError('no device')):
            fallback = Renderer(world, backend='auto')
        self.assertEqual(fallback.backend_name, 'cpu')
        self.assertIn('no device', fallback.backend_error)
        player = Player(x=12.5, y=6.5, yaw=math.pi / 2)
        self.assertEqual(fallback.frame(player, 80, 30), Renderer(world).frame(player, 80, 30))

    def test_device_loss_closes_gpu_and_finishes_the_same_frame_on_cpu(self):
        world = scene_world()
        device = Mock()
        device.render.side_effect = RuntimeError('device lost')
        with patch('ascii3d.gpu_renderer.GPUBackend', return_value=device):
            renderer = Renderer(world, backend='gpu')
        player = Player(x=12.5, y=6.5, yaw=math.pi / 2)
        expected = Renderer(world).frame(player, 80, 30)
        self.assertEqual(renderer.frame(player, 80, 30), expected)
        self.assertEqual(renderer.frame(player, 80, 30), expected)
        self.assertEqual(renderer.backend_name, 'cpu')
        self.assertIn('device lost', renderer.backend_error)
        device.render.assert_called_once()
        device.close.assert_called_once()

    def test_uncertain_rays_share_the_existing_exact_cpu_renderer(self):
        world = scene_world()
        device = SimpleNamespace(render=lambda player, width, height: [None] * (width * height), close=lambda: None)
        with patch('ascii3d.gpu_renderer.GPUBackend', return_value=device):
            renderer = Renderer(world, backend='gpu')
        player = Player(x=12.5, y=6.5, yaw=math.pi / 2, pitch=-0.1)
        self.assertEqual(renderer.frame(player, 80, 30), Renderer(world).frame(player, 80, 30))

    def test_origin_near_a_float32_grid_boundary_avoids_an_unsafe_gpu_query(self):
        backend = GPUBackend.__new__(GPUBackend)
        backend.gpu = Mock(signature=(1, 2, 3))
        backend.gpu._signature.return_value = (1, 2, 3)
        backend.last_stats = {}
        self.assertIsNone(backend.render(Player(x=4 + 1e-8), 60, 20))
        backend.gpu.query.assert_not_called()
        self.assertEqual(backend.last_stats['fallback_rays'], 1200)


@unittest.skipUnless(os.environ.get('MONOLITH_GPU_TESTS') == '1' and importlib.util.find_spec('wgpu'),
                     'optional hardware GPU parity test')
class HardwareIntegratedRendererTests(unittest.TestCase):
    def test_complete_frames_resize_aspect_doors_enemies_and_edits(self):
        for aspect in (0.25, 0.5, 1.2):
            world = scene_world()
            cpu = Renderer(world, cell_aspect=aspect)
            gpu = Renderer(world, cell_aspect=aspect, backend='gpu')
            self.addCleanup(gpu.close)
            self.assertEqual(gpu.backend_name, 'gpu', gpu.backend_error)
            player = Player(x=12.5, y=6.5, yaw=math.pi / 2, pitch=-0.1)
            for width, height in ((60, 20), (81, 35), (60, 40)):
                for yaw in (math.pi / 2, 2.1):
                    player.yaw = yaw
                    self.assertEqual(gpu.frame(player, width, height, time_seconds=2),
                                     cpu.frame(player, width, height, time_seconds=2))
            world.doors[0].target_open = True
            for _ in range(5):
                world.doors[0].update(player, 0.05)
            self.assertGreater(world.doors[0].openness, 0)
            self.assertEqual(gpu.frame(player, 80, 30), cpu.frame(player, 80, 30))
            world.box(8, 12, 1, 10, 14, 6, STONE)
            self.assertEqual(gpu.frame(player, 80, 30), cpu.frame(player, 80, 30))
            world.heightfield.paint_cell(12, 8, PATH)
            self.assertEqual(gpu.frame(player, 80, 30), cpu.frame(player, 80, 30))
            self.assertEqual(gpu.ray_backend.rebuilds, 2)
            gpu.close()

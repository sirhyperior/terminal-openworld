"""Complete presentation parity includes semantic buffers, hue and exact hiding."""

from dataclasses import replace
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ascii3d.combat import Fireball
from ascii3d.player import Player
from ascii3d.presentation import StyledFrame
from ascii3d.renderer import Renderer
from ascii3d.surfaces import ConvexSolid, SolidBox
from ascii3d.world import FLOOR, GRASS, METAL, STONE, WATER, WOOD, World
from tools import verify_gpu_renderer
from tools.verify_gpu_renderer import frame_fingerprints, presentation_comparison


def color_world():
    world = World.empty(24, 24, 12)
    world.box(0, 0, 0, 24, 24, 1, FLOOR)
    world.box(1, 8, 1, 7, 9, 5, WOOD)
    world.box(17, 9, 1, 23, 10, 5, METAL)
    world.box(7, 14, 0, 16, 18, 1, WATER)
    world.add_solid(ConvexSolid(((9, 10, 1), (15, 10, 1), (9, 16, 1), (9, 10, 7)),
                               ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)), STONE))
    return world


class PresentationComparisonTests(unittest.TestCase):
    @staticmethod
    def sample():
        return StyledFrame(3, 1, ['x x'], [bytearray((8, 8, 8))],
                           [bytearray((GRASS, GRASS, GRASS))],
                           effects=[bytearray(3)], color_mode='color')

    def test_identical_glyphs_cannot_hide_material_or_effect_mismatches(self):
        original = self.sample()
        for name, changed in (
                ('material', replace(original, materials=[bytearray((WATER, GRASS, GRASS))])),
                ('effects', replace(original, effects=[bytearray((3, 0, 0))]))):
            with self.subTest(buffer=name):
                result = presentation_comparison(original, changed)
                self.assertTrue(result['image_equal'])
                self.assertTrue(result['style_equal'])
                self.assertFalse(result[name + '_equal'])
                self.assertFalse(result['color_ansi_equal'])
                self.assertTrue(result['gray_ansi_equal'])
                self.assertFalse(result['presentation_equal'])

    def test_fingerprints_include_each_buffer_and_both_output_modes(self):
        frame = self.sample()
        fingerprints = frame_fingerprints(frame)
        self.assertEqual(set(fingerprints), {'image_sha256', 'styles_sha256', 'materials_sha256',
                                             'effects_sha256', 'gray_ansi_sha256', 'color_ansi_sha256'})
        self.assertTrue(all(len(value) == 64 for value in fingerprints.values()))
        self.assertEqual(fingerprints, frame_fingerprints(replace(frame, color_mode='gray')))

    def test_verifier_retains_startup_failure_and_rejects_report_replacement(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            report = Path(directory) / 'failed.json'
            arguments = ['--save', str(report), '--scenes', 'indoors']
            with patch.object(verify_gpu_renderer, 'variant', side_effect=RuntimeError('fixture device failure')), \
                    redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(verify_gpu_renderer.main(arguments), 1)
            retained = report.read_bytes()
            saved = json.loads(retained)
            self.assertFalse(saved['complete'] or saved['passed'])
            self.assertEqual(saved['color_mode'], 'color')
            self.assertEqual(saved['errors'][0]['scene'], None)
            self.assertIn('fixture device failure', saved['errors'][0]['message'])
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                verify_gpu_renderer.main(arguments)
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(report.read_bytes(), retained)

    def test_uncertain_gpu_candidates_preserve_complete_color_output(self):
        world = color_world()
        device = SimpleNamespace(render=lambda player, width, height: [None] * (width * height),
                                 close=lambda: None)
        with patch('ascii3d.gpu_renderer.GPUBackend', return_value=device):
            fallback = Renderer(world, backend='gpu')
        reference = Renderer(world)
        self.addCleanup(fallback.close)
        self.addCleanup(reference.close)
        world.combat.fireballs.append(Fireball(8.5, 7.5, 2.8, (0, 1, 0)))
        player = Player(x=8.5, y=2.5, yaw=1.4, pitch=-0.12)
        for mode in ('color', 'gray'):
            with self.subTest(mode=mode):
                first = fallback.styled_frame(player, 61, 25, time_seconds=2.5, color_mode=mode)
                second = reference.styled_frame(player, 61, 25, time_seconds=2.5, color_mode=mode)
                self.assertTrue(presentation_comparison(first, second)['presentation_equal'])

    def test_hidden_fireball_does_not_leak_bright_glyphs_hues_or_styles(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.box(0, 6, 1, 24, 7, 10, STONE)
        renderer = Renderer(world)
        self.addCleanup(renderer.close)
        player = Player(x=8.5, y=4.5, yaw=math.pi / 2)
        empty = renderer.styled_frame(player, 61, 25, color_mode='color')
        world.combat.fireballs.append(Fireball(8.5, 9, 3, (0, 1, 0)))
        hidden = renderer.styled_frame(player, 61, 25, color_mode='color')
        self.assertTrue(presentation_comparison(empty, hidden)['presentation_equal'])


@unittest.skipUnless(os.environ.get('MONOLITH_GPU_TESTS') == '1' and importlib.util.find_spec('wgpu'),
                     'optional hardware GPU complete-color parity test')
class HardwareColorParityTests(unittest.TestCase):
    def test_live_cell_aspect_matches_fresh_projection_at_the_same_size(self):
        world = color_world()
        cpu, gpu = Renderer(world), Renderer(world, backend='gpu')
        fresh = Renderer(world, cell_aspect=0.8)
        for renderer in (cpu, gpu, fresh):
            self.addCleanup(renderer.close)
        self.assertEqual(gpu.backend_name, 'gpu', gpu.backend_error)
        player = Player(x=8.5, y=2.5, yaw=1.4, pitch=-0.12)
        expected = fresh.styled_frame(player, 61, 25, time_seconds=2.5)
        for renderer in (cpu, gpu):
            before = renderer.styled_frame(player, 61, 25, time_seconds=2.5)
            renderer.set_cell_aspect(0.8)
            after = renderer.styled_frame(player, 61, 25, time_seconds=2.5)
            self.assertNotEqual(before.rows, after.rows)
            self.assertTrue(presentation_comparison(after, expected)['presentation_equal'])
        self.assertEqual(gpu.backend_name, 'gpu', gpu.backend_error)

    def test_material_light_fog_tangent_faces_and_edits_preserve_all_color_buffers(self):
        world = color_world()
        cpu, gpu = Renderer(world), Renderer(world, backend='gpu')
        self.addCleanup(cpu.close)
        self.addCleanup(gpu.close)
        self.assertEqual(gpu.backend_name, 'gpu', gpu.backend_error)
        world.combat.fireballs.append(Fireball(8.5, 7.5, 2.8, (0, 1, 0)))
        for x, yaw, pitch in ((8.5, math.pi / 2, 0), (9.0, math.pi / 2, 0),
                              (8.1, 1.4, -0.2), (10.5, 1.8, 0.2)):
            player = Player(x=x, y=2.5, yaw=yaw, pitch=pitch)
            first = cpu.styled_frame(player, 81, 35, time_seconds=3, color_mode='color')
            second = gpu.styled_frame(player, 81, 35, time_seconds=3, color_mode='color')
            self.assertTrue(presentation_comparison(first, second)['presentation_equal'])
        world.add_solid(SolidBox(7, 7, 1, 9, 8, 5, WOOD))
        player = Player(x=8.5, y=2.5, yaw=math.pi / 2, pitch=-0.1)
        self.assertTrue(presentation_comparison(
            cpu.styled_frame(player, 61, 25, color_mode='color'),
            gpu.styled_frame(player, 61, 25, color_mode='color'))['presentation_equal'])
        self.assertEqual(gpu.ray_backend.rebuilds, 1)
        self.assertEqual(gpu.backend_name, 'gpu', gpu.backend_error)


if __name__ == '__main__':
    unittest.main()

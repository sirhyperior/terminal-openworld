"""Convex GPU candidates use real planes, bounded indexing and exact finishing."""

import importlib.util
import math
import os
import struct
import unittest

from ascii3d.gpu_renderer import GPUBackend, StaticGPU, decode, refine, solid_geometry_data
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.surfaces import ConvexSolid, SolidBox
from ascii3d.world import FLOOR, STONE, WOOD, World


def tetrahedron(x=5.0, y=7.0, z=1.0):
    return ConvexSolid(((x, y, z), (x + 4, y, z), (x, y + 4, z), (x, y, z + 4)),
                       ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)), STONE)


def test_world():
    world = World.empty(24, 24, 12)
    world.box(0, 0, 0, 24, 24, 1, FLOOR)
    world.add_solid(tetrahedron())
    world.add_solid(SolidBox(8, 12, 1, 10, 13, 5, WOOD))
    world.add_solid(tetrahedron(13, 8, 1))
    return world


class SolidUploadTests(unittest.TestCase):
    def test_upload_preserves_actual_convex_planes_and_box_fastpath(self):
        world = test_world()
        packed, planes, hierarchy, node_count = solid_geometry_data(world.solids)
        records = list(struct.iter_unpack('<8f4I', packed))
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0][8:10], (0, 4))
        self.assertEqual(records[1][8:10], (4, 0))
        self.assertEqual(records[2][8:10], (4, 4))
        expected = [value for solid in world.solids for plane in getattr(solid, 'planes', ()) for value in plane]
        self.assertEqual(len(planes), len(expected))
        for actual, value in zip(planes, expected):
            self.assertAlmostEqual(actual, value, places=5)
        nodes = list(struct.iter_unpack('<8f4I', hierarchy))
        self.assertEqual(node_count, 5)
        self.assertEqual(sorted(node[9] for node in nodes if node[9]), [1, 2, 3])
        for index, node in enumerate(nodes):
            self.assertLess(index, node[8])
            self.assertLessEqual(node[8], node_count)
        self.assertEqual(nodes[0][8], node_count)

    def test_empty_upload_has_valid_storage_buffers_and_zero_traversal(self):
        solids, planes, nodes, count = solid_geometry_data([])
        self.assertEqual((len(solids), len(planes), len(nodes), count), (48, 4, 48, 0))

    def test_exact_refinement_does_not_accept_a_convex_bounding_box_hit(self):
        world = test_world()
        origin, direction = (8.5, 2.5, 2.6), (0, 1, 0)
        self.assertIsNone(world.solids[0].ray_hit(origin, direction, 48))
        wrong = (0, 0, 0, 0, 0, 0, 0, 0, 0, STONE, 4, 0)
        self.assertIsNone(refine(world, origin, direction, wrong, reject_invalid=True))
        behind = (0, 0, 0, 0, 0, 0, 0, 0, 0, WOOD, 4, 1)
        self.assertEqual(refine(world, origin, direction, behind), (9.5, WOOD, (0, -1, 0)))


@unittest.skipUnless(os.environ.get('MONOLITH_GPU_TESTS') == '1' and importlib.util.find_spec('wgpu'),
                     'optional hardware GPU convex parity test')
class HardwareConvexTests(unittest.TestCase):
    def test_ray_through_empty_convex_aabb_keeps_farther_true_hit(self):
        world = test_world()
        backend = GPUBackend(world)
        self.addCleanup(backend.close)
        player = Player(x=8.5, y=2.5, z=1, yaw=math.pi / 2)
        result = backend.render(player, 1, 1)
        self.assertIsNotNone(result[0], 'well-separated ray should produce an exact GPU candidate')
        self.assertEqual(result[0][:3], (9.5, WOOD, (0, -1, 0)))

    def test_full_frame_parity_with_inclined_faces_tangencies_and_edits(self):
        world = test_world()
        cpu, gpu = Renderer(world), Renderer(world, backend='gpu')
        self.addCleanup(gpu.close)
        self.assertEqual(gpu.backend_name, 'gpu', gpu.backend_error)
        for x, yaw, pitch in ((8.5, math.pi / 2, 0), (7.2, 1.45, 0.12),
                              (5.0, math.pi / 2, 0), (8.5, 0.9, -0.3)):
            player = Player(x=x, y=2.5, z=1, yaw=yaw, pitch=pitch)
            self.assertEqual(cpu.frame(player, 61, 25), gpu.frame(player, 61, 25))
        world.add_solid(tetrahedron(4, 13, 1))
        player = Player(x=8.5, y=2.5, z=1, yaw=math.pi / 2)
        self.assertEqual(cpu.frame(player, 61, 25), gpu.frame(player, 61, 25))
        self.assertEqual(gpu.ray_backend.rebuilds, 1)

    def test_all_refined_shader_samples_match_independent_solid_queries(self):
        from ascii3d.gpu_renderer import camera_rays

        world = test_world()
        gpu = StaticGPU(world)
        self.addCleanup(gpu.close)
        player = Player(x=8.5, y=2.5, z=1, yaw=1.45, pitch=0.1)
        raw = decode(gpu.query(player, 63, 25))
        origin = player.x, player.y, player.eye_z
        for candidates, direction in zip(raw, camera_rays(player, 63, 25)):
            # Uncertain rays are deliberately rerun by the production CPU path.
            if any(int(candidates[offset + 2]) & 64 for offset in (0, 4, 8)):
                continue
            actual = refine(world, origin, direction, candidates)
            expected = world.geometry_hit(origin, direction, 48)
            if expected is not None:
                self.assertIsNotNone(actual)
                self.assertAlmostEqual(actual[0], expected.distance, places=7)
                self.assertEqual(actual[1], expected.material)


if __name__ == '__main__':
    unittest.main()

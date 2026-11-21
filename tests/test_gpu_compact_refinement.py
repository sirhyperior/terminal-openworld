"""Compact shader readback preserves exact host candidates without a GPU."""

import math
import random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from ascii3d.gpu_renderer import GPUBackend, camera_rays, refine
from ascii3d.native_solids import NativeGPURefiner, SolidLibrary
from ascii3d.player import Player
from ascii3d.surfaces import ConvexSolid, HeightField, SolidBox
from ascii3d.world import FLOOR, GRASS, METAL, STONE, WATER, WATER_LEVEL, World


def synthetic_hits(world, player, width, height, aspect, rng):
    """Combine exact candidate locations, uncertainty flags and misses."""
    origin = player.x, player.y, player.eye_z
    records = []
    for direction in camera_rays(player, width, height, aspect):
        dx, dy, dz = direction
        voxel = field = solid = 0
        if dz < -1e-12:
            distance = (1 - origin[2]) / dz
            x, y = math.floor(origin[0] + dx * distance), math.floor(origin[1] + dy * distance)
            if 0 <= x < world.width and 0 <= y < world.depth and distance <= 48:
                voxel = (2 << 28) | (y * world.width + x + 1)
        ground = world.heightfield.ray_hit(origin, direction, 48)
        if ground is not None:
            hx = origin[0] + dx * ground.distance
            hy = origin[1] + dy * ground.distance
            x, y = math.floor(hx), math.floor(hy)
            if 0 <= x < world.width and 0 <= y < world.depth:
                triangle = 3 if hy - y > hx - x else 2
                field = (triangle << 28) | (y * world.width + x + 1)
        for index, box in enumerate(world.solids):
            if box.ray_hit(origin, direction, 48) is not None:
                solid = index + 1
                break
        if rng.randrange(9) == 0:
            # Wrong triangle/location exercises exact rejection after readback.
            field = (3 << 28) | rng.randint(1, world.width * world.depth)
        keep = rng.randint(0, 7)
        records.append((voxel if keep & 1 else 0, field if keep & 2 else 0,
                        solid if keep & 4 else 0, 64 if rng.randrange(17) == 0 else 0))
    return records


def legacy_results(world, player, width, height, aspect, records):
    """Expand records through the previous production diagnostic API."""
    origin = player.x, player.y, player.eye_z
    results = []
    for (voxel, field, solid, flags), direction in zip(
            records, camera_rays(player, width, height, aspect)):
        if flags & 64:
            results.append(None)
        elif not (voxel or field or solid):
            results.append(GPUBackend.MISS)
        else:
            vi, fi, si = (voxel & 0x0fffffff) - 1, (field & 0x0fffffff) - 1, solid - 1
            candidates = (0, world.cells[vi] if voxel else 0, 1 | ((voxel >> 28) << 8), vi,
                          0, world.heightfield.materials[fi] if field else 0, (field >> 28) | 512, fi,
                          0, world.solids[si].material if solid else 0, 4, si)
            results.append(refine(world, origin, direction, candidates, with_axis=True, reject_invalid=True))
    return results


class GPUCompactRefinementTests(unittest.TestCase):
    def fake_backend(self, world, aspect):
        backend = GPUBackend.__new__(GPUBackend)
        backend.world, backend.cell_aspect = world, aspect
        backend.gpu = SimpleNamespace(signature=(1,), _signature=lambda: (1,), query=Mock())
        backend.rebuilds = 0
        backend._size = None
        backend._native_refiner = None
        return backend

    def test_seeded_mixed_records_match_previous_path_after_pose_and_size_changes(self):
        self.check_seeded_mixed_records()

    def test_native_batch_matches_previous_path_after_pose_and_size_changes(self):
        try:
            library = SolidLibrary()
        except (AttributeError, OSError):
            self.skipTest('optional native solid library not built')
        if library.gpu_refine is None:
            self.skipTest('optional native GPU refiner not built')
        self.check_seeded_mixed_records(library)

    def check_seeded_mixed_records(self, library=None):
        world = World.empty(32, 32, 12)
        world.box(0, 0, 0, 32, 32, 1, FLOOR)
        world.box(3, 6, 0, 13, 13, 1, WATER)
        world.heightfield = HeightField(32, 32, [
            1.2 + 0.025 * x + 0.012 * y for y in range(33) for x in range(33)])
        world.add_solid(SolidBox(2, 16, 1, 16, 17, 5, STONE))
        world.add_solid(SolidBox(17, 4, 0, 18, 27, 4, METAL))
        world.add_solid(ConvexSolid(((5, 6, 1), (11, 6, 1), (5, 12, 1), (5, 6, 7)),
                                    ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)), STONE))
        aspect = 0.7
        backend = self.fake_backend(world, aspect)
        if library is not None:
            backend._native_refiner = NativeGPURefiner(library, world, WATER_LEVEL)
        rng = random.Random(520826)
        player = Player(x=8.25, y=4.4, z=2.1)
        for width, height, yaw, pitch in ((41, 19, 1.4, -0.2), (41, 19, 0.2, 0.17),
                                          (60, 23, 1.05, -0.3), (41, 19, 1.93, 0)):
            with self.subTest(size=(width, height), yaw=yaw, pitch=pitch):
                player.yaw, player.pitch = yaw, pitch
                records = synthetic_hits(world, player, width, height, aspect, rng)
                data = b''.join(struct.pack('<4I', *record) for record in records)
                backend.gpu.query.return_value = memoryview(data).cast('I')
                actual = backend.render(player, width, height)
                expected = legacy_results(world, player, width, height, aspect, records)
                self.assertEqual(actual, expected)
                self.assertEqual(backend.last_stats['fallback_rays'], actual.count(None))
                self.assertGreater(actual.count(None), 0)
                self.assertIn(GPUBackend.MISS, actual)
                self.assertTrue(any(hit is not None and hit[1] for hit in actual))
                backend.gpu.query.assert_called_with(player, width, height)

    def test_coincident_candidates_keep_solid_then_terrain_then_voxel_order(self):
        world = World.empty(12, 12, 6)
        world.box(0, 0, 0, 12, 12, 1, FLOOR)
        world.heightfield = HeightField(12, 12, [1.0] * 169, GRASS)
        world.add_solid(SolidBox(3, 3, 0, 6, 6, 1, STONE))
        player = Player(x=4.25, y=4.25, z=0.02, yaw=0, pitch=-math.pi / 4)
        backend = self.fake_backend(world, 0.5)
        index = 4 * world.width + 4 + 1
        voxel, field = (2 << 28) | index, (2 << 28) | index
        for record, material in (((voxel, field, 1, 0), STONE),
                                 ((voxel, field, 0, 0), GRASS),
                                 ((voxel, 0, 0, 0), FLOOR)):
            with self.subTest(record=record):
                backend.gpu.query.return_value = struct.pack('<4I', *record)
                hit, = backend.render(player, 1, 1)
                self.assertEqual(hit[1], material)
                self.assertEqual(hit[3], 2)


if __name__ == '__main__':
    unittest.main()

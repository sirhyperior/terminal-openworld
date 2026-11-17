"""Gothic pieces share exact sight/collision and preserve usable circulation."""

import importlib.util
import math
import os
import unittest
from unittest.mock import patch

from ascii3d.architecture import bevel_voxel_corners, build_landmark, pointed_arch, tapered_tower
from ascii3d.player import Player
from ascii3d.terrain import Landmark, stair_routes
from ascii3d.world import AIR, GRASS, PATH, STONE, World


class GothicArchitectureTests(unittest.TestCase):
    def test_beveled_voxel_corners_use_diagonal_sight_and_collision_faces(self):
        world = World.empty(20, 20, 12)
        world.box(0, 0, 0, 20, 20, 1, GRASS)
        world.box(4, 4, 1, 11, 11, 8, STONE)
        world.box(6, 6, 1, 9, 9, 7, AIR)
        pieces = bevel_voxel_corners(world, 4, 4, 1, 11, 11, 8)
        self.assertEqual(len(pieces), 4)
        self.assertEqual(world.get(4, 4, 3), AIR)
        self.assertIsNone(world.solid_hit((4.2, 4.2, 3), (0, 0, 1), 6))
        hit = world.geometry_hit((2, 4.2, 3), (1, 0, 0), 8)
        self.assertAlmostEqual(hit.distance, 2.8, places=8)
        self.assertAlmostEqual(hit.normal[0], -1 / math.sqrt(2))
        self.assertAlmostEqual(hit.normal[1], -1 / math.sqrt(2))
        self.assertFalse(world.collides(4.15, 4.15, 1, radius=0.15))
        self.assertTrue(world.collides(4.8, 4.8, 1, radius=0.15))
        self.assertFalse(world.collides(7.5, 7.5, 1))
        self.assertEqual(world.surface_height(5.5, 4.5), 8)
        bevel_voxel_corners(world, 4, 4, 1, 11, 11, 8)
        self.assertEqual(len(world.solids), 4)

    def test_beveled_low_block_still_requires_jumping(self):
        world = World.empty(20, 20, 8)
        world.box(0, 0, 0, 20, 20, 1, GRASS)
        world.box(4, 4, 1, 11, 11, 2, STONE)
        bevel_voxel_corners(world, 4, 4, 1, 11, 11, 2)
        player = Player(x=3, y=4.25, z=1, yaw=0)
        for _ in range(160):
            player.update(world, {"w"}, 1 / 120)
        self.assertLess(player.x, 4.75)
        self.assertEqual(player.z, 1)
        self.assertFalse(world.collides(player.x, player.y, player.z))

    def test_citadel_west_terrace_passage_connects_side_arch_to_the_road(self):
        landmark = Landmark("MOURNING CITADEL", (20, 20, 52, 56), 4)
        world = World.empty(80, 80, 32)
        world.box(0, 0, 0, 80, 80, 4, GRASS)
        build_landmark(world, landmark)
        player = Player(x=21.5, y=38.5, z=4, yaw=math.pi)
        for destination, yaw in ((15.5, math.pi), (21.5, 0)):
            player.yaw = yaw
            for _ in range(480):
                player.update(world, {"w"}, 1 / 120)
                self.assertEqual(player.z, 4)
                self.assertFalse(world.collides(player.x, player.y, player.z))
                if player.x <= destination if yaw else player.x >= destination:
                    break
            self.assertLess(abs(player.x - destination), 0.04)
        self.assertEqual(world.get(17, 33, 4), STONE)
        self.assertEqual(world.get(17, 43, 4), STONE)

    def test_landmark_foundations_keep_grass_outside_narrow_doorway_paths(self):
        world = World.empty(80, 80, 32)
        build_landmark(world, Landmark("THORNWATCH", (20, 20, 52, 56), 4))
        self.assertEqual(world.surface_material(18.5, 24.5), GRASS)
        for x, y in ((36.5, 18.5), (36.5, 57.5), (18.5, 38.5), (56.5, 38.5)):
            self.assertEqual(world.get(int(x), int(y), 3), PATH)

    def test_pointed_arch_passage_is_open_and_its_sloping_head_is_exact(self):
        for axis in ("x", "y"):
            with self.subTest(axis=axis):
                world = World.empty(20, 20, 12)
                world.box(0, 0, 0, 20, 20, 1, GRASS)
                if axis == "x":
                    world.box(3, 8, 1, 14, 9, 9)
                else:
                    world.box(8, 3, 1, 9, 14, 9)
                pointed_arch(world, 5 if axis == "x" else 8,
                             8 if axis == "x" else 5, 6, 1, 6, axis=axis)
                center = (8, 8.5) if axis == "x" else (8.5, 8)
                self.assertFalse(world.collides(*center, 1))
                origin = (8, 6, 2.5) if axis == "x" else (6, 8, 2.5)
                direction = (0, 1, 0) if axis == "x" else (1, 0, 0)
                self.assertIsNone(world.solid_hit(origin, direction, 5))
                # At a quarter-span the underside lies halfway up the head.
                x, y = (6.5, 8.5) if axis == "x" else (8.5, 6.5)
                hit = world.geometry_hit((x, y, 3), (0, 0, 1), 8)
                self.assertIsNotNone(hit)
                self.assertAlmostEqual(hit.distance, 2.92, places=7)
                self.assertLess(hit.normal[2], 0)
                self.assertNotEqual(hit.normal[0 if axis == "x" else 1], 0)

    def test_octagonal_tower_has_hollow_center_and_solid_tapered_walls(self):
        world = World.empty(24, 24, 20)
        pieces = tapered_tower(world, 12, 12, 1, 15, radius=3)
        self.assertEqual(len(pieces), 9)
        self.assertFalse(world.collides(12, 12, 1))
        self.assertTrue(world.collides(14.65, 12, 1))
        hit = world.geometry_hit((12, 12, 19), (0, 0, -1), 20)
        self.assertAlmostEqual(hit.distance, 3)
        self.assertLess(abs(hit.normal[2]), 1)
        # An edit/rebuild never adds duplicate convex surfaces.
        tapered_tower(world, 12, 12, 1, 15, radius=3)
        self.assertEqual(len(world.solids), 9)

    def test_each_style_preserves_stair_headroom_and_ground_to_roof_walk(self):
        for name in ("THORNWATCH", "BLACK ABBEY", "ASTRAL RELIQUARY", "MOURNING CITADEL"):
            with self.subTest(style=name):
                landmark = Landmark(name, (20, 20, 52, 56), 4)
                world = World.empty(80, 80, 32)
                world.box(0, 0, 0, 80, 80, 4, GRASS)
                build_landmark(world, landmark)
                for x, start, end, feet in stair_routes(landmark):
                    player = Player(x=x, y=start, z=feet)
                    for _ in range(720):
                        player.update(world, {"w"}, 1 / 120)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                        if player.y >= end:
                            break
                    self.assertGreaterEqual(player.y, end)
                    self.assertAlmostEqual(player.z, feet + 5, places=4)
                    player.yaw = -math.pi / 2
                    for _ in range(720):
                        player.update(world, {"w"}, 1 / 120)
                        if player.y <= start:
                            break
                    self.assertLessEqual(player.y, start)
                    self.assertAlmostEqual(player.z, feet, places=4)
                x0, y0, x1, y1 = landmark.bounds
                cx, cy = (x0 + x1) // 2 + 0.5, (y0 + y1) // 2 + 0.5
                for x, y in ((x0 + 0.5, cy), (x1 - 0.5, cy), (cx, y0 + 0.5), (cx, y1 - 0.5)):
                    self.assertFalse(world.collides(x, y, landmark.base))
                balcony = Player(x=x1 + 2.5, y=cy, z=landmark.base + 5, yaw=0)
                for _ in range(160):
                    balcony.update(world, {"w"}, 1 / 120)
                self.assertLessEqual(balcony.x, x1 + 4 - balcony.RADIUS + 1e-6)
                self.assertAlmostEqual(balcony.z, landmark.base + 5)
                first, second, third = stair_routes(landmark)
                player = Player(x=x0 - 1.5, y=cy, z=landmark.base, yaw=0)
                points = ((cx, cy), (cx, first[1]), (first[0], first[1]),
                          (first[0], first[2]), (cx, first[2]), (cx, second[1]),
                          (second[0], second[1]), (second[0], second[2]),
                          (cx, second[2]), (cx, third[1]), (third[0], third[1]),
                          (third[0], third[2]))
                for x, y in points:
                    for _ in range(1200):
                        if math.hypot(x - player.x, y - player.y) < 0.04:
                            break
                        player.yaw = math.atan2(y - player.y, x - player.x)
                        player.update(world, {"w"}, 1 / 120)
                    self.assertLess(math.hypot(x - player.x, y - player.y), 0.04)
                self.assertAlmostEqual(player.z, landmark.roof, places=4)

    def test_named_destinations_have_distinct_geometry_and_fractured_roofs(self):
        signatures = set()
        for name in ("THORNWATCH", "BLACK ABBEY", "ASTRAL RELIQUARY", "MOURNING CITADEL"):
            landmark = Landmark(name, (20, 20, 52, 56), 4)
            world = World.empty(80, 80, 32)
            build_landmark(world, landmark)
            signatures.add((bytes(world.cells), tuple((p.vertices, p.material) for p in world.solids
                                                     if hasattr(p, "vertices"))))
            if name in ("BLACK ABBEY", "ASTRAL RELIQUARY"):
                self.assertEqual(world.get(39, 40 if name == "ASTRAL RELIQUARY" else 38, 18), AIR)
        self.assertEqual(len(signatures), 4)

    def test_authored_destination_silhouettes_stay_inside_world_height(self):
        from ascii3d.map_expansion import _ashgate, _gravewood
        from ascii3d.terrain import LANDMARKS

        world = World.empty(512, 512, 32)
        _ashgate(world)
        _gravewood(world)
        for landmark in LANDMARKS:
            build_landmark(world, landmark)
        for solid in world.solids:
            self.assertGreaterEqual(solid.z0, 0)
            self.assertLess(solid.z1, world.height)


@unittest.skipUnless(os.environ.get('MONOLITH_GPU_TESTS') == '1' and importlib.util.find_spec('wgpu'),
                     'optional hardware gothic-architecture parity test')
class HardwareArchitectureTests(unittest.TestCase):
    def test_pointed_openings_spires_and_sloping_supports_match_complete_cpu_frames(self):
        from ascii3d.renderer import Renderer

        landmark = Landmark('THORNWATCH', (12, 16, 36, 40), 4)
        world = World.empty(56, 56, 32)
        world.box(0, 0, 0, 56, 56, 4, GRASS)
        build_landmark(world, landmark)
        cpu, gpu = Renderer(world), Renderer(world, backend='gpu')
        self.addCleanup(cpu.close)
        self.addCleanup(gpu.close)
        self.assertEqual(gpu.backend_name, 'gpu', gpu.backend_error)
        for x, y, z, yaw, pitch in ((24.5, 8.5, 4, math.pi / 2, 0.20),
                                   (7.5, 28.5, 4, 0, 0),
                                   (24.5, 28.5, 4, -math.pi / 2, 0.12),
                                   (24.5, 30.5, 19, -math.pi / 2, 0.10)):
            with self.subTest(pose=(x, y, z, yaw, pitch)):
                player = Player(x=x, y=y, z=z, yaw=yaw, pitch=pitch)
                self.assertFalse(world.collides(x, y, z))
                images, buffers = [], []
                for renderer in (cpu, gpu):
                    original = renderer.scenery.draw

                    def capture(pixels, depths, *args):
                        buffers.append([row[:] for row in depths])
                        return original(pixels, depths, *args)

                    with patch.object(renderer.scenery, 'draw', side_effect=capture):
                        images.append(renderer.scene(player, 61, 25))
                # Ink equality covers glyph, level, material and palette effects.
                self.assertEqual(images[0], images[1])
                for row0, row1 in zip(buffers[0], buffers[1]):
                    for depth0, depth1 in zip(row0, row1):
                        self.assertEqual(math.isfinite(depth0), math.isfinite(depth1))
                        if math.isfinite(depth0):
                            # Same float64 refinement tolerance as the complete
                            # frame verifier; ray evaluation order may differ.
                            self.assertLessEqual(abs(depth0 - depth1), 1e-7)


if __name__ == "__main__":
    unittest.main()

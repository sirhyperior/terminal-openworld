"""Continuous road boundaries share point materials without changing ground."""

import importlib.util
import math
import os
from statistics import quantiles
import unittest
from unittest.mock import patch

from ascii3d.palette import color_rgb
from ascii3d.paving import PAVING_SCALE, PAVING_SIZE, cobble_texture
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.roads import RoadNetwork
from ascii3d.scenery import Scenery
from ascii3d.sound_surfaces import surface_kind
from ascii3d.surfaces import HeightField
from ascii3d.world import BRIDGE, FLOOR, GRASS, PATH, STONE, WATER, WOOD, World


def grassy_world(size=24):
    world = World.empty(size, size, 10)
    world.box(0, 0, 0, size, size, 1, GRASS)
    return world


class RoadNetworkTests(unittest.TestCase):
    def test_diagonal_boundary_distinguishes_points_inside_the_same_voxel(self):
        roads = RoadNetwork((((0, 0), (16, 16)),))
        inside, outside = (4.1, 6.1), (4.1, 6.9)
        self.assertEqual(tuple(map(math.floor, inside)), tuple(map(math.floor, outside)))
        self.assertTrue(roads.contains(*inside))
        self.assertFalse(roads.contains(*outside))
        self.assertEqual(roads.material_at(*inside, GRASS), PATH)
        self.assertEqual(roads.material_at(*outside, GRASS), GRASS)

    def test_round_ends_and_turns_stay_connected_across_spatial_buckets(self):
        roads = RoadNetwork((((0, 0), (8, 0), (8, 16)),), width=2)
        for point in ((-0.9, 0), (7.99, 0), (8.01, 0), (8, 7.999),
                      (8, 8.001), (8.65, -0.65), (8, 16.9)):
            self.assertTrue(roads.contains(*point), point)
        for point in ((-0.8, -0.8), (9.1, -1.1), (8, 17.1)):
            self.assertFalse(roads.contains(*point), point)
        degenerate = RoadNetwork((((-2, -2), (-2, -2)),), width=2)
        self.assertTrue(degenerate.contains(-2, -2.5))
        self.assertFalse(degenerate.contains(-2, -3.1))

    def test_authored_surfaces_take_precedence_over_paving(self):
        roads = RoadNetwork((((0, 0), (16, 16)),))
        for material in (BRIDGE, FLOOR, STONE, WATER, WOOD, PATH):
            self.assertEqual(roads.material_at(4, 4, material), material)

    def test_cell_coverage_matches_exact_queries_at_strips_joins_and_round_ends(self):
        routes = (((4, 1.5), (4, 8), (12, 16)), ((13, 3), (14, 3), (14, 3)))
        indexed = RoadNetwork(routes)
        reference = RoadNetwork(routes, bucket_size=7)
        self.assertIn(True, indexed._cell_coverage.values())
        points = [(x / 4, y / 4) for x in range(-4, 68) for y in range(-4, 72)]
        for x in (2.5, 5.5, 15.5):
            points.extend((test_x, y) for y in (0, 1.5, 3, 7.75, 8)
                          for test_x in (math.nextafter(x, -math.inf), x, math.nextafter(x, math.inf)))
        self.assertEqual([indexed.contains(*point) for point in points],
                         [reference.contains(*point) for point in points])

    def test_long_roads_use_bounded_local_candidates_and_reject_overloaded_junctions(self):
        roads = RoadNetwork((((0, 0), (512, 0)),))
        self.assertGreater(len(roads.segments), 50)
        self.assertLessEqual(roads.candidate_count(256, 0), 4)
        self.assertLessEqual(roads.max_bucket_segments, roads.MAX_SEGMENTS_PER_BUCKET)
        self.assertEqual(roads.candidate_count(256, 100), 0)
        with self.assertRaises(ValueError):
            RoadNetwork([((0, 0), (1, 0))] * (roads.MAX_SEGMENTS_PER_BUCKET + 1))
        for kwargs in ({"width": 0}, {"bucket_size": -1}, {"width": math.inf}):
            with self.assertRaises(ValueError):
                RoadNetwork((), **kwargs)
        with self.assertRaises(ValueError):
            RoadNetwork((((0, 0), (math.nan, 1)),))
        self.assertFalse(roads.contains(math.inf, 0))
        self.assertFalse(RoadNetwork(()).contains(0, 0))


class ContinuousRoadIntegrationTests(unittest.TestCase):
    def test_irregular_stones_and_joints_blend_at_distance(self):
        positions = [(x / PAVING_SCALE, y / PAVING_SCALE) for x in range(64) for y in range(0, 64, 5)]
        near = [cobble_texture(x, y, 5) for x, y in positions]
        distant = [cobble_texture(x, y, 15) for x, y in positions]
        deciles = quantiles(near, n=10)
        self.assertGreater(deciles[-1] - deciles[0], 0.67)
        self.assertAlmostEqual(max(distant) - min(distant), (max(near) - min(near)) / 2)
        self.assertEqual(len({cobble_texture(x, y, 20) for x, y in positions}), 1)
        # Each scanline crosses a mix of stones and joints across many cells.
        joint_counts = [sum(cobble_texture(x / PAVING_SCALE, y / PAVING_SCALE, 5) < 0.36
                            for x in range(64)) for y in range(64)]
        self.assertTrue(all(5 < count < 54 for count in joint_counts))

    def test_paving_wraps_without_a_texture_seam_and_uses_a_muted_palette(self):
        period = PAVING_SIZE / PAVING_SCALE
        for x, y in ((0.0, 0.27), (-0.11, 0.0), (3.25, -9.8)):
            self.assertAlmostEqual(cobble_texture(x, y, 4), cobble_texture(x + period, y - period, 4))
        self.assertLess(abs(cobble_texture(-1e-6, 1.3, 5) - cobble_texture(1e-6, 1.3, 5)), 0.0001)
        self.assertLess(max(color_rgb(PATH, 10)), 150)

    def test_surface_foley_and_support_use_points_without_creating_steps(self):
        world = grassy_world()
        points = ((4.1, 6.1), (4.1, 6.9))
        supports = [world.walk_support(x, y, 1)[0] for x, y in points]
        cells = bytes(world.cells)
        world.roads = RoadNetwork((((0, 0), (16, 16)),))
        for index, (x, y) in enumerate(points):
            self.assertEqual(world.surface_material(x, y), PATH if index == 0 else GRASS)
            self.assertEqual(world.surface_height(x, y), 1)
            self.assertEqual(world.walk_support(x, y, 1)[0], supports[index])
            self.assertFalse(world.collides(x, y, 1))
            self.assertEqual(surface_kind(world, x, y, 1), "stone" if index == 0 else "grass")
        self.assertEqual(bytes(world.cells), cells)
        world.box(3, 3, 0, 6, 6, 1, BRIDGE)
        self.assertEqual(world.surface_material(4, 4), BRIDGE)
        self.assertEqual(surface_kind(world, 4, 4, 1), "wood")

    def test_renderer_samples_exact_road_material_on_flat_and_sloping_ground(self):
        for sloping in (False, True):
            with self.subTest(sloping=sloping):
                world = grassy_world()
                if sloping:
                    heights = [1 + x * 0.03 for y in range(25) for x in range(25)]
                    world.heightfield = HeightField(24, 24, heights, material=GRASS)
                world.roads = RoadNetwork((((0, 0), (24, 24)),))
                renderer = Renderer(world, particles=False)
                self.addCleanup(renderer.close)
                player = Player(x=10, y=4, z=world.surface_height(10, 4), pitch=-0.4)
                with patch.object(renderer.shading, "surface", wraps=renderer.shading.surface) as shade:
                    renderer.scene(player, 60, 20)
                samples = [call.args for call in shade.call_args_list
                           if call.args[0] in (GRASS, PATH) and call.args[4][2] > 0]
                self.assertGreater(len(samples), 50)
                self.assertEqual({sample[0] for sample in samples}, {GRASS, PATH})
                for material, x, y, *_ in samples:
                    self.assertEqual(material, world.roads.material_at(x, y, GRASS))

    def test_path_centered_cell_keeps_grass_on_its_exposed_edges(self):
        world = grassy_world()
        world.outdoor_bounds = (0, 0, 24, 24)
        baseline = Scenery(world).grass_chunk(2, 2)
        original = next(blades for x, y, blades in baseline if (x, y) == (8, 8))
        self.assertEqual(len(original), 16)
        world.roads = RoadNetwork((((0, 0), (24, 24)),), width=0.5)
        self.assertEqual(world.surface_material(8.5, 8.5), PATH)
        patches = Scenery(world).grass_chunk(2, 2)
        retained = next(blades for x, y, blades in patches if (x, y) == (8, 8))
        expected = [blade for blade in original if not world.roads.contains(blade.x, blade.y)]
        self.assertEqual(retained, expected)
        self.assertGreater(len(retained), 0)
        self.assertLess(len(retained), 16)
        self.assertEqual(len(next(blades for x, y, blades in patches if (x, y) == (8, 11))), 16)
        self.assertTrue(all(world.surface_material(blade.x, blade.y) == GRASS
                            for _, _, blades in patches for blade in blades))


@unittest.skipUnless(os.environ.get("MONOLITH_GPU_TESTS") == "1" and importlib.util.find_spec("wgpu"),
                     "optional hardware GPU continuous-road material parity")
class HardwareRoadParityTests(unittest.TestCase):
    def test_complete_gpu_presentation_matches_cpu_for_both_ground_paths(self):
        for sloping in (False, True):
            with self.subTest(sloping=sloping):
                world = grassy_world()
                if sloping:
                    world.heightfield = HeightField(24, 24,
                        [1 + x * 0.03 for y in range(25) for x in range(25)], material=GRASS)
                world.roads = RoadNetwork((((0, 0), (24, 24)),))
                cpu = Renderer(world, backend="cpu", particles=False)
                gpu = Renderer(world, backend="gpu", particles=False)
                self.addCleanup(cpu.close)
                self.addCleanup(gpu.close)
                self.assertEqual(gpu.backend_name, "gpu", gpu.backend_error)
                player = Player(x=10.5, y=4.5, z=world.surface_height(10.5, 4.5), pitch=-0.4)
                first = cpu.styled_frame(player, 60, 20)
                second = gpu.styled_frame(player, 60, 20)
                self.assertEqual(first.rows, second.rows)
                self.assertEqual(first.materials, second.materials)
                self.assertEqual(first.styles, second.styles)
                self.assertEqual(first.effects, second.effects)
                self.assertGreater(sum(row.count(PATH) for row in first.materials), 10)
                self.assertLess(gpu.ray_backend.last_stats["fallback_rays"], 60 * 20)


if __name__ == "__main__":
    unittest.main()

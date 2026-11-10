import math
import unittest

from ascii3d.geometry import Camera
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.scenery import Scenery
from ascii3d.trees import Crown, Trees
from ascii3d.terminal import fit_viewport
from ascii3d.world import FLOOR, GRASS, Tree, World, build_world
from tools.benchmark import EXTRA_SCENARIOS, SCENARIOS


class VegetationTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_short_grass_covers_every_clear_outdoor_cell_including_approaches(self):
        # Exhaustively check a bounded world; enormous maps create only the
        # nearby deterministic chunks rather than millions of eager blades.
        world = World.empty(24, 24, 10)
        world.outdoor_bounds = (1, 1, 23, 23)
        world.box(0, 0, 0, 24, 24, 1, GRASS)
        world.box(7, 7, 1, 11, 11, 4, GRASS)
        scenery = Scenery(world)
        for cy in range(6):
            for cx in range(6):
                scenery.grass_chunk(cx, cy)
        counts = {}
        for blade in scenery.blades:
            self.assertGreaterEqual(blade.height, 0.09)
            self.assertLessEqual(blade.height, 0.24)
            cell = int(blade.x), int(blade.y)
            counts[cell] = counts.get(cell, 0) + 1
            self.assertEqual(blade.z, world.surface_height(*cell))
        x0, y0, x1, y1 = world.outdoor_bounds
        for y in range(y0, y1):
            for x in range(x0, x1):
                if world.surface_material(x, y) == GRASS:
                    self.assertGreaterEqual(counts.get((x, y), 0), 12)
        self.assertEqual(self.world.get(16, 34, 0), GRASS)
        self.assertEqual(self.world.get(16, 56, 0), GRASS)
        live = Scenery(self.world)
        for x, y in ((16, 34), (16, 56)):
            patches = live.grass_chunk(x // live.CHUNK, y // live.CHUNK)
            self.assertGreaterEqual(len(next(blades for px, py, blades in patches
                                             if (px, py) == (x, y))), 12)

    def test_player_motion_bends_nearby_grass_without_moving_roots(self):
        renderer = Renderer(self.world)
        player = Player(x=24.5, y=34.5, pitch=-0.65)
        still = renderer.scene(player, 100, 36, time_seconds=2)
        roots = [(blade.x, blade.y) for blade in renderer.scenery.blades]
        player.moving, player.running = True, True
        disturbed = renderer.scene(player, 100, 36, time_seconds=2)
        self.assertNotEqual(still, disturbed)
        self.assertEqual(roots, [(blade.x, blade.y) for blade in renderer.scenery.blades])
        player.moving, player.running = False, False
        self.assertEqual(still, renderer.scene(player, 100, 36, time_seconds=2))

    def test_trunk_collision_is_circular_and_foliage_is_soft(self):
        tree = self.world.trees[12, 34]
        self.assertTrue(self.world.collides(tree.x, tree.y, 1))
        self.assertFalse(self.world.collides(tree.x + 0.4, tree.y + 0.4, 1))
        self.assertFalse(self.world.collides(tree.x + 1, tree.y, tree.height + 0.2))

    def test_crown_silhouette_is_rounded_and_trunk_is_narrow(self):
        world = World.empty(20, 20, 10)
        world.trees[8, 12] = Tree(8.5, 12.5)
        pixels = [[" "] * 100 for _ in range(40)]
        depths = [[math.inf] * 100 for _ in range(40)]
        camera = Camera(Player(x=8.5, y=4.5, pitch=0.25), 100, 40, 57.5, 0.5)
        Trees(world).draw(pixels, depths, camera, {})
        row_widths = [sum(char != " " for char in row) for row in pixels]
        occupied = [width for width in row_widths if width]
        self.assertGreater(max(occupied), 8)
        self.assertLess(occupied[0], max(occupied) * 0.75)
        self.assertLess(occupied[-1], max(occupied) * 0.5)

    def test_offscreen_crown_does_not_spend_fullscreen_intersection_budget(self):
        pixels = [[" "] * 100 for _ in range(30)]
        depths = [[math.inf] * 100 for _ in range(30)]
        camera = Camera(Player(x=5, y=5, pitch=-0.4), 100, 30, 57.5, 0.5)
        stats = {"tree_samples": 0}
        crown = Crown(20, 6, 6, 1.5, 1.5, 1.5)
        Trees._crown(crown, pixels, depths, camera, stats, 9000)
        self.assertEqual(stats["tree_samples"], 0)
        self.assertFalse(any(char != " " for row in pixels for char in row))

    def test_close_trunks_remain_visible_from_all_sides_when_looking_up_or_down(self):
        world = World.empty(24, 24, 10)
        tree = Tree(12.5, 12.5)
        world.trees[12, 12] = tree
        trees = Trees(world)
        for yaw in (0, math.pi / 2, math.pi, -math.pi / 2):
            for pitch in (-0.35, 0.35):
                for distance in (1.0, 0.75, 0.5, 0.45):
                    with self.subTest(yaw=yaw, pitch=pitch, distance=distance):
                        player = Player(x=tree.x - math.cos(yaw) * distance,
                                        y=tree.y - math.sin(yaw) * distance,
                                        yaw=yaw, pitch=pitch)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                        pixels = [[" "] * 80 for _ in range(28)]
                        depths = [[math.inf] * 80 for _ in range(28)]
                        trees.draw(pixels, depths, Camera(player, 80, 28, 46, 0.5), {})
                        occupied_rows = sum(any(char != " " for char in row) for row in pixels)
                        self.assertGreater(occupied_rows, 14)

    def test_inside_crown_renders_exit_surface_and_respects_foreground_depth(self):
        player = Player(x=8.5, y=12.5, z=5 - Player.EYE, yaw=0)
        camera = Camera(player, 80, 28, 46, 0.5)
        crown = Crown(8.5, 12.5, 5, 1.5, 1.5, 1.5)
        pixels = [[" "] * 80 for _ in range(28)]
        depths = [[math.inf] * 80 for _ in range(28)]
        stats = {"tree_samples": 0}
        Trees._crown(crown, pixels, depths, camera, stats, 80 * 28 * 3)
        self.assertTrue(all(char != " " for row in pixels for char in row))
        self.assertTrue(all(0.18 <= depth <= 1.5 for row in depths for depth in row))
        self.assertEqual(stats["tree_samples"], 80 * 28)
        for x, y in ((0, 0), (40, 14), (79, 27)):
            u, v = (x + 0.5 - 40) / 46, (14 - y - 0.5) / 23
            self.assertAlmostEqual(depths[y][x], 1.5 / math.sqrt(1 + u * u + v * v))
        foreground = [["#"] * 80 for _ in range(28)]
        Trees._crown(crown, foreground, [[0.2] * 80 for _ in range(28)], camera,
                     {"tree_samples": 0}, 80 * 28 * 3)
        self.assertTrue(all(char == "#" for row in foreground for char in row))

    def test_jump_into_live_canopy_stays_visible_within_sample_budget(self):
        player = Player(x=12.5, y=33.95, z=2.25, pitch=0.65)
        self.assertFalse(self.world.collides(player.x, player.y, player.z))
        renderer = Renderer(self.world)
        pixels = renderer.scene(player, 100, 35)
        canopy_chars = ":;ox*#%@"
        self.assertGreater(sum(char in canopy_chars for row in pixels[:18] for char in row), 100)
        self.assertLessEqual(renderer.scenery.stats["tree_samples"], 100 * 35 * 3)

    def test_near_plane_crown_is_not_discarded_with_visible_exit_in_front(self):
        player = Player(x=7.0, y=12.5, z=5 - Player.EYE, yaw=0)
        camera = Camera(player, 80, 28, 46, 0.5)
        pixels = [[" "] * 80 for _ in range(28)]
        depths = [[math.inf] * 80 for _ in range(28)]
        Trees._crown(Crown(8.5, 12.5, 5, 1.6, 1.5, 1.5), pixels, depths,
                     camera, {"tree_samples": 0}, 80 * 28 * 3)
        self.assertNotEqual(pixels[14][40], " ")
        self.assertGreater(depths[14][40], 1)

    def test_tree_behind_camera_does_not_leave_clipped_trunk_artifacts(self):
        world = World.empty(20, 20, 10)
        world.trees[8, 12] = Tree(8.5, 12.5)
        pixels = [[" "] * 80 for _ in range(28)]
        depths = [[math.inf] * 80 for _ in range(28)]
        camera = Camera(Player(x=8.5, y=13.5), 80, 28, 46, 0.5)
        Trees(world).draw(pixels, depths, camera, {})
        self.assertTrue(all(char == " " for row in pixels for char in row))

    def test_near_clipped_trunk_preserves_foreground_occlusion(self):
        tree = Tree(8.5, 12.5)
        for pitch in (-0.35, 0.35):
            with self.subTest(pitch=pitch):
                camera = Camera(Player(x=8.5, y=12.0, pitch=pitch), 80, 28, 46, 0.5)
                pixels = [["#"] * 80 for _ in range(28)]
                depths = [[0.1] * 80 for _ in range(28)]
                Trees._trunk(tree, pixels, depths, camera)
                self.assertTrue(all(char == "#" for row in pixels for char in row))
                self.assertTrue(all(depth == 0.1 for row in depths for depth in row))

    def test_trees_do_not_draw_through_voxel_walls(self):
        world = World.empty(20, 20, 10)
        world.box(0, 0, 0, 20, 20, 1, FLOOR)
        world.box(0, 7, 1, 20, 8, 10)
        player = Player(x=8.5, y=4.5)
        plain = Renderer(world).scene(player, 90, 30)
        world.trees[8, 12] = Tree(8.5, 12.5)
        self.assertEqual(plain, Renderer(world).scene(player, 90, 30))

    def test_larger_maps_keep_visible_vegetation_work_within_pixel_budgets(self):
        for size in (40, 64, 112):
            world = World.empty(size, size, 10)
            world.outdoor_bounds = (1, 1, size - 1, size - 1)
            world.box(0, 0, 0, size, size, 1, GRASS)
            renderer = Renderer(world)
            renderer.scene(Player(x=18.5, y=18.5, pitch=-0.35), 90, 30, time_seconds=1)
            stats = renderer.scenery.stats
            self.assertGreater(stats["grass_drawn"], 0)
            self.assertLessEqual(stats["grass_chunks"], 81)
            self.assertLessEqual(stats["grass_candidates"], stats["grass_budget"])
            self.assertLessEqual(stats["tree_samples"], stats["tree_pixel_budget"])


class TraversalOptimizationTests(unittest.TestCase):
    def test_merged_bounds_match_exact_rays_with_partial_chunks_and_raised_surfaces(self):
        world = World.empty(37, 49, 10)
        world.box(0, 0, 0, 37, 49, 1, FLOOR)
        world.box(14, 12, 1, 18, 20, 4)
        world.box(15, 12, 1, 17, 20, 3, 0)
        world.box(28, 36, 1, 37, 38, 7)
        world.box(2, 40, 1, 8, 49, 2)
        fast, exact = Renderer(world), Renderer(world, skip_empty_space=False)
        for x, y, z, yaw in ((5.5, 5.5, 1, 0.8), (32.5, 44.5, 1, -1.8),
                              (10.5, 30.5, 3.5, 2.1), (20.5, 15.5, 1, math.pi)):
            for pitch in (-0.5, 0.0, 0.45):
                with self.subTest(pose=(x, y, z, yaw), pitch=pitch):
                    player = Player(x=x, y=y, z=z, yaw=yaw, pitch=pitch)
                    self.assertEqual(fast.scene(player, 80, 26), exact.scene(player, 80, 26))

    def test_skipping_matches_exact_traversal_in_all_benchmark_views(self):
        world = build_world()
        fast, reference = Renderer(world), Renderer(world, skip_empty_space=False)
        for name, pose in {**SCENARIOS, **EXTRA_SCENARIOS}.items():
            for pitch_offset in (-0.15, 0.15):
                with self.subTest(scene=name, pitch_offset=pitch_offset):
                    player = Player(**pose)
                    player.pitch += pitch_offset
                    self.assertEqual(fast.scene(player, 90, 28, time_seconds=1.5),
                                     reference.scene(player, 90, 28, time_seconds=1.5))

    def test_editing_world_invalidates_empty_space_cache(self):
        world = World.empty(20, 20, 10)
        world.box(0, 0, 0, 20, 20, 1, FLOOR)
        player = Player(x=10.5, y=4.5)
        renderer = Renderer(world)
        before = renderer.scene(player, 80, 28)
        world.box(4, 10, 1, 17, 11, 7)
        after = renderer.scene(player, 80, 28)
        self.assertNotEqual(before, after)
        self.assertEqual(after, Renderer(world, skip_empty_space=False).scene(player, 80, 28))


class ViewportBudgetTests(unittest.TestCase):
    def test_large_windows_cannot_multiply_the_render_work(self):
        for budget in (1200, 4800, 11520):
            for columns, rows in ((60, 21), (80, 24), (120, 41), (180, 65), (300, 120)):
                width, height = fit_viewport(columns, rows, budget)
                self.assertLessEqual(width * height, budget)
                self.assertGreaterEqual(width, 60)
                self.assertGreaterEqual(height, 20)
                self.assertLessEqual(width, columns)
                self.assertLessEqual(height, rows)

    def test_small_window_is_not_enlarged_past_its_actual_size(self):
        self.assertEqual(fit_viewport(40, 12), (40, 12))
        self.assertEqual(fit_viewport(120, 41), (120, 41))


if __name__ == "__main__":
    unittest.main()

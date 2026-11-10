"""Analytic crown spans retain the scalar per-pixel surface and occlusion."""

import math
import random
import unittest
from unittest.mock import patch

from ascii3d.geometry import Camera
from ascii3d.player import Player
from ascii3d.trees import Crown, Trees
from ascii3d.world import Tree, World


def scalar_crown(crown, pixels, depths, cam):
    """Independent viewport-wide ellipsoid ray reference, without span bounds."""
    ix, iy, iz = 1 / crown.rx ** 2, 1 / crown.ry ** 2, 1 / crown.rz ** 2
    ox, oy, oz = cam.x - crown.x, cam.y - crown.y, cam.z - crown.z
    bx, by, bz = ox * ix, oy * iy, oz * iz
    constant = ox * bx + oy * by + oz * bz - 1
    palette = " .,:;ox*#%@"
    for y in range(cam.height):
        v = (cam.height / 2 - y - 0.5) / cam.fy
        base_x, base_y = cam.cy * (cam.cp - v * cam.sp), cam.sy * (cam.cp - v * cam.sp)
        dz = cam.sp + v * cam.cp
        for x in range(cam.width):
            u = (x + 0.5 - cam.width / 2) / cam.fx
            dx, dy = base_x + u * cam.sy, base_y - u * cam.cy
            a = dx * dx * ix + dy * dy * iy + dz * dz * iz
            b = dx * bx + dy * by + dz * bz
            discriminant = b * b - a * constant
            if discriminant < 0:
                continue
            root = math.sqrt(discriminant)
            depth = (-b - root) / a
            if depth < cam.NEAR:
                depth = (-b + root) / a
            if depth < cam.NEAR or depth >= depths[y][x]:
                continue
            hx, hy, hz = ox + dx * depth, oy + dy * depth, oz + dz * depth
            nx, ny, nz = hx * ix, hy * iy, hz * iz
            normal_length = math.sqrt(nx * nx + ny * ny + nz * nz)
            light = max(0, (-nx * 0.38 - ny * 0.48 + nz * 0.79) / normal_length)
            grain = (int((hx + crown.x) * 14) * 37 ^ int((hy + crown.y) * 14) * 19 ^ int(hz * 14) * 7) & 7
            brightness = (0.29 + light * 0.52 + grain * 0.018) / (1 + depth * 0.035)
            pixels[y][x] = palette[max(1, min(9, int(brightness * 10)))]
            depths[y][x] = depth


class CrownSpanTests(unittest.TestCase):
    def test_selection_preserves_nearest_limit_and_shared_distance_detail(self):
        world = World.empty(128, 128, 20)
        rows = (14, 16, 18, 20, 22, 24, 36, 42)
        for y in (*rows, 3, 65):
            world.trees[64, y] = Tree(64.5, y + 0.5)
        world.trees[90, 11] = Tree(90.5, 11.5)
        trees = Trees(world)
        for width, height, expected_rows in ((60, 20, rows[:6]), (120, 35, rows)):
            with self.subTest(viewport=(width, height)):
                camera = Camera(Player(x=64.5, y=10.5), width, height,
                                width * 0.575, 0.5)
                selected = trees.visible_selection(camera)
                self.assertEqual([tree.y for _, tree in selected],
                                 [y + 0.5 for y in expected_rows])
                trunks, crowns = [], []
                with patch.object(trees, "_trunk", side_effect=lambda tree, *args: trunks.append(tree)), \
                        patch.object(trees, "_crown", side_effect=lambda crown, *args: crowns.append(crown)):
                    trees.draw([[" "] * width for _ in range(height)],
                               [[math.inf] * width for _ in range(height)], camera, {})
                self.assertEqual(trunks, [tree for _, tree in selected])
                expected_crowns = []
                for y in expected_rows:
                    tree = world.trees[64, y]
                    expected_crowns.extend(trees.crowns[tree] if y - 10 <= 24
                                           else trees.crowns[tree][:1])
                self.assertEqual(crowns, expected_crowns)

    def test_projected_work_bound_covers_unoccluded_samples_and_rejects_budget_pressure(self):
        world = World.empty(32, 32, 16)
        world.trees[8, 12] = Tree(8.5, 12.5)
        trees = Trees(world)
        near_bound = None
        for pose in ((8.5, 4.5, 1, 0.25), (8.5, 12.5, 5 - Player.EYE, 0)):
            player = Player(x=pose[0], y=pose[1], z=pose[2], pitch=pose[3])
            camera = Camera(player, 80, 28, 46, 0.5)
            bound = trees.projected_work_bound(camera)
            stats = {}
            trees.draw([[" "] * 80 for _ in range(28)],
                       [[math.inf] * 80 for _ in range(28)], camera, stats)
            self.assertGreaterEqual(bound, stats["tree_samples"])
            self.assertLessEqual(stats["tree_samples"], 80 * 28 * 3)
            if pose[1] == 12.5:
                near_bound = bound
        self.assertGreaterEqual(near_bound, 80 * 28 * 3)

    def test_spans_match_scalar_glyphs_and_depths_outside_inside_and_near_plane(self):
        rng = random.Random(7919)
        crown = Crown(8.5, 12.5, 6, 1.8, 1.1, 1.6)
        cases = [(8.5, 12.5, 6, 0, 0),
                 (7.0, 12.5, 6, 0, 0),
                 (8.5, 11.45, 6, math.pi / 2, 0),
                 (8.5, 4.5, 2.48, math.pi / 2, 0.25)]
        for _ in range(40):
            angle = rng.uniform(-math.pi, math.pi)
            distance = rng.choice((0.2, 0.8, 1.5, 3, 10, 28))
            x, y = crown.x - math.cos(angle) * distance, crown.y - math.sin(angle) * distance
            cases.append((x, y, crown.z + rng.uniform(-3, 3),
                          angle + rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6)))
        for pose in cases:
            with self.subTest(pose=pose):
                x, y, eye, yaw, pitch = pose
                cam = Camera(Player(x=x, y=y, z=eye - Player.EYE, yaw=yaw, pitch=pitch),
                             80, 28, 46, 0.5)
                depths = [[0.25 if (x + y) % 11 == 0 else math.inf
                           for x in range(80)] for y in range(28)]
                actual = [["#"] * 80 for _ in range(28)]
                expected = [row[:] for row in actual]
                expected_depths = [row[:] for row in depths]
                stats = {"tree_samples": 0}
                Trees._crown(crown, actual, depths, cam, stats, 80 * 28 * 3)
                scalar_crown(crown, expected, expected_depths, cam)
                self.assertEqual(actual, expected)
                for row, reference in zip(depths, expected_depths):
                    for value, target in zip(row, reference):
                        if math.isinf(target):
                            self.assertTrue(math.isinf(value))
                        else:
                            self.assertAlmostEqual(value, target, places=11)

    def test_crown_span_avoids_proven_miss_rays_and_hidden_scanlines(self):
        crown = Crown(8.5, 12.5, 5, 1.65, 1.55, 1.65)
        cam = Camera(Player(x=8.5, y=4.5, pitch=0.25), 120, 40, 69, 0.5)
        x0, y0, x1, y1 = cam.bounds(crown.x, crown.y, crown.z,
                                           crown.rx, crown.ry, crown.rz)
        rectangular_candidates = (x1 - x0 + 1) * (y1 - y0 + 1)
        pixels = [[" "] * 120 for _ in range(40)]
        depths = [[math.inf] * 120 for _ in range(40)]
        stats = {"tree_samples": 0}
        Trees._crown(crown, pixels, depths, cam, stats, 120 * 40 * 3)
        self.assertLess(stats["tree_samples"], rectangular_candidates * 0.8)
        self.assertGreater(stats["tree_samples"], 0)
        hidden_stats = {"tree_samples": 0}
        Trees._crown(crown, pixels, [[0.1] * 120 for _ in range(40)], cam,
                     hidden_stats, 120 * 40 * 3)
        self.assertEqual(hidden_stats["tree_samples"], 0)


if __name__ == "__main__":
    unittest.main()

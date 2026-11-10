"""Exact audio neighborhoods and cached maps stay bounded as the world grows."""

import math
import unittest
from unittest.mock import patch

from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.soundscape import Soundscape
from ascii3d.world import BRIDGE, GRASS, PATH, WATER, World


def full_scan_audio(world, x, y, yaw):
    """Pre-optimization reference: visit every actual water tile."""
    outdoors = world.get(math.floor(x), math.floor(y), 0) in (GRASS, WATER, BRIDGE, PATH)
    nearest, total, weighted_x, weighted_y = math.inf, 0.0, 0.0, 0.0
    for cy in range(world.depth):
        for cx in range(world.width):
            if world.get(cx, cy, 0) != WATER:
                continue
            dx, dy = max(cx - x, 0, x - cx - 1), max(cy - y, 0, y - cy - 1)
            distance = dx * dx + dy * dy
            nearest = min(nearest, distance)
            if distance < 18 ** 2:
                weight = 1 / (1 + distance)
                total += weight
                weighted_x += (cx + 0.5 - x) * weight
                weighted_y += (cy + 0.5 - y) * weight
    river = 0.5 * max(0, 1 - math.sqrt(nearest) / 18) ** 2 * (1 if outdoors else 0.12)
    pan = 0.0
    if total:
        dx, dy = weighted_x / total, weighted_y / total
        pan = max(-0.55, min(0.55, (dx * math.sin(yaw) - dy * math.cos(yaw)) / max(6, math.hypot(dx, dy))))
    return (0.18 if outdoors else 0.025), river, pan


class WorldWorkBudgetTests(unittest.TestCase):
    def test_bucketed_audio_matches_full_scan_at_banks_bridges_edges_and_after_edits(self):
        world = World.empty(112, 112, 8)
        world.box(0, 0, 0, 112, 112, 1, GRASS)
        world.box(0, 80, 0, 112, 87, 1, WATER)
        world.box(22, 78, 0, 27, 90, 1, BRIDGE)
        scene = Soundscape(world)
        for edited in (False, True):
            if edited:
                world.box(45, 80, 0, 59, 87, 1, GRASS)
            for x, y in ((0.1, 79.5), (24.5, 83), (52.5, 76.5), (111.8, 100),
                         (55, 20), (7.99, 61.999), (8.01, 62.001)):
                for yaw in (0, 1.2, math.pi):
                    with self.subTest(edited=edited, x=x, y=y, yaw=yaw):
                        self.assertEqual(scene.at(x, y, yaw), full_scan_audio(world, x, y, yaw))

    def test_audio_query_only_visits_fixed_local_buckets_after_warmup(self):
        class CountedBuckets(dict):
            calls = 0

            def get(self, *args):
                self.calls += 1
                return super().get(*args)

        for size in (64, 112, 192):
            world = World.empty(size, size, 3)
            world.box(0, 0, 0, size, size, 1, WATER)
            scene = Soundscape(world)
            scene.at(32, 32, 0)
            buckets = scene._water_chunks = CountedBuckets(scene._water_chunks)
            with patch.object(world, "get", wraps=world.get) as get:
                scene.at(32, 32, 0)
                self.assertEqual(get.call_count, 1)  # listener ground only
            self.assertLessEqual(buckets.calls, 49)

    def test_static_map_is_cached_player_marker_moves_and_voxel_edits_invalidate(self):
        world = World.empty(112, 112, 8)
        world.box(0, 0, 0, 112, 112, 1, GRASS)
        renderer = Renderer(world)
        player = Player(x=55.5, y=30.5)

        def draw(width=100, height=30):
            pixels = [[" "] * width for _ in range(height)]
            renderer._map(pixels, player)
            return pixels

        with patch.object(world, "surface_height", wraps=world.surface_height) as query:
            first = draw()
            queries = query.call_count
            self.assertGreater(queries, 0)
            self.assertLessEqual(queries, 112 * 112)
            player.x += 20
            self.assertNotEqual(first, draw())
            self.assertEqual(query.call_count, queries)
            world.box(0, 90, 0, 112, 97, 1, WATER)
            self.assertTrue(any("~" in row for row in draw()))
            self.assertGreater(query.call_count, queries)
            queries = query.call_count
            draw(60, 15)
            self.assertGreater(query.call_count, queries)


if __name__ == "__main__":
    unittest.main()

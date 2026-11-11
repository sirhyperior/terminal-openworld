"""Local vegetation, raised roots and floor-aware ambient sound."""

import math
import unittest
from unittest.mock import patch

from ascii3d.geometry import Camera
from ascii3d.player import Player
from ascii3d.scenery import Scenery
from ascii3d.sound_surfaces import surface_kind
from ascii3d.soundscape import Soundscape
from ascii3d.trees import Trees
from ascii3d.world import FLOOR, GRASS, STONE, WOOD, Tree, World


def grass_world(size=32, elevation=1):
    world = World.empty(size, size, 20)
    world.outdoor_bounds = (0, 0, size, size)
    world.box(0, 0, 0, size, size, elevation, STONE)
    world.box(0, 0, elevation - 1, size, size, elevation, GRASS)
    return world


class ElevatedSceneryTests(unittest.TestCase):
    def test_fractional_floor_cover_suppresses_only_the_covered_grass_roots(self):
        from ascii3d.surfaces import SolidBox

        world = grass_world(elevation=1)
        # The exclusive edge leaves the center clear above the western half.
        world.add_solid(SolidBox(8, 8, 1, 8.5, 9, 1.25, FLOOR))
        patches = Scenery(world).grass_chunk(2, 2)
        blades = next(blades for x, y, blades in patches if (x, y) == (8, 8))
        self.assertEqual(len(blades), 8)
        self.assertTrue(all(blade.x >= 8.5 and blade.z == 1 for blade in blades))
        self.assertTrue(all(world.surface_material(blade.x, blade.y) == GRASS for blade in blades))
        self.assertTrue(all(len(blades) == 16 for x, y, blades in patches if (x, y) != (8, 8)))

    def test_sloped_grass_uses_each_blades_exact_supported_height_without_thinning(self):
        from ascii3d.surfaces import HeightField

        world = grass_world(elevation=1)
        heights = [2 + x / 8 + y / 16
                   for y in range(world.depth + 1) for x in range(world.width + 1)]
        world.heightfield = HeightField(world.width, world.depth, heights, material=GRASS)
        scenery = Scenery(world)
        patches = scenery.grass_chunk(2, 2)
        self.assertEqual(len(patches), 16)
        for x, y, blades in patches:
            self.assertEqual(len(blades), 16)
            self.assertGreater(len({blade.z for blade in blades}), 12)
            for blade in blades:
                self.assertAlmostEqual(blade.z, 2 + blade.x / 8 + blade.y / 16)
                self.assertAlmostEqual(blade.z, world.surface_height(blade.x, blade.y))

    def test_construction_does_not_scan_or_allocate_the_enormous_grass_field(self):
        world = World.empty(512, 512, 32)
        world.outdoor_bounds = (0, 0, 512, 512)
        with patch.object(world, "get", wraps=world.get) as get:
            scenery = Scenery(world)
        self.assertEqual(get.call_count, 0)
        self.assertEqual(scenery.blades, [])
        self.assertEqual(len(scenery._chunks), 0)

    def test_raised_grass_keeps_full_patch_density_at_the_actual_surface(self):
        world = grass_world(elevation=6)
        scenery = Scenery(world)
        patches = scenery.grass_chunk(2, 2)
        self.assertEqual(len(patches), 16)
        for x, y, blades in patches:
            self.assertEqual(len(blades), 16)
            for blade in blades:
                self.assertEqual(blade.z, 6)
                self.assertTrue(x <= blade.x < x + 1 and y <= blade.y < y + 1)
                self.assertTrue(0.09 <= blade.height <= 0.24)
        self.assertEqual(surface_kind(world, 9.5, 9.5, 6), "grass")

    def test_chunk_cache_stays_bounded_and_eviction_preserves_seeded_geometry(self):
        world = grass_world(size=64)
        scenery = Scenery(world)
        original = scenery.grass_chunk(0, 0)
        for cy in range(16):
            for cx in range(16):
                scenery.grass_chunk(cx, cy)
                self.assertLessEqual(len(scenery._chunks), scenery.MAX_GRASS_CHUNKS)
        self.assertNotIn((0, 0), scenery._chunks)
        self.assertEqual(scenery.grass_chunk(0, 0), original)
        self.assertLessEqual(len(scenery.blades), scenery.MAX_GRASS_CHUNKS * 16 * 16)

    def test_voxel_edits_invalidate_grass_roots_and_material(self):
        world = grass_world(elevation=3)
        scenery = Scenery(world)
        before = scenery.grass_chunk(2, 2)
        self.assertTrue(before)
        world.box(8, 8, 2, 12, 12, 3, FLOOR)
        self.assertEqual(scenery.grass_chunk(2, 2), [])
        world.box(8, 8, 3, 12, 12, 5, GRASS)
        after = scenery.grass_chunk(2, 2)
        self.assertTrue(all(blade.z == 5 for _, _, blades in after for blade in blades))
        self.assertEqual([(b.x, b.y) for _, _, blades in before for b in blades],
                         [(b.x, b.y) for _, _, blades in after for b in blades])

    def test_raised_tree_trunk_and_crown_translate_together(self):
        frames = []
        for elevation in (1, 6):
            world = World.empty(24, 24, 20)
            world.trees[8, 12] = Tree(8.5, 12.5, height=elevation + 3.3,
                                     base_z=elevation)
            pixels = [[" "] * 80 for _ in range(28)]
            depths = [[math.inf] * 80 for _ in range(28)]
            player = Player(x=8.5, y=4.5, z=elevation, pitch=0.25)
            stats = {}
            Trees(world).draw(pixels, depths, Camera(player, 80, 28, 46, 0.5), stats)
            self.assertLessEqual(stats["tree_samples"], 80 * 28 * 3)
            frames.append(pixels)
        self.assertEqual(frames[0], frames[1])
        self.assertTrue(any("|" in row for row in frames[1]))

    def test_elevated_grass_is_visible_and_preserves_local_draw_budgets(self):
        world = grass_world(size=64, elevation=8)
        scenery = Scenery(world)
        pixels = [[" "] * 90 for _ in range(30)]
        depths = [[math.inf] * 90 for _ in range(30)]
        player = Player(x=18.5, y=18.5, z=8, pitch=-0.35)
        scenery.draw(pixels, depths, player, 2, 51.75, 0.5)
        self.assertGreater(scenery.stats["grass_drawn"], 0)
        self.assertLessEqual(scenery.stats["grass_chunks"], 81)
        self.assertLessEqual(scenery.stats["grass_candidates"], 90 * 30 // 3)
        self.assertLessEqual(len(scenery._chunks), scenery.MAX_GRASS_CHUNKS)
        self.assertTrue(all(blade.z == 8 for blade in scenery.blades))

    def test_fully_occluded_grass_does_not_sample_invisible_wind(self):
        scenery = Scenery(grass_world(size=64, elevation=8))
        # Keep a single patch whose projected roots are all inside the depth
        # buffer; offscreen roots may legitimately bend back into the view.
        scenery.blades = [blade for x, y, blades in scenery.grass_chunk(4, 5)
                          if (x, y) == (18, 22) for blade in blades]
        pixels = [["#"] * 90 for _ in range(30)]
        depths = [[0.0] * 90 for _ in range(30)]
        player = Player(x=18.5, y=18.5, z=8, pitch=-0.35)
        with patch.object(scenery, "wind_at", wraps=scenery.wind_at) as wind:
            scenery.draw(pixels, depths, player, 2, 51.75, 0.5)
        self.assertGreater(scenery.stats["grass_candidates"], 0)
        self.assertEqual(wind.call_count, 0)
        self.assertEqual(scenery.stats["grass_drawn"], 0)
        self.assertTrue(all(char == "#" for row in pixels for char in row))

    def test_wind_follows_elevated_listener_and_roof_cover(self):
        world = grass_world(elevation=6)
        soundscape = Soundscape(world)
        self.assertEqual(soundscape.at(9.5, 9.5, 0, feet=6)[0], 0.18)
        world.box(8, 8, 10, 12, 12, 11, WOOD)
        self.assertEqual(soundscape.at(9.5, 9.5, 0, feet=6)[0], 0.025)
        self.assertEqual(soundscape.at(9.5, 9.5, 0, feet=11)[0], 0.18)
        self.assertEqual(surface_kind(world, 9.5, 9.5, 11), "wood")


if __name__ == "__main__":
    unittest.main()

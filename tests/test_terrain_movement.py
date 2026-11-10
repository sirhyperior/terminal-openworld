"""Supported stair traversal, head clearance and surface-specific feedback."""

import unittest
from unittest.mock import patch

from ascii3d.app import REGION_NAMES, spawn_region
from ascii3d.events import GameEvent
from ascii3d.player import Player
from ascii3d.sound import EFFECTS, Mixer, SoundBank, TERRAIN_STEP_CUES
from ascii3d.targeting import cylinder_hit
from ascii3d.world import AIR, CRATE, FLOOR, GRASS, STONE, WOOD, Tree, World, build_world


class TerrainMovementTests(unittest.TestCase):
    def stairs(self, material=FLOOR):
        world = World.empty(20, 10, 14)
        world.box(0, 0, 0, 20, 10, 1, GRASS)
        for step in range(5):
            world.box(4 + step, 2, 1, 5 + step, 7, 2 + step, material)
        world.box(9, 2, 0, 15, 7, 6, FLOOR)
        return world

    def test_walk_and_sprint_climb_supported_stairs_and_emit_foley(self):
        for keys in ({"w"}, {"w", "shift"}):
            with self.subTest(keys=keys):
                world = self.stairs()
                player = Player(x=2.5, y=4.5, yaw=0)
                events = []
                for _ in range(300):
                    player.update(world, keys, 1 / 120)
                    events.extend(player.events)
                    self.assertFalse(world.collides(player.x, player.y, player.z))
                    if player.x > 10:
                        break
                self.assertGreater(player.x, 10)
                self.assertAlmostEqual(player.z, 6, places=4)
                steps = [event for event in events if event.name == "terrain_step"]
                self.assertEqual(len(steps), 5)
                self.assertTrue(all(event.surface == "stone" for event in steps))
                self.assertTrue(all(event.name in EFFECTS for event in events))
                self.assertNotIn("jump", [event.name for event in events])

    def test_step_rejects_ceiling_tall_walls_crates_rails_and_airborne_climbing(self):
        for obstruction in ("ceiling", "wall", "crate", "rail", "airborne"):
            with self.subTest(obstruction=obstruction):
                world = World.empty(16, 10, 10)
                world.box(0, 0, 0, 16, 10, 1, GRASS)
                material = CRATE if obstruction == "crate" else WOOD if obstruction == "rail" else FLOOR
                world.box(4, 2, 1, 7, 7, 2 if obstruction != "wall" else 5, material)
                if obstruction == "ceiling":
                    world.box(2, 2, 3, 8, 7, 4, STONE)
                player = Player(x=3.7, y=4.5, yaw=0)
                if obstruction == "airborne":
                    player.grounded = False
                    self.assertFalse(player._step_up(world, 3.9, 4.5))
                    continue
                for _ in range(60):
                    player.update(world, {"w"}, 1 / 120)
                self.assertLessEqual(player.x, 4 - player.RADIUS + 1e-6)
                self.assertAlmostEqual(player.z, 1, places=5)

    def test_surface_queries_follow_top_floors_and_invalidate_on_box(self):
        world = self.stairs()
        self.assertEqual(world.surface_height(5.5, 4.5), 3)
        self.assertEqual(world.surface_material(5.5, 4.5), FLOOR)
        world.box(5, 4, 8, 6, 5, 9, WOOD)
        self.assertEqual(world.surface_height(5.5, 4.5), 9)
        self.assertEqual(world.surface_material(5.5, 4.5), WOOD)
        world.box(5, 4, 8, 6, 5, 9, AIR)
        self.assertEqual(world.surface_height(5.5, 4.5), 3)
        self.assertEqual(world.surface_height(-0.2, 4.5), 0)

    def test_elevated_trunks_share_collision_and_exact_occlusion(self):
        world = World.empty(40, 40, 20)
        world.trees[8, 8] = Tree(8.5, 8.5, height=10, base_z=6)
        self.assertTrue(world.collides(8.5, 8.5, 6))
        self.assertFalse(world.collides(8.5, 8.5, 2))
        self.assertIsNone(world.solid_hit((6.5, 8.5, 3), (1, 0, 0), 4))
        self.assertAlmostEqual(world.solid_hit((6.5, 8.5, 7), (1, 0, 0), 4), 1.8)
        # Distant population cannot turn a short targeting query into a scan.
        for y in range(20, 40):
            for x in range(20, 40):
                world.trees[x, y] = Tree(x + 0.5, y + 0.5)
        with patch("ascii3d.world.cylinder_hit", wraps=cylinder_hit) as hits:
            world.solid_hit((6.5, 8.5, 7), (1, 0, 0), 4)
            self.assertEqual(hits.call_count, 1)

    def test_tree_segment_index_keeps_large_radius_hits_after_dictionary_mutations(self):
        world = World.empty(20, 20, 10)
        tree = Tree(5.5, 8.5, radius=3.2)
        for insert in (lambda: world.trees.update({(5, 8): tree}),
                       lambda: world.trees.setdefault((5, 8), tree),
                       lambda: setattr(world, "trees", {(5, 8): tree})):
            world.trees.clear()
            insert()
            expected = cylinder_hit((2.5, 5.5, 2), (1, 0, 0),
                                    tree.x, tree.y, tree.base_z, tree.radius,
                                    tree.height - tree.base_z, 5)
            self.assertAlmostEqual(world.solid_hit((2.5, 5.5, 2), (1, 0, 0), 5), expected)


class TerrainSoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = SoundBank()

    def test_terrain_step_routes_each_surface_to_registered_original_foley(self):
        mixer = Mixer(self.bank)
        self.assertIn("terrain_step", EFFECTS)
        for surface, cue in TERRAIN_STEP_CUES.items():
            mixer.add(GameEvent("terrain_step", surface=surface))
            self.assertTrue(any(mixer.voices[-1].samples is clip for clip in self.bank.clips[cue]))
        mixer.add(GameEvent("terrain_step", surface="unknown"))
        self.assertIs(mixer.voices[-1].samples, self.bank.clips["terrain_step"][0])

    def test_region_entrances_are_supported_and_have_headroom(self):
        world = build_world()
        for region in REGION_NAMES:
            player = spawn_region(region)
            self.assertFalse(world.collides(player.x, player.y, player.z), region)
            self.assertTrue(world.collides(player.x, player.y, player.z - 0.05), region)
            self.assertGreater(player.z, 1)


if __name__ == "__main__":
    unittest.main()

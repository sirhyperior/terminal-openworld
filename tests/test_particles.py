"""World-space particles remain deterministic, bounded and correctly hidden."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import FIRE_STAFF, Fireball, FireBurst, WeaponPickup
from ascii3d.geometry import Camera
from ascii3d.palette import ARCANE, ASH, DUST, EMBER, UI_ACCENT
from ascii3d.particles import Particles
from ascii3d.player import Player
from ascii3d.shading import Ink, ink
from ascii3d.sound import EFFECTS
from ascii3d.world import GRASS, STONE, World


class ParticleTests(unittest.TestCase):
    def setUp(self):
        self.world = World.empty(64, 64, 32)
        self.player = Player(x=32.5, y=28.5, z=1)

    @staticmethod
    def buffers(width=120, height=35, depth=math.inf):
        return ([[' '] * width for _ in range(height)],
                [[depth] * width for _ in range(height)])

    @staticmethod
    def tokens(pixels):
        return [[(str(char), char.level, char.material, char.effects) if isinstance(char, Ink) else char
                 for char in row] for row in pixels]

    def draw(self, particles, seconds=1.25, width=120, height=35, depth=math.inf):
        pixels, depths = self.buffers(width, height, depth)
        particles.draw(pixels, depths, self.player, seconds, width * 0.575, 0.5)
        return pixels, depths

    def test_generic_world_has_no_ambient_field_and_disable_preserves_buffers(self):
        particles = Particles(self.world)
        pixels, _ = self.draw(particles)
        self.assertTrue(all(char == ' ' for row in pixels for char in row))
        self.assertEqual(particles.stats['ambient_candidates'], 0)
        self.world.combat.fireballs.append(Fireball(32.5, 33, 2.5, (1, 0, 0)))
        particles.enabled = False
        pixels, depths = self.buffers()
        before, before_depths = [row[:] for row in pixels], [row[:] for row in depths]
        particles.draw(pixels, depths, self.player, 2, 69, 0.5)
        self.assertEqual(pixels, before)
        self.assertEqual(depths, before_depths)
        self.assertEqual(particles.stats['particle_candidates'], 0)

    def test_same_pose_and_simulation_time_freeze_all_particle_metadata(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        particles = Particles(self.world)
        first, depths = self.draw(particles, seconds=1.25)
        later, _ = self.draw(particles, seconds=2.25)
        again, again_depths = self.draw(particles, seconds=1.25)
        self.assertGreater(particles.stats['particles_drawn'], 0)
        self.assertEqual(self.tokens(first), self.tokens(again))
        self.assertEqual(depths, again_depths)
        self.assertNotEqual(self.tokens(first), self.tokens(later))
        fresh, _ = self.draw(Particles(self.world), seconds=1.25)
        self.assertEqual(self.tokens(first), self.tokens(fresh))
        materials = {char.material for row in first for char in row if isinstance(char, Ink)}
        self.assertTrue(materials <= {DUST, ASH})

    def test_particle_world_positions_do_not_follow_camera_motion(self):
        self.world.combat.fireballs = [Fireball(32.5, 34, 2.5, (1, 0, 0))]
        captured = []
        original = Camera.project

        def observe(camera, x, y, z):
            captured.append((x, y, z))
            return original(camera, x, y, z)

        particles = Particles(self.world)
        with patch.object(Camera, 'project', observe):
            first, _ = self.draw(particles, seconds=0.8)
            first_points = captured[:]
            captured.clear()
            self.player.x += 0.5
            moved, _ = self.draw(particles, seconds=0.8)
        self.assertTrue(first_points)
        self.assertEqual(first_points, captured)
        self.assertNotEqual(self.tokens(first), self.tokens(moved))

    def test_removing_an_invisible_source_does_not_reseed_visible_trails(self):
        hidden = Fireball(32.5, 10, 2.5, (1, 0, 0))
        visible = Fireball(32.5, 34, 2.5, (1, 0, 0))
        self.world.combat.fireballs = [hidden, visible]
        particles = Particles(self.world)
        first, _ = self.draw(particles, seconds=0.8)
        self.world.combat.fireballs.remove(hidden)
        second, _ = self.draw(particles, seconds=0.8)
        self.assertEqual(self.tokens(first), self.tokens(second))

    def test_opaque_depths_hide_particles_even_when_surface_is_black(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        self.world.combat.fireballs = [Fireball(32.5, 34, 2.5, (1, 0, 0))]
        self.world.combat.bursts = [FireBurst(32.5, 34, 2.5, 0.12)]
        particles = Particles(self.world)
        pixels, depths = self.buffers(depth=0.1)
        pixels = [[ink(' ', 0, STONE)] * 120 for _ in range(35)]
        before = self.tokens(pixels)
        before_depths = [row[:] for row in depths]
        particles.draw(pixels, depths, self.player, 1, 69, 0.5)
        self.assertEqual(self.tokens(pixels), before)
        self.assertEqual(depths, before_depths)
        self.assertEqual(particles.stats['particles_drawn'], 0)
        self.assertGreater(particles.stats['particle_occluded'], 0)

    def test_particles_do_not_write_solid_depth_and_protect_labels_and_ui(self):
        self.world.combat.fireballs = [Fireball(32.5, 34, 2.5, (1, 0, 0))]
        particles = Particles(self.world)
        visible, depths = self.draw(particles)
        self.assertGreater(particles.stats['particles_drawn'], 0)
        self.assertTrue(all(math.isinf(value) for row in depths for value in row))
        for fill in ('L', ink('+', 15, UI_ACCENT)):
            pixels, depths = self.buffers()
            pixels = [[fill] * 120 for _ in range(35)]
            before = self.tokens(pixels)
            particles.draw(pixels, depths, self.player, 1, 69, 0.5)
            self.assertEqual(self.tokens(pixels), before)
            self.assertEqual(particles.stats['particles_drawn'], 0)
            self.assertGreater(particles.stats['particle_protected'], 0)

    def test_sparse_field_and_work_budget_do_not_grow_with_world_size(self):
        for size in (64, 512):
            world = World.empty(size, size, 32)
            world.outdoor_bounds = (0, 0, size, size)
            particles = Particles(world)
            pixels, depths = self.buffers(120, 35)
            with patch.object(world, 'surface_height', side_effect=AssertionError('whole-world terrain probe')):
                particles.draw(pixels, depths, self.player, 2, 69, 0.5)
            self.assertLessEqual(particles.stats['ambient_candidates'], Particles.MAX_AMBIENT_CANDIDATES)
            self.assertLessEqual(particles.stats['particle_candidates'], Particles.MAX_CANDIDATES)
            self.assertLessEqual(particles.stats['particles_drawn'], 70)
            self.assertLessEqual(particles.stats['particle_chunks'], Particles.MAX_CHUNKS)
            self.assertGreater(particles.stats['particles_drawn'], 0)
            if size == 64:
                expected = self.tokens(pixels)
            else:
                self.assertEqual(self.tokens(pixels), expected)

    def test_cache_eviction_recreates_the_same_world_anchored_field(self):
        particles = Particles(self.world)
        original = particles._chunk(4, 5, 1)
        for index in range(200):
            particles._chunk(index, index // 3, index % 4)
            self.assertLessEqual(len(particles._chunks), Particles.MAX_CHUNKS)
        self.assertNotIn((4, 5, 1), particles._chunks)
        self.assertEqual(particles._chunk(4, 5, 1), original)

    def test_many_effects_respect_shared_budget_and_small_viewports(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        self.world.combat.fireballs = [Fireball(32.5 + i * 0.02, 34, 2.5, (1, 0, 0)) for i in range(100)]
        self.world.combat.bursts = [FireBurst(32.5, 34, 2.5, 0.12) for _ in range(100)]
        self.world.combat.pickups = [WeaponPickup(32.5, 34, weapon=FIRE_STAFF) for _ in range(100)]
        for width, height in ((60, 15), (120, 35), (300, 115)):
            particles = Particles(self.world)
            pixels, _ = self.draw(particles, width=width, height=height)
            stats = particles.stats
            self.assertLessEqual(stats['particle_candidates'], stats['particle_budget'])
            self.assertLessEqual(stats['particle_budget'], Particles.MAX_CANDIDATES)
            self.assertLessEqual(stats['particles_drawn'], stats['particle_draw_budget'])
            self.assertLessEqual(stats['particle_draw_budget'], Particles.MAX_DRAWS)
            self.assertLessEqual(stats['particle_sources'], 8 + 8 + Particles.MAX_PICKUP_SOURCES)
            self.assertEqual(len(pixels), height)
            self.assertTrue(all(len(row) == width for row in pixels))

    def test_existing_gameplay_events_cover_sources_and_rendering_never_advances_them(self):
        combat = self.world.combat
        combat.held_item = WeaponPickup(0, 0, weapon=FIRE_STAFF)
        events = combat.attack(self.world, self.player)
        self.assertIn('fireball_cast', {event.name for event in events})
        self.assertTrue(all(event.name in EFFECTS for event in events))
        before = [(ball.x, ball.y, ball.z, ball.direction, ball.range_left) for ball in combat.fireballs]
        combat.bursts.append(FireBurst(32.5, 34, 2.5, 0.12))
        combat.pickups.append(WeaponPickup(32.5, 34))
        particles = Particles(self.world)
        self.draw(particles, seconds=3)
        self.assertEqual(before, [(ball.x, ball.y, ball.z, ball.direction, ball.range_left)
                                  for ball in combat.fireballs])
        self.assertEqual(combat.bursts[0].remaining, 0.12)
        self.assertFalse(combat.pickups[0].collected)
        self.assertTrue(all(event.name in EFFECTS for event in events))


if __name__ == '__main__':
    unittest.main()

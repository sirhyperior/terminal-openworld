"""World-space particles remain deterministic, bounded and correctly hidden."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import FIRE_STAFF, Fireball, FireBurst, WeaponPickup
from ascii3d.geometry import Camera
from ascii3d.palette import ARCANE, ASH, DUST, EMBER, FIRE, UI_ACCENT
from ascii3d.particles import Particles
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.shading import Ink, ink
from ascii3d.sound import EFFECTS
from ascii3d.world import GRASS, STONE, World, build_world


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

    def test_same_local_gust_carries_and_lights_ash_while_dust_stays_quiet(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        particles = Particles(self.world)
        fields = []
        # Hold the simulation time fixed so the local wind is the only input
        # changing either the cluster positions or the ash's silver tones.
        motes = ((32.1, 34, 2.4, 0.6, 0), (33.2, 34, 2.4, 1.3, 1))
        with patch.object(particles, '_chunk', return_value=motes):
            for wind in ((0, 0), (0.9, 0.2)):
                pixels, depths = self.buffers()
                particles.draw(pixels, depths, self.player, 1.25, 69, 0.5,
                               wind_at=lambda x, y: wind)
                fields.append({(x, y): cell for y, row in enumerate(pixels) for x, cell in enumerate(row)
                               if isinstance(cell, Ink)})
        calm, gust = fields
        self.assertNotEqual(set(calm), set(gust))
        self.assertGreater(max(cell.level for cell in gust.values() if cell.material == ASH),
                           max(cell.level for cell in calm.values() if cell.material == ASH))
        self.assertLessEqual(max(cell.level for cell in gust.values() if cell.material == DUST), 6)

    def test_eye_band_stays_populated_across_heights_with_bounded_inspection(self):
        world = World.empty(128, 128, 32)
        world.outdoor_bounds = (0, 0, 128, 128)
        eye_band = total = 0
        for x in (25.5, 32.5, 40.5, 48.5):
            for z in (1, 2, 3, 4):
                for yaw in (0, math.pi / 2, math.pi, math.pi * 1.5):
                    player = Player(x=x, y=40.5, z=z, yaw=yaw)
                    pixels, depths = self.buffers()
                    particles = Particles(world)
                    particles.draw(pixels, depths, player, 1.25, 69, 0.5)
                    eye_band += sum(cell != ' ' for row in pixels[14:21] for cell in row)
                    total += particles.stats['particles_drawn']
                    self.assertLessEqual(particles.stats['ambient_candidates'], 65)
                    self.assertLessEqual(particles.stats['ambient_samples'],
                                         particles.stats['ambient_sample_budget'])
                    self.assertLessEqual(particles.stats['ambient_sample_budget'],
                                         Particles.MAX_AMBIENT_SAMPLES)
                    self.assertLessEqual(particles.stats['particles_drawn'],
                                         particles.stats['particle_draw_budget'])
        self.assertGreater(eye_band, total * 0.35)
        self.assertGreater(total, 64 * 30)

    def test_real_indoor_and_open_views_have_visible_readable_motes(self):
        world = build_world()
        renderer = Renderer(world)
        for x, y, minimum in ((128.5, 76.5, 30), (128.5, 111.5, 20),
                              (128.5, 88.5, 30), (72.5, 247.5, 25)):
            with self.subTest(camera=(x, y)):
                pixels = renderer.scene(Player(x=x, y=y, z=1), 120, 40, 1.25)
                motes = [cell for row in pixels for cell in row
                         if isinstance(cell, Ink) and cell.material in (DUST, ASH)]
                self.assertGreaterEqual(len(motes), minimum)
                bodies = [cell for cell in motes if cell != '*']
                sparks = [cell for cell in motes if cell == '*']
                self.assertLessEqual(sum(cell.level for cell in bodies) / len(bodies), 6.5)
                self.assertTrue(all(cell.level <= 9 for cell in bodies))
                self.assertLessEqual(len(sparks), 2)
                self.assertTrue(all(14 <= cell.level <= 15 for cell in sparks))
                self.assertTrue(all(str(cell) in ('.', "'", '*') for cell in motes))

    def test_only_selected_ash_glints_while_dust_and_other_ash_keep_steady_bodies(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        particles = Particles(self.world)
        motes = ((32, 34, 2.4, math.pi / 2, 0),
                 (33, 34, 2.4, 1.1, 96),
                 (31, 34, 2.4, math.pi / 2, 1))
        levels = []
        glyphs = []
        with patch.object(particles, '_chunk', return_value=motes):
            for seconds in (0, math.pi / (2 * 0.26)):
                pixels, depths = self.buffers()
                particles.draw(pixels, depths, self.player, seconds, 69, 0.5,
                               wind_at=lambda x, y: (0.9, 0.2))
                levels.append({material: sorted(cell.level for row in pixels for cell in row
                                                if isinstance(cell, Ink) and cell.material == material)
                               for material in (ASH, DUST)})
                glyphs.append([str(cell) for row in pixels for cell in row if isinstance(cell, Ink)])
        self.assertEqual(levels[0][DUST], levels[1][DUST])
        self.assertEqual(levels[0][ASH][0], levels[1][ASH][0])
        self.assertGreater(levels[0][ASH][1], levels[1][ASH][1])
        self.assertEqual(glyphs[0].count('*'), 1)
        self.assertNotIn('*', glyphs[1])
        self.assertNotIn(':', glyphs[0])
        self.assertNotIn('+', glyphs[0])

    def test_many_eligible_ash_seeds_have_only_two_brief_bright_accents(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        particles = Particles(self.world)
        motes = tuple((30 + index * 0.12, 34, 2.4, math.pi / 2, 0) for index in range(30))
        with patch.object(particles, '_chunk', return_value=motes):
            for seconds, expected in ((0, 2), (0.25, 0)):
                pixels, depths = self.buffers()
                particles.draw(pixels, depths, self.player, seconds, 69, 0.5,
                               wind_at=lambda x, y: (0.9, 0.2))
                ash = [cell for row in pixels for cell in row
                       if isinstance(cell, Ink) and cell.material == ASH]
                sparks = [cell for cell in ash if cell == '*']
                self.assertEqual(len(sparks), expected)
                self.assertEqual(particles.stats['ambient_glints'], expected)
                self.assertTrue(all(14 <= cell.level <= 15 for cell in sparks))
                self.assertTrue(all(cell.level <= 9 for cell in ash if cell != '*'))

    def test_extra_eye_motes_retain_world_positions_when_camera_height_changes(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        particles = Particles(self.world)
        # All chunks expose the same controlled world motes. Ordinary motes
        # retain their broad height range; only the extras use the eye band.
        ordinary = (32.5, 34, 4, 0, 1)
        extra = (32.5, 34, self.player.eye_z, 0, 0)
        values = (ordinary,) * Particles.MOTES_PER_CHUNK + (extra,)
        fields = []
        original = Camera.project

        def observe(camera, x, y, z):
            fields[-1].add((x, y, z))
            return original(camera, x, y, z)

        with patch.object(particles, '_chunk', return_value=values), patch.object(Camera, 'project', observe):
            for rise in (0, 0.3):
                self.player.z = 1 + rise
                fields.append(set())
                self.draw(particles, seconds=0)
        self.assertEqual(fields[0], fields[1])
        self.assertEqual(len(fields[0]), 2)

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

    def test_bright_ambient_motes_never_overpaint_even_dim_spellfire(self):
        self.world.outdoor_bounds = (0, 0, 64, 64)
        particles = Particles(self.world)
        for material in (FIRE, ARCANE):
            pixels, depths = self.buffers()
            pixels = [[ink('*', 1, material)] * 120 for _ in range(35)]
            before = self.tokens(pixels)
            particles.draw(pixels, depths, self.player, 1, 69, 0.5)
            self.assertEqual(self.tokens(pixels), before)
            self.assertEqual(particles.stats['particles_drawn'], 0)

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

import math
import unittest
from unittest.mock import patch

from ascii3d.app import spawn_player
from ascii3d.player import Player
from ascii3d.renderer import Renderer, _river_ripple
from ascii3d.scenery import Scenery, Wind
from ascii3d.map_expansion import FIRST_BRIDGE_BOUNDS, EAST_BRIDGE_BOUNDS
from ascii3d.terrain import NEW_BRIDGES
from ascii3d.world import (AIR, BRIDGE, FLOOR, GRASS, RIVERBED_LEVEL, WATER, WATER_LEVEL,
                           World, build_world, river_center)


def advance(player, world, seconds, keys=(), jump=False):
    for tick in range(round(seconds * 120)):
        player.update(world, set(keys), 1 / 120, jump=jump and tick == 0)


class OutdoorMovementTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()

    def test_north_gate_connects_fortress_and_meadow(self):
        door = next(door for door in self.world.doors if door.name == "north castle gate")
        door.openness, door.target_open = 1, True
        player = Player(x=55.5, y=71.0)
        advance(player, self.world, 2.5, {"w"})
        self.assertGreater(player.y, 79)
        self.assertAlmostEqual(player.z, 1, places=5)
        self.assertFalse(self.world.collides(player.x, player.y, player.z))

    def test_entire_bridge_is_walkable_without_jumping(self):
        player = Player(x=24.5, y=78.5)
        for _ in range(840):
            player.update(self.world, {"w"}, 1 / 120)
            self.assertAlmostEqual(player.z, 1, places=5)
            self.assertFalse(player.in_water)
        self.assertGreater(player.y, 101)

    def test_river_continues_on_both_sides_of_bridge(self):
        for x in range(self.world.width):
            y = math.floor(river_center(x + 0.5))
            expected = BRIDGE if any(bounds[0] <= x < bounds[2] for bounds in
                                    (FIRST_BRIDGE_BOUNDS, EAST_BRIDGE_BOUNDS, *NEW_BRIDGES)) else WATER
            self.assertEqual(self.world.get(x, y, 0), expected)
        self.assertIn("BRIDGE", self.world.area(24.5, 86))

    def test_stepping_into_water_sinks_to_bed_and_current_drifts_east(self):
        player = Player(x=6.5, y=river_center(6.5) - 7)
        for _ in range(360):
            player.update(self.world, {"w"}, 1 / 120)
        self.assertTrue(player.in_water)
        self.assertAlmostEqual(player.z, RIVERBED_LEVEL, places=5)
        before = player.x
        advance(player, self.world, 1)
        self.assertGreater(player.x, before + 0.4)
        self.assertLess(player.z, WATER_LEVEL)
        self.assertFalse(self.world.collides(player.x, player.y, player.z))

    def test_can_jump_out_of_river_onto_bank(self):
        x = 7.5
        wet_rows = [y for y in range(self.world.depth) if self.world.get(int(x), y, 0) == WATER]
        player = Player(x=x, y=max(wet_rows) + 0.6, z=RIVERBED_LEVEL)
        advance(player, self.world, 0.55, {"w"}, jump=True)
        advance(player, self.world, 1)
        self.assertGreater(player.y, max(wet_rows) + 1)
        self.assertAlmostEqual(player.z, 1, places=4)
        self.assertFalse(player.in_water)

    def test_bridge_rails_have_collision(self):
        player = Player(x=24.5, y=86.5, yaw=0)
        advance(player, self.world, 2, {"w", "shift"})
        self.assertLessEqual(player.x, 27 - Player.RADIUS + 1e-6)
        self.assertGreater(player.x, 26.7)


class AnimatedSceneryTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()
        self.renderer = Renderer(self.world)

    def test_blades_are_seeded_and_only_grow_on_clear_grass(self):
        other = Scenery(self.world)
        for cy in range(7, 10):
            for cx in range(2, 5):
                self.renderer.scenery.grass_chunk(cx, cy)
                other.grass_chunk(cx, cy)
        blades = self.renderer.scenery.blades
        self.assertGreater(len(blades), 1000)
        self.assertEqual(blades, other.blades)
        for blade in blades:
            self.assertEqual(self.world.get(int(blade.x), int(blade.y), int(blade.z) - 1), GRASS)
            self.assertEqual(self.world.get(int(blade.x), int(blade.y), int(blade.z)), AIR)

    def test_wind_is_deterministic_spatially_varied_and_continuous(self):
        wind = Wind(self.world.outdoor_bounds)
        gusts = wind.gusts(2.5)
        self.assertEqual(gusts, wind.gusts(2.5))
        first = wind.sample(6, 35, 2.5, gusts)
        self.assertNotEqual(first, wind.sample(28, 55, 2.5, gusts))
        nearby_time = wind.sample(6, 35, 2.501, wind.gusts(2.501))
        self.assertLess(math.dist(first, nearby_time), 0.01)
        self.assertNotEqual(gusts, wind.gusts(12))
        # A gust can reseed without an abrupt bend at its lifetime boundary.
        for boundary in (4.8, 9.6):
            before = wind.sample(12, 40, boundary - 0.0001, wind.gusts(boundary - 0.0001))
            after = wind.sample(12, 40, boundary + 0.0001, wind.gusts(boundary + 0.0001))
            self.assertLess(math.dist(before, after), 0.001)

    def test_stationary_view_animates_and_same_time_is_repeatable(self):
        player = spawn_player(True)
        first = self.renderer.scene(player, 100, 32, time_seconds=0)
        later = self.renderer.scene(player, 100, 32, time_seconds=2)
        self.assertNotEqual(first, later)
        self.assertEqual(first, self.renderer.scene(player, 100, 32, time_seconds=0))
        self.assertTrue(any(char in "/\\|'" for row in first for char in row))

    def test_water_itself_flows_with_no_grass(self):
        world = World.empty(20, 20, 8)
        world.box(0, 0, 0, 20, 20, 1, WATER)
        renderer = Renderer(world)
        player = Player(x=8.5, y=5.5, pitch=-0.3)
        first = renderer.scene(player, 80, 28, time_seconds=0)
        later = renderer.scene(player, 80, 28, time_seconds=1)
        self.assertNotEqual(first, later)
        self.assertTrue(any(char == "~" for row in first for char in row))

    def test_water_surface_is_below_bank_height(self):
        player = Player(x=7.5, y=river_center(7.5), pitch=-0.4)
        scene = self.renderer.scene(player, 91, 31)
        # This view is over water, not inside a solid voxel wall.
        self.assertTrue(any(char in "~-=:." for char in scene[20]))
        self.assertFalse(self.world.collides(player.x, player.y, RIVERBED_LEVEL))

    def test_river_strokes_turn_with_the_camera_instead_of_staying_horizontal(self):
        world = World.empty(120, 120, 8)
        world.box(0, 0, 0, 120, 120, 1, WATER)
        renderer = Renderer(world)
        player = Player(x=24.5, y=river_center(24.5), yaw=0, pitch=-0.35)
        downstream = renderer.scene(player, 80, 28, time_seconds=0.7)
        self.assertGreater(sum(char in "|/\\" for row in downstream for char in row), 50)
        player.yaw = math.pi / 2
        across = renderer.scene(player, 80, 28, time_seconds=0.7)
        self.assertGreater(sum(char in "-~" for row in across for char in row), 50)
        player.yaw = math.pi
        upstream = renderer.scene(player, 80, 28, time_seconds=0.7)
        self.assertGreater(sum(char in "|/\\" for row in upstream for char in row), 50)

    def test_straight_current_converges_in_perspective_and_stays_oriented_far_away(self):
        world = World.empty(80, 80, 8)
        world.box(0, 0, 0, 80, 80, 1, WATER)
        world.current = lambda x: (0.55, 0.0)
        renderer = Renderer(world)
        player = Player(x=24.5, y=43.5, yaw=0, pitch=-0.35)
        scene = renderer.scene(player, 80, 28, time_seconds=0.7)
        self.assertTrue(any(char == "/" for row in scene[20:] for char in row[5:24]))
        self.assertTrue(any(char == "\\" for row in scene[20:] for char in row[56:75]))
        self.assertTrue(any(char == "|" for row in scene[20:] for char in row[38:42]))
        player.pitch = -0.15
        # Make a crest visible on every sample so this checks orientation,
        # independently of whether a particular distant texel is a trough.
        with patch("ascii3d.renderer._river_ripple", return_value=1.0):
            distant = renderer.scene(player, 80, 28, time_seconds=0.7)
        # This scanline hits the water roughly 43 units ahead, beyond the
        # simplified texture's 24-unit boundary. It must keep its orientation.
        self.assertTrue(any(char in "|/\\" for char in distant[11]))

    def test_water_stroke_orientation_uses_the_actual_current(self):
        world = World.empty(40, 60, 8)
        world.box(0, 0, 0, 40, 60, 1, WATER)
        renderer = Renderer(world)
        player = Player(x=15.5, y=35.5, yaw=0, pitch=-0.35)
        with patch("ascii3d.renderer._river_ripple", return_value=1.0):
            world.current = lambda x: (0.55, 0.0)
            along = renderer.scene(player, 80, 28)
            world.current = lambda x: (0.0, 0.55)
            across = renderer.scene(player, 80, 28)
        self.assertEqual(along[24][40], "|")
        self.assertEqual(across[24][40], "~")

    def test_water_pattern_advects_downstream_around_bends(self):
        for x in (4.5, 15.5, 31.5, 54.5):
            for cross in (-1.5, 0, 1.5):
                with self.subTest(x=x, cross=cross):
                    y = river_center(x) + cross
                    moved_x = x + 0.9 * 0.75
                    moved_y = y + river_center(moved_x) - river_center(x)
                    self.assertAlmostEqual(_river_ripple(x, y, 2),
                                           _river_ripple(moved_x, moved_y, 2.75))

    def test_water_streaks_vary_less_along_the_channel_than_across_it(self):
        along_energy = across_energy = 0
        for x in range(2, 62, 3):
            for index in range(-5, 6):
                y = river_center(x) + index * 0.4
                base = _river_ripple(x, y, 1.2)
                along = _river_ripple(x + 0.05, y + river_center(x + 0.05) - river_center(x), 1.2)
                across = _river_ripple(x, y + 0.05, 1.2)
                along_energy += (along - base) ** 2
                across_energy += (across - base) ** 2
        self.assertLess(along_energy, across_energy * 0.30)

    def test_water_animation_repeats_at_frozen_time_after_turning(self):
        world = World.empty(40, 60, 8)
        world.box(0, 0, 0, 40, 60, 1, WATER)
        renderer = Renderer(world)
        player = Player(x=15.5, y=35.5, yaw=0, pitch=-0.35)
        frozen = renderer.scene(player, 80, 28, time_seconds=2)
        self.assertNotEqual(frozen, renderer.scene(player, 80, 28, time_seconds=3))
        player.yaw = 0.8
        renderer.scene(player, 80, 28, time_seconds=2)
        player.yaw = 0
        self.assertEqual(frozen, renderer.scene(player, 80, 28, time_seconds=2))

    def test_animated_water_does_not_show_through_a_wall(self):
        world = World.empty(20, 30, 8)
        world.box(0, 0, 0, 20, 30, 1, WATER)
        world.box(0, 0, 0, 20, 8, 1, FLOOR)
        world.box(0, 7, 1, 20, 8, 8)
        renderer = Renderer(world)
        player = Player(x=10.5, y=4.5, pitch=-0.2)
        self.assertEqual(renderer.scene(player, 80, 28, time_seconds=0),
                         renderer.scene(player, 80, 28, time_seconds=2))

    def test_scenery_is_hidden_behind_solid_walls(self):
        world = World.empty(16, 20, 9)
        world.outdoor_bounds = (1, 1, 15, 19)
        world.box(0, 0, 0, 16, 20, 1, GRASS)
        world.box(0, 0, 0, 16, 8, 1, FLOOR)
        world.box(0, 7, 1, 16, 8, 8)
        renderer = Renderer(world)
        # Keep only tufts behind the wall; no foreground grass can animate.
        for cy in range(5):
            for cx in range(4):
                renderer.scenery.grass_chunk(cx, cy)
        renderer.scenery.blades = [blade for blade in renderer.scenery.blades if blade.y > 8]
        player = Player(x=8.5, y=4.5)
        first = renderer.scene(player, 80, 26, time_seconds=0)
        self.assertEqual(first, renderer.scene(player, 80, 26, time_seconds=2))
        self.assertFalse(any(char in "/\\|'" for row in first for char in row))

    def test_scaled_map_shows_bridge_river_grass_at_small_sizes(self):
        for width, height in ((60, 20), (80, 24), (120, 40), (180, 64)):
            with self.subTest(size=(width, height)):
                plain = self.renderer.frame(spawn_player(True), width, height)
                mapped = self.renderer.frame(spawn_player(True), width, height, show_map=True)
                self.assertNotEqual(plain, mapped)
                self.assertEqual(len(mapped), height)
                self.assertTrue(all(len(line) == width for line in mapped))
                self.assertTrue(any("~" in row for row in mapped))
                self.assertTrue(all(32 <= ord(c) < 127 for row in mapped for c in row))


if __name__ == "__main__":
    unittest.main()

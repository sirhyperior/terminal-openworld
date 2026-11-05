import math
import unittest

from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import AIR, CRATE, FLOOR, World, build_world


def flat_world() -> World:
    world = World.empty(32, 32, 10)
    world.box(0, 0, 0, 32, 32, 1, FLOOR)
    return world


def advance(player: Player, world: World, seconds: float, keys=(), jump=False):
    for frame in range(round(seconds * 120)):
        player.update(world, set(keys), 1 / 120, jump=jump and frame == 0)


class MovementTests(unittest.TestCase):
    def setUp(self):
        self.world = flat_world()
        self.player = Player(x=8.5, y=12.5, yaw=0.0)

    def test_walk_and_sprint_cover_correct_distances(self):
        advance(self.player, self.world, 1, {"w"})
        self.assertAlmostEqual(self.player.x, 8.5 + Player.WALK_SPEED, places=5)
        self.player = Player(x=8.5, y=12.5, yaw=0.0)
        advance(self.player, self.world, 1, {"w", "shift"})
        self.assertAlmostEqual(self.player.x, 8.5 + Player.RUN_SPEED, places=5)

    def test_diagonal_movement_has_same_speed(self):
        advance(self.player, self.world, 1, {"w", "d"})
        distance = math.hypot(self.player.x - 8.5, self.player.y - 12.5)
        self.assertAlmostEqual(distance, Player.WALK_SPEED, places=5)

    def test_strafing_and_turning_match_camera(self):
        self.player.yaw = math.pi / 2
        advance(self.player, self.world, 1, {"d"})
        self.assertGreater(self.player.x, 8.5)
        self.assertAlmostEqual(self.player.y, 12.5)
        advance(self.player, self.world, 0.5, {"right"})
        self.assertLess(self.player.yaw, math.pi / 2)

    def test_sprint_does_not_tunnel_through_wall_at_large_dt(self):
        self.world.box(10, 0, 1, 11, 32, 6)
        for _ in range(20):
            self.player.update(self.world, {"w", "shift"}, 0.1)
        self.assertLessEqual(self.player.x, 10 - Player.RADIUS + 1e-6)
        self.assertGreater(self.player.x, 9.7)

    def test_player_slides_along_wall(self):
        self.world.box(10, 0, 1, 11, 32, 6)
        advance(self.player, self.world, 1, {"w", "d", "shift"})
        self.assertLessEqual(self.player.x, 10 - Player.RADIUS + 1e-6)
        self.assertLess(self.player.y, 9.0)

    def test_jump_rises_and_lands_without_sinking(self):
        highest = self.player.z
        for frame in range(240):
            self.player.update(self.world, set(), 1 / 120, jump=frame == 0)
            highest = max(highest, self.player.z)
            self.assertFalse(self.world.collides(self.player.x, self.player.y, self.player.z))
        self.assertGreater(highest, 2.2)
        self.assertLess(highest, 2.4)
        self.assertAlmostEqual(self.player.z, 1, places=5)
        self.assertTrue(self.player.grounded)

    def test_jump_cannot_be_retriggered_in_air(self):
        advance(self.player, self.world, 0.15, jump=True)
        current_speed = self.player.vertical_speed
        self.player.update(self.world, set(), 1 / 120, jump=True)
        self.assertLess(self.player.vertical_speed, current_speed)

    def test_head_collision_under_ceiling(self):
        self.world.box(1, 1, 4, 31, 31, 5)
        maximum = 1.0
        for frame in range(180):
            self.player.update(self.world, set(), 1 / 120, jump=frame == 0)
            maximum = max(maximum, self.player.z)
            self.assertLessEqual(self.player.z + Player.HEIGHT, 4.000001)
        self.assertGreater(maximum, 2.25)
        self.assertTrue(self.player.grounded)
        self.assertAlmostEqual(self.player.z, 1, places=5)

    def test_jump_onto_low_wall_then_fall_off(self):
        self.player.x = 8.0
        self.world.box(9, 11, 1, 12, 14, 2, CRATE)
        advance(self.player, self.world, 0.55, {"w"}, jump=True)
        advance(self.player, self.world, 0.7)
        self.assertGreater(self.player.x, 9.3)
        self.assertAlmostEqual(self.player.z, 2, places=4)
        self.assertTrue(self.player.grounded)
        advance(self.player, self.world, 1.2, {"w"})
        advance(self.player, self.world, 1)
        self.assertAlmostEqual(self.player.z, 1, places=4)

    def test_circle_collider_can_pass_near_corner(self):
        self.world.box(6, 6, 1, 7, 7, 3)
        self.assertFalse(self.world.collides(5.83, 5.83, 1))
        self.assertTrue(self.world.collides(5.86, 5.86, 1))

    def test_player_stays_within_world(self):
        self.player.x = 0.25
        advance(self.player, self.world, 1, {"s", "shift"})
        self.assertGreaterEqual(self.player.x, Player.RADIUS)

    def test_zero_dt_does_not_change_position(self):
        position = (self.player.x, self.player.y, self.player.z)
        self.player.update(self.world, {"w", "shift"}, 0)
        self.assertEqual((self.player.x, self.player.y, self.player.z), position)
        self.assertTrue(self.player.grounded)


class WorldAndRenderingTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()
        self.renderer = Renderer(self.world)

    def test_spawn_and_open_doorways_are_walkable(self):
        player = Player()
        self.assertFalse(self.world.collides(player.x, player.y, player.z))
        for door in self.world.doors:
            door.openness = 1.0
            door.target_open = True
        for x, y in ((14.5, 10.5), (10.5, 13.5), (21.5, 13.5), (15.5, 23.5)):
            with self.subTest(door=(x, y)):
                self.assertFalse(self.world.collides(x, y, 1))
        self.assertTrue(self.world.collides(11.5, 10.5, 1))

    def test_arch_and_roof_exist_above_walkable_space(self):
        self.assertEqual(self.world.get(14, 10, 2), AIR)
        self.assertNotEqual(self.world.get(14, 10, 4), AIR)
        self.assertNotEqual(self.world.get(5, 15, 6), AIR)

    def test_default_frame_is_rectangular_plain_ascii(self):
        frame = self.renderer.frame(Player(), 120, 40)
        self.assertEqual(len(frame), 40)
        self.assertTrue(all(len(row) == 120 for row in frame))
        self.assertTrue(all(32 <= ord(char) < 127 for row in frame for char in row))
        self.assertGreater(len(set("".join(frame[2:-3]))), 5)

    def test_real_vertical_perspective_changes_when_jumping(self):
        player = Player()
        grounded = self.renderer.scene(player, 90, 30)
        player.z += 1.0
        airborne = self.renderer.scene(player, 90, 30)
        self.assertNotEqual(grounded, airborne)
        # An overhead lintel appears in the higher camera's sight line.
        self.assertNotEqual(grounded[12], airborne[12])

    def test_pitch_and_yaw_change_view(self):
        player = Player()
        original = self.renderer.scene(player, 80, 25)
        player.pitch = 0.4
        self.assertNotEqual(original, self.renderer.scene(player, 80, 25))
        player.pitch, player.yaw = 0, 0
        self.assertNotEqual(original, self.renderer.scene(player, 80, 25))

    def test_ray_hits_overhead_geometry(self):
        world = flat_world()
        renderer = Renderer(world)
        player = Player(x=12.5, y=12.5)
        open_sky = renderer.scene(player, 61, 31)
        self.assertEqual(open_sky[0][30], " ")
        world.box(1, 1, 5, 31, 31, 6)
        roof = renderer.scene(player, 61, 31)
        self.assertNotEqual(roof[0][30], " ")

    def test_resize_and_overlays_stay_in_bounds(self):
        for width, height in ((1, 1), (40, 12), (60, 20), (80, 24), (120, 40), (180, 64)):
            for help_open in (False, True):
                with self.subTest(size=(width, height), help=help_open):
                    frame = self.renderer.frame(Player(), width, height, show_map=True, help_open=help_open)
                    self.assertEqual(len(frame), height)
                    self.assertTrue(all(len(line) == width for line in frame))


if __name__ == "__main__":
    unittest.main()

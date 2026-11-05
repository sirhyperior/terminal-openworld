import math
import unittest

from ascii3d.door_render import draw_doors
from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import FLOOR, World, build_world


class DoorTests(unittest.TestCase):
    def setUp(self):
        self.world = build_world()
        self.player = Player(x=14.5, y=8.2)

    def advance(self, seconds, keys=()):
        events = []
        for _ in range(round(seconds * 120)):
            self.player.update(self.world, set(keys), 1 / 120)
            events.extend(self.world.update_doors(self.player, 1 / 120))
        return events

    def test_closed_doors_stop_walking_and_sprinting(self):
        self.advance(1, {"w", "shift"})
        self.assertLess(self.player.y, 10.5 - self.player.RADIUS)
        self.assertGreater(self.player.y, 10.1)

    def test_open_and_walk_through_then_close_from_other_side(self):
        self.assertEqual(self.world.interact(self.player).name, "door_open")
        self.advance(0.7)
        self.assertEqual(self.world.doors[0].openness, 1)
        self.advance(1.3, {"w"})
        self.assertGreater(self.player.y, 12.4)
        self.player.yaw = -math.pi / 2
        self.assertEqual(self.world.interact(self.player).name, "door_close")
        self.advance(0.7)
        self.assertEqual(self.world.doors[0].openness, 0)

    def test_interaction_requires_reach_facing_and_line_of_sight(self):
        self.world.combat.pickups.clear()  # Isolate the door targeting contract.
        self.player.y = 4.5
        self.assertIsNone(self.world.interaction_target(self.player))
        self.player.y = 8.2
        self.player.yaw = -math.pi / 2
        self.assertIsNone(self.world.interaction_target(self.player))
        self.player.yaw = math.pi / 2
        self.assertIs(self.world.interaction_target(self.player), self.world.doors[0])
        self.world.box(12, 9, 1, 17, 10, 4)
        self.assertIsNone(self.world.interaction_target(self.player))

    def test_closing_door_reverses_before_crushing_player(self):
        door = self.world.doors[0]
        door.openness, door.target_open = 1.0, False
        self.player.y = 10.5
        events = self.advance(1)
        self.assertIn("door_blocked", [event.name for event in events])
        self.assertTrue(door.target_open)
        self.assertFalse(self.world.collides(self.player.x, self.player.y, self.player.z))
        self.assertEqual(sum(event.name == "door_blocked" for event in events), 1)

    def test_opening_leaf_stops_safely_if_player_is_in_swing(self):
        door = self.world.doors[0]
        self.player.x, self.player.y = 12.4, 12.0
        door.target_open = True
        events = self.advance(1)
        self.assertLess(door.openness, 1)
        self.assertFalse(self.world.collides(self.player.x, self.player.y, self.player.z))
        self.assertEqual(sum(event.name == "door_blocked" for event in events), 1)

    def test_e_does_not_turn_player_and_target_shows_prompt(self):
        yaw = self.player.yaw
        self.player.update(self.world, {"e"}, 1 / 60)
        self.assertEqual(self.player.yaw, yaw)
        frame = Renderer(self.world).frame(self.player, 100, 34)
        self.assertIn("[E] Open courtyard doors", "\n".join(frame))

    def test_resuming_a_blocked_swing_emits_a_fresh_creak_event(self):
        door = self.world.doors[0]
        self.player.x, self.player.y = 12.4, 12.0
        door.target_open = True
        self.advance(1)
        self.player.x, self.player.y = 14.5, 8.2
        events = self.advance(0.7)
        self.assertEqual(door.openness, 1)
        self.assertEqual(sum(event.name == "door_open" for event in events), 1)

    def test_panels_animate_without_mutating_static_voxels_or_cache_revision(self):
        before, revision = bytes(self.world.cells), self.world.revision
        self.world.interact(self.player)
        self.advance(0.2)
        self.assertGreater(self.world.doors[0].openness, 0)
        self.assertLess(self.world.doors[0].openness, 1)
        self.assertEqual(before, bytes(self.world.cells))
        self.assertEqual(revision, self.world.revision)

    def test_closed_open_and_half_open_are_distinct_views(self):
        renderer = Renderer(self.world)
        closed = renderer.scene(self.player, 90, 28)
        self.world.doors[0].openness = 0.5
        halfway = renderer.scene(self.player, 90, 28)
        self.world.doors[0].openness = 1
        opened = renderer.scene(self.player, 90, 28)
        self.assertNotEqual(closed, halfway)
        self.assertNotEqual(halfway, opened)

    def test_doors_are_occluded_by_architecture(self):
        world = World.empty(20, 20, 10)
        world.box(0, 0, 0, 20, 20, 1, FLOOR)
        world.box(0, 7, 1, 20, 8, 10)
        player = Player(x=8.5, y=4.5)
        before = Renderer(world).scene(player, 80, 28)
        world.doors.append(Door("hidden", 7, 11.5, 3))
        self.assertEqual(before, Renderer(world).scene(player, 80, 28))

    def test_fast_door_planes_match_physical_ray_boxes(self):
        world = World.empty(20, 20, 10)
        door = Door("test", 7, 9.5, 3)
        world.doors.append(door)
        player = Player(x=8.5, y=4.5)
        width, height, focal = 80, 28, 46.0
        for openness in (0.0, 0.45, 1.0):
            for yaw in (1.3, math.pi / 2, 1.85):
                door.openness, player.yaw = openness, yaw
                pixels = [[" "] * width for _ in range(height)]
                depths = [[math.inf] * width for _ in range(height)]
                draw_doors(world, pixels, depths, player, focal, 0.5)
                for y in range(1, height, 3):
                    for x in range(1, width, 3):
                        u, v = (x + 0.5 - width / 2) / focal, (height / 2 - y - 0.5) / (focal * 0.5)
                        ray = (math.cos(yaw) + u * math.sin(yaw), math.sin(yaw) - u * math.cos(yaw), v)
                        hits = [panel.ray_hit((player.x, player.y, player.eye_z), ray) for panel in door.panels]
                        expected = min((hit[0] for hit in hits if hit), default=math.inf)
                        actual = depths[y][x]
                        self.assertTrue(actual == expected or math.isclose(actual, expected, abs_tol=1e-7),
                                        (openness, yaw, x, y, expected, actual))


if __name__ == "__main__":
    unittest.main()

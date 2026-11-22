import math
from textwrap import wrap
import unittest

from ascii3d.app import spawn_player, spawn_region
from ascii3d.combat import SWORD, WeaponPickup
from ascii3d.dialogue import CHARACTERS_PER_SECOND, TURN_SECONDS, Conversation
from ascii3d.doors import Door
from ascii3d.events import GameEvent
from ascii3d.npcs import NPC
from ascii3d.player import Player
from ascii3d.world import FLOOR, World, build_world


class NPCTargetingTests(unittest.TestCase):
    def setUp(self):
        self.world = World.empty(16, 16, 8)
        self.world.box(0, 0, 0, 16, 16, 1, FLOOR)
        self.npc = NPC("Traveling keeper", 8.5, 7.0, 1.0, -math.pi / 2, ("Good evening.",))
        self.world.npcs.append(self.npc)
        self.player = Player(8.5, 5.3, 1.0)

    def test_shared_dispatch_reports_resident_identity_and_dialogue_cue(self):
        selected = []
        self.assertIs(self.world.interaction_target(self.player), self.npc)
        self.assertEqual(self.world.interact(self.player, on_talk=selected.append),
                         [GameEvent("dialogue_start", self.npc.x, self.npc.y)])
        self.assertEqual(selected, [self.npc])

    def test_dialogue_requires_reach_aim_and_clear_sight(self):
        selected = []
        for y, yaw, pitch in ((3.5, math.pi / 2, 0.0), (5.3, 0.0, 0.0), (5.3, math.pi / 2, 0.62)):
            with self.subTest(y=y, yaw=yaw, pitch=pitch):
                self.player.y, self.player.yaw, self.player.pitch = y, yaw, pitch
                self.assertEqual(self.world.interact(self.player, on_talk=selected.append),
                                 [GameEvent("interaction_miss")])
        self.player.pitch = 0.0
        self.world.box(8, 6, 1, 9, 7, 4)
        self.assertEqual(self.world.interact(self.player, on_talk=selected.append),
                         [GameEvent("interaction_miss")])
        self.assertFalse(selected)

    def test_door_and_resident_share_nearest_target_ordering(self):
        door = Door("front gate", 7.5, 6.0, 2.0)
        self.world.doors.append(door)
        selected = []
        self.assertIs(self.world.interaction_target(self.player), door)
        self.assertEqual(self.world.interact(self.player, on_talk=selected.append)[0].name, "door_open")
        self.assertFalse(selected)
        self.world.doors[:] = [Door("rear gate", 7.5, 7.8, 2.0)]
        self.assertIs(self.world.interaction_target(self.player), self.npc)
        self.assertAlmostEqual(self.world.solid_hit((8.5, 5.3, 2.48), (0, 1, 0), 2.3), 1.41)

    def test_resident_body_stops_movement(self):
        for _ in range(120):
            self.player.update(self.world, {"w"}, 1 / 120)
        self.assertTrue(self.player.grounded)
        self.assertAlmostEqual(self.player.y, self.npc.y - self.npc.radius - Player.RADIUS, delta=0.03)


class ConversationTests(unittest.TestCase):
    def test_reveal_progress_is_time_based_and_natural_completion_can_advance(self):
        player = Player(8.5, 5.3, 1.0)
        npc = NPC("Keeper", 8.5, 7.0, 1.0, 0.0, ("Evening.", "Farewell."))
        conversation = Conversation(npc, player)
        self.assertIsNone(conversation.view.text)
        self.assertEqual(conversation.update(player, TURN_SECONDS).name, "dialogue_line")
        self.assertEqual(conversation.view.visible_characters, 1)
        for _ in range(4):
            self.assertIsNone(conversation.update(player, 1 / (2 * CHARACTERS_PER_SECOND)))
        self.assertEqual(conversation.view.visible_characters, 3)
        self.assertIsNone(conversation.update(player, 0.5))
        self.assertIsNone(conversation.view.visible_characters)
        self.assertEqual(conversation.update(player, 0.0, advance=True).name, "dialogue_line")
        self.assertEqual(conversation.view.visible_characters, 1)
        self.assertTrue(conversation.view.last)

        # A press on the frame that would finish revealing still reveals the
        # current line. The next press dismisses it.
        self.assertEqual(conversation.update(player, 0.5, advance=True).name, "dialogue_reveal")
        self.assertFalse(conversation.finished)
        self.assertEqual(conversation.update(player, 0.0, advance=True).name, "dialogue_end")
        self.assertTrue(conversation.finished)


class NPCPlacementTests(unittest.TestCase):
    def test_residents_are_on_dry_ground_and_reachable_from_nearby_starts(self):
        world = build_world()
        routes = {"Iven Ashward": ("ashgate", 115), "Mael Veyr": ("ashgate", 30),
                  "Sister Morwen": ("gravewood", 28), "Vesper Thorn": ("thornwatch", 115)}
        self.assertCountEqual([npc.name for npc in world.npcs], routes.keys())
        for npc in world.npcs:
            with self.subTest(npc=npc.name):
                region, steps = routes[npc.name]
                support = world.walk_support(npc.x, npc.y, npc.z, radius=npc.radius)
                self.assertIsNotNone(support)
                self.assertAlmostEqual(support[0], npc.z)
                self.assertFalse(world.in_water(npc.x, npc.y, npc.z))
                self.assertGreaterEqual(len(npc.dialogue), 2)
                self.assertTrue(all(line.isascii() and line.isprintable() for line in npc.dialogue))
                self.assertTrue(all(len(wrap(line, 48)) <= 3 for line in npc.dialogue))
                player = spawn_region(region)
                start_x, start_y = player.x, player.y
                for _ in range(steps):
                    player.update(world, {"w"}, 1 / 120)
                self.assertAlmostEqual(math.hypot(player.x - start_x, player.y - start_y),
                                       steps * Player.WALK_SPEED / 120)
                self.assertTrue(player.grounded)
                self.assertFalse(player.in_water)
                player.yaw = math.atan2(npc.y - player.y, npc.x - player.x)
                player.pitch = 0.0
                self.assertIs(world.interaction_target(player), npc)

    def test_gatehouse_residents_leave_the_spawns_and_main_aisle_clear(self):
        world = build_world()
        for outside in (False, True):
            with self.subTest(outside=outside):
                player = spawn_player(outside)
                self.assertFalse(world.collides(player.x, player.y, player.z))
                target = world.interaction_target(player)
                self.assertIsInstance(target, WeaponPickup)
                self.assertEqual(target.weapon, SWORD)
                if outside:
                    for _ in range(140):
                        player.update(world, {"w"}, 1 / 120)
                    self.assertIs(world.interaction_target(player), world.doors[0])
                    self.assertEqual(world.interact(player)[0].name, "door_open")
                for _ in range(480):
                    player.update(world, {"w"}, 1 / 120)
                    world.update_doors(player, 1 / 120)
                self.assertGreater(player.y, 83.0)
                self.assertAlmostEqual(player.x, 128.5)
                self.assertTrue(player.grounded)

    def test_empty_worlds_have_independent_resident_lists(self):
        world = World.empty(2, 2, 2)
        world.npcs.append(NPC("Keeper", 1.0, 1.0, 1.0, 0.0, ("Hello.",)))
        self.assertEqual(World.empty(2, 2, 2).npcs, [])

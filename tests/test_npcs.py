import math
from textwrap import wrap
import unittest

from ascii3d.app import spawn_player, spawn_region
from ascii3d.combat import SWORD, WeaponPickup
from ascii3d.dialogue import CHARACTERS_PER_SECOND, TURN_SECONDS, Conversation
from ascii3d.doors import Door
from ascii3d.events import GameEvent
from ascii3d.npcs import NPC, PatrolStop
from ascii3d.player import Player
from ascii3d.world import AIR, FLOOR, STONE, WATER, World, build_world


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
        self.assertEqual([event.name for event in conversation.update(player, TURN_SECONDS)],
                         ["dialogue_line", "dialogue_letter"])
        self.assertEqual(conversation.view.visible_characters, 1)
        letters = []
        for _ in range(4):
            letters.extend(conversation.update(player, 1 / (2 * CHARACTERS_PER_SECOND)))
        self.assertEqual([event.name for event in letters], ["dialogue_letter"] * 2)
        self.assertEqual(conversation.view.visible_characters, 3)
        self.assertEqual([event.name for event in conversation.update(player, 0.5)], ["dialogue_letter"] * 4)
        self.assertIsNone(conversation.view.visible_characters)
        self.assertEqual([event.name for event in conversation.update(player, 0.0, advance=True)],
                         ["dialogue_line", "dialogue_letter"])
        self.assertEqual(conversation.view.visible_characters, 1)
        self.assertTrue(conversation.view.last)

        # A press on the frame that would finish revealing still reveals the
        # current line. The next press dismisses it.
        self.assertEqual([event.name for event in conversation.update(player, 0.5, advance=True)],
                         ["dialogue_reveal"])
        self.assertFalse(conversation.finished)
        self.assertEqual([event.name for event in conversation.update(player, 0.0, advance=True)], ["dialogue_end"])
        self.assertTrue(conversation.finished)

    def test_letter_events_preserve_spacing_and_leave_punctuation_and_skip_silent(self):
        player = Player(8.5, 5.3, 1.0)
        npc = NPC("Keeper", 8.5, 7.0, 1.0, 0.0, ("A, so be it.",))
        conversation = Conversation(npc, player)
        self.assertEqual(conversation.update(player, TURN_SECONDS / 2), ())
        line, first = conversation.update(player, TURN_SECONDS / 2)
        self.assertEqual(line.name, "dialogue_line")
        self.assertEqual(first, GameEvent("dialogue_letter", npc.x, npc.y))
        later = conversation.update(player, 4 / CHARACTERS_PER_SECOND)
        self.assertEqual([event.name for event in later], ["dialogue_letter", "dialogue_letter"])
        self.assertEqual([event.delay for event in later], [2 / CHARACTERS_PER_SECOND, 3 / CHARACTERS_PER_SECOND])
        self.assertEqual(conversation.view.visible_characters, 5)
        self.assertEqual([event.name for event in conversation.update(player, 0.1, advance=True)],
                         ["dialogue_reveal"])
        self.assertEqual(conversation.update(player, 0.1), ())


class NPCPatrolTests(unittest.TestCase):
    def setUp(self):
        self.world = World.empty(16, 16, 8)
        self.world.box(0, 0, 0, 16, 16, 1, FLOOR)
        self.npc = NPC("Traveling keeper", 4.5, 4.5, 1.0, 0, ("Good evening.",),
                       patrol=(PatrolStop(6.5, 4.5, 0.5), PatrolStop(4.5, 4.5)))
        self.world.npcs.append(self.npc)
        self.player = Player(2.5, 2.5, 1.0)

    def advance(self, ticks):
        events = []
        for _ in range(ticks):
            events.extend(self.world.update_npcs(self.player, 1 / 120))
        return events

    def test_configured_loop_pauses_and_emits_footsteps_only_for_contact(self):
        still = NPC("Keeper", 7.5, 7.5, 1, 0, ("Welcome.",))
        self.world.npcs.append(still)
        events = self.advance(147)
        self.assertEqual((self.npc.x, self.npc.y), (6.5, 4.5))
        self.assertGreater(self.npc.walk_blend, 0)
        self.assertEqual([event.name for event in events], ["npc_step", "npc_step"])
        self.assertTrue(all(event.y == 4.5 and event.surface == "stone"
                            and 0 < event.strength < 1 for event in events))
        self.assertEqual(self.advance(48), [])
        self.assertEqual((self.npc.x, self.npc.y, self.npc.walk_blend), (6.5, 4.5, 0.0))
        self.advance(120)
        self.assertLess(self.npc.x, 6.0)
        self.assertAlmostEqual(self.npc.yaw, math.pi)
        self.advance(200)
        self.assertGreater(self.npc.x, 4.5)
        self.assertAlmostEqual(math.remainder(self.npc.yaw, math.tau), 0.0)
        self.assertEqual((still.x, still.y, still.yaw, still.walk_blend), (7.5, 7.5, 0, 0.0))

    def test_blocking_actors_stop_the_route_until_they_move(self):
        self.player.x, self.player.y = 6.0, 4.5
        self.advance(270)
        self.assertLessEqual(self.npc.x, 6.0 - self.player.RADIUS - self.npc.radius)
        self.assertEqual(self.npc.walk_blend, 0)
        self.player.y = 2.5
        other = NPC("Guard", 6.5, 4.5, 1, 0, ("Halt.",))
        self.world.npcs.append(other)
        self.advance(120)
        self.assertLessEqual(self.npc.x, 6.5 - self.npc.radius - other.radius)
        self.assertEqual(self.npc.walk_blend, 0)
        other.y = 6.5
        self.advance(120)
        self.assertEqual((self.npc.x, self.npc.y), (6.5, 4.5))

    def test_walls_holes_and_water_wait_at_safe_edge(self):
        for material in (STONE, AIR, WATER):
            with self.subTest(material=material):
                self.setUp()
                self.npc.patrol = (PatrolStop(9.5, 4.5),)
                if material == STONE:
                    self.world.box(6, 3, 1, 10, 6, 2)
                else:
                    self.world.box(6, 3, 0, 10, 6, 1, material)
                self.advance(360)
                expected_edge = 6 + (self.npc.radius if material != STONE else -self.npc.radius)
                self.assertAlmostEqual(self.npc.x, expected_edge, delta=0.02)
                self.assertEqual(self.npc.z, 1)
                self.assertFalse(self.world.in_water(self.npc.x, self.npc.y, self.npc.z))
                self.assertEqual(self.advance(120), [])

    def test_authored_stairs_are_walkable_both_ways(self):
        self.npc.x = 2.5
        self.npc.patrol = (PatrolStop(9.5, 4.5, 1.0), PatrolStop(2.5, 4.5, 1.0))
        self.world.add_stair_flight(4, 2, 4, 6, 1, 3, axis="x", material=FLOOR)
        self.advance(520)
        self.assertEqual((self.npc.x, self.npc.z), (9.5, 3.0))
        self.advance(715)
        self.assertEqual((self.npc.x, self.npc.z), (2.5, 1.0))

    def test_shared_door_sweep_reverses_before_hitting_resident(self):
        self.npc.x, self.npc.y = 5.05, 4.8
        door = Door("Guardhouse door", 4.0, 4.0, 2.0, double=False, openness=1.0)
        self.world.doors.append(door)
        events = []
        for _ in range(100):
            events.extend(self.world.update_doors(self.player, 1 / 120))
            self.assertFalse(self.world.collides(self.npc.x, self.npc.y, self.npc.z,
                                                self.npc.radius, self.npc.height, ignore_npc=self.npc))
        self.assertEqual(sum(event.name == "door_blocked" for event in events), 1)
        self.assertTrue(door.target_open)
        self.assertEqual(door.openness, 1.0)


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

"""Material contact, landing routing, and milestone sound contracts."""

from array import array
import math
from types import SimpleNamespace
import unittest

from ascii3d.doors import Door
from ascii3d.events import GameEvent
from ascii3d.player import Player
from ascii3d.sound import EFFECTS, LANDING_CUES, Mixer, SAMPLE_RATE, SoundBank, synthesize
from ascii3d.sound_surfaces import surface_kind
from ascii3d.world import BRIDGE, CRATE, FLOOR, GRASS, METAL, PATH, STONE, WATER, WOOD, World


class SurfaceContactTests(unittest.TestCase):
    def test_player_emits_matching_steps_and_landing_metadata_on_all_six_surfaces(self):
        for material, surface in ((FLOOR, "stone"), (GRASS, "grass"), (WOOD, "wood"),
                                  (WATER, "water"), (PATH, "gravel"), (METAL, "metal")):
            with self.subTest(surface=surface):
                world = World.empty(20, 20, 8)
                world.box(0, 0, 0, 20, 20, 1, material)
                player = Player(x=8.5, y=4.5)
                events = []
                for tick in range(240):
                    player.update(world, {"w"}, 1 / 120, jump=tick == 0)
                    events.extend(player.events)
                self.assertIn("step_" + surface, [event.name for event in events])
                landings = [event for event in events if event.name == "land"]
                self.assertEqual(len(landings), 1)
                self.assertEqual(landings[0].surface, surface)
                self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_supported_materials_have_explicit_foley_surfaces(self):
        for material, expected in ((STONE, "stone"), (FLOOR, "stone"),
                                   (GRASS, "grass"), (PATH, "gravel"),
                                   (METAL, "metal"), (WOOD, "wood"),
                                   (CRATE, "wood"), (BRIDGE, "wood")):
            with self.subTest(material=material):
                world = World.empty(6, 6, 6)
                world.box(0, 0, 0, 6, 6, 1, material)
                self.assertEqual(surface_kind(world, 2.5, 2.5, 1.0002), expected)

    def test_bridge_and_crate_tops_override_the_ground_below(self):
        world = World.empty(8, 8, 8)
        world.box(0, 0, 0, 8, 8, 1, WATER)
        world.box(2, 2, 3, 4, 4, 4, BRIDGE)
        world.box(5, 2, 1, 6, 3, 3, CRATE)
        self.assertEqual(surface_kind(world, 2.5, 2.5, 4), "wood")
        self.assertEqual(surface_kind(world, 5.5, 2.5, 3), "wood")
        self.assertEqual(surface_kind(world, 1.5, 2.5, 0.12), "water")
        self.assertEqual(surface_kind(world, 2.5, 2.5, 4, in_water=True), "water")

    def test_footprint_detects_edge_support_without_sampling_distant_or_lower_tiles(self):
        world = World.empty(8, 8, 8)
        world.box(0, 0, 0, 8, 8, 1, GRASS)
        world.box(3, 3, 1, 4, 4, 3, METAL)
        # Center is over air at this height, but the player's foot overlaps.
        self.assertEqual(surface_kind(world, 2.9, 3.5, 3), "metal")
        self.assertEqual(surface_kind(world, 2.9, 2.9, 3), "metal")
        self.assertEqual(surface_kind(world, 2.7, 3.5, 3), "stone")
        self.assertEqual(surface_kind(world, 2.9, 3.5, 4), "stone")
        # A nearby wall is not the ground material.
        self.assertEqual(surface_kind(world, 2.9, 3.5, 1), "grass")

    def test_center_contact_wins_at_a_material_boundary(self):
        world = World.empty(8, 8, 4)
        world.box(0, 0, 0, 8, 8, 1, GRASS)
        world.box(3, 3, 0, 4, 4, 1, PATH)
        self.assertEqual(surface_kind(world, 2.99, 3.5, 1), "grass")
        self.assertEqual(surface_kind(world, 3.01, 3.5, 1), "gravel")

    def test_rotated_door_top_is_wood_but_side_is_not_support(self):
        world = World.empty(12, 12, 8)
        world.box(0, 0, 0, 12, 12, 1, FLOOR)
        door = Door("test", 4, 4, 3, angle=0.27, double=False, openness=0.65)
        world.doors.append(door)
        panel = door.panels[0]
        x = panel.x + panel.ux * 1.3 - panel.uy * 0.14
        y = panel.y + panel.uy * 1.3 + panel.ux * 0.14
        self.assertEqual(surface_kind(world, x, y, panel.bottom + panel.height), "wood")
        self.assertEqual(surface_kind(world, x, y, 1), "stone")
        self.assertEqual(surface_kind(world, x, y, 5), "stone")

    def test_contact_queries_remain_small_and_deterministic(self):
        world = World.empty(8, 8, 8)
        world.box(3, 3, 1, 4, 4, 3, WOOD)
        calls = 0
        get = world.get

        def counted_get(x, y, z):
            nonlocal calls
            calls += 1
            return get(x, y, z)

        world.get = counted_get
        for _ in range(10):
            self.assertEqual(surface_kind(world, 2.9, 3.5, 3), "wood")
        self.assertLessEqual(calls, 50)


class MilestoneCueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = SoundBank()

    def test_landing_metadata_selects_surface_clip_without_changing_event_name(self):
        mixer = Mixer(self.bank)
        for surface, cue in LANDING_CUES.items():
            event = SimpleNamespace(name="land", surface=surface, x=None, y=None, strength=0.8)
            mixer.add(event)
            self.assertIs(mixer.voices[-1].samples, self.bank.clips[cue][0])
            self.assertEqual(event.name, "land")
        mixer.add(GameEvent("land"))
        self.assertIs(mixer.voices[-1].samples, self.bank.clips["land"][0])
        mixer.add(SimpleNamespace(name="land", surface="unknown", x=None, y=None, strength=1))
        self.assertIs(mixer.voices[-1].samples, self.bank.clips["land"][0])

    def test_landing_can_use_a_legacy_custom_bank(self):
        bank = SimpleNamespace(clips={"land": self.bank.clips["land"]})
        mixer = Mixer(bank)
        mixer.add(SimpleNamespace(name="land", surface="grass", x=None, y=None, strength=1))
        self.assertIs(mixer.voices[-1].samples, bank.clips["land"][0])

    def test_all_surfaces_have_distinct_steps_and_landings_with_step_variation(self):
        steps, landings = set(), set()
        for surface, cue in LANDING_CUES.items():
            variants = self.bank.clips["step_" + surface]
            self.assertEqual(len({clip.tobytes() for clip in variants}), 3)
            steps.add(variants[0].tobytes())
            landings.add(self.bank.clips[cue][0].tobytes())
        self.assertEqual(len(steps), 6)
        self.assertEqual(len(landings), 6)

    def test_combat_cues_are_original_reproducible_click_free_and_bounded(self):
        cues = ("sword_pickup", "sword_swing", "sword_hit", "sword_miss",
                "attack_empty", "dummy_down", "dummy_reset")
        mixer = Mixer(self.bank)
        for name in cues:
            with self.subTest(cue=name):
                self.assertIn(name, EFFECTS)
                clip = self.bank.clips[name][0]
                self.assertEqual(clip, synthesize(name))
                self.assertEqual((clip[0], clip[-1]), (0, 0))
                self.assertGreater(len(clip), SAMPLE_RATE * 0.08)
                rms = math.sqrt(sum(sample * sample for sample in clip) / len(clip))
                self.assertGreater(rms, 300)
                mixer.add(GameEvent(name, strength=3))
        for _ in range(30):
            mixer.add(GameEvent("sword_hit"))
        self.assertLessEqual(len(mixer.voices), Mixer.MAX_VOICES)
        pcm = array("h", mixer.render(512))
        self.assertLessEqual(max(map(abs, pcm)), 32760)


if __name__ == "__main__":
    unittest.main()

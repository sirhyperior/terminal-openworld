from array import array
import math
import tempfile
import time
from pathlib import Path
import unittest
import wave

from ascii3d.events import GameEvent
from ascii3d.player import Player
from ascii3d.sound import Audio, EFFECTS, Mixer, SAMPLE_RATE, SoundBank, synthesize
from ascii3d.world import BRIDGE, FLOOR, GRASS, WATER, World


class SoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = SoundBank()

    def test_all_registered_effects_are_nonempty_finite_pcm(self):
        for name, variants in self.bank.clips.items():
            for clip in variants:
                self.assertEqual(clip.typecode, "h")
                self.assertGreater(len(clip), SAMPLE_RATE * 0.08)
                self.assertGreater(max(map(abs, clip)), 100)
                self.assertLessEqual(max(map(abs, clip)), 32767)
        self.assertEqual(self.bank.clips["door_open"][0], synthesize("door_open"))

    def test_door_creaks_have_separate_friction_bursts_instead_of_a_continuous_tone(self):
        size = round(SAMPLE_RATE * 0.02)
        for name in ("door_open", "door_close"):
            for clip in self.bank.clips[name]:
                with self.subTest(effect=name):
                    # Exclude the outer fades: the moving door should have
                    # audible strain/release pauses within the sound itself.
                    levels = [math.sqrt(sum(sample * sample for sample in clip[i:i + size]) / size)
                              for i in range(round(len(clip) * 0.12),
                                             round(len(clip) * 0.82) - size, size)]
                    self.assertLess(min(levels), max(levels) * 0.30)
                    self.assertGreaterEqual(sum(level < max(levels) * 0.35 for level in levels), 2)

    def test_every_door_cue_has_three_distinct_repeatable_click_free_variants(self):
        for name in ("door_open", "door_close", "door_blocked"):
            with self.subTest(effect=name):
                variants = self.bank.clips[name]
                self.assertEqual(len(variants), 3)
                self.assertEqual(len({clip.tobytes() for clip in variants}), 3)
                for variation, clip in enumerate(variants):
                    self.assertEqual(clip, synthesize(name, variation))
                    self.assertEqual((clip[0], clip[-1]), (0, 0))
                    self.assertLessEqual(max(map(abs, clip)), 27000)

    def test_enemy_hit_is_stronger_and_more_immediate_than_the_air_swing(self):
        for hit, swing in zip(self.bank.clips["sword_hit"], self.bank.clips["sword_swing"]):
            hit_energy = sum(sample * sample for sample in hit)
            swing_energy = sum(sample * sample for sample in swing)
            hit_rms = math.sqrt(hit_energy / len(hit))
            swing_rms = math.sqrt(swing_energy / len(swing))
            self.assertGreater(hit_rms, swing_rms * 1.25)
            early = round(SAMPLE_RATE * 0.08)
            self.assertGreater(sum(sample * sample for sample in hit[:early]) / hit_energy, 0.80)
            self.assertLess(sum(sample * sample for sample in swing[:early]) / swing_energy, 0.30)

    def test_enemy_hit_survives_a_full_voice_queue_and_low_priority_sounds(self):
        mixer = Mixer(self.bank)
        for _ in range(Mixer.MAX_VOICES):
            mixer.add(GameEvent("door_open"))
        mixer.add(GameEvent("sword_hit"))
        impact = mixer.voices[-1]
        self.assertTrue(any(impact.samples is clip for clip in self.bank.clips["sword_hit"]))
        for _ in range(12):
            mixer.add(GameEvent("step_grass"))
            mixer.add(GameEvent("sword_swing"))
        self.assertIn(impact, mixer.voices)
        self.assertEqual(len(mixer.voices), Mixer.MAX_VOICES)
        pcm = array("h", mixer.render(512))
        self.assertLessEqual(max(map(abs, pcm)), 32760)

    def test_mix_overlaps_effects_with_safe_stereo_clipping_and_bounded_voices(self):
        mixer = Mixer(self.bank)
        for _ in range(30):
            mixer.add(GameEvent("door_open", strength=5))
        self.assertEqual(len(mixer.voices), mixer.MAX_VOICES)
        pcm = array("h", mixer.render(512))
        self.assertEqual(len(pcm), 1024)
        self.assertGreater(max(map(abs, pcm)), 100)
        self.assertLessEqual(max(map(abs, pcm)), 32760)

    def test_spatial_pan_and_attenuation(self):
        mixer = Mixer(self.bank)
        mixer.add(GameEvent("door_open", 2, 0), (0, 0, math.pi / 2))
        voice = mixer.voices[0]
        self.assertGreater(voice.right, voice.left)
        mixer.add(GameEvent("door_open", 20, 0), (0, 0, math.pi / 2))
        self.assertLess(mixer.voices[1].left + mixer.voices[1].right, voice.left + voice.right)

    def test_mute_is_silent_and_discards_pending_voices(self):
        mixer = Mixer(self.bank)
        mixer.add(GameEvent("step_stone"))
        self.assertEqual(mixer.render(512, (0.2, 0.2), enabled=False), bytes(2048))
        self.assertFalse(mixer.voices)
        self.assertEqual(mixer.render(512), bytes(2048))

    def test_missing_audio_device_does_not_break_gameplay(self):
        def unavailable():
            raise OSError("No audio device")
        with Audio(output_factory=unavailable, bank=self.bank) as audio:
            self.assertFalse(audio.available)
            audio.emit(GameEvent("door_open"))
            audio.pause(True)
            self.assertFalse(audio.toggle())
            self.assertIn("No audio device", audio.error)

    def test_unmapped_event_is_rejected_to_enforce_sound_coverage(self):
        mixer = Mixer(self.bank)
        with self.assertRaises(KeyError):
            mixer.add(GameEvent("unregistered_feature"))

    def test_exported_preview_is_valid_stereo_wave(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview.wav"
            self.bank.write_preview(path)
            with wave.open(str(path)) as audio:
                self.assertEqual(audio.getnchannels(), 2)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getframerate(), SAMPLE_RATE)
                self.assertGreater(audio.getnframes(), SAMPLE_RATE * 3)

    def test_immediate_virtual_device_cannot_spin_mixer_above_sample_rate(self):
        class ImmediateOutput:
            frames = 512
            closed = False

            def ready(self):
                return True

            def write(self, item, samples):
                pass

            def close(self):
                self.closed = True

        output = ImmediateOutput()
        start = time.perf_counter()
        with Audio(output_factory=lambda: output, bank=self.bank) as audio:
            audio.emit(GameEvent("door_open"))
            time.sleep(0.12)
        elapsed = time.perf_counter() - start
        self.assertGreater(audio.blocks_rendered, 0)
        self.assertLessEqual(audio.blocks_rendered, math.ceil(elapsed * SAMPLE_RATE / 512) + 4)
        self.assertTrue(output.closed)
        self.assertFalse(audio.enabled)


class MovementSoundTests(unittest.TestCase):
    def world(self, material):
        world = World.empty(24, 24, 10)
        world.box(0, 0, 0, 24, 24, 1, material)
        return world

    def collect(self, player, world, seconds, keys=(), jump=False):
        events = []
        for tick in range(round(seconds * 120)):
            player.update(world, set(keys), 1 / 120, jump=jump and tick == 0)
            events.extend(player.events)
        self.assertTrue(all(event.name in EFFECTS for event in events))
        return [event.name for event in events]

    def test_footsteps_match_surface_and_airborne_steps_are_silent(self):
        for material, name in ((FLOOR, "stone"), (GRASS, "grass"), (BRIDGE, "wood"), (WATER, "water")):
            with self.subTest(surface=name):
                player = Player(x=8.5, y=8.5)
                events = self.collect(player, self.world(material), 2, {"w"})
                self.assertIn("step_" + name, events)
        player = Player(x=8.5, y=8.5)
        events = self.collect(player, self.world(FLOOR), 0.4, {"w"}, jump=True)
        self.assertIn("jump", events)
        self.assertFalse(any(event.startswith("step_") for event in events))

    def test_jump_and_landing_emit_once_without_idle_thuds(self):
        player = Player(x=8.5, y=8.5)
        world = self.world(FLOOR)
        events = self.collect(player, world, 2, jump=True)
        self.assertEqual(events.count("jump"), 1)
        self.assertEqual(events.count("land"), 1)
        self.assertEqual(self.collect(player, world, 2), [])

    def test_blocked_walk_does_not_generate_repeating_footsteps(self):
        world = self.world(FLOOR)
        world.box(0, 10, 1, 24, 11, 7)
        player = Player(x=8.5, y=9.7)
        self.assertEqual(self.collect(player, world, 2, {"w"}), [])


if __name__ == "__main__":
    unittest.main()

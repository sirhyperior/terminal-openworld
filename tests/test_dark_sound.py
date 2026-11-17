"""Audible design contracts for the original dark-fantasy sound palette."""

import math
import unittest

from ascii3d.sound import SAMPLE_RATE, SoundBank, synthesize


def energy(clip):
    return sum(sample * sample for sample in clip)


def periodicity(clip):
    """Strong repeated waveform cycles reveal a musical beep/chord replacement."""
    strongest = 0.0
    for lag in range(round(SAMPLE_RATE / 500), round(SAMPLE_RATE / 70), 7):
        first, second = clip[:-lag], clip[lag:]
        correlation = sum(a * b for a, b in zip(first, second))
        strongest = max(strongest, abs(correlation) /
                        max(1, math.sqrt(energy(first) * energy(second))))
    return strongest


class DarkSoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = SoundBank()

    def test_relic_spellfire_and_return_are_textured_instead_of_reward_tones(self):
        for cue in ("staff_pickup", "fireball_cast", "enemy_alert", "enemy_respawn",
                    "player_respawn"):
            for variant, clip in enumerate(self.bank.clips[cue]):
                with self.subTest(cue=cue, variant=variant):
                    # A sustained pitched oscillator has correlation near one.
                    # Material/breath noise remains irregular even with a body.
                    self.assertLess(periodicity(clip), 0.80)

    def test_iron_floor_rings_longer_than_soft_earth_without_a_louder_step(self):
        for metal, grass in zip(self.bank.clips["step_metal"],
                                self.bank.clips["step_grass"]):
            metal_tail = energy(metal[round(len(metal) * 0.7):]) / energy(metal)
            grass_tail = energy(grass[round(len(grass) * 0.7):]) / energy(grass)
            self.assertGreater(metal_tail, grass_tail * 3)
            metal_rms = math.sqrt(energy(metal) / len(metal))
            grass_rms = math.sqrt(energy(grass) / len(grass))
            self.assertAlmostEqual(metal_rms / grass_rms, 1.0, delta=0.05)

    def test_parchment_and_leather_interface_stay_below_combat_feedback(self):
        hit = self.bank.clips["sword_hit"][0]
        hit_rms = math.sqrt(energy(hit) / len(hit))
        for cue in ("ui_map", "ui_help", "ui_pause", "ui_reset", "ui_exit", "ui_toggle"):
            clip = self.bank.clips[cue][0]
            with self.subTest(cue=cue):
                self.assertLess(math.sqrt(energy(clip) / len(clip)), hit_rms * 0.4)

    def test_recurring_stone_and_relic_gestures_have_reproducible_variation(self):
        for cue in ("enemy_alert", "enemy_attack", "enemy_hurt", "enemy_down",
                    "enemy_respawn", "staff_pickup", "water_splash", "dummy_reset"):
            clips = self.bank.clips[cue]
            self.assertEqual(len({clip.tobytes() for clip in clips}), 3, cue)
            for variant, clip in enumerate(clips):
                with self.subTest(cue=cue, variant=variant):
                    self.assertEqual(clip, synthesize(cue, variant))
                    self.assertEqual((clip[0], clip[-1]), (0, 0))
                    self.assertLessEqual(max(map(abs, clip)), 27000)


if __name__ == "__main__":
    unittest.main()

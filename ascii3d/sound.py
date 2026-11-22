"""Original dark-fantasy Foley and bounded asynchronous stereo playback.

Synthesis is performed once before play. Gameplay only queues semantic events;
the renderer never opens devices, writes files, or generates audio samples.
"""

from array import array
from dataclasses import dataclass
import math
import os
from pathlib import Path
import queue
import random
import threading
import time
import wave

from .events import GameEvent
from .audio_output import BUFFER_COUNT, BUFFER_FRAMES, SAMPLE_RATE, StreamPacer, WaveOutput


EFFECTS = {
    "step_stone": 0.18, "step_grass": 0.16, "step_wood": 0.20, "step_water": 0.25,
    "step_gravel": 0.23, "step_metal": 0.27, "step_cobblestone": 0.20,
    "terrain_step": 0.18,
    "jump": 0.18, "land": 0.26, "water_splash": 0.32,
    "land_stone": 0.28, "land_grass": 0.27, "land_wood": 0.32,
    "land_water": 0.38, "land_gravel": 0.31, "land_metal": 0.38, "land_cobblestone": 0.29,
    "door_open": 0.88, "door_close": 0.82, "door_blocked": 0.22,
    "sword_pickup": 0.42, "sword_swing": 0.29, "sword_hit": 0.34,
    "sword_miss": 0.18, "attack_empty": 0.15,
    "staff_pickup": 0.62, "item_drop": 0.24,
    "fireball_cast": 0.65, "fireball_hit": 0.42,
    "fireball_impact": 0.38, "fireball_fizzle": 0.24,
    "dummy_down": 0.58, "dummy_reset": 0.48,
    "enemy_alert": 0.78, "enemy_step": 0.24, "enemy_attack": 0.42,
    "enemy_miss": 0.22, "enemy_hurt": 0.28,
    "enemy_down": 0.85, "enemy_respawn": 0.90,
    "player_hurt": 0.30, "player_down": 0.80, "player_respawn": 0.60,
    "dialogue_start": 0.22, "dialogue_line": 0.32, "dialogue_reveal": 0.12, "dialogue_end": 0.18,
    "interaction_miss": 0.10, "ui_map": 0.13, "ui_help": 0.14,
    "ui_pause": 0.16, "ui_reset": 0.25, "ui_exit": 0.18, "ui_toggle": 0.10,
    "ui_dev_open": 0.14, "ui_dev_close": 0.12, "ui_dev_teleport": 0.26, "ui_dev_report": 0.19,
}
LANDING_CUES = {surface: "land_" + surface
                for surface in ("stone", "grass", "wood", "water", "gravel", "metal", "cobblestone")}
TERRAIN_STEP_CUES = {surface: "step_" + surface for surface in LANDING_CUES}

# Relative start, length and slip frequency for each strain/release gesture.
# All doors share one friction model; event differences are configuration.
_DOOR_STRAINS = {
    "door_open": ((0.07, 0.23, 83), (0.41, 0.19, 62), (0.72, 0.16, 96)),
    "door_close": ((0.05, 0.19, 68), (0.35, 0.22, 91), (0.69, 0.17, 56)),
    "door_blocked": ((0.07, 0.54, 71),),
}


def _door_creak(name, rng, rate, duration):
    """Uneven stick/slip friction excites damped wooden/hinge resonances."""
    bursts = [(duration * (start + rng.uniform(-0.012, 0.012)),
               duration * length, frequency * rng.uniform(0.86, 1.14))
              for start, length, frequency in _DOOR_STRAINS[name]]
    # Each state is [feedback, damping squared, excitation gain, mix gain,
    # previous sample, older sample]. Short decays leave audible release gaps.
    modes = []
    for frequency, decay, gain in ((111, 0.022, 0.66), (293, 0.012, 0.34),
                                    (713, 0.006, 0.16)):
        angle = math.tau * frequency * rng.uniform(0.94, 1.06) / rate
        damping = math.exp(-1 / (rate * decay))
        modes.append([2 * damping * math.cos(angle), damping * damping,
                      math.sin(angle), gain, 0.0, 0.0])
    latch = 0.012 if name == "door_open" else duration - 0.045
    burst_index, next_slip, grain, friction = 0, 0.0, 0.0, 0.0
    for index in range(round(duration * rate)):
        t = index / rate
        noise = rng.uniform(-1, 1)
        grain += (noise - grain) * 0.25
        friction += (grain - friction) * 0.04
        while burst_index < len(bursts) and t >= bursts[burst_index][0] + bursts[burst_index][1]:
            burst_index += 1
            next_slip = t
        strain, impulse = 0.0, 0.0
        if burst_index < len(bursts):
            start, length, frequency = bursts[burst_index]
            if t >= start:
                progress = (t - start) / length
                strain = math.sin(math.pi * progress) ** 0.7
                if t >= next_slip:
                    impulse = strain * rng.uniform(0.55, 1.0)
                    # Fresh jitter on every release keeps the groan irregular.
                    next_slip = t + rng.uniform(0.55, 1.65) / (frequency * (1 - 0.35 * progress))
        value = (grain - friction) * strain * 0.10
        for mode in modes:
            resonant = impulse * mode[2] + mode[0] * mode[4] - mode[1] * mode[5]
            mode[5], mode[4] = mode[4], resonant
            value += resonant * mode[3]
        contact = t - latch
        if 0 <= contact < 0.065:
            # A short wooden latch/stop, subordinate to the friction creak.
            value += (grain * 0.22 + math.sin(math.tau * contact * 137) * 0.25) * math.exp(-contact * 65)
        yield value


# Frequencies are deliberately inharmonic: these are damped material bodies,
# not pitched notes. The same model serves boots, debris, weapons and masonry.
_MATERIAL_MODES = {
    "stone": ((91, 0.024, 0.65), (217, 0.016, 0.30), (563, 0.009, 0.12)),
    "cobblestone": ((107, 0.022, 0.58), (311, 0.013, 0.33),
                    (746, 0.007, 0.19), (1271, 0.004, 0.10)),
    "grass": ((73, 0.016, 0.50), (173, 0.009, 0.14)),
    "wood": ((106, 0.048, 0.64), (267, 0.024, 0.34), (631, 0.012, 0.12)),
    "water": ((133, 0.025, 0.25), (379, 0.014, 0.18)),
    "gravel": ((97, 0.020, 0.45), (431, 0.010, 0.19), (937, 0.006, 0.10)),
    "metal": ((181, 0.095, 0.42), (497, 0.062, 0.22), (1129, 0.038, 0.11)),
}
# Surface-dependent boot, scrape and toe-release amounts. Both ordinary steps
# and hard landings use these contacts, so elevated floors keep the same voice.
_CONTACT_TEXTURES = {
    "stone": (0.46, 0.16, 27), "grass": (0.22, 0.68, 17),
    "wood": (0.38, 0.24, 24), "water": (0.12, 0.95, 11),
    "gravel": (0.62, 0.38, 16), "metal": (0.33, 0.18, 31),
    "cobblestone": (0.53, 0.27, 60),
}


class _Body:
    """Noise/impulse-excited, decaying modes; constructed only during loading."""

    def __init__(self, modes, rate, pitch=1.0):
        self.modes = []
        for frequency, decay, gain in modes:
            angle = math.tau * frequency * pitch / rate
            damping = math.exp(-1 / (rate * decay))
            self.modes.append([2 * damping * math.cos(angle), damping * damping,
                               math.sin(angle) * gain, 0.0, 0.0])

    def sample(self, excitation):
        value = 0.0
        for mode in self.modes:
            current = excitation * mode[2] + mode[0] * mode[3] - mode[1] * mode[4]
            mode[4], mode[3] = mode[3], current
            value += current
        return value


def _gesture(t, start, length):
    """A soft-edged contact/rush that occupies one authored time window."""
    progress = (t - start) / length
    return math.sin(math.pi * progress) ** 2 if 0 < progress < 1 else 0.0


def synthesize(name: str, variation: int = 0, rate: int = SAMPLE_RATE) -> array:
    """Build original weathered Foley, cold spellfire and turbulent ambience.

    Impacts excite irregular material resonances, while movement is filtered
    cloth/air/stone noise. No external recordings, speech, or musical UI tones.
    All filtering, synthesis and room tails finish before gameplay begins.
    """
    ambient = name in ("wind", "river")
    duration = 6.0 if ambient else EFFECTS[name]
    rng = random.Random(7129 + sum(map(ord, name)) * 43 + variation * 719)
    result = array("h")
    low = slow = air = 0.0
    # Rate-independent filters keep previews at other sample rates recognizable.
    low_alpha = 1 - math.exp(-math.tau * 760 / rate)
    slow_alpha = 1 - math.exp(-math.tau * 105 / rate)
    air_alpha = 1 - math.exp(-math.tau * 2400 / rate)
    pitch = 0.93 + variation * 0.057
    surface = name.split("_", 1)[1] if name.startswith(("step_", "land_")) else "stone"
    surface = surface if surface in _MATERIAL_MODES else "stone"
    modes = _MATERIAL_MODES[surface]
    if name in ("sword_pickup", "sword_hit"):
        modes = ((307, 0.022, 0.45), (839, 0.014, 0.23), (1877, 0.008, 0.10))
    elif name.startswith("enemy_"):
        modes = ((58, 0.062, 0.65), (137, 0.039, 0.32), (367, 0.021, 0.15))
    elif name.startswith("fireball_") or name in ("staff_pickup", "player_respawn"):
        modes = ((71, 0.075, 0.42), (127, 0.058, 0.28), (229, 0.039, 0.17))
    elif name in ("player_hurt", "player_down"):
        modes = ((62, 0.026, 0.62), (149, 0.015, 0.27))
    elif name in ("dummy_down", "dummy_reset", "item_drop"):
        modes = _MATERIAL_MODES["wood"]
    elif name == "wind":
        modes = ((137, 0.010, 0.12), (331, 0.006, 0.06))
    elif name == "river":
        modes = ((273, 0.013, 0.13), (617, 0.007, 0.08))
    body = _Body(modes, rate, pitch)
    door = _door_creak(name, rng, rate, duration) if name in _DOOR_STRAINS else None
    # Deterministic irregular chips/drops rather than periodic digital rattles.
    contacts = [(rng.uniform(0.018, duration * 0.68), rng.uniform(0.015, 0.045),
                 rng.uniform(0.12, 0.38)) for _ in range(5)]
    for index in range(round(duration * rate)):
        t = index / rate
        noise = rng.uniform(-1, 1)
        low += (noise - low) * low_alpha
        slow += (noise - slow) * slow_alpha
        air += (noise - air) * air_alpha
        grit, breath = noise - air, air - low
        chips = sum(_gesture(t, start, length) * gain for start, length, gain in contacts)
        transient = math.exp(-t * 44)
        excitation, value = 0.0, 0.0
        if name == "wind":
            gust = (0.66 + 0.20 * math.sin(math.tau * t / duration + 0.7)
                    + 0.14 * math.sin(math.tau * t * 3 / duration + 1.9))
            leaves = max(0, math.sin(math.tau * t * 2 / duration + 0.6)) ** 4
            value = (slow * 3.3 + low * 0.65 + breath * leaves * 0.18) * gust
            # A distant hollow moan is turbulent noise, without a steady drone.
            excitation = low * gust * (0.25 + leaves * 0.45)
        elif name == "river":
            flow = 0.82 + 0.13 * math.sin(math.tau * t * 2 / duration + 0.4)
            eddy = 0.5 + 0.5 * math.sin(math.tau * t * 7 / duration + 1.3)
            value = (slow * 2.2 + low * 1.15 + breath * 0.22) * flow
            excitation = (breath * eddy + noise * max(0, abs(noise) - 0.84) * 0.25) * 0.45
        elif name.startswith(("step_", "land_")) or name in ("terrain_step", "land", "enemy_step"):
            landing = name.startswith("land")
            crack, scrape, decay = _CONTACT_TEXTURES[surface]
            heel = math.exp(-t * (28 if landing else 42))
            toe = _gesture(t, 0.045, 0.095 if landing else 0.075)
            excitation = (noise * heel + low * toe * 0.28) * (1.2 if landing else 0.85)
            value = (slow * 2.7 + low * 0.75 + grit * crack) * heel
            value += (breath * scrape + low * 0.30) * toe
            if surface == "water":
                value += (low * 1.8 + breath * 0.5) * math.exp(-t * 11)
            elif surface == "gravel":
                value += (grit * chips * 1.6 + low * 0.35) * math.exp(-t * decay)
            elif surface == "cobblestone":
                # An uneven set of laid stones gives the heel and toe separate
                # hard contacts, with a short scuff as the sole crosses a seam.
                toe_start = (0.047 if landing else 0.065) + variation * 0.006
                toe_strike = _gesture(t, toe_start, 0.016)
                seam = _gesture(t, toe_start + 0.010, 0.030)
                excitation += (noise + low * 0.35) * toe_strike * 0.74
                value += (grit * 0.42 + low * 0.32) * toe_strike
                value += (grit * 0.26 + breath * 0.35) * seam
            elif surface == "grass":
                value += breath * (0.5 + chips) * math.exp(-t * decay)
            if name == "enemy_step":
                excitation *= 1.45
                value = (slow * 4.1 + low * 1.3 + grit * 0.18) * math.exp(-t * 26)
                value += breath * chips * math.exp(-t * 16)
        elif door is not None:
            value = next(door)
        elif name in ("jump", "attack_empty"):
            cloth = _gesture(t, 0.005, duration * 0.90)
            value = (low * 1.1 + breath * 0.35) * cloth + slow * transient * 0.8
        elif name == "water_splash":
            value = (low * 1.8 + breath * 0.43 + grit * 0.07) * math.exp(-t * 10)
            value += breath * chips * 0.7
            excitation = low * math.exp(-t * 16) * 0.35
        elif name == "sword_pickup":
            draw = _gesture(t, 0.015, 0.20)
            value = breath * draw * 0.55 + low * math.exp(-t * 27) * 0.8
            excitation = noise * transient * 0.65 + grit * draw * 0.12
        elif name == "staff_pickup":
            # Old wood knocks, then an unpitched breath through cold relic metal.
            breath_in = _gesture(t, 0.065, 0.48)
            excitation = low * breath_in * 0.9 + noise * transient * 0.22
            value = slow * 2.1 * breath_in + breath * chips * 0.17
        elif name == "item_drop":
            excitation = noise * transient + noise * _gesture(t, 0.066, 0.025) * 0.4
            value = (slow * 2.0 + low * 1.2 + grit * 0.16) * math.exp(-t * 25)
        elif name == "fireball_cast":
            rush = _gesture(t, 0.035, 0.42)
            tear = math.exp(-t * 48)
            excitation = (low * rush + noise * tear * 0.30) * 1.1
            value = (slow * 2.1 + low * 1.2 + breath * 0.38) * rush
            value += grit * tear * 0.45 + breath * chips * math.exp(-t * 5) * 0.25
        elif name in ("fireball_hit", "fireball_impact"):
            excitation = noise * math.exp(-t * 32) * 1.4
            value = (slow * 3.4 + low * 1.8 + grit * 0.34) * math.exp(-t * 20)
            value += breath * chips * math.exp(-t * 9) * 0.8
            if name == "fireball_hit":
                value += grit * math.exp(-t * 85) * 0.7
        elif name == "fireball_fizzle":
            ember = _gesture(t, 0.002, duration * 0.97)
            value = (breath * 0.75 + low * 0.55) * ember * math.exp(-t * 8)
            value += grit * chips * 0.25
        elif name in ("sword_swing", "sword_miss"):
            sweep = _gesture(t, 0.015, duration * 0.90)
            value = (low * 1.15 + breath * 0.50) * sweep
            value += grit * chips * 0.04 + slow * sweep * 0.75
        elif name == "sword_hit":
            # Immediate blade bite, compact impact body and a short iron shiver.
            excitation = noise * math.exp(-t * 65) * 1.6
            value = (slow * 3.2 + low * 1.6 + grit * 0.78) * math.exp(-t * 43)
        elif name in ("dummy_down", "dummy_reset"):
            rising = name == "dummy_reset"
            motion = _gesture(t, 0.02, duration * 0.90) if rising else math.exp(-t * 12)
            bumps = chips if rising else chips * math.exp(-t * 6)
            excitation = noise * (motion * 0.45 + bumps)
            value = (slow * 1.9 + low * 1.1) * motion + breath * bumps * 0.45
        elif name in ("enemy_alert", "enemy_respawn"):
            rising = name == "enemy_respawn"
            strain = _gesture(t, 0.015, duration * 0.96)
            crumble = chips + 0.16
            excitation = (low * 1.5 + grit * crumble * 0.38) * strain
            value = (slow * 3.5 + low * 0.9 + breath * crumble * 0.65) * strain
            if not rising:
                value += (low * 1.8 + grit * 0.27) * transient
        elif name == "enemy_attack":
            # A grinding intake precedes the slam; its duration stays aligned
            # with the simulation's existing dodge warning.
            strain = _gesture(t, 0.005, duration * 0.98)
            excitation = (low * 1.5 + grit * chips * 0.42) * strain
            value = (slow * 3.8 + low * 1.0 + breath * (0.3 + chips)) * strain
        elif name in ("enemy_miss", "enemy_hurt"):
            excitation = noise * math.exp(-t * 39) * 1.35
            value = (slow * 2.6 + low * 1.3 + grit * (0.55 if name == "enemy_hurt" else 0.22)) * transient
            value += breath * chips * math.exp(-t * 15)
        elif name == "enemy_down":
            crack = math.exp(-t * 62)
            grind = _gesture(t, 0.03, 0.25)
            landing = _gesture(t, 0.26, 0.16)
            settle = _gesture(t, 0.33, 0.50)
            excitation = noise * (crack * 1.35 + grind * 0.21 + settle * chips * 0.62)
            excitation += low * landing * 2.3
            value = (low * 1.4 + grit * 0.72) * crack
            value += (low * 0.65 + breath * 0.52) * grind
            value += (slow * 5.3 + low * 0.88) * landing + (breath + grit * 0.30) * settle * chips
        elif name == "player_hurt":
            strike = math.exp(-t * 49)
            flinch = _gesture(t, 0.026, 0.17)
            excitation = noise * strike * 1.5 + low * flinch * 0.27
            value = slow * math.exp(-t * 31) * 4.6 + (low * 1.9 + grit * 0.55) * strike
            value += (breath * 1.0 + low * 0.32) * flinch
        elif name == "player_down":
            retreat = _gesture(t, 0.015, duration * 0.96) * math.exp(-t * 2)
            excitation = low * retreat * 1.2
            value = (slow * 3.8 + low * 0.45) * retreat
        elif name == "player_respawn":
            wake = _gesture(t, 0.015, duration * 0.96)
            excitation = low * wake * 0.9
            value = (slow * 2.9 + breath * 0.28) * wake
        elif name == "dialogue_line":
            # Two quiet, uneven syllable-like breaths mark a new line.
            voice = _gesture(t, 0.014, 0.13) + 0.65 * _gesture(t, 0.14, 0.16)
            pulse = 0.76 + 0.24 * math.sin(math.tau * (93 * t - 23 * t * t))
            value = (slow * 2.7 * pulse + low * 0.42 + breath * 0.16) * voice
        elif name == "dialogue_reveal":
            rustle = _gesture(t, 0.006, 0.084)
            value = (low * 0.55 + breath * 0.85) * rustle + slow * math.exp(-t * 48)
        elif name in ("dialogue_start", "dialogue_end"):
            cloth = _gesture(t, 0.008, duration * 0.88)
            settle = math.exp(-t * (31 if name == "dialogue_start" else 46))
            value = (low * 0.8 + breath * 0.26) * cloth + slow * settle * 1.15
        else:
            # Parchment, leather and a wooden catch distinguish map/help/pause
            # without confirmation beeps or fantasy reward jingles.
            paper = name in ("ui_map", "ui_help")
            fold = _gesture(t, 0.003, duration * (0.90 if paper else 0.65))
            click = math.exp(-t * (58 if name == "ui_toggle" else 39))
            value = (breath * (0.7 if paper else 0.20) + low * 0.8) * fold
            value += slow * click * 1.2 + grit * click * 0.12
            excitation = noise * click * (0.10 if paper else 0.26)
        value += body.sample(excitation)
        if not ambient:
            value *= min(1, t / 0.003, (duration - t) / 0.008)
        result.append(round(max(-0.95, min(0.95, value)) * 18000))
    if ambient:
        fade = rate // 5
        for index in range(fade):
            f = index / fade
            result[-fade + index] = round(result[-fade + index] * (1 - f) + result[index] * f)
        result = result[fade:]
    else:
        # Small, dark reflections belong to masonry/ritual effects. These are
        # baked samples, so room tails add no voices or device work in gameplay.
        echoes = ()
        if name in ("step_stone", "land", "land_stone", "enemy_step"):
            echoes = ((0.023, 0.12), (0.051, 0.045))
        elif name in ("staff_pickup", "fireball_cast", "enemy_alert", "enemy_down", "player_respawn"):
            echoes = ((0.043, 0.17), (0.097, 0.08))
        original = result[:]
        for seconds, gain in echoes:
            delay = round(rate * seconds)
            for index in range(delay, len(result)):
                result[index] = max(-30000, min(30000, result[index] + round(original[index - delay] * gain)))
    # Final fades follow all echoes. Loop joins remain smooth in either stereo
    # channel; mute/pause/voice-stealing fades continue to live in Mixer.
    fade = min(len(result) // 4, max(2, round(rate * 0.008)))
    if ambient:
        join = (result[0] + result[-1]) / 2
        for index in range(fade):
            amount = index / (fade - 1)
            amount = amount * amount * (3 - 2 * amount)
            result[index] = round(join + (result[index] - join) * amount)
            result[-1 - index] = round(join + (result[-1 - index] - join) * amount)
    else:
        for index in range(fade):
            amount = index / (fade - 1)
            result[index] = round(result[index] * amount)
            result[-1 - index] = round(result[-1 - index] * amount)
    rms = math.sqrt(sum(sample * sample for sample in result) / max(1, len(result)))
    target_db = (-17 if name == "river" else -19) if ambient else (-28 if name.startswith("ui_") or name in ("interaction_miss", "attack_empty", "sword_miss") else -21)
    if name == "sword_hit":
        target_db = -18
    elif name in ("player_hurt", "enemy_attack"):
        target_db = -19
    elif name in ("enemy_step", "enemy_hurt"):
        target_db = -24
    elif name.startswith("dialogue_"):
        target_db = -26
    gain = min(3.0, 32768 * 10 ** (target_db / 20) / max(1, rms),
               27000 / max(1, max(map(abs, result))))
    return array("h", (round(sample * gain) for sample in result))


class SoundBank:
    def __init__(self):
        varied = {"sword_swing", "sword_hit", "fireball_cast", "fireball_hit",
                  "fireball_impact", "staff_pickup", "item_drop", "water_splash",
                  "dummy_down", "dummy_reset", "enemy_step", "enemy_hurt",
                  "enemy_attack", "enemy_alert", "enemy_down", "enemy_respawn",
                  "player_hurt", *_DOOR_STRAINS}
        self.clips = {name: tuple(synthesize(name, v)
                                 for v in range(3 if name.startswith("step_") or name in varied else 1))
                      for name in EFFECTS}
        self.ambient = {name: synthesize(name) for name in ("wind", "river")}
        self.ambient_right = {}
        for name, clip in self.ambient.items():
            offset = SAMPLE_RATE // (7 if name == "wind" else 13)
            self.ambient_right[name] = clip[offset:] + clip[:offset]

    def write_preview(self, path):
        samples = array("h")
        for name in EFFECTS:
            for sample in self.clips[name][0]:
                samples.extend((sample, sample))
            samples.extend([0] * (SAMPLE_RATE // 5 * 2))
        # Include the flowing river and wind; the previous preview omitted both.
        mixer = Mixer(self, volume=0.55)
        for ambient in ((0.0, 0.5), (0.18, 0.0)):
            for _ in range(round(SAMPLE_RATE * 2 / BUFFER_FRAMES)):
                samples.extend(array("h", mixer.render(BUFFER_FRAMES, ambient)))
            for _ in range(8):
                samples.extend(array("h", mixer.render(BUFFER_FRAMES, enabled=False)))
        with wave.open(str(Path(path)), "wb") as output:
            output.setparams((2, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
            output.writeframes(samples.tobytes())


@dataclass
class Voice:
    samples: array
    left: float
    right: float
    position: int = 0
    priority: int = 0


class Mixer:
    MAX_VOICES = 8
    RELEASE_FRAMES = round(SAMPLE_RATE * 0.008)

    def __init__(self, bank, volume=0.55):
        self.bank, self.volume = bank, volume
        self.voices = []
        self._variation = 0
        self._ambient_position = [0, 0]
        self._ambient_gain = [0.0, 0.0]
        self._ambient_pan = 0.0
        self._master_gain = 0.0
        self._master_target = 0.0
        self._master_remaining = 0
        self._master_step = 0.0
        self._enabled_last = True
        # A fixed-size tail accumulator fades stolen/cleared voices without
        # increasing the number of live voices or allocating extra audio clips.
        self._tail_left = [0.0] * self.RELEASE_FRAMES
        self._tail_right = [0.0] * self.RELEASE_FRAMES
        self._tail_position = 0

    def _release(self, voice):
        count = min(self.RELEASE_FRAMES, len(voice.samples) - voice.position)
        for index in range(count):
            slot = (self._tail_position + index) % self.RELEASE_FRAMES
            value = voice.samples[voice.position + index] * (1 - index / max(1, count - 1))
            self._tail_left[slot] += value * voice.left
            self._tail_right[slot] += value * voice.right

    def release_all(self):
        for voice in self.voices:
            self._release(voice)
        self.voices.clear()

    def reset(self):
        """Discard stale audio after losing/reopening a device; resume with a fade."""
        self.voices.clear()
        self._tail_left[:] = [0.0] * self.RELEASE_FRAMES
        self._tail_right[:] = [0.0] * self.RELEASE_FRAMES
        self._ambient_gain[:] = [0.0, 0.0]
        self._master_gain = self._master_target = 0.0
        self._master_remaining = 0

    def add(self, event, listener=(0.0, 0.0, math.pi / 2)):
        name = LANDING_CUES.get(getattr(event, "surface", None), "land") if event.name == "land" else event.name
        if event.name == "terrain_step":
            name = TERRAIN_STEP_CUES.get(getattr(event, "surface", None), "terrain_step")
        # Custom/test banks can keep the original generic landing clip.
        if name not in self.bank.clips:
            name = event.name
        choices = self.bank.clips[name]
        samples = choices[self._variation % len(choices)]
        self._variation += 1
        gain, pan = event.strength, 0.0
        # Personal feedback stays centered even if an entrance respawn moves
        # the listener before the asynchronous worker consumes the event.
        personal = event.name in ("player_hurt", "player_down", "player_respawn")
        if not personal and event.x is not None and event.y is not None:
            dx, dy = event.x - listener[0], event.y - listener[1]
            distance = math.hypot(dx, dy)
            gain /= 1 + distance * 0.16
            pan = max(-0.85, min(0.85, (dx * math.sin(listener[2]) - dy * math.cos(listener[2])) / max(2.0, distance)))
        priority = (3 if event.name in ("player_hurt", "player_down")
                    else 2 if event.name in ("sword_hit", "fireball_hit", "fireball_impact",
                                             "enemy_attack", "enemy_down", "player_respawn")
                    or event.name.startswith("door_")
                    else 0 if event.name.startswith("step_") or event.name in ("enemy_step", "terrain_step")
                    else 1)
        if len(self.voices) >= self.MAX_VOICES:
            oldest = min(self.voices, key=lambda voice: voice.priority)
            if priority < oldest.priority:
                return
            self.voices.remove(oldest)
            self._release(oldest)
        self.voices.append(Voice(samples, gain * (1 - pan) * 0.65, gain * (1 + pan) * 0.65, priority=priority))

    def render(self, frames, ambient=(0.0, 0.0), enabled=True):
        if not enabled and self._enabled_last:
            self.release_all()
        self._enabled_last = enabled
        target_master = self.volume if enabled else 0.0
        if target_master != self._master_target:
            self._master_target = target_master
            self._master_remaining = max(1, round(SAMPLE_RATE * 0.012))
            self._master_step = (target_master - self._master_gain) / self._master_remaining
        if not enabled and self._master_gain == 0:
            self.reset()
            return bytes(frames * 4)
        left, right = [0.0] * frames, [0.0] * frames
        for i in range(min(frames, self.RELEASE_FRAMES)):
            slot = (self._tail_position + i) % self.RELEASE_FRAMES
            left[i], right[i] = self._tail_left[slot], self._tail_right[slot]
            self._tail_left[slot] = self._tail_right[slot] = 0.0
        self._tail_position = (self._tail_position + frames) % self.RELEASE_FRAMES
        for voice in self.voices:
            count = min(frames, len(voice.samples) - voice.position)
            for i in range(count):
                sample = voice.samples[voice.position + i]
                left[i] += sample * voice.left
                right[i] += sample * voice.right
            voice.position += count
        self.voices[:] = [voice for voice in self.voices if voice.position < len(voice.samples)]
        smoothing = 1 - math.exp(-1 / (SAMPLE_RATE * 0.065))
        pan_target = ambient[2] if len(ambient) > 2 else 0.0
        for channel, name in enumerate(("wind", "river")):
            target_gain = ambient[channel] if enabled else 0.0
            gain = self._ambient_gain[channel]
            clip = self.bank.ambient[name]
            other = self.bank.ambient_right[name]
            position = self._ambient_position[channel]
            if target_gain < 1e-6 and gain < 1e-6:
                self._ambient_position[channel] = (position + frames) % len(clip)
                if channel == 1:
                    self._ambient_pan = pan_target + (self._ambient_pan - pan_target) * (1 - smoothing) ** frames
                continue
            pan = self._ambient_pan if channel == 1 else 0.0
            settled = abs(target_gain - gain) < 1e-6 and (channel == 0 or abs(pan_target - pan) < 1e-6)
            if settled:
                gain = target_gain
                pan = pan_target if channel == 1 else 0.0
                gl, gr = gain * (1 - pan * 0.65), gain * (1 + pan * 0.65)
                for i in range(frames):
                    slot = (position + i) % len(clip)
                    left[i] += clip[slot] * gl
                    right[i] += other[slot] * gr
            else:
                for i in range(frames):
                    gain += (target_gain - gain) * smoothing
                    slot = (position + i) % len(clip)
                    left[i] += clip[slot] * gain * (1 - pan * 0.65)
                    right[i] += other[slot] * gain * (1 + pan * 0.65)
                    if channel == 1:
                        pan += (pan_target - pan) * smoothing
            if channel == 1:
                self._ambient_pan = pan
            self._ambient_gain[channel] = gain
            self._ambient_position[channel] = (position + frames) % len(clip)
        output = array("h")
        volume = self._master_gain
        for a, b in zip(left, right):
            # A continuous soft knee prevents hard clipping when effects overlap.
            for sample in (a * volume, b * volume):
                absolute = abs(sample)
                if absolute > 24500:
                    excess = absolute - 24500
                    sample = math.copysign(24500 + 8260 * excess / (8260 + excess), sample)
                output.append(round(sample))
            if self._master_remaining:
                volume += self._master_step
                self._master_remaining -= 1
                if not self._master_remaining:
                    volume = self._master_target
        self._master_gain = volume
        if not enabled and volume == 0:
            self._ambient_gain[:] = [0.0, 0.0]
        return output.tobytes()


class ThreadAudio:
    def __init__(self, enabled=True, volume=0.55, output_factory=WaveOutput, bank=None):
        self.bank = bank or SoundBank()
        self.mixer = Mixer(self.bank, volume)
        # Exercise both ambient mix paths before opening playback. Keep the
        # first-use setup and buffer allocation outside the live stream.
        for _ in range(20):
            self.mixer.render(BUFFER_FRAMES, (0.08, 0.08))
        self.mixer.reset()
        self.available, self.error = False, ""
        self._enabled = enabled
        self.listener = (0.0, 0.0, math.pi / 2)
        self.ambient = (0.0, 0.0)
        self._paused = False
        self._queue = queue.Queue(maxsize=32)
        self._stop = threading.Event()
        self._retry = threading.Event()
        self._thread = None
        self._output_factory = output_factory
        self.output = None
        self._epoch = 0
        self.blocks_rendered = 0
        self.recoveries = 0
        self.underruns = 0
        self.max_write_gap_ms = 0.0
        try:
            self.output = output_factory()
            self.available = True
        except OSError as error:
            self.error = str(error)
        self._thread = threading.Thread(target=self._run, name="monolith-audio", daemon=True)
        self._thread.start()

    @property
    def enabled(self):
        return self._enabled and self.available

    def emit(self, event):
        if event.name not in EFFECTS:
            raise ValueError(f"No sound registered for event: {event.name}")
        if self.enabled:
            try:
                self._queue.put_nowait((self._epoch, event))
            except queue.Full:
                pass

    def toggle(self):
        return self.set_muted(self._enabled and self.available)

    def set_muted(self, muted):
        if self.available and self._enabled == (not muted):
            return self.enabled
        self._enabled = not muted
        self._clear()
        if self._enabled and not self.available:
            self._retry.set()
        if self.enabled:
            self.emit(GameEvent("ui_toggle"))
        return self.enabled

    def set_volume(self, volume):
        # The mixer ramps any changed gain across the next output samples.
        self.mixer.volume = volume

    def _clear(self):
        # A full effect queue must never prevent mute/pause from discarding old
        # events. Controls use a generation, not a sentinel in the event queue.
        self._epoch += 1
        for _ in range(self._queue.maxsize):
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def pause(self, paused):
        if paused != self._paused:
            self._paused = paused
            self._clear()

    def _stream(self, output):
        pacer = StreamPacer(output.frames, getattr(output, "buffer_count", 3), time.perf_counter())
        seen_epoch = self._epoch
        while not self._stop.is_set():
            item = output.ready()
            if item is None:
                # Real device backpressure owns the playback clock. In
                # particular, immediately refill every returned buffer after a
                # scheduling delay rather than waiting for an old wall timer.
                pacer.blocked(time.perf_counter())
                if hasattr(output, "wait"):
                    output.wait(0.025)
                else:
                    self._stop.wait(0.003)
                continue
            remaining = pacer.delay(time.perf_counter())
            if remaining > 0:
                self._stop.wait(min(remaining, 0.01))
                continue
            if seen_epoch != self._epoch:
                seen_epoch = self._epoch
                self.mixer.release_all()
            for _ in range(32):
                try:
                    epoch, event = self._queue.get_nowait()
                except queue.Empty:
                    break
                if epoch == self._epoch:
                    self.mixer.add(event, self.listener)
            ambient = (0.0, 0.0) if self._paused else self.ambient
            output.write(item, self.mixer.render(output.frames, ambient, self.enabled))
            self.blocks_rendered += 1
            pacer.submitted()

    def _run(self):
        while not self._stop.is_set():
            if self.output is None:
                self._retry.wait(1.0)
                self._retry.clear()
                if self._stop.is_set():
                    break
                if not self._enabled:
                    continue
                try:
                    self.output = self._output_factory()
                    self.mixer.reset()
                    self._clear()
                    self.available, self.error = True, ""
                    self.recoveries += 1
                except OSError as error:
                    self.error = str(error)
                    continue
            output = self.output
            try:
                self._stream(output)
            except Exception as error:
                self.error, self.available = f"{type(error).__name__}: {error}", False
                self._clear()
            finally:
                self.underruns += getattr(output, "underruns", 0)
                self.max_write_gap_ms = max(self.max_write_gap_ms, getattr(output, "max_write_gap_ms", 0))
                output.close()
            if not self._stop.is_set():
                self.output = None

    def close(self):
        if self._stop.is_set():
            return
        if self.available and self._thread and self._thread.is_alive():
            self._enabled = False
            self._clear()
            # Let the fade and queued silence reach the device before reset.
            # This happens only at shutdown, never in the gameplay hot path.
            target = self.blocks_rendered + getattr(self.output, "buffer_count", 3) + 1
            deadline = time.perf_counter() + 0.25
            while self.available and self.blocks_rendered < target and time.perf_counter() < deadline:
                self._stop.wait(0.003)
        self._stop.set()
        self._retry.set()
        if self.output is not None and hasattr(self.output, "wake"):
            self.output.wake()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.available = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Audio:
    """One gameplay API; native playback is isolated, test sinks stay in-process."""

    def __init__(self, enabled=True, volume=0.55, output_factory=WaveOutput, bank=None):
        if os.name == "nt" and output_factory is WaveOutput:
            from .audio_process import ProcessAudio
            engine = ProcessAudio(enabled, volume, bank)
        else:
            engine = ThreadAudio(enabled, volume, output_factory, bank)
        object.__setattr__(self, "_engine", engine)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_engine"), name)

    def __setattr__(self, name, value):
        if name == "_engine" or "_engine" not in self.__dict__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._engine, name, value)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._engine.close()

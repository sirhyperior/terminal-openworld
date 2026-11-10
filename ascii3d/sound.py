"""Original fantasy Foley, bounded stereo mixing, and asynchronous Windows output.

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
    "step_gravel": 0.23, "step_metal": 0.27,
    "terrain_step": 0.18,
    "jump": 0.18, "land": 0.26, "water_splash": 0.32,
    "land_stone": 0.28, "land_grass": 0.27, "land_wood": 0.32,
    "land_water": 0.38, "land_gravel": 0.31, "land_metal": 0.38,
    "door_open": 0.70, "door_close": 0.65, "door_blocked": 0.18,
    "sword_pickup": 0.42, "sword_swing": 0.29, "sword_hit": 0.34,
    "sword_miss": 0.18, "attack_empty": 0.15,
    "staff_pickup": 0.48, "item_drop": 0.24,
    "fireball_cast": 0.65, "fireball_hit": 0.42,
    "fireball_impact": 0.38, "fireball_fizzle": 0.24,
    "dummy_down": 0.58, "dummy_reset": 0.48,
    "enemy_alert": 0.65, "enemy_step": 0.24, "enemy_attack": 0.42,
    "enemy_miss": 0.22, "enemy_hurt": 0.28,
    "enemy_down": 0.85, "enemy_respawn": 0.90,
    "player_hurt": 0.30, "player_down": 0.80, "player_respawn": 0.60,
    "interaction_miss": 0.10, "ui_map": 0.13, "ui_help": 0.14,
    "ui_pause": 0.16, "ui_reset": 0.25, "ui_exit": 0.18, "ui_toggle": 0.10,
}
LANDING_CUES = {surface: "land_" + surface
                for surface in ("stone", "grass", "wood", "water", "gravel", "metal")}
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
    for frequency, decay, gain in ((183, 0.016, 0.60), (487, 0.008, 0.32),
                                    (1127, 0.004, 0.16)):
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


def synthesize(name: str, variation: int = 0, rate: int = SAMPLE_RATE) -> array:
    """Layer filtered noise, resonances, and short echoes; no sampled game audio."""
    ambient = name in ("wind", "river")
    duration = 6.0 if ambient else EFFECTS[name]
    rng = random.Random(4127 + sum(map(ord, name)) * 31 + variation * 701)
    result = array("h")
    low = slow = 0.0
    pitch = 0.94 + variation * 0.055
    door = _door_creak(name, rng, rate, duration) if name in _DOOR_STRAINS else None
    for index in range(round(duration * rate)):
        t = index / rate
        noise = rng.uniform(-1, 1)
        low += (noise - low) * 0.17
        slow += (noise - slow) * 0.008
        if name == "wind":
            # Soft broad gusts with a little grass rustle remain audible on
            # small speakers, without a whistle or a constant bright hiss.
            gust = (0.70 + 0.18 * math.sin(math.tau * t / duration)
                    + 0.12 * math.sin(math.tau * t * 3 / duration + 1.1))
            rustle = max(0.0, math.sin(math.tau * t * 2 / duration + 0.4)) ** 3
            value = (low * 0.65 + slow * 2.6
                     + (noise - low) * rustle * 0.07) * gust
        elif name == "river":
            # Layered rushing/babbling noise, without the old steady tonal hum.
            flow = 0.85 + 0.10 * math.sin(math.tau * t / duration) + 0.05 * math.sin(math.tau * t * 3 / duration)
            value = (low * 1.1 + slow * 1.8 + (noise - low) * 0.14) * flow
        elif name == "terrain_step":
            body = math.sin(math.tau * t * 95 * pitch) * math.exp(-t * 32)
            value = body * 0.65 + low * math.exp(-t * 18) * 0.5
        elif name.startswith("step_"):
            body = math.exp(-t * 32) * math.sin(math.tau * pitch * (95 * t - 45 * t * t))
            if name == "step_stone":
                value = body * 0.7 + noise * math.exp(-t * 38) * 0.65 + low * math.exp(-t * 15) * 0.35
            elif name == "step_grass":
                value = body * 0.35 + (noise - low) * math.exp(-t * 26) * 0.30 + low * math.exp(-t * 13) * 0.7
            elif name == "step_wood":
                value = body * 0.85 + math.sin(math.tau * t * 245 * pitch) * math.exp(-t * 26) * 0.25 + noise * math.exp(-t * 60) * 0.35
            elif name == "step_gravel":
                grains = 0.35 + 0.65 * math.sin(t * 217 * pitch) ** 8
                value = body * 0.38 + (noise - low) * grains * math.exp(-t * 15) * 0.9 + low * math.exp(-t * 22) * 0.5
            elif name == "step_metal":
                ring = math.sin(math.tau * t * 390 * pitch) * 0.32 + math.sin(math.tau * t * 721 * pitch) * 0.13
                value = body * 0.62 + ring * math.exp(-t * 17) + noise * math.exp(-t * 65) * 0.4
            else:
                value = low * math.exp(-t * 12) + math.sin(math.tau * (240 * t - 280 * t * t)) * math.exp(-t * 17) * 0.3
        elif name.startswith("land_"):
            body = math.sin(math.tau * t * 64 * pitch) * math.exp(-t * 24)
            if name == "land_grass":
                value = body * 0.5 + low * math.exp(-t * 17) * 1.1 + (noise - low) * math.exp(-t * 18) * 0.15
            elif name == "land_wood":
                value = body * 0.95 + math.sin(math.tau * t * 181 * pitch) * math.exp(-t * 18) * 0.3 + noise * math.exp(-t * 45) * 0.3
            elif name == "land_gravel":
                crunch = (noise - low) * (0.3 + 0.7 * math.sin(t * 193) ** 8)
                value = body * 0.65 + crunch * math.exp(-t * 13) * 0.9 + low * math.exp(-t * 19) * 0.7
            elif name == "land_metal":
                ring = math.sin(math.tau * t * 293) * 0.28 + math.sin(math.tau * t * 547) * 0.16
                value = body * 0.85 + ring * math.exp(-t * 12) + noise * math.exp(-t * 48) * 0.45
            elif name == "land_water":
                value = body * 0.2 + (low * 1.6 + noise * 0.15) * math.exp(-t * 10)
                value += math.sin(math.tau * (225 * t - 210 * t * t)) * math.exp(-t * 12) * 0.28
            else:
                value = body * 0.9 + low * math.exp(-t * 22) * 1.4 + noise * math.exp(-t * 45) * 0.28
        elif door is not None:
            value = next(door)
        elif name == "land":
            value = (math.sin(math.tau * t * 76 * pitch) * 0.75 + low * 1.4) * math.exp(-t * 22)
        elif name == "water_splash":
            value = (low * 1.5 + noise * 0.17 + math.sin(math.tau * (280 * t - 250 * t * t)) * 0.2) * math.exp(-t * 10)
        elif name == "jump":
            value = (noise - low) * math.sin(math.pi * t / duration) ** 1.4 * 0.22 + low * math.exp(-t * 16) * 0.6
        elif name == "sword_pickup":
            ring = math.sin(math.tau * t * 615) * 0.2 + math.sin(math.tau * t * 1013) * 0.10
            value = ring * math.exp(-t * 11) + low * math.exp(-t * 28) * 0.7 + noise * math.exp(-t * 60) * 0.2
        elif name == "staff_pickup":
            shimmer = (math.sin(math.tau * t * 523 * pitch) * 0.32
                       + math.sin(math.tau * t * 784 * pitch) * 0.18)
            value = shimmer * math.exp(-t * 8) + low * math.exp(-t * 22) * 0.5
        elif name == "item_drop":
            value = (math.sin(math.tau * t * 117 * pitch) * 0.65
                     + low * 1.1 + noise * 0.12) * math.exp(-t * 28)
        elif name == "fireball_cast":
            # Ignition crack, rushing flame and a short falling fiery tail.
            rush = math.sin(math.pi * min(1, t / 0.38)) ** 1.5 if t < 0.38 else 0
            value = (low * 1.4 + (noise - low) * 0.20) * (rush + math.exp(-t * 25) * 0.5)
            value += math.sin(math.tau * pitch * (210 * t - 100 * t * t)) * math.exp(-t * 9) * 0.45
        elif name in ("fireball_hit", "fireball_impact"):
            value = (low * 1.6 + noise * 0.25) * math.exp(-t * 15)
            value += math.sin(math.tau * t * 69 * pitch) * math.exp(-t * 20) * 0.9
            if name == "fireball_hit":
                value += (noise - low) * math.exp(-t * 70) * 0.8
        elif name == "fireball_fizzle":
            value = (noise - low) * math.sin(math.pi * t / duration) * math.exp(-t * 12) * 0.65
        elif name in ("sword_swing", "sword_miss"):
            sweep = math.sin(math.pi * t / duration) ** (2 if name == "sword_swing" else 1.2)
            value = ((noise - low) * 0.25 + low * 0.8) * sweep
            value += slow * math.exp(-t * 12) * (0.4 if name == "sword_swing" else 0.15)
        elif name == "sword_hit":
            # A dry contact crack, solid thwack and brief blade bite. Keep the
            # impact immediate so it reads differently from the airy swing.
            body = math.sin(math.tau * t * 153 * pitch) * math.exp(-t * 26) * 0.85
            crack = (noise - low) * math.exp(-t * 90) * 0.80
            crunch = low * math.exp(-t * 35) * 1.1
            blade = (math.sin(math.tau * t * 1673 * pitch) * 0.22
                     + math.sin(math.tau * t * 2531 * pitch) * 0.10) * math.exp(-t * 75)
            value = body + crack + crunch + blade
        elif name in ("dummy_down", "dummy_reset"):
            settle = t if name == "dummy_down" else duration - t
            pulse = math.exp(-settle * 13) + 0.45 * math.exp(-abs(settle - 0.16) * 50)
            creak = math.sin(math.tau * (119 * t + 6 * math.sin(t * 23))) * 0.18
            value = (low * 1.1 + math.sin(math.tau * t * 83) * 0.6) * pulse
            value += creak * math.sin(math.pi * t / duration) + noise * pulse * 0.13
        elif name == "enemy_step":
            # The guardian's weight adds a low stone knock under the scrape.
            value = (math.sin(math.tau * t * 73 * pitch) * 0.85
                     + low * 1.0) * math.exp(-t * 30)
            value += (noise - low) * math.exp(-t * 20) * 0.20
        elif name in ("enemy_alert", "enemy_respawn"):
            rising = name == "enemy_respawn"
            envelope = math.sin(math.pi * t / duration) ** (1.5 if rising else 0.8)
            rumble = math.sin(math.tau * pitch * (61 * t + 9 * t * t))
            resonance = math.sin(math.tau * t * 183 * pitch) * 0.22
            value = (rumble * 0.65 + resonance + slow * 2.2) * envelope
            value += low * (0.35 if rising else 0.65) * math.exp(-t * 12)
        elif name == "enemy_attack":
            # A rising stone grind telegraphs the strike, leaving time to dodge.
            progress = t / duration
            grind = (low * 1.3 + (noise - low) * 0.18)
            tension = math.sin(math.tau * pitch * (97 * t + 130 * t * t)) * 0.35
            value = (grind + tension) * math.sin(math.pi * progress) ** 0.8
        elif name == "enemy_miss":
            value = (low * 1.4 + noise * 0.15) * math.exp(-t * 24)
            value += math.sin(math.tau * t * 87 * pitch) * math.exp(-t * 26) * 0.65
        elif name == "enemy_hurt":
            value = (noise * 0.30 + low * 1.1) * math.exp(-t * 32)
            value += (math.sin(math.tau * t * 307 * pitch) * 0.45
                      + math.sin(math.tau * t * 479 * pitch) * 0.20) * math.exp(-t * 21)
        elif name == "enemy_down":
            collapse = math.exp(-t * 9) + 0.55 * math.exp(-abs(t - 0.19) * 38)
            value = (low * 1.5 + noise * 0.14) * collapse
            value += math.sin(math.tau * pitch * (81 * t - 18 * t * t)) * math.exp(-t * 8) * 0.65
        elif name == "player_hurt":
            value = (math.sin(math.tau * t * 61 * pitch) * 0.9
                     + low * 1.1 + noise * 0.10) * math.exp(-t * 22)
            value += (noise - low) * math.exp(-t * 55) * 0.4
        elif name == "player_down":
            falling = math.sin(math.tau * pitch * (106 * t - 45 * t * t))
            value = (falling * 0.65 + slow * 2.4) * math.sin(math.pi * t / duration) * math.exp(-t * 3)
        elif name == "player_respawn":
            rise = math.sin(math.pi * t / duration) ** 1.5
            value = (math.sin(math.tau * t * 262 * pitch) * 0.25
                     + math.sin(math.tau * t * 393 * pitch) * 0.16
                     + low * 0.65) * rise
        elif name == "attack_empty":
            value = low * math.exp(-t * 25) * 0.8 + (noise - low) * math.sin(math.pi * t / duration) ** 2 * 0.16
        else:
            # Leather/paper-like UI feedback, with a small muted wooden click.
            value = low * math.exp(-t * 25) * 0.65 + math.sin(math.tau * t * 430 * pitch) * math.exp(-t * 75) * 0.15
        if not ambient:
            value *= min(1, t / 0.003, (duration - t) / 0.008)
        result.append(round(max(-0.95, min(0.95, value)) * 18000))
    if ambient:
        fade = rate // 5
        for index in range(fade):
            f = index / fade
            result[-fade + index] = round(result[-fade + index] * (1 - f) + result[index] * f)
        result = result[fade:]
    elif name in ("step_stone", "land", "land_stone"):
        for delay, gain in ((round(rate * 0.027), 0.15), (round(rate * 0.061), 0.07)):
            original = result[:]
            for index in range(delay, len(result)):
                result[index] = max(-30000, min(30000, result[index] + round(original[index - delay] * gain)))
    # Apply the final envelope AFTER echoes, and join ambient loops smoothly.
    # Otherwise a voice/loop can stop at a nonzero sample and produce a click.
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
        target_db = -18  # Contact must remain clear over its simultaneous whoosh.
    elif name in ("player_hurt", "enemy_attack"):
        target_db = -19
    elif name in ("enemy_step", "enemy_hurt"):
        target_db = -24
    gain = min(3.0, 32768 * 10 ** (target_db / 20) / max(1, rms),
               27000 / max(1, max(map(abs, result))))
    result = array("h", (round(sample * gain) for sample in result))
    return result


class SoundBank:
    def __init__(self):
        varied = {"sword_swing", "sword_hit", "fireball_cast", "fireball_hit",
                  "fireball_impact", "enemy_step", "enemy_hurt", "enemy_attack",
                  *_DOOR_STRAINS}
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
        self._enabled = True if not self.available else not self._enabled
        self._clear()
        if not self.available:
            self._retry.set()
        if self.enabled:
            self.emit(GameEvent("ui_toggle"))
        return self.enabled

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

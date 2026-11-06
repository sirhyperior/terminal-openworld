from array import array
from collections import deque
import math
import threading
import time
from types import SimpleNamespace
import unittest

from ascii3d.audio_output import SAMPLE_RATE, StreamPacer
from ascii3d.audio_process import ProcessAudio
from ascii3d.events import GameEvent
from ascii3d.sound import Audio, Mixer, SoundBank
from ascii3d.soundscape import Soundscape
from ascii3d.world import GRASS, WATER, World, build_world


def constant_bank():
    clip = array("h", [10000] * SAMPLE_RATE)
    silence = array("h", [0] * SAMPLE_RATE)
    return SimpleNamespace(clips={"door_open": (clip,), "ui_pause": (clip,)},
                           ambient={"wind": silence, "river": silence},
                           ambient_right={"wind": silence, "river": silence})


class ProcessTestOutput:
    frames = 512

    def ready(self):
        return True

    def write(self, item, pcm):
        pass

    def close(self):
        pass


class ProcessFailingOutput(ProcessTestOutput):
    def ready(self):
        raise OSError("Disconnected test device")


class ProcessRecoveringFactory:
    def __init__(self):
        self.count = 0

    def __call__(self):
        self.count += 1
        return ProcessFailingOutput() if self.count == 1 else ProcessTestOutput()


class AudioProcessTests(unittest.TestCase):
    def test_isolated_worker_plays_controls_and_closes_without_leaking_process(self):
        audio = ProcessAudio(bank=constant_bank(), output_factory=ProcessTestOutput)
        try:
            self.assertTrue(audio.available, audio.error)
            audio.ambient = (0.1, 0.3)
            audio.listener = (2, 4, 0)
            audio.emit(GameEvent("door_open"))
            time.sleep(0.07)
            self.assertGreater(audio.blocks_rendered, 0)
            self.assertFalse(audio.toggle())
            self.assertTrue(audio.toggle())
            audio.pause(True)
            audio.emit(GameEvent("ui_pause"))
            self.assertEqual(audio.error, "")
        finally:
            audio.close()
        self.assertFalse(audio._process.is_alive())
        self.assertFalse(audio.enabled)

    def test_isolated_worker_reports_recovery_and_clears_stale_device_error(self):
        audio = ProcessAudio(bank=constant_bank(), output_factory=ProcessRecoveringFactory())
        try:
            deadline = time.perf_counter() + 0.3
            while not audio.error and time.perf_counter() < deadline:
                time.sleep(0.005)
            self.assertIn("Disconnected", audio.error)
            audio.toggle()
            deadline = time.perf_counter() + 1.5
            while (not audio.available or audio.error) and time.perf_counter() < deadline:
                time.sleep(0.005)
            self.assertTrue(audio.available, audio.error)
            self.assertEqual(audio.error, "")
            self.assertEqual(audio.recoveries, 1)
        finally:
            audio.close()


class SignalContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = SoundBank()

    def test_one_shots_end_at_zero_even_after_reverb(self):
        for name, variants in self.bank.clips.items():
            for clip in variants:
                with self.subTest(effect=name):
                    self.assertEqual((clip[0], clip[-1]), (0, 0))

    def test_ambient_loop_boundary_is_continuous_in_both_channels(self):
        for clips in (self.bank.ambient, self.bank.ambient_right):
            for name, clip in clips.items():
                # The rotated stereo channel joins at an ordinary neighboring
                # sample; its jump must remain within normal noise amplitude.
                typical = math.sqrt(sum((b - a) ** 2 for a, b in zip(clip, clip[1:])) / (len(clip) - 1))
                self.assertLess(abs(clip[0] - clip[-1]), max(2, typical * 3), name)
        self.assertEqual(self.bank.ambient["river"][0], self.bank.ambient["river"][-1])

    def test_mute_and_resume_ramp_without_a_hard_cut_or_replaying_old_effects(self):
        mixer = Mixer(constant_bank(), volume=1)
        mixer.add(GameEvent("door_open"))
        before = array("h", mixer.render(512))
        muted = array("h", mixer.render(512, enabled=False))
        resumed = array("h", mixer.render(512))
        joined = before[::2] + muted[::2]
        self.assertLess(max(abs(b - a) for a, b in zip(joined, joined[1:])), 200)
        self.assertGreater(muted[0], 0)
        self.assertTrue(all(value == 0 for value in muted[-100:]))
        self.assertTrue(all(value == 0 for value in resumed))

    def test_pause_and_voice_stealing_release_active_waveforms(self):
        mixer = Mixer(constant_bank(), volume=1)
        mixer.add(GameEvent("door_open"))
        before = array("h", mixer.render(512))
        mixer.release_all()
        after = array("h", mixer.render(512))
        joined = before[::2] + after[::2]
        self.assertLess(max(abs(b - a) for a, b in zip(joined, joined[1:])), 200)
        self.assertEqual(after[-1], 0)
        for _ in range(20):
            mixer.add(GameEvent("door_open"))
        self.assertLessEqual(len(mixer.voices), Mixer.MAX_VOICES)
        self.assertEqual(len(mixer._tail_left), Mixer.RELEASE_FRAMES)

    def test_ambient_fades_are_independent_of_audio_block_boundaries(self):
        first, split = Mixer(self.bank), Mixer(self.bank)
        expected = first.render(1024, (0.18, 0.5, 0.3))
        actual = split.render(512, (0.18, 0.5, 0.3)) + split.render(512, (0.18, 0.5, 0.3))
        self.assertEqual(expected, actual)


class PlaybackSchedulingTests(unittest.TestCase):
    def test_driver_backpressure_resynchronizes_instead_of_waiting_on_wall_clock(self):
        pacer = StreamPacer(512, 5, 0)
        for _ in range(5):
            self.assertEqual(pacer.delay(0), 0)
            pacer.submitted()
        self.assertGreater(pacer.delay(0), 0)
        for tick in range(1, 100):
            # A faster device clock makes a buffer available before the old
            # wall-clock deadline. Refilling it must not be delayed.
            now = tick * 0.018
            pacer.blocked(now)
            self.assertEqual(pacer.delay(now), 0)
            pacer.submitted()

    def test_stream_handles_a_faster_device_clock_without_emptying_queue(self):
        class FastDevice:
            frames, buffer_count = 512, 3

            def __init__(self):
                self.queue = deque()
                self.started = False
                self.underruns = 0

            def ready(self):
                now = time.perf_counter()
                while self.queue and self.queue[0] <= now:
                    self.queue.popleft()
                if self.started and not self.queue:
                    self.underruns += 1
                    self.started = False
                return True if len(self.queue) < self.buffer_count else None

            def write(self, item, pcm):
                now = time.perf_counter()
                self.queue.append(max(now, self.queue[-1] if self.queue else now) + 0.016)
                if len(self.queue) == self.buffer_count:
                    self.started = True

            def close(self):
                pass

        device = FastDevice()
        with Audio(output_factory=lambda: device, bank=constant_bank()) as audio:
            audio.emit(GameEvent("door_open"))
            time.sleep(0.35)
        self.assertEqual(device.underruns, 0)

    def test_full_effect_queue_cannot_drop_pause_or_replay_stale_events(self):
        gate = threading.Event()

        class GatedDevice:
            frames = 512

            def ready(self):
                return True if gate.is_set() else None

            def write(self, item, pcm):
                pass

            def close(self):
                pass

        with Audio(output_factory=GatedDevice, bank=constant_bank()) as audio:
            for _ in range(40):
                audio.emit(GameEvent("door_open"))
            audio.pause(True)
            self.assertTrue(audio._queue.empty())
            gate.set()
            time.sleep(0.04)
            self.assertFalse(audio.mixer.voices)

    def test_device_loss_can_recover_and_discards_old_effects(self):
        lost = threading.Event()

        class FailingDevice:
            frames = 512

            def ready(self):
                lost.set()
                raise OSError("Device disconnected")

            def close(self):
                pass

        class RecoveredDevice:
            frames = 512

            def ready(self):
                return True

            def write(self, item, pcm):
                pass

            def close(self):
                pass

        devices = iter((FailingDevice(), RecoveredDevice()))
        with Audio(output_factory=lambda: next(devices), bank=constant_bank()) as audio:
            self.assertTrue(lost.wait(0.2))
            deadline = time.perf_counter() + 0.2
            while audio.available and time.perf_counter() < deadline:
                time.sleep(0.002)
            self.assertFalse(audio.available)
            audio.toggle()
            deadline = time.perf_counter() + 0.3
            while not audio.available and time.perf_counter() < deadline:
                time.sleep(0.002)
            self.assertTrue(audio.available)
            self.assertEqual(audio.recoveries, 1)
            self.assertEqual(audio.error, "")


class RiverAudioTests(unittest.TestCase):
    def test_river_level_and_stereo_direction_follow_actual_water_tiles(self):
        world = World.empty(12, 12, 10)
        world.box(0, 0, 0, 12, 12, 1, GRASS)
        world.box(0, 8, 0, 12, 11, 1, WATER)
        soundscape = Soundscape(world)
        near = soundscape.at(5.5, 7.5, math.pi / 2)
        far = soundscape.at(5.5, 1.5, math.pi / 2)
        facing_east = soundscape.at(5.5, 7.5, 0)
        self.assertGreater(near[1], far[1])
        self.assertLess(facing_east[2], 0)
        self.assertLess(abs(near[2]), 0.1)
        world.box(0, 8, 0, 12, 11, 1, GRASS)
        self.assertEqual(soundscape.at(5.5, 7.5, 0)[1], 0)

    def test_bridge_and_banks_have_audible_continuous_flow_without_footsteps(self):
        scene = Soundscape(build_world())
        wind, river, pan = scene.at(24.5, 86.5, math.pi / 2)
        self.assertGreater(river, 0.3)
        mixer = Mixer(SoundBank())
        pcm = array("h")
        for _ in range(40):
            pcm.extend(array("h", mixer.render(512, (0, river, pan))))
        rms = math.sqrt(sum(sample * sample for sample in pcm) / len(pcm))
        self.assertGreater(rms, 600)
        self.assertNotEqual(pcm[::2], pcm[1::2])


if __name__ == "__main__":
    unittest.main()

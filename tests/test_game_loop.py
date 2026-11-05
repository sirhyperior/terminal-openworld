"""Run scripted frames through the real app loop without terminal/device I/O."""

from contextlib import ExitStack
import unittest
from unittest.mock import patch

from ascii3d.app import FrameRateCounter, main
from ascii3d.combat import CombatState, Enemy, SwordPickup
from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.terminal import Keys
from ascii3d.world import FLOOR, World


class GameLoopTests(unittest.TestCase):
    def run_frames(self, script, world, player, *, demo=False, frame_work=None,
                   clock_tick=1 / 60, advance_sleep=False):
        events, states, pauses, frames = [], [], [], []
        clock = 0.0

        def now():
            nonlocal clock
            clock += clock_tick
            return clock

        def sleep(seconds):
            nonlocal clock
            if advance_sleep:
                clock += seconds

        class FakeTerminal:
            def __init__(self, *args):
                self.keyboard = self
                self.index = 0

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def poll(self):
                nonlocal clock
                if frame_work:
                    clock += frame_work[self.index].get("input", 0)
                pressed, down = script[self.index]
                self.index += 1
                return Keys(set(down), set(pressed))

            def size(self):
                return 60, 20

            def draw(self, frame):
                nonlocal clock
                if frame_work:
                    clock += frame_work[self.index - 1].get("output", 0)
                frames.append(frame)
                combat = world.combat
                states.append((combat.has_sword, combat.cooldown, combat.swing_remaining,
                               combat.enemies[0].down_remaining, combat.enemies[0].hp))

        class FakeAudio:
            available = enabled = True

            def __init__(self, *args):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def emit(self, event):
                events.append(event)

            def pause(self, paused):
                pauses.append(paused)

        class FakeRenderer:
            def __init__(self, *args):
                pass

            def frame(self, *args, **kwargs):
                return (args, kwargs)

        with ExitStack() as stack:
            for name, value in (("Terminal", FakeTerminal), ("Audio", FakeAudio),
                                ("Renderer", FakeRenderer), ("build_world", lambda: world),
                                ("spawn_player", lambda outside: Player(x=player.x, y=player.y, yaw=player.yaw)),
                                ("time.perf_counter", now), ("time.sleep", sleep)):
                stack.enter_context(patch("ascii3d.app." + name, value))
            args = ["--frames", str(len(script))]
            if demo:
                args.append("--demo")
            self.assertEqual(main(args), 0)
        self.assertTrue(all(event.name in EFFECTS for event in events))
        return events, states, pauses, frames

    def test_hud_fps_tracks_actual_completed_frames_and_counts_output_stalls(self):
        world = self.make_world()
        # A 5 ms frame waits for the 40 FPS cap; the next spends 200 ms in
        # input/output. Measure both, independently of the physics dt clamp.
        work = [{"input": 0.002, "output": 0.003},
                {"input": 0.10, "output": 0.10}, {}]
        _, _, _, frames = self.run_frames([((), ())] * 3, world,
                                          Player(x=8.5, y=4.5), frame_work=work,
                                          clock_tick=0, advance_sleep=True)
        rates = [frame[0][3] for frame in frames]
        self.assertEqual(rates[0], 0)
        self.assertAlmostEqual(rates[1], 40)
        self.assertAlmostEqual(rates[2], 2 / 0.225)

    def make_world(self):
        world = World.empty(24, 24, 10)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.combat = CombatState(pickups=[SwordPickup(8.5, 6.5)],
                                   enemies=[Enemy("Training dummy", 8.5, 7.2)])
        return world

    def test_e_q_pause_help_and_reset_use_real_loop_and_route_sound(self):
        world = self.make_world()
        script = [({"e", "q"}, {"q"}), ({"p", "e", "q"}, ()), ((), ()),
                  ({"p"}, ()), ({"h", "q"}, ()), ((), ()), ({"h"}, ()),
                  ({"r"}, ()), ((), {"q"})]
        events, states, pauses, frames = self.run_frames(script, world, Player(x=8.5, y=4.5))
        names = [event.name for event in events]
        self.assertEqual(names.count("sword_pickup"), 1)
        self.assertEqual(names.count("sword_swing"), 1)
        self.assertEqual(names.count("sword_hit"), 1)
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[1], states[2])
        self.assertLess(states[3][1], states[2][1])
        self.assertEqual(states[3], states[4])
        self.assertEqual(states[4], states[5])
        self.assertTrue(all(state[0] for state in states))
        self.assertEqual(world.combat.enemies[0].hp, 2)
        self.assertEqual(pauses, [False, True, True, False, True, True, False, False, False])
        self.assertAlmostEqual(frames[-1][0][0].yaw, Player().yaw)

    def test_downed_reset_freezes_while_paused_and_emits_on_resume(self):
        world = self.make_world()
        enemy = world.combat.enemies[0]
        enemy.hp, enemy.down_remaining = 0, 0.04
        events, states, _, _ = self.run_frames([({"p"}, ()), ((), ()), ({"p"}, ()), ((), ())],
                                               world, Player(x=8.5, y=4.5))
        self.assertEqual(states[0][3], 0.04)
        self.assertEqual(states[1][3], 0.04)
        self.assertEqual(sum(event.name == "dummy_reset" for event in events), 1)
        self.assertEqual(enemy.hp, 3)

    def test_demo_can_collect_a_pickup_without_assuming_door_fields(self):
        world = self.make_world()
        events, _, _, _ = self.run_frames([((), ())], world, Player(x=8.5, y=4.5), demo=True)
        self.assertIn("sword_pickup", [event.name for event in events])


class FrameRateTests(unittest.TestCase):
    def test_constant_rate_is_live_and_keeps_only_recent_samples(self):
        counter = FrameRateCounter()
        self.assertEqual(counter.update(0), 0)
        for frame in range(1, 401):
            self.assertAlmostEqual(counter.update(frame / 40), 40)
        self.assertLessEqual(len(counter._starts), 42)

    def test_uneven_frames_report_frames_per_elapsed_time(self):
        counter = FrameRateCounter()
        counter.update(0)
        counter.update(0.025)
        self.assertAlmostEqual(counter.update(0.075), 2 / 0.075)
        # Averaging the individual 40 and 20 FPS values would report 30.

    def test_long_stalls_are_not_clamped_by_the_physics_time_limit(self):
        counter = FrameRateCounter()
        counter.update(0)
        self.assertAlmostEqual(counter.update(2), 0.5)
        self.assertLess(counter.update(2.025), 1)
        for frame in range(2, 43):
            rate = counter.update(2 + frame / 40)
        self.assertAlmostEqual(rate, 40)

    def test_rate_changes_replace_old_samples_within_one_second(self):
        counter = FrameRateCounter()
        for frame in range(41):
            counter.update(frame / 40)
        for frame in range(1, 21):
            rate = counter.update(1 + frame / 20)
        self.assertAlmostEqual(rate, 20)


if __name__ == "__main__":
    unittest.main()

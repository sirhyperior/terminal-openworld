"""Run scripted frames through the real app loop without terminal/device I/O."""

from contextlib import ExitStack
import io
import unittest
from unittest.mock import Mock, patch

from ascii3d.app import FrameRateCounter, main
from ascii3d.combat import FIRE_STAFF, CombatState, Enemy, WeaponPickup
from ascii3d.player import Player
from ascii3d.sound import EFFECTS
from ascii3d.terminal import Keys, WindowsMouse
from ascii3d.world import FLOOR, World


class GameLoopTests(unittest.TestCase):
    def run_frames(self, script, world, player, *, demo=False, frame_work=None,
                   clock_tick=1 / 60, advance_sleep=False, sizes=None, mouse=None, keyboard_look=False,
                   fail_render=False, capture_error="", native_mouse=None, region=None, max_cells=None):
        events, states, pauses, frames = [], [], [], []
        self.capture_states = []
        captures = self.capture_states
        terminal_budgets = self.terminal_budgets = []
        player_positions = self.player_positions = []
        native_states = self.native_capture_states = []
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
            def __init__(self, max_cells=None):
                terminal_budgets.append(max_cells)
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
                dx, dy = mouse[self.index - 1] if mouse else (0, 0)
                return Keys(set(down), set(pressed), dx, dy)

            def size(self):
                return sizes[self.index - 1] if sizes else (60, 20)

            def set_mouse_capture(self, active):
                captures.append(active)
                self.mouse_captured = active and not capture_error
                self.mouse_error = capture_error if active else ""
                if native_mouse is not None:
                    native_mouse.set_capture(active)
                    self.mouse_captured = native_mouse.captured
                    native_states.append((native_mouse.captured, native_mouse.pointer.clip()))

            def draw(self, frame):
                nonlocal clock
                if frame_work:
                    clock += frame_work[self.index - 1].get("output", 0)
                frames.append(frame)
                live_player = frame[0][0]
                player_positions.append((live_player.x, live_player.y, live_player.z))
                combat = world.combat
                states.append((combat.held_item is not None, combat.cooldown, combat.swing_remaining,
                               combat.enemies[0].down_remaining, combat.enemies[0].hp,
                               tuple((ball.x, ball.y, ball.z) for ball in combat.fireballs),
                               frame[0][0].yaw, frame[0][0].pitch))

        class FakeAudio:
            available = enabled = True

            def __init__(self, *args):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self_capture = captures[-1] if captures else False
                if self_capture:
                    raise AssertionError("Mouse must release before audio drains")

            def emit(self, event):
                events.append(event)

            def pause(self, paused):
                pauses.append(paused)

        class FakeRenderer:
            def __init__(self, *args):
                pass

            def prepare_world(self):
                pass

            def frame(self, *args, **kwargs):
                if fail_render:
                    raise OSError("simulated renderer failure")
                return (args, kwargs)

        with ExitStack() as stack:
            if fail_render:
                stack.enter_context(patch("ascii3d.app.sys.stderr", io.StringIO()))
            for name, value in (("Terminal", FakeTerminal), ("Audio", FakeAudio),
                                ("Renderer", FakeRenderer), ("build_world", lambda: world),
                                ("spawn_player", lambda outside: Player(x=player.x, y=player.y, yaw=player.yaw)),
                                ("time.perf_counter", now), ("time.sleep", sleep)):
                stack.enter_context(patch("ascii3d.app." + name, value))
            args = ["--frames", str(len(script))]
            if keyboard_look:
                args.append("--keyboard-look")
            if demo:
                args.append("--demo")
            if region:
                args.extend(("--region", region))
            if max_cells is not None:
                args.extend(("--max-cells", str(max_cells)))
            self.assertEqual(main(args), 1 if fail_render else 0)
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

    def test_viewport_defaults_to_full_terminal_and_accepts_an_explicit_large_budget(self):
        for budget in (None, 4800, 24000):
            with self.subTest(budget=budget):
                _, _, _, frames = self.run_frames(
                    [((), ())], self.make_world(), Player(x=8.5, y=4.5),
                    max_cells=budget, sizes=[(240, 80)])
                self.assertEqual(self.terminal_budgets, [budget])
                self.assertEqual(frames[0][0][1:3], (240, 80))

    def test_viewport_budget_below_playable_minimum_is_rejected_before_loading(self):
        for budget in ("0", "1199"):
            with self.subTest(budget=budget), patch("ascii3d.app.sys.stderr", io.StringIO()), \
                    patch("ascii3d.app.build_world") as build:
                with self.assertRaises(SystemExit) as raised:
                    main(["--max-cells", budget])
                self.assertEqual(raised.exception.code, 2)
                build.assert_not_called()

    def test_resize_grows_shrinks_and_resumes_at_the_minimum_with_input_and_audio(self):
        sizes = [(120, 40), (240, 80), (40, 10), (1, 1), (60, 20)]
        for keyboard in (False, True):
            with self.subTest(keyboard=keyboard):
                world = self.make_world()
                world.combat.cooldown = 1.0
                script = [((), {"w", "right"})] * len(sizes)
                _, states, pauses, frames = self.run_frames(
                    script, world, Player(x=8.5, y=4.5), sizes=sizes,
                    keyboard_look=keyboard, mouse=[(20, 10)] * len(sizes))
                self.assertEqual([frame[0][1:3] for frame in frames], sizes)
                self.assertEqual(pauses, [False, False, True, True, False])
                self.assertEqual(self.capture_states,
                                 [not keyboard, not keyboard, False, False, not keyboard, False])
                self.assertEqual(states[1], states[2])
                self.assertEqual(states[2], states[3])
                self.assertEqual(self.player_positions[1], self.player_positions[2])
                self.assertEqual(self.player_positions[2], self.player_positions[3])
                self.assertNotEqual(self.player_positions[0], self.player_positions[1])
                self.assertNotEqual(self.player_positions[3], self.player_positions[4])
                times = [frame[1]["time_seconds"] for frame in frames]
                self.assertEqual(times[1], times[2])
                self.assertEqual(times[2], times[3])
                self.assertGreater(times[4], times[3])

    def make_world(self):
        world = World.empty(24, 24, 10)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.combat = CombatState(pickups=[WeaponPickup(8.5, 6.5)],
                                   enemies=[Enemy("Training dummy", 8.5, 7.2)])
        return world

    def test_e_click_pause_help_and_reset_use_real_loop_and_route_sound(self):
        world = self.make_world()
        script = [({"e", "attack"}, {"attack"}), ({"p", "e", "attack"}, ()), ((), ()),
                  ({"p"}, ()), ({"h", "attack"}, ()), ((), ()), ({"h"}, ()),
                  ({"r"}, ()), ((), {"attack"})]
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

    def test_empty_e_keeps_quiet_feedback_without_an_instruction_notice(self):
        events, _, _, frames = self.run_frames([({"e"}, ())], self.make_world(),
                                               Player(x=3.5, y=3.5))
        self.assertEqual([event.name for event in events], ["interaction_miss"])
        self.assertEqual(frames[0][1]["notice"], "")

    def test_defeat_returns_to_entrance_with_health_and_inventory_preserved(self):
        world = self.make_world()
        held = WeaponPickup(0, 0, collected=True)
        world.combat.held_item = held
        enemy_hp = world.combat.enemies[0].hp
        hits = 0

        def fatal_hit(dt, current_world, player):
            nonlocal hits
            hits += 1
            return player.take_damage(player.max_hp) if hits == 1 else []

        with patch.object(world.combat, "update", side_effect=fatal_hit):
            events, _, _, frames = self.run_frames([((), ()), ((), ())], world,
                                                   Player(x=8.5, y=4.5))
        names = [event.name for event in events]
        self.assertEqual(names, ["player_hurt", "player_down", "player_respawn"])
        player = frames[-1][0][0]
        self.assertEqual((player.x, player.y, player.hp), (8.5, 4.5, 10))
        self.assertIs(world.combat.held_item, held)
        self.assertEqual(world.combat.enemies[0].hp, enemy_hp)
        self.assertIn("restored at the entrance", frames[-1][1]["notice"])

    def test_region_start_and_reset_use_the_same_elevated_entrance(self):
        world = self.make_world()
        world.box(0, 0, 2, 24, 24, 3, FLOOR)
        held = WeaponPickup(0, 0, collected=True)
        world.combat.held_item = held
        with patch("ascii3d.app.spawn_region", side_effect=lambda region:
                   Player(x=8.5, y=4.5, z=3, yaw=0)) as spawn:
            events, _, _, frames = self.run_frames([((), {"w"}), ({"r"}, ())], world,
                                                   Player(x=8.5, y=4.5), region="ridge")
        self.assertEqual(spawn.call_count, 2)
        self.assertTrue(all(call.args == ("ridge",) for call in spawn.call_args_list))
        self.assertGreater(frames[0][0][0].x, 8.5)
        player = frames[1][0][0]
        self.assertEqual((player.x, player.y, player.hp), (8.5, 4.5, 10))
        self.assertAlmostEqual(player.z, 3, places=5)
        self.assertIs(world.combat.held_item, held)
        self.assertIn("ui_reset", [event.name for event in events])

    def test_staff_swap_cast_pause_help_small_terminal_and_reset_route_real_events(self):
        world = self.make_world()
        world.combat.pickups[0].weapon = FIRE_STAFF
        sword = WeaponPickup(0, 0, collected=True)
        world.combat.held_item = sword
        world.combat.enemies[0].y = 14.5
        script = [({"e", "attack"}, ()), ({"p", "attack"}, ()), ((), ()), ({"p"}, ()),
                  ({"h", "attack"}, ()), ((), ()), ({"h"}, ()), ({"attack"}, ()), ({"r"}, ()),
                  ((), ())]
        sizes = [(60, 20)] * len(script)
        sizes[7] = (40, 10)
        events, states, _, _ = self.run_frames(script, world, Player(x=8.5, y=4.5), sizes=sizes)
        names = [e.name for e in events]
        self.assertEqual(names.count("item_drop"), 1)
        self.assertEqual(names.count("staff_pickup"), 1)
        self.assertEqual(names.count("fireball_cast"), 1)
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[1], states[2])
        self.assertEqual(states[3], states[4])
        self.assertEqual(states[4], states[5])
        self.assertEqual(states[6], states[7])
        self.assertNotEqual(states[8][5], states[7][5])
        self.assertEqual(world.combat.held_item.weapon, FIRE_STAFF)
        self.assertFalse(sword.collected)

    def test_mouse_look_applies_once_per_frame_not_per_physics_step(self):
        _, states, _, _ = self.run_frames([((), ())], self.make_world(),
                                          Player(x=8.5, y=4.5), mouse=[(40, -20)], clock_tick=0.1)
        self.assertAlmostEqual(states[0][6], Player().yaw - 0.1)
        self.assertAlmostEqual(states[0][7], 0.05)
        self.assertEqual(self.capture_states, [True, False])

    def test_mouse_motion_and_attack_are_dispatched_in_the_same_frame(self):
        world = self.make_world()
        world.combat.held_item = WeaponPickup(0, 0, collected=True)
        events, states, _, _ = self.run_frames([({"attack"}, ())], world,
                                               Player(x=8.5, y=4.5), mouse=[(20, 10)])
        self.assertEqual([event.name for event in events], ["sword_swing", "sword_hit"])
        self.assertAlmostEqual(states[0][6], Player().yaw - 0.05)
        self.assertAlmostEqual(states[0][7], -0.025)

    def test_native_capture_failure_explains_keyboard_fallback_without_crashing(self):
        _, _, _, frames = self.run_frames([((), ())], self.make_world(),
                                          Player(x=8.5, y=4.5),
                                          capture_error="ClipCursor: access denied")
        self.assertIn("restart with --keyboard-look", frames[0][1]["notice"])
        self.assertFalse(frames[0][1]["mouse_captured"])

    def test_render_errors_release_mouse_before_audio_cleanup(self):
        self.run_frames([((), ())], self.make_world(), Player(x=8.5, y=4.5), fail_render=True)
        self.assertEqual(self.capture_states, [True, False])

    def test_pause_and_help_restore_native_clip_before_rendering_and_audio(self):
        original_clip = (-1000, -1000, 2000, 2000)
        current_clip = original_clip
        pointer = Mock(console_window=1, supports_raw_mouse=True)
        pointer.foreground.return_value = 1
        pointer.minimized.return_value = False
        pointer.rect.return_value = (100, 200, 900, 800)
        pointer.cursor.return_value = (320, 450)
        pointer.clip.side_effect = lambda: current_clip
        capture = pointer.relative_capture
        capture.clip = (500, 500, 501, 501)

        def set_clip(value):
            nonlocal current_clip
            current_clip = value
            return True

        def start(window, bounds):
            return set_clip(capture.clip)

        pointer.set_clip.side_effect = set_clip
        pointer.start_relative.side_effect = start
        script = [((), ()), ({"p"}, ()), ((), ()), ({"p"}, ()),
                  ({"h"}, ()), ((), ()), ({"h"}, ())]
        self.run_frames(script, self.make_world(), Player(x=8.5, y=4.5),
                        native_mouse=WindowsMouse(pointer))
        self.assertEqual(self.native_capture_states,
                         [(True, capture.clip), (False, original_clip), (False, original_clip),
                          (True, capture.clip), (False, original_clip), (False, original_clip),
                          (True, capture.clip), (False, original_clip)])
        self.assertEqual(capture.stop.call_count, 3)

    def test_default_mouse_mode_ignores_q_and_arrows_keyboard_mode_uses_enter_action(self):
        for keyboard in (False, True):
            with self.subTest(keyboard=keyboard):
                events, states, _, _ = self.run_frames(
                    [({"q"}, {"right"}), ({"attack"}, ())], self.make_world(),
                    Player(x=8.5, y=4.5), keyboard_look=keyboard)
                self.assertEqual([e.name for e in events], ["attack_empty"])
                if keyboard:
                    self.assertLess(states[0][6], Player().yaw)
                else:
                    self.assertEqual(states[0][6], Player().yaw)
                self.assertEqual(self.capture_states, [not keyboard, not keyboard, False])

    def test_pause_help_blur_and_small_terminal_release_mouse_and_discard_view_motion(self):
        script = [((), ()), ({"p"}, ()), ({"h"}, ()), ({"h"}, ()),
                  ({"p", "attack"}, ()), ((), ()), ((), ()), ({"blur"}, ())]
        sizes = [(60, 20)] * len(script)
        sizes[5] = (40, 10)
        events, states, _, frames = self.run_frames(script, self.make_world(),
                                                   Player(x=8.5, y=4.5), sizes=sizes,
                                                   mouse=[(20, 10)] * len(script))
        self.assertEqual(self.capture_states, [True, False, False, False, True, False, True, False, False])
        self.assertEqual(states[0][6:8], states[4][6:8])
        self.assertEqual(states[4][6:8], states[5][6:8])
        self.assertNotEqual(states[5][6:8], states[6][6:8])
        self.assertEqual(states[6][6:8], states[7][6:8])
        self.assertNotIn("attack_empty", [event.name for event in events])
        self.assertTrue(frames[2][0][5] and frames[2][0][6])  # help over pause
        self.assertFalse(frames[4][0][5] or frames[4][0][6])


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

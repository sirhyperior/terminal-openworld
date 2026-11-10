"""Relative pointer ownership, button edges and frame-independent look."""

import ctypes
import math
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ascii3d.player import Player
from ascii3d.terminal import Keys, PosixKeyboard, WindowsKeyboard, WindowsMouse


class FakePointer:
    console_window = 1

    def __init__(self, foreground=1):
        self.active = foreground
        self.bounds = (100, 200, 900, 800)
        self.position = (320, 450)
        self.confinement = (-1000, -1000, 2000, 2000)
        self.left = False
        self.iconic = False
        self.clip_ok = self.move_ok = True
        self.moves, self.clips, self.shown = [], [], []
        self.hidden = 0
        self.key_states = set()
        self.key_queries = []

    def foreground(self):
        return self.active

    def is_terminal(self, window):
        return window in (1, 2)

    def minimized(self, window):
        return self.iconic

    def rect(self, window):
        return self.bounds

    def cursor(self):
        return self.position

    def clip(self):
        return self.confinement

    def set_clip(self, bounds):
        self.clips.append(bounds)
        if self.clip_ok:
            self.confinement = bounds
        return self.clip_ok

    def move(self, x, y):
        self.moves.append((x, y))
        if self.move_ok:
            self.position = (x, y)
        return self.move_ok

    def button_down(self):
        return self.left

    def key_down(self, virtual_key):
        self.key_queries.append(virtual_key)
        return virtual_key in self.key_states

    def hide(self):
        self.hidden += 1
        return 2

    def show(self, count):
        self.shown.append(count)


class MouseInputTests(unittest.TestCase):
    def setUp(self):
        self.pointer = FakePointer()
        self.mouse = WindowsMouse(self.pointer)

    def make_native_mouse(self):
        pointer = FakePointer()
        pointer.supports_raw_mouse = True
        capture = Mock(clip=(500, 500, 501, 501))
        pointer.relative_capture = capture

        def start(window, bounds):
            pointer.confinement = capture.clip
            return True

        pointer.start_relative = Mock(side_effect=start)
        return pointer, capture, WindowsMouse(pointer)

    def test_keys_preserve_old_constructor_and_default_to_no_motion(self):
        keys = Keys({"w"}, {"e"})
        self.assertEqual((keys.mouse_dx, keys.mouse_dy), (0, 0))

    def test_capture_epoch_resync_preserves_held_movement_and_suppresses_action_repeats(self):
        keyboard = WindowsKeyboard.__new__(WindowsKeyboard)
        keyboard.api = Mock()
        keyboard.api.FlushConsoleInputBuffer.return_value = True
        keyboard.handle, keyboard.mouse = 123, self.mouse
        keyboard.mapping = {0x57: "w", 0x44: "d", 0x10: "shift", 0xA0: "shift",
                            0xA1: "shift", 0x0D: "attack", 0x50: "p", 0x4D: "m"}
        keyboard.down = {"d", "m"}  # their key-up records may have been flushed
        self.pointer.key_states = {0x57, 0xA0, 0x0D, 0x50}
        keyboard.set_mouse_capture(True)
        self.assertEqual(keyboard.down, {"w", "shift", "attack", "p"})
        self.assertEqual(len(self.pointer.key_queries), len(keyboard.mapping))
        keyboard.set_mouse_capture(True)
        self.assertEqual(len(self.pointer.key_queries), len(keyboard.mapping))
        keyboard.api.FlushConsoleInputBuffer.assert_called_once_with(123)

    def test_modern_terminal_needs_confirmed_input_before_capture(self):
        self.pointer.active = 2
        self.mouse.set_capture(True)
        self.assertFalse(self.mouse.captured)
        self.assertFalse(self.pointer.moves)
        self.pointer.left = True
        self.assertFalse(self.mouse.button(True))  # capture click only
        self.assertEqual(self.mouse.poll(), (0, 0, False))
        self.assertTrue(self.mouse.captured)
        self.assertFalse(self.mouse.button(True))
        self.assertFalse(self.mouse.button(False))
        self.assertTrue(self.mouse.button(True))
        self.assertFalse(self.mouse.button(True))  # held is not another attack

    def test_unrelated_foreground_application_cannot_be_captured(self):
        self.pointer.active = 99
        self.mouse.confirm_focus()
        self.mouse.set_capture(True)
        self.mouse.button(True)
        self.assertEqual(self.mouse.poll(), (0, 0, False))
        self.assertFalse(self.pointer.moves)
        self.assertFalse(self.pointer.clips)

    def test_relative_motion_recenters_repeatedly_without_screen_edge_limit(self):
        self.mouse.set_capture(True)
        total = 0
        for _ in range(150):
            self.pointer.position = (545, 490)
            dx, dy, blurred = self.mouse.poll()
            self.assertEqual((dx, dy, blurred), (45, -10, False))
            self.assertEqual(self.pointer.position, (500, 500))
            total += dx
        self.assertGreater(total * 0.0025, math.tau * 2)
        self.assertEqual(self.mouse.poll(), (0, 0, False))

    def test_pause_restores_cursor_clip_visibility_and_release_is_idempotent(self):
        original_cursor, original_clip = self.pointer.position, self.pointer.confinement
        self.mouse.set_capture(True)
        self.assertEqual(self.pointer.confinement, self.pointer.bounds)
        self.mouse.set_capture(False)
        self.assertEqual(self.pointer.position, original_cursor)
        self.assertEqual(self.pointer.confinement, original_clip)
        self.assertEqual(self.pointer.shown, [2])
        self.mouse.set_capture(False)
        self.assertEqual(self.pointer.shown, [2])

    def test_native_release_uses_latest_clip_and_cleans_up_after_helper_error(self):
        for failed_stop in (False, True):
            with self.subTest(failed_stop=failed_stop):
                pointer, capture, mouse = self.make_native_mouse()
                original_clip, original_cursor = pointer.confinement, pointer.position
                mouse.set_capture(True)
                # The helper owns the successful native readback, including
                # changes made after the high-level capture was established.
                capture.clip = pointer.confinement = (600, 600, 601, 601)
                if failed_stop:
                    capture.stop.side_effect = OSError("helper teardown failed")
                    with self.assertRaises(OSError):
                        mouse.set_capture(False)
                else:
                    mouse.set_capture(False)
                self.assertEqual(pointer.confinement, original_clip)
                self.assertEqual(pointer.position, original_cursor)
                self.assertFalse(mouse.captured or mouse.raw_relative or mouse.requested)
                self.assertFalse(mouse.sample_button())
                self.assertEqual(mouse.poll(), (0, 0, False))
                capture.stop.assert_called_once()

    def test_native_release_retries_once_per_call_without_reacquiring_or_rebalancing(self):
        pointer, capture, mouse = self.make_native_mouse()
        original_clip, original_cursor = pointer.confinement, pointer.position
        mouse.set_capture(True)
        pointer.clip_ok = False
        mouse.set_capture(False)
        self.assertFalse(mouse.captured or mouse.raw_relative)
        self.assertTrue(mouse._release_pending)
        self.assertTrue(mouse.release_error)
        self.assertEqual(pointer.clips, [original_clip])
        self.assertEqual(pointer.moves, [])
        self.assertEqual(pointer.shown, [0])

        # An immediate resume cannot adopt its own stuck clip as the original.
        mouse.set_capture(True)
        self.assertFalse(mouse.captured)
        self.assertEqual(mouse.original_clip, original_clip)
        pointer.start_relative.assert_called_once()
        self.assertEqual(pointer.clips, [original_clip, original_clip])

        pointer.clip_ok = True
        mouse.set_capture(False)
        self.assertFalse(mouse._release_pending)
        self.assertEqual(mouse.release_error, "")
        self.assertEqual(pointer.confinement, original_clip)
        self.assertEqual(pointer.moves, [original_cursor])
        self.assertEqual(pointer.shown, [0])
        capture.stop.assert_called_once()

    def test_pending_release_never_overwrites_a_foreign_clip(self):
        pointer, capture, mouse = self.make_native_mouse()
        mouse.set_capture(True)
        pointer.clip_ok = False
        mouse.set_capture(False)
        calls = list(pointer.clips)
        foreign_clip = (1000, 1000, 1200, 1200)
        pointer.confinement, pointer.active = foreign_clip, 99
        pointer.clip_ok = True
        mouse.set_capture(False)
        self.assertFalse(mouse._release_pending)
        self.assertEqual(mouse.release_error, "")
        self.assertEqual(pointer.confinement, foreign_clip)
        self.assertEqual(pointer.clips, calls)
        self.assertEqual(pointer.moves, [])
        self.assertEqual(pointer.shown, [0])
        capture.stop.assert_called_once()

    def test_focus_loss_clears_capture_without_warping_another_app(self):
        original_clip = self.pointer.confinement
        self.mouse.set_capture(True)
        self.pointer.active = 99
        self.pointer.position = (1600, 900)
        self.assertEqual(self.mouse.poll(), (0, 0, True))
        self.assertFalse(self.mouse.captured)
        self.assertFalse(self.mouse.requested)
        self.assertEqual(self.mouse.window, 1)
        self.assertEqual(self.pointer.position, (1600, 900))
        self.assertEqual(self.pointer.confinement, original_clip)
        self.assertEqual(self.pointer.shown, [2])

    def test_stale_console_record_cannot_redirect_active_capture_to_another_terminal(self):
        self.mouse.set_capture(True)
        self.pointer.active = 2
        moves = list(self.pointer.moves)
        self.assertFalse(self.mouse.button(True))
        self.assertFalse(self.mouse.captured)
        self.assertFalse(self.mouse.requested)
        self.assertEqual(self.pointer.moves, moves)
        self.assertEqual(self.mouse.poll(), (0, 0, True))

    def test_inactive_stale_click_and_focus_cannot_bind_first_modern_host(self):
        self.pointer.active = 2
        self.pointer.left = True
        self.mouse.confirm_focus()
        self.mouse.button(True)
        self.assertIsNone(self.mouse.window)
        self.mouse.set_capture(True)
        self.mouse.confirm_focus()
        self.assertIsNone(self.mouse.window)  # focus records alone are insufficient
        self.assertFalse(self.mouse.captured)
        self.assertFalse(self.pointer.moves)

    def test_initial_modern_binding_requires_live_button_and_pointer_inside_host(self):
        self.pointer.active = 2
        self.mouse.set_capture(True)
        self.mouse.button(True)
        self.assertIsNone(self.mouse.window)
        self.pointer.left, self.pointer.position = True, (1500, 1500)
        self.mouse.button(True)
        self.assertIsNone(self.mouse.window)
        self.pointer.position = (320, 450)
        self.mouse.button(True)
        self.mouse.poll()
        self.assertTrue(self.mouse.captured)

    def test_verified_host_is_retained_across_blur_and_cannot_rebind_to_another_host(self):
        self.mouse.set_capture(True)
        self.pointer.active = 2
        self.mouse.focus_lost()
        self.mouse.set_capture(True)
        self.pointer.left = True
        self.mouse.confirm_focus()
        self.mouse.button(True)
        self.assertEqual(self.mouse.window, 1)
        self.assertFalse(self.mouse.captured)

    def test_another_apps_clip_is_not_overwritten_during_focus_loss(self):
        self.mouse.set_capture(True)
        other_clip = (1000, 1000, 1200, 1200)
        self.pointer.active, self.pointer.confinement = 99, other_clip
        self.mouse.focus_lost()
        self.assertEqual(self.pointer.confinement, other_clip)

    def test_resize_recenters_without_emitting_artificial_motion_and_minimize_releases(self):
        self.mouse.set_capture(True)
        self.pointer.bounds = (100, 200, 1100, 1000)
        self.assertEqual(self.mouse.poll(), (0, 0, False))
        self.assertEqual(self.pointer.position, (600, 600))
        self.pointer.iconic = True
        self.assertEqual(self.mouse.poll(), (0, 0, True))
        self.assertFalse(self.mouse.captured)

    def test_capture_failure_restores_clip_and_never_hides_cursor(self):
        original_clip = self.pointer.confinement
        self.pointer.move_ok = False
        self.mouse.set_capture(True)
        self.assertFalse(self.mouse.captured)
        self.assertEqual(self.pointer.confinement, original_clip)
        self.assertEqual(self.pointer.hidden, 0)

    def test_held_button_on_resume_does_not_attack_until_released(self):
        self.pointer.left = True
        self.mouse.set_capture(True)
        self.assertFalse(self.mouse.button(True))
        self.mouse.button(False)
        self.assertTrue(self.mouse.button(True))
        self.mouse.set_capture(False)
        self.mouse.set_capture(True)
        self.assertFalse(self.mouse.button(True))

    def test_look_direction_wrap_pitch_limits_and_nonfinite_input(self):
        player = Player(yaw=math.pi / 2)
        player.look(100, -100)
        self.assertAlmostEqual(player.yaw, math.pi / 2 - 0.25)
        self.assertAlmostEqual(player.pitch, 0.25)
        player.look(10000, 10000)
        self.assertTrue(0 <= player.yaw < math.tau)
        self.assertEqual(player.pitch, -0.65)
        before = (player.yaw, player.pitch)
        player.look(math.nan, 0)
        self.assertEqual(before, (player.yaw, player.pitch))
        player.look(100, 100, -1)
        self.assertEqual(before, (player.yaw, player.pitch))

    def test_posix_keyboard_fallback_maps_enter_attack_and_ignores_q(self):
        keyboard = PosixKeyboard.__new__(PosixKeyboard)
        keyboard.fd, keyboard.expiry, keyboard.pending, keyboard.escape_time = 0, {}, b"", 0
        with patch("ascii3d.terminal.os.read", side_effect=[b"q\r\x1b[C", BlockingIOError]), \
                patch("ascii3d.terminal.time.perf_counter", return_value=1):
            keys = keyboard.poll()
        self.assertEqual(keys.pressed, {"attack", "right"})
        self.assertNotIn("q", keys.down)


class MousePollingTests(unittest.TestCase):
    """Exercise the complete reader with bounded, host-shaped input batches."""

    def setUp(self):
        self.pointer = FakePointer()
        self.queue = []
        self.keyboard = WindowsKeyboard.__new__(WindowsKeyboard)
        keyboard = self.keyboard
        keyboard.ctypes = ctypes
        keyboard.available, keyboard.count = ctypes.c_ulong(), ctypes.c_ulong()
        keyboard.records = [None] * 256
        keyboard.handle, keyboard.down, keyboard.mapping = 123, set(), {}
        keyboard.mouse = WindowsMouse(self.pointer)
        keyboard.api = SimpleNamespace(GetNumberOfConsoleInputEvents=self.available,
                                       ReadConsoleInputW=self.read)
        keyboard.mouse.set_capture(True)

    def available(self, handle, count):
        count._obj.value = len(self.queue)
        return True

    def read(self, handle, records, maximum, count):
        batch = self.queue[:maximum]
        del self.queue[:maximum]
        records[:len(batch)] = batch
        count._obj.value = len(batch)
        return True

    def record(self, down, flags=0):
        event = SimpleNamespace(dwButtonState=int(down), dwEventFlags=flags)
        self.queue.append(SimpleNamespace(EventType=2,
                          Event=SimpleNamespace(MouseEvent=event)))

    def test_press_is_recovered_with_motion_when_console_click_is_missing(self):
        self.pointer.position, self.pointer.left = (545, 490), True
        self.record(True, 1)
        keys = self.keyboard.poll()
        self.assertEqual(keys.pressed, {"attack"})
        self.assertEqual((keys.mouse_dx, keys.mouse_dy), (45, -10))
        self.assertEqual(self.keyboard.poll().pressed, set())

    def test_motion_or_wheel_state_cannot_forge_a_press_or_release(self):
        for flags in (1, 4, 8):
            self.record(True, flags)
        self.assertEqual(self.keyboard.poll().pressed, set())
        self.pointer.left = True
        self.record(True)
        self.assertEqual(self.keyboard.poll().pressed, {"attack"})
        self.record(False, 1)
        self.record(False, 4)
        self.assertEqual(self.keyboard.poll().pressed, set())
        self.assertTrue(self.keyboard.mouse.left_down)

    def test_motion_cannot_identify_an_unverified_terminal(self):
        self.keyboard.mouse.set_capture(False)
        self.keyboard.mouse.window = None
        self.pointer.active = 2
        self.keyboard.mouse.set_capture(True)
        self.pointer.left = True
        self.record(True, 1)
        self.assertEqual(self.keyboard.poll().pressed, set())
        self.assertIsNone(self.keyboard.mouse.window)
        self.assertFalse(self.keyboard.mouse.captured)

    def test_delayed_console_ack_after_physical_release_does_not_repeat(self):
        self.pointer.left = True
        self.assertEqual(self.keyboard.poll().pressed, {"attack"})
        self.pointer.left = False
        self.assertEqual(self.keyboard.poll().pressed, set())
        self.record(True)
        self.record(False)
        self.assertEqual(self.keyboard.poll().pressed, set())
        self.pointer.left = True
        self.record(True)
        self.assertEqual(self.keyboard.poll().pressed, {"attack"})

    def test_fast_click_between_physical_samples_and_double_click_are_retained(self):
        self.record(True)
        self.record(False)
        self.assertEqual(self.keyboard.poll().pressed, {"attack"})
        self.pointer.left = True
        self.record(True, 3)  # Some hosts combine DOUBLE_CLICK and MOUSE_MOVED.
        self.assertEqual(self.keyboard.poll().pressed, {"attack"})
        self.assertEqual(self.keyboard.poll().pressed, set())

    def test_motion_backlog_does_not_delay_or_duplicate_physical_click(self):
        for _ in range(2000):
            self.record(False, 1)
        self.record(True)
        self.pointer.left = True
        self.assertEqual(self.keyboard.poll().pressed, {"attack"})
        self.assertEqual(len(self.queue), 977)
        self.assertEqual(self.keyboard.poll().pressed, set())
        self.assertEqual(self.queue, [])

    def test_blur_discards_physical_press_and_keeps_foreign_window_free(self):
        self.pointer.active, self.pointer.left = 99, True
        keys = self.keyboard.poll()
        self.assertEqual(keys.pressed, {"blur"})
        self.assertEqual((keys.mouse_dx, keys.mouse_dy), (0, 0))
        self.assertFalse(self.keyboard.mouse.captured)

    def test_raw_packets_are_the_only_captured_click_source(self):
        self.keyboard.mouse.raw_relative = True
        self.pointer.relative_capture = SimpleNamespace(
            poll=Mock(side_effect=[(9, -7, True), (0, 0, False)]))
        self.record(True)
        self.record(False, 1)
        keys = self.keyboard.poll()
        self.assertEqual((keys.mouse_dx, keys.mouse_dy), (9, -7))
        self.assertEqual(keys.pressed, {"attack"})
        self.record(True)
        self.assertEqual(self.keyboard.poll().pressed, set())


if __name__ == "__main__":
    unittest.main()

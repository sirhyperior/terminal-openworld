"""Relative pointer ownership, button edges and frame-independent look."""

import math
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


if __name__ == "__main__":
    unittest.main()

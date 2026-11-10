"""Native input integration tests. Run in a Windows console (not a pipe)."""

import os
import sys
import unittest
from unittest.mock import Mock


@unittest.skipUnless(os.name == "nt" and sys.stdin.isatty() and sys.stdout.isatty(),
                     "needs a live Windows console; engine tests work everywhere")
class WindowsInputTests(unittest.TestCase):
    def setUp(self):
        import ctypes
        from ctypes import wintypes as wt
        from ascii3d.terminal import WindowsKeyboard

        self.ctypes, self.wt = ctypes, wt
        self.keyboard = WindowsKeyboard()
        self.record_type = type(self.keyboard.records[0])
        self.keyboard.api.WriteConsoleInputW.argtypes = [wt.HANDLE, ctypes.POINTER(self.record_type),
                                                        wt.DWORD, ctypes.POINTER(wt.DWORD)]
        self.keyboard.api.WriteConsoleInputW.restype = wt.BOOL
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
        self.user.MapVirtualKeyW.restype = wt.UINT
        self.keyboard.poll()

    def tearDown(self):
        self.keyboard.close()

    def inject(self, key: int, down: bool, modifiers: int = 0):
        record = self.record_type()
        record.EventType = 1
        event = record.Event.KeyEvent
        event.bKeyDown, event.wRepeatCount = down, 1
        event.wVirtualKeyCode, event.dwControlKeyState = key, modifiers
        event.wVirtualScanCode = self.user.MapVirtualKeyW(key, 0)
        event.uChar.UnicodeChar = chr(key) if 0x41 <= key <= 0x5A else (" " if key == 0x20 else "\0")
        written = self.wt.DWORD()
        result = self.keyboard.api.WriteConsoleInputW(self.keyboard.handle, self.ctypes.byref(record),
                                                     1, self.ctypes.byref(written))
        self.assertTrue(result)
        self.assertEqual(written.value, 1)

    def test_native_structure_layout(self):
        self.assertEqual(self.ctypes.sizeof(self.record_type), 20)
        self.assertEqual(self.ctypes.sizeof(self.keyboard.records[0].Event.KeyEvent), 16)
        self.assertEqual(self.ctypes.sizeof(self.keyboard.records[0].Event.MouseEvent), 16)

    def test_enter_attacks_and_q_is_unassigned(self):
        self.inject(ord("Q"), True)
        self.assertNotIn("q", self.keyboard.poll().pressed)
        self.inject(0x0D, True)
        self.assertIn("attack", self.keyboard.poll().pressed)
        self.inject(0x0D, True)
        self.assertNotIn("attack", self.keyboard.poll().pressed)

    def test_native_left_click_record_emits_once_per_button_down(self):
        from ascii3d.terminal import WindowsMouse
        pointer = Mock(console_window=1)
        pointer.foreground.return_value = 1
        pointer.is_terminal.return_value = True
        pointer.minimized.return_value = False
        pointer.rect.return_value = (0, 0, 1000, 800)
        pointer.cursor.return_value = (500, 400)
        pointer.clip.return_value = (0, 0, 1000, 800)
        pointer.set_clip.return_value = pointer.move.return_value = True
        pointer.hide.return_value = 1
        pointer.button_down.return_value = False
        pointer.key_down.return_value = False
        self.keyboard.mouse = WindowsMouse(pointer)
        self.keyboard.mouse.set_capture(True)
        for down, expected in ((True, True), (True, False), (False, False), (True, True)):
            pointer.button_down.return_value = down
            record = self.record_type()
            record.EventType = 0x2
            record.Event.MouseEvent.dwButtonState = int(down)
            written = self.wt.DWORD()
            self.assertTrue(self.keyboard.api.WriteConsoleInputW(self.keyboard.handle, self.ctypes.byref(record),
                                                                1, self.ctypes.byref(written)))
            self.assertEqual("attack" in self.keyboard.poll().pressed, expected)

    def test_activation_discards_queued_mouse_and_focus_before_binding_modern_host(self):
        from ascii3d.terminal import WindowsMouse
        pointer = Mock(console_window=1)
        pointer.foreground.return_value = 2
        pointer.is_terminal.return_value = True
        pointer.minimized.return_value = False
        pointer.rect.return_value = (0, 0, 1000, 800)
        pointer.cursor.return_value = (500, 400)
        pointer.button_down.return_value = True
        pointer.key_down.return_value = False
        self.keyboard.mouse = WindowsMouse(pointer)
        for kind in (0x10, 0x2):
            record = self.record_type()
            record.EventType = kind
            if kind == 0x10:
                record.Event.FocusEvent = True
            else:
                record.Event.MouseEvent.dwButtonState = 1
            written = self.wt.DWORD()
            self.assertTrue(self.keyboard.api.WriteConsoleInputW(self.keyboard.handle, self.ctypes.byref(record),
                                                                1, self.ctypes.byref(written)))
        self.keyboard.set_mouse_capture(True)
        self.assertNotIn("attack", self.keyboard.poll().pressed)
        self.assertIsNone(self.keyboard.mouse.window)
        self.assertFalse(self.keyboard.mouse.captured)
        pointer.move.assert_not_called()

    def test_simultaneous_movement_sprint_jump_and_release(self):
        self.inject(0x10, True, 0x10)
        self.inject(ord("W"), True, 0x10)
        self.inject(0x27, True, 0x10)
        self.inject(0x20, True, 0x10)
        state = self.keyboard.poll()
        self.assertTrue({"shift", "w", "right", "space"} <= state.down, state)
        self.assertTrue({"w", "right", "space"} <= state.pressed)
        self.assertFalse(self.keyboard.poll().pressed)
        self.inject(0x20, False, 0x10)
        self.inject(ord("W"), False, 0x10)
        self.inject(0x27, False, 0x10)
        self.inject(0x10, False)
        self.assertFalse(self.keyboard.poll().down)

    def test_key_repeat_does_not_repeat_actions(self):
        self.inject(ord("M"), True)
        self.assertIn("m", self.keyboard.poll().pressed)
        self.inject(ord("M"), True)
        self.assertNotIn("m", self.keyboard.poll().pressed)
        self.inject(ord("M"), False)
        self.keyboard.poll()
        self.inject(ord("M"), True)
        self.assertIn("m", self.keyboard.poll().pressed)

    def test_control_c_exits(self):
        self.inject(ord("C"), True, 0x8)
        self.assertIn("escape", self.keyboard.poll().pressed)

    def test_pause_record_releases_the_native_helper_and_restores_clip(self):
        from ascii3d.terminal import WindowsMouse

        original_clip = (-1000, -1000, 2000, 2000)
        current_clip = original_clip
        pointer = Mock(console_window=1, supports_raw_mouse=True)
        pointer.foreground.return_value = 1
        pointer.minimized.return_value = False
        pointer.rect.return_value = (100, 200, 900, 800)
        pointer.cursor.return_value = (320, 450)
        pointer.key_down.return_value = False
        pointer.clip.side_effect = lambda: current_clip
        capture = pointer.relative_capture
        capture.clip = (500, 500, 501, 501)
        capture.poll.return_value = (0, 0, False)

        def set_clip(value):
            nonlocal current_clip
            current_clip = value
            return True

        pointer.set_clip.side_effect = set_clip
        pointer.start_relative.side_effect = lambda window, bounds: set_clip(capture.clip)
        self.keyboard.mouse = WindowsMouse(pointer)
        self.keyboard.set_mouse_capture(True)
        self.inject(ord("P"), True)
        self.assertIn("p", self.keyboard.poll().pressed)
        self.keyboard.set_mouse_capture(False)
        self.assertEqual(current_clip, original_clip)
        capture.stop.assert_called_once()
        self.assertFalse(self.keyboard.mouse.captured or self.keyboard.mouse.requested)
        self.inject(ord("P"), False)
        self.keyboard.poll()
        self.assertEqual(current_clip, original_clip)

    def test_losing_focus_clears_held_keys(self):
        self.inject(ord("W"), True)
        self.keyboard.poll()
        record = self.record_type()
        record.EventType, record.Event.FocusEvent = 0x10, False
        written = self.wt.DWORD()
        self.assertTrue(self.keyboard.api.WriteConsoleInputW(self.keyboard.handle, self.ctypes.byref(record),
                                                            1, self.ctypes.byref(written)))
        state = self.keyboard.poll()
        self.assertFalse(state.down)
        self.assertIn("blur", state.pressed)

    def test_console_modes_are_restored(self):
        original_in, original_out = self.keyboard.original_input, self.keyboard.original_output
        self.keyboard.close()
        mode = self.wt.DWORD()
        self.assertTrue(self.keyboard.api.GetConsoleMode(self.keyboard.handle, self.ctypes.byref(mode)))
        self.assertEqual(mode.value, original_in)
        self.assertTrue(self.keyboard.api.GetConsoleMode(self.keyboard.output, self.ctypes.byref(mode)))
        self.assertEqual(mode.value, original_out)


if __name__ == "__main__":
    unittest.main()

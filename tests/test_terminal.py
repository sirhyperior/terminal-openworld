"""Native input integration tests. Run in a Windows console (not a pipe)."""

import os
import sys
import unittest


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

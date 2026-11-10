"""Raw mouse accumulation, packet interpretation and scoped capture lifecycle."""

import ctypes
import os
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from ascii3d.mouse_capture import MouseMotion, NativeMouseCapture, _RawInput
from ascii3d.terminal import WindowsMouse


class MouseMotionTests(unittest.TestCase):
    def setUp(self):
        self.motion = MouseMotion()
        self.motion.reset()

    def test_motion_and_fast_click_survive_in_one_frame(self):
        self.motion.feed(23, -11, down=True)
        self.motion.feed(14, 5, up=True)
        self.assertEqual(self.motion.take(), (37, -6, True))
        self.assertEqual(self.motion.take(), (0, 0, False))

    def test_held_capture_click_and_repeat_down_do_not_attack(self):
        self.motion.reset(held=True)
        self.motion.feed(3, 2, down=True)
        self.assertEqual(self.motion.take(), (3, 2, False))
        self.motion.feed(0, 0, up=True)
        self.motion.feed(4, 1, down=True)
        self.assertEqual(self.motion.take(), (4, 1, True))
        self.motion.feed(4, 1, down=True)
        self.assertEqual(self.motion.take(), (4, 1, False))

    def test_reset_discards_all_queued_motion_and_clicks(self):
        self.motion.feed(100, -40, down=True)
        self.motion.reset()
        self.assertEqual(self.motion.take(), (0, 0, False))


class RawPacketTests(unittest.TestCase):
    def setUp(self):
        self.capture = NativeMouseCapture.__new__(NativeMouseCapture)
        self.capture.motion = MouseMotion()
        self.capture.motion.reset()
        self.capture.absolute = {}
        self.capture.get_window_style = Mock(return_value=0x08000088)
        self.packet = _RawInput()
        self.packet.header.kind = 0
        self.packet.header.size = ctypes.sizeof(self.packet)
        self.capture.api = SimpleNamespace(GetRawInputData=self.read,
                          GetSystemMetrics=lambda index: {0: 1920, 1: 1080,
                                                          78: 3840, 79: 2160,
                                                          23: 0}[index])

    def read(self, handle, command, target, size, header_size):
        ctypes.memmove(target, ctypes.byref(self.packet), ctypes.sizeof(self.packet))
        return ctypes.sizeof(self.packet)

    def test_relative_packet_keeps_motion_and_button_flags_independent(self):
        self.packet.mouse.x, self.packet.mouse.y = 37, -22
        self.packet.mouse.buttons.pair.flags = 1
        self.capture._read(1)
        self.assertEqual(self.capture.motion.take(), (37, -22, True))

    def test_absolute_device_baselines_then_converts_position_deltas(self):
        self.packet.mouse.motion_flags = 1
        self.packet.mouse.x, self.packet.mouse.y = 10000, 12000
        self.capture._read(1)
        self.assertEqual(self.capture.motion.take(), (0, 0, False))
        self.packet.mouse.x += 1000
        self.packet.mouse.y -= 500
        self.capture._read(1)
        dx, dy, attack = self.capture.motion.take()
        self.assertAlmostEqual(dx, 1000 * 1920 / 65535)
        self.assertAlmostEqual(dy, -500 * 1080 / 65535)
        self.assertFalse(attack)

    def test_swapped_primary_button_and_absolute_device_cache_are_bounded(self):
        self.capture.api.GetSystemMetrics = lambda index: 1 if index == 23 else 1920
        self.packet.mouse.buttons.pair.flags = 4
        self.packet.mouse.motion_flags = 1
        for device in range(40):
            self.packet.header.device = device
            self.capture._read(1)
            self.assertLessEqual(len(self.capture.absolute), 16)
        self.assertTrue(self.capture.motion.take()[2])

    def test_truncated_packet_does_not_create_phantom_motion(self):
        self.capture.api.GetRawInputData = lambda *args: 0xFFFFFFFF
        self.capture._read(1)
        self.assertEqual(self.capture.motion.take(), (0, 0, False))


class NativeResourceTests(unittest.TestCase):
    def setUp(self):
        self.capture = NativeMouseCapture.__new__(NativeMouseCapture)
        self.capture.api = Mock()
        self.capture.api.GetForegroundWindow.return_value = 7
        self.capture.api.GetCapture.return_value = 42
        self.capture.api.PeekMessageW.return_value = False
        self.capture.api.GetClipCursor.return_value = False
        self.capture.window, self.capture.owner = 42, 7
        self.capture.cursor = 123
        self.capture.clip = None
        self.capture.center = (500, 500)
        self.capture.active, self.capture.failed, self.capture.closed = True, False, False
        self.capture.motion = MouseMotion()
        self.capture.motion.reset()
        self.capture.absolute = {}
        self.capture.get_window_style = Mock(return_value=0x08000088)

    def test_resize_keeps_positive_clip_inside_helper_and_cannot_take_foreign_focus(self):
        self.assertTrue(self.capture.resize((100, 200, 900, 800)))
        self.assertEqual(self.capture.clip, (500, 500, 501, 501))
        self.capture.api.SetWindowPos.assert_called_once_with(42, -1, 499, 499, 3, 3, 0x50)
        for call in self.capture.api.ClipCursor.call_args_list:
            rect = call.args[0]._obj
            self.assertGreater(rect.right, rect.left)
            self.assertGreater(rect.bottom, rect.top)
        self.capture.api.SetForegroundWindow.assert_not_called()
        self.capture.api.GetForegroundWindow.return_value = 99
        self.capture.api.reset_mock()
        self.assertFalse(self.capture.resize((100, 200, 900, 800)))
        self.capture.api.ClipCursor.assert_not_called()

    def test_resize_records_the_actual_clip_for_release_ownership(self):
        def read_clip(target):
            rect = target._obj
            rect.left, rect.top, rect.right, rect.bottom = 499, 499, 501, 501
            return True

        self.capture.api.GetClipCursor.side_effect = read_clip
        self.assertTrue(self.capture.resize((100, 200, 900, 800)))
        self.assertEqual(self.capture.clip, (499, 499, 501, 501))
        self.capture.get_window_style.return_value = 0x08000080
        self.capture.poll()
        # Recover the original helper bounds, independently of clip readback.
        for call in self.capture.api.SetWindowPos.call_args_list:
            self.assertEqual(call.args, (42, -1, 499, 499, 3, 3, 0x50))

    def test_cursor_message_hides_only_inside_the_active_helper(self):
        self.assertEqual(self.capture._window_proc(42, 0x20, 0, 0), 1)
        self.capture.api.SetCursor.assert_called_once_with(123)
        self.capture.api.SetSystemCursor.assert_not_called()
        self.capture.active = False
        self.capture.api.reset_mock()
        self.capture._window_proc(42, 0x20, 0, 0)
        self.capture.api.SetCursor.assert_not_called()

    def test_stop_unregisters_and_hides_without_changing_foreign_clip(self):
        self.capture.motion.feed(1, 2, down=True)
        self.capture.stop()
        device = self.capture.api.RegisterRawInputDevices.call_args.args[0]._obj
        self.assertEqual(device.flags, 1)
        self.assertIsNone(device.target)
        self.capture.api.ShowWindow.assert_called_once_with(42, 0)
        self.capture.api.ClipCursor.assert_not_called()
        self.capture.api.ReleaseCapture.assert_called_once()
        self.assertEqual(self.capture.motion.take(), (0, 0, False))

    def test_native_poll_restores_its_z_order_and_uses_only_its_private_cursor(self):
        self.capture.clip = (500, 500, 501, 501)
        self.capture.get_window_style.return_value = 0x08000080
        self.capture.motion.feed(12, -3, down=True)
        self.assertEqual(self.capture.poll(), (12, -3, True))
        self.capture.api.SetWindowPos.assert_called_once_with(42, -1, 499, 499, 3, 3, 0x50)
        self.capture.api.SetCursor.assert_called_once_with(123)
        self.capture.api.SetSystemCursor.assert_not_called()

    def test_message_pump_is_bounded_and_blur_or_callback_failure_is_reported(self):
        self.capture.api.PeekMessageW.return_value = True
        self.capture._drain()
        self.assertEqual(self.capture.api.DispatchMessageW.call_count,
                         NativeMouseCapture.MAX_MESSAGES)
        self.capture.api.PeekMessageW.return_value = False
        self.capture.failed = True
        with self.assertRaises(OSError):
            self.capture.poll()
        self.capture.failed = False
        self.capture.api.GetForegroundWindow.return_value = 99
        with self.assertRaises(OSError):
            self.capture.poll()


class NativeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.original = (-1000, -1000, 2000, 2000)
        self.current_clip = self.original
        self.pointer = Mock(console_window=1, supports_raw_mouse=True)
        self.pointer.foreground.return_value = 1
        self.pointer.minimized.return_value = False
        self.pointer.rect.return_value = (100, 200, 900, 800)
        self.pointer.cursor.return_value = (320, 450)
        self.pointer.clip.side_effect = lambda: self.current_clip
        self.pointer.set_clip.side_effect = self.clip
        self.capture = self.pointer.relative_capture
        self.capture.clip = (500, 500, 501, 501)
        self.capture.poll.return_value = (37, -11, True)
        self.pointer.start_relative.side_effect = self.start
        self.mouse = WindowsMouse(self.pointer)

    def clip(self, value):
        self.current_clip = value
        return True

    def start(self, window, bounds):
        self.current_clip = self.capture.clip
        return True

    def test_native_motion_and_button_are_consumed_once_without_legacy_hiding(self):
        self.mouse.set_capture(True)
        self.assertTrue(self.mouse.raw_relative)
        self.pointer.hide.assert_not_called()
        self.assertEqual(self.mouse.poll(), (37, -11, False))
        self.assertTrue(self.mouse.sample_button())
        self.assertFalse(self.mouse.sample_button())
        self.mouse.set_capture(False)
        self.capture.stop.assert_called_once()
        self.assertEqual(self.current_clip, self.original)
        self.pointer.move.assert_called_once_with(320, 450)

    def test_blur_stops_helper_without_moving_or_reclipping_foreign_app(self):
        self.mouse.set_capture(True)
        self.pointer.foreground.return_value = 99
        self.current_clip = (1000, 1000, 1200, 1200)
        self.assertEqual(self.mouse.poll(), (0, 0, True))
        self.capture.stop.assert_called_once()
        self.pointer.move.assert_not_called()
        self.pointer.set_clip.assert_not_called()
        self.assertFalse(self.mouse.sample_button())

    def test_partial_resize_failure_restores_the_successfully_changed_clip(self):
        self.mouse.set_capture(True)
        self.pointer.rect.return_value = (100, 200, 1100, 1000)

        def partial_resize(bounds):
            self.capture.clip = (600, 600, 601, 601)
            self.current_clip = self.capture.clip
            return False

        self.capture.resize.side_effect = partial_resize
        self.assertEqual(self.mouse.poll(), (0, 0, True))
        self.assertEqual(self.current_clip, self.original)
        self.assertFalse(self.mouse.captured)


@unittest.skipUnless(os.name == "nt", "requires Windows cursor resources")
class WindowsCursorResourceTests(unittest.TestCase):
    def test_private_cursor_is_fully_transparent_and_class_is_unregistered(self):
        from ctypes import wintypes as wt
        from ascii3d.terminal import _WindowsPointer

        class IconInfo(ctypes.Structure):
            _fields_ = [("icon", wt.BOOL), ("x", wt.DWORD), ("y", wt.DWORD),
                        ("mask", wt.HBITMAP), ("color", wt.HBITMAP)]

        class Bitmap(ctypes.Structure):
            _fields_ = [("kind", wt.LONG), ("width", wt.LONG), ("height", wt.LONG),
                        ("stride", wt.LONG), ("planes", wt.WORD), ("bits", wt.WORD),
                        ("data", wt.LPVOID)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        pointer = _WindowsPointer(kernel)
        capture = NativeMouseCapture(kernel, pointer.api)
        api, gdi = pointer.api, ctypes.WinDLL("gdi32")
        api.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(IconInfo)]
        api.GetClassInfoExW.argtypes = [wt.HINSTANCE, wt.LPCWSTR,
                                       ctypes.POINTER(capture.class_type)]
        gdi.GetObjectW.argtypes = [wt.HANDLE, ctypes.c_int, wt.LPVOID]
        gdi.GetBitmapBits.argtypes = [wt.HANDLE, wt.LONG, wt.LPVOID]
        gdi.DeleteObject.argtypes = [wt.HANDLE]
        icon = IconInfo()
        try:
            self.assertTrue(api.GetIconInfo(capture.cursor, ctypes.byref(icon)))
            self.assertFalse(icon.color)
            bitmap = Bitmap()
            self.assertTrue(gdi.GetObjectW(icon.mask, ctypes.sizeof(bitmap), ctypes.byref(bitmap)))
            data = ctypes.create_string_buffer(bitmap.stride * bitmap.height)
            copied = gdi.GetBitmapBits(icon.mask, len(data), data)
            self.assertEqual(copied, len(data))
            half = len(data) // 2
            self.assertEqual(set(data.raw[:half]), {255})
            self.assertEqual(set(data.raw[half:]), {0})
            descriptor = capture.class_type()
            descriptor.size = ctypes.sizeof(descriptor)
            self.assertTrue(api.GetClassInfoExW(capture.instance, capture.class_name,
                                               ctypes.byref(descriptor)))
            self.assertEqual(descriptor.cursor, capture.cursor)
        finally:
            if icon.mask:
                gdi.DeleteObject(icon.mask)
            if icon.color:
                gdi.DeleteObject(icon.color)
            capture.close()
            pointer.close()
        descriptor = capture.class_type()
        descriptor.size = ctypes.sizeof(descriptor)
        self.assertFalse(api.GetClassInfoExW(capture.instance, capture.class_name,
                                            ctypes.byref(descriptor)))

    @unittest.skipUnless(os.environ.get("MONOLITH_DESKTOP_TESTS") == "1",
                         "opt in with MONOLITH_DESKTOP_TESTS=1; briefly captures desktop pointer")
    def test_real_desktop_cursor_is_inside_helper_and_releases_across_capture_epochs(self):
        from ctypes import wintypes as wt
        from ascii3d.terminal import _WindowsPointer

        class CursorInfo(ctypes.Structure):
            _fields_ = [("size", wt.DWORD), ("flags", wt.DWORD),
                        ("cursor", wt.HANDLE), ("position", wt.POINT)]

        pointer = _WindowsPointer(ctypes.WinDLL("kernel32", use_last_error=True))
        original_clip, original_cursor = pointer.clip(), pointer.cursor()
        owner = pointer.foreground()
        if not owner or original_clip is None or original_cursor is None:
            self.skipTest("requires an unlocked Windows input desktop")
        if not pointer.set_clip(original_clip):
            self.skipTest("ClipCursor denied; run outside the sandbox")
        # Use the current foreground window as an inert host fixture. No
        # terminal binding, foreign window edits or injected clicks/keys occur.
        pointer.console_window = owner
        pointer.api.WindowFromPoint.argtypes = [wt.POINT]
        pointer.api.WindowFromPoint.restype = wt.HWND
        pointer.api.GetCursorInfo.argtypes = [ctypes.POINTER(CursorInfo)]
        mouse = WindowsMouse(pointer)
        try:
            for epoch in range(3):
                with self.subTest(epoch=epoch):
                    mouse.set_capture(True)
                    self.assertTrue(mouse.captured, pointer.capture_error)
                    capture = pointer.relative_capture
                    self.assertGreater(capture.clip[2], capture.clip[0])
                    self.assertGreater(capture.clip[3], capture.clip[1])
                    # Cursor shape selection follows queued WM_SETCURSOR;
                    # allow the real desktop to finish its enter transition.
                    for _ in range(20):
                        mouse.poll()
                        info = CursorInfo()
                        info.size = ctypes.sizeof(info)
                        self.assertTrue(pointer.api.GetCursorInfo(ctypes.byref(info)))
                        if info.cursor == capture.cursor:
                            break
                        time.sleep(0.005)
                    self.assertEqual(pointer.api.WindowFromPoint(wt.POINT(*pointer.cursor())),
                                     capture.window)
                    self.assertEqual(info.cursor, capture.cursor)
                    self.assertEqual(pointer.foreground(), owner)
                    # The same path used by P/help must restore the real clip.
                    mouse.set_capture(False)
                    self.assertFalse(mouse.captured)
                    self.assertEqual(pointer.clip(), original_clip)
                    self.assertEqual(pointer.cursor(), original_cursor)
        finally:
            try:
                mouse.set_capture(False)
                capture = pointer.relative_capture
                if capture is not None and pointer.clip() == capture.clip:
                    # An empty-RECT regression can deny further ClipCursor calls
                    # in this process. An independent emergency cleanup must keep
                    # a failed test from leaving the desktop pointer confined.
                    subprocess.run([sys.executable, "-B", "-c",
                                    "import ctypes,sys; from ctypes import wintypes as w; "
                                    "u=ctypes.windll.user32; "
                                    f"r=w.RECT{original_clip!r}; "
                                    "ok=u.ClipCursor(ctypes.byref(r)) or u.ClipCursor(None); "
                                    "sys.exit(0 if ok else 1)"],
                                   check=True, timeout=5, creationflags=0x08000000)
                    self.assertEqual(pointer.clip(), original_clip)
                    pointer.move(*original_cursor)
            finally:
                pointer.close()


if __name__ == "__main__":
    unittest.main()

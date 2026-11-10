"""Windows-only relative mouse capture without changing a terminal host.

Raw Input keeps device motion/button edges independent of cursor warps and the
console's character-cell event queue. A tiny, non-activating game popup
under the confined pointer supplies a transparent cursor; keyboard focus stays with
the terminal. No system cursors or foreign window classes are modified.
"""

import ctypes
from ctypes import wintypes as wt


class MouseMotion:
    """Frame accumulator; held capture clicks and repeated downs never attack."""

    def __init__(self):
        self.reset()

    def reset(self, held=False):
        self.dx = self.dy = 0
        self.down, self.attack = bool(held), False

    def feed(self, dx, dy, down=False, up=False):
        self.dx += dx
        self.dy += dy
        if down:
            self.attack |= not self.down
            self.down = True
        if up:
            self.down = False

    def take(self):
        result = self.dx, self.dy, self.attack
        self.dx = self.dy = 0
        self.attack = False
        return result


class _ButtonPair(ctypes.Structure):
    _fields_ = [("flags", wt.USHORT), ("data", wt.USHORT)]


class _Buttons(ctypes.Union):
    _anonymous_ = ("pair",)
    _fields_ = [("value", wt.ULONG), ("pair", _ButtonPair)]


class _RawMouse(ctypes.Structure):
    _anonymous_ = ("buttons",)
    _fields_ = [("motion_flags", wt.USHORT), ("buttons", _Buttons),
                ("raw_buttons", wt.ULONG), ("x", wt.LONG),
                ("y", wt.LONG), ("extra", wt.ULONG)]


class _RawHeader(ctypes.Structure):
    _fields_ = [("kind", wt.DWORD), ("size", wt.DWORD),
                ("device", wt.HANDLE), ("parameter", wt.WPARAM)]


class _RawInput(ctypes.Structure):
    _fields_ = [("header", _RawHeader), ("mouse", _RawMouse)]


class _Device(ctypes.Structure):
    _fields_ = [("page", wt.USHORT), ("usage", wt.USHORT),
                ("flags", wt.DWORD), ("target", wt.HWND)]


class NativeMouseCapture:
    """A lazy Win32 resource, driven only by the existing bounded input poll."""

    MAX_MESSAGES = 1024

    def __init__(self, kernel, user):
        self.kernel, self.api = kernel, user
        self.window = self.owner = self.clip = self.center = None
        self.active = self.failed = False
        self.error = ""
        self.closed = False
        self.absolute = {}
        self.motion = MouseMotion()
        self.motion.reset()
        self._bind()
        self.instance = kernel.GetModuleHandleW(None)
        width, height = user.GetSystemMetrics(13), user.GetSystemMetrics(14)
        mask_size = ((width + 15) // 16) * 2 * height
        and_mask = ctypes.create_string_buffer(b"\xff" * mask_size)
        xor_mask = ctypes.create_string_buffer(b"\0" * mask_size)
        self.cursor = user.CreateCursor(self.instance, 0, 0, width, height, and_mask, xor_mask)
        if not self.cursor:
            raise ctypes.WinError(ctypes.get_last_error())
        self.class_name = f"MONOLITH.Mouse.{kernel.GetCurrentProcessId()}.{id(self)}"
        self.callback = self.callback_type(self._window_proc)
        descriptor = self.class_type()
        descriptor.size = ctypes.sizeof(descriptor)
        descriptor.procedure = self.callback
        descriptor.instance = self.instance
        descriptor.name = self.class_name
        descriptor.cursor = self.cursor
        # This is a private cursor resource, never a replacement system cursor.
        if not user.RegisterClassExW(ctypes.byref(descriptor)):
            error = ctypes.WinError(ctypes.get_last_error())
            user.DestroyCursor(self.cursor)
            raise error

    def _bind(self):
        api, kernel = self.api, self.kernel
        self.callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND,
                                                wt.UINT, wt.WPARAM, wt.LPARAM)

        class WindowClass(ctypes.Structure):
            _fields_ = [("size", wt.UINT), ("style", wt.UINT),
                        ("procedure", self.callback_type),
                        ("class_extra", ctypes.c_int), ("window_extra", ctypes.c_int),
                        ("instance", wt.HINSTANCE), ("icon", wt.HANDLE),
                        ("cursor", wt.HANDLE), ("background", wt.HBRUSH),
                        ("menu", wt.LPCWSTR), ("name", wt.LPCWSTR),
                        ("small_icon", wt.HANDLE)]

        self.class_type = WindowClass
        api.RegisterClassExW.argtypes = [ctypes.POINTER(WindowClass)]
        api.RegisterClassExW.restype = wt.ATOM
        api.UnregisterClassW.argtypes = [wt.LPCWSTR, wt.HINSTANCE]
        api.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, wt.HWND, wt.HMENU,
                                       wt.HINSTANCE, wt.LPVOID]
        api.CreateWindowExW.restype = wt.HWND
        api.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        api.DefWindowProcW.restype = ctypes.c_ssize_t
        api.DestroyWindow.argtypes = [wt.HWND]
        api.IsWindow.argtypes = [wt.HWND]
        api.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
        api.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wt.UINT]
        api.RegisterRawInputDevices.argtypes = [ctypes.POINTER(_Device), wt.UINT, wt.UINT]
        api.RegisterRawInputDevices.restype = wt.BOOL
        api.GetRawInputData.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID,
                                       ctypes.POINTER(wt.UINT), wt.UINT]
        api.GetRawInputData.restype = wt.UINT
        api.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND,
                                    wt.UINT, wt.UINT, wt.UINT]
        api.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
        api.DispatchMessageW.restype = ctypes.c_ssize_t
        api.SetCursor.argtypes = [wt.HANDLE]
        api.SetCursor.restype = wt.HANDLE
        api.CreateCursor.argtypes = [wt.HINSTANCE, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wt.LPVOID, wt.LPVOID]
        api.CreateCursor.restype = wt.HANDLE
        api.DestroyCursor.argtypes = [wt.HANDLE]
        api.SetCapture.argtypes = [wt.HWND]
        api.SetCapture.restype = wt.HWND
        api.GetCapture.restype = wt.HWND
        self.get_window_style = (api.GetWindowLongPtrW if ctypes.sizeof(wt.HWND) == 8
                                 else api.GetWindowLongW)
        self.get_window_style.argtypes = [wt.HWND, ctypes.c_int]
        self.get_window_style.restype = ctypes.c_ssize_t
        kernel.GetModuleHandleW.argtypes = [wt.LPCWSTR]
        kernel.GetModuleHandleW.restype = wt.HMODULE

    def _window_proc(self, window, message, wparam, lparam):
        try:
            if message == 0x20:  # WM_SETCURSOR
                if self.active:
                    self.api.SetCursor(self.cursor)
                    return 1
            elif message == 0x21:  # WM_MOUSEACTIVATE: keep terminal keyboard focus.
                return 3  # MA_NOACTIVATE; do not eat clicks.
            elif message == 0xFF:  # WM_INPUT
                if self.active and self.api.GetForegroundWindow() == self.owner:
                    self._read(lparam)
                # DefWindowProc performs the required foreground input cleanup.
        except BaseException:
            # ctypes callbacks must never leak Python exceptions into user32.
            self.failed = True
        return self.api.DefWindowProcW(window, message, wparam, lparam)

    def _read(self, handle):
        packet = _RawInput()
        size = wt.UINT(ctypes.sizeof(packet))
        copied = self.api.GetRawInputData(handle, 0x10000003, ctypes.byref(packet),
                                          ctypes.byref(size), ctypes.sizeof(_RawHeader))
        if copied == 0xFFFFFFFF or copied < ctypes.sizeof(packet) or packet.header.kind != 0:
            return
        mouse = packet.mouse
        dx, dy = mouse.x, mouse.y
        if mouse.motion_flags & 1:  # Absolute devices (e.g. remote desktop).
            virtual = bool(mouse.motion_flags & 2)
            width = self.api.GetSystemMetrics(78 if virtual else 0)
            height = self.api.GetSystemMetrics(79 if virtual else 1)
            position = (mouse.x * width / 65535, mouse.y * height / 65535)
            key = (packet.header.device, virtual)
            previous = self.absolute.get(key)
            if key not in self.absolute and len(self.absolute) >= 16:
                self.absolute.clear()
            self.absolute[key] = position
            dx, dy = ((position[0] - previous[0], position[1] - previous[1])
                      if previous is not None else (0, 0))
        else:
            self.absolute.clear()
        # Raw flags describe physical buttons; honor the Windows primary button.
        down, up = (4, 8) if self.api.GetSystemMetrics(23) else (1, 2)
        self.motion.feed(dx, dy, bool(mouse.buttons.pair.flags & down),
                         bool(mouse.buttons.pair.flags & up))

    def _drain(self):
        message = wt.MSG()
        for _ in range(self.MAX_MESSAGES):
            if not self.api.PeekMessageW(ctypes.byref(message), self.window, 0, 0, 1):
                break
            self.api.DispatchMessageW(ctypes.byref(message))

    def start(self, owner, bounds, held):
        """Register only while captured; callers own original clip restoration."""
        self.owner, self.failed, self.error = owner, False, ""
        if not self.window:
            # TOOLWINDOW | NOACTIVATE, WS_POPUP. Deliberately unowned by the
            # external terminal: cross-thread ownership would attach input
            # queues and let a slow frame stall the host. Scope by foreground
            # checks instead; only our own tiny window becomes topmost.
            self.window = self.api.CreateWindowExW(0x08000088, self.class_name,
                            "MONOLITH mouse capture", 0x80000000,
                            0, 0, 3, 3, None, None, self.instance, None)
            if not self.window:
                self.window = None
                return self._failure("CreateWindowExW")
        self._drain()
        self.motion.reset(held)
        self.absolute.clear()
        device = _Device(1, 2, 0x100, self.window)  # RIDEV_INPUTSINK
        if not self.api.RegisterRawInputDevices(ctypes.byref(device), 1, ctypes.sizeof(device)):
            return self._failure("RegisterRawInputDevices")
        self.active = True
        if not self.resize(bounds):
            self.stop()
            return False
        self.api.SetCapture(self.window)
        if self.api.GetCapture() != self.window:
            self.error = "Could not capture the native cursor window"
            self.stop()
            return False
        self.api.SetCursor(self.cursor)
        return True

    def resize(self, bounds):
        if self.api.GetForegroundWindow() != self.owner:
            self.error = "Terminal lost focus during capture"
            return False
        x, y = (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2
        if not self.api.SetWindowPos(self.window, -1, x - 1, y - 1, 3, 3, 0x50):
            return self._failure("SetWindowPos")
        self.center = x, y
        # Enter the helper before locking to a point. Clipping first can move
        # the pointer without a mouse-enter transition, leaving the host's old
        # cursor selected. Warps are not Raw Input device motion.
        expanded = wt.RECT(*bounds)
        if not self.api.ClipCursor(ctypes.byref(expanded)):
            return self._failure("ClipCursor")
        self.clip = tuple(bounds)
        if not (self.api.SetCursorPos(x - 1, y) and self.api.SetCursorPos(x, y)):
            return self._failure("SetCursorPos")
        # Keep a positive-area clip strictly inside the helper. On scaled
        # desktops an empty RECT can move the cursor to (x - 1, y - 1), outside
        # the helper, and make later ClipCursor calls fail with access denied.
        # The margin also covers inclusive endpoints and DPI rounding while
        # Raw Input keeps the full device deltas independently of confinement.
        confinement = x, y, x + 1, y + 1
        rect = wt.RECT(*confinement)
        if not self.api.ClipCursor(ctypes.byref(rect)):
            return self._failure("ClipCursor")
        # Track every successful clip for transactional acquisition cleanup.
        self.clip = confinement
        actual = wt.RECT()
        if self.api.GetClipCursor(ctypes.byref(actual)):
            self.clip = actual.left, actual.top, actual.right, actual.bottom
        return True

    def _failure(self, operation):
        self.error = f"{operation}: {ctypes.WinError(ctypes.get_last_error())}"
        return False

    def poll(self):
        self._drain()
        if (self.failed or not self.api.IsWindow(self.window)
                or self.api.GetCapture() != self.window
                or self.api.GetForegroundWindow() != self.owner):
            raise OSError("Native mouse capture failed; use --keyboard-look.")
        # Desktop helpers can reorder non-activating windows. Recover only our
        # capture pixel's z-order, while the verified host remains foreground.
        if not self.get_window_style(self.window, -20) & 8:
            x, y = self.center
            if not self.api.SetWindowPos(self.window, -1, x - 1, y - 1, 3, 3, 0x50):
                raise OSError("Native mouse capture lost its cursor window.")
        self.api.SetCursor(self.cursor)
        return self.motion.take()

    def stop(self):
        self.active = False
        if self.window:
            if self.api.GetCapture() == self.window:
                self.api.ReleaseCapture()
            device = _Device(1, 2, 1, None)  # RIDEV_REMOVE requires NULL target.
            self.api.RegisterRawInputDevices(ctypes.byref(device), 1, ctypes.sizeof(device))
            self.api.ShowWindow(self.window, 0)
            self._drain()
        self.motion.reset()
        self.absolute.clear()

    def close(self):
        if self.closed:
            return
        self.stop()
        if self.window:
            self.api.DestroyWindow(self.window)
            self.window = None
        self.api.UnregisterClassW(self.class_name, self.instance)
        self.api.DestroyCursor(self.cursor)
        self.closed = True

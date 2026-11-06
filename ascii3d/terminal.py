"""Terminal lifecycle and nonblocking keyboard input; no third-party packages."""

from dataclasses import dataclass, field
import math
import os
import shutil
import sys
import time


def fit_viewport(columns: int, rows: int, max_cells: int = 4800) -> tuple[int, int]:
    """Bound render work while retaining native text cells and a usable HUD."""
    width, height = min(columns, 180), min(max(1, rows - 1), 64)
    if width * height > max_cells:
        scale = math.sqrt(max_cells / (width * height))
        width = max(min(width, 60), int(width * scale))
        height = max(min(height, 20), int(height * scale))
        if width * height > max_cells:
            width = max(min(width, 60), max_cells // height)
    return max(1, width), max(1, height)


@dataclass
class Keys:
    down: set[str] = field(default_factory=set)
    pressed: set[str] = field(default_factory=set)
    mouse_dx: float = 0.0
    mouse_dy: float = 0.0


class _WindowsPointer:
    """Small Win32 seam; all pointer ownership is handled by WindowsMouse."""

    def __init__(self, kernel):
        import ctypes
        from ctypes import wintypes as wt

        self.ctypes, self.wt = ctypes, wt
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        kernel.GetConsoleWindow.restype = wt.HWND
        self.console_window = kernel.GetConsoleWindow()
        self.api.GetForegroundWindow.restype = wt.HWND
        self.api.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
        self.api.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
        self.api.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
        self.api.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
        self.api.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.api.GetClipCursor.argtypes = [ctypes.POINTER(wt.RECT)]
        self.api.ClipCursor.argtypes = [ctypes.POINTER(wt.RECT)]
        self.api.IsIconic.argtypes = [wt.HWND]
        self.api.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.api.GetAsyncKeyState.restype = wt.SHORT

    def foreground(self):
        return self.api.GetForegroundWindow()

    def is_terminal(self, window):
        if not window:
            return False
        if window == self.console_window:
            return True
        name = self.ctypes.create_unicode_buffer(128)
        self.api.GetClassNameW(window, name, len(name))
        return name.value in ("CASCADIA_HOSTING_WINDOW_CLASS", "ConsoleWindowClass")

    def minimized(self, window):
        return bool(self.api.IsIconic(window))

    def rect(self, window):
        rect = self.wt.RECT()
        if not self.api.GetClientRect(window, self.ctypes.byref(rect)):
            return None
        low, high = self.wt.POINT(rect.left, rect.top), self.wt.POINT(rect.right, rect.bottom)
        if not (self.api.ClientToScreen(window, self.ctypes.byref(low))
                and self.api.ClientToScreen(window, self.ctypes.byref(high))):
            return None
        return low.x, low.y, high.x, high.y

    def cursor(self):
        point = self.wt.POINT()
        return (point.x, point.y) if self.api.GetCursorPos(self.ctypes.byref(point)) else None

    def clip(self):
        rect = self.wt.RECT()
        if self.api.GetClipCursor(self.ctypes.byref(rect)):
            return rect.left, rect.top, rect.right, rect.bottom
        return None

    def set_clip(self, rect):
        bounds = self.wt.RECT(*rect) if rect is not None else None
        return bool(self.api.ClipCursor(self.ctypes.byref(bounds) if bounds is not None else None))

    def move(self, x, y):
        return bool(self.api.SetCursorPos(x, y))

    def button_down(self):
        return self.key_down(0x01)

    def key_down(self, virtual_key):
        return bool(self.api.GetAsyncKeyState(virtual_key) & 0x8000)

    def hide(self):
        # Best effort: ShowCursor changes this GUI thread's display counter.
        # A separate console/Windows Terminal host owns its own counter, so it
        # may keep its pointer visible. Do not attach host input queues or
        # replace system cursors merely to hide it; balance only our own calls.
        count = 0
        while count < 16:
            count += 1
            if self.api.ShowCursor(False) < 0:
                break
        return count

    def show(self, count):
        for _ in range(count):
            self.api.ShowCursor(True)


class WindowsMouse:
    """Relative look without screen-edge limits, restricted to our terminal.

    Windows Terminal's console handle is a hidden compatibility window. An
    fresh console click with its physical button still held identifies its host
    before capture; focus records alone never identify another foreground app.
    """

    def __init__(self, pointer):
        self.pointer = pointer
        self.requested = self.captured = False
        self.window = None
        self.bounds = self.center = None
        self.original_clip = self.original_cursor = None
        self.hide_count = 0
        self.left_down = False
        self._blurred = False

    def confirm_focus(self):
        if not self.requested:
            return
        foreground = self.pointer.foreground()
        if self.captured:
            if foreground != self.window:
                self.focus_lost()
            return
        if self.window is None and foreground == self.pointer.console_window:
            self.window = foreground

    def focus_lost(self):
        self.release(restore_cursor=False)
        self.requested = False
        self.left_down = False
        self._blurred = True

    def set_capture(self, active):
        self.requested = bool(active)
        if not active:
            self.release()
            return
        # A classic console has an unambiguous foreground HWND. Modern terminal
        # hosts need their own input event before we can safely identify them.
        if self.window is None and self.pointer.foreground() == self.pointer.console_window:
            self.confirm_focus()
        self._acquire()

    def _acquire(self):
        if self.captured or not self.requested or self.window is None:
            return
        if self.pointer.foreground() != self.window or self.pointer.minimized(self.window):
            return
        bounds, cursor = self.pointer.rect(self.window), self.pointer.cursor()
        if bounds is None or cursor is None or bounds[2] - bounds[0] < 2 or bounds[3] - bounds[1] < 2:
            return
        original_clip = self.pointer.clip()
        center = ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
        if not self.pointer.set_clip(bounds):
            return
        if not self.pointer.move(*center):
            self.pointer.set_clip(original_clip)
            return
        self.original_clip, self.original_cursor = original_clip, cursor
        self.bounds, self.center = bounds, center
        self.hide_count = self.pointer.hide()
        self.left_down = self.pointer.button_down()
        self.captured = True

    def button(self, down):
        """Return only a fresh left-down edge; the capture click is consumed."""
        self.confirm_focus()
        if self.requested and self.window is None and down and self.pointer.button_down():
            foreground = self.pointer.foreground()
            bounds, cursor = self.pointer.rect(foreground), self.pointer.cursor()
            if (self.pointer.is_terminal(foreground) and bounds is not None and cursor is not None
                    and bounds[0] <= cursor[0] < bounds[2] and bounds[1] <= cursor[1] < bounds[3]):
                # Only a fresh console click with its physical button still
                # held can identify a modern host. Focus records are not proof.
                self.window = foreground
        attack = bool(down and not self.left_down and self.captured)
        self.left_down = bool(down)
        return attack

    def poll(self):
        if not self.captured:
            blurred, self._blurred = self._blurred, False
            if not blurred:
                self._acquire()
            return 0.0, 0.0, blurred
        if self.pointer.foreground() != self.window or self.pointer.minimized(self.window):
            self.focus_lost()
            self._blurred = False
            return 0.0, 0.0, True
        bounds, cursor = self.pointer.rect(self.window), self.pointer.cursor()
        if (bounds is None or cursor is None
                or bounds[2] - bounds[0] < 2 or bounds[3] - bounds[1] < 2):
            self.focus_lost()
            self._blurred = False
            return 0.0, 0.0, True
        if bounds != self.bounds:
            # Resizing changes the center; discard that artificial displacement.
            if not self.pointer.set_clip(bounds):
                self.focus_lost()
                self._blurred = False
                return 0.0, 0.0, True
            self.bounds = bounds
            self.center = ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
            if not self.pointer.move(*self.center):
                self.focus_lost()
                self._blurred = False
                return 0.0, 0.0, True
            return 0.0, 0.0, False
        dx, dy = cursor[0] - self.center[0], cursor[1] - self.center[1]
        if not self.pointer.move(*self.center):
            self.focus_lost()
            self._blurred = False
            return 0.0, 0.0, True
        return dx, dy, False

    def release(self, restore_cursor=True):
        if not self.captured:
            return
        self.captured = False
        # Another app may have changed confinement after focus changed. Do not
        # overwrite its clip or warp its pointer back to our old location.
        if self.pointer.clip() == self.bounds:
            self.pointer.set_clip(self.original_clip)
        if restore_cursor and self.pointer.foreground() == self.window and self.original_cursor is not None:
            self.pointer.move(*self.original_cursor)
        self.pointer.show(self.hide_count)
        self.hide_count = 0


class WindowsKeyboard:
    """Read native console key-down AND key-up records, including real Shift."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes as wt

        self.ctypes = ctypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)

        class Character(ctypes.Union):
            _fields_ = [("UnicodeChar", wt.WCHAR), ("AsciiChar", ctypes.c_char)]

        class KeyEvent(ctypes.Structure):
            _fields_ = [("bKeyDown", wt.BOOL), ("wRepeatCount", wt.WORD),
                        ("wVirtualKeyCode", wt.WORD), ("wVirtualScanCode", wt.WORD),
                        ("uChar", Character), ("dwControlKeyState", wt.DWORD)]

        class Coord(ctypes.Structure):
            _fields_ = [("X", wt.SHORT), ("Y", wt.SHORT)]

        class MouseEvent(ctypes.Structure):
            _fields_ = [("dwMousePosition", Coord), ("dwButtonState", wt.DWORD),
                        ("dwControlKeyState", wt.DWORD), ("dwEventFlags", wt.DWORD)]

        class EventData(ctypes.Union):
            _fields_ = [("KeyEvent", KeyEvent), ("MouseEvent", MouseEvent), ("FocusEvent", wt.BOOL),
                        ("padding", ctypes.c_byte * 16)]

        class InputRecord(ctypes.Structure):
            _fields_ = [("EventType", wt.WORD), ("Event", EventData)]

        self.api.GetStdHandle.argtypes = [wt.DWORD]
        self.api.GetStdHandle.restype = wt.HANDLE
        self.api.GetConsoleMode.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
        self.api.GetConsoleMode.restype = wt.BOOL
        self.api.SetConsoleMode.argtypes = [wt.HANDLE, wt.DWORD]
        self.api.SetConsoleMode.restype = wt.BOOL
        self.api.GetNumberOfConsoleInputEvents.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
        self.api.GetNumberOfConsoleInputEvents.restype = wt.BOOL
        self.api.ReadConsoleInputW.argtypes = [wt.HANDLE, ctypes.POINTER(InputRecord), wt.DWORD,
                                               ctypes.POINTER(wt.DWORD)]
        self.api.ReadConsoleInputW.restype = wt.BOOL
        self.api.FlushConsoleInputBuffer.argtypes = [wt.HANDLE]
        self.api.FlushConsoleInputBuffer.restype = wt.BOOL
        self.handle = self.api.GetStdHandle(-10)
        self.output = self.api.GetStdHandle(-11)
        mode_in, mode_out = wt.DWORD(), wt.DWORD()
        if not self.api.GetConsoleMode(self.handle, ctypes.byref(mode_in)):
            raise OSError("Open this program in a real terminal, such as Windows Terminal or PowerShell.")
        if not self.api.GetConsoleMode(self.output, ctypes.byref(mode_out)):
            raise OSError("Terminal output is unavailable. Use --snapshot when redirecting output.")
        self.original_input, self.original_output = mode_in.value, mode_out.value
        # Disable line buffering, echo, Quick Edit and VT keyboard translation.
        new_input = (mode_in.value & ~(0x1 | 0x2 | 0x4 | 0x40 | 0x200)) | 0x80 | 0x8 | 0x10
        if not self.api.SetConsoleMode(self.output, mode_out.value | 0x4):
            raise OSError("This terminal does not support ANSI output. Try Windows Terminal.")
        if not self.api.SetConsoleMode(self.handle, new_input):
            self.api.SetConsoleMode(self.output, self.original_output)
            raise ctypes.WinError(ctypes.get_last_error())
        self.records = (InputRecord * 256)()
        self.count = wt.DWORD()
        self.available = wt.DWORD()
        self.down: set[str] = set()
        try:
            self.mouse = WindowsMouse(_WindowsPointer(self.api))
        except BaseException:
            self.api.SetConsoleMode(self.handle, self.original_input)
            self.api.SetConsoleMode(self.output, self.original_output)
            raise
        self.mapping = {0x1B: "escape", 0x20: "space", 0x10: "shift", 0xA0: "shift", 0xA1: "shift",
                        0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down", 0x09: "tab",
                        0x0D: "attack"}
        self.mapping.update({ord(key.upper()): key for key in "wasdemhprf"})

    def poll(self) -> Keys:
        pressed: set[str] = set()
        api, byref = self.api, self.ctypes.byref
        if not api.GetNumberOfConsoleInputEvents(self.handle, byref(self.available)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        # Bound the batch: repeated input cannot starve rendering.
        remaining = min(self.available.value, 1024)
        while remaining:
            if not api.ReadConsoleInputW(self.handle, self.records, min(remaining, 256), byref(self.count)):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            if not self.count.value:
                break
            remaining -= self.count.value
            for record in self.records[:self.count.value]:
                if record.EventType == 0x10:
                    if record.Event.FocusEvent:
                        self.mouse.confirm_focus()
                    else:
                        self.down.clear()
                        self.mouse.focus_lost()
                        pressed.add("blur")
                    continue
                if record.EventType == 0x2:
                    if self.mouse.button(bool(record.Event.MouseEvent.dwButtonState & 0x1)):
                        pressed.add("attack")
                    continue
                if record.EventType != 0x1:
                    continue
                event = record.Event.KeyEvent
                key = self.mapping.get(event.wVirtualKeyCode)
                if event.bKeyDown and event.wVirtualKeyCode == ord("C") and event.dwControlKeyState & 0xC:
                    pressed.add("escape")
                if key:
                    if event.bKeyDown:
                        if key not in self.down:
                            pressed.add(key)
                        self.down.add(key)
                    else:
                        self.down.discard(key)
                # Modifier state also catches Shift held before the app started.
                if event.dwControlKeyState & 0x10:
                    self.down.add("shift")
                else:
                    self.down.discard("shift")
        dx, dy, blurred = self.mouse.poll()
        if blurred:
            self.down.clear()
            pressed.add("blur")
        if "blur" in pressed:
            pressed.discard("attack")
            dx = dy = 0.0
        return Keys(set(self.down), pressed, dx, dy)

    def close(self) -> None:
        try:
            self.mouse.set_capture(False)
        finally:
            self.api.SetConsoleMode(self.handle, self.original_input)
            self.api.SetConsoleMode(self.output, self.original_output)

    def set_mouse_capture(self, active):
        if active and not self.mouse.requested:
            # Establish a new input epoch: a queued click/focus record from
            # before pause or another foreground window cannot identify a host.
            if not self.api.FlushConsoleInputBuffer(self.handle):
                return
            # Flushing can discard key-up records, but clearing all keys would
            # stall held WASD/Shift until keyboard repeat resumes. Reconcile
            # physical state once per capture epoch, including held action keys
            # so their next repeat does not become a second UI/attack press.
            self.down = {key for code, key in self.mapping.items()
                         if self.mouse.pointer.key_down(code)}
        self.mouse.set_capture(active)


class PosixKeyboard:
    """Portable raw-terminal fallback; uppercase WASD carries the Shift modifier.

    Traditional Unix terminals don't send key-up events. A short timeout models
    held keys there; Windows uses precise native events instead.
    """

    def __init__(self):
        import termios
        import tty

        self.termios = termios
        self.fd = sys.stdin.fileno()
        self.original = termios.tcgetattr(self.fd)
        self.blocking = os.get_blocking(self.fd)
        tty.setraw(self.fd)
        os.set_blocking(self.fd, False)
        self.expiry: dict[str, float] = {}
        self.pending = b""
        self.escape_time = 0.0

    def poll(self) -> Keys:
        now = time.perf_counter()
        self.expiry = {key: expiry for key, expiry in self.expiry.items() if expiry > now}
        previous = set(self.expiry)
        pressed: set[str] = set()
        for _ in range(4):
            try:
                data = os.read(self.fd, 4096)
            except BlockingIOError:
                break
            if not data:
                break
            self.pending = (self.pending + data)[:16384]
        arrows = {b"A": "up", b"B": "down", b"C": "right", b"D": "left"}
        count = 0
        while self.pending and count < 1024:
            count += 1
            if self.pending.startswith(b"\x1b"):
                if len(self.pending) == 1:
                    if not self.escape_time:
                        self.escape_time = now
                    if now - self.escape_time < 0.035:
                        break
                    key, self.pending = "escape", b""
                elif self.pending[1:2] in (b"[", b"O"):
                    end = next((i for i in range(2, len(self.pending))
                                if 0x40 <= self.pending[i] <= 0x7E), None)
                    if end is None:
                        break
                    key = arrows.get(self.pending[end:end + 1], "")
                    self.pending = self.pending[end + 1:]
                else:
                    key, self.pending = "escape", self.pending[1:]
                self.escape_time = 0.0
            else:
                char = chr(self.pending[0])
                self.pending = self.pending[1:]
                key = {" ": "space", "\t": "tab", "\x03": "escape",
                       "\r": "attack", "\n": "attack"}.get(char, char.lower())
                if char in "WASD":
                    self.expiry["shift"] = now + 0.20
            if key in {"w", "a", "s", "d", "attack", "e", "m", "h", "p", "r", "f", "escape", "space",
                       "tab", "left", "right", "up", "down"}:
                if key not in previous:
                    pressed.add(key)
                self.expiry[key] = now + 0.20
        return Keys(set(self.expiry), pressed)

    def close(self) -> None:
        self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.original)
        os.set_blocking(self.fd, self.blocking)


class Terminal:
    def __init__(self, max_cells: int = 4800):
        self.keyboard = None
        self.last_size = (0, 0)
        self.max_cells = max_cells
        self.origin = (1, 1)

    def __enter__(self) -> "Terminal":
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise OSError("Run 'python main.py' in a terminal. For a still frame, use --snapshot.")
        self.keyboard = WindowsKeyboard() if os.name == "nt" else PosixKeyboard()
        try:
            sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[0m\x1b[97;40m\x1b[2J\x1b[H")
            sys.stdout.flush()
        except BaseException:
            self.keyboard.close()
            raise
        return self

    def size(self) -> tuple[int, int]:
        size = shutil.get_terminal_size((100, 32))
        width, height = fit_viewport(size.columns, size.lines, self.max_cells)
        self.origin = (max(1, (size.lines - 1 - height) // 2 + 1),
                       max(1, (size.columns - width) // 2 + 1))
        return width, height

    @property
    def mouse_captured(self):
        return isinstance(self.keyboard, WindowsKeyboard) and self.keyboard.mouse.captured

    def set_mouse_capture(self, active):
        if isinstance(self.keyboard, WindowsKeyboard):
            self.keyboard.set_mouse_capture(active)

    def draw(self, lines: list[str]) -> None:
        size = (len(lines[0]), len(lines), self.origin)
        clear = "\x1b[2J" if size != self.last_size else ""
        self.last_size = size
        top, left = self.origin
        separator = "\r\n" + (f"\x1b[{left}G" if left > 1 else "")
        sys.stdout.write(clear + f"\x1b[{top};{left}H" + separator.join(lines))
        sys.stdout.flush()

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            sys.stdout.write("\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
        finally:
            if self.keyboard:
                self.keyboard.close()

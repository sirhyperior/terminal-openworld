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

        class EventData(ctypes.Union):
            _fields_ = [("KeyEvent", KeyEvent), ("FocusEvent", wt.BOOL),
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
        self.handle = self.api.GetStdHandle(-10)
        self.output = self.api.GetStdHandle(-11)
        mode_in, mode_out = wt.DWORD(), wt.DWORD()
        if not self.api.GetConsoleMode(self.handle, ctypes.byref(mode_in)):
            raise OSError("Open this program in a real terminal, such as Windows Terminal or PowerShell.")
        if not self.api.GetConsoleMode(self.output, ctypes.byref(mode_out)):
            raise OSError("Terminal output is unavailable. Use --snapshot when redirecting output.")
        self.original_input, self.original_output = mode_in.value, mode_out.value
        # Disable line buffering, echo, Quick Edit and VT keyboard translation.
        new_input = (mode_in.value & ~(0x1 | 0x2 | 0x4 | 0x10 | 0x40 | 0x200)) | 0x80 | 0x8
        if not self.api.SetConsoleMode(self.output, mode_out.value | 0x4):
            raise OSError("This terminal does not support ANSI output. Try Windows Terminal.")
        if not self.api.SetConsoleMode(self.handle, new_input):
            self.api.SetConsoleMode(self.output, self.original_output)
            raise ctypes.WinError(ctypes.get_last_error())
        self.records = (InputRecord * 256)()
        self.count = wt.DWORD()
        self.available = wt.DWORD()
        self.down: set[str] = set()
        self.mapping = {0x1B: "escape", 0x20: "space", 0x10: "shift", 0xA0: "shift", 0xA1: "shift",
                        0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down", 0x09: "tab"}
        self.mapping.update({ord(key.upper()): key for key in "wasdqemhprf"})

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
                if record.EventType == 0x10 and not record.Event.FocusEvent:
                    self.down.clear()
                    pressed.add("blur")
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
        return Keys(set(self.down), pressed)

    def close(self) -> None:
        self.api.SetConsoleMode(self.handle, self.original_input)
        self.api.SetConsoleMode(self.output, self.original_output)


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
        while True:
            try:
                data = os.read(self.fd, 4096)
            except BlockingIOError:
                break
            if not data:
                break
            self.pending += data
        arrows = {b"A": "up", b"B": "down", b"C": "right", b"D": "left"}
        while self.pending:
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
                key = {" ": "space", "\t": "tab", "\x03": "escape"}.get(char, char.lower())
                if char in "WASD":
                    self.expiry["shift"] = now + 0.20
            if key in {"w", "a", "s", "d", "q", "e", "m", "h", "p", "r", "f", "escape", "space",
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

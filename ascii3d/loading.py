"""Bounded startup activity display; percentages count completed phases only."""

from contextlib import contextmanager
import os
import shutil
import threading
import time
from typing import Callable, TextIO


STARTUP_STAGES = (
    "Building world",
    "Preparing view",
    "Preparing surfaces",
    "Preparing ambience",
    "Opening terminal",
    "Starting audio",
)

ANIMATION_INTERVAL = 0.15
TIP_INTERVAL = 3.0
SPINNER = "|/-\\"
GATEHOUSE = (
    r"                           _.._               *",
    r"           .           .-'      '-.",
    r"                      (            )      .",
    r"        *              '-.______.-'",
    "             /\\                 /\\",
    "        /\\  /__\\       /\\      /__\\  /\\",
    "       /__\\ |::|_n_n_n/  \\n_n_n|::| /__\\",
    r"       |::|_|::|     /____\    |::|_|::|",
    r"   ____|::|_|::|_____| /\ |____|::|_|::|____",
    r" _/:::::::::::::;;;;;|/||\|;;;;;:::::::::::::\_",
    r"  `----._     _..----' || `----.._     _.----'",
    r"         `---'    _..--''--.._    `---'",
)
TITLE = "M O N O L I T H"
GATEHOUSE_WIDTH = max(map(len, GATEHOUSE))
TIPS = (
    "WASD move; Shift sprint; Space jump.",
    "E opens doors and collects weapons.",
    "M shows nearby roads and bridges.",
    "H shows controls; P pauses play.",
    "Only one weapon fits in your hands.",
    "Watch the Warden's raised fists.",
    "Ordinary blocks require a jump.",
)
COMPACT_TIPS = (
    "WASD move; Space jumps.",
    "E opens / collects.",
    "M shows the map.",
    "H help; P pause.",
    "One weapon at a time.",
    "Dodge raised fists.",
    "Jump onto blocks.",
)


class LoadingProgress:
    """Report completed startup phases, rather than estimated elapsed time.

    Call advance only after the current stage succeeds. No timer advances the
    percentage, and close never turns an interrupted load into 100 percent.
    """

    def __init__(self, stream: TextIO, enabled: bool, *,
                 clock: Callable[[], float] | None = None):
        self.stream = stream
        self.enabled = enabled
        self.completed = 0
        self._started = False
        self._closed = False
        self._line_width = 0
        self._alternate_screen = False
        self._card_size = None
        self._progress_row = 1
        self._clock = clock if clock is not None else time.monotonic
        self._started_at = 0.0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._worker = None

    def start(self) -> None:
        with self._lock:
            if self._started or self._closed:
                return
            self._started = True
            self._started_at = self._clock()
            if not self.enabled:
                return
            self._draw()
            worker = threading.Thread(target=self._animate, name="monolith-loading", daemon=True)
            # Assign only a started worker, so close can always join safely.
            try:
                worker.start()
            except RuntimeError:
                # A constrained host can still display synchronous phases.
                return
            self._worker = worker

    def advance(self) -> None:
        self.start()
        with self._lock:
            if self._closed:
                return
            self.completed += 1
            ready = self.completed == len(STARTUP_STAGES)
            if ready:
                self._stop.set()
            self._draw()
        if ready:
            self.close()

    @contextmanager
    def suspend(self):
        """Serialize terminal screen transitions with the animation writer."""
        with self._lock:
            yield

    def clear_line(self) -> None:
        """Leave the main screen clean before the terminal saves/switches it."""
        with self._lock:
            if self.enabled and self._started and not self._closed:
                self.stream.write('\r' + ' ' * min(self._size()[0], self._line_width) + '\r')
                self.stream.flush()
                self._line_width = 0

    def use_alternate_screen(self) -> None:
        """Redraw the splash once the gameplay terminal owns the screen."""
        with self._lock:
            self._alternate_screen = True
            self._card_size = None

    def _animate(self) -> None:
        while not self._stop.wait(ANIMATION_INTERVAL):
            with self._lock:
                if self._closed or self._stop.is_set():
                    return
                try:
                    self._draw()
                except (OSError, ValueError):
                    # A lost stream must not leave a noisy background thread.
                    # Synchronous phase writes retain normal app error handling.
                    self._stop.set()
                    return

    def _size(self) -> tuple[int, int]:
        try:
            size = os.get_terminal_size(self.stream.fileno())
        except (AttributeError, OSError, ValueError):
            size = shutil.get_terminal_size((80, 24))
        # Before Terminal starts, autowrap still belongs to the user's shell.
        # Reserve its final column and erase only the previous progress text.
        return max(0, size.columns - 1), size.lines

    def _draw_card(self, width: int, height: int) -> None:
        rows = ()
        if width >= 50 and height >= 6:
            scene = GATEHOUSE if height >= len(GATEHOUSE) + 7 else ()
            left = (width - GATEHOUSE_WIDTH) // 2
            rows = (*(" " * left + row for row in scene), "", TITLE.center(width).rstrip(), "")
        if self._alternate_screen:
            top = max(1, (height - len(rows) - 3) // 2 + 1)
            self.stream.write(f"\x1b[2J\x1b[{top};1H" + "\r\n".join(rows))
            self._progress_row = top + len(rows)
        elif rows:
            self.stream.write("\n".join(rows) + "\n")
        self._card_size = width, height

    def _draw(self) -> None:
        if not self.enabled:
            return
        width, height = self._size()
        if self._card_size is None or (self._alternate_screen and self._card_size != (width, height)):
            self._draw_card(width, height)
        percent = self.completed * 100 // len(STARTUP_STAGES)
        ready = self.completed == len(STARTUP_STAGES)
        stage = STARTUP_STAGES[self.completed] if not ready else "Ready"
        elapsed = max(0.0, self._clock() - self._started_at)
        spinner = "*" if ready else SPINNER[int(elapsed / ANIMATION_INTERVAL) % len(SPINNER)]
        tip_index = int(elapsed / TIP_INTERVAL) % len(TIPS)
        footnote = width >= 50 and height >= 6 and self._alternate_screen
        if width < 50:
            line = f"Loading {percent:3d}% {spinner} | {stage}"
        else:
            bar_width = 24 if width >= 100 else 12
            filled = self.completed * bar_width // len(STARTUP_STAGES)
            bar = "#" * filled + "-" * (bar_width - filled)
            label = f"MONOLITH: {stage}" if width >= 100 or ready else stage
            line = f"Loading {percent:3d}% | {label} {spinner} [{bar}]"
            if width >= 100:
                line += f" {int(elapsed)}s"
            if not ready and not footnote:
                available = width - len(line) - 3
                tip = TIPS[tip_index] if len(TIPS[tip_index]) <= available else COMPACT_TIPS[tip_index]
                if len(tip) <= available:
                    line += " | " + tip
        line = line[:width]
        if self._alternate_screen:
            view = f"\x1b[{self._progress_row};1H\x1b[2K" + line.center(width).rstrip()
            if footnote:
                tip = "" if ready else TIPS[tip_index]
                view += f"\x1b[{self._progress_row + 2};1H\x1b[2K" + tip.center(width).rstrip()
            self.stream.write(view)
        else:
            erase = min(width, max(self._line_width, len(line)))
            self.stream.write("\r" + line.ljust(erase))
            self._line_width = len(line)
        self.stream.flush()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            worker = self._worker
        # Never join while holding the writer lock: the worker may be waiting
        # for it after its timer expires. No loading writes survive this call.
        if worker is not None and worker is not threading.current_thread():
            worker.join()
        if self.enabled and self._started:
            if not self._alternate_screen:
                self.stream.write("\n")
            self.stream.flush()

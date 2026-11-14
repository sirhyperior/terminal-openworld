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
            width = self._width()
            if width >= 50:
                self.stream.write("M O N O L I T H".center(width) + "\n"
                                  + "The road waits beyond the gate.".center(width) + "\n\n")
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
                self.stream.write('\r' + ' ' * min(self._width(), self._line_width) + '\r')
                self.stream.flush()
                self._line_width = 0

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

    def _width(self) -> int:
        try:
            columns = os.get_terminal_size(self.stream.fileno()).columns
        except (AttributeError, OSError, ValueError):
            columns = shutil.get_terminal_size((80, 24)).columns
        # Before Terminal starts, autowrap still belongs to the user's shell.
        # Reserve its final column and erase only the previous progress text.
        return max(0, columns - 1)

    def _draw(self) -> None:
        if not self.enabled:
            return
        width = self._width()
        percent = self.completed * 100 // len(STARTUP_STAGES)
        ready = self.completed == len(STARTUP_STAGES)
        stage = STARTUP_STAGES[self.completed] if not ready else "Ready"
        elapsed = max(0.0, self._clock() - self._started_at)
        spinner = "*" if ready else SPINNER[int(elapsed / ANIMATION_INTERVAL) % len(SPINNER)]
        if width < 50:
            line = f"Loading {percent:3d}% {spinner} | {stage}"
        else:
            filled = self.completed * 12 // len(STARTUP_STAGES)
            bar = "#" * filled + "-" * (12 - filled)
            label = f"MONOLITH: {stage}" if width >= 100 or ready else stage
            line = f"Loading {percent:3d}% | {label} {spinner} [{bar}]"
            if width >= 100:
                line += f" {int(elapsed)}s"
            if not ready:
                index = int(elapsed / TIP_INTERVAL) % len(TIPS)
                available = width - len(line) - 3
                tip = TIPS[index] if len(TIPS[index]) <= available else COMPACT_TIPS[index]
                if len(tip) <= available:
                    line += " | " + tip
        line = line[:width]
        erase = min(width, max(self._line_width, len(line)))
        self.stream.write("\r" + line.ljust(erase))
        self.stream.flush()
        self._line_width = len(line)

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
            self.stream.write("\n")
            self.stream.flush()

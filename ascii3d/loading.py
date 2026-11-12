"""Small, synchronous startup progress display with no input or device I/O."""

import os
import shutil
from typing import TextIO


STARTUP_STAGES = (
    "Building world",
    "Preparing view",
    "Preparing surfaces",
    "Preparing ambience",
    "Opening terminal",
    "Starting audio",
)


class LoadingProgress:
    """Report completed startup phases, rather than estimated elapsed time.

    Call advance only after the current stage succeeds. No timer advances the
    percentage, and close never turns an interrupted load into 100 percent.
    """

    def __init__(self, stream: TextIO, enabled: bool):
        self.stream = stream
        self.enabled = enabled
        self.completed = 0
        self._started = False
        self._closed = False
        self._line_width = 0

    def start(self) -> None:
        if self._started or self._closed:
            return
        self._started = True
        self._draw()

    def advance(self) -> None:
        if self._closed:
            return
        self.start()
        self.completed += 1
        self._draw()
        if self.completed == len(STARTUP_STAGES):
            self.close()

    def _draw(self) -> None:
        if not self.enabled:
            return
        percent = self.completed * 100 // len(STARTUP_STAGES)
        stage = STARTUP_STAGES[self.completed] if self.completed < len(STARTUP_STAGES) else "Ready"
        try:
            columns = os.get_terminal_size(self.stream.fileno()).columns
        except (AttributeError, OSError, ValueError):
            columns = shutil.get_terminal_size((80, 24)).columns
        # Before Terminal starts, autowrap still belongs to the user's shell.
        # Reserve its final column and erase only the previous progress text.
        width = max(0, columns - 1)
        line = f"Loading {percent:3d}% | MONOLITH: {stage}"[:width]
        erase = min(width, max(self._line_width, len(line)))
        self.stream.write("\r" + line.ljust(erase))
        self.stream.flush()
        self._line_width = len(line)

    def close(self) -> None:
        if self._closed:
            return
        if self.enabled and self._started:
            self.stream.write("\n")
            self.stream.flush()
        self._closed = True

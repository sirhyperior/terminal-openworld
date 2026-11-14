"""Foreground styling kept separate from the terminal's visible text cells."""

from dataclasses import dataclass
import re


# Sixteen perceptually useful, neutral foreground levels. The lowest still
# leaves a faint visible mark; empty/fully dark samples use a space instead.
GRAY_LEVELS = (28, 38, 50, 63, 77, 92, 108, 125,
               143, 161, 179, 197, 214, 230, 243, 255)
GRAY_CODES = tuple(f"\x1b[38;2;{level};{level};{level}m" for level in GRAY_LEVELS)
WHITE_ON_BLACK = "\x1b[97;40m"
_ASCII_ROW = re.compile(r"[ -~]*\Z")


@dataclass(frozen=True, slots=True)
class StyledFrame:
    """A rectangular ASCII frame with a compact foreground index per cell.

    Rows contain visible ASCII only, never control sequences. Callers own the
    buffers until construction and must not mutate them while drawing a frame.
    ANSI byte lengths therefore never influence viewport sizing or clipping.
    """

    width: int
    height: int
    rows: list[str]
    styles: list[bytearray]
    materials: list[bytearray] | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.width, int) or not isinstance(self.height, int)
                or self.width < 1 or self.height < 1):
            raise ValueError("frame dimensions must be positive integers")
        if len(self.rows) != self.height or len(self.styles) != self.height:
            raise ValueError("frame row count must match its height")
        if self.materials is not None and (len(self.materials) != self.height or any(
                not isinstance(row, bytearray) or len(row) != self.width for row in self.materials)):
            raise ValueError("material buffers must match frame dimensions")
        for row, style in zip(self.rows, self.styles):
            if len(row) != self.width or _ASCII_ROW.fullmatch(row) is None:
                raise ValueError("frame rows must contain exactly width printable ASCII cells")
            if not isinstance(style, bytearray) or len(style) != self.width:
                raise ValueError("frame styles must be width-sized bytearrays")
            if max(style) >= len(GRAY_LEVELS):
                raise ValueError("foreground styles must be between 0 and 15")

    def ansi_rows(self) -> list[str]:
        """Encode adjacent foreground runs, restoring white/black per row.

        Blank cells have no visible foreground. Ignoring their style changes
        avoids spending output bandwidth on empty sky or cleared panels.
        """
        result = []
        for row, styles in zip(self.rows, self.styles):
            parts = ["\x1b[40m"]
            current = -1
            start = 0
            for column, char in enumerate(row):
                if char == " ":
                    continue
                style = styles[column]
                if style != current:
                    parts.append(row[start:column])
                    parts.append(GRAY_CODES[style])
                    start, current = column, style
            parts.append(row[start:])
            parts.append(WHITE_ON_BLACK)
            result.append("".join(parts))
        return result

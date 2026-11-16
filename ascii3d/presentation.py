"""Foreground styling kept separate from the terminal's visible text cells."""

from dataclasses import dataclass
import re

from .palette import COLOR_CODES, GRAY_LEVELS, UI


# Sixteen neutral foreground levels with readable shadows against black.
# Empty samples use a space, so the raised foreground floor never lights sky.
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
    effects: list[bytearray] | None = None
    color_mode: str = "gray"

    def __post_init__(self) -> None:
        if (not isinstance(self.width, int) or not isinstance(self.height, int)
                or self.width < 1 or self.height < 1):
            raise ValueError("frame dimensions must be positive integers")
        if len(self.rows) != self.height or len(self.styles) != self.height:
            raise ValueError("frame row count must match its height")
        if self.color_mode not in ("gray", "color"):
            raise ValueError("styled foreground mode must be gray or color")
        if self.materials is not None and (len(self.materials) != self.height or any(
                not isinstance(row, bytearray) or len(row) != self.width for row in self.materials)):
            raise ValueError("material buffers must match frame dimensions")
        if self.effects is not None and (len(self.effects) != self.height or any(
                not isinstance(row, bytearray) or len(row) != self.width or max(row) >= 16
                for row in self.effects)):
            raise ValueError("effect buffers must match dimensions with values 0..15")
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
        if self.color_mode == "color":
            return self._color_rows()
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

    def _color_rows(self) -> list[str]:
        result = []
        palette = COLOR_CODES
        for row_index, (row, styles) in enumerate(zip(self.rows, self.styles)):
            materials = self.materials[row_index] if self.materials is not None else None
            effects = self.effects[row_index] if self.effects is not None else None
            parts = ["\x1b[40m"]
            current = None
            start = 0
            for column, char in enumerate(row):
                if char == " ":
                    continue
                material = materials[column] if materials is not None else UI
                effect = effects[column] if effects is not None else 0
                code = palette[material][effect * 16 + styles[column]]
                if code != current:
                    parts.append(row[start:column])
                    parts.append(code)
                    start, current = column, code
            parts.append(row[start:])
            parts.append(WHITE_ON_BLACK)
            result.append("".join(parts))
        return result

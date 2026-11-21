"""Foreground styling kept separate from the terminal's visible text cells."""

from dataclasses import dataclass
import re

from .palette import COLOR_CODES, GRAY_LEVELS, UI


# Sixteen neutral foreground levels with readable shadows against black.
# Empty samples use a space, so the raised foreground floor never lights sky.
GRAY_CODES = tuple(f"\x1b[38;2;{level};{level};{level}m" for level in GRAY_LEVELS)
WHITE_ON_BLACK = "\x1b[97;40m"
_ASCII_ROW = re.compile(r"[ -~]*\Z")


def encode_ansi_row(row, styles, materials, effects, mode, start=0, stop=None):
    """Encode a row span with its own foreground and background state."""
    text = row[start:stop]
    if styles is None:
        return text
    parts = ["\x1b[40m"]
    current = None
    plain_start = start
    if mode == "gray":
        for column, char in enumerate(text, start):
            if char != " " and (style := styles[column]) != current:
                parts.extend((row[plain_start:column], GRAY_CODES[style]))
                plain_start, current = column, style
    else:
        palette = COLOR_CODES
        for column, char in enumerate(text, start):
            if char != " ":
                material = materials[column] if materials is not None else UI
                effect = effects[column] if effects is not None else 0
                code = palette[material][effect * 16 + styles[column]]
                if code != current:
                    parts.extend((row[plain_start:column], code))
                    plain_start, current = column, code
    parts.extend((row[plain_start:stop], WHITE_ON_BLACK))
    return "".join(parts)


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
        materials = self.materials if self.color_mode == "color" else None
        effects = self.effects if self.color_mode == "color" else None
        return [encode_ansi_row(row, style, materials[y] if materials is not None else None,
                                effects[y] if effects is not None else None, self.color_mode)
                for y, (row, style) in enumerate(zip(self.rows, self.styles))]

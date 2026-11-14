"""Bounded foreground palettes for semantic materials, depth and firelight.

The first eleven identifiers deliberately match the world's material IDs.
Later identifiers describe rendered details only; they never change collision
or the material used for contact sound. Palette lookup requires no world import.
"""


AIR, STONE, FLOOR, METAL, CRATE, GRASS, WATER, WOOD, LEAVES, PATH, BRIDGE = range(11)
FIRE, EMBER, ARCANE, STRAW, BONE = range(11, 16)
UI_ACCENT, UI_DANGER, UI_POSITIVE, UI_MUTED = range(16, 20)
DUST, ASH = range(20, 22)
UI = 255

GRAY_LEVELS = (9, 16, 25, 36, 50, 67, 87, 110,
               136, 162, 188, 211, 229, 242, 250, 255)

# Saturation is intentional: character density and lighting still reveal shape.
# Palette construction compensates for hue luminance so the common low/mid
# levels do not become much darker than their grayscale counterparts.
BASE_COLORS = {
    STONE: (158, 180, 213), FLOOR: (209, 180, 135),
    METAL: (157, 202, 232), CRATE: (183, 112, 49),
    GRASS: (78, 195, 85), WATER: (51, 179, 207),
    WOOD: (176, 106, 51), LEAVES: (42, 175, 103),
    PATH: (186, 150, 83), BRIDGE: (161, 112, 67),
    FIRE: (255, 105, 23), EMBER: (250, 65, 22),
    ARCANE: (170, 98, 255), STRAW: (222, 166, 70),
    BONE: (233, 222, 181), UI_ACCENT: (85, 205, 225),
    UI_DANGER: (255, 86, 79), UI_POSITIVE: (91, 222, 139),
    UI_MUTED: (137, 157, 184),
    DUST: (202, 180, 133), ASH: (142, 164, 196),
}


def _material_row(material, base):
    peak = max(base)
    normalized = tuple(channel / peak for channel in base)
    values = []
    for effects in range(16):
        fog, warmth = effects >> 2, effects & 3
        # UI cues do not inherit the scene's atmospheric effects.
        interface = material in (UI_ACCENT, UI_DANGER, UI_POSITIVE, UI_MUTED)
        if interface:
            fog = warmth = 0
        luminance = sum(channel * weight for channel, weight in
                        zip(normalized, (0.2126, 0.7152, 0.0722)))
        fog_amount = (0.0, 0.15, 0.30, 0.45)[fog]
        if material in (FIRE, EMBER, ARCANE):
            fog_amount *= 0.55
        distant = (luminance * 0.65, luminance * 0.82, luminance * 1.10)
        color = tuple(a * (1 - fog_amount) + b * fog_amount
                      for a, b in zip(normalized, distant))
        warm_amount = (0.0, 0.18, 0.36, 0.60)[warmth]
        color = tuple(a * (1 - warm_amount) + b * warm_amount
                      for a, b in zip(color, (1.0, 0.34, 0.08)))
        for level_index, level in enumerate(GRAY_LEVELS):
            # A shadow is not just the same saturated hue with a smaller RGB.
            # Cooler, quieter recesses and pale highlights reveal local volume.
            shade = color
            if not interface and material not in (FIRE, EMBER, ARCANE):
                shadow = max(0.0, (7 - level_index) / 7) * 0.48
                quiet = sum(color) / 3
                cool = (quiet * 0.64, quiet * 0.82, quiet * 1.12)
                shade = tuple(a * (1 - shadow) + b * shadow for a, b in zip(color, cool))
            # Hot cores approach white while the lower-intensity surrounding
            # glyphs retain the flame or magic hue. This needs no bloom overlay.
            white = 0.0
            if material in (FIRE, EMBER):
                white = max(0.0, (level_index - 10) / 5) ** 1.6
            elif material == ARCANE:
                white = max(0.0, (level_index - 11) / 4) * 0.60
            elif not interface:
                polish = (0.80 if material == METAL else 0.58 if material == WATER else
                          0.45 if material in (STONE, FLOOR, BONE) else 0.26)
                white = max(0.0, (level_index - 10) / 5) ** 2 * polish
            lit = tuple(channel * (1 - white) + white for channel in shade)
            luminance = sum(channel * weight for channel, weight in
                            zip(lit, (0.2126, 0.7152, 0.0722)))
            scale = level / luminance
            values.append(tuple(max(0, min(255, round(channel * scale))) for channel in lit))
    return tuple(values)


_NEUTRAL_ROW = tuple((level, level, level) for _ in range(16) for level in GRAY_LEVELS)
_RGB_ROWS = {material: _material_row(material, base) for material, base in BASE_COLORS.items()}
_RGB_ROWS[AIR] = ((0, 0, 0),) * 256
COLOR_RGB = tuple(_RGB_ROWS.get(material, _NEUTRAL_ROW) for material in range(256))

# Unknown materials share the neutral row instead of allocating duplicate tables.
# Identical RGB values also share their ANSI code, allowing runs to coalesce even
# when semantic material/effect identifiers differ.
_ANSI_CODES = {}


def _ansi(rgb):
    value = _ANSI_CODES.get(rgb)
    if value is None:
        value = f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
        _ANSI_CODES[rgb] = value
    return value


_NEUTRAL_CODES = tuple(_ansi(rgb) for rgb in _NEUTRAL_ROW)
_CODE_ROWS = {material: tuple(_ansi(rgb) for rgb in row) for material, row in _RGB_ROWS.items()}
COLOR_CODES = tuple(_CODE_ROWS.get(material, _NEUTRAL_CODES) for material in range(256))


def color_rgb(material: int, level: int, effects: int = 0) -> tuple[int, int, int]:
    """Look up one foreground color; effects packs two fog and two warmth bits."""
    if (type(material) is not int or not 0 <= material <= 255
            or type(level) is not int or not 0 <= level < 16
            or type(effects) is not int or not 0 <= effects < 16):
        raise ValueError("color lookup requires material 0..255, level/effects 0..15")
    return COLOR_RGB[material][effects * 16 + level]

"""Bounded dark-fantasy foreground ramps for materials, depth and spectral light.

The first eleven identifiers deliberately match the world's material IDs.
Later identifiers describe rendered details only; they never change collision
or the material used for contact sound. Palette lookup requires no world import.
"""


AIR, STONE, FLOOR, METAL, CRATE, GRASS, WATER, WOOD, LEAVES, PATH, BRIDGE = range(11)
FIRE, EMBER, ARCANE, STRAW, BONE = range(11, 16)
UI_ACCENT, UI_DANGER, UI_POSITIVE, UI_MUTED = range(16, 20)
DUST, ASH = range(20, 22)
WIND_GRASS, WIND_LEAVES, WATER_CREST = range(22, 25)
CLOTH, LEATHER, SKIN = range(25, 28)
UI = 255

# Keep the readable shadow floor while leaving room for the brightest glyphs
# to separate in gray mode. Sky is always an empty black cell.
GRAY_LEVELS = (100, 106, 113, 121, 130, 141, 154, 169,
               186, 198, 210, 221, 232, 242, 250, 255)

# Four painted stops per material: recess, shade, lit face and rim. Ordinary
# surfaces share a graphite recess. Their midtones carry most of the local
# color; the brightest stone stays pewter so magic can reach paper white.
_GRAPHITE = (100, 102, 113)
_RAMPS = {
    STONE: (_GRAPHITE, (123, 130, 146), (165, 170, 186), (225, 229, 237)),
    FLOOR: (_GRAPHITE, (138, 127, 142), (181, 164, 178), (229, 218, 225)),
    METAL: (_GRAPHITE, (109, 135, 158), (143, 182, 202), (239, 248, 250)),
    CRATE: (_GRAPHITE, (147, 122, 134), (199, 160, 172), (232, 208, 211)),
    GRASS: (_GRAPHITE, (141, 122, 158), (190, 161, 192), (226, 209, 215)),
    WATER: (_GRAPHITE, (104, 128, 168), (133, 176, 221), (183, 217, 239)),
    WOOD: (_GRAPHITE, (145, 123, 135), (195, 164, 174), (223, 211, 214)),
    LEAVES: (_GRAPHITE, (123, 126, 154), (171, 165, 202), (211, 210, 228)),
    PATH: ((88, 87, 81), (110, 110, 101), (141, 144, 133), (184, 184, 168)),
    BRIDGE: (_GRAPHITE, (137, 126, 148), (185, 165, 183), (222, 209, 215)),
    FIRE: ((82, 100, 155), (79, 151, 196), (130, 219, 231), (255, 255, 255)),
    EMBER: ((110, 94, 141), (133, 116, 185), (158, 166, 216), (211, 225, 244)),
    ARCANE: ((106, 95, 136), (155, 116, 185), (206, 153, 225), (248, 231, 255)),
    STRAW: (_GRAPHITE, (139, 129, 136), (183, 166, 162), (226, 215, 204)),
    BONE: (_GRAPHITE, (139, 136, 145), (193, 186, 186), (247, 242, 232)),
    DUST: (_GRAPHITE, (144, 129, 152), (173, 163, 190), (211, 207, 221)),
    ASH: (_GRAPHITE, (123, 137, 147), (154, 178, 185), (209, 224, 225)),
    WIND_GRASS: (_GRAPHITE, (134, 141, 168), (175, 185, 215), (226, 232, 243)),
    WIND_LEAVES: (_GRAPHITE, (149, 132, 166), (191, 168, 205), (229, 215, 235)),
    WATER_CREST: (_GRAPHITE, (109, 143, 157), (128, 201, 204), (210, 244, 239)),
    CLOTH: (_GRAPHITE, (120, 104, 141), (174, 143, 175), (219, 198, 221)),
    LEATHER: (_GRAPHITE, (139, 109, 104), (178, 140, 114), (215, 182, 151)),
    SKIN: (_GRAPHITE, (158, 121, 114), (204, 167, 142), (242, 208, 180)),
    UI_ACCENT: (_GRAPHITE, (128, 145, 166), (171, 190, 215), (215, 231, 246)),
    UI_DANGER: ((136, 84, 103), (180, 105, 130), (222, 143, 157), (254, 191, 199)),
    UI_POSITIVE: (_GRAPHITE, (115, 147, 144), (151, 189, 178), (206, 238, 221)),
    UI_MUTED: (_GRAPHITE, (126, 131, 143), (157, 164, 174), (199, 205, 216)),
}
_MIST = (_GRAPHITE, (120, 133, 150), (154, 168, 187), (180, 193, 211))
_SPECTRAL_LIGHT = ((95, 106, 122), (99, 146, 165), (133, 205, 216), (224, 249, 250))


def _mix(left, right, fraction):
    return tuple(round(a + (b - a) * fraction) for a, b in zip(left, right))


def _tones(stops):
    # Levels 0, 5, 10, 15 land exactly on the authored stops.
    return tuple(_mix(stops[group], stops[group + 1], step / 5)
                 for group in range(3) for step in range(5)) + (stops[-1],)


def _material_row(material, stops):
    if material in (UI_ACCENT, UI_DANGER, UI_POSITIVE, UI_MUTED):
        return _tones(stops) * 16
    values = []
    for fog in (0.0, 0.20, 0.43, 0.68):
        if material in (FIRE, EMBER, ARCANE):
            fog *= 0.5
        for glow in (0.0, 0.24, 0.46, 0.72):
            # A distant lit surface recedes into the same mist as its neighbor.
            lit = (_mix(a, b, glow) for a, b in zip(stops, _SPECTRAL_LIGHT))
            veiled = tuple(_mix(a, b, fog) for a, b in zip(lit, _MIST))
            values.extend(_tones(veiled))
    return tuple(values)


_NEUTRAL_ROW = tuple((level, level, level) for _ in range(16) for level in GRAY_LEVELS)
_RGB_ROWS = {material: _material_row(material, stops) for material, stops in _RAMPS.items()}
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
    """Look up one foreground color from two fog and two local light bits."""
    if (type(material) is not int or not 0 <= material <= 255
            or type(level) is not int or not 0 <= level < 16
            or type(effects) is not int or not 0 <= effects < 16):
        raise ValueError("color lookup requires material 0..255, level/effects 0..15")
    return COLOR_RGB[material][effects * 16 + level]

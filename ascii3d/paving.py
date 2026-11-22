"""A seamless stone-and-earth texture shared by both lighting paths."""

from functools import lru_cache
import math
import random


_STONES_ACROSS = 16
_TEXELS_PER_STONE = 8
PAVING_SIZE = _STONES_ACROSS * _TEXELS_PER_STONE
PAVING_SCALE = 12.0
PAVING_DISTANCE = 20.0
PAVING_DISTANT_TONE = 0.59


@lru_cache(maxsize=1)
def paving_tile() -> bytes:
    """Rasterize jittered stones once with periodic neighbors at the edges."""
    rng = random.Random(1906)
    sites = {(x, y): (rng.uniform(0.08, 0.92), rng.uniform(0.08, 0.92),
                      rng.uniform(0.55, 0.81), rng.uniform(0.057, 0.109))
             for y in range(_STONES_ACROSS) for x in range(_STONES_ACROSS)}
    tile = bytearray(PAVING_SIZE ** 2)
    for cell_x, cell_y in sites:
        neighbors = []
        for sy in range(cell_y - 2, cell_y + 3):
            for sx in range(cell_x - 2, cell_x + 3):
                dx, dy, stone_tone, joint = sites[sx % _STONES_ACROSS, sy % _STONES_ACROSS]
                neighbors.append((sx + dx, sy + dy, stone_tone, joint))
        for j in range(_TEXELS_PER_STONE):
            y = cell_y + j / _TEXELS_PER_STONE
            for i in range(_TEXELS_PER_STONE):
                x = cell_x + i / _TEXELS_PER_STONE
                nearest = second = math.inf
                closest = next_site = neighbors[0]
                for site in neighbors:
                    square = (x - site[0]) ** 2 + (y - site[1]) ** 2
                    if square < nearest:
                        nearest, second = square, nearest
                        closest, next_site = site, closest
                    elif square < second:
                        second, next_site = square, site
                sx, sy, stone_tone, joint = closest
                rim_x, rim_y = sx - next_site[0], sy - next_site[1]
                separation = math.hypot(rim_x, rim_y)
                edge = (second - nearest) / (2.0 * separation)
                # Let packed earth separate the crowns. The bevel faces the
                # same northwest moonlight as the rest of the scene.
                rise = max(0.0, edge - joint)
                coverage = min(1.0, rise * 13.0)
                bevel = max(0.0, 1.0 - rise * 5.0)
                moonward = (rim_x + rim_y) / separation
                crown = max(0.0, 1.0 - nearest * 2.0)
                face = stone_tone + crown * 0.13 + (sx - x + sy - y) * 0.05
                face += bevel * (0.04 + moonward * 0.16)
                tone = 0.15 + (face - 0.15) * coverage
                offset = (cell_y * _TEXELS_PER_STONE + j) * PAVING_SIZE + cell_x * _TEXELS_PER_STONE + i
                tile[offset] = round(min(1.0, tone) * 255)
    return bytes(tile)


def cobble_texture(x: float, y: float, distance: float) -> float:
    """Sample the world-anchored texture and blend out sub-cell relief."""
    if distance >= PAVING_DISTANCE:
        return PAVING_DISTANT_TONE
    tile = paving_tile()
    x, y = x * PAVING_SCALE, y * PAVING_SCALE
    ix, iy = math.floor(x), math.floor(y)
    u, v = x - ix, y - iy
    x0, x1 = ix % PAVING_SIZE, (ix + 1) % PAVING_SIZE
    y0, y1 = (iy % PAVING_SIZE) * PAVING_SIZE, ((iy + 1) % PAVING_SIZE) * PAVING_SIZE
    a, b = tile[y0 + x0], tile[y1 + x0]
    top = a + (tile[y0 + x1] - a) * u
    bottom = b + (tile[y1 + x1] - b) * u
    stone = (top + (bottom - top) * v) / 255.0
    detail = min(1.0, (PAVING_DISTANCE - distance) * 0.10)
    return PAVING_DISTANT_TONE + (stone - PAVING_DISTANT_TONE) * detail

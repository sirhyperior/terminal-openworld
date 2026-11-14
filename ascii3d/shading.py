"""Shared, world-anchored ASCII materials and foreground luminance.

Ink tokens are cached strings: compositors move their semantic material/tone
with the winning glyph, without allocating an object for each scene cell.
Plain text consumers still receive ordinary characters when joining rows.
"""

from functools import lru_cache
import math

from .world import BRIDGE, CRATE, FLOOR, GRASS, LEAVES, METAL, PATH, STONE, WATER, WOOD


RAMP = "..,:;irsxXA#%@"
ALBEDO = (0.0, 0.72, 0.64, 0.85, 0.59, 0.58, 0.74, 0.58, 0.54, 0.61, 0.64)


class Ink(str):
    """A reusable glyph carrying its foreground level and source material."""

    __slots__ = ("level", "material")

    def __new__(cls, glyph: str, level: int, material: int):
        value = super().__new__(cls, glyph)
        value.level, value.material = level, material
        return value


@lru_cache(maxsize=8192)
def ink(glyph: str, level: int, material: int = STONE) -> Ink:
    return Ink(glyph, max(0, min(15, level)), material)


class Shading:
    """Bounded material lighting; visibility queries never change simulation."""

    MAX_LIGHTS = 2
    MAX_SHADOW_SAMPLES = 256

    def __init__(self, world=None):
        self.world = world
        self.lights = ()
        self._visibility = {}

    def prepare(self, player, seconds=0.0):
        self._visibility.clear()
        if self.world is None:
            self.lights = ()
            return
        balls = sorted(self.world.combat.fireballs,
                       key=lambda ball: (ball.x - player.x) ** 2 + (ball.y - player.y) ** 2)
        self.lights = tuple((ball.x, ball.y, ball.z) for ball in balls[:self.MAX_LIGHTS])

    def surface(self, material, x, y, z, normal, distance, *, glyph=None, emission=0.0,
                texture_position=None):
        nx, ny, nz = normal
        directional = max(0.0, -nx * 0.38 - ny * 0.48 + nz * 0.79)
        light = 0.28 + directional * 0.72
        # Stable coarse grains avoid random substitutions and tiny masonry grids.
        tx, ty, tz = (x, y, z) if texture_position is None else texture_position
        grain = (int(tx * 4) * 37 ^ int(ty * 4) * 19 ^ int(tz * 4) * 7) & 7
        texture = 0.90 + grain * 0.025
        if material in (WOOD, BRIDGE, CRATE):
            texture = 0.70 if (tx * 0.19 + ty * 1.3 + tz * 0.13) % 1 < 0.055 else texture
        elif material in (STONE, FLOOR):
            texture = 0.76 if (tz * 1.35 + tx * 0.03) % 1 < 0.055 else texture
        elif material == METAL:
            light += directional ** 8 * 0.22
        brightness = ALBEDO[material] * texture * light / (1 + max(0.0, distance) * 0.029)
        for index, source in enumerate(self.lights):
            dx, dy, dz = source[0] - x, source[1] - y, source[2] - z
            square = dx * dx + dy * dy + dz * dz
            if not 0.0001 < square < 36:
                continue
            facing = max(0.0, (nx * dx + ny * dy + nz * dz) / math.sqrt(square))
            if facing <= 0:
                continue
            # Nearby points may be on opposite sides of thin masonry. Reuse
            # only the exact same surface ray, including its normal offset.
            key = index, x, y, z, nx, ny, nz
            visible = self._visibility.get(key)
            if visible is None:
                if len(self._visibility) >= self.MAX_SHADOW_SAMPLES:
                    continue
                # Offset out of the shaded surface; use the shared exact LOS.
                start = (x + nx * 0.015, y + ny * 0.015, z + nz * 0.015)
                length = math.dist(start, source)
                direction = tuple((source[i] - start[i]) / length for i in range(3))
                visible = self.world.line_clear(start, direction, length)
                self._visibility[key] = visible
            if visible:
                brightness += facing * (1 - square / 36) * 0.55
        brightness = min(1.0, max(emission, brightness))
        level = max(1, min(15, int(brightness * 15 + 0.5)))
        if glyph is None:
            glyph = RAMP[min(len(RAMP) - 1, max(0, int(brightness * (len(RAMP) - 1))))]
        return ink(glyph, level, material)


DEFAULT_SHADING = Shading()

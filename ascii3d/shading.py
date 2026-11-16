"""Shared, world-anchored ASCII materials and foreground luminance.

Ink tokens are cached strings: compositors move their semantic material/tone
with the winning glyph, without allocating an object for each scene cell.
Plain text consumers still receive ordinary characters when joining rows.
"""

from functools import lru_cache
import math

from .world import BRIDGE, CRATE, FLOOR, GRASS, LEAVES, METAL, PATH, STONE, WATER, WOOD
from .palette import ARCANE, ASH, BONE, DUST, EMBER, FIRE, STRAW


RAMP = "..,:;irsxXA#%@"
MIN_SURFACE_LEVEL = 4
ALBEDO = (0.0, 0.72, 0.64, 0.85, 0.59, 0.58, 0.74, 0.58, 0.54, 0.61, 0.64,
          1.0, 0.80, 0.90, 0.67, 0.90, 0.95, 0.95, 0.95, 0.70, 0.80, 0.65)


class Ink(str):
    """A reusable glyph carrying its foreground level and source material."""

    __slots__ = ("level", "material", "effects")

    def __new__(cls, glyph: str, level: int, material: int, effects: int = 0):
        value = super().__new__(cls, glyph)
        value.level, value.material = level, material
        value.effects = effects
        return value


@lru_cache(maxsize=16384)
def ink(glyph: str, level: int, material: int = STONE, effects: int = 0) -> Ink:
    return Ink(glyph, max(0, min(15, level)), material, effects)


class Shading:
    """Bounded material lighting; visibility queries never change simulation."""

    MAX_LIGHTS = 2
    MAX_SHADOW_SAMPLES = 256

    def __init__(self, world=None):
        self.world = world
        self.lights = ()
        self._visibility = {}
        self.eye = None

    def prepare(self, player, seconds=0.0):
        self._visibility.clear()
        self.eye = (player.x, player.y, player.eye_z)
        if self.world is None:
            self.lights = ()
            return
        balls = sorted(self.world.combat.fireballs,
                       key=lambda ball: (ball.x - player.x) ** 2 + (ball.y - player.y) ** 2)
        self.lights = tuple((ball.x, ball.y, ball.z) for ball in balls[:self.MAX_LIGHTS])

    def surface(self, material, x, y, z, normal, distance, *, glyph=None, emission=0.0,
                texture_position=None, texture_normal=None):
        nx, ny, nz = normal
        directional = max(0.0, -nx * 0.38 - ny * 0.48 + nz * 0.79)
        emissive = material in (FIRE, EMBER, ARCANE)
        # Shadow-facing surfaces need enough fill light to retain texture and
        # character density; authored luminous shells keep their edge/core range.
        light = 0.10 + directional * 0.90 if emissive else 0.30 + directional * 0.70
        # Broad stains establish form before fine grain. Both remain anchored
        # to world coordinates or the caller's moving object-local coordinates.
        tx, ty, tz = (x, y, z) if texture_position is None else texture_position
        normal_texture = normal if texture_normal is None else texture_normal
        ax, ay, az = abs(normal_texture[0]), abs(normal_texture[1]), abs(normal_texture[2])
        a, b = (ty, tz) if ax > ay and ax > az else ((tx, tz) if ay > az else (tx, ty))
        broad = math.sin(tx * 0.83 + ty * 0.57 + tz * 0.39)
        fine = (math.sin(tx * 5.31 - ty * 3.17 + tz * 7.07)
                if material not in (WOOD, BRIDGE, CRATE, PATH, STRAW) else 0.0)
        grain = (int(tx * 11) * 37 ^ int(ty * 11) * 19 ^ int(tz * 11) * 7) & 15
        texture = 0.78 + broad * 0.27 + fine * 0.11
        if material in (WOOD, BRIDGE, CRATE):
            fiber = math.sin(a * 17.0 + math.sin(b * 0.93) * 0.45)
            texture = 0.78 + broad * 0.26
            if fiber > 0.87:
                texture *= 0.28
            elif fiber < -0.93:
                texture += 0.15
            if (b * 0.48) % 1 < 0.025:
                texture *= 0.48
            if material == CRATE:
                u, v = a % 1, b % 1
                if min(u, 1 - u, v, 1 - v) < 0.075 or abs(u - v) < 0.045:
                    texture += 0.35
        elif material in (STONE, FLOOR):
            course = b * 0.85 + math.sin(a * 0.41) * 0.045
            joint = (a * 0.70 + (int(course) & 1) * 0.50) % 1
            seam = course % 1
            texture = 0.78 + broad * 0.31 + fine * 0.13
            if material == FLOOR:
                joint, seam = (a * 0.50) % 1, (b * 0.50) % 1
            if seam < 0.04 or joint < 0.026:
                texture *= 0.24
            elif seam > 0.955 or joint > 0.965:
                texture += 0.24
            if grain == 0:
                texture *= 0.55
        elif material == PATH:
            texture = 0.70 + broad * 0.24 + grain * 0.022
            if grain < 2:
                texture *= 0.42
        elif material in (GRASS, LEAVES):
            texture = 0.80 + broad * 0.24 + fine * 0.10 + grain * 0.008
        elif material == STRAW:
            strand = math.sin(a * 23 + b * 1.7)
            texture = 0.77 + broad * 0.22 + strand * 0.16
            if strand > 0.92:
                texture *= 0.40
        elif material == BONE:
            texture = 0.85 + broad * 0.13 + fine * 0.08
            if abs(math.sin(a * 9 + b * 5)) < 0.045:
                texture *= 0.42
        elif material == METAL:
            texture = 0.89 + fine * 0.10
            if (a * 13 + b * 0.11) % 1 < 0.035:
                texture *= 0.46
        # Reflective highlights move with the view instead of being painted
        # uniformly over a whole face. Rough materials avoid this extra work.
        if material in (METAL, WATER):
            if self.eye is not None:
                vx, vy, vz = self.eye[0] - x, self.eye[1] - y, self.eye[2] - z
                length = math.sqrt(vx * vx + vy * vy + vz * vz)
                if length > 1e-10:
                    hx, hy, hz = vx / length - 0.38, vy / length - 0.48, vz / length + 0.79
                    half_length = math.sqrt(hx * hx + hy * hy + hz * hz)
                    if half_length > 1e-10:
                        specular = max(0.0, (nx * hx + ny * hy + nz * hz) / half_length)
                        light += specular ** (24 if material == METAL else 40) * 0.72
            else:
                light += directional ** 12 * 0.30
        albedo = ALBEDO[material] if 0 <= material < len(ALBEDO) else 0.65
        brightness = albedo * max(0.08, texture) * light * 1.52 / (1 + max(0.0, distance) * 0.036)
        warmth = 0.0
        # Emissive shells carry their authored edge/core intensity. Lighting
        # them from their own source erases that gradient and wastes shadow rays.
        lights = () if emission > 0 and material in (FIRE, EMBER, ARCANE) else self.lights
        for index, source in enumerate(lights):
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
                if length <= 1e-10:
                    visible = True
                else:
                    direction = tuple((source[i] - start[i]) / length for i in range(3))
                    visible = self.world.line_clear(start, direction, length)
                self._visibility[key] = visible
            if visible:
                # The same material relief modulates local diffuse light;
                # firelight must not wash a dark crack into a flat bright face.
                contribution = facing * (1 - square / 36) * 0.90 * albedo * max(0.08, texture)
                brightness += contribution
                warmth += contribution
        brightness = min(1.0, max(emission, brightness))
        if not emissive:
            # Raise the full surface range before selecting BOTH ink and glyph.
            # Brighter RGB alone still leaves shaded walls as almost empty dots.
            brightness = 0.24 + brightness * 0.76
        level = max(1, min(15, int(brightness * 15 + 0.5)))
        if glyph is None:
            glyph = RAMP[min(len(RAMP) - 1, max(0, int(brightness * (len(RAMP) - 1))))]
        # Explicit depth and light metadata travel with the depth-test winner.
        # These bands only affect foreground color; they never change geometry.
        fog = 0 if distance < 12 else 1 if distance < 24 else 2 if distance < 36 else 3
        warm = 0 if warmth < 0.08 else 1 if warmth < 0.22 else 2 if warmth < 0.40 else 3
        return ink(glyph, level, material, (fog << 2) | warm)


DEFAULT_SHADING = Shading()

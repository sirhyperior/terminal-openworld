"""Shared, world-anchored ASCII materials and foreground luminance.

Ink tokens are cached strings: compositors move their semantic material/tone
with the winning glyph, without allocating an object for each scene cell.
Plain text consumers still receive ordinary characters when joining rows.
"""

from array import array
from functools import lru_cache
import math

from .world import BRIDGE, CRATE, FLOOR, GRASS, LEAVES, METAL, PATH, STONE, WATER, WOOD
from .palette import ARCANE, BONE, EMBER, FIRE, STRAW, WIND_GRASS, WIND_LEAVES


RAMP = "..,:;irsxXA#%@"
_RAMP_MAX = len(RAMP) - 1
MIN_SURFACE_LEVEL = 4
ALBEDO = (0.0, 0.72, 0.64, 0.85, 0.59, 0.58, 0.74, 0.58, 0.54, 0.61, 0.64,
          1.0, 0.80, 0.90, 0.67, 0.90, 0.95, 0.95, 0.95, 0.70, 0.80, 0.65)
_ALBEDO_COUNT = len(ALBEDO)
_TEXTURE_AXES = frozenset((STONE, FLOOR, WOOD, BRIDGE, CRATE, STRAW, BONE, METAL))
_TEXTURE_GRAIN = frozenset((STONE, FLOOR, GRASS, LEAVES, PATH))
GRASS_GLYPHS = (".,", ",;", ';"', "\"'")


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


def grass_ink(tone, x, y, turn):
    noise = (int(x * 6.0) * 73856093 ^ int(y * 6.0) * 19349663) & 15
    wind = int((turn + 0.6) * 3)
    glyph = GRASS_GLYPHS[min(3, tone.level // 3)][(noise + wind) % 2]
    return ink(glyph, tone.level, tone.material, tone.effects)


class VoxelMoonlight:
    """First opaque voxel seen from the western sky along (-1, 0, 1).

    Along each light ray, y and x + z are constant. A unit voxel projects
    onto two adjacent x + z intervals. In the first its front is the west
    face; in the second its front is the top. Within each interval these
    faces always sort in the same order, so one integer stores the exact
    first face for every point in the interval, including window openings.
    """

    def __init__(self, world):
        self.span = world.width + world.height
        self.depth = world.depth
        self.faces = array("I", [0xffffffff]) * (self.span * self.depth)
        faces = memoryview(self.faces)
        self.rows = [faces[y * self.span:(y + 1) * self.span] for y in range(self.depth)]

    def add(self, x, y, z):
        row = self.rows[y]
        band, west = x + z, 2 * x
        if west < row[band]:
            row[band] = west
        if west + 1 < row[band + 1]:
            row[band + 1] = west + 1

    def blocked(self, x, y, z):
        diagonal = x + z
        if not (0 <= y < self.depth and 0 <= diagonal < self.span):
            return False
        band = int(diagonal)
        face = self.rows[int(y)][band]
        entry_x = (face >> 1) + (diagonal - band if face & 1 else 0)
        return x > entry_x + 1e-6


class Shading:
    """Bounded material lighting; visibility queries never change simulation."""

    MAX_LIGHTS = 2
    MAX_SHADOW_SAMPLES = 256

    def __init__(self, world=None):
        self.world = world
        self.moonlight = None
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
                texture_position=None, texture_normal=None, foliage_turn=None):
        nx, ny, nz = normal
        directional = -nx * 0.38 - ny * 0.48 + nz * 0.79
        if not directional > 0.0:
            directional = 0.0
        emissive = material in (FIRE, EMBER, ARCANE)
        # Shadow-facing surfaces need enough fill light to retain texture and
        # character density; authored luminous shells keep their edge/core range.
        light = 0.10 + directional * 0.90 if emissive else 0.30 + directional * 0.70
        # Broad stains establish form before fine grain. Both remain anchored
        # to world coordinates or the caller's moving object-local coordinates.
        if texture_position is None:
            tx, ty, tz = x, y, z
        else:
            tx, ty, tz = texture_position
        if material in _TEXTURE_AXES:
            normal_texture = normal if texture_normal is None else texture_normal
            ax, ay, az = abs(normal_texture[0]), abs(normal_texture[1]), abs(normal_texture[2])
            a, b = (ty, tz) if ax > ay and ax > az else ((tx, tz) if ay > az else (tx, ty))
        broad = math.sin(tx * 0.83 + ty * 0.57 + tz * 0.39)
        fine = (math.sin(tx * 5.31 - ty * 3.17 + tz * 7.07)
                if material not in (WOOD, BRIDGE, CRATE, PATH, STRAW) else 0.0)
        if material in _TEXTURE_GRAIN:
            grain = (int(tx * 11) * 37 ^ int(ty * 11) * 19 ^ int(tz * 11) * 7) & 15
        pigment = material
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
            if material == FLOOR:
                joint, seam = (a * 0.50) % 1, (b * 0.50) % 1
            else:
                course = b * 0.85 + math.sin(a * 0.41) * 0.045
                joint = (a * 0.70 + (int(course) & 1) * 0.50) % 1
                seam = course % 1
            texture = 0.78 + broad * 0.31 + fine * 0.13
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
            if foliage_turn is not None:
                # A gust turns the exposed side of leaf clusters into the
                # light first. Their attached texture breaks up the moving
                # edge while the underlying form and shadow rays stay fixed.
                exposure = foliage_turn + broad * 0.17 - nx * 0.19 + nz * 0.16 - 0.47
                texture += max(-0.08, min(0.22, exposure * 0.38))
                if exposure > 0:
                    pigment = WIND_GRASS if material == GRASS else WIND_LEAVES
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
        else:
            texture = 0.78 + broad * 0.27 + fine * 0.11
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
        # Sample outside the receiver to keep a lit roof or wall from
        # shadowing its own front face. Sky fill keeps sheltered routes legible.
        if (self.moonlight is not None and not emissive
                and self.moonlight.blocked(x + nx * 1e-5, y + ny * 1e-5, z + nz * 1e-5)):
            light = 0.24 + (light - 0.24) * 0.42
        albedo = ALBEDO[material] if 0 <= material < _ALBEDO_COUNT else 0.65
        texture = texture if texture > 0.08 else 0.08
        depth = distance if distance > 0.0 else 0.0
        brightness = albedo * texture * light * 1.52 / (1 + depth * 0.036)
        firelight = 0.0
        # Emissive shells carry their authored edge/core intensity. Lighting
        # them from their own source erases that gradient and wastes shadow rays.
        lights = self.lights
        if lights and not (emission > 0 and emissive):
            brightness, firelight = self._illuminate(
                x, y, z, nx, ny, nz, albedo, texture, brightness, lights)
        # All diffuse contributions are nonnegative. The upper bound also
        # keeps the rounded foreground level and glyph index in their ranges.
        brightness = brightness if brightness > emission else emission
        if not brightness < 1.0:
            brightness = 1.0
        if not emissive:
            # Raise the full surface range before selecting BOTH ink and glyph.
            # Brighter RGB alone still leaves shaded walls as almost empty dots.
            brightness = 0.24 + brightness * 0.76
        level = int(brightness * 15 + 0.5) or 1
        if glyph is None:
            glyph = RAMP[int(brightness * _RAMP_MAX)]
        # Explicit depth and light metadata travel with the depth-test winner.
        # These bands only affect foreground color; they never change geometry.
        fog = 0 if distance < 12 else 1 if distance < 24 else 2 if distance < 36 else 3
        glow = 0 if firelight < 0.08 else 1 if firelight < 0.22 else 2 if firelight < 0.40 else 3
        return ink(glyph, level, pigment, (fog << 2) | glow)

    def _illuminate(self, x, y, z, nx, ny, nz, albedo, texture, brightness, lights):
        firelight = 0.0
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
                contribution = facing * (1 - square / 36) * 0.90 * albedo * texture
                brightness += contribution
                firelight += contribution
        return brightness, firelight


DEFAULT_SHADING = Shading()

"""Sparse, seeded world-space particles sharing the opaque scene depth buffer.

This is presentation only. Existing wind, pickup and fire events supply sound;
particle positions depend on simulation time and never advance gameplay state.
"""

from collections import OrderedDict
import math

from .combat import BURST_DURATION, FIREBALL_RANGE, MAX_FIREBALLS
from .geometry import Camera
from .palette import ARCANE, ASH, DUST, EMBER, FIRE, UI, UI_ACCENT, UI_DANGER, UI_MUTED, UI_POSITIVE
from .shading import Ink, ink


_UI_MATERIALS = frozenset((UI, UI_ACCENT, UI_DANGER, UI_POSITIVE, UI_MUTED))


def _seed(x: int, y: int, z: int, slot: int) -> int:
    value = (x * 73856093 ^ y * 19349663 ^ z * 83492791 ^ slot * 2654435761) & 0xFFFFFFFF
    value ^= value >> 16
    value = value * 2246822519 & 0xFFFFFFFF
    return value ^ (value >> 13)


class Particles:
    """A small analytic field and bounded trails; no whole-world allocation."""

    CHUNK = 6
    VERTICAL_CHUNK = 4
    MOTES_PER_CHUNK = 6
    EYE_MOTES_PER_CHUNK = 24
    EYE_BAND_HALF_HEIGHT = 1.25
    MAX_CHUNKS = 64
    MAX_CANDIDATES = 256
    MAX_AMBIENT_CANDIDATES = 96
    MAX_AMBIENT_SAMPLES = 256
    MAX_AMBIENT_GLINTS = 2
    MAX_DRAWS = 128
    MAX_PICKUP_SOURCES = 16
    AMBIENT_RADIUS = 18.0
    EFFECT_RADIUS = 28.0

    def __init__(self, world):
        self.world = world
        self.enabled = True
        self._chunks = OrderedDict()
        self.stats = {}

    def _chunk(self, cx, cy, cz):
        key = cx, cy, cz
        values = self._chunks.get(key)
        if values is not None:
            self._chunks.move_to_end(key)
            return values
        values = []
        for slot in range(self.MOTES_PER_CHUNK + self.EYE_MOTES_PER_CHUNK):
            value = _seed(cx, cy, cz, slot)
            x = (cx + 0.12 + (value & 1023) / 1023 * 0.76) * self.CHUNK
            y = (cy + 0.12 + ((value >> 10) & 1023) / 1023 * 0.76) * self.CHUNK
            z = (cz + 0.12 + ((value >> 20) & 1023) / 1023 * 0.76) * self.VERTICAL_CHUNK
            phase = (value % 8191) / 8191 * math.tau
            values.append((x, y, z, phase, value))
        values = tuple(values)
        self._chunks[key] = values
        while len(self._chunks) > self.MAX_CHUNKS:
            self._chunks.popitem(last=False)
        return values

    @staticmethod
    def _visible_source(camera, x, y, z, radius):
        dx, dy, dz = x - camera.x, y - camera.y, z - camera.z
        along = dx * camera.cy + dy * camera.sy
        depth = along * camera.cp + dz * camera.sp
        right = dx * camera.sy - dy * camera.cy
        up = -along * camera.sp + dz * camera.cp
        return (depth + radius >= camera.NEAR and depth - radius <= Particles.EFFECT_RADIUS
                and abs(right) <= max(0.0, depth) * camera.width / (2 * camera.fx) + radius
                and abs(up) <= max(0.0, depth) * camera.height / (2 * camera.fy) + radius)

    def draw(self, pixels, depths, player, time_seconds, focal, aspect, *, wind_at=None):
        """Composite points without changing any opaque depth or world state.

        Ambient dust is restricted to authored environments. Generic geometry
        fixtures remain clear unless a visible existing effect emits particles.
        """
        height = len(pixels)
        width = len(pixels[0]) if height else 0
        cells = width * height
        budget = min(self.MAX_CANDIDATES, max(24, cells // 18)) if cells else 0
        draw_budget = min(self.MAX_DRAWS, max(12, cells // 60)) if cells else 0
        ambient_budget = min(self.MAX_AMBIENT_CANDIDATES, max(12, cells // 64)) if cells else 0
        sample_budget = min(self.MAX_AMBIENT_SAMPLES, max(48, cells // 18)) if cells else 0
        stats = dict(particle_budget=budget, particle_candidates=0, particle_draw_budget=draw_budget,
                     particles_drawn=0, ambient_candidates=0, dynamic_candidates=0,
                     ambient_samples=0, ambient_sample_budget=sample_budget,
                     ambient_glint_candidates=0, ambient_glints=0,
                     particle_sources=0, particle_chunks=len(self._chunks), particle_occluded=0,
                     particle_protected=0)
        self.stats = stats
        if not self.enabled or not cells:
            return
        camera = Camera(player, width, height, focal, aspect)
        projected = []

        def emit(x, y, z, material, level, glyph, kind, limit, projected_point=None):
            if stats['particle_candidates'] >= budget:
                return False
            stats['particle_candidates'] += 1
            stats[kind + '_candidates'] += 1
            if not (0 <= x < self.world.width and 0 <= y < self.world.depth
                    and 0 <= z < self.world.height):
                return True
            point = camera.project(x, y, z) if projected_point is None else projected_point
            if point is None or point[2] > limit:
                return True
            px, py, depth = point
            column, row = round(px), round(py)
            if 0 <= column < width and 0 <= row < height:
                # The slight fade avoids a wall of equally bright screen dots.
                level = max(1, min(15, level - int(depth / (8 if kind == 'ambient' else 16))))
                fog = 0 if depth < 12 else 1 if depth < 24 else 2 if depth < 36 else 3
                projected.append((depth, row, column, material, level, glyph, fog << 2))
            return True

        seconds = float(time_seconds)
        combat = self.world.combat
        # Bright sources have first claim on the work budget. Each source is
        # tested before generating local detail; invisible effects stay cheap.
        for ball in combat.fireballs[:MAX_FIREBALLS]:
            if not self._visible_source(camera, ball.x, ball.y, ball.z, 1.3):
                continue
            stats['particle_sources'] += 1
            dx, dy, dz = ball.direction
            travel = FIREBALL_RANGE - ball.range_left
            origin = (round((ball.x - dx * travel) * 256),
                      round((ball.y - dy * travel) * 256),
                      round((ball.z - dz * travel) * 256))
            phase_start = _seed(*origin, 0) % 8191 / 8191 * math.tau
            for index in range(10):
                phase = phase_start + index * 2.399963229728653
                age = (seconds * 2.3 + index / 10) % 1.0
                behind = 0.18 + age * 1.05
                spread = 0.035 + age * 0.16
                x = ball.x - dx * behind + math.cos(phase) * spread
                y = ball.y - dy * behind + math.sin(phase) * spread
                z = ball.z - dz * behind + math.sin(phase * 1.7) * spread - age * age * 0.30
                if not emit(x, y, z, EMBER, 13 - int(age * 12), "." if age > 0.3 else "'",
                            'dynamic', self.EFFECT_RADIUS):
                    break

        for burst in combat.bursts[:MAX_FIREBALLS]:
            if not self._visible_source(camera, burst.x, burst.y, burst.z, 1.2):
                continue
            stats['particle_sources'] += 1
            progress = max(0.0, min(1.0, 1 - burst.remaining / BURST_DURATION))
            age = progress * 0.42
            phase_start = _seed(round(burst.x * 256), round(burst.y * 256), round(burst.z * 256), 0) % 8191 / 8191 * math.tau
            for index in range(12):
                phase = index * 2.399963229728653 + phase_start
                speed = 1.2 + (index % 5) * 0.35
                x = burst.x + math.cos(phase) * speed * age
                y = burst.y + math.sin(phase) * speed * age
                z = burst.z + (0.2 + index % 4 * 0.35) * age - age * age * 1.8
                if not emit(x, y, z, FIRE if progress < 0.2 else EMBER,
                            15 - int(progress * 10), "*" if progress < 0.25 else ".",
                            'dynamic', self.EFFECT_RADIUS):
                    break

        for pickup in combat.pickups[:self.MAX_PICKUP_SOURCES]:
            if pickup.collected or not self._visible_source(camera, pickup.x, pickup.y, pickup.z + 0.9, 0.5):
                continue
            stats['particle_sources'] += 1
            for index in range(3):
                phase = seconds * 0.75 + index * math.tau / 3 + pickup.x * 0.17 + pickup.y * 0.31
                age = (seconds * 0.18 + index / 3) % 1.0
                x = pickup.x + math.cos(phase) * 0.19
                y = pickup.y + math.sin(phase) * 0.19
                z = pickup.z + 0.35 + age
                level = 3 + int(math.sin(math.pi * age) * 8)
                if not emit(x, y, z, ARCANE, level, ".", 'dynamic', 16):
                    break

        if self.world.outdoor_bounds is not None and stats['particle_candidates'] < budget:
            cx, cy, cz = (math.floor(player.x / self.CHUNK), math.floor(player.y / self.CHUNK),
                          math.floor(player.eye_z / self.VERTICAL_CHUNK))
            nearby = []
            for z in range(cz - 1, cz + 2):
                for y in range(cy - 2, cy + 3):
                    for x in range(cx - 2, cx + 3):
                        px, py, pz = (x + 0.5) * self.CHUNK, (y + 0.5) * self.CHUNK, (z + 0.5) * self.VERTICAL_CHUNK
                        if self._visible_source(camera, px, py, pz, 4.8):
                            along = (px - player.x) * camera.cy + (py - player.y) * camera.sy
                            square = ((px - player.x) ** 2 + (py - player.y) ** 2
                                      + 4 * (pz - player.eye_z) ** 2 + max(0, -along) * 36)
                            nearby.append((square, x, y, z))
            nearby.sort()
            for _, x, y, z in nearby:
                if (stats['ambient_candidates'] >= ambient_budget or stats['particle_candidates'] >= budget
                        or stats['ambient_samples'] >= sample_budget):
                    break
                # The same local gust that rolls the canopy carries a loose
                # group of ash flakes. Quieter dust hangs closer to its home.
                wind_x, wind_y = ((0, 0) if wind_at is None else
                                  wind_at((x + 0.5) * self.CHUNK, (y + 0.5) * self.CHUNK))
                for slot, (px, py, pz, phase, value) in enumerate(self._chunk(x, y, z)):
                    if (stats['ambient_candidates'] >= ambient_budget
                            or stats['ambient_samples'] >= sample_budget):
                        break
                    stats['ambient_samples'] += 1
                    extra = slot >= self.MOTES_PER_CHUNK
                    if extra and abs(pz - player.eye_z) > self.EYE_BAND_HALF_HEIGHT + 0.26:
                        continue
                    eddy = phase + seconds * 0.26
                    roll = math.sin(eddy)
                    lift = roll * 0.26
                    # Prefer a denser set of fixed world motes near eye height.
                    # Moving the camera changes selection, never positions;
                    # the unchanged work budget keeps the wider field sparse.
                    if extra and abs(pz + lift - player.eye_z) > self.EYE_BAND_HALF_HEIGHT:
                        continue
                    material = ASH if value % 4 == 0 else DUST
                    drift = 0.78 if material == ASH else 0.28
                    wx = wind_x * drift + math.cos(eddy) * 0.13
                    wy = wind_y * drift + roll * 0.10
                    px, py, pz = px + wx, py + wy, pz + lift
                    point = camera.project(px, py, pz)
                    if point is None or point[2] > self.AMBIENT_RADIUS:
                        continue
                    column, row = round(point[0]), round(point[1])
                    if not (0 <= column < width and 0 <= row < height):
                        continue
                    if point[2] >= depths[row][column] - 0.015:
                        stats['particle_occluded'] += 1
                        continue
                    # Preserve the dark field. Rare, short glints catch wind
                    # on rising ash; ordinary bodies never share their peak.
                    level = 4 + value % 3
                    glyph = "'" if material == ASH else "."
                    if material == ASH:
                        level += max(0, min(3, round((wind_x + wind_y * 0.6) * 4)))
                        if (roll > 0.7 and point[2] < 12
                                and stats['ambient_glint_candidates'] < self.MAX_AMBIENT_GLINTS):
                            strength = min(1, math.hypot(wind_x, wind_y))
                            if strength > 0.25 and math.sin(phase + seconds * 2.6) > 0.97:
                                glyph = "*"
                                # Compensate the standard fade only for this
                                # tiny accent, leaving steady haze subdued.
                                level = 14 + ((value >> 2) & 1) + int(point[2] / 8)
                                stats['ambient_glint_candidates'] += 1
                    if not emit(px, py, pz, material, level, glyph,
                                'ambient', self.AMBIENT_RADIUS, point):
                        break

        # Nearest first plus a cell stamp keeps distant points from painting
        # over closer particles. Never write their depths into the solid buffer.
        projected.sort(key=lambda point: point[0])
        stamped = set()
        for depth, row, column, material, level, glyph, effects in projected:
            if stats['particles_drawn'] >= draw_budget:
                break
            cell = row, column
            if cell in stamped:
                continue
            if depth >= depths[row][column] - 0.015:
                stats['particle_occluded'] += 1
                continue
            old = pixels[row][column]
            if ((not isinstance(old, Ink) and old != ' ')
                    or (isinstance(old, Ink) and old.material in _UI_MATERIALS)):
                stats['particle_protected'] += 1
                continue
            if (isinstance(old, Ink) and old.material in (FIRE, ARCANE)
                    and (material in (ASH, DUST) or old.level >= level)):
                continue
            pixels[row][column] = ink(glyph, level, material, effects)
            stamped.add(cell)
            stats['particles_drawn'] += 1
            if material == ASH and glyph == "*":
                stats['ambient_glints'] += 1
        stats['particle_chunks'] = len(self._chunks)

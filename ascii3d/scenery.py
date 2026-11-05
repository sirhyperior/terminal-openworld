"""Seeded grass geometry and a continuous wind field with local, drifting gusts."""

from dataclasses import dataclass
import math
import random

from .player import Player
from .geometry import Camera
from .trees import Trees
from .world import AIR, GRASS, World


@dataclass(frozen=True, slots=True)
class Gust:
    x: float
    y: float
    radius: float
    strength: float
    dx: float
    dy: float


class Wind:
    def __init__(self, bounds: tuple[int, int, int, int]):
        self.bounds = bounds

    def gusts(self, seconds: float) -> list[Gust]:
        """Overlapping gusts rise/fall smoothly, then respawn at new seeded points."""
        x0, y0, x1, y1 = self.bounds
        gusts = []
        for slot in range(6):
            duration = 4.8 + slot * 0.61
            cycle = (seconds + slot * 2.31) / duration
            epoch, age = math.floor(cycle), cycle % 1.0
            rng = random.Random(17389 + slot * 100003 + epoch * 7919)
            x = rng.uniform(x0, x1) + (age - 0.5) * 6.0
            y = rng.uniform(y0, y1) + (age - 0.5) * 2.5
            radius = rng.uniform(4.0, 8.5)
            strength = rng.uniform(0.55, 1.15) * math.sin(math.pi * age) ** 2
            angle = rng.uniform(-1.0, 1.0)
            gusts.append(Gust(x, y, radius, strength, math.cos(angle), math.sin(angle)))
        return gusts

    @staticmethod
    def sample(x: float, y: float, seconds: float, gusts: list[Gust]) -> tuple[float, float]:
        # Traveling waves keep neighboring tufts coherent between stronger gusts.
        sweep = math.sin(x * 0.55 + y * 0.37 - seconds * 2.9)
        dx = 0.16 + 0.32 * sweep
        dy = 0.22 * math.sin(y * 0.49 - x * 0.28 - seconds * 2.3)
        for gust in gusts:
            distance_squared = (x - gust.x) ** 2 + (y - gust.y) ** 2
            falloff = 1.0 - distance_squared / (gust.radius * gust.radius)
            if falloff > 0:
                force = falloff * falloff * gust.strength
                dx += force * gust.dx
                dy += force * gust.dy
        return dx, dy


@dataclass(frozen=True, slots=True)
class Blade:
    x: float
    y: float
    height: float
    phase: float


class Scenery:
    CHUNK = 4
    DETAIL_RADIUS = 14

    def __init__(self, world: World):
        self.wind = Wind(world.outdoor_bounds) if world.outdoor_bounds else None
        self.trees = Trees(world)
        self.blades: list[Blade] = []
        self._indexed_blades = None
        self._chunks = {}
        self._seconds = None
        self._gusts = []
        self._wind_cache = {}
        self.stats = {}
        if not world.outdoor_bounds:
            return
        rng = random.Random(58431)
        x0, y0, x1, y1 = world.outdoor_bounds
        for y in range(y0, y1):
            for x in range(x0, x1):
                if world.get(x, y, 0) != GRASS or world.get(x, y, 1) != AIR:
                    continue
                positions = [(a, b) for a in range(4) for b in range(4)]
                rng.shuffle(positions)
                tree = world.trees.get((x, y))
                for a, b in positions:
                    bx, by = x + (a + rng.uniform(0.15, 0.85)) / 4, y + (b + rng.uniform(0.15, 0.85)) / 4
                    if tree and (bx - tree.x) ** 2 + (by - tree.y) ** 2 < (tree.radius + 0.03) ** 2:
                        continue
                    self.blades.append(Blade(bx, by, rng.uniform(0.09, 0.24), rng.uniform(0, math.tau)))
        self._index()

    def _index(self):
        patches = {}
        for blade in self.blades:
            patches.setdefault((int(blade.x), int(blade.y)), []).append(blade)
        chunks = {}
        for (x, y), blades in patches.items():
            chunks.setdefault((x // self.CHUNK, y // self.CHUNK), []).append((x, y, blades))
        self._chunks, self._indexed_blades = chunks, self.blades

    def prepare(self, seconds):
        if self._indexed_blades is not self.blades:
            self._index()
        if seconds != self._seconds:
            self._seconds = seconds
            self._gusts = self.wind.gusts(seconds) if self.wind else []
            self._wind_cache.clear()

    def wind_at(self, x, y):
        cell = (int(x), int(y))
        value = self._wind_cache.get(cell)
        if value is None:
            value = self.wind.sample(cell[0] + 0.5, cell[1] + 0.5, self._seconds, self._gusts) if self.wind else (0, 0)
            self._wind_cache[cell] = value
        return value

    def draw(self, pixels: list[list[str]], depths: list[list[float]], player: Player,
             seconds: float, focal: float, aspect: float) -> None:
        width, height = len(pixels[0]), len(pixels)
        self.prepare(seconds)
        cam = Camera(player, width, height, focal, aspect)
        budget = max(96, width * height // 3)
        self.stats = {"grass_budget": budget, "grass_candidates": 0, "grass_drawn": 0,
                      "grass_chunks": 0, "tree_samples": 0}
        self.trees.draw(pixels, depths, cam, self.stats)
        if not self.wind:
            return
        chunks = []
        cx, cy = int(player.x) // self.CHUNK, int(player.y) // self.CHUNK
        for y in range(cy - 4, cy + 5):
            for x in range(cx - 4, cx + 5):
                patches = self._chunks.get((x, y))
                if not patches:
                    continue
                dx, dy = (x + 0.5) * self.CHUNK - player.x, (y + 0.5) * self.CHUNK - player.y
                along = dx * cam.cy + dy * cam.sy
                right = dx * cam.sy - dy * cam.cy
                if -3 < along < self.DETAIL_RADIUS + 3 and abs(right) < max(0, along) + 4:
                    chunks.append((dx * dx + dy * dy, patches))
        chunks.sort(key=lambda item: item[0])
        self.stats["grass_chunks"] = len(chunks)
        project, stroke = cam.project, cam.stroke
        for _, patches in chunks:
            for x, y, blades in patches:
                dx, dy = x + 0.5 - player.x, y + 0.5 - player.y
                along, right = dx * cam.cy + dy * cam.sy, dx * cam.sy - dy * cam.cy
                if along < 0.05 or along > self.DETAIL_RADIUS or abs(right) > along + 1:
                    continue
                root = project(x + 0.5, y + 0.5, 1.02)
                if root is None or root[1] < -4 or root[1] > height + 10 or root[0] < -8 or root[0] > width + 8:
                    continue
                count = 16 if along < 3 else (8 if along < 6 else (4 if along < 9 else 2))
                wx, wy = self.wind_at(x, y)
                # Nearby moving feet push the blades away, then release them
                # naturally as the smooth influence radius leaves the patch.
                distance_squared = dx * dx + dy * dy
                if player.moving and 0.02 < distance_squared < 3.24:
                    force = (1 - distance_squared / 3.24) ** 2 * (2.2 if player.running else 1.4)
                    wx, wy = wx + dx * force, wy + dy * force
                for blade in blades[:count]:
                    if self.stats["grass_candidates"] >= budget:
                        return
                    self.stats["grass_candidates"] += 1
                    base = project(blade.x, blade.y, 1.015)
                    if base is None or base[1] > height + 8:
                        continue
                    # Roots behind an obstacle do not require detailed strokes.
                    bx, by = round(base[0]), round(base[1])
                    if 0 <= bx < width and 1 <= by < height:
                        if depths[by][bx] < base[2] - 0.5 and depths[by - 1][bx] < base[2] - 0.5:
                            continue
                    flutter = math.sin(seconds * 5.1 + blade.phase) * 0.15
                    vx, vy = wx + flutter, wy + flutter * 0.6
                    bend = min(1.2, math.hypot(vx, vy))
                    scale = blade.height * 0.9
                    tip = project(blade.x + vx * scale, blade.y + vy * scale,
                                  1.015 + blade.height * (1 - bend * 0.30))
                    if tip is not None and abs(tip[1] - base[1]) < 1.5:
                        drawn = stroke(pixels, depths, base, tip)
                    else:
                        mid = project(blade.x + vx * scale * 0.25, blade.y + vy * scale * 0.25,
                                      1.015 + blade.height * 0.55)
                        drawn = stroke(pixels, depths, base, mid)
                        drawn |= stroke(pixels, depths, mid, tip)
                    self.stats["grass_drawn"] += bool(drawn)

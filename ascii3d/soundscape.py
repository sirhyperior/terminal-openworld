"""Shared environmental audio sampling from the actual world, including rivers."""

import math

from .world import AIR, BRIDGE, GRASS, PATH, WATER


class Soundscape:
    CHUNK = 8
    RADIUS = 18

    def __init__(self, world):
        self.world = world
        self._revision = -1
        self._water_chunks = {}

    def at(self, x, y, yaw, feet=None):
        if self.world.revision != self._revision:
            chunks = {}
            for cy in range(self.world.depth):
                for cx in range(self.world.width):
                    if self.world.get(cx, cy, 0) == WATER:
                        chunks.setdefault((cx // self.CHUNK, cy // self.CHUNK), []).append((cx, cy))
            self._water_chunks = chunks
            self._revision = self.world.revision
        cx, cy = math.floor(x), math.floor(y)
        if feet is None:
            # Existing three-argument callers retain their flat-world material
            # classification and one-query cost. Live callers supply feet.
            ground = self.world.get(cx, cy, 0)
            outdoors = ground in (GRASS, WATER, BRIDGE, PATH)
        else:
            # Wind belongs to the listener's actual floor, not buried z=0.
            # A clear sky also exposes a timber balcony or stone roof walk.
            head = max(0, math.ceil(feet + 1.7))
            outdoors = not any(self.world.get(cx, cy, z) not in (AIR, WATER)
                               for z in range(head, self.world.height))
        wind = 0.18 if outdoors else 0.025
        nearest = math.inf
        total = direction_x = direction_y = 0.0
        # The river only influences an 18-unit neighborhood. Bucket queries
        # retain exact tile distances/weights without scanning the whole map.
        nearby = []
        for by in range(math.floor((y - self.RADIUS - 1) / self.CHUNK),
                        math.floor((y + self.RADIUS) / self.CHUNK) + 1):
            for bx in range(math.floor((x - self.RADIUS - 1) / self.CHUNK),
                            math.floor((x + self.RADIUS) / self.CHUNK) + 1):
                nearby.extend(self._water_chunks.get((bx, by), ()))
        nearby.sort(key=lambda tile: (tile[1], tile[0]))
        for cx, cy in nearby:
            dx = max(cx - x, 0.0, x - cx - 1)
            dy = max(cy - y, 0.0, y - cy - 1)
            distance_squared = dx * dx + dy * dy
            nearest = min(nearest, distance_squared)
            if distance_squared < self.RADIUS ** 2:
                weight = 1 / (1 + distance_squared)
                total += weight
                direction_x += (cx + 0.5 - x) * weight
                direction_y += (cy + 0.5 - y) * weight
        distance = math.sqrt(nearest)
        proximity = max(0.0, 1 - distance / self.RADIUS)
        river = 0.50 * proximity * proximity * (1.0 if outdoors else 0.12)
        pan = 0.0
        if total:
            dx, dy = direction_x / total, direction_y / total
            side = dx * math.sin(yaw) - dy * math.cos(yaw)
            pan = max(-0.55, min(0.55, side / max(6.0, math.hypot(dx, dy))))
        return wind, river, pan

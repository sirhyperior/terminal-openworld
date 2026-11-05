"""Shared environmental audio sampling from the actual world, including rivers."""

import math

from .world import BRIDGE, GRASS, PATH, WATER


class Soundscape:
    def __init__(self, world):
        self.world = world
        self._revision = -1
        self._water = []

    def at(self, x, y, yaw):
        if self.world.revision != self._revision:
            self._water = [(cx, cy) for cy in range(self.world.depth) for cx in range(self.world.width)
                           if self.world.get(cx, cy, 0) == WATER]
            self._revision = self.world.revision
        ground = self.world.get(math.floor(x), math.floor(y), 0)
        outdoors = ground in (GRASS, WATER, BRIDGE, PATH)
        wind = 0.18 if outdoors else 0.025
        nearest = math.inf
        total = direction_x = direction_y = 0.0
        for cx, cy in self._water:
            dx = max(cx - x, 0.0, x - cx - 1)
            dy = max(cy - y, 0.0, y - cy - 1)
            distance_squared = dx * dx + dy * dy
            nearest = min(nearest, distance_squared)
            if distance_squared < 18 ** 2:
                weight = 1 / (1 + distance_squared)
                total += weight
                direction_x += (cx + 0.5 - x) * weight
                direction_y += (cy + 0.5 - y) * weight
        distance = math.sqrt(nearest)
        proximity = max(0.0, 1 - distance / 18)
        river = 0.50 * proximity * proximity * (1.0 if outdoors else 0.12)
        pan = 0.0
        if total:
            dx, dy = direction_x / total, direction_y / total
            side = dx * math.sin(yaw) - dy * math.cos(yaw)
            pan = max(-0.55, min(0.55, side / max(6.0, math.hypot(dx, dy))))
        return wind, river, pan

"""Hinged doors: shared oriented panels for rendering and physical collision."""

from dataclasses import dataclass, field
import math

from .events import GameEvent


@dataclass(frozen=True, slots=True)
class Panel:
    x: float
    y: float
    ux: float
    uy: float
    length: float
    bottom: float = 1.0
    height: float = 2.9
    thickness: float = 0.16

    def collides(self, x, y, feet, radius, height):
        if feet >= self.bottom + self.height or feet + height <= self.bottom:
            return False
        dx, dy = x - self.x, y - self.y
        u, v = dx * self.ux + dy * self.uy, -dx * self.uy + dy * self.ux
        du = max(-u, 0, u - self.length)
        dv = max(abs(v) - self.thickness / 2, 0)
        return du * du + dv * dv < radius * radius

    def ray_hit(self, origin, direction, limit=48.0):
        ox, oy, oz = origin
        dx, dy, dz = direction
        rx, ry = ox - self.x, oy - self.y
        local_o = (rx * self.ux + ry * self.uy, -rx * self.uy + ry * self.ux, oz - self.bottom)
        local_d = (dx * self.ux + dy * self.uy, -dx * self.uy + dy * self.ux, dz)
        near, far = 0.0, limit
        face = 1
        for axis, low, high in ((0, 0.0, self.length), (1, -self.thickness / 2, self.thickness / 2),
                                (2, 0.0, self.height)):
            o, d = local_o[axis], local_d[axis]
            if abs(d) < 1e-10:
                if o < low or o > high:
                    return None
                continue
            a, b = (low - o) / d, (high - o) / d
            entry, leave = min(a, b), max(a, b)
            if entry > near:
                near, face = entry, axis
            far = min(far, leave)
            if near > far:
                return None
        distance = near if near > 1e-5 else far
        if not 0 < distance <= limit:
            return None
        return distance, face, local_o[0] + local_d[0] * distance, local_o[2] + dz * distance


@dataclass
class Door:
    name: str
    x: float
    y: float
    width: float
    angle: float = 0.0
    double: bool = True
    openness: float = 0.0
    target_open: bool = False
    _cached: tuple = field(default=(), repr=False)
    _cached_openness: float = field(default=-1.0, repr=False)
    _blocked: bool = field(default=False, repr=False)

    def panels_at(self, openness):
        swing = openness * math.pi / 2
        length = self.width / 2 if self.double else self.width
        theta = self.angle + swing
        panels = [Panel(self.x, self.y, math.cos(theta), math.sin(theta), length)]
        if self.double:
            ex = self.x + math.cos(self.angle) * self.width
            ey = self.y + math.sin(self.angle) * self.width
            theta = self.angle + math.pi - swing
            panels.append(Panel(ex, ey, math.cos(theta), math.sin(theta), length))
        return tuple(panels)

    @property
    def panels(self):
        if self.openness != self._cached_openness:
            self._cached, self._cached_openness = self.panels_at(self.openness), self.openness
        return self._cached

    def toggle(self):
        self._blocked = False
        self.target_open = not self.target_open
        return GameEvent("door_open" if self.target_open else "door_close", self.x, self.y)

    def update(self, player, dt):
        target = float(self.target_open)
        if self.openness == target:
            return None
        delta = min(max(0, dt), 0.05) * 1.8
        next_value = min(1.0, self.openness + delta) if self.target_open else max(0.0, self.openness - delta)
        # Test the actual swept motion in small angular increments; either an
        # opening or closing leaf can otherwise push the player into a wall.
        steps = max(1, math.ceil(abs(next_value - self.openness) / 0.01))
        for step in range(1, steps + 1):
            value = self.openness + (next_value - self.openness) * step / steps
            if any(panel.collides(player.x, player.y, player.z, player.RADIUS + 0.02, player.HEIGHT)
                   for panel in self.panels_at(value)):
                # Reverse a closing door; stop an opening door at its safe pose.
                self.target_open = True
                event = None if self._blocked else GameEvent("door_blocked", self.x, self.y)
                self._blocked = True
                return event
        resumed = self._blocked
        self.openness = next_value
        self._blocked = False
        return GameEvent("door_open", self.x, self.y) if resumed else None

    def interaction_distance(self, origin, direction, reach=2.6):
        # The doorway remains targetable even when both leaves are swung aside.
        portal = Panel(self.x, self.y, math.cos(self.angle), math.sin(self.angle), self.width,
                       thickness=0.3)
        hits = [panel.ray_hit(origin, direction, reach) for panel in (portal,) + self.panels]
        return min((hit[0] for hit in hits if hit), default=None)

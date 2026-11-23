"""Residents, authored patrols and conversations."""

from dataclasses import dataclass, field
import math
from typing import ClassVar, TYPE_CHECKING

from .events import GameEvent
from .targeting import cylinder_hit

if TYPE_CHECKING:
    from .player import Player
    from .world import World


@dataclass(frozen=True, slots=True)
class PatrolStop:
    """An authored destination and time to stand there before walking on."""

    x: float
    y: float
    pause: float = 0.0


@dataclass(slots=True)
class NPC:
    name: str
    x: float
    y: float
    z: float
    yaw: float
    dialogue: tuple[str, ...]
    outfit: str = "keeper"
    patrol: tuple[PatrolStop, ...] = ()
    walk_phase: float = field(default=0.0, init=False)
    walk_blend: float = field(default=0.0, init=False)
    _patrol_index: int = field(default=0, init=False, repr=False)
    _wait: float = field(default=0.0, init=False, repr=False)
    _step_distance: float = field(default=0.0, init=False, repr=False)

    radius: ClassVar[float] = 0.29
    height: ClassVar[float] = 1.75
    walk_speed: ClassVar[float] = 1.65
    step_distance: ClassVar[float] = 0.68

    @property
    def eye_z(self) -> float:
        return self.z + 1.58

    def interaction_distance(self, origin, direction, reach):
        return cylinder_hit(origin, direction, self.x, self.y, self.z,
                            self.radius, self.height, reach)

    def collides(self, x, y, feet, radius, height):
        return (feet < self.z + self.height and feet + height > self.z
                and (x - self.x) ** 2 + (y - self.y) ** 2 < (radius + self.radius) ** 2)

    def update(self, world: "World", player: "Player", dt: float) -> GameEvent | None:
        """Walk one simulation step along the configured route, waiting at obstructions."""
        if not self.patrol or dt <= 0:
            return None
        dt = min(dt, 0.04)
        blend_step = dt * 8.0
        if self._wait > 0:
            self._wait = max(0.0, self._wait - dt)
            self.walk_blend = max(0.0, self.walk_blend - blend_step)
            return None

        stop = self.patrol[self._patrol_index]
        dx, dy = stop.x - self.x, stop.y - self.y
        distance = math.hypot(dx, dy)
        if distance == 0:
            self._arrive(stop)
            self.walk_blend = max(0.0, self.walk_blend - blend_step)
            return None

        heading = math.atan2(dy, dx)
        turn = math.remainder(heading - self.yaw, math.tau)
        turn_limit = 5.0 * dt
        self.yaw = (self.yaw + max(-turn_limit, min(turn_limit, turn))) % math.tau
        if abs(turn) > math.pi / 6 + turn_limit:
            self.walk_blend = max(0.0, self.walk_blend - blend_step)
            return None

        travel = min(distance, self.walk_speed * dt, 0.08)
        if travel == distance:
            x, y = stop.x, stop.y
        else:
            x, y = self.x + dx * travel / distance, self.y + dy * travel / distance
        z = self._walk_height(world, player, x, y)
        if z is None:
            self.walk_blend = max(0.0, self.walk_blend - blend_step)
            return None

        self.x, self.y, self.z = x, y, z
        self.walk_blend = min(1.0, self.walk_blend + blend_step)
        self.walk_phase = (self.walk_phase + math.pi * travel / self.step_distance) % math.tau
        if travel == distance:
            self._arrive(stop)
        self._step_distance += travel
        if self._step_distance < self.step_distance:
            return None

        from .sound_surfaces import surface_kind

        self._step_distance %= self.step_distance
        return GameEvent("npc_step", x, y, 0.42, surface_kind(world, x, y, z, radius=self.radius))

    def _arrive(self, stop: PatrolStop) -> None:
        self._patrol_index = (self._patrol_index + 1) % len(self.patrol)
        self._wait = stop.pause

    def _walk_height(self, world: "World", player: "Player", x: float, y: float) -> float | None:
        support = world.walk_support(x, y, self.z, self.radius, walking=True)
        if support is None:
            return None
        z = support[0]
        if (z < player.z + player.HEIGHT and z + self.height > player.z
                and (x - player.x) ** 2 + (y - player.y) ** 2 < (self.radius + player.RADIUS) ** 2):
            return None
        if (world.in_water(x, y, z)
                or not world.terrain_walkable(x, y, self.radius, feet=z)
                or world.collides(x, y, z, self.radius, self.height, ignore_npc=self)):
            return None
        return z


def make_residents() -> list[NPC]:
    """Place residents beside Ashgate's gatehouse, Gravewood and Thornwatch."""
    from .terrain import LANDMARKS

    thornwatch = LANDMARKS[0]
    watch_x, watch_y = thornwatch.to_world(306.6, 121.8)
    return [
        NPC("Iven Ashward", 130.35, 80.5, 1.0, math.radians(210), (
            "Easy there, traveler. I'm Iven. I've kept this gate since the ash first fell.",
            "There's an iron sword by the entrance. The dummies in the west yard won't mind a few swings.",
            "Take the north road for Gravewood. Keep to the cobbles after you cross the river.",
        )),
        NPC("Mael Veyr", 126.9, 79.5, 1.0, math.radians(298), (
            "I'm Mael Veyr. Keep your voice low. The ash remembers names.",
            "I learned the rites at Black Abbey, before the bells cracked.",
            "I keep one coal from the abbey hearth. If the last bell ever rings, I'll carry the flame home.",
        ), outfit="sorcerer"),
        NPC("Sister Morwen", 74.0, 241.3, 1.0, math.radians(205), (
            "Can you hear it? When the wind lapses, the old chapel almost sounds full again.",
            "There is a fire staff on the timber floor inside. The Warden keeps to the watchstones west of here.",
            "If you see it raise both fists, step away. The dead need no company tonight.",
        ), outfit="mourner"),
        NPC("Vesper Thorn", watch_x, watch_y, float(thornwatch.base), math.radians(215) + thornwatch.angle, (
            "I mind the north road. When the wind lets up, the balcony is the only quiet place in this fort.",
            "The upper stairs are inside. Take the east balcony for a view of the highlands.",
            "If you cross the river later, stay on the timber bridge. The current can pull you off your feet.",
        ), outfit="sentinel"),
    ]

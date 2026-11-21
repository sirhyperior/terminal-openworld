"""Stationary residents and their authored conversations."""

from dataclasses import dataclass
import math
from typing import ClassVar

from .targeting import cylinder_hit


@dataclass(slots=True)
class NPC:
    name: str
    x: float
    y: float
    z: float
    yaw: float
    dialogue: tuple[str, ...]
    outfit: str = "keeper"

    radius: ClassVar[float] = 0.29
    height: ClassVar[float] = 1.75

    @property
    def eye_z(self) -> float:
        return self.z + 1.58

    def interaction_distance(self, origin, direction, reach):
        return cylinder_hit(origin, direction, self.x, self.y, self.z,
                            self.radius, self.height, reach)

    def collides(self, x, y, feet, radius, height):
        return (feet < self.z + self.height and feet + height > self.z
                and (x - self.x) ** 2 + (y - self.y) ** 2 < (radius + self.radius) ** 2)


def make_residents() -> list[NPC]:
    """Place residents beside Ashgate's gatehouse, Gravewood and Thornwatch."""
    from .terrain import LANDMARKS

    thornwatch = LANDMARKS[0]
    watch_x, watch_y = thornwatch.to_world(306.6, 121.8)
    return [
        NPC("Iven Ashward", 130.35, 80.5, 1.0, math.radians(210), (
            "Easy there, traveler. I'm Iven. I've kept this gate since the ash first fell.",
            "There's an iron sword by the entrance. The dummies in the west yard won't mind a few swings.",
            "Take the north road for Gravewood. Keep to the gravel after you cross the river.",
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

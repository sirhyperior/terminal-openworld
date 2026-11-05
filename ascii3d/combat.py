"""Small, deterministic sword inventory and passive training targets.

Targeting and collision stay independent of text rendering. The world supplies
the same line-of-sight query used by its E interaction path.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .events import GameEvent
from .targeting import cylinder_hit, view_ray

if TYPE_CHECKING:
    from .player import Player
    from .world import World


ATTACK_REACH = 2.55
ATTACK_COOLDOWN = 0.48
SWING_DURATION = 0.30
INTERACTION_REACH = 2.6
NAME_REACH = 10.0


def _box_hit(origin, direction, bounds, reach):
    near, far = 0.0, reach
    for o, d, (low, high) in zip(origin, direction, bounds):
        if abs(d) < 1e-10:
            if not low <= o <= high:
                return None
        else:
            a, b = (low - o) / d, (high - o) / d
            near, far = max(near, min(a, b)), min(far, max(a, b))
            if near > far:
                return None
    return near if far >= 0 and near <= reach else None


@dataclass
class SwordPickup:
    x: float
    y: float
    z: float = 1.0
    name: str = "iron sword"
    collected: bool = False

    def interaction_distance(self, origin, direction, reach=INTERACTION_REACH):
        if self.collected:
            return None
        # A modest envelope makes the thin upright blade usable in text cells.
        return _box_hit(origin, direction,
                        ((self.x - 0.30, self.x + 0.30),
                         (self.y - 0.30, self.y + 0.30),
                         (self.z + 0.15, self.z + 1.60)), reach)


@dataclass
class Enemy:
    """A stationary, reusable target; this milestone instantiates a dummy."""

    name: str
    x: float
    y: float
    z: float = 1.0
    radius: float = 0.40
    height: float = 2.05
    max_hp: int = 3
    hp: int = 3
    respawn_delay: float = 4.0
    down_remaining: float = 0.0
    hit_remaining: float = 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def ray_hit(self, origin, direction, reach):
        """Intersect the visible torso/head cylinder, including vertical aim."""
        return cylinder_hit(origin, direction, self.x, self.y, self.z,
                            self.radius, self.height, reach)

    def collides(self, x, y, feet, radius, height):
        # Keep the fixed support solid while downed: a reset cannot spawn its
        # body inside the player, and the player cannot stand on a narrow post.
        if feet >= self.z + self.height or feet + height <= self.z:
            return False
        return (x - self.x) ** 2 + (y - self.y) ** 2 < (radius + self.radius) ** 2


@dataclass
class CombatState:
    pickups: list[SwordPickup] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    has_sword: bool = False
    cooldown: float = 0.0
    swing_remaining: float = 0.0

    def collect(self, pickup: SwordPickup, player: "Player") -> GameEvent:
        origin, direction = view_ray(player)
        if (self.has_sword or not any(item is pickup for item in self.pickups)
                or pickup.interaction_distance(origin, direction) is None):
            return GameEvent("interaction_miss", player.x, player.y)
        self.has_sword = True
        # The outdoor placement offers the same starter weapon to --outside.
        # Both disappear together; this is one inventory item, not spare loot.
        for item in self.pickups:
            item.collected = True
        return GameEvent("sword_pickup", pickup.x, pickup.y)

    def aimed_enemy(self, world: "World", player: "Player",
                    reach: float = NAME_REACH) -> Enemy | None:
        origin, direction = view_ray(player)
        nearest, distance = None, max(0.0, reach)
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            hit = enemy.ray_hit(origin, direction, distance)
            if hit is not None and (nearest is None or hit < distance):
                nearest, distance = enemy, hit
        if nearest is not None and world.line_clear(origin, direction, distance):
            return nearest
        return None

    def attack(self, world: "World", player: "Player") -> list[GameEvent]:
        if self.cooldown > 1e-8:
            return []
        if not self.has_sword:
            self.cooldown = 0.30
            return [GameEvent("attack_empty", player.x, player.y)]
        self.cooldown = ATTACK_COOLDOWN
        self.swing_remaining = SWING_DURATION
        enemy = self.aimed_enemy(world, player, ATTACK_REACH)
        # Let confirmed contact lead the feedback; an air swing keeps its full
        # whoosh. Both paths still emit their separate semantic events.
        events = [GameEvent("sword_swing", player.x, player.y,
                            0.55 if enemy is not None else 1.0)]
        if enemy is None:
            events.append(GameEvent("sword_miss", player.x, player.y))
            return events
        enemy.hp = max(0, enemy.hp - 1)
        enemy.hit_remaining = 0.18
        events.append(GameEvent("sword_hit", enemy.x, enemy.y))
        if not enemy.alive:
            enemy.down_remaining = enemy.respawn_delay
            events.append(GameEvent("dummy_down", enemy.x, enemy.y))
        return events

    def update(self, dt: float) -> list[GameEvent]:
        dt = max(0.0, dt)
        self.cooldown = max(0.0, self.cooldown - dt)
        self.swing_remaining = max(0.0, self.swing_remaining - dt)
        events = []
        for enemy in self.enemies:
            enemy.hit_remaining = max(0.0, enemy.hit_remaining - dt)
            if not enemy.alive:
                enemy.down_remaining = max(0.0, enemy.down_remaining - dt)
                if enemy.down_remaining <= 1e-8:
                    enemy.hp = enemy.max_hp
                    events.append(GameEvent("dummy_reset", enemy.x, enemy.y))
        return events

    def collides(self, x, y, feet, radius, height) -> bool:
        return any(enemy.collides(x, y, feet, radius, height) for enemy in self.enemies)


def make_training_combat() -> CombatState:
    return CombatState(
        pickups=[SwordPickup(14.5, 6.5), SwordPickup(15.3, 35.6)],
        enemies=[Enemy("Training dummy", 20.5, 36.5)],
    )

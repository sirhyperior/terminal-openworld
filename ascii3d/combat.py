"""Shared weapons, projectiles, passive targets and territorial enemies.

Targeting and collision stay independent of text rendering. The world supplies
the same line-of-sight query used by its E interaction path.
"""

from dataclasses import dataclass, field
import math
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
FIREBALL_SPEED = 12.0
FIREBALL_RANGE = 28.0
MAX_FIREBALLS = 8
BURST_DURATION = 0.22


@dataclass(frozen=True)
class Weapon:
    name: str
    pickup_cue: str
    cooldown: float


SWORD = Weapon("iron sword", "sword_pickup", ATTACK_COOLDOWN)
FIRE_STAFF = Weapon("fire staff", "staff_pickup", 0.65)


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
class WeaponPickup:
    x: float
    y: float
    z: float = 1.0
    weapon: Weapon = SWORD
    collected: bool = False
    group: str | None = None

    @property
    def name(self):
        return self.weapon.name

    def interaction_distance(self, origin, direction, reach=INTERACTION_REACH):
        if self.collected:
            return None
        # A shared envelope makes thin upright weapons usable in text cells.
        return _box_hit(origin, direction,
                        ((self.x - 0.30, self.x + 0.30),
                         (self.y - 0.30, self.y + 0.30),
                         (self.z + 0.15, self.z + 1.60)), reach)


@dataclass
class Fireball:
    x: float
    y: float
    z: float
    direction: tuple[float, float, float]
    range_left: float = FIREBALL_RANGE


@dataclass
class FireBurst:
    x: float
    y: float
    z: float
    remaining: float = BURST_DURATION


@dataclass(frozen=True)
class EnemyBehavior:
    """Shared territorial melee behavior; instance placement stays separate."""

    speed: float = 1.55
    aggro_range: float = 7.5
    attack_range: float = 1.35
    windup: float = 0.55
    recovery: float = 1.2
    damage: int = 2
    step_distance: float = 1.05


WARDEN_BEHAVIOR = EnemyBehavior()


@dataclass
class Enemy:
    """A target with optional territorial behavior, independent of rendering."""

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
    behavior: EnemyBehavior | None = None
    territory: tuple[float, float, float, float] | None = None
    home: tuple[float, float, float] | None = None
    state: str = "idle"
    facing: float = -math.pi / 2
    walk_phase: float = 0.0
    attack_remaining: float = 0.0
    attack_cooldown: float = 0.0
    _step_distance: float = field(default=0.0, repr=False)
    _steer_heading: float = field(default=0.0, repr=False)
    _steer_remaining: float = field(default=0.0, repr=False)

    def __post_init__(self):
        if self.home is None:
            self.home = (self.x, self.y, self.z)

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
        if self.behavior is not None and not self.alive:
            return False
        if feet >= self.z + self.height or feet + height <= self.z:
            return False
        return (x - self.x) ** 2 + (y - self.y) ** 2 < (radius + self.radius) ** 2

    def inside_territory(self, x, y, radius=0.0):
        if self.territory is None:
            return False
        x0, y0, x1, y1 = self.territory
        return x0 + radius <= x < x1 - radius and y0 + radius <= y < y1 - radius

    def _sees_player(self, world, player):
        # Compare torso centers so jumping/standing behind a low wall follows
        # the same exact solid query as weapon and interaction targeting.
        origin = (self.x, self.y, self.z + self.height * 0.60)
        delta = (player.x - self.x, player.y - self.y,
                 player.z + player.HEIGHT * 0.60 - origin[2])
        distance = math.sqrt(sum(value * value for value in delta))
        return distance < 1e-8 or world.line_clear(
            origin, tuple(value / distance for value in delta), distance)

    def _attack_reaches(self, world, player, visible=False):
        return (player.hp > 0 and self.inside_territory(player.x, player.y)
                and abs(player.z - self.z) < 0.75
                and math.hypot(player.x - self.x, player.y - self.y)
                <= self.behavior.attack_range
                and (visible or self._sees_player(world, player)))

    def _can_stand(self, world, player, x, y, z):
        from .world import AIR, WATER

        if not self.inside_territory(x, y, self.radius):
            return False
        if (player is not None and player.hp > 0
                and z < player.z + player.HEIGHT and z + self.height > player.z
                and math.hypot(x - player.x, y - player.y) < self.radius + player.RADIUS):
            return False
        if world.collides(x, y, z, self.radius, self.height, ignore_enemy=self):
            return False
        # This ground-bound type never climbs or drops. Five footprint samples
        # prevent walking off edited ledges or onto water, with constant work.
        floor = math.floor(z - 1e-4)
        for dx, dy in ((0, 0), (self.radius, 0), (-self.radius, 0),
                       (0, self.radius), (0, -self.radius)):
            if world.get(math.floor(x + dx), math.floor(y + dy), floor) in (AIR, WATER):
                return False
        return True

    def can_respawn(self, world, player):
        return self._can_stand(world, player, *self.home)

    def _move_toward(self, world, player, target_x, target_y, dt):
        from .sound_surfaces import surface_kind

        dx, dy = target_x - self.x, target_y - self.y
        distance = math.hypot(dx, dy)
        if distance < 0.03:
            return []
        heading = math.atan2(dy, dx)
        travel = min(distance, self.behavior.speed * dt)
        # Fixed candidate and substep budgets avoid path searches as the world
        # grows. Alternate headings skirt isolated pillars and slide along walls.
        # Briefly retain a successful detour: choosing a fresh tangent every
        # frame would oscillate against the middle of a flat obstacle face.
        self._steer_remaining = max(0.0, self._steer_remaining - dt)
        count = max(1, math.ceil(travel / 0.08))
        moved = 0.0
        for _ in range(count):
            angles = [heading + turn for turn in
                      (0, math.pi / 4, -math.pi / 4, math.pi / 2, -math.pi / 2)]
            if self._steer_remaining > 0:
                angles.insert(0, self._steer_heading)
            for angle in angles:
                x = self.x + math.cos(angle) * travel / count
                y = self.y + math.sin(angle) * travel / count
                if self._can_stand(world, player, x, y, self.z):
                    moved += math.hypot(x - self.x, y - self.y)
                    self.x, self.y, self.facing = x, y, angle
                    if self._steer_remaining <= 0 and angle != heading:
                        self._steer_heading, self._steer_remaining = angle, 0.75
                    break
            else:
                break
        self.walk_phase += moved * 4.2
        self._step_distance += moved
        if self._step_distance >= self.behavior.step_distance:
            self._step_distance %= self.behavior.step_distance
            return [GameEvent("enemy_step", self.x, self.y, surface=surface_kind(
                world, self.x, self.y, self.z))]
        return []

    def update(self, world, player, dt):
        """Advance one bounded AI step; fixed-step callers normally use 1/120s."""
        if self.behavior is None or player is None or not self.alive or dt <= 0:
            return []
        dt = min(dt, 0.1)
        events = []
        self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
        if self.attack_remaining > 0:
            self.attack_remaining = max(0.0, self.attack_remaining - dt)
            if self.attack_remaining <= 1e-8:
                self.attack_remaining = 0.0
                self.attack_cooldown = self.behavior.recovery
                self.state = "recovering"
                if self._attack_reaches(world, player):
                    events.extend(player.take_damage(self.behavior.damage))
                else:
                    events.append(GameEvent("enemy_miss", self.x, self.y))
            return events
        distance = math.hypot(player.x - self.x, player.y - self.y)
        within = player.hp > 0 and self.inside_territory(player.x, player.y)
        engaged = self.state in ("chasing", "windup", "recovering")
        if within and (engaged or distance <= self.behavior.aggro_range) and self._sees_player(world, player):
            if not engaged:
                events.append(GameEvent("enemy_alert", self.x, self.y))
            self.facing = math.atan2(player.y - self.y, player.x - self.x)
            if self._attack_reaches(world, player, visible=True):
                if self.attack_cooldown <= 1e-8:
                    self.state = "windup"
                    self.attack_remaining = self.behavior.windup
                    events.append(GameEvent("enemy_attack", self.x, self.y))
                else:
                    self.state = "recovering"
            else:
                self.state = "chasing"
                events.extend(self._move_toward(world, player, player.x, player.y, dt))
        else:
            self.state = "returning"
            events.extend(self._move_toward(world, player, self.home[0], self.home[1], dt))
            if math.hypot(self.x - self.home[0], self.y - self.home[1]) < 0.03:
                self.state = "idle"
        return events


@dataclass
class CombatState:
    pickups: list[WeaponPickup] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    held_item: WeaponPickup | None = None
    cooldown: float = 0.0
    swing_remaining: float = 0.0
    fireballs: list[Fireball] = field(default_factory=list)
    bursts: list[FireBurst] = field(default_factory=list)

    def collect(self, pickup: WeaponPickup, player: "Player", world: "World") -> list[GameEvent]:
        origin, direction = view_ray(player)
        hit = pickup.interaction_distance(origin, direction)
        if (not any(item is pickup for item in self.pickups) or hit is None
                or not world.line_clear(origin, direction, hit)
                or pickup is self.held_item):
            return [GameEvent("interaction_miss", player.x, player.y)]
        events = []
        if self.held_item is not None:
            dropped = self.held_item
            # Settle on the support below the player, including crate/door tops.
            # A mid-jump swap must not leave an item suspended in the air.
            feet = max(0.12, player.z + 0.001)
            # Prefer just behind the feet, so the dropped envelope does not
            # swallow the view ray and immediately steal the new item's prompt.
            for offset in (math.pi, math.pi / 2, -math.pi / 2, 0, None):
                x = player.x if offset is None else player.x + math.cos(player.yaw + offset) * 0.55
                y = player.y if offset is None else player.y + math.sin(player.yaw + offset) * 0.55
                if offset is not None:
                    direction = ((x - player.x) / 0.55, (y - player.y) / 0.55, 0)
                    if not world.line_clear((player.x, player.y, player.z + 0.8), direction, 0.55):
                        continue
                below = world.solid_hit((x, y, feet), (0, 0, -1), feet)
                z = max(0.12, feet - below) if below is not None else 0.12
                if not world.collides(x, y, z, 0.14, 1.60):
                    dropped.x, dropped.y, dropped.z = x, y, z
                    break
            else:
                # A narrow ledge may support only the edge of the player's
                # footprint. Retain feet height rather than burying the item.
                dropped.x, dropped.y, dropped.z = player.x, player.y, player.z
            dropped.collected, dropped.group = False, None
            if not any(item is dropped for item in self.pickups):
                self.pickups.append(dropped)
            events.append(GameEvent("item_drop", dropped.x, dropped.y))
        # Only explicit aliases (the two starter sword placements) disappear
        # together. Dropping the held instance never resurrects its old alias.
        for item in self.pickups:
            if item is pickup or (pickup.group is not None and item.group == pickup.group):
                item.collected = True
        self.held_item = pickup
        self.swing_remaining = 0.0
        # Keep the cooldown through swaps, so collecting cannot bypass it.
        events.append(GameEvent(pickup.weapon.pickup_cue, pickup.x, pickup.y))
        return events

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
        if self.cooldown > 1e-8 or player.hp <= 0:
            return []
        if self.held_item is None:
            self.cooldown = 0.30
            return [GameEvent("attack_empty", player.x, player.y)]
        weapon = self.held_item.weapon
        self.cooldown = weapon.cooldown
        self.swing_remaining = SWING_DURATION
        if weapon == FIRE_STAFF:
            if len(self.fireballs) >= MAX_FIREBALLS:
                return [GameEvent("attack_empty", player.x, player.y)]
            origin, direction = view_ray(player)
            # Start at the eye: a muzzle offset must never teleport past a wall.
            self.fireballs.append(Fireball(*origin, direction))
            return [GameEvent("fireball_cast", player.x, player.y)]
        enemy = self.aimed_enemy(world, player, ATTACK_REACH)
        # Let confirmed contact lead the feedback; an air swing keeps its full
        # whoosh. Both paths still emit their separate semantic events.
        events = [GameEvent("sword_swing", player.x, player.y,
                            0.55 if enemy is not None else 1.0)]
        if enemy is None:
            events.append(GameEvent("sword_miss", player.x, player.y))
            return events
        events.extend(self._damage(enemy, "sword_hit"))
        return events

    @staticmethod
    def _damage(enemy, cue):
        enemy.hp = max(0, enemy.hp - 1)
        enemy.hit_remaining = 0.18
        events = [GameEvent(cue, enemy.x, enemy.y)]
        if enemy.behavior is not None:
            events.append(GameEvent("enemy_hurt", enemy.x, enemy.y))
        if not enemy.alive:
            enemy.down_remaining = enemy.respawn_delay
            enemy.state = "down"
            enemy.attack_remaining = enemy.attack_cooldown = 0.0
            events.append(GameEvent("enemy_down" if enemy.behavior is not None else "dummy_down",
                                    enemy.x, enemy.y))
        return events

    def update(self, dt: float, world: "World", player: "Player | None" = None) -> list[GameEvent]:
        dt = max(0.0, dt)
        if dt <= 0:
            return []
        self.cooldown = max(0.0, self.cooldown - dt)
        self.swing_remaining = max(0.0, self.swing_remaining - dt)
        events = []
        for enemy in self.enemies:
            enemy.hit_remaining = max(0.0, enemy.hit_remaining - dt)
            if not enemy.alive:
                enemy.down_remaining = max(0.0, enemy.down_remaining - dt)
                if (enemy.down_remaining <= 1e-8
                        and (enemy.behavior is None or enemy.can_respawn(world, player))):
                    if enemy.behavior is not None:
                        enemy.x, enemy.y, enemy.z = enemy.home
                        enemy.state = "idle"
                        enemy.attack_remaining = enemy.attack_cooldown = 0.0
                        enemy._step_distance = enemy.walk_phase = 0.0
                        enemy._steer_remaining = 0.0
                    enemy.hp = enemy.max_hp
                    events.append(GameEvent("enemy_respawn" if enemy.behavior is not None else "dummy_reset",
                                            enemy.x, enemy.y))
            else:
                events.extend(enemy.update(world, player, dt))
        for burst in self.bursts:
            burst.remaining = max(0.0, burst.remaining - dt)
        self.bursts[:] = [burst for burst in self.bursts if burst.remaining > 1e-8]
        events.extend(self._advance_fireballs(world, dt))
        return events

    def _advance_fireballs(self, world, dt):
        events, active = [], []
        for ball in self.fireballs[:MAX_FIREBALLS]:
            origin = (ball.x, ball.y, ball.z)
            distance = min(ball.range_left, FIREBALL_SPEED * dt)
            solid = world.solid_hit(origin, ball.direction, distance)
            travel = distance if solid is None else solid
            target = None
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                hit = enemy.ray_hit(origin, ball.direction, travel)
                if hit is not None and (solid is None or hit < solid) and (target is None or hit < travel):
                    target, travel = enemy, hit
            ball.x, ball.y, ball.z = (origin[i] + ball.direction[i] * travel for i in range(3))
            ball.range_left = max(0.0, ball.range_left - travel)
            if target is not None:
                events.extend(self._damage(target, "fireball_hit"))
            elif solid is not None:
                events.append(GameEvent("fireball_impact", ball.x, ball.y))
            elif ball.range_left <= 1e-8:
                events.append(GameEvent("fireball_fizzle", ball.x, ball.y))
            else:
                active.append(ball)
                continue
            self.bursts.append(FireBurst(ball.x, ball.y, ball.z))
        self.fireballs[:] = active
        self.bursts[:] = self.bursts[-MAX_FIREBALLS:]
        return events

    def collides(self, x, y, feet, radius, height, ignore_enemy=None) -> bool:
        return any(enemy is not ignore_enemy and enemy.collides(x, y, feet, radius, height)
                   for enemy in self.enemies)


def make_training_combat() -> CombatState:
    from .map_expansion import (DUMMY_POSITIONS, STAFF_POSITION, SWORD_POSITIONS,
                                WARDEN_POSITION, WATCHSTONE_BOUNDS)
    return CombatState(
        pickups=[*(WeaponPickup(x, y, group="starter_sword")
                   for x, y in SWORD_POSITIONS),
                 WeaponPickup(*STAFF_POSITION, weapon=FIRE_STAFF)],
        enemies=[*(Enemy("Training dummy", x, y) for x, y in DUMMY_POSITIONS),
                 Enemy("Watchstone Warden", *WARDEN_POSITION, radius=0.44, height=2.15,
                       max_hp=4, hp=4, respawn_delay=12.0, behavior=WARDEN_BEHAVIOR,
                       territory=WATCHSTONE_BOUNDS)],
    )

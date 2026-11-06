"""Fixed-step movement, cylinder collision, gravity and jumping."""

from dataclasses import dataclass, field
import math

from .events import GameEvent
from .sound_surfaces import surface_kind
from .world import INDOOR_SPAWN, World


@dataclass
class Player:
    x: float = INDOOR_SPAWN[0]
    y: float = INDOOR_SPAWN[1]
    z: float = INDOOR_SPAWN[2]
    yaw: float = math.pi / 2
    pitch: float = 0.0
    vertical_speed: float = 0.0
    grounded: bool = True
    stride: float = 0.0
    moving: bool = False
    running: bool = False
    in_water: bool = False
    max_hp: int = 10
    hp: int = 10
    events: list[GameEvent] = field(default_factory=list, repr=False)
    _step_distance: float = field(default=0.0, repr=False)

    RADIUS = 0.22
    HEIGHT = 1.7
    EYE = 1.48
    WALK_SPEED = 3.4
    RUN_SPEED = 6.2
    GRAVITY = 19.0
    JUMP_SPEED = 7.1

    def take_damage(self, amount: int) -> list[GameEvent]:
        """Apply one confirmed hit and report feedback once per living player."""
        if amount <= 0 or self.hp <= 0:
            return []
        self.hp = max(0, self.hp - amount)
        events = [GameEvent("player_hurt", self.x, self.y)]
        if self.hp == 0:
            events.append(GameEvent("player_down", self.x, self.y))
        return events

    @property
    def eye_z(self) -> float:
        bob = math.sin(self.stride) * 0.025 if self.grounded and self.moving else 0.0
        return self.z + self.EYE + bob

    def look(self, dx: float, dy: float, sensitivity: float = 0.0025) -> None:
        """Apply one frame of relative mouse motion, independent of physics dt."""
        if not all(math.isfinite(value) for value in (dx, dy, sensitivity)) or sensitivity <= 0:
            return
        self.yaw = (self.yaw - dx * sensitivity) % math.tau
        self.pitch = max(-0.65, min(0.65, self.pitch - dy * sensitivity))

    def update(self, world: World, keys: set[str], dt: float, jump: bool = False) -> None:
        dt = max(0.0, min(dt, 0.1))
        self.events.clear()
        if not dt:
            return
        was_grounded, was_water = self.grounded, self.in_water
        landing_speed = 0.0
        turn = int("right" in keys) - int("left" in keys)
        self.yaw = (self.yaw - turn * 1.8 * dt) % math.tau
        look = int("up" in keys) - int("down" in keys)
        self.pitch = max(-0.65, min(0.65, self.pitch + look * dt))
        forward = int("w" in keys) - int("s" in keys)
        strafe = int("d" in keys) - int("a" in keys)
        length = math.hypot(forward, strafe)
        self.running = "shift" in keys and length > 0
        speed = self.RUN_SPEED if self.running else self.WALK_SPEED
        self.in_water = world.in_water(self.x, self.y, self.z)
        if self.in_water:
            speed *= 0.55
        if length:
            forward, strafe = forward / length, strafe / length
        cosine, sine = math.cos(self.yaw), math.sin(self.yaw)
        dx = (cosine * forward + sine * strafe) * speed * dt
        dy = (sine * forward - cosine * strafe) * speed * dt
        if self.in_water:
            current_x, current_y = world.current(self.x)
            dx += current_x * dt
            dy += current_y * dt

        if jump and self.grounded:
            self.vertical_speed = self.JUMP_SPEED
            self.grounded = False
            self.events.append(GameEvent("jump", self.x, self.y))

        # Substeps keep sprinting from tunnelling through walls. Axis separation
        # lets the cylinder slide smoothly along a wall, including at corners.
        count = max(1, math.ceil(max(abs(dx), abs(dy), abs(self.vertical_speed * dt)) / 0.08))
        step_dt = dt / count
        old_x, old_y = self.x, self.y
        for _ in range(count):
            next_x, next_y = self.x + dx / count, self.y + dy / count
            if not world.collides(next_x, self.y, self.z, self.RADIUS, self.HEIGHT):
                self.x = next_x
            if not world.collides(self.x, next_y, self.z, self.RADIUS, self.HEIGHT):
                self.y = next_y
            self.vertical_speed -= self.GRAVITY * step_dt
            dz = self.vertical_speed * step_dt
            next_z = self.z + dz
            if world.collides(self.x, self.y, next_z, self.RADIUS, self.HEIGHT):
                if dz < 0:
                    landing_speed = max(landing_speed, -self.vertical_speed)
                # Resolve the point of contact instead of leaving a visible gap.
                safe, blocked = self.z, next_z
                for _ in range(12):
                    middle = (safe + blocked) * 0.5
                    if world.collides(self.x, self.y, middle, self.RADIUS, self.HEIGHT):
                        blocked = middle
                    else:
                        safe = middle
                self.z = safe
                self.grounded = dz < 0
                self.vertical_speed = 0.0
            else:
                self.z = next_z
                self.grounded = False
        distance = math.hypot(self.x - old_x, self.y - old_y)
        self.moving = distance > 0.0001
        self.stride += distance * 3.1
        self.in_water = world.in_water(self.x, self.y, self.z)
        if self.in_water != was_water:
            self.events.append(GameEvent("water_splash", self.x, self.y, 0.75))
        if not was_grounded and self.grounded and landing_speed > 1.5:
            surface = surface_kind(world, self.x, self.y, self.z, self.in_water)
            self.events.append(GameEvent("land", self.x, self.y,
                                         min(1.0, landing_speed / 7), surface))
        if self.grounded and self.moving and length:
            self._step_distance += distance
            stride = 1.7 if self.running else 1.3
            if self._step_distance >= stride:
                self._step_distance %= stride
                surface = surface_kind(world, self.x, self.y, self.z, self.in_water)
                self.events.append(GameEvent("step_" + surface, self.x, self.y, 0.9 if self.running else 0.7))

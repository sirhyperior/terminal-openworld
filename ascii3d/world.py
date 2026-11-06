"""Voxel architecture. Coordinates are X/east, Y/north, Z/up."""

from dataclasses import dataclass, field
import math

from .doors import Door
from .events import GameEvent
from .combat import CombatState, WeaponPickup, make_training_combat
from .targeting import cylinder_hit, view_ray
from .map_expansion import INDOOR_SPAWN, OUTDOOR_SPAWN


AIR, STONE, FLOOR, METAL, CRATE, GRASS, WATER, WOOD, LEAVES, PATH, BRIDGE = range(11)
WATER_LEVEL = 0.68
RIVERBED_LEVEL = 0.12


def river_center(x: float) -> float:
    return 86.0 + 1.6 * math.sin(x * 0.18) + 0.45 * math.sin(x * 0.43)


@dataclass(frozen=True, slots=True)
class Tree:
    x: float
    y: float
    radius: float = 0.20
    height: float = 4.3
    seed: int = 0


@dataclass
class World:
    width: int
    depth: int
    height: int
    cells: bytearray
    outdoor_bounds: tuple[int, int, int, int] | None = None
    trees: dict[tuple[int, int], Tree] = field(default_factory=dict)
    revision: int = 0
    doors: list[Door] = field(default_factory=list)
    combat: CombatState = field(default_factory=CombatState)

    @classmethod
    def empty(cls, width: int, depth: int, height: int) -> "World":
        return cls(width, depth, height, bytearray(width * depth * height))

    def get(self, x: int, y: int, z: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.depth and 0 <= z < self.height:
            return self.cells[(z * self.depth + y) * self.width + x]
        return AIR

    def box(self, x0: int, y0: int, z0: int, x1: int, y1: int, z1: int,
            material: int = STONE) -> None:
        """Fill a box; upper bounds are exclusive. AIR carves openings."""
        self.revision += 1
        for z in range(max(0, z0), min(self.height, z1)):
            for y in range(max(0, y0), min(self.depth, y1)):
                for x in range(max(0, x0), min(self.width, x1)):
                    self.cells[(z * self.depth + y) * self.width + x] = material

    def collides(self, x: float, y: float, feet: float,
                 radius: float = 0.22, height: float = 1.7,
                 ignore_enemy=None) -> bool:
        # Water is a volume to wade through, with an implicit shallow riverbed.
        if x - radius < 0 or y - radius < 0:
            return True
        if x + radius > self.width or y + radius > self.depth or feet < RIVERBED_LEVEL - 1e-7:
            return True
        for cy in range(math.floor(y - radius), math.floor(y + radius) + 1):
            for cx in range(math.floor(x - radius), math.floor(x + radius) + 1):
                dx = max(cx - x, 0.0, x - (cx + 1))
                dy = max(cy - y, 0.0, y - (cy + 1))
                if dx * dx + dy * dy >= radius * radius:
                    continue
                tree = self.trees.get((cx, cy))
                if tree and feet < tree.height and feet + height > 1:
                    if (x - tree.x) ** 2 + (y - tree.y) ** 2 < (radius + tree.radius) ** 2:
                        return True
                for cz in range(math.floor(feet + 1e-7), math.floor(feet + height - 1e-7) + 1):
                    material = self.get(cx, cy, cz)
                    if material and material != WATER:
                        return True
        return (any(panel.collides(x, y, feet, radius, height)
                    for door in self.doors for panel in door.panels)
                or self.combat.collides(x, y, feet, radius, height,
                                        ignore_enemy=ignore_enemy))

    def line_clear(self, origin, direction, distance, ignore_door=None):
        """Exact voxel, swinging-panel and trunk occlusion before a target.

        A door may ignore its own leaves when being operated. Every other
        target, including attacks, sees those same leaves as opaque.
        """
        return self.solid_hit(origin, direction, max(0.0, distance - 1e-7), ignore_door) is None

    def solid_hit(self, origin, direction, distance, ignore_door=None):
        """First solid surface on a segment; shared by sight and projectiles.

        Direction must be normalized. Water remains transparent, as for sight.
        Return travel distance rather than sampling, even for thin door leaves.
        """
        limit = max(0.0, distance)
        cell = [math.floor(value) for value in origin]
        steps = [1 if value >= 0 else -1 for value in direction]
        deltas = [abs(1 / value) if abs(value) > 1e-12 else math.inf
                  for value in direction]
        crossings = [((cell[i] + 1 - origin[i]) if steps[i] > 0
                      else (origin[i] - cell[i])) * deltas[i]
                     if math.isfinite(deltas[i]) else math.inf for i in range(3)]
        travelled, nearest = 0.0, None
        while True:
            if self.get(*cell) not in (AIR, WATER):
                nearest = travelled
                break
            axis = min(range(3), key=lambda i: crossings[i])
            if crossings[axis] > limit:
                break
            travelled = crossings[axis]
            cell[axis] += steps[axis]
            crossings[axis] += deltas[axis]
        limit = limit if nearest is None else nearest
        for door in self.doors:
            if door is ignore_door:
                continue
            for panel in door.panels:
                hit = panel.ray_hit(origin, direction, limit)
                if hit is not None:
                    nearest = limit = hit[0]
        for tree in self.trees.values():
            hit = cylinder_hit(origin, direction, tree.x, tree.y, 1.0,
                               tree.radius, tree.height - 1.0, limit)
            if hit is not None:
                nearest = limit = hit
        return nearest

    def interaction_target(self, player, reach=2.6):
        origin, direction = view_ray(player)
        candidates = []
        for target in (*self.doors, *self.combat.pickups):
            distance = target.interaction_distance(origin, direction, reach)
            if distance is not None:
                candidates.append((distance, target))
        for distance, target in sorted(candidates, key=lambda item: item[0]):
            ignored = target if isinstance(target, Door) else None
            if self.line_clear(origin, direction, distance, ignore_door=ignored):
                return target
        return None

    def interact(self, player):
        target = self.interaction_target(player)
        if isinstance(target, Door):
            return [target.toggle()]
        if isinstance(target, WeaponPickup):
            return self.combat.collect(target, player, self)
        return [GameEvent("interaction_miss")]

    def update_doors(self, player, dt):
        return [event for door in self.doors if (event := door.update(player, dt)) is not None]

    def in_water(self, x: float, y: float, feet: float) -> bool:
        return feet < WATER_LEVEL and self.get(math.floor(x), math.floor(y), 0) == WATER

    @staticmethod
    def current(x: float) -> tuple[float, float]:
        # Downstream is east; its north/south component follows the river bends.
        slope = 0.288 * math.cos(x * 0.18) + 0.1935 * math.cos(x * 0.43)
        return 0.55, 0.55 * slope

    def area(self, x: float, y: float) -> str:
        from .map_expansion import expanded_area_name
        if self.outdoor_bounds and (name := expanded_area_name(x, y)):
            return name
        if self.outdoor_bounds:
            material = self.get(int(x), int(y), 0)
            if material == BRIDGE:
                return "TIMBER BRIDGE"
            if material == WATER:
                return "FLOWING RIVER"
            if abs(y - river_center(x)) < 5:
                return "RIVERBANK"
            return "NORTH MEADOW" if y > river_center(x) else "CASTLE MEADOW"
        return "THE COURTYARD"


def build_world() -> World:
    from .map_expansion import EXPANDED_DEPTH, EXPANDED_WIDTH, WORLD_HEIGHT, expand_world
    world = World.empty(EXPANDED_WIDTH, EXPANDED_DEPTH, WORLD_HEIGHT)
    world.outdoor_bounds = (1, 1, world.width - 1, world.depth - 1)
    world.box(0, 0, 0, world.width, world.depth, 1, GRASS)
    # A continuous river crosses the northern meadow. Its centerline derivative
    # still supplies both physical current and perspective-aligned water strokes.
    for x in range(world.width):
        center = river_center(x + 0.5)
        world.box(x, math.floor(center - 2.5), 0,
                  x + 1, math.ceil(center + 2.5), 1, WATER)
    expand_world(world)
    world.combat = make_training_combat()
    return world

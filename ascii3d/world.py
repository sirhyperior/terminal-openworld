"""Voxel architecture. Coordinates are X/east, Y/north, Z/up."""

from dataclasses import dataclass, field
import math

from .doors import Door
from .events import GameEvent
from .combat import CombatState, SwordPickup, make_training_combat
from .targeting import cylinder_hit, view_ray


AIR, STONE, FLOOR, METAL, CRATE, GRASS, WATER, WOOD, LEAVES, PATH, BRIDGE = range(11)
WATER_LEVEL = 0.68
RIVERBED_LEVEL = 0.12


def river_center(x: float) -> float:
    return 45.0 + 1.6 * math.sin(x * 0.18) + 0.45 * math.sin(x * 0.43)


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
                 radius: float = 0.22, height: float = 1.7) -> bool:
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
                or self.combat.collides(x, y, feet, radius, height))

    def line_clear(self, origin, direction, distance, ignore_door=None):
        """Exact voxel, swinging-panel and trunk occlusion before a target.

        A door may ignore its own leaves when being operated. Every other
        target, including attacks, sees those same leaves as opaque.
        """
        limit = max(0.0, distance - 1e-7)
        cell = [math.floor(value) for value in origin]
        steps = [1 if value >= 0 else -1 for value in direction]
        deltas = [abs(1 / value) if abs(value) > 1e-12 else math.inf
                  for value in direction]
        crossings = [((cell[i] + 1 - origin[i]) if steps[i] > 0
                      else (origin[i] - cell[i])) * deltas[i]
                     if math.isfinite(deltas[i]) else math.inf for i in range(3)]
        while True:
            if self.get(*cell) not in (AIR, WATER):
                return False
            axis = min(range(3), key=lambda i: crossings[i])
            if crossings[axis] >= limit:
                break
            cell[axis] += steps[axis]
            crossings[axis] += deltas[axis]
        for door in self.doors:
            if door is not ignore_door and any(panel.ray_hit(origin, direction, limit)
                                              for panel in door.panels):
                return False
        for tree in self.trees.values():
            if cylinder_hit(origin, direction, tree.x, tree.y, 1.0,
                            tree.radius, tree.height - 1.0, limit) is not None:
                return False
        return True

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
            return target.toggle()
        if isinstance(target, SwordPickup):
            return self.combat.collect(target, player)
        return GameEvent("interaction_miss")

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
        if self.outdoor_bounds and (y >= 29 or x >= 33):
            material = self.get(int(x), int(y), 0)
            if material == BRIDGE:
                return "TIMBER BRIDGE"
            if material == WATER:
                return "FLOWING RIVER"
            if abs(y - river_center(x)) < 5:
                return "RIVERBANK"
            return "NORTH MEADOW" if y > river_center(x) else "RIVER MEADOW"
        if y >= 21:
            return "NORTH GALLERY"
        if x >= 21:
            return "PILLAR HALL"
        if x <= 10 and y >= 11:
            return "THE CLOISTER"
        if y <= 9:
            return "SOUTH COURT"
        return "THE COURTYARD"


def build_world() -> World:
    from .map_expansion import EXPANDED_DEPTH, EXPANDED_WIDTH, expand_world
    world = World.empty(EXPANDED_WIDTH, EXPANDED_DEPTH, 10)
    world.outdoor_bounds = (1, 1, world.width - 1, world.depth - 1)
    world.box(0, 0, 0, world.width, world.depth, 1, GRASS)
    world.box(0, 0, 0, 33, 29, 1, FLOOR)

    # Perimeter, with taller towers at the four corners.
    world.box(0, 0, 1, 33, 1, 6)
    world.box(0, 28, 1, 33, 29, 6)
    world.box(0, 0, 1, 1, 29, 6)
    world.box(32, 0, 1, 33, 29, 6)
    for x in (1, 30):
        for y in (1, 26):
            world.box(x, y, 1, x + 2, y + 2, 8)

    # A central court reached through a broad, genuinely overhead arch.
    world.box(2, 10, 1, 22, 11, 5)
    world.box(12, 10, 1, 17, 11, 4, AIR)
    world.box(11, 10, 1, 12, 11, 6, METAL)
    world.box(17, 10, 1, 18, 11, 6, METAL)
    world.box(11, 10, 5, 18, 11, 6, METAL)

    # Windowed west cloister, two doorways, and an actual roof.
    world.box(10, 11, 1, 11, 23, 6)
    for y in (12, 19):
        world.box(10, y, 1, 11, y + 3, 4, AIR)
    world.box(10, 16, 3, 11, 18, 5, AIR)
    world.box(1, 11, 6, 11, 24, 7)
    for y in (13, 18, 22):
        world.box(4, y, 1, 5, y + 1, 6, METAL)

    # East hall: repeated pillars, lintels, windows, and a covered arcade.
    world.box(21, 4, 1, 22, 24, 6)
    for y in (5, 12, 20):
        world.box(21, y, 1, 22, y + 3, 4, AIR)
    for y in (9, 17):
        world.box(21, y, 3, 22, y + 2, 5, AIR)
    for y in (7, 13, 19, 25):
        for x in (24, 28):
            world.box(x, y, 1, x + 1, y + 1, 6, METAL)
        world.box(24, y, 5, 29, y + 1, 6, METAL)
    world.box(22, 4, 6, 32, 27, 7)

    # North gallery and side routes form a loop around the court.
    world.box(11, 23, 1, 22, 24, 5)
    world.box(14, 23, 1, 18, 24, 4, AIR)
    world.box(11, 23, 3, 13, 24, 4, AIR)
    world.box(19, 23, 3, 21, 24, 4, AIR)

    # Waist-high masonry and stacked crates can be jumped onto or over.
    world.box(13, 15, 1, 18, 16, 2)
    world.box(13, 16, 1, 14, 19, 2)
    world.box(17, 16, 1, 18, 19, 2)
    world.box(6, 5, 1, 8, 7, 2, CRATE)
    world.box(5, 6, 1, 6, 7, 3, CRATE)
    world.box(26, 23, 1, 28, 25, 2, CRATE)
    world.box(27, 24, 2, 28, 25, 3, CRATE)

    # Slender monuments make depth and face lighting readable from spawn.
    world.box(4, 8, 1, 5, 9, 5, METAL)
    world.box(19, 8, 1, 20, 9, 5, METAL)
    world.box(15, 26, 1, 16, 27, 5, METAL)

    # The north gate connects the original architecture to the open meadow.
    world.box(13, 28, 1, 20, 29, 5, AIR)
    world.box(12, 28, 1, 13, 29, 7, METAL)
    world.box(20, 28, 1, 21, 29, 7, METAL)
    world.box(12, 28, 6, 21, 29, 7, METAL)
    # Grass continues across the approaches instead of leaving bare path strips.

    # A continuous, gently meandering river flows west to east across the meadow.
    for x in range(world.width):
        center = river_center(x + 0.5)
        world.box(x, math.floor(center - 2.5), 0, x + 1, math.ceil(center + 2.5), 1, WATER)

    # A level plank deck spans both banks. Rails and posts have real collision.
    world.box(14, 39, 0, 19, 54, 1, BRIDGE)
    for x in (13, 19):
        world.box(x, 40, 1, x + 1, 53, 2, WOOD)
        for y in (40, 44, 48, 52):
            world.box(x, y, 1, x + 1, y + 1, 3, WOOD)

    # Curved crowns and thin trunks are rendered separately from the voxel grid.
    # Collision uses the same trunk radius; foliage is soft and non-solid.
    for seed, (x, y) in enumerate(((5, 34), (29, 34), (36, 38), (5, 56), (27, 57), (36, 54))):
        world.trees[x, y] = Tree(x + 0.5, y + 0.5, 0.18 + seed % 3 * 0.025,
                                 4.0 + seed % 3 * 0.22, seed)
    for x, y in ((7, 40), (26, 40), (32, 50), (9, 51), (24, 53)):
        if world.get(x, y, 0) == GRASS:
            world.box(x, y, 1, x + 1, y + 1, 2)
    world.doors = [Door("courtyard doors", 12.05, 10.5, 4.9),
                   Door("cloister door", 10.5, 12.05, 2.9, math.pi / 2, double=False),
                   Door("gallery doors", 14.05, 23.5, 3.9)]
    expand_world(world)
    world.combat = make_training_combat()
    return world

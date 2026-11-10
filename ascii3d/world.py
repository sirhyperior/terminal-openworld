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
    base_z: float = 1.0


class _TreeMap(dict):
    """Cell index with a conservative radius bound maintained on insertion."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.max_radius = 0.0
        self.update(*args, **kwargs)

    def __setitem__(self, key, tree):
        self.max_radius = max(self.max_radius, tree.radius)
        super().__setitem__(key, tree)

    def update(self, *args, **kwargs):
        for key, tree in dict(*args, **kwargs).items():
            self[key] = tree

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def clear(self):
        super().clear()
        self.max_radius = 0.0

    def __ior__(self, other):
        self.update(other)
        return self


@dataclass
class World:
    width: int
    depth: int
    height: int
    cells: bytearray
    outdoor_bounds: tuple[int, int, int, int] | None = None
    trees: dict[tuple[int, int], Tree] = field(default_factory=_TreeMap)
    revision: int = 0
    doors: list[Door] = field(default_factory=list)
    combat: CombatState = field(default_factory=CombatState)
    _surfaces: dict[tuple[int, int], tuple[int, int]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if not isinstance(self.trees, _TreeMap):
            self.trees = _TreeMap(self.trees)

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
        self._surfaces.clear()
        for z in range(max(0, z0), min(self.height, z1)):
            for y in range(max(0, y0), min(self.depth, y1)):
                left, right = max(0, x0), min(self.width, x1)
                if right > left:
                    offset = (z * self.depth + y) * self.width
                    self.cells[offset + left:offset + right] = bytes([material]) * (right - left)

    def _surface(self, x: float, y: float) -> tuple[int, int]:
        """Top voxel per queried column; edits invalidate this lazy cache."""
        cx, cy = math.floor(x), math.floor(y)
        if not (0 <= cx < self.width and 0 <= cy < self.depth):
            return 0, AIR
        key = cx, cy
        if key not in self._surfaces:
            offset, layer = cy * self.width + cx, self.width * self.depth
            surface = (0, AIR)
            for z in range(self.height - 1, -1, -1):
                material = self.cells[z * layer + offset]
                if material:
                    surface = z + 1, material
                    break
            self._surfaces[key] = surface
        return self._surfaces[key]

    def surface_height(self, x: float, y: float) -> int:
        return self._surface(x, y)[0]

    def surface_material(self, x: float, y: float) -> int:
        return self._surface(x, y)[1]

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
                if tree and feet < tree.height and feet + height > tree.base_z:
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
        # Tree keys already form a spatial index. Only cells intersecting the
        # segment's expanded bounds can contribute a trunk hit, regardless of
        # how many distant trees the enormous map contains.
        if not self.trees:
            return nearest
        if not isinstance(self.trees, _TreeMap):
            self.trees = _TreeMap(self.trees)
        padding = self.trees.max_radius
        end_x, end_y = origin[0] + direction[0] * limit, origin[1] + direction[1] * limit
        x0, x1 = math.floor(min(origin[0], end_x) - padding), math.floor(max(origin[0], end_x) + padding) + 1
        y0, y1 = math.floor(min(origin[1], end_y) - padding), math.floor(max(origin[1], end_y) + padding) + 1
        if (x1 - x0) * (y1 - y0) >= len(self.trees):
            candidates = self.trees.values()
        else:
            candidates = (tree for cy in range(y0, y1) for cx in range(x0, x1)
                          if (tree := self.trees.get((cx, cy))) is not None)
        for tree in candidates:
            hit = cylinder_hit(origin, direction, tree.x, tree.y, tree.base_z,
                               tree.radius, tree.height - tree.base_z, limit)
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
            from .terrain import terrain_area_name
            if name := terrain_area_name(x, y):
                return name
            if abs(y - river_center(x)) < 5:
                return "RIVERBANK"
            return "NORTH MEADOW" if y > river_center(x) else "CASTLE MEADOW"
        return "THE COURTYARD"


def build_world() -> World:
    from .map_expansion import EXPANDED_DEPTH, EXPANDED_WIDTH, WORLD_HEIGHT, expand_world
    world = World.empty(EXPANDED_WIDTH, EXPANDED_DEPTH, WORLD_HEIGHT)
    world.outdoor_bounds = (1, 1, world.width - 1, world.depth - 1)
    from .terrain import add_landmarks, build_terrain
    build_terrain(world)
    # A continuous river crosses the northern meadow. Its centerline derivative
    # still supplies both physical current and perspective-aligned water strokes.
    for x in range(world.width):
        center = river_center(x + 0.5)
        world.box(x, math.floor(center - 2.5), 0,
                  x + 1, math.ceil(center + 2.5), 1, WATER)
    expand_world(world)
    add_landmarks(world)
    world.combat = make_training_combat()
    return world

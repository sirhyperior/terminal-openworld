"""Voxel architecture. Coordinates are X/east, Y/north, Z/up."""

from dataclasses import dataclass, field
import math

from .doors import Door
from .events import GameEvent
from .combat import CombatState, WeaponPickup, make_training_combat
from .targeting import cylinder_hit, view_ray
from .map_expansion import INDOOR_SPAWN, OUTDOOR_SPAWN
from .surfaces import ConvexSolid, HeightField, SolidBox, circle_rect, grid_intervals


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
    heightfield: HeightField | None = field(default=None, repr=False)
    solids: list[SolidBox | ConvexSolid] = field(default_factory=list, repr=False)
    _solid_chunks: dict = field(default_factory=dict, repr=False)
    _stair_keys: set = field(default_factory=set, repr=False)
    _solid_query_cache: tuple | None = field(default=None, repr=False)

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
        if self.heightfield is not None:
            self.heightfield.edit_box(x0, y0, z0, x1, y1, z1, material)
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

    @property
    def geometry_present(self):
        return self.heightfield is not None or bool(self.solids)

    def add_solid(self, box: SolidBox | ConvexSolid):
        self.solids.append(box)
        # Include incident chunks for closed ray faces at exact grid corners.
        for cy in range(math.floor((box.y0 - 1e-8) / 8), math.floor((box.y1 + 1e-8) / 8) + 1):
            for cx in range(math.floor((box.x0 - 1e-8) / 8), math.floor((box.x1 + 1e-8) / 8) + 1):
                self._solid_chunks.setdefault((cx, cy), []).append(box)
        self.revision += 1
        return box

    def add_stair_flight(self, x0, y0, width, length, bottom, top, axis="y",
                         direction=1, riser=0.25, material=FLOOR):
        if width <= 0 or length <= 0 or riser <= 0 or top <= bottom or axis not in ("x", "y") or direction not in (-1, 1):
            raise ValueError("stairs require positive dimensions, rising height and an X/Y direction")
        key = (x0, y0, width, length, bottom, top, axis, direction, riser, material)
        if key in self._stair_keys:
            return ()
        self._stair_keys.add(key)
        count = math.ceil((top - bottom) / riser - 1e-9)
        boxes = []
        for step in range(count):
            start = step * length / count if direction > 0 else (count - 1 - step) * length / count
            end = start + length / count
            high = min(top, bottom + (step + 1) * riser)
            box = (SolidBox(x0, y0 + start, bottom, x0 + width, y0 + end, high, material, stair=True)
                   if axis == "y" else SolidBox(x0 + start, y0, bottom, x0 + end, y0 + width, high, material, stair=True))
            boxes.append(self.add_solid(box))
        return tuple(boxes)

    def _near_solids(self, x, y, radius=0):
        seen = set()
        for cy in range(math.floor((y - radius) / 8), math.floor((y + radius) / 8) + 1):
            for cx in range(math.floor((x - radius) / 8), math.floor((x + radius) / 8) + 1):
                for box in self._solid_chunks.get((cx, cy), ()):
                    identity = id(box)
                    if identity not in seen:
                        seen.add(identity)
                        yield box

    def geometry_hit(self, origin, direction, limit):
        hit = self.heightfield.ray_hit(origin, direction, limit) if self.heightfield is not None else None
        if hit is not None:
            limit = hit.distance
        solid = self._solid_hit(origin, direction, limit, self._solid_chunks)
        return solid if solid is not None else hit

    @staticmethod
    def _solid_hit(origin, direction, limit, chunks, start=0.0, size=8):
        hit = None
        if chunks:
            seen = set()
            for cx, cy, entry, _ in grid_intervals(origin[0], origin[1], direction[0], direction[1], start, limit, size):
                if entry > limit + 1e-8:
                    break
                for box in chunks.get((cx, cy), ()):
                    identity = id(box)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    candidate = box.ray_hit(origin, direction, limit)
                    if candidate is not None:
                        hit, limit = candidate, candidate.distance
        return hit

    @staticmethod
    def _solid_tree_hit(origin, direction, limit, tree):
        """Trace bounded solid groups; report ties for the existing grid path."""
        hit, tied = None, False
        stack = [tree]
        while stack:
            bounds, left, right, boxes = stack.pop()
            if bounds.ray_entry(origin, direction, limit) is None:
                continue
            if boxes:
                for box in boxes:
                    candidate = box.ray_hit(origin, direction, limit)
                    if candidate is not None:
                        if hit is not None and abs(candidate.distance - hit.distance) <= 1e-8:
                            tied = True
                        hit, limit = candidate, candidate.distance
            else:
                # The spatial split's nearer side is likely to produce the
                # first hit. Its exact depth then bounds every later group.
                left_bounds, right_bounds = left[0], right[0]
                if ((left_bounds.x0 + left_bounds.x1 - right_bounds.x0 - right_bounds.x1) * direction[0]
                        + (left_bounds.y0 + left_bounds.y1 - right_bounds.y0 - right_bounds.y1) * direction[1]
                        + (left_bounds.z0 + left_bounds.z1 - right_bounds.z0 - right_bounds.z1) * direction[2]) <= 0:
                    stack.extend((right, left))
                else:
                    stack.extend((left, right))
        return hit, tied

    def geometry_query(self, bounds, planes):
        """Conservative once-per-view selection; exact rays retain final say."""
        x0, y0, x1, y1 = bounds
        planes = tuple(planes)

        def visible(box):
            if box.x1 < x0 or box.x0 > x1 or box.y1 < y0 or box.y0 > y1:
                return False
            return all(nx * (box.x1 if nx >= 0 else box.x0)
                       + ny * (box.y1 if ny >= 0 else box.y0)
                       + nz * (box.z1 if nz >= 0 else box.z0) + offset >= -1e-7
                       for nx, ny, nz, offset in planes)

        def enclosing(boxes):
            if not boxes:
                return None
            return SolidBox(min(b.x0 for b in boxes), min(b.y0 for b in boxes), min(b.z0 for b in boxes),
                            max(b.x1 for b in boxes), max(b.y1 for b in boxes), max(b.z1 for b in boxes))

        def tree_for(boxes):
            bounds = enclosing(boxes)
            if len(boxes) <= 4:
                return bounds, None, None, tuple(boxes)
            spans = bounds.x1 - bounds.x0, bounds.y1 - bounds.y0, bounds.z1 - bounds.z0
            axis = max(range(3), key=spans.__getitem__)
            ordered = sorted(boxes, key=(lambda b: b.x0 + b.x1, lambda b: b.y0 + b.y1,
                                         lambda b: b.z0 + b.z1)[axis])
            middle = len(ordered) // 2
            return bounds, tree_for(ordered[:middle]), tree_for(ordered[middle:]), ()

        selected = [box for box in self.solids if visible(box)]
        selection_key = self.revision, tuple(id(box) for box in selected)
        if self._solid_query_cache is not None and self._solid_query_cache[0] == selection_key:
            _, chunks, solid_cell_size, solid_tree = self._solid_query_cache
        else:
            # Fine tread cells avoid testing an entire eight-unit flight at
            # every ray crossing. Bound index construction for generic boxes.
            ranges = [(math.floor(box.x0 - 1e-8), math.floor(box.y0 - 1e-8),
                       math.floor(box.x1 + 1e-8), math.floor(box.y1 + 1e-8), box)
                      for box in selected]
            work = sum((rx1 - rx0 + 1) * (ry1 - ry0 + 1) for rx0, ry0, rx1, ry1, _ in ranges)
            chunks = {}
            if work <= 2048:
                solid_cell_size = 1
                for rx0, ry0, rx1, ry1, box in ranges:
                    for y in range(ry0, ry1 + 1):
                        for x in range(rx0, rx1 + 1):
                            chunks.setdefault((x, y), []).append(box)
            else:
                solid_cell_size = 8
                selected_ids = set(selection_key[1])
                for key, boxes in self._solid_chunks.items():
                    candidates = [box for box in boxes if id(box) in selected_ids]
                    if candidates:
                        chunks[key] = candidates
            solid_tree = tree_for(selected) if len(selected) > 8 else None
            self._solid_query_cache = selection_key, chunks, solid_cell_size, solid_tree
        solid_bounds = enclosing(selected)
        ground_boxes = []
        ground = self.heightfield
        if ground is not None:
            for cy in range(max(0, math.floor(y0 / 8)), min((ground.depth + 7) // 8, math.floor(y1 / 8) + 1)):
                for cx in range(max(0, math.floor(x0 / 8)), min((ground.width + 7) // 8, math.floor(x1 / 8) + 1)):
                    low, high = ground._chunk_bounds(cx, cy)
                    if low == math.inf:
                        continue
                    box = SolidBox(cx * 8, cy * 8, 0, min(ground.width, (cx + 1) * 8),
                                   min(ground.depth, (cy + 1) * 8), high)
                    if visible(box):
                        ground_boxes.append(box)
        ground_bounds = enclosing(ground_boxes)
        if solid_bounds is None and ground_bounds is None:
            return None

        def query(origin, direction, limit):
            hit = None
            if ground_bounds is not None:
                end_z = origin[2] + direction[2] * limit
                if min(origin[2], end_z) <= ground_bounds.z1 + 1e-7:
                    entry = ground_bounds.ray_entry(origin, direction, limit)
                    if entry is not None:
                        hit = ground.ray_hit(origin, direction, limit, minimum=entry)
                        if hit is not None:
                            limit = hit.distance
            if solid_bounds is not None:
                end_z = origin[2] + direction[2] * limit
                if (min(origin[2], end_z) <= solid_bounds.z1 + 1e-7
                        and max(origin[2], end_z) >= solid_bounds.z0 - 1e-7):
                    entry = solid_bounds.ray_entry(origin, direction, limit)
                    if entry is not None:
                        if solid_tree is not None:
                            solid, tied = self._solid_tree_hit(origin, direction, limit, solid_tree)
                        else:
                            solid, tied = None, True
                        if tied:
                            # Preserve the grid's original coincident-face
                            # order, including configured overlapping solids.
                            solid = self._solid_hit(origin, direction, limit, chunks, entry, solid_cell_size)
                        if solid is not None:
                            hit = solid
            return hit

        query.bounds = (*selected, *ground_boxes)
        query.minimum_depth = 0.0
        if len(planes) >= 2:
            nx, ny, nz, offset = planes[-2]
            far = planes[-1]
            if (abs(nx * nx + ny * ny + nz * nz - 1.0) < 1e-8
                    and (nx, ny, nz) == tuple(-value for value in far[:3])):
                # Camera rays have unit forward component. This nearest AABB
                # support plane bounds their original, unnormalized parameter.
                minimum = min(nx * (box.x0 if nx >= 0 else box.x1)
                              + ny * (box.y0 if ny >= 0 else box.y1)
                              + nz * (box.z0 if nz >= 0 else box.z1) + offset
                              for box in (*selected, *ground_boxes))
                query.minimum_depth = max(0.0, minimum - 1e-7)
        return query

    def _point_surface(self, x, y):
        top, material = self._surface(x, y)
        if self.heightfield is not None:
            ground = self.heightfield.height_at(x, y)
            if ground is not None and ground >= top - 1e-8:
                top, material = ground, self.heightfield.material_at(x, y)
        for box in self._near_solids(x, y):
            if isinstance(box, SolidBox):
                if box.x0 <= x < box.x1 and box.y0 <= y < box.y1 and box.z1 > top:
                    top, material = box.z1, box.material
            else:
                for surface, kind in box.footprint(x, y, 0.0):
                    if surface > top:
                        top, material = surface, kind
        return top, material

    def surface_height(self, x: float, y: float) -> float:
        return self._point_surface(x, y)[0]

    def surface_material(self, x: float, y: float) -> int:
        return self._point_surface(x, y)[1]

    def _contact_surfaces(self, x, y, feet, radius, max_rise, max_drop, *, walking=False):
        low, high = feet - max_drop, feet + max_rise
        if self.heightfield is not None:
            for top, material in self.heightfield.footprint(x, y, radius):
                if low - 1e-7 <= top <= high + 1e-7:
                    yield top, material
        for box in self._near_solids(x, y, radius):
            if isinstance(box, SolidBox):
                if walking and not box.stair and box.z1 > feet + 1e-7:
                    continue
                if low - 1e-7 <= box.z1 <= high + 1e-7 and circle_rect(x, y, radius, box.x0, box.y0, box.x1, box.y1):
                    yield box.z1, box.material
            else:
                for top, material in box.footprint(x, y, radius):
                    if walking and top > feet + 1e-7:
                        continue
                    if low - 1e-7 <= top <= high + 1e-7:
                        yield top, material
        for cy in range(math.floor(y - radius), math.floor(y + radius) + 1):
            for cx in range(math.floor(x - radius), math.floor(x + radius) + 1):
                if not circle_rect(x, y, radius, cx, cy, cx + 1, cy + 1):
                    continue
                for top in range(math.ceil(low - 1e-7), math.floor(high + 1e-7) + 1):
                    if walking and top > feet + 1e-7:
                        continue
                    material = self.get(cx, cy, top - 1)
                    if material not in (AIR, WATER):
                        yield float(top), material

    def walk_support(self, x, y, feet, radius=0.22, max_rise=0.5, max_drop=0.5, *, walking=False):
        """Find support; walking may rise only on terrain or authored treads.

        Generic queries retain all surfaces for item placement and camera
        settling. Ordinary solids still support standing, descent and landing.
        """
        allowed = (STONE, FLOOR, GRASS, PATH)
        return max((pair for pair in self._contact_surfaces(x, y, feet, radius, max_rise, max_drop, walking=walking)
                    if pair[1] in allowed or pair[0] <= feet + 1e-7), default=None)

    def terrain_walkable(self, x, y, radius=0.22, feet=None):
        if self.heightfield is None:
            return True
        return not any(grade > 1.0 + 1e-9 and (feet is None or abs(top - feet) <= 0.06)
                       for top, _, grade in self.heightfield.footprint(x, y, radius, with_grade=True))

    def contact_material(self, x, y, feet, radius=0.22, tolerance=0.06):
        # Preserve the existing voxel/door Foley resolver's center precedence.
        contacts = []
        if self.heightfield is not None:
            contacts.extend((top, material) for top, material in self.heightfield.footprint(x, y, radius)
                            if abs(top - feet) <= tolerance)
        for box in self._near_solids(x, y, radius):
            if isinstance(box, SolidBox):
                if abs(box.z1 - feet) <= tolerance and circle_rect(x, y, radius, box.x0, box.y0, box.x1, box.y1):
                    contacts.append((box.z1, box.material))
            else:
                contacts.extend((top, material) for top, material in box.footprint(x, y, radius)
                                if abs(top - feet) <= tolerance)
        contact = max(contacts, default=None)
        return contact[1] if contact is not None else None

    def step_contact(self, x, y, feet, radius=0.22):
        return any(box.stair and abs(box.z1 - feet) < 1e-5 and circle_rect(x, y, radius, box.x0, box.y0, box.x1, box.y1)
                   for box in self._near_solids(x, y, radius))

    def collides(self, x: float, y: float, feet: float,
                 radius: float = 0.22, height: float = 1.7,
                 ignore_enemy=None) -> bool:
        # Water is a volume to wade through, with an implicit shallow riverbed.
        if x - radius < 0 or y - radius < 0:
            return True
        if x + radius > self.width or y + radius > self.depth or feet < RIVERBED_LEVEL - 1e-7:
            return True
        if self.heightfield is not None and any(feet < top - 1e-7 for top, _ in self.heightfield.footprint(x, y, radius)):
            return True
        if any(box.overlaps(x, y, feet, radius, height) for box in self._near_solids(x, y, radius)):
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
        geometry = self.geometry_hit(origin, direction, limit) if self.geometry_present else None
        if geometry is not None:
            limit = geometry.distance
        cell = [math.floor(value) for value in origin]
        steps = [1 if value >= 0 else -1 for value in direction]
        deltas = [abs(1 / value) if abs(value) > 1e-12 else math.inf
                  for value in direction]
        crossings = [((cell[i] + 1 - origin[i]) if steps[i] > 0
                      else (origin[i] - cell[i])) * deltas[i]
                     if math.isfinite(deltas[i]) else math.inf for i in range(3)]
        travelled, nearest = 0.0, geometry.distance if geometry is not None else None
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
    if world.heightfield is not None:
        world.heightfield.prepare()
    world.combat = make_training_combat()
    return world

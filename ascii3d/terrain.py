"""Continuous highlands and shared fine stairs beyond the original castle hub."""

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .world import World


HUB_SIZE = 112  # Quiet southwest lowland, retained for small fixture worlds.
CANYON_BOUNDS = (270, 294, 350, 346)
from .map_expansion import FIRST_BRIDGE_BOUNDS, EAST_BRIDGE_BOUNDS

NEW_BRIDGES = ((388, 207, 393, 231),)
RIVER_BRIDGES = (FIRST_BRIDGE_BOUNDS, EAST_BRIDGE_BOUNDS, *NEW_BRIDGES)
RAVINE_BRIDGE = (294, 304, 326, 309, 9)


@dataclass(frozen=True, slots=True)
class Landmark:
    name: str
    bounds: tuple[int, int, int, int]
    base: int
    angle: float = 0.0

    def to_world(self, x: float, y: float) -> tuple[float, float]:
        cx, cy = (self.bounds[0] + self.bounds[2]) / 2, (self.bounds[1] + self.bounds[3]) / 2
        c, s = math.cos(self.angle), math.sin(self.angle)
        return cx + c * (x - cx) - s * (y - cy), cy + s * (x - cx) + c * (y - cy)

    def to_local(self, x: float, y: float) -> tuple[float, float]:
        cx, cy = (self.bounds[0] + self.bounds[2]) / 2, (self.bounds[1] + self.bounds[3]) / 2
        c, s = math.cos(self.angle), math.sin(self.angle)
        return cx + c * (x - cx) + s * (y - cy), cy - s * (x - cx) + c * (y - cy)

    @property
    def world_bounds(self):
        x0, y0, x1, y1 = self.bounds
        points = [self.to_world(x, y) for x in (x0 - 3, x1 + 6) for y in (y0 - 3, y1 + 3)]
        return min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points)

    @property
    def floors(self) -> tuple[int, int, int]:
        return self.base, self.base + 5, self.base + 10

    @property
    def roof(self) -> int:
        return self.base + 15


LANDMARKS = (
    Landmark("THORNWATCH", (292, 120, 316, 144), 7, math.radians(17)),
    Landmark("BLACK ABBEY", (202, 344, 230, 376), 4),
    Landmark("ASTRAL RELIQUARY", (374, 270, 402, 298), 10, math.radians(-23)),
    Landmark("MOURNING CITADEL", (402, 416, 438, 456), 12),
)

# All endpoints lie on dry, open approaches. Junctions form a six-site loop,
# with an Ashgate-Abbey shortcut and a stone bridge across the riven valley.
ROUTE_WAYPOINTS = (
    ((152, 93), (170, 93), (230, 104), (270, 110), (304, 110), (304, 120)),
    ((304, 144), (304, 193), (304, 213), (330, 240), (388, 252), (388, 270)),
    ((388, 298), (388, 306), (388, 340), (420, 390), (420, 416)),
    ((402, 436), (370, 436), (300, 406), (250, 388), (216, 388), (216, 376)),
    ((202, 360), (160, 340), (120, 300), (88, 272), (72, 260), (72, 254)),
    ((72, 242), (72, 236), (88, 236), (88, 231), (88, 211), (88, 160), (128, 136), (128, 120)),
    ((128, 120), (128, 156), (150, 180), (150, 200), (88, 200), (88, 211)),
    ((88, 231), (110, 250), (160, 300), (190, 320), (216, 332), (216, 344)),
    ((230, 360), (250, 360), (270, 306), (294, 306), (326, 306), (350, 306), (388, 306)),
    ((128, 60), (128, 72)),
    ((103, 93), (88, 93), (88, 84)),
    ((41, 242), (41, 238), (55, 238), (55, 248), (63, 248)),
    ((128, 120), (128, 136)),
)


_ROTATED_NODES = {(304, 110): LANDMARKS[0], (304, 120): LANDMARKS[0],
                  (304, 144): LANDMARKS[0], (388, 252): LANDMARKS[2],
                  (388, 270): LANDMARKS[2], (388, 298): LANDMARKS[2],
                  (388, 306): LANDMARKS[2]}
ROUTE_WAYPOINTS = tuple(tuple(tuple(value - .5 for value in _ROTATED_NODES[node].to_world(node[0] + .5, node[1] + .5))
                                  if node in _ROTATED_NODES else node for node in route)
                        for route in ROUTE_WAYPOINTS)


def _smooth_blend(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def terrain_height(x: float, y: float) -> float:
    """Return repeatable natural elevation, retaining the hub and river valley."""
    from .world import river_center

    if x <= HUB_SIZE and y <= HUB_SIZE:
        return 1.0
    # Preserve the river's low valley across the entire enlarged map. Its
    # centerline is shared with currents and the renderer, not approximated.
    river_distance = abs(y - river_center(x))
    river_blend = _smooth_blend((river_distance - 16) / 36)
    hub_blend = _smooth_blend(max(x - HUB_SIZE, y - HUB_SIZE) / 30)
    hills = (8 + 3.0 * math.sin(x / 38) + 2.5 * math.cos(y / 49)
             + 2.0 * math.sin((x + y) / 71))
    ridge = 6 * _smooth_blend(1 - abs(x - 320 - 0.28 * (y - 200)) / 90)
    valley = 5 * _smooth_blend(1 - abs(x - 150 - 0.18 * y) / 40)
    height = 1 + hub_blend * river_blend * max(0.0, hills + ridge - valley)

    # A scar in the uplands has one authored dry crossing. Its approaches
    # blend to the deck, while the trench and sheer sides remain below it.
    x0, y0, x1, y1 = CANYON_BOUNDS
    if x0 <= x <= x1 and y0 <= y <= y1:
        cross = abs(x - 310)
        ends = _smooth_blend(min((y - y0) / 12, (y1 - y) / 12))
        crossing = (_smooth_blend(1 - abs(y - 306) / 14)
                    * _smooth_blend(min((x - x0) / 12, (x1 - x) / 12))
                    * _smooth_blend(min((y - y0) / 8, (y1 - y) / 8)))
        height = height * (1 - crossing) + 9 * crossing
        height -= 12 * _smooth_blend(1 - cross / 16) * ends

    pads = [(landmark.bounds, landmark.base, landmark) for landmark in LANDMARKS]
    pads += [((98, 58, 161, 128), 1, None), ((31, 223, 100, 274), 1, None)]
    for bounds, base, landmark in pads:
        x0, y0, x1, y1 = bounds
        lx, ly = landmark.to_local(x, y) if landmark is not None and landmark.angle else (x, y)
        distance = max(x0 - 4 - lx, lx - (x1 + 6), y0 - 4 - ly, ly - (y1 + 3), 0)
        if distance < 36:
            blend = _smooth_blend(distance / 36)
            height = base * (1 - blend) + height * blend
    return max(1.0, min(20.0, height))


def build_terrain(world: "World") -> None:
    """Sample continuous ground once, with conservative solid voxel foundations."""
    from .surfaces import HeightField
    from .world import GRASS, STONE

    stride = world.width + 1
    heights = [terrain_height(x, y)
               for y in range(world.depth + 1) for x in range(world.width + 1)]
    field = HeightField(world.width, world.depth, heights, material=GRASS)
    for y in range(world.depth):
        offset = y * stride
        foundations = [math.floor(min(heights[offset + x], heights[offset + x + 1],
                                      heights[offset + stride + x], heights[offset + stride + x + 1]))
                       for x in range(world.width)]
        for x, height in enumerate(foundations):
            if (heights[offset + x] == height == heights[offset + x + 1]
                    == heights[offset + stride + x] == heights[offset + stride + x + 1]):
                # The grass voxel already represents this exact constant plane.
                # Retain every vertex for adjoining fractional surface cells.
                field.enabled[y * world.width + x] = 0
        left = 0
        while left < world.width:
            height = foundations[left]
            right = left + 1
            while right < world.width and foundations[right] == height:
                right += 1
            if height > 1:
                world.box(left, y, 0, right, y + 1, height - 1, STONE)
            world.box(left, y, height - 1, right, y + 1, height, GRASS)
            left = right
    # Attach after filling: foundation voxel edits must not cut the surface.
    world.heightfield = field


def _road_cells():
    """Rasterize connected three-cell-wide routes once during construction."""
    cells = set()
    for route in ROUTE_WAYPOINTS:
        for (x0, y0), (x1, y1) in zip(route, route[1:]):
            length = math.ceil(max(abs(x1 - x0), abs(y1 - y0), 1))
            for step in range(length + 1):
                x = round(x0 + (x1 - x0) * step / length)
                y = round(y0 + (y1 - y0) * step / length)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        cells.add((x + dx, y + dy))
    return cells


def stair_routes(landmark: Landmark):
    """Return approach/landing waypoints for three north-facing stair flights."""
    x0, y0, x1, y1 = landmark.bounds
    return ((x0 + 4.5, y0 + 1.5, y0 + 13.0, landmark.base),
            (x1 - 4.5, y0 + 1.5, y0 + 13.0, landmark.base + 5),
            (x0 + 4.5, y1 - 14.0, y1 - 2.0, landmark.base + 10))


def _building(world: "World", landmark: Landmark) -> None:
    from .architecture import build_landmark

    build_landmark(world, landmark)


def add_landmarks(world: "World") -> None:
    """Connect the highlands, configure shared halls, and plant sparse trees."""
    from .world import AIR, BRIDGE, GRASS, PATH, WOOD, Tree

    roads = _road_cells()
    from .roads import RoadNetwork
    world.roads = RoadNetwork(tuple(tuple((x + .5, y + .5) for x, y in route)
                                    for route in ROUTE_WAYPOINTS))
    world.revision += 1
    for x0, y0, x1, y1 in RIVER_BRIDGES:
        if x1 > world.width or y1 > world.depth:
            continue
        world.box(x0, y0, 0, x1, y1, 1, BRIDGE)
        world.box(x0, y0, 1, x1, y1, 4, AIR)
        for x in (x0 - 1, x1):
            world.box(x, y0 + 1, 1, x + 1, y1 - 1, 2, WOOD)
            for y in range(y0 + 1, y1 - 1, 4):
                world.box(x, y, 1, x + 1, y + 1, 3, WOOD)
    x0, y0, x1, y1, deck = RAVINE_BRIDGE
    if x1 < world.width and y1 < world.depth:
        world.box(x0, y0, deck - 1, x1, y1, deck, BRIDGE)
        world.box(x0, y0, deck, x1, y1, world.height, AIR)
        for y in (y0 - 1, y1):
            world.box(x0, y, deck, x1, y + 1, deck + 1, WOOD)
        # Slender piers descend into the trench; the deck is the only crossing.
        for x in (300, 319):
            world.box(x, y0, 1, x + 1, y1, deck - 1)
    for landmark in LANDMARKS:
        if (landmark.bounds[2] + 6 < world.width and landmark.bounds[3] + 3 < world.depth
                and landmark.roof + 2 <= world.height):
            _building(world, landmark)
    # Sparse wind-worn outcrops use real irregular surfaces, not square props.
    from .rocks import add_rock
    for seed, (x, y, width, depth, height) in enumerate((
            (183.5, 122.5, 5, 4, 2.6), (264.5, 153.5, 4, 3, 2.1),
            (284.5, 287.5, 5, 4, 3), (337.5, 331.5, 4, 5, 2.8),
            (204.5, 391.5, 5, 3, 2.5), (96.5, 266.5, 3, 4, 1.8),
            (58.5, 270.5, 4, 3, 1.7), (145.5, 99.5, 3, 3, 1.5))):
        if not (width < x < world.width - width and depth < y < world.depth - depth):
            continue
        if world.surface_material(x, y) != GRASS:
            continue
        bottom = min(world.surface_height(x + dx, y + dy)
                     for dx in (-width / 2, 0, width / 2)
                     for dy in (-depth / 2, 0, depth / 2)) - 0.25
        add_rock(world, x, y, bottom, width, depth, height, seed=seed)
    # Coarse seeded patches keep the enormous landscape populated without
    # turning collision/targeting into a global, per-frame generation job.
    for gy in range(9, world.depth - 5, 12):
        for gx in range(9, world.width - 5, 12):
            seed = (gx * 73856093 ^ gy * 19349663) & 0xFFFFFFFF
            if seed % 5 == 0:
                continue
            x, y = gx + seed % 5 - 2, gy + (seed >> 4) % 5 - 2
            if (101 <= x < 156 and 69 <= y < 123
                    or 33 <= x < 49 and 241 <= y < 257
                    or 54 <= x < 84 and 226 <= y < 255):
                continue
            px, py = x + 0.5, y + 0.5
            feet = world.surface_height(px, py)
            if (x, y) in roads or world.surface_material(px, py) != GRASS:
                continue
            world.trees[x, y] = Tree(px, py, 0.18 + seed % 3 * 0.02,
                                    feet + 3.5 + seed % 5 * 0.2, seed, base_z=feet)
    for gx in range(26, 111, 7):
        for gy in range(219, 282, 7):
            seed = (gx * 73856093 ^ gy * 19349663) & 0xFFFFFFFF
            x, y = gx + seed % 3, gy + (seed >> 4) % 3
            if (x, y) in roads or (33 <= x < 49 and 241 <= y < 257) or (54 <= x < 84 and 226 <= y < 255):
                continue
            if world.surface_material(x + .5, y + .5) != GRASS:
                continue
            feet = world.surface_height(x + .5, y + .5)
            world.trees[x, y] = Tree(x + .5, y + .5, .20, feet + 4.5 + seed % 4 * .3, seed, base_z=feet)
    from .map_expansion import CLOSE_TREE
    x, y = CLOSE_TREE
    if x < world.width and y < world.depth and world.surface_material(x, y) == GRASS:
        feet = world.surface_height(x, y)
        world.trees[int(x), int(y)] = Tree(x, y, .20, feet + 4.0, 0, base_z=feet)


def terrain_area_name(x: float, y: float) -> str | None:
    from .world import river_center

    for landmark in LANDMARKS:
        x0, y0, x1, y1 = landmark.bounds
        lx, ly = landmark.to_local(x, y)
        if x0 - 3 <= lx < x1 + 6 and y0 - 3 <= ly < y1 + 3:
            return landmark.name
    if x < HUB_SIZE and y < HUB_SIZE:
        return None
    for bounds, name in zip(RIVER_BRIDGES, ("GRAVEWOOD BRIDGE", "THORN BRIDGE", "RELIQUARY BRIDGE")):
        x0, y0, x1, y1 = bounds
        if x0 <= x < x1 and y0 <= y < y1:
            return name
    x0, y0, x1, y1, _ = RAVINE_BRIDGE
    if x0 <= x < x1 and y0 <= y < y1:
        return "RIVEN BRIDGE"
    if abs(y - river_center(x)) < 8:
        return None
    x0, y0, x1, y1 = CANYON_BOUNDS
    if x0 <= x < x1 and y0 <= y < y1:
        return "THE RIVEN VALE"
    if x > 350 and y > 330:
        return "MOURNING HIGHLANDS"
    if y > 300:
        return "ASHEN UPLANDS"
    if y > 140:
        return "GRAVE HIGHLANDS"
    return "THORN RIDGES"

"""Deterministic highlands, roads and reusable buildings beyond the castle hub.

Everything remains ordinary editable voxels. Heights describe supported feet,
not a second collision surface, so terrain, floors, stairs and Foley agree.
"""

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .world import World


HUB_SIZE = 112
CANYON_BOUNDS = (270, 250, 350, 330)
NEW_BRIDGES = ((224, 80, 229, 94), (395, 80, 400, 94))


@dataclass(frozen=True, slots=True)
class Landmark:
    name: str
    bounds: tuple[int, int, int, int]
    base: int

    @property
    def floors(self) -> tuple[int, int, int]:
        return self.base, self.base + 5, self.base + 10

    @property
    def roof(self) -> int:
        return self.base + 15


LANDMARKS = (
    Landmark("RIDGE HALL", (136, 40, 160, 64), 5),
    Landmark("NORTHERN KEEP", (66, 190, 92, 216), 7),
    Landmark("HILL OBSERVATORY", (214, 178, 238, 202), 10),
    Landmark("FAR CITADEL", (382, 372, 412, 402), 12),
)

# Roads join existing dry hub routes to open arches in the new landmarks.
# Each polyline endpoint is a route junction or building entrance.
ROUTE_WAYPOINTS = (
    ((88, 48), (88, 57), (108, 57), (124, 52), (136, 52)),
    ((160, 52), (226, 52), (226, 144), (226, 178)),
    ((226, 52), (330, 52), (397, 52), (397, 144), (397, 300), (397, 372)),
    ((66, 103), (71, 103), (71, 113), (55, 113), (55, 144), (79, 144), (79, 190)),
    ((92, 203), (150, 203), (180, 190), (214, 190)),
    ((238, 190), (300, 190), (397, 300)),
    ((79, 216), (79, 330), (112, 352), (318, 352), (382, 387)),
    ((318, 352), (318, 450), (450, 450), (450, 170), (397, 170)),
)


def terrain_height(x: float, y: float) -> int:
    """Return a seeded-looking, repeatable terrace height without random state."""
    from .world import river_center

    if x < HUB_SIZE and y < HUB_SIZE:
        return 1
    # Preserve the river's low valley across the entire enlarged map. Its
    # centerline is shared with currents and the renderer, not approximated.
    river_distance = abs(y - river_center(x))
    river_blend = max(0.0, min(1.0, (river_distance - 8) / 18))
    hub_blend = max(0.0, min(1.0, max(x - 111, y - 111) / 30))
    hills = (8 + 3.0 * math.sin(x / 38) + 2.5 * math.cos(y / 49)
             + 2.0 * math.sin((x + y) / 71))
    ridge = 6 * max(0.0, 1 - abs(x - 320 - 0.28 * (y - 200)) / 90)
    valley = 5 * max(0.0, 1 - abs(x - 150 - 0.18 * y) / 40)
    height = 1 + hub_blend * river_blend * max(0.0, hills + ridge - valley)

    # A narrow ravine has steep sides and gradual entrances at either end.
    x0, y0, x1, y1 = CANYON_BOUNDS
    if x0 <= x < x1 and y0 <= y < y1:
        cross = abs(x - 310 + 0.5 * (y - 290))
        ends = max(0.0, min(1.0, (y - y0) / 16, (y1 - y) / 16))
        height -= 12 * max(0.0, 1 - cross / 8) * ends

    # Blend the hillside into supported building pads; no isolated vertical
    # plinth forces a jump or traps a player at an entrance.
    for landmark in LANDMARKS:
        x0, y0, x1, y1 = landmark.bounds
        distance = max(x0 - 4 - x, x - (x1 + 6), y0 - 4 - y, y - (y1 + 3), 0)
        if distance < 18:
            blend = distance / 18
            height = landmark.base * (1 - blend) + height * blend
    return max(1, min(20, math.floor(height + 0.5)))


def build_terrain(world: "World") -> None:
    """Fill columns in equal-height row runs through the normal voxel editor."""
    from .world import GRASS, STONE

    for y in range(world.depth):
        left = 0
        while left < world.width:
            height = terrain_height(left + 0.5, y + 0.5)
            right = left + 1
            while (right < world.width
                   and terrain_height(right + 0.5, y + 0.5) == height):
                right += 1
            if height > 1:
                world.box(left, y, 0, right, y + 1, height - 1, STONE)
            world.box(left, y, height - 1, right, y + 1, height, GRASS)
            left = right


def _road_cells():
    """Rasterize connected three-cell-wide routes once during construction."""
    cells = set()
    for route in ROUTE_WAYPOINTS:
        for (x0, y0), (x1, y1) in zip(route, route[1:]):
            length = max(abs(x1 - x0), abs(y1 - y0), 1)
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
    return ((x0 + 4.5, y0 + 3.0, y0 + 10.0, landmark.base),
            (x1 - 4.5, y0 + 3.0, y0 + 10.0, landmark.base + 5),
            (x0 + 4.5, y1 - 10.0, y1 - 3.0, landmark.base + 10))


def _building(world: "World", landmark: Landmark) -> None:
    """One shared three-storey hall, configured by bounds and floor elevation."""
    from .world import AIR, FLOOR, METAL, PATH, STONE, WOOD

    x0, y0, x1, y1 = landmark.bounds
    base, roof = landmark.base, landmark.roof
    center_x, center_y = (x0 + x1) // 2, (y0 + y1) // 2
    world.box(x0 - 3, y0 - 3, 0, x1 + 6, y1 + 3, base, STONE)
    world.box(x0 - 3, y0 - 3, base - 1, x1 + 6, y1 + 3, base, PATH)
    world.box(x0 - 3, y0 - 3, base, x1 + 6, y1 + 3, world.height, AIR)
    for bounds in ((x0, y0, x1, y0 + 1), (x0, y1 - 1, x1, y1),
                   (x0, y0 + 1, x0 + 1, y1 - 1), (x1 - 1, y0 + 1, x1, y1 - 1)):
        ax, ay, bx, by = bounds
        world.box(ax, ay, base, bx, by, roof, STONE)
    for feet in (*landmark.floors, roof):
        world.box(x0 + 1, y0 + 1, feet - 1, x1 - 1, y1 - 1, feet,
                  FLOOR if feet == base else WOOD)
    # Open arches are passageways, not exceptional doors or new interactions.
    for x in (x0, x1 - 1):
        world.box(x, center_y - 2, base, x + 1, center_y + 3, base + 3, AIR)
    for y in (y0, y1 - 1):
        world.box(center_x - 2, y, base, center_x + 3, y + 1, base + 3, AIR)
    for feet in landmark.floors:
        for x in (x0, x1 - 1):
            for y in (y0 + 4, y1 - 7):
                world.box(x, y, feet + 1, x + 1, y + 3, feet + 4, AIR)
        for y in (y0, y1 - 1):
            for x in (x0 + 5, x1 - 8):
                world.box(x, y, feet + 1, x + 3, y + 1, feet + 4, AIR)
    # Each five-step flight opens the slab above it. Other floor regions remain
    # solid; the player can circle to the next staircase on the new storey.
    for cx, start_y, _, feet in stair_routes(landmark):
        sx, sy = math.floor(cx) - 1, round(start_y + 1)
        world.box(sx, sy - 1, feet + 4, sx + 3, sy + 4, feet + 5, AIR)
        for step in range(5):
            world.box(sx, sy + step, feet, sx + 3, sy + step + 1,
                      feet + step + 1, FLOOR)
    # First-floor balcony with an open upper arch and a continuous safety rail.
    feet = base + 5
    world.box(x1 - 1, center_y - 2, feet, x1, center_y + 3, feet + 3, AIR)
    world.box(x1 - 1, center_y - 4, feet - 1, x1 + 5, center_y + 5, feet, WOOD)
    world.box(x1 + 4, center_y - 4, feet, x1 + 5, center_y + 5, feet + 1, WOOD)
    for y in (center_y - 4, center_y + 4):
        world.box(x1, y, feet, x1 + 4, y + 1, feet + 1, WOOD)
    # A readable rooftop silhouette and enclosed overlook reached by flight 3.
    for bounds in ((x0, y0, x1, y0 + 1), (x0, y1 - 1, x1, y1),
                   (x0, y0 + 1, x0 + 1, y1 - 1), (x1 - 1, y0 + 1, x1, y1 - 1)):
        ax, ay, bx, by = bounds
        world.box(ax, ay, roof, bx, by, roof + 1, METAL)
    for x in (x0, x1 - 2):
        for y in (y0, y1 - 2):
            world.box(x, y, roof + 1, x + 2, y + 2, roof + 2, STONE)


def add_landmarks(world: "World") -> None:
    """Connect the highlands, configure shared halls, and plant sparse trees."""
    from .world import AIR, BRIDGE, GRASS, PATH, WOOD, Tree

    roads = _road_cells()
    for x, y in sorted(roads, key=lambda point: (point[1], point[0])):
        if not (0 <= x < world.width and 0 <= y < world.depth):
            continue
        feet = terrain_height(x + 0.5, y + 0.5)
        # Routes repaint terrain, never a landmark's existing masonry/timber
        # floor. Keeping those authored surfaces also preserves hub rebuilds.
        if world.get(x, y, feet - 1) in (GRASS, PATH):
            world.box(x, y, feet - 1, x + 1, y + 1, feet, PATH)
    for x0, y0, x1, y1 in NEW_BRIDGES:
        if x1 > world.width or y1 > world.depth:
            continue
        world.box(x0, y0, 0, x1, y1, 1, BRIDGE)
        world.box(x0, y0, 1, x1, y1, 4, AIR)
        for x in (x0 - 1, x1):
            world.box(x, y0 + 1, 1, x + 1, y1 - 1, 2, WOOD)
            for y in range(y0 + 1, y1 - 1, 4):
                world.box(x, y, 1, x + 1, y + 1, 3, WOOD)
    for landmark in LANDMARKS:
        if (landmark.bounds[2] + 6 < world.width and landmark.bounds[3] + 3 < world.depth
                and landmark.roof + 2 <= world.height):
            _building(world, landmark)
    # Coarse seeded patches keep the enormous landscape populated without
    # turning collision/targeting into a global, per-frame generation job.
    for gy in range(9, world.depth - 5, 12):
        for gx in range(9, world.width - 5, 12):
            seed = (gx * 73856093 ^ gy * 19349663) & 0xFFFFFFFF
            if seed % 5 == 0:
                continue
            x, y = gx + seed % 5 - 2, gy + (seed >> 4) % 5 - 2
            if x < HUB_SIZE and y < HUB_SIZE:
                continue
            feet = terrain_height(x + 0.5, y + 0.5)
            if ((x, y) in roads or world.get(x, y, feet - 1) != GRASS
                    or world.get(x, y, feet) != AIR):
                continue
            world.trees[x, y] = Tree(x + 0.5, y + 0.5, 0.18 + seed % 3 * 0.02,
                                    feet + 3.5 + seed % 5 * 0.2, seed, base_z=feet)


def terrain_area_name(x: float, y: float) -> str | None:
    from .world import river_center

    for landmark in LANDMARKS:
        x0, y0, x1, y1 = landmark.bounds
        if x0 - 3 <= x < x1 + 6 and y0 - 3 <= y < y1 + 3:
            return landmark.name
    if x < HUB_SIZE and y < HUB_SIZE:
        return None
    for bounds, name in zip(NEW_BRIDGES, ("HIGHLAND BRIDGE", "CITADEL BRIDGE")):
        x0, y0, x1, y1 = bounds
        if x0 <= x < x1 and y0 <= y < y1:
            return name
    if abs(y - river_center(x)) < 8:
        return None
    x0, y0, x1, y1 = CANYON_BOUNDS
    if x0 <= x < x1 and y0 <= y < y1:
        return "SPLITSTONE RAVINE"
    if x > 350 and y > 330:
        return "CITADEL HIGHLANDS"
    if y > 300:
        return "NORTHERN UPLANDS"
    if y > 140:
        return "ROLLING HIGHLANDS"
    return "EASTERN RIDGES"

"""Fixed castle grounds and a surrounding meadow, built with shared voxels/doors."""

import math
from typing import TYPE_CHECKING

from .doors import Door

if TYPE_CHECKING:
    from .world import World


EXPANDED_WIDTH = 512
EXPANDED_DEPTH = 512
WORLD_HEIGHT = 32
CASTLE_BOUNDS = (28, 24, 82, 76)
CURTAIN_BOUNDS = (30, 26, 80, 74)
RUIN_BOUNDS = (48, 97, 67, 109)
LODGE_BOUNDS = (92, 40, 105, 54)
FIRST_BRIDGE_BOUNDS = (22, 80, 27, 94)
EAST_BRIDGE_BOUNDS = (84, 80, 89, 94)
INDOOR_SPAWN = (55.5, 30.5, 1.0)
OUTDOOR_SPAWN = (55.5, 20.5, 1.0)
SWORD_POSITIONS = ((55.5, 32.5), (55.5, 22.5))
STAFF_POSITION = (53.5, 103.5)
DUMMY_POSITIONS = ((42.5, 48.5), (46.5, 48.5), (50.5, 48.5))
WATCHSTONE_BOUNDS = (12, 99, 24, 106)
WARDEN_POSITION = (18.5, 103.0, 1.0)
# A known isolated tree, used for close/canopy rendering checks.
CLOSE_TREE = (12.5, 34.5)


def _castle(world):
    from .world import AIR, CRATE, FLOOR, GRASS, METAL, PATH, WOOD

    # A broad enclosure with an open yard, roofed halls and four tall towers.
    world.box(30, 26, 0, 80, 74, 1, FLOOR)
    world.box(38, 40, 0, 61, 57, 1, PATH)
    world.box(63, 39, 0, 76, 59, 1, GRASS)
    for bounds in ((30, 26, 80, 28), (30, 72, 80, 74),
                   (30, 28, 32, 72), (78, 28, 80, 72)):
        x0, y0, x1, y1 = bounds
        world.box(x0, y0, 1, x1, y1, 6)
    # Curtain walk segments connect to the west cloister roof; taller corner
    # towers interrupt the ring rather than promising an unbroken circuit.
    world.box(32, 28, 5, 78, 30, 6)
    world.box(32, 70, 5, 78, 72, 6)
    world.box(32, 30, 5, 34, 70, 6)
    world.box(76, 30, 5, 78, 70, 6)
    for x in range(30, 80, 4):
        for y in (26, 73):
            world.box(x, y, 6, min(x + 2, 80), y + 1, 7)
    for y in range(30, 72, 4):
        for x in (30, 79):
            world.box(x, y, 6, x + 1, y + 2, 7)

    # Standard gate openings: southern entrance, north trail, east/west meadows.
    world.box(53, 26, 1, 58, 28, 4, AIR)
    world.box(53, 72, 1, 58, 74, 4, AIR)
    world.box(30, 45, 1, 32, 50, 4, AIR)
    world.box(78, 45, 1, 80, 50, 4, AIR)

    # The south gatehouse is the indoor start. Its roof frames the open yard.
    for x in (49, 61):
        world.box(x, 28, 1, x + 1, 36, 5)
    world.box(49, 28, 5, 62, 36, 6, WOOD)
    for x in (49, 61):
        world.box(x, 30, 2, x + 1, 33, 4, AIR)

    # Covered west cloister: repeated open arches rather than extra doors.
    world.box(32, 42, 5, 39, 63, 6)
    for y in (42, 47, 52, 57, 62):
        world.box(38, y, 1, 39, y + 1, 5)
    # The west approach uses the same quarter-unit stair geometry as the halls.
    world.add_stair_flight(34, 32, 3, 10, 1, 6,
                           axis="y", direction=1, riser=0.25, material=FLOOR)
    world.box(32, 42, 5, 37, 43, 6)

    # A central northern great hall, with south doors and a rear arch to the gate.
    world.box(47, 61, 0, 65, 72, 1, WOOD)
    for bounds in ((47, 61, 65, 62), (47, 71, 65, 72),
                   (47, 62, 48, 71), (64, 62, 65, 71)):
        x0, y0, x1, y1 = bounds
        world.box(x0, y0, 1, x1, y1, 6)
    world.box(53, 61, 1, 58, 62, 4, AIR)
    world.box(53, 71, 1, 58, 72, 4, AIR)
    for x in (47, 64):
        for y in (64, 68):
            world.box(x, y, 2, x + 1, y + 2, 5, AIR)
    for x in (50, 61):
        for y in (64, 68):
            world.box(x, y, 1, x + 1, y + 1, 6, METAL)
    world.box(47, 61, 6, 65, 72, 7, WOOD)

    # Hollow corner towers keep the castle silhouette legible from the meadow.
    for x in (28, 75):
        for y in (24, 69):
            world.box(x, y, 1, x + 7, y + 7, 8)
            world.box(x + 2, y + 2, 1, x + 5, y + 5, 7, AIR)
            inner_x = x + 5 if x == 28 else x
            inner_y = y + 4 if y == 24 else y + 1
            world.box(inner_x, inner_y, 1, inner_x + 2, inner_y + 2, 4, AIR)
            # Narrow windows and crenellations use the same opaque material.
            outer_y = y if y == 24 else y + 6
            world.box(x + 3, outer_y, 3, x + 4, outer_y + 1, 5, AIR)
            for dx, dy in ((0, 0), (3, 0), (6, 0), (0, 3),
                           (6, 3), (0, 6), (3, 6), (6, 6)):
                world.box(x + dx, y + dy, 8, x + dx + 1, y + dy + 1, 9)

    # Jumpable crates and masonry occupy the edge of the court, off the routes.
    world.box(65, 32, 1, 68, 35, 2, CRATE)
    world.box(67, 34, 2, 68, 35, 3, CRATE)
    world.box(68, 61, 1, 73, 62, 2)
    world.box(68, 62, 1, 69, 66, 2)


def _grounds(world):
    from .world import AIR, BRIDGE, FLOOR, PATH, WOOD

    # A loop on all four sides gives both castle gates and bridge approaches
    # short, dry routes; paths stop at the water and bridges carry them across.
    for bounds in ((53, 8, 58, 26), (22, 20, 89, 23),
                   (21, 23, 24, 80), (85, 23, 88, 80),
                   (24, 77, 86, 80), (53, 74, 58, 78),
                   (24, 46, 31, 49), (79, 46, 93, 49),
                   (14, 94, 101, 97), (54, 94, 59, 98),
                   (22, 94, 27, 100), (84, 94, 89, 97)):
        x0, y0, x1, y1 = bounds
        world.box(x0, y0, 0, x1, y1, 1, PATH)
    for x0, y0, x1, y1 in (FIRST_BRIDGE_BOUNDS, EAST_BRIDGE_BOUNDS):
        world.box(x0, y0, 0, x1, y1, 1, BRIDGE)
        for x in (x0 - 1, x1):
            world.box(x, y0 + 1, 1, x + 1, y1 - 1, 2, WOOD)
            for y in range(y0 + 1, y1 - 1, 4):
                world.box(x, y, 1, x + 1, y + 1, 3, WOOD)

    # Northern ruined chapel and its western timber floor retain the fire staff.
    world.box(49, 98, 0, 66, 108, 1, FLOOR)
    world.box(50, 101, 0, 56, 107, 1, WOOD)
    for bounds in ((48, 97, 67, 98), (48, 108, 67, 109),
                   (48, 98, 49, 108), (66, 98, 67, 108)):
        x0, y0, x1, y1 = bounds
        world.box(x0, y0, 1, x1, y1, 5)
    world.box(54, 97, 1, 59, 98, 4, AIR)
    world.box(66, 102, 1, 67, 106, 5, AIR)
    world.box(48, 101, 1, 49, 104, 4, AIR)
    world.box(48, 105, 3, 52, 109, 5, AIR)
    world.box(61, 105, 5, 67, 109, 6, WOOD)

    # A small eastern lodge and western watchstones keep the meadow readable.
    world.box(93, 41, 0, 104, 53, 1, WOOD)
    for bounds in ((92, 40, 105, 41), (92, 53, 105, 54),
                   (92, 41, 93, 53), (104, 41, 105, 53)):
        x0, y0, x1, y1 = bounds
        world.box(x0, y0, 1, x1, y1, 5)
    world.box(92, 45, 1, 93, 50, 4, AIR)
    for y in (42, 50):
        world.box(104, y, 2, 105, y + 2, 4, AIR)
    world.box(92, 47, 5, 105, 54, 6, WOOD)
    world.box(12, 99, 0, 24, 106, 1, PATH)
    world.box(12, 105, 1, 24, 106, 2)
    for x in (12, 23):
        world.box(x, 99, 1, x + 1, 100, 4)
        world.box(x, 104, 1, x + 1, 105, 3)


def expand_world(world: "World") -> None:
    """Build deterministic architecture into prefilled meadow/river terrain.

    Rebuilding static scenery is idempotent; existing named doors keep their
    animation state. Generic fixture worlds remain independent of this builder.
    """
    from .world import AIR, GRASS, Tree

    if world.width < 112 or world.depth < 112 or world.height < 12:
        raise ValueError("Castle grounds require a world of at least 112x112x12")
    _castle(world)
    _grounds(world)
    existing_names = {door.name for door in world.doors}
    for door in (Door("south castle gate", 53.05, 26.5, 4.9),
                 Door("north castle gate", 53.05, 73.5, 4.9),
                 Door("west castle gate", 30.5, 45.05, 4.9, math.pi / 2),
                 Door("east castle gate", 79.5, 45.05, 4.9, math.pi / 2),
                 Door("great hall doors", 53.05, 61.5, 4.9),
                 Door("ruin doors", 54.05, 97.5, 4.9),
                 Door("lodge doors", 92.5, 45.05, 4.9, math.pi / 2)):
        if door.name not in existing_names:
            world.doors.append(door)
    # Sparse fixed groups frame the castle from every side without obstructing
    # trails, doors, combat targets or bridge approaches. Grass stays chunked.
    positions = ((12, 34), (12, 16), (25, 12), (43, 12), (72, 12), (94, 18),
                 (9, 53), (13, 69), (38, 81), (68, 81), (101, 31), (105, 62),
                 (99, 75), (8, 93), (35, 101), (77, 104), (101, 100), (39, 91))
    for seed, (x, y) in enumerate(positions):
        px, py = x + 0.5, y + 0.5
        feet = world.surface_height(px, py)
        if world.surface_material(px, py) == GRASS:
            world.trees[x, y] = Tree(x + 0.5, y + 0.5,
                                    0.18 + seed % 3 * 0.025,
                                    feet + 3.0 + seed % 3 * 0.22, seed, base_z=feet)


def expanded_area_name(x: float, y: float) -> str | None:
    """Describe static landmarks; World.area supplies material-aware meadow names."""
    if not (0 <= x < EXPANDED_WIDTH and 0 <= y < EXPANDED_DEPTH):
        return None
    if 48 <= x < 67 and 97 <= y < 109:
        return "NORTHERN RUINS"
    if 12 <= x < 24 and 99 <= y < 106:
        return "THE WATCHSTONES"
    if 92 <= x < 105 and 40 <= y < 54:
        return "EASTERN LODGE"
    for bounds, name in ((FIRST_BRIDGE_BOUNDS, "WEST BRIDGE"), (EAST_BRIDGE_BOUNDS, "EAST BRIDGE")):
        x0, y0, x1, y1 = bounds
        if x0 <= x < x1 and y0 <= y < y1:
            return name
    if ((28 <= x < 35 or 75 <= x < 82)
            and (24 <= y < 31 or 69 <= y < 76)):
        return "CASTLE TOWERS"
    if 30 <= x < 80 and 26 <= y < 74:
        if 49 <= x < 62 and y < 36:
            return "SOUTH GATEHOUSE"
        if 47 <= x < 65 and y >= 61:
            return "GREAT HALL"
        if x < 39 and 42 <= y < 63:
            return "WEST CLOISTER"
        if 38 <= x < 53 and 40 <= y < 57:
            return "TRAINING YARD"
        if x >= 63 and 39 <= y < 59:
            return "CASTLE GARDEN"
        return "CASTLE COURTYARD"
    return None

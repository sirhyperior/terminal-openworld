"""Fixed castle grounds and a surrounding meadow, built with shared voxels/doors."""

import math
from typing import TYPE_CHECKING

from .doors import Door

if TYPE_CHECKING:
    from .world import World


EXPANDED_WIDTH = 512
EXPANDED_DEPTH = 512
WORLD_HEIGHT = 32
# Ashgate reuses the proven courtyard/cloister circulation at its new site.
ASHGATE_OFFSET = (73, 46)
CASTLE_BOUNDS = (101, 70, 155, 122)
CURTAIN_BOUNDS = (103, 72, 153, 120)
RUIN_BOUNDS = (63, 242, 82, 254)
LODGE_BOUNDS = (292, 120, 316, 144)  # Legacy import: now Thornwatch.
FIRST_BRIDGE_BOUNDS = (86, 211, 91, 231)
EAST_BRIDGE_BOUNDS = (302, 193, 307, 213)
INDOOR_SPAWN = (128.5, 76.5, 1.0)
OUTDOOR_SPAWN = (128.5, 66.5, 1.0)
SWORD_POSITIONS = ((128.5, 78.5), (128.5, 68.5))
STAFF_POSITION = (68.5, 248.5)
DUMMY_POSITIONS = ((115.5, 94.5), (119.5, 94.5), (123.5, 94.5))
WATCHSTONE_BOUNDS = (34, 242, 48, 256)
WARDEN_POSITION = (41.5, 250.0, 1.0)
CLOSE_TREE = (85.5, 80.5)


def _castle(world, offset=(0, 0)):
    from .world import AIR, CRATE, FLOOR, GRASS, METAL, PATH, WOOD

    dx, dy = offset

    def box(x0, y0, z0, x1, y1, z1, material=1):
        world.box(x0 + dx, y0 + dy, z0, x1 + dx, y1 + dy, z1, material)

    def stairs(x, y, *args, **kwargs):
        return world.add_stair_flight(x + dx, y + dy, *args, **kwargs)

    # A broad enclosure with an open yard, roofed halls and four tall towers.
    box(30, 26, 0, 80, 74, 1, FLOOR)
    box(38, 40, 0, 61, 57, 1, PATH)
    box(63, 39, 0, 76, 59, 1, GRASS)
    for bounds in ((30, 26, 80, 28), (30, 72, 80, 74),
                   (30, 28, 32, 72), (78, 28, 80, 72)):
        x0, y0, x1, y1 = bounds
        box(x0, y0, 1, x1, y1, 6)
    # Curtain walk segments connect to the west cloister roof; taller corner
    # towers interrupt the ring rather than promising an unbroken circuit.
    box(32, 28, 5, 78, 30, 6)
    box(32, 70, 5, 78, 72, 6)
    box(32, 30, 5, 34, 70, 6)
    box(76, 30, 5, 78, 70, 6)
    for x in range(30, 80, 4):
        for y in (26, 73):
            box(x, y, 6, min(x + 2, 80), y + 1, 7)
    for y in range(30, 72, 4):
        for x in (30, 79):
            box(x, y, 6, x + 1, y + 2, 7)

    # Standard gate openings: southern entrance, north trail, east/west meadows.
    box(53, 26, 1, 58, 28, 4, AIR)
    box(53, 72, 1, 58, 74, 4, AIR)
    box(30, 45, 1, 32, 50, 4, AIR)
    box(78, 45, 1, 80, 50, 4, AIR)

    # The south gatehouse is the indoor start. Its roof frames the open yard.
    for x in (49, 61):
        box(x, 28, 1, x + 1, 36, 5)
    box(49, 28, 5, 62, 36, 6, WOOD)
    for x in (49, 61):
        box(x, 30, 2, x + 1, 33, 4, AIR)

    # Covered west cloister: repeated open arches rather than extra doors.
    box(32, 42, 5, 39, 63, 6)
    for y in (42, 47, 52, 57, 62):
        box(38, y, 1, 39, y + 1, 5)
    # The west approach uses the same quarter-unit stair geometry as the halls.
    stairs(34, 32, 3, 10, 1, 6,
                           axis="y", direction=1, riser=0.25, material=FLOOR)
    box(32, 42, 5, 37, 43, 6)

    # A central northern great hall, with south doors and a rear arch to the gate.
    box(47, 61, 0, 65, 72, 1, WOOD)
    for bounds in ((47, 61, 65, 62), (47, 71, 65, 72),
                   (47, 62, 48, 71), (64, 62, 65, 71)):
        x0, y0, x1, y1 = bounds
        box(x0, y0, 1, x1, y1, 6)
    box(53, 61, 1, 58, 62, 4, AIR)
    box(53, 71, 1, 58, 72, 4, AIR)
    for x in (47, 64):
        for y in (64, 68):
            box(x, y, 2, x + 1, y + 2, 5, AIR)
    for x in (50, 61):
        for y in (64, 68):
            box(x, y, 1, x + 1, y + 1, 6, METAL)
    box(47, 61, 6, 65, 72, 7, WOOD)

    # Hollow corner towers keep the castle silhouette legible from the meadow.
    for x in (28, 75):
        for y in (24, 69):
            box(x, y, 1, x + 7, y + 7, 8)
            box(x + 2, y + 2, 1, x + 5, y + 5, 7, AIR)
            inner_x = x + 5 if x == 28 else x
            inner_y = y + 4 if y == 24 else y + 1
            box(inner_x, inner_y, 1, inner_x + 2, inner_y + 2, 4, AIR)
            # Narrow windows and crenellations use the same opaque material.
            outer_y = y if y == 24 else y + 6
            box(x + 3, outer_y, 3, x + 4, outer_y + 1, 5, AIR)
            for merlon_x, merlon_y in ((0, 0), (3, 0), (6, 0), (0, 3),
                           (6, 3), (0, 6), (3, 6), (6, 6)):
                box(x + merlon_x, y + merlon_y, 8, x + merlon_x + 1, y + merlon_y + 1, 9)

    # Jumpable crates and masonry occupy the edge of the court, off the routes.
    box(65, 32, 1, 68, 35, 2, CRATE)
    box(67, 34, 2, 68, 35, 3, CRATE)
    box(68, 61, 1, 73, 62, 2)
    box(68, 62, 1, 69, 66, 2)


def _ashgate(world):
    from .architecture import bevel_voxel_corners, pointed_arch, tapered_tower
    from .world import AIR, STONE

    _castle(world, ASHGATE_OFFSET)
    for x in (101, 148):
        for y in (70, 115):
            bevel_voxel_corners(world, x, y, 1, x + 7, y + 7, 8)
    # Pointed gate crowns and lancets break up the older rectangular enclosure.
    for x, y, width, axis, depth in ((126, 72, 5, "x", 2),
                                      (126, 118, 5, "x", 2),
                                      (103, 91, 5, "y", 2),
                                      (151, 91, 5, "y", 2),
                                      (126, 107, 5, "x", 1)):
        pointed_arch(world, x, y, width, 1, 4, axis=axis, depth=depth)
    # Spires sit on the hollow corner towers, preserving their interior rooms.
    for x in (104.5, 151.5):
        for y in (73.5, 118.5):
            tapered_tower(world, x, y, 9, 6, radius=3.3)
    # Repeated external buttresses leave gates and courtyard routes clear.
    for x in (103, 152):
        for y in (83, 103, 112):
            world.box(x - 1, y, 1, x + 1, y + 2, 4, STONE)
    for x in (120, 137):
        for y in (110, 114):
            pointed_arch(world, x, y, 2, 2, 3, axis="y")
    # Broken masonry at the garden edge stays a jump-only prop.
    world.box(141, 107, 2, 146, 108, 3, AIR)


def _gravewood(world):
    from .architecture import pointed_arch, tapered_tower
    from .world import AIR, FLOOR, GRASS, PATH, STONE, WOOD

    x0, y0, x1, y1 = RUIN_BOUNDS
    world.box(32, 224, 0, 99, 273, 1, GRASS)
    world.box(x0, y0, 0, x1, y1, 1, FLOOR)
    world.box(65, 246, 0, 71, 252, 1, WOOD)
    for bounds in ((x0, y0, x1, y0 + 1), (x0, y1 - 1, x1, y1),
                   (x0, y0 + 1, x0 + 1, y1 - 1), (x1 - 1, y0 + 1, x1, y1 - 1)):
        ax, ay, bx, by = bounds
        world.box(ax, ay, 1, bx, by, 7, STONE)
    pointed_arch(world, 69, y0, 5, 1, 5)
    pointed_arch(world, 69, y1 - 1, 5, 1, 5)
    pointed_arch(world, x1 - 1, 246, 5, 1, 5, axis="y")
    pointed_arch(world, x0, 246, 4, 1, 5, axis="y")
    # The roof has fallen away; two broken spires and surviving ribs frame sky.
    tapered_tower(world, x0 + 1.5, y1 - 1.5, 6, 5, radius=2)
    tapered_tower(world, x1 - 1.5, y1 - 1.5, 6, 4, radius=2)
    world.box(76, 250, 6, 82, 254, 7, WOOD)
    for x in (65, 79):
        world.box(x, 243, 1, x + 1, 244, 5, STONE)
    # Grave silhouettes leave every authored path and its shoulder clear.
    from .terrain import _road_cells
    roads = _road_cells()
    for row in range(3):
        for column in range(5):
            x, y = 56 + column * 5, 228 + row * 4
            if any((px, y) in roads for px in range(x - 1, x + 2)):
                continue
            world.box(x, y, 1, x + 1, y + 1, 3, STONE)
            world.box(x - 1, y, 2, x + 2, y + 1, 3, STONE)
    for x, y, high in ((34, 243, 4), (47, 243, 3), (34, 255, 3), (47, 255, 4)):
        world.box(x, y, 1, x + 1, y + 1, high, STONE)
    world.box(34, 255, 1, 48, 256, 2, STONE)


def expand_world(world: "World") -> None:
    """Author Ashgate and Gravewood using shared opaque geometry and panels."""
    if world.width < 160 or world.depth < 274 or world.height < 16:
        raise ValueError("Dark-fantasy grounds require at least 160x274x16")
    # Runtime rebuilds leave immutable solids, panels and seeded trees intact.
    if getattr(world, "_dark_grounds_built", False):
        return
    _ashgate(world)
    _gravewood(world)
    world.doors.extend((
        Door("Ashgate south gate", 126.05, 72.5, 4.9),
        Door("Ashgate north gate", 126.05, 119.5, 4.9),
        Door("Ashgate west gate", 103.5, 91.05, 4.9, math.pi / 2),
        Door("Ashgate east gate", 152.5, 91.05, 4.9, math.pi / 2),
        Door("Ashgate hall doors", 126.05, 107.5, 4.9),
        Door("Gravewood chapel doors", 69.05, 242.5, 4.9),
    ))
    world._dark_grounds_built = True


def expanded_area_name(x: float, y: float) -> str | None:
    if not (0 <= x < EXPANDED_WIDTH and 0 <= y < EXPANDED_DEPTH):
        return None
    if 63 <= x < 82 and 242 <= y < 254:
        return "GRAVEWOOD CHAPEL"
    if 34 <= x < 48 and 242 <= y < 256:
        return "THE WATCHSTONES"
    if 32 <= x < 99 and 224 <= y < 273:
        return "GRAVEWOOD"
    if 101 <= x < 155 and 70 <= y < 122:
        if 122 <= x < 135 and y < 82:
            return "ASHGATE GATEHOUSE"
        if 120 <= x < 138 and y >= 107:
            return "ASHGATE GREAT HALL"
        if x < 112 and 88 <= y < 109:
            return "ASHGATE CLOISTER"
        if 111 <= x < 126 and 86 <= y < 103:
            return "ASHGATE TRAINING YARD"
        if x >= 136 and 85 <= y < 105:
            return "ASHGATE GARDEN"
        return "ASHGATE"
    return None

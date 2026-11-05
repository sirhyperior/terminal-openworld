"""Static, connected northern ruins and eastern river route.

Keep the original 41-by-62 region intact. Geometry uses existing materials and
doors so collision, rendering, surface footsteps, and interactions stay shared.
"""

from typing import TYPE_CHECKING

from .doors import Door

if TYPE_CHECKING:
    from .world import World


EXPANDED_WIDTH = 65
EXPANDED_DEPTH = 86
# Exclusive bounds; exported for map/river validation and future placement.
EAST_BRIDGE_BOUNDS = (49, 38, 54, 54)
RUIN_BOUNDS = (28, 69, 47, 83)
LODGE_BOUNDS = (45, 14, 61, 29)


def expand_world(world: "World") -> None:
    """Add fixed scenery after the original map and continuous river exist."""
    # Import only when building: world.py calls this after defining its types.
    from .world import AIR, BRIDGE, FLOOR, GRASS, PATH, WOOD, Tree

    if world.width < EXPANDED_WIDTH or world.depth < EXPANDED_DEPTH or world.height < 6:
        raise ValueError("Map expansion requires a world of at least 65x86x6")

    # The eastern lodge has a timber floor, windows, and a sheltered rear bay.
    # Its open north doorway connects the entry directly to the second bridge.
    world.box(46, 15, 0, 60, 28, 1, WOOD)
    world.box(45, 14, 1, 61, 15, 5)
    world.box(45, 28, 1, 61, 29, 5)
    world.box(45, 15, 1, 46, 28, 5)
    world.box(60, 15, 1, 61, 28, 5)
    world.box(50, 14, 1, 55, 15, 4, AIR)
    world.box(50, 28, 1, 55, 29, 4, AIR)
    for x in (45, 60):
        for y in (18, 24):
            world.box(x, y, 2, x + 1, y + 3, 4, AIR)
    world.box(45, 21, 5, 61, 29, 6, WOOD)

    # Gravel approaches stop at intact bridge decks and do not fill the river.
    world.box(41, 10, 0, 54, 13, 1, PATH)
    world.box(51, 13, 0, 54, 15, 1, PATH)
    world.box(51, 28, 0, 54, 38, 1, PATH)
    x0, y0, x1, y1 = EAST_BRIDGE_BOUNDS
    world.box(x0, y0, 0, x1, y1, 1, BRIDGE)
    for x in (x0 - 1, x1):
        world.box(x, y0 + 1, 1, x + 1, y1 - 1, 2, WOOD)
        for y in range(y0 + 1, y1 - 1, 4):
            world.box(x, y, 1, x + 1, y + 1, 3, WOOD)

    # A walkable loop joins both river crossings to the ruined northern court.
    # Everything west of the original east edge begins beyond its north edge.
    world.box(51, 54, 0, 54, 80, 1, PATH)
    world.box(14, 63, 0, 54, 66, 1, PATH)
    world.box(36, 66, 0, 39, 70, 1, PATH)
    world.box(47, 77, 0, 54, 80, 1, PATH)
    world.box(14, 66, 0, 17, 76, 1, PATH)

    # A partly roofless ruin: uneven walls, a broken eastern exit, and one
    # timber platform give future encounters distinct, traversable spaces.
    world.box(29, 70, 0, 46, 82, 1, FLOOR)
    world.box(30, 75, 0, 36, 81, 1, WOOD)
    world.box(28, 69, 1, 47, 70, 5)
    world.box(28, 82, 1, 47, 83, 5)
    world.box(28, 70, 1, 29, 82, 5)
    world.box(46, 70, 1, 47, 82, 5)
    world.box(35, 69, 1, 40, 70, 4, AIR)
    world.box(36, 82, 1, 40, 83, 4, AIR)
    world.box(28, 75, 1, 29, 78, 4, AIR)
    world.box(46, 77, 1, 47, 80, 5, AIR)
    world.box(28, 72, 2, 29, 74, 4, AIR)
    world.box(28, 78, 3, 29, 83, 5, AIR)
    world.box(29, 82, 2, 34, 83, 5, AIR)
    world.box(40, 79, 5, 47, 83, 6, WOOD)

    # Open watchstones terminate the western branch without blocking its view.
    world.box(10, 75, 0, 21, 82, 1, PATH)
    world.box(10, 81, 1, 21, 82, 2)
    for x in (10, 20):
        world.box(x, 75, 1, x + 1, 76, 4)
        world.box(x, 80, 1, x + 1, 81, 3)

    # Reuse exactly the existing Door/Panel format and all associated feedback.
    # Named definitions also make rebuilding the static extension idempotent.
    existing_names = {door.name for door in world.doors}
    for door in (Door("lodge doors", 50.05, 14.5, 4.9),
                 Door("ruin doors", 35.05, 69.5, 4.9)):
        if door.name not in existing_names:
            world.doors.append(door)

    # Sparse deterministic trees remain off every trail and doorway. Scenery
    # retains its spatial/detail budgets rather than adding per-frame work here.
    tree_positions = ((43, 6), (60, 7), (43, 33), (60, 35), (60, 57),
                      (43, 60), (5, 70), (23, 72), (7, 82), (24, 83),
                      (57, 83), (61, 73), (56, 67), (49, 84))
    for seed, (x, y) in enumerate(tree_positions, 100):
        if world.get(x, y, 0) == GRASS and world.get(x, y, 1) == AIR:
            world.trees[x, y] = Tree(x + 0.5, y + 0.5,
                                     0.18 + seed % 3 * 0.025,
                                     4.0 + seed % 3 * 0.22, seed)

    for x, y in ((42, 17), (58, 61), (8, 67), (20, 67)):
        world.box(x, y, 1, x + 1, y + 1, 2)


def expanded_area_name(x: float, y: float) -> str | None:
    """Name extension landmarks; defer ordinary river terrain to World.area."""
    if not (0 <= x < EXPANDED_WIDTH and 0 <= y < EXPANDED_DEPTH):
        return None
    if x < 41 and y < 62:
        return None
    if 28 <= x < 47 and 69 <= y < 83:
        return "NORTHERN RUINS"
    if 10 <= x < 21 and 75 <= y < 82:
        return "THE WATCHSTONES"
    if 45 <= x < 61 and 14 <= y < 29:
        return "EASTERN LODGE"
    if 49 <= x < 54 and 38 <= y < 54:
        return "EAST BRIDGE"
    if (14 <= x < 54 and 63 <= y < 66
            or 51 <= x < 54 and 54 <= y < 80
            or 14 <= x < 17 and 66 <= y < 76
            or 36 <= x < 39 and 66 <= y < 70
            or 47 <= x < 54 and 77 <= y < 80):
        return "NORTH TRAIL"
    if y >= 62:
        return "NORTH COMMON"
    if x >= 41 and y < 38:
        return "EAST MEADOW"
    return None

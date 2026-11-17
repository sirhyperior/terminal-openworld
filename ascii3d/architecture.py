"""Small shared gothic construction kit using the engine's exact solids.

Arches are open passageways, not interactive objects. Their sloping stone
spandrels, buttresses and octagonal towers participate in ordinary collision,
support and ray occlusion, including the optional GPU geometry path.
"""

import math
from dataclasses import replace

from .surfaces import ConvexSolid
from .world import AIR, FLOOR, GRASS, METAL, PATH, STONE, WOOD


BOX_FACES = ((0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7))


def _piece(world, vertices, faces, material=STONE):
    solid = ConvexSolid(tuple(vertices), tuple(faces), material)
    # Builders can be reapplied without leaving duplicate collision/ray pieces.
    keys = getattr(world, "_architecture_keys", None)
    if keys is None:
        keys = world._architecture_keys = set()
    key = solid.vertices, solid.faces, solid.material
    if key not in keys:
        keys.add(key)
        world.add_solid(solid)
    return solid


def pointed_arch(world, x, y, width, bottom, height, axis="x", depth=1):
    """Carve a pointed opening; X spans a Y wall, Y spans an X wall.

    X/Y and depth are integer voxel bounds. The pointed head uses two exact
    triangular prisms rather than a staircase outline. Height is integral so
    the original lintel above the cut remains intact.
    """
    if axis not in ("x", "y") or width <= 0 or height <= 0 or depth <= 0:
        raise ValueError("arches require positive dimensions and an X/Y span")
    if any(int(value) != value for value in (x, y, width, bottom, height, depth)):
        raise ValueError("arch voxel bounds must be integral")
    x, y, width, bottom, height, depth = map(int, (x, y, width, bottom, height, depth))
    if axis == "x":
        world.box(x, y, bottom, x + width, y + depth, bottom + height, AIR)
    else:
        world.box(x, y, bottom, x + depth, y + width, bottom + height, AIR)
    spring, top = bottom + height * 0.64, bottom + height
    faces = ((0, 2, 1), (3, 4, 5), (0, 1, 4, 3),
             (1, 2, 5, 4), (2, 0, 3, 5))
    pieces = []
    for edge in (0, width):
        profile = ((edge, spring), (edge, top), (width / 2, top))
        vertices = [((x + along, y + across, z) if axis == "x"
                     else (x + across, y + along, z))
                    for across in (0, depth) for along, z in profile]
        pieces.append(_piece(world, vertices, faces))
    return tuple(pieces)


def bevel_voxel_corners(world, x0, y0, z0, x1, y1, z1, material=STONE):
    """Replace four square exterior corner columns with exact diagonal faces.

    The retained half of each corner cell remains solid. Interior voxels,
    floors below z0 and surfaces above z1 are untouched.
    """
    if any(int(value) != value for value in (x0, y0, z0, x1, y1, z1)):
        raise ValueError("bevel bounds must be integral")
    if x1 - x0 < 2 or y1 - y0 < 2 or z1 <= z0:
        raise ValueError("bevels require positive height and at least two-cell sides")
    x0, y0, z0, x1, y1, z1 = map(int, (x0, y0, z0, x1, y1, z1))
    faces = ((0, 2, 1), (3, 4, 5), (0, 1, 4, 3),
             (1, 2, 5, 4), (2, 0, 3, 5))
    result = []
    for x, dx in ((x0, 1), (x1, -1)):
        for y, dy in ((y0, 1), (y1, -1)):
            world.box(min(x, x + dx), min(y, y + dy), z0,
                      max(x, x + dx), max(y, y + dy), z1, AIR)
            profile = ((x + dx, y), (x + dx, y + dy), (x, y + dy))
            vertices = [(px, py, z) for z in (z0, z1) for px, py in profile]
            result.append(_piece(world, vertices, faces, material))
    return tuple(result)


def buttress(world, x, y, bottom, height, width=1, reach=3, axis="x", direction=1):
    """Add one sloping support with its tall edge at (x,y)."""
    if axis not in ("x", "y") or direction not in (-1, 1):
        raise ValueError("buttresses require an X/Y axis and signed direction")
    outer = direction * reach
    # Four lower corners and four upper corners describe an inclined prism.
    profile = ((0, 0), (outer, 0), (outer, width), (0, width))
    points = []
    for upper in (False, True):
        for along, across in profile:
            z = bottom + (height if along == 0 else 0.8) if upper else bottom
            points.append((x + along, y + across, z) if axis == "x"
                          else (x + across, y + along, z))
    return _piece(world, points, BOX_FACES)


def tapered_tower(world, x, y, bottom, height, radius=3, material=STONE, spire=True):
    """Build an empty octagonal tower shell with an optional steep metal spire.

    Eight small convex wall sectors leave the center hollow. Place decorative
    towers off passageways; no doorway is implied through the shell.
    """
    if radius <= 1.2 or height <= 3:
        raise ValueError("towers require radius above 1.2 and height above 3")
    top = bottom + height - (3 if spire else 0)
    taper = 0.83
    result = []
    for side in range(8):
        a, b = side * math.tau / 8, (side + 1) * math.tau / 8
        vertices = []
        for z, outer in ((bottom, radius), (top, radius * taper)):
            inner = outer - 0.75
            vertices.extend((x + r * math.cos(angle), y + r * math.sin(angle), z)
                            for r, angle in ((outer, a), (outer, b), (inner, b), (inner, a)))
        result.append(_piece(world, vertices, BOX_FACES, material))
    if spire:
        vertices = [(x + radius * taper * math.cos(side * math.tau / 8),
                     y + radius * taper * math.sin(side * math.tau / 8), top)
                    for side in range(8)] + [(x, y, bottom + height)]
        faces = [tuple(reversed(range(8)))] + [(side, (side + 1) % 8, 8) for side in range(8)]
        result.append(_piece(world, vertices, faces, METAL))
    return tuple(result)


def _shell(world, landmark):
    """Shared walkable floors, arches, stairs and guarded east balcony."""
    from .terrain import stair_routes

    x0, y0, x1, y1 = landmark.bounds
    base, roof = landmark.base, landmark.roof
    center_x, center_y = (x0 + x1) // 2, (y0 + y1) // 2
    world.box(x0 - 3, y0 - 3, 0, x1 + 6, y1 + 3, base, STONE)
    world.box(x0 - 3, y0 - 3, base - 1, x1 + 6, y1 + 3, base, GRASS)
    # A narrow cross joins every doorway without outlining the whole pad.
    world.box(center_x - 1, y0 - 3, base - 1, center_x + 2, y1 + 3, base, PATH)
    world.box(x0 - 3, center_y - 1, base - 1, x1 + 6, center_y + 2, base, PATH)
    world.box(x0 - 3, y0 - 3, base, x1 + 6, y1 + 3, world.height, AIR)
    for ax, ay, bx, by in ((x0, y0, x1, y0 + 1), (x0, y1 - 1, x1, y1),
                           (x0, y0 + 1, x0 + 1, y1 - 1), (x1 - 1, y0 + 1, x1, y1 - 1)):
        world.box(ax, ay, base, bx, by, roof)
    for feet in (*landmark.floors, roof):
        world.box(x0 + 1, y0 + 1, feet - 1, x1 - 1, y1 - 1, feet,
                  FLOOR if feet == base else WOOD)
    for x in (x0, x1 - 1):
        pointed_arch(world, x, center_y - 2, 5, base, 4, axis="y")
    for y in (y0, y1 - 1):
        pointed_arch(world, center_x - 2, y, 5, base, 4)
    for feet in landmark.floors:
        for x in (x0, x1 - 1):
            for y in (y0 + 4, y1 - 7):
                pointed_arch(world, x, y, 3, feet + 1, 3, axis="y")
        for y in (y0, y1 - 1):
            for x in (x0 + 5, x1 - 8):
                pointed_arch(world, x, y, 3, feet + 1, 3)
    for cx, start_y, _, feet in stair_routes(landmark):
        sx, sy = math.floor(cx) - 1, math.floor(start_y) + 1
        world.box(sx, sy, feet + 4, sx + 3, sy + 10, feet + 5, AIR)
        world.add_stair_flight(sx, sy, 3, 10, feet, feet + 5,
                               axis="y", direction=1, riser=0.25, material=FLOOR)
    feet = base + 5
    pointed_arch(world, x1 - 1, center_y - 2, 5, feet, 4, axis="y")
    world.box(x1 - 1, center_y - 4, feet - 1, x1 + 5, center_y + 5, feet, WOOD)
    world.box(x1 + 4, center_y - 4, feet, x1 + 5, center_y + 5, feet + 1, WOOD)
    for y in (center_y - 4, center_y + 4):
        world.box(x1, y, feet, x1 + 4, y + 1, feet + 1, WOOD)
    for ax, ay, bx, by in ((x0, y0, x1, y0 + 1), (x0, y1 - 1, x1, y1),
                           (x0, y0 + 1, x0 + 1, y1 - 1), (x1 - 1, y0 + 1, x1, y1 - 1)):
        world.box(ax, ay, roof, bx, by, roof + 1, METAL)


def build_landmark(world, landmark):
    """Place the complete architecture, including real stairs, at its bearing."""
    if not getattr(landmark, "angle", 0.0):
        return _build_axis_landmark(world, landmark)
    from .orientation import place_rotated
    from .world import World

    keys = getattr(world, "_oriented_landmark_keys", None)
    if keys is None:
        keys = world._oriented_landmark_keys = set()
    key = landmark.name, landmark.bounds, landmark.base, landmark.angle
    if key in keys:
        return ()
    x0, y0, x1, y1 = landmark.bounds
    width, depth = x1 - x0, y1 - y0
    # An eight-cell border holds every tower/buttress/terrace. Local coordinates
    # keep staging storage proportional to a landmark, rather than the map.
    local = replace(landmark, bounds=(8, 8, 8 + width, 8 + depth), angle=0.0)
    source = World.empty(width + 24, depth + 24, world.height)
    _build_axis_landmark(source, local)
    placed = place_rotated(world, source, landmark, offset=(x0 - 8, y0 - 8),
                           bounds=(5, 5, 0, width + 14, depth + 11, source.height))
    # Keep authored flight provenance in its original local coordinate system;
    # no axis-aligned stair geometry is inserted into the final world.
    flights = getattr(world, "_oriented_stairs", None)
    if flights is None:
        flights = world._oriented_stairs = []
    for flight in sorted(source._stair_keys):
        flights.append((landmark, (flight[0] + x0 - 8, flight[1] + y0 - 8, *flight[2:])))
    keys.add(key)
    return placed


def _build_axis_landmark(world, landmark):
    """Author a distinct silhouette around the shared three-level circulation."""
    _shell(world, landmark)
    x0, y0, x1, y1 = landmark.bounds
    base, roof = landmark.base, landmark.roof
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    name = landmark.name.upper()
    # Supports stay outside doors, windows, balcony and stair lanes.
    for y in (y0 + 9, y1 - 10):
        buttress(world, x0, y, base, 11, reach=3, direction=-1)
    for x in (x0 + 9, x1 - 10):
        buttress(world, x, y0, base, 10, axis="y", direction=-1)
    if "ABBEY" in name:
        # A breached upper nave, unequal broken towers and roofless bays.
        tapered_tower(world, x0, y0, base, 12, radius=2.2, spire=False)
        tapered_tower(world, x1 - 1, y0, base, 18, radius=2.2, spire=False)
        world.box(x0 + 7, y1 - 1, base + 8, x0 + 11, y1, roof + 1, AIR)
        # Missing roof panels leave the central crossing and all stair landings.
        world.box(cx + 3, cy - 3, roof - 1, x1 - 7, cy + 3, roof, AIR)
        for y in (y0 + 8, y1 - 9):
            pointed_arch(world, cx - 3, y, 7, roof, 4)
            # Freestanding rib piers frame the broken vault above the roof.
            world.box(cx - 4, y, roof, cx - 3, y + 1, roof + 4)
            world.box(cx + 4, y, roof, cx + 5, y + 1, roof + 4)
    elif "RELIQUARY" in name or "OBSERVATORY" in name:
        # Fractured octagonal roof: sloping metal sectors surround an open sky.
        for side in (0, 1, 3, 4, 6):
            a, b = side * math.tau / 8, (side + 1) * math.tau / 8
            profile = [(cx + r * math.cos(angle), cy + r * math.sin(angle), z)
                       for r, angle, z in ((8, a, roof + 1.7), (8, b, roof + 1.7),
                                          (4, b, roof + 4), (4, a, roof + 4))]
            # A thin inclined quadrilateral slab, not a filled dome/AABB.
            _piece(world, [(x, y, z + dz) for dz in (0, 0.35) for x, y, z in profile],
                   BOX_FACES, METAL)
        tapered_tower(world, x0, y1 - 1, base, 18, radius=2.1, spire=False)
        world.box(cx + 3, cy + 2, roof - 1, cx + 6, cy + 5, roof, AIR)
    elif "CITADEL" in name:
        # Largest fortress: paired high needles and a stepped, guarded terrace.
        for x in (x0, x1 - 1):
            tapered_tower(world, x, y0, base, min(19, world.height - base - 0.2), radius=2.8)
        for x in range(x0 + 3, x1 - 2, 4):
            if abs(x - cx) > 3:
                world.box(x, y1 - 1, roof + 1, x + 1, y1, min(roof + 3, world.height), STONE)
        # West terrace is open at the side arch and has its own low parapet.
        world.box(x0 - 3, cy - 5, base - 1, x0, cy + 6, base, FLOOR)
        for start, end in ((cy - 5, cy - 2), (cy + 3, cy + 6)):
            world.box(x0 - 3, start, base, x0 - 2, end, base + 1, STONE)
    else:
        # Thornwatch's narrow ridge fort ends in two sharply tapered spires.
        for x in (x0, x1 - 1):
            tapered_tower(world, x, y0, base, 19, radius=2.2)
        # Ragged shoulders above the rear wall break the rectangular parapet.
        for x in (x0 + 3, x1 - 4):
            buttress(world, x, y1, roof, 2.5, reach=2.5, axis="y", direction=-1)

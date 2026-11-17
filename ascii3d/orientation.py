"""Rigid placement of authored voxel/convex geometry at arbitrary XY angles.

The temporary authoring grid is consumed once during startup. Final geometry
uses the existing exact convex query path for rendering, collision and support.
"""

import math

from .surfaces import ConvexSolid, SolidBox


BOX_FACES = ((0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7))


def transform_point(landmark, point, offset=(0, 0)):
    """Map a staging point to the landmark's real world location; keep Z."""
    x, y = landmark.to_world(point[0] + offset[0], point[1] + offset[1])
    return x, y, point[2]


def transform_direction(landmark, direction):
    """Rotate a vector without translating it or changing its length."""
    cosine, sine = math.cos(landmark.angle), math.sin(landmark.angle)
    x, y, z = direction
    return x * cosine - y * sine, x * sine + y * cosine, z


def voxel_cuboids(source, bounds=None):
    """Greedily merge final equal-material voxels, retaining every AIR cut.

    Bounds are exclusive XYZ limits. The private compact copy is consumed;
    source cells and their edit/cache state remain unchanged.
    """
    if bounds is None:
        bounds = (0, 0, 0, source.width, source.depth, source.height)
    x0, y0, z0, x1, y1, z1 = bounds
    width, depth, height = x1 - x0, y1 - y0, z1 - z0
    layer = width * depth
    cells = bytearray(source.get(x, y, z) for z in range(z0, z1)
                      for y in range(y0, y1) for x in range(x0, x1))
    for z in range(height):
        for y in range(depth):
            x = 0
            while x < width:
                index = z * layer + y * width + x
                material = cells[index]
                if not material:
                    x += 1
                    continue
                right = x + 1
                while right < width and cells[index + right - x] == material:
                    right += 1
                row = bytes([material]) * (right - x)
                back = y + 1
                while back < depth:
                    start = z * layer + back * width + x
                    if cells[start:start + len(row)] != row:
                        break
                    back += 1
                top = z + 1
                while top < height:
                    if any(cells[top * layer + yy * width + x:
                                 top * layer + yy * width + right] != row
                           for yy in range(y, back)):
                        break
                    top += 1
                blank = bytes(right - x)
                for zz in range(z, top):
                    for yy in range(y, back):
                        start = zz * layer + yy * width + x
                        cells[start:start + len(blank)] = blank
                yield SolidBox(x0 + x, y0 + y, z0 + z,
                               x0 + right, y0 + back, z0 + top, material)
                x = right


def rotate_solid(source, landmark, offset=(0, 0)):
    """Rotate an actual piece, preserving treads and every sloping face."""
    if isinstance(source, SolidBox):
        vertices = tuple((x, y, z) for z in (source.z0, source.z1)
                         for x, y in ((source.x0, source.y0), (source.x1, source.y0),
                                      (source.x1, source.y1), (source.x0, source.y1)))
        faces = BOX_FACES
    else:
        vertices, faces = source.vertices, source.faces
    return ConvexSolid(tuple(transform_point(landmark, point, offset) for point in vertices),
                       faces, source.material, stair=source.stair)


def place_rotated(target, source, landmark, offset=(0, 0), bounds=None):
    """Add one staged structure without changing the surrounding terrain.

    Return the exact placed solids; their union bounds describe this placement.
    Generated scenery remains free to sample the final rotated surfaces.
    """
    placed = []
    for solid in voxel_cuboids(source, bounds):
        placed.append(target.add_solid(rotate_solid(solid, landmark, offset)))
    for solid in source.solids:
        placed.append(target.add_solid(rotate_solid(solid, landmark, offset)))
    return tuple(placed)

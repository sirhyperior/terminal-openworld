"""Exact continuous ground triangles and configurable fractional solid steps.

Camera rays use their original (possibly unnormalized) parameter. Ground is a
solid below a continuous triangulated vertex grid, independent of voxel storage.
"""

from array import array
from dataclasses import dataclass, field
import math


EPSILON = 1e-7


@dataclass(frozen=True, slots=True)
class SurfaceHit:
    distance: float
    material: int
    normal: tuple[float, float, float]


def grid_intervals(ox, oy, dx, dy, start, limit, size=1):
    """Visit only crossed XY cells, retaining exact entry/exit parameters."""
    t = start
    x = math.floor((ox + dx * (t + 1e-9)) / size)
    y = math.floor((oy + dy * (t + 1e-9)) / size)
    sx, sy = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
    tx = ((x + (sx > 0)) * size - ox) / dx if abs(dx) > 1e-12 else math.inf
    ty = ((y + (sy > 0)) * size - oy) / dy if abs(dy) > 1e-12 else math.inf
    ax = abs(size / dx) if abs(dx) > 1e-12 else math.inf
    ay = abs(size / dy) if abs(dy) > 1e-12 else math.inf
    while t <= limit + 1e-9:
        end = tx if tx < ty else ty
        if limit < end:
            end = limit
        yield x, y, t, end
        if end >= limit:
            return
        crossing = end + 1e-10
        if tx <= crossing:
            x += sx
            tx += ax
        if ty <= crossing:
            y += sy
            ty += ay
        t = end


def circle_rect(x, y, radius, x0, y0, x1, y1):
    dx, dy = max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1)
    return dx * dx + dy * dy < radius * radius + 1e-12


@dataclass(frozen=True, slots=True)
class SolidBox:
    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float
    material: int = 2
    stair: bool = False

    def ray_hit(self, origin, direction, limit):
        return self._ray_query(origin, direction, limit, False)

    def ray_entry(self, origin, direction, limit) -> float | None:
        """Closed slab entry for coarse bounds, without allocating a hit."""
        return self._ray_query(origin, direction, limit, True)

    def _ray_query(self, origin, direction, limit, entry_only):
        # Unroll the three slabs: these bounds are queried for every camera
        # ray. Keep X/Y/Z tie order, and defer normals until a confirmed hit.
        ox, oy, oz = origin
        dx, dy, dz = direction
        enter, leave = 0.0, limit
        axis, sign = 2, 1.0
        if abs(dx) < 1e-12:
            if ox < self.x0 or ox > self.x1:
                return None
        else:
            a, b = (self.x0 - ox) / dx, (self.x1 - ox) / dx
            face = -1.0
            if a > b:
                a, b, face = b, a, 1.0
            if a > enter:
                enter, axis, sign = a, 0, face
            if b < leave:
                leave = b
            if enter > leave + 1e-10:
                return None
        if abs(dy) < 1e-12:
            if oy < self.y0 or oy > self.y1:
                return None
        else:
            a, b = (self.y0 - oy) / dy, (self.y1 - oy) / dy
            face = -1.0
            if a > b:
                a, b, face = b, a, 1.0
            if a > enter:
                enter, axis, sign = a, 1, face
            if b < leave:
                leave = b
            if enter > leave + 1e-10:
                return None
        if abs(dz) < 1e-12:
            if oz < self.z0 or oz > self.z1:
                return None
        else:
            a, b = (self.z0 - oz) / dz, (self.z1 - oz) / dz
            face = -1.0
            if a > b:
                a, b, face = b, a, 1.0
            if a > enter:
                enter, axis, sign = a, 2, face
            if b < leave:
                leave = b
            if enter > leave + 1e-10:
                return None
        if leave < 0:
            return None
        if entry_only:
            return enter
        normal = (sign, 0.0, 0.0) if axis == 0 else (0.0, sign, 0.0) if axis == 1 else (0.0, 0.0, sign)
        return SurfaceHit(enter, self.material, normal)

    def overlaps(self, x, y, feet, radius, height):
        return (feet < self.z1 - EPSILON and feet + height > self.z0 + EPSILON
                and circle_rect(x, y, radius, self.x0, self.y0, self.x1, self.y1))

    def footprint(self, x, y, radius):
        if circle_rect(x, y, radius, self.x0, self.y0, self.x1, self.y1):
            return ((self.z1, self.material),)
        return ()


def _polygon_contains(vertices, x, y):
    """Closed containment in an ordered convex polygon of either winding."""
    sign = 0
    for i, (ax, ay) in enumerate(vertices):
        bx, by = vertices[(i + 1) % len(vertices)]
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if abs(cross) > 1e-10:
            direction = 1 if cross > 0 else -1
            if sign and sign != direction:
                return False
            sign = direction
    return True


def _convex_hull(points):
    points = sorted(set(points))
    if len(points) <= 2:
        return points
    def half(sequence):
        result = []
        for p in sequence:
            while len(result) > 1:
                a, b = result[-2:]
                if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) > 1e-12:
                    break
                result.pop()
            result.append(p)
        return result
    return half(points)[:-1] + half(reversed(points))[:-1]


@dataclass(frozen=True, slots=True)
class ConvexSolid:
    """Small closed convex piece shared by sight, collision and support.

    Face indices follow their perimeter; either winding is accepted and is
    normalized outward once. Concave structures are assemblies of pieces.
    """

    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, ...], ...]
    material: int = 2
    stair: bool = field(default=False, init=False)
    planes: tuple = field(init=False, repr=False)
    edges: tuple = field(init=False, repr=False)
    x0: float = field(init=False)
    y0: float = field(init=False)
    z0: float = field(init=False)
    x1: float = field(init=False)
    y1: float = field(init=False)
    z1: float = field(init=False)

    def __post_init__(self):
        vertices = tuple(tuple(float(v) for v in point) for point in self.vertices)
        faces = tuple(tuple(face) for face in self.faces)
        if not 4 <= len(vertices) <= 32 or not 4 <= len(faces) <= 32:
            raise ValueError('convex pieces require 4..32 vertices and faces')
        if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in vertices):
            raise ValueError('convex vertices must be finite XYZ coordinates')
        if len(set(vertices)) != len(vertices):
            raise ValueError('convex vertices must be distinct')
        center = tuple(sum(p[i] for p in vertices) / len(vertices) for i in range(3))
        planes, ordered, edge_counts = [], [], {}
        for face in faces:
            if (len(face) < 3 or len(set(face)) != len(face)
                    or any(type(i) is not int or not 0 <= i < len(vertices) for i in face)):
                raise ValueError('faces require distinct valid vertex indices')
            a, b, c = (vertices[face[i]] for i in range(3))
            u, v = tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))
            normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            length = math.sqrt(sum(n * n for n in normal))
            if length < 1e-10:
                raise ValueError('face begins with collinear vertices')
            normal = tuple(n / length for n in normal)
            offset = sum(normal[i] * a[i] for i in range(3))
            if sum(normal[i] * center[i] for i in range(3)) > offset:
                normal, offset, face = tuple(-n for n in normal), -offset, tuple(reversed(face))
            if offset - sum(normal[i] * center[i] for i in range(3)) < 1e-9:
                raise ValueError('convex piece must have nonzero volume')
            if any(sum(normal[i] * p[i] for i in range(3)) > offset + 1e-7 for p in vertices):
                raise ValueError('piece is not convex')
            if any(abs(sum(normal[i] * vertices[j][i] for i in range(3)) - offset) > 1e-7 for j in face):
                raise ValueError('face is not planar')
            for i, index in enumerate(face):
                nxt, last = face[(i + 1) % len(face)], face[(i + 2) % len(face)]
                a, b, c = vertices[index], vertices[nxt], vertices[last]
                u, v = tuple(b[j] - a[j] for j in range(3)), tuple(c[j] - b[j] for j in range(3))
                cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                if sum(cross[j] * normal[j] for j in range(3)) < -1e-9:
                    raise ValueError('face perimeter is not convex and ordered')
                # Local turn signs alone also admit a self-intersecting star.
                # Every face vertex must lie inside every oriented edge.
                for other in face:
                    v = tuple(vertices[other][j] - a[j] for j in range(3))
                    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                    if sum(cross[j] * normal[j] for j in range(3)) < -1e-9:
                        raise ValueError('face perimeter is not convex and ordered')
                edge = tuple(sorted((index, nxt)))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
            ordered.append(face)
            planes.append((*normal, offset))
        if any(count != 2 for count in edge_counts.values()) or set(i for f in faces for i in f) != set(range(len(vertices))):
            raise ValueError('convex piece must be closed with every vertex used')
        for name, value in (('vertices', vertices), ('faces', tuple(ordered)), ('planes', tuple(planes)),
                            ('edges', tuple(edge_counts))):
            object.__setattr__(self, name, value)
        for axis, names in enumerate((('x0', 'x1'), ('y0', 'y1'), ('z0', 'z1'))):
            object.__setattr__(self, names[0], min(p[axis] for p in vertices))
            object.__setattr__(self, names[1], max(p[axis] for p in vertices))

    def ray_hit(self, origin, direction, limit):
        enter, leave, normal = 0.0, limit, (0.0, 0.0, 1.0)
        for nx, ny, nz, offset in self.planes:
            numerator = offset - (nx * origin[0] + ny * origin[1] + nz * origin[2])
            denominator = nx * direction[0] + ny * direction[1] + nz * direction[2]
            if abs(denominator) < 1e-12:
                if numerator < -1e-10:
                    return None
                continue
            t = numerator / denominator
            if denominator < 0:
                if t > enter:
                    enter, normal = t, (nx, ny, nz)
            else:
                leave = min(leave, t)
            if enter > leave + 1e-10:
                return None
        return SurfaceHit(enter, self.material, normal) if leave >= 0 else None

    def ray_entry(self, origin, direction, limit):
        hit = self.ray_hit(origin, direction, limit)
        return hit.distance if hit is not None else None

    def overlaps(self, x, y, feet, radius, height):
        bottom, top = feet + EPSILON, feet + height - EPSILON
        if (bottom >= self.z1 or top <= self.z0 or bottom >= top
                or not circle_rect(x, y, radius, self.x0, self.y0, self.x1, self.y1)):
            return False
        points = [(vx, vy) for vx, vy, vz in self.vertices if bottom <= vz <= top]
        for first, second in self.edges:
            a, b = self.vertices[first], self.vertices[second]
            if abs(b[2] - a[2]) < 1e-12:
                continue
            for level in (bottom, top):
                fraction = (level - a[2]) / (b[2] - a[2])
                if 0 <= fraction <= 1:
                    points.append((a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])))
        hull = _convex_hull(points)
        if len(hull) >= 3 and _polygon_contains(hull, x, y):
            return True
        for i, (ax, ay) in enumerate(hull):
            bx, by = hull[(i + 1) % len(hull)]
            dx, dy = bx - ax, by - ay
            squared = dx * dx + dy * dy
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / squared)) if squared else 0.0
            if (ax + t * dx - x) ** 2 + (ay + t * dy - y) ** 2 <= radius * radius + 1e-12:
                return True
        return False

    def footprint(self, x, y, radius):
        """Maximize each upward face over its exact intersection with a disk."""
        if not circle_rect(x, y, radius, self.x0, self.y0, self.x1, self.y1):
            return ()
        results = []
        for face, (nx, ny, nz, offset) in zip(self.faces, self.planes):
            if nz <= 1e-10:
                continue
            vertices = tuple(self.vertices[i][:2] for i in face)
            aa, bb, cc = -nx / nz, -ny / nz, offset / nz
            candidates = [(x, y)] if _polygon_contains(vertices, x, y) else []
            gradient = math.hypot(aa, bb)
            if gradient:
                px, py = x + radius * aa / gradient, y + radius * bb / gradient
                if _polygon_contains(vertices, px, py):
                    candidates.append((px, py))
            for i, (px, py) in enumerate(vertices):
                if (px - x) ** 2 + (py - y) ** 2 <= radius * radius + 1e-10:
                    candidates.append((px, py))
                qx, qy = vertices[(i + 1) % len(vertices)]
                ex, ey = qx - px, qy - py
                qa = ex * ex + ey * ey
                if qa < 1e-20:
                    continue
                qb = 2 * ((px - x) * ex + (py - y) * ey)
                qc = (px - x) ** 2 + (py - y) ** 2 - radius * radius
                discriminant = qb * qb - 4 * qa * qc
                if discriminant >= -1e-12:
                    root = math.sqrt(max(0.0, discriminant))
                    for t in ((-qb - root) / (2 * qa), (-qb + root) / (2 * qa)):
                        if -1e-9 <= t <= 1 + 1e-9:
                            candidates.append((px + t * ex, py + t * ey))
            if candidates:
                results.append((max(cc + aa * px + bb * py for px, py in candidates), self.material))
        return tuple(results)


class HeightField:
    CHUNK = 8
    RAY_CACHE_CELLS = 4096

    def __init__(self, width, depth, heights, material=5):
        self.width, self.depth = width, depth
        self.heights = array("d", heights)
        if len(self.heights) != (width + 1) * (depth + 1):
            raise ValueError("heightfield needs one height at every grid vertex")
        if not all(math.isfinite(v) and v >= 0 for v in self.heights):
            raise ValueError("heightfield heights must be finite and nonnegative")
        self.materials = bytearray([material]) * (width * depth)
        self.enabled = bytearray([1]) * (width * depth)
        self._chunks = {}
        self._chunk_envelopes = {}
        self._footprints = {}
        self._ray_cells = {}
        self._ray_origin = None
        self._maximum = max(self.heights, default=0.0)
        self.revision = 0

    def _corners(self, x, y):
        i = y * (self.width + 1) + x
        h = self.heights
        return h[i], h[i + 1], h[i + self.width + 1], h[i + self.width + 2]

    def cell_bounds(self, x, y):
        values = self._corners(x, y)
        return min(values), max(values)

    def _plane(self, x, y, second=False):
        h00, h10, h01, h11 = self._corners(x, y)
        return (h11 - h01, h01 - h00, h00) if second else (h10 - h00, h11 - h10, h00)

    def _ray_cell(self, x, y, index, origin):
        """Cache exact origin-relative planes and normals; flags remain live."""
        h00, h10, h01, h11 = self._corners(x, y)
        a0, b0, a1, b1 = h10 - h00, h11 - h10, h11 - h01, h01 - h00
        ox, oy, oz = origin
        numerator0 = h00 + a0 * (ox - x) + b0 * (oy - y) - oz
        numerator1 = h00 + a1 * (ox - x) + b1 * (oy - y) - oz
        length0, length1 = math.sqrt(a0 * a0 + b0 * b0 + 1), math.sqrt(a1 * a1 + b1 * b1 + 1)
        normal0, normal1 = (-a0 / length0, -b0 / length0, 1 / length0), (-a1 / length1, -b1 / length1, 1 / length1)
        value = h00, a0, b0, a1, b1, max(h00, h10, h01, h11), numerator0, numerator1, normal0, normal1
        if len(self._ray_cells) >= self.RAY_CACHE_CELLS:
            self._ray_cells.clear()
        self._ray_cells[index] = value
        return value

    def height_at(self, x, y):
        cx, cy = math.floor(x), math.floor(y)
        if not (0 <= cx < self.width and 0 <= cy < self.depth
                and self.enabled[cy * self.width + cx]):
            return None
        u, v = x - cx, y - cy
        a, b, c = self._plane(cx, cy, v > u)
        return c + a * u + b * v

    def material_at(self, x, y):
        cx, cy = math.floor(x), math.floor(y)
        if 0 <= cx < self.width and 0 <= cy < self.depth and self.enabled[cy * self.width + cx]:
            return self.materials[cy * self.width + cx]
        return 0

    def paint_cell(self, x, y, material):
        if 0 <= x < self.width and 0 <= y < self.depth:
            self.materials[y * self.width + x] = material
            self.revision += 1
            self._footprints.clear()
            self._ray_cells.clear()
            key = x // self.CHUNK, y // self.CHUNK
            self._chunks.pop(key, None)
            self._chunk_envelopes.pop(key, None)

    def edit_box(self, x0, y0, z0, x1, y1, z1, material):
        """Authored voxels and cuts replace touched surface cells; turf repaints."""
        for y in range(max(0, y0), min(self.depth, y1)):
            for x in range(max(0, x0), min(self.width, x1)):
                i = y * self.width + x
                if not self.enabled[i]:
                    continue
                low, high = self.cell_bounds(x, y)
                if z0 < high - 1e-8 and z1 >= low - 1e-8:
                    if material in (5, 9):
                        self.materials[i] = material
                    else:
                        self.enabled[i] = 0
                        key = x // self.CHUNK, y // self.CHUNK
                        self._chunks.pop(key, None)
                        self._chunk_envelopes.pop(key, None)
        self.revision += 1
        self._footprints.clear()
        self._ray_cells.clear()

    def _chunk_bounds(self, cx, cy):
        key = cx, cy
        if key not in self._chunks:
            low, high = math.inf, -math.inf
            x0, y0 = max(0, cx * self.CHUNK), max(0, cy * self.CHUNK)
            x1, y1 = min(self.width, (cx + 1) * self.CHUNK), min(self.depth, (cy + 1) * self.CHUNK)
            if x0 >= x1 or y0 >= y1:
                self._chunks[key] = low, high
                self._chunk_envelopes[key] = 0.0, 0.0, -math.inf
                return low, high
            stride, heights = self.width + 1, self.heights
            h00, h10 = heights[y0 * stride + x0], heights[y0 * stride + x1]
            h01, h11 = heights[y1 * stride + x0], heights[y1 * stride + x1]
            slope_x = (h10 + h11 - h00 - h01) / (2 * (x1 - x0))
            slope_y = (h01 + h11 - h00 - h10) / (2 * (y1 - y0))
            upper = -math.inf
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if self.enabled[y * self.width + x]:
                        corners = self._corners(x, y)
                        low, high = min(low, *corners), max(high, *corners)
                        local_x, local_y = x - x0, y - y0
                        upper = max(upper,
                                    corners[0] - slope_x * local_x - slope_y * local_y,
                                    corners[1] - slope_x * (local_x + 1) - slope_y * local_y,
                                    corners[2] - slope_x * local_x - slope_y * (local_y + 1),
                                    corners[3] - slope_x * (local_x + 1) - slope_y * (local_y + 1))
            # Every linear triangle is below this plane because all of its
            # vertices are. Pad rounding conservatively, including large input
            # heights; the envelope only rejects work, never supplies a hit.
            if upper != -math.inf:
                upper += 1e-12 * (1 + abs(upper) + abs(high)
                                   + abs(slope_x) * self.CHUNK + abs(slope_y) * self.CHUNK)
            self._chunks[key] = low, high
            self._chunk_envelopes[key] = slope_x, slope_y, upper
        return self._chunks[key]

    def prepare(self):
        for cy in range((self.depth + self.CHUNK - 1) // self.CHUNK):
            for cx in range((self.width + self.CHUNK - 1) // self.CHUNK):
                self._chunk_bounds(cx, cy)

    def ray_hit(self, origin, direction, limit, minimum=0.0):
        ox, oy, oz = origin
        dx, dy, dz = direction
        if min(oz, oz + dz * limit) > self._maximum + EPSILON:
            return None
        start, end = minimum, limit
        for o, d, high in ((ox, dx, self.width), (oy, dy, self.depth)):
            if abs(d) < 1e-12:
                if not 0 <= o < high:
                    return None
            else:
                a, b = -o / d, (high - o) / d
                start, end = max(start, min(a, b)), min(end, max(a, b))
        if start > end or end < 0:
            return None
        width, depth = self.width, self.depth
        ray_origin = ox, oy, oz
        if self._ray_origin != ray_origin:
            self._ray_cells.clear()
            self._ray_origin = ray_origin
        enabled, materials, ray_cells = self.enabled, self.materials, self._ray_cells
        step_x, step_y = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
        delta_x = abs(1 / dx) if abs(dx) > 1e-12 else math.inf
        delta_y = abs(1 / dy) if abs(dy) > 1e-12 else math.inf
        abs_dx, abs_dy, abs_dz = abs(dx), abs(dy), abs(dz)
        # Nonnegative vertices bound every triangle slope by the maximum
        # height, and every eight-cell envelope slope by that same value.
        # One conservative ray margin replaces repeated per-chunk/cell error
        # arithmetic. This only admits extra exact tests; it never supplies a
        # surface or changes the triangle intersection tolerances below.
        maximum = self._maximum
        rate_bound = abs_dz + maximum * (abs_dx + abs_dy)
        margin = (EPSILON + 1e-8 * rate_bound
                  + 1e-12 * (1 + abs(oz) + maximum * (33 + abs(ox) + width + abs(oy) + depth)
                             + rate_bound * abs(limit)))
        for chunk_x, chunk_y, a, b in grid_intervals(ox, oy, dx, dy, start, end, self.CHUNK):
            low, high = self._chunk_bounds(chunk_x, chunk_y)
            if low == math.inf or oz + dz * (b if dz < 0 else a) > high + margin:
                continue
            fine_start, fine_end = a, b
            # Restrict fine traversal to where the ray could meet this chunk's
            # constant ceiling. Retain a parameter halo for the exact triangle
            # tests' 1e-8 endpoint tolerance and grid-boundary offset.
            halo = 1.1e-8
            if dz < -1e-12:
                crossing = (high + margin - oz) / dz - halo
                if crossing > fine_start:
                    fine_start = crossing
            elif dz > 1e-12:
                crossing = (high + margin - oz) / dz + halo
                if crossing < fine_end:
                    fine_end = crossing
            if fine_start > fine_end:
                continue
            slope_x, slope_y, upper = self._chunk_envelopes[chunk_x, chunk_y]
            local_x, local_y = ox - chunk_x * self.CHUNK, oy - chunk_y * self.CHUNK
            clearance = oz - upper - slope_x * local_x - slope_y * local_y
            rate = dz - slope_x * dx - slope_y * dy
            if clearance + rate * (fine_end if rate < 0 else fine_start) > margin:
                continue
            if rate < -1e-12:
                crossing = (margin - clearance) / rate - halo
                if crossing > fine_start:
                    fine_start = crossing
            elif rate > 1e-12:
                crossing = (margin - clearance) / rate + halo
                if crossing < fine_end:
                    fine_end = crossing
            if fine_start > fine_end:
                continue
            # Inline only the fine traversal. Its crossings and tie tolerances
            # match grid_intervals, without creating a generator per chunk.
            x = math.floor(ox + dx * (fine_start + 1e-9))
            y = math.floor(oy + dy * (fine_start + 1e-9))
            next_x = ((x + (step_x > 0)) - ox) / dx if abs_dx > 1e-12 else math.inf
            next_y = ((y + (step_y > 0)) - oy) / dy if abs_dy > 1e-12 else math.inf
            left = fine_start
            while left <= fine_end + 1e-9:
                right = next_x if next_x < next_y else next_y
                if fine_end < right:
                    right = fine_end
                if 0 <= x < width and 0 <= y < depth:
                    index = y * width + x
                    if enabled[index]:
                        planes = ray_cells.get(index)
                        if planes is None:
                            planes = self._ray_cell(x, y, index, origin)
                        cc, a0, b0, a1, b1, cell_top, numerator0, numerator1, normal0, normal1 = planes
                        # The ray is linear over this cell. All triangle
                        # heights lie below its highest vertex; expand by the
                        # existing intersection tolerance at either endpoint.
                        if oz + dz * (right if dz < 0 else left) <= cell_top + margin:
                            za = oz + dz * left
                            u, v = ox + dx * left - x, oy + dy * left - y
                            aa, bb = (a1, b1) if v > u else (a0, b0)
                            if za < cc + aa * u + bb * v - EPSILON:
                                return SurfaceHit(max(0.0, left), materials[index], (0.0, 0.0, 1.0))
                            nearest = math.inf
                            hit_normal = None
                            for second in (False, True):
                                aa, bb = (a1, b1) if second else (a0, b0)
                                denominator = dz - aa * dx - bb * dy
                                if denominator >= -1e-12:
                                    continue
                                t = (numerator1 if second else numerator0) / denominator
                                if left - 1e-8 <= t <= right + 1e-8 and t >= -1e-8:
                                    u, v = ox + dx * t - x, oy + dy * t - y
                                    if (v >= u - 1e-8) if second else (v <= u + 1e-8):
                                        distance = max(0.0, t)
                                        if distance < nearest:
                                            nearest, hit_normal = distance, normal1 if second else normal0
                            if nearest != math.inf:
                                return SurfaceHit(nearest, materials[index], hit_normal)
                if right >= fine_end:
                    break
                crossing = right + 1e-10
                if next_x <= crossing:
                    x += step_x
                    next_x += delta_x
                if next_y <= crossing:
                    y += step_y
                    next_y += delta_y
                left = right
        return None

    def footprint(self, x, y, radius, with_grade=False):
        """Exact maximum of each ground triangle intersecting a circular foot."""
        key = x, y, radius
        if key in self._footprints:
            values = self._footprints[key]
            return values if with_grade else tuple((top, material) for top, material, _ in values)
        results = []
        for cy in range(max(0, math.floor(y - radius)), min(self.depth, math.floor(y + radius) + 1)):
            for cx in range(max(0, math.floor(x - radius)), min(self.width, math.floor(x + radius) + 1)):
                index = cy * self.width + cx
                if not self.enabled[index] or not circle_rect(x, y, radius, cx, cy, cx + 1, cy + 1):
                    continue
                for second in (False, True):
                    vertices = ((cx, cy), (cx, cy + 1), (cx + 1, cy + 1)) if second else (
                        (cx, cy), (cx + 1, cy), (cx + 1, cy + 1))
                    aa, bb, cc = self._plane(cx, cy, second)
                    candidates = []
                    def inside(px, py):
                        return (cx - 1e-9 <= px <= cx + 1 + 1e-9
                                and cy - 1e-9 <= py <= cy + 1 + 1e-9
                                and ((py - cy >= px - cx - 1e-9) if second
                                     else (py - cy <= px - cx + 1e-9)))
                    if inside(x, y):
                        candidates.append((x, y))
                    gradient = math.hypot(aa, bb)
                    if gradient:
                        px, py = x + radius * aa / gradient, y + radius * bb / gradient
                        if inside(px, py):
                            candidates.append((px, py))
                    for i, (px, py) in enumerate(vertices):
                        if (px - x) ** 2 + (py - y) ** 2 <= radius * radius + 1e-10:
                            candidates.append((px, py))
                        qx, qy = vertices[(i + 1) % 3]
                        ex, ey = qx - px, qy - py
                        offset_x, offset_y = px - x, py - y
                        qa = ex * ex + ey * ey
                        qb = 2 * (offset_x * ex + offset_y * ey)
                        qc = offset_x * offset_x + offset_y * offset_y - radius * radius
                        discriminant = qb * qb - 4 * qa * qc
                        if discriminant >= 0:
                            root = math.sqrt(discriminant)
                            for t in ((-qb - root) / (2 * qa), (-qb + root) / (2 * qa)):
                                if -1e-9 <= t <= 1 + 1e-9:
                                    candidates.append((px + t * ex, py + t * ey))
                    if candidates:
                        top = max(cc + aa * (px - cx) + bb * (py - cy) for px, py in candidates)
                        results.append((top, self.materials[index], aa * aa + bb * bb))
        if len(self._footprints) >= 512:
            self._footprints.clear()
        self._footprints[key] = tuple(results)
        values = self._footprints[key]
        return values if with_grade else tuple((top, material) for top, material, _ in values)

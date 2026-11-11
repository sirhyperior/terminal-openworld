"""Exact continuous ground triangles and configurable fractional solid steps.

Camera rays use their original (possibly unnormalized) parameter. Ground is a
solid below a continuous triangulated vertex grid, independent of voxel storage.
"""

from array import array
from dataclasses import dataclass
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

    def _ray_cell(self, x, y, index):
        """Cache both exact planes; materials/enabled flags remain live."""
        h00, h10, h01, h11 = self._corners(x, y)
        a0, b0, a1, b1 = h10 - h00, h11 - h10, h11 - h01, h01 - h00
        value = (h00, a0, b0, a1, b1, max(h00, h10, h01, h11),
                 max(abs(a0), abs(a1)), max(abs(b0), abs(b1)))
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
        enabled, materials, ray_cells = self.enabled, self.materials, self._ray_cells
        step_x, step_y = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
        delta_x = abs(1 / dx) if abs(dx) > 1e-12 else math.inf
        delta_y = abs(1 / dy) if abs(dy) > 1e-12 else math.inf
        abs_dx, abs_dy, abs_dz = abs(dx), abs(dy), abs(dz)
        for chunk_x, chunk_y, a, b in grid_intervals(ox, oy, dx, dy, start, end, self.CHUNK):
            low, high = self._chunk_bounds(chunk_x, chunk_y)
            if low == math.inf or min(oz + dz * a, oz + dz * b) > high + EPSILON:
                continue
            fine_start, fine_end = a, b
            # Restrict fine traversal to where the ray could meet this chunk's
            # constant ceiling. Retain a parameter halo for the exact triangle
            # tests' 1e-8 endpoint tolerance and grid-boundary offset.
            halo = 1.1e-8
            margin = EPSILON + 1e-8 * abs_dz + 1e-12 * (1 + abs(high) + abs(oz) + abs_dz * abs(b))
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
            margin = (EPSILON + 1e-8 * (abs_dz + abs(slope_x) * abs_dx + abs(slope_y) * abs_dy)
                      + 1e-12 * (1 + abs(oz) + abs(upper)
                                 + abs(slope_x * local_x) + abs(slope_y * local_y) + abs(rate * b)))
            gap_start, gap_end = clearance + rate * fine_start, clearance + rate * fine_end
            if min(gap_start, gap_end) > margin:
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
                            planes = self._ray_cell(x, y, index)
                        cc, a0, b0, a1, b1, cell_top, max_a, max_b = planes
                        za, zb = oz + dz * left, oz + dz * right
                        # The ray is linear over this cell. All triangle
                        # heights lie below its highest vertex; expand by the
                        # existing intersection tolerance at either endpoint.
                        margin = EPSILON + 1e-8 * (abs_dz + max_a * abs_dx + max_b * abs_dy)
                        if min(za, zb) <= cell_top + margin:
                            u, v = ox + dx * left - x, oy + dy * left - y
                            aa, bb = (a1, b1) if v > u else (a0, b0)
                            if za < cc + aa * u + bb * v - EPSILON:
                                return SurfaceHit(max(0.0, left), materials[index], (0.0, 0.0, 1.0))
                            nearest = math.inf
                            hit_a = hit_b = 0.0
                            for second in (False, True):
                                aa, bb = (a1, b1) if second else (a0, b0)
                                denominator = dz - aa * dx - bb * dy
                                if denominator >= -1e-12:
                                    continue
                                t = (cc + aa * (ox - x) + bb * (oy - y) - oz) / denominator
                                if left - 1e-8 <= t <= right + 1e-8 and t >= -1e-8:
                                    u, v = ox + dx * t - x, oy + dy * t - y
                                    if (v >= u - 1e-8) if second else (v <= u + 1e-8):
                                        distance = max(0.0, t)
                                        if distance < nearest:
                                            nearest, hit_a, hit_b = distance, aa, bb
                            if nearest != math.inf:
                                length = math.sqrt(hit_a * hit_a + hit_b * hit_b + 1)
                                return SurfaceHit(nearest, materials[index],
                                                  (-hit_a / length, -hit_b / length, 1 / length))
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

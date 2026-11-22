"""Continuous cobblestone strips with exact, spatially bounded point queries.

Roads change the ground material only. They never add slabs, alter elevation,
or replace bridge decks and masonry. Buckets select candidates; a capsule's
true distance test alone decides its boundary, including diagonal edges.
"""

import math

from .palette import GRASS, PATH


_CELL_SCALE = 2
_CELL_LIMIT = 65536
_CELL_MARGIN = 1e-7
_CELL_REACH = math.hypot(0.25, 0.25) + _CELL_MARGIN


def _distance_squared(segment, x, y):
    ax, ay, dx, dy, inverse = segment
    px, py = x - ax, y - ay
    along = max(0.0, min(1.0, (px * dx + py * dy) * inverse))
    offset_x, offset_y = px - along * dx, py - along * dy
    return offset_x * offset_x + offset_y * offset_y


class RoadNetwork:
    MAX_SEGMENT_LENGTH = 8.0
    MAX_SEGMENTS_PER_BUCKET = 96

    def __init__(self, routes, width: float = 3.0, bucket_size: float = 8.0):
        if not (math.isfinite(width) and math.isfinite(bucket_size)
                and width > 0 and bucket_size > 0):
            raise ValueError("road width and bucket size must be positive and finite")
        self.width, self.bucket_size = width, bucket_size
        self.routes = tuple(tuple(tuple(point) for point in route) for route in routes)
        if any(len(point) != 2 or not all(math.isfinite(value) for value in point)
               for route in self.routes for point in route):
            raise ValueError("road waypoints must be finite XY coordinates")
        self._radius_squared = (width / 2) ** 2
        segments, buckets = [], {}
        radius = width / 2
        for route in self.routes:
            for (x0, y0), (x1, y1) in zip(route, route[1:]):
                length = math.hypot(x1 - x0, y1 - y0)
                count = max(1, math.ceil(length / self.MAX_SEGMENT_LENGTH))
                for part in range(count):
                    start = part / count
                    end = (part + 1) / count
                    ax, ay = x0 + (x1 - x0) * start, y0 + (y1 - y0) * start
                    bx, by = x0 + (x1 - x0) * end, y0 + (y1 - y0) * end
                    dx, dy = bx - ax, by - ay
                    squared = dx * dx + dy * dy
                    index = len(segments)
                    segments.append((ax, ay, dx, dy, 1 / squared if squared else 0.0))
                    for cy in range(math.floor((min(ay, by) - radius) / bucket_size),
                                    math.floor((max(ay, by) + radius) / bucket_size) + 1):
                        for cx in range(math.floor((min(ax, bx) - radius) / bucket_size),
                                        math.floor((max(ax, bx) + radius) / bucket_size) + 1):
                            candidates = buckets.setdefault((cx, cy), [])
                            candidates.append(index)
                            if len(candidates) > self.MAX_SEGMENTS_PER_BUCKET:
                                raise ValueError("road junction exceeds the local segment budget")
        self.segments = tuple(segments)
        self._buckets = {key: tuple(indices) for key, indices in buckets.items()}
        self.max_bucket_segments = max(map(len, self._buckets.values()), default=0)
        self._cell_coverage = None
        # At most 256 half-unit cells per segment and bucket. Keep the coarse
        # exact query for custom sizes or levels outside this work budget.
        if (bucket_size == 8.0 and radius < _CELL_LIMIT
                and sum(map(len, self._buckets.values())) <= 1024
                and all(abs(x) < _CELL_LIMIT and abs(y) < _CELL_LIMIT
                        for route in self.routes for x, y in route)):
            self._cell_coverage = self._index_cells(radius)

    def _index_cells(self, radius):
        """Index definite coverage and retain exact candidates at the edges."""
        coverage = {}
        bucket_cells = int(self.bucket_size * _CELL_SCALE)
        # Capsule distance varies by at most the distance from the cell center.
        # Leave near ties for the exact point test, including roundoff in the
        # projection at the supported coordinate scale.
        full_squared = (radius - _CELL_REACH) ** 2 if radius > _CELL_REACH else -1.0
        near_squared = (radius + _CELL_REACH) ** 2
        edge = radius + _CELL_MARGIN
        floor = math.floor
        for (bx, by), indices in self._buckets.items():
            start_x, start_y = bx * bucket_cells, by * bucket_cells
            for index in indices:
                segment = self.segments[index]
                ax, ay, dx, dy, _ = segment
                low_x = max(start_x, floor((min(ax, ax + dx) - edge) * _CELL_SCALE))
                low_y = max(start_y, floor((min(ay, ay + dy) - edge) * _CELL_SCALE))
                high_x = min(start_x + bucket_cells, floor((max(ax, ax + dx) + edge) * _CELL_SCALE) + 1)
                high_y = min(start_y + bucket_cells, floor((max(ay, ay + dy) + edge) * _CELL_SCALE) + 1)
                for cy in range(low_y, high_y):
                    y = (cy + 0.5) / _CELL_SCALE
                    for cx in range(low_x, high_x):
                        key = cx, cy
                        entry = coverage.get(key)
                        if entry is True:
                            continue
                        squared = _distance_squared(segment, (cx + 0.5) / _CELL_SCALE, y)
                        if squared <= full_squared:
                            coverage[key] = True
                        elif squared <= near_squared:
                            if entry is None:
                                coverage[key] = [index]
                            else:
                                entry.append(index)
        return {key: True if entry is True else tuple(entry) for key, entry in coverage.items()}

    def candidate_count(self, x: float, y: float) -> int:
        """Number of exact segment tests this local bucket can require."""
        if not (math.isfinite(x) and math.isfinite(y)):
            return 0
        return len(self._buckets.get((math.floor(x / self.bucket_size),
                                      math.floor(y / self.bucket_size)), ()))

    def contains(self, x: float, y: float) -> bool:
        """Test the union of closed capsule strips, with round ends and joins."""
        coverage = self._cell_coverage
        if coverage is not None and 0 <= x < _CELL_LIMIT and 0 <= y < _CELL_LIMIT:
            candidates = coverage.get((math.floor(x * _CELL_SCALE), math.floor(y * _CELL_SCALE)))
            if candidates is True:
                return True
            if candidates is None:
                return False
        else:
            if not (math.isfinite(x) and math.isfinite(y)):
                return False
            candidates = self._buckets.get((math.floor(x / self.bucket_size),
                                            math.floor(y / self.bucket_size)), ())
        radius_squared = self._radius_squared
        segments = self.segments
        for index in candidates:
            if _distance_squared(segments[index], x, y) <= radius_squared:
                return True
        return False

    def material_at(self, x: float, y: float, base_material: int) -> int:
        """Preserve authored surfaces; lay paving only over actual grass."""
        return PATH if base_material == GRASS and self.contains(x, y) else base_material

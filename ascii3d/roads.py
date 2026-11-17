"""Continuous gravel strips with exact, spatially bounded point queries.

Roads change the ground material only. They never add slabs, alter elevation,
or replace bridge decks and masonry. Buckets select candidates; a capsule's
true distance test alone decides its boundary, including diagonal edges.
"""

import math

from .palette import GRASS, PATH


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

    def candidate_count(self, x: float, y: float) -> int:
        """Number of exact segment tests this local bucket can require."""
        if not (math.isfinite(x) and math.isfinite(y)):
            return 0
        return len(self._buckets.get((math.floor(x / self.bucket_size),
                                      math.floor(y / self.bucket_size)), ()))

    def contains(self, x: float, y: float) -> bool:
        """Test the union of closed capsule strips, with round ends and joins."""
        if not (math.isfinite(x) and math.isfinite(y)):
            return False
        candidates = self._buckets.get((math.floor(x / self.bucket_size),
                                        math.floor(y / self.bucket_size)), ())
        for index in candidates:
            ax, ay, dx, dy, inverse = self.segments[index]
            px, py = x - ax, y - ay
            along = max(0.0, min(1.0, (px * dx + py * dy) * inverse))
            offset_x, offset_y = px - along * dx, py - along * dy
            if offset_x * offset_x + offset_y * offset_y <= self._radius_squared:
                return True
        return False

    def material_at(self, x: float, y: float, base_material: int) -> int:
        """Preserve authored surfaces; lay gravel only over actual grass."""
        return PATH if base_material == GRASS and self.contains(x, y) else base_material

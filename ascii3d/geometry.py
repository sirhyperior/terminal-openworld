"""Shared perspective projection and depth-tested text strokes."""

import math

from .player import Player


class Camera:
    NEAR = 0.18

    def __init__(self, player: Player, width: int, height: int, focal: float, aspect: float):
        self.width, self.height = width, height
        self.fx, self.fy = focal, focal * aspect
        self.x, self.y, self.z = player.x, player.y, player.eye_z
        self.cy, self.sy = math.cos(player.yaw), math.sin(player.yaw)
        self.cp, self.sp = math.cos(player.pitch), math.sin(player.pitch)
        forward = (self.cy * self.cp, self.sy * self.cp, self.sp)
        right, up = (self.sy, -self.cy, 0), (-self.cy * self.sp, -self.sy * self.sp, self.cp)
        self.frustum = [(forward, self.NEAR)]
        for axis, tangent in ((right, width / (2 * self.fx)), (up, height / (2 * self.fy))):
            for sign in (-1, 1):
                self.frustum.append((tuple(forward[i] * tangent + sign * axis[i] for i in range(3)), 0.0))

    def project(self, x: float, y: float, z: float):
        dx, dy, dz = x - self.x, y - self.y, z - self.z
        along = dx * self.cy + dy * self.sy
        depth = along * self.cp + dz * self.sp
        if depth < self.NEAR:
            return None
        right, up = dx * self.sy - dy * self.cy, -along * self.sp + dz * self.cp
        return (self.width / 2 - 0.5 + right * self.fx / depth,
                self.height / 2 - 0.5 - up * self.fy / depth, depth)

    def bounds(self, x, y, z, rx, ry, rz):
        points = [self.project(x + a * rx, y + b * ry, z + c * rz)
                  for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
        if any(point is None for point in points):
            return 0, 0, self.width - 1, self.height - 1
        return (max(0, math.floor(min(p[0] for p in points))),
                max(0, math.floor(min(p[1] for p in points))),
                min(self.width - 1, math.ceil(max(p[0] for p in points))),
                min(self.height - 1, math.ceil(max(p[1] for p in points))))

    def stroke_world(self, pixels, depths, start, end, radius=0.0, char=None):
        """Clip a 3D segment before projection, then bound its raster work."""
        nx, ny, nz = self.frustum[0][0]
        start_depth = ((start[0] - self.x) * nx + (start[1] - self.y) * ny
                       + (start[2] - self.z) * nz)
        end_depth = ((end[0] - self.x) * nx + (end[1] - self.y) * ny
                     + (end[2] - self.z) * nz)
        near = self.NEAR + 1e-7
        if start_depth < near and end_depth < near:
            return False
        if start_depth < near:
            fraction = (near - start_depth) / (end_depth - start_depth)
            start = tuple(start[i] + (end[i] - start[i]) * fraction for i in range(3))
        elif end_depth < near:
            fraction = (near - end_depth) / (start_depth - end_depth)
            end = tuple(end[i] + (start[i] - end[i]) * fraction for i in range(3))
        a, b = self.project(*start), self.project(*end)
        if a is None or b is None:
            return False
        # Close trunks can project far beyond the screen. Clip in screen space
        # too, preserving inverse depth and a margin for the six-cell stroke
        # half-width. This avoids sparse 512-sample lines across huge endpoints.
        low, high = 0.0, 1.0
        for axis, lower, upper in ((0, -7, self.width + 6), (1, -7, self.height + 6)):
            delta = b[axis] - a[axis]
            if abs(delta) < 1e-12:
                if not lower <= a[axis] <= upper:
                    return False
                continue
            first, last = (lower - a[axis]) / delta, (upper - a[axis]) / delta
            low, high = max(low, min(first, last)), min(high, max(first, last))
            if low > high:
                return False
        if low > 0 or high < 1:
            def clipped(fraction):
                return (a[0] + (b[0] - a[0]) * fraction,
                        a[1] + (b[1] - a[1]) * fraction,
                        1 / ((1 - fraction) / a[2] + fraction / b[2]))
            a, b = clipped(low), clipped(high)
        return self.stroke(pixels, depths, a, b, radius, char)

    def triangle(self, pixels, depths, a, b, c, char="#"):
        """Fill an opaque projected face with perspective-correct depth.

        Screen clipping bounds work to the viewport. Thin faces still receive
        their edge strokes from the caller, including when smaller than a cell.
        """
        if a is None or b is None or c is None:
            return
        ax, ay, az = a
        bx, by, bz = b
        cx, cy, cz = c
        denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(denominator) < 1e-9:
            return
        x0, x1 = max(0, math.ceil(min(ax, bx, cx))), min(self.width - 1, math.floor(max(ax, bx, cx)))
        y0, y1 = max(0, math.ceil(min(ay, by, cy))), min(self.height - 1, math.floor(max(ay, by, cy)))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                u = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / denominator
                v = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / denominator
                w = 1 - u - v
                if min(u, v, w) < -1e-7:
                    continue
                depth = 1 / (u / az + v / bz + w / cz)
                if depth <= depths[y][x] + 0.01:
                    pixels[y][x], depths[y][x] = char, depth

    def quad(self, pixels, depths, a, b, c, d, char="#"):
        """Fill a convex planar face by spans with perspective-correct depth.

        Closed enemy blocks reuse each projected vertex and visit their face
        pixels once, avoiding two overlapping triangle bounding-box scans.
        """
        if any(point is None for point in (a, b, c, d)):
            self.triangle(pixels, depths, a, b, c, char)
            self.triangle(pixels, depths, a, c, d, char)
            return
        ax, ay, az = a
        bx, by, bz = b
        cx, cy, cz = c
        denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(denominator) < 1e-9:
            return
        inverse_x = ((by - cy) / az + (cy - ay) / bz + (ay - by) / cz) / denominator
        inverse_y = ((cx - bx) / az + (ax - cx) / bz + (bx - ax) / cz) / denominator
        inverse_zero = 1 / az - inverse_x * ax - inverse_y * ay
        points = (a, b, c, d)
        edges = []
        for i, start in enumerate(points):
            end = points[(i + 1) % 4]
            if abs(end[1] - start[1]) > 1e-10:
                edges.append((min(start[1], end[1]), max(start[1], end[1]),
                              start[0], start[1],
                              (end[0] - start[0]) / (end[1] - start[1])))
        y0 = max(0, math.ceil(min(point[1] for point in points)))
        y1 = min(self.height - 1, math.floor(max(point[1] for point in points)))
        for y in range(y0, y1 + 1):
            crossings = [x + (y - start_y) * slope
                         for low, high, x, start_y, slope in edges if low <= y <= high]
            if len(crossings) < 2:
                continue
            x0 = max(0, math.ceil(min(crossings) - 1e-7))
            x1 = min(self.width - 1, math.floor(max(crossings) + 1e-7))
            row, zrow = pixels[y], depths[y]
            inverse_row = inverse_y * y + inverse_zero
            for x in range(x0, x1 + 1):
                inverse = inverse_x * x + inverse_row
                if inverse <= 0:
                    continue
                depth = 1 / inverse
                if depth <= zrow[x] + 0.01:
                    row[x], zrow[x] = char, depth

    def stroke(self, pixels, depths, start, end, radius=0.0, char=None):
        if start is None or end is None:
            return False
        sx, sy, sz = start
        ex, ey, ez = end
        if max(sx, ex) < -8 or min(sx, ex) > self.width + 8:
            return False
        if max(sy, ey) < -8 or min(sy, ey) > self.height + 8:
            return False
        count = min(512, max(1, math.ceil(max(abs(ex - sx), abs(ey - sy)))))
        char = char or ("/" if ex - sx > 0.2 else ("\\" if ex - sx < -0.2 else "|"))
        drawn = False
        for point in range(count + 1):
            fraction = point / count
            x, y = round(sx + (ex - sx) * fraction), round(sy + (ey - sy) * fraction)
            if not 0 <= y < self.height:
                continue
            depth = 1 / ((1 - fraction) / sz + fraction / ez)
            if radius == 0:
                # Grass strokes are one character wide: avoid width arithmetic,
                # clipping ranges and an inner loop for that common case.
                if 0 <= x < self.width and depth <= depths[y][x] + 0.01:
                    pixels[y][x], depths[y][x] = char, depth
                    drawn = True
                continue
            half_width = min(6, round(self.fx * radius / depth))
            for column in range(max(0, x - half_width), min(self.width, x + half_width + 1)):
                if depth - radius <= depths[y][column] + 0.01:
                    pixels[y][column], depths[y][column] = char, depth - radius
                    drawn = True
        return drawn

"""Rounded, irregular foliage volumes and thin branching trunks."""

from dataclasses import dataclass
import math
import random

from .geometry import Camera
from .world import Tree, World


@dataclass(frozen=True, slots=True)
class Crown:
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float


class Trees:
    CHUNK = 8

    def __init__(self, world: World):
        self.chunks = {}
        self.crowns = {}
        self._nearby_chunk = None
        self._nearby_trees = ()
        for tree in world.trees.values():
            self.chunks.setdefault((int(tree.x) // self.CHUNK, int(tree.y) // self.CHUNK), []).append(tree)
            rng = random.Random(7157 + tree.seed * 101)
            center_z = tree.height + 0.9
            crowns = [Crown(tree.x, tree.y, center_z, 1.65, 1.55, 1.65)]
            for index in range(3):
                angle = index * math.tau / 3 + rng.uniform(-0.3, 0.3)
                crowns.append(Crown(tree.x + math.cos(angle) * 1.05,
                                    tree.y + math.sin(angle) * 0.95,
                                    center_z + rng.uniform(-0.65, 0.25),
                                    rng.uniform(0.9, 1.35), rng.uniform(0.9, 1.3), rng.uniform(0.95, 1.4)))
            self.crowns[tree] = crowns

    def visible_selection(self, camera: Camera):
        """Select the same ordered local trees for drawing and work estimates."""
        cx, cy = int(camera.x) // self.CHUNK, int(camera.y) // self.CHUNK
        nearby = []
        if self._nearby_chunk != (cx, cy):
            self._nearby_trees = tuple(tree for y in range(cy - 6, cy + 7)
                                       for x in range(cx - 6, cx + 7)
                                       for tree in self.chunks.get((x, y), ()))
            self._nearby_chunk = cx, cy
        for tree in self._nearby_trees:
            dx, dy = tree.x - camera.x, tree.y - camera.y
            along = dx * camera.cy + dy * camera.sy
            right = dx * camera.sy - dy * camera.cy
            if -3 < along < 48 and abs(right) < max(0, along) * 0.95 + 4:
                nearby.append((dx * dx + dy * dy, tree))
        nearby.sort(key=lambda item: item[0])
        return nearby[:max(6, camera.width * camera.height // 200)]

    def _crowns_for(self, distance_squared, tree):
        return self.crowns[tree][:1] if distance_squared > 24 ** 2 else self.crowns[tree]

    def projected_work_bound(self, camera: Camera):
        """Bound crown sample work even when a depth prepass hides terrain.

        Count each selected crown's complete projected rectangle, before exact
        frustum, scanline and depth rejection. A value below the sample budget
        proves that removing hidden voxel depths cannot exhaust that budget.
        """
        budget = camera.width * camera.height * 3
        total = 0
        for distance_squared, tree in self.visible_selection(camera):
            for crown in self._crowns_for(distance_squared, tree):
                x0, y0, x1, y1 = camera.bounds(crown.x, crown.y, crown.z,
                                               crown.rx, crown.ry, crown.rz)
                total += max(0, x1 - x0 + 1) * max(0, y1 - y0 + 1)
                if total >= budget:
                    return total
        return total

    def draw(self, pixels, depths, camera: Camera, stats):
        pixel_budget = camera.width * camera.height * 3
        stats["tree_pixel_budget"] = pixel_budget
        stats["tree_samples"] = 0
        for distance_squared, tree in self.visible_selection(camera):
            self._trunk(tree, pixels, depths, camera)
            for crown in self._crowns_for(distance_squared, tree):
                if stats["tree_samples"] >= pixel_budget:
                    return
                self._crown(crown, pixels, depths, camera, stats, pixel_budget)

    @staticmethod
    def _trunk(tree: Tree, pixels, depths, camera):
        root = (tree.x, tree.y, tree.base_z)
        fork = (tree.x + 0.10, tree.y - 0.08, tree.height)
        camera.stroke_world(pixels, depths, root, fork, tree.radius, "|")
        for index in range(3):
            angle = index * math.tau / 3 + tree.seed * 0.2
            start = (tree.x + 0.04, tree.y, tree.height - 0.8)
            tip = (tree.x + math.cos(angle) * 1.1, tree.y + math.sin(angle), tree.height + 0.7)
            camera.stroke_world(pixels, depths, start, tip, tree.radius * 0.35)

    @staticmethod
    def _crown(crown, pixels, depths, cam, stats, budget):
        sqrt = math.sqrt
        dx, dy, dz = crown.x - cam.x, crown.y - cam.y, crown.z - cam.z
        for (nx, ny, nz), offset in cam.frustum:
            support = sqrt((nx * crown.rx) ** 2 + (ny * crown.ry) ** 2 + (nz * crown.rz) ** 2)
            if dx * nx + dy * ny + dz * nz + support < offset:
                return
        x0, y0, x1, y1 = cam.bounds(crown.x, crown.y, crown.z, crown.rx, crown.ry, crown.rz)
        if x0 > x1 or y0 > y1:
            return
        ix, iy, iz = 1 / crown.rx ** 2, 1 / crown.ry ** 2, 1 / crown.rz ** 2
        ox, oy, oz = cam.x - crown.x, cam.y - crown.y, cam.z - crown.z
        bx, by, bz = ox * ix, oy * iy, oz * iz
        constant = ox * bx + oy * by + oz * bz - 1
        center_depth = ((crown.x - cam.x) * cam.cy + (crown.y - cam.y) * cam.sy) * cam.cp + (crown.z - cam.z) * cam.sp
        nearest = center_depth - max(crown.rx, crown.ry, crown.rz)
        columns = [(x + 0.5 - cam.width / 2) / cam.fx for x in range(x0, x1 + 1)]
        palette = " .,:;ox*#%@"
        near = cam.NEAR
        cy, sy, cp, sp = cam.cy, cam.sy, cam.cp, cam.sp
        # A scanline's ray is base + u * (sy, -cy, 0). Its ellipsoid
        # discriminant is quadratic in u, so conservative root intervals skip
        # only proven misses. Inside/near-tangent cases keep the scalar path.
        ray_square = sy * sy * ix + cy * cy * iy
        ray_dot = sy * bx - cy * by
        quadratic = ray_dot * ray_dot - ray_square * constant
        screen_middle = cam.width / 2 - 0.5
        samples = stats["tree_samples"]
        for y in range(y0, y1 + 1):
            v = (cam.height / 2 - y - 0.5) / cam.fy
            base_x, base_y = cy * (cp - v * sp), sy * (cp - v * sp)
            dz = sp + v * cp
            depth_row = depths[y]
            left, right = x0, x1
            if constant > 0 and quadratic < -1e-12:
                linear_a = 2 * (base_x * sy * ix - base_y * cy * iy)
                base_a = base_x * base_x * ix + base_y * base_y * iy + dz * dz * iz
                base_b = base_x * bx + base_y * by + dz * bz
                linear = 2 * ray_dot * base_b - linear_a * constant
                zero = base_b * base_b - base_a * constant
                determinant = linear * linear - 4 * quadratic * zero
                tolerance = 1e-10 * max(1.0, linear * linear, abs(4 * quadratic * zero))
                if determinant < -tolerance:
                    continue
                if determinant >= 0:
                    extent = sqrt(determinant)
                    first = (-linear + extent) / (2 * quadratic)
                    last = (-linear - extent) / (2 * quadratic)
                    # One-cell padding retains exact scalar tangent decisions
                    # despite cancellation in the conservative projected roots.
                    left = max(left, math.floor(first * cam.fx + screen_middle) - 1)
                    right = min(right, math.ceil(last * cam.fx + screen_middle) + 1)
            if left > right or max(depth_row[left:right + 1]) < nearest:
                continue
            for x in range(left, right + 1):
                if depth_row[x] < nearest:
                    continue
                samples += 1
                if samples > budget:
                    stats["tree_samples"] = budget
                    return
                u = columns[x - x0]
                dx, dy = base_x + u * sy, base_y - u * cy
                a = dx * dx * ix + dy * dy * iy + dz * dz * iz
                b = dx * bx + dy * by + dz * bz
                discriminant = b * b - a * constant
                if discriminant < 0:
                    continue
                root = sqrt(discriminant)
                depth = (-b - root) / a
                if depth < near:
                    # Inside a soft crown (or with its entry clipped away),
                    # the visible surface is the forward exit, not behind us.
                    depth = (-b + root) / a
                if depth < near:
                    continue
                if depth >= depth_row[x]:
                    continue
                hx, hy, hz = ox + dx * depth, oy + dy * depth, oz + dz * depth
                nx, ny, nz = hx * ix, hy * iy, hz * iz
                normal_length = sqrt(nx * nx + ny * ny + nz * nz)
                light = (-nx * 0.38 - ny * 0.48 + nz * 0.79) / normal_length
                if light < 0:
                    light = 0
                grain = (int((hx + crown.x) * 14) * 37 ^ int((hy + crown.y) * 14) * 19 ^ int(hz * 14) * 7) & 7
                brightness = (0.29 + light * 0.52 + grain * 0.018) / (1 + depth * 0.035)
                shade = int(brightness * 10)
                if shade < 1:
                    shade = 1
                elif shade > 9:
                    shade = 9
                pixels[y][x] = palette[shade]
                depth_row[x] = depth
        stats["tree_samples"] = samples

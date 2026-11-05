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

    def draw(self, pixels, depths, camera: Camera, stats):
        cx, cy = int(camera.x) // self.CHUNK, int(camera.y) // self.CHUNK
        nearby = []
        for y in range(cy - 6, cy + 7):
            for x in range(cx - 6, cx + 7):
                for tree in self.chunks.get((x, y), ()):
                    dx, dy = tree.x - camera.x, tree.y - camera.y
                    along = dx * camera.cy + dy * camera.sy
                    right = dx * camera.sy - dy * camera.cy
                    if -3 < along < 48 and abs(right) < max(0, along) * 0.95 + 4:
                        nearby.append((dx * dx + dy * dy, tree))
        nearby.sort(key=lambda item: item[0])
        pixel_budget = camera.width * camera.height * 3
        stats["tree_pixel_budget"] = pixel_budget
        stats["tree_samples"] = 0
        for distance_squared, tree in nearby[:max(6, camera.width * camera.height // 200)]:
            self._trunk(tree, pixels, depths, camera)
            crowns = self.crowns[tree][:1] if distance_squared > 24 ** 2 else self.crowns[tree]
            for crown in crowns:
                if stats["tree_samples"] >= pixel_budget:
                    return
                self._crown(crown, pixels, depths, camera, stats, pixel_budget)

    @staticmethod
    def _trunk(tree: Tree, pixels, depths, camera):
        root = (tree.x, tree.y, 1.0)
        fork = (tree.x + 0.10, tree.y - 0.08, tree.height)
        camera.stroke_world(pixels, depths, root, fork, tree.radius, "|")
        for index in range(3):
            angle = index * math.tau / 3 + tree.seed * 0.2
            start = (tree.x + 0.04, tree.y, tree.height - 0.8)
            tip = (tree.x + math.cos(angle) * 1.1, tree.y + math.sin(angle), tree.height + 0.7)
            camera.stroke_world(pixels, depths, start, tip, tree.radius * 0.35)

    @staticmethod
    def _crown(crown, pixels, depths, cam, stats, budget):
        dx, dy, dz = crown.x - cam.x, crown.y - cam.y, crown.z - cam.z
        for (nx, ny, nz), offset in cam.frustum:
            support = math.sqrt((nx * crown.rx) ** 2 + (ny * crown.ry) ** 2 + (nz * crown.rz) ** 2)
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
        for y in range(y0, y1 + 1):
            v = (cam.height / 2 - y - 0.5) / cam.fy
            base_x, base_y = cam.cy * (cam.cp - v * cam.sp), cam.sy * (cam.cp - v * cam.sp)
            dz = cam.sp + v * cam.cp
            depth_row = depths[y]
            for offset, u in enumerate(columns):
                x = x0 + offset
                if depth_row[x] < nearest:
                    continue
                stats["tree_samples"] += 1
                if stats["tree_samples"] > budget:
                    stats["tree_samples"] = budget
                    return
                dx, dy = base_x + u * cam.sy, base_y - u * cam.cy
                a = dx * dx * ix + dy * dy * iy + dz * dz * iz
                b = dx * bx + dy * by + dz * bz
                discriminant = b * b - a * constant
                if discriminant < 0:
                    continue
                root = math.sqrt(discriminant)
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
                normal_length = math.sqrt(nx * nx + ny * ny + nz * nz)
                light = max(0, (-nx * 0.38 - ny * 0.48 + nz * 0.79) / normal_length)
                grain = (int((hx + crown.x) * 14) * 37 ^ int((hy + crown.y) * 14) * 19 ^ int(hz * 14) * 7) & 7
                brightness = (0.29 + light * 0.52 + grain * 0.018) / (1 + depth * 0.035)
                pixels[y][x] = palette[max(1, min(9, int(brightness * 10)))]
                depth_row[x] = depth

"""Ray/box rendering of thin swinging panels into the common scene depth buffer."""

import math

from .geometry import Camera
from .shading import DEFAULT_SHADING
from .world import METAL, WOOD


def draw_doors(world, pixels, depths, player, focal, aspect, shading=None):
    if not world.doors:
        return
    height, width = len(pixels), len(pixels[0])
    cam = Camera(player, width, height, focal, aspect)
    origin = (cam.x, cam.y, cam.z)
    shading = shading or DEFAULT_SHADING
    for door in world.doors:
        for panel in door.panels:
            center_x = panel.x + panel.ux * panel.length / 2
            center_y = panel.y + panel.uy * panel.length / 2
            along = (center_x - cam.x) * cam.cy + (center_y - cam.y) * cam.sy
            if along < -panel.length or along > 40:
                continue
            right = (center_x - cam.x) * cam.sy - (center_y - cam.y) * cam.cy
            center_depth = along * cam.cp + (panel.bottom + panel.height / 2 - cam.z) * cam.sp
            if abs(right) > max(0, center_depth) + panel.length + panel.height:
                continue
            rx, ry = cam.x - panel.x, cam.y - panel.y
            ou, ov, oz = rx * panel.ux + ry * panel.uy, -rx * panel.uy + ry * panel.ux, cam.z - panel.bottom
            half, length, tall = panel.thickness / 2, panel.length, panel.height
            bounds = ((0, length), (-half, half), (0, tall))
            local_origin = (ou, ov, oz)
            # Draw only camera-facing rectangle planes. Each pixel needs one
            # division, instead of a full three-axis slab intersection per leaf.
            for face, (low, high) in enumerate(bounds):
                if local_origin[face] < low:
                    plane = low
                elif local_origin[face] > high:
                    plane = high
                else:
                    continue
                others = [axis for axis in range(3) if axis != face]
                corners = []
                for a in bounds[others[0]]:
                    for b in bounds[others[1]]:
                        point = [0, 0, 0]
                        point[face], point[others[0]], point[others[1]] = plane, a, b
                        pu, pv, pz = point
                        corners.append(cam.project(panel.x + pu * panel.ux - pv * panel.uy,
                                                   panel.y + pu * panel.uy + pv * panel.ux, panel.bottom + pz))
                if any(point is None for point in corners):
                    x0, y0, x1, y1 = 0, 0, width - 1, height - 1
                else:
                    x0, x1 = max(0, math.floor(min(p[0] for p in corners))), min(width - 1, math.ceil(max(p[0] for p in corners)))
                    y0, y1 = max(0, math.floor(min(p[1] for p in corners))), min(height - 1, math.ceil(max(p[1] for p in corners)))
                if x0 > x1 or y0 > y1:
                    continue
                columns = [(x + 0.5 - width / 2) / cam.fx for x in range(x0, x1 + 1)]
                numerator = plane - local_origin[face]
                for y in range(y0, y1 + 1):
                    v = (height / 2 - y - 0.5) / cam.fy
                    bx, by = cam.cy * (cam.cp - v * cam.sp), cam.sy * (cam.cp - v * cam.sp)
                    dz = cam.sp + v * cam.cp
                    base_u, base_v = bx * panel.ux + by * panel.uy, -bx * panel.uy + by * panel.ux
                    slope_u = cam.sy * panel.ux - cam.cy * panel.uy
                    slope_v = -cam.sy * panel.uy - cam.cy * panel.ux
                    for index, u in enumerate(columns):
                        x = x0 + index
                        du, dv = base_u + u * slope_u, base_v + u * slope_v
                        denominator = du if face == 0 else (dv if face == 1 else dz)
                        if abs(denominator) < 1e-10:
                            continue
                        distance = numerator / denominator
                        if distance <= 0 or distance >= depths[y][x]:
                            continue
                        a, b, c = ou + du * distance, oz + dz * distance, ov + dv * distance
                        if not (-1e-7 <= a <= length + 1e-7 and -1e-7 <= b <= tall + 1e-7 and -half - 1e-7 <= c <= half + 1e-7):
                            continue
                        grain = (a * 9 + math.sin(b * 2.7) * 0.035) % 1
                        texture = 0.7 if grain > 0.1 else 0.48
                        if (a * 3.5) % 1 < 0.06:
                            texture = 0.24
                        if abs(b - 0.5) < 0.09 or abs(b - tall + 0.5) < 0.09:
                            texture = 0.92 if (a * 2) % 1 < 0.16 else 0.45
                        if abs(a - length + 0.24) < 0.09 and abs(b - 1.25) < 0.15:
                            texture = 1.0
                        sign = -1.0 if plane == bounds[face][0] else 1.0
                        normal = ((panel.ux * sign, panel.uy * sign, 0.0) if face == 0 else
                                  (-panel.uy * sign, panel.ux * sign, 0.0) if face == 1 else
                                  (0.0, 0.0, sign))
                        material = METAL if texture >= 0.9 else WOOD
                        pixels[y][x] = shading.surface(material,
                            panel.x + a * panel.ux - c * panel.uy,
                            panel.y + a * panel.uy + c * panel.ux,
                            panel.bottom + b, normal, distance)
                        depths[y][x] = distance

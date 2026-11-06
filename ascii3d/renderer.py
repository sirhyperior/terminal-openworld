"""Perspective voxel ray casting: one 3D DDA ray per terminal character."""

import math

from .player import Player
from .doors import Door
from .door_render import draw_doors
from .combat_render import draw_combat
from .scenery import Scenery
from .world import (AIR, BRIDGE, CRATE, FLOOR, GRASS, LEAVES, METAL, PATH, WATER,
                    WATER_LEVEL, WOOD, World, river_center)


RAMP = " .,:;!+=*#%@"


def _river_ripple(x: float, y: float, time_seconds: float) -> float:
    """Long streaks in river coordinates, advected downstream around bends."""
    stream = x - time_seconds * 0.9
    cross = y - river_center(x)
    return (math.sin(cross * 3.4 + 0.55 * math.sin(stream * 1.7))
            + 0.4 * math.sin(cross * 6.7 - stream * 2.3))


def _flow_glyph(dx: float, dy: float) -> str:
    """Choose a stroke along the projected current in terminal-cell units."""
    ax, ay = abs(dx), abs(dy)
    if ay <= ax * 0.35:
        return "-"
    if ax <= ay * 0.4:
        return "|"
    return "\\" if dx * dy > 0 else "/"


class Renderer:
    def __init__(self, world: World, cell_aspect: float = 0.5, skip_empty_space: bool = True):
        self.world = world
        self.cell_aspect = cell_aspect
        self._size = (0, 0)
        self._columns: list[float] = []
        self._rows: list[float] = []
        self._focal = 1.0
        self.scenery = Scenery(world)
        self.skip_empty_space = skip_empty_space
        self._world_revision = -1
        self._chunk_tops = []
        self._empty_bounds = []
        self._room_bounds = []
        self._map_key = None
        self._map_rows = []

    def _update_chunks(self):
        if self._world_revision == self.world.revision:
            return
        world = self.world
        chunks_x = (world.width + 1) // 2
        tops = [0] * (chunks_x * ((world.depth + 1) // 2))
        occupied = [0] * len(tops)
        for z in range(world.height):
            for y in range(world.depth):
                offset = (z * world.depth + y) * world.width
                chunk_row = (y >> 1) * chunks_x
                for x in range(world.width):
                    if world.cells[offset + x]:
                        index = chunk_row + (x >> 1)
                        tops[index] = z + 1
                        occupied[index] |= 1 << z
        self._chunk_tops = tops
        # Merge clear 2x2 columns into rectangles at each integer height.
        # These are conservative empty volumes, derived only on voxel edits.
        # Long meadow rays can cross one rectangle instead of many chunks.
        chunks_y = (world.depth + 1) // 2
        bounds = [None] * (world.height * len(tops))
        for level in range(world.height):
            for row in range(chunks_y):
                left = 0
                while left < chunks_x:
                    if tops[row * chunks_x + left] > level:
                        left += 1
                        continue
                    right = left + 1
                    while right < chunks_x and tops[row * chunks_x + right] <= level:
                        right += 1
                    low, high = row, row + 1
                    while low > 0 and all(tops[(low - 1) * chunks_x + x] <= level
                                          for x in range(left, right)):
                        low -= 1
                    while high < chunks_y and all(tops[high * chunks_x + x] <= level
                                                  for x in range(left, right)):
                        high += 1
                    top = max(tops[y * chunks_x + x] for y in range(low, high)
                              for x in range(left, right))
                    rectangle = (left * 2, low * 2, right * 2, high * 2, top)
                    for x in range(left, right):
                        bounds[level * len(tops) + row * chunks_x + x] = rectangle
                    left = right
        self._empty_bounds = bounds
        # The same conservative 2x2 grid can also skip AIR below a roof.
        # Every occupied voxel (including water) contributes a height bit.
        # Merge only rows containing a below-roof gap; outdoor rays retain
        # the original above-terrain cache and its cheaper lookup path.
        rooms = [None] * len(bounds)
        for level in range(world.height):
            bit = 1 << level
            for row in range(chunks_y):
                left = 0
                while left < chunks_x:
                    if occupied[row * chunks_x + left] & bit:
                        left += 1
                        continue
                    right = left + 1
                    while right < chunks_x and not occupied[row * chunks_x + right] & bit:
                        right += 1
                    if any(tops[row * chunks_x + x] > level for x in range(left, right)):
                        low, high = row, row + 1
                        while low > 0 and all(not occupied[(low - 1) * chunks_x + x] & bit
                                              for x in range(left, right)):
                            low -= 1
                        while high < chunks_y and all(not occupied[high * chunks_x + x] & bit
                                                      for x in range(left, right)):
                            high += 1
                        mask = 0
                        for y in range(low, high):
                            for x in range(left, right):
                                mask |= occupied[y * chunks_x + x]
                        bottom = (mask & (bit - 1)).bit_length()
                        above = mask >> (level + 1)
                        ceiling = level + (above & -above).bit_length() if above else world.height
                        rectangle = (left * 2, low * 2, right * 2, high * 2, bottom, ceiling)
                        for x in range(left, right):
                            index = row * chunks_x + x
                            if tops[index] > level:
                                rooms[level * len(tops) + index] = rectangle
                    left = right
        self._room_bounds = rooms
        self._world_revision = world.revision

    def scene(self, player: Player, width: int, height: int, time_seconds: float = 0.0) -> list[list[str]]:
        if width < 1 or height < 1:
            return []
        if self._size != (width, height):
            focal = width / (2 * math.tan(math.radians(82) / 2))
            self._focal = focal
            self._columns = [(x + 0.5 - width / 2) / focal for x in range(width)]
            self._rows = [(height / 2 - y - 0.5) / (focal * self.cell_aspect)
                          for y in range(height)]
            self._size = (width, height)

        world = self.world
        self.scenery.prepare(time_seconds)
        self._update_chunks()
        chunk_tops, chunks_x = self._chunk_tops, (world.width + 1) // 2
        empty_bounds, chunk_count = self._empty_bounds, len(chunk_tops)
        room_bounds = self._room_bounds
        skip_empty = self.skip_empty_space
        floor = math.floor
        cells, ww, wd, wh = world.cells, world.width, world.depth, world.height
        layer = ww * wd
        px, py, pz = player.x, player.y, player.eye_z
        start_x, start_y, start_z = int(px), int(py), int(pz)
        cy, sy = math.cos(player.yaw), math.sin(player.yaw)
        cp, sp = math.cos(player.pitch), math.sin(player.pitch)
        current, aspect = world.current, self.cell_aspect
        horizontal_rays = None
        if player.pitch == 0:
            # With a level camera the horizontal DDA setup is identical on
            # every scanline. Compute it once per column, not once per pixel.
            horizontal_rays = []
            for u in self._columns:
                dx, dy = cy + u * sy, sy - u * cy
                sx, sy_step = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
                ddx = abs(1 / dx) if abs(dx) > 1e-12 else 1e30
                ddy = abs(1 / dy) if abs(dy) > 1e-12 else 1e30
                initial_x = ((start_x + 1 - px) if sx > 0 else (px - start_x)) * ddx
                initial_y = ((start_y + 1 - py) if sy_step > 0 else (py - start_y)) * ddy
                horizontal_rays.append((dx, dy, sx, sy_step, ddx, ddy, initial_x, initial_y))
        ramp = RAMP
        ramp_max = len(ramp) - 1
        pixels = []
        depths = []
        # Dynamic opaque panels supply an early ray limit. Static architecture
        # can still win in front, but hidden geometry behind a door is not traced.
        door_pixels = [[" "] * width for _ in range(height)] if world.doors else None
        door_depths = [[math.inf] * width for _ in range(height)] if world.doors else None
        if world.doors:
            draw_doors(world, door_pixels, door_depths, player, self._focal, self.cell_aspect)

        for row_index, v in enumerate(self._rows):
            row = []
            depth_row = []
            panel_row = door_pixels[row_index] if door_pixels is not None else None
            panel_depth_row = door_depths[row_index] if door_depths is not None else None
            # Forward + vertical camera-plane offset, then horizontal offset.
            base_x, base_y, dz = cy * (cp - v * sp), sy * (cp - v * sp), sp + v * cp
            step_z = 1 if dz >= 0 else -1
            delta_z = abs(1.0 / dz) if abs(dz) > 1e-12 else 1e30
            initial_z = ((start_z + 1 - pz) if step_z > 0 else (pz - start_z)) * delta_z

            for column_index, u in enumerate(self._columns):
                panel_depth = panel_depth_row[column_index] if panel_depth_row is not None else math.inf
                ray_limit = panel_depth if panel_depth < 48 else 48
                if horizontal_rays is not None:
                    dx, dy, step_x, step_y, delta_x, delta_y, side_x, side_y = horizontal_rays[column_index]
                else:
                    dx, dy = base_x + u * sy, base_y - u * cy
                    step_x, step_y = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
                    delta_x = abs(1.0 / dx) if abs(dx) > 1e-12 else 1e30
                    delta_y = abs(1.0 / dy) if abs(dy) > 1e-12 else 1e30
                    side_x = ((start_x + 1 - px) if step_x > 0 else (px - start_x)) * delta_x
                    side_y = ((start_y + 1 - py) if step_y > 0 else (py - start_y)) * delta_y
                side_z = initial_z
                x, y, z = start_x, start_y, start_z
                material, axis, distance = 0, 0, 0.0

                # Rays walk the voxel grid exactly, without a sampling step size.
                for _ in range(110):
                    chunk_index = (y >> 1) * chunks_x + (x >> 1)
                    top = chunk_tops[chunk_index] if skip_empty else wh
                    room = room_bounds[z * chunk_count + chunk_index] if skip_empty and z < top else None
                    skip_volume = z >= top or room is not None
                    if skip_volume:
                        # A column's space above its highest voxel is empty.
                        # Jump to its boundary or floor plane, then resume exact
                        # traversal. Below roofs, cached AIR prisms additionally
                        # supply a conservative floor and ceiling boundary.
                        # Downward rays prefer a region at the local terrain
                        # height, avoiding repeated descents past unrelated
                        # taller columns elsewhere in a larger rectangle.
                        if room is None:
                            level = top if step_z < 0 else z
                            low_x, low_y, high_x, high_y, top = empty_bounds[level * chunk_count + chunk_index]
                            end_z = (pz - top) * delta_z if step_z < 0 else 1e30
                        else:
                            low_x, low_y, high_x, high_y, bottom, ceiling = room
                            end_z = ((ceiling - pz) if step_z > 0 else (pz - bottom)) * delta_z
                        end_x = ((high_x if step_x > 0 else low_x) - px) * step_x * delta_x
                        end_y = ((high_y if step_y > 0 else low_y) - py) * step_y * delta_y
                        if end_x <= end_y and end_x <= end_z:
                            distance, axis = end_x, 0
                        elif end_y <= end_z:
                            distance, axis = end_y, 1
                        else:
                            distance, axis = end_z, 2
                        if distance > ray_limit:
                            break
                        if room is not None and ((axis != 0 and abs(dx) > 1e-12
                                                  and abs(px + dx * distance - round(px + dx * distance)) < 1e-7)
                                                 or (axis != 1 and abs(dy) > 1e-12
                                                     and abs(py + dy * distance - round(py + dy * distance)) < 1e-7)
                                                 or (axis != 2 and abs(dz) > 1e-12
                                                     and abs(pz + dz * distance - round(pz + dz * distance)) < 1e-7)):
                            # At exact room corners, accumulated DDA rounding
                            # determines which touching face wins. Preserve its
                            # ordinary stepping for those few boundary rays.
                            skip_volume = False
                    if skip_volume:
                        advance = distance + 1e-7
                        x, y, z = floor(px + dx * advance), floor(py + dy * advance), floor(pz + dz * advance)
                        if not (0 <= x < ww and 0 <= y < wd and 0 <= z < wh):
                            break
                        material = cells[z * layer + y * ww + x]
                        if material and material != WATER:
                            # Most downward meadow rays land on this plane.
                            # Do not rebuild DDA crossings after their hit.
                            break
                        side_x = (x + (step_x > 0) - px) * step_x * delta_x
                        side_y = (y + (step_y > 0) - py) * step_y * delta_y
                        side_z = (z + (step_z > 0) - pz) * step_z * delta_z
                    elif side_x <= side_y and side_x <= side_z:
                        distance, side_x, x, axis = side_x, side_x + delta_x, x + step_x, 0
                    elif side_y <= side_z:
                        distance, side_y, y, axis = side_y, side_y + delta_y, y + step_y, 1
                    else:
                        distance, side_z, z, axis = side_z, side_z + delta_z, z + step_z, 2
                    if distance > ray_limit or not (0 <= x < ww and 0 <= y < wd and 0 <= z < wh):
                        break
                    material = cells[z * layer + y * ww + x]
                    if material == WATER:
                        # Water is a lower, flat surface inside its voxel. Rays
                        # can cross the air above it without hitting a solid wall.
                        surface = (WATER_LEVEL - pz) / dz if dz < -1e-12 else -1.0
                        if distance - 1e-8 <= surface <= min(side_x, side_y, side_z) + 1e-8:
                            distance, axis = surface, 2
                        else:
                            material = AIR
                    if material:
                        break

                if not material:
                    row.append(panel_row[column_index] if panel_row is not None else " ")
                    depth_row.append(panel_depth)
                    continue
                depth_row.append(distance)
                # Sample just inside the surface so equivalent traversal paths
                # choose the same texel/wind cell at integer grid boundaries.
                sample_distance = distance + 1e-8
                hx, hy, hz = px + dx * sample_distance, py + dy * sample_distance, pz + dz * sample_distance
                if material == WATER:
                    wave = _river_ripple(hx, hy, time_seconds)
                    # Points and foam have no direction. Skip current/projection
                    # work for those samples, retaining the same visible pattern.
                    if distance > 24:
                        if wave <= 0.6:
                            row.append(".")
                            continue
                    elif wave <= 0:
                        row.append(":" if wave > -0.65 else ".")
                        continue
                    elif wave > 1.28 and distance < 18:
                        row.append("*")
                        continue
                    # Differentiate perspective projection along the same local
                    # current used by movement. The common focal/depth factor
                    # cancels; dz supplies the vertical perspective term. Streaks
                    # converge toward the horizon instead of facing screen X.
                    flow_x, flow_y = current(hx)
                    along_flow = cy * flow_x + sy * flow_y
                    stroke = _flow_glyph(sy * flow_x - cy * flow_y - u * cp * along_flow,
                                         aspect * dz * along_flow)
                    row.append("~" if wave > 0.72 and stroke == "-" and distance <= 24 else stroke)
                    continue
                if axis == 0:
                    a, b, light = hy, hz, (0.87 if step_x > 0 else 0.54)
                elif axis == 1:
                    a, b, light = hx, hz, (0.72 if step_y > 0 else 0.45)
                else:
                    a, b, light = hx, hy, (0.93 if step_z < 0 else 0.40)
                fu, fv = a % 1.0, b % 1.0

                if material == GRASS:
                    noise = (int(hx * 6.0) * 73856093 ^ int(hy * 6.0) * 19349663) & 15
                    wx, wy = self.scenery.wind_at(hx, hy)
                    # A continuous turf layer covers every grass surface, even
                    # where individual blades become subpixel or leave the LOD.
                    row.append(",;\"'"[(noise // 4 + int((wx + wy * 0.6 + 0.6) * 3)) % 4])
                    continue
                elif material == PATH:
                    noise = (int(hx * 10) * 17 + int(hy * 10) * 31) % 13
                    texture = 0.26 if noise > 2 else 0.15
                elif material in (WOOD, BRIDGE):
                    # Crosswise deck planks; long grain on posts and rails.
                    grain = (a * 8 + math.sin(b * 5) * 0.12) % 1.0
                    texture = 0.75 if grain > 0.12 else 0.40
                    if axis == 2 and (hy * 2.5) % 1.0 < 0.09:
                        texture = 0.22
                elif material == LEAVES:
                    noise = (int(a * 7) * 37 ^ int(b * 7) * 19) % 9
                    texture = 0.38 + noise * 0.045
                elif material == FLOOR:
                    # Large tiled floor with darker grout and a quiet checker.
                    texture = 0.29 if (int(a) + int(b)) % 2 else 0.21
                    if fu < 0.035 or fv < 0.035:
                        texture = 0.12
                elif material == METAL:
                    texture = 0.9 if 0.09 < fu < 0.91 else 0.48
                    if fv < 0.065 or fv > 0.935:
                        texture = 1.0
                    if 0.43 < fu < 0.57:
                        texture = 0.72
                elif material == CRATE:
                    # Framed wood with diagonal bracing on every face.
                    edge = fu < 0.09 or fu > 0.91 or fv < 0.09 or fv > 0.91
                    brace = abs(fu - fv) < 0.065 or abs(fu + fv - 1) < 0.065
                    texture = 0.94 if edge or brace else 0.42 + (int(a * 14) % 3) * 0.06
                else:
                    # Staggered masonry courses, including horizontal wall tops.
                    course = int(b * 2)
                    joint = (a + (course % 2) * 0.5) % 1.0
                    texture = 0.84
                    if (b * 2) % 1.0 < 0.075 or joint < 0.045:
                        texture = 0.30

                fog = 1.0 / (1.0 + distance * 0.047)
                brightness = texture * light * fog * 1.30
                if brightness > 1.0:
                    brightness = 1.0
                shade = int(brightness * ramp_max)
                row.append(ramp[shade if shade > 0 else 1])
            pixels.append(row)
            depths.append(depth_row)
        self.scenery.draw(pixels, depths, player, time_seconds, self._focal, self.cell_aspect)
        draw_combat(world.combat, world, pixels, depths, player,
                    self._focal, self.cell_aspect, time_seconds)
        return pixels

    def frame(self, player: Player, width: int, height: int, fps: float = 0.0,
              show_map: bool = False, help_open: bool = False, paused: bool = False,
              time_seconds: float = 0.0, notice: str = "", sound_on: bool | None = None,
              keyboard_look: bool = False, mouse_captured: bool | None = None) -> list[str]:
        width, height = max(1, width), max(1, height)
        if width < 60 or height < 20:
            lines = ["MONOLITH / TERMINAL 3D", "", "Enlarge the terminal to at least 60 x 20.",
                     f"Current size: {width} x {height}", "", "ESC to exit"]
            return [line[:width].ljust(width) for line in (lines + [""] * height)[:height]]
        view_height = height - 5
        pixels = self.scene(player, width, view_height, time_seconds)
        middle_x, middle_y = width // 2, view_height // 2
        pixels[middle_y][middle_x] = "+"
        if show_map:
            self._map(pixels, player)
        target = self.world.interaction_target(player)
        prompt = notice
        if not prompt and target:
            action = ("Close" if target.target_open else "Open") if isinstance(target, Door) else "Collect"
            prompt = f"[E] {action} {target.name}"
            if not isinstance(target, Door) and self.world.combat.held_item is not None:
                prompt += f" (drop {self.world.combat.held_item.name})"
        if prompt and not help_open and not paused:
            prompt = "  " + prompt[:width - 6] + "  "
            self._write(pixels, (width - len(prompt)) // 2, view_height - 2, prompt)
        if help_open:
            look = "ARROWS        look / aim" if keyboard_look else "MOUSE         look / aim"
            attack = "ENTER         attack" if keyboard_look else "LEFT CLICK    attack"
            lines = ["CONTROLS", "", "WASD          move / strafe",
                     "SHIFT / SPACE sprint / jump", look, attack,
                     "E             open / use / collect",
                     "One held item; collect another to swap.",
                     "M / TAB       map       F sound",
                     "R             return to entrance",
                     "H back        P resume  ESC quit"]
            if not keyboard_look:
                lines.insert(6, "Click terminal to capture; P releases mouse.")
            self._panel(pixels, lines)
        elif paused:
            lines = ["PAUSED", "", "P    resume", "H    controls", "ESC  quit"]
            self._panel(pixels, lines)

        heading = (90 - math.degrees(player.yaw)) % 360
        compass = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[int((heading + 22.5) // 45) % 8]
        if player.in_water:
            state = "WADING"
        elif not player.grounded:
            state = "AIRBORNE"
        else:
            state = "SPRINT" if player.running else "WALK"
        held = self.world.combat.held_item
        equipment = held.name.upper() if held is not None else "UNARMED"
        maximum = max(1, player.max_hp)
        health = max(0, min(player.hp, maximum))
        filled = math.ceil(health * 10 / maximum)
        bar = "#" * filled + "-" * (10 - filled)
        title = f"  HP [{bar}] {health}/{maximum} / " + equipment
        rate = f"{fps:4.0f} FPS  "
        if sound_on is not None:
            rate = ("SND ON  " if sound_on else "SND OFF  ") + rate
        top = title + " " * max(1, width - len(title) - len(rate)) + rate
        status = f"  {self.world.area(player.x, player.y)}   /   {compass} {heading:03.0f}   /   {state}"
        position = f"{player.x:04.1f}, {player.y:04.1f}  "
        status += " " * max(1, width - len(status) - len(position)) + position
        if help_open:
            controls = "  H back  P resume  ESC quit"
        elif paused:
            controls = "  P resume  H controls  ESC quit"
        elif not keyboard_look and mouse_captured is False:
            controls = " Click to capture mouse  E interact  H controls  P pause"
        elif width >= 100:
            look, attack = ("ARROWS", "ENTER") if keyboard_look else ("MOUSE", "LEFT CLICK")
            controls = f"  WASD move  {look} look  {attack} attack  E interact  M map  H controls  P pause"
        else:
            look, attack = ("ARROWS", "ENTER") if keyboard_look else ("MOUSE", "LMB")
            controls = f" WASD move {look} look {attack} attack E use H help P pause"
        lines = [top, "-" * width] + ["".join(row) for row in pixels]
        lines += ["-" * width, status, controls]
        return [line[:width].ljust(width) for line in lines]

    def _map(self, pixels: list[list[str]], player: Player) -> None:
        # Scale the whole enlarged map to the available space, preserving the
        # approximate physical aspect of two north/south cells per text row.
        max_width, max_height = min(43, len(pixels[0]) // 3), len(pixels) - 4
        if max_width < 16 or max_height < 8:
            return
        scale = max(1.0, self.world.width / max_width, self.world.depth / (2 * max_height))
        map_width = math.ceil(self.world.width / scale)
        map_height = math.ceil(self.world.depth / (2 * scale))
        left, top = len(pixels[0]) - map_width - 3, 1
        self._write(pixels, left, top, "+" + "-" * map_width + "+")
        key = (self.world.revision, len(pixels[0]), len(pixels), len(self.world.trees))
        if key != self._map_key:
            rows = []
            for row in range(map_height):
                y0 = self.world.depth - 1 - int(row * 2 * scale)
                y1 = max(0, self.world.depth - int((row + 1) * 2 * scale))
                chars = []
                for column in range(map_width):
                    x0, x1 = int(column * scale), min(self.world.width, math.ceil((column + 1) * scale))
                    priority, char = 0, " "
                    for y in range(y1, y0 + 1):
                        for x in range(x0, x1):
                            material = self.world.get(x, y, 0)
                            obstacle = self.world.get(x, y, 1) or (x, y) in self.world.trees
                            if obstacle:
                                rank, symbol = 5, "#"
                            elif material == BRIDGE:
                                rank, symbol = 4, "="
                            elif material == WATER:
                                rank, symbol = 3, "~"
                            elif material == PATH:
                                rank, symbol = 2, "."
                            elif material == GRASS:
                                rank, symbol = 1, ","
                            else:
                                rank, symbol = 0, " "
                            if rank >= priority:
                                priority, char = rank, symbol
                    chars.append(char)
                rows.append("|" + "".join(chars) + "|")
            self._map_rows, self._map_key = rows, key
        for row, line in enumerate(self._map_rows):
            self._write(pixels, left, top + row + 1, line)
        marker_x = left + 1 + min(map_width - 1, max(0, int(player.x / scale)))
        marker_y = top + 1 + min(map_height - 1, max(0, int((self.world.depth - 1 - player.y) / (2 * scale))))
        direction = (">", "^", "<", "v")[int((player.yaw + math.pi / 4) / (math.pi / 2)) % 4]
        pixels[marker_y][marker_x] = direction
        self._write(pixels, left, top + map_height + 1, "+" + "-" * map_width + "+")
        legend = "N ^  ~ river  = bridge  , grass"
        self._write(pixels, left, top + map_height + 2, legend[:map_width + 2])

    @staticmethod
    def _write(pixels: list[list[str]], x: int, y: int, text: str) -> None:
        if 0 <= y < len(pixels):
            for index, char in enumerate(text):
                if 0 <= x + index < len(pixels[y]):
                    pixels[y][x + index] = char

    def _panel(self, pixels: list[list[str]], lines: list[str]) -> None:
        size = max(len(line) for line in lines) + 6
        x, y = (len(pixels[0]) - size) // 2, max(0, (len(pixels) - len(lines) - 2) // 2)
        self._write(pixels, x, y, "+" + "-" * (size - 2) + "+")
        for i, line in enumerate(lines):
            self._write(pixels, x, y + i + 1, "|  " + line.ljust(size - 6) + "  |")
        self._write(pixels, x, y + len(lines) + 1, "+" + "-" * (size - 2) + "+")

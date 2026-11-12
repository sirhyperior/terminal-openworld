"""Perspective voxel and continuous-surface rays, sharing exact depth tests."""

import heapq
import math

from .player import Player
from .doors import Door
from .door_render import draw_doors
from .combat_render import draw_combat, large_opaque_enemy
from .geometry import Camera
from .scenery import Scenery
from .world import (AIR, BRIDGE, CRATE, FLOOR, GRASS, LEAVES, METAL, PATH, WATER,
                    WATER_LEVEL, WOOD, World, river_center)


RAMP = " .,:;!+=*#%@"


def _analytic_depth_rows(boxes, camera):
    """Conservative projected bounds, swept in spans rather than per box/pixel.

    Each pixel receives the nearest possible forward depth of any selected
    analytic AABB. Projection never supplies a hit. A box crossing the near
    plane uses the whole viewport, retaining rays arbitrarily close to the eye.
    Work is bounded by eight projections and one interval per box/scanline,
    plus one viewport's worth of output writes, even for overlapping boxes.
    """
    width, height = camera.width, camera.height
    intervals = [[] for _ in range(height)]
    for box in boxes:
        points = [camera.project(x, y, z)
                  for x in (box.x0, box.x1) for y in (box.y0, box.y1) for z in (box.z0, box.z1)]
        if any(point is None for point in points):
            # This conservative full-view interval dominates every other
            # nonnegative bound. Avoid preparing redundant overlapping spans.
            return [[0.0] * width for _ in range(height)]
        else:
            # Integer sample centers match Camera.project. Expand both edges
            # and depth for the query's endpoint/coincident-face tolerances.
            left = max(0, math.floor(min(p[0] for p in points) - 1e-7))
            right = min(width, math.ceil(max(p[0] for p in points) + 1e-7) + 1)
            low = max(0, math.floor(min(p[1] for p in points) - 1e-7))
            high = min(height, math.ceil(max(p[1] for p in points) + 1e-7) + 1)
            depth = max(0.0, min(p[2] for p in points) - 1e-7)
        if left >= right:
            continue
        for row in range(low, high):
            intervals[row].append((left, depth, right))
    rows = []
    for entries in intervals:
        entries.sort()
        heap = []
        row = [math.inf] * width
        column = index = 0
        while column < width:
            while index < len(entries) and entries[index][0] <= column:
                _, depth, end = entries[index]
                heapq.heappush(heap, (depth, end))
                index += 1
            while heap and heap[0][1] <= column:
                heapq.heappop(heap)
            end = entries[index][0] if index < len(entries) else width
            if heap:
                depth, stop = heap[0]
                end = min(end, stop)
                row[column:end] = [depth] * (end - column)
            column = end
        rows.append(row)
    return rows


def _extend_horizon(skyline, origin_x, origin_y, eye, top, x0, y0, x1, y1):
    """Bound a rectangle's upward slope for every origin in one camera cell."""
    if top <= eye:
        return True
    if (x0 < origin_x + 1 and x1 > origin_x
            and y0 < origin_y + 1 and y1 > origin_y):
        return False
    relative_x = x0 - (origin_x + 1), x1 - origin_x
    relative_y = y0 - (origin_y + 1), y1 - origin_y
    dx, dy = max(relative_x[0], -relative_x[1], 0), max(relative_y[0], -relative_y[1], 0)
    distance_squared = dx * dx + dy * dy
    slope = (top - eye) ** 2 / distance_squared if distance_squared else math.inf
    angles = sorted(math.atan2(y, x) % math.tau for x in relative_x for y in relative_y)
    gaps = [angles[i + 1] - angles[i] for i in range(3)]
    gaps.append(angles[0] + math.tau - angles[3])
    gap = max(range(4), key=gaps.__getitem__)
    start = angles[(gap + 1) % 4]
    end = start + math.tau - gaps[gap]
    scale = 128 / math.tau
    first, last = math.floor(start * scale) - 1, math.floor(end * scale) + 1
    for index in range(first, last + 1):
        index %= 128
        if slope > skyline[index]:
            skyline[index] = slope
    return True


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


def _clear_rectangles(clear, width, height):
    """Partition clear cells in linear time by joining matching row runs.

    Every cell belongs to at most one rectangle. Unlike expanding each run
    through all neighboring rows, this also bounds cache construction on large
    plateaus and open interiors without changing the exact ray traversal.
    """
    active = {}
    complete = []
    for y in range(height):
        following = {}
        x = 0
        offset = y * width
        while x < width:
            if not clear[offset + x]:
                x += 1
                continue
            left = x
            x += 1
            while x < width and clear[offset + x]:
                x += 1
            key = left, x
            rectangle = active.pop(key, None)
            if rectangle is None:
                rectangle = [left, y, x, y + 1]
            else:
                rectangle[3] = y + 1
            following[key] = rectangle
        complete.extend(active.values())
        active = following
    complete.extend(active.values())
    return complete


def _overlapping_clear_runs(clear, width, height):
    """Recover maximal row-run overlaps with two linear vertical passes.

    Each cell's vertical clear interval is known before joining a row run.
    Intersecting those intervals gives the same overlap as extending the run
    through neighboring rows, without rescanning its rectangle's entire area.
    """
    lower, upper = [0] * len(clear), [height] * len(clear)
    starts = [0] * width
    for y in range(height):
        offset = y * width
        for x in range(width):
            index = offset + x
            if clear[index]:
                lower[index] = starts[x]
            else:
                starts[x] = y + 1
    ends = [height] * width
    for y in range(height - 1, -1, -1):
        offset = y * width
        for x in range(width):
            index = offset + x
            if clear[index]:
                upper[index] = ends[x]
            else:
                ends[x] = y
    for y in range(height):
        offset, x = y * width, 0
        while x < width:
            if not clear[offset + x]:
                x += 1
                continue
            left = x
            x += 1
            while x < width and clear[offset + x]:
                x += 1
            yield left, y, x, max(lower[offset + left:offset + x]), min(upper[offset + left:offset + x])


class Renderer:
    def __init__(self, world: World, cell_aspect: float = 0.5, skip_empty_space: bool = True,
                 combat_depth_prepass: bool = True, backend: str = 'cpu'):
        self.world = world
        self.cell_aspect = cell_aspect
        self._size = (0, 0)
        self._columns: list[float] = []
        self._rows: list[float] = []
        self._focal = 1.0
        self.scenery = Scenery(world)
        self.skip_empty_space = skip_empty_space
        self.combat_depth_prepass = combat_depth_prepass and skip_empty_space
        self.combat_prepass_used = False
        self._world_revision = -1
        self._chunk_tops = []
        self._empty_bounds = []
        self._empty_columns = []
        self._room_bounds = []
        self._map_key = None
        self._map_rows = []
        self._ceiling_key = None
        self._ceiling_top = world.height
        self._horizon_tops = []
        self._horizon_key = None
        self._sky_horizon = None
        self._analytic_horizon_key = None
        self._analytic_sky_horizon = None
        self.cache_stats = {}
        self.ray_backend = None
        self.backend_name = 'cpu'
        self.backend_error = ''
        if backend not in ('cpu', 'gpu', 'auto'):
            raise ValueError('renderer backend must be cpu, gpu or auto')
        if backend != 'cpu':
            try:
                from .gpu_renderer import GPUBackend
                self.ray_backend = GPUBackend(world, cell_aspect)
                self.backend_name = 'gpu'
            except Exception as error:
                self.backend_error = str(error)

    def close(self):
        if self.ray_backend is not None:
            backend, self.ray_backend = self.ray_backend, None
            try:
                backend.close()
            except Exception as error:
                self.backend_error = str(error)

    def prepare_world(self) -> None:
        """Build static traversal caches before interactive input/audio starts."""
        self._update_chunks()
        if self.world.heightfield is not None:
            self.world.heightfield.prepare()

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
        blocks_x, blocks_y = (chunks_x + 1) // 2, (((world.depth + 1) // 2) + 1) // 2
        block_tops = [0] * (blocks_x * blocks_y)
        for y in range((world.depth + 1) // 2):
            for x in range(chunks_x):
                index = (y >> 1) * blocks_x + (x >> 1)
                block_tops[index] = max(block_tops[index], tops[y * chunks_x + x])
        self._horizon_tops = block_tops
        # Keep overlapping clear rectangles, so rays can take the same broad
        # jumps from every row. Vertical interval intersection bounds building
        # work linearly instead of repeatedly searching neighboring rows.
        chunks_y = (world.depth + 1) // 2
        bounds = [None] * (world.height * len(tops))
        columns = [None] * len(bounds)
        highest = max(tops, default=0)
        whole = (0, 0, chunks_x * 2, chunks_y * 2, highest)
        for level in range(world.height):
            base = level * len(tops)
            if level >= highest:
                bounds[base:base + len(tops)] = [whole] * len(tops)
                columns[base:base + len(tops)] = [whole] * len(tops)
                continue
            clear = [top <= level for top in tops]
            if not any(clear):
                continue
            for left, row, right, low, high in _overlapping_clear_runs(clear, chunks_x, chunks_y):
                # Downward lookups choose level=the current chunk top, which
                # belongs to this rectangle and therefore equals its maximum.
                # Upward lookups never use the rectangle's floor boundary.
                rectangle = (left * 2, low * 2, right * 2, high * 2, level)
                run = [rectangle] * (right - left)
                start = base + row * chunks_x + left
                bounds[start:start + len(run)] = run
            # A row's horizontal span can be limited by distant hills far to
            # one side of a north-facing ray. A transposed atlas gives the same
            # conservative overlaps in the other direction. Choose by the
            # dominant horizontal ray component, once per pixel.
            transposed = [clear[y * chunks_x + x] for x in range(chunks_x)
                          for y in range(chunks_y)]
            for low, column, high, left, right in _overlapping_clear_runs(transposed, chunks_y, chunks_x):
                rectangle = (left * 2, low * 2, right * 2, high * 2, level)
                for y in range(low, high):
                    columns[base + y * chunks_x + column] = rectangle
        self._empty_bounds = bounds
        self._empty_columns = columns
        # The same conservative 2x2 grid can also skip AIR below a roof.
        # Every occupied voxel (including water) contributes a height bit.
        # Merge only rows containing a below-roof gap; outdoor rays retain
        # the original above-terrain cache and its cheaper lookup path.
        rooms = [None] * len(bounds)
        room_masks = {}
        union_cells, fallback_runs = 0, 0
        for level in range(max(tops, default=0)):
            bit = 1 << level
            clear = [not mask & bit for mask in occupied]
            base = level * len(tops)
            for left, low, right, high in _clear_rectangles(clear, chunks_x, chunks_y):
                indices = [y * chunks_x + x for y in range(low, high)
                           for x in range(left, right)]
                if not any(tops[index] > level for index in indices):
                    continue
                key = left, low, right, high
                mask = room_masks.get(key)
                if mask is None:
                    mask = 0
                    for index in indices:
                        mask |= occupied[index]
                    union_cells += len(indices)
                    room_masks[key] = mask
                bottom = (mask & (bit - 1)).bit_length()
                above = mask >> (level + 1)
                ceiling = level + (above & -above).bit_length() if above else world.height
                rectangle = (left * 2, low * 2, right * 2, high * 2, bottom, ceiling)
                for index in indices:
                    if tops[index] > level:
                        rooms[base + index] = rectangle
            # Restore overlapping room skips where they buy broad traversal.
            # Memoized unions are free across rows/heights. A strict scan
            # budget bounds unusual fragmented geometry; disjoint prisms above
            # remain an exact fallback rather than rescanning large regions.
            remaining = len(tops) * 8
            for left, row, right, low, high in _overlapping_clear_runs(clear, chunks_x, chunks_y):
                offset = row * chunks_x
                if not any(tops[offset + x] > level for x in range(left, right)):
                    continue
                key = left, low, right, high
                mask = room_masks.get(key)
                if mask is None:
                    work = (right - left) * (high - low)
                    if work > remaining:
                        fallback_runs += 1
                        continue
                    remaining -= work
                    union_cells += work
                    mask = 0
                    for y in range(low, high):
                        for x in range(left, right):
                            mask |= occupied[y * chunks_x + x]
                    room_masks[key] = mask
                bottom = (mask & (bit - 1)).bit_length()
                above = mask >> (level + 1)
                ceiling = level + (above & -above).bit_length() if above else world.height
                rectangle = (left * 2, low * 2, right * 2, high * 2, bottom, ceiling)
                for x in range(left, right):
                    index = offset + x
                    if tops[index] > level:
                        rooms[base + index] = rectangle
        self._room_bounds = rooms
        self.cache_stats = {"chunks": len(tops), "room_union_cells": union_cells,
                            "room_union_budget": len(tops) * world.height * 9,
                            "room_overlap_fallback_runs": fallback_runs}
        self._world_revision = world.revision

    def _local_ceiling(self, player, cp, sp):
        """Conservative voxel ceiling over every possible ray endpoint.

        Rays are not normalized: use the actual camera-plane extrema rather
        than assuming the 48-depth limit means a 48-unit horizontal radius.
        Snapped camera tiles allow reuse during ordinary movement. Only voxel
        traversal uses this ceiling; panels, trunks and combat still draw into
        their shared depth buffers independently.
        """
        forward = max(abs(cp - self._rows[0] * sp), abs(cp - self._rows[-1] * sp))
        side = max(abs(self._columns[0]), abs(self._columns[-1]))
        radius = math.ceil(48 * math.hypot(forward, side)) + 2
        tile_x, tile_y = math.floor(player.x / 8), math.floor(player.y / 8)
        key = self.world.revision, tile_x, tile_y, radius
        if key != self._ceiling_key:
            chunks_x = (self.world.width + 1) // 2
            left = max(0, (tile_x * 8 - radius) // 2)
            low = max(0, (tile_y * 8 - radius) // 2)
            right = min(chunks_x, (tile_x * 8 + 8 + radius) // 2 + 1)
            high = min((self.world.depth + 1) // 2, (tile_y * 8 + 8 + radius) // 2 + 1)
            self._ceiling_top = max((max(self._chunk_tops[y * chunks_x + left:y * chunks_x + right], default=0)
                                     for y in range(low, high)), default=0)
            self._ceiling_key = key
        return self._ceiling_top

    def _prepare_horizon(self, player, cp, sp):
        """Conservative voxel skyline for every origin in the camera cell.

        Four-cell blocks bound voxel tops; expanded relative XY rectangles
        include the entire integer camera-origin cell. Their nearest distance
        and lowest possible eye height overestimate every upward slope. Angular
        bins include the full corner interval plus adjacent bins for rounding.
        Dynamic panels, scenery and combat retain their independent depth pass.
        """
        forward = max(abs(cp - self._rows[0] * sp), abs(cp - self._rows[-1] * sp))
        side = max(abs(self._columns[0]), abs(self._columns[-1]))
        radius = math.ceil(48 * math.hypot(forward, side)) + 2
        origin_x, origin_y = math.floor(player.x), math.floor(player.y)
        eye = math.floor(player.eye_z * 4) / 4
        key = self.world.revision, origin_x, origin_y, eye, radius
        if key == self._horizon_key:
            return self._sky_horizon
        world = self.world
        blocks_x, blocks_y = (world.width + 3) // 4, (world.depth + 3) // 4
        left, low = max(0, (origin_x - radius) // 4), max(0, (origin_y - radius) // 4)
        right = min(blocks_x, (origin_x + 1 + radius) // 4 + 1)
        high = min(blocks_y, (origin_y + 1 + radius) // 4 + 1)
        skyline = [0.0] * 128
        chunks_x, chunks_y = (world.width + 1) // 2, (world.depth + 1) // 2
        for by in range(low, high):
            for bx in range(left, right):
                top = self._horizon_tops[by * blocks_x + bx]
                if top <= eye:
                    continue
                x0, y0 = bx * 4, by * 4
                x1, y1 = min(world.width, x0 + 4), min(world.depth, y0 + 4)
                parts = [(top, x0, y0, x1, y1)]
                if (x0 < origin_x + 1 and x1 > origin_x
                        and y0 < origin_y + 1 and y1 > origin_y):
                    # Split only the origin block: a nearby bridge rail need
                    # not disable every azimuth for a clear camera column.
                    parts = [(self._chunk_tops[cy * chunks_x + cx], cx * 2, cy * 2,
                              min(world.width, cx * 2 + 2), min(world.depth, cy * 2 + 2))
                             for cy in range(by * 2, min(chunks_y, by * 2 + 2))
                             for cx in range(bx * 2, min(chunks_x, bx * 2 + 2))]
                for top, x0, y0, x1, y1 in parts:
                    if not _extend_horizon(skyline, origin_x, origin_y, eye, top, x0, y0, x1, y1):
                        # A roof/tall wall in the camera's own 2x2 region
                        # makes the bound uninformative; trace ordinary rays.
                        self._sky_horizon, self._horizon_key = None, key
                        return None
        self._sky_horizon, self._horizon_key = skyline, key
        return skyline

    def _prepare_analytic_horizon(self, player, cp, sp):
        """Conservative independent skyline for continuous ground and solids."""
        forward = max(abs(cp - self._rows[0] * sp), abs(cp - self._rows[-1] * sp))
        side = max(abs(self._columns[0]), abs(self._columns[-1]))
        radius = math.ceil(48 * math.hypot(forward, side)) + 2
        origin_x, origin_y = math.floor(player.x), math.floor(player.y)
        eye = math.floor(player.eye_z * 4) / 4
        world, ground = self.world, self.world.heightfield
        key = (world.revision, id(ground), ground.revision if ground is not None else None,
               origin_x, origin_y, eye, radius)
        if key == self._analytic_horizon_key:
            return self._analytic_sky_horizon
        skyline = [0.0] * 128
        if ground is not None:
            size = ground.CHUNK
            left, low = max(0, (origin_x - radius) // size), max(0, (origin_y - radius) // size)
            right = min((ground.width + size - 1) // size, (origin_x + 1 + radius) // size + 1)
            high = min((ground.depth + size - 1) // size, (origin_y + 1 + radius) // size + 1)
            for cy in range(low, high):
                for cx in range(left, right):
                    _, top = ground._chunk_bounds(cx, cy)
                    if top <= eye or top == -math.inf:
                        continue
                    x0, y0 = cx * size, cy * size
                    x1, y1 = min(ground.width, x0 + size), min(ground.depth, y0 + size)
                    if (x0 <= origin_x < x1 and y0 <= origin_y < y1):
                        # A high point elsewhere in this coarse chunk must not
                        # make every direction unbounded around a low player.
                        parts = [(ground.cell_bounds(x, y)[1], x, y, x + 1, y + 1)
                                 for y in range(y0, y1) for x in range(x0, x1)
                                 if ground.enabled[y * ground.width + x]]
                    else:
                        parts = [(top, x0, y0, x1, y1)]
                    for top, x0, y0, x1, y1 in parts:
                        if not _extend_horizon(skyline, origin_x, origin_y, eye, top, x0, y0, x1, y1):
                            self._analytic_sky_horizon, self._analytic_horizon_key = None, key
                            return None
        for box in world.solids:
            if (box.x1 < origin_x - radius or box.x0 > origin_x + 1 + radius
                    or box.y1 < origin_y - radius or box.y0 > origin_y + 1 + radius):
                continue
            if not _extend_horizon(skyline, origin_x, origin_y, eye, box.z1,
                                   box.x0, box.y0, box.x1, box.y1):
                self._analytic_sky_horizon, self._analytic_horizon_key = None, key
                return None
        self._analytic_sky_horizon, self._analytic_horizon_key = skyline, key
        return skyline

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
        empty_columns = self._empty_columns
        room_bounds = self._room_bounds
        skip_empty = self.skip_empty_space
        floor = math.floor
        cells, ww, wd, wh = world.cells, world.width, world.depth, world.height
        layer = ww * wd
        px, py, pz = player.x, player.y, player.eye_z
        start_x, start_y, start_z = int(px), int(py), int(pz)
        cy, sy = math.cos(player.yaw), math.sin(player.yaw)
        cp, sp = math.cos(player.pitch), math.sin(player.pitch)
        local_ceiling = self._local_ceiling(player, cp, sp)
        sky_horizon = self._prepare_horizon(player, cp, sp) if skip_empty else None
        horizon_scale = 128 / math.tau
        current, aspect = world.current, self.cell_aspect
        origin = (px, py, pz)
        geometry_hit = None
        if world.geometry_present:
            # Query only analytic shapes that can reach a sampled camera ray.
            # The unnormalized ray parameter is forward depth, so the original
            # 48-unit ray limit is also this frustum's exact far plane.
            forward = (cy * cp, sy * cp, sp)
            right, up = (sy, -cy, 0.0), (-cy * sp, -sy * sp, cp)
            umin, umax = self._columns[0], self._columns[-1]
            vmin, vmax = self._rows[-1], self._rows[0]
            normals = [tuple(right[i] - umin * forward[i] for i in range(3)),
                       tuple(umax * forward[i] - right[i] for i in range(3)),
                       tuple(up[i] - vmin * forward[i] for i in range(3)),
                       tuple(vmax * forward[i] - up[i] for i in range(3)),
                       forward, tuple(-value for value in forward)]
            planes = [(*normal, -sum(normal[i] * origin[i] for i in range(3)))
                      for normal in normals]
            planes[-1] = (*planes[-1][:3], planes[-1][3] + 48)
            endpoints = [(px, py)] + [
                (px + 48 * (forward[0] + u * right[0] + v * up[0]),
                 py + 48 * (forward[1] + u * right[1] + v * up[1]))
                for u in (umin, umax) for v in (vmin, vmax)]
            bounds = (min(point[0] for point in endpoints), min(point[1] for point in endpoints),
                      max(point[0] for point in endpoints), max(point[1] for point in endpoints))
            geometry_hit = world.geometry_query(bounds, planes)
        analytic_minimum = getattr(geometry_hit, "minimum_depth", 0.0)
        analytic_boxes = getattr(geometry_hit, "bounds", None)
        analytic_depths = (_analytic_depth_rows(analytic_boxes,
                           Camera(player, width, height, self._focal, self.cell_aspect))
                           if analytic_boxes is not None else None)
        analytic_horizon = (self._prepare_analytic_horizon(player, cp, sp)
                            if geometry_hit is not None and skip_empty else None)
        early_height = world.heightfield.height_at(px, py) if world.heightfield is not None else None
        early_ground = skip_empty and early_height is not None
        early_misses = 0
        horizontal_rays = None
        if player.pitch == 0:
            # With a level camera the horizontal DDA setup is identical on
            # every scanline. Compute it once per column, not once per pixel.
            horizontal_rays = []
            for u in self._columns:
                dx, dy = cy + u * sy, sy - u * cy
                sx, sy_step = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
                ddx = 1.0 / dx if dx > 1e-12 else -1.0 / dx if dx < -1e-12 else 1e30
                ddy = 1.0 / dy if dy > 1e-12 else -1.0 / dy if dy < -1e-12 else 1e30
                initial_x = ((start_x + 1 - px) if sx > 0 else (px - start_x)) * ddx
                initial_y = ((start_y + 1 - py) if sy_step > 0 else (py - start_y)) * ddy
                horizon = analytic_slope = math.inf
                if sky_horizon is not None or analytic_horizon is not None:
                    azimuth = int((math.atan2(dy, dx) % math.tau) * horizon_scale) % 128
                    horizontal_squared = dx * dx + dy * dy
                    if sky_horizon is not None:
                        horizon = sky_horizon[azimuth] * horizontal_squared
                    if analytic_horizon is not None:
                        analytic_slope = analytic_horizon[azimuth] * horizontal_squared
                horizontal_rays.append((dx, dy, sx, sy_step, ddx, ddy, initial_x, initial_y,
                                        horizon, analytic_slope))
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

        combat_depths = None
        self.combat_prepass_used = False
        if self.combat_depth_prepass and world.combat.enemies:
            camera = Camera(player, width, height, self._focal, self.cell_aspect)
            if (large_opaque_enemy(world.combat, camera)
                    and self.scenery.trees.projected_work_bound(camera) < width * height * 3):
                # Hidden terrain can be omitted only when extra invisible crown
                # samples cannot exhaust the shared foliage budget. Grass counts
                # candidates before depth rejection, so its budget is unchanged.
                # Keep ordinary terrain/scenery depths: pre-seeding combat here
                # would alter root-proxy rejection and the existing raster order.
                combat_depths = [[math.inf] * width for _ in range(height)]
                combat_pixels = [[" "] * width for _ in range(height)]
                draw_combat(world.combat, world, combat_pixels, combat_depths, player,
                            self._focal, self.cell_aspect, time_seconds, labels=False)
                self.combat_prepass_used = True

        gpu_hits = None
        if self.ray_backend is not None:
            try:
                gpu_hits = self.ray_backend.render(player, width, height)
            except Exception as error:
                self.backend_error = str(error)
                self.close()
                self.backend_name = 'cpu'

        for row_index, v in enumerate(self._rows):
            row = []
            depth_row = []
            panel_row = door_pixels[row_index] if door_pixels is not None else None
            panel_depth_row = door_depths[row_index] if door_depths is not None else None
            combat_depth_row = combat_depths[row_index] if combat_depths is not None else None
            analytic_depth_row = analytic_depths[row_index] if analytic_depths is not None else None
            # Forward + vertical camera-plane offset, then horizontal offset.
            base_x, base_y, dz = cy * (cp - v * sp), sy * (cp - v * sp), sp + v * cp
            step_z = 1 if dz >= 0 else -1
            delta_z = 1.0 / dz if dz > 1e-12 else -1.0 / dz if dz < -1e-12 else 1e30
            initial_z = ((start_z + 1 - pz) if step_z > 0 else (pz - start_z)) * delta_z
            early_depth = (pz - early_height) * delta_z if early_ground else math.inf
            rising = sky_horizon is not None and dz > 0
            analytic_rising = analytic_horizon is not None and dz > 0
            dz_squared = dz * dz

            for column_index, u in enumerate(self._columns):
                panel_depth = panel_depth_row[column_index] if panel_depth_row is not None else math.inf
                ray_limit = panel_depth if panel_depth < 48 else 48
                if combat_depth_row is not None and combat_depth_row[column_index] < ray_limit:
                    ray_limit = combat_depth_row[column_index]
                gpu_hit = gpu_hits[row_index * width + column_index] if gpu_hits is not None else None
                if gpu_hit is not None and (not gpu_hit[1] or abs(gpu_hit[0] - ray_limit) > 1e-7):
                    dx, dy = base_x + u * sy, base_y - u * cy
                    step_x, step_y = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
                    distance, material, gpu_normal, axis = gpu_hit
                    if distance > ray_limit:
                        material, gpu_normal = 0, None
                    analytic_hit = None
                    query_analytic = early_query = False
                    voxel_sky = True
                else:
                    voxel_sky = False
                    analytic_near = analytic_depth_row[column_index] if analytic_depth_row is not None else analytic_minimum
                    query_analytic = geometry_hit is not None and ray_limit >= analytic_near
                    if horizontal_rays is not None:
                        (dx, dy, step_x, step_y, delta_x, delta_y, side_x, side_y,
                         horizon, analytic_slope) = horizontal_rays[column_index]
                        if analytic_rising and dz_squared > analytic_slope:
                            query_analytic = False
                        if rising and dz_squared > horizon:
                            if not query_analytic:
                                row.append(panel_row[column_index] if panel_row is not None else " ")
                                depth_row.append(panel_depth)
                                continue
                            voxel_sky = True
                    else:
                        dx, dy = base_x + u * sy, base_y - u * cy
                        # Sky rays do not need signs, reciprocal crossing deltas,
                        # or any voxel traversal initialization.
                        if rising or analytic_rising:
                            azimuth = int((math.atan2(dy, dx) % math.tau) * horizon_scale) % 128
                            horizontal_squared = dx * dx + dy * dy
                            if analytic_rising and dz_squared > analytic_horizon[azimuth] * horizontal_squared:
                                query_analytic = False
                            if rising and dz_squared > sky_horizon[azimuth] * horizontal_squared:
                                if not query_analytic:
                                    row.append(panel_row[column_index] if panel_row is not None else " ")
                                    depth_row.append(panel_depth)
                                    continue
                                voxel_sky = True
                        step_x, step_y = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
                        delta_x = 1.0 / dx if dx > 1e-12 else -1.0 / dx if dx < -1e-12 else 1e30
                        delta_y = 1.0 / dy if dy > 1e-12 else -1.0 / dy if dy < -1e-12 else 1e30
                        side_x = ((start_x + 1 - px) if step_x > 0 else (px - start_x)) * delta_x
                        side_y = ((start_y + 1 - py) if step_y > 0 else (py - start_y)) * delta_y
                    side_z = initial_z
                    inverse_x, inverse_y = step_x * delta_x, step_y * delta_y
                    ray_bounds = empty_bounds if delta_x <= delta_y else empty_columns
                    x, y, z = start_x, start_y, start_z
                    material, axis, distance = 0, 0, 0.0
                    analytic_hit = None
                    gpu_normal = None
                    early_query = early_ground and query_analytic and step_z < 0 and early_misses < 4
                # Rays walk the voxel grid exactly, without a sampling step size.
                for _ in range(0 if voxel_sky else 110):
                    if skip_empty and step_z > 0 and z >= local_ceiling:
                        break
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
                            low_x, low_y, high_x, high_y, top = ray_bounds[level * chunk_count + chunk_index]
                            end_z = (pz - top) * delta_z if step_z < 0 else 1e30
                        else:
                            low_x, low_y, high_x, high_y, bottom, ceiling = room
                            end_z = ((ceiling - pz) if step_z > 0 else (pz - bottom)) * delta_z
                        end_x = ((high_x if step_x > 0 else low_x) - px) * inverse_x
                        end_y = ((high_y if step_y > 0 else low_y) - py) * inverse_y
                        if end_x <= end_y and end_x <= end_z:
                            distance, axis = end_x, 0
                        elif end_y <= end_z:
                            distance, axis = end_y, 1
                        else:
                            distance, axis = end_z, 2
                        if early_query:
                            # The cached prism is provably empty of voxels.
                            # On continuous outdoor ground, an exact surface
                            # often wins before its first voxel boundary. Keep
                            # the voxel-first path where authored floors/walls
                            # replaced the heightfield, including interiors.
                            early_query = False
                            early_limit = min(ray_limit, distance + 1e-8)
                            if early_limit >= analytic_near and early_depth <= early_limit:
                                analytic_hit = geometry_hit(origin, (dx, dy, dz), early_limit)
                                if analytic_hit is not None:
                                    query_analytic = False
                                    break
                                if early_limit >= ray_limit:
                                    query_analytic = False
                                else:
                                    # Bound duplicate work when nearby walls
                                    # or chunk edges make early queries miss.
                                    early_misses += 1
                        if distance > ray_limit:
                            break
                        if room is not None:
                            # Fractional coordinates detect the same ambiguous
                            # grid corners without repeated round/abs calls.
                            # Ordinary DDA still decides their touching face.
                            corner = False
                            if axis != 0 and delta_x < 1e30:
                                fraction = (px + dx * distance) % 1.0
                                corner = fraction < 1e-7 or fraction > 0.9999999
                            if not corner and axis != 1 and delta_y < 1e30:
                                fraction = (py + dy * distance) % 1.0
                                corner = fraction < 1e-7 or fraction > 0.9999999
                            if not corner and axis != 2 and delta_z < 1e30:
                                fraction = (pz + dz * distance) % 1.0
                                corner = fraction < 1e-7 or fraction > 0.9999999
                            if corner:
                                skip_volume = False
                    if skip_volume:
                        advance = distance + 1e-7
                        # The crossed coordinate is an integer cache boundary.
                        # Only the other two coordinates need a floor query.
                        if axis == 0:
                            x = high_x if step_x > 0 else low_x - 1
                            y, z = floor(py + dy * advance), floor(pz + dz * advance)
                        elif axis == 1:
                            x, z = floor(px + dx * advance), floor(pz + dz * advance)
                            y = high_y if step_y > 0 else low_y - 1
                        else:
                            x, y = floor(px + dx * advance), floor(py + dy * advance)
                            z = (ceiling if step_z > 0 else bottom - 1) if room is not None else top - 1
                        if not (0 <= x < ww and 0 <= y < wd and 0 <= z < wh):
                            break
                        material = cells[z * layer + y * ww + x]
                        if material and material != WATER:
                            # Most downward meadow rays land on this plane.
                            # Do not rebuild DDA crossings after their hit.
                            break
                        side_x = (x + (step_x > 0) - px) * inverse_x
                        side_y = (y + (step_y > 0) - py) * inverse_y
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

                # Voxel AIR/sky acceleration knows nothing about analytic
                # surfaces. Query those independently, but only as far as the
                # opaque voxel/water hit already found, or a panel/combat bound.
                # Preserve the same coincident-surface tolerance as the merge.
                if query_analytic:
                    analytic_limit = min(ray_limit, distance + 1e-8) if material else ray_limit
                    if analytic_limit >= analytic_near:
                        analytic_hit = geometry_hit(origin, (dx, dy, dz), analytic_limit)
                normal = gpu_normal
                if analytic_hit is not None and (not material or analytic_hit.distance <= distance + 1e-8):
                    distance, material, normal = analytic_hit.distance, analytic_hit.material, analytic_hit.normal
                    ax, ay, az = abs(normal[0]), abs(normal[1]), abs(normal[2])
                    axis = 0 if ax >= ay and ax >= az else (1 if ay >= az else 2)
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
                if normal is not None and normal[2] > 0.0:
                    # Continuous slope lighting replaces terrace-side shading;
                    # flat stair treads retain the ordinary top-face light.
                    light = max(0.25, min(0.97, 0.76 + 0.17 * normal[2]
                                         - 0.16 * normal[0] - 0.12 * normal[1]))
                fu, fv = a % 1.0, b % 1.0

                if material == GRASS and ((axis == 2 and step_z < 0)
                                          or (normal is not None and normal[2] > 0.0)):
                    noise = (int(hx * 6.0) * 73856093 ^ int(hy * 6.0) * 19349663) & 15
                    wx, wy = self.scenery.wind_at(hx, hy)
                    # A continuous turf layer covers every grass top, even
                    # where individual blades become subpixel or leave the LOD.
                    wind = int((wx + wy * 0.6 + 0.6) * 3)
                    if normal is None:
                        row.append(",;\"'"[(noise // 4 + wind) % 4])
                    else:
                        # Restrained turf glyphs cover slopes continuously,
                        # including at the horizon beyond the blade radius.
                        fog = 1.0 / (1.0 + distance * 0.033)
                        band = min(3, max(0, int(light * fog * 4)))
                        row.append((".,", ",;", ';"', "\"'")[band][(noise + wind) % 2])
                    continue
                elif material == GRASS:
                    # Terrace lips have directional shade, so a grassy rise
                    # reads as a solid step instead of more flat turf noise.
                    texture = 0.65 if fv > 0.18 else 0.32
                elif material == PATH:
                    noise = (int(hx * 10) * 17 + int(hy * 10) * 31) % 13
                    texture = 0.35 if noise > 2 else 0.23
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
                    texture = 0.38 if (int(a) + int(b)) % 2 else 0.30
                    if fu < 0.035 or fv < 0.035:
                        texture = 0.18
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

                fog = 1.0 / (1.0 + distance * 0.033)
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
            lines = ["CONTROLS", "", "WASD          move / strafe / climb steps",
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
        position = f"{player.x:04.1f}, {player.y:04.1f}  Z {player.z:.1f}  "
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
        # Large worlds keep a readable local chart rather than shrinking a
        # doorway or trail into a single world-overview pixel. Snapped origins
        # let the static background remain cached while the player moves.
        max_width, max_height = min(43, len(pixels[0]) // 3), len(pixels) - 4
        if max_width < 16 or max_height < 8:
            return
        world = self.world
        local = max(world.width, world.depth) > 128
        span_x, span_y = (min(96, world.width), min(96, world.depth)) if local else (world.width, world.depth)
        origin_x = max(0, min(world.width - span_x, int(player.x // 16) * 16 - span_x // 2)) if local else 0
        origin_y = max(0, min(world.depth - span_y, int(player.y // 16) * 16 - span_y // 2)) if local else 0
        scale = max(1.0, span_x / max_width, span_y / (2 * max_height))
        map_width = math.ceil(span_x / scale)
        map_height = math.ceil(span_y / (2 * scale))
        left, top = len(pixels[0]) - map_width - 3, 1
        self._write(pixels, left, top, "+" + "-" * map_width + "+")
        key = (world.revision, len(pixels[0]), len(pixels), len(world.trees), origin_x, origin_y)
        if key != self._map_key:
            rows = []
            for row in range(map_height):
                y0 = origin_y + span_y - 1 - int(row * 2 * scale)
                y1 = max(origin_y, origin_y + span_y - int((row + 1) * 2 * scale))
                chars = []
                for column in range(map_width):
                    x0 = origin_x + int(column * scale)
                    x1 = min(origin_x + span_x, origin_x + int((column + 1) * scale))
                    priority, char = 0, " "
                    for y in range(y1, y0 + 1):
                        for x in range(x0, x1):
                            surface = world.surface_height(x, y)
                            material = world.surface_material(x, y)
                            if (x, y) in world.trees:
                                rank, symbol = 5, "#"
                            elif material == BRIDGE:
                                rank, symbol = 4, "="
                            elif material == WATER:
                                rank, symbol = 3, "~"
                            elif material == PATH:
                                rank, symbol = 4, "."
                            elif material == GRASS:
                                rank, symbol = 2, ("^" if surface >= 8 else ";" if surface > 1 else ",")
                            elif material:
                                rank, symbol = 6, "#"
                            else:
                                rank, symbol = 0, " "
                            if rank >= priority:
                                priority, char = rank, symbol
                    chars.append(char)
                rows.append("|" + "".join(chars) + "|")
            self._map_rows, self._map_key = rows, key
        for row, line in enumerate(self._map_rows):
            self._write(pixels, left, top + row + 1, line)
        marker_x = left + 1 + min(map_width - 1, max(0, int((player.x - origin_x) / scale)))
        marker_y = top + 1 + min(map_height - 1, max(0, int((origin_y + span_y - 1 - player.y) / (2 * scale))))
        direction = (">", "^", "<", "v")[int((player.yaw + math.pi / 4) / (math.pi / 2)) % 4]
        pixels[marker_y][marker_x] = direction
        self._write(pixels, left, top + map_height + 1, "+" + "-" * map_width + "+")
        legend = "LOCAL N^  ~ river  ^ ridge" if local else "N ^  ~ river  = bridge  , grass"
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

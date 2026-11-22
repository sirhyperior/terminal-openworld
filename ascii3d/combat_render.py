"""Bounded, depth-tested ASCII geometry for pickups and fantasy enemies."""

import math

from .combat import (BURST_DURATION, FIRE_STAFF, MAX_FIREBALLS, CombatState,
                     Enemy, NAME_REACH, SWING_DURATION, WARDEN_COLLAPSE_DURATION)
from .geometry import Camera
from .palette import ARCANE, BONE, EMBER, FIRE, STRAW, UI_POSITIVE
from .shading import DEFAULT_SHADING, MIN_SURFACE_LEVEL, RAMP, Shading, ink
from .world import METAL, STONE, WOOD


DRAW_DISTANCE = 28.0
MAX_ENEMY_DRAWS = 24
MAX_PICKUP_DRAWS = 16


def large_opaque_enemy(combat, cam):
    """Only large nearby bodies justify a second bounded geometry pass."""
    budget = min(MAX_ENEMY_DRAWS, max(1, cam.width * cam.height // 180))
    for enemy in combat.enemies:
        if not actor_visible(cam, enemy.x, enemy.y, enemy.z + 1.0, 1.25):
            continue
        if enemy.alive:
            center = cam.project(enemy.x, enemy.y, enemy.z + enemy.height / 2)
            if center is not None:
                depth = center[2]
                area = (2 * enemy.radius * enemy.height * cam.fx * cam.fy
                        / (depth * depth))
                if area >= cam.width * cam.height * 0.16:
                    return True
        budget -= 1
        if budget == 0:
            break
    return False


def actor_visible(cam, x, y, z, radius):
    """Conservatively cull a bounded actor or item before rasterizing it."""
    dx, dy, dz = x - cam.x, y - cam.y, z - cam.z
    if dx * dx + dy * dy + dz * dz > (DRAW_DISTANCE + radius) ** 2:
        return False
    for (nx, ny, nz), offset in cam.frustum:
        if dx * nx + dy * ny + dz * nz + radius * math.sqrt(nx * nx + ny * ny + nz * nz) < offset:
            return False
    return True


def _stroke(cam, pixels, depths, a, b, char=None, radius=0.0,
            material=METAL, emission=0.0, shade_bias=0):
    center = tuple((a[i] + b[i]) / 2 for i in range(3))
    depth = max(0, (center[0] - cam.x) * cam.cy + (center[1] - cam.y) * cam.sy)
    start, end = cam.project(*a), cam.project(*b)
    direction = end[0] - start[0] if start is not None and end is not None else 0
    glyph = char or ("/" if direction > 0.2 else "\\" if direction < -0.2 else "|")
    if getattr(cam, 'depth_only', False):
        cam.stroke(pixels, depths, start, end, radius, glyph)
        return
    shading = getattr(cam, "shading", DEFAULT_SHADING)
    normal = (-cam.cy, -cam.sy, 0)
    tone = shading.surface(material, *center, normal, depth, glyph=glyph, emission=emission)
    axis = tuple(b[i] - a[i] for i in range(3))
    square = sum(value * value for value in axis)

    def sample(x, y, z, distance):
        dx, dy, dz = x - a[0], y - a[1], z - a[2]
        along = (dx * axis[0] + dy * axis[1] + dz * axis[2]) / square if square > 1e-12 else 0
        nx, ny, nz = dx - along * axis[0], dy - along * axis[1], dz - along * axis[2]
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        surface_normal = (nx / length, ny / length, nz / length) if radius and length > 1e-8 else normal
        token = shading.surface(material, x, y, z, surface_normal, distance, glyph=glyph,
                                emission=emission, texture_position=(dx, dy, dz))
        if shade_bias:
            token = ink(glyph, max(MIN_SURFACE_LEVEL, min(15, token.level + shade_bias)),
                        material, token.effects)
        return token

    shader = sample if depth < 14 else None
    if shade_bias and shader is None:
        tone = ink(glyph, max(MIN_SURFACE_LEVEL, min(15, tone.level + shade_bias)),
                   material, tone.effects)
    cam.stroke(pixels, depths, start, end, radius, tone, shader=shader)


def _ring(cam, pixels, depths, x, y, z, rx, ry, rz, char=None,
          material=METAL, emission=0.0):
    points = [(x + rx * math.cos(i * math.tau / 8),
               y + ry * math.cos(i * math.tau / 8),
               z + rz * math.sin(i * math.tau / 8)) for i in range(8)]
    for i in range(8):
        _stroke(cam, pixels, depths, points[i], points[(i + 1) % 8], char,
                material=material, emission=emission)


def _clip_surface(cam, vertices):
    """Clip world faces to the near plane without losing an opaque interior."""
    nx, ny, nz = cam.frustum[0][0]
    near = cam.NEAR + 1e-7
    result = []
    previous = vertices[-1]
    before = (previous[0] - cam.x) * nx + (previous[1] - cam.y) * ny + (previous[2] - cam.z) * nz
    for point in vertices:
        after = (point[0] - cam.x) * nx + (point[1] - cam.y) * ny + (point[2] - cam.z) * nz
        if (before >= near) != (after >= near):
            fraction = (near - before) / (after - before)
            result.append(tuple(previous[i] + (point[i] - previous[i]) * fraction for i in range(3)))
        if after >= near:
            result.append(point)
        previous, before = point, after
    return result


def _surface_brush(cam, vertices, normal, material, emission):
    """Keep material coordinates attached to a moving face, not the camera."""
    a, b = vertices[:2]
    axis = tuple(b[i] - a[i] for i in range(3))
    length = math.sqrt(sum(value * value for value in axis))
    axis = tuple(value / length for value in axis)
    nx, ny, nz = normal
    ux, uy, uz = axis
    other = (ny * uz - nz * uy, nz * ux - nx * uz, nx * uy - ny * ux)
    vs = [sum((point[i] - a[i]) * other[i] for i in range(3)) for point in vertices]
    us = [sum((point[i] - a[i]) * axis[i] for i in range(3)) for point in vertices]
    u0, v0, width, height = min(us), min(vs), max(us) - min(us), max(vs) - min(vs)
    shading = getattr(cam, "shading", DEFAULT_SHADING)

    def sample(x, y, z, distance):
        dx, dy, dz = x - a[0], y - a[1], z - a[2]
        u = dx * ux + dy * uy + dz * uz
        v = dx * other[0] + dy * other[1] + dz * other[2]
        fu = (u - u0) / width if width > 1e-10 else 0.5
        fv = (v - v0) / height if height > 1e-10 else 0.5
        edge = max(0.0, min(fu, 1 - fu, fv, 1 - fv))
        glow = emission
        if material in (FIRE, ARCANE):
            # Separate luminous centers from the colored outer facets.
            glow *= 0.48 + 0.52 * min(1.0, edge * 4)
        token = shading.surface(material, x, y, z, normal, distance, emission=glow,
                                texture_position=(u, v, 0), texture_normal=(0, 0, 1))
        bias = 0
        if material in (STONE, METAL, BONE):
            # Worn edges catch light; broad armor gets a recessed chevron.
            if edge < 0.07:
                bias = 2 if material != BONE else 1
            elif material == STONE and width > 0.45 and height > 0.45 and 0.2 < fv < 0.72:
                if abs(abs(fu - 0.5) * 0.65 - (fv - 0.22)) < 0.04:
                    bias = -4
        if bias:
            level = max(MIN_SURFACE_LEVEL, min(15, token.level + bias))
            token = ink(RAMP[min(len(RAMP) - 1, int(level / 15 * (len(RAMP) - 1)))],
                        level, material, token.effects)
        return token

    return sample


def draw_actor_surface(cam, pixels, depths, vertices, char, material=METAL,
                       emission=0.0, *, cull=False, textured=True, fixed_ink=None):
    """Shade and fill an opaque actor face with the shared camera depth."""
    a, b, c = vertices[:3]
    center = tuple(sum(point[i] for point in vertices) / len(vertices) for i in range(3))
    u, v = tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))
    normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(value * value for value in normal))
    if length < 1e-12:
        return
    facing = sum(normal[i] * ((cam.x, cam.y, cam.z)[i] - center[i]) for i in range(3))
    if cull and facing <= 0:
        return
    sign = 1 if facing >= 0 else -1
    normal = tuple(value * sign / length for value in normal)
    clipped = _clip_surface(cam, vertices)
    if len(clipped) < 3:
        return
    points = [cam.project(*point) for point in clipped]
    depth = max(0, (center[0] - cam.x) * cam.cy + (center[1] - cam.y) * cam.sy)
    depth_only = getattr(cam, 'depth_only', False)
    tone = char
    if not depth_only:
        tone = fixed_ink if fixed_ink is not None else getattr(cam, "shading", DEFAULT_SHADING).surface(
            material, *center, normal, depth, emission=emission)
    shader = None
    if textured and fixed_ink is None and not depth_only and depth < 14:
        width = max(point[0] for point in points) - min(point[0] for point in points)
        height = max(point[1] for point in points) - min(point[1] for point in points)
        if width * height >= 4:
            shader = _surface_brush(cam, vertices, normal, material, emission)
    if len(points) == 4:
        cam.quad(pixels, depths, *points, tone, shader=shader)
    else:
        for i in range(1, len(points) - 1):
            cam.triangle(pixels, depths, points[0], points[i], points[i + 1], tone, shader=shader)


def _face(cam, pixels, depths, a, b, c, char, material=METAL, emission=0.0):
    draw_actor_surface(cam, pixels, depths, (a, b, c), char, material, emission)


def _quad(cam, pixels, depths, a, b, c, d, char, material=METAL, emission=0.0):
    draw_actor_surface(cam, pixels, depths, (a, b, c, d), char, material, emission)


def _pickup_marker(pickup, cam, pixels, depths):
    """Shared restrained item cue: a small plinth diamond and one glint.

    Keep future pickup shapes inside this same local, occluded presentation;
    names and collection instructions appear only in the shared E prompt.
    """
    x, y, z = pickup.x, pickup.y, pickup.z
    points = [(x - 0.28, y, z + 0.03), (x, y + 0.28, z + 0.03),
              (x + 0.28, y, z + 0.03), (x, y - 0.28, z + 0.03)]
    for i in range(4):
        _stroke(cam, pixels, depths, points[i], points[(i + 1) % 4], "+",
                material=ARCANE, emission=0.50)
    glint = (x, y, z + 1.70)
    _stroke(cam, pixels, depths, glint, glint, "*", material=ARCANE, emission=0.85)


def _draw_pickup(pickup, cam, pixels, depths, time_seconds):
    x, y, z = pickup.x, pickup.y, pickup.z
    if pickup.weapon == FIRE_STAFF:
        _staff_shape(cam, pixels, depths, lambda right, up, forward:
                     (x + right, y + forward, z + up))
        _pickup_marker(pickup, cam, pixels, depths)
        return
    angle = time_seconds * 0.55
    ux, uy = math.cos(angle), math.sin(angle)
    # Upright blade with a turning flat, guard, grip and small ground marker.
    tip = (x, y, z + 1.48)
    left = (x - ux * 0.10, y - uy * 0.10, z + 0.57)
    right = (x + ux * 0.10, y + uy * 0.10, z + 0.57)
    # Give the blade a shallow solid cross-section, so it stays opaque and
    # recognizable even when its slowly turning flat is viewed edge-on.
    front = (x - uy * 0.045, y + ux * 0.045, z + 0.57)
    back = (x + uy * 0.045, y - ux * 0.045, z + 0.57)
    for a, b in ((left, front), (front, right), (right, back), (back, left)):
        _face(cam, pixels, depths, a, b, tip, "#")
    _stroke(cam, pixels, depths, left, tip, "/")
    _stroke(cam, pixels, depths, tip, right, "\\")
    _stroke(cam, pixels, depths, (x - ux * 0.27, y - uy * 0.27, z + 0.53),
            (x + ux * 0.27, y + uy * 0.27, z + 0.53), "=")
    _stroke(cam, pixels, depths, (x, y, z + 0.24), (x, y, z + 0.53), "#",
            material=WOOD)
    _pickup_marker(pickup, cam, pixels, depths)


def _staff_shape(cam, pixels, depths, point, casting=0.0):
    # A solid wooden shaft and a faceted rune crystal in a forked crown. The same
    # geometry supplies the world pickup and the camera-relative held staff.
    corners = [(-0.032, -0.032), (0.032, -0.032),
               (0.032, 0.032), (-0.032, 0.032)]
    for i, (x, y) in enumerate(corners):
        nx, ny = corners[(i + 1) % 4]
        a, b = point(x, 0.08, y), point(nx, 0.08, ny)
        c, d = point(nx, 1.18, ny), point(x, 1.18, y)
        _quad(cam, pixels, depths, a, b, c, d, "#", material=WOOD)
    for side in (-1, 1):
        _stroke(cam, pixels, depths, point(side * 0.03, 1.04, 0),
                point(side * 0.18, 1.38, 0), "/" if side > 0 else "\\")
    ring = [point(0.13, 1.37, 0), point(0, 1.37, 0.13),
            point(-0.13, 1.37, 0), point(0, 1.37, -0.13)]
    for i in range(4):
        for up in (1.20, 1.55):
            _face(cam, pixels, depths, ring[i], ring[(i + 1) % 4], point(0, up, 0), "@",
                  material=ARCANE, emission=0.60 + casting * 0.20)
    if casting:
        tip = point(0, 1.60 + casting * 0.12, 0)
        _stroke(cam, pixels, depths, tip, tip, "*", material=FIRE, emission=0.95)


def _draw_flame(flame, cam, pixels, depths, radius, direction=None, seconds=0.0):
    x, y, z = flame.x, flame.y, flame.z
    pulse = 0.5 + 0.5 * math.sin(seconds * 11 + x * 0.7 + y * 0.3)
    ring = [(x + radius, y, z), (x, y + radius, z),
            (x - radius, y, z), (x, y - radius, z)]
    for i in range(4):
        for side in (-1, 1):
            _face(cam, pixels, depths, ring[i], ring[(i + 1) % 4],
                  (x, y, z + side * radius), "@" if side < 0 else "*",
                  material=FIRE, emission=0.74 + pulse * 0.16 + (0.10 if side < 0 else 0))
    if direction is not None:
        tail = tuple(value - component * 0.45 for value, component in zip((x, y, z), direction))
        edge = tuple(value - component * radius * 1.15
                     for value, component in zip((x, y, z), direction))
        depth = max(0, (x - cam.x) * cam.cy + (y - cam.y) * cam.sy)
        ember = ("." if getattr(cam, 'depth_only', False) else
                 getattr(cam, "shading", DEFAULT_SHADING).surface(EMBER, x, y, z,
                    (-cam.cy, -cam.sy, 0), depth, glyph=".", emission=0.42 + pulse * 0.12))
        projected_tail, projected_center = cam.project(*tail), cam.project(x, y, z)
        # A head-on tail projects onto the fireball itself. Omit that subpixel
        # detail instead of painting a dim ember over the bright opaque core.
        if (projected_tail is not None and projected_center is not None
                and math.hypot(projected_tail[0] - projected_center[0],
                               projected_tail[1] - projected_center[1]) >= 1.0):
            cam.stroke_world(pixels, depths, tail, edge, char=ember)
    _stroke(cam, pixels, depths, (x, y, z), (x, y, z), "*",
            material=FIRE, emission=1.0)


def _draw_enemy(enemy: Enemy, cam, pixels, depths):
    if enemy.behavior is not None:
        if enemy.alive or enemy.collapse_remaining > 1e-8:
            _draw_warden(enemy, cam, pixels, depths)
        return
    x, y, z = enemy.x, enemy.y, enemy.z
    # The fixed stake stays visible and solid after the straw body falls.
    support_height = 1.25 if enemy.alive else enemy.height
    _stroke(cam, pixels, depths, (x, y, z), (x, y, z + support_height), "|", 0.055,
            material=WOOD)
    _stroke(cam, pixels, depths, (x - 0.36, y, z + 0.03),
            (x + 0.36, y, z + 0.03), "=", material=WOOD)
    _stroke(cam, pixels, depths, (x, y - 0.30, z + 0.03),
            (x, y + 0.30, z + 0.03), "=", material=WOOD)
    if not enemy.alive:
        _stroke(cam, pixels, depths, (x, y, z + 0.40), (x + 0.85, y, z + 0.24), "%", 0.10,
                material=STRAW)
        _ring(cam, pixels, depths, x + 1.00, y, z + 0.27, 0.20, 0, 0.20, material=BONE)
        return
    lean = math.sin((0.18 - enemy.hit_remaining) * 45) * enemy.hit_remaining * 0.5
    x += lean
    # Opaque faceted straw and a compact head read from every approach. Keep
    # emphasis on the body itself rather than adding a large overlay or halo.
    lower = [(x + 0.18 * math.cos(i * math.tau / 8), y + 0.18 * math.sin(i * math.tau / 8), z + 0.92)
             for i in range(8)]
    upper = [(x + 0.30 * math.cos(i * math.tau / 8), y + 0.30 * math.sin(i * math.tau / 8), z + 1.55)
             for i in range(8)]
    for i in range(8):
        j = (i + 1) % 8
        _quad(cam, pixels, depths, lower[i], upper[i], upper[j], lower[j], "%", material=STRAW)
    head = [(x + 0.24, y, z + 1.80), (x, y + 0.24, z + 1.80),
            (x - 0.24, y, z + 1.80), (x, y - 0.24, z + 1.80)]
    for i in range(4):
        for end in (z + 1.55, z + 2.05):
            _face(cam, pixels, depths, head[i], head[(i + 1) % 4], (x, y, end), "@", material=BONE)
    for side in (-1, 1):
        _stroke(cam, pixels, depths, (x + side * 0.35, y, z + 1.45),
                (x + side * 0.22, y, z + 0.91), "/" if side < 0 else "\\", material=STRAW)
        _stroke(cam, pixels, depths, (x + side * 0.20, y, z + 1.42),
                (x + side * 0.70, y, z + 1.22), "=", 0.04, material=WOOD)


def _draw_warden(enemy, cam, pixels, depths):
    """An opaque stone knight; joint motion uses simulation state only."""
    alive = enemy.alive
    cosine, sine = math.cos(enemy.facing), math.sin(enemy.facing)
    recoil = math.sin(enemy.hit_remaining * 35) * enemy.hit_remaining * 0.20 if alive else 0
    stride = math.sin(enemy.walk_phase) * 0.13
    raised = (1 - enemy.attack_remaining / enemy.behavior.windup
              if enemy.state == "windup" else 0.0)
    dx, dy = cam.x - enemy.x, cam.y - enemy.y
    camera_right = dx * sine - dy * cosine
    camera_forward = dx * cosine + dy * sine + recoil
    camera_up = cam.z - enemy.z

    def point(right, forward, up):
        return (enemy.x + cosine * (forward - recoil) + sine * right,
                enemy.y + sine * (forward - recoil) - cosine * right,
                enemy.z + up)

    if not alive:
        progress = 1 - enemy.collapse_remaining / WARDEN_COLLAPSE_DURATION
        angle = 1.50 * progress ** 1.55
        fall_cos, fall_sin = math.cos(angle), math.sin(angle)
        pivot = 0.20
        height = camera_up - pivot
        camera_forward, camera_up = (camera_forward * fall_cos + height * fall_sin,
                                     height * fall_cos - camera_forward * fall_sin + pivot)

        def fallen_point(right, forward, up):
            height = up - pivot
            along = forward * fall_cos - height * fall_sin
            return (enemy.x + cosine * along + sine * right,
                    enemy.y + sine * along - cosine * right,
                    enemy.z + pivot + height * fall_cos + forward * fall_sin)

        point = fallen_point

    def block(right, forward, bottom, half_width, half_depth, top, char):
        center = point(right, forward, (bottom + top) / 2)
        depth = max(0.18, (center[0] - cam.x) * cam.cy + (center[1] - cam.y) * cam.sy)
        # During the brief fall the stone silhouette is enough. Skip the
        # extra bevel faces on each fragment as it rotates out of view.
        detailed = alive and cam.fx * max(half_width, half_depth) / depth >= 1.75

        def ring(width, length, height, cut):
            if cut:
                footprint = ((-width + cut, -length), (width - cut, -length),
                             (width, -length + cut), (width, length - cut),
                             (width - cut, length), (-width + cut, length),
                             (-width, length - cut), (-width, -length + cut))
            else:
                footprint = ((-width, -length), (width, -length),
                             (width, length), (-width, length))
            return [point(right + x, forward + y, height) for x, y in footprint]

        if detailed:
            cut = min(half_width, half_depth) * 0.30
            bevel = min(0.055, (top - bottom) * 0.16)
            # Broad, shallow shoulder and helmet bevels catch overhead moonlight
            # even when their vertical faces are turned away from it.
            inset = min(half_width, half_depth) * 0.38
            rings = (ring(half_width - inset, half_depth - inset, bottom, cut * 0.65),
                     ring(half_width, half_depth, bottom + bevel, cut),
                     ring(half_width, half_depth, top - bevel, cut),
                     ring(half_width - inset, half_depth - inset, top, cut * 0.65))
        else:
            rings = (ring(half_width, half_depth, bottom, 0), ring(half_width, half_depth, top, 0))
        inside = (abs(camera_right - right) < half_width
                  and abs(camera_forward - forward) < half_depth and bottom < camera_up < top)
        for lower, upper in zip(rings, rings[1:]):
            for i in range(len(lower)):
                j = (i + 1) % len(lower)
                draw_actor_surface(cam, pixels, depths, (lower[i], lower[j], upper[j], upper[i]),
                                   char, STONE, cull=not inside)
        draw_actor_surface(cam, pixels, depths, tuple(reversed(rings[0])), char, STONE, cull=not inside)
        draw_actor_surface(cam, pixels, depths, rings[-1], char, STONE, cull=not inside)

    for side in (-1, 1):
        block(side * 0.22, side * stride, 0.04, 0.14, 0.18, 0.88, "#")
    block(0, 0, 0.82, 0.40, 0.24, 1.60, "#")
    block(0, 0, 1.61, 0.24, 0.22, 2.08, "@")
    # The carved visor faces the target; raised stone fists telegraph a strike.
    _stroke(cam, pixels, depths, point(-0.17, 0.225, 1.85),
            point(0.17, 0.225, 1.85), "=", material=STONE, shade_bias=-4)
    for side in (-1, 1):
        up = 1.12 + raised * 0.75
        forward = 0.15 + raised * 0.18 - side * stride
        _stroke(cam, pixels, depths, point(side * 0.43, 0, 1.48),
                point(side * 0.50, forward, up), "#", 0.08, material=STONE)
        block(side * 0.50, forward, up - 0.12, 0.12, 0.13, up + 0.12, "%")


def _draw_actor_name(actor, cam, pixels, depths):
    top = actor.z + actor.height
    projected = cam.project(actor.x, actor.y, top + 0.24)
    if projected is None:
        return
    px, py, depth = projected
    row = round(py)
    name = "".join(char for char in actor.name if 32 <= ord(char) <= 126)
    if isinstance(actor, Enemy):
        label = f"{name} [{actor.hp}/{actor.max_hp}]"[:48]
    else:
        label = [ink(char, 15, UI_POSITIVE) for char in f"<{name[:46]}>"]
        head = cam.project(actor.x, actor.y, top)
        if head is not None:
            row = min(row, math.ceil(head[1]) - 1)
    column = round(px - (len(label) - 1) / 2)
    if not 0 <= row < cam.height:
        return
    for index, char in enumerate(label):
        x = column + index
        if 0 <= x < cam.width and depth <= depths[row][x] + 0.02:
            pixels[row][x] = char


def _draw_equipped(combat, cam, pixels, depths, player):
    phase = 1 - combat.swing_remaining / SWING_DURATION if combat.swing_remaining else 0
    arc = math.sin(math.pi * phase) if combat.swing_remaining else 0
    bob = math.sin(player.stride) * 0.018 if player.moving else 0
    impact = player.damage_impact ** 2

    def point(right, up, depth):
        up -= 0.22 * impact
        depth -= 0.12 * impact
        return (cam.x + cam.cy * cam.cp * depth + cam.sy * right - cam.cy * cam.sp * up,
                cam.y + cam.sy * cam.cp * depth - cam.cy * right - cam.sy * cam.sp * up,
                cam.z + cam.sp * depth + cam.cp * up)

    if combat.held_item.weapon == FIRE_STAFF:
        def staff_point(right, up, forward):
            return point(0.38 + right * 0.70 - arc * 0.06,
                         -0.70 + up * 0.70 + bob - arc * 0.05,
                         0.95 + forward * 0.70 + arc * 0.12)
        _staff_shape(cam, pixels, depths, staff_point, arc)
        return

    grip = (0.34 - arc * 0.45, -0.45 + bob, 0.90)
    guard = (grip[0] + 0.025, grip[1] + 0.18, 0.98)
    tip = (0.48 - arc * 1.20, 0.20 + arc * 0.25 + bob, 1.10)
    _stroke(cam, pixels, depths, point(*grip), point(*guard), "#", 0.012, material=WOOD)
    _stroke(cam, pixels, depths, point(guard[0] - 0.10, guard[1], guard[2]),
            point(guard[0] + 0.10, guard[1], guard[2]), "=")
    left = point(guard[0] - 0.035, guard[1], guard[2])
    right = point(guard[0] + 0.035, guard[1], guard[2])
    _face(cam, pixels, depths, left, right, point(*tip), "#")
    _stroke(cam, pixels, depths, left,
            point(*tip), "/")
    _stroke(cam, pixels, depths, point(*tip),
            right, "\\")


def draw_combat(combat: CombatState, world, pixels, depths, player,
                focal, aspect, time_seconds, *, labels=True, depth_only=False, moonlight=None):
    if not pixels or not pixels[0]:
        return
    if not (combat.pickups or combat.enemies or combat.held_item or combat.fireballs or combat.bursts
            or (labels and not depth_only and world.npcs)):
        return
    height, width = len(pixels), len(pixels[0])
    cam = Camera(player, width, height, focal, aspect)
    cam.depth_only = depth_only
    cam.shading = DEFAULT_SHADING if depth_only else Shading(world)
    if not depth_only:
        cam.shading.moonlight = moonlight
        cam.shading.prepare(player, time_seconds)
    pickup_budget = min(MAX_PICKUP_DRAWS, max(1, width * height // 240))
    for pickup in combat.pickups:
        if pickup.collected or not actor_visible(cam, pickup.x, pickup.y, pickup.z + 0.8, 0.9):
            continue
        _draw_pickup(pickup, cam, pixels, depths, time_seconds)
        pickup_budget -= 1
        if pickup_budget == 0:
            break
    enemy_budget = min(MAX_ENEMY_DRAWS, max(1, width * height // 180))
    for enemy in combat.enemies:
        radius = 2.35 if enemy.collapse_remaining > 1e-8 else 1.25
        if not actor_visible(cam, enemy.x, enemy.y, enemy.z + 1.0, radius):
            continue
        _draw_enemy(enemy, cam, pixels, depths)
        enemy_budget -= 1
        if enemy_budget == 0:
            break
    if labels and not depth_only:
        aimed = combat.aimed_actor(world, player, NAME_REACH)
        if aimed is not None:
            _draw_actor_name(aimed, cam, pixels, depths)
    for ball in combat.fireballs[:MAX_FIREBALLS]:
        if actor_visible(cam, ball.x, ball.y, ball.z, 0.20):
            _draw_flame(ball, cam, pixels, depths, 0.14, ball.direction, time_seconds)
    for burst in combat.bursts[:MAX_FIREBALLS]:
        if actor_visible(cam, burst.x, burst.y, burst.z, 0.35):
            progress = 1 - burst.remaining / BURST_DURATION
            _draw_flame(burst, cam, pixels, depths, 0.14 + progress * 0.20, seconds=time_seconds)
    if combat.held_item is not None:
        _draw_equipped(combat, cam, pixels, depths, player)

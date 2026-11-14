"""Bounded, depth-tested ASCII geometry for pickups and fantasy enemies."""

import math

from .combat import (BURST_DURATION, FIRE_STAFF, MAX_FIREBALLS, CombatState,
                     Enemy, NAME_REACH, SWING_DURATION)
from .geometry import Camera
from .shading import DEFAULT_SHADING, Shading, ink
from .world import GRASS, METAL, STONE, WOOD


DRAW_DISTANCE = 28.0
MAX_ENEMY_DRAWS = 24
MAX_PICKUP_DRAWS = 16


def large_opaque_enemy(combat, cam):
    """Only large nearby bodies justify a second bounded geometry pass."""
    budget = min(MAX_ENEMY_DRAWS, max(1, cam.width * cam.height // 180))
    for enemy in combat.enemies:
        if not _visible(cam, enemy.x, enemy.y, enemy.z + 1.0, 1.25):
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


def _visible(cam, x, y, z, radius):
    dx, dy, dz = x - cam.x, y - cam.y, z - cam.z
    if dx * dx + dy * dy + dz * dz > (DRAW_DISTANCE + radius) ** 2:
        return False
    for (nx, ny, nz), offset in cam.frustum:
        if dx * nx + dy * ny + dz * nz + radius * math.sqrt(nx * nx + ny * ny + nz * nz) < offset:
            return False
    return True


def _stroke(cam, pixels, depths, a, b, char=None, radius=0.0):
    center = tuple((a[i] + b[i]) / 2 for i in range(3))
    depth = max(0, (center[0] - cam.x) * cam.cy + (center[1] - cam.y) * cam.sy)
    glyph = char or "|"
    tone = getattr(cam, "shading", DEFAULT_SHADING).surface(METAL, *center,
        (-cam.cy, -cam.sy, 0), depth, glyph=glyph)
    cam.stroke(pixels, depths, cam.project(*a), cam.project(*b), radius, tone)


def _ring(cam, pixels, depths, x, y, z, rx, ry, rz, char=None):
    points = [(x + rx * math.cos(i * math.tau / 8),
               y + ry * math.cos(i * math.tau / 8),
               z + rz * math.sin(i * math.tau / 8)) for i in range(8)]
    projected = [cam.project(*point) for point in points]
    for i in range(8):
        cam.stroke(pixels, depths, projected[i], projected[(i + 1) % 8], char=char)


def _face(cam, pixels, depths, a, b, c, char, material=METAL, emission=0.0):
    center = tuple((a[i] + b[i] + c[i]) / 3 for i in range(3))
    u, v = tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))
    normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(value * value for value in normal))
    if length < 1e-12:
        return
    sign = 1 if sum(normal[i] * ((cam.x, cam.y, cam.z)[i] - center[i]) for i in range(3)) >= 0 else -1
    normal = tuple(value * sign / length for value in normal)
    depth = max(0, (center[0] - cam.x) * cam.cy + (center[1] - cam.y) * cam.sy)
    tone = getattr(cam, "shading", DEFAULT_SHADING).surface(material, *center, normal, depth, emission=emission)
    cam.triangle(pixels, depths, cam.project(*a), cam.project(*b), cam.project(*c), tone)


def _pickup_marker(pickup, cam, pixels, depths):
    """Shared restrained item cue: a small plinth diamond and one glint.

    Keep future pickup shapes inside this same local, occluded presentation;
    names and collection instructions appear only in the shared E prompt.
    """
    x, y, z = pickup.x, pickup.y, pickup.z
    points = [(x - 0.28, y, z + 0.03), (x, y + 0.28, z + 0.03),
              (x + 0.28, y, z + 0.03), (x, y - 0.28, z + 0.03)]
    for i in range(4):
        _stroke(cam, pixels, depths, points[i], points[(i + 1) % 4], "+")
    glint = cam.project(x, y, z + 1.70)
    cam.stroke(pixels, depths, glint, glint, char=ink("*", 15, METAL))


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
    _stroke(cam, pixels, depths, (x, y, z + 0.24), (x, y, z + 0.53), "#")
    _pickup_marker(pickup, cam, pixels, depths)


def _staff_shape(cam, pixels, depths, point, casting=0.0):
    # A solid wooden shaft and a faceted ember in a forked crown. The same
    # geometry supplies the world pickup and the camera-relative held staff.
    corners = [(-0.032, -0.032), (0.032, -0.032),
               (0.032, 0.032), (-0.032, 0.032)]
    for i, (x, y) in enumerate(corners):
        nx, ny = corners[(i + 1) % 4]
        a, b = point(x, 0.08, y), point(nx, 0.08, ny)
        c, d = point(nx, 1.18, ny), point(x, 1.18, y)
        _face(cam, pixels, depths, a, b, c, "#", material=WOOD)
        _face(cam, pixels, depths, a, c, d, "#", material=WOOD)
    for side in (-1, 1):
        _stroke(cam, pixels, depths, point(side * 0.03, 1.04, 0),
                point(side * 0.18, 1.38, 0), "/" if side > 0 else "\\")
    ring = [point(0.13, 1.37, 0), point(0, 1.37, 0.13),
            point(-0.13, 1.37, 0), point(0, 1.37, -0.13)]
    for i in range(4):
        for up in (1.20, 1.55):
            _face(cam, pixels, depths, ring[i], ring[(i + 1) % 4], point(0, up, 0), "@")
    if casting:
        tip = point(0, 1.60 + casting * 0.12, 0)
        _stroke(cam, pixels, depths, tip, tip, "*")


def _draw_flame(flame, cam, pixels, depths, radius, direction=None):
    x, y, z = flame.x, flame.y, flame.z
    ring = [(x + radius, y, z), (x, y + radius, z),
            (x - radius, y, z), (x, y - radius, z)]
    for i in range(4):
        for side in (-1, 1):
            _face(cam, pixels, depths, ring[i], ring[(i + 1) % 4],
                  (x, y, z + side * radius), "@" if side < 0 else "*", emission=1.0)
    center = cam.project(x, y, z)
    cam.stroke(pixels, depths, center, center, char=ink("*", 15, METAL))
    if direction is not None:
        tail = tuple(value - component * 0.45 for value, component in zip((x, y, z), direction))
        cam.stroke_world(pixels, depths, tail, (x, y, z), char=ink(".", 10, METAL))


def _draw_enemy(enemy: Enemy, cam, pixels, depths):
    if enemy.behavior is not None:
        if enemy.alive:
            _draw_warden(enemy, cam, pixels, depths)
        return
    x, y, z = enemy.x, enemy.y, enemy.z
    # The fixed stake stays visible and solid after the straw body falls.
    support_height = 1.25 if enemy.alive else enemy.height
    _stroke(cam, pixels, depths, (x, y, z), (x, y, z + support_height), "|", 0.055)
    _stroke(cam, pixels, depths, (x - 0.36, y, z + 0.03),
            (x + 0.36, y, z + 0.03), "=")
    _stroke(cam, pixels, depths, (x, y - 0.30, z + 0.03),
            (x, y + 0.30, z + 0.03), "=")
    if not enemy.alive:
        _stroke(cam, pixels, depths, (x, y, z + 0.40), (x + 0.85, y, z + 0.24), "%", 0.10)
        _ring(cam, pixels, depths, x + 1.00, y, z + 0.27, 0.20, 0, 0.20)
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
        _face(cam, pixels, depths, lower[i], upper[i], upper[j], "%", material=GRASS)
        _face(cam, pixels, depths, lower[i], upper[j], lower[j], "%", material=GRASS)
    head = [(x + 0.24, y, z + 1.80), (x, y + 0.24, z + 1.80),
            (x - 0.24, y, z + 1.80), (x, y - 0.24, z + 1.80)]
    for i in range(4):
        for end in (z + 1.55, z + 2.05):
            _face(cam, pixels, depths, head[i], head[(i + 1) % 4], (x, y, end), "@")
    for side in (-1, 1):
        _stroke(cam, pixels, depths, (x + side * 0.35, y, z + 1.45),
                (x + side * 0.22, y, z + 0.91), "/" if side < 0 else "\\")
        _stroke(cam, pixels, depths, (x + side * 0.20, y, z + 1.42),
                (x + side * 0.70, y, z + 1.22), "=", 0.04)


def _draw_warden(enemy, cam, pixels, depths):
    """An opaque stone knight; joint motion uses simulation state only."""
    cosine, sine = math.cos(enemy.facing), math.sin(enemy.facing)
    recoil = math.sin(enemy.hit_remaining * 35) * enemy.hit_remaining * 0.20
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

    def block(right, forward, bottom, half_width, half_depth, top, char):
        lower = [point(right + rx * half_width, forward + fy * half_depth, bottom)
                 for rx, fy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        upper = [point(right + rx * half_width, forward + fy * half_depth, top)
                 for rx, fy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        lower = [cam.project(*vertex) for vertex in lower]
        upper = [cam.project(*vertex) for vertex in upper]
        # Closed opaque blocks only expose faces toward the camera. Project
        # vertices once and skip hidden face fills; retain all faces for
        # a camera inside a block, including close camera-plane crossings.
        sides = (camera_forward <= forward - half_depth,
                 camera_right >= right + half_width,
                 camera_forward >= forward + half_depth,
                 camera_right <= right - half_width)
        above, below = camera_up >= top, camera_up <= bottom
        inside = (not (any(sides) or above or below)
                  or any(vertex is None for vertex in (*lower, *upper)))
        for i in range(4):
            if not (inside or sides[i]):
                continue
            j = (i + 1) % 4
            normals = ((-cosine, -sine, 0), (sine, -cosine, 0),
                       (cosine, sine, 0), (-sine, cosine, 0))
            center = point(right, forward, (bottom + top) / 2)
            depth = max(0, (center[0] - cam.x) * cam.cy + (center[1] - cam.y) * cam.sy)
            tone = getattr(cam, "shading", DEFAULT_SHADING).surface(STONE, *center, normals[i], depth)
            cam.quad(pixels, depths, lower[i], upper[i], upper[j], lower[j], tone)
        for enabled, vertices, up, normal in ((inside or above, upper, top, (0, 0, 1)),
                                               (inside or below, lower, bottom, (0, 0, -1))):
            if enabled:
                center = point(right, forward, up)
                depth = max(0, (center[0] - cam.x) * cam.cy + (center[1] - cam.y) * cam.sy)
                tone = getattr(cam, "shading", DEFAULT_SHADING).surface(STONE, *center, normal, depth)
                cam.quad(pixels, depths, *vertices, tone)

    for side in (-1, 1):
        block(side * 0.22, side * stride, 0.04, 0.14, 0.18, 0.88, "#")
    block(0, 0, 0.82, 0.40, 0.24, 1.60, "#")
    block(0, 0, 1.61, 0.24, 0.22, 2.08, "@")
    # The carved visor faces the target; raised stone fists telegraph a strike.
    _stroke(cam, pixels, depths, point(-0.17, 0.225, 1.85),
            point(0.17, 0.225, 1.85), "=")
    for side in (-1, 1):
        up = 1.12 + raised * 0.75
        forward = 0.15 + raised * 0.18 - side * stride
        _stroke(cam, pixels, depths, point(side * 0.43, 0, 1.48),
                point(side * 0.50, forward, up), "#", 0.08)
        block(side * 0.50, forward, up - 0.12, 0.12, 0.13, up + 0.12, "%")


def _draw_name(enemy, cam, pixels, depths):
    projected = cam.project(enemy.x, enemy.y, enemy.z + enemy.height + 0.24)
    if projected is None:
        return
    px, py, depth = projected
    label = f"{enemy.name} [{enemy.hp}/{enemy.max_hp}]"
    label = "".join(char for char in label if 32 <= ord(char) <= 126)[:48]
    row, column = round(py), round(px - (len(label) - 1) / 2)
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

    def point(right, up, depth):
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
    _stroke(cam, pixels, depths, point(*grip), point(*guard), "#", 0.012)
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
                focal, aspect, time_seconds, *, labels=True):
    if not pixels or not pixels[0]:
        return
    if not (combat.pickups or combat.enemies or combat.held_item
            or combat.fireballs or combat.bursts):
        return
    height, width = len(pixels), len(pixels[0])
    cam = Camera(player, width, height, focal, aspect)
    cam.shading = Shading(world)
    cam.shading.prepare(player, time_seconds)
    pickup_budget = min(MAX_PICKUP_DRAWS, max(1, width * height // 240))
    for pickup in combat.pickups:
        if pickup.collected or not _visible(cam, pickup.x, pickup.y, pickup.z + 0.8, 0.9):
            continue
        _draw_pickup(pickup, cam, pixels, depths, time_seconds)
        pickup_budget -= 1
        if pickup_budget == 0:
            break
    enemy_budget = min(MAX_ENEMY_DRAWS, max(1, width * height // 180))
    for enemy in combat.enemies:
        if not _visible(cam, enemy.x, enemy.y, enemy.z + 1.0, 1.25):
            continue
        _draw_enemy(enemy, cam, pixels, depths)
        enemy_budget -= 1
        if enemy_budget == 0:
            break
    if labels:
        aimed = combat.aimed_enemy(world, player, NAME_REACH)
        if aimed is not None:
            _draw_name(aimed, cam, pixels, depths)
    for ball in combat.fireballs[:MAX_FIREBALLS]:
        if _visible(cam, ball.x, ball.y, ball.z, 0.20):
            _draw_flame(ball, cam, pixels, depths, 0.14, ball.direction)
    for burst in combat.bursts[:MAX_FIREBALLS]:
        if _visible(cam, burst.x, burst.y, burst.z, 0.35):
            progress = 1 - burst.remaining / BURST_DURATION
            _draw_flame(burst, cam, pixels, depths, 0.14 + progress * 0.20)
    if combat.held_item is not None:
        _draw_equipped(combat, cam, pixels, depths, player)

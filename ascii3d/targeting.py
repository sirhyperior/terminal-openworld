"""Small shared view-ray and solid-cylinder targeting queries."""

import math


def view_ray(player):
    """Return the normalized ray through the center of the player's view."""
    cosine = math.cos(player.pitch)
    return ((player.x, player.y, player.eye_z),
            (math.cos(player.yaw) * cosine, math.sin(player.yaw) * cosine,
             math.sin(player.pitch)))


def cylinder_hit(origin, direction, x, y, bottom, radius, height, reach):
    """Intersect a finite vertical cylinder, including vertical aim."""
    ox, oy, oz = origin
    dx, dy, dz = direction
    rx, ry = ox - x, oy - y
    a = dx * dx + dy * dy
    near, far = 0.0, reach
    if a < 1e-12:
        if rx * rx + ry * ry > radius * radius:
            return None
    else:
        b = rx * dx + ry * dy
        c = rx * rx + ry * ry - radius * radius
        discriminant = b * b - a * c
        if discriminant < 0:
            return None
        root = math.sqrt(discriminant)
        near = max(near, (-b - root) / a)
        far = min(far, (-b + root) / a)
    if abs(dz) < 1e-10:
        if not bottom <= oz <= bottom + height:
            return None
    else:
        low, high = (bottom - oz) / dz, (bottom + height - oz) / dz
        near, far = max(near, min(low, high)), min(far, max(low, high))
    return near if 0 <= near <= far else None

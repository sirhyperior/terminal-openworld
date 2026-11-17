"""Seeded weathered rocks built once from the shared exact convex geometry."""

import math
import random
from typing import TYPE_CHECKING

from .surfaces import ConvexSolid
from .world import STONE

if TYPE_CHECKING:
    from .world import World


def add_rock(world: "World", x: float, y: float, bottom: float,
             width: float = 2, depth: float = 2, height: float = 1.5,
             seed: int = 0, material: int = STONE) -> ConvexSolid:
    """Add one opaque, irregular boulder centered on X/Y within its dimensions.

    A convex octagonal footprint rises to a smaller displaced shoulder and an
    off-center crown. The 17 vertices/17 faces share the engine's exact rays,
    circular collision and support; bounds only reject work. The base is flat
    at ``bottom``, while the crown reaches ``bottom + height``. Place the base
    slightly inside sloping ground to avoid exposing its underside.

    No voxel boxes, random global state, animation or extra runtime work are
    introduced. Repeated calls add separate instances, just like add_solid().
    """
    if (not all(math.isfinite(value) for value in (x, y, bottom, width, depth, height))
            or min(width, depth, height) <= 0):
        raise ValueError("rocks require finite positions and positive finite dimensions")
    rng = random.Random(seed)
    angle = rng.uniform(-math.pi / 8, math.pi / 8)
    outline = []
    for side in range(8):
        radius = rng.uniform(0.91, 1.0)
        direction = angle + side * math.tau / 8
        outline.append((radius * math.cos(direction), radius * math.sin(direction)))
    # Normalize to exact authored bounds, preserving the ordered convex outline.
    low_x, high_x = min(p[0] for p in outline), max(p[0] for p in outline)
    low_y, high_y = min(p[1] for p in outline), max(p[1] for p in outline)
    outline = [((px - low_x) / (high_x - low_x) - 0.5,
                (py - low_y) / (high_y - low_y) - 0.5) for px, py in outline]
    taper = rng.uniform(0.54, 0.66)
    shoulder = bottom + height * rng.uniform(0.64, 0.76)
    shift_x, shift_y = rng.uniform(-0.025, 0.025), rng.uniform(-0.025, 0.025)
    crown_x, crown_y = rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06)
    vertices = [(x + px * width, y + py * depth, bottom) for px, py in outline]
    vertices += [(x + (px * taper + shift_x) * width,
                  y + (py * taper + shift_y) * depth, shoulder) for px, py in outline]
    vertices.append((x + crown_x * width, y + crown_y * depth, bottom + height))
    faces = [tuple(reversed(range(8)))]
    faces += [(side, (side + 1) % 8, (side + 1) % 8 + 8, side + 8)
              for side in range(8)]
    faces += [(side + 8, (side + 1) % 8 + 8, 16) for side in range(8)]
    return world.add_solid(ConvexSolid(tuple(vertices), tuple(faces), material))

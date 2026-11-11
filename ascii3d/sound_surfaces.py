"""Deterministic Foley materials from the player's actual ground contact."""

import math

from .world import BRIDGE, CRATE, FLOOR, GRASS, METAL, PATH, STONE, WATER, WATER_LEVEL, WOOD


_MATERIALS = {
    STONE: "stone", FLOOR: "stone", GRASS: "grass", PATH: "gravel",
    WOOD: "wood", BRIDGE: "wood", CRATE: "wood", METAL: "metal",
}
_CONTACT_RADIUS = 0.22
_CONTACT_TOLERANCE = 0.06


def surface_kind(world, x: float, y: float, feet: float, in_water: bool = False) -> str:
    """Resolve support for a step/landing; do not call on every physics frame.

    Sample the same circular footprint as player collision, rather than only
    the center cell: a player can stand on a crate/bridge edge with air below
    their center. Only surfaces at foot height count, so ground below a raised
    bridge and nearby walls cannot supply its material. Water takes precedence
    while wading. Continuous hills and fractional treads use the shared analytic
    contact query; wooden door tops also provide support.
    """
    cx, cy = math.floor(x), math.floor(y)
    if in_water or (feet < WATER_LEVEL and world.get(cx, cy, 0) == WATER):
        return "water"

    material = world.contact_material(x, y, feet, _CONTACT_RADIUS, _CONTACT_TOLERANCE)
    if material in _MATERIALS:
        return _MATERIALS[material]

    cz = round(feet) - 1
    # Contact resolution can leave a tiny positive gap above a voxel top.
    if abs(feet - (cz + 1)) <= _CONTACT_TOLERANCE:
        material = world.get(cx, cy, cz)
        if material in _MATERIALS:
            return _MATERIALS[material]
        nearest, surface = _CONTACT_RADIUS ** 2, None
        for sy in range(math.floor(y - _CONTACT_RADIUS), math.floor(y + _CONTACT_RADIUS) + 1):
            for sx in range(math.floor(x - _CONTACT_RADIUS), math.floor(x + _CONTACT_RADIUS) + 1):
                dx = max(sx - x, 0.0, x - (sx + 1))
                dy = max(sy - y, 0.0, y - (sy + 1))
                distance = dx * dx + dy * dy
                material = world.get(sx, sy, cz)
                if distance < nearest and material in _MATERIALS:
                    nearest, surface = distance, _MATERIALS[material]
        if surface is not None:
            return surface

    for door in world.doors:
        for panel in door.panels:
            if abs(feet - (panel.bottom + panel.height)) > _CONTACT_TOLERANCE:
                continue
            dx, dy = x - panel.x, y - panel.y
            u = dx * panel.ux + dy * panel.uy
            v = -dx * panel.uy + dy * panel.ux
            du = max(-u, 0.0, u - panel.length)
            dv = max(abs(v) - panel.thickness / 2, 0.0)
            if du * du + dv * dv < _CONTACT_RADIUS ** 2:
                return "wood"
    return "stone"

"""Opaque ASCII figures for the people who occupy the landmarks."""

from dataclasses import dataclass
import math

from .combat_render import actor_visible, draw_actor_surface
from .geometry import Camera
from .npcs import NPC
from .palette import ARCANE, BONE, CLOTH, LEATHER, METAL, SKIN
from .shading import ink


MAX_NPC_DRAWS = 6
BREATH_SECONDS = 3.6


@dataclass(frozen=True)
class Outfit:
    coat: int
    mantle: int
    clasp: int
    hem: float
    hem_width: float
    crown_width: float | None
    drape: tuple[tuple[float, float, float], ...] = ()


OUTFITS = {
    "keeper": Outfit(LEATHER, CLOTH, METAL, 0.48, 0.20, 0.073),
    "mourner": Outfit(CLOTH, CLOTH, BONE, 0.12, 0.25, 0.039),
    "sentinel": Outfit(CLOTH, METAL, METAL, 0.62, 0.18, 0.105),
    "sorcerer": Outfit(CLOTH, CLOTH, METAL, 0.055, 0.263, None, ((0.217, 0.118, 0.60),)),
}


def _draw_shadow_hood(point, face):
    """Build the hood shell, its inset rim and an opaque recessed lining."""
    outline = ((-0.105, 1.405), (-0.153, 1.535), (-0.123, 1.67), (0, 1.75),
               (0.123, 1.67), (0.153, 1.535), (0.105, 1.405))
    opening = ((-0.062, 1.465), (-0.103, 1.545), (-0.076, 1.629), (0, 1.68),
               (0.076, 1.629), (0.103, 1.545), (0.062, 1.465))
    rim = [point(x, 0.163, z) for x, z in outline]
    back = [point(x * 0.86, -0.141, 1.55 + (z - 1.55) * 0.88) for x, z in outline]
    lip = [point(x, 0.163, z) for x, z in opening]
    lining = [point(x * 0.86, 0.026, 1.55 + (z - 1.55) * 0.88) for x, z in opening]
    inner_edge = ink(":", 4, CLOTH)

    face(tuple(reversed(back)), CLOTH)
    for i in range(len(rim)):
        j = (i + 1) % len(rim)
        face((rim[i], back[i], back[j], rim[j]), CLOTH)
        face((rim[i], rim[j], lip[j], lip[i]), CLOTH)
        face((lip[i], lip[j], lining[j], lining[i]), CLOTH, fixed_ink=inner_edge)
    face(lining, CLOTH, fixed_ink=ink(".", 2, CLOTH))


def _draw_npc(npc: NPC, camera: Camera, pixels, depths, time_seconds: float):
    outfit = OUTFITS.get(npc.outfit, OUTFITS["keeper"])
    shadow_hood = outfit.crown_width is None
    cosine, sine = math.cos(npc.yaw), math.sin(npc.yaw)
    scale = npc.height / 1.75
    # A slower weight shift and an offset breath cycle keep residents from
    # moving in sync. Both motions taper down to the planted lower body.
    phase = time_seconds * (math.pi / BREATH_SECONDS) + npc.x * 0.41 + npc.y * 0.67
    sway = 0.065 * math.sin(phase)
    breath = 0.5 + 0.5 * math.sin(2 * phase + 0.7)
    rise = 0.060 * (breath - 1)
    expansion = 0.10 * breath

    def point(right, forward, up):
        upper_body = max(0.0, (up - 0.68) / 1.07)
        right += sway * upper_body
        forward *= 1.0 + expansion * upper_body
        return (npc.x + cosine * forward + sine * right,
                npc.y + sine * forward - cosine * right,
                npc.z + (up + rise * upper_body) * scale)

    def ring(right, forward, width, length, up):
        return [point(right + x, forward + y, up)
                for x, y in ((-width, -length), (width, -length),
                             (width, length), (-width, length))]

    def face(vertices, material, *, emission=0.0, fixed_ink=None):
        draw_actor_surface(camera, pixels, depths, vertices, "#", material, emission,
                           cull=True, textured=False, fixed_ink=fixed_ink)

    def solid(material, right, forward, *profiles, emission=0.0):
        rings = [ring(right, forward, *profile) for profile in profiles]

        face(tuple(reversed(rings[0])), material, emission=emission)
        for lower, upper in zip(rings, rings[1:]):
            for index in range(4):
                next_index = (index + 1) % 4
                face((lower[index], lower[next_index], upper[next_index], upper[index]),
                     material, emission=emission)
        face(rings[-1], material, emission=emission)

    # The enclosed volumes provide silhouettes and hide scenery from every side.
    stride = npc.walk_blend * math.sin(npc.walk_phase)
    for side in (-1, 1):
        swing = side * stride
        lift = 0.07 * max(0.0, swing)
        solid(LEATHER, side * 0.105, 0.025 + swing * 0.09, (0.067, 0.105, 0.01 + lift),
              (0.068, 0.066, 0.14 + lift))
        solid(CLOTH, side * 0.102, swing * 0.065, (0.059, 0.053, 0.12 + lift * 0.5),
              (0.070, 0.074, outfit.hem + 0.12))
        arm_swing = -swing * 0.09
        if shadow_hood:
            solid(outfit.coat, side * 0.23, arm_swing, (0.054, 0.063, 0.76),
                  (0.066, 0.074, 1.29))
        else:
            solid(outfit.coat, side * 0.234, arm_swing, (0.046, 0.049, 0.88),
                  (0.065, 0.071, 1.29))
            solid(SKIN, side * 0.234, 0.011 + arm_swing, (0.033, 0.036, 0.80),
                  (0.044, 0.043, 0.90))
    solid(outfit.coat, 0, 0, (outfit.hem_width, 0.129, outfit.hem), *outfit.drape,
          (0.162, 0.109, 0.96), (0.210, 0.130, 1.30))
    solid(outfit.mantle, 0, 0, (0.242, 0.148, 1.25),
          (0.249, 0.151, 1.32), (0.108, 0.106, 1.44))
    solid(LEATHER, 0, 0, (0.177, 0.124, 0.91), (0.177, 0.124, 0.97))
    solid(outfit.clasp, 0, 0.143, (0.043, 0.028, 1.20), (0.043, 0.028, 1.29))
    if shadow_hood:
        solid(ARCANE, 0, 0.169, (0.022, 0.006, 1.22), (0.032, 0.010, 1.246),
              (0.022, 0.006, 1.272), emission=0.45)
        _draw_shadow_hood(point, face)
        return

    solid(outfit.mantle, 0, 0, (0.112, 0.108, 1.40), (0.142, 0.126, 1.62),
          (outfit.crown_width, 0.070, 1.75))
    # Set the face forward inside the hood rim, visible only from the front.
    solid(SKIN, 0, 0.107, (0.059, 0.025, 1.44), (0.095, 0.044, 1.54),
          (0.086, 0.039, 1.61))

    gaze = (camera.x - npc.x) * cosine + (camera.y - npc.y) * sine
    if gaze > 0.18:
        eyes = [camera.project(*point(side * 0.044, 0.151, 1.56)) for side in (-1, 1)]
        if all(eye is not None for eye in eyes) and abs(eyes[0][0] - eyes[1][0]) >= 2.5:
            for eye in eyes:
                camera.stroke(pixels, depths, eye, eye, char=ink(".", 4, LEATHER))


def draw_npcs(npcs: list[NPC], pixels, depths, player, focal, aspect, shading,
              time_seconds: float = 0.0):
    height, width = len(pixels), len(pixels[0])
    camera = Camera(player, width, height, focal, aspect)
    camera.shading = shading
    budget = min(MAX_NPC_DRAWS, max(1, width * height // 240))
    for npc in npcs:
        radius = math.hypot(npc.height / 2, 0.36)
        if actor_visible(camera, npc.x, npc.y, npc.z + npc.height / 2, radius):
            _draw_npc(npc, camera, pixels, depths, time_seconds)
            budget -= 1
            if budget == 0:
                break

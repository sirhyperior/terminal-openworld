"""Integrated surface gradients and particles stay deterministic and opaque."""

import math
import unittest

from ascii3d.combat import WARDEN_BEHAVIOR, CombatState, Enemy, Fireball
from ascii3d.palette import STONE, color_rgb
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import FLOOR, GRASS, World


class VisualQualityTests(unittest.TestCase):
    def test_close_guardian_has_a_broad_visible_gray_and_color_range(self):
        world = World.empty(24, 24, 12)
        world.box(0, 0, 0, 24, 24, 1, FLOOR)
        world.combat = CombatState(enemies=[Enemy('Stone guardian', 8.5, 8.5,
            radius=0.44, height=2.15, behavior=WARDEN_BEHAVIOR, territory=(1, 1, 23, 23))])
        renderer = Renderer(world, particles=False)
        self.addCleanup(renderer.close)
        player = Player(x=8.5, y=5.8, yaw=math.pi / 2, pitch=-0.1)
        frame = renderer.styled_frame(player, 120, 40)
        samples = [(frame.styles[y][x], frame.effects[y][x])
                   for y in range(2, 35) for x in range(120)
                   if frame.materials[y][x] == STONE]
        levels = {level for level, _ in samples}
        self.assertGreaterEqual(len(levels), 6)
        self.assertGreaterEqual(max(levels) - min(levels), 7)
        self.assertGreaterEqual(len({color_rgb(STONE, level, effects) for level, effects in samples}), 6)

    def test_particles_animate_on_simulation_time_and_are_optional_without_world_mutation(self):
        world = World.empty(32, 32, 12)
        world.outdoor_bounds = (1, 1, 31, 31)
        world.box(0, 0, 0, 32, 32, 1, GRASS)
        world.combat.fireballs = [Fireball(16, 12, 2.7, (1, 0, 0))]
        renderer = Renderer(world)
        self.addCleanup(renderer.close)
        player = Player(x=16, y=8, yaw=math.pi / 2)
        revision, cells = world.revision, bytes(world.cells)
        first = renderer.styled_frame(player, 120, 40, time_seconds=2)
        second = renderer.styled_frame(player, 120, 40, time_seconds=2)
        self.assertEqual((first.rows, first.styles, first.materials, first.effects),
                         (second.rows, second.styles, second.materials, second.effects))
        self.assertGreater(renderer.particles.stats['particles_drawn'], 0)
        renderer.particles.enabled = False
        disabled = renderer.styled_frame(player, 120, 40, time_seconds=2)
        self.assertNotEqual((first.rows, first.materials), (disabled.rows, disabled.materials))
        self.assertEqual(renderer.particles.stats['particles_drawn'], 0)
        self.assertEqual((revision, cells), (world.revision, bytes(world.cells)))


if __name__ == '__main__':
    unittest.main()

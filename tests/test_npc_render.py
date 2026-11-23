"""NPC silhouette, facing and scene occlusion regressions."""

import math
import unittest
from unittest.mock import patch

from ascii3d.combat import Enemy
from ascii3d.dialogue import DialogueView
from ascii3d.geometry import Camera
from ascii3d.npc_render import draw_npcs
from ascii3d.npcs import NPC
from ascii3d.palette import SKIN, UI_POSITIVE
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.shading import Shading
from ascii3d.surfaces import SolidBox
from ascii3d.world import FLOOR, STONE, World


class NPCRenderingTests(unittest.TestCase):
    def setUp(self):
        self.npc = NPC("Iven", 8.5, 8.5, 1.0, -math.pi / 2, ("Welcome.",))
        self.player = Player(x=8.5, y=5.5)

    def draw(self, seconds=0.0, *, width=90, height=30, focal=52):
        pixels = [["~"] * width for _ in range(height)]
        depths = [[math.inf] * width for _ in range(height)]
        draw_npcs([self.npc], pixels, depths, self.player, focal, 0.5, Shading(), seconds)
        return pixels, depths

    def test_all_outfits_have_opaque_torso_and_head_from_every_side(self):
        for outfit in ("keeper", "mourner", "sentinel"):
            self.npc.outfit = outfit
            for yaw in (0, math.pi / 2, math.pi, -math.pi / 2):
                with self.subTest(outfit=outfit, yaw=yaw):
                    self.player.yaw = yaw
                    self.player.x = self.npc.x - 3.0 * math.cos(yaw)
                    self.player.y = self.npc.y - 3.0 * math.sin(yaw)
                    camera = Camera(self.player, 90, 30, 52, 0.5)
                    pixels, depths = self.draw()
                    for height in (1.12, 1.58):
                        x, y, depth = camera.project(self.npc.x, self.npc.y, self.npc.z + height)
                        self.assertNotEqual(pixels[round(y)][round(x)], "~")
                        self.assertLess(depths[round(y)][round(x)], depth)

    def test_face_turns_with_npc_yaw_and_disappears_behind_the_hood(self):
        camera = Camera(self.player, 90, 30, 52, 0.5)
        x, y, _ = camera.project(self.npc.x, self.npc.y, self.npc.z + 1.54)
        front, _ = self.draw()
        self.npc.yaw += math.pi
        back, _ = self.draw()
        self.assertEqual(front[round(y)][round(x)].material, SKIN)
        self.assertNotEqual(back[round(y)][round(x)].material, SKIN)

    def test_idle_motion_is_visible_across_viewports_and_keeps_feet_planted(self):
        for width, height, distance in ((60, 15, 2.6), (120, 35, 5.0)):
            with self.subTest(width=width, distance=distance):
                self.player.y = self.npc.y - distance
                self.player.pitch = -0.22
                focal = width / (2 * math.tan(math.radians(41)))
                camera = Camera(self.player, width, height, focal, 0.5)
                _, lower_body, _ = camera.project(self.npc.x, self.npc.y, self.npc.z + 0.4)
                lower_row = math.ceil(lower_body)
                size = dict(width=width, height=height, focal=focal)
                first, depths = self.draw(0.4, **size)
                poses = [self.draw(seconds, **size) for seconds in (2.2, 4.0, 5.8)]
                self.assertTrue(any(pixels[:lower_row] != first[:lower_row] for pixels, _ in poses))
                self.assertTrue(any(math.isfinite(depth) for row in depths[lower_row:] for depth in row))
                for pixels, posed_depths in poses:
                    self.assertEqual(pixels[lower_row:], first[lower_row:])
                    self.assertEqual(posed_depths[lower_row:], depths[lower_row:])
                self.assertEqual(self.draw(0.4, **size), (first, depths))

    def test_world_wall_completely_occludes_npc(self):
        world = World.empty(18, 18, 8)
        world.box(0, 0, 0, 18, 18, 1, FLOOR)
        world.box(0, 6, 1, 18, 7, 8)
        renderer = Renderer(world, particles=False)
        self.addCleanup(renderer.close)
        empty = renderer.scene(self.player, 90, 30, 0.4)
        world.npcs.append(self.npc)
        for seconds in (0.4, 2.2, 4.0, 5.8):
            with self.subTest(seconds=seconds):
                self.assertEqual(renderer.scene(self.player, 90, 30, seconds), empty)

    def test_walk_phase_moves_limbs_and_a_stop_restores_the_idle_pose(self):
        idle = self.draw()
        self.npc.walk_blend = 1.0
        self.npc.walk_phase = math.pi / 2
        leading = self.draw()
        self.npc.walk_phase += math.pi
        trailing = self.draw()
        self.assertNotEqual(idle, leading)
        self.assertNotEqual(leading, trailing)
        self.npc.walk_blend = 0.0
        self.assertEqual(self.draw(), idle)

    def test_viewport_budget_limits_visible_npcs(self):
        pixels = [[" "] * 40 for _ in range(12)]
        depths = [[math.inf] * 40 for _ in range(12)]
        behind = NPC("Behind", self.player.x, self.player.y - 3, 1.0, 0, ("Welcome.",))
        npcs = [behind] + [self.npc] * 10
        with patch("ascii3d.npc_render._draw_npc") as draw:
            draw_npcs(npcs, pixels, depths, self.player, 24, 0.5, Shading())
        self.assertEqual(draw.call_count, 2)
        self.assertTrue(all(call.args[0] is self.npc for call in draw.call_args_list))


class NPCNameTests(unittest.TestCase):
    def setUp(self):
        self.world = World.empty(18, 18, 8)
        self.world.box(0, 0, 0, 18, 18, 1, FLOOR)
        self.npc = NPC("Iven", 8.5, 8.5, 1.0, -math.pi / 2, ("Welcome.",))
        self.world.npcs.append(self.npc)
        self.player = Player(x=8.5, y=5.5)
        self.renderer = Renderer(self.world, particles=False)
        self.addCleanup(self.renderer.close)

    def test_resident_name_is_above_head_and_distinct_even_in_monochrome(self):
        for width, height in ((60, 20), (120, 40)):
            with self.subTest(width=width):
                styled = self.renderer.styled_frame(self.player, width, height)
                row, line = next((i, line) for i, line in enumerate(styled.rows) if "<Iven>" in line)
                self.assertLess(row, height // 2)
                column = line.index("<Iven>")
                self.assertEqual(styled.materials[row][column:column + 6], bytes([UI_POSITIVE]) * 6)
                self.assertIn("<Iven>", self.renderer.styled_frame(self.player, width, height,
                                                                    color_mode="mono")[row])
                self.assertNotIn("[E] Talk", "\n".join(styled.rows))

    def test_only_the_front_actor_gets_an_aimed_label(self):
        enemy = Enemy("Training dummy", 8.5, 10.5)
        self.world.combat.enemies.append(enemy)
        rows = "\n".join(self.renderer.frame(self.player, 80, 30))
        self.assertIn("<Iven>", rows)
        self.assertNotIn("Training dummy", rows)
        self.npc.y, enemy.y = enemy.y, self.npc.y
        rows = "\n".join(self.renderer.frame(self.player, 80, 30))
        self.assertIn("Training dummy [3/3]", rows)
        self.assertNotIn("<Iven>", rows)

    def test_label_requires_aim_range_visibility_and_no_dialogue(self):
        self.player.yaw += 0.3
        self.assertNotIn("<Iven>", "\n".join(self.renderer.frame(self.player, 120, 40)))
        self.player.yaw = math.pi / 2
        self.npc.y = 17.0
        self.assertNotIn("<Iven>", "\n".join(self.renderer.frame(self.player, 120, 40)))
        self.npc.y = 8.5
        rows = self.renderer.frame(self.player, 120, 40, dialogue=DialogueView("Iven", "Welcome.", True))
        self.assertNotIn("<Iven>", "\n".join(rows))
        self.world.add_solid(SolidBox(0, 6, 2.57, 18, 7, 4, STONE))
        self.assertIs(self.world.combat.aimed_actor(self.world, self.player), self.npc)
        self.assertNotIn("<Iven>", "\n".join(self.renderer.frame(self.player, 120, 40)))


if __name__ == "__main__":
    unittest.main()

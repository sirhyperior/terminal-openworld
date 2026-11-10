"""Combat ray limits preserve final raster order and foliage work budgets."""

import unittest

from ascii3d.combat import CombatState, Enemy, WARDEN_BEHAVIOR
from ascii3d.doors import Door
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.world import FLOOR, GRASS, STONE, Tree, World


class CombatPrepassTests(unittest.TestCase):
    def fixture(self, grass=False):
        world = World.empty(40, 40, 16)
        world.box(0, 0, 0, 40, 40, 1, GRASS if grass else FLOOR)
        if grass:
            world.outdoor_bounds = (1, 1, 39, 39)
        enemy = Enemy("Stone sentinel", 16.5, 18.5, radius=0.44, height=2.15,
                      hp=4, max_hp=4, behavior=WARDEN_BEHAVIOR,
                      territory=(1, 1, 39, 39))
        world.combat = CombatState(enemies=[enemy])
        return world, enemy, Player(x=16.5, y=16.5)

    def compare(self, world, player, expected):
        fast = Renderer(world)
        reference = Renderer(world, combat_depth_prepass=False)
        for yaw_offset, pitch in ((0, 0), (0.15, -0.2), (-0.15, 0.2)):
            pose = Player(x=player.x, y=player.y, z=player.z,
                          yaw=player.yaw + yaw_offset, pitch=pitch)
            self.assertEqual(fast.scene(pose, 80, 26, 1.5),
                             reference.scene(pose, 80, 26, 1.5))
        self.assertEqual(fast.combat_prepass_used, expected)
        return fast

    def test_close_generic_body_and_grass_keep_identical_visible_pixels(self):
        world, _, player = self.fixture(grass=True)
        self.compare(world, player, True)

    def test_dead_and_near_plane_enemies_keep_the_ordinary_path(self):
        world, enemy, player = self.fixture()
        enemy.hp = 0
        self.compare(world, player, False)
        enemy.hp = enemy.max_hp
        player.y = enemy.y - 0.1
        self.compare(world, player, False)

    def test_walls_and_panels_keep_occlusion_and_labels(self):
        for kind in ("wall", "door"):
            world, _, player = self.fixture()
            if kind == "wall":
                world.box(12, 17, 1, 22, 18, 8, STONE)
            else:
                world.doors.append(Door("screen", 14, 17.5, 5))
            self.compare(world, player, True)

    def test_dense_nearby_canopies_disable_the_prepass_without_detail_loss(self):
        world, _, player = self.fixture(grass=True)
        for x, y in ((15, 17), (17, 17), (16, 19), (14, 20), (18, 20)):
            world.trees[x, y] = Tree(x + 0.5, y + 0.5, height=3.3)
        renderer = self.compare(world, player, False)
        self.assertLessEqual(renderer.scenery.stats["tree_samples"], 80 * 26 * 3)

    def test_nearly_coplanar_voxel_and_body_faces_preserve_depth_tolerance(self):
        world, enemy, player = self.fixture()
        enemy.y = 18.405
        enemy.facing = 0
        world.box(12, 18, 1, 22, 19, 4, STONE)
        self.compare(world, player, True)


if __name__ == "__main__":
    unittest.main()

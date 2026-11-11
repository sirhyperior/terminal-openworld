"""Weapon swaps settle the dropped footprint on continuous terrain."""

import math
import unittest

from ascii3d.combat import FIRE_STAFF, WeaponPickup
from ascii3d.player import Player
from ascii3d.surfaces import HeightField
from ascii3d.world import World


class SmoothItemTests(unittest.TestCase):
    def test_swap_settles_dropped_item_on_its_own_slope_footprint(self):
        world = World.empty(20, 20, 10)
        world.heightfield = HeightField(20, 20, [1 + x * 0.1
                                                for y in range(21) for x in range(21)])
        player = Player(x=8.5, y=8.5, z=1.872, yaw=math.pi / 2)
        sword = WeaponPickup(0, 0)
        staff = WeaponPickup(8.5, 10, z=1.85, weapon=FIRE_STAFF)
        world.combat.held_item = sword
        world.combat.pickups = [staff]
        self.assertEqual([e.name for e in world.interact(player)], ["item_drop", "staff_pickup"])
        self.assertAlmostEqual(sword.z, world.heightfield.height_at(sword.x, sword.y) + 0.014)
        self.assertFalse(world.collides(sword.x, sword.y, sword.z, 0.14, 1.6))
        self.assertTrue(world.collides(sword.x, sword.y, sword.z - 0.001, 0.14, 1.6))


if __name__ == "__main__":
    unittest.main()

"""Player damage feedback and readable health at every supported HUD width."""

import unittest

from ascii3d.combat import FIRE_STAFF, WeaponPickup
from ascii3d.player import Player
from ascii3d.renderer import Renderer
from ascii3d.sound import EFFECTS
from ascii3d.world import FLOOR, World


class PlayerHealthTests(unittest.TestCase):
    def test_damage_clamps_and_defeat_feedback_occurs_once(self):
        player = Player()
        self.assertEqual((player.hp, player.max_hp), (10, 10))
        events = player.take_damage(2)
        self.assertEqual(player.hp, 8)
        self.assertEqual([event.name for event in events], ["player_hurt"])
        events += player.take_damage(99)
        self.assertEqual(player.hp, 0)
        self.assertEqual([event.name for event in events[-2:]],
                         ["player_hurt", "player_down"])
        self.assertEqual(player.take_damage(1), [])
        self.assertEqual(Player().take_damage(0), [])
        self.assertEqual(Player().take_damage(-2), [])
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_health_bar_keeps_equipment_sound_and_fps_at_minimum_width(self):
        world = World.empty(12, 12, 8)
        world.box(0, 0, 0, 12, 12, 1, FLOOR)
        world.combat.held_item = WeaponPickup(0, 0, weapon=FIRE_STAFF)
        renderer = Renderer(world)
        player = Player(x=6.5, y=4.5)
        for width in (60, 120, 180):
            for hp, bar in ((10, "##########"), (6, "######----"), (0, "----------")):
                with self.subTest(width=width, hp=hp):
                    player.hp = hp
                    frame = renderer.frame(player, width, 20, fps=40, sound_on=True)
                    self.assertIn(f"HP [{bar}] {hp}/10", frame[0])
                    for label in ("FIRE STAFF", "SND ON", "40 FPS"):
                        self.assertIn(label, frame[0])
                    self.assertNotIn("MONOLITH", frame[0])
                    self.assertTrue(all(len(line) == width for line in frame))


if __name__ == "__main__":
    unittest.main()

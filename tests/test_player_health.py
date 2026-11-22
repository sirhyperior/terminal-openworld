"""Player damage feedback and readable health at every supported HUD width."""

import math
import unittest

from ascii3d.combat import FIRE_STAFF, WeaponPickup
from ascii3d.palette import UI_DANGER
from ascii3d.player import DAMAGE_CUE_DURATION, DAMAGE_IMPACT_DURATION, Player
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
        self.assertEqual(player.last_damage, 8)
        self.assertEqual([event.name for event in events[-2:]],
                         ["player_hurt", "player_down"])
        self.assertEqual(player.take_damage(1), [])
        self.assertEqual(Player().take_damage(0), [])
        self.assertEqual(Player().take_damage(-2), [])
        self.assertTrue(all(event.name in EFFECTS for event in events))

    def test_hit_cue_is_readable_in_all_modes_and_ages_with_simulation(self):
        world = World.empty(12, 12, 8)
        world.box(0, 0, 0, 12, 12, 1, FLOOR)
        renderer = Renderer(world)
        player = Player(x=6.5, y=4.5)
        player.take_damage(2)
        for mode in ("mono", "gray", "color"):
            with self.subTest(mode=mode):
                frame = renderer.styled_frame(player, 60, 20, color_mode=mode, paused=True)
                rows = frame if mode == "mono" else frame.rows
                self.assertIn("[-2 HP]", rows[1])
                self.assertIn("HP [########--] 8/10", rows[0])
                self.assertEqual(len(rows[1]), 60)
                if mode == "color":
                    self.assertEqual(frame.materials[0][2], UI_DANGER)
                    self.assertEqual(frame.materials[1][30], UI_DANGER)
        self.assertEqual(player.damage_remaining, DAMAGE_CUE_DURATION)
        for _ in range(60):
            player.update(world, set(), 1 / 120)
        self.assertNotIn("[-2 HP]", renderer.frame(player, 60, 20)[1])
        self.assertEqual(player.hp, 8)

    def test_peripheral_marks_point_to_damage_and_fade_before_the_readout(self):
        world = World.empty(12, 12, 8)
        world.box(0, 0, 0, 12, 12, 1, FLOOR)
        renderer = Renderer(world)
        player = Player(x=6.5, y=4.5, yaw=math.pi / 2)
        for source, label, row, column, marks in (
            ((6.5, 6.5), "FRONT", 3, 29, "^^^"),
            ((4.5, 4.5), "LEFT", 9, 2, "<<<"),
            ((6.5, 2.5), "BEHIND", 14, 29, "vvv"),
            ((8.5, 4.5), "RIGHT", 9, 55, ">>>"),
        ):
            with self.subTest(label=label):
                player.take_damage(1, source=source)
                frame = renderer.styled_frame(player, 60, 20, color_mode="color")
                self.assertIn(f"[-1 HP]  {label}", frame.rows[1])
                self.assertEqual(frame.rows[row][column:column + 3], marks)
                self.assertEqual(list(frame.materials[row][column:column + 3]), [UI_DANGER] * 3)
                self.assertEqual(frame.rows[9][30], "+")
        player.yaw = 0
        self.assertIn("FRONT", renderer.frame(player, 60, 20)[1])
        for _ in range(math.ceil(DAMAGE_IMPACT_DURATION * 120) + 1):
            player.update(world, set(), 1 / 120)
        frame = renderer.frame(player, 60, 20)
        self.assertIn("[-1 HP]  FRONT", frame[1])
        self.assertNotEqual(frame[3][29:32], "^^^")
        player.take_damage(1)
        self.assertNotIn("FRONT", renderer.frame(player, 60, 20)[1])
        self.assertEqual(renderer.frame(player, 60, 20)[9][2:5], "!!!")

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

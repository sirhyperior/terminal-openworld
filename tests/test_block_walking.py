"""Vertical fixtures require jumping; authored fine stairs retain walking support."""

import math
import unittest

from ascii3d.combat import FIRE_STAFF, WeaponPickup
from ascii3d.player import Player
from ascii3d.surfaces import HeightField, SolidBox
from ascii3d.world import AIR, FLOOR, GRASS, PATH, STONE, World, build_world


BLOCK_MATERIALS = (STONE, FLOOR, GRASS, PATH)
SURFACES = {STONE: "stone", FLOOR: "stone", GRASS: "grass", PATH: "gravel"}


def fixture_world(material=STONE, rise=1.0, *, partial_terrain=False):
    world = World.empty(24, 24, 12)
    if partial_terrain:
        world.heightfield = HeightField(24, 24, [1.6] * 625, material=GRASS)
        # Turf materials repaint enabled terrain, so carve the authored block's
        # columns first to exercise its voxel face with every material.
        world.box(4, 2, 1, 10, 20, 2, AIR)
        world.box(4, 2, 1, 10, 20, 2, material)
        return world, 1.6, 2.0
    world.box(0, 0, 0, 24, 24, 1, GRASS)
    if rise == 1:
        world.box(4, 2, 1, 10, 20, 2, material)
    else:
        world.add_solid(SolidBox(4, 2, 1, 10, 20, 1 + rise, material))
    return world, 1.0, 1.0 + rise


class BlockWalkingTests(unittest.TestCase):
    def assert_blocked(self, world, feet, keys, dt):
        player = Player(x=3.2, y=12, z=feet, yaw=0)
        events = []
        for _ in range(round(1 / dt)):
            player.update(world, keys, dt)
            events.extend(player.events)
            self.assertTrue(player.grounded)
            self.assertAlmostEqual(player.z, feet, places=5)
            self.assertFalse(world.collides(player.x, player.y, player.z))
        self.assertGreater(player.x, 3.6)
        self.assertLessEqual(player.x, 4 - player.RADIUS + 1e-6)
        self.assertFalse({"jump", "land", "terrain_step"} & {e.name for e in events})

    def test_unit_blocks_reject_walking_sprinting_diagonals_and_large_updates(self):
        controls = ({"w"}, {"w", "shift"}, {"w", "d"}, {"w", "d", "shift"})
        for material in BLOCK_MATERIALS:
            world, feet, _ = fixture_world(material)
            for keys in controls:
                for dt in (1 / 120, 1 / 30, 0.1):
                    with self.subTest(material=material, keys=keys, dt=dt):
                        self.assert_blocked(world, feet, keys, dt)

    def test_partial_heightfield_cannot_snap_up_four_tenths_onto_voxels(self):
        for material in BLOCK_MATERIALS:
            world, feet, _ = fixture_world(material, partial_terrain=True)
            self.assertEqual(world.heightfield.height_at(3.5, 12), 1.6)
            self.assertIsNone(world.heightfield.height_at(4.5, 12))
            for keys in ({"w"}, {"w", "shift"}):
                for dt in (1 / 120, 0.1):
                    with self.subTest(material=material, keys=keys, dt=dt):
                        self.assert_blocked(world, feet, keys, dt)

    def test_unmarked_quarter_and_half_unit_solids_do_not_become_stairs(self):
        for material in BLOCK_MATERIALS:
            for rise in (0.25, 0.5):
                world, feet, _ = fixture_world(material, rise)
                for keys in ({"w"}, {"w", "shift"}):
                    for dt in (1 / 120, 0.1):
                        with self.subTest(material=material, rise=rise, keys=keys, dt=dt):
                            self.assert_blocked(world, feet, keys, dt)

    def test_explicit_jumps_land_on_voxel_fractional_and_partial_terrain_fixtures(self):
        for material in BLOCK_MATERIALS:
            for kind in ("unit", "quarter", "half", "partial_terrain"):
                with self.subTest(material=material, kind=kind):
                    rise = {"unit": 1.0, "quarter": 0.25, "half": 0.5,
                            "partial_terrain": 0.4}[kind]
                    world, feet, top = fixture_world(
                        material, rise, partial_terrain=kind == "partial_terrain")
                    player = Player(x=3.2, y=12, z=feet, yaw=0)
                    events = []
                    highest = feet
                    for tick in range(160):
                        player.update(world, {"w"} if tick < 60 else set(), 1 / 120,
                                      jump=tick == 0)
                        events.extend(player.events)
                        highest = max(highest, player.z)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                    self.assertGreater(highest, top + 0.1)
                    self.assertGreater(player.x, 4 + player.RADIUS)
                    self.assertLess(player.x, 10 - player.RADIUS)
                    self.assertAlmostEqual(player.z, top, places=5)
                    self.assertTrue(player.grounded)
                    self.assertEqual(sum(e.name == "jump" for e in events), 1)
                    landings = [e for e in events if e.name == "land"]
                    self.assertEqual(len(landings), 1)
                    self.assertEqual(landings[0].surface, SURFACES[material])
                    self.assertNotIn("terrain_step", [e.name for e in events])

    def test_standing_and_descending_plain_solids_preserve_support_without_stair_foley(self):
        for material in BLOCK_MATERIALS:
            for rise in (0.25, 0.5):
                with self.subTest(material=material, rise=rise):
                    world, feet, top = fixture_world(material, rise)
                    player = Player(x=9.5, y=12, z=top, yaw=0)
                    events = []
                    for tick in range(90):
                        player.update(world, set() if tick < 30 else {"w"}, 1 / 120)
                        events.extend(player.events)
                        self.assertTrue(player.grounded)
                        self.assertEqual(player.vertical_speed, 0)
                        self.assertFalse(world.collides(player.x, player.y, player.z))
                        if tick < 30:
                            self.assertAlmostEqual(player.z, top, places=5)
                    self.assertGreater(player.x, 10 + player.RADIUS)
                    self.assertAlmostEqual(player.z, feet, places=5)
                    self.assertFalse({"jump", "land", "terrain_step"} & {e.name for e in events})
                    self.assertIn("step_grass", [e.name for e in events])

    def test_generic_support_still_settles_upward_on_ordinary_fixtures(self):
        for kind in ("quarter", "half", "partial_terrain"):
            with self.subTest(kind=kind):
                rise = {"quarter": 0.25, "half": 0.5, "partial_terrain": 0.4}[kind]
                world, feet, top = fixture_world(
                    STONE, rise, partial_terrain=kind == "partial_terrain")
                self.assertEqual(world.walk_support(3.9, 12, feet), (top, STONE))
                self.assertEqual(world.walk_support(3.9, 12, feet, walking=True), (feet, GRASS))
                self.assertEqual(world.walk_support(4.5, 12, top, walking=True), (top, STONE))
                self.assertFalse(world.step_contact(4.5, 12, top))

    def test_swapping_items_settles_the_dropped_footprint_on_an_unmarked_ledge(self):
        world = World.empty(20, 20, 10)
        world.box(0, 0, 0, 20, 20, 1, GRASS)
        world.add_solid(SolidBox(8, 8, 1, 9, 12, 1.25, FLOOR))
        player = Player(x=8.5, y=8.5, z=1.25, yaw=math.pi / 2)
        sword = WeaponPickup(0, 0)
        staff = WeaponPickup(8.5, 10, z=1.25, weapon=FIRE_STAFF)
        world.combat.held_item = sword
        world.combat.pickups = [staff]
        self.assertEqual([event.name for event in world.interact(player)],
                         ["item_drop", "staff_pickup"])
        # The first drop position's center is beyond the ledge, while its
        # footprint still overlaps it and therefore needs upward settling.
        self.assertAlmostEqual(sword.x, 8.5)
        self.assertAlmostEqual(sword.y, 7.95)
        self.assertAlmostEqual(world.surface_height(sword.x, sword.y), 1.0)
        self.assertAlmostEqual(sword.z, 1.25)
        self.assertFalse(world.collides(sword.x, sword.y, sword.z, 0.14, 1.60))
        self.assertTrue(world.collides(sword.x, sword.y, sword.z - 0.001, 0.14, 1.60))


class BuiltWorldWalkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = build_world()

    def test_castle_curtain_tower_and_courtyard_blocks_require_jumping(self):
        cases = (
            ("north curtain", 38.5, 72.5, 6, math.pi / 2, "y", 73, 1),
            ("south curtain", 38.5, 27.5, 6, -math.pi / 2, "y", 27, -1),
            ("west curtain", 31.5, 34.5, 6, math.pi, "x", 31, -1),
            ("east curtain", 78.5, 34.5, 6, 0, "x", 79, 1),
            ("tower merlon", 29.5, 24.5, 8, math.pi, "x", 29, -1),
            ("courtyard masonry", 70.5, 60.5, 1, math.pi / 2, "y", 61, 1),
        )
        for name, x, y, feet, yaw, axis, boundary, direction in cases:
            for keys in ({"w"}, {"w", "shift"}):
                for dt in (1 / 120, 0.1):
                    with self.subTest(case=name, keys=keys, dt=dt):
                        player = Player(x=x, y=y, z=feet, yaw=yaw)
                        self.assertFalse(self.world.collides(x, y, feet))
                        self.assertTrue(self.world.collides(x, y, feet - 0.01))
                        events = []
                        for _ in range(round(0.5 / dt)):
                            player.update(self.world, keys, dt)
                            events.extend(player.events)
                            self.assertTrue(player.grounded)
                            self.assertAlmostEqual(player.z, feet, places=5)
                            self.assertFalse(self.world.collides(player.x, player.y, player.z))
                        coordinate = getattr(player, axis)
                        self.assertGreater(direction * (coordinate - (x if axis == "x" else y)), 0.1)
                        if direction > 0:
                            self.assertLessEqual(coordinate, boundary - player.RADIUS + 1e-6)
                        else:
                            self.assertGreaterEqual(coordinate, boundary + player.RADIUS - 1e-6)
                        self.assertFalse({"jump", "land", "terrain_step"} & {e.name for e in events})

    def test_all_thirteen_flights_walk_and_sprint_both_directions_with_contact_foley(self):
        flights = sorted(self.world._stair_keys)
        self.assertEqual(len(flights), 13)
        total_contacts = 0
        for flight in flights:
            x0, y0, width, length, bottom, top, axis, direction, riser, _ = flight
            along = x0 if axis == "x" else y0
            across = (y0 if axis == "x" else x0) + width / 2
            low_end = along - 0.5 if direction > 0 else along + length + 0.5
            high_end = along + length + 0.5 if direction > 0 else along - 0.5
            yaw = (0 if direction > 0 else math.pi) if axis == "x" else direction * math.pi / 2
            expected_contacts = math.ceil((top - bottom) / riser - 1e-9)
            for keys in ({"w"}, {"w", "shift"}):
                player = Player(x=low_end if axis == "x" else across,
                                y=across if axis == "x" else low_end, z=bottom, yaw=yaw)
                speed = player.RUN_SPEED if "shift" in keys else player.WALK_SPEED
                budget = math.ceil((length + 1.25) * 120 / speed) + 10
                for destination, heading, height, travel in (
                        (high_end, yaw, top, direction),
                        (low_end, yaw + math.pi, bottom, -direction)):
                    with self.subTest(flight=flight, keys=keys, height=height):
                        player.yaw = heading
                        events = []
                        for _ in range(budget):
                            player.update(self.world, keys, 1 / 120)
                            events.extend(player.events)
                            self.assertTrue(player.grounded)
                            self.assertEqual(player.vertical_speed, 0)
                            self.assertFalse(self.world.collides(player.x, player.y, player.z))
                            if travel * (getattr(player, axis) - destination) >= 0:
                                break
                        else:
                            self.fail("authored flight did not reach its landing")
                        self.assertAlmostEqual(player.z, height, places=5)
                        contacts = [event for event in events if event.name == "terrain_step"]
                        self.assertEqual(len(contacts), expected_contacts)
                        self.assertTrue(all(event.surface in ("stone", "wood", "grass", "gravel")
                                            for event in contacts))
                        self.assertFalse({"jump", "land"} & {e.name for e in events})
                        total_contacts += len(contacts)
        self.assertEqual(total_contacts, 1040)


if __name__ == "__main__":
    unittest.main()

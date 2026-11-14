"""Non-box solids share exact sight, cylindrical collision and support."""

from dataclasses import FrozenInstanceError
import math
import random
import unittest

from ascii3d.player import Player
from ascii3d.surfaces import ConvexSolid, SolidBox
from ascii3d.world import FLOOR, GRASS, STONE, World


FACES = ((0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5),
         (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7))


def wedge(material=STONE):
    return ConvexSolid(((2, 2, 1), (4, 2, 1), (4, 4, 1), (2, 4, 1),
                        (2, 2, 2), (4, 2, 4), (4, 4, 4), (2, 4, 2)), FACES, material)


def diamond():
    points = ((4, 3), (5, 4), (4, 5), (3, 4))
    return ConvexSolid(tuple((x, y, z) for z in (1, 3) for x, y in points), FACES)


class ConvexSolidTests(unittest.TestCase):
    def test_closed_finite_convex_validation_and_immutability(self):
        solid = wedge()
        with self.assertRaises(FrozenInstanceError):
            solid.material = FLOOR
        vertices, faces = solid.vertices, solid.faces
        invalid = [(vertices, faces[:-1]),
                   (vertices + ((3, 3, 2),), faces),
                   (((math.nan, 2, 1),) + vertices[1:], faces),
                   (vertices, ((0, 3, 2, 1, 0),) + faces[1:]),
                   (vertices, ((0, 3, 2, 80),) + faces[1:]),
                   (vertices, ((0, 2, 3, 1),) + faces[1:])]
        for points, polygons in invalid:
            with self.subTest(points=points, polygons=polygons):
                with self.assertRaises(ValueError):
                    ConvexSolid(points, polygons)
        # Reversed perimeter winding is normalized, including generator inputs.
        reversed_solid = ConvexSolid(list(vertices), [tuple(reversed(f)) for f in faces])
        self.assertEqual(reversed_solid.planes, solid.planes)

    def test_exact_unnormalized_ray_normal_limit_and_inside_policy(self):
        solid = wedge()
        hit = solid.ray_hit((3, 3, 6), (0, 0, -2), 8)
        self.assertAlmostEqual(hit.distance, 1.5)
        self.assertEqual(hit.normal, (-1 / math.sqrt(2), 0, 1 / math.sqrt(2)))
        self.assertIsNone(solid.ray_hit((3, 3, 6), (0, 0, -2), 1.4))
        self.assertEqual(solid.ray_entry((3, 3, 6), (0, 0, -2), 1.5), 1.5)
        hit = solid.ray_hit((3, 3, 1.5), (0, 0, 0), 8)
        self.assertEqual((hit.distance, hit.normal), (0, (0, 0, 1)))
        self.assertIsNone(solid.ray_hit((3, 3, 6), (0, 0, 0), 8))
        self.assertIsNone(solid.ray_hit((1, 3, 1), (-1, 0, 0), 8))

    def test_box_shaped_piece_matches_box_ray_depths_for_seeded_rays(self):
        vertices = tuple((x, y, z) for z in (1, 3) for x, y in ((2, 2), (4, 2), (4, 4), (2, 4)))
        solid, box = ConvexSolid(vertices, FACES), SolidBox(2, 2, 1, 4, 4, 3)
        rng = random.Random(9182)
        for _ in range(200):
            origin = tuple(rng.uniform(0, 6) for _ in range(3))
            direction = tuple(rng.uniform(-2, 2) for _ in range(3))
            actual, expected = solid.ray_hit(origin, direction, 8), box.ray_hit(origin, direction, 8)
            if expected is None:
                self.assertIsNone(actual)
            else:
                self.assertAlmostEqual(actual.distance, expected.distance, places=12)
                self.assertEqual(actual.normal, expected.normal)

    def test_cylinder_projection_preserves_real_corners_and_empty_aabb(self):
        solid = diamond()
        self.assertFalse(solid.overlaps(5.25, 4, 1.2, 0.2, 1.7))
        self.assertTrue(solid.overlaps(5.19, 4, 1.2, 0.2, 1.7))
        self.assertFalse(solid.overlaps(4.8, 4.8, 1.2, 0.2, 1.7))
        self.assertTrue(solid.overlaps(4, 4, 1.2, 0.2, 1.7))
        self.assertFalse(solid.overlaps(4, 4, 3, 0.2, 1.7))
        self.assertFalse(solid.overlaps(4, 4, -0.7, 0.2, 1.7))
        self.assertIsNone(solid.ray_hit((2, 4.9, 2), (1, 0, 0), 1))

    def test_sloping_support_matches_cylinder_contact_without_aabb_floor(self):
        solid = wedge(FLOOR)
        self.assertEqual(solid.footprint(3, 3, 0), ((3, FLOOR),))
        self.assertAlmostEqual(solid.footprint(3, 3, 0.22)[0][0], 3.22)
        self.assertAlmostEqual(solid.footprint(1.9, 3, 0.22)[0][0], 2.12)
        self.assertEqual(solid.footprint(1.7, 3, 0.22), ())
        self.assertFalse(solid.overlaps(3, 3, 3.22, 0.22, 1.7))
        self.assertTrue(solid.overlaps(3, 3, 3.219, 0.22, 1.7))
        world = World.empty(10, 10, 10)
        world.add_solid(solid)
        self.assertEqual(world.surface_height(3, 3), 3)
        self.assertEqual(world.surface_material(3, 3), FLOOR)
        self.assertEqual(world.surface_height(1.9, 3), 0)
        self.assertAlmostEqual(world.walk_support(3, 3, 3)[0], 3.22)
        self.assertIsNone(world.walk_support(3, 3, 3, walking=True))
        self.assertAlmostEqual(world.walk_support(3, 3, 3.22, walking=True)[0], 3.22)
        self.assertEqual(world.contact_material(3, 3, 3.22), FLOOR)
        self.assertFalse(world.step_contact(3, 3, 3.22))

    def test_inclined_roof_has_exact_head_collision(self):
        vertices = ((2, 2, 3), (4, 2, 4), (4, 4, 4), (2, 4, 3),
                    (2, 2, 5), (4, 2, 5), (4, 4, 5), (2, 4, 5))
        roof = ConvexSolid(vertices, FACES)
        # Lowest roof underside touched by this circular footprint is Z3.4.
        self.assertFalse(roof.overlaps(3, 3, 1.7, 0.2, 1.7))
        self.assertTrue(roof.overlaps(3, 3, 1.701, 0.2, 1.7))
        hit = roof.ray_hit((3, 3, 2), (0, 0, 1), 5)
        self.assertAlmostEqual(hit.distance, 1.5)
        self.assertLess(hit.normal[2], 0)

    def test_world_sight_prepared_queries_and_insertions_share_exact_solid(self):
        world = World.empty(16, 16, 10)
        world.add_solid(diamond())
        query = world.geometry_query((0, 0, 16, 16), ())
        origin, direction = (2, 4.9, 2), (1, 0, 0)
        self.assertAlmostEqual(query(origin, direction, 8).distance, 1.9)
        self.assertAlmostEqual(world.solid_hit(origin, direction, 8), 1.9)
        self.assertTrue(world.line_clear(origin, direction, 1.8))
        self.assertFalse(world.line_clear(origin, direction, 2))
        # A true farther hit survives missing the foreground solid's AABB.
        world.add_solid(SolidBox(6, 4, 1, 7, 6, 3))
        origin = (4.8, 4.8, 2)
        query = world.geometry_query((0, 0, 16, 16), ())
        self.assertAlmostEqual(query(origin, direction, 8).distance, 1.2)
        self.assertAlmostEqual(world.solid_hit(origin, direction, 8), 1.2)

    def test_low_convex_prop_requires_jump_while_flat_support_still_lands(self):
        world = World.empty(12, 12, 8)
        world.box(0, 0, 0, 12, 12, 1, GRASS)
        vertices = tuple((x, y, z) for z in (1, 1.25) for x, y in ((4, 2), (6, 2), (6, 10), (4, 10)))
        world.add_solid(ConvexSolid(vertices, FACES))
        player = Player(x=3.2, y=5, z=1, yaw=0)
        for _ in range(60):
            player.update(world, {'w', 'shift'}, 1 / 120)
        self.assertLessEqual(player.x, 4 - player.RADIUS + 1e-6)
        self.assertEqual(player.z, 1)
        for tick in range(160):
            player.update(world, {'w'} if tick < 55 else set(), 1 / 120, jump=tick == 0)
            self.assertFalse(world.collides(player.x, player.y, player.z))
        self.assertTrue(player.grounded)
        self.assertAlmostEqual(player.z, 1.25)


if __name__ == '__main__':
    unittest.main()

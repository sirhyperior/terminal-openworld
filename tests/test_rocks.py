"""Natural rock silhouettes retain exact sight, cylinder contact and support."""

import math
import random
import unittest

from ascii3d.rocks import add_rock
from ascii3d.surfaces import SolidBox
from ascii3d.world import GRASS, STONE, World


class RockTests(unittest.TestCase):
    def test_seeded_shapes_are_repeatable_bounded_and_keep_global_random_state(self):
        state = random.getstate()
        first = World.empty(24, 24, 12)
        second = World.empty(24, 24, 12)
        for seed in range(64):
            with self.subTest(seed=seed):
                rock = add_rock(first, 8, 9, 1, width=4, depth=3, height=2, seed=seed)
                repeated = add_rock(second, 8, 9, 1, width=4, depth=3, height=2, seed=seed)
                self.assertEqual(rock, repeated)
                self.assertEqual(len(rock.vertices), 17)
                self.assertEqual(len(rock.faces), 17)
                self.assertEqual((rock.x0, rock.y0, rock.z0, rock.x1, rock.y1, rock.z1),
                                 (6, 7.5, 1, 10, 10.5, 3))
                self.assertFalse(rock.stair)
        self.assertEqual(random.getstate(), state)
        self.assertEqual(len({solid.vertices for solid in first.solids}), 64)
        self.assertEqual(len(first.solids), 64)

    def test_cut_corner_is_empty_even_inside_the_bounding_box(self):
        world = World.empty(16, 16, 10)
        rock = add_rock(world, 8, 8, 1, width=4, depth=4, height=2, seed=3)
        x, y = rock.x1 - 0.01, rock.y1 - 0.01
        origin, direction = (x, y, 5), (0, 0, -1)
        box = SolidBox(rock.x0, rock.y0, rock.z0, rock.x1, rock.y1, rock.z1)
        self.assertIsNotNone(box.ray_hit(origin, direction, 5))
        self.assertIsNone(rock.ray_hit(origin, direction, 5))
        self.assertIsNone(world.geometry_hit(origin, direction, 5))
        self.assertTrue(world.line_clear(origin, direction, 5))
        self.assertEqual(rock.footprint(x, y, 0.005), ())
        self.assertFalse(world.collides(x, y, 1.1, radius=0.005))

    def test_real_roof_rays_support_and_cylinder_collision_agree(self):
        world = World.empty(16, 16, 10)
        rock = add_rock(world, 8, 8, 1, width=4, depth=3, height=2, seed=11)
        for x, y in ((8, 8), (7.8, 8.2), (8.5, 7.7)):
            with self.subTest(point=(x, y)):
                hit = rock.ray_hit((x, y, 6), (0, 0, -1), 6)
                self.assertIsNotNone(hit)
                top = 6 - hit.distance
                self.assertAlmostEqual(world.surface_height(x, y), top)
                self.assertEqual(world.surface_material(x, y), STONE)
                self.assertAlmostEqual(max(z for z, _ in rock.footprint(x, y, 0)), top)
                support = world.walk_support(x, y, top, radius=0.12,
                                             max_rise=2, max_drop=2)
                self.assertIsNotNone(support)
                feet, material = support
                self.assertEqual(material, STONE)
                self.assertFalse(world.collides(x, y, feet, radius=0.12))
                self.assertTrue(world.collides(x, y, feet - 0.005, radius=0.12))
                self.assertGreater(hit.normal[2], 0)
                self.assertLess(hit.normal[2], 1)

    def test_inserted_rock_refreshes_prepared_queries_and_surface_results(self):
        world = World.empty(16, 16, 10)
        world.box(0, 0, 0, 16, 16, 1, GRASS)
        # Populate both the voxel surface and the prepared geometry caches.
        self.assertEqual(world.surface_height(8, 8), 1)
        old = add_rock(world, 3, 3, 1, seed=0)
        before = world.geometry_query((0, 0, 16, 16), ())
        self.assertIsNone(before((8, 8, 5), (0, 0, -1), 4))
        revision = world.revision
        rock = add_rock(world, 8, 8, 1, width=3, depth=3, height=2, seed=4)
        self.assertEqual(world.revision, revision + 1)
        self.assertEqual(world.solids, [old, rock])
        after = world.geometry_query((0, 0, 16, 16), ())
        expected = rock.ray_hit((8, 8, 5), (0, 0, -1), 4)
        self.assertEqual(after((8, 8, 5), (0, 0, -1), 4), expected)
        self.assertGreater(world.surface_height(8, 8), 2)
        self.assertEqual(world.surface_material(8, 8), STONE)

    def test_invalid_dimensions_do_not_mutate_the_world(self):
        for kwargs in ({"width": 0}, {"depth": -1}, {"height": 0},
                       {"width": math.nan}, {"height": math.inf},
                       {"x": math.inf}, {"bottom": math.nan}):
            with self.subTest(kwargs=kwargs):
                world = World.empty(16, 16, 10)
                arguments = {"x": 8, "y": 8, "bottom": 1, **kwargs}
                with self.assertRaises(ValueError):
                    add_rock(world, **arguments)
                self.assertFalse(world.solids)
                self.assertEqual(world.revision, 0)


if __name__ == "__main__":
    unittest.main()

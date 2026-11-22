"""Optional compiled lighting for the renderer's ordinary opaque samples."""

from array import array
from ctypes import POINTER, Structure, c_double, c_int, c_size_t, c_uint8, c_uint32
from itertools import chain

from .native_solids import _Hit
from .palette import (ARCANE, BONE, BRIDGE, CRATE, EMBER, FIRE, FLOOR, GRASS,
                      LEAVES, METAL, PATH, STONE, STRAW, WATER, WIND_GRASS, WOOD)
from .paving import PAVING_DISTANCE, PAVING_DISTANT_TONE, PAVING_SCALE, PAVING_SIZE, paving_tile
from .roads import RoadNetwork
from .scenery import Scenery, Wind
from .shading import ALBEDO, GRASS_GLYPHS, RAMP, Shading, VoxelMoonlight, grass_ink, ink
from .world import World


_GLYPHS = RAMP + "".join(GRASS_GLYPHS)
_SAMPLE_SIZE = 9
_FALLBACK = 0xffffffff
_PANEL = _FALLBACK - 1


class _SurfaceLighting(Structure):
    _fields_ = [("moon", POINTER(c_uint32)), ("span", c_int), ("depth", c_int),
                ("ex", c_double), ("ey", c_double), ("ez", c_double), ("ramp_max", c_int),
                ("albedos", POINTER(c_double)), ("albedo_count", c_int), ("paving", POINTER(c_uint8)),
                ("paving_size", c_int), ("paving_scale", c_double), ("paving_fade", c_double),
                ("paving_distant_tone", c_double)]


class _SceneRoads(Structure):
    _fields_ = [("segments", POINTER(c_double)), ("offsets", POINTER(c_uint32)),
                ("indices", POINTER(c_uint32)), ("x0", c_int), ("y0", c_int),
                ("width", c_int), ("height", c_int), ("bucket_size", c_double),
                ("radius_squared", c_double)]

    @classmethod
    def pack(cls, roads):
        if roads is None or not roads._buckets:
            return cls()
        buckets = roads._buckets
        x0, y0 = min(x for x, _ in buckets), min(y for _, y in buckets)
        x1, y1 = max(x for x, _ in buckets), max(y for _, y in buckets)
        width, height = x1 - x0 + 1, y1 - y0 + 1
        if width * height > 65536 or min(x0, y0) < -(1 << 30) or max(x1, y1) > 1 << 30:
            return None
        indices, offsets = [], [0]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                indices.extend(buckets.get((x, y), ()))
                offsets.append(len(indices))
        return cls((c_double * (5 * len(roads.segments)))(*chain.from_iterable(roads.segments)),
                   (c_uint32 * len(offsets))(*offsets), (c_uint32 * len(indices))(*indices),
                   x0, y0, width, height, roads.bucket_size, roads._radius_squared)


class _SceneGust(Structure):
    _fields_ = [(name, c_double) for name in ("x", "y", "radius", "strength", "dx", "dy")]


def _ink_from_code(result):
    return ink(_GLYPHS[result & 255], (result >> 8) & 15, result >> 16, ((result >> 12) & 3) << 2)


class NativeShading:
    def __init__(self, shade, shade_gpu_frame=None, shade_gpu_frame_firelight=None):
        if (STONE, FLOOR, METAL, CRATE, GRASS, WATER, WOOD, LEAVES, PATH,
                BRIDGE, FIRE, EMBER, ARCANE, STRAW, BONE) != tuple(range(1, 16)) or WIND_GRASS != 22:
            raise ValueError("Unsupported native shading material IDs")
        if len(_GLYPHS) > 256 or array("I").itemsize != 4:
            raise ValueError("Unsupported native shading buffers")
        shade.argtypes = (POINTER(c_double), POINTER(c_uint32), c_size_t, POINTER(c_uint32),
                          c_int, c_int, c_double, c_double, c_double, c_int, POINTER(c_double), c_int)
        self._legacy_path = shade.__name__ != "monolith_shade_paving_batch"
        self._paving_args = () if self._legacy_path else None
        if not self._legacy_path:
            shade.argtypes += (POINTER(c_uint8), c_int, c_double, c_double, c_double)
        shade.restype = None
        self._shade = shade
        self._albedos = (c_double * len(ALBEDO))(*ALBEDO)
        self._moon = None
        self._moon_buffer = None
        self._tokens = {0: " ", _PANEL: " ", _FALLBACK: " "}
        self._shade_gpu_frame = shade_gpu_frame
        self._shade_gpu_frame_firelight = shade_gpu_frame_firelight
        self._roads = None
        self._road_data = _SceneRoads()
        packed_args = (
            POINTER(_Hit), POINTER(c_double), POINTER(c_double), c_uint32, c_uint32,
            c_double, c_double, c_double, c_double, POINTER(_SurfaceLighting),
            POINTER(_SceneRoads), POINTER(_SceneGust), c_int, c_int, c_double,
            POINTER(c_double), POINTER(c_double), POINTER(c_uint32), POINTER(c_double), POINTER(c_uint32))
        if shade_gpu_frame is not None:
            shade_gpu_frame.argtypes = packed_args
            shade_gpu_frame.restype = c_uint32
        if shade_gpu_frame_firelight is not None:
            shade_gpu_frame_firelight.argtypes = packed_args + (POINTER(c_double), c_int, c_double)
            shade_gpu_frame_firelight.restype = c_uint32

    def available(self, shading, *, packed=False):
        return (type(shading) is Shading and "surface" not in vars(shading)
                and shading.eye is not None
                and (not shading.lights or (packed and self._shade_gpu_frame_firelight is not None))
                and (shading.moonlight is None or type(shading.moonlight) is VoxelMoonlight))

    def _lighting(self, shading):
        moon = shading.moonlight
        if self._moon is not moon:
            self._moon, self._moon_buffer = moon, None
            if moon is not None:
                self._moon_buffer = (c_uint32 * len(moon.faces)).from_buffer(moon.faces)
        if self._paving_args is None:
            tile = (c_uint8 * (PAVING_SIZE ** 2)).from_buffer_copy(paving_tile())
            self._paving_args = (tile, PAVING_SIZE, PAVING_SCALE, PAVING_DISTANCE, PAVING_DISTANT_TONE)
        return (self._moon_buffer, moon.span if moon is not None else 0, moon.depth if moon is not None else 0,
                *shading.eye, len(RAMP) - 1, self._albedos, len(self._albedos), *self._paving_args)

    def can_shade_gpu_frame(self, world, scenery):
        if (self._shade_gpu_frame is None or self._legacy_path
                or type(world) is not World or "ground_material" in vars(world)
                or type(scenery) is not Scenery or "wind_at" in vars(scenery)
                or (scenery.wind is not None and
                    (type(scenery.wind) is not Wind or "sample" in vars(scenery.wind)))):
            return False
        roads = world.roads
        if roads is not None and (type(roads) is not RoadNetwork or
                                  {"material_at", "contains"}.intersection(vars(roads))):
            return False
        if roads is not self._roads:
            self._roads, self._road_data = roads, _SceneRoads.pack(roads)
        return self._road_data is not None

    def gpu_frame(self, hits, shading, scenery, rotation, door_pixels, door_depths, combat_depths):
        width, height = len(hits.columns), len(hits.rows)
        count = width * height
        codes, depths = array("I", [0]) * count, array("d", [0]) * count
        specials = (c_uint32 * count)()
        output = (c_uint32 * count).from_buffer(codes)
        depth_output = (c_double * count).from_buffer(depths)
        buffers = []
        for depth_rows in (door_depths, combat_depths):
            if depth_rows is None:
                buffers.append(None)
            else:
                values = array("d", chain.from_iterable(depth_rows))
                buffers.append((c_double * count).from_buffer(values))
        lighting = _SurfaceLighting(*self._lighting(shading))
        gusts = (_SceneGust * len(scenery._gusts))(
            *(_SceneGust(g.x, g.y, g.radius, g.strength, g.dx, g.dy) for g in scenery._gusts))
        args = (
            hits.hits, hits.columns, hits.rows, width, height, *rotation, lighting, self._road_data,
            gusts, len(gusts), scenery.wind is not None, scenery._seconds, *buffers,
            output, depth_output, specials)
        if shading.lights:
            count_lights = len(shading.lights)
            lights = (c_double * (3 * count_lights))(*chain.from_iterable(shading.lights))
            special_count = self._shade_gpu_frame_firelight(
                *args, lights, count_lights, shading.FIRELIGHT_RADIUS_SQUARED)
        else:
            special_count = self._shade_gpu_frame(*args)
        tokens = self._tokens
        for code in set(codes).difference(tokens):
            tokens[code] = _ink_from_code(code)
        pixels = [list(map(tokens.__getitem__, codes[start:start + width]))
                  for start in range(0, count, width)]
        depth_rows = [depths[start:start + width].tolist() for start in range(0, count, width)]
        pending = [[] for _ in range(height)]
        for index in specials[:special_count]:
            y, x = divmod(index, width)
            if codes[index] == _PANEL:
                pixels[y][x] = door_pixels[y][x]
            else:
                pending[y].append(x)
        return pixels, depth_rows, pending

    def finish(self, shading, samples, destinations):
        if not destinations:
            return
        count = len(destinations)
        inputs = (c_double * len(samples)).from_buffer(samples)
        output = array("I", [0]) * count
        results = (c_uint32 * count).from_buffer(output)
        self._shade(inputs, results, count, *self._lighting(shading))
        tokens = self._tokens
        legacy_path = self._legacy_path
        for index, ((row, column), result) in enumerate(zip(destinations, output)):
            # Older optional libraries still batch every other material.
            if legacy_path and result >> 16 == PATH:
                result = _FALLBACK
            if result == _FALLBACK:
                start = index * _SAMPLE_SIZE
                x, y, z, nx, ny, nz, distance, material, turn = samples[start:start + _SAMPLE_SIZE]
                if material == GRASS and nz > 0:
                    tone = shading.surface(GRASS, x, y, z, (nx, ny, nz), distance, foliage_turn=turn)
                    row[column] = grass_ink(tone, x, y, turn)
                else:
                    row[column] = shading.surface(int(material), x, y, z, (nx, ny, nz), distance)
                continue
            token = tokens.get(result)
            if token is None:
                token = _ink_from_code(result)
                tokens[result] = token
            row[column] = token

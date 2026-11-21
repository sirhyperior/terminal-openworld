"""Optional compiled lighting for the renderer's ordinary opaque samples."""

from array import array
from ctypes import POINTER, c_double, c_int, c_size_t, c_uint32

from .palette import (ARCANE, BONE, BRIDGE, CRATE, EMBER, FIRE, FLOOR, GRASS,
                      LEAVES, METAL, PATH, STONE, STRAW, WATER, WIND_GRASS, WOOD)
from .shading import ALBEDO, GRASS_GLYPHS, RAMP, Shading, VoxelMoonlight, grass_ink, ink


_GLYPHS = RAMP + "".join(GRASS_GLYPHS)
_SAMPLE_SIZE = 9
_FALLBACK = 0xffffffff


class NativeShading:
    def __init__(self, shade):
        if (STONE, FLOOR, METAL, CRATE, GRASS, WATER, WOOD, LEAVES, PATH,
                BRIDGE, FIRE, EMBER, ARCANE, STRAW, BONE) != tuple(range(1, 16)) or WIND_GRASS != 22:
            raise ValueError("Unsupported native shading material IDs")
        if len(_GLYPHS) > 256 or array("I").itemsize != 4:
            raise ValueError("Unsupported native shading buffers")
        shade.argtypes = (POINTER(c_double), POINTER(c_uint32), c_size_t, POINTER(c_uint32),
                          c_int, c_int, c_double, c_double, c_double, c_int, POINTER(c_double), c_int)
        shade.restype = None
        self._shade = shade
        self._albedos = (c_double * len(ALBEDO))(*ALBEDO)
        self._moon = None
        self._moon_buffer = None
        self._tokens = {}

    def available(self, shading):
        return (type(shading) is Shading and "surface" not in vars(shading)
                and shading.eye is not None and not shading.lights
                and (shading.moonlight is None or type(shading.moonlight) is VoxelMoonlight))

    def finish(self, shading, samples, destinations):
        if not destinations:
            return
        moon = shading.moonlight
        if self._moon is not moon:
            self._moon, self._moon_buffer = moon, None
            if moon is not None:
                self._moon_buffer = (c_uint32 * len(moon.faces)).from_buffer(moon.faces)
        count = len(destinations)
        inputs = (c_double * len(samples)).from_buffer(samples)
        output = array("I", [0]) * count
        results = (c_uint32 * count).from_buffer(output)
        self._shade(inputs, results, count, self._moon_buffer,
                    moon.span if moon is not None else 0, moon.depth if moon is not None else 0,
                    *shading.eye, len(RAMP) - 1, self._albedos, len(self._albedos))
        tokens = self._tokens
        for index, ((row, column), result) in enumerate(zip(destinations, output)):
            token = tokens.get(result)
            if token is None:
                if result == _FALLBACK:
                    start = index * _SAMPLE_SIZE
                    x, y, z, nx, ny, nz, distance, material, turn = samples[start:start + _SAMPLE_SIZE]
                    if material == GRASS and nz > 0:
                        tone = shading.surface(GRASS, x, y, z, (nx, ny, nz), distance, foliage_turn=turn)
                        row[column] = grass_ink(tone, x, y, turn)
                    else:
                        row[column] = shading.surface(int(material), x, y, z, (nx, ny, nz), distance)
                    continue
                token = ink(_GLYPHS[result & 255], (result >> 8) & 15, result >> 16, ((result >> 12) & 3) << 2)
                tokens[result] = token
            row[column] = token

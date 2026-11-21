"""Optional float64 geometry queries through a prebuilt C library."""

from array import array
from ctypes import CDLL, POINTER, Structure, byref, c_double, c_int, c_int32, c_uint8
from pathlib import Path
import os
import sys

from .surfaces import ConvexSolid, HeightField, SolidBox, SurfaceHit


_Vector = c_double * 3


class _Bounds(Structure):
    _fields_ = [('low', _Vector), ('high', _Vector)]

    @classmethod
    def from_box(cls, box):
        return cls(_Vector(box.x0, box.y0, box.z0), _Vector(box.x1, box.y1, box.z1))


class _Node(Structure):
    _fields_ = [('bounds', _Bounds), ('left', c_int32), ('right', c_int32),
                ('first', c_int32), ('count', c_int32)]


class _Shape(Structure):
    _fields_ = [('bounds', _Bounds), ('material', c_int32), ('first_plane', c_int32),
                ('plane_count', c_int32)]


class _Plane(Structure):
    _fields_ = [('normal', _Vector), ('offset', c_double)]


class _Hit(Structure):
    _fields_ = [('distance', c_double), ('normal', _Vector),
                ('material', c_int32), ('tied', c_int32)]


class _HeightChunk(Structure):
    _fields_ = [('high', c_double), ('slope_x', c_double), ('slope_y', c_double), ('upper', c_double)]


class _HeightFieldData(Structure):
    _fields_ = [('heights', POINTER(c_double)), ('enabled', POINTER(c_uint8)),
                ('materials', POINTER(c_uint8)), ('chunks', POINTER(_HeightChunk)),
                ('width', c_int32), ('depth', c_int32), ('chunk_columns', c_int32),
                ('chunk_rows', c_int32), ('chunk_size', c_int32), ('maximum', c_double)]


class SolidLibrary:
    def __init__(self, path=None):
        if path is None:
            suffix = '.dll' if os.name == 'nt' else '.dylib' if sys.platform == 'darwin' else '.so'
            path = Path(__file__).with_name(f'monolith_solid_bvh{suffix}')
        library = CDLL(str(Path(path).resolve()))
        library.monolith_solid_abi.argtypes = []
        library.monolith_solid_abi.restype = c_int
        if library.monolith_solid_abi() != 1:
            raise OSError('Unsupported MONOLITH solid library ABI')
        self.trace = library.monolith_solid_hit
        self.trace.argtypes = (POINTER(_Node), POINTER(_Shape), POINTER(_Plane),
                               c_double, c_double, c_double, c_double, c_double, c_double,
                               c_double, c_double, POINTER(_Hit))
        self.trace.restype = c_int
        self.heightfield_trace = getattr(library, 'monolith_heightfield_hit', None)
        if self.heightfield_trace is not None:
            self.heightfield_trace.argtypes = (POINTER(_HeightFieldData), c_double, c_double, c_double,
                                               c_double, c_double, c_double, c_double, c_double, POINTER(_Hit))
            self.heightfield_trace.restype = c_int


class NativeSolidTree:
    """Packed immutable buffers retained for the selected geometry tree."""

    def __init__(self, library, tree):
        nodes, shapes, planes = [], [], []

        def pack(branch):
            bounds, left, right, boxes = branch
            index = len(nodes)
            nodes.append(None)
            if boxes:
                first = len(shapes)
                for box in boxes:
                    if type(box) not in (SolidBox, ConvexSolid):
                        raise TypeError('Native solid tree requires built-in shapes')
                    if not isinstance(box.material, int) or not -(2 ** 31) <= box.material < 2 ** 31:
                        raise TypeError('Native solid materials must fit a signed 32-bit integer')
                    box_planes = box.planes if type(box) is ConvexSolid else ()
                    shapes.append(_Shape(_Bounds.from_box(box), box.material,
                                         len(planes), len(box_planes)))
                    planes.extend(_Plane(_Vector(nx, ny, nz), offset)
                                  for nx, ny, nz, offset in box_planes)
                node = _Node(_Bounds.from_box(bounds), -1, -1, first, len(boxes))
            else:
                node = _Node(_Bounds.from_box(bounds), pack(left), pack(right), 0, 0)
            nodes[index] = node
            return index

        pack(tree)
        self._trace = library.trace
        self._nodes = (_Node * len(nodes))(*nodes)
        self._shapes = (_Shape * len(shapes))(*shapes)
        self._planes = (_Plane * len(planes))(*planes)

    def ray_hit(self, origin, direction, limit, entry):
        hit = _Hit()
        if not self._trace(self._nodes, self._shapes, self._planes,
                           *origin, *direction, limit, entry, byref(hit)):
            return None, False
        normal = hit.normal
        return SurfaceHit(hit.distance, hit.material, (normal[0], normal[1], normal[2])), bool(hit.tied)


class NativeHeightField:
    """Reuse the field's exact chunk bounds and live elevation/material buffers."""

    def __init__(self, library, field):
        if type(field) is not HeightField:
            raise TypeError('Native terrain requires a built-in heightfield')
        self.field = field
        self._trace = library.heightfield_trace
        self._revision = None
        self._data = None

    def _prepare(self):
        field = self.field
        width, depth, chunk_size = field.width, field.depth, field.CHUNK
        if not all(0 < value < 2 ** 31 for value in (width, depth, chunk_size)):
            return None
        height_count, cell_count = (width + 1) * (depth + 1), width * depth
        if not (len(field.heights) == height_count and len(field.enabled) == len(field.materials) == cell_count):
            return None
        try:
            heights = (c_double * height_count).from_buffer(field.heights)
            enabled = (c_uint8 * cell_count).from_buffer(field.enabled)
            materials = (c_uint8 * cell_count).from_buffer(field.materials)
        except (TypeError, ValueError, BufferError):
            return None
        columns, rows = (width + chunk_size - 1) // chunk_size, (depth + chunk_size - 1) // chunk_size
        bounds = array('d')
        for cy in range(rows):
            for cx in range(columns):
                _, high = field._chunk_bounds(cx, cy)
                bounds.extend((high, *field._chunk_envelopes[cx, cy]))
        chunks = (_HeightChunk * (columns * rows)).from_buffer(bounds)
        return _HeightFieldData(heights, enabled, materials, chunks, width, depth,
                                columns, rows, chunk_size, field._maximum)

    def ray_hit(self, origin, direction, limit, minimum=0.0):
        field = self.field
        if self._trace is not None:
            revision = field.revision
            if self._revision != revision:
                self._data = self._prepare()
                self._revision = revision
            if self._data is not None:
                hit = _Hit()
                result = self._trace(byref(self._data), *origin, *direction, limit, minimum, byref(hit))
                if result >= 0:
                    return SurfaceHit(hit.distance, hit.material, tuple(hit.normal)) if result else None
        return field.ray_hit(origin, direction, limit, minimum=minimum)

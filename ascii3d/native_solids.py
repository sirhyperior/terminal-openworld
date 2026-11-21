"""Optional float64 geometry queries through a prebuilt C library."""

from array import array
from ctypes import CDLL, POINTER, Structure, byref, c_double, c_int, c_int32, c_uint8, c_uint16, c_uint32
from itertools import chain
from pathlib import Path
import math
import os
import struct
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


class _VoxelPrism(Structure):
    _fields_ = [(name, c_int32) for name in ('low_x', 'low_y', 'high_x', 'high_y', 'bottom', 'ceiling')]


class _VoxelGrid(Structure):
    _fields_ = [('cells', POINTER(c_uint8)), ('tops', POINTER(c_int32)),
                ('bounds', POINTER(c_uint32)), ('columns', POINTER(c_uint32)),
                ('rooms', POINTER(c_uint32)), ('prisms', POINTER(_VoxelPrism)),
                ('width', c_int32), ('depth', c_int32), ('height', c_int32),
                ('chunks_x', c_int32), ('chunk_count', c_int32), ('water', c_int32),
                ('water_level', c_double)]


class _GPUScene(Structure):
    _fields_ = [('cells', POINTER(c_uint8)), ('materials', POINTER(c_uint8)),
                ('heights', POINTER(c_double)), ('shapes', POINTER(_Shape)),
                ('planes', POINTER(_Plane)), ('width', c_uint32), ('depth', c_uint32),
                ('cell_count', c_uint32), ('shape_count', c_uint32), ('water_level', c_double)]


def _pack_shape(box, planes):
    if type(box) not in (SolidBox, ConvexSolid):
        raise TypeError('Native geometry requires built-in shapes')
    if not isinstance(box.material, int) or not -(2 ** 31) <= box.material < 2 ** 31:
        raise TypeError('Native solid materials must fit a signed 32-bit integer')
    box_planes = box.planes if type(box) is ConvexSolid else ()
    shape = _Shape(_Bounds.from_box(box), box.material, len(planes), len(box_planes))
    planes.extend(_Plane(_Vector(nx, ny, nz), offset) for nx, ny, nz, offset in box_planes)
    return shape


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
        self.voxel_frame = getattr(library, 'monolith_voxel_frame', None)
        if self.voxel_frame is not None:
            self.voxel_frame.argtypes = (POINTER(_VoxelGrid), *(c_double,) * 7, c_int, c_int, c_int,
                                         *(POINTER(c_double),) * 5, POINTER(c_uint16), POINTER(c_double))
            self.voxel_frame.restype = None
        self.shade_surfaces = getattr(library, 'monolith_shade_batch', None)
        self.gpu_refine = getattr(library, 'monolith_gpu_refine', None)
        if self.gpu_refine is not None:
            self.gpu_refine.argtypes = (POINTER(_GPUScene), POINTER(c_uint32), POINTER(_Hit),
                                       POINTER(c_double), POINTER(c_double), c_uint32, c_uint32,
                                       c_double, c_double, c_double, c_double, c_double, c_double, c_double)
            self.gpu_refine.restype = None


class NativeVoxelGrid:
    """Batch the static voxel DDA with the same world and prism caches as Python."""

    def __init__(self, cast, world, tops, bounds, columns, rooms, water, water_level):
        prism_ids = {None: 0}
        prisms = array('i', [0] * 6)

        def indexes(cache):
            ids = array('I')
            for prism in cache:
                index = prism_ids.get(prism)
                if index is None:
                    index = prism_ids[prism] = len(prism_ids)
                    prisms.extend(prism)
                    if len(prism) == 5:
                        prisms.append(0)
                ids.append(index)
            return (c_uint32 * len(ids)).from_buffer(ids)

        chunks_x = (world.width + 1) // 2
        cells = (c_uint8 * len(world.cells)).from_buffer(world.cells)
        packed_bounds, packed_columns, packed_rooms = map(indexes, (bounds, columns, rooms))
        packed_prisms = (_VoxelPrism * len(prism_ids)).from_buffer(prisms)
        self._data = _VoxelGrid(cells, (c_int32 * len(tops))(*tops), packed_bounds, packed_columns,
                                packed_rooms, packed_prisms, world.width, world.depth, world.height,
                                chunks_x, len(tops), water, water_level)
        self._cast = cast
        self._viewport = None

    def frame(self, origin, camera, ceiling, columns, rows, panels, combat):
        data = self._data
        if not (all(math.isfinite(value) for value in camera)
                and all(0 <= value < bound for value, bound in zip(origin, (data.width, data.depth, data.height)))):
            return None
        if self._viewport is None or self._viewport[0] is not columns or self._viewport[1] is not rows:
            width, height = len(columns), len(rows)
            if any(not math.isfinite(value) or abs(value) > 1000 for value in (*columns, *rows)):
                return None
            size = width * height
            self._viewport = (columns, rows, (c_double * width)(*columns), (c_double * height)(*rows),
                              (c_double * size)(), (c_uint16 * size)(), (c_double * size)())
        _, _, native_columns, native_rows, depths, faces, first_empty = self._viewport

        def depth_buffer(source):
            if source is None:
                return None
            buffer = array('d', chain.from_iterable(source))
            return (c_double * len(buffer)).from_buffer(buffer)

        self._cast(byref(data), *origin, *camera, ceiling, len(columns), len(rows), native_columns,
                   native_rows, depth_buffer(panels), depth_buffer(combat), depths, faces, first_empty)
        return depths, faces, first_empty


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
                shapes.extend(_pack_shape(box, planes) for box in boxes)
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


class NativeGPURefiner:
    """Refine a whole readback in one call, retaining exact Python fallbacks."""

    _record = struct.Struct('=4d2i')

    def __init__(self, library, world, water_level):
        if library.gpu_refine is None or sys.byteorder != 'little':
            raise ValueError('Native compact GPU refinement is unavailable')
        self._refine = library.gpu_refine
        cells = (c_uint8 * len(world.cells)).from_buffer(world.cells)
        field = world.heightfield
        heights = materials = None
        if field is not None:
            if type(field) is not HeightField or (field.width, field.depth) != (world.width, world.depth):
                raise TypeError('Native GPU refinement requires a matching built-in heightfield')
            heights = (c_double * len(field.heights)).from_buffer(field.heights)
            materials = (c_uint8 * len(field.materials)).from_buffer(field.materials)
        planes = []
        shapes = [_pack_shape(box, planes) for box in world.solids]
        self._scene = _GPUScene(cells, materials, heights, (_Shape * len(shapes))(*shapes),
                                (_Plane * len(planes))(*planes), world.width, world.depth,
                                len(cells), len(shapes), water_level)
        self._size = None

    def refine(self, raw, columns, rows, origin, cy, sy, cp, sp, miss):
        width, height = len(columns), len(rows)
        if self._size != (width, height):
            self._columns = (c_double * width)(*columns)
            self._rows = (c_double * height)(*rows)
            self._output = (_Hit * (width * height))()
            self._size = width, height
        record_type = c_uint32 * (width * height * 4)
        records = record_type.from_buffer_copy(raw) if memoryview(raw).readonly else record_type.from_buffer(raw)
        self._refine(byref(self._scene), records, self._output, self._columns, self._rows,
                     width, height, *origin, cy, sy, cp, sp)
        return [None if axis < 0 else miss if not material else
                (distance, material, None, axis - 4) if axis >= 4 else
                (distance, material, (nx, ny, nz), axis)
                for distance, nx, ny, nz, material, axis in self._record.iter_unpack(self._output)]


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

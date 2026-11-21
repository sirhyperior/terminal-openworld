"""Optional float64 solid tree queries through a prebuilt C library."""

from ctypes import CDLL, POINTER, Structure, byref, c_double, c_int, c_int32
from pathlib import Path
import os
import sys

from .surfaces import ConvexSolid, SolidBox, SurfaceHit


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

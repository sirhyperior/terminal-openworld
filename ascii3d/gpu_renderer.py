"""Optional hardware GPU geometry candidates with float64 CPU refinement."""

from array import array
import math
from pathlib import Path
import struct
import time

from .native_solids import NativeGPURefiner, SolidLibrary
from .world import WATER, WATER_LEVEL


_COMPACT_RECORD = struct.Struct('<4I')
_CELL_INDEX_MASK = 0x0fffffff


def camera_rays(player, width, height, aspect=0.5):
    focal = width / (2 * math.tan(math.radians(82) / 2))
    cy, sy = math.cos(player.yaw), math.sin(player.yaw)
    cp, sp = math.cos(player.pitch), math.sin(player.pitch)
    for y in range(height):
        v = (height / 2 - y - 0.5) / (focal * aspect)
        for x in range(width):
            u = (x + 0.5 - width / 2) / focal
            yield cy * (cp - v * sp) + u * sy, sy * (cp - v * sp) - u * cy, sp + v * cp


def voxel_data(cells):
    # array('I', bytearray) reinterprets groups of four bytes. Expand material
    # values instead: the shader indexes one u32 for every voxel.
    return array('I', iter(cells))


def solid_geometry_data(solids):
    """Pack real solid planes and a stackless conservative bounds hierarchy.

    Bounds reject candidates only. Convex leaves retain every plane so a ray
    through an empty part of a piece's AABB can still hit another solid behind.
    The threaded hierarchy avoids a shader stack or a global solid scan.
    """
    packed, planes, nodes = bytearray(), array('f'), []
    for solid in solids:
        shape_planes = getattr(solid, 'planes', ())
        packed.extend(struct.pack('<8f4I', solid.x0, solid.y0, solid.z0, solid.material,
                                  solid.x1, solid.y1, solid.z1, 0,
                                  len(planes) // 4, len(shape_planes), 0, 0))
        planes.extend(value for plane in shape_planes for value in plane)

    def build(indices):
        lower = tuple(min(getattr(solids[i], name) for i in indices) for name in ('x0', 'y0', 'z0'))
        upper = tuple(max(getattr(solids[i], name) for i in indices) for name in ('x1', 'y1', 'z1'))
        index = len(nodes)
        nodes.append(None)
        leaf = 0
        if len(indices) == 1:
            leaf = indices[0] + 1
        else:
            axis = max(range(3), key=lambda a: upper[a] - lower[a])
            low_name, high_name = (('x0', 'x1'), ('y0', 'y1'), ('z0', 'z1'))[axis]
            indices.sort(key=lambda i: (getattr(solids[i], low_name) + getattr(solids[i], high_name), i))
            middle = len(indices) // 2
            build(indices[:middle])
            build(indices[middle:])
        nodes[index] = (*lower, 0, *upper, 0, len(nodes), leaf, 0, 0)

    if solids:
        build(list(range(len(solids))))
    hierarchy = b''.join(struct.pack('<8f4I', *node) for node in nodes)
    return (bytes(packed) or bytes(48), planes or array('f', [0] * 4),
            hierarchy or bytes(48), len(nodes))


class StaticGPU:
    """Persistent device, shader and static buffers; no GUI or display surface."""

    def __init__(self, world, backend=None, cell_aspect=0.5, compact=False):
        try:
            import wgpu
        except ImportError as error:
            raise RuntimeError('Install requirements-gpu.txt in the optional GPU environment; main.py remains the CPU game') from error

        self.wgpu, self.world = wgpu, world
        self.cell_aspect = cell_aspect
        self.compact = compact
        adapters = [a for a in wgpu.gpu.enumerate_adapters_sync()
                    if a.info['adapter_type'] in ('DiscreteGPU', 'IntegratedGPU')
                    and (backend is None or a.info['backend_type'].lower() == backend.lower())]
        if not adapters:
            raise RuntimeError('No hardware GPU adapter; CPU game remains available via main.py')
        adapters.sort(key=lambda a: a.info['adapter_type'] != 'DiscreteGPU')
        self.adapter = adapters[0]
        self.device = self.adapter.request_device_sync()
        self.signature = self._signature()
        field = world.heightfield
        packed_ground = array('I', ((enabled << 8) | material
                                   for enabled, material in zip(field.enabled, field.materials))) if field else array('I', [0])
        packed_boxes, planes, hierarchy, self.solid_node_count = solid_geometry_data(world.solids)
        data = [bytes(112), voxel_data(world.cells), array('f', field.heights) if field else array('f', [0]),
                packed_ground, packed_boxes, planes, hierarchy]
        self.buffers = [self.device.create_buffer_with_data(data=value,
                        usage=wgpu.BufferUsage.STORAGE | (wgpu.BufferUsage.COPY_DST if i == 0 else 0))
                        for i, value in enumerate(data)]
        layout = self.device.create_bind_group_layout(entries=[
            {'binding': i, 'visibility': wgpu.ShaderStage.COMPUTE,
             'buffer': {'type': 'storage' if i == 7 else 'read-only-storage'}} for i in range(8)])
        self.layout = layout
        shader = self.device.create_shader_module(code=Path(__file__).with_name('gpu_static.wgsl').read_text())
        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[layout])
        self.pipeline = self.device.create_compute_pipeline(layout=pipeline_layout,
                         compute={'module': shader, 'entry_point': 'main'})
        self.output = self.bind_group = None
        self.size = None

    def _signature(self):
        field = self.world.heightfield
        return self.world.revision, id(field), field.revision if field else None, len(self.world.solids)

    def resize(self, width, height):
        if self.size == (width, height):
            return
        if min(width, height) < 1:
            raise ValueError('viewport dimensions must be positive')
        if self.output is not None:
            self.output.destroy()
        self.output = self.device.create_buffer(size=width * height * (16 if self.compact else 48),
                      usage=self.wgpu.BufferUsage.STORAGE | self.wgpu.BufferUsage.COPY_SRC)
        self.bind_group = self.device.create_bind_group(layout=self.layout, entries=[
            {'binding': i, 'resource': {'buffer': buffer, 'offset': 0, 'size': buffer.size}}
            for i, buffer in enumerate([*self.buffers, self.output])])
        self.size = width, height

    def query(self, player, width, height):
        if self._signature() != self.signature:
            raise RuntimeError('Static geometry changed; rebuild the GPU prototype before querying')
        self.resize(width, height)
        focal = width / (2 * math.tan(math.radians(82) / 2))
        cy, sy = math.cos(player.yaw), math.sin(player.yaw)
        cp, sp = math.cos(player.pitch), math.sin(player.pitch)
        payload = struct.pack('<16f8I4f', player.x, player.y, player.eye_z, 0,
                              cy * cp, sy * cp, sp, 0, sy, -cy, 0, 0, -cy * sp, -sy * sp, cp, 0,
                              width, height, self.world.width, self.world.depth,
                              self.world.height, self.solid_node_count, int(self.world.heightfield is not None), int(self.compact),
                              1 / focal, 1 / (focal * self.cell_aspect), 48, WATER_LEVEL)
        self.device.queue.write_buffer(self.buffers[0], 0, payload)
        encoder = self.device.create_command_encoder()
        compute = encoder.begin_compute_pass()
        compute.set_pipeline(self.pipeline)
        compute.set_bind_group(0, self.bind_group)
        compute.dispatch_workgroups((width * height + 63) // 64)
        compute.end()
        self.device.queue.submit([encoder.finish()])
        return self.device.queue.read_buffer(self.output)

    def close(self):
        if self.output is not None:
            self.output.destroy()
        for buffer in self.buffers:
            buffer.destroy()
        self.device.destroy()


def decode(data):
    # Keep one flat tuple per pixel. Expanding three padded Python tuples here
    # costs substantially more than GPU dispatch/readback at terminal sizes.
    return list(struct.iter_unpack('<f3If3If3I', data))


def refine_candidate(world, origin, direction, hit, offset=None):
    if offset is None:
        distance, material, kind, index, axis, *_ = hit
    else:
        distance, material, packed, index = hit[offset:offset + 4]
        kind, axis = packed & 63, packed >> 8
    if not material:
        return None
    return _refine_candidate(world, origin, direction, distance, material, kind, index, axis)


def _refine_candidate(world, origin, direction, distance, material, kind, index, axis):
    if kind == 1:
        coordinate = (index % world.width if axis == 0 else
                      (index // world.width) % world.depth if axis == 1 else
                      index // (world.width * world.depth))
        if material == WATER:
            distance = (WATER_LEVEL - origin[2]) / direction[2]
        elif abs(direction[axis]) > 1e-12:
            face = coordinate if direction[axis] >= 0 else coordinate + 1
            distance = (face - origin[axis]) / direction[axis]
        return (distance, material, None) if 0 <= distance <= 48 + 1e-8 else None
    if kind in (2, 3):
        x, y = index % world.width, index // world.width
        a, b, c = world.heightfield._plane(x, y, kind == 3)
        denominator = direction[2] - a * direction[0] - b * direction[1]
        if denominator >= -1e-12:
            return None
        distance = (c + a * (origin[0] - x) + b * (origin[1] - y) - origin[2]) / denominator
        u, v = origin[0] + direction[0] * distance - x, origin[1] + direction[1] * distance - y
        if not (-1e-8 <= distance <= 48 + 1e-8 and -1e-8 <= u <= 1 + 1e-8 and -1e-8 <= v <= 1 + 1e-8
                and ((v >= u - 1e-8) if kind == 3 else (v <= u + 1e-8))):
            return None
        length = math.sqrt(a * a + b * b + 1)
        return max(0.0, distance), material, (-a / length, -b / length, 1 / length)
    if kind == 4:
        exact = world.solids[index].ray_hit(origin, direction, 48)
    else:
        exact = world.heightfield.ray_hit(origin, direction, 48)
    return (exact.distance, exact.material, exact.normal) if exact is not None else None


def refine(world, origin, direction, hit, with_axis=False, reject_invalid=False):
    if len(hit) != 12:
        return refine_candidate(world, origin, direction, hit)
    voxel = refine_candidate(world, origin, direction, hit, 0) if hit[1] else None
    field = refine_candidate(world, origin, direction, hit, 4) if hit[5] else None
    solid = refine_candidate(world, origin, direction, hit, 8) if hit[9] else None
    if reject_invalid and ((hit[1] and voxel is None) or (hit[5] and field is None) or (hit[9] and solid is None)):
        return None
    result = _nearest_candidate(voxel, field, solid)
    if result is None or not with_axis:
        return result
    axis = hit[2] >> 8 if result is voxel else _normal_axis(result[2])
    return (*result, axis)


def _nearest_candidate(voxel, field, solid):
    analytic = solid if solid is not None and (field is None or solid[0] <= field[0] + 1e-10) else field
    return analytic if analytic is not None and (voxel is None or analytic[0] <= voxel[0] + 1e-8) else voxel


def _normal_axis(normal):
    x, y, z = abs(normal[0]), abs(normal[1]), abs(normal[2])
    if y > x:
        return 2 if z > y else 1
    return 2 if z > x else 0


def _refine_compact(world, origin, direction, voxel, field, solid):
    """Refine only the candidates named by one compact shader record."""
    voxel_hit = field_hit = solid_hit = None
    voxel_axis = voxel >> 28
    if voxel:
        index = (voxel & _CELL_INDEX_MASK) - 1
        material = world.cells[index]
        if material:
            voxel_hit = _refine_candidate(world, origin, direction, 0, material, 1, index, voxel_axis)
            if voxel_hit is None:
                return None
    if field:
        index = (field & _CELL_INDEX_MASK) - 1
        material = world.heightfield.materials[index]
        if material:
            field_hit = _refine_candidate(world, origin, direction, 0, material, field >> 28, index, 2)
            if field_hit is None:
                return None
    if solid:
        index = solid - 1
        material = world.solids[index].material
        if material:
            solid_hit = _refine_candidate(world, origin, direction, 0, material, 4, index, 0)
            if solid_hit is None:
                return None
    result = _nearest_candidate(voxel_hit, field_hit, solid_hit)
    if result is None:
        return None
    axis = voxel_axis if result is voxel_hit else _normal_axis(result[2])
    return (*result, axis)


def choose_raw(candidates):
    offset = min((0, 4, 8), key=lambda i: candidates[i] if candidates[i + 1] else math.inf)
    distance, material, packed, index = candidates[offset:offset + 4]
    return distance, material, packed & 63, index, packed >> 8


class GPUBackend:
    """Game geometry accelerator; uncertain rays retain the CPU's exact path."""

    MISS = (math.inf, 0, None, 0)

    def __init__(self, world, cell_aspect=0.5):
        self.world, self.cell_aspect = world, cell_aspect
        self.gpu = StaticGPU(world, cell_aspect=cell_aspect, compact=True)
        self.adapter_info = dict(self.gpu.adapter.info)
        self.last_stats = {}
        self.rebuilds = 0
        self._size = None
        self._columns = self._rows = ()
        self._native_library = None
        try:
            self._native_library = SolidLibrary()
        except (AttributeError, OSError):
            pass
        self._native_refiner = self._prepare_refiner()

    def _prepare_refiner(self):
        library = self._native_library
        if library is not None and library.gpu_refine is not None:
            try:
                return NativeGPURefiner(library, self.world, WATER_LEVEL)
            except (BufferError, TypeError, ValueError):
                pass
        return None

    def set_cell_aspect(self, value):
        self.cell_aspect = self.gpu.cell_aspect = value
        self._size = None
        if self._native_refiner is not None:
            self._native_refiner.invalidate_projection()

    def render(self, player, width, height):
        if self.gpu._signature() != self.gpu.signature:
            self.gpu.close()
            self.gpu = StaticGPU(self.world, self.adapter_info['backend_type'], self.cell_aspect, compact=True)
            self._native_refiner = self._prepare_refiner()
            self.rebuilds += 1
        origin = player.x, player.y, player.eye_z
        # A float32 origin straddling a grid plane cannot establish which side
        # the float64 camera occupies. The existing CPU renderer resolves it.
        margin = 4e-7 * (1 + max(abs(value) for value in origin))
        if any(0 < abs(value - round(value)) < margin for value in origin):
            self.last_stats = {'fallback_rays': width * height, 'origin_fallback': True}
            return None
        start = time.perf_counter()
        raw = self.gpu.query(player, width, height)
        queried = time.perf_counter()
        if memoryview(raw).nbytes != width * height * _COMPACT_RECORD.size:
            raise ValueError('GPU readback size does not match the viewport')
        decoded = time.perf_counter()
        if self._size != (width, height):
            focal = width / (2 * math.tan(math.radians(82) / 2))
            self._columns = [(x + 0.5 - width / 2) / focal for x in range(width)]
            self._rows = [(height / 2 - y - 0.5) / (focal * self.cell_aspect) for y in range(height)]
            self._size = width, height
        cy, sy = math.cos(player.yaw), math.sin(player.yaw)
        cp, sp = math.cos(player.pitch), math.sin(player.pitch)
        if self._native_refiner is not None:
            results = self._native_refiner.refine(raw, self._columns, self._rows, origin,
                                                  cy, sy, cp, sp, self.MISS)
            fallbacks = results.count(None)
        else:
            records = _COMPACT_RECORD.iter_unpack(raw)
            results, fallbacks = [], 0
            offsets = [(u * sy, u * cy) for u in self._columns]
            world = self.world
            for v in self._rows:
                forward = cp - v * sp
                base_x, base_y, dz = cy * forward, sy * forward, sp + v * cp
                for offset_x, offset_y in offsets:
                    voxel, field, solid, flags = next(records)
                    if flags & 64:
                        result = None
                    elif voxel or field or solid:
                        direction = base_x + offset_x, base_y - offset_y, dz
                        result = _refine_compact(world, origin, direction, voxel, field, solid)
                    else:
                        result = self.MISS
                    results.append(result)
                    fallbacks += result is None
        self.last_stats = {'query_readback_ms': (queried - start) * 1000,
                           # Decoding is included in the refinement stage.
                           'decode_ms': (decoded - queried) * 1000,
                           'refine_ms': (time.perf_counter() - decoded) * 1000,
                           'native_refinement': self._native_refiner is not None,
                           'fallback_rays': fallbacks, 'rebuilds': self.rebuilds}
        return results

    def close(self):
        self._native_refiner = None
        self.gpu.close()

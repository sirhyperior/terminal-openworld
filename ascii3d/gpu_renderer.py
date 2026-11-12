"""Optional hardware GPU geometry candidates with float64 CPU refinement."""

from array import array
from dataclasses import dataclass
import math
from pathlib import Path
import struct
import time

from .world import WATER, WATER_LEVEL


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
        packed_boxes = array('f', (value for box in world.solids
                                  for value in (box.x0, box.y0, box.z0, box.material,
                                                box.x1, box.y1, box.z1, 0))) or array('f', [0] * 8)
        data = [bytes(112), voxel_data(world.cells), array('f', field.heights) if field else array('f', [0]),
                packed_ground, packed_boxes]
        self.buffers = [self.device.create_buffer_with_data(data=value,
                        usage=wgpu.BufferUsage.STORAGE | (wgpu.BufferUsage.COPY_DST if i == 0 else 0))
                        for i, value in enumerate(data)]
        layout = self.device.create_bind_group_layout(entries=[
            {'binding': i, 'visibility': wgpu.ShaderStage.COMPUTE,
             'buffer': {'type': 'storage' if i == 5 else 'read-only-storage'}} for i in range(6)])
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
                              self.world.height, len(self.world.solids), int(self.world.heightfield is not None), int(self.compact),
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
    analytic = solid if solid is not None and (field is None or solid[0] <= field[0] + 1e-10) else field
    result = analytic if analytic is not None and (voxel is None or analytic[0] <= voxel[0] + 1e-8) else voxel
    if result is None or not with_axis:
        return result
    if result is voxel:
        axis = hit[2] >> 8
    else:
        normal = result[2]
        axis = max(range(3), key=lambda a: abs(normal[a]))
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

    def render(self, player, width, height):
        if self.gpu._signature() != self.gpu.signature:
            self.gpu.close()
            self.gpu = StaticGPU(self.world, self.adapter_info['backend_type'], self.cell_aspect, compact=True)
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
        records = list(struct.iter_unpack('<4I', raw))
        decoded = time.perf_counter()
        results, fallbacks = [], 0
        if self._size != (width, height):
            focal = width / (2 * math.tan(math.radians(82) / 2))
            self._columns = [(x + 0.5 - width / 2) / focal for x in range(width)]
            self._rows = [(height / 2 - y - 0.5) / (focal * self.cell_aspect) for y in range(height)]
            self._size = width, height
        cy, sy = math.cos(player.yaw), math.sin(player.yaw)
        cp, sp = math.cos(player.pitch), math.sin(player.pitch)
        for pixel, record in enumerate(records):
            voxel, field, solid, flags = record
            if flags & 64:
                results.append(None)
                fallbacks += 1
                continue
            if not (voxel or field or solid):
                results.append(self.MISS)
                continue
            u, v = self._columns[pixel % width], self._rows[pixel // width]
            direction = cy * (cp - v * sp) + u * sy, sy * (cp - v * sp) - u * cy, sp + v * cp
            voxel_index = (voxel & 0x0fffffff) - 1
            field_index = (field & 0x0fffffff) - 1
            solid_index = solid - 1
            candidates = (0, self.world.cells[voxel_index] if voxel else 0, 1 | ((voxel >> 28) << 8), voxel_index,
                          0, self.world.heightfield.materials[field_index] if field else 0, (field >> 28) | 512, field_index,
                          0, self.world.solids[solid_index].material if solid else 0, 4, solid_index)
            result = refine(self.world, origin, direction, candidates, with_axis=True, reject_invalid=True)
            if result is None and (voxel or field or solid):
                results.append(None)
                fallbacks += 1
            else:
                results.append(result if result is not None else self.MISS)
        self.last_stats = {'query_readback_ms': (queried - start) * 1000,
                           'decode_ms': (decoded - queried) * 1000,
                           'refine_ms': (time.perf_counter() - decoded) * 1000,
                           'fallback_rays': fallbacks, 'rebuilds': self.rebuilds}
        return results

    def close(self):
        self.gpu.close()

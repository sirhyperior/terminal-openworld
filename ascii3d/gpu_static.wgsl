// Experimental static geometry only. One invocation per terminal character.
// Float32 candidates are checked against the CPU reference by gpu_prototype.py.
struct Params {
    origin: vec4<f32>,
    forward: vec4<f32>,
    right: vec4<f32>,
    up: vec4<f32>,
    sizes: vec4<u32>, // viewport W/H, world W/D
    scene: vec4<u32>, // world H, solid BVH node count, field present, compact output
    lens: vec4<f32>, // inverse focal X/Y, far depth, water level
}
struct Box { low: vec4<f32>, high: vec4<f32>, metadata: vec4<u32> }
struct SolidNode { low: vec4<f32>, high: vec4<f32>, metadata: vec4<u32> }
struct Hit { depth: f32, material: u32, kind: u32, index: u32, axis: u32 }
@group(0) @binding(0) var<storage, read> params: Params;
@group(0) @binding(1) var<storage, read> voxels: array<u32>;
@group(0) @binding(2) var<storage, read> heights: array<f32>;
@group(0) @binding(3) var<storage, read> ground: array<u32>;
@group(0) @binding(4) var<storage, read> boxes: array<Box>;
@group(0) @binding(5) var<storage, read> solid_planes: array<vec4<f32>>;
@group(0) @binding(6) var<storage, read> solid_nodes: array<SolidNode>;
@group(0) @binding(7) var<storage, read_write> output: array<vec4<u32>>;

fn empty_hit() -> Hit { return Hit(1e30, 0u, 0u, 0u, 0u); }
fn reciprocal(value: f32) -> f32 {
    if abs(value) < 1e-12 { return 1e30; }
    return 1.0 / abs(value);
}

fn voxel_hit(o: vec3<f32>, d: vec3<f32>) -> Hit {
    var cell = vec3<i32>(floor(o));
    let step = select(vec3<i32>(-1), vec3<i32>(1), d >= vec3<f32>(0));
    let delta = vec3<f32>(reciprocal(d.x), reciprocal(d.y), reciprocal(d.z));
    var side = select(o - vec3<f32>(cell), vec3<f32>(cell + vec3<i32>(1)) - o,
                      step > vec3<i32>(0)) * delta;
    let size = vec3<i32>(i32(params.sizes.z), i32(params.sizes.w), i32(params.scene.x));
    var distance = 0.0;
    var axis = 0u;
    var flags = 0u;
    let padding = 4e-7 * (1.0 + max(abs(o.x), max(abs(o.y), abs(o.z)))
                              + params.lens.z * max(abs(d.x), max(abs(d.y), abs(d.z))));
    for (var n = 0u; n < params.sizes.z + params.sizes.w + params.scene.x + 3u; n++) {
        if side.x <= side.y && side.x <= side.z { axis = 0u; }
        else if side.y <= side.z { axis = 1u; }
        else { axis = 2u; }
        distance = side[axis];
        let point = o + d * distance;
        for (var a = 0u; a < 3u; a++) {
            if a != axis && min(fract(point[a]), 1.0 - fract(point[a])) < padding { flags = 64u; }
        }
        cell[axis] += step[axis];
        side[axis] = 1e30;
        if abs(d[axis]) > 1e-12 {
            side[axis] = (f32(cell[axis] + select(0, 1, step[axis] > 0)) - o[axis]) / d[axis];
        }
        if distance > params.lens.z || any(cell < vec3<i32>(0)) || any(cell >= size) { break; }
        let index = u32((cell.z * size.y + cell.y) * size.x + cell.x);
        var material = voxels[index];
        if material == 6u {
            var surface = -1.0;
            if d.z < -1e-12 { surface = (params.lens.w - o.z) / d.z; }
            if distance - 1e-8 <= surface && surface <= min(side.x, min(side.y, side.z)) + 1e-8 {
                distance = surface;
                axis = 2u;
            } else { material = 0u; }
        }
        if material != 0u { return Hit(distance, material, 1u | flags, index, axis); }
    }
    return Hit(1e30, 0u, flags, 0u, 0u);
}

fn field_hit(o: vec3<f32>, d: vec3<f32>, limit: f32) -> Hit {
    if params.scene.z == 0u { return empty_hit(); }
    let size = vec2<i32>(i32(params.sizes.z), i32(params.sizes.w));
    var cell = vec2<i32>(floor(o.xy + d.xy * 1e-9));
    let step = select(vec2<i32>(-1), vec2<i32>(1), d.xy >= vec2<f32>(0));
    let delta = vec2<f32>(reciprocal(d.x), reciprocal(d.y));
    var side = select(o.xy - vec2<f32>(cell), vec2<f32>(cell + vec2<i32>(1)) - o.xy,
                      step > vec2<i32>(0)) * delta;
    var left = 0.0;
    var flags = 0u;
    let padding = 4e-7 * (1.0 + max(abs(o.x), max(abs(o.y), abs(o.z)))
                              + params.lens.z * max(abs(d.x), max(abs(d.y), abs(d.z))));
    for (var n = 0u; n < params.sizes.z + params.sizes.w + 1u; n++) {
        if left > limit + 1e-9 || any(cell < vec2<i32>(0)) || any(cell >= size) { break; }
        let right = min(limit, min(side.x, side.y));
        let index = u32(cell.y * size.x + cell.x);
        if ground[index] >= 256u {
            let stride = params.sizes.z + 1u;
            let vertex = u32(cell.y) * stride + u32(cell.x);
            let h00 = heights[vertex];
            let h10 = heights[vertex + 1u];
            let h01 = heights[vertex + stride];
            let h11 = heights[vertex + stride + 1u];
            let slopes = array<vec2<f32>, 2>(vec2<f32>(h10 - h00, h11 - h10),
                                            vec2<f32>(h11 - h01, h01 - h00));
            let uv = o.xy + d.xy * left - vec2<f32>(cell);
            let plane = slopes[select(0u, 1u, uv.y > uv.x)];
            if o.z + d.z * left < h00 + dot(plane, uv) - 1e-7 {
                return Hit(max(0.0, left), ground[index] & 255u, 5u | 64u, index, 2u);
            }
            var hit = empty_hit();
            for (var triangle = 0u; triangle < 2u; triangle++) {
                let slope = slopes[triangle];
                let denominator = d.z - dot(slope, d.xy);
                if abs(denominator) < padding { flags = 64u; }
                if denominator >= -1e-12 { continue; }
                let t = (h00 + dot(slope, o.xy - vec2<f32>(cell)) - o.z) / denominator;
                let tolerance = padding / max(abs(denominator), 1e-4);
                if t >= -tolerance && t <= limit + tolerance
                        && (abs(t - left) < tolerance || abs(t - right) < tolerance) { flags = 64u; }
                if t < left - 1e-8 || t > right + 1e-8 || t < -1e-8 { continue; }
                let at = o.xy + d.xy * t - vec2<f32>(cell);
                if abs(at.x - at.y) < padding * 2.0 { flags = 64u; }
                if (triangle == 0u && at.y <= at.x + 1e-8) || (triangle == 1u && at.y >= at.x - 1e-8) {
                    if max(0.0, t) < hit.depth {
                        hit = Hit(max(0.0, t), ground[index] & 255u, (2u + triangle) | flags, index, 2u);
                    }
                }
            }
            if hit.material != 0u { hit.kind |= flags; return hit; }
        }
        if right >= limit { break; }
        let crossing = right + 1e-10;
        if side.x <= crossing {
            cell.x += step.x;
            side.x = 1e30;
            if abs(d.x) > 1e-12 { side.x = (f32(cell.x + select(0, 1, step.x > 0)) - o.x) / d.x; }
        }
        if side.y <= crossing {
            cell.y += step.y;
            side.y = 1e30;
            if abs(d.y) > 1e-12 { side.y = (f32(cell.y + select(0, 1, step.y > 0)) - o.y) / d.y; }
        }
        left = right;
    }
    return Hit(1e30, 0u, flags, 0u, 0u);
}

fn box_hit(o: vec3<f32>, d: vec3<f32>, limit: f32, index: u32) -> Hit {
    let box = boxes[index];
    var enter = 0.0;
    var leave = limit;
    var axis = 2u;
    var flags = 0u;
    let padding = 4e-7 * (1.0 + max(abs(o.x), max(abs(o.y), abs(o.z)))
                              + params.lens.z * max(abs(d.x), max(abs(d.y), abs(d.z))));
    for (var a = 0u; a < 3u; a++) {
        if abs(d[a]) < 1e-12 {
            if o[a] < box.low[a] || o[a] > box.high[a] {
                let gap = max(box.low[a] - o[a], o[a] - box.high[a]);
                return Hit(1e30, 0u, select(0u, 64u, gap < padding), 0u, 0u);
            }
        } else {
            let t0 = (box.low[a] - o[a]) / d[a];
            let t1 = (box.high[a] - o[a]) / d[a];
            if min(t0, t1) > enter { enter = min(t0, t1); axis = a; }
            leave = min(leave, max(t0, t1));
            let tolerance = padding / max(abs(d[a]), 1e-6);
            if abs(enter - leave) < tolerance { flags = 64u; }
            if enter > leave + 1e-10 { return Hit(1e30, 0u, flags, 0u, 0u); }
        }
    }
    if leave < 0.0 { return empty_hit(); }
    return Hit(enter, u32(box.low.w), 4u | flags, index, axis);
}

fn convex_hit(o: vec3<f32>, d: vec3<f32>, limit: f32, index: u32) -> Hit {
    let shape = boxes[index];
    if shape.metadata.y == 0u { return box_hit(o, d, limit, index); }
    var enter = 0.0;
    var leave = limit;
    var flags = 0u;
    var axis = 2u;
    let scale = max(abs(o.x), max(abs(o.y), abs(o.z)))
              + max(abs(shape.low.x), max(abs(shape.low.y), abs(shape.low.z)))
              + max(abs(shape.high.x), max(abs(shape.high.y), abs(shape.high.z)));
    let padding = 8e-7 * (1.0 + scale + params.lens.z * length(d));
    for (var face = 0u; face < shape.metadata.y; face++) {
        let plane = solid_planes[shape.metadata.x + face];
        let numerator = plane.w - dot(plane.xyz, o);
        let denominator = dot(plane.xyz, d);
        // A nearly parallel face may change sign after float32 conversion.
        // Preserve uncertainty even on a miss so the full CPU query can win.
        if abs(denominator) < 1e-6 * max(1.0, length(d)) {
            if abs(numerator) <= padding + params.lens.z * abs(denominator) { flags = 64u; }
        }
        if abs(denominator) < 1e-12 {
            if numerator < -1e-10 { return Hit(1e30, 0u, flags, 0u, 0u); }
            continue;
        }
        let t = numerator / denominator;
        let tolerance = padding / max(abs(denominator), 1e-6);
        if denominator < 0.0 {
            if t > enter {
                enter = t;
                let n = abs(plane.xyz);
                axis = select(select(2u, 1u, n.y >= n.z), 0u, n.x >= n.y && n.x >= n.z);
            }
        } else { leave = min(leave, t); }
        if abs(enter - leave) <= tolerance { flags = 64u; }
        if enter > leave + 1e-10 { return Hit(1e30, 0u, flags, 0u, 0u); }
    }
    if leave < 0.0 { return Hit(1e30, 0u, flags, 0u, 0u); }
    return Hit(enter, u32(shape.low.w), 4u | flags, index, axis);
}

fn node_intersects(o: vec3<f32>, d: vec3<f32>, limit: f32, node: SolidNode) -> bool {
    let padding = 8e-7 * (1.0 + length(o) + params.lens.z * length(d));
    var enter = 0.0;
    var leave = limit + padding;
    for (var axis = 0u; axis < 3u; axis++) {
        let low = node.low[axis] - padding;
        let high = node.high[axis] + padding;
        if abs(d[axis]) < 1e-12 {
            if o[axis] < low || o[axis] > high { return false; }
        } else {
            let first = (low - o[axis]) / d[axis];
            let last = (high - o[axis]) / d[axis];
            enter = max(enter, min(first, last));
            leave = min(leave, max(first, last));
            if enter > leave { return false; }
        }
    }
    return leave >= 0.0;
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let count = params.sizes.x * params.sizes.y;
    if id.x >= count { return; }
    let x = id.x % params.sizes.x;
    let y = id.x / params.sizes.x;
    let u = (f32(x) + 0.5 - f32(params.sizes.x) * 0.5) * params.lens.x;
    let v = (f32(params.sizes.y) * 0.5 - f32(y) - 0.5) * params.lens.y;
    let d = params.forward.xyz + u * params.right.xyz + v * params.up.xyz;
    let o = params.origin.xyz;
    let voxel = voxel_hit(o, d);
    // Float32 voxel depth may round just before an analytic boundary. Expand
    // only candidate search; Python performs the original float64 merge.
    let padding = 1e-5 * (1.0 + max(abs(o.x), max(abs(o.y), abs(o.z)))
                              + params.lens.z * max(abs(d.x), max(abs(d.y), abs(d.z))));
    let limit = min(params.lens.z, voxel.depth + padding);
    let field = field_hit(o, d, limit);
    var solid = empty_hit();
    var solid_flags = 0u;
    var node_index = 0u;
    loop {
        if node_index >= params.scene.y { break; }
        let node = solid_nodes[node_index];
        if !node_intersects(o, d, min(limit, solid.depth + padding), node) {
            node_index = node.metadata.x;
            continue;
        }
        node_index++;
        if node.metadata.y != 0u {
            let candidate = convex_hit(o, d, min(limit, solid.depth + padding), node.metadata.y - 1u);
            solid_flags |= candidate.kind & 64u;
            if candidate.material != 0u {
                if abs(candidate.depth - solid.depth) <= padding { solid_flags |= 64u; }
                if candidate.depth <= solid.depth { solid = candidate; }
            }
        }
    }
    solid.kind |= solid_flags;
    if params.scene.w != 0u {
        let voxel_code = select(0u, (voxel.index + 1u) | (voxel.axis << 28u), voxel.material != 0u);
        let field_code = select(0u, (field.index + 1u) | ((field.kind & 63u) << 28u), field.material != 0u);
        let solid_code = select(0u, solid.index + 1u, solid.material != 0u);
        output[id.x] = vec4<u32>(voxel_code, field_code, solid_code, (voxel.kind | field.kind | solid.kind) & 64u);
        return;
    }
    output[id.x * 3u] = vec4<u32>(bitcast<u32>(voxel.depth), voxel.material, voxel.kind | (voxel.axis << 8u), voxel.index);
    output[id.x * 3u + 1u] = vec4<u32>(bitcast<u32>(field.depth), field.material, field.kind | (field.axis << 8u), field.index);
    output[id.x * 3u + 2u] = vec4<u32>(bitcast<u32>(solid.depth), solid.material, solid.kind | (solid.axis << 8u), solid.index);
}

/* Refine compact GPU candidates using the same float64 tests as the host. */
typedef struct {
    uint32_t voxel, field, solid, flags;
} GPURecord;

typedef struct {
    const uint8_t *cells, *materials;
    const double *heights;
    const Shape *shapes;
    const Plane *planes;
    uint32_t width, depth, cell_count, shape_count;
    double water_level;
} GPUScene;

static int gpu_field_hit(const GPUScene *scene, const Trace *ray, uint32_t code, Hit *hit) {
    uint32_t index = (code & 0x0fffffffu) - 1, kind = code >> 28;
    if (!scene->heights || index >= (uint64_t) scene->width * scene->depth || (kind != 2 && kind != 3))
        return 0;
    hit->material = scene->materials[index];
    if (!hit->material)
        return 1;
    uint32_t x = index % scene->width, y = index / scene->width;
    size_t stride = (size_t) scene->width + 1, vertex = index + (size_t) y;
    const double *h = scene->heights + vertex;
    double a = kind == 3 ? h[stride + 1] - h[stride] : h[1] - h[0];
    double b = kind == 3 ? h[stride] - h[0] : h[stride + 1] - h[1];
    const double *o = ray->origin, *d = ray->direction;
    double denominator = d[2] - a * d[0] - b * d[1];
    if (denominator >= -1e-12)
        return 0;
    double distance = (h[0] + a * (o[0] - x) + b * (o[1] - y) - o[2]) / denominator;
    double u = o[0] + d[0] * distance - x, v = o[1] + d[1] * distance - y;
    if (!(distance >= -1e-8 && distance <= 48 + 1e-8 &&
          u >= -1e-8 && u <= 1 + 1e-8 && v >= -1e-8 && v <= 1 + 1e-8 &&
          (kind == 3 ? v >= u - 1e-8 : v <= u + 1e-8)))
        return 0;
    double length = sqrt(a * a + b * b + 1);
    hit->distance = fmax(0.0, distance);
    hit->normal[0] = -a / length;
    hit->normal[1] = -b / length;
    hit->normal[2] = 1 / length;
    return 1;
}

static int gpu_voxel_hit(const GPUScene *scene, const Trace *ray, uint32_t code, Hit *hit) {
    uint32_t index = (code & 0x0fffffffu) - 1, axis = code >> 28;
    if (index >= scene->cell_count || axis > 2)
        return 0;
    hit->material = scene->cells[index];
    if (!hit->material)
        return 1;
    const double *o = ray->origin, *d = ray->direction;
    double distance = 0.0;
    if (hit->material == 6) {
        distance = (scene->water_level - o[2]) / d[2];
    } else if (fabs(d[axis]) > 1e-12) {
        uint32_t coordinate = axis == 0 ? index % scene->width :
                              axis == 1 ? index / scene->width % scene->depth :
                                          index / scene->width / scene->depth;
        double face = coordinate + (d[axis] < 0);
        distance = (face - o[axis]) / d[axis];
    }
    hit->distance = distance;
    hit->tied = (int32_t) axis + 4; /* Voxel normal is implicit in its face axis. */
    return distance >= 0.0 && distance <= 48 + 1e-8;
}

static void gpu_refine_record(const GPUScene *scene, const Trace *ray, const GPURecord *record, Hit *out) {
    Hit voxel = {0}, field = {0};
    if (record->flags & 64u)
        return;
    if (record->voxel && !gpu_voxel_hit(scene, ray, record->voxel, &voxel))
        return;
    if (record->field && !gpu_field_hit(scene, ray, record->field, &field))
        return;
    if (record->solid) {
        if (record->solid > scene->shape_count)
            return;
        const Shape *shape = scene->shapes + record->solid - 1;
        if (shape->material) {
            Hit solid = {0};
            int found = shape->plane_count ? convex(shape, ray, &solid.distance, solid.normal) :
                                             slab(&shape->bounds, ray, &solid.distance, solid.normal);
            if (!found)
                return;
            if (!field.material || solid.distance <= field.distance + 1e-10) {
                solid.material = shape->material;
                field = solid;
            }
        }
    }
    if (field.material && (!voxel.material || field.distance <= voxel.distance + 1e-8)) {
        double x = fabs(field.normal[0]), y = fabs(field.normal[1]), z = fabs(field.normal[2]);
        field.tied = y > x ? (z > y ? 2 : 1) : (z > x ? 2 : 0);
        *out = field;
    } else if (voxel.material) {
        *out = voxel;
    } else if (!(record->voxel || record->field || record->solid)) {
        out->tied = 0; /* Miss. An invalid candidate keeps -1 for CPU fallback. */
    }
}

EXPORT void monolith_gpu_refine(const GPUScene *scene, const GPURecord *records, Hit *output,
                                const double *columns, const double *rows, uint32_t width, uint32_t height,
                                double ox, double oy, double oz, double cy, double sy, double cp, double sp) {
    Trace ray = {0};
    ray.planes = scene->planes;
    ray.origin[0] = ox;
    ray.origin[1] = oy;
    ray.origin[2] = oz;
    ray.limit = 48;
    for (uint32_t y = 0; y < height; ++y) {
        double v = rows[y], forward = cp - v * sp;
        double base_x = cy * forward, base_y = sy * forward, dz = sp + v * cp;
        ray.direction[2] = dz;
        ray.parallel[2] = fabs(dz) < 1e-12;
        for (uint32_t x = 0; x < width; ++x, ++records, ++output) {
            *output = (Hit) {0};
            output->tied = -1;
            double dx = base_x + columns[x] * sy, dy = base_y - columns[x] * cy;
            ray.direction[0] = dx;
            ray.direction[1] = dy;
            ray.parallel[0] = fabs(dx) < 1e-12;
            ray.parallel[1] = fabs(dy) < 1e-12;
            gpu_refine_record(scene, &ray, records, output);
        }
    }
}

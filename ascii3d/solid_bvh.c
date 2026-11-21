#include <math.h>
#include <stddef.h>
#include <stdint.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

typedef struct {
    double low[3], high[3];
} Bounds;

typedef struct {
    Bounds bounds;
    int32_t left, right, first, count;
} Node;

typedef struct {
    Bounds bounds;
    int32_t material, first_plane, plane_count;
} Shape;

typedef struct {
    double normal[3], offset;
} Plane;

typedef struct {
    double distance, normal[3];
    int32_t material, tied;
} Hit;

typedef struct {
    const Node *nodes;
    const Shape *shapes;
    const Plane *planes;
    double origin[3], direction[3];
    int parallel[3];
    double limit;
    int found;
    Hit *hit;
} Trace;

/* Use divisions and X/Y/Z order to match SolidBox._ray_query exactly. */
static int slab(const Bounds *bounds, const Trace *ray, double *entry, double *normal) {
    double enter = 0.0, leave = ray->limit;
    int axis = 2;
    double sign = 1.0;
    for (int i = 0; i < 3; ++i) {
        double origin = ray->origin[i];
        if (ray->parallel[i]) {
            if (origin < bounds->low[i] || origin > bounds->high[i])
                return 0;
        } else {
            double a = (bounds->low[i] - origin) / ray->direction[i];
            double b = (bounds->high[i] - origin) / ray->direction[i];
            double face = -1.0;
            if (a > b) {
                double previous = a;
                a = b;
                b = previous;
                face = 1.0;
            }
            if (a > enter) {
                enter = a;
                axis = i;
                sign = face;
            }
            if (b < leave)
                leave = b;
            if (enter > leave + 1e-10)
                return 0;
        }
    }
    if (leave < 0.0)
        return 0;
    *entry = enter;
    if (normal) {
        normal[0] = normal[1] = normal[2] = 0.0;
        normal[axis] = sign;
    }
    return 1;
}

static int convex(const Shape *shape, const Trace *ray, double *entry, double *normal) {
    double enter = 0.0, leave = ray->limit;
    const Plane *planes = ray->planes + shape->first_plane;
    const Plane *front = 0;
    for (int32_t i = 0; i < shape->plane_count; ++i) {
        const Plane *plane = &planes[i];
        double nx = plane->normal[0], ny = plane->normal[1], nz = plane->normal[2];
        double numerator = plane->offset - (nx * ray->origin[0] + ny * ray->origin[1] + nz * ray->origin[2]);
        double denominator = nx * ray->direction[0] + ny * ray->direction[1] + nz * ray->direction[2];
        if (fabs(denominator) < 1e-12) {
            if (numerator < -1e-10)
                return 0;
            continue;
        }
        double t = numerator / denominator;
        if (denominator < 0.0) {
            if (t > enter) {
                enter = t;
                front = plane;
            }
        } else if (t < leave) {
            leave = t;
        }
        if (enter > leave + 1e-10)
            return 0;
    }
    if (leave < 0.0)
        return 0;
    *entry = enter;
    normal[0] = front ? front->normal[0] : 0.0;
    normal[1] = front ? front->normal[1] : 0.0;
    normal[2] = front ? front->normal[2] : 1.0;
    return 1;
}

/* The prepared Python tree is balanced, bounding recursion to its height. */
static void traverse(Trace *ray, int32_t index, double entry) {
    if (entry > ray->limit + 1e-10)
        return;
    const Node *node = &ray->nodes[index];
    if (node->count) {
        for (int32_t i = 0; i < node->count; ++i) {
            const Shape *shape = &ray->shapes[node->first + i];
            double distance, normal[3];
            int hit = shape->plane_count ? convex(shape, ray, &distance, normal)
                                          : slab(&shape->bounds, ray, &distance, normal);
            if (!hit)
                continue;
            if (ray->found && fabs(distance - ray->hit->distance) <= 1e-8)
                ray->hit->tied = 1;
            ray->found = 1;
            ray->limit = ray->hit->distance = distance;
            ray->hit->material = shape->material;
            ray->hit->normal[0] = normal[0];
            ray->hit->normal[1] = normal[1];
            ray->hit->normal[2] = normal[2];
        }
        return;
    }

    double left_entry = 0.0, right_entry = 0.0;
    int left = slab(&ray->nodes[node->left].bounds, ray, &left_entry, 0);
    int right = slab(&ray->nodes[node->right].bounds, ray, &right_entry, 0);
    if (left && (!right || left_entry <= right_entry)) {
        traverse(ray, node->left, left_entry);
        if (right)
            traverse(ray, node->right, right_entry);
    } else if (right) {
        traverse(ray, node->right, right_entry);
        if (left)
            traverse(ray, node->left, left_entry);
    }
}

EXPORT int monolith_solid_abi(void) {
    return 1;
}

EXPORT int monolith_solid_hit(const Node *nodes, const Shape *shapes, const Plane *planes,
                              double ox, double oy, double oz, double dx, double dy, double dz,
                              double limit, double entry, Hit *hit) {
    Trace ray = {nodes, shapes, planes, {ox, oy, oz}, {dx, dy, dz},
                 {fabs(dx) < 1e-12, fabs(dy) < 1e-12, fabs(dz) < 1e-12}, limit, 0, hit};
    hit->tied = 0;
    traverse(&ray, 0, entry);
    return ray.found;
}

typedef struct {
    double high, slope_x, slope_y, upper;
} HeightChunk;

typedef struct {
    const double *heights;
    const uint8_t *enabled, *materials;
    const HeightChunk *chunks;
    int32_t width, depth, chunk_columns, chunk_rows, chunk_size;
    double maximum;
} HeightFieldData;

typedef struct {
    double ox, oy, oz, dx, dy, dz, margin;
} HeightRay;

typedef struct {
    int64_t x, y;
    int step_x, step_y;
    double next_x, next_y, delta_x, delta_y;
} HeightGrid;

/* Reproduce grid_intervals' initial offset, including sub-threshold rays. */
static int grid_start(HeightGrid *grid, const HeightRay *ray, double start, int size) {
    double x = floor((ray->ox + ray->dx * (start + 1e-9)) / size);
    double y = floor((ray->oy + ray->dy * (start + 1e-9)) / size);
    if (!(x >= INT32_MIN && x <= INT32_MAX && y >= INT32_MIN && y <= INT32_MAX))
        return 0;
    grid->x = (int64_t) x;
    grid->y = (int64_t) y;
    grid->step_x = ray->dx >= 0.0 ? 1 : -1;
    grid->step_y = ray->dy >= 0.0 ? 1 : -1;
    grid->next_x = grid->next_y = grid->delta_x = grid->delta_y = INFINITY;
    if (fabs(ray->dx) > 1e-12) {
        grid->next_x = ((grid->x + (grid->step_x > 0)) * size - ray->ox) / ray->dx;
        grid->delta_x = fabs(size / ray->dx);
    }
    if (fabs(ray->dy) > 1e-12) {
        grid->next_y = ((grid->y + (grid->step_y > 0)) * size - ray->oy) / ray->dy;
        grid->delta_y = fabs(size / ray->dy);
    }
    return 1;
}

static double grid_end(const HeightGrid *grid, double limit) {
    double end = grid->next_x < grid->next_y ? grid->next_x : grid->next_y;
    return limit < end ? limit : end;
}

static void grid_advance(HeightGrid *grid, double end) {
    double crossing = end + 1e-10;
    if (grid->next_x <= crossing) {
        grid->x += grid->step_x;
        grid->next_x += grid->delta_x;
    }
    if (grid->next_y <= crossing) {
        grid->y += grid->step_y;
        grid->next_y += grid->delta_y;
    }
}

static int height_clip(double origin, double direction, int high, double *start, double *end) {
    if (fabs(direction) < 1e-12)
        return 0.0 <= origin && origin < high;
    double a = -origin / direction;
    double b = (high - origin) / direction;
    double enter = a < b ? a : b;
    double leave = a > b ? a : b;
    if (enter > *start)
        *start = enter;
    if (leave < *end)
        *end = leave;
    return 1;
}

static int height_cell(const HeightFieldData *field, const HeightRay *ray, int64_t x, int64_t y,
                       double left, double right, Hit *hit) {
    size_t index = (size_t) y * field->width + (size_t) x;
    if (!field->enabled[index])
        return 0;
    size_t stride = (size_t) field->width + 1;
    const double *heights = field->heights + (size_t) y * stride + (size_t) x;
    double h00 = heights[0], h10 = heights[1], h01 = heights[stride], h11 = heights[stride + 1];
    double high = h00 > h10 ? h00 : h10;
    if (h01 > high)
        high = h01;
    if (h11 > high)
        high = h11;
    if (ray->oz + ray->dz * (ray->dz < 0.0 ? right : left) > high + ray->margin)
        return 0;

    double a[2] = {h10 - h00, h11 - h01};
    double b[2] = {h11 - h10, h01 - h00};
    double u = ray->ox + ray->dx * left - x;
    double v = ray->oy + ray->dy * left - y;
    int second = v > u;
    if (ray->oz + ray->dz * left < h00 + a[second] * u + b[second] * v - 1e-7) {
        hit->distance = left > 0.0 ? left : 0.0;
        hit->normal[0] = hit->normal[1] = 0.0;
        hit->normal[2] = 1.0;
        hit->material = field->materials[index];
        return 1;
    }

    /* A coincident crossing retains the first triangle, as in HeightField. */
    double nearest = INFINITY;
    int triangle = 0;
    for (second = 0; second <= 1; ++second) {
        double denominator = ray->dz - a[second] * ray->dx - b[second] * ray->dy;
        if (denominator >= -1e-12)
            continue;
        double numerator = h00 + a[second] * (ray->ox - x) + b[second] * (ray->oy - y) - ray->oz;
        double t = numerator / denominator;
        if (left - 1e-8 <= t && t <= right + 1e-8 && t >= -1e-8) {
            u = ray->ox + ray->dx * t - x;
            v = ray->oy + ray->dy * t - y;
            double distance = t > 0.0 ? t : 0.0;
            if ((second ? (v >= u - 1e-8) : (v <= u + 1e-8)) && distance < nearest) {
                nearest = distance;
                triangle = second;
            }
        }
    }
    if (nearest == INFINITY)
        return 0;
    double nx = a[triangle], ny = b[triangle];
    double length = sqrt(nx * nx + ny * ny + 1.0);
    hit->distance = nearest;
    hit->normal[0] = -nx / length;
    hit->normal[1] = -ny / length;
    hit->normal[2] = 1.0 / length;
    hit->material = field->materials[index];
    return 1;
}

static int height_chunk(const HeightFieldData *field, const HeightRay *ray, const HeightGrid *chunk,
                        double start, double end, Hit *hit) {
    if (chunk->x < 0 || chunk->x >= field->chunk_columns || chunk->y < 0 || chunk->y >= field->chunk_rows)
        return 0;
    size_t index = (size_t) chunk->y * field->chunk_columns + (size_t) chunk->x;
    const HeightChunk *bounds = &field->chunks[index];
    if (bounds->high == -INFINITY || ray->oz + ray->dz * (ray->dz < 0.0 ? end : start) > bounds->high + ray->margin)
        return 0;

    /* Keep the endpoint halo of the exact fine traversal after both clips. */
    const double halo = 1.1e-8;
    if (ray->dz < -1e-12) {
        double crossing = (bounds->high + ray->margin - ray->oz) / ray->dz - halo;
        if (crossing > start)
            start = crossing;
    } else if (ray->dz > 1e-12) {
        double crossing = (bounds->high + ray->margin - ray->oz) / ray->dz + halo;
        if (crossing < end)
            end = crossing;
    }
    if (start > end)
        return 0;
    double local_x = ray->ox - chunk->x * field->chunk_size;
    double local_y = ray->oy - chunk->y * field->chunk_size;
    double clearance = ray->oz - bounds->upper - bounds->slope_x * local_x - bounds->slope_y * local_y;
    double rate = ray->dz - bounds->slope_x * ray->dx - bounds->slope_y * ray->dy;
    if (clearance + rate * (rate < 0.0 ? end : start) > ray->margin)
        return 0;
    if (rate < -1e-12) {
        double crossing = (ray->margin - clearance) / rate - halo;
        if (crossing > start)
            start = crossing;
    } else if (rate > 1e-12) {
        double crossing = (ray->margin - clearance) / rate + halo;
        if (crossing < end)
            end = crossing;
    }
    if (start > end)
        return 0;

    HeightGrid cell;
    if (!grid_start(&cell, ray, start, 1))
        return -1;
    while (start <= end + 1e-9) {
        double right = grid_end(&cell, end);
        if (0 <= cell.x && cell.x < field->width && 0 <= cell.y && cell.y < field->depth
                && height_cell(field, ray, cell.x, cell.y, start, right, hit))
            return 1;
        if (right >= end)
            break;
        grid_advance(&cell, right);
        start = right;
    }
    return 0;
}

/* Returns -1 when original Python tracing is needed for an unusual input. */
EXPORT int monolith_heightfield_hit(const HeightFieldData *field, double ox, double oy, double oz,
                                    double dx, double dy, double dz, double limit, double minimum, Hit *hit) {
    if (!isfinite(ox) || !isfinite(oy) || !isfinite(oz) || !isfinite(dx) || !isfinite(dy)
            || !isfinite(dz) || !isfinite(limit) || !isfinite(minimum))
        return -1;
    double far_z = oz + dz * limit;
    if ((far_z < oz ? far_z : oz) > field->maximum + 1e-7)
        return 0;
    double start = minimum, end = limit;
    if (!height_clip(ox, dx, field->width, &start, &end) || !height_clip(oy, dy, field->depth, &start, &end)
            || start > end || end < 0.0)
        return 0;
    double rate_bound = fabs(dz) + field->maximum * (fabs(dx) + fabs(dy));
    double margin = 1e-7 + 1e-8 * rate_bound
        + 1e-12 * (1.0 + fabs(oz) + field->maximum * (33.0 + fabs(ox) + field->width + fabs(oy) + field->depth)
                   + rate_bound * fabs(limit));
    if (!isfinite(margin))
        return -1;
    HeightRay ray = {ox, oy, oz, dx, dy, dz, margin};
    HeightGrid chunk;
    if (!grid_start(&chunk, &ray, start, field->chunk_size))
        return -1;
    while (start <= end + 1e-9) {
        double right = grid_end(&chunk, end);
        int result = height_chunk(field, &ray, &chunk, start, right, hit);
        if (result)
            return result;
        if (right >= end)
            break;
        grid_advance(&chunk, right);
        start = right;
    }
    return 0;
}

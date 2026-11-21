#include <math.h>
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

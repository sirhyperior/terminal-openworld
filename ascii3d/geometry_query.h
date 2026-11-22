/* The view bounds enclose the already selected ground and solid geometry. */
typedef struct {
    const Bounds *ground_bounds, *solid_bounds;
    const Node *nodes;
    const Shape *shapes;
    const Plane *planes;
} GeometryQuery;

typedef struct {
    Hit hit;
    double solid_entry;
} GeometryResult;

/* Bit 0 marks an available hit. Bit 1 requests the original solid grid order. */
EXPORT int monolith_geometry_hit(const GeometryQuery *geometry, const HeightFieldData *field,
                                double ox, double oy, double oz, double dx, double dy, double dz,
                                double limit, GeometryResult *result) {
    if (!isfinite(ox) || !isfinite(oy) || !isfinite(oz) || !isfinite(dx) || !isfinite(dy)
            || !isfinite(dz) || !isfinite(limit))
        return -1;

    Trace ray = {geometry->nodes, geometry->shapes, geometry->planes, {ox, oy, oz}, {dx, dy, dz},
                 {fabs(dx) < 1e-12, fabs(dy) < 1e-12, fabs(dz) < 1e-12}, limit, 0, NULL};
    int found = 0;
    double entry;
    const Bounds *ground = geometry->ground_bounds;
    if (ground && fmin(oz, oz + dz * limit) <= ground->high[2] + 1e-7
            && slab(ground, &ray, &entry, NULL)) {
        found = monolith_heightfield_hit(field, ox, oy, oz, dx, dy, dz, limit, entry, &result->hit);
        if (found < 0)
            return -1;
        if (found)
            ray.limit = result->hit.distance;
    }

    const Bounds *solids = geometry->solid_bounds;
    double end_z = oz + dz * ray.limit;
    if (solids && fmin(oz, end_z) <= solids->high[2] + 1e-7
            && fmax(oz, end_z) >= solids->low[2] - 1e-7
            && slab(solids, &ray, &entry, NULL)) {
        if (geometry->nodes) {
            Hit solid = {0};
            ray.hit = &solid;
            traverse(&ray, 0, entry);
            if (!solid.tied) {
                if (ray.found)
                    result->hit = solid;
                return found || ray.found;
            }
        }
        result->solid_entry = entry;
        return found | 2;
    }
    return found;
}

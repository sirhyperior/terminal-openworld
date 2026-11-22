/* Shade the already resolved GPU hits without visiting them again in Python.
   Flag ambiguous hits, ordered water effects and local light samples for Python. */
static const uint32_t SCENE_PANEL = UINT32_MAX - 1;

typedef struct {
    const double *segments;
    const uint32_t *offsets, *indices;
    int x0, y0, width, height;
    double bucket_size, radius_squared;
} SceneRoads;

static int scene_road_contains(const SceneRoads *roads, double x, double y) {
    if (!roads->width)
        return 0;
    double cx = floor(x / roads->bucket_size) - roads->x0;
    double cy = floor(y / roads->bucket_size) - roads->y0;
    if (!(0 <= cx && cx < roads->width && 0 <= cy && cy < roads->height))
        return 0;
    size_t bucket = (size_t)cy * roads->width + (int)cx;
    for (uint32_t i = roads->offsets[bucket]; i < roads->offsets[bucket + 1]; ++i) {
        const double *segment = roads->segments + 5 * roads->indices[i];
        double px = x - segment[0], py = y - segment[1];
        double along = (px * segment[2] + py * segment[3]) * segment[4];
        along = !(along < 1) ? 1 : (along > 0 ? along : 0);
        double offset_x = px - along * segment[2], offset_y = py - along * segment[3];
        if (offset_x * offset_x + offset_y * offset_y <= roads->radius_squared)
            return 1;
    }
    return 0;
}

typedef struct {
    double x, y, radius, strength, dx, dy;
} SceneGust;

static double scene_wind_turn(double x, double y, double seconds, const SceneGust *gusts, int count) {
    /* Scenery.wind_at samples at the center of the truncated world cell. */
    x = trunc(x) + 0.5;
    y = trunc(y) + 0.5;
    double dx = 0.16 + 0.32 * sin(x * 0.55 + y * 0.37 - seconds * 2.9);
    double dy = 0.22 * sin(y * 0.49 - x * 0.28 - seconds * 2.3);
    for (int i = 0; i < count; ++i) {
        const SceneGust *gust = &gusts[i];
        double gx = x - gust->x, gy = y - gust->y;
        double falloff = 1.0 - (gx * gx + gy * gy) / (gust->radius * gust->radius);
        if (falloff > 0) {
            double force = falloff * falloff * gust->strength;
            dx += force * gust->dx;
            dy += force * gust->dy;
        }
    }
    return dx + dy * 0.6;
}

static int scene_near_light(const ShadeSample *sample, const double *lights, int count,
                           double radius_squared) {
    for (int i = 0; i < count; ++i, lights += 3) {
        double x = lights[0] - sample->x, y = lights[1] - sample->y, z = lights[2] - sample->z;
        if (x * x + y * y + z * z <= radius_squared && sample->nx * x + sample->ny * y + sample->nz * z >= 0)
            return 1;
    }
    return 0;
}

static uint32_t shade_gpu_frame(const Hit *hits, const double *columns, const double *rows,
                                uint32_t width, uint32_t height, double cy, double sy,
                                double cp, double sp, const SurfaceLighting *lighting,
                                const SceneRoads *roads, const SceneGust *gusts, int gust_count,
                                int wind, double seconds, const double *panels, const double *combat,
                                uint32_t *tokens, double *depths, uint32_t *special,
                                const double *lights, int light_count, double radius_squared) {
    uint32_t index = 0, count = 0;
    for (uint32_t y = 0; y < height; ++y) {
        double v = rows[y], forward = cp - v * sp;
        double base_x = cy * forward, base_y = sy * forward, dz = sp + v * cp;
        for (uint32_t x = 0; x < width; ++x, ++index) {
            const Hit *hit = &hits[index];
            double panel = panels ? panels[index] : INFINITY;
            double limit = fmin(panel, 48);
            if (combat && combat[index] < limit)
                limit = combat[index];
            double distance = hit->distance;
            int material = hit->material;
            uint32_t token = UINT32_MAX;
            double depth = panel;
            if (hit->tied >= 0 && (!material || fabs(distance - limit) > 1e-7)) {
                if (!material || distance > limit) {
                    token = isfinite(panel) ? SCENE_PANEL : 0;
                } else if (material != SHADE_WATER && 0 <= material && material <= 255) {
                    double dx = base_x + columns[x] * sy, dy = base_y - columns[x] * cy;
                    double sample_distance = distance + 1e-8;
                    ShadeSample sample = {lighting->ex + dx * sample_distance,
                                          lighting->ey + dy * sample_distance,
                                          lighting->ez + dz * sample_distance,
                                          hit->normal[0], hit->normal[1], hit->normal[2],
                                          distance, material, 0.0};
                    switch (hit->tied) {
                    case 4: sample.nx = dx >= 0 ? -1.0 : 1.0; break;
                    case 5: sample.ny = dy >= 0 ? -1.0 : 1.0; break;
                    case 6: sample.nz = dz >= 0 ? -1.0 : 1.0; break;
                    }
                    /* Keep LOS and its sample budget in the original row order.
                       The native shader only sees points that cannot be lit. */
                    if (!scene_near_light(&sample, lights, light_count, radius_squared)) {
                        if (material == SHADE_GRASS && sample.nz > 0) {
                            if (scene_road_contains(roads, sample.x, sample.y))
                                sample.material = SHADE_PATH;
                            else if (wind)
                                sample.foliage_turn = scene_wind_turn(sample.x, sample.y, seconds,
                                                                     gusts, gust_count);
                        }
                        token = shade_surface(&sample, lighting);
                        depth = distance;
                    }
                }
            }
            tokens[index] = token;
            depths[index] = depth;
            if (token >= SCENE_PANEL)
                special[count++] = index;
        }
    }
    return count;
}

EXPORT uint32_t monolith_shade_gpu_frame(const Hit *hits, const double *columns, const double *rows,
                                       uint32_t width, uint32_t height, double cy, double sy,
                                       double cp, double sp, const SurfaceLighting *lighting,
                                       const SceneRoads *roads, const SceneGust *gusts, int gust_count,
                                       int wind, double seconds, const double *panels, const double *combat,
                                       uint32_t *tokens, double *depths, uint32_t *special) {
    return shade_gpu_frame(hits, columns, rows, width, height, cy, sy, cp, sp, lighting, roads, gusts,
                           gust_count, wind, seconds, panels, combat, tokens, depths, special, NULL, 0, 0);
}

EXPORT uint32_t monolith_shade_gpu_frame_firelight(
        const Hit *hits, const double *columns, const double *rows, uint32_t width, uint32_t height,
        double cy, double sy, double cp, double sp, const SurfaceLighting *lighting, const SceneRoads *roads,
        const SceneGust *gusts, int gust_count, int wind, double seconds, const double *panels,
        const double *combat, uint32_t *tokens, double *depths, uint32_t *special,
        const double *lights, int light_count, double radius_squared) {
    return shade_gpu_frame(hits, columns, rows, width, height, cy, sy, cp, sp, lighting, roads, gusts,
                           gust_count, wind, seconds, panels, combat, tokens, depths, special,
                           lights, light_count, radius_squared);
}

/* Batched no-firelight path for Shading.surface's default scene samples.
   Material IDs mirror palette.py and are checked by the Python wrapper. */
enum {
    SHADE_STONE = 1, SHADE_FLOOR, SHADE_METAL, SHADE_CRATE, SHADE_GRASS,
    SHADE_WATER, SHADE_WOOD, SHADE_LEAVES, SHADE_PATH, SHADE_BRIDGE,
    SHADE_FIRE, SHADE_EMBER, SHADE_ARCANE, SHADE_STRAW, SHADE_BONE,
    SHADE_WIND_GRASS = 22
};

typedef struct {
    double x, y, z, nx, ny, nz, distance, material, foliage_turn;
} ShadeSample;

/* Python's positive divisor gives negative coordinates a positive phase. */
static double shade_phase(double value) {
    double phase = value - trunc(value);
    return phase < 0 ? phase + 1.0 : phase;
}

/* Match the shared Python texture sampling at the same world-space hit. */
static double shade_cobble_texture(const ShadeSample *sample, const uint8_t *tile,
                                  int size, double scale, double fade, double distant_tone) {
    double distance = sample->distance;
    if (distance >= fade)
        return distant_tone;
    double x = sample->x * scale, y = sample->y * scale;
    int64_t ix = (int64_t)floor(x), iy = (int64_t)floor(y);
    double u = x - ix, v = y - iy;
    /* The shared texture side is a power of two. */
    uint64_t mask = size - 1;
    uint64_t x0 = (uint64_t)ix & mask, x1 = (uint64_t)(ix + 1) & mask;
    uint64_t y0 = ((uint64_t)iy & mask) * size, y1 = ((uint64_t)(iy + 1) & mask) * size;
    double a = tile[y0 + x0], b = tile[y1 + x0];
    double top = a + (tile[y0 + x1] - a) * u;
    double bottom = b + (tile[y1 + x1] - b) * u;
    double stone = (top + (bottom - top) * v) / 255.0;
    double detail = fmin(1.0, (fade - distance) * 0.10);
    return distant_tone + (stone - distant_tone) * detail;
}

static double shade_texture(const ShadeSample *sample, int material, int *pigment) {
    double x = sample->x, y = sample->y, z = sample->z;
    double a, b;
    double ax = fabs(sample->nx), ay = fabs(sample->ny), az = fabs(sample->nz);
    if (ax > ay && ax > az) {
        a = y; b = z;
    } else {
        a = x; b = ay > az ? z : y;
    }
    double broad = sin(x * 0.83 + y * 0.57 + z * 0.39);
    if (material == SHADE_WOOD || material == SHADE_BRIDGE || material == SHADE_CRATE) {
        double fiber = sin(a * 17.0 + sin(b * 0.93) * 0.45);
        double texture = 0.78 + broad * 0.26;
        if (fiber > 0.87)
            texture *= 0.28;
        else if (fiber < -0.93)
            texture += 0.15;
        if (shade_phase(b * 0.48) < 0.025)
            texture *= 0.48;
        if (material == SHADE_CRATE) {
            double u = shade_phase(a), v = shade_phase(b);
            if (u < 0.075 || 1 - u < 0.075 || v < 0.075 || 1 - v < 0.075
                    || fabs(u - v) < 0.045)
                texture += 0.35;
        }
        return texture;
    }
    if (material == SHADE_STRAW) {
        double strand = sin(a * 23 + b * 1.7);
        double texture = 0.77 + broad * 0.22 + strand * 0.16;
        return strand > 0.92 ? texture * 0.40 : texture;
    }
    int grain = 0;
    if (material == SHADE_STONE || material == SHADE_FLOOR || material == SHADE_GRASS
            || material == SHADE_LEAVES) {
        uint64_t ix = (int64_t)(x * 11), iy = (int64_t)(y * 11), iz = (int64_t)(z * 11);
        grain = (ix * 37 ^ iy * 19 ^ iz * 7) & 15;
    }
    double fine = sin(x * 5.31 - y * 3.17 + z * 7.07);
    switch (material) {
    case SHADE_STONE:
    case SHADE_FLOOR: {
        double joint, seam;
        if (material == SHADE_FLOOR) {
            joint = shade_phase(a * 0.50);
            seam = shade_phase(b * 0.50);
        } else {
            double course = b * 0.85 + sin(a * 0.41) * 0.045;
            joint = shade_phase(a * 0.70 + ((int64_t)course & 1) * 0.50);
            seam = shade_phase(course);
        }
        double texture = 0.78 + broad * 0.31 + fine * 0.13;
        if (seam < 0.04 || joint < 0.026)
            texture *= 0.24;
        else if (seam > 0.955 || joint > 0.965)
            texture += 0.24;
        return grain == 0 ? texture * 0.55 : texture;
    }
    case SHADE_GRASS:
    case SHADE_LEAVES: {
        double texture = 0.80 + broad * 0.24 + fine * 0.10 + grain * 0.008;
        if (material == SHADE_GRASS && sample->nz > 0) {
            double exposure = sample->foliage_turn + broad * 0.17
                - sample->nx * 0.19 + sample->nz * 0.16 - 0.47;
            double lift = exposure * 0.38;
            texture += lift < -0.08 ? -0.08 : lift > 0.22 ? 0.22 : lift;
            if (exposure > 0)
                *pigment = SHADE_WIND_GRASS;
        }
        return texture;
    }
    case SHADE_BONE: {
        double texture = 0.85 + broad * 0.13 + fine * 0.08;
        return fabs(sin(a * 9 + b * 5)) < 0.045 ? texture * 0.42 : texture;
    }
    case SHADE_METAL: {
        double texture = 0.89 + fine * 0.10;
        return shade_phase(a * 13 + b * 0.11) < 0.035 ? texture * 0.46 : texture;
    }
    default:
        return 0.78 + broad * 0.27 + fine * 0.11;
    }
}

static int shade_moon_blocked(const ShadeSample *sample, const uint32_t *moon, int span, int depth) {
    double x = sample->x + sample->nx * 1e-5;
    double y = sample->y + sample->ny * 1e-5;
    double z = sample->z + sample->nz * 1e-5;
    double diagonal = x + z;
    if (!(0 <= y && y < depth && 0 <= diagonal && diagonal < span))
        return 0;
    int band = (int)diagonal;
    uint32_t face = moon[(size_t)(int)y * span + band];
    return x > (face >> 1) + (face & 1 ? diagonal - band : 0) + 1e-6;
}

static double shade_specular(const ShadeSample *sample, int material, double ex, double ey, double ez) {
    double vx = ex - sample->x, vy = ey - sample->y, vz = ez - sample->z;
    double length = sqrt(vx * vx + vy * vy + vz * vz);
    if (length <= 1e-10)
        return 0.0;
    double hx = vx / length - 0.38, hy = vy / length - 0.48, hz = vz / length + 0.79;
    double half_length = sqrt(hx * hx + hy * hy + hz * hz);
    if (half_length <= 1e-10)
        return 0.0;
    double specular = (sample->nx * hx + sample->ny * hy + sample->nz * hz) / half_length;
    return pow(specular > 0 ? specular : 0.0, material == SHADE_METAL ? 24 : 40) * 0.72;
}

typedef struct {
    const uint32_t *moon;
    int span, depth;
    double ex, ey, ez;
    int ramp_max;
    const double *albedos;
    int albedo_count;
    const uint8_t *paving;
    int paving_size;
    double paving_scale, paving_fade, paving_distant_tone;
} SurfaceLighting;

/* Return packed glyph, level and fog indices. Moving textures and local
   light visibility still use the shared Python renderer. */
static uint32_t shade_surface(const ShadeSample *sample, const SurfaceLighting *lighting) {
    if (!(fabs(sample->x) <= 1e9 && fabs(sample->y) <= 1e9 && fabs(sample->z) <= 1e9
            && fabs(sample->foliage_turn) <= 1e9
            && fabs(sample->nx) <= 2 && fabs(sample->ny) <= 2 && fabs(sample->nz) <= 2)) {
        return UINT32_MAX;
    }
    int material = (int)sample->material;
    double distance = sample->distance;
    double directional = -sample->nx * 0.38 - sample->ny * 0.48 + sample->nz * 0.79;
    if (!(directional > 0.0))
        directional = 0.0;
    int emissive = material == SHADE_FIRE || material == SHADE_EMBER || material == SHADE_ARCANE;
    double light = emissive ? 0.10 + directional * 0.90 : 0.30 + directional * 0.70;
    if (material == SHADE_METAL || material == SHADE_WATER)
        light += shade_specular(sample, material, lighting->ex, lighting->ey, lighting->ez);
    if (lighting->moon && !emissive && shade_moon_blocked(sample, lighting->moon, lighting->span, lighting->depth))
        light = 0.24 + (light - 0.24) * 0.42;
    double albedo = 0 <= material && material < lighting->albedo_count ? lighting->albedos[material] : 0.65;
    int pigment = material;
    double texture = material == SHADE_PATH
        ? shade_cobble_texture(sample, lighting->paving, lighting->paving_size,
                               lighting->paving_scale, lighting->paving_fade, lighting->paving_distant_tone)
        : shade_texture(sample, material, &pigment);
    texture = texture > 0.08 ? texture : 0.08;
    double brightness = albedo * texture * light * 1.52 / (1 + (distance > 0 ? distance : 0) * 0.036);
    brightness = brightness > 0.0 ? brightness : 0.0;
    if (!(brightness < 1.0))
        brightness = 1.0;
    if (!emissive)
        brightness = 0.24 + brightness * 0.76;
    uint32_t level = (uint32_t)(brightness * 15 + 0.5);
    if (level == 0)
        level = 1;
    uint32_t glyph = (uint32_t)(brightness * lighting->ramp_max);
    if (material == SHADE_GRASS && sample->nz > 0) {
        uint64_t ix = (int64_t)(sample->x * 6.0), iy = (int64_t)(sample->y * 6.0);
        uint32_t noise = (ix * 73856093 ^ iy * 19349663) & 15;
        uint32_t wind = (int64_t)((sample->foliage_turn + 0.6) * 3);
        uint32_t band = level / 3;
        glyph = lighting->ramp_max + 1 + 2 * (band > 3 ? 3 : band) + ((noise + wind) & 1);
    }
    uint32_t fog = distance < 12 ? 0 : distance < 24 ? 1 : distance < 36 ? 2 : 3;
    return ((uint32_t)pigment << 16) | (fog << 12) | (level << 8) | glyph;
}

EXPORT void monolith_shade_paving_batch(const ShadeSample *samples, uint32_t *results, size_t count,
                                       const uint32_t *moon, int span, int depth,
                                       double ex, double ey, double ez, int ramp_max,
                                       const double *albedos, int albedo_count, const uint8_t *paving,
                                       int paving_size, double paving_scale, double paving_fade,
                                       double paving_distant_tone) {
    SurfaceLighting lighting = {moon, span, depth, ex, ey, ez, ramp_max, albedos,
                                albedo_count, paving, paving_size, paving_scale, paving_fade, paving_distant_tone};
    for (size_t i = 0; i < count; ++i)
        results[i] = shade_surface(&samples[i], &lighting);
}

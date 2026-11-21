/* The native viewport walker shares the Python renderer's empty-prism atlas. */
typedef struct {
    int32_t low_x, low_y, high_x, high_y, bottom, ceiling;
} VoxelPrism;

typedef struct {
    const uint8_t *cells;
    const int32_t *tops;
    const uint32_t *bounds, *columns, *rooms;
    const VoxelPrism *prisms;
    int32_t width, depth, height, chunks_x, chunk_count, water;
    double water_level;
} VoxelGrid;

static int voxel_corner(double coordinate) {
    double fraction = coordinate - floor(coordinate);
    return fraction < 1e-7 || fraction > 0.9999999;
}

static void voxel_ray(const VoxelGrid *grid, double px, double py, double pz,
                      double dx, double dy, double dz, double limit, int ceiling,
                      double *hit_depth, uint16_t *hit_face, double *first_empty) {
    const int width = grid->width, depth = grid->depth, height = grid->height;
    const size_t layer = (size_t) width * depth, count = grid->chunk_count;
    int x = (int) px, y = (int) py, z = (int) pz;
    const int sx = dx >= 0.0 ? 1 : -1, sy = dy >= 0.0 ? 1 : -1, sz = dz >= 0.0 ? 1 : -1;
    const double ddx = dx > 1e-12 ? 1.0 / dx : dx < -1e-12 ? -1.0 / dx : 1e30;
    const double ddy = dy > 1e-12 ? 1.0 / dy : dy < -1e-12 ? -1.0 / dy : 1e30;
    const double ddz = dz > 1e-12 ? 1.0 / dz : dz < -1e-12 ? -1.0 / dz : 1e30;
    const double ix = sx * ddx, iy = sy * ddy;
    const uint32_t *bounds = ddx <= ddy ? grid->bounds : grid->columns;
    double side_x = (sx > 0 ? x + 1 - px : px - x) * ddx;
    double side_y = (sy > 0 ? y + 1 - py : py - y) * ddy;
    double side_z = (sz > 0 ? z + 1 - pz : pz - z) * ddz;
    double distance = 0.0;
    int axis = 0, material = 0;
    *first_empty = -INFINITY;
    for (int iteration = 0; iteration < 110; ++iteration) {
        if (sz > 0 && z >= ceiling)
            break;
        size_t chunk = (size_t) (y >> 1) * grid->chunks_x + (x >> 1);
        int top = grid->tops[chunk];
        uint32_t room = z < top ? grid->rooms[(size_t) z * count + chunk] : 0;
        int skip = z >= top || room;
        const VoxelPrism *prism = NULL;
        if (skip) {
            double end_z;
            if (room) {
                prism = grid->prisms + room;
                end_z = (sz > 0 ? prism->ceiling - pz : pz - prism->bottom) * ddz;
            } else {
                int level = sz < 0 ? top : z;
                prism = grid->prisms + bounds[(size_t) level * count + chunk];
                top = prism->bottom;
                end_z = sz < 0 ? (pz - top) * ddz : 1e30;
            }
            double end_x = ((sx > 0 ? prism->high_x : prism->low_x) - px) * ix;
            double end_y = ((sy > 0 ? prism->high_y : prism->low_y) - py) * iy;
            if (end_x <= end_y && end_x <= end_z) {
                distance = end_x;
                axis = 0;
            } else if (end_y <= end_z) {
                distance = end_y;
                axis = 1;
            } else {
                distance = end_z;
                axis = 2;
            }
            if (sz < 0 && *first_empty == -INFINITY)
                *first_empty = distance;
            if (distance > limit)
                break;
            if (room && ((axis != 0 && ddx < 1e30 && voxel_corner(px + dx * distance))
                         || (axis != 1 && ddy < 1e30 && voxel_corner(py + dy * distance))
                         || (axis != 2 && ddz < 1e30 && voxel_corner(pz + dz * distance))))
                skip = 0;
        }
        if (skip) {
            double advance = distance + 1e-7;
            x = axis == 0 ? (sx > 0 ? prism->high_x : prism->low_x - 1) : (int) floor(px + dx * advance);
            y = axis == 1 ? (sy > 0 ? prism->high_y : prism->low_y - 1) : (int) floor(py + dy * advance);
            if (axis != 2)
                z = (int) floor(pz + dz * advance);
            else if (room)
                z = sz > 0 ? prism->ceiling : prism->bottom - 1;
            else
                z = top - 1;
            if (x < 0 || x >= width || y < 0 || y >= depth || z < 0 || z >= height)
                break;
            material = grid->cells[(size_t) z * layer + (size_t) y * width + x];
            if (material && material != grid->water)
                break;
            side_x = (x + (sx > 0) - px) * ix;
            side_y = (y + (sy > 0) - py) * iy;
            side_z = (z + (sz > 0) - pz) * sz * ddz;
        } else if (side_x <= side_y && side_x <= side_z) {
            distance = side_x;
            side_x += ddx;
            x += sx;
            axis = 0;
        } else if (side_y <= side_z) {
            distance = side_y;
            side_y += ddy;
            y += sy;
            axis = 1;
        } else {
            distance = side_z;
            side_z += ddz;
            z += sz;
            axis = 2;
        }
        if (distance > limit || x < 0 || x >= width || y < 0 || y >= depth || z < 0 || z >= height)
            break;
        material = grid->cells[(size_t) z * layer + (size_t) y * width + x];
        if (material == grid->water) {
            double surface = dz < -1e-12 ? (grid->water_level - pz) / dz : -1.0;
            double leave = fmin(fmin(side_x, side_y), side_z);
            if (distance - 1e-8 <= surface && surface <= leave + 1e-8) {
                distance = surface;
                axis = 2;
            } else {
                material = 0;
            }
        }
        if (material)
            break;
    }
    *hit_depth = distance;
    *hit_face = (uint16_t) ((material << 2) | axis);
}

EXPORT void monolith_voxel_frame(const VoxelGrid *grid, double px, double py, double pz,
                                double cy, double sy, double cp, double sp, int ceiling,
                                int width, int height, const double *columns, const double *rows,
                                const double *panels, const double *combat, double *hit_depths,
                                uint16_t *hit_faces, double *first_empty) {
    size_t index = 0;
    for (int y = 0; y < height; ++y) {
        double v = rows[y], forward = cp - v * sp;
        double base_x = cy * forward, base_y = sy * forward, dz = sp + v * cp;
        for (int x = 0; x < width; ++x, ++index) {
            double u = columns[x];
            double limit = panels && panels[index] < 48.0 ? panels[index] : 48.0;
            if (combat && combat[index] < limit)
                limit = combat[index];
            voxel_ray(grid, px, py, pz, base_x + u * sy, base_y - u * cy, dz,
                      limit, ceiling, hit_depths + index, hit_faces + index, first_empty + index);
        }
    }
}

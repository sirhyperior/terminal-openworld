# Smooth hills and fine stairs — work checkpoint, 2026-11-10

**Superseded handoff:** work resumed on 2026-11-11. Read
[current performance checkpoint](smooth-performance-2026-11-11.md) first.
Camera/report repairs and 393 native tests are now completed; the latest
performance result is 12/24 matched passes. The text below retains the earlier
checkpoint history and must not be mistaken for the latest validation state.

The user approved the geometry work after requesting the viewport checkpoint.
That preceding work is committed as **d20cd0d**. The geometry changes described
here remain **uncommitted in the working tree**. Work stopped at the user's
explicit wrap-up request; functional integration has progressed, but final
full validation, visual review and performance acceptance are incomplete.

## Implemented

- `ascii3d/surfaces.py` provides a continuous one-unit vertex grid split into
  exact planar triangles, circular-footprint support maxima, chunk-accelerated
  ray queries, outward normals and configurable fractional solid boxes.
- `World` shares the shapes across cylinder collision, support/material queries,
  sight/projectiles, top surfaces and staircase instances. Terrain retains
  conservative voxel foundations. Constant integer-flat cells fall through to
  identical voxels; neighboring fractional vertices remain continuous.
- Elevation generation uses continuous smooth blends, preserving the flat hub,
  low river valley, supported landmark pads and 1–20 elevation range. Paths
  repaint materials while retaining shape. Trees and every grass root use point
  heights; per-blade checks reject partial analytic floor coverage.
- All **13 flights** (12 highland hall flights plus the west cloister) share
  20 quarter-unit risers / half-unit treads over a ten-unit run for a five-unit
  rise. Hall openings/approaches were repositioned for headroom and access.
- Grounded walking follows slopes and ascending/descending treads. Jumps remain
  airborne; large drops fall; wood/crate/metal rails do not auto-climb. Natural
  grades above 45 degrees block walking independent of tick size or direction.
  Only triangles actually touching the selected support impose that limit.
- Existing semantic `terrain_step`/surface Foley covers discrete tread ascent
  and descent; slopes use distance-based grass/gravel footsteps. No synthesis or
  device code/dependencies changed. Dropped weapons settle their own circular
  footprint on slopes rather than falling back to floating at player height.
- Renderer merges exact analytic depths with voxel, door, water, foliage and
  combat depths; continuous normals shade turf. Conservative sampled-frustum
  selection avoids analytic work for invisible geometry. Indexed boxes retain
  exact corner and parallel-boundary hits through conservative chunk insertion.

The lead owned shared geometry/world, item settlement, integration and docs;
three agents separately owned renderer, movement/Foley, and content/vegetation.
Read-only reviews caught and repaired corner ray misses, unused-triangle slope
rejection, wooden landing descent and grass on partial analytic floor coverage.

## Verified, with limits

An **initial full piped suite ran 359 tests in 209.792 s: 348 passed, 11 skipped**.
The skips are ten native-console cases and the opt-in desktop cursor test.
That run predates the final corner/grade/frustum/flat-cell refinements; do not
describe it as a final suite of the current working tree.

Focused checks on the later code passed:

| Coverage | Passing tests |
| --- | ---: |
| Smooth movement, steep grades, jump/drop, shallow triangle and bridge support | 12 |
| Exact analytic rendering, occlusion, sampled frustum and culled/global equivalence | 11 |
| Existing terrain renderer / room traversal | 8 / 7 |
| Generated continuous ground, flat fallback, roads and west stairs | 4 |
| Elevated vegetation/materials, including partial analytic floors | 10 |
| Shared exact geometry, independent all-triangle rays, circular support, edits, indexed corners | 6 |
| Dropped-item slope footprint | 1 |

Nine terrain tests passed during integration, including all 12 hall flights in
both directions and all four entrance-to-roof walks; west-flight tests verify
ascent/descent too. Existing engine, outdoors, audio milestone and terrain
movement suites passed during integration. Final native-suite/demo/audio-device
checks and visual inspection have **not** been repeated for this checkpoint.

## Failed performance evidence and immediate resume work

[Initial failed benchmark](smooth-interleaved-first-failed.txt) preserves every
printed matched-role comparison: **24/24 fail**, mean increases
199.77–827.37%, p95 increases 186.18–808.37%. The run later aborted on the
misplaced `stair_walk` camera. The JSON/raw samples and audio-health summary were
not written by the existing end-only save path. Do not infer device health or
replace any baseline from that run.

The latest optimizations eliminate redundant flat planes and add conservative
per-frame frustum selection / coarse query bounds. Their correctness has focused
coverage above; **their performance has not been measured**. Preserve the 15%
mean/p95 gate and failed evidence. Earlier expansion/castle acceptance remains
separate and unresolved.

Resume in this order:

1. Read `AGENTS.md`, `PROJECT_STATUS.md`, this file and the current Git diff.
2. Correct `TERRAIN_SCENARIOS["stair_walk"]` from `(140.5,40.5,Z5)` to the
   clear approach `(140.5,41.5,Z5)`; verify every benchmark camera against the
   shared cylinder support/collision geometry. Natural camera Z already uses
   footprint support. This camera repair is **not yet applied**.
3. Make `tools/benchmark_pair.py` persist partial results/failure metadata during
   measurement, so a late camera/device exception cannot discard raw samples.
4. Run the final full suite in a native console; opt into the real cursor test
   when desktop access is available. Inspect hills/ravine, water boundaries,
   indoor floors, stair ascent/descent and roof transitions, then finite live
   demos and sound. Unit success does not replace physical host review.
5. Reconstruct `d20cd0d` as the frozen control and run a fresh **60-frame,
   120x40, live-audio ABBA** comparison serially. Retain all failures; profile
   any remaining costs without reducing range, detail or acceptance thresholds.
6. Update handoff/results and obtain play confirmation before committing the
   new implementation under the repository's commit policy.

Generic editing limit: `World.box()` currently repaints or replaces a whole
unit-XY heightfield cell when an edit intersects its terrain surface range.
It does not support arbitrary partial-Z caves/cuts through a sloped cell.
Current hub/river/building authoring uses flat pads and is covered by tests;
partial-height terrain editing is a documented limitation, not exact voxel-cut
semantics. Direct `HeightField.paint_cell()` increments the field revision;
callers also increment `world.revision` to invalidate scenery/map caches.

## Resume commands

Use unused output paths and run timing work without concurrent tests/previews.
Temporary controls were removed at wrap-up; reconstruct from Git as follows.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
$env:MONOLITH_DESKTOP_TESTS='1' # Native console / desktop access required
python -B -m unittest discover -s tests -v
python -B main.py --snapshot
python -B main.py --region ridge --demo --frames 100
python -B main.py --audio-test
git archive --format=zip --output=smooth-control-tmp.zip d20cd0d ascii3d
Expand-Archive -LiteralPath smooth-control-tmp.zip -DestinationPath smooth_control_tmp
# Repair/check the stair camera and partial-report persistence first.
python -B tools/benchmark_pair.py --before-source smooth_control_tmp --before-elevated-audio --frames 60 --audio --save benchmarks/smooth-interleaved-followup.json
```

Useful visual poses (set natural Z from circular support, not only point height):
Ridge road `(128.5,52.5,yaw0,pitch-0.12)`, hillside
`(200.5,220.5,yaw0.35,pitch-0.22)`, ridge `(320.5,208.5,yaw1.4,pitch-0.15)`,
ravine `(300.5,282.5,yaw0.15,pitch-0.25)`, west stairs
`(35.5,31,Z1,yawpi/2)` and `(35.5,43,Z6,yaw-pi/2)`, Ridge flight
`(140.5,41.5,Z5,yawpi/2)` and `(140.5,53,Z10,yaw-pi/2)`.

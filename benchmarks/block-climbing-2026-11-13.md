# Ordinary blocks require jumping — 2026-11-13

## Context and reproduction

At the user's request, uncommitted color/shading changes and their associated
optimizations/tools were restored through Git to fd56e49. Rollback/rule checkpoint
**a2049c3** records the monochrome restoration and explicit permission to use
subagents. Color is deferred. Prior experiment data is retained only in
`abandoned-color-2026-11-13.zip`; it does not describe this engine.

Two independent subagent investigations reproduced the long-standing block
climbing report. From `(31.5,38.5,Z6)`, facing west (`yaw=pi`), W at 1/120 s
steps onto the west curtain merlon at tick 10, reaching Z7 without jumping.
Equivalent cases affect all four curtain walls, tower merlons and courtyard
masonry. Crates remain blocked because the old fallback whitelisted masonry.

There were two causes:

1. `Player._step_up()` explicitly climbed a full one-unit voxel based on its
   material whenever headroom existed.
2. `_follow_ground()` also accepted arbitrary solid/voxel tops within a half
   unit. Removing the first path alone still let a player on Z1.6 terrain walk
   onto a Z2 voxel, or climb unmarked quarter/half-unit solids.

## Shared repair

- Remove the legacy one-unit fallback and both movement call sites.
- `SolidBox.stair` defaults false; shared `World.add_stair_flight()` marks its
  generated treads. Geometry, placement, rendering and collision shapes do not
  change.
- Player ground following uses `walk_support(..., walking=True)`. Upward walking
  support can come from continuous terrain or authored treads, with existing
  rise, material, grade and headroom limits. Ordinary props still support
  standing, descent and landings after jumping.
- Generic `walk_support()` behavior stays unchanged for dropped-item footprints
  and benchmark camera settling. Filter movement candidates before choosing the
  highest support so a rejected obstacle cannot hide valid lower ground.
- Stair contact Foley recognizes real treads. Existing `terrain_step`, surface
  footsteps, jump and landing cues are retained; blocked ordinary props no
  longer emit false stair events. No new action/cue or dependency is introduced.

The older synthetic test deliberately required five full-voxel auto-steps. Its
fixture is migrated to the shared quarter-unit stair mechanism rather than
preserving the reported behavior to satisfy that outdated test.

## Verification

- `block-climb-native-2026-11-13.txt` / `.json`: **429 native-console tests
  passed**, zero failures/errors, one sandbox desktop-cursor skip. Real GPU and
  native input checks ran. Suite: 178.693 s; native runner exits 0 and confirms
  engine source hashes stayed unchanged throughout the run.
- Initial focused movement/surface/item checks: **51 tests pass**.
- `tests/test_block_walking.py`: **9 new regression tests pass**. They cover
  48 unit-block input/material/dt combinations, 16 fractional-terrain approaches,
  32 fractional-solid approaches, 16 explicit jump landings, ordinary-solid
  standing/descent/Foley, generic support and actual dropped-item settling.
- The built-world test shares one world across six castle obstruction cases
  (24 walk/sprint/update-rate approaches) and all **13 authored flights** in
  both directions at walking/sprinting speeds: **52 legs**, continuously
  grounded/noncolliding, exactly **1,040 stair contact cues**, no jump/landing.
- `block-climb-before-tests-2026-11-13.txt` runs that new regression file against
  frozen a2049c3. It fails with **136 assertion failures across subtests** and
  three expected unsupported-keyword errors for the new walking query option.
  It preserves direct behavioral proof that the original engine climbs these
  obstacles. This is an expected failing control, not a current test failure.

## Matched performance method

- `block-climb-live-120x40-2026-11-13.json`: **34/34 matched roles pass**.
  Largest mean increase **3.07%** (stair walking); largest p95 increase **8.38%**
  (river diagonal). Both static-geometry fingerprints and camera poses agree.
  Native audio has zero underruns/recoveries, 59.40 ms maximum refill interval.
  All thresholds, raw samples and original controls are retained unchanged.

Use the same-geometry helper with a2049c3/fd56e49 source, 120x40, 60 samples per
variant, five warmups and serial per-frame ABBA with one shared live native
audio mixer. Both variants use CPU rendering to isolate the movement change.
Static geometry fingerprints and all matched camera poses must agree; all 34
roles, including actual terrace/stair walking, retain the unchanged 15% mean
and p95 gates. No historical baseline is replaced.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
# Reconstruct only if absent:
git archive --format=zip --output=movement-control-tmp.zip a2049c3 ascii3d
Expand-Archive -LiteralPath movement-control-tmp.zip -DestinationPath movement_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source movement_control_tmp --reference-label a2049c3 --audio --save benchmarks/block-next-unused.json
# Native console, including hardware/input checks:
$env:MONOLITH_GPU_TESTS='1'; $env:MONOLITH_DESKTOP_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest discover -s tests -v
```

# Project Status

Last reviewed **2026-11-17**. [Repository rules](AGENTS.md) ¡¤
[User backlog](backlog.md) ¡¤ [Launch and controls](README.md).

## Current checkpoint

Uncommitted six-site map, dark-fantasy sound and stronger eye-level ash/dust are
implemented. The user then clarified that blockiness means overall grid-shaped
roads/building masses/orientations and the map, not decorative bevels.
Latest changes give roads continuous capsule boundaries; Thornwatch rotates17¡Æ
and Astral Reliquary-23¡Æ, including real floors/openings/stairs/collision.
Their terrain pads, entrances, road ends, spawns and benchmark cameras rotate
with them. The map uses fractional coverage and directional edge glyphs.

**The broader geometry work is unfinished.** Work stopped at the standing15%
usage cutoff. No jobs remain active. Preserve the current failing shortcut test;
do not mark overall blockiness complete or claim the current source passes the
full suite. No implementation commit has been made; play review remains pending.

## Verified evidence and limits

[Detailed evidence](benchmarks/darkworld-2026-11-17.md) distinguishes these stages:

- The first six-site version passed564 real-console tests (one desktop-pointer
  opt-in skip),36 CPU/GPU complete frame pairs and live audio without underruns
  or recoveries. It is frozen with a SHA256 manifest in
  `benchmarks/darkworld-grid-control-2026-11-17.zip`. Those full-suite/parity
  results **precede** the latest road/rotation/map edits.
- Against46c36a3, matched120x40/60-frame styled/live-audio semantic timing passed
  CPU12/34 and GPU19/34 roles. Every failed role is retained. No historical
  baseline or15% mean/p95 threshold changed; fullscreen30+FPS is unverified.
- Latest focused checks:19 road/elevated/presentation checks pass, including
  actual GPU flat/sloping road materials;8 rotation/terrain checks pass,
  including all12 highland flights both ways and every ground-to-roof path;
 6 map shape/cache checks pass. All destination spawns build without collision.
- Latest continuous six-destination walk passes with rotated joins. The
  ravine-to-Reliquary shortcut remains blocked near
  **(340.76,306.5,Z10.64)** on `(326,306)->(350,306)`. The player stays grounded
  and collision-free but cannot advance, suggesting a too-steep terrain grade.
  The final changed point-material assertion was not rerun after cutoff.

## Resume priorities

1. Repair that shortcut grade/route without weakening slope limits or deleting
   the regression. Re-run the exact route check below, then the full route group.
2. Migrate the aggregate block-walking test: it assumes13 axis-aligned entries
   in `_stair_keys`; current source has7 there and6 `(landmark,flight_key)`
   entries in `_oriented_stairs`. Transform the latter through `to_world` and
   add `landmark.angle` to movement headings. Preserve1040 contact coverage.
3. Run the full current-source native suite, rotated hardware frame parity and
   new performance/output checks. Rebuild a fresh semantic role manifest;
   `darkworld-roles-2026-11-17.json` belongs to the first grid version.
4. Continue overall massing/layout work and user fullscreen review; rotating
   two otherwise rectangular halls does not finish the broader natural-form goal.

```powershell
python -B -m unittest tests.test_map_expansion.MapExpansionTests.test_six_destinations_have_dry_walkable_routes_with_real_collision_and_height -v
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_roads tests.test_oriented_architecture tests.test_terrain tests.test_map_shapes -v
.\.venv-gpu\Scripts\python.exe -B validate_native_tmp.py
.\run.bat
python -B main.py --region thornwatch --keyboard-look
```

`validate_native_tmp.py` is retained for the pending full native rerun; it opens
a hidden genuine console and reserves an unused `continuous-world-native-tests`
report prefix. Use a new prefix after any run. `quality_native_smoke_tmp.py`
remains for120x40/160x50 actual output. Temporary previews, extracted controls
and caches were removed; extract the frozen grid control ZIP to a new directory
before any incremental benchmark.

The old lag camera `(215.2,187.4,Z10)` referred to replaced geometry. Reproduce
an equivalent spike at a clear playable camera on the new layout. Physical mouse,
speaker/fullscreen review, POSIX held keys and Python3.10 execution remain open.

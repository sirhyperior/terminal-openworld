# Project Status

Last reviewed **2026-11-21**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

The six-site map, sound redesign, continuous roads, two angled landmarks and
fractional map sampling are committed at `b988df7`. The user wants the original
dark atmosphere with occasional pinpricks of light. The working pass restores
the original palette and surface shading, with denser, dim eye-level motes and
up to two brief ash sparks and four isolated river glints per scene. The
broader blockiness item and physical fullscreen play review remain open.

## Verified evidence and limits

[Appearance evidence](benchmarks/moon-glints-2026-11-21.md) distinguishes the
current sparse pass from the earlier broad-contrast experiment. With particles
hidden, the gatehouse, hall, exterior and canopy samples from the earlier
palette match cell for cell. The river differs only at the sparkle cells.
The current 61 focused tests and 24 CPU/GPU frame comparisons passed.
The final matched GPU run passed all 34 mean gates and 31 p95 gates. Indoors,
ridge upper and citadel roof exceeded the 15% p95 threshold.
The third river bridge walking test fails both directions on the current tree
and reproduces on `b988df7`. The voxel moonlight map omits convex roofs.

[Map and sound evidence](benchmarks/darkworld-2026-11-17.md) retains the
earlier 564-test native run, paired performance failures and subsequent focused
road, rotation and map checks. The full current native suite and stable
fullscreen 30+ FPS are unverified. The six-destination loop passed with rotated
joins, with a separate ravine-to-Reliquary shortcut stall near
**(340.76, 306.5, Z10.64)** on `(326,306)->(350,306)`.

## Resume priorities

1. Repair the shortcut and third river bridge grades. Preserve slope limits and
   rerun both route regressions before the full route group.
2. Migrate the aggregate block-walking test. It assumes 13 axis-aligned entries
   in `_stair_keys`. Current source has 7 there and 6 `(landmark, flight_key)`
   entries in `_oriented_stairs`. Transform the latter through `to_world` and
   add `landmark.angle` to movement headings. Preserve 1,040 contact checks.
3. Run the full current native suite and verify physical fullscreen output.
   Continue overall building massing and map layout work.

```powershell
.\run.bat
python -B main.py --keyboard-look --color-mode color
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_particles tests.test_shading tests.test_color_integration tests.test_color_gpu_parity -v
python -B -m unittest tests.test_map_expansion.MapExpansionTests.test_six_destinations_have_dry_walkable_routes_with_real_collision_and_height tests.test_outdoors.OutdoorMovementTests.test_all_river_bridges_connect_both_banks_without_jumping -v
.\.venv-gpu\Scripts\python.exe -B validate_native_tmp.py
```

`validate_native_tmp.py` opens a hidden genuine console and reserves an unused
report prefix. Use a new prefix after each run. `quality_native_smoke_tmp.py`
supports 120x40 and 160x50 native output checks. For a matching appearance
control, extract `git archive` of `b988df7 ascii3d tools` into a fresh directory.

The old lag camera `(215.2,187.4,Z10)` referred to replaced geometry. Reproduce
an equivalent spike at a clear playable camera on the new layout. Physical mouse,
speaker/fullscreen review, POSIX held keys and Python 3.10 execution remain open.

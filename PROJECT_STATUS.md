# Project Status

Last reviewed **2026-11-21**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

The user reports around 20 FPS in fullscreen. The follow-up writes only
changed terminal spans, shares expanded foreground data and limits grass
generation to chunks that can contribute within the blade budget. Real Xfce
fullscreen at 336×124 improved mean/p95 frame time from 26.45/35.44 to
25.50/25.54 ms. Six of 358 final intervals exceeded 33.33 ms. The reproducible
Thornwatch spike near `(296.03, 130.09, Z7)` now costs 40–45 ms. All 180 matched
replay frames preserve glyphs and color. The user's setup, physical Windows
fullscreen, hardware GPU and live audio remain open.
[Fullscreen follow-up evidence](benchmarks/optimization-fullscreen-output-2026-11-21.md)

At full detail, all 34 Python CPU roles pass the existing 15% mean and p95
gates at 160×50. The optional C backend lowers mean/p95 by up to 56%/55% on
the same tightened Python control. All 102 full-detail frame and depth samples
match `df643ea`. Full-detail frame-rate acceptance remains open.
[Optimization evidence](benchmarks/optimization-cpu-2026-11-21.md)

## Verified evidence and limits

`df643ea` commits the restored palette, eye-level motes and sparse glints on
the six-site world from `b988df7`. Its Windows GPU evidence passed 34 mean
gates and 31 p95 gates. The voxel moonlight map omits convex roofs. The
broader blockiness item remains open. [Appearance evidence](benchmarks/moon-glints-2026-11-21.md)

The third river bridge walk fails in both directions and reproduces on
`b988df7`. The six-destination loop passed with the rotated joins. The
ravine-to-Reliquary shortcut stalls near **(340.76, 306.5, Z10.64)** on
`(326,306)->(350,306)`. [Map and sound evidence](benchmarks/darkworld-2026-11-17.md)

The Linux suite ran 595 tests with 20 skips and 10 failures. All 10 reproduced
on `df643ea`, including stale stair/road assumptions and one animated scenery
comparison. The new glint expansion check also passed independently.

## Resume priorities

1. Capture the user's reported fullscreen slowdown with `--frame-timing`.
   Compare terminal write/flush, GPU fallback, render, input, simulation and
   cap waits. Benchmark full detail separately. Use the
   [fullscreen follow-up](benchmarks/optimization-fullscreen-output-2026-11-21.md).
2. Repair the shortcut and third river bridge grades. Preserve slope limits and
   rerun both route regressions before the full route group.
3. Migrate the aggregate block-walking test. It assumes 13 axis-aligned entries
   in `_stair_keys`. Current source has 7 there and 6 `(landmark, flight_key)`
   entries in `_oriented_stairs`. Transform the latter through `to_world` and
   add `landmark.angle` to movement headings. Preserve 1,040 contact checks.
4. Run the current Windows native suite and continue overall building massing
   and map layout work.

```powershell
.\run.bat --frame-timing fullscreen-timing.json
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

The archived lag camera `(215.2,187.4,Z10)` referred to replaced geometry.
The Thornwatch approach supplies a repeatable replacement probe.
Physical mouse, speaker/fullscreen review, POSIX held keys and Python 3.10
execution remain open.

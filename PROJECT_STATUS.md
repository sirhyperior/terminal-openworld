# Project Status

Last reviewed **2026-11-21**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

Startup now shows a moonlit ASCII gatehouse, then centers the splash in the
game's alternate screen during audio startup. All 42 focused loading and
game-loop tests passed. A 120×40 Windows GPU demo drew 60 frames with live
audio, zero underruns or recoveries, and restored the console screen, cursor
and modes. [Native startup smoke](benchmarks/loading-gatehouse-native-2026-11-21.json)

The renderer traces every native scene cell, following the restoration in
`780e5c8`. The Windows optimization batches exact GPU candidate refinement,
CPU voxel traversal and static surface lighting through the optional native
library. The rebuilt DLL is active in this checkout. All 102 styled frame
pairs at 240×80 match `427dc70` exactly, including opaque depths.

With an RTX 3080 Laptop GPU and live audio, all 34 matched 240×80 roles
pass both relative performance gates. Mean time falls 12–58% and p95 falls
10–54%. None reaches the 33.33 ms p95 target at that size. The live Windows
console reached 38.46 FPS at 160×50 Ashgate with 29.29 ms p95. At 240×80,
Ashgate reached 20.20 FPS and Thornwatch 10.71 FPS. Physical fullscreen
and 30+ FPS across scenes remain open.
[Windows timing and parity evidence](benchmarks/full-detail-windows-2026-11-21.md)

## Verified evidence and limits

`df643ea` establishes the palette, eye-level motes and sparse glints on the
six-site world. The voxel moonlight map omits convex roofs. The broader
blockiness item remains open. [Appearance evidence](benchmarks/moon-glints-2026-11-21.md)

The third river bridge walk fails in both directions and reproduces on
`b988df7`. The six-destination loop passed with the rotated joins. The
ravine-to-Reliquary shortcut stalls near **(340.76, 306.5, Z10.64)** on
`(326,306)->(350,306)`. [Map and sound evidence](benchmarks/darkworld-2026-11-17.md)

The native Windows suite ran 611 tests with two skips and ten failures.
All failures reproduced on `427dc70`, including existing stair and road
assumptions and the animated scenery comparison.
[Suite log](benchmarks/full-detail-windows-native-tests-2026-11-21.txt) ·
[Control rerun](benchmarks/full-detail-windows-control-failing-tests-2026-11-21.txt)

## Resume priorities

1. Capture a physical fullscreen run with `--frame-timing`. Use the
   [Windows measurements](benchmarks/full-detail-windows-2026-11-21.md) to
   compare remaining per-cell CPU work, fallback rays and console output.
2. Repair the shortcut and third river bridge grades. Preserve slope limits and
   rerun both route regressions before the full route group.
3. Migrate the aggregate block-walking test. It assumes 13 axis-aligned entries
   in `_stair_keys`. Current source has 7 there and 6 `(landmark, flight_key)`
   entries in `_oriented_stairs`. Transform the latter through `to_world` and
   add `landmark.angle` to movement headings. Preserve 1,040 contact checks.
4. Continue building massing and map layout work.

```powershell
.\run.bat --frame-timing fullscreen-full-detail-timing.json
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

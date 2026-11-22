# Project Status

Last reviewed **2026-11-23**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

The rebuilt optional DLL shades resolved GPU hits at the full viewport size.
Ambiguous rays use exact traversal and the combined native terrain/solid query
when available. Explicit GPU uses the compiled paving sampler when installed.
Road point queries keep exact boundaries and skip capsule tests in cells with
proven coverage. Water and local firelight still follow the shared renderer.

At 240×80 with live audio, all 35 matched auto roles pass both relative timing
gates. Thirteen meet 33.33 ms p95 before terminal writes. Paving drops from
67.52/83.54 to 27.04/30.42 ms mean/p95. Thornwatch lodge drops from
76.11/98.81 to 34.04/41.23 ms. All 105 matched frames and opaque depth
buffers agree, and all 51 focused tests pass. In physical 213×60 conhost,
Ashgate rises from 16.77 to 19.47 FPS and Thornwatch from 10.40 to 14.27 FPS.
Live audio had zero underruns or recoveries. The 30+ FPS target remains open.
[Fullscreen performance and validation](benchmarks/fullscreen-throughput-2026-11-23.md)

Prior paving appearance and developer console checks are retained together.
[Road relief and developer split validation](benchmarks/cobble-relief-dev-split-2026-11-23.md)
The 120×40 Mael spawn and aimed-view p95 regressions remain open.
[Mael and actor label timings](benchmarks/npc-labels-mael-2026-11-22.md)

## Verified evidence and limits

The original `--dev` console passed native Windows checks for editing, live
settings, teleport, sound and restoration. Renderer switches can take a few seconds.
[Developer console validation](benchmarks/dev-console-2026-11-22.md)

The native Windows dialogue smoke verified keyboard targeting, all three lines
of Iven's conversation, resumed movement, console restoration and live audio.
[Dialogue smoke](benchmarks/npc-dialogue-native-2026-11-21.json) ·
[NPC idle animation timings](benchmarks/npc-idle-animation-2026-11-22.md)

The moonlit loading splash passed 42 focused loading and game-loop tests and a
120×40 live-audio Windows GPU smoke with console restoration.
[Startup evidence](benchmarks/loading-gatehouse-native-2026-11-21.json)

`df643ea` establishes the palette, eye-level motes and sparse glints on the
six-site world. The voxel moonlight map omits convex roofs. The broader
blockiness work remains open. [Appearance evidence](benchmarks/moon-glints-2026-11-21.md)

The third river bridge walk fails in both directions and reproduces on
`b988df7`. The six-destination loop passed with the rotated joins. The
ravine-to-Reliquary shortcut stalls near **(340.76, 306.5, Z10.64)** on
`(326,306)->(350,306)`. [Map and sound evidence](benchmarks/darkworld-2026-11-17.md)

The native Windows suite before NPC idle motion ran 626 tests with GPU checks
enabled. There were 614 passes, two skips and the same ten failures as the prior
full-detail suite. The prior control reproduced all ten on `427dc70`, including
stair and road assumptions and the animated scenery comparison.
[Suite log](benchmarks/backlog-native-tests-2026-11-21.txt) ·
[Suite manifest](benchmarks/backlog-native-tests-2026-11-21.json) ·
[Prior control](benchmarks/full-detail-windows-control-failing-tests-2026-11-21.txt)

## Resume priorities

1. Compare physical fullscreen presentation in Windows Terminal and classic
   conhost with `--frame-timing` at the same grid size, cap and audio mode.
   Heavy river, firelight and terrace views still need engine work. Rerun the
   120×40 Mael poses and explicit GPU paving pose (128.5, 63.5, Z1), facing north
   at pitch −0.28, against the frozen source.
2. Repair the shortcut and third river bridge grades. Preserve slope limits and
   rerun both route regressions before the full route group.
3. Migrate the aggregate block-walking test. It assumes 13 axis-aligned entries
   in `_stair_keys`. Current source has 7 there and 6 `(landmark, flight_key)`
   entries in `_oriented_stairs`. Transform the latter through `to_world` and
   add `landmark.angle` to movement headings. Preserve 1,040 contact checks.
4. Continue building massing and map layout work.

```powershell
.\run-dev.bat
.\run.bat --frame-timing fullscreen-full-detail-timing.json
python -B main.py --keyboard-look --color-mode color
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_particles tests.test_shading tests.test_color_integration tests.test_color_gpu_parity -v
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_roads tests.test_native_shading tests.test_player_health tests.test_particles tests.test_enemies -v
python -B -m unittest tests.test_dev_build tests.test_dev_console tests.test_frame_timing -v
python -B -m unittest tests.test_map_expansion.MapExpansionTests.test_six_destinations_have_dry_walkable_routes_with_real_collision_and_height tests.test_outdoors.OutdoorMovementTests.test_all_river_bridges_connect_both_banks_without_jumping -v
.\.venv-gpu\Scripts\python.exe -B validate_native_tmp.py
```

`validate_native_tmp.py` opens a hidden genuine console and reserves an unused
report prefix. Use a new prefix after each run. `quality_native_smoke_tmp.py`
supports 120x40 and 160x50 native output checks. For a matching appearance
control, extract `git archive` of `b988df7 ascii3d tools` into a fresh directory.

The archived lag camera `(215.2,187.4,Z10)` referred to replaced geometry.
The Thornwatch approach supplies a repeatable replacement probe.
Physical mouse, speaker review, POSIX held keys and Python 3.10
execution remain open.

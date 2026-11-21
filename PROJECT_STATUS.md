# Project Status

Last reviewed **2026-11-22**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

Mael Veyr stands ahead and left of the default Ashgate spawn. His ankle-length
robes and pointed hood follow the other residents' idle animation. The hood
has a recessed opaque lining that hides his face. Both Ashgate starting routes
to the sword and gate remain clear.

The nearest actor under the crosshair gets a depth-tested label with clear
sight. Residents use sage-green `<Name>` text and enemies show name and health.
Dialogue hides the labels while the reticle is absent. All four residents can
be reached on foot.

The 81 focused targeting, movement and render tests passed, along with three
dedicated hood tests. Six hardware GPU and CPU color frames matched at Mael's
talk position. His hood was visible from the normal spawn at 60×20 and 120×40.

Matched live-audio benchmarks passed the mean and p95 gates at 240×80. Both
120×40 views exceeded the regression gates. Spawn p95 rose from 15.52 to
22.33 ms and aimed p95 rose from 14.84 to 17.28 ms. Small-viewport rendering
cost remains open.
[Mael and actor label timings](benchmarks/npc-labels-mael-2026-11-22.md)

The preceding idle animation passed 68 focused tests and eight CPU/GPU frame
pairs. The matched 240×80 and isolated 120×40 cases met the mean and p95 gates.
[NPC idle animation timings](benchmarks/npc-idle-animation-2026-11-22.md)

E uses shared aim, reach and visibility checks. Both characters turn toward
each other before the text box opens and E advances the lines while gameplay
is frozen. A 120×40 native Windows GPU run verified keyboard input, all three
lines of Iven's conversation, movement resumption, console restoration and
live audio with zero underruns or recoveries.
[Dialogue smoke](benchmarks/npc-dialogue-native-2026-11-21.json)

The renderer traces every native scene cell. The previous full-detail Windows
optimization batches exact GPU candidate refinement, CPU voxel traversal and
static surface lighting. Its rebuilt DLL is active. Before the NPC changes, all
102 styled frame pairs at 240×80 matched `427dc70`, including opaque depths.

With an RTX 3080 Laptop GPU and live audio, all 34 matched 240×80 roles
pass both relative performance gates. Mean time falls 12–58% and p95 falls
10–54%. None reaches the 33.33 ms p95 target at that size. The live Windows
console reached 38.46 FPS at 160×50 Ashgate with 29.29 ms p95. At 240×80,
Ashgate reached 20.20 FPS and Thornwatch 10.71 FPS. Physical fullscreen
and 30+ FPS across scenes remain open.
[Windows timing and parity evidence](benchmarks/full-detail-windows-2026-11-21.md)

Follow-up 240×80 live-audio benchmarks tested native voxel traversal on GPU
fallback rays and reuse of static GPU hits at a fixed camera pose. Both were
withdrawn after missing the existing p95 gate. The optimization backlog entry
remains open. [Follow-up measurements](benchmarks/exact-gpu-follow-up-2026-11-21.md)

## Verified evidence and limits

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

1. Capture a physical fullscreen run with `--frame-timing`. Use the
   [Windows measurements](benchmarks/full-detail-windows-2026-11-21.md) to
   compare remaining per-cell CPU work, fallback rays and console output. Use
   the Mael benchmark's fixed spawn and talk camera poses for 120×40 follow-up.
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

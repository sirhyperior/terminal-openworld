# Project Status

Last reviewed **2026-11-23**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

The developer console renders a live split view with FPS while the editor
has focus. `bug <message>` appends the player's feet coordinates and local
timestamp to the backlog. Dialogue reveals letters in place, with E to reveal
the line and E again to continue. Combat has directional damage cues and a
depth-tested Warden fall. Cobblestone contacts have dedicated Foley.

The Riven Vale shortcut near (340.8, 306.5, Z10.7) and the third river bridge
are walkable in both directions. The 1,040-contact test covers all 13 stair
flights, including six transformed flights. The live native console replay
passed report, FPS, motion, audio and restoration checks. All four matched
120×40 gameplay roles pass the mean and p95 timing gates.
[Backlog validation](benchmarks/backlog-validation-2026-11-23.md)

The rebuilt optional DLL also shades static GPU hits outside local firelight
and leaves shared visibility checks in screen order. At 240×80 with live
audio, the fireball role improves from **65.12/100.18 to 52.08/80.63 ms**
mean/p95. All three sampled roles pass both regression gates. All 20 paired
frames and depth buffers match.
[Firelight timing](benchmarks/backlog-firelight-auto-240x80-2026-11-23.json) ·
[Frame parity](benchmarks/backlog-firelight-parity-2026-11-23.json)

The prior 240×80 full-grid comparison passed both relative gates on all 35
auto roles. In physical 213×60 conhost, Ashgate reached 19.47 FPS and
Thornwatch reached 14.27 FPS. These runs precede the current backlog work.
[Fullscreen evidence](benchmarks/fullscreen-throughput-2026-11-23.md)

The native Windows suite ran 672 tests with GPU checks enabled. All 14
failure records across four test methods reproduce on `0dcb8e6`. Two tests
skipped. The remaining failures cover the stair benchmark's camera assertion,
paving palette readability, scenery occlusion and an old grass fixture.
[Native suite](benchmarks/backlog-validation-native-2026-11-23.txt) ·
[Frozen control](benchmarks/backlog-validation-control-failures-2026-11-23.txt)

## Open issues and resume

1. The **30+ FPS fullscreen target** remains open. Measure Windows Terminal
   and classic conhost on the same physical grid, replay, cap and audio
   configuration. River, firelight and terrace views still exceed the 33.33 ms
   budget before terminal writes.
2. Replay the 120×40 Mael spawn and aimed views against their frozen control
   and the fixed-yaw explicit GPU paving pose (128.5, 63.5, Z1), north at
   pitch −0.28. [Mael timing gates](benchmarks/npc-labels-mael-2026-11-22.md) ·
   [Paving controls](benchmarks/cobble-relief-dev-split-2026-11-23.md)
3. Continue building massing and map layout. The voxel moonlight map omits
   convex roofs. Physical mouse, speaker review, POSIX held keys and Python
   3.10 execution remain open.
   [Appearance evidence](benchmarks/moon-glints-2026-11-21.md)

```powershell
.\run-dev.bat
.\run.bat --keyboard-look --demo --frames 60 --frame-timing fullscreen-ashgate-replay.json
.\run.bat --keyboard-look --demo --region thornwatch --frames 60 --frame-timing fullscreen-thornwatch-replay.json
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_native_shading tests.test_color_gpu_parity tests.test_dev_build tests.test_game_loop tests.test_block_walking -v
python -B -m unittest tests.test_map_expansion tests.test_outdoors.OutdoorMovementTests -v
```

Use unused timing filenames. Rebuild the optional DLL with the compiler command
in the README before timing native shading. The native suite helper
`validate_native_tmp.py` opens a hidden console and needs an unused report
prefix for each run. [Benchmark index](benchmarks/README.md)

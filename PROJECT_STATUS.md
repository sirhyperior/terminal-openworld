# Project Status

Last reviewed **2026-11-23**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

NPCs support opt-in `PatrolStop` routes with timed stops, walking animation,
collision and surface footsteps. Conversations stop the patrol, and natural
letter reveals have low-volume 25 ms cues. Immediate reveal plays one rustle.
The live native replay verified patrol, dialogue, pause, resume and terminal
restoration. The two matched 120×40 roles pass both timing gates. The active
level spread across ten ordinary audio cues fell from 8.53 to 1.00 dB in PCM.
After play feedback, all door cues gained 3 dB. The 36 focused sound and door
tests passed, and live playback had zero underruns or recoveries.
[Door level verification](benchmarks/patrol-dialogue-fireball-2026-11-23.md#door-level-follow-up)

The rebuilt DLL keeps compiled base shading on resolved hits after the
shared firelight shadow budget fills. At 240×80 with live audio, the p95
cast frame falls from **71.49 to 47.71 ms** in the Ashgate yard and from
**82.82 to 56.67 ms** in the gatehouse. All 24 paired frames, opaque depths
and surface shadow results match.
[Current timing and validation](benchmarks/patrol-dialogue-fireball-2026-11-23.md)

The previous checkpoint verified the live developer console, the Riven Vale
and Reliquary Bridge repairs, 1,040 stair contacts, combat feedback and
cobblestone audio. [Prior validation](benchmarks/backlog-validation-2026-11-23.md)

The prior 240×80 full-grid comparison passed both relative gates on all 35
auto roles. In physical 213×60 conhost, Ashgate reached 19.47 FPS and
Thornwatch reached 14.27 FPS. These runs precede the current backlog work.
[Fullscreen evidence](benchmarks/fullscreen-throughput-2026-11-23.md)

The native Windows suite ran 683 tests with GPU checks enabled. Its 14
failure records match the prior suite. Two frame-timing tests initially
errored because their mock lacked the NPC update result. After correcting
the fixture, all 39 frame-timing, developer console and game-loop tests
passed. Two platform tests skipped in the full run.
[Native suite](benchmarks/backlog-patrol-audio-fireball-native-2026-11-23.txt) ·
[Prior failure replay](benchmarks/backlog-validation-control-failures-2026-11-23.txt)

## Open issues and resume

1. The **30+ FPS fullscreen target** remains open. Measure Windows Terminal
   and classic conhost on the same physical grid, replay, cap and audio
   configuration. Profile the remaining early-flight spike with the new DLL.
   River, firelight and terrace views still exceed the 33.33 ms budget before
   terminal writes.
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
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_native_shading tests.test_color_gpu_parity tests.test_combat tests.test_doors -v
python -B -m unittest tests.test_npcs tests.test_npc_render tests.test_game_loop tests.test_sound -v
```

Use unused timing filenames. Rebuild the optional DLL with the compiler command
in the README before timing native shading. The native suite helper
`validate_native_tmp.py` opens a hidden console and needs an unused report
prefix for each run. [Benchmark index](benchmarks/README.md)

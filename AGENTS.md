# Repository Guidelines

## Project and Context

MONOLITH is a first-person 3D exploration sandbox rendered entirely as white
ASCII on black in a terminal. Preserve responsive WASD movement, Shift sprinting,
Space jumping, readable environments and keyboard accessibility. Use Python
3.10+ and prefer the standard library; justify new dependencies.

- Before development, read [PROJECT_STATUS.md](PROJECT_STATUS.md), then relevant
  README sections, source and tests. Verify documentation against implementation.
- Keep stable rules here, current state/issues/decisions in `PROJECT_STATUS.md`,
  user instructions in `README.md`, and detailed measurements in `benchmarks/`.
  Update status/review date after significant work, including resume paths and
  commands. Distinguish verified facts, reports and proposals; never invent progress.
- Ask before major architectural changes. Routine additive features within the
  existing engine do not require another approval.

## Gameplay Conventions

- **E handles every direct environment interaction**: open/activate/use/collect.
  Use shared targeting/dispatch, look/reach/line-of-sight checks and `[E]` prompts.
- Default new doors to `Door`/`Panel` and the shared renderer. Configure placement,
  dimensions, orientation and leaf count; share operation, animation, obstruction
  protection, prompts and sound. Document deliberate exceptions.
- Implement recurring mechanisms once, with instance differences as configuration;
  apply fixes across instances and test common behavior. Separate targeting,
  state, simulation, collision, rendering and sound events. Extend abstractions
  for concrete needs while retaining work budgets.
- Items/enemies use opaque, depth-tested shapes. Reuse restrained pickup markers;
  show enemy labels only when aimed at with clear sight.
- Windows mouse motion looks and left click attacks; **Q is unbound**. Preserve
  `--keyboard-look` (arrows/Enter) for accessibility and other platforms.

## Engine and Performance

- X/Y are ground and Z is height. Keep collision independent of rendering,
  fixed-step physics, simulation-time animation, seeded scenery, nonblocking
  input and terminal cleanup. Pause/help freeze movement and scenery.
- Edit voxels through `World.box()` to invalidate caches. Keep occlusion exact,
  vegetation work bounded by visibility/detail budgets, and exact-ray tests.
- Benchmark rendering changes; use live-audio benchmarks for gameplay changes
  when a Windows device is available. Compare mean **and p95** on the same
  hardware, Python, dimensions, frame count and audio mode. Preserve failed runs;
  never relax thresholds, cherry-pick results or silently replace baselines.

## Required Sound

Implement sound with every gameplay feature, player action and environmental
interaction: emit semantic `GameEvent`s, register cues in `sound.py`, and test
coverage. Use original or appropriately licensed audio. Preserve mute, volume,
pause, silent headless modes and graceful operation without a device.

Keep synthesis/device I/O outside simulation/rendering. Native output uses an
isolated process, completion callbacks, primed buffers and click-free fades.
Preserve bounded mixing and queue health checks. Device backpressure paces real
output; wall-clock rate caps are only for immediately returning sinks.

## Source Guide

`main.py`, `python -m ascii3d` and `run.bat` launch the game. In `ascii3d/`:

- `app.py`, `terminal.py`, `mouse_capture.py`: CLI/frame loop, input/native mouse
  capture and terminal lifecycle.
- `world.py`, `map_expansion.py`, `terrain.py`, `player.py`: materials/layout,
  highlands, shared multilevel landmarks, collision, stairs, movement, jumping,
  water current and player health.
- `renderer.py`, `scenery.py`, `trees.py`, `geometry.py`: rays, HUD/map,
  grass/wind, trees and shared projection/fill/strokes.
- `targeting.py`, `doors.py`, `door_render.py`: view queries and shared panels.
- `combat.py`, `combat_render.py`: items, weapons/projectiles, enemy simulation
  and depth-tested presentation.
- `events.py`, `sound.py`, `audio_output.py`, `audio_process.py`, `soundscape.py`,
  `sound_surfaces.py`, `audio_check.py`: feedback, synthesis, playback,
  environmental sampling, contact Foley and diagnostics.

## Validation and Workspace

Use four spaces, existing type hints/dataclasses, `snake_case`, `PascalCase` and
`UPPER_CASE` constants. No formatter/linter/build step is configured. Tests use
`unittest`, `test_*.py` and `test_*` methods. Cover changed collision, jumping,
water, animation and occlusion; inspect indoor/outdoor rendering changes.
Windows input tests require a live console and otherwise skip.

Run from the repository root; README documents launch options:

```powershell
python -B main.py --snapshot
python -B main.py --demo --frames 100
python -B main.py --audio-test
python -B -m unittest discover -s tests -v
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/castle-milestone-before-live.json
```

Remove generated previews, temporary probes and caches after review unless asked
to retain them. Keep benchmark evidence needed for open issues; consult
[benchmarks/README.md](benchmarks/README.md) before removing reports.

## Git Workflow

- Use imperative commit subjects. After the user confirms an implementation is
  successful, commit all changes for it; also honor explicit checkpoint requests.
- Perform requested reverts/undos through Git so history records the reversal.
- PRs explain resulting behavior, issues, validation and applicable screenshots/
  benchmarks.

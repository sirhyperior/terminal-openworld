# Repository Guidelines

## Project and Context

MONOLITH is a first-person 3D exploration sandbox rendered entirely as monochrome
ASCII on black in a terminal. Grayscale foregrounds are the current visual
foundation; full color follows the approved world redesign and user play review. Preserve responsive WASD movement, Shift sprinting,
Space jumping, readable environments and keyboard accessibility. Use Python
3.10+ and prefer the standard library; justify new dependencies.

The world's standing theme is **dark fantasy**. Future structures, terrain,
NPCs, enemies and environmental details must fit that theme in their design,
names and atmosphere while preserving readable navigation and interactions.

- At session start or resume, read [PROJECT_STATUS.md](PROJECT_STATUS.md), then
  [backlog.md](backlog.md). Consider that
  user-maintained backlog alongside current blockers and explicit requests;
  its numbering does not set priority. Remove completed entries and renumber
  only after verifying completion. Then read relevant README sections, source
  and tests; verify documentation against implementation.
- Keep stable rules here, current state/issues/decisions in `PROJECT_STATUS.md`,
  user instructions in `README.md`, and detailed measurements in `benchmarks/`.
  Update status/review date after significant work, including resume paths and
  commands. Distinguish verified facts, reports and proposals; never invent progress.
- At significant updates and every handoff, prune stale or redundant context
  from both files. Keep this file for durable rules and `PROJECT_STATUS.md` for
  the current checkpoint, open issues, latest validation and next steps. Link
  detailed investigations/history in `benchmarks/`; do not accumulate session
  logs, temporary usage readings or duplicate README content. Preserve required
  benchmark evidence when cleaning documentation.
- Ask before major architectural changes. Routine additive features within the
  existing engine do not require another approval.
- Create and use subagents whenever they help with the work; no additional user
  permission is needed. Delegate independent investigation, implementation or
  review tasks, coordinate shared files, and verify their results before handoff.
- Check account usage between major phases. When either relevant usage window
  reaches **15% remaining or less**, wrap up the session: stop starting new work,
  safely finish or stop active jobs, and leave a precise verified checkpoint,
  open issues and resume commands. Do not invent completion to fit the limit.

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
- Upward ground following is for continuous terrain and authored stair treads.
  Ordinary blocks require jumping. Keep generic support queries available for
  item placement and camera settling when tightening player movement rules.
- Startup percentages count completed work. Loading animation must stop before
  gameplay or terminal restoration; silent headless modes start no animation.
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
- `loading.py`: completed-phase progress, bounded startup animation and tips.
- `gpu_renderer.py`, `gpu_static.wgsl`: optional GPU geometry candidates,
  float64 refinement and exact CPU fallback; presentation remains shared.
- `world.py`, `map_expansion.py`, `terrain.py`, `player.py`: materials/layout,
  highlands, shared multilevel landmarks, collision, stairs, movement, jumping,
  water current and player health.
- `surfaces.py`: shared continuous ground triangles, exact circular support,
  analytic ray hits, convex pieces and fractional stair solids.
- `shading.py`, `presentation.py`: shared semantic material lighting, compact
  grayscale foreground buffers and ANSI serialization.
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

Run from the repository root. README documents launch/test options;
`PROJECT_STATUS.md` identifies current benchmark controls and resume commands.

Remove generated previews, temporary probes and caches after review unless asked
to retain them. Keep benchmark evidence needed for open issues; consult
[benchmarks/README.md](benchmarks/README.md) before removing reports.

## Git Workflow

- Use imperative commit subjects. After the user confirms an implementation is
  successful, commit all changes for it; also honor explicit checkpoint requests.
- Perform requested reverts/undos through Git so history records the reversal.
- PRs explain resulting behavior, issues, validation and applicable screenshots/
  benchmarks.

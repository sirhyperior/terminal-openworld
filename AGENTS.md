# Repository Guidelines

## Project Objectives

MONOLITH is a first-person 3D exploration sandbox rendered entirely as white
ASCII text on black in a terminal. Preserve responsive WASD movement, Shift
sprinting, Space jumping, readable environments, and keyboard accessibility.
Prefer Python's standard library; justify any new dependency.

## Shared Interaction & Mechanism Conventions

- Use **E for all direct interactions with the environment**, including opening,
  activating, using, and collecting. Route actions through shared targeting and
  dispatch, with consistent look/reach/line-of-sight checks and `[E]` prompts.
- Default nearly all new doors to the existing `Door`/`Panel` format and shared
  renderer. Configure placement, size, orientation, and leaf count while keeping
  operation, animation, obstruction protection, prompts, and sound consistent.
  Record the reason for any deliberate exception.
- Keep each recurring mechanism's common behavior in one implementation, with
  instance differences expressed as data/configuration. Apply shared fixes and
  improvements across its instances and cover the shared behavior with tests.
- Keep items and enemies readable without crowding the environment: opaque,
  depth-tested shapes, restrained shared pickup markers, and enemy labels only
  when aimed at. Reuse the pickup presentation for future item types.
- Consider future extension when adding features: maintain clear boundaries
  between targeting, state, simulation, collision, rendering, and sound events.
  Extend the common interaction path as new mechanism types are actually added;
  keep abstractions proportional to concrete needs and preserve work budgets.
- Mouse movement controls the view and left click attacks on Windows. Q has no
  attack binding. Preserve `--keyboard-look` (arrows/Enter) for accessibility and
  platforms without mouse capture. Keep E as the shared environment interaction key.
- Ask the user for approval before major architectural changes. Routine additive
  features within the existing engine do not require another approval.

## Required Sound Feedback

Every future gameplay feature, player action, and environmental interaction must
include corresponding sound effects or an appropriate ambient layer. Implement
audio with the feature, rather than deferring it. Emit semantic `GameEvent`s,
register matching cues in `sound.py`, and test event coverage. Preserve mute,
volume, pause, silent headless modes, and graceful operation without an audio
device. Keep synthesis/device I/O off the simulation and rendering paths. Native
playback uses an isolated process, device-completion callbacks, primed buffers,
and click-free fades. Let device backpressure pace real output; use the wall-clock
cap only for sinks returning buffers immediately. Preserve bounded mixing and
queue-level health checks. Use original or appropriately licensed audio.

## Persistent Context Workflow

- Before every new development task, read [PROJECT_STATUS.md](PROJECT_STATUS.md),
  then relevant sections of `README.md`, source, and tests. Follow the latest
  user instructions and verify documentation against the implementation.
- After significant work, update `PROJECT_STATUS.md` with completed/in-progress
  work, validation results, bugs, next steps, and the review date.
- Record important design decisions with their reasons, discoveries, and exact
  files or commands needed to resume unfinished work in a new Codex session.
- Keep stable objectives and conventions here; keep changing development state
  in `PROJECT_STATUS.md` and user-facing instructions in `README.md`.
- Keep documentation accurate and concise. Remove stale statements, distinguish
  verified facts from proposals, and never invent progress or approved features.

## Project Structure & Module Organization

`main.py`, `python -m ascii3d`, and Windows `run.bat` launch the application.
Source lives in `ascii3d/`:

- `app.py`: CLI and simulation/frame loop.
- `world.py`, `player.py`: map/materials, collision, movement, and water current.
- `renderer.py`, `scenery.py`: voxel ray casting, HUD/map, depth-tested grass, wind.
- `geometry.py`, `trees.py`: shared projection/strokes and rounded tree rendering.
- `targeting.py`: shared view rays and solid-cylinder targeting queries.
- `terminal.py`: platform keyboard/mouse input, capture and terminal lifecycle.
- `doors.py`, `door_render.py`: shared swinging panels, collision, and rendering.
- `events.py`, `sound.py`: gameplay feedback events, original Foley, and audio output.
- `audio_output.py`, `audio_process.py`: native buffers and isolated playback.
- `soundscape.py`, `audio_check.py`: shared environmental sources and diagnostics.
- `sound_surfaces.py`: deterministic ground-contact classification for Foley.
- `map_expansion.py`: central castle, surrounding grounds, landmarks and standard doors.
- `combat.py`, `combat_render.py`: single-item holding, sword/staff attacks,
  fireballs, passive targets and shared
  depth-tested item/enemy rendering; check `PROJECT_STATUS.md` for validation.

`tests/` contains `unittest` suites. Generated PNG/WAV/text previews are temporary
review artifacts; remove them after review unless the user asks to keep them.

## Build, Test, and Development Commands

Python 3.10+; no build step or external packages. Run from the repository root:

```powershell
python main.py                          # Courtyard
python main.py --outside                # River meadow
python main.py --snapshot               # Plain-text frame; no live terminal
python main.py --outside --benchmark 120 # Rendering performance
python main.py --demo --frames 100       # Interactive smoke test
python main.py --audio-test             # Audible river/effects and queue health
python -m unittest discover -s tests -v  # Test suite
python tools/benchmark.py --frames 60 --compare benchmarks/vegetation-current.json
python tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/castle-milestone-before-live.json
```

## Coding Style & Naming Conventions

Use four spaces, `snake_case` modules/functions, `PascalCase` classes, and
`UPPER_CASE` constants. Follow existing type hints, dataclasses, and PEP 8.
No formatter or linter is configured.

## Architecture Constraints

X/Y form the ground plane; Z is height. Keep collision independent of rendering.
Preserve fixed-step physics, simulation-time animation, seeded scenery, correct
occlusion, nonblocking input, and terminal cleanup. Pause/help must freeze both
movement and scenery. Benchmark rendering-loop changes.
Keep vegetation work bounded by visibility/detail budgets and retain exact-ray
comparison tests. Edit voxels through `World.box()` to invalidate render caches.
Compare both mean and p95 timings on the same hardware before updating baselines.
Use the audio-enabled benchmark for gameplay changes when a Windows output
device is available. E is reserved for interaction; mouse look is the Windows
default and arrow look is available in explicit keyboard mode.

## Testing Guidelines

Use `test_*.py` files and `test_*` methods. Cover changed behavior, especially
collision, jumping, water, animation continuity, and occlusion. Windows input
tests need a live Windows console and otherwise skip. Check indoor/outdoor
visuals for rendering changes. No coverage threshold is configured.

## Commit & Pull Request Guidelines

Follow available Git conventions; otherwise use imperative subjects such as
`Add riverbank collision tests`. PRs should explain changes, reference relevant
issues, report validation, and include screenshots or benchmarks where applicable.

- After the user confirms an implementation is successful, commit all changes
  for that implementation. Treat this as an ongoing repository workflow.
- Perform requested reverts and undos through Git so the change history records
  the reversal; do not manually erase committed work.

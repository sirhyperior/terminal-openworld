# Project Status

Last reviewed: **2026-11-05**. Read this before development, then
[AGENTS.md](AGENTS.md) and relevant source/tests. This is the session handoff.

## Current State

MONOLITH is a playable white-on-black ASCII terminal exploration sandbox using
Python 3.10+ and the standard library. Verified with Python 3.14.4 on Windows.
Run `python main.py` or `python main.py --outside`. There is no build step,
package dependency or CI configuration. Git was initialized on 2026-11-05 and
the starting project state was committed; see `AGENTS.md` for the ongoing
commit-after-success and Git-based undo workflow.

The saved surface-audio, map-expansion and sword/dummy modules are now integrated
into live play. The live map is **65x86x10** with five standard swinging doors,
two bridges, northern ruins, watchstones, an eastern lodge and gravel trails.
Original fortress geometry and spawns remain intact: indoor `(14.5,4.5,1)` and
outdoor `(16.5,34.5,1)`.

**Gameplay integration and visibility changes are implemented and tested.
The frame-time acceptance check remains open. Do not claim preserved FPS or
replace approved benchmarks.** See validation/performance below.

## Completed Playable Features

- Perspective voxel ray casting, textured surfaces, depth buffering and pitch.
- WASD movement, Shift sprint, Space jump, arrow turning, cylinder collision,
  wall sliding, gravity, head collision and obstacle landing.
- Courtyard/corridors/gallery, crates, arches, meadow, rounded trees, wind-reactive
  short grass, flowing river, wading/current and two wooden bridges.
- Five E-operated standard doors with shared aim/reach/occlusion checks, prompts,
  animation, collision, obstruction protection and sound.
- E collects the iron sword near either spawn; the two placements represent one
  inventory item and disappear together. Q attacks and no longer turns left.
- A passive 3-HP training dummy at `(20.5,36.5)`: 2.55-unit attack reach,
  0.48-second cooldown, 0.30-second swing and four-second reset. Aimed names/health
  appear within ten units when the body has a clear line of sight.
- Pause/help/too-small terminals freeze combat and scenery. R resets the player
  while preserving inventory, door state and target state. Demo interaction now
  handles both doors and pickups without assuming every target is a door.
- Help, pause, map, reset, focus-loss pause, resizing, terminal cleanup, snapshots,
  finite demos, viewport limits and rendering benchmarks.
- Original synthesized movement/door/UI/combat sound, wind and stereo river
  ambience; six surfaces (stone, grass, wood, water, gravel, metal) have distinct
  footsteps and landing cues. Ground contact includes raised crates/bridges and
  wooden door tops. Generic `land` events carry optional surface metadata.
- F mute, CLI volume/mute, WAV export, no-device fallback and silent headless
  modes remain. Native audio still uses an isolated process, primed completion-
  driven buffers, fades, bounded mixing and device recovery.

## River Animation Orientation Fix

The user reported river lines remaining parallel to terminal X while turning.
World-position sampling was already present, but the near and distant shaders
always chose horizontal `-`, `~` or `=` glyphs.

- `renderer._river_ripple()` now makes elongated streaks in river coordinates
  (`x - 0.9 * simulation_time`, `y - river_center(x)`). They follow bends and
  advect downstream without camera-dependent phase or wall-clock animation.
- Water strokes use the perspective derivative of `World.current()` at each
  visible hit, including yaw, pitch, screen position and terminal cell aspect.
  `_flow_glyph()` chooses horizontal, vertical or diagonal strokes; distant
  simplification retains direction. Foam uses small isotropic glints.
- Only directional streaks calculate current/projection; plain points and foam
  skip that work, and water skips solid-material UV/lighting setup. Collision,
  the water level, depth/bridge occlusion and existing river audio are unchanged.
- Seven new outdoor regressions cover camera rotation, convergence, distance,
  actual current direction, advection around bends, longitudinal streak shape,
  frozen-time repeatability and wall occlusion. The complete native-console
  suite passed **153/153**, zero skips, including exact-ray comparisons.
- Added `river_diagonal` and `river_upstream` extra benchmark views (15 total).
  Inspected indoor/outdoor and along/across/oblique river text views; no previews
  were retained. README explains the world-aligned streaks.
- The first full measurement is preserved as `benchmarks/river-flow-initial.json`:
  large stalls included indoors (105.09 ms mean) and audio (3 underruns, 759.1 ms
  maximum refill interval). Do not hide that failure or attribute it solely to
  water work. A subsequent isolated native `--audio-test` passed with 244 buffers,
  zero underruns/recoveries and a 69.2 ms maximum refill interval.
- An audio-off interleaved old/new shader check before the final work-skipping
  optimization isolated about 1.8-4.0 ms added mean cost in water-heavy views;
  indoors stayed approximately 18.3/18.6 ms. The optimized full measurement is
  `benchmarks/river-flow.json`, compared with `sword-hit.json` at matching
  60-frame/120x40/audio settings. All 13 comparable scenes passed the 15% mean
  and p95 limit; the two new views have no previous comparison. River measured
  29.53/35.60 ms mean/p95, oblique 27.39/30.42 ms, upstream 25.14/28.44 ms.
  Final playback had zero underruns/recoveries and a 96.2 ms maximum refill
  interval. Historical milestone-wide baseline acceptance remains open.

```powershell
python -B -m unittest discover -s tests -p test_outdoors.py -v
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/sword-hit.json --save benchmarks/river-flow.json
```

## Distinct Sword Impacts on Enemies

The user requested a different sword sound on enemy contact. A `sword_hit` event
already existed, but competed with a full-volume swing. Contact feedback is now
more distinct while keeping the same combat targeting/damage rules.

- `sound.synthesize()` gives `sword_hit` a sharp crack, solid impact body and
  brief metallic blade bite, with the existing three variations and 0.34-second
  duration. Its loudness target is -18 dBFS, subject to the existing peak limit.
  Signal checks found 1.26-1.32x the air-swing RMS and 98% of hit energy in the
  first 80 ms; the swing retains its slower airy envelope.
- `CombatState.attack()` emits a 0.55-strength `sword_swing` alongside confirmed
  hits, and the full 1.0-strength whoosh on misses. `sword_hit` stays positioned
  at the enemy. Cooldown, reach, aim, line of sight and damage are unchanged;
  blocked/out-of-range/unarmed attacks do not gain hit feedback.
- `Mixer.add()` gives confirmed impacts priority 2, alongside doors, so normal
  whooshes/footsteps cannot displace them in a full queue. The eight-voice limit,
  bounded release tails, mute/volume/pause, headless modes and isolated output
  architecture remain.
- Three new regressions cover hit/miss event routing and relative whoosh gain,
  impact loudness/attack envelope, and impact retention at the voice limit.
  The complete native-console suite passed **146/146**, zero skips.
- A temporary guarded native probe used real `CombatState.attack()` events and
  meadow ambience: miss, enemy hit, miss, enemy hit. It confirmed event strengths
  1.0/0.55 for miss/hit whooshes and dummy HP 3 -> 1. Playback completed with
  77 buffers, zero underruns/recoveries and a 62.4 ms maximum refill interval.
  The probe was removed; no preview audio files were retained.
- `benchmarks/sword-hit.json` records the audio-enabled 60-frame/120x40 run with
  all 13 scenes. Mean/p95 comparisons passed for the six scenes shared with
  `door-creaks.json`; the seven extra scenes were measured without a matching
  comparison. Training averaged 24.77 ms, p95 27.75 ms. Audio had zero underruns/
  recoveries and a 92.3 ms maximum refill interval. This does not approve a new
  baseline or resolve the historical milestone-wide frame-time acceptance.

Restart the running game to load the prewarmed hit clips. Validation commands:

```powershell
python -B -m unittest discover -s tests -p test_combat.py -v
python -B -m unittest discover -s tests -p test_sound.py -v
python -B main.py --audio-test
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/door-creaks.json --save benchmarks/sword-hit.json
```

## Door Creak Replacement

The user requested wooden creaks instead of the whirring door sounds. Replaced
the opening/closing pitch-sweep recipe and the blocked-door thud in `sound.py`.

- `_door_creak()` is the shared synthesis model for `door_open`, `door_close`
  and `door_blocked`; `_DOOR_STRAINS` configures their strain/release timing.
  Irregular friction impulses excite three damped wood/hinge resonances with
  short rough scrape layers and a subdued latch/stop. The old repeating sweep
  and door-specific short echoes were removed.
- All three cues now have three deterministic variations, prewarmed in
  `SoundBank`. Existing durations (0.70/0.65/0.18 seconds), loudness target,
  semantic events, spatial mixing, eight-voice limit and native playback
  architecture remain. All five doors use these shared cues; door mechanics,
  mute/volume/pause and headless behavior are unchanged.
- Two new sound regressions verify internal friction/release gaps (rather than
  a continuously sustained tone), three distinct/reproducible variants per cue,
  clean endpoints and safe peaks. The full suite passed **143/143**, zero skips,
  in a live Windows console. Signal checks verify the intended structure, not
  the user's subjective perception on their speakers/headphones.
- `--audio-test` now also exercises `door_blocked`. Native playback passed:
  244 buffers, zero empty-queue events/recoveries, 65.2 ms maximum refill interval.
  No audio previews were retained, following the folder-cleanup preference.
- The audio-enabled six-scene measurement is saved in
  `benchmarks/door-creaks.json`, compared against `trees-near-after.json` with
  matching 60-frame/120x40/platform/audio settings. It is a measurement, not an
  approved replacement baseline. River still flagged +15.9% mean/+22.7% p95;
  the other five scenes stayed within 15%. Audio had zero underruns/recoveries
  and a 64.2 ms maximum refill interval. Existing graphics acceptance remains open.

Restart a running game to load the new prewarmed clips. To verify:

```powershell
python -B -m unittest discover -s tests -p test_sound.py -v
python -B main.py --audio-test
python -B tools/benchmark.py --frames 60 --audio --compare benchmarks/trees-near-after.json --save benchmarks/door-creaks.json
```

## Close-Tree Disappearance Fix

The user reported trees disappearing when approached. Reproduced with a downward
pitch of -0.35: an isolated tree rendered 364 cells at distance 1.0, then zero at
0.75 and closer. Its root/fork projections straddled the camera's near plane;
the entire line was discarded when either endpoint could not be projected.
Foliage also disappeared from inside a crown because only the entry intersection
was considered, even when that intersection lay behind the camera.

- `Camera.stroke_world()` clips tree trunk/branch segments against the near
  plane before projecting them. It then clips projected segments to a padded
  viewport with perspective-correct depth, preserving continuous close lines
  and the existing 512-sample stroke limit. Grass keeps its projected fast path.
- `Camera.NEAR` shares the existing 0.18-unit camera cutoff. `Trees._crown()`
  uses the forward exit surface when the entry is clipped or behind the camera.
  Voxel/door occlusion and the three-times-view-pixels crown budget remain.
- Six new vegetation checks cover close approaches from all four sides while
  looking up/down, analytic exit depths from inside a crown, foreground
  occlusion, near-plane crossing, a jump into the live canopy and hidden trees
  behind the camera. Inspected indoor/outdoor and both close-up text views;
  no preview files were retained.
- `--extra-scenes` now includes `tree_close` and `tree_canopy` (13 total cameras).
  Exact-ray comparison tests include these views as well.
- Matched 60-frame, 120x40, audio-enabled measurements are in
  `benchmarks/trees-near-before.json` and `benchmarks/trees-near-after.json`.
  All original six scenes stayed within 15% of this fresh pre-fix measurement.
  The complete 13-scene comparison still failed for lodge, east bridge,
  watchstones, training and inside-canopy views; do not describe it as a full
  performance pass. Audio had zero underruns/recoveries in both runs, with
  maximum refill intervals 63.8/67.3 ms respectively.
- An interleaved, audio-off trunk-clipping probe showed negligible added cost in
  ordinary expansion views. A separate 60-frame interleaved probe isolated the
  corrected crown exit rendering: inside-canopy mean 13.40 -> 16.93 ms, p95
  17.58 -> 21.71 ms, with clipped trunks in both versions. The additional cost
  draws previously missing foliage and remains within the fixed sample budget.
  These probes do not replace the audio-enabled comparison or historical
  references. The existing milestone-wide frame-time acceptance remains open.

Resume/render-validation commands:

```powershell
python -B -m unittest discover -s tests -p test_vegetation.py -v
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/trees-near-before.json --save benchmarks/trees-near-after.json
```

## FPS Counter Check

The user requested confirmation that the terminal counter is accurate and live.
It was already refreshed per frame and included cap waits/terminal output, but
its exponential average of instantaneous FPS could overreport uneven frames
(alternating 25/50 ms frames averaged to 30 FPS instead of 26.67).

- `app.FrameRateCounter` now counts completed start-to-start intervals over a
  rolling window of roughly one second, using the existing monotonic clock read.
  This includes input, simulation, render, terminal write/flush, scheduler stalls
  and cap waits. FPS timing is separate from the 100 ms physics catch-up clamp.
- The HUD refreshes every frame, rounded to an integer; the initial 0 indicates
  that no complete frame has yet been timed. It also remains live while paused.
- Five new checks in `tests/test_game_loop.py` cover steady/uneven rates, long
  stalls, response to rate changes and actual app-loop cap/output accounting.
- A native, audio-enabled 45-frame run at `--fps 20` ended at **20 FPS** in the
  HUD; independently timed terminal writes measured **20.15 FPS** across that
  short run. The temporary probe needed a Windows multiprocessing main guard;
  the corrected probe passed and was removed. Counter overhead was measured at
  0.312 microseconds/update with 41 retained timestamps at 40 FPS.
- This HUD-only change does not resolve or replace the existing renderer
  benchmark failure below. README now distinguishes live and headless FPS.

## Folder Cleanup

On 2026-11-05, the user requested removal of unnecessary previews. Removed the
generated `previews/` directory (PNG/text frames and pose/frame JSON), root image
and WAV previews, and Python bytecode caches. README no longer links to removed
artifacts; audio previews can still be exported with `--sound-preview`.
Source, tests, launchers and benchmark records were retained. Keep future review
exports temporary unless the user asks to preserve them.
Initial cleanup removed 40 generated files (2.79 MiB), including all 16 preview
assets. SHA-256 checks confirmed all 42 source/test/tool/benchmark files unchanged;
indoor/outdoor `-B --snapshot` checks passed at 120x40 and README links resolve.
Bytecode caches recreated by a concurrent Python run were removed again; normal
Python runs may regenerate these ignored caches.

## Visibility Request

The user asked for items and enemies to stand out without obscuring the setting,
and reported that the sword blade was see-through.

- `geometry.Camera.triangle()` fills opaque faces with perspective-correct depth
  and viewport clipping. Both pickup and held sword blades now have filled faces.
- `combat_render.py` gives pickups a small shared ground diamond and one glint.
  Preserve/reuse this local presentation when future item types are added; keep
  names/instructions in the shared E prompt rather than permanent floating text.
- The dummy has an opaque faceted straw torso and head, readable from four sides.
  Its name/HP remains aim-only. All geometry and markers respect scene depth.
- The fixed support stays visible and retains its standing collision cylinder
  while the straw body is down. This prevents a four-second reset from spawning
  inside the player. Further play review can revisit this documented choice.
- Sword/pickup/dummy screenshots and eight text frames were inspected during
  integration, then removed in the user-requested folder cleanup. They were
  review artifacts, not runtime assets.

## Important Implementation Boundaries

- `World.combat` defaults to an independent empty `CombatState` for fixture worlds;
  only `build_world()` installs the starter sword placements and training dummy.
- `targeting.py` shares normalized view rays and finite cylinder intersection
  between interaction/combat/trunk occlusion. `World.line_clear()` uses exact
  voxel traversal plus analytic door-panel/trunk checks. E targeting returns
  original target objects and dispatches by their concrete type. A door ignores
  its own leaves only while being operated; other targets see them as opaque.
- `app.py` queues Q presses until a fixed physics step, advances combat only when
  active, and routes its returned semantic events to the unchanged audio backend.
- `events.py` appends `surface: str | None = None` after the original positional
  fields. `Player` queries `sound_surfaces.surface_kind()` only on steps/landings.
- `world.py` calls `map_expansion.expand_world()` after original construction and
  doors; its area names defer to extension landmarks first. Full-map route tests
  now include traversal from the original spawn and the second bridge.
- `renderer.py` merges clear **2x2 terrain columns** into cached empty rectangles
  at each integer height. This extends the existing empty-space optimization;
  it does not approximate rays or reduce drawing distances. Downward rays use
  local terrain height; completed hits/sky exits avoid rebuilding DDA crossings.
  The finer columns allow bridge interiors to skip past nearby thin railings.
  `World.box()` revisions invalidate all these bounds.
- Keep X/Y ground, Z height, 120 Hz physics, seeded scenery and simulation-time
  animation. Live render cap is 40 FPS, viewport 4,800 cells, maximum 180x64.
  Grass remains chunked with radius 14, candidates <= view pixels / 3; tree
  intersection work remains <= 3x view pixels. Recreate Renderer on tree changes.
- Keep standard-library dependencies and shared Door/Panel behavior. No major
  architecture change was requested or approved. Ask before undertaking one.

## Validation

Latest complete suite: **153/153 tests passed, zero skipped**, in a live Windows
console on Python 3.14.4:

```powershell
python -B -m unittest discover -s tests
```

New tests cover collection/one-item inventory, reach/aim/wall/door/trunk occlusion,
exact short corner crossings, cooldown, hit/miss/down/reset sound coverage, dummy
collision, Q without turning, real app-loop pause/help/reset/event dispatch, demo
pickup handling, depth/labels/opaque blade interiors/four-sided dummy readability,
minimum-size help, complete-map connectivity and six-surface Player metadata.
Exact-render comparisons cover all fifteen benchmark cameras and partial
chunks/raised surfaces at multiple pitches. Native keyboard tests require a live
console; a piped run skips six tests as expected.

Also passed:

- Indoor and outdoor snapshots; reviewed sword/dummy PNGs and extension text
  frames. Frame outputs remain rectangular printable ASCII.
- `python -B main.py --demo --frames 100` and the same with `--outside`, each
  completed with native audio and terminal cleanup.
- `python -B main.py --audio-test`: 244 buffers, **0 empty-queue events,
  0 recoveries**, 69.2 ms maximum refill interval on the latest standalone check.
  The diagnostic plays an
  11-second river/surface/door/combat sequence. These are queue-health observations,
  not a perceptual recording of the user's speakers/headphones.
- Verified WAV export with all current cues and ambient layers; the generated
  preview was removed during cleanup. Regenerate when needed with
  `python -B main.py --sound-preview effects.wav`.

## Performance: Acceptance Still Open

`benchmarks/milestone-start.json` remains the fresh pre-milestone reference from
this hardware: 60 frames/scene, 120x40, audio on. Its means/p95s in milliseconds:
indoors 14.32/17.90, courtyard 14.77/17.89, meadow 23.10/27.87, close grass
22.42/27.17, bridge 22.57/27.74, river 21.62/25.68. It had zero underruns and
recoveries. Historical `doors-audio-current.json`, `vegetation-current.json` and
`audio-repair-measurement.json` remain unchanged; the historical failed comparison
has not been erased or promoted to an approved reference.

Run and inspect:

```powershell
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/milestone-start.json --save benchmarks/milestone-integrated.json
```

`milestone-integrated.json` records the integrated renderer, **not an approved
replacement baseline**. The 15% mean/p95 comparison still fails. Timings varied
substantially between runs, including indoors. Initial expanded-map outdoor means
were roughly 49-59 ms. Empty-rectangle/early-exit optimization reduced several
measured scenes toward 25-31 ms; subsequent runs were variable and still failed.
Do not select a favorable run to claim the threshold passed.

Profiling identified voxel traversal on newly extended clear sightlines, followed
by conservative column bounds around bridge rails. In an interleaved same-process
probe, 2x2 bounds reduced bridge median from 29.42 to 22.66 ms versus 4x4 merged
bounds, river from 25.48 to 23.97 ms, close grass from 17.25 to 16.31 ms; indoors
changed 12.90 to 13.54 ms. This supports the optimization but does not substitute
for the full matched audio-enabled acceptance check. All exact-ray tests passed.

`--extra-scenes` adds ruins, lodge, east bridge, watchstones, equipped combat,
close-trunk, inside-canopy, diagonal-river and upstream-river views.
They are measured without historical percent comparisons when absent from the
reference; the original six keep their unchanged comparison. Recent final runs
reported zero underruns/recoveries; `river-flow-initial.json` preserves a stalled
run with three underruns. Consult the JSON for the latest
mean, p95, FPS and queue-health results. Benchmarks exclude terminal output.

## Remaining Work / Resume Here

1. Resolve the remaining matched benchmark failure before claiming preserved FPS.
   Profile `Renderer.scene()` on close grass, bridge, river and the extension
   views; distinguish code cost from timing variability. Keep the 15% threshold,
   exact-ray equivalence and existing vegetation/audio bounds. Do not change the
   baseline or relax the threshold to hide regressions.
2. User play review of pickup/dummy readability, sword feel and fixed downed
   support collision is still useful. The implemented visibility request is
   covered by tests and completed visual review; no further feature scope is
   implied.
3. Enemies remain passive; no player damage, save/load or objective system exists.
   POSIX key holds and Python 3.10 minimum remain unverified (3.14.4 checked).
   Broader audio gaps: device unplug/replug and subjective listening.

No unfinished delegated agents are required. Integration work, tests, benchmark
evidence and resume commands are on disk; temporary review previews were removed.

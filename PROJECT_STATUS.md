# Project Status

Last reviewed: **2026-11-10**. Earlier gameplay checkpoint: `f27e9ff` (2026-11-06).
Read this with [AGENTS.md](AGENTS.md); [README.md](README.md) covers play/controls.
Current checkpoint: wrap up the enormous terrain/floor/visibility expansion at
the user's request on 2026-11-10. Earlier mouse repairs are included and still
await physical play review. User explicitly requested a local Git commit.

## Future Milestones Requested by the User

1. **Use the full terminal screen.** Fill the available terminal area instead of
   centering a viewport constrained by the current 4,800-cell/180x64 limits. The
   user expects more character cells to increase effective image resolution.
   Measure the actual cell dimensions and frame cost; font/cell size still sets
   the available character resolution. Preserve resize, small-window and keyboard
   accessibility behavior. Current caps remain in this checkpoint.
2. **Smooth natural terrain.** Replace the visible Minecraft-like blocky hills
   with smooth, continuous hillside surfaces. The user explicitly rejected the
   current terraced appearance. Design rendering, collision, ground support,
   grass/tree placement, water transitions and Foley together; the existing
   voxel terraces are an interim implementation. Review the required geometric
   architecture before starting that larger change.
3. **Make stair steps smaller.** Replace the current chunky one-unit risers with
   finer steps and comfortable walking transitions. Share stair geometry and
   traversal across landmarks, preserve headroom, guardrails, jumping and
   material-specific contacts, and validate ascent/descent on every flight.
   Current one-unit steps remain in this checkpoint.
4. **Finish performance acceptance.** Preserve the unchanged 15% mean/p95 limits
   and all failed evidence. The latest completed expansion ABBA run passes
   20/24 matched roles; bridge, east bridge, Warden and river diagonal still fail.
   Later local renderer/scenery improvements need a fresh full paired run.

## Expansion Milestones — Checkpoint Progress

1. **World content — implemented:** 512x512x32 within the existing voxel engine;
   original castle hub, terraced highlands/valleys/ravine, connected roads and
   four three-floor landmarks with balconies and rooftops. Nine focused tests
   pass, including continuous entrance-to-roof walks and all 12 stair flights.
2. **Scenery and sound — implemented:** nearby grass uses a 128-chunk cache at
   existing density; grass/trees follow actual elevation. Live ambience follows
   the player's floor/roof. Seven new scenery and 18 vegetation tests pass.
   Terrain steps emit registered surface-specific Foley; sound controls remain.
3. **Visibility/rendering — implemented, acceptance incomplete:** clearer floors,
   local terrain map and HUD elevation; bounded overlapping row/column air
   volumes, room skips and conservative sky bounds retain exact voxel hits.
   Crown spans and delayed grass wind avoid hidden work. No range/detail or
   acceptance thresholds were reduced. The user wants smooth hills/finer stairs
   in future, so current terraced geometry is not final visual acceptance.
   The final checkpoint also includes early sky rejection, signed reciprocal
   arithmetic and a large-enemy depth prepass guarded by conservative foliage
   work. Focused reference tests passed; the final combination has not received
   another full paired audio benchmark.
4. **Integration — checkpoint validation:** surface queries, safe one-unit
   stair traversal, region starts and elevated benchmark scenes are implemented.
   First native suite: 298 tests, one repeat-build failure from road painting
   over three chapel floor cells. That defect is fixed; the unchanged regression
   and nine terrain tests pass. Final native-console suite: **316 tests passed,
   zero skips**, in 96.240 s. Performance acceptance remains open.

The starting source was frozen in temporary `terrain_before_tmp/` for matched
controls; this temporary source tree is removed after checkpoint review.
`benchmarks/terrain-before-live.json` retains the initial 24-scene,
60-frame/120x40/live-audio measurement (zero underruns/recoveries). Substantial
timing variability remains; contemporaneous paired comparisons are required.
`benchmarks/terrain-interleaved-first.json` retains the first paired ABBA run:
19/24 scenes exceed the unchanged 15% mean/p95 threshold. Diagnostic function
counts in `terrain-profile-first.txt` confirm excess ray traversal, especially
bridge/Warden/great-hall views. This is a failed result, not acceptance.
`terrain-interleaved-optimized.json` failed 8/24; the latest completed
`terrain-interleaved-horizon.json` failed 4/24, with zero audio underruns or
recoveries. Its ten new terrain/floor/walking scenarios measured means
5.475–19.017 ms and p95 6.450–20.491 ms. These headless measurements exclude
terminal writes/cap waits and do not establish a universal live FPS guarantee.

## Open Issues and Priorities

1. **Mouse fix needs physical play review in the user's tabbed Windows Terminal.**
   Both reported symptoms (visible center cursor and failed pause release) have
   a reproduced Win32 cause and a 2026-11-10 regression fix. An empty confinement
   rectangle moved the pointer outside the helper and made subsequent release
   calls fail with access denied on this desktop. Positive-area confinement
   inside a slightly larger helper fixes the native probe. Native desktop cursor
   identity/hit testing and three capture/release cycles now pass, along with
   console P dispatch and app pause/help regressions. This does not constitute
   physical confirmation in the user's host. Earlier missed-click behavior still
   has no captured user-device trace. Keep `--keyboard-look` available.
2. **Earlier castle-wide performance acceptance remains open.** The Warden
   increment passed a separate matched check, not a whole-project FPS guarantee.
   Old/new controls vary for an unverified reason. Profile gatehouse, water and
   combat without reducing detail or relaxing the 15% mean/p95 limit. Retain
   interleaved wall-time controls and failed evidence; the
   [benchmark index](benchmarks/README.md) identifies relevant reports. The
   earlier mouse-release render/audio comparison failed all 24 historical scene
   limits; mouse modules were outside its execution path. The expansion has its
   separate contemporary comparisons above; no whole-project FPS acceptance is
   claimed.
3. Play review remains for navigation, swaps, Warden combat and audio. Physical
   speakers, device unplug/replug, POSIX held keys and minimum Python 3.10 remain
   unverified. No save/load or objectives are implemented.

## Implemented State

Standard-library Python game, tested on Windows/Python 3.14.4. The expansion
source builds a 512x512x32 world (8 MiB of voxel cells). The original 112x112 hub
retains its four-tower castle, gatehouse, hall, cloister, training yard, garden,
ruins, watchstones and lodge. Four bridges cross the river; seven doors share
panels and E interaction. West steps reach the cloister roof/west wall; a complete
castle roof circuit is not verified. `map_expansion.py` owns original placements:

- Indoor/outdoor starts: `(55.5,30.5,1)` / `(55.5,20.5,1)`, facing north.
- Sword aliases: `(55.5,32.5)` / `(55.5,22.5)`, one shared item.
- Staff: `(53.5,103.5)` in northern ruins; dummies at `(42.5,48.5)`,
  `(46.5,48.5)`, `(50.5,48.5)`.
- Warden home: `(18.5,103,1)`; territory `(12,99)-(24,106)`.

`terrain.py` owns heights (1–20), gravel routes, Splitstone Ravine and four
configurations of one shared three-floor building, each with reachable roof:

- Ridge Hall `(136,40)-(160,64)`: floors Z5/10/15, roof Z20.
- Northern Keep `(66,190)-(92,216)`: floors Z7/12/17, roof Z22.
- Hill Observatory `(214,178)-(238,202)`: floors Z10/15/20, roof Z25.
- Far Citadel `(382,372)-(412,402)`: floors Z12/17/22, roof Z27.

`--region ridge|keep|observatory|citadel` starts at the selected entrance; R and
defeat use that same entrance. Grounded movement climbs one-unit terrain and
masonry steps with clearance, emitting surface-specific `terrain_step` feedback.
Crates, wooden/metal guardrails and doors retain their collision/jump behavior.
The large world uses a cached 96x96 local map; the HUD includes elevation.

One held item: swaps drop the same previous instance on supported, reachable
ground. Sword/staff deal one damage. Staff fireballs have finite range and no
ammo limit; no splash/world destruction. Dummies have three HP/four-second
resets and retain solid supports while down.

The four-HP Warden acquires players inside its territory within 7.5 units/clear
sight, pursues with local steering, and returns home when they leave. Its warned
radial slam deals two health; leaving reach, jumping above hit height or breaking
sight can dodge. Respawn waits 12 simulation seconds, then requires a clear,
supported home without player overlap. Dead Wardens are invisible/non-solid.
Shared tuning is in `EnemyBehavior`.

The HUD shows ten-point health. Defeat/R restores health at the selected entrance
while preserving items, doors and enemy state. Empty E gives quiet feedback
without an instruction notice. Pause/help/small viewports freeze physics,
scenery, AI and projectiles. Meadow wind and gameplay actions have synthesized
feedback. Detailed controls/weapon tuning are in README/source.

## Technical Handoff

- **Input:** capture clicks do not attack. Bind modern hosts from a fresh
  own-console click, physical button state and foreground bounds; focus records
  alone are insufficient. Retain the verified HWND across pause/blur. Activation
  flushes stale records/resamples held keys; mouse delta applies once per rendered
  frame, independently of 120 Hz physics. Lifecycle code requests release on
  pause/help/blur/minimize/small viewport/exit/exceptions. `ExitStack` requests
  release before audio drains. Failed clip restoration retries once per call,
  keeps the original clip and blocks recapture until cleanup completes; foreign
  clip changes cancel that retry. Helper teardown errors still run restoration.
  Moving the game tab between terminal windows requires restart or keyboard mode.
  The Raw Input helper is a non-activating, 3x3 topmost popup with a private
  transparent cursor and a positive-area 1x1 clip inside its margin. It is
  deliberately **unowned by the terminal**: cross-thread ownership implicitly joins input
  queues and can stall the host. No global cursors or host input queues change.
  Warp into the helper before confinement; never use an empty clip rectangle.
  Read back the actual clip for release ownership. Registration/pumping is
  bounded; teardown unregisters/hides the helper and attempts clip restoration.
  Acquisition/resize failure cleanup has regression coverage. An explicit
  keyboard fallback notice covers unavailable desktop access. Old thread-local
  ShowCursor/recentering remains only in the compatibility/test path.
- **State/collision:** fixture worlds have independent empty `CombatState`;
  `build_world()` installs gameplay. Starter aliases disappear together; drops
  never resurrect aliases and swaps preserve cooldown. `World.interact()` shares
  targeting and returns event lists. `CombatState.update(dt, world, player=None)`
  receives the live player. `Enemy.behavior=None` preserves dummies; moving enemies
  exclude only themselves through `World.collides(ignore_enemy=...)`. Bounded
  steering/support checks avoid map-wide pathfinding. `Player.take_damage()` owns
  health/events; app owns entrance respawn.
- **Rendering:** projectiles sweep shared `World.solid_hit()` voxel/panel/trunk
  queries; water is transparent. Fireballs/bursts each cap at eight. Warden planar
  `Camera.quad()` fills retain a near-plane triangle fallback and reference tests.
  Terrain skips use conservative 2x2/AIR-only volumes with ordinary DDA at
  ambiguous corners. Invalidate via `World.box()`; recreate Renderer if trees change.
  Surface queries cache top voxel/material per queried column and invalidate on
  box edits. Trunk sight/projectile candidates use the smaller of the population
  or a radius-safe local cell range; inserted tree radii maintain its bound.
  Interactive static cache and river index preparation occurs during loading,
  before terminal capture or live audio starts.
- **Budgets:** ray depth 48, 110 traversal iterations; live viewport 4,800 cells,
  maximum 180x64. Grass: inspect at most 81 nearby chunks, retain at most 128,
  radius 14, candidates <= pixels/3; tree crown
  samples <= 3*pixels. Map backgrounds cache by revision/viewport. River audio
  queries 8x8 water buckets within radius 18, with full-scan equivalence tests.
- **Audio:** prewarmed synthesis/isolated native playback stay off gameplay paths.
  Completion callbacks pace three primed 1,024-frame buffers; mixing caps at
  eight voices. Preserve fades, queue health, mute/pause/volume/no-device behavior.
  Player hurt/defeat/respawn cues stay centered across queued listener teleports.

## Validation

Expansion checkpoint (2026-11-10): **316 native-console tests passed, zero skips**
with `MONOLITH_DESKTOP_TESTS=1`, workspace TMP/TEMP and Python 3.14.4. This includes
all terrain/stair routes, elevated scenery, scalar crown references, exact voxel
ray cases, gated combat-prepass equivalence/fallbacks, region reset, sound and
the real desktop cursor capture/release regression. Temporary previews/probes
and caches are removed after review; benchmark failures/diagnostics are retained.
The final `--region ridge --demo --frames 100` smoke exited 0 with live sound
and restored terminal state after entering Ridge Hall at Z5.
The latest full performance run remains the 20/24 pass described above; final
early-sky/scenery/signed-inverse/gated-prepass changes are not yet accepted by a
new complete live-audio comparison. Continue from the recorded future milestones.

Mouse repair (2026-11-10): **274 native-console tests passed, zero skips**, with
`MONOLITH_DESKTOP_TESTS=1`, Python 3.14.4 and workspace-local TMP/TEMP. This includes
actual global cursor-handle/hit-test checks and three real capture/release cycles,
native P console records, pause/help through the app, transient restoration
failures and foreign clip ownership. The snapshot command also passed. Detailed
failed-probe evidence, repaired measurements and limits are recorded in
[benchmarks/mouse-capture-2026-11-10.md](benchmarks/mouse-capture-2026-11-10.md).
The first piped suite had a WAV-export permission error with the sandbox's
default temporary folder; the documented workspace TMP/TEMP setting resolved it.
Native input and clipping require desktop access outside that sandbox.
After review, the 18 native mouse-capture tests passed again with normalized
clip/z-order recovery coverage and checked emergency test cleanup.
The 100-frame native-console demo exited successfully with live sound and
completed terminal cleanup.

`benchmarks/mouse-release-audio.json` (2026-11-10): 24 scenes, 120x40/60 frames,
live world Soundscape, zero underruns/recoveries and 78.2 ms maximum refill
interval. Compared with `mouse-input-audio.json`, mean/p95 exceed the unchanged
15% limits in all 24 scenes (largest increases 105.4%/143.6%, great hall).
This failed report is retained; neither report establishes castle acceptance.
The timed code is unchanged by the mouse repair; the reason for timing drift
remains unverified. Desktop capture and terminal output are excluded.

Historical mouse checks (2026-11-07): **267 native-console tests passed, zero skips**,
including packet/button-source regressions, capture cleanup/failure handling,
transparent Win32 cursor masks and class-resource cleanup. The standalone
separate-process GUI probe received raw clicks during injected drags, retained
host keyboard focus and restored the original clip on release. Its automation
pointer overlay is not a reliable visual check of the user's actual OS cursor.
Subsequent user playtesting reported the visible center cursor and failed pause
release above; those historical automated results did not establish a fix.
The sandbox denies
ClipCursor; real capture diagnostics required desktop access, not system changes.

`benchmarks/mouse-input-audio.json`: 24-scene render/audio smoke, 120x40/60 frames,
zero underruns/recoveries, 75.6 ms maximum refill interval. This excludes desktop
input handling and is not a new performance baseline. Earlier results below are
from 2026-11-06.

- Piped suites skip ten console-only input cases; the desktop check also skips
  unless explicitly enabled. Use the native console and opt in for full validation.
  Test success does not replace physical mouse play review.
- Both 100-frame demos restored console modes: 39.38/38.14 FPS at 120x29 against
  a 40 FPS cap, with zero audio underruns/recoveries. The 18-second audio diagnostic
  likewise reported no empty queues/recoveries.
- `benchmarks/watchstone-interleaved.json`: 24 scenes, 120x40, 60 frames/variant,
  per-frame ABBA, three 120 Hz combat steps/frame and shared native mixer with
  each variant's actual Soundscape. Largest mean/p95 increases: **4.23%/11.91%**;
  no underruns/recoveries. Failed phases remain retained. This validates only
  the Warden increment; earlier castle-wide acceptance remains unresolved.

## Resume Commands

Use a native console for input tests. Workspace-local temporary storage avoids
sandbox WAV-export permissions; spawn helpers need an `if __name__ == "__main__"`
guard. Match benchmark frame counts/audio modes; see README for more options.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
$env:MONOLITH_DESKTOP_TESTS='1' # Optional real cursor check; requires desktop access
python -B -m unittest discover -s tests -v
python -B main.py
python -B main.py --keyboard-look
python -B main.py --region ridge
python -B main.py --region citadel
python -B main.py --outside --demo --frames 100
python -B main.py --audio-test
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/castle-milestone-before-live.json --save benchmarks/castle-review.json
```

For the open expansion performance check, reconstruct the frozen control and
use an unused report path as documented in
[benchmarks/terrain-expansion.md](benchmarks/terrain-expansion.md). Start the
future smooth-hill/finer-stair milestone with a shared geometry/collision design;
do not simulate smooth terrain by changing only its visual surface.

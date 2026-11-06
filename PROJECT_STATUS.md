# Project Status

Last reviewed: **2026-11-06**. Read this before development, then
[AGENTS.md](AGENTS.md), [README.md](README.md) and the relevant source/tests.

## Current State

MONOLITH uses Python 3.10+ and the standard library, verified on Windows with
Python 3.14.4. The current milestone adds the first active enemy and player
health to the castle/grounds engine, removes the empty-E instruction notice,
and improves meadow wind. No dependencies or engine rewrite were introduced.
The earlier castle, input and fire-staff implementation remains integrated.

The world is **112x112x12**, versus 65x86x10 before this milestone (2.24 times the
ground area). A central castle has four hollow towers, crenellated curtain walls,
a south gatehouse, great hall, west cloister, training yard and garden. Meadow
surrounds it on all four sides. The northern river, two dry bridges, ruined
chapel, watchstones, eastern lodge and connecting gravel trails remain explorable.

- Indoor spawn: `(55.5,30.5,1)`; outdoor spawn: `(55.5,20.5,1)`, facing north.
- Sword aliases: `(55.5,32.5)` and `(55.5,22.5)`. They represent one item.
- Fire staff: `(53.5,103.5,1)`, on the western timber floor in the northern ruins.
- Three passive dummies: `(42.5,48.5)`, `(46.5,48.5)`, `(50.5,48.5)`.
- One active **Watchstone Warden**: home `(18.5,103,1)`, confined by its body
  radius to watchstones bounds `(12,99)-(24,106)`. It acquires players inside
  those grounds within 7.5 units with clear sight, follows at 1.55 units/second,
  and returns home when they leave. A radial ground slam has 1.35-unit reach,
  a 0.55-second warning and 1.2-second recovery, dealing two health. Leaving
  reach/grounds, jumping above the hit height or breaking sight dodges the slam.
  Four weapon hits defeat it; it respawns at home after 12 simulation seconds,
  waiting for clear, supported ground and no player overlap. Dead Wardens have
  no solid support or lingering body; passive dummy supports stay unchanged.
- The upper HUD replaces the title with a ten-point health bar. Defeat returns
  the player to the selected entrance at full health, retaining items/world
  state; R also restores health. Empty E retains its quiet sound but no notice.
- Bridge decks: `(22,80)-(27,94)` and `(84,80)-(89,94)`, exclusive upper bounds.
- Seven standard doors: south/north/east/west castle gates, hall, ruins and lodge.
- E operates doors and collects/swaps items. Only one item can be held; the
  previous instance drops nearby and can be collected again without duplication.
- Left click attacks on Windows; mouse motion looks/aims. WASD, Shift and Space
  still move, sprint and jump. Q is unbound. `--keyboard-look` enables arrows
  and Enter; this fallback is automatic on non-Windows systems.
- Pause is a small resume/controls/quit card. Help is a separate concise controls
  card. H can open help over pause and return to it; P closes help and resumes.
  Pause/help/small terminals freeze physics, scenery, combat and projectiles.
- R resets the player and health while preserving held/dropped items, doors and target state.
  West steps can be jumped to reach the cloister roof and west wall walk. The
  taller corner towers interrupt the walk; there is no verified full roof circuit.

## Mouse Ownership and Lifecycle

`terminal.Keys` adds pixel `mouse_dx/mouse_dy` and the semantic `attack` press.
`Player.look()` consumes motion once per rendered frame, independent of fixed
physics catch-up. Default sensitivity is 0.0025 radians/pixel; yaw wraps and
pitch retains the existing +/-0.65 limit. Arrow input is filtered in mouse mode.

Windows uses native console button records and Win32 pointer recentering for
continuous turning beyond screen edges. Click the terminal to capture; the first
capture click does not attack. Modern Terminal hosts require a fresh own-console
click with the physical button held and cursor inside the foreground host.
Focus records alone cannot identify a host. Its verified HWND survives pause and
blur rather than silently rebinding to another terminal window.

Capture activation flushes stale console records, then resamples physical held
keys so WASD/Shift remain responsive and held menu/attack keys cannot repeat as
fresh actions. Pause, help, blur, minimize, small viewports, exit and exceptions
release the pointer. `app.py` uses `ExitStack` to release capture before audio
drains, including finite frame limits and rendering errors. Clip/visibility
restoration avoids overwriting a different foreground application's ownership.
Moving the game tab into another terminal window requires restarting or using
keyboard mode. Physical mouse feel still needs user play review; native record
and mocked ownership tests do not measure the user's hand/speakers.

Cursor hiding remains **best effort, not resolved for external console hosts**.
Win32 `ShowCursor` changes the calling GUI thread's count; Windows Terminal and
conhost own another thread's visible pointer. A native two-thread experiment
showed counts `0/0 -> -1/-1` while attached, returning to `-1/0` after detach.
Persistent host input attachment can stall the host; global cursor replacement
affects other apps. Neither was introduced. Existing balanced hide/show and
capture release behavior is preserved, with the limitation recorded in
`terminal.py`. A future host/UI ownership change needs architectural approval.

**Standing mouse issues, reported by the user on 2026-11-06:** the cursor still
does not disappear while locked into the terminal, and clicks appear not to
register while the mouse is moving. Both need review and fixing. The click-loss
behavior has not yet been reproduced or diagnosed; passing native-record and
mocked capture tests does not establish correct simultaneous motion/click input
in the user's terminal host. Resume investigation in `terminal.py`
(`WindowsKeyboard.poll()` and `WindowsMouse`) and `app.py` attack dispatch,
with regressions in `tests/test_mouse_input.py`, `tests/test_terminal.py` and
`tests/test_game_loop.py`. Verify real captured movement plus repeated clicks,
along with pause/blur/exit restoration; preserve `--keyboard-look` as a fallback.

## Implementation Boundaries

- `map_expansion.py` owns static castle/grounds geometry, exported spawn/weapon/
  bridge/target constants and standard Door placements. `world.py` builds meadow
  and river before applying it. Player defaults and app spawning share those data.
- X/Y are ground, Z is height. Keep 120 Hz physics, seeded scenery, simulation-
  time animation, independent collision and nonblocking bounded input.
- `World.combat` defaults to an independent empty state for fixture worlds.
  Only `build_world()` installs gameplay items and targets.
- `CombatState.held_item` holds a `WeaponPickup` instance. Weapon configuration
  supplies names, pickup cues and cooldowns. Explicit starter alias groups hide
  together; drops reuse the held object and never resurrect an alias.
- `World.interact()` returns event lists, so a swap emits both drop and pickup.
  `CombatState.update(dt, world)` advances fireballs. Swapping preserves cooldown;
  drop placement checks support and line of sight, including thin doors.
- Sword: 2.55 reach, 0.48-second cooldown, 0.30-second animation. Staff: one shot
  per press, 0.65-second cooldown, 12 units/second, 28-unit range, no ammo limit.
  Either weapon deals one direct damage; dummies have three HP and four-second
  resets. No splash damage or world destruction.
- `EnemyBehavior` in `combat.py` supplies shared territorial movement/melee
  tuning; `Enemy.behavior=None` preserves passive targets. Placements are data
  from `map_expansion.py`. `CombatState.update(dt, world, player=None)` accepts
  the live player; the app supplies it on each fixed step. Collision excludes
  only the enemy being moved through `World.collides(ignore_enemy=...)`.
  Five support samples, at most six steering headings and 0.08-unit substeps
  with a 0.1-second AI cap bound work; a short remembered detour prevents
  oscillation at pillar faces. This is local steering, not global pathfinding.
  `Player.take_damage()` owns health clamping and hurt/defeat events; app owns
  entrance respawn. Pauses/help/small terminals freeze all of this.
- Fireballs sweep their centers continuously using shared `World.solid_hit()`
  queries (exact voxels, panels, trunks), stopping at the first live target or
  solid. Water is transparent. Flight and impact bursts each cap at eight.
- Items/enemies use opaque depth-tested shapes and restrained pickup markers;
  enemy names/HP appear only when aimed at within ten units with clear sight.
- Warden blocks project each vertex once, cull hidden faces and fill convex
  planar faces with `Camera.quad()` spans. Camera/near-plane crossings retain
  the triangle fallback. A 192-frame pose/view probe exactly matched the initial
  triangle renderer; a permanent reference comparison tests perspective depth,
  foreground occlusion, clipping and near-plane fallback.
- Rendering keeps the 48-depth ray limit, 110 traversal iterations, 4,800-cell
  default viewport and 180x64 maximum. Grass uses 81 nearby chunks, radius 14 and
  candidates <= pixels / 3. Tree crown samples remain <= 3 * pixels.
- The overhead map caches static rows by world revision and viewport size and
  overlays the moving player marker separately. `Soundscape` buckets water in
  8x8 chunks and queries only its existing 18-unit influence radius. Exact
  full-scan equivalence is tested at banks, bridges, edges and after voxel edits.
- Renderer terrain caches remain on a conservative 2x2 grid and invalidate via
  `World.box()` revisions. The current optimization adds AIR-only below-roof
  volumes to the existing above-terrain skip path; exact-ray checks are required.
  Recreate Renderer when tree layout changes.
- Audio synthesis/device I/O stays outside simulation/rendering. Semantic events,
  prewarmed original Foley, isolated native process, completion callbacks, primed
  buffers, fades, bounded mixing, mute/volume/pause and silent headless modes remain.
  All seven doors share operation, obstruction protection and wooden creaks.
  Warden and player events have original synthesized cues. Player hurt/defeat/
  respawn sounds stay centered even if queued before a listener teleport.
  Meadow wind has gentle gust/rustle and a -19 dB source target (previously
  -23 dB); spatial gains and exact river buckets are unchanged.

## Validation and Performance

Latest native-console suite: **241/241 tests passed, zero skips**, Python 3.14.4.
The 25 added tests cover active AI/attacks/territory/respawn, health/HUD, app
defeat/empty-E routing, opaque Warden rendering and audio coverage/spatialization.
The native 18-second audio diagnostic passed: 395 buffers, zero empty-queue
events/recoveries, 73.0 ms maximum refill interval. Visual ASCII checks reviewed
the Warden idle/raised-fist poses and health HUD; automated tests cover all four
body views, wall occlusion, aimed-only labels and minimum HUD width.
Final 100-frame native-audio demos passed indoors/outdoors at 120x29, restored
console modes and measured 39.38/38.14 FPS against the 40 FPS cap. Both had zero
underruns/recoveries; maximum refill intervals were 80.27/72.43 ms. The temporary
native suite runner needed a multiprocessing `__main__` guard; its initial
unguarded run timed out audio workers. The guarded final suite passed in 29.01s.

Previous castle native-console suite: **216/216 tests passed, zero skips**.
This includes nine native input tests, 17 mouse ownership/look tests, separate
menu checks, castle routes/placement, app-loop dispatch/cleanup, sound coverage,
fixed vegetation budgets and exact-render comparisons at every benchmark camera.
Seven room-cache regressions cover ceilings, tunnels, holes, raised floors,
water/bridges, moving doors, odd edge chunks and voxel-edit invalidation.

Both 100-frame native-audio demos passed, restored console modes, and measured
**39.60/39.53 FPS** indoors/outdoors against the 40 FPS cap at a 120x29 live viewport.
Both had zero underruns/recoveries; maximum refill intervals were 71.9/72.5 ms.
The live counter includes input/output/cap waits; headless benchmark FPS does not.
Windows mouse records and ownership were tested, but physical mouse feel still
needs user play review. Piped suites skip console-only tests; sandbox PTYs can
reject injection, so use a hidden native process to exercise all input tests.
Workspace-local temporary storage avoids sandbox default-temp WAV permissions.

The room-cache extension keeps conservative AIR-only volumes, exact voxel hits
and existing work limits. Boundary rays that land on multiple integer planes
use ordinary DDA to preserve face/material ordering. Over 30 warmed gatehouse
frames, traversal iterations fell from 1,381,086 to 432,341. A focused interleaved
probe improved gatehouse mean/p95 from 22.42/24.62 to 19.31/21.91 ms; other sampled
views showed some overhead. This is not a full acceptance claim.

The watchstone increment passed a **24-scene, per-frame ABBA comparison** against
the frozen pre-feature working tree at 120x40: 60 measured frames per variant,
five warmup frames, three 120 Hz combat steps per rendered frame and live native
audio. Both versions sampled their actual Soundscape; the native mixer was
shared. `watchstone-interleaved.json` records final results: maximum mean/p95
increases **4.23%/11.91%**, within the unchanged 15% limit. The active Warden
scene changed from **16.464/20.265 to 17.136/18.884 ms** mean/p95 (+4.08%/-6.81%).
Audio had zero underruns/recoveries and 72.97 ms maximum refill interval.

Keep failed phases: `watchstone-interleaved-first.json` flagged Warden mean
+15.14%; `watchstone-interleaved-culling.json` still flagged its p95 +19.47%.
The convex face span change fixed the final comparison without lowering detail
or changing pixels in the 192-view probe. `watchstone-before.json` is the initial
23-scene audio snapshot using the older benchmark loop, not an approved baseline.
Reports include camera/platform metadata and hashes of frozen source inputs.
These comparisons cover the incremental feature cost, not absolute 40 FPS or
the older castle-wide acceptance. Timings still vary between runs; no cause for
that variation has been established.

**The earlier castle-wide frame-time acceptance remains open. Do not promote
new measurements to approved baselines.** All measurements below are retained:

- `castle-milestone-before.json`: initial pre-change 17-scene run with the old
  ambient proxy. `castle-milestone-first.json` is diagnostic only: its first
  second overlapped a visual-render probe, invalidating acceptance.
- `castle-milestone-before-live.json`: frozen pre-milestone working-tree code,
  60 frames/120x40/audio, actual old Soundscape sampling and map overlay.
- `castle-milestone-live.json`: isolated rebuilt castle before room optimization.
  Gatehouse 20.95/22.95 ms mean/p95 and ruins 15.23/19.41 ms flagged; other comparable
  roles stayed within 15%. Audio: zero underruns/recoveries, 72.7 ms max refill.
- `castle-milestone-optimized.json`: final 23-camera/audio run, including open
  meadow sides, exterior, hall, roof, combat, map and river. It flagged 16/18
  comparable roles against the fresh old-map run. Gatehouse 17.68/19.84 ms;
  river 26.51/34.91 ms; fireballs 29.23/34.20 ms. Audio: zero underruns/recoveries,
  73.0 ms max refill. Preserve this failure rather than selecting a favorable run.
- `castle-milestone-control-recheck.json`: untouched frozen old code also varied
  substantially: meadow 17.61->28.56 ms mean, staff 13.08->22.91 ms, while other
  roles stayed close. Timing variation cannot be attributed solely to this code
  change. Its cause is unverified; do not invent a hardware/background-load cause.
- `castle-size-scaling.json`: per-frame ABBA control, audio off, same castle and
  pixel-identical visible scenes padded from 112x112 into 160x160 storage. Across
  gatehouse, court, close grass and river, added cost was <=1.0% mean and <=1.6%
  p95. This isolates storage-size overhead; it does not approve the full map's
  geometry costs or replace audio-enabled whole-scene measurements.

Camera coordinates and dimensions are saved in new reports. Old/new world
comparisons concern scene roles rather than identical geometry. Historical
`milestone-start.json` remains the original pre-milestone reference; its earlier
milestone-wide 15% mean/p95 acceptance was unresolved before this work. Preserve
staff, river-flow, door-creak and tree records, including failed/concurrent runs.
`river-flow-initial.json` records a real stalled run with three audio underruns;
later successes do not erase it. Never relax thresholds or cherry-pick results.

## Resume / Next Steps

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
python -B -m unittest discover -s tests -v
python -B main.py --demo --frames 100
python -B main.py --outside --demo --frames 100
python -B main.py --keyboard-look
python -B main.py --audio-test
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/castle-milestone-before-live.json --save benchmarks/castle-review.json
```

Use a native console for the nine input cases; piped test runs skip them. The
normal benchmark now includes a `warden` camera and three fixed combat steps
for active/combat scenes. Keep comparison frame counts/audio modes matched.

1. Review and fix the standing mouse issues: the pointer remains visible during
   capture, and clicks appear to be lost while moving the mouse. Reproduce in
   the user's terminal host and test simultaneous motion/click delivery; the
   root cause and fix remain open.
2. Resolve the earlier castle-wide matched comparison before claiming its
   preserved frame times. The watchstone increment passed its own matched check.
   Use interleaved controls and retain mean/p95 wall times; CPU-time
   observations may help investigate variability but must not replace wall time.
   Profile `Renderer.scene()` gatehouse/water/combat paths, preserve exact-ray
   equality, ray distances and detail budgets. Do not change the baseline/limit.
3. User play review: mouse feel/capture, menu clarity, castle navigation, weapon
   drops and dummy readability. Physical speakers, device unplug/replug, POSIX
   key holds and minimum Python 3.10 remain unverified. No save/load or objectives
   have been added. Warden combat, player health and respawn need user play review.

Current parallel ownership was enemy simulation/tests, wind/creature/player
audio, and cursor investigation/review; root integrated player health, HUD/body
rendering, world collision, app behavior, tests, documentation and measurements.
The cursor investigation found no safe host-independent hiding change. All
delegated work is finished. Temporary source copies, probes
and previews are removed after review; benchmark JSON is retained. This checkpoint
also includes the earlier castle and staff implementation. The user authorized
committing the current state with the standing mouse issues documented; this
does not mark those issues as resolved.

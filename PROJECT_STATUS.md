# Project Status

Last reviewed: **2026-11-07**. Earlier gameplay checkpoint: `f27e9ff` (2026-11-06).
Read this with [AGENTS.md](AGENTS.md); [README.md](README.md) covers play/controls.
Current checkpoint scope: documentation/cache cleanup and native mouse capture
approved on 2026-11-07, with the two cursor bugs below explicitly unresolved.

## Open Issues and Priorities

1. **Two future mouse fixes, reported by the user on 2026-11-07:**
   - The cursor is still visible at the center of the terminal while captured.
   - Pausing the game does not free the cursor.

   Both remain unresolved after the Raw Input change. The user authorized this
   checkpoint with these bugs recorded, not confirmation that mouse capture is
   successful. Reproduce in their tabbed Windows Terminal; review cursor binding
   in `mouse_capture.py`, and pause/clip teardown through `app.py` and
   `terminal.py` (`WindowsMouse.release()`, `NativeMouseCapture.stop()`). Extend
   `test_mouse_capture.py`, `test_mouse_input.py`, `test_terminal.py` and
   `test_game_loop.py` with real-host regressions. Earlier missed-click behavior
   has packet-stream coverage but no captured user-device trace or explicit
   physical confirmation. Keep `--keyboard-look` available.
2. **Earlier castle-wide performance acceptance remains open.** The Warden
   increment passed a separate matched check, not a whole-project FPS guarantee.
   Old/new controls vary for an unverified reason. Profile gatehouse, water and
   combat without reducing detail or relaxing the 15% mean/p95 limit. Retain
   interleaved wall-time controls and failed evidence; the
   [benchmark index](benchmarks/README.md) identifies relevant reports.
3. Play review remains for navigation, swaps, Warden combat and audio. Physical
   speakers, device unplug/replug, POSIX held keys and minimum Python 3.10 remain
   unverified. No save/load or objectives are implemented.

## Implemented State

Standard-library Python game, last tested on Windows/Python 3.14.4. The
112x112x12 world has a four-tower castle, gatehouse, hall, cloister, training yard
and garden surrounded by meadow. Two bridges cross the northern river toward
ruined chapel, western watchstones and eastern lodge. Seven doors share panels
and E interaction. West steps reach the cloister roof/west wall; a complete
roof circuit is not verified. `map_expansion.py` owns dimensions and placements:

- Indoor/outdoor starts: `(55.5,30.5,1)` / `(55.5,20.5,1)`, facing north.
- Sword aliases: `(55.5,32.5)` / `(55.5,22.5)`, one shared item.
- Staff: `(53.5,103.5)` in northern ruins; dummies at `(42.5,48.5)`,
  `(46.5,48.5)`, `(50.5,48.5)`.
- Warden home: `(18.5,103,1)`; territory `(12,99)-(24,106)`.

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
  pause/help/blur/minimize/small viewport/exit/exceptions; pause release is broken
  in the reported host. `ExitStack` requests release before audio drains.
  Moving the game tab between terminal windows requires restart or keyboard mode.
  The approved Raw Input helper is a non-activating, one-pixel topmost popup with
  a private transparent cursor and single-point confinement. It is deliberately
  **unowned by the terminal**: cross-thread ownership implicitly joins input
  queues and can stall the host. No global cursors or host input queues change.
  Warp into the helper before point-locking; ClipCursor accepts right/bottom
  endpoints. Registration/pumping is bounded; teardown unregisters/hides the
  helper and attempts clip restoration. Acquisition/resize failure cleanup has
  regression coverage. An explicit
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
- **Budgets:** ray depth 48, 110 traversal iterations; live viewport 4,800 cells,
  maximum 180x64. Grass: 81 chunks, radius 14, candidates <= pixels/3; tree crown
  samples <= 3*pixels. Map backgrounds cache by revision/viewport. River audio
  queries 8x8 water buckets within radius 18, with full-scan equivalence tests.
- **Audio:** prewarmed synthesis/isolated native playback stay off gameplay paths.
  Completion callbacks pace three primed 1,024-frame buffers; mixing caps at
  eight voices. Preserve fades, queue health, mute/pause/volume/no-device behavior.
  Player hurt/defeat/respawn cues stay centered across queued listener teleports.

## Validation

Mouse-fix checks (2026-11-07): **267 native-console tests passed, zero skips**,
including packet/button-source regressions, capture cleanup/failure handling,
transparent Win32 cursor masks and class-resource cleanup. The standalone
separate-process GUI probe received raw clicks during injected drags, retained
host keyboard focus and restored the original clip on release. Its automation
pointer overlay is not a reliable visual check of the user's actual OS cursor.
Subsequent user playtesting reported the visible center cursor and failed pause
release above; automated results do not establish that either bug is fixed.
The sandbox denies
ClipCursor; real capture diagnostics required desktop access, not system changes.

`benchmarks/mouse-input-audio.json`: 24-scene render/audio smoke, 120x40/60 frames,
zero underruns/recoveries, 75.6 ms maximum refill interval. This excludes desktop
input handling and is not a new performance baseline. Earlier results below are
from 2026-11-06.

- Piped suites skip nine console-only input cases; use the native console for
  full validation. Test success does not replace physical mouse play review.
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
python -B -m unittest discover -s tests -v
python -B main.py
python -B main.py --keyboard-look
python -B main.py --outside --demo --frames 100
python -B main.py --audio-test
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/castle-milestone-before-live.json --save benchmarks/castle-review.json
```

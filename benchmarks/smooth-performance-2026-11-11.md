# Geometry performance repair — 2026-11-11

Work resumed after the user's poor-frame-rate report. Recovering performance is
the immediate milestone; smooth hills/stairs remain uncommitted and are not
accepted merely because correctness tests pass. The user also established dark
fantasy as the standing theme for future content; it is recorded in AGENTS.md,
README and PROJECT_STATUS.md.

## Controls and evidence

The frozen pre-geometry control is Git **d20cd0d**. A separate temporary
copy preserved the working-tree engine at the start of this repair. It is
retained as `smooth-resume-source-2026-11-11.zip` for reference comparisons;
the temporary source directory is removed at wrap-up. Do not replace either
control or overwrite any report. Paired measurements use the same Windows host,
Python 3.14.4, 120x40, 60 frames per variant, five warmups, ABBA ordering and a
shared live native mixer with listener-height sampling in both variants.
Both per-scene mean and p95 retain the **15% regression limit**. Terminal writes
and cap waits are excluded; headless FPS is not a full-terminal guarantee.

- `smooth-interleaved-first-failed.txt` retains the earlier initial geometry
  failure: 24/24 failed, then a misplaced stair camera aborted the run before
  JSON/raw samples/audio health were saved.
- `smooth-resume-profile.txt` / `smooth-resume-profile-sources.json` profile the
  resumed engine before this repair. They are call-count diagnostics, not
  acceptance timings. Hidden analytic work dominated upper floors and hills.
- `smooth-interleaved-repair-2026-11-11.json` is the first **complete** repaired
  run: **8/24 pass, 16/24 fail**, exit 1. Audio: **0 underruns, 0 recoveries**,
  72.70 ms maximum refill interval, no device error. All raw frame samples,
  camera preflight, source hashes and failure states are retained.
- `smooth-repair-profile.txt` / `smooth-repair-profile-sources.json` identify
  remaining terrain ray work in Warden/east-bridge/highland views and excessive
  stair candidate checks on upper floors. Profiled times are not substituted
  for wall-clock acceptance results.

The first complete repair run's new scenes cost 61.759/67.621 ms
mean/p95 in highlands, 75.194/81.936 ms at the ravine, and 70.219/81.615 ms
walking stairs. This confirms remaining performance work; no baseline is
promoted and no FPS acceptance is claimed.

## Implemented and checked in repair stage one

- Fixed the stair camera to `(140.5,41.5,Z5)` and preflight all 34 current camera
  poses before measurement/audio startup. Explicit cameras fail rather than
  being silently moved; natural poses use cylinder support.
- Paired reports reserve unused paths, save atomic scene checkpoints, and retain
  partial raw samples/source hashes/error phase/scene/variant on exceptions and
  audio cleanup failures. Incomplete or no-device runs cannot pass. Ten focused
  benchmark tests pass, including a real-world camera preflight.
- Renderer queries analytic geometry after its voxel traversal, bounded by the
  nearest voxel/water/door/combat hit. Sky queries remain independent. Thirty-two
  focused tests pass and 68 before/after images match exactly, with shared combat
  render functions to avoid cross-import weapon-type artifacts.
- Exact plane caching (maximum 4,096 cells), fine-DDA loop work, deferred hit
  allocation and unrolled AABB slabs reduce shared query overhead. Nine surface
  tests and 4,064 frozen-reference rays match distance/material/normal exactly.
- Coarse bound queries use allocation-free ray entries; repeated solid candidates
  use identity rather than dataclass-value hashes. Combined smooth tests pass.

## Later repairs and final measured checkpoint

Later changes are integrated, tested and measured:

- A cached fine XY index for visible stair boxes limits candidate tests, with a
  2,048-entry construction-work bound and an eight-unit fallback for large shapes.
  Public-query regressions compare against uncropped exact rays, including
  corners, large shapes, later insertions and first/cached selection stability.
  Review caught and repaired a local variable shadowing the view bounds.
- Prepared queries reject wholly separated Z intervals before bound division.
- An independent conservative analytic skyline uses 128 angular bins and exact
  field/stair bounds. Per-chunk constant/affine upper envelopes clip provably
  empty ray intervals before exact triangle testing. No range/detail was reduced.
- A conservative nearest forward-depth bound skips analytic calls behind an
  already closer voxel/water/door/combat bound. Coincident faces remain covered.
- Verification includes **28,064 exact frozen-ray comparisons**, 34 field frame
  and depth comparisons, and **136 full image/depth pairs** over all 34 camera
  roles with varied pitches and wide/tall viewports. These are correctness
  diagnostics, not acceptance timings.

All three completed runs below use the method/control above and remain retained:

| Report | Matched passes | Audio underruns / recoveries | Max refill gap |
| --- | ---: | ---: | ---: |
| `smooth-interleaved-repair-2026-11-11.json` | 8/24 | 0 / 0 | 72.70 ms |
| `smooth-interleaved-envelope-2026-11-11.json` | 9/24 | 0 / 0 | 75.10 ms |
| `smooth-interleaved-depthbound-2026-11-11.json` | **12/24** | 0 / 0 | 73.20 ms |

**Performance acceptance is not achieved.** The latest report fails meadow,
bridge, river, east_bridge, watchstones, warden, staff, map, river_diagonal,
castle_exterior, great_hall and east_meadow. Warden mean/p95 remain
**+105.32%/+144.88%** against its contemporary control; east bridge is
**+75.90%/+78.35%**. The map p95 also fails at +15.64%; do not waive borderline
failures or retry unchanged code to select a favorable result.

Latest representative costs (120x40, live audio, terminal output excluded):

| Role | Mean ms | p95 ms |
| --- | ---: | ---: |
| Gatehouse | 17.513 | 19.831 |
| Bridge | 27.965 | 33.534 |
| East bridge | 28.005 | 36.251 |
| Warden | 27.195 | 41.482 |
| Ridge approach | 38.412 | 47.059 |
| Ridge upper floor | 33.104 | 40.682 |
| Highlands | 42.262 | 49.195 |
| Ravine | 62.557 | 71.746 |
| Stair walking | 58.721 | 68.530 |

Absolute timings vary across runs; only within-run paired ratios establish the
listed comparisons. Do not claim a wall-clock speedup from lower profile call
counts. `smooth-envelope-profile.txt` and its source-hash companion retain the
latest fixed-pose diagnostic counts; those fixed poses do not reproduce the
benchmark's varying yaw, simulation and walking workloads.

## Final validation and actual live demo

**393 native-console tests passed, zero skips, 141.439 seconds**, Python 3.14.4,
workspace TMP/TEMP and `MONOLITH_DESKTOP_TESTS=1`. This includes real console
input, cursor capture/release, all stair routes, jumping/water, exact geometry,
occlusion, sound coverage and benchmark exception persistence. Snapshot exits 0.

`smooth-ridge-live-2026-11-11.json` records a **100-frame native Ridge Hall demo**
at the actual **80x24** grid, default full-terminal mode, sound enabled, exit 0
and completed terminal cleanup. After five warmups: render mean/p95
**12.043/21.592 ms**, terminal write **0.215/0.735 ms**, completed loop interval
**25.386/25.733 ms** (about **39.4 FPS**, including cap waits). There are 95 render
samples and 94 loop intervals; the final frame has no following interval.
Audio reports **0 underruns / 0 recoveries**, 84.298 ms maximum refill interval.
This is one instrumented native route, not a larger-screen or whole-world FPS
guarantee. The temporary probe is removed; its methodology/raw samples/hash are
retained in the report. The 18-second standalone audio diagnostic and physical
speaker/unplug checks were not repeated.

Plain-text snapshot and indoor/outdoor/stair reference frames were inspected.
The temporary offscreen GDI preview helper produced unreliable glyph output;
those previews are not accepted visual evidence and are removed. Physical
appearance/play review in the user's tabbed Windows Terminal remains pending.

## Resume and stop conditions

The geometry/performance work is checkpointed at the user's **2026-11-11**
commit request. `d20cd0d` remains the pre-geometry comparison control; performance
acceptance is still open. Geometry approval is already granted. Resume as follows:

1. Read AGENTS.md (including dark-fantasy direction), PROJECT_STATUS.md, this
   report and the current Git diff. Do not redo completed camera/report repairs.
2. Reproduce the latest failing roles with **varying yaw and live simulation**,
   matching `tools/benchmark_pair.py:frame`, not only a stationary fixed-time
   frame. Profile voxel traversal, analytic queries, AI support/collision and
   preparation separately. Retain diagnostics/source hashes.
3. Investigate whether always doing voxel DDA before the analytic hit wastes
   work in terrain-dominated views. A measured, exact early-query/hybrid policy
   is a **proposal, not implemented**. Preserve the successful wall-bounded path
   indoors. Likewise projected row-interval/min-depth culling is only a proposal;
   avoid naive per-box rectangle writes that can exceed current work budgets.
4. Compare ray/frame/depth results before measuring each change. Keep all 13
   stair routes, water/jump/guardrail behavior, sound and unchanged budgets.
   Generic partial-Z terrain edits remain the documented whole-cell limitation.
5. Run another serial **60-frame / 120x40 / live-audio ABBA** against d20cd0d,
   using an unused report path and the unchanged 15% mean/p95 gates. Keep every
   failure. New terrain scenes have absolute costs, not fabricated percentages
   against different historical geometry. The archived resumed engine can also
   be used as a same-geometry reference, with clearly labeled controls.
6. Once performance passes, repeat checks appropriate to subsequent changes,
   inspect the user's actual terminal dimensions and larger-screen cost, and
   perform physical visual/play/audio review. Do not reduce the default full
   terminal resolution to conceal FPS costs. Commit after user success
   confirmation or an explicit checkpoint request, per AGENTS.md.

The user requested a precise handoff if work is unfinished when remaining Codex
usage reaches **15%**. Check the account usage tool between major phases; stop
and document if either relevant usage window has 15% or less remaining. At the
first check, 66% remained in the short window and 70% in the weekly window.
**Stopped at 15% short-window / 62% weekly remaining** on 2026-11-11, as requested.
Check the latest meter before resuming. No active tests, benchmarks or subagent
processes are left running. Temporary controls/probes/previews/caches are removed;
the starting-engine archive is hash-verified against the initial profile source
manifest and retained as benchmark evidence. Work was uncommitted at that
wrap-up and subsequently checkpointed at the user's 2026-11-11 request.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
python -B -m unittest discover -s tests -v
# Reconstruct d20cd0d only if the temporary control is absent.
git archive --format=zip --output=smooth-control-tmp.zip d20cd0d ascii3d
Expand-Archive -LiteralPath smooth-control-tmp.zip -DestinationPath smooth_control_tmp
python -B tools/benchmark_pair.py --before-source smooth_control_tmp --before-elevated-audio --frames 60 --audio --save benchmarks/smooth-next-unused.json
# Optional exact same-geometry reference from this repair's starting engine:
Expand-Archive -LiteralPath benchmarks/smooth-resume-source-2026-11-11.zip -DestinationPath smooth_resume_tmp
```

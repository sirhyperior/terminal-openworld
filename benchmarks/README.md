# Benchmark Evidence

Read on demand for performance/audio history; current priorities/results are in
[PROJECT_STATUS.md](../PROJECT_STATUS.md). These reports are not interchangeable
approved baselines. Preserve failed/concurrent runs; compare mean and p95 on
matched hardware, Python, dimensions, frames and audio mode. Camera roles across
different maps are not identical geometry. Git checkpoint `f27e9ff` retains the
longer historical narrative removed from the main handoff during cleanup.

## Open Comparisons

- **Grayscale redesign foundation (2026-11-14, incomplete milestone):**
  [Checkpoint and approved world brief](visual-redesign-2026-11-14.md) records
  shared shading, styled terminal output, exact convex geometry/GPU support,
  failures and resume order. `visual-control-2026-11-14.zip` freezes the actual
  working source including uncommitted movement/loading fixes. Preserve its
  manifest, hotspot diagnostic and all initial failed test evidence. World
  authoring remains outstanding. Final native475tests pass (one cursor skip).
  Same-geometry/live-audio CPU1/34 andGPU4/34 role gates fail; complete raw reports
  are retained with clean audio. No baseline or threshold was replaced.
- **Richer loading presentation (2026-11-13):**
  [Loading validation](loading-screen-2026-11-13.md) records truthful stage
  percentages with a title, animated activity, bar and rotating tips. 435 native
  tests pass on the initial presentation, with one sandbox cursor skip; 38 final
  focused checks pass after responsive-layout/transition cleanup. An actual
  30-frame GPU/audio smoke reaches 100 once, has no loading worker in gameplay,
  and reports zero underruns/recoveries. No new gameplay timing baseline is claimed.
- **Ordinary block climbing repair (2026-11-13):**
  [Movement evidence](block-climbing-2026-11-13.md) records the reproduction,
  shared stair/support repair, expected failing control and validation.
  429 native tests pass with one sandbox cursor skip; all 13 authored flights
  retain traversal/Foley. Matched 120x40/60-frame live-audio CPU ABBA against
  a2049c3 passes **34/34**, with zero underruns/recoveries. This isolates the
  movement fix and does not close the historical performance comparison.
- **Abandoned color experiments (2026-11-13):** the user requested restoration
  to fd56e49 and deferred color. `abandoned-color-2026-11-13.zip` retains the
  generated reports, failed runs, partial samples and their original source
  manifests as historical evidence only. Their source code is not active and
  their measurements do not describe the restored engine. No baseline changed.
- **Current CPU repair and approved GPU prototype:**
  [2026-11-12 evidence](smooth-performance-2026-11-12.md) records the current
  checkpoint. The final CPU comparison against `d20cd0d` passes **14/24**
  roles; the separate same-geometry comparison against `a3d044f` passes **34/34**,
  with zero underruns/recoveries. The earlier grouped experiment failed three
  views and had one underrun; every failure is retained. There are 204 exact
  CPU frame/depth pairs and 34,816 exact terrain rays. GPU integration now shares
  production presentation; 204 full image pairs match, and 420 native tests pass
  with one sandbox cursor skip. Latest full GPU ABBA passes **14/24** against
  d20cd0d, with clean audio; its earlier 11/24 and 13/24 failures are retained.
  A 100-frame actual 160x50 GPU demo completes with sound and loading progress.
  Whole-game performance acceptance remains open; stage-only prototype timings
  are not a replacement control.
- **Smooth hills/fine stairs (2026-11-11 checkpoint):**
  [2026-11-11 performance repair](smooth-performance-2026-11-11.md) resumes the
  immediate FPS work. `smooth-interleaved-repair-2026-11-11.json` is complete:
  8/24 matched roles pass; the later envelope report passes 9/24 and the latest
  `smooth-interleaved-depthbound-2026-11-11.json` passes **12/24**, all with zero
  audio underruns/recoveries. All 393 native tests pass; a 100-frame native 80x24
  Ridge demo averages about 39.4 FPS including cap waits. Performance acceptance
  remains open. Work stopped at the user's 15% remaining usage threshold.
  Preserve `smooth-resume-source-2026-11-11.zip`: its engine files match the
  initial profile source manifest and support same-geometry reference checks.
  The camera and atomic partial-report repairs are implemented.
  [smooth-geometry.md](smooth-geometry.md) records architecture, focused checks
  and exact resume steps. [First failed output](smooth-interleaved-first-failed.txt)
  retains 24/24 failed matched roles, followed by a stale stair-camera exception.
  End-only JSON saving lost that run's raw samples/audio-health summary; that
  historical failure remains retained. Work is checkpointed at the user's
  2026-11-11 request; no baseline replacement or performance acceptance is claimed.
- **Full-terminal viewport:** [viewport-milestone.md](viewport-milestone.md)
  records native final-cell checks, large/tall renderer validation and live-audio
  frame cost. `viewport-interleaved-120x40.json` is diagnostic because its
  flat/elevated listener sampling differs. The corrected
  `viewport-interleaved-height-120x40.json` passes 23/24 matched roles; castle
  exterior p95 fails +20.52% against the unchanged 15% limit. The failure is
  retained and no baseline is replaced. Larger-resolution costs are measured
  separately; resolution scaling is not a percentage regression comparison.
- **Highland expansion:** [terrain-expansion.md](terrain-expansion.md) records
  milestones, controls and repairs. `terrain-interleaved-first.json` failed
  19/24 scene comparisons; `terrain-profile-first.txt` retains diagnostic counts.
  `terrain-interleaved-optimized.json` also failed 8/24 comparisons. Further
  `terrain-interleaved-horizon.json` passes 20/24, with four failures retained.
  Later signed-inverse/scenery/prepass work has focused checks; full paired
  acceptance remains open at the user's wrap-up checkpoint. Limits are unchanged.
- **Castle-wide acceptance is unresolved.** `castle-milestone-before-live.json`
  is the frozen old-map, 60-frame/120x40/audio control with actual Soundscape.
  `castle-milestone-live.json` predates room optimization;
  `castle-milestone-optimized.json` still flagged 16/18 comparable roles.
  `castle-milestone-control-recheck.json` also varied substantially in unchanged
  old code, for an unverified reason. Do not promote these to approved baselines.
- `castle-milestone-before.json` used the earlier ambient proxy.
  `castle-milestone-first.json` overlapped a visual probe: diagnostic only.
  `castle-size-scaling.json` isolates storage size with identical visible scenes
  padded from 112x112 to 160x160: <=1.0% mean/1.6% p95 added cost, audio off.
  This does not establish full geometry/audio performance.
- **Warden increment:** `watchstone-before.json` is the initial 23-scene snapshot.
  `watchstone-interleaved-first.json` failed Warden mean (+15.14%);
  `watchstone-interleaved-culling.json` failed p95 (+19.47%).
  `watchstone-interleaved.json` passed after convex spans: 24-scene ABBA,
  largest mean/p95 increases 4.23%/11.91%, no underruns/recoveries. These three
  reports use their own comparison schema, not the CLI `--compare` format.
  Frozen sources/probes were temporary; reports retain methodology/source hashes.

## Earlier References

| Reports | Purpose / limits |
| --- | --- |
| `vegetation-before.json`, `vegetation-current.json` | Vegetation reference pair; README's normal comparison uses the latter. |
| `trees-near-before.json`, `trees-near-after.json` | Close-tree rendering comparison. |
| `milestone-start.json`, `milestone-integrated.json` | Earlier milestone reference/integration; overall acceptance was already unresolved. |
| `doors-audio-current.json`, `door-creaks.json`, `sword-hit.json` | Door/audio and sword-feedback history. |
| `audio-repair-measurement.json` | Repaired audio, with frame-time flags preventing reference replacement. |
| `river-flow-initial.json`, `river-flow.json` | Initial run stalled with three underruns; later success does not erase it. |
| `staff-before.json`, `fire-staff.json`, `staff-training-interleaved.json` | Staff references and focused interleaved observations. |
| `fire-staff-concurrent.json` | Concurrent diagnostic; unsuitable as an isolated acceptance result. |
| `mouse-input-audio.json` | Render/audio smoke after the native input fix; does not time desktop capture or establish a new baseline. |
| `mouse-capture-2026-11-10.md` | Empty-clip failure reproduction, repaired native cursor/release evidence, tests and remaining physical-host review. |
| `mouse-release-audio.json` | 2026-11-10 audio smoke: no underruns/recoveries, but all 24 historical mean/p95 comparisons failed; retained evidence, not a replacement baseline. |

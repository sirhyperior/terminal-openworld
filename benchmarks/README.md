# Benchmark Evidence

Read on demand for performance/audio history; current priorities/results are in
[PROJECT_STATUS.md](../PROJECT_STATUS.md). These reports are not interchangeable
approved baselines. Preserve failed/concurrent runs; compare mean and p95 on
matched hardware, Python, dimensions, frames and audio mode. Camera roles across
different maps are not identical geometry. Git checkpoint `f27e9ff` retains the
longer historical narrative removed from the main handoff during cleanup.

The NPC idle-motion comparison records the matched live-audio timings and the
control/control diagnosis of the original small-viewport p95 spikes.
[NPC idle animation (2026-11-22)](npc-idle-animation-2026-11-22.md)

## Open Comparisons

- Mael's spawn and talk views passed the 240×80 live-audio gates and exceeded
  the 120×40 regression limits.
  [Mael and actor label timings (2026-11-22)](npc-labels-mael-2026-11-22.md)

- The selective fallback and camera reuse experiments exceeded the p95 gate
  in matched live-audio comparisons.
  [Exact GPU follow-up (2026-11-21)](exact-gpu-follow-up-2026-11-21.md)

- **Full-resolution Windows optimization (2026-11-21):**
  [Matched live-audio and native console runs](full-detail-windows-2026-11-21.md)
  track the batch GPU refinement, voxel traversal and surface lighting changes.

- **Full-resolution retry (2026-11-21):**
  [Restored detail and exact acceleration](full-detail-retry-2026-11-21.md)
  tracks parity with the pre-cloud renderer and timings with every scene cell
  traced. The adaptive results below are retained as historical evidence.

- **Fullscreen terminal follow-up (2026-11-21):**
  [Graphical output and Thornwatch replay](optimization-fullscreen-output-2026-11-21.md)
  records changed-span output, GPU and terminal timing diagnostics, the
  reproducible grass-generation spike, and matching fullscreen comparisons.

- **Fullscreen optimization (2026-11-21):**
  [Measured renderer and terminal changes](optimization-cpu-2026-11-21.md)
  track exact CPU improvements, compiled solid traversal, and adaptive live
  pacing at 160×50 and 240×80.

- **Dim ash and sparse glints (2026-11-21):**
  [Appearance and performance evidence](moon-glints-2026-11-21.md) records the
  sparse highlights and subdued palette, and preserves the earlier
  broad-contrast experiment and its live-audio startup failures.

- **Six-site dark world, sound and particles (2026-11-17):**
  [Implementation and validation](darkworld-2026-11-17.md) records the new map,
  stronger eye-level particles, sound replacement and initial blockiness work.
  The version-1 role manifest locks old/new playable poses against `46c36a3`.
  These are semantic comparisons across different maps, not identical geometry.

- **Moonlit palette (2026-11-17):** [Color, shadow and motion evidence](moonlight-2026-11-17.md)
  covers the new color ramps, directional shadows, wind and current response,
  three matched playable views and the incremental comparison against `5b5a263`.
- **Stronger visibility (2026-11-16):** [Surface lighting adjustment](visibility-2026-11-16.md)
  responds to the user's insufficient-shadow-visibility play report with ambient
  fill, denser shadow glyphs and readable actor recesses. All 69 rendering tests
  pass, including hardware parity; four scene depth buffers match. CPU/live-audio
  incremental timing passes 34/34 roles, with zero underruns/recoveries. The earlier
  [palette-only lift](shadow-readability-2026-11-16.md)
  passed 34/34 timing roles but remained too dark for the user; its evidence and
  all historical performance failures remain retained.
- **Surface depth and particles (2026-11-14):** [Quality validation](visual-quality-2026-11-14.md)
  records per-character material shading, stronger relief and bounded depth-tested
  particles against the 96-file pre-quality color archive. The native 534-test
  suite passes (one cursor skip); all 204 CPU/GPU pairs pass. Incremental timing
  fails the unchanged 15% mean/p95 gates: CPU 8/34 pass; GPU timing/native output
  checks remain deferred at the usage cutoff. No historical baseline changed.
- **Rich color pass (2026-11-14):** [Implementation and validation](color-pass-2026-11-14.md)
  records semantic hues, depth/firelight variants and gray/mono fallbacks.
  Native 508-test suite passes (one cursor skip); 204 CPU/GPU complete frame/style/
  material/effect/ANSI/depth pairs pass. Incremental CPU 34/34 styled/live-audio roles
  pass against `color-control-2026-11-14.zip`; GPU 30/34 fails four p95 roles. Four
  actual native GPU gray/color apps pass with clean audio/restoration. Failed
  zero-sample diagnostic startups remain retained; no tail attribution claimed.
  The grayscale foundation's historical failures remain open; no baseline changed.
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

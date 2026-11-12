# CPU geometry repair and GPU prototype — 2026-11-12

The session started at clean checkpoint `a3d044f`. Smooth geometry approval was
already granted. The user subsequently approved an **optional GPU renderer
prototype using wgpu-py**, retaining real terminal ASCII output and a CPU
fallback. That approval covers the prototype/backend dependency; it does not
establish GPU accuracy, device availability or performance acceptance.

## CPU controls and results

All paired timing runs are serial Windows/Python 3.14.4, 120x40, 60 measured
frames per variant, five warmups, per-frame ABBA, shared live audio and elevated
listener sampling. Mean and p95 retain the **15%** gates. Source hashes and raw
samples remain in each report. Terminal output and frame cap waits are excluded.

- `smooth-interleaved-projected-2026-11-12.json`: projected bounds alone;
  **12/24 pass**, zero audio underruns/recoveries. This failed run is retained.
- `smooth-same-geometry-grouped-2026-11-12.json`: diagnostic against `a3d044f`,
  with matching camera poses and a hash of voxel cells, field vertices/flags/
  materials and solid configurations. It failed Great Hall, Ridge approach,
  terrace walking and audio health (**one underrun**, zero recoveries).
- `smooth-same-geometry-bounded-2026-11-12.json`: revised bounded work, same
  geometry/control/method; **34/34 pass**, zero underruns/recoveries, 63.15 ms
  maximum refill interval. Stair-walking mean/p95 fall **17.21%/16.07%**, east
  meadow **14.13%/20.00%**. Warden remains **+2.31%/+2.00%** against this smooth
  checkpoint. This is a same-geometry diagnostic, **not a replacement baseline**.
- `smooth-interleaved-bounded-2026-11-12.json`: final CPU repair against the
  original pre-geometry **`d20cd0d`**; **14/24 pass**, zero underruns/recoveries,
  100.14 ms maximum refill interval. **Performance acceptance remains open.**

Final failures against `d20cd0d`:

| Role | Mean change | p95 change |
| --- | ---: | ---: |
| Meadow | +14.91% | +15.11% |
| Bridge | +59.24% | +58.42% |
| River | +19.24% | +23.23% |
| East bridge | +69.84% | +62.63% |
| Watchstones | +94.91% | +84.59% |
| Warden | +99.60% | +101.58% |
| Staff | +46.72% | +38.94% |
| River diagonal | +52.52% | +50.02% |
| Castle exterior | +23.95% | +28.77% |
| East meadow | +30.90% | +21.46% |

Do not waive Meadow's borderline failure. Do not compare absolute timings from
different runs as a speedup: concurrent host load/frequency were not established.
The Great Hall profile made no analytic ray calls, so its earlier p95 outlier
cannot be attributed to the solid hierarchy without further evidence.

## Implemented CPU work

- Conservative projected analytic AABBs supply per-pixel minimum depth through
  scanline interval sweeps. Work uses eight corner projections per box, at most
  one interval per box/row, and one viewport's output writes. A near-plane
  fallback covering the viewport short-circuits redundant bounds preparation.
- Outdoor early queries operate only inside a proven voxel-empty prism, for
  downward rays whose local-height estimate fits that interval. At most four
  failed attempts per frame can add a second query. Interiors keep the existing
  voxel-bounded route. The unbounded early-query experiment caused the retained
  Ridge/terrace regressions; it is repaired, not accepted as a gain.
- Terrain tolerance rejection uses a conservative per-ray bound based on
  nonnegative vertex heights, while final triangle tolerances remain unchanged.
  Origin-relative plane numerators and normals use the bounded 4,096-cell cache;
  changing or mutable origins, repainting and cuts invalidate/rebuild correctly.
- Prepared stair selections cache a spatial hierarchy. Exact candidate hits
  bound later groups; coincident candidates use the original fine-grid path to
  preserve ordering. Small selections retain the existing path and fine-index
  construction retains its 2,048-entry work bound/fallback.
- `tools/profile_workloads.py` profiles the real `benchmark_pair.frame` workload,
  including varying yaw, simulation and walking. Reports use unused paths and
  retain source manifests. Profiles are diagnostic counts, not acceptance FPS.

`smooth-moving-profile-2026-11-12.*` records the original moving workloads.
`smooth-projected-moving-profile-2026-11-12.*` shows limited Warden query reduction
and larger stair-candidate reduction. `smooth-grouped-moving-profile-2026-11-12.*`
identifies excessive duplicate early queries at Ridge approach (432,521 queries
over 60 frames), motivating the bounded policy.

## Correctness and native tests

- `smooth-final-exact-2026-11-12.json`: **204 complete frame and pre-scenery depth
  pairs**, all 34 roles, evolving simulation/yaw plus wide/tall views and changed
  pitch; **34,816 standalone terrain rays** match distance/material/normal exactly
  against `a3d044f`. Shared combat functions and Door identity avoid cross-import
  presentation artifacts when using the same simulated world.
- Earlier exact reports are retained. The first projected report has 12 HUD
  prompt differences from mismatched imported Door classes, with all depths
  already equal. Its corrected companion passes; this was a harness error.
  Traversal, grouped and bounded intermediate exact reports also pass.
- **400 native-console tests**, zero failures/errors, **one sandbox cursor skip**,
  159.356 seconds. Full authoritative output:
  `smooth-native-tests-2026-11-12.txt`. The JSON summary was reconstructed from
  that log after the temporary runner tried serializing a skipped TestCase object.
  The skipped desktop test reports `ClipCursor denied; run outside the sandbox`.
  Native console input tests ran successfully. No input implementation changed.
- New focused checks cover projected bounds/near planes and work, bounded early
  misses, foundation reads, moving/mutable ray origins, and 1,004 solid hierarchy
  comparisons including overlaps, limits and coincident faces.

No backlog item is completed by this performance pass. The user added a report
of walking automatically onto castle-wall blocks; it remains uninvestigated in
`user_designated_milestones.md` and must be preserved.

## GPU scope

The user approved a prototype after discussion of GPU acceleration. Use an
isolated `.venv-gpu` and optional dependencies; the existing CPU launch and
standard-library/Python 3.10 path must keep working. Measure GPU dispatch **and
readback**, and compare visibility/material/depth with the CPU reference before
integrating or selecting a default. GPU float precision and transfer cost are
unverified concerns, not grounds to relax exact occlusion.

Primary API references: [offscreen compute](https://wgpu-py.readthedocs.io/en/latest/guide.html#offscreen),
[compute buffers](https://wgpu-py.readthedocs.io/en/latest/utils.html#compute-with-buffers),
[installation/platform requirements](https://wgpu-py.readthedocs.io/en/latest/start.html).
The selected wgpu 0.33.0 requires Python 3.11+ for the optional prototype; the
CPU game retains Python 3.10+. Its dependency is justified by GPU access that
the Python standard library does not supply. No GUI canvas is required.

## Integrated GPU checkpoint and handoff

The user subsequently authorized complete integration after a demonstrated GPU
advantage. Integration is implemented in `ascii3d/gpu_renderer.py` and
`ascii3d/gpu_static.wgsl`; `Renderer` shares all existing shading/presentation.
App launch supports `--renderer auto|cpu|gpu`, auto uses available hardware,
and missing/lost devices retain CPU operation. `run.bat` prefers `.venv-gpu`.
This is functional integration, **not completed performance acceptance**.

- `gpu-static-flat-all-120x40-2026-11-12.json` passes all 34 roles and **428,400**
  sampled depth/material/normal/coverage checks with clean audio. Stage-only
  results justified integration; they are not whole-game FPS comparisons.
- Production parity reports `gpu-integrated-parity-first`, `-fast`, and
  `-compact` each pass **204 complete image pairs** with no coverage changes.
  Maximum float64 depth difference is **2.85e-14** from arithmetic ordering;
  no existing tests or thresholds were relaxed. CPU fallback resolves uncertain
  candidates. Compact transfer uses 16 bytes per pixel; the diagnostic retains
  full candidate records separately.
- Full live-audio ABBA against **d20cd0d**, 120x40/60 frames: first integration
  passes **11/24**, traversal-setup repair **13/24**, and compact transfer
  **14/24**. Reports are `gpu-integrated-first-120x40-2026-11-12.json`, `-fast-`
  and `-compact-`; all remain retained. The last run has zero underruns and
  recoveries, 85.54 ms maximum refill interval.
- The compact run still fails courtyard, meadow, grass_close, Warden, map,
  tree_close, tree_canopy, castle_exterior, west_meadow and east_meadow.
  Warden mean/p95 regress **22.42%/19.96%** against d20cd0d; several cheaper
  views pay more host finishing overhead than their CPU query cost. Indoor,
  bridge, river, east-bridge, combat and Great Hall roles improve. Do not waive
  remaining failures or replace the original control.
- **420 native-console tests pass with zero failures/errors and one sandbox
  desktop cursor skip**. Hardware GPU tests run, including device loss, exact
  CPU fallback, edits/rebuilds, resizing, cell aspect, doors and enemy rendering.
  Evidence: `gpu-integrated-native-tests-2026-11-12.json` and `.txt`.
- `gpu-native-demo-2026-11-12.json` records **100 actual game frames at 160x50**,
  Ridge Hall auto-walking, GPU backend, live sound, exit 0 and resource cleanup.
  All loading phases, including 100%, were observed. Mean render time after
  five warmups is **28.371 ms**; loop intervals/terminal-write costs were not
  separately recorded, so this is not an asserted FPS measurement. Audio has
  zero underruns/recoveries, 61.0 ms maximum refill interval. Physical appearance
  in the user's tabbed terminal and speakers remains unconfirmed.

Loading percentage milestone 2 is verified by eight focused tests, the full
suite and native startup. Cleanup milestone 6 removes temporary controls/probes
and caches while retaining failed runs, source manifests, optional dependencies
and reusable verification tools. The wall-block automatic step-up report remains
uninvestigated; no movement behavior was changed in this session.

Resume performance work by profiling GPU host refinement and considering a
measured CPU/GPU selection policy for cheaper views. Such a policy is a proposal,
not implemented. Then compare complete frames and run serial matched live-audio
ABBA with unchanged mean/p95 gates, including larger terminals. Full GPU
architecture approval is already granted; no renewed approval is needed.

The user explicitly reaffirmed wrapping up at 15% remaining usage. The latest
check was **12% short-window / 47% weekly remaining** during final handoff; new
feature work stopped. No performance acceptance or completed FPS fix is claimed.

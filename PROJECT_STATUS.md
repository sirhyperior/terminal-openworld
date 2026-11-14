# Project Status

Last reviewed: **2026-11-14**. Standing rules: [AGENTS.md](AGENTS.md).
User backlog: [backlog.md](backlog.md). Launch/controls: [README.md](README.md).

## Current checkpoint

- **Approved grayscale/world overhaul is in progress, not complete.** The user
  approved the six-destination ruined gothic world, shared non-box geometry,
  grayscale-first output, and rich color throughout only after play review of
  the finished grayscale milestone. Approved layout, evidence and remaining
  implementation steps: [redesign checkpoint](benchmarks/visual-redesign-2026-11-14.md).
- Implemented foundation: shared material/normal/distance shading; 16 neutral
  foreground levels and compact `StyledFrame` style/material buffers;
  `--color-mode gray|mono`; exact CPU convex rays/collision/support; indexed
  exact GPU convex candidates with float64 refinement/fallback; explicit
  CPU/CPU and GPU/GPU benchmark selection and changed-map role manifests.
- **The playable map is still the original layout.** Construction kit, six
  rebuilt destinations/routes, mist/dust/embers, full actor art and UI/loading
  art pass are outstanding. No full-color implementation has begun.
- Preserve the prior uncommitted loading/movement fixes. The verified control
  `benchmarks/visual-control-2026-11-14.zip` contains 83 working files and their
  SHA256 manifest, including those fixes; HEAD alone is not the control.
- Existing movement, E targeting, doors, sound events, fixed-step simulation,
  CPU dependency policy and optional GPU remain. Color rollback checkpoint
  a2049c3/abandoned archive is history, not the active implementation baseline.
- Changes remain uncommitted pending successful user implementation review.

## Latest validation and limits

- Geometry agent: 34 convex/surface/prepared-query/block-walking checks passed,
  including all 13 authored flights. GPU agent: 16 real-hardware GPU checks
  passed, including convex AABB misses, tangent seams and geometry edits.
- **Final native-console suite: 475 tests passed, zero failures/errors, one
  sandbox ClipCursor skip; 169.703 seconds.** The native report verifies real
  console handles and unchanged ascii3d/tests/tools source hashes. Earlier
  123-check and full-suite failures remain retained; the shadow-cache leak,
  turf lighting and foliage translation regressions are repaired. Evidence:
  `visual-foundation-native-2026-11-14.txt/.json`.
- **CPU/CPU same-geometry live-audio ABBA fails 33/34 roles** at 120x40,
  60 frames, unchanged 15% mean/p95 limits. Only stair walking passes. Audio has
  zero underruns/recoveries, maximum refill gap 57.78 ms. Raw report:
  `visual-foundation-cpu-live-2026-11-14.json`. GPU/GPU passes only **4/34**, also
  failing acceptance; audio has zero underruns/recoveries, maximum gap 60.43 ms.
  `visual-foundation-gpu-live-2026-11-14.json` retains that complete run. Both
  reports have the correct explicit backends and unchanged engine source hashes.
  No jobs remain; temporary helpers, previews and extracted control are removed.
  Native terminal-write cost, actual fullscreen, slow-turn readability, physical
  mouse/speaker review and Python 3.10 remain unverified. Four software-rendered
  grayscale views were inspected; this is not native terminal visual approval.
- Old lag-location diagnostic is retained. Exact (215.2,187.4,Z10) overlaps
  geometry, so its timings are not a playable-camera acceptance benchmark or a
  confirmed reproduction. Keep that backlog issue open.
- Historical d20cd0d CPU/GPU acceptance remains independently open at 14/24 roles.
  Current 40 FPS is a cap/target, not established performance in every scene.
  Preserve 15% mean/p95 limits and all failed reports.

## Session cutoff and next steps

The user-required usage cutoff was reached. No further implementation starts in
this session. Resume with shader/style-buffer profiling and optimization before
world authoring; the grayscale milestone is not ready for completion review.

## Resume commands

Finish foundation performance and CPU/GPU style/material-buffer parity checks
before authoring the replacement map.
Use native-console input checks; time jobs serially and use unused report paths.
Archive reference must include the previous working fixes, not just Git HEAD.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
$env:MONOLITH_GPU_TESTS='1'; $env:MONOLITH_DESKTOP_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv-gpu\Scripts\python.exe -B main.py --renderer gpu --color-mode gray
python -B main.py --renderer cpu --color-mode mono --keyboard-look
# Reconstruct the frozen working control only if absent:
Expand-Archive -LiteralPath benchmarks/visual-control-2026-11-14.zip -DestinationPath visual_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source visual_control_tmp --before-renderer cpu --after-renderer cpu --frames 60 --audio --save benchmarks/visual-next-cpu-unused.json
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source visual_control_tmp --before-renderer gpu --after-renderer gpu --frames 60 --audio --save benchmarks/visual-next-gpu-unused.json
```

Older required evidence: [benchmark index](benchmarks/README.md),
[loading](benchmarks/loading-screen-2026-11-13.md),
[movement](benchmarks/block-climbing-2026-11-13.md).

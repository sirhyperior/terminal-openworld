# Project Status

Last reviewed: **2026-11-16**. Standing rules: [AGENTS.md](AGENTS.md).
User backlog: [backlog.md](backlog.md). Launch/controls: [README.md](README.md).

## Current checkpoint

- **Stronger visibility is implemented for play review.** The user found the
  first palette-only lift insufficient. Ordinary surfaces now receive stronger
  ambient fill and use denser shadow characters, with a level-4 floor retained by
  actor recesses. Color/grayscale foregrounds start at 100/255. Highlights,
  surface texture and depth remain distinct; black backgrounds, geometry,
  simulation and sound are unchanged.
- The preceding color, surface-detail and particle work is committed at
  **e9e35b7**. This shadow adjustment remains uncommitted pending user play review.
  [Visibility evidence](benchmarks/visibility-2026-11-16.md) owns the current
  validation and the frozen comparison source.
- The **six-landmark world rebuild remains unimplemented**. The approved brief is
  in the [redesign checkpoint](benchmarks/visual-redesign-2026-11-14.md). Current
  particles, shared E interactions, input/accessibility and sound remain intact.

## Latest verification

- **69 rendering tests pass**, no skips, including surface/actor quality, shadow
  density and texture at near/far distances, readable actor recesses, hue/depth
  contrast, emission gradients, particles, exact occlusion and hardware CPU/GPU
  parity. Four sampled scenes retain identical depth buffers and surface coverage;
  glyphs and foreground levels deliberately change for readability.
- Software before/after comparisons were reviewed for the gatehouse, great hall,
  tree canopy and Warden in both color and gray. Actual terminal appearance still
  needs user play review.
- The 120x40/60-frame styled-color CPU/live-audio comparison against the frozen
  first lift **passes 34/34 roles**: maximum mean/p95 increases **5.14%/13.66%**,
  within the unchanged 15% limits. Source hashes/geometry match; audio has zero
  underruns/recoveries/errors and clean shutdown. This is incremental validation;
  historical failures remain open. No validation jobs remain active.
- At the preceding quality checkpoint, **534 native-console tests** passed
  (one cursor skip) and **204 CPU/GPU frame/depth pairs** passed. Its incremental
  CPU timing failed: **8/34 roles passed**. These remain historical results, not
  a rerun for the shadow change. See
  [quality evidence](benchmarks/visual-quality-2026-11-14.md).

## Open work and limits

- **Historical performance remains unresolved.** The quality increment, preceding
  color GPU p95 failures, grayscale foundation and d20cd0d comparisons retain
  their original limits and failed evidence. No slower control is promoted to a
  baseline. The 40 FPS cap is not a sustained-performance guarantee.
- Quality GPU incremental timing and native app diagnostics remain deferred.
  `quality_native_smoke_tmp.py` is retained for those pending 120x40/160x50 checks;
  remove it after they finish. Resume commands and controls are in the quality
  report. Prior native-output evidence is in the
  [color report](benchmarks/color-pass-2026-11-14.md).
- Physical mouse/speaker quality, actual fullscreen font/layout, POSIX held keys
  and Python 3.10 execution remain unverified. CPU has no mandatory dependencies;
  optional wgpu 0.33.0 uses Python 3.11+.
- World redesign, remaining blockiness, optimization and the separate sound
  overhaul remain in the backlog. Old lag position (215.2,187.4,Z10) overlaps
  geometry; its retained diagnostic is not a proven playable-camera reproduction.

## Resume / review commands

Run from the repository root; use a native console for input checks. Run timing
jobs serially and choose unused report paths. Required historical evidence and
controls are indexed in [benchmarks/README.md](benchmarks/README.md).

```powershell
.\.venv-gpu\Scripts\python.exe -B main.py --renderer gpu --color-mode color
python -B main.py --renderer cpu --color-mode gray --keyboard-look
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_color_presentation tests.test_presentation tests.test_shading tests.test_color_actors tests.test_color_integration tests.test_visual_quality tests.test_color_gpu_parity tests.test_surface_quality tests.test_actor_quality tests.test_particles -v
# Reconstruct the immediate visibility control only if absent:
Expand-Archive -LiteralPath benchmarks/visibility-control-2026-11-16.zip -DestinationPath visibility_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source visibility_control_tmp --reference-label first-shadow-lift --before-renderer cpu --after-renderer cpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/visibility-cpu-next-unused.json
```

# Project Status

Last reviewed: **2026-11-14**. Standing rules: [AGENTS.md](AGENTS.md).
User backlog: [backlog.md](backlog.md). Launch/controls: [README.md](README.md).

## Current checkpoint

- **Visual quality and particles are implemented for play review.** The user
  reported flat, uniform-colored bodies and weak grayscale depth. Visible actor
  faces now shade per character, with local material detail, broad armor bevels,
  dark recesses, pale highlights and a wider tonal range. Nearby tree trunks use
  curved shading. Grain and relief remain attached to their surfaces.
- Sparse dust/ash, pickup motes, fire trails and impact sparks use seeded world
  positions and simulation time. Shared depth tests hide them behind opaque
  geometry; labels remain readable. Work, draw counts and cached chunks are
  bounded. Existing wind, pickup and fire feedback supplies their sound context.
- `--color-mode color|gray|mono` remains available, default color. Black
  backgrounds, opaque geometry, plain snapshots, pause/help, terminal cleanup,
  E interactions, movement/collision and existing sound events are preserved.
- The **six-landmark world rebuild is still unimplemented**. No map, enemy AI,
  objectives or save system was added. Approved world brief remains in
  [redesign checkpoint](benchmarks/visual-redesign-2026-11-14.md).
- Changes remain uncommitted pending successful user play review. The foundation
  checkpoint is fe42316. `benchmarks/quality-control-2026-11-14.zip` preserves
  96 SHA256-verified pre-quality working files, including the preceding color
  changes; Git HEAD alone is not this comparison source.

## Latest verification

- **534-test native-console suite passed**, zero failures/errors, one sandbox
  ClipCursor skip, 184.823 seconds. Real native handles and unchanged
  ascii3d/tests/tools hashes are verified in the
  [native test report](benchmarks/quality-native-tests-2026-11-14.json).
- **204 complete CPU/GPU pairs across 34 roles pass** for glyphs, luminance,
  materials, effects, color/grayscale ANSI and depth coverage. Maximum depth
  difference is 2.84e-14, within the existing exact-ray comparison tolerance.
  GPU remains healthy; source hashes are unchanged. See the
  [parity report](benchmarks/quality-gpu-parity-2026-11-14.json).
- Quality performance acceptance **fails**: the complete 120x40/60-frame styled
  color-to-color CPU/live-audio comparison passes **8/34** roles. Maximum mean
  increase is **40.31%** (tree_canopy); maximum p95 increase is **39.72%** (Warden).
  Zero errors, underruns or recoveries; source hashes and world geometry match.
  The original run completed without a retry; inconclusive process enumeration
  did not indicate an actual interruption. All samples and failed gates remain.
  [Current quality evidence](benchmarks/visual-quality-2026-11-14.md) owns the
  timing state and final measurements, including any failed or recovered runs.

## Open work and limits

- The account usage window reached **13% remaining**. Work stopped after safely
  finishing the active CPU measurement. No validation jobs remain active.
  There is no usage-cutoff exception for this quality session. GPU incremental
  timing and native app diagnostics were not started and remain deferred.
  Retain `quality_native_smoke_tmp.py` for pending 120x40/160x50 native checks;
  remove it after those checks finish. Native output with live audio, frame
  pacing, output size and actual fullscreen review remain pending.
- Reviewed software previews and the extracted comparison tree were removed;
  the verified ZIP and required test/benchmark evidence remain.
- The user still needs to judge the latest appearance in the actual terminal.
  Physical mouse/speaker quality, actual fullscreen font/layout, POSIX held keys
  and Python 3.10 execution remain unverified. The CPU engine has no mandatory
  dependencies; optional wgpu 0.33.0 uses Python 3.11+.
- **Historical performance remains unresolved.** The preceding color increment
  passed CPU 34/34 but failed four GPU p95 roles. Earlier grayscale foundation
  CPU 1/34 and GPU 4/34, and d20cd0d 14/24 acceptance, remain independently open.
  The 40 FPS cap is not a sustained-performance guarantee. Keep the 15% mean/p95
  limits and all failed evidence; do not promote a slower control to a baseline.
- World redesign, remaining blockiness, optimization and the separate sound
  overhaul remain in the backlog. Old lag position (215.2,187.4,Z10) overlaps
  geometry; its retained diagnostic is not a proven playable-camera reproduction.
- Earlier color implementation and native-output evidence is linked in
  [color pass](benchmarks/color-pass-2026-11-14.md), including its matched host
  font, Gulim 8x16. Those runs do not validate the newer quality increment.

## Resume / review commands

Use a native console for input checks. Run timing jobs serially with unused paths.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
$env:MONOLITH_GPU_TESTS='1'; $env:MONOLITH_DESKTOP_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv-gpu\Scripts\python.exe -B main.py --renderer gpu --color-mode color
python -B main.py --renderer cpu --color-mode gray --keyboard-look
# Reconstruct the pre-quality control only if absent:
Expand-Archive -LiteralPath benchmarks/quality-control-2026-11-14.zip -DestinationPath quality_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source quality_control_tmp --before-renderer cpu --after-renderer cpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/quality-next-cpu-unused.json
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source quality_control_tmp --before-renderer gpu --after-renderer gpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/quality-next-gpu-unused.json
.\.venv-gpu\Scripts\python.exe -B quality_native_smoke_tmp.py 120 40 benchmarks/quality-native-color-120x40-2026-11-14.json
.\.venv-gpu\Scripts\python.exe -B quality_native_smoke_tmp.py 160 50 benchmarks/quality-native-color-160x50-2026-11-14.json
```

Required older evidence remains linked in [benchmark index](benchmarks/README.md).

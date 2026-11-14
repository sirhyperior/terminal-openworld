# Surface depth and particle quality

The user requested particles and, primarily, visibly better detail/depth within
one body. Both Instagram references were rechecked in the browser: their forms
use deep shaded gaps, bright fine highlights, curved silhouettes and sparse
animated points. A single color sampled at each face center was a concrete
limitation in the previous actor renderer.

## Implemented changes

- Optional per-character shader callbacks in the existing triangle, quad and
  clipped stroke rasterizers reconstruct perspective-correct world positions.
  The constant-glyph path is retained. Shader callbacks run only for visible
  depth-test winners; geometry/depth remain independent of shade.
- Actor surfaces use stable object-local coordinates; Warden parts use closed
  chamfered solids, including upper/lower bevel bands, recessed visor and carved
  details. Fire/crystal intensity varies across a face. Depth-only combat prepass
  uses identical geometry and zero material-shading calls.
- Stronger directional relief, weathered stone, mortar/edge wear, wood/bark grain,
  straw, bone cracks and view-dependent metal/water glints. Deep grayscale levels
  now reach 9/255; shadows cool/desaturate and highlights become paler. Nearby
  tree stems/branches receive per-character cylindrical normal shading.
- Analytic seeded dust/ash, fire trails, impact embers and small pickup motes use
  simulation time and world positions. Shared depth hides particles; they never
  modify opaque depths. Labels/UI and bright fire/crystal cores are protected.
  Authored-world ambient search is local; generic test worlds remain undusted.
- Budgets: at most 256 candidates, 96 ambient candidates, 128 draws and 64 retained
  particle chunks, scaling down with viewport size. Existing actor/scenery LOD
  and source limits remain. Existing wind/pickup/fire events and cues cover these
  decorative effects; no new gameplay, audio synthesis or input binding.

## Evidence and controls

`quality-control-2026-11-14.zip` preserves 96 working files and a SHA256 manifest
of the actual pre-quality color source, including earlier uncommitted changes.
This does not replace any historical accepted performance reference.

- `quality-first-focused-2026-11-14.txt`: 108 tests, one shadow-back Warden range
  failure. Broad shallow bevels were strengthened and the >=6 per-view condition
  retained; four measured body spans became 14, 12, 10, 14 levels. Failed evidence stays.
- Flat-face tests establish multiple shades within one face, stable texture
  coordinates and identical shader-on/off depth coverage. A rendered close-scene
  comparison expanded from 4 brightness levels to 13; color and grayscale previews
  both show recesses, highlights and material texture. Software previews are not
  physical terminal approval and are removed after review.
- `quality-gpu-parity-2026-11-14.json`: 204 pairs across 34 roles pass, zero errors
  or color/material/effect/ANSI mismatches. Coverage matches; maximum depth error
  is 2.84e-14. Source hashes unchanged.
- `quality-native-tests-2026-11-14.txt/.json`: 534-test native console suite passes,
  zero failures/errors, one sandbox ClipCursor skip, 184.823 seconds. Real console
  handles and unchanged ascii3d/tests/tools source hashes are verified.

The 15% mean/p95 gates remain unchanged. World voxel/terrain/
solid geometry and cameras match the control; actor render silhouettes are
deliberately different. New-versus-old image equality is not an acceptance test;
current CPU-versus-GPU presentation/depth equality remains required.

## Performance and remaining checks

`quality-cpu-styled-live-2026-11-14.json/.txt` is complete: **8/34 roles pass**,
26 fail, zero errors. CPU-to-CPU, 120x40, 60 samples per variant, per-frame ABBA,
color-to-color styled output including ANSI serialization and live native audio.
Maximum mean increase: **40.31%** at tree_canopy. Maximum p95 increase: **39.72%**
at warden. Audio submitted 6,715 buffers with zero underruns/recoveries and clean
shutdown. Source hashes remained unchanged and geometry fingerprints match.
The original run continued despite inconclusive process enumeration; no retry
or replacement of its samples was needed. Performance acceptance fails.

Usage reached 13% remaining, triggering the repository's 15% cutoff. GPU-to-GPU
timing and actual native app output/pacing/byte measurements were not started.
The prepared `quality_native_smoke_tmp.py` passed syntax checking only; its
runtime is unverified. Run its two diagnostics serially after the timing job.
The 40 FPS cap remains; sustained 40 FPS is not established. Historical failures
remain independently open. Changes are uncommitted pending user play review.
Reviewed previews and the extracted control were removed; the archive remains.

## Resume / reproduction

```powershell
# Extract only if absent, and choose unused report paths.
Expand-Archive -LiteralPath benchmarks/quality-control-2026-11-14.zip -DestinationPath quality_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source quality_control_tmp --before-renderer cpu --after-renderer cpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/quality-next-cpu-unused.json
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source quality_control_tmp --before-renderer gpu --after-renderer gpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/quality-next-gpu-unused.json
.\.venv-gpu\Scripts\python.exe -B quality_native_smoke_tmp.py 120 40 benchmarks/quality-native-color-120x40-2026-11-14.json
.\.venv-gpu\Scripts\python.exe -B quality_native_smoke_tmp.py 160 50 benchmarks/quality-native-color-160x50-2026-11-14.json
```

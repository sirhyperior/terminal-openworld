# Readable shadow foregrounds

This records the first palette-only lift. The user found it insufficient;
[stronger visibility](visibility-2026-11-16.md) owns the current implementation.

The user reported that the preceding depth/color pass made shadowed areas much
too dark. Shared foreground levels previously began at 9, 16 and 25 out of 255.
Directional shade, texture recesses, distance fading and actor shade biases
frequently select those low levels, making visible geometry disappear into black.

## Change and visual checks

The shared 16-level foreground table now runs from 70 to 255, with a gradual lift
through the shadows and midtones. Level 1 rises from 16 to 78. Both material color
and neutral grayscale use this table; all palettes remain precomputed. Glyphs,
lighting calculations, geometry, depth tests, sound and simulation are unchanged.
AIR and empty backgrounds remain black, and the brightest endpoint remains white.

`shadow-control-2026-11-16.zip` is a Git archive of `ascii3d/` and `tools/` at
`e9e35b7`, the user's preceding color/depth checkpoint. Its SHA256 is recorded in
`shadow-frames-2026-11-16.json`. It isolates this palette change and does not replace
any historical accepted performance reference.

- `shadow-focused-2026-11-16.txt`: **44 focused tests pass**, no skips. Coverage
  includes low-end foreground luminance across 12 ordinary materials and all 16
  fog/firelight combinations, ordered tones, retained shadow hue/depth contrast,
  ANSI serialization, actor detail, occlusion and hardware CPU/GPU parity.
- `shadow-frames-2026-11-16.json`: indoor gatehouse, great hall, tree canopy and
  Warden at 120x40 and simulation time 2.0 have identical before/after visible
  cells, style levels, materials and effects. Only their displayed RGB changes.
- Reviewed software comparisons in color and gray show more visible shaded
  walls, timber and actor recesses, retaining pale highlights and darker texture.
  The temporary previews use System.Drawing/GulimChe at 8x16 cells; this is a
  software review, not actual fullscreen terminal approval. No new dependencies.

Reviewed previews, temporary probe scripts and the extracted control were removed.
The control ZIP, focused-test output and frame/timing evidence remain retained.

## Incremental timing

The serial CPU comparison **passes 34/34 roles**, with no errors. The report and
raw samples are saved in `shadow-cpu-styled-live-2026-11-16.json`, with console
output in the matching `.txt`. It uses identical geometry, 120x40, Python 3.14.4,
60 samples per variant, per-frame ABBA, color-to-color styled output including
ANSI serialization and live native audio. Maximum mean increase is **1.69%**
(lodge); maximum p95 increase is **5.54%** (indoors), within the unchanged 15%
limits. Audio has zero underruns/recoveries/errors and clean shutdown. Post-run
before/after engine hashes match the report's source manifests. No validation
jobs remain active. GPU timing was not rerun for this shared palette adjustment;
the focused hardware presentation-parity check passes.

The older quality/color/GPU performance failures remain independently open;
see [quality evidence](visual-quality-2026-11-14.md) and the
[benchmark index](README.md). This adjustment does not establish whole-game FPS.

## Reproduction

Choose unused report paths and run timing jobs serially.

```powershell
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_color_presentation tests.test_presentation tests.test_shading tests.test_color_actors tests.test_color_integration tests.test_visual_quality tests.test_color_gpu_parity -v
Expand-Archive -LiteralPath benchmarks/shadow-control-2026-11-16.zip -DestinationPath shadow_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source shadow_control_tmp --reference-label e9e35b7 --before-renderer cpu --after-renderer cpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/shadow-cpu-next-unused.json
```

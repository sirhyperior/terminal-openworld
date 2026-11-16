# Stronger surface visibility

The user found the first 70/255 palette lift insufficient during play review.
Shadow-facing surfaces still received only 10% ambient light and often quantized
to level 1 with sparse dot glyphs. A brighter dot did not reveal enough surface.

## Resulting behavior

- Ordinary surfaces now receive 30% ambient fill, with directional light retaining
  the remaining range. After the existing distance/local-light calculations,
  display brightness uses `0.24 + 0.76 * brightness` before selecting both the
  foreground level and the glyph. Dark walls retain denser characters and texture.
- The ordinary surface floor is level 4. Shared actor strokes and recessed face
  details retain that floor when applying their authored shade biases.
- The common foreground table now starts at 100/255, up from the first lift's 70.
  Color and grayscale both use it. Fog still cools distant surfaces, textures
  remain attached to their surfaces, and bright highlights stay distinct.
- Fire/ember/arcane lighting and emission levels retain their preceding calculation
  and edge/core gradients. Their low-level RGB also benefits from the common
  palette lift. Black backgrounds, geometry, exact depth tests, simulation, input
  and sound are unchanged. No dependency or architecture change.

`visibility-control-2026-11-16.zip` freezes **40 actual working source files** from
the first shadow lift, including `ascii3d/`, `tools/` and a SHA256 manifest. It is
an incremental comparison source, not an accepted historical performance baseline.
The first lift's evidence remains in [shadow-readability-2026-11-16.md](shadow-readability-2026-11-16.md).

## Validation

- `visibility-focused-final-2026-11-16.txt`: **69 rendering tests pass**, no skips,
  including all surface/actor quality tests, shadow glyph density and texture at
  distances 2/24/48, actor recess readability, emission gradients, particles,
  exact opaque raster coverage, light occlusion and hardware CPU/GPU parity.
- The earlier `visibility-precheck-2026-11-16.txt` preserves five failures from
  older tests that required nearly black foregrounds, a >4x lit/shadow RGB ratio
  and >190 RGB contrast. Those expectations conflict with the user's readability
  correction. Tests now require readable shadows, >=4 face-level separation,
  >=45 RGB directional contrast, and >=10 distinct tones on a textured lit plane.
- `visibility-focused-first-2026-11-16.txt` preserves three failures in the new
  texture fixture: it varied X/Y against a +X normal with Z fixed at a floor seam.
  The final fixture samples the actual Y/Z surface plane; its requirements remain.
- `visibility-frames-2026-11-16.json`: all four scenes retain **identical depth
  buffers and ordinary-surface cell counts**. Before/after glyphs/styles change
  deliberately. Software color/gray comparisons were reviewed at 8x16 cells with
  System.Drawing and requested GulimChe; terminal appearance still needs play review.

| Scene | Mean foreground before / after | Sparse surface cells before / after |
| --- | --- | --- |
| Gatehouse | 141.68 / 204.41 | 969 / 0 |
| Great hall | 131.35 / 203.67 | 1,224 / 0 |
| Tree canopy | 79.52 / 164.94 | 4,007 / 0 |
| Warden | 148.97 / 210.85 | 654 / 0 |

Foreground means use weighted RGB over ordinary visible surface cells, excluding
UI/particles/emissive materials; they do not measure physical screen brightness.
Sparse means spaces, periods or commas. These fixed 120x40/time-2.0 scenes show
readability changes, not a replacement for the user's fullscreen assessment.

## Incremental timing

The serial CPU/live-audio comparison **passes 34/34 roles**, with identical
geometry, 120x40, Python 3.14.4, 60 samples per variant, per-frame ABBA, and
styled-color generation plus ANSI serialization. Maximum mean increase is
**5.14%** (wall_walk); maximum p95 increase is **13.66%** (river), within the
unchanged 15% limits. Audio has zero underruns/recoveries/errors and clean
shutdown. Raw evidence is in `visibility-cpu-styled-live-2026-11-16.json` and its
matching `.txt`.

Post-run source hashes match both manifests; the control matches the first lift's
recorded source, and all 40 archived SHA256 entries verify. No validation jobs
remain active. Historical quality/color/GPU performance failures remain
independently open; this does not establish whole-game FPS. GPU timing was not
rerun; the focused hardware presentation-parity test passes.

## Reproduction

Run timing jobs serially and choose unused report paths. Extract only if absent.

```powershell
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest tests.test_color_presentation tests.test_presentation tests.test_shading tests.test_color_actors tests.test_color_integration tests.test_visual_quality tests.test_color_gpu_parity tests.test_surface_quality tests.test_actor_quality tests.test_particles -v
Expand-Archive -LiteralPath benchmarks/visibility-control-2026-11-16.zip -DestinationPath visibility_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source visibility_control_tmp --reference-label first-shadow-lift --before-renderer cpu --after-renderer cpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/visibility-cpu-next-unused.json
```

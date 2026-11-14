# Rich foreground color pass

The user requested color immediately, superseding the earlier grayscale-review
prerequisite, and explicitly authorized continuing beyond the standing usage
cutoff for this pass. The account limits had also refreshed at implementation
start. This changes presentation on the existing map; the six-destination world
rebuild and historical renderer performance acceptance remain separate open work.

## Implementation

- Rich semantic material hues throughout: stone/steel, floors, timber/crates,
  paths, grass/leaves, water and bridges. Actor components carry explicit stone,
  straw, bone, timber, metal, rune, fire and ember identities.
- Sixteen luminance levels combine with four distance-fog bands and four warm
  firelight tiers. Fog cools/desaturates distant surfaces; warmth comes only
  from the existing bounded, exact-LOS light queries. No hue is inferred from
  the final character. Coincident offset/light positions safely avoid zero-length
  ray normalization.
- Reused foreground RGB/ANSI lookup rows preserve low/midlevel readability,
  white-hot fire cores and bright rune highlights. Effects/material/level buffers
  follow whichever glyph wins depth testing. Backgrounds remain black; empty
  cells cause no needless foreground changes and equal colors share runs.
- `--color-mode color|gray|mono`, default color. Plain snapshots remain ANSI-free.
  HUD health retains numerical/bar cues, with explicit health colors; E prompts
  and the map player marker have restrained accents. Map symbols keep materials
  in their cached cells. Native terminal dimensions/resets/resize stay shared.
- Fire glow/ember intensity uses simulation time; pause/help retain frozen time.
  Rendering color adds no gameplay action, interaction, synthesis or new audio
  event. Existing fire/weapon/impact sounds remain unchanged.

## Controls and evidence

`color-control-2026-11-14.zip` preserves and SHA256-verifies 90 working files,
including the exact grayscale source and source manifest. This is an incremental
control; it does not replace the older approved performance references.

- `color-first-focused-2026-11-14.txt`: 84 focused checks pass, one optional
  hardware skip in that invocation. Separate hardware verification below is real.
- `color-gpu-parity-2026-11-14.json`: **204 complete CPU/GPU pairs across 34
  roles pass**, zero errors or mismatches. Compares glyphs, luminance, materials,
  fog/warm effects, both color and grayscale ANSI, and exact depths. Final source
  hashes remain unchanged and GPU health is checked. Startup failures retain
  reports rather than claiming completion.
- Six software-rendered views inspected: castle exterior, canopy, diagonal river,
  great hall, active fireballs and Warden. Colors distinguish materials while
  retaining text and negative space. This does not establish the user's physical
  terminal, chosen font or speaker quality. Temporary preview files are removed.

`color-native-tests-2026-11-14.txt/.json`: **508-test native suite passed**, zero
failures/errors and one sandbox ClipCursor skip,163.678 seconds. Real console
handles and unchanged source hashes are verified. Matched timing and actual
terminal-write measurements follow after source-frozen runs complete.

## Incremental CPU result

`color-cpu-styled-live-2026-11-14.json/.txt`: **34/34 roles pass**, same geometry,
120x40/60 frames, CPU/CPU, live audio, styled frame plus ANSI serialization on both
variants. Maximum mean increase **8.42%** (east meadow), maximum p95 **13.35%**
(terrace walking), below the unchanged 15% gate. Audio: zero underruns/recoveries,
maximum refill gap 80.99 ms. All raw samples retained.

Mean serialized row bytes vary by scene: indoors 18,973.5¡æ19,633.7; close grass
22,561.7¡æ21,626.6; fireballs 23,218.0¡æ23,921.2. More color does not universally
increase run count; adjacent identical RGB values and blank cells share runs.
These bytes exclude terminal-origin controls/CRLF and actual native writes.

`color-gpu-styled-live-2026-11-14.json/.txt`: **30/34 roles pass**. Courtyard,
lodge, tree canopy and ridge roof fail p95. The unchanged 15% gate is not accepted.
Both runs have zero audio underruns/recoveries and unchanged source hashes;
passing CPU does not close GPU or earlier whole-engine failures.

The tail diagnostic helpers produced zero timed samples: one audio-child report
reservation failure, then a native 0xc0000008 INVALID_HANDLE during frozen GPU
adapter enumeration. All launch/details/partial artifacts are retained under
`color-gpu-tail-diagnostic*`; no tail attribution is supported by those probes.

## Actual native output

Four 60-frame actual GPU apps passed: frozen gray/current color at 120x40 and
160x50. Their `color-native-before-gray-*` / `color-native-after-color-*` JSON
reports preserve per-frame work, draw/flush times, paced intervals, actual bytes,
poses, console state, adapter/audio health and unchanged source hashes. Each
restores modes, cursor and alternate screen and keeps black backgrounds. Color
runs contain nonneutral foregrounds; demo movement confirms they were not paused.

Actual host font was **±¼¸²Ã¼ 8x16**, substituted for the requested Consolas 16 but
identical in all four runs. Timings below are diagnostics, not acceptance: demo
positions vary with real elapsed time.

| View | Gray work mean/p95(ms) | Color work mean/p95(ms) | Color draw/flush mean/p95(ms) |
| --- | --- | --- | --- |
| 120x40 |25.605/33.517|26.528/37.039|4.263/8.107|
| 160x50 |37.572/46.065|37.744/51.680|6.081/8.282|

Color paced intervals mean/p95: 29.945/40.152ms and 37.733/52.303ms. Mean payload:
18,457 and 27,858 bytes, about 2% above gray. All four runs have zero audio underruns
or recoveries. These results do not establish stable 40 FPS or the user's physical
Windows Terminal/font/speaker quality. Temporary helpers, previews and extracted
control are removed; no jobs remain. The source archive and all evidence stay.

## Measurement method

Benchmark `--presentation plain` preserves historical timing semantics. New
`--presentation styled --before-color-mode gray --after-color-mode color` times
the full styled frame and ANSI row serialization on both variants. It records
raw row-byte samples (including ANSI, excluding CRLF/cursor control) separately
from raw frame-time samples, with unchanged 15% mean/p95 gates and explicit
CPU/CPU or GPU/GPU selection. It does **not** include native writes.

Run live audio jobs serially at 120x40, 60 frames, identical geometry/cameras,
Python and hardware. Preserve failed/incomplete runs; final native application
measurements include actual terminal draws/flushes and pacing separately.

```powershell
Expand-Archive -LiteralPath benchmarks/color-control-2026-11-14.zip -DestinationPath color_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source color_control_tmp --before-renderer cpu --after-renderer cpu --frames 60 --audio --presentation styled --before-color-mode gray --after-color-mode color --save benchmarks/color-next-cpu-unused.json
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source color_control_tmp --before-renderer gpu --after-renderer gpu --frames 60 --audio --presentation styled --before-color-mode gray --after-color-mode color --save benchmarks/color-next-gpu-unused.json
.\.venv-gpu\Scripts\python.exe -B tools/verify_gpu_renderer.py --color-mode color --save benchmarks/color-next-parity-unused.json
```

# Fullscreen optimization

Reviewed 2026-11-21 against the committed `df643ea` engine. The Linux x86-64
host used Python 3.12.14 and an AMD EPYC 9V74. Timings here compare CPU to CPU,
with audio disabled. Windows GPU and live-audio results are recorded in the
earlier reports with their own controls and configurations.

## Changes and diagnosis

The [160×50 profile](optimization-cpu-profile-2026-11-21.txt) used eight
instrumented frames per role after five warmups. At Thornwatch's upper floor,
solid-tree traversal took 65% of profiled scene time, including about 686,000
convex tests and 1.1 million bounding-box tests. Material shading also took
32–39% of profiled scene time in the gatehouse, castle exterior and east
meadow. The [source manifest](optimization-cpu-profile-2026-11-21.sources.json)
identifies the profiled engine.

- Build two-piece BVH leaves and choose the median split with the smallest
  area-weighted child bounds. Traverse groups by ray entry depth and reuse
  each entry when the nearest exact hit shortens the remaining ray. Coincident
  solid hits still use the existing grid order.
- Compute texture coordinates and grain only for the materials that use them.
  Floors calculate their own seams directly. The shading formulas and
  foreground metadata retain their existing inputs and outputs.

The [first split and leaf diagnostic](optimization-cpu-tree-first-2026-11-21.json)
used 20 styled-color frames at 160×50 at eight identical poses. It preceded
entry ordering and the shading change. Lodge, ridge upper, ridge roof and
terrace walk improved 14.8–20.7% in mean and 11.2–17.0% at p95. The other four
roles stayed within the existing 15% mean and p95 gates.

## Matched timings

The [160×50 comparison](optimization-cpu-160x50-2026-11-21.json) measured 60
frames per variant in per-frame ABBA order with five warmups. Geometry hashes
and all 34 camera poses matched. The timer includes foreground generation,
ANSI serialization and each role's usual simulation workload. Terminal writes
are measured separately. All 34 roles passed the established 15% mean and p95
regression gates. Mean improved in 33 roles and p95 improved in 31. The three
roles within the absolute 33.33 ms p95 frame budget were tree canopy, citadel
roof and the highland map. The control had two.

| 160×50 role | Control mean / p95 ms | Current mean / p95 ms | Change mean / p95 |
| --- | ---: | ---: | ---: |
| Lodge | 346.10 / 396.30 | 278.38 / 360.73 | −19.6% / −9.0% |
| Ridge approach | 353.34 / 386.19 | 281.51 / 312.27 | −20.3% / −19.1% |
| Ridge upper floor | 251.56 / 281.17 | 195.46 / 215.57 | −22.3% / −23.3% |
| Ridge roof | 148.91 / 159.38 | 114.57 / 127.18 | −23.1% / −20.2% |
| Terrace walk | 351.53 / 374.06 | 278.36 / 300.03 | −20.8% / −19.8% |
| Stair walk | 321.35 / 348.21 | 236.02 / 262.72 | −26.6% / −24.6% |

The [240×80 comparison](optimization-cpu-240x80-2026-11-21.json) kept the same
eight roles as the first diagnostic and measured 20 frames per variant. All
eight roles passed the relative gates, mean improved in all eight and p95
improved in seven. None met the 33.33 ms p95 budget. The fastest p95 was meadow
at 125.65 ms, and the slowest was lodge at 691.68 ms.

| 240×80 role | Control mean / p95 ms | Current mean / p95 ms | Change mean / p95 |
| --- | ---: | ---: | ---: |
| Lodge | 808.71 / 869.52 | 607.38 / 691.68 | −24.9% / −20.5% |
| Ridge upper floor | 571.89 / 618.77 | 452.79 / 475.04 | −20.8% / −23.2% |
| Ridge roof | 363.82 / 387.98 | 285.19 / 318.83 | −21.6% / −17.8% |
| Terrace walk | 849.16 / 875.73 | 641.35 / 656.70 | −24.5% / −25.0% |

## Adaptive terminal pacing

Live play measures time through the terminal write and adjusts world sample
count. The output still fills the viewport. HUD, targeting text, map, reticle
and point effects are drawn at native size. Odd reduced dimensions retain a
center ray and aspect correction keeps the full viewport's field of view.
An exact visibility test still governs interactions and aimed labels. Lower
scene sample counts visibly coarsen textures and silhouette edges.

[Six live PTY runs](optimization-live-pty-2026-11-21.json) started at the
gatehouse and two collision-free Thornwatch benchmark poses, then exercised
120 frames each through the demo's movement and turn input. Times use the app
loop's monotonic frame starts, including terminal writes and cap waits. All
six filled the final cell, restored the terminal and finished with a 40 FPS
HUD reading. Mean frame time was 25.10–25.72 ms and p95 was 25.11–26.99 ms.
Ten of the 714 measured intervals exceeded 33.33 ms.

| Viewport and route | Renderer | Mean / p95 / max ms | Final scene grid |
| --- | --- | ---: | ---: |
| 160×50 gatehouse | Python CPU | 25.10 / 25.11 / 26.14 | 69×19 |
| 160×50 lodge | Python CPU | 25.50 / 26.19 / 51.42 | 25×7 |
| 240×80 ridge upper floor | Python CPU | 25.29 / 25.14 / 39.45 | 43×13 |
| 240×80 lodge | Python CPU | 25.66 / 26.99 / 63.64 | 21×5 |
| 240×80 lodge | Compiled solids | 25.72 / 26.23 / 53.38 | 21×5 |
| 240×80 ridge upper floor | Compiled solids | 25.20 / 25.12 / 33.44 | 49×15 |

Early PTY smoke runs exposed nonblocking stdin also making stdout nonblocking
when the launcher duplicated one descriptor. The POSIX reader now opens its
own descriptor, and the final runs use shared stdin/stdout to verify the fix.
Prewarming the initial view during loading reduced the first live interval
from as much as 181 ms to 25–34 ms in these runs. The
[earlier attempts](optimization-live-pty-diagnostics-2026-11-21.json) retain
the setup failures and prewarm control. Windows console drawing, hardware
GPU timing and live audio remain unverified on this host.

## Compiled solid traversal

An optional C library uses the prepared Python solid tree and double-precision
intersection math. Coincident hits keep the Python grid query. The library is
optional at runtime and built with strict floating-point flags. The normal
launcher automatically picks it up when the binary is installed and hardware
GPU rendering is unavailable. [Build commands](../README.md#renderer-backends)

The [20-frame full-detail comparison](optimization-native-160x50-2026-11-21.json)
used the tightened Python traversal as control and compared five 160×50 styled
roles. Mean and p95 improved 26–56% and 26–55% across lodge, ridge upper, ridge
roof and terrace walk. Indoors was +0.31% mean and +22.93% p95, which failed
the 15% gate. A [60-frame indoor follow-up](optimization-native-indoors-2026-11-21.json)
observed −3.17% mean and −6.61% p95. Both runs are retained. Full-detail lodge
still took 115.27 ms mean and 131.11 ms p95 in the compiled comparison.

[Exact frame parity](optimization-exact-parity-2026-11-21.json) compared
independent `df643ea` and compiled-backend worlds across all 34 camera roles.
All 102 sampled full-detail frames match pre-scenery opaque depths, glyphs,
foreground levels, material IDs, effects and ANSI rows. The samples include
160×50, 240×80 and pitched 80×60 views. Separate native geometry unit tests
exercise coincident hits, cache refresh, invalid ABI and Python fallback.

## Regression suite

`python -B -m unittest discover -s tests -q` ran 595 tests on Linux with the
native library present. It reported 20 skips and 10 failures. All 10 failures
reproduced when the nine affected test methods were rerun from `df643ea`. They
cover the unrotated stair-camera assertion, the 13-flight aggregate test, the
Reliquary shortcut, the third river bridge, the animated scenery comparison,
the generated foundation/road fixture and the Ashgate-to-Thornwatch grade. The
additional single-cell glint expansion and extreme-aspect check passed
independently.

## Resume

Run on a consistent host with report paths that have never been used.

```bash
monolith_control=$(mktemp -d /tmp/monolith-df643ea.XXXXXX)
git archive df643ea ascii3d | tar -x -C "$monolith_control"
python -B tools/benchmark_same_geometry.py --before-source "$monolith_control" \
  --reference-label df643ea --frames 60 --width 160 --height 50 \
  --presentation styled --before-color-mode color --after-color-mode color \
  --save benchmarks/optimization-cpu-next-160x50.json
python -B tools/profile_workloads.py lodge ridge_approach terrace_walk indoors \
  --frames 8 --width 160 --height 50 --save benchmarks/optimization-cpu-next-profile.txt
```

Run the same-geometry comparison with `--before-renderer gpu --after-renderer
gpu --audio` on the Windows GPU and audio device. Use the actual fullscreen
dimensions for that machine and retain the native terminal loop timings
separately. Profile the lodge and approach first. Those views remain expensive
across sampled headings at 160×50, within the existing world layout.

```bat
run.bat --demo --frames 120 --region thornwatch
run.bat --demo --frames 120 --region thornwatch --full-detail
```

# Full-resolution Windows renderer

The Windows checkout of `427dc70` was the control. Both variants used
Python 3.14.4, an RTX 3080 Laptop GPU via Vulkan, the auto renderer, the color
palette, and the whole terminal grid. GCC 14.2 built both native libraries with
`-O3 -ffp-contract=off -fexcess-precision=standard`. The control library
already accelerated exact solids and continuous terrain.

The candidate batches compact GPU hit refinement in float64. The CPU backup
can traverse the voxel atlas in one native call. The exact Python path still
handles ambiguous GPU rays and coincident solid faces as before. Batched
diffuse shading covers static opaque materials and wind-tinted grass in
scenes without local firelight. Water and animated overlays use the shared
rendering path.

## Appearance

All 102 [GPU frame pairs](full-detail-windows-render-parity-2026-11-21.json)
at 240×80 match the control in glyphs, foreground levels, material and effect
buffers, ANSI rows, and pre-scenery opaque depths. The 34 roles cover indoor
and outdoor views, movement, water, actors, the map, and fireballs. A separate
[voxel kernel replay](full-detail-windows-voxel-parity-2026-11-21.json)
matches the same fields for 102 frame pairs at 160×50, 240×80 and pitched
80×60. Every scene cell is traced.

The [Windows native suite](full-detail-windows-native-tests-2026-11-21.txt)
ran 611 tests, with two skips and ten failures. Repeating the nine affected
test methods on [the frozen control](full-detail-windows-control-failing-tests-2026-11-21.txt)
reproduced all ten failures. The [suite manifest](full-detail-windows-native-tests-2026-11-21.json)
records console availability and source hashes.

## Matched 240×80 workloads

The [paired live-audio benchmark](full-detail-windows-auto-240x80-2026-11-21.json)
uses five warmups and twenty measured frames per variant in ABBA order for
every role. Both variants use the same world fingerprint, camera poses, color
mode and native mixer. Timing includes simulation, audio updates and ANSI row
encoding. Terminal writes and frame-cap waits are measured separately in the
console runs.

Mean frame time fell 12.03–57.87% and p95 fell 9.83–53.60% across the 34
roles. All roles pass the existing 15% mean and p95 regression gates. None
reached 33.33 ms p95 at 240×80. Audio recorded zero underruns or recoveries.

| Role | Control mean / p95 ms | Candidate mean / p95 ms |
| --- | ---: | ---: |
| Indoors | 86.1 / 101.5 | 46.2 / 59.4 |
| Lodge | 153.6 / 177.3 | 71.7 / 91.2 |
| Highlands | 112.3 / 129.1 | 76.3 / 90.4 |
| Ridge upper floor | 137.1 / 159.5 | 57.8 / 74.8 |
| Terrace walk | 185.4 / 218.8 | 96.2 / 113.4 |

## Native Windows console

The real game loop drew 60 frames per run in a hidden classic Windows console
with the same 5×10 Consolas cells, 40 FPS cap, color mode, and live audio.
These report observed frame intervals, including console writes and cap
waits. Demo poses advance with elapsed time, so the separate ABBA benchmark
provides the matched workloads. Physical fullscreen remains unverified.

| Demo | Viewport | Control FPS / p95 ms | Candidate FPS / p95 ms |
| --- | ---: | ---: | ---: |
| Ashgate | 160×50 | 26.51 / 44.29 | 38.46 / 29.29 |
| Ashgate | 240×80 | 11.95 / 99.50 | 20.20 / 62.90 |
| Thornwatch | 240×80 | 5.83 / 213.57 | 10.71 / 116.15 |

- Ashgate 160×50 [control](full-detail-windows-control-ashgate-160x50-2026-11-21.json) and [candidate](full-detail-windows-candidate-ashgate-160x50-2026-11-21.json).
- Ashgate 240×80 [control](full-detail-windows-control-ashgate-240x80-2026-11-21.json) and [candidate](full-detail-windows-candidate-ashgate-240x80-2026-11-21.json).
- Thornwatch 240×80 [control](full-detail-windows-control-thornwatch-240x80-2026-11-21.json) and [candidate](full-detail-windows-candidate-thornwatch-240x80-2026-11-21.json).

At Thornwatch, mean GPU host refinement fell from 50.01 to 6.73 ms
with about 2,440 exact fallback rays per frame. Mean total render time fell
from 155.56 to 77.58 ms. Console write and flush averaged 9.54 ms
on the candidate. All six runs had zero audio underruns or recoveries.

## Rebuild and live timing

The built native library is picked up by the normal launcher. Rebuild it
on a fresh checkout before measuring. [Build commands](../README.md#renderer-backends)

To reproduce the matched comparison, extract `git archive 427dc70 ascii3d`
into a separate directory and build its DLL with the same compiler and flags.
From the current tree, use the GPU virtual environment to run the comparison.

```powershell
$controlDirectory = 'C:\path\to\control'
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source $controlDirectory --reference-label 427dc70 --before-renderer auto --after-renderer auto --frames 20 --width 240 --height 80 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/my-unused-comparison.json
```

```powershell
.\run.bat --frame-timing fullscreen-full-detail-timing.json
```

Use an unused report path. Enter fullscreen in the terminal and play through
both Ashgate and the Thornwatch approach. The report separates the game loop,
scene rendering, GPU refinement, terminal encoding, and terminal writes.

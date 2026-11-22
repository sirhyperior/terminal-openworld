# Irregular road paving validation

The control is the preceding staggered-cobble worktree with its original
native library. Its 49 engine and DLL fingerprints match the candidate in the
previous validated milestone. The candidate uses the irregular stone tile and
the rebuilt native lighting library.
[Previous road and combat comparison](roads-combat-feedback-2026-11-22.md)

## Visual comparison

At 120×40, the native renderer preview faces north along Ashgate at
(128.5, 63.5, 1) with pitch −0.42. Both frames contain 1,897 paving cells.
Mean road foreground sRGB luma falls from 184.78 to 130.42 (−29.4%). The
revised view shows varied irregular stones with rounded crowns and gaps
where the previous view showed repeating straight stripes. The focused
road, lighting and hardware parity suite passed 36 tests.

## Matched timing

Both series use the Ashgate approach at (128.5, 63.5, 1), facing north with
pitch −0.28, on the RTX 3080 Laptop GPU via Vulkan. Each ABBA run alternates
one frozen world and live waveOut worker per process. Both 120×40 and 240×80
cases warm up five frames before recording 40 styled color frames. The mean
and nearest-rank p95 pool 80 samples per variant and size. Timings include
world ambience sampling, rendering and ANSI encoding. Terminal writes and
physical fullscreen are outside the workload.

### Explicit GPU

GPU geometry with Python surface shading passed both 15% gates at 240×80.
The 120×40 case exceeded both gates. All four launches reported clean live
audio and the paving masks matched at each size.
[Explicit GPU samples and source hashes](road-appearance-gpu-live-2026-11-22.json)

| View | Control mean / p95 ms | Candidate mean / p95 ms | Mean / p95 change | Gate |
| --- | ---: | ---: | ---: | --- |
| 120×40 | 24.81 / 31.25 | 31.46 / 38.40 | +26.78% / +22.88% | Fail |
| 240×80 | 83.94 / 98.01 | 93.82 / 107.16 | +11.77% / +9.33% | Pass |

### Default auto renderer

Auto selected the hardware GPU with the matching native surface shading
library in each build. Both sizes passed the mean and p95 gates, with
unchanged paving masks and zero audio underruns or recoveries. The 240×80
p95 remains above 33.33 ms. The explicit GPU regression at 120×40 remains
open.
[Auto renderer samples and source hashes](road-appearance-auto-live-2026-11-22.json)

| View | Control mean / p95 ms | Candidate mean / p95 ms | Mean / p95 change | Gate |
| --- | ---: | ---: | ---: | --- |
| 120×40 | 20.62 / 25.57 | 23.03 / 26.33 | +11.72% / +2.98% | Pass |
| 240×80 | 64.19 / 76.63 | 67.15 / 87.37 | +4.61% / +14.02% | Pass |

Both render paths measured the same paving colors. Mean paving foreground
sRGB luma changed from 184.18 to 129.06 at 120×40 and from 184.60 to 129.02 at
240×80 in this timed camera pose.

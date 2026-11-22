# Cobble relief and split developer console validation

## Native split console

A hidden 160×50 Win32 console ran the full app with live waveOut audio and
hardware GPU selected by `auto`. Injected native key records verified the
106-column scene, divider and 53-column editor against the actual console
buffer. The scene stayed frozen and reused while typing. Settings immediately
updated monochrome, grayscale and color ANSI output, native and GPU rendering,
and the scene after teleporting to Thornwatch. A 1,200-cell budget showed a live
33-column preview beside the editor in a 60×20 viewport. Removing the budget
and pressing Esc restored the full view. Movement and audio resumed.

All 51 checks passed. The main screen, cursor and modes restored. The audio
worker stopped cleanly after 129 blocks, with zero underruns or recoveries.
In this diagnostic run the cached typing frame composed in 0.22 ms and
recorded no scene samples. The initial 106×45 scene redraw took 19.41 ms to
render, and the three same-size color-mode redraws ranged from 17.26 to
22.48 ms. These are individual frame phases from the native smoke.
[Native checks, frame timings and captured ASCII frames](dev-split-native-2026-11-23.json)

## Paving appearance

The matched Ashgate frames contain the same paving masks at each size.
At 120×40 the mean foreground luma difference between adjacent paved cells
rose from 7.28 to 8.21 across 1,368 road cells. At 240×80 it rose from 4.26
to 4.90 across 6,067 cells. Mean road foreground luma remained close to 129
on an sRGB 0–255 scale. The differences use horizontal and vertical pairs
whose cells are both paving.

## Matched road timing

The frozen control is the complete 2026-11-22 irregular paving worktree and
native DLL, verified against the 50 fingerprints in its earlier live-audio
report. The timed Ashgate road camera remained at (128.5, 63.5, 1), facing
north at pitch −0.28. Four isolated launches in ABBA order each warmed up five
frames and measured 40 frames per size with one world and one live waveOut
worker. Mean and nearest-rank p95 pool 80 samples per version and size on the
RTX 3080 Laptop GPU, Vulkan and Python 3.14.4. Timings cover ambience sampling,
scene rendering and styled ANSI encoding. Terminal writes, the open editor
and physical fullscreen are outside this matched rendering workload.
[Previous paving report and 120×40 explicit GPU regression](road-appearance-2026-11-22.md)

The initial attempt hit the existing five-second audio worker startup
deadline in one auto launch and all four explicit GPU launches. The replay
generated the same unmodified game sound bank before opening the worker.
Both variants still used live waveOut playback for all timed frames.
[Initial launches and incomplete comparisons](cobble-relief-live-cold-start-2026-11-23.json)

### Default auto renderer

Auto used GPU geometry plus the native surface shader. Both sizes passed the
15% mean and p95 gates. The 240×80 p95 remains above 33.33 ms. All four replay
launches completed with zero audio underruns or recoveries.
[Default auto timing samples](cobble-relief-auto-live-2026-11-23.json)

| View | Control mean / p95 ms | Candidate mean / p95 ms | Mean / p95 change |
| --- | ---: | ---: | ---: |
| 120×40 | 22.47 / 27.82 | 18.95 / 21.31 | −15.69% / −23.40% |
| 240×80 | 55.06 / 66.19 | 57.33 / 68.91 | +4.12% / +4.12% |

### Explicit GPU renderer

Explicit GPU uses Python surface shading. The 120×40 replay passed both
15% gates. The 240×80 case passed on mean and exceeded the p95 gate.
Neither candidate launch recorded a garbage-collection pause of 1 ms or more
in its five slowest 240×80 frames. All four launches had zero audio underruns
or recoveries.
[Explicit GPU timing samples](cobble-relief-gpu-live-2026-11-23.json)

| View | Control mean / p95 ms | Candidate mean / p95 ms | Mean / p95 change | Gate |
| --- | ---: | ---: | ---: | --- |
| 120×40 | 22.88 / 24.65 | 23.19 / 25.01 | +1.34% / +1.45% | Pass |
| 240×80 | 74.37 / 77.07 | 77.97 / 93.01 | +4.84% / +20.68% | Fail |

# Exact GPU performance follow-up

The control is `19ddeeb`. Each comparison uses the RTX 3080 Laptop GPU via
Vulkan, Python 3.14.4, the auto renderer, 240×80 terminal cells, five warmup
frames per variant, ABBA ordering, styled color and live Windows audio. The
timings include simulation, audio updates and ANSI encoding. Terminal writes
and physical fullscreen were outside these paired measurements. All three
completed comparisons recorded zero audio underruns and recoveries.

## Selective native voxel tracing

The first candidate reused the native voxel walker for rays rejected by the
GPU, with the existing exact analytic tests and dynamic depths still resolved
per frame. The 20-frame comparison passed 29 of 34 roles. Indoors, map,
training, great hall and citadel roof exceeded the unchanged 15% p95 limit.
Every role had a p95 above 33.33 ms. The candidate was withdrawn.
[Matched live run](gpu-fallback-voxels-live-native-240x80-2026-11-21.json)

The initial direct launches stopped at the audio readiness deadline before
producing timing samples. Launching the paired benchmark through a hidden
Windows console initialized the native mixer.
[Initial startup](gpu-fallback-voxels-live-240x80-2026-11-21.json) ·
[Direct retry](gpu-fallback-voxels-live-retry-240x80-2026-11-21.json)

## Repeated camera views

The second candidate reused the last camera's exact, refined static geometry
results. CPU fallbacks, doors, lighting and scenery continued per frame. The
first 20-frame benchmark held 27 cameras fixed and retained seven standard
turning and walking workloads. It passed 30 of 34 roles. Bridge, castle
exterior, wall walk and ridge roof exceeded the 15% p95 limit.
[First cache run](gpu-repeated-views-live-240x80-2026-11-21.json)

The revision stored the hit buffer only after two consecutive identical
views. Continuously moving cameras held no previous ray buffer. Nine focused
tests passed on hardware GPU, including opened doors in a cached view and
cache invalidation after static geometry edits. The 60-frame retry covered
the four previous failures plus indoor, outdoor and movement controls.
It passed 11 of 12 roles. The indoors mean fell 7.10% and p95 rose 19.86%,
exceeding the unchanged gate. The candidate was withdrawn.
[Revised cache run](gpu-repeated-views-retry-live-240x80-2026-11-21.json)

| Retry role | Camera motion | Control mean / p95 ms | Candidate mean / p95 ms |
| --- | --- | ---: | ---: |
| Indoors | Fixed | 39.39 / 44.89 | 36.60 / 53.81 |
| Lodge | Fixed | 74.95 / 94.57 | 62.45 / 75.71 |
| Wall walk | Fixed | 42.68 / 61.89 | 39.18 / 46.80 |
| Ridge roof | Fixed | 42.27 / 62.16 | 36.04 / 45.10 |
| Ridge approach | Turning | 80.81 / 100.71 | 81.24 / 112.20 |
| Terrace walk | Walking | 92.60 / 118.67 | 91.75 / 117.77 |

The full reports contain the camera assignments, source hashes, raw samples,
and unchanged regression gates. The existing renderer is retained, and the
30+ FPS fullscreen milestone remains open.

# Fullscreen terminal output and Thornwatch frame pacing

Reviewed 2026-11-21 after the user reported around 20 FPS on their fullscreen
setup. The earlier Linux PTY run established loop throughput with a reader
draining the stream. The Windows test remains open. The archived native
Windows 160×50 test averaged 50.01 ms with 73.37 ms p95 per interval, and
terminal drawing averaged 11.99 ms with 22.36 ms p95. That run predates adaptive
scene detail. [Archived Windows timing](moon-glints-native-160x50-2026-11-21.json)

Live presentation retains a copy of the displayed rows. It serializes changed
spans with independent cursor and foreground controls, redraws when the
viewport changes, and reuses ANSI for identical rows within a draw. The
full-frame serializer remains available for snapshots and headless checks.

[Paired output replay](optimization-terminal-output-2026-11-21.json) uses
identical adaptive color frames at 160×50, 240×80 and 360×140, with indoor and
lodge views both stationary and turning. All 432 replayed screens matched
exact glyphs and foreground colors after each update. At 240×80 the change
cut output characters by 14.3% indoors and 9.1% in the lodge while turning,
and by 96.6% and 98.4% with stationary cameras. Timing excludes the terminal
presenter. All 12 mean and p95 assembly comparisons stayed within 15%.

## Graphical terminal

The Xfce comparisons ran the normal live game loop in fullscreen VTE on Linux
with Python 3.12.14, CPU rendering, color, muted audio, a 40 FPS cap and 180
frames per process. Each resolution uses control, candidate, candidate,
control order and the same Thornwatch lodge demo. This exercises real terminal
parsing and writes on the Linux desktop. [Raw fullscreen runs and harness](optimization-fullscreen-xfce-2026-11-21.json)

| Output update only | Control loop mean / p95 ms | Updated loop mean / p95 ms | Control draw mean / p95 ms | Updated draw mean / p95 ms |
| --- | ---: | ---: | ---: | ---: |
| 224×82 | 25.83 / 29.34 | 25.78 / 29.28 | 2.23 / 2.70 | 1.67 / 2.31 |
| 336×124 | 26.56 / 36.85 | 26.33 / 33.82 | 5.39 / 9.27 | 3.50 / 7.56 |

At 336×124, mean output dropped from 71,758 to 60,711 bytes. Native write time
varied and its pooled p95 increased from 3.44 to 4.28 ms. Both variants reached
the 40 FPS cap in much of the route. The same wide run exposed a repeatable
55–62 ms interval near `(296.03, 130.09, Z7)`, with approximately 46–48 ms in
scene rendering on the changed-output variant despite a coarse sample grid.

## Thornwatch spike and adaptive color packing

At the crossing, the old renderer generated grass for freshly admitted chunks
before spending the blade budget. Generation now runs in draw order and stops
with the existing blade budget. Chunk bounds reject patches outside the draw
cone, and each blade root resolves height and material through one world query.
Adaptive styling also packs the foreground of each sampled row once and
applies the native HUD and world overlays to its expanded copies.

[Matched replay](optimization-thornwatch-replay-2026-11-21.json) feeds both
versions the same 180 poses and sample budgets from the wide fullscreen trace.
All glyphs, materials, foreground levels, effect buffers and ANSI rows match.
Render time fell from 13.35 / 25.18 ms to 9.29 / 16.35 ms mean / p95. At
`(296.00, 130.08, Z7)` the scene fell from 43.53 ms to 25.89 ms, including
grass generation falling from 35.47 to 17.61 ms. Replay timings end before
terminal output.

The final matched 336×124 fullscreen run includes all three changes. The
adaptive controller used an average of 161 scene samples versus 113 in its
control. The X296 crossing still costs 39.5–44.8 ms per interval, down from
55.2–59.5 ms in the paired control. Of the six final intervals above 33.33 ms,
two came from startup, two from this crossing, and two from a later turn.

| 336×124 fullscreen lodge | Control mean / p95 | Updated mean / p95 |
| --- | ---: | ---: |
| Frame interval ms | 26.45 / 35.44 | 25.50 / 25.54 |
| Render ms | 15.31 / 29.47 | 12.31 / 20.70 |
| Terminal draw ms | 5.18 / 7.76 | 3.29 / 6.05 |
| Output bytes | 71,973 / 81,376 | 61,582 / 76,963 |

This corresponds to 37.81 → 39.21 FPS and 23 → 6 intervals over 33.33 ms out
of 358. The worst final interval was 55.53 ms at startup. The Windows result
and live audio remain unverified.

All 131 focused vegetation, rendering, terminal, timing and game-loop tests
passed. A 72-frame PTY smoke at 336×124 verified the new diagnostic's interval
and stage samples, viewport, backend, byte counts, and terminal restoration.

## Live timing on the reported setup

Launch in fullscreen, play through the slowdown and use Esc to exit. The
report separates console output, render and GPU fallback, audio/input,
simulation, and time spent waiting for the frame cap. Use an unused filename.

```bat
run.bat --frame-timing fullscreen-timing.json
```

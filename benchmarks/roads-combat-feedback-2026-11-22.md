# Cobblestone roads and combat feedback validation

## Live-audio timing

The matched control is `4907509` with its original native solid library. The
candidate freezes both gameplay changes and the rebuilt library. Each
comparison uses the same RTX 3080 Laptop GPU via Vulkan, Python 3.14.4 and live
Windows waveOut audio. An ABBA sequence alternates isolated processes with one
world and one audio worker in each. Every case warms up five frames per process
before taking 40 samples. The mean and nearest-rank p95 pool 80 samples per
variant and case. Raw reports retain renderer and device metadata, source and
binary fingerprints, sample arrays, and audio health.

The Ashgate camera is at (128.5, 63.5, 1), facing north with pitch −0.28. It
shows 1,368 road samples at 120×40 and 6,067 at 240×80 in both builds. The
Watchstone camera is at (41.5, 246.5, 1), facing north with pitch −0.06. It views
the living Warden and then separately renders an injured player and a defeated
Warden. The feedback case applies 2 HP damage and a final sword hit, emits the
same four existing sounds in both builds, and advances fixed-step timers
through the first third of a second of the effect. Timings include ambience,
styled frames and ANSI encoding. They exclude terminal writes and fullscreen.

### Default auto renderer

Auto selected the hardware GPU and enabled native surface shading. All six
cases passed both 15% gates. The four launches recorded zero audio underruns
or recoveries. At 240×80 all three cases exceeded 33.33 ms at p95, so the 30 FPS
fullscreen target remains open. [Auto renderer raw data](roads-combat-auto-live-2026-11-22.json)

| View | Control mean / p95 ms | Candidate mean / p95 ms | Mean / p95 change |
| --- | ---: | ---: | ---: |
| 120×40 Ashgate cobbles | 21.96 / 24.59 | 22.89 / 27.62 | +4.21% / +12.29% |
| 120×40 living Warden | 27.16 / 30.68 | 27.79 / 32.68 | +2.31% / +6.52% |
| 120×40 active feedback | 23.04 / 30.35 | 23.05 / 26.62 | +0.05% / −12.29% |
| 240×80 Ashgate cobbles | 69.39 / 90.80 | 66.59 / 79.08 | −4.04% / −12.91% |
| 240×80 living Warden | 80.73 / 91.77 | 79.39 / 90.35 | −1.66% / −1.55% |
| 240×80 active feedback | 69.58 / 80.25 | 67.99 / 82.33 | −2.29% / +2.59% |

### Explicit GPU

This mode uses GPU geometry and the Python surface shading path. All six
cases passed both 15% gates. The four launches recorded zero audio underruns
or recoveries. [Explicit GPU raw data](roads-combat-gpu-live-2026-11-22.json)

| View | Control mean / p95 ms | Candidate mean / p95 ms | Mean / p95 change |
| --- | ---: | ---: | ---: |
| 120×40 Ashgate cobbles | 25.23 / 30.88 | 27.38 / 30.48 | +8.51% / −1.30% |
| 120×40 living Warden | 31.60 / 36.85 | 33.48 / 39.56 | +5.94% / +7.35% |
| 120×40 active feedback | 28.59 / 31.98 | 28.60 / 32.73 | +0.03% / +2.37% |
| 240×80 Ashgate cobbles | 85.79 / 94.08 | 93.24 / 104.80 | +8.68% / +11.40% |
| 240×80 living Warden | 96.81 / 110.03 | 97.62 / 114.53 | +0.84% / +4.09% |
| 240×80 active feedback | 85.45 / 97.61 | 81.49 / 94.09 | −4.64% / −3.60% |

## Visual parity

CPU, native and hardware GPU produced matching styled output on the Ashgate
approach at (128.5, 61.5, 1), pitch −0.31, and the Watchstone Warden collapse
at (41.5, 246.45, 1), pitch −0.08. Both cameras faced north. At 60×20, 120×40
and 240×80 the Ashgate scene had 302, 1,503 and 6,611 road samples. The combat
frames showed both `[-2 HP]` and stone particles 0.12 seconds into the effect.

## Native Windows smoke

Two hidden 120×40 native consoles ran the full game loop with the default
auto renderer, hardware GPU and live waveOut audio. An authored Warden's
melee hit produced `[-2 HP]` on the native screen. An injected Enter then
landed a sword hit, produced up to nine visible stone shards, and let the
defeat effect expire. The run emitted one `player_hurt` and one `enemy_down`.
The outdoor run displayed 1,365 cobblestone cells and an injected W triggered
`step_stone` on the road.

All 20 checks passed on the final runs. The audio workers reported 42 and 19
blocks with zero underruns or recoveries. Both consoles restored the cursor,
input/output modes and screen when gameplay closed. The retained first
attempts captured the reference screen before the loading splash, which
invalidated their screen-hash comparisons. The rerun captured immediately
before entering the gameplay alternate screen.
[Native console runs and ASCII frames](roads-combat-native-2026-11-22.json)

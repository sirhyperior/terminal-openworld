# Backlog validation, 2026-11-23

## Live developer console

The 160×50 Win32 console drew 84 consecutive live split frames at 106×45
scene cells and 24 full-width frames after Esc. Injected native keyboard
records opened the editor, teleported above Ashgate paving, submitted a bug
report while the player fell, changed the FPS cap from 40 to 24, and started
the demo. The FPS readout responded, the temporary backlog received the
coordinates at submission, and the console restored its modes, cursor and
screen. The native audio worker played 99 blocks with zero underruns or
recoveries. Captured events include the report cue, a cobblestone landing
and seven cobblestone steps.
[Native replay](backlog-live-dev-replay-2026-11-23.json)

The first probe injected punctuation using virtual codes for navigation
keys, captured console restoration outside the terminal lifecycle, and
included absent interval samples in its summary. The replay corrected the
probe and kept production behavior under test.
[First probe](backlog-live-dev-2026-11-23.json)

## Matched gameplay timing

The runs used Python 3.14.4, RTX 3080 Laptop GPU via Vulkan, auto renderer,
styled color at 120×40 and a shared live waveOut worker with the game sound
bank prepared before startup. Each role has five warmups and 40 timed frames
per variant in ABBA order. These timings include ANSI row encoding.
The frozen control is `0dcb8e6` with the prior optional DLL. Both sides of
these gameplay comparisons use that DLL.

| Role | Control mean / p95 ms | Candidate mean / p95 ms |
| --- | ---: | ---: |
| Iven’s first conversation | 8.21 / 9.21 | 7.98 / 8.98 |
| Ashgate cobblestone walk | 14.97 / 17.65 | 14.74 / 18.26 |
| Watchstone Warden hit and defeat | 14.73 / 18.03 | 15.33 / 17.98 |
| Ashgate interior hit | 10.14 / 11.82 | 10.25 / 11.97 |

All four roles pass the existing 15% mean and p95 gates. The first Watchstone
comparison exceeded the p95 gate by recording 22.06 ms against 17.48 ms.
Using four-sided armor blocks during the short depth-tested fall brought the
replay within both gates. Every completed comparison had zero audio underruns
or recoveries.
[Dialogue and walking](backlog-dialogue-cobblestone-live-2026-11-23.json) ·
[Combat replay](backlog-combat-live-replay-2026-11-23.json) ·
[First combat run](backlog-combat-live-2026-11-23.json)

## Road grading

The shortcut past (340.8, 306.5, Z10.7) has a longer approach ramp, and the
Reliquary Bridge joins a level landing blended into the bank. The shortcut
passes 12 combinations of direction, lane and walk or sprint. The three
river bridges pass both directions. Replaying the original terrain failed
all 12 shortcut cases and both directions on the Reliquary Bridge.
The six-destination route and 1,040 stair contact checks pass.

## Native firelight

The 240×80 live-audio comparison used identical world geometry and Python
source with the previous and rebuilt DLLs. It used the same hardware, output
mode, warmups and samples as the 120×40 comparisons. Resolved static hits
that cannot be lit stay in the compiled shader. Potential local light,
water and ambiguous hits retain the shared Python shading and its
screen-order visibility checks.

| Role | Control mean / p95 ms | Candidate mean / p95 ms |
| --- | ---: | ---: |
| Indoors | 19.93 / 22.21 | 19.60 / 22.64 |
| Fireballs | 65.12 / 100.18 | 52.08 / 80.63 |
| Ashgate paving | 25.98 / 29.31 | 26.79 / 30.88 |

All three roles pass both regression gates. Fireballs improve by 20.02%
mean and 19.52% p95. The live worker produced 218 blocks with zero underruns
or recoveries. All 20 paired frames match glyphs, style, material and effect
buffers, opaque depth, color and grayscale ANSI rows, and shadow-ray order.
The fireball role still exceeds 33.33 ms before terminal writes.
[240×80 timing](backlog-firelight-auto-240x80-2026-11-23.json) ·
[120×40 and 240×80 parity](backlog-firelight-parity-2026-11-23.json)

## Integrated suite

Native Win32 input and output with `MONOLITH_GPU_TESTS=1` and the rebuilt DLL
ran all 672 tests. Two tests skipped. The 14 failure records cover four
test methods, including 11 subtests of the paving shadow palette. Running
those four methods with source from `0dcb8e6` reproduced the exact failure
labels. The new developer console, dialogue, combat, route, Foley and native
firelight checks passed.
[Suite log](backlog-validation-native-2026-11-23.txt) ·
[Run manifest](backlog-validation-native-2026-11-23.json) ·
[Control failure replay](backlog-validation-control-failures-2026-11-23.txt)

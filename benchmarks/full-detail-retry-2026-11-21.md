# Full-resolution rendering retry

The GitHub backlog at `11460a2` records that adaptive sampling made the game
coarser and less visible on the user's display. Commit `780e5c8` restores the
full terminal-resolution scene and removes automatic scene downsampling. It
retains the earlier exact terminal-output and solid-query optimizations. The
default viewport traces one ray per scene cell at all frame rates.

[Original-graphics parity](full-detail-retry-parity-2026-11-21.json) compares
independent worlds against pre-cloud `df643ea`, with compiled solids and
terrain enabled on the current side. All 102 sampled frames across 34 roles
match glyphs, levels, material and effect buffers, ANSI output and pre-scenery
depths exactly. The comparisons cover 160×50, 240×80 and pitched 80×60 views.

## Compiled continuous terrain

The optional library now traverses the heightfield in double precision using
the same chunk envelopes and triangle order as Python. The wrapper reuses
packed bounds until a terrain edit and shares the height and material data.
An older library still accelerates solids and uses Python for ground rays.

The [160×50 full-detail benchmark](full-detail-native-terrain-160x50-2026-11-21.json)
compares `780e5c8` with compiled solids and Python terrain against the same
compiled solids plus compiled terrain. The same geometry and camera roles are
measured in ABBA order over twenty styled-color frames per variant after five
warmups. Timing includes ANSI serialization. Host is Linux x86-64 on an AMD
EPYC 9V74 with Python 3.12.14 and audio off. All 34 mean and p95 limits pass under the existing 15%
regression gates. Three of 34 roles met the absolute 33.33 ms p95 budget with
either version.

| 160×50 role | Solids only mean / p95 ms | Solids and terrain mean / p95 ms |
| --- | ---: | ---: |
| Indoors | 49.65 / 51.23 | 49.77 / 52.01 |
| Lodge | 112.34 / 118.13 | 95.66 / 105.96 |
| Ridge upper floor | 98.93 / 103.93 | 84.72 / 88.23 |
| Highlands | 88.14 / 90.62 | 69.87 / 71.29 |
| Ravine | 95.16 / 111.78 | 76.25 / 86.22 |
| Terrace walk | 135.08 / 143.22 | 108.30 / 113.92 |
| Stair walk | 110.71 / 116.57 | 90.49 / 91.03 |

The [240×80 benchmark](full-detail-native-terrain-240x80-2026-11-21.json) used
the same method for eight roles spanning indoor, water and terrain views.
All eight mean/p95 regression gates passed. Mean/p95 fell from 206.61/237.52
to 157.90/165.02 ms in highlands, 265.21/279.09 to 217.62/225.54 ms in the
lodge, and 214.59/221.56 to 169.78/174.26 ms in the ravine. None met the
absolute 33.33 ms p95 target at this size.

## GPU host-side finishing

The host consumes the compact GPU records directly and precomputes the camera
terms each row and column share. Exact candidate, tie and fallback rules stay
covered by the previous diagnostic refinement path. In the
[host replay](full-detail-compact-gpu-host-2026-11-21.json), every hit and
fallback matched across forty timed draws per variant. At a 160×45 ray grid
the stage fell from 12.07/12.47 to 8.13/8.52 ms mean/p95. At 240×75 it fell
from 29.22/33.11 to 19.55/23.54 ms. The synthetic readback isolates Python
decoding and refinement. Hardware GPU and Windows fullscreen timings remain
open.

The focused Linux suite ran 144 tests, with 140 passing and four hardware
GPU tests skipped. A live 240×80 PTY smoke drew all eight requested frames
with a 240×75 scene grid (18,000 rays per frame), then restored the terminal.

## Resume

Rebuild the optional compiled library using the instructions for the host.
The ordinary launcher draws full detail. Capture the same actual fullscreen
configuration on Windows, with an unused timing path.
[Native build instructions](../README.md#renderer-backends)

```bat
run.bat --frame-timing fullscreen-full-detail-timing.json
```

The frozen compiled-solids control can be reproduced by extracting `ascii3d/`
from `780e5c8`, then building its library using the same compiler and flags.

# Full-grid rendering and fullscreen throughput

The frozen control contains the pre-optimization worktree and native DLL,
including the revised paving and split developer console. The candidate keeps
the same field of view, glyph size and scene-cell count. The optional DLL
shades resolved GPU hits directly from the float64 hit buffer. Ambiguous hits
retain exact tracing. Water, firelight and overlay drawing retain the shared
rendering paths.
[Frozen control](fullscreen-throughput-control-2026-11-23.zip)

## Matched 240×80 workloads

Python 3.14.4, RTX 3080 Laptop GPU, Vulkan, color and live waveOut audio.
The paired benchmark verifies identical geometry, warms each role up for five
frames and measures 20 frames per variant in per-frame ABBA order. Both
variants share the native audio worker with a prebuilt game sound bank.
These frame times include simulation, audio updates and ANSI encoding.
Terminal writes and cap waits are measured separately.
[Raw timings and source hashes](fullscreen-throughput-auto-240x80-2026-11-23.json)

| Role | Control mean / p95 ms | Candidate mean / p95 ms |
| --- | ---: | ---: |
| Ashgate paving | 67.52 / 83.54 | 27.04 / 30.42 |
| Indoors | 49.35 / 52.72 | 21.90 / 24.73 |
| Thornwatch lodge | 76.11 / 98.81 | 34.04 / 41.23 |
| Thornwatch terrace walk | 111.49 / 136.17 | 60.07 / 73.11 |
| River | 75.02 / 83.81 | 70.14 / 79.76 |
| Fireballs | 103.28 / 114.35 | 105.40 / 118.91 |

All 35 roles pass the existing 15% mean and p95 regression gates.
Twenty-two average at most 33.33 ms and 13 meet 33.33 ms p95.
Audio had zero underruns or recoveries. The paving role uses (128.5, 63.5, Z1),
pitch −0.28 and the standard paired yaw sweep. The historical explicit GPU
paving gate used a fixed yaw and a separate control. Its matched timing
remains open.

All 105 matched frame pairs at 240×80 have identical glyphs, foreground,
material and effect buffers, ANSI rows and opaque depths before scenery.
The focused Windows suite passed all 51 tests with hardware GPU tests enabled.
[Exact frame comparison](fullscreen-throughput-parity-240x80-2026-11-23.json)

## Visible Windows fullscreen

Each run used a dedicated classic conhost at 213×60 with 8×16 Consolas,
covering the 1707×960 display. Runs retained 60 frames and 59 intervals, used
the 40 FPS cap, and played live audio with zero underruns or recoveries.
All console sessions restored their modes, cursor and buffer. These are
elapsed-time demos, so each variant traverses a different distance in 60
frames. Fullscreen coverage was verified at each end. Foreground focus was
observed at the end of the Ashgate control, and the other end snapshots
showed another window held focus.

| Demo | Control FPS / p95 interval ms | Candidate FPS / p95 interval ms | Candidate render mean / p95 ms | Candidate write and flush mean / p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Ashgate | 16.77 / 117.62 | 19.47 / 80.53 | 12.86 / 17.30 | 34.00 / 51.92 |
| Thornwatch | 10.40 / 158.28 | 14.27 / 127.80 | 32.42 / 49.77 | 30.70 / 63.31 |

Ashgate timings used the packed shader prior to the fused terrain/solid query.
The Thornwatch run included both. A separate Ashgate probe sent each unchanged
ANSI payload in one `WriteConsoleW` call. Its 36.18/54.86 ms write mean/p95
showed no gain. The production terminal output path stays the same.

- Ashgate [control](fullscreen-throughput-control-ashgate-2026-11-23.json) and [candidate](fullscreen-throughput-packed-ashgate-2026-11-23.json).
- Thornwatch [control](fullscreen-throughput-control-thornwatch-2026-11-23.json) and [candidate](fullscreen-throughput-final-thornwatch-2026-11-23.json).
- [Direct write experiment](fullscreen-throughput-direct-ashgate-2026-11-23.json).

## Resume

Rebuild the optional DLL using the compiler command in the README. Compare
classic conhost with Windows Terminal on the same grid, replay and audio
mode. Use unused output filenames for each host and scene.

```powershell
.\run.bat --keyboard-look --demo --frames 60 --frame-timing benchmarks\fullscreen-ashgate-replay.json
.\run.bat --keyboard-look --demo --region thornwatch --frames 60 --frame-timing benchmarks\fullscreen-thornwatch-replay.json
```

The 240×80 engine comparison can be rerun with
`tools/benchmark_same_geometry.py`, the extracted control, auto on both sides,
`--width 240 --height 80 --frames 20 --audio --presentation styled` and color
on both sides. The dedicated paving camera is an extra workload beyond the
tool's usual 34 roles.

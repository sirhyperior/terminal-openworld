# Developer console validation

## Native Windows smoke

A hidden 120×40 Win32 console ran the game with the RTX 3080 Laptop GPU,
Python 3.14.4 and live waveOut audio. Injected native keyboard records opened
the console, edited and recalled a command, displayed live settings, and
teleported from Ashgate to Thornwatch. Play ran at 60×20 in CPU mono and
resumed at 120×40 in GPU gray. The checks covered movement, mute, the worker's
shared volume control and the developer audio events. All 20 checks passed
with 152 audio blocks, zero underruns and zero recoveries. The audio worker
stopped and the terminal restored its modes, cursor and main screen.

The 15 console frames outside renderer switches took 0.90 ms mean and
1.32 ms p95. CPU and GPU renderer preparation took 2.33 s and 3.01 s,
respectively, on the switch frames. The smoke used injected keyboard input.
Physical mouse, speaker and fullscreen review remain open.
[Smoke runs and transcripts](dev-console-native-smoke-2026-11-22.json)

The final GPU projection fix passed a separate native smoke. From the same
120×40 view, the commands `set cell-aspect 0.8` and `set cell-aspect 0.5`
changed and restored the native refinement offsets at the same 120×35
scene size. The GPU stayed active, the console restored cleanly, and live
audio produced 17 blocks with zero underruns and recoveries.
[Final live cell-aspect smoke](dev-console-native-cell-aspect-2026-11-22.json)

## Matched live-audio timing

The ABBA comparison used the Ashgate spawn, 120×40, color mode, Vulkan on the
same GPU and a 240 FPS cap. The control was `c5baa3d`. The developer build
ran with `--dev` and the console closed, before the live cell-aspect change
was fixed to refresh the native GPU projection. No cell-aspect changes
occurred during the comparison. Each run retained 120 timed frames.
The comparison pools 220 samples per version after the first 10 frames of
each run. All four runs had zero audio underruns and recoveries.

| Frame work | Control | Developer build | Change |
| --- | ---: | ---: | ---: |
| Mean | 20.64 ms | 20.99 ms | +1.66% |
| p95 | 24.43 ms | 24.86 ms | +1.77% |

Both stayed within the existing 15% gate. This comparison covers one native
viewport and camera pose. The first complete timing attempt is preserved.
The probe's import order caused the archived playback workers to time out.
The rerun fixed the probe and repeated all four trials.
[Raw frame samples and audio status](dev-console-native-timing-2026-11-22.json)

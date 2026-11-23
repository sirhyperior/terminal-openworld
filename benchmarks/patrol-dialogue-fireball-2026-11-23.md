# Patrol, dialogue audio, and fireball validation

## Fireball shot onset

At 240×80, the auto renderer now keeps compiled base shading for resolved
receivers after the existing 256-ray firelight budget fills. Hits that can
reuse a visible ray still go through the shared light and normal checks.
Water and ambiguous geometry keep their ordered exact fallback. The Python
voxel visibility query now steps by scalar coordinates with the same X, Y, Z
tie order.

The frozen control is `a37e647` with its prior native DLL. Both builds used
Python 3.14.4, an RTX 3080 Laptop GPU via Vulkan, and a live waveOut worker.
Each pose used eight ABBA episodes per build with 12 measured frames per
episode, starting at the actual attack. Five warmup frames preceded the
episodes. Timings include simulation, ambience, color rendering and ANSI
encoding. Physical terminal writes are outside these timings.

| 240×80 role | Phase | Control mean / p95 ms | Candidate mean / p95 ms |
| --- | --- | ---: | ---: |
| Ashgate training yard | Cast | 66.16 / 71.49 | 43.63 / 47.71 |
| Ashgate training yard | First three frames | 75.97 / 93.81 | 51.84 / 68.86 |
| Ashgate training yard | Whole episode | 77.73 / 91.86 | 45.45 / 65.58 |
| Ashgate gatehouse | Cast | 75.08 / 82.82 | 49.24 / 56.67 |
| Ashgate gatehouse | First three frames | 87.78 / 106.19 | 57.96 / 77.60 |
| Ashgate gatehouse | Whole episode | 85.60 / 103.59 | 48.16 / 70.79 |

The cast p95 fell 33.26% in the yard and 31.57% in the gatehouse. Both roles
pass the 15% regression gates at every measured phase. The live worker
recorded 571 blocks through cleanup with no underruns or recoveries. All
24 paired shot frames match glyphs, color ANSI, style, material and effect
buffers, opaque depth and ordered surface shadow results. A seeded replay
also matched all 4,096 shared visibility distances, including 2,030 blocked
rays across landmark poses, door angles, axis ties and grid boundaries.
The shot still exceeds the 33.33 ms budget in these views.
[Final timing](fireball-shot-final-live-2026-11-23.json) ·
[Frame and shadow parity](fireball-shot-parity-2026-11-23.json) ·
[Budget-only timing](fireball-shot-budget-live-2026-11-23.json)

## NPC patrols and dialogue audio

At 120×40, Iven's authored test route exercised walking, a timed stop,
surface footsteps, a conversation, pause and resumed walking. Native key
records passed all nine checks in 160 frames. The mixer received 29 letter
cues, three reveal rustles and two footsteps. The worker wrote 94 blocks
with zero underruns or recoveries. Console modes, cursor and screen restored.
[Native console replay](npc-patrol-dialogue-native-2026-11-23.json)

The paired comparison used five warmups and 40 ABBA samples per build and
role, color ANSI output and shared live waveOut. The dialogue role uses
the same interaction inputs. The patrol role enables the candidate's authored
test route. Both roles pass the 15% mean and p95 gates with clean audio.
[Matched gameplay timings](npc-patrol-dialogue-live-2026-11-23.json)

| 120×40 role | Control mean / p95 ms | Candidate mean / p95 ms |
| --- | ---: | ---: |
| Iven dialogue | 8.81 / 10.03 | 8.85 / 10.17 |
| Resident view with opt-in patrol | 9.03 / 10.11 | 8.90 / 10.03 |

Across 24 variants of ten ordinary cues, the spread in loudest overlapping
40 ms RMS narrowed from 8.53 dB to 1.00 dB. Sword pickup moved from −11.70
to −19 dBFS in that measurement. The three 25 ms letter clips measure
−33 dBFS RMS. These measurements describe synthesized PCM before playback.
Speaker and headphone listening review remains open.

## Integrated suite

The hidden Win32 console ran 683 tests with GPU checks enabled and two skips.
All 14 failure records match the prior native suite. The initial run also
showed two frame-timing mock errors at the new NPC update hook. The corrected
mock returns an empty event sequence. All 39 frame-timing, developer console
and game-loop tests passed on replay.
[Native suite log](backlog-patrol-audio-fireball-native-2026-11-23.txt) ·
[Run manifest](backlog-patrol-audio-fireball-native-2026-11-23.json)

## Door level follow-up

After play feedback, the loudest 40 ms RMS of each opening and closing
variant rose from −20 to −17 dBFS. Each blocked-door variant rose from
−23 to −20 dBFS. The highest PCM peak was 11,765 of 32,767. All 36 focused
sound and door tests passed. The Windows `--audio-test` played 396 buffers
with zero underruns or recoveries and a maximum refill interval of 83.4 ms.

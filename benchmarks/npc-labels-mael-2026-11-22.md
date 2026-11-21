# Mael and actor label performance

The control is the three-resident build with idle motion before Mael and the
shared actor labels. The comparison uses the same RTX 3080 Laptop GPU via
Vulkan, Python 3.14.4, the auto renderer, styled color, live Windows audio and
matching fixed camera poses. Four hidden native console launches follow ABBA
order, with one world and one sound worker per process. Each case pools 60
timed samples per variant, with five warmups before each block. Timings include
ambience updates, scene and HUD rendering, and ANSI encoding. They exclude
terminal writes and physical fullscreen.

The default Ashgate camera showed no Mael label. The second camera uses the
same position and aim in both variants, about 2.68 units from Mael's authored
position. The candidate drew `<Mael Veyr>` above him on both viewports. All
four completed launches matched map geometry and recorded zero audio
underruns or recoveries. The third launch initially timed out during audio
startup before it sampled frames. The resumed comparison retained both
completed blocks and reran the missing blocks with the same source hashes.
[Initial run](npc-labels-mael-live-2026-11-22.json) ·
[Completed comparison](npc-labels-mael-live-retry-2026-11-22.json)

| View | Control mean / p95 ms | Candidate mean / p95 ms | Mean / p95 change | 15% gate |
| --- | ---: | ---: | ---: | --- |
| 120×40 spawn | 13.41 / 15.52 | 16.83 / 22.33 | +25.49% / +43.93% | Fail |
| 120×40 aimed | 12.53 / 14.84 | 14.91 / 17.28 | +19.05% / +16.40% | Fail |
| 240×80 spawn | 43.62 / 57.73 | 44.15 / 56.41 | +1.20% / −2.29% | Pass |
| 240×80 aimed | 45.87 / 59.43 | 44.40 / 54.40 | −3.21% / −8.46% | Pass |

Both 120×40 candidate cases took less than 33.33 ms at p95. Both 240×80
cases passed the relative gates and remained above 33.33 ms at p95. The
comparison measures the combined NPC and label change.

# NPC idle animation performance

The control is the working-tree NPC prototype immediately before the idle
animation. Both variants render Iven from identical fixed poses at 2.10 and
4.94 units. An NPC-free preflight render verified that his body is visible in
every case. The same authored map, Python 3.14.4, RTX 3080 Laptop GPU via Vulkan,
auto renderer, styled color, live Windows audio and 5×10 terminal cells were
used throughout. Timings include audio control and ambience updates, rendering
and ANSI row encoding. Terminal writes and physical fullscreen were outside
the measurement. The unchanged gate allows up to a 15% increase in mean and
p95. Each result uses 60 measured samples per variant and case.

## Initial ABBA

Both 240×80 cases passed. The 120×40 means passed and both p95 comparisons
failed. The raw report retains the samples, source fingerprints, visible cell
counts and the common animation timestamps.
[Initial matched run](npc-idle-animation-live-2026-11-21.json)

| View | Control mean / p95 ms | Animated mean / p95 ms | Gate |
| --- | ---: | ---: | --- |
| 120×40 close | 15.05 / 18.59 | 16.85 / 34.28 | Fail |
| 120×40 mid-range | 14.57 / 16.91 | 16.03 / 31.06 | Fail |
| 240×80 close | 47.66 / 66.96 | 47.06 / 59.95 | Pass |
| 240×80 mid-range | 44.30 / 64.58 | 44.62 / 62.23 | Pass |

## Garbage-collection diagnostics

An instrumented control/control run at 120×40 used two worlds with identical
source and reproduced a +107.70% mid-range p95 difference. The four slow
samples in the second column lasted 39.38–46.34 ms, each containing a
23.14–28.19 ms Python generation-1 GC pause. The control/control close
case passed.
[Control/control run](npc-idle-animation-control-control-2026-11-21.json)

An instrumented control/animation run alternated ABBA and BAAB blocks. Close
passed with mean down 2.43% and p95 down 4.99%. The mid-range case failed on
p95 again. Each of its four slow 35.45–44.02 ms candidate frames contained a
21.64–25.98 ms generation-1 collection. These comparisons retain all pauses in
the published timings. The control/control run shows that the two-world
interleave can assign its collection cost unevenly even with identical code.
[Balanced-order run](npc-idle-animation-balanced-2026-11-21.json)

## Isolated 120×40 replay

The final ABBA comparison alternated process launches so each process held
only one game world and one active sound worker. Each launch warmed up five
frames before measuring 30 timestamps per case. Pooling both launches per
variant gave the same 60 samples and measured timestamps as the initial run.
Both cases passed with garbage collection still enabled. All completed runs
had zero audio underruns and recoveries.
[Single-world run](npc-idle-animation-single-world-2026-11-22.json)

| View | Control mean / p95 ms | Animated mean / p95 ms | Mean / p95 change |
| --- | ---: | ---: | ---: |
| 120×40 close | 14.60 / 20.06 | 13.71 / 17.73 | −6.12% / −11.65% |
| 120×40 mid-range | 14.88 / 18.23 | 12.99 / 16.69 | −12.70% / −8.44% |

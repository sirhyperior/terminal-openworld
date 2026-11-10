# Full-terminal viewport — 2026-11-10

## Result and scope

Live play now uses every native terminal column and row by default. The former
4,800-cell budget, 180-column/64-row ceilings and unused last row are removed.
The terminal's font and physical cell aspect are unchanged. `--max-cells 4800`
offers an explicit centered budget; budgets must be at least 1,200 cells.
Budgeting preserves a 60x20 playable viewport when the screen allows it, even
for unusually wide or tall screens. Native output dimensions take precedence
over stale environment overrides. Physical resize invalidates the output clear
even when a budget produces the same rounded size and origin.

For a 240x80 terminal, the previous default produced 116x41 cells (4,756).
The new default produces 240x80 (19,200); an explicit 4,800 budget produces
120x40. These are cell counts, not a claim of equal frame cost or FPS.
No ray range, traversal limit, scenery density or acceptance threshold changed.
Renderer, simulation, collision and audio implementation text is unchanged.

Three agents owned separate tasks: terminal sizing/output and focused tests;
CLI, README and loop tests; and independent large-viewport renderer validation.
The lead reviewed integration, native output, measurements and status updates.
No architecture change or dependency was introduced.

## Functional validation

- Full piped suite: **331 discovered, 320 passed, 11 skipped**, 117.131 seconds.
  The skips are ten native-console input cases and one opt-in desktop cursor case.
- The ten native-console input cases subsequently **all passed**, 0.038 seconds,
  with desktop access. This includes console-mode restoration, simultaneous
  movement/sprint/jump, pause release, Enter attack and unbound Q.
- The remaining opt-in desktop cursor case **passed**, 0.032 seconds, including
  three capture/release epochs. Thus all **331 test cases passed** across the
  full suite and separate native reruns; no skipped case remains unexecuted.
- Fifteen new tests cover default/explicit viewport dispatch, budget rejection,
  resize freeze/resume, native-size precedence, final-cell output, clears on
  rounded-size resizes, exception cleanup, exact indoor/outdoor DDA equivalence,
  projection/map cache reuse, keyboard/mouse menus and unchanged foliage budgets.
  Large/tall coverage includes 240x80, 320x100 and 80x160.
- [Native console probe](viewport-native-console.json): actual output grid
  **80x24**, origin (1,1), first/final characters read back as A/Z, cursor at
  (79,23), and output modes restored. This verifies the final cell without
  scrolling in this ConPTY session. One synthetic write took 0.122 ms; it is not
  a mean/p95 gameplay or terminal-throughput benchmark.
- `python -B main.py --snapshot` passed. The native
  `python -B main.py --outside --demo --frames 100` run exited 0 at 80x24 with
  SND ON, showing meadow/entrance and indoor frames, then restoring the alternate
  screen/cursor/console lifecycle. Large-viewport exact-image tests cover the
  larger layouts without a production renderer change.

The restricted native probe could write the frame but was denied console-cell
readback (WinError 5). Repeating it with desktop access passed. The console font
API returned a zero pixel width and height 16 under ConPTY; this is not a valid
measurement of the user's physical font/cell size. Physical resize/play review
in the user's tabbed Windows Terminal remains outstanding.

## Matched performance comparison

Frozen control: Git checkpoint `d2fa0a7`, reconstructed with `git archive` into
temporary `viewport_control_tmp/`. Reports preserve production-file SHA-256
values. Archive LF versus checkout CRLF accounts for many byte-hash differences;
normalizing line endings shows only `app.py` and `terminal.py` implementation
text differs. Neither is imported by the timed engine path.

Method: same Windows host/Python 3.14.4, 120x40, 60 measured frames per variant,
five warmups, per-frame ABBA, shared native mixer and actual listener-height
Soundscape sampling. Both mean and p95 retain the **15% limit per matched role**.
Terminal writes and frame-cap waits are excluded.

- [First report](viewport-interleaved-120x40.json): all 24 roles passed, but the
  helper retained its earlier flat-control/elevated-current audio assumption.
  It is retained as diagnostic evidence and is not used for acceptance here.
- [Corrected report](viewport-interleaved-height-120x40.json): **23/24 passed**;
  castle exterior failed p95 **+20.52%** (15.414 to 18.577 ms); its mean rose
  **5.05%** (11.408 to 11.984 ms). Across matched current scenes, means were
  8.539–19.838 ms and p95 9.189–23.693 ms. Audio: **zero underruns/recoveries**,
  72.64 ms maximum refill interval. Exit 1 and the failed samples are retained.

The helper now accepts `--before-elevated-audio` for frozen controls supporting
listener height, and records each variant's sampling mode. Earlier controls
without that capability retain their default flat-world sampling. The cause of
the failed p95 comparison is unverified. This milestone does not close earlier
expansion or castle-wide performance acceptance, replace a baseline, or claim
a universal terminal FPS.

## Resolution cost

Separate serial runs use the same host/Python, 60 measured frames, five warmups,
34 castle/highland/combat/map/walking scenes and live listener-height audio.
[80x24](viewport-80x24-live.json) matches the measured native grid;
[240x80](viewport-240x80-live.json) is a larger representative render resolution,
not a claim that the user's terminal was measured at that size. Terminal writes
and cap waits are excluded. Different resolutions are not percentage acceptance
comparisons.

| Scene | 80x24 mean ms | 80x24 p95 ms | 240x80 mean ms | 240x80 p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Gatehouse | 6.850 | 7.882 | 67.576 | 76.147 |
| Meadow | 4.634 | 5.643 | 37.347 | 39.326 |
| Bridge | 6.769 | 7.671 | 59.937 | 65.799 |
| Ridge upper floor | 6.972 | 7.590 | 73.316 | 76.650 |
| Highland map | 2.354 | 3.100 | 20.461 | 21.476 |

Across all scenes, 80x24 mean/p95 ranges are **2.354–8.926 / 3.100–9.803 ms**;
240x80 ranges are **20.461–73.316 / 21.476–76.650 ms**. Both runs had **zero
audio underruns/recoveries**; maximum refill intervals were 72.28/72.62 ms.
Larger views can fall below the 40 FPS target; use an explicit character budget
when frame cost matters. No default resolution was reduced to hide this cost.

## Reproduce

Use an unused report path and run timing checks serially. Remove temporary
source/probes after review; retain reports, including failures.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
git archive --format=zip --output=viewport-control-tmp.zip d2fa0a7 ascii3d
Expand-Archive -LiteralPath viewport-control-tmp.zip -DestinationPath viewport_control_tmp
python -B tools/benchmark_pair.py --before-source viewport_control_tmp --before-elevated-audio --frames 60 --audio --save benchmarks/viewport-followup-120x40.json
python -B tools/benchmark.py --frames 60 --width 80 --height 24 --audio --extra-scenes --terrain-scenes --save benchmarks/viewport-followup-80x24.json
python -B tools/benchmark.py --frames 60 --width 240 --height 80 --audio --extra-scenes --terrain-scenes --save benchmarks/viewport-followup-240x80.json
python -B -m unittest discover -s tests -v
python -B main.py
python -B main.py --max-cells 4800
python -B main.py --keyboard-look
```

The next smooth-terrain milestone needs a shared geometry/collision/support,
vegetation, water and Foley design approved before implementation. Smaller
stairs remain a separate requested follow-up; current voxel terraces/risers
are unchanged.

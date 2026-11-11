# Project Status

Last reviewed: **2026-11-11**. Read [AGENTS.md](AGENTS.md) for standing rules and
[user_designated_milestones.md](user_designated_milestones.md) for the user's
backlog. [README.md](README.md) covers gameplay, controls and world locations.

## Current checkpoint

- Current checkpoint: smooth hills, finer stairs and performance repairs,
  committed at the user's request on **2026-11-11**. Pre-geometry control:
  **`d20cd0d`** (full-terminal viewport). Geometry approval is granted;
  routine work within that scope needs no renewed approval.
- The 512x512 world now has shared continuous ground and 13 stair flights with
  quarter-unit risers/half-unit treads. Rendering, collision, support, targeting,
  vegetation and Foley use the shared geometry. All flights pass ascent/descent.
- Full-terminal sizing is the default; `--max-cells 4800` is optional. Preserve
  keyboard look and the 60x20 playable minimum. Dark fantasy is the standing
  theme for future content, as specified in AGENTS.md.
- **Performance acceptance remains open: 12/24 matched roles pass.** No baseline
  was replaced or threshold relaxed. Performance work awaits resume; no jobs run.

## Next work

1. Profile the failed roles with **varying yaw and live simulation**, matching
   `tools/benchmark_pair.py:frame`. Fixed-pose profiles alone missed important
   costs. Separate voxel traversal, analytic queries, AI collision and setup.
2. Investigate query ordering in terrain-heavy views while retaining the fast
   wall-bounded path indoors. Early-query/hybrid ordering and projected row
   intervals are **proposals, not implemented**. Current skyline/envelope,
   stair-index and minimum-depth optimizations are implemented and tested.
3. Preserve exact ray/frame/depth results, sound and work budgets; then run a
   serial live-audio ABBA against `d20cd0d`, with an unused report path and the
   unchanged **15% mean and p95** gates. Retain every failure.

Detailed methods, failure list, profiles, controls and proposals:
[performance handoff](benchmarks/smooth-performance-2026-11-11.md).
[Benchmark index](benchmarks/README.md) covers older unresolved comparisons and
retained evidence, including the hash-verified starting-engine archive.

## Latest verification

- **393 native-console tests passed, zero skips** on Windows/Python 3.14.4,
  including desktop cursor checks, all stair routes, jumping/water, occlusion,
  sound and benchmark failure persistence. Snapshot passes.
- Latest completed comparison:
  `benchmarks/smooth-interleaved-depthbound-2026-11-11.json`, 120x40/60 frames,
  live audio: **12/24 pass**, zero underruns/recoveries. Warden mean/p95 still
  regress **105.32%/144.88%**. New terrain/stair scenes also remain costly.
- Native Ridge Hall demo: 100 frames at **80x24**, about **39.4 FPS** including
  cap waits, clean audio and terminal cleanup. This does not establish larger
  terminal or whole-world performance.

## Remaining limits

- Physical play/appearance and mouse capture/pause release in the user's tabbed
  Windows Terminal remain unconfirmed; keep `--keyboard-look`. Native fixes and
  evidence: [mouse diagnostics](benchmarks/mouse-capture-2026-11-10.md).
- Voxel edits intersecting a sloped heightfield replace whole XY cells;
  arbitrary partial-Z terrain cuts/caves are unsupported.
- Physical speakers/device reconnects, POSIX held keys and Python 3.10 remain
  unverified. The standalone audio diagnostic needs a fresh run. No save/load
  or objectives are implemented.

## Resume commands

Use a native console for complete input coverage. Set desktop-test opt-in only
when native cursor access is available. Temporary controls must be reconstructed.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
$env:MONOLITH_DESKTOP_TESTS='1'
python -B -m unittest discover -s tests -v
python -B main.py --region ridge
python -B main.py --keyboard-look
python -B main.py --audio-test
# Only if the control is absent:
git archive --format=zip --output=smooth-control-tmp.zip d20cd0d ascii3d
Expand-Archive -LiteralPath smooth-control-tmp.zip -DestinationPath smooth_control_tmp
python -B tools/benchmark_pair.py --before-source smooth_control_tmp --before-elevated-audio --frames 60 --audio --save benchmarks/smooth-next-unused.json
```

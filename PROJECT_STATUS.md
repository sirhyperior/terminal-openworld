# Project Status

Last reviewed: **2026-11-12**. Standing rules: [AGENTS.md](AGENTS.md).
User backlog: [user_designated_milestones.md](user_designated_milestones.md).
Gameplay/launch: [README.md](README.md).

## Current checkpoint

- CPU/GPU/loading/cleanup work is checkpointed at the user's explicit Git commit
  request on **2026-11-12**. The pre-session smooth-geometry control is `a3d044f`.
- The user approved GPU prototyping and subsequently complete integration once
  a performance advantage was demonstrated. Integration is implemented; further
  work within that approved architecture needs no renewed approval.
- `Renderer` uses optional hardware geometry queries with float64 refinement
  and exact CPU fallback for uncertain rays. Production shading, doors, actors,
  vegetation, HUD, input, physics and audio remain shared. CLI supports
  `--renderer auto|cpu|gpu`; auto uses available hardware. `run.bat` prefers the
  installed `.venv-gpu`. Optional wgpu 0.33.0 needs Python 3.11+; CPU remains
  standard-library/Python 3.10 compatible (3.10 execution still unverified).
- **Performance acceptance remains open.** Latest GPU comparison passes 14/24
  original-control roles; GPU improves several expensive views but regresses
  some cheaper ones. No baseline was replaced or 15% mean/p95 gate relaxed.
- Startup percentages are implemented and verified. Temporary workspace probes
  and controls have been removed, while benchmark evidence and reusable tools
  remain. No map, movement or gameplay behavior was changed in this session.

## Latest verification

- **420 native-console tests**, zero failures/errors, one sandbox desktop-cursor
  skip. Includes hardware GPU, device-loss fallback, edits, resize, aspect,
  collision/stairs/water, sound and loading. Native input tests ran successfully.
- Integrated GPU: **204 byte-identical full frame pairs**, including evolving
  simulation, doors, actors, wide/tall views and varied pitch. No coverage
  differences; maximum float64 depth difference **2.85e-14**. Existing tests and
  tolerances remain unchanged. Static prototype checks 428,400 samples.
- Latest serial 120x40/60-frame/live-audio ABBA:
  `benchmarks/gpu-integrated-compact-120x40-2026-11-12.json`, **14/24 pass**,
  zero underruns/recoveries. Earlier integrated runs pass 11/24 and 13/24;
  all failures and raw samples are retained. CPU repair alone also passes 14/24;
  its separate same-geometry comparison against a3d044f passes 34/34.
- Actual **160x50 native GPU Ridge demo**, 100 frames, walking and live sound,
  exit 0, loading reaches 100%, resources close. Mean render time after warmup
  28.371 ms; loop/write timing was not separately captured, so no FPS claim.
  Audio: zero underruns/recoveries, 61.0 ms maximum refill interval.

Detailed controls, failures, measurements and methods:
[2026-11-12 evidence](benchmarks/smooth-performance-2026-11-12.md).
[Benchmark index](benchmarks/README.md) links retained earlier controls/history.

## Next work and limits

1. Optimize GPU host finishing and investigate a measured CPU/GPU policy for
   cheaper views. A selection policy is **proposed, not implemented**. Latest
   failures: courtyard, meadow, grass_close, Warden, map, tree_close,
   tree_canopy, castle_exterior, west_meadow and east_meadow. Warden mean/p95
   remain +22.42%/+19.96% against **d20cd0d**.
2. Repeat full image/depth checks after meaningful changes, then serial matched
   live-audio ABBA with unchanged gates. Measure larger terminals and actual
   terminal output. Preserve full-terminal resolution and keyboard look.
3. The user's report of automatically walking onto castle-wall blocks remains
   uninvestigated in the backlog. Do not remove it or claim it fixed.
4. Physical play/appearance/mouse capture in the user's tabbed terminal,
   speakers/reconnects, POSIX held keys and Python 3.10 remain unverified.
   The standalone audio diagnostic was not rerun. No save/load or objectives.
   Partial-Z edits through sloped terrain still replace whole XY cells.

The user reaffirmed the **15% remaining usage** wrap-up rule, now in AGENTS.md.
The final check reached **12% short-window / 47% weekly remaining**; feature work
stopped and only handoff/cleanup continued. No benchmark/test jobs remain active.

## Resume commands

Use a native console for input coverage. Desktop cursor opt-in requires native
cursor access; the restricted workspace skipped that single test.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
$env:MONOLITH_GPU_TESTS='1'; $env:MONOLITH_DESKTOP_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv-gpu\Scripts\python.exe -B main.py --renderer gpu --region ridge
python -B main.py --renderer cpu --keyboard-look
# Reconstruct the original control only if absent:
git archive --format=zip --output=smooth-control-tmp.zip d20cd0d ascii3d
Expand-Archive -LiteralPath smooth-control-tmp.zip -DestinationPath smooth_control_tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_pair.py --before-source smooth_control_tmp --before-elevated-audio --after-renderer gpu --frames 60 --audio --save benchmarks/gpu-next-unused.json
# Same-geometry control, when needed, is a3d044f, not the historical d20cd0d.
```

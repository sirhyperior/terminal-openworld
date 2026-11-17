# Project Status

Last reviewed **2026-11-17**. [Repository rules](AGENTS.md) ·
[User backlog](backlog.md) · [Launch and controls](README.md).

## Current checkpoint

The default palette now uses graphite stone, wine-dark wood, heather foliage,
indigo water and cold spellfire. Local gusts turn foliage toward lilac and
silver, ash follows the wind, and aqua crests travel downstream. Architectural
voxels cast west-lit shadows through real openings. Gray mode preserves tonal
movement and the readable shadow floor. The changes are uncommitted for play
review. Immediate control `5b5a263` includes the previous visibility lift.

[Moonlight evidence](benchmarks/moonlight-2026-11-17.md) records the reference
inspection, three matched views, measurements and verification. The sampled
views have identical before/after depth and occupied character counts. The
33-test rendering group and 11-test hardware-parity/prepass group passed.
The full suite, including the newest ash test, remains pending at the usage
cutoff. Fullscreen appearance still needs user review.

## Remaining work

- **Current incremental CPU timing failed in 7/34 roles.** Great hall frame
  time rose 46.96% mean and 36.59% p95. Six other roles exceeded the 15% p95
  gate. The matched live-audio run completed with zero underruns or recoveries.
  Profile great hall and tree canopy first. No validation jobs remain active.
- Historical performance gates remain open. [Benchmark index](benchmarks/README.md)
  retains the original controls and failed runs, including the quality pass
  and earlier GPU p95 regressions. The old lag position at (215.2, 187.4, Z10)
  overlaps geometry. Reproduction in a playable camera remains open.
- Quality GPU incremental timing and native output diagnostics remain pending.
  Keep `quality_native_smoke_tmp.py` for those 120×40/160×50 checks. Resume
  guidance is in [the quality report](benchmarks/visual-quality-2026-11-14.md).
- The [six-landmark rebuild](benchmarks/visual-redesign-2026-11-14.md),
  blocky geometry, optimization and sound overhaul remain in the backlog.
  Physical mouse, speaker and fullscreen quality, POSIX held keys and Python
  3.10 execution still need host review.

## Resume

Play the new default color mode from the repository root. Run the suite in a
native console to include Windows input checks.

```powershell
.\run.bat
python -B main.py --renderer cpu --color-mode gray --keyboard-look
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv-gpu\Scripts\python.exe -B tools/profile_workloads.py great_hall tree_canopy --audio --save benchmarks/moonlight-profile-unused.txt
```

Use an unused path for each benchmark. Run measurements serially. To reconstruct
the immediate control for the moonlight comparison in a fresh directory:

```powershell
git archive --format=zip --output=moonlight-control-tmp.zip 5b5a263 ascii3d tools
Expand-Archive -LiteralPath moonlight-control-tmp.zip -DestinationPath moonlight-control-tmp
.\.venv-gpu\Scripts\python.exe -B tools/benchmark_same_geometry.py --before-source moonlight-control-tmp --reference-label 5b5a263 --before-renderer cpu --after-renderer cpu --frames 60 --audio --presentation styled --before-color-mode color --after-color-mode color --save benchmarks/moonlight-cpu-next-unused.json
```

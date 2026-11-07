# Benchmark Evidence

Read on demand for performance/audio history; current priorities/results are in
[PROJECT_STATUS.md](../PROJECT_STATUS.md). These reports are not interchangeable
approved baselines. Preserve failed/concurrent runs; compare mean and p95 on
matched hardware, Python, dimensions, frames and audio mode. Camera roles across
different maps are not identical geometry. Git checkpoint `f27e9ff` retains the
longer historical narrative removed from the main handoff during cleanup.

## Open Comparisons

- **Castle-wide acceptance is unresolved.** `castle-milestone-before-live.json`
  is the frozen old-map, 60-frame/120x40/audio control with actual Soundscape.
  `castle-milestone-live.json` predates room optimization;
  `castle-milestone-optimized.json` still flagged 16/18 comparable roles.
  `castle-milestone-control-recheck.json` also varied substantially in unchanged
  old code, for an unverified reason. Do not promote these to approved baselines.
- `castle-milestone-before.json` used the earlier ambient proxy.
  `castle-milestone-first.json` overlapped a visual probe: diagnostic only.
  `castle-size-scaling.json` isolates storage size with identical visible scenes
  padded from 112x112 to 160x160: <=1.0% mean/1.6% p95 added cost, audio off.
  This does not establish full geometry/audio performance.
- **Warden increment:** `watchstone-before.json` is the initial 23-scene snapshot.
  `watchstone-interleaved-first.json` failed Warden mean (+15.14%);
  `watchstone-interleaved-culling.json` failed p95 (+19.47%).
  `watchstone-interleaved.json` passed after convex spans: 24-scene ABBA,
  largest mean/p95 increases 4.23%/11.91%, no underruns/recoveries. These three
  reports use their own comparison schema, not the CLI `--compare` format.
  Frozen sources/probes were temporary; reports retain methodology/source hashes.

## Earlier References

| Reports | Purpose / limits |
| --- | --- |
| `vegetation-before.json`, `vegetation-current.json` | Vegetation reference pair; README's normal comparison uses the latter. |
| `trees-near-before.json`, `trees-near-after.json` | Close-tree rendering comparison. |
| `milestone-start.json`, `milestone-integrated.json` | Earlier milestone reference/integration; overall acceptance was already unresolved. |
| `doors-audio-current.json`, `door-creaks.json`, `sword-hit.json` | Door/audio and sword-feedback history. |
| `audio-repair-measurement.json` | Repaired audio, with frame-time flags preventing reference replacement. |
| `river-flow-initial.json`, `river-flow.json` | Initial run stalled with three underruns; later success does not erase it. |
| `staff-before.json`, `fire-staff.json`, `staff-training-interleaved.json` | Staff references and focused interleaved observations. |
| `fire-staff-concurrent.json` | Concurrent diagnostic; unsuitable as an isolated acceptance result. |
| `mouse-input-audio.json` | Render/audio smoke after the native input fix; does not time desktop capture or establish a new baseline. |

# Highland expansion — 2026-11-10

## Scope and milestones

The world grows from 112x112x12 to **512x512x32**: 20.90 times the ground area.
It retains dense standard-library voxel storage (8,388,608 cell bytes), the
original castle hub, weapon/enemy positions and seven shared interactive doors.
No streaming/storage architecture or new runtime dependency was introduced.

Terrain support heights span 1–20. Connected gravel routes cross terraced ridges,
valleys, Splitstone Ravine and four river bridges. About 1,300 sparse trees
include elevated trunks. Four instances of one configured building mechanism
provide three occupied floors, a balcony, roof access and guardrails:

| Landmark | Bounds X/Y | Occupied feet Z | Roof Z | CLI start |
| --- | --- | --- | ---: | --- |
| Ridge Hall | (136,40)–(160,64) | 5,10,15 | 20 | `--region ridge` |
| Northern Keep | (66,190)–(92,216) | 7,12,17 | 22 | `--region keep` |
| Hill Observatory | (214,178)–(238,202) | 10,15,20 | 25 | `--region observatory` |
| Far Citadel | (382,372)–(412,402) | 12,17,22 | 27 | `--region citadel` |

There are 12 physical stair flights. Grounded movement can climb one-unit
grass/gravel/masonry steps with support and clear headroom. Crates, wooden
guardrails and analytic doors retain their collision/jump behavior. A semantic
`terrain_step` event routes to registered surface-specific original Foley.

Grass retains 16 blades per clear cell before trunk exclusion and existing LOD
selection. It is generated in 4x4 chunks with a 128-chunk cache (at most 32,768
resident blades), with deterministic regeneration and voxel-edit invalidation.
Trees and grass use actual base heights; wind exposure follows the live floor
and roof. The terrain map shows a cached 96x96 local region and the HUD shows Z.

## Validation progress

- Nine terrain checks pass, including continuous entrance-to-roof walks, all
  stair flights, castle-to-Ridge Hall travel, additional bridges, guardrails,
  supported trees and deterministic elevations.
- Seven elevated-scenery checks and 18 existing vegetation checks pass.
- Seven movement/sound checks include support invalidation, unsafe-step
  rejection, large-radius exact trunk occlusion and registered Foley routing.
- Nineteen game-loop checks pass, including a selected elevated region's reset,
  inventory persistence, pause/help and mouse-release ordering.
- The first native full suite ran 298 tests with one failure: road painting
  replaced three original chapel floor cells. Road painting now preserves
  authored materials; the unchanged repeat-build regression passes again.
- Six representative exterior, upper-floor, rooftop and ravine frames were
  rendered for visual inspection. Generated previews are temporary.
- Final checkpoint native suite: **316 tests passed, zero skips**, in 96.240 s,
  with `MONOLITH_DESKTOP_TESTS=1`, workspace TMP/TEMP and Python 3.14.4.
  Full performance acceptance is deferred at the user's explicit wrap-up request.
- Final `python -B main.py --region ridge --demo --frames 100` native-console
  smoke exited 0 with live sound and terminal restoration.

## Performance method

The starting working source was copied to temporary `terrain_before_tmp/`
before development. The frozen rendering/simulation engine corresponds to
checkpoint `45062ddf039cb01bfaf7ca858798b3625b5ac126`; the preceding mouse repair
was present but is outside these headless benchmark imports. Reports retain all
production-file SHA-256 values so the measured variants can be identified after
temporary source cleanup.

`tools/benchmark_pair.py` loads both engines into separate import namespaces.
Each camera gets five warmup frames per variant, then per-frame **ABBA** order
with **60 measured frames per variant** at **120x40**, on the same Python 3.14.4,
Windows host and reported Intel CPU. Combat scenes run three 120 Hz steps/frame.
A shared isolated native audio process receives each engine's actual listener
position and Soundscape; frozen events are converted to the current semantic
event type for safe process transport. New live sampling includes feet height.

Comparisons retain the **15% mean and p95 limit in every matched scene**. The
24 original camera roles remain fixed. New terrain, upper-floor, roof, map and
walking scenarios have measurements but no fabricated historical percentages.
Raw per-frame samples, camera positions, startup costs, source hashes and audio
health are saved. Terminal output/frame-cap waits are excluded. These checks
measure this expansion against its starting engine; earlier castle-wide
historical acceptance remains a separate open issue.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
python -B tools/benchmark_pair.py --before-source terrain_control_tmp --frames 60 --audio --save benchmarks/terrain-followup.json
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --terrain-scenes --save benchmarks/my-terrain-run.json
```

For future changes, preserve the current `ascii3d/` tree before editing and pass
its parent directory to `--before-source`. The temporary tree for this change
is removed after review; retained reports are not silently replaced baselines.
To reconstruct the original render/simulation control for this checkpoint:

```powershell
git archive --format=zip --output=terrain-control.zip 45062dd ascii3d
Expand-Archive -LiteralPath terrain-control.zip -DestinationPath terrain_control_tmp
```

Use an unused report filename for each follow-up; never overwrite the retained
failed reports. The earlier mouse fixes differ in the temporary snapshot but
are outside the measured engine's imports.

## Retained runs and repairs

- `terrain-before-live.json`: initial 24-scene/60-frame/120x40 live-audio run,
  zero underruns/recoveries. General host timing drift makes this sequential
  historical comparison less informative than the contemporaneous ABBA control.
- **`terrain-interleaved-first.json`: failed 19/24 comparisons**, with Warden
  mean/p95 increases of **167.10%/161.03%**. Zero underruns/recoveries, 69.70 ms
  maximum refill interval. All failing data remain retained.
- `terrain-profile-first.txt`: diagnostic call counts showed excess repeated
  empty-space traversal. Per ten bridge frames, floor calls rose from 307,896
  to 695,625; Warden 191,302 to 674,474; great hall 161,769 to 412,509.
  Profile timings are diagnostic and are not substituted for wall-time checks.
- **`terrain-interleaved-optimized.json`: failed 8/24 comparisons** after the
  initial overlap/sky repairs. Audio had zero underruns/recoveries and an 87.76 ms
  maximum refill interval. Matched camera failures remain recorded, including
  east bridge mean/p95 +92.36%/+80.22% and Warden +57.82%/+52.74%.
- `terrain-profile-sweep.txt` and `terrain-traversal-counts.json`: full yaw-sweep
  diagnostics identified additional region-boundary crossings toward new terrain.
  A second atlas of column-oriented empty volumes reduced bridge and east-bridge
  iterations while retaining exact ray results. Conservative angular sky bounds
  were subsequently implemented and checked against ordinary DDA.
- **`terrain-interleaved-horizon.json`: failed 4/24 comparisons**, with zero
  underruns/recoveries and a 69.84 ms maximum refill interval:

  | Role | Mean change | p95 change |
  | --- | ---: | ---: |
  | bridge | +17.10% | +25.46% |
  | east bridge | +15.25% | +19.43% |
  | Warden | +33.34% | +35.10% |
  | river diagonal | +23.99% | +24.88% |

  All ten new terrain/floor/map/walking scenarios measured mean 5.475–19.017 ms
  and p95 6.450–20.491 ms. These observations do not establish terminal FPS or
  erase the four matched-role failures.
- `terrain-horizon-counts.json`: conservative azimuth skyline diagnostic.
- `terrain-scenery-spans.json` and `terrain-scenery-spans-wind.json`: isolated
  same-geometry scenery checks, including exact frame equivalence. Crown spans,
  hidden scanline rejection, cached tree candidates and delayed hidden-grass
  wind sampling reduce work without changing density or geometry.
- `terrain-signed-inverse.json`: isolated exact-image arithmetic diagnostic.
- `terrain-combat-prepass-prototype.json`: ungated prototype; Warden mean/p95
  -7.57%/-12.65% with identical frames. Final code adds a generic large-enemy
  coverage gate and a conservative crown-work bound so foliage cannot exhaust
  its sample budget due to hidden terrain. Five reference tests cover this gate.

The repair recovers maximal overlapping clear row rectangles with two linear
vertical passes. Room occupancy unions are memoized and limited by an explicit
linear work budget, with conservative disjoint prisms as an exact fallback.
Upward rays stop above a conservative local voxel ceiling covering the entire
unnormalized ray footprint; dynamic shapes retain their independent depth pass.
Corner checks and known boundary cells avoid redundant round/floor calls.

After these repairs, diagnostic floor counts per ten frames were 306,236 for
bridge, 189,746 for Warden and 108,070 for great hall. Exact accelerated versus
ordinary DDA comparisons passed for elevated floors, wide-frustum tall geometry,
indoor room cases and 48 original benchmark poses. Ray depth 48, traversal cap
110, vegetation pixel budgets and visible detail have not been reduced.

Performance acceptance remains pending; failed reports are not promoted to
baselines. Later early-sky, signed-inverse, scenery and gated combat-prepass
changes have focused correctness/diagnostic checks but **no complete final
live-audio ABBA run**. The user requested a checkpoint instead of further tuning.

## User-requested future milestones

1. Fill the terminal's entire usable screen to increase character-cell resolution.
2. Replace visibly blocky voxel terraces with smooth natural hillside surfaces.
3. Replace chunky one-unit stairs with smaller risers/treads.
4. Complete performance acceptance after those designs and the current pending
   optimization checks, preserving all existing evidence and limits.

These are future tasks, not changes claimed by this checkpoint. Geometric
representation, collision/support, vegetation and Foley need a coordinated
design for smooth slopes and finer stairs; see `PROJECT_STATUS.md` for handoff.

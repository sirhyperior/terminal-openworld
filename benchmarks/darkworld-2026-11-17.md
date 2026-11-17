# Dark world, sound and continuous-geometry checkpoint

The user requested original backlog items 1, 5 and 6, then asked for stronger
particles and work on blockiness while usage permitted. The implementation is
uncommitted for play review. Immediate control is **46c36a3**; the repository
engine was clean at session start. The user's backlog edit was preserved until
verified completed entries were removed and the remaining items renumbered.
Historical performance controls and failed reports remain independent.

## Implemented map

The approved six-site brief is now authored: Ashgate (128,96), Gravewood
(72,248), Thornwatch (304,132), Black Abbey (216,360), Astral Reliquary (388,284)
and Mourning Citadel (420,436). Gravel roads form a continuous loop, with an
Ashgate-Abbey shortcut and the Abbey-Reliquary route over the Riven Vale.
Three timber bridges cross the relocated, winding central river. Its analytic
centerline derivative still drives current and water strokes.

Ashgate retains the proven gatehouse, court, hall, cloister, garden, training
and wall-walk circulation at its new location. Gravewood has graves, seeded
woods, a ruined staff chapel and the Warden clearing. The four highland sites
share three occupied levels and fine stairs, while broken vaults, fractured
roof sectors, terraces, buttresses and unequal spires distinguish their forms.
Six doors use existing shared targeting, animation, collision and sound.
Starting swords, staff, dummies and Warden moved with their destinations.
All original controls, inventory/combat behavior and return-to-selected-start
behavior remain. New CLI destination names retain ridge/keep/observatory aliases.

Actual fixed-step tests walk continuously from the indoor start through all six
sites and back, plus all shortcut/local road segments. All thirteen flights
retain bidirectional walk/sprint traversal and 1,040 exact stair contacts.
Three river bridges are tested in both directions; the elevated ravine deck
retains dry support over its steep trench. Initial steep banks, a grave across
the chapel path and the Citadel terrace rail obstruction were repaired.

## Shape and particle work

Reusable exact convex arches, buttresses, octagonal tapered towers and diagonal
corner bevels participate in the existing ray/collision/support paths. Eight
seeded irregular rock outcrops use one solid each. Grass with narrow gravel
approaches replaces rectangular gravel foundation pads. No new dependencies,
physics architecture or per-frame geometry generation were added.

This is progress on the original broad blockiness request. Large wall/floor
volumes and authored props still use rectilinear forms; the remaining backlog
entry stays open for further appearance review.

Ash/dust have more static world-anchored seeds eligible near eye height. Across
64 deterministic empty-sky poses (four positions, heights and headings), central
seven-row visibility rose **117 to 214 (+82.9%)**, and whole-view visibility rose
**555 to 748 (+34.8%)**. This supersedes the earlier modest +24.8% eye-band tuning.
The same 65 ambient candidates are tested per sampled 120x35 pose. Maxima remain
96 ambient candidates, 256 total candidates, 128 draws and 64 cached chunks;
cache contents can reach 1,152 motes. Dynamic effects retain first claim on the
work budget. Wind, simulation time, depth hiding and UI protection remain tested.

## Sound

All existing semantic cues now use original dark-fantasy procedural Foley:
filtered air/cloth/grit, damped inharmonic material impacts, heavy door friction,
iron/wood contact, cold turbulent spellfire, low stone Warden gestures and quiet
parchment/leather interface sounds. Wind and river use textured turbulence.
Recurring stone/relic contacts have repeatable variants. No external recordings
or new assets/licenses are required. Mixer/process/device architecture, eight
voice cap, fades, mute, volume, pause, silence fallback and queue health remain.

## First grid-version validation

These results describe the six-site version frozen in
`darkworld-grid-control-2026-11-17.zip` (100 files with SHA256 manifest).
They precede the user's clarified continuous-road/rotated-building work below.

- Final real Windows console: **564 tests, zero failures/errors, one opt-in
  desktop pointer skip, 202.776 seconds**. Python 3.14.4, optional hardware GPU
  checks enabled, both console handles valid and engine hashes unchanged.
  [Full output](darkworld-native-tests-final-2026-11-17.txt) and
  [environment/source evidence](darkworld-native-tests-final-2026-11-17.json).
- Architecture includes exact pointed-opening/bevel/rock ray and cylinder
  tests, four complete CPU/GPU architecture images and the existing 1e-7 depth
  tolerance. All authored spires remain below world height Z32.
- Software color previews inspected six exterior views and gatehouse, great
  hall, Abbey nave, Reliquary roof, Citadel upper gallery and staff chapel.
  Temporary previews are removed after review. These do not verify the user's
  physical fullscreen display, mouse or speakers.
- Retained first aborted wrapper output/metadata: missing multiprocessing
  main guard caused workers to attempt exclusive report creation. Engine code
  was unaffected. The next ConPTY run retained eight rejected native input
  injections and one stale tree test. The tree now uses CLOSE_TREE; the final
  genuine-console run passes. Its partial JSON is retained alongside recovered
  metadata because the earlier wrapper tried to serialize unittest objects.

The live 18-second audio diagnostic played **395 buffers**, with **zero empty
queue events**, **zero recoveries** and **74.0 ms** maximum refill interval.
[Audio diagnostic](darkworld-audio-check-2026-11-17.txt) retains the output.
Complete production CPU/GPU presentation passed **36/36 frame pairs**, including
style/material/effect/color/gray ANSI and opaque coverage; maximum depth error
7.11e-15. [Parity report](darkworld-gpu-parity-2026-11-17.json).

Matched 120x40, 60-frame, styled/color, live-audio ABBA against46c36a3:

| Backends | Roles passing15% mean/p95 gate | Underruns / recoveries | Max refill gap |
| --- | --- | --- | --- |
| CPU/CPU |12/34 |0 /0 |72.73ms |
| GPU/GPU |19/34 |0 /0 |77.84ms |

[CPU raw samples](darkworld-cpu-live-2026-11-17.json) and
[GPU raw samples](darkworld-gpu-live-2026-11-17.json) retain every failure.
These are semantic comparisons across different layouts using the locked
[role manifest](darkworld-roles-2026-11-17.json), not identical-geometry timings.
The largest CPU change was the old lodge vs new Thornwatch view (+393.36% mean,
+353.69% p95; after130.419/144.164ms). No baseline or threshold changed.
Actual app terminal-write120x40/160x50 checks were not started before the cutoff.

## User clarification and latest working changes

The user explicitly clarified overall grid-aligned forms, especially diagonal
road edges, building orientation/masses and the map. Decorative bevels do not
complete that goal. The following edits are newer than the full suite/timings:

- RoadNetwork uses true point-to-polyline capsule boundaries, rounded joins,
  <=8-unit pieces and bounded buckets (production maximum8 pieces per bucket,
  hard construction bound96). Raster road painting was removed. Rendering,
  ground materials, Foley, grass roots and map sampling share exact point
  classification; terrain support/collision elevations are unchanged.
- Thornwatch rotates17 degrees and the Reliquary-23 degrees. Complete authored
  voxels are merged into exact convex cuboids and rotated alongside arches,
  windows, floors and quarter-rise treads. Terrain pads, entrances, road ends,
  spawn headings and benchmark cameras follow the same rigid transform.
  Marked convex treads retain ordinary stair ascent permission; equal-height
  floor materials take precedence over natural terrain.
- Map aggregation now uses nine fractional samples per character and bounded
  neighborhood directions for road and building edge glyphs, instead of integer
  any-hit cells. Six shape/cache/work-budget checks pass; cache hits make no
  world sampling calls.

Latest focused checks:19 road/elevated/presentation tests pass, including actual
CPU/GPU flat and sloping road material/style/effect parity. Eight rotation/terrain
checks pass, including all12 highland flights both ways with Foley, clear
entrances, floor supports, guards and every ground-to-roof walk. All destination
starts build without player collision. These checks do not establish a full
current-source test pass or rotated GPU parity.

Mandatory usage cutoff stopped new work. Current world has7 unrotated flights
in `_stair_keys` and6 transformed entries in `_oriented_stairs`. The old aggregate
block-walking test still assumes all13 are axis-aligned; migrate it using the
new metadata. The continuous six-site loop passes with transformed interior joins, but the
ravine-to-Reliquary shortcut stalls near (340.76,306.5,Z10.64) on the326,306 to
350,306 segment. The player remains grounded/collision-free; investigate grade.
The point-material assertion changed after the run has not been rerun. Preserve
that regression. The full current suite, oriented hardware frames, new semantic
manifests/timings and actual terminal output remain pending. Broader blockiness stays open.


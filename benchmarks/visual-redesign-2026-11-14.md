# Grayscale redesign checkpoint

The user approved the full visual/world plan on 2026-11-14. This report records
the foundation increment; **the full milestone is not complete**. No full-color
work or world-layout replacement has begun. Stop for user play review after the
finished grayscale world, before introducing rich color throughout.

## Approved destination and presentation brief

Retain the dependency-free Python CPU engine, optional GPU, terminal display,
512x512 map, controls, existing combat and interaction behavior. Target the
current 40 FPS cap without claiming sustained 40 FPS today. Both supplied reels
were inspected: fine characters, rounded opaque forms, dark negative space,
sparse highlights and brightness-driven depth are the reference vocabulary.

| Destination | Center | Authored purpose |
| --- | --- | --- |
| Ashgate | 128,96 | Starting fortress, gatehouse/court/cloister/training/wall walk |
| Gravewood | 72,248 | Twisted woods, graves, staff chapel, Warden stone circle |
| Thornwatch | 304,132 | Tapered ridge watchfort, upper rooms and roof route |
| Black Abbey | 216,360 | Breached nave, pointed arches, raised undercroft, broken towers |
| Astral Reliquary | 388,284 | Fractured observatory roof and elevated galleries |
| Mourning Citadel | 420,436 | Largest fortress, terraces, three occupied levels, high overlook |

Connect them in a loop, add Ashgate-Abbey and Abbey-Reliquary links (the latter
crossing a deep ravine), and place a winding river across the middle with three
bridges. Rebuild continuous hills, irregular woods/rock/clearings and long views.
Keep dry routes, real stairs, walkable doors, jump-only ordinary props, launcher
region aliases, and return-to-selected-entrance behavior. No new AI/objectives/save
system. Every added audible source needs events, cues and coverage.

## Implemented foundation

- Shared `Shading` material/normal/distance response and cached semantic `Ink`
  tokens now cover terrain, water, doors, foliage, actor faces and weapons.
  Up to two fireballs contribute local lighting; exact LOS work is capped at
  256 queries per shading context. Exact sample/normal cache keys prevent thin
  wall leakage. Foliage texture coordinates translate with its volume.
- `StyledFrame` carries explicit dimensions, glyph rows, bytearray grayscale
  levels and material identities. ANSI runs keep foregrounds neutral, background
  black, and reset per row. `--color-mode gray|mono` defaults to gray; plain
  snapshots and the uniform-white fallback contain no ANSI.
- Immutable bounded `ConvexSolid` pieces have exact halfspace ray hits/normals,
  vertically clipped cylinder collision and circular footprint support.
  Existing boxes/stairs retain fast paths and movement permission remains
  separate from generic support. World queries share the real pieces.
- GPU solid candidates use exact convex planes and a stackless AABB hierarchy.
  Bounds reject candidates only; float64 refinement and uncertainty fallback
  remain. Real GPU tests include missing a front AABB's solid and hitting a
  farther true solid, seams, tangencies and edits.
- Benchmark tools accept explicit before/after backend choices and reject silent
  fallback. Optional version-1 role manifests record distinct old/new poses for
  changed-map semantic comparisons. Geometry fingerprints include convex faces
  and vertices, not just their bounds.

## Preserved evidence and limits

- `visual-control-2026-11-14.zip` preserves 83 current working files, including
  the prior uncommitted loading/movement fixes. Every archived file was SHA256
  verified against the source at capture; `source-manifest.json` is inside.
  HEAD alone is not this control.
- `visual-hotspot-before-2026-11-14.json` retains raw CPU/GPU full-turn/local-walk
  samples at the reported (215.2,187.4,Z10). That exact position overlaps geometry
  (highest generic support Z25). This audio-off diagnostic is not a verified
  reproduction or a valid playable-camera acceptance benchmark.
- `visual-foundation-first-tests-2026-11-14.txt`: 123 focused checks, ten failures
  (old literal-glyph expectations and missing normal influence on turf glyphs).
  Expectations now verify opaque coverage/materials; turf glyphs respond to light.
- `visual-foundation-full-tests-2026-11-14.txt`: 475 checks, one foliage vertical
  translation failure, one Windows atomic-report replacement error, eleven skips.
  Translation was repaired using local texture coordinates; all ten elevated
  scenery checks then passed. All seven benchmark checks passed on immediate
  rerun without a code change for the replacement error. Preserve this failed run.
- Four software-rendered grayscale views (hall, exterior, tree, ravine) were
  inspected. These do not establish appearance in the user's terminal or motion
  quality. Temporary preview files are removed after review.

Final native verification: **475 tests passed, zero failures/errors, one sandbox
ClipCursor skip, 169.703 seconds**. `visual-foundation-native-2026-11-14.txt/.json`
verify native console handles and unchanged source hashes. The aborted first
helper launch has separate retained metadata; the successful helper was removed.

Same-geometry performance results are recorded below when complete. Historical d20cd0d performance acceptance stays independent
and unresolved; never replace it with this new control.

## Matched performance and wrap-up

`visual-foundation-cpu-live-2026-11-14.json`: identical geometry, explicit CPU/CPU,
120x40, 60 measured frames per role, live audio, ABBA. **1/34 passes; 33 fail**
the unchanged 15% mean/p95 gate. Only stair walking passes (+12.45% mean,
+13.39% p95). Audio available, zero underruns/recoveries, maximum gap 57.78 ms.
The result does not establish renderer performance acceptance.

`visual-foundation-gpu-live-2026-11-14.json`: matched GPU/GPU conditions, **4/34
passes; 30 fail**. Complete with no errors/fallback, zero audio underruns or
recoveries and maximum gap 60.43 ms. Both reports' final engine hashes match
current source. No historical baseline or threshold changed.

GPU/GPU finished safely after the mandatory 15%-remaining cutoff. No jobs remain;
the native helper, previews and extracted frozen source are removed. The control
ZIP and manifest remain available for reconstruction. Prioritize profiling scalar shading, foliage material work, style/material packing
and shadow queries before any map replacement. Keep every failed report.

## Remaining work and resume order

1. Preserve final native-suite evidence; extend CPU/GPU complete-frame verification
   to compare style/material buffers as well as glyphs and exact depths.
2. Pass CPU/CPU and GPU/GPU 120x40, 60-frame live-audio ABBA against the frozen
   current-map control, keeping 15% mean and p95 limits. Measure actual terminal
   serialization/frame pacing separately; headless timings omit terminal writes.
3. Add/test the configurable arch, buttress, tower, ruin and rock construction
   kit. Then author the approved six-destination world and relocate gameplay.
4. Add bounded mist/dust/embers, finish actor art and HUD/menu/loading styling,
   validate sound coverage and verify routes/occlusion/new geometry.
5. Lock before/after semantic role manifests before final timing optimization.
   Inspect 60x20,120x40,160x50 and actual fullscreen, including motion/pause/map.
6. Deliver the complete grayscale milestone for user play review. Only after
   approval implement rich material colors and extend the same output buffers.

Do not remove map/blockiness/optimization/color backlog entries for this foundation
increment. No commit is authorized until successful user implementation review.

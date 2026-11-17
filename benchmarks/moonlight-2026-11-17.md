# Moonlit color and environmental response

The previous playable colors and visibility lift are committed at `5b5a263`.
Both reference reels were inspected on November 17. The tree carries a few
bright tips across a darker branch mass, and shaded gaps distinguish the roses
in the bouquet. The new color mode uses this distribution of light on the
existing map. [Tree](https://www.instagram.com/reel/DfoWsojSWA2/) ·
[Bouquet](https://www.instagram.com/reel/DfryVt2yjpb/)

## Presentation

- Four authored color stops per material blend across 16 tones. Stone runs from
  graphite to pewter, wood through muted wine, and grass through heather. Distance
  blends the materials toward a common blue-gray. White is available to a
  spellfire core. Visible fire casts cyan. Gray and plain ASCII remain available.
- Westward sky rays use a static projection of opaque voxels into (y, x + z).
  Each interval stores the first west or top face. A single lookup determines
  whether a sample is shaded. World edits rebuild the projection with the other
  renderer caches. Voxel walls, roofs and bridge decks cast these shadows. Other
  geometry can receive them. Local firelight still uses its separate scene LOS.
- Grass, swaying blade tips and tree crowns take their exposed colors from the
  local wind. Dust and ash sample that wind by particle chunk. Ambient dust has
  a steady tone. Water switches between indigo troughs and aqua crests along
  the downstream wave, with a tonal change in gray. All use simulation time.

## Matched frame inspection

CPU styled output at 120×42, simulation time 2.0, rendered in software with
8×16 Consolas cells. Comparisons crop the five HUD rows. Each pair has an
identical opaque depth-buffer hash and identical nonblank cell count.
Foreground luma averages weighted RGB over the nonblank scene glyphs, including
particles. It measures the ink, independent of glyph coverage or monitor brightness.

| View | Position and heading (x, y, z, yaw, pitch) | Cells | Before luma | After luma |
| --- | --- | ---: | ---: | ---: |
| West cloister | 35.5, 43.5, 1, 1.34, −0.03 | 4,224 | 201.5 | 142.8 |
| East meadow | 100.5, 68.5, 1, π/2, −0.10 | 3,176 | 202.4 | 161.6 |
| River crossing | 8.5, river_center(8.5), 0.12, 0, −0.10 | 3,345 | 211.7 | 174.0 |

The river animation samples five seconds at eight frames per second. The
playable scene and particle budgets supply every character. The sheet and
animation accompany the chat handoff outside the repository.

## Verification

- 33 surface, actor, shading, visual-quality and color-integration checks passed
  together. Two new shadow checks cover 2,240 voxel-ray comparisons, a carved
  opening, cache rebuilding and a shaded floor's readable glyph and level.
- 11 hardware-enabled color parity and combat-prepass checks passed together.
  Focused palette, wind, water, particle and foliage tests also ran during
  implementation. The full discovery suite, including the final ash-specific
  check, remains to be rerun at the next session.
- Fullscreen appearance and interactive motion still need play review.

## Incremental performance

The [matched CPU report](moonlight-cpu-live-2026-11-17.json) completed all
34 roles at 120×40, Python 3.14.4, 60 frames per variant, with per-frame ABBA,
styled ANSI serialization and live Windows audio. Geometry fingerprints matched
and final engine hashes matched the measured source. Audio recorded zero
underruns, recoveries and errors. The unchanged 15% mean/p95 limit passed in
27 roles and failed in seven.

| Failed role | Mean increase | p95 increase |
| --- | ---: | ---: |
| Close grass | 8.74% | 20.31% |
| River | 11.57% | 19.19% |
| Close tree | 13.29% | 20.73% |
| Tree canopy | 14.07% | 16.25% |
| Great hall | 46.96% | 36.59% |
| Citadel approach | 11.13% | 24.90% |
| Terrace walk | 9.33% | 17.07% |

The measurements include shadow sampling, motion response and terminal
serialization in the frame cost. They do not isolate a cause. Profile the
great hall and canopy first. Retain this report for comparison after repairs.

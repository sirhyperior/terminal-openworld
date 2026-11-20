# Ash and moonlit highlights

Reviewed 2026-11-21. Immediate source control is `b988df7`, the committed
continuous-road and angled-landmark world. The working appearance pass uses
that same world and changes presentation only.

## Earlier contrast experiment (superseded)

The user asked to restore the darker atmosphere and confine the new light to
specks. The descriptions and results in this section are the rejected first
pass. The subsequent correction is described below.

- The seeded ash/dust field concentrates more motes at eye height. It culls
  hidden and offscreen points before spending the ambient emission budget.
  The extra examination cap is 256 seeds a frame, with the existing 96 ambient
  candidates, 256 total candidates, 128 draws and 64 chunks retained. Dust is
  brighter and some nearby dust takes up two dots. Ash is silver with rare
  one-cell stars during gust peaks. Dynamic effects keep priority and the same
  opaque depth and UI protection apply.
- The shadow floor remains readable. A more distinct palette separates blue-gray
  stone, wine wood, warm gravel, heather, lilac foliage and indigo water. Light
  catches chipped masonry and exposed gravel, glances off metal at reflecting
  angles and rises on foliage with gusts. Water has stronger aqua crests and
  sparse crest highlights that move with the current and respect voxel shadows.
- Highlights use the existing voxel moonlight map. Convex and rotated roofs
  have the existing limitation that they do not enter that shadow map.

Across three times and headings at each of six paired 120x40 scene samples,
visible motes increased from 259 to 687 (2.65x), with mean foreground level
5.22 to 8.52 on a 0–15 scale. This comparison preceded the final glyph-only
adjustment and removal of redundant frustum work. Both keep the selected visible
positions and levels. Paired indoor, exterior, river and hall stills were also
inspected. The river diagonal view at simulation time 1.5 showed 53 distinct
white crest cells. Temporary previews are removed after inspection.

The focused 76-test lighting/render/actor/work-budget run passed, with real GPU
color parity enabled. The focused 24-test particle run passed, covering bounds,
determinism, indoor and outdoor visibility, animated glints and solid/UI hiding.
An outdoor movement run found the 388–393 X, 207–231 Y bridge test already fails
in both directions. The failures reproduce with the untouched `b988df7` engine.
No full current native suite pass is claimed.

The [matched GPU run](moon-glints-gpu-silent-2026-11-21.json) used the same
geometry fingerprint, RTX 3080 Laptop GPU, Python 3.14.4, 120x40 styled color,
60 measured frames per role and audio off on both sides. All 34 mean times
stayed within the established 15% gate. The p95 gate passed 32/34 roles:

| Role | Before mean / p95 ms | After mean / p95 ms | Change mean / p95 |
| --- | --- | --- | --- |
| Indoors | 25.850 / 31.585 | 28.285 / 47.481 | +9.42% / +50.33% |
| Tree canopy | 19.811 / 24.397 | 21.259 / 28.576 | +7.31% / +17.13% |

The [first live-audio attempt](moon-glints-gpu-live-2026-11-21.json) and
[retry](moon-glints-gpu-live-retry-2026-11-21.json) each stopped before
measurement after an audio worker startup timeout. Both are retained. The
headless timing omits terminal writes and cannot establish fullscreen FPS.

The [production frame parity run](moon-glints-parity-2026-11-21.json) passed
36/36 CPU/GPU frame pairs across six camera roles, matching glyph, style,
material, effect, ANSI and opaque coverage. Maximum depth error was 1.43e-14.
The [native 160x50 smoke](moon-glints-native-160x50-2026-11-21.json) drew all
60 requested frames with actual GPU color, movement, live device audio and
restored console state. The audio device submitted 68 buffers with zero
underruns or recoveries. This is a launch and output check.

## Sparse correction

The ordinary palette and shading source now match `b988df7` exactly. The
increase in particle density comes from seeded eye-level placement and earlier
visibility culling. Steady dust and ash use the original brightness range and
glyphs. A small fraction of rising ash can flash at a gust peak for a short
simulation-time interval. At most two ash stars can appear in a scene. Water
uses the earlier crest brightness with up to four one-cell glints. Glints are
spaced apart, follow the crest motion, and respect the voxel moonlight shadow.
Metal uses the original view-dependent reflection.

With particles disabled, comparison against `b988df7` at three times showed
identical indoor, hall, castle exterior and canopy frames. The three river
views changed only at glint cells. Focused verification passed 61 tests,
including real GPU color parity, particle bounds and brightness, and river
placement, motion and shadow suppression. The rendering and input loop still
uses the same opaque geometry.

The [initial sparse-pass matched GPU run](sparse-glints-gpu-silent-2026-11-21.json)
used the same geometry fingerprint, RTX 3080 Laptop GPU, Python 3.14.4,
120x40 styled color, 60 measured frames per role and audio off on both
sides. All 34 mean times stayed within the 15% gate. The p95 gate passed
32/34 roles. Indoors moved from 30.962 ms to 46.873 ms (+51.39%) and the map
view moved from 30.611 ms to 35.313 ms (+15.36%). The historical reports
and gates are retained. This run preceded the final ash pulse adjustment.

The initial sparse comparison counted 674 visible motes versus 231 in 21
matched frames at 120x40. The initial ash trigger produced no flashes in
20 seconds of wind sampling at each of three fixed outdoor/entrance cameras.
Removing the extra seed eligibility gate made the flashes visible without
raising either their brightness or the two-spark limit. Using the same camera
poses, captured opaque depths and real world wind, a flash appeared on 35/480
sampled ticks in the gatehouse, 28/480 in the courtyard and 38/480 outside the
castle. The water and particle density did not change in this adjustment.

The [final trigger timing run](sparse-glints-final-gpu-2026-11-21.json) used
identical settings. All 34 mean gates passed. The p95 gate passed 31/34
roles. Indoors rose from 34.792 ms to 50.669 ms (+45.63%), ridge upper from
69.528 ms to 81.599 ms (+17.36%), and citadel roof from 29.082 ms to 34.178 ms
(+17.52%). The final 61 focused tests passed. The [final parity report](sparse-glints-final-parity-2026-11-21.json)
matched all 24 CPU/GPU frame pairs across gatehouse, hall, castle exterior
and diagonal river poses. Side-by-side stills were inspected and the temporary
previews were removed.

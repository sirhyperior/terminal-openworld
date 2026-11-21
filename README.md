# MONOLITH

A dark fantasy first-person exploration sandbox drawn entirely with
**colored ASCII text on black**. Future structures, landscapes, NPCs and enemies
follow that theme.

Stone runs from graphite to pewter, timber has a muted wine tint, and pale
gravel marks a route through heather-colored grass. Moonlight enters from the
west. Walls, roofs and bridge decks cast shadows across floors and figures.
Mortar, wood grain and armor bevels still catch enough light to read in shade.
Distant silhouettes soften toward blue-gray against the black sky.

Gusts turn grass toward silver-blue and catch lilac edges in the canopy. A
denser drift of dim ash and dust hangs near eye height, with occasional bright
flecks as the wind lifts the ash. Indigo water carries aqua crests and a few
pinpricks of moonlight downstream. Spellfire has a pale core, violet embers and
a cold light that reaches nearby surfaces. Pause or open help to freeze the
wind, current and particles together.

Use `--color-mode gray` for neutral grayscale or `--color-mode mono` for uniform
white. Snapshots remain plain ASCII in every mode. Colors carry semantic material,
light and depth data through the same opaque depth tests used by the world.

Explore a **512 by 512 world** with six connected dark-fantasy destinations:

| Destination | What to explore |
| --- | --- |
| Ashgate (128,96) | Spired fortress, court, training yard, garden, cloister and wall walk |
| Gravewood (72,248) | Grave rows, ruined staff chapel, irregular woods and the Warden's watchstones |
| Thornwatch (304,132) | Ridge watchfort with narrow spires and an upper balcony |
| Black Abbey (216,360) | Broken towers, breached nave and surviving pointed vault ribs |
| Astral Reliquary (388,284) | Elevated galleries under a fractured octagonal roof |
| Mourning Citadel (420,436) | Largest fortress, guarded terraces, three floors and a high overlook |

Gravel roads form a loop between all six sites, with an Ashgate-Abbey shortcut
and a crossing from the Abbey toward the Reliquary over the Riven Vale.
Three timber bridges span the winding river through the middle of the map.
Broad slopes blend into the roads and building approaches. Follow continuous
hillsides and quarter-unit stone stair risers; jump to climb ordinary props.
The four highland buildings each have three usable floors, real stairs, windows,
a balcony and a rooftop overlook. Ashgate's west steps reach the cloister roof
and adjacent wall walk. Pointed arches, tapered octagonal spires and sloping
buttresses use the same opaque geometry for sight and collision. Diagonal
tower corners, grass approaches and irregular stone outcrops soften the earlier
layout. The latest working changes give roads continuous rounded boundaries
and rotate Thornwatch by 17 degrees and the Reliquary by -23 degrees, including their
walls, floors, stairways and openings. This broader geometry update is still
under validation; see PROJECT_STATUS.md before treating it as accepted.

M shows a local terrain map that follows your position. `^` marks high ground,
`;` lower hills, `~` water and `=` bridges. Your direction marker moves over
the map; the lower HUD shows your region, coordinates and elevation.

Continuous ground geometry is shared by rendering, collision, vegetation,
targeting and footstep contacts. All thirteen stair flights use the same fine
step mechanism. Frame-rate acceptance and physical fullscreen review remain
open; see [the current checkpoint](PROJECT_STATUS.md).

Six wooden doors use **E**, with shared swinging animation, sound and obstruction
protection: Ashgate's four gates and hall doors, plus Gravewood's chapel doors.
Other arches are open passageways. Look at a nearby door to see its prompt.
Doors stop or reopen if a leaf would hit you; step clear before closing.

Collect the upright **iron sword with E** near either Ashgate starting entrance.
Find the **fire staff** on the western timber floor inside Gravewood Chapel
(`68.5, 248.5`). **You can hold only one item**: collecting another drops the
held item nearby. The prompt names the item that will be dropped.

Press **left click** to swing the sword or fire the staff. Ashgate's three
passive training dummies stand at `(115.5-123.5, 94.5)`. Their names and health
appear only when aimed at with clear sight. Sword reach is about 2.5 units;
fireballs travel up to 28 units and stop at walls, doors, trunks or targets.
The staff fires once per click with a 0.65-second cooldown and no ammo limit.
Either weapon deals one damage. Three hits knock a dummy down; it resets after
four seconds. Its fixed support stays solid while it is down.

A **Watchstone Warden** guards the western Gravewood clearing (`34-48, 242-256`).
This four-HP stone guardian notices players within 7.5 units, follows them,
and raises its fists before a close ground slam. Step away during the warning.
It stays in its clearing and returns home when you leave. Defeat it with either
weapon; it respawns at home after 12 seconds, waiting if that spot is occupied.
R returns you to your selected entrance with held item and world state preserved.

The upper HUD shows your **10-point health bar**. A Warden hit costs two health.
Defeat returns you to your starting entrance with full health, keeping your
held item and world state. R also restores health when returning to the entrance.

The renderer casts a real 3D ray through buildings and terrain for every character. The
camera has perspective, pitch, height, textured surfaces, face lighting, and
distance shading. Movement includes gravity, cylinder collision, sliding along
walls, and jumping with head collision.

## Run

Requires **Python 3.10 or newer**, with **no extra packages**.

```powershell
python main.py
```

To start in the southern meadow facing the castle:

```powershell
python main.py --outside
```

Start at a destination directly. R and defeat return to the selected entrance
while preserving inventory and world state:

```powershell
python main.py --region ashgate
python main.py --region gravewood
python main.py --region thornwatch
python main.py --region abbey
python main.py --region reliquary
python main.py --region citadel
```

The old `ridge`, `keep` and `observatory` aliases select Thornwatch, Black Abbey
and Astral Reliquary. The default indoor start is Ashgate's south gatehouse
`(128.5, 76.5, Z1)`; `--outside` starts at `(128.5, 66.5, Z1)`. Look north to find
the courtyard. Follow the north gate's road to the river or leave through the
east gate toward Thornwatch. Use M for the local map.

Short grass covers the outdoor ground, including the bridge approaches. Nearby
blades are 0.09-0.24 world units tall, with a continuous turf texture filling in
the distance. Faster wind waves and local gusts make patches sway together;
walking and sprinting push nearby blades aside. Trees have rounded, irregular
crowns, branching trunks, and circular trunk collision. River streaks follow the
bends and rotate with perspective as you turn; ripples and foam move downstream.
If you step into the water, you wade on a shallow bed,
move more slowly, and drift with the current. Jump to climb out onto the bank,
or use the bridge for a dry crossing. Pause and the help screen freeze the
environment's animation along with movement.

On Windows you can also double-click `run.bat`. Windows Terminal is recommended;
PowerShell and Command Prompt consoles also work. Use a monospace font and a
terminal around **120 columns by 40 rows**, or maximize it. The program fills
the terminal and adjusts when it is resized. It needs at least 60 columns by
20 terminal rows; smaller windows freeze play and show a resize notice.

## Controls

| Key | Action |
| --- | --- |
| W / S | Walk forward / backward |
| A / D | Strafe left / right |
| Hold Shift | Sprint |
| Space | Jump; you can land on low walls and crates |
| Mouse movement | Turn and look up / down on Windows |
| E | Open / close a door, or collect an item and drop your held item |
| Left click | Swing the sword or shoot a fireball with the held staff |
| F | Mute / unmute sound |
| M or Tab | Show / hide the overhead map |
| H | Open / close the control guide |
| P | Pause / resume |
| R | Return to the starting entrance with full health; preserve inventory and world state |
| Esc or Ctrl+C | Exit |

On Windows, **click inside the terminal to capture mouse look**. The capture
click does not attack. Turning continues beyond screen edges. P opens pause;
H opens controls. Resume with P. Native key-down/up events preserve
simultaneous WASD, Shift and jumping. Q is no longer an attack control.
Captured mouse motion and attack clicks are read independently. The native
helper hides the pointer during capture; P and H release it. The reported
center-cursor and pause-release bugs have a native desktop regression fix;
physical play review in a tabbed Windows Terminal remains pending.
`--keyboard-look` is available for play without mouse capture. Unavailable
native capture also shows that fallback command.

For keyboard controls, run `python main.py --keyboard-look`: arrows look and
**Enter** attacks. This mode is automatic on Linux/macOS, where mouse capture
is unavailable. POSIX key-repeat timing approximates held movement; uppercase
WASD supplies sprinting. Moving a captured game tab into a different terminal
window requires restarting the game or using keyboard mode.

The game uses the alternate terminal screen and restores console modes, cursor,
and colors when it exits. Focus loss pauses play on Windows; press P to resume.

## Options

```powershell
python main.py --demo                # Automatic walk; Esc still exits
python main.py --outside             # Southern meadow facing the castle
python main.py --region thornwatch   # Start at the ridge watchfort
python main.py --keyboard-look       # Arrows to look; Enter to attack
python main.py --fps 30              # Lower the frame-rate cap
python main.py --mute                # Start silently; F enables sound
python main.py --volume 0.35         # Master sound level, 0 to 1
python main.py --sound-preview effects.wav # Export the original effects
python main.py --audio-test          # Play river/effects and check playback health
python main.py --max-cells 4800      # Optional viewport budget to reduce CPU use
python main.py --color-mode color   # Dark-fantasy palette on black (default)
python main.py --color-mode gray    # Neutral grayscale foregrounds
python main.py --color-mode mono    # Uniform-white terminal fallback
python main.py --cell-aspect 0.5     # Font cell width divided by its height
python main.py --snapshot            # One plain-text frame; no terminal needed
python main.py --benchmark 120       # Time 120 frames without terminal output
python main.py --demo --frames 100   # A finite interactive smoke test
python main.py --frame-timing fullscreen-timing.json  # Save a live timing report on exit
python -m ascii3d                    # Alternate entry point
```

Interactive startup shows a MONOLITH title card, animated activity spinner,
progress bar and rotating gameplay tips. Wide terminals also show elapsed time.
The spinner and tips keep moving while a longer stage runs. The loading
percentage counts completed startup phases, rather than predicting remaining
time; it reaches 100% after the world, renderer, terminal and audio have been
initialized. Animation stops before gameplay and on interrupted/failed startup.
Snapshot, benchmark and redirected output omit the loading display and start no
animation worker.

The live viewport uses **every terminal column and row** by default and
traces one ray per scene cell. The HUD, prompts, map, labels and reticle are
drawn at the terminal's native character size. `--cell-aspect` adjusts
perspective for the font cell's width-to-height ratio.

Use `--max-cells 4800` to limit rendering work on a large terminal. An explicit
budget of at least 1,200 cells scales and centers the viewport while keeping
the 60x20 minimum playable size when the terminal allows it. Snapshot and
benchmark modes accept `--width` and `--height` and trace every scene cell at
the requested dimensions.

The live FPS counter refreshes every frame and reports completed game-loop
frames per elapsed second over a rolling window of roughly one second. It
includes input, simulation, rendering, terminal writes/flushes and frame-cap
waits. It is rounded to a whole number, starts at 0 before the first completed
frame, and averages brief fluctuations. The default cap is 40 FPS (`--fps`
changes it). Headless benchmark FPS excludes terminal output and cap waits.

For a fullscreen slowdown, run `run.bat --frame-timing fullscreen-timing.json`,
play in fullscreen, then exit with Esc. Use an unused filename. The report
records viewport and sample sizes, renderer selection, input, audio controls,
simulation, rendering, terminal encoding, writes and frame-cap waits. It
saves up to the last 3,600 completed frames after restoring the terminal.

## Sound

Original procedural sound now emphasizes dark-fantasy materials: heavy boot
contacts on stone, grass, wood, water, gravel and metal; cloth movement; grit,
scrapes and damped body resonances. Weathered doors strain and release around
wooden latches. Sword contacts have an immediate iron/wood impact, while the
staff exhales cold spellfire with turbulent tails and crumbling embers.
The Warden uses low, inharmonic stone weight for movement, warnings, impacts,
collapse and return. Player damage and respawn use their own cues. Interface
feedback is subdued parchment/leather movement. Gusting wind and flowing water
use textured turbulence. All sounds are synthesized locally, without recordings.

Footsteps and landings follow the actual supporting material, including stairs,
raised crates and bridge tops. Recurring contacts and relic effects have
repeatable variations. Effects overlap with distance attenuation and stereo
positioning. Confirmed sword hits lead with the impact and a softer whoosh;
misses keep the full air swing.
Pause/help hush the environment while preserving menu feedback. F toggles sound;
the header shows its state. Mute, pause, volume changes, and stopped voices fade
smoothly. Lost output devices retry automatically; F also requests a retry when
output is unavailable.

The river is a continuous, stereo rushing-water layer, including while standing
still and while crossing the bridge. Its level and stereo direction follow
actual water tiles, fading with distance. It is mixed separately from footsteps
and splashes.

Export a fresh effects/ambience WAV with `--sound-preview effects.wav`.
Live audio currently uses Windows' built-in
[waveOut API](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutopen)
through `ctypes`; there are no extra packages or downloaded sound assets. On
other platforms, or without an audio device, play continues silently and WAV
export still works. Snapshot and ordinary benchmark modes never start audio.

Sounds are synthesized and warmed up at startup. Native playback runs in a
separate process so rendering cannot hold its Python execution lock. At most
eight voices mix into three 1,024-frame stereo buffers (about 139 ms total),
primed before playback starts and refilled from device-completion events.
Immediate-return virtual sinks retain a safety rate cap. Effect ends and ambient
loop seams are smoothed, and overlapping peaks use a soft limiter.

To check reported crackling/cutouts, run `python main.py --audio-test`: its
18-second sequence plays meadow wind, the river, surface Foley, doors, both
weapons and Warden/player effects,
and reports empty-queue events, maximum refill
interval, and output recoveries. Zero empty-queue events verifies buffer
continuity during that run; it does not measure the speakers or headphones.
New gameplay features must include matching sound events; this is a standing
contributor requirement in `AGENTS.md`.

## Performance checks

Clear 2x2 terrain columns are merged into cached empty rectangles during voxel
edits. Rays skip these empty volumes while preserving exact hits; the larger
bounds accelerate open sightlines.
Conservative AIR volumes below roofs also skip empty room interiors, stopping
at floors, ceilings and walls. Corner crossings preserve ordinary voxel order.
Grass uses
spatial chunks, distance-based detail, cached wind, and a per-frame blade budget.
Far grass remains visible as animated turf. Tree detail also has a pixel budget.
Grass is generated in nearby 4x4 chunks with at most 128 retained chunks;
revisiting a patch regenerates the same blades. Terrain cache construction uses
bounded grid passes, and ray skips preserve exact voxel hits across floors and
ceilings. These limits keep scenery work bounded as the map expands.
The overhead map caches its static background until voxel edits or resizing.
River audio checks only nearby water buckets within its fixed 18-unit radius.

Use the same machine, Python version, resolution, and frame count to compare:

```powershell
python tools/benchmark.py --frames 60 --compare benchmarks/vegetation-current.json
python tools/benchmark.py --frames 60 --save benchmarks/my-run.json
python tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/castle-milestone-before-live.json
python tools/benchmark.py --frames 60 --audio --extra-scenes --terrain-scenes --save benchmarks/my-terrain-run.json
```

This checks six indoor/outdoor camera roles and reports mean and p95 frame
times, excluding terminal output. Comparison exits with an error if either frame
time grows more than 15% in any scene; `--max-regression` adjusts that threshold.
Timing varies with background load. Review unexpected results before replacing
a baseline. `vegetation-before.json` preserves the earlier renderer's timings;
`vegetation-current.json` records the optimized renderer on the development PC.
The `--audio` run includes live ambience/effect mixing and needs a Windows audio
device. `doors-audio-current.json` records that mode with the interactive doors;
new baselines must use the same audio mode. Door panels supply early ray limits,
so static geometry hidden behind a closed door is not traversed.
`--extra-scenes` keeps stable workload names for chapel, watchfort, east bridge,
watchstones, an active Warden, equipped sword
combat, the staff pickup, live fireballs, the map overlay, close trees, river
angles, castle exterior, great hall and roof views. Audio-enabled measurements
include actual listener-position river/wind sampling. Saved camera coordinates
and world dimensions identify each layout; old and new map views represent
similar scene types rather than identical geometry. New scenes without a
reference have no percentage comparison; existing comparisons retain the 15%
mean/p95 limit. Historical benchmarks remain on disk and are not replaced by
measurements of the rebuilt castle.
Audio-enabled runs also report playback health and fail on buffer underruns or
output errors. `audio-repair-measurement.json` records the latest repaired-audio
run; the historical frame-time check still flags slower scenes, so that report
has **not** replaced the approved reference.

`--terrain-scenes` adds highland terrain, the ravine, upper floors, rooftop
views, the highland map and actual terrace/stair walking with contact sounds.
`tools/benchmark_pair.py` compares a preserved
source tree against the current engine in per-frame ABBA order with the same
live mixer, records raw samples and source hashes, and keeps the 15% mean/p95
limit. Add `--before-elevated-audio` when the frozen control already supports
listener-height sampling (checkpoint `d2fa0a7` or later), so both variants use
the same ambience calculation. See `benchmarks/README.md` for retained
measurements and limits.

For CPU diagnosis with the paired benchmark's changing yaw, enemy simulation
and actual walking workloads:

```powershell
python -B tools/profile_workloads.py warden east_bridge stair_walk --audio --save benchmarks/my-unused-profile.txt
```

The profile and its `.sources.json` companion require unused paths. These
instrumented call counts include five warmup frames before profiling and help
locate expensive work; use the paired benchmark for performance acceptance.

## Renderer backends

The playable game supports `--renderer auto|cpu|native|gpu`. Auto prefers a
hardware GPU, then the optional compiled solid library, then the Python CPU
renderer. `--renderer cpu` selects the standard-library Python path.

The optional native library accelerates exact float64 voxel, solid and
continuous terrain traversal, as well as exact refinement of GPU candidates.
It also batches lighting for static opaque surfaces in scenes without local
firelight. Coincident solid hits use the Python grid query. Build or rebuild
the library from the repository root. The normal launcher picks up the result
automatically.

```bash
cc -std=c11 -O3 -ffp-contract=off -fexcess-precision=standard -fPIC -shared \
  ascii3d/solid_bvh.c -lm -o ascii3d/monolith_solid_bvh.so
```

From a Windows x64 Developer Command Prompt with MSVC installed:

```bat
cl /nologo /std:c11 /O2 /fp:strict /LD ascii3d\solid_bvh.c /link /OUT:ascii3d\monolith_solid_bvh.dll
run.bat --renderer native
```

From PowerShell with 64-bit MinGW GCC installed:

```powershell
gcc -std=c11 -O3 -ffp-contract=off -fexcess-precision=standard -shared ascii3d/solid_bvh.c -o ascii3d/monolith_solid_bvh.dll
.\run.bat
```

GPU geometry includes exact convex-plane candidates and indexed solid bounds,
with float64 refinement and uncertain-ray CPU fallback. It uses
the same production shading, doors, actors, vegetation and HUD. Ambiguous rays
retain the exact CPU path; missing/lost devices fall back without changing play.

GPU support requires **Python 3.11+** and optional `wgpu`, which supplies GPU
access unavailable in the standard library. The CPU game retains Python 3.10+
and needs no added dependencies. Install GPU support in an isolated environment:

```powershell
python -m venv .venv-gpu
.\.venv-gpu\Scripts\python.exe -m pip install -r requirements-gpu.txt
.\.venv-gpu\Scripts\python.exe -B main.py --renderer gpu
```

`run.bat` prefers this local environment when present. Full-detail frame
times vary by scene and terminal size. The latest matched Windows runs
and native console timings are in the [benchmark report](benchmarks/full-detail-windows-2026-11-21.md).

The separate `tools/gpu_prototype.py` remains a static-stage diagnostic with
simplified ASCII shading. It excludes doors, actors, vegetation and HUD; its
stage timings do not replace full-game benchmarks. Reports include dispatch and
readback, hardware identity, CPU finishing, raw samples and accuracy checks.

```powershell
.\.venv-gpu\Scripts\python.exe -B tools/gpu_prototype.py --scenes warden --snapshot
$env:MONOLITH_GPU_TESTS='1'
.\.venv-gpu\Scripts\python.exe -B -m unittest discover -s tests -p 'test_gpu*.py' -v
```

## Check the engine

```powershell
python -m unittest discover -s tests -v
```

On Windows, run input tests in a native console. To include the real desktop
cursor regression, set `$env:MONOLITH_DESKTOP_TESTS='1'` before the test command;
it briefly captures and restores the pointer three times. It needs an unlocked
desktop with native cursor access. In a restricted workspace, set
`$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path` so the WAV-export test uses writable
temporary storage.

Edit `ascii3d/world.py` and `ascii3d/map_expansion.py` to build a different
environment. `ascii3d/terrain.py` configures highlands, roads and shared
multilevel landmarks. `World.box()` fills a
rectangular volume; filling it with `AIR` cuts out doors or windows. X and Y are
the ground plane; Z is height. The castle ground and river bridge decks are at Z = 1;
the river surface is at Z = 0.68 and its shallow bed at Z = 0.12. `scenery.py`
controls height-aware grass placement and wind; `trees.py` renders the rounded tree
crowns. Use `World.box()` to edit voxels so cached empty-space bounds invalidate.
Use `World.add_stair_flight()` for walkable stairs. Its shared treads carry a
stair marker; ordinary voxel boxes and unmarked `SolidBox` props stay obstacles.

# MONOLITH

A first-person 3D playground drawn entirely with **white ASCII text on black**.
Explore a **castle surrounded by meadow** in a 112 by 112 world. Four towers and
battlements frame an open courtyard, a roofed gatehouse, a great hall, a west
cloister and a garden. Jump up the west steps to reach the cloister roof and
nearby wall walk. Gravel trails circle the castle and lead to two bridges over
the northern river, ruined chapel, watchstones and an eastern lodge.

Seven wooden doors share **E** interaction, swinging animation and collision.
Approach and look at a doorway to see its prompt. Doors stop or reopen if a leaf
would hit you; step clear of the swing before closing.

Collect the upright **iron sword with E** near either starting entrance. Find
the **fire staff** on the western timber floor inside the northern ruins
(`53.5, 103.5`). Cross either river bridge, follow the north-bank trail toward
the chapel and enter its south doors, then head left. **You can hold only one item**: collecting another drops your
current item nearby, where you can collect it again. The E prompt shows which
item will be dropped.

Press **left click** to swing the sword or shoot a fireball with the staff. Aim
at the three passive dummies in the western training yard (`42.5-50.5, 48.5`)
to see each target's name and health.
Sword strikes need about 2.5 units of reach. Fireballs follow your aim, travel
up to 28 units, and stop on walls, doors, tree trunks or the first target hit.
The staff fires once per click with a 0.65-second cooldown and no ammo limit.
Either weapon deals one damage; three hits knock the dummy down, and it resets
after four seconds. The fixed support remains solid while it is down. R returns
you to the entrance with your held item and world state preserved.

A **Watchstone Warden** guards the western watchstones (`12-24, 99-106`),
across the river from the castle. This four-HP stone guardian notices players
inside its grounds within 7.5 units, follows them, and raises its fists before
slamming the ground at close range. Step away during its warning to dodge. It stays inside
the watchstones and returns home when you leave. Defeat it with either weapon;
it respawns at its original position after 12 seconds, waiting longer if the
spot is occupied. The three training dummies remain passive.

The upper HUD shows your **10-point health bar**. A Warden hit costs two health.
Defeat returns you to your starting entrance with full health, keeping your
held item and world state. R also restores health when returning to the entrance.

The renderer casts a real 3D ray through a voxel world for every character. The
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

The indoor start is the south gatehouse (`55.5, 30.5`); the outdoor start is
`55.5, 20.5`. The courtyard connects to meadow gates on all four sides. Continue
north through the great hall and north gate, then follow the trail west or east
to a bridge. The lodge lies east of the castle. Press M to see the whole map.

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
terminal around **120 columns by 40 rows**, or maximize it. The program adjusts
when the terminal is resized. It needs at least 60 columns by 21 terminal rows.

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
Captured mouse motion and attack clicks are read independently. **Known Windows
Terminal bugs:** user playtesting reports a visible cursor at the center and
pausing does not free it. Both fixes are pending; `--keyboard-look` is available
for play without mouse capture. Unavailable native capture also shows that
fallback command.

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
python main.py --keyboard-look       # Arrows to look; Enter to attack
python main.py --fps 30              # Lower the frame-rate cap
python main.py --mute                # Start silently; F enables sound
python main.py --volume 0.35         # Master sound level, 0 to 1
python main.py --sound-preview effects.wav # Export the original effects
python main.py --audio-test          # Play river/effects and check playback health
python main.py --max-cells 7200      # Allow a larger live viewport; uses more CPU
python main.py --cell-aspect 0.5     # Font cell width divided by its height
python main.py --snapshot            # One plain-text frame; no terminal needed
python main.py --benchmark 120       # Time 120 frames without terminal output
python main.py --demo --frames 100   # A finite interactive smoke test
python -m ascii3d                    # Alternate entry point
```

The live viewport defaults to a **4,800-character budget** (120x40). Large
terminals center the viewport without stretching characters or increasing the
work per frame indefinitely. `--max-cells` changes that budget, subject to the
180-column / 64-row ceiling. Snapshot and benchmark modes accept `--width` and
`--height` and do not use the live viewport budget.

The live FPS counter refreshes every frame and reports completed game-loop
frames per elapsed second over a rolling window of roughly one second. It
includes input, simulation, rendering, terminal writes/flushes and frame-cap
waits. It is rounded to a whole number, starts at 0 before the first completed
frame, and averages brief fluctuations. The default cap is 40 FPS (`--fps`
changes it). Headless benchmark FPS excludes terminal output and cap waits.

## Sound

Original fantasy-style Foley adds uneven wooden door creaks and quiet latches,
distinct stone, grass, wood, water, gravel and metal footsteps and landings,
cloth-like jumps,
splashes, weapon pickup tones, dropped-item thuds, blade whooshes,
fireball ignition/rush, impacts and fading embers, sharp sword impacts on enemies, dummy
feedback and quiet interface
cues. Meadow wind includes gentle gusts and grass rustle. The Warden has stone
footsteps, an alert, an attack warning, hit/defeat and respawn feedback; player
damage and entrance respawn have their own cues. Footsteps and landings use the supporting surface, including raised crate
and bridge tops. Wind and river ambience change as you explore. Effects
overlap, with distance attenuation and stereo positioning for nearby doors.
Door opening, closing and obstruction cues each have three variations.
Successful sword strikes play a distinct impact at the enemy and a softer
whoosh; misses keep the full air-swing sound.
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
These limits keep scenery work bounded as the map expands.
The overhead map caches its static background until voxel edits or resizing.
River audio checks only nearby water buckets within its fixed 18-unit radius.

Use the same machine, Python version, resolution, and frame count to compare:

```powershell
python tools/benchmark.py --frames 60 --compare benchmarks/vegetation-current.json
python tools/benchmark.py --frames 60 --save benchmarks/my-run.json
python tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/castle-milestone-before-live.json
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
`--extra-scenes` adds ruins, lodge, east bridge, watchstones, an active Warden, equipped sword
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

## Check the engine

```powershell
python -m unittest discover -s tests -v
```

Edit `ascii3d/world.py` and `ascii3d/map_expansion.py` to build a different
environment. `World.box()` fills a
rectangular volume; filling it with `AIR` cuts out doors or windows. X and Y are
the ground plane; Z is height. Normal ground and the bridge deck are at Z = 1;
the river surface is at Z = 0.68 and its shallow bed at Z = 0.12. `scenery.py`
controls the grass placement and wind field; `trees.py` renders the rounded tree
crowns. Use `World.box()` to edit voxels so cached empty-space bounds invalidate.

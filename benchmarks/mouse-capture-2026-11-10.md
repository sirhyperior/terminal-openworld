# Native mouse repair evidence — 2026-11-10

Starting checkpoint: `45062ddf039cb01bfaf7ca858798b3625b5ac126`.
Windows / Python 3.14.4 / Intel64 Family 6 Model 154 Stepping 3, GenuineIntel.
The reported visible center pointer and failed pause release were investigated
together. These are native API measurements, not physical user acceptance in a
tabbed Windows Terminal.

## Reproduced failure

A desktop-access probe called `ClipCursor`, then read `GetClipCursor` and
`GetCursorPos` in the same process. The original desktop clip was
`(0, 0, 1707, 960)`. The following sequence was retained from the probe:

| Requested clip | BOOL result | Actual clip | Cursor | Error |
| --- | --- | --- | --- | --- |
| `(500,500,501,501)` | 1 | `(500,500,501,501)` | `(500,500)` | 0 |
| original | 1 | original | `(500,500)` | 0 |
| `(501,501,502,502)` | 1 | `(501,501,502,502)` | `(501,501)` | 0 |
| original | 1 | original | `(501,501)` | 0 |
| `(500,500,500,500)` | 1 | `(500,500,500,500)` | `(499,499)` | 0 |
| original | 0 | `(500,500,500,500)` | `(499,499)` | 5 |

A final restoration attempt in that process also returned 0/error 5. A fresh
process released confinement successfully. An independent three-second watchdog
was used for the confirming probe. An earlier short probe produced the same
empty-rectangle/release failure and required fresh-process release.

The game's helper previously occupied `[500,501)` in each axis while its empty
clip could put the cursor at `(499,499)`. That places the pointer over the host,
where the helper's private transparent cursor cannot reliably apply. The failed
release also explains why correct P dispatch could leave the pointer confined.
The exact Windows-internal reason for denying subsequent calls is unverified;
the observed empty-rectangle behavior is sufficient to avoid that state.

[Microsoft's ClipCursor reference](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-clipcursor)
documents the shared confinement resource and restoration requirement. It does
not document the empty-rectangle behavior measured here.

## Repair and native measurements

`NativeMouseCapture` now uses a positive-area 1x1 clip inside a 3x3 helper. It
retains the helper center independently of clip readback for z-order recovery.
`WindowsMouse.release()` uses the latest native clip, runs cleanup even when
helper teardown raises, and retries a failed restoration once per call. Pending
restoration blocks recapture; a foreign clip change cancels our ownership.

Three successive native capture/release cycles produced clip
`(853,456,854,457)`. `WindowFromPoint` identified the helper at the actual pointer.
`GetCursorInfo` selected its private transparent cursor after the queued cursor
transition (within the next 25 ms sample in the standalone probe). Each release
restored `(0,0,1707,960)` with BOOL 1/error 0. Foreground ownership stayed with
the existing host. No system cursor replacements or foreign input-queue
attachments were used.

The durable opt-in desktop regression repeats capture/release three times and
checks actual cursor handles, hit testing, foreground identity and original clip
and position restoration. Its host fixture is the current foreground window;
it does not inject terminal input or establish physical Windows Terminal play
acceptance. An independent emergency cleanup checks Win32 success if an
empty-rectangle regression prevents restoration in the test process.

## Validation

- Native-console full suite with desktop access: **274 tests passed, zero skips**
  in 34.378 seconds. This includes P console records and actual app pause/help
  dispatch, with existing sound-event coverage.
- After review corrected a normalized-clip/z-order edge case and strengthened
  emergency test cleanup, **18 mouse-capture tests passed, zero skips**.
- `python -B main.py --snapshot`: passed.
- `python -B main.py --demo --frames 100`: exited 0 in a native console with
  live sound; alternate-screen, cursor and console cleanup sequences completed.
- Initial piped suite: 267 tests, one WAV-export permission error and nine
  console skips. Workspace-local TMP/TEMP fixed the environment limitation.
  A sandboxed native-console attempt also denied `WriteConsoleInputW`; the
  successful full run used desktop access.

```powershell
$env:TMP=$PWD.Path; $env:TEMP=$PWD.Path
$env:MONOLITH_DESKTOP_TESTS='1'
python -B -m unittest discover -s tests -v
```

Final production-file SHA-256 values at review (line endings are significant):

- `ascii3d/mouse_capture.py`: `6E63B9A9B8A1E91C45684AB25598510EB5DFC24EB72CF8CA3561E376B45FF3D1`
- `ascii3d/terminal.py`: `7BC9239A4F856A1696B296D22B1162945B3C2F95ECD6EB7C31664978B32B952D`

## Live-audio benchmark: retained failure

```powershell
python -B tools/benchmark.py --frames 60 --audio --extra-scenes --compare benchmarks/mouse-input-audio.json --save benchmarks/mouse-release-audio.json
```

24 scenes / 120x40 / 60 measured frames / Python 3.14.4 / same reported CPU and
live world Soundscape as the historical reference. This run exited **1** because
all 24 mean/p95 scene comparisons exceeded the unchanged 15% limit.

| Scene | Mean ms | p95 ms | Mean change | p95 change |
| --- | ---: | ---: | ---: | ---: |
| gatehouse (`indoors`) | 35.255 | 42.040 | +25.3% | +34.1% |
| river | 31.498 | 38.869 | +55.1% | +56.0% |
| training | 33.361 | 40.078 | +74.6% | +66.7% |
| great hall | 43.106 | 59.230 | +105.4% | +143.6% |

Audio: 994 buffers, **0 underruns, 0 recoveries**, maximum refill interval
78.18 ms, no reported device error. The failed report is retained as
`mouse-release-audio.json`; no baseline was replaced. These input repairs are
outside the benchmark's imports/timed execution. Render/simulation/audio sources
are unchanged. This historical comparison does not establish the cause of the
timing drift or satisfy the open castle-wide performance acceptance. It excludes
desktop input handling, terminal output and frame-cap waits.

Read-only performance review identified full tree scans in sight/projectile
queries and full-viewport door scans for near-plane faces as profiling candidates.
Their contribution is unmeasured; no speculative renderer change was made.

# Richer startup display — 2026-11-13

The loading-screen backlog item was selected after checking available account
usage. Color stays deferred; the existing movement repair is preserved.

## Behavior and lifecycle

- Plain white ASCII title card and a dark-fantasy welcome line.
- A completed-phase progress bar, activity spinner and rotating accurate gameplay
  tips. Wide windows show elapsed seconds. Activity does not advance percentages;
  only the existing six completed startup phases do. Ready reaches 100 once.
- One standard-library worker waits on an Event at 0.15-second intervals (at most
  about 6.7 repaints/second). Tips rotate every three seconds. No input, geometry,
  synthesis or device operations run in that worker.
- Loading and terminal entry share an output barrier. ExitStack registers loader
  cleanup before attempting audio entry, ensuring a startup failure stops/joins
  animation before terminal restoration. Completion and interruption also join
  before gameplay. No loading work continues in the frame loop.
- Snapshot, benchmark and redirected output stay silent and create no worker.
  No dependency, color mode, game action or sound cue is added. Existing mute,
  volume, input and environmental audio behavior is unchanged.

## Validation

- Initial focused loading suite: **14 tests pass**, including Event-signaled
  animation with a controlled clock, unchanged zero percent while tips/spinner
  change, completed stages, narrow/zero-width output, headless worker exclusion,
  idempotent shutdown, failed-flush cleanup, world interruption and audio-entry
  failure ordering.
- Independent read-only review found no blocking deadlock or lifecycle issue in
  startup, output serialization, Event shutdown/join, headless behavior or audio
  failure cleanup.
- Initial layout inspection found that the minimum viewport omitted the bar and
  80-column windows could omit tips during a long stage. The final responsive
  layout keeps complete bars at 60/80/100/120/160 columns, chooses complete
  compact tips where necessary, and preserves the final autowrap column.
  The main-screen loading line is erased under the output barrier before the
  alternate-screen switch, so it cannot reappear as a stale 66% line on exit.
- `loading-native-tests-2026-11-13.txt` / `.json`: **435 native-console tests
  passed**, zero failures/errors, one sandbox cursor skip. Real GPU/input checks
  ran, engine hashes stayed unchanged, runner exit 0. This run covers the initial
  presentation before compact-layout and main-screen-line cleanup.
- `loading-final-focused-2026-11-13.txt`: **38 final loading/game-loop checks
  pass**, including the responsive layout, terminal/audio entry failures,
  interruption, cleanup, headless output and existing gameplay-loop behavior.
- `loading-native-demo-2026-11-13.json`: actual **120x30 native GPU app**,
  **30 demo frames**, exit 0, sound available. Transcript has 58 title/progress
  writes over about eight seconds and uses exactly the completed-stage values
  0/16/33/50/66/83/100, with 100 appearing once. Spinner activity and three tips
  are observed. Every game frame and shutdown report **zero loading workers**.
  Audio: zero underruns/recoveries, 59.10 ms maximum refill interval. Final engine
  hashes stay unchanged. This is a startup/lifecycle smoke, not a frame-time
  acceptance comparison or physical speaker/visible-terminal review.

This feature improves feedback during waiting; it does not claim to
reduce world construction time or establish a new gameplay performance baseline.

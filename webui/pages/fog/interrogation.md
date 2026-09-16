# Frontend-design fog — Analyse › Interrogation

Places where a frame assumes something the core or the data cannot provide, or where the spec is
ambiguous. Each bullet: question · why it matters · source.

- **The frames' timescale cannot exist at 1 Hz.** Frames 2 / 2b / 2c draw falls of 0.7–1.1 s, a "steepest
  window 3 samples", anatomy axes of −1 s … +2 s and slopes near −0.7 mV/s. §0 makes F-03 ~21 s long on
  1 Hz recordings, so a 1 s fall is one sample. · Every number on the interrogation pages is downstream of
  this. · frames 2/2b/2c vs spec §0. **Resolved** by the inventory's mechanical rule — frame times ×10,
  frame slopes ÷10 — so angles, depths and shapes stay as drawn and only the time/slope tick labels move.
  Needs confirming against a real F-03 measurement before the numbers are believed.

- **Is the steepest window in samples or seconds?** The frames say "3 samples", but the four recordings run
  at 1, 2 and 10 Hz, so "3 samples" is 3 s, 1.5 s or 0.3 s depending on the member. · A family that spans
  recordings would then be measured with three different windows. · frame 2 Rules, §0 recordings table.
  Built as samples, as drawn; a per-recording note is not shown.

- **Frame 1b names families the canon does not have.** It lists `F-11 biphasic` (9 members) and
  `F-12 burst` (31); §0 has `F-04 spike train` and `F-11 burst`, and no F-12. · The picker is the entry
  point to every other family. · frame 1b vs §0. Built with the canon's ids (F-01, F-03, F-04, F-07, F-11).

- **F-07 "5 recordings" vs 4 usable ones.** Frame 1b gives F-07 five recordings; §0 has five recordings
  total, one of which (`M4_aug`) is held out (D6) and refused everywhere. · Either F-07 draws on the held-out
  recording — which the lock forbids — or the count is wrong. · frame 1b, §0, P19/D6. Built as 4.

- **The frame draws the `seed` verdict blue.** §3 reserves blue for machine origin / selection and green for
  human annotation origin; `canon.VERDICTS` gives seed green. · A blue dot on a member tile reads as
  "machine picked this". · frame 1 legend vs §3. Built with two greens (seed darker), amber, red.

- **Frame 3 colours the max-slope histogram red.** §3 reserves red for artifact / excluded / destructive. ·
  A red distribution reads as "these events are artifacts". · frame 3 vs §3. Built with a neutral
  categorical feature palette (blue / purple / teal).

- **Inter-event interval n.** Frame 3 shows `n 15` for 16 events, i.e. one global sequence — but the 16
  events sit in 3 recordings across 4 channels, so an "interval" between the last M2_aug event and the first
  M3_jul event is not an interval. · The CV and its null are the headline result of that card. · frame 3.
  Built per recording × channel (n 12 for F-03), with an InfoTip saying so. Confirm which the thesis wants.

- **Where do the exponent CIs come from?** Frame 3 shows β with a 95 % CI and a *null* β with a CI, but not
  whether the CI is OLS-analytic, bootstrapped over members, or bootstrapped over the 200 null draws. ·
  With n = 16 the three differ a lot, and P10 makes the CI the load-bearing number. · frame 3, P10.
  Fixture values only.

- **Does the null re-run per view change?** Parameters says "views only · nothing here is stored", but
  switching `interval defined as` or `outliers` changes what the null must be matched to. · A cached null
  matched to a different definition would silently mis-state p. · frame 3 Parameters, P10.

- **Frame 2b's table window.** The frame's per-event table reads `41–44 of 212` while the strip shows
  `41–50` and the current event is 45 — the table page cannot start at 41 and hold the current event with a
  page size of 4. (`UI_SWEEP_2026-09-14.md` already lists the per-frame arithmetic defects.) · Built as a
  4-row page computed from the selection, so the label is honest.

- **Block index base.** The live detection chain uses 0-based `analyse/block/<i>` (`block/0` = "01
  Baseline"); the interrogation chain uses 1-based `analyse/interrogation/block/<n>` (`block/1` = "01
  Resolve spans"), which the inventory chose so the route matches the printed stage number. · Two bases in
  one workspace is a trap for deep links written by hand. · inventory "Moving between chains".

- **`+ stage` on an interrogation chain.** The ribbon offers it (frame 1), but §6.4's type-contract modal is
  not specified for a chain whose terminal is Features: inserting a second feature block would emit two
  Feature sets into one Aggregate. · P7 says one block per analysis type; the frames never show two. ·
  frame 1 ribbon, §6.4, P7. Built as a *swap* (pick slope or spike shape), with FitzHugh–Nagumo disabled.

- **Who owns "Analyse events" arriving here?** The toolbar reads "arrived via Analyse events", but the live
  chain page's button is disabled ("out of slice scope") and is owned by the chain inventory. · Until it is
  enabled, the only way onto this page is the URL or the nav. · inventory §2, frame 1.

- **`Stage 1 outlier for Review`** writes a queue through `recordDemoWrite('review','add-queue',…)`, but the
  spec does not say what a one-span interrogation queue is: Review works in named queues with one source
  each (P20), and an outlier from an interrogation is a fourth source kind. · §10.1, P20, frame 3.

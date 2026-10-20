# night-disc — report (branch `night/disc`, cut from main f1f1109)

## In plain words

- **The runs list** now matches your drawing. Each run is a box with three columns. On the left: the run's icon, its kind
  (seed / template / reference / draft), and the channel cells with "3 of 5 ch" in normal black text. In the middle:
  the name, the plain facts (how many found, on how many channels, when it finished), and any extra buttons. On the
  right: the × in the corner, the A/B box under it, and the Report button as a file icon under that. Text wraps instead
  of being cut off, so every box shows all of itself at the narrow column and at a 1024 px window.
- **"49 matches, not 155"** was not a different null or a different cut. It was a different search. Picture two folders
  on a desk, one per recording, each holding its own list of channels and hours. Switching the Scope card to M2_aug opened
  M2_aug's folder ("demo · talk") and then wrote "the first 3 channels, 0–174 h" over the list inside it. The next seed
  search ran on that smaller scope: 3 channels × 174 h instead of 5 channels × 721 h. Fewer channels and fewer hours give
  fewer matches, so it found 49. It is fixed: switching recording now opens that recording's folder exactly as you left
  it. (The Demo instance session has already restored "demo · talk" in the real database.)
- **The seed cards** are no longer cut off. The histogram's "count" label has room. The "… kept · the null gives …"
  label stays inside the plot. The *Keep the matches* text and buttons sit inside the card's border instead of against it.
- **The map's level 3** has a thin scrollbar above the dataset names. It moves with the table's own scrollbar, and the
  algorithm names stay pinned on the left.

## Assumed

- **Unit name.** The smoke unit is `zzzzzzzzzzz_night_disc.json`, the gate unit the brief names. The brief also asks for
  it to sort before `zzzzzzzzzzz_a2_p4_seed.json`, but no name starting `zzzzzzzzzzz_n…` can. Every state in it is
  read-only (no preview, keep or recording switch), so its position does not matter.
- **The × is always shown** (muted). It used to appear only on hover. The researcher asked for it "in the utmost right
  corner" and for every box to be "clearly fully visible".
- **The facts line is shown in full and wraps.** It keeps the existing qualifiers ("null from the preview", "computed on
  the cluster", "stale") rather than trimming them to found · ch · done. One smoke state reads "null from the preview".
- **Report needs a name for screen readers.** The icon's title and aria-label are both "Report", as the drawing asks.
- **A held-out recording** is never written to the bridge: the card refuses it from the client's copy. So a switch to it
  still shows the old client-side defaults (the first three channels, 0–174 h) and marks the runs stale, as before.
  Every other switch sends the recording alone and no longer marks the opened session's runs "stale", because those
  runs are that session's own.
- **The draft row's right column is empty.** A draft has no ×, no A/B box and no report yet.

## Item 1 — the runs list as drawn

**Found.** Main's run row was five grid lines: the name beside the glyph, then the kind, the status, the coverage and an
actions line with Report on it. The drawing asks for three columns.

**Changed.** `chrome.tsx` (`RunRow`, `BandSetRow`, `CoverageStrip`), `SeedPage.tsx` (`DraftRow`), `discovery.css` (the
run-row block replaced; `.dsc-cov-n`; the draft name now wraps to two lines like a run's).
- Left (64 px): the glyph (it opens the run too), the kind badge (9.5 px to fit), the coverage cells, and "n of m ch" in
  `var(--text)`.
- Middle: the name, clamped to two lines with the full name on hover. Under it, the detail and the status line, both
  wrapping. Under those, *Run on the missing N*, *Import results*, *Retry* and *Open in Jobs* as small buttons that wrap
  their own text.
- Right (24 px): the ×, then the A/B box, then `IconButton icon="file" label="Report"`.
- The band-set row and the Seed page's draft row (with its rename pencil) use the same three columns.

All test ids are kept: `run-row-*`, `report-*`, `pick-*`, `remove-*`, `run-missing-*`, `coverage-*`, `draft-name`.

**Tests.** `tests/test_night_disc.py` (conda): the three columns and their contents in order, the Report icon, the body-
coloured count, the band-set and draft rows, and the CSS (three-column grid, facts that wrap).
`tests/test_site_runs_scope_link.py`: two item-1 checks from this afternoon encoded the five-line row (Report on the
actions line, the actions line spanning the grid). They are updated to the three columns. This is a deliberate change.

## Item 2 — the seed cards

**Found.**
- *Choose the cut*: the y-axis label "count" is drawn right-aligned at `padL - 6` = 28 px. In the 10 px mono font it is
  about 31 px wide, so it began off the card's left edge.
- The cut label was clamped at `W - 150`, so a 40-character "155 kept · the null gives 0.4 per draw" ran off the right
  edge.
- *Keep the matches*: the card has no padding of its own (only its head pads itself). The lede, both ways and *Save as
  template* sat against the border.

**Changed.**
- `padL` 34 → 44.
- A new `cutLabelX` places the cut label right of the handle when it fits, otherwise left of it (anchored at its end),
  and never past either edge.
- `.dsc-keep` children take a 14 px inline margin and the card has a 14 px bottom padding. In each way, the button stays
  its own width and the line beside it wraps.

**Tests.** `tests/test_night_disc.py`: `padL >= 42` and `cutLabelX` used in the histogram; the keep card's inner margin.
The real check is the two measured smoke states below.

## Item 3 — "49 matches, not 155"

**Found.** I read the main-checkout sandbox copy (`webui/runtime/20261020-225544`, way 2) and its jobs table:
- The kept run **seed 056a5d** (session 9, "demo · talk") was made at 14:29 on CH3_A2, CH4_A2, CH6_B1, CH7_B2, CH8_B2 ×
  0–721 h. Its settings: seed `library:2:1592512:1592876` (F-30's medoid), k 200, exclusion 0.5, no scale bank, the
  preview's 5-draw null, α 0.01 with no correction. The cut was 2.463 and it kept 155.
- Session 9's saved scope had been rewritten to **CH1_A1, CH2_A1, CH3_A2 × 0–174 h** (updated 22:37 local).
- Job 723 at 22:36 is a fresh preview of the same seed on that scope: 600 matches and a 6-draw null. Its recommended cut
  keeps **49**.

So the query on screen was not the kept run's query. The cause is in `chrome.tsx`'s `changeRecording`, which called
`setScope({ recording, channels: first three, section: [0, min(hours, 174)] })`. `PUT /api/discovery/session` then
opens the TARGET recording's existing session (`_open_session_on`) and writes the body's channels and section over it.
Any switch to M2_aug from another recording therefore clobbered "demo · talk". It was not the null, Settings › Nulls,
or a different draft.

**Changed (client only, no bridge change).**
- `api/discovery.ts` gains `putRecording(recording)`, which sends `{ recording }` alone (append-only).
- `session.ts` `setScope` sends a bare recording change through it.
- `changeRecording` sends `{ recording: key }`.
- The bridge already keeps a session's `channels_json` and span when the body carries neither. It builds a new session
  with its own defaults when the recording has none.
- The confirm now reads "Each recording keeps its own session. Changing the recording opens that recording's session as
  it was left …". The toast says the session was opened as it was left.
- The Cross-channel deep link (`putScopeLink`, `?channels=`) still writes its channels on purpose.

**The exact clicks that give 155** (for the Demo instance click script; "demo · talk" restored):
1. Library › Atlas › group *by shape distance* (g-05) › family **F-30** › *Seed search in Discovery*.
2. Discovery opens on M2_aug, session "demo · talk". The scope chip reads CH3_A2, CH4_A2, CH6_B1, CH7_B2, CH8_B2 ·
   0–721 h. The draft is seed 056a5d.
3. Step 3, *Choose the cut*: 1000 matches, a 5-draw null per channel, the green recommended cut **d ≤ 2.463**, **155
   kept**. Step 4 shows **seed 056a5d** kept, with the preview's null.

**The preview has to be re-run once before the talk.** A session holds ONE stored preview, and the 22:36 preview on the
clobbered scope replaced F-30's. On a sandbox copy taken at 23:24, after the scope was restored, F-30 opened on step 2,
*Not previewed yet*. Pressing *Run preview* there took 83 s on this loaded machine (the page estimated 34 s) and gave
`recommended 2.463 · 155 kept · the null gives 0 per draw` again. The preview's null is deterministic, so the figure
reproduces exactly. The manager was told at 23:27.

**To reproduce 49 on main before this fix** (sandbox only):
1. With Discovery on any other recording, choose M2_aug in the Scope card and press *Change*.
2. The scope becomes CH1_A1, CH2_A1, CH3_A2 × 0–174 h.
3. *Seed search* › the F-30 seed › *Run preview*. The result is 600 matches, a 6-draw null, and 49 kept at the
   recommended cut.

With this branch, step 2 opens "demo · talk" with its 5 channels × 721 h untouched.

**Tests.**
- `tests/test_night_disc.py` (conda), red first: `changeRecording` writes `{ recording: key }` (only the held-out branch
  writes defaults), `putRecording` sends `{ recording }`, and the confirm no longer says "clears".
- `tests/test_webui_night_disc_recording_switch.py` (webui/.venv): a bare switch A → B → A returns A's session with its
  5 channels and its 0–700 h section; a bare switch to a recording with no session builds one with its own defaults.
  This pins the bridge behaviour the fix relies on, and it passes on main.

## Item 4 — the map's top scrollbar

**Changed.** `MapPage.tsx` gains `TopScrollbar`, rendered above level 3's `map-wrap`. It is a 12 px `overflow-x: auto`
strip whose inner width is `scrollWidth - clientWidth + its own clientWidth`, so the two have the same scroll range (the
table's vertical scrollbar narrows its client width). Scroll listeners sync it both ways, with a 1 px dead band so they
never ping-pong. A ResizeObserver on the wrap and the table keeps it in step when datasets or rows are hidden. It keeps
its height but is hidden when the table fits, so nothing jumps.

The row labels' `position: sticky; left: 0` is unchanged. At level 2 the same rule holds (no top bar was asked for
there). Level 1 is a timeline that fits the card's width and never scrolls sideways.

**Tests.** `tests/test_night_disc.py`: the bar comes before the table at level 3 and uses scrollLeft, scroll listeners
and a ResizeObserver. The measured smoke state is below.

## Smoke states

New unit `webui/smoke_pages/zzzzzzzzzzz_night_disc.json` (all read-only):
1. `night-disc-run-rows-three-columns-at-1024`: Runs with the page narrowed to 960 px. Every run box has `.dsc-run-left`,
   `-mid` and `-right`. No part (glyph, kind tag, coverage, name, facts, action buttons, ×, A/B, Report) overlaps another
   or leaves its box. The columns do not overlap, and every name is at least 60 px wide. Report is the bare icon titled
   "Report". The ch count is not the facts' grey. Passes as `runs-list[data-night-geometry="ok"]` (the detail is in
   `data-night-geometry-detail`). No Report remains on an actions line.
2. `night-disc-run-rows-three-columns-at-full-width`: the same measure at the full width (the 296 px column). A finished
   template run's Report is in `.dsc-run-right` with `aria-label="Report"`.
3. `night-disc-seed-cut-card-not-clipped`: on `discovery/seed?step=3`, every histogram text lies inside the plot and the
   card. It records `no-preview` when the session holds none; it never runs one.
4. `night-disc-seed-keep-card-not-squished`: on `discovery/seed?step=4`, the lede, the ways and Save sit at least 8 px
   inside the border. No button overlaps its line, and no button label is squeezed.
5. `night-disc-map-top-scrollbar`: Map level 3. The bar sits above the dataset names. Scrolling the bar moves the table,
   scrolling the table moves the bar, and the row labels stay at the left edge (`map-wrap[data-night-top="ok"]`).

Edited in place, `webui/smoke_pages/zzzzzzzzzzz_site_runs.json`:
- `site-runs-run-row-actions-on-their-own-line` now expects a done run's Report under `.dsc-run-right`, not
  `.dsc-run-actions`.
- `site-runs-run-row-geometry-at-1024`'s eval also measures `.dsc-run-report` and the left column's kind badge. Its
  `no_overlap` pairs are unchanged and still hold, because the Report icon is in another column from the coverage and
  the name.

`webui/smoke.py` is not edited: nothing in it reads a moved test id. `discovery.json`'s `remove-and-pick-apart` still
measures × against A/B, now stacked in the right column.

## Gates

All gates were run after the manager's RESUME (23:20), from the worktree.

**Type-check and build.** `tsc -b` passes, and `vite build` passes.

**Tests.**
- The red commit `bd1d680` was exported with `git archive` into the scratchpad (no branch switch) and run there against
  its own base source. 14 tests failed: all 12 in `test_night_disc.py`, plus two in `test_site_runs_scope_link.py`.
  - `test_a_run_row_puts_its_actions_on_their_own_line` failed as intended.
  - `test_f3_…` failed only because the export left out `webui/smoke.py`.
- Green: `tests/test_night_disc.py`, `tests/test_site_runs_scope_link.py` and `tests/test_import_boundaries.py` give 43
  passed (conda). `tests/test_webui_night_disc_recording_switch.py` gives 2 passed (webui/.venv).

**In the browser** (main-checkout sandbox on 8768, main's server with this client; runtime folders
`C:\Users\mmebr\Documents\CNN\webui\runtime\20261020-225544`, stopped at the 22:58 pause, and
`C:\Users\mmebr\Documents\CNN\webui\runtime\20261020-232414`, stopped at 23:35):
- **Item 3.** Switching M2_aug → CO_fs2 → M2_aug through the Scope card left "demo · talk" at CH3_A2..CH8_B2 × 0–721 h
  (read back from `/api/discovery/session`). CO_fs2's session opened with its own 4 channels × 0–480 h. No console
  errors.
- **Item 1.** Measured with this unit's geometry eval: ok at 1376 and 1024 px on "demo · talk" (7 rows) and on
  CO_fs2_rq4 (47 rows, 4 with *Run on the missing N*). Screenshots are in `webui/runtime/site/` (gitignored).
- **Item 2.** After running F-30's preview: the cut card and the keep card were ok at 1376 and 1024 px.
- **Item 4.** The map's top bar is synced both ways. The table overflows, and the labels stay pinned.

**Smoke** (`--pages-only --only <unit>`):

| unit | result |
|---|---|
| `zzzzzzzzzzz_night_disc` | 5/5 ok |
| `zzzzzzzzzzz_a1_coverage` | 2/2 ok |
| `zzzzzzzzzzz_site_map` | 7/7 ok |
| `zzzzzzzzzzz_a1_polish_discovery` | 2/2 ok |
| `zzzzzzzzzzz_site_runs` | 6 ok, 1 EXC |

The EXC is `site-runs-run-row-geometry-at-1024`: "the state names a smoke run the walk could not find". Its hash needs
`{run:a}`, which only the full walk's flows create. Its edited eval was run by hand at 1024 px on the same page and
returned `data-geometry="ok"`.

**Not run here.** `discovery` (the full walk) and `zzzzzzzzzzz_a1_seed_search` (it runs a preview, keeps it and writes
runs) are left to the manager's gate.

## Open questions and risks

- **The preview in "demo · talk" on the real database.** The session's stored preview is still the 22:36 3-channel one,
  unless the Demo instance session re-ran it. Re-run F-30's preview once before the talk so step 3 is instant.
- **The top scrollbar** is a 12 px strip. Headless Chromium draws overlay scrollbars, so the screenshot shows no thumb.
  Desktop Chrome on Windows draws it; worth a look on the researcher's screen.
- **The kind badge** is 9.5 px in the left column so that "reference" fits in 64 px.

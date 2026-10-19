# night-b — Explore, Library, Analyse (port 8768), 2026-10-19/20

**In plain words.** I used Explore, the Library and Analyse the way a tired researcher would. I did it on two
made-up databases built to be as big as the real one. Twelve problems were small enough to fix tonight, and each
fix went in test-first. The two that matter most were slowness. Opening the Library's atlas sent the same question
to the server ten times at once. The first open of a Library family took close to a minute on a database of the
real size. The worst things left are listed at the end, each with how to reproduce it.

## Assumed

- **`webui/client/src/api/explore.ts` is Explore's file.** Only `explore/*` imports it, and neither A nor C works
  near it. I used it for the shared reads (`getWholeChannelSpans`, `getChannelShared`). One existing line in each
  of `getSignalLive` and `getCrossChannel` changed, so this is not append-only.
- **"Library rose reference with no accepted motifs"** I checked at the bridge only, not in the browser.
  `GET /api/library/rose-reference?unit=motifs` answers `median_slope: null` with a sentence saying why, which is
  honest. The night fixture has no chain with Event shape, so no rose was drawn.
- **Bridge timings are noisy.** Another session's import was running on the same machine. A freshly started bridge
  also runs its background workers (corpus map, scorer) for the first minutes. Load times are given for a cold
  bridge and a warm one, and the request counts matter more than the seconds.
- **Analyse's default picker on Signal is not changed.** Signal shows the newest three runs by default (finding
  R4), so scratch Analyse runs push the Discovery runs out. That is a product decision, not a bug, so it is
  reported only.
- **C's list was split.** Of the six items the coordinator relayed from C, I fixed (1), (2), (3) and (5). Item (4)
  (Corpus counts 0 while computing) and item (6) (Templates captions) are reported, not fixed.

## What I drove

`scripts/night/b_fixture.py <out.sqlite>` builds the interaction fixture. It runs `tests/perf_fixture.py` at
16 ch × 72 h, adds one extra run of 90 k detections on channel 1 (about 97 k on that channel in all), and adds a
Library: 12 motif families with omitted members, sequences of three, and a sequence grouping.

The load fixture is `python tests/perf_fixture.py full.sqlite` (FULL: 5 M detections, about 385 k on channel 1).
I added the same Library to it with `b_fixture.add_library`.

`scripts/night/b_drive.py --url http://127.0.0.1:8768 --only loads,signal,take,cross,library,analyse,send` runs the
walk. It uses the conda Playwright and saves screenshots to `--shots`. For the real database, pass `--signal-ch`,
`--cross-ch`, `--family`, `--sparse-ch` and `--thresholds` with ids that exist there.

- `take`, `cross` (Mark artifact), `library` (Keep), `analyse` (Run chain) and `send` **write**. Use them on a
  sandbox only.
- Each probe prints `ok`/`BAD` with what it saw.

## Findings — fixed

| # | Page | Finding | Fix | Commit (red → green) |
|---|---|---|---|---|
| F1 | Library atlas / family / recurrence | **The "every 2 s groupings re-read" was not a timer.** `useAllGroupings` is called by the page, `GroupingGate`, both resolved-id hooks, the grouping bar and the drawer. Each call mounted its own `useSourced(getGroupings)`: 10 reads in about 10 ms on every atlas open (family 9, unknown `?grouping=` 11), queued behind one sqlite connection. | `library/groupingsRead.ts`: one shared read in flight (2 s window). A reload anywhere re-reads once for every caller. Atlas 10 → 1, family 9 → 1, `g-99` 11 → 2 (the gate's deliberate re-read). | de3ba7f → 62dbb40 |
| F2 | Explore Signal, Cross-channel | The whole channel's spans were read 2–3× per open: `getSignalLive` plus Signal's ‹ N / M › list at once, and Cross-channel's chip after paint. Fixture: 2.7 s + 5.4 s. | `explore/coalesce.ts` (keyed, in-flight only) through `api/explore.ts::getWholeChannelSpans`. Cross-channel starts the chip's read beside the window read. Now 1 read. | d177bb2 → e1aac9c |
| F3 | Cross-channel | `/api/channels/{id}` was read twice at once at scale (37 s and 30 s on a fresh FULL bridge; the page painted at 45 s). | `getChannelShared` through the same helper. | e780bcc → 0960fe4 |
| F4 | Library family (cold) | **The first open of a family at scale took 44 s** (FULL + 12 families). `_library_detections` returned about 385 k rows a recording, using a per-row `absolute_bounds` call and `np.asarray` over tuples. `background_null._Recording` then looped over every row again to build a mask that only needs their union. | The shift is done in SQL (`corpus.spans`'s statement of the rule), then `np.fromiter`, a numpy sort, and the merged intervals are returned. The union mask is unchanged (pinned). Cold-process harness: F-01 7.0 s, F-02 4.1 s; the bridge after restart: F-01 19 s on a cold, busy bridge, F-03 5.3 s once warm. | f5abe60 → 322f5fc |
| F5 | Analyse › Interrogation | *Open in Library →* wrote `#/library/family?family=id001`. The family page reads its id from the path, so it drew the first family (F-01) under the Library header. | `library/family/<id>`. A seed-store id that is not a Library family now says "No family id001 in grouping g-01". | 064760f → c7095ef |
| F6 | Explore Signal | The header said *demo data*, the legend said *demo* and the ribbons said "(demo canon)" on every live channel (`demo={!!demo}` on the live read's data). | They follow `demoRead.source`. | 661711c → e42c677 |
| F7 | Library section bar | A kept label-chain family's id is its whole chain (26 labels joined by '.'). The crumb ran over the *Templates* tab, and at 1024 px the tabs shrank under each other. Build sequences said "1 sequences in 1 label chains". | The crumb ellipsises (the heading prints the id in full). The tabs are `flex: none`. Singular words. | d9397f8 → d15cc73 |
| F8 | Analyse block pages (Event shape, Intervals) | With one event the table read "events 1.000 · intervals 0.00e+0". Every exact zero printed as `0.00e+0`. | `analyse/fmtNum.ts`: 0 → "0", `n_…` → integer. `EventFeatures.tsx` re-exports it. | 0bb7f35 → 850073a |
| F9 | Intervals timeline | "intervals within [all] [all]" appeared whenever there was nothing to colour by (duplicate React key `all`). With 0 events it said "no depth or score measured". | The bridge's `all` class is not listed twice. `serialize._interval_classes` says "the span holds no event". | da3ff8c → 7cf0e78 |
| F10 | Analyse block pages | The "more (N)" fold followed you to the next block page: open on Intervals, ribbon to Trains, and Trains showed it open; after a reload it was closed. `Headline` reads storage only on mount. | `registry.tsx` keys the block page's `Headline` by page. | 150487f → f85b6a8 |
| F11 | Analyse chain (C's walk) | `?template=<name>` became `GET /api/templates/NaN`, shown as a bare "422 Unprocessable Content". | Looked up by name or short name. If missing: "no saved template called “nope”". | 06f52aa → 8059fd2 |
| F12 | Cross-channel, Block (C's walk) | The loading and error headers defaulted to *demo data*. An unknown channel was "not in the demo data", with a link to fixture channel CH4_A2. A stage past the chain's end was titled "02 —". | No chip unless the read was demo. "No channel 999 in this project" with *Open the Corpus*. "08 · no such stage". | 06f52aa → 8059fd2 |
| F13 | Interrogation (C's walk) | `?family=nope` silently drew id001. | A red notice names the missing family and offers the one shown. | f8e15d3 → 43899af |

## Findings — reported (not fixed: too big or outside B's files)

| # | Page | Finding | Severity | One-line reproduction | Where |
|---|---|---|---|---|---|
| R1 | **Review (A)** — the Take-span path | **Take span → Open Review lands on "No more items in the demo fixture · every materialised item of Explore spans is judged; the other 0 are not in the fixture"** while the rail says *622 left* and the counter *0 / 622*. The bridge sends those rows `judged: false` with `baseVerdict: 'seed'`, and the client counts any `baseVerdict` as judged, so the taken span can never be reviewed. The copy also says "demo fixture" on live data. | **high** (demo path) | Signal → *Take span for Review* → toast *Open Review →* | `review/queue.ts:64` (`!!row.baseVerdict \|\| row.judged === true`), `review/index.tsx:68-74`, `review/common.tsx:40` |
| R2 | Explore Signal (scale) | Tier 2 waits for the whole channel's spans: `/api/channels/{id}/spans?t0=0&t1=<duration>` takes 2 s on its own and 6–16 s on a busy bridge with 385 k detections (C saw 153 s). `spans()` fetches every row as `sqlite3.Row` and builds a dict per row before capping at 5 000. Fix: read the viewport for tier 2 and the ‹ N / M › list on demand (C's proposal), and/or tuples plus a count query in `spans()`. | high | `#/explore/signal/1` on FULL | `api/explore.ts:~100` (`getSignalLive`), `SignalPage.tsx:~142`, `server/corpus.py:834` |
| R3 | Explore Signal / Cross (scale) | `GET /api/channels/{id}` runs `corpus.ribbons` over every detection on each call: 0.8–3.5 s alone, 12–37 s on a busy fresh bridge. Signal reads it twice in sequence (SignalPage, then `getSignalLive`). Cache the ribbons by a detections fingerprint. | med | as R2 | `server/app.py:209-217`, `server/corpus.py::ribbons` (not B's) |
| R4 | Explore Signal | The default detections picker shows the **newest three runs with detections**. After a few *Run chain* tries in Analyse, Signal on that channel shows those scratch runs ("9 motifs in view" against 97 k detections). | med | Analyse: run a threshold chain on CH1 → Signal CH1 | `explore/signalModel.ts:24-27` |
| R5 | Library family (scale) | The cold first open is still 5–19 s: `_family_coherence` draws quiet windows over every recording a family touches, and `_library_detections` still costs about 0.4–1 s a recording (the SQL fetch). Caching the merged union per recording by `_library_fingerprint` would remove it after the first family. The fingerprint itself is about 1 s (`COUNT(*)` over 5 M detections). | med | `#/library/family/F-02` on a fresh FULL bridge | `server/library.py:1389` (`_library_fingerprint`), `:1430` |
| R6 | Every page | `App.tsx` polls `/api/runs?limit=1` every 5 s (4 reads in 20 s on an idle atlas). This is expected for the jobs chip, but it is the one read that never stops. | low | any page, 20 s idle | `App.tsx:57` (C) |
| R7 | Explore Corpus (C) | All counts read 0 while "computing the map for the first time…". `/api/channels/<n>/tags` is read 16× on open. | med | fresh bridge, `#/explore/corpus` | `explore/CorpusPage.tsx:~266`, `explore/RightRail.tsx:30-61` |
| R8 | Library Templates (C) | 30 grey caption nodes on the list (one per card). | low | `#/library/templates` | `library/TemplatesPage.tsx` |
| R9 | Explore Signal | With every band toggled off the nav reads "– / 0+" (a capped "+" on zero). | low | toggle all six bands off | `explore/SpanView.tsx:210-213` |
| R10 | Cross-channel | The "align" label sits at the end of the first controls row, away from its *as recorded / lag-aligned* switch on the next row (1440 px). | low | `#/explore/cross-channel/1` | `explore/CrossChannelPage.tsx:~299` |
| R11 | Analyse chain | *Use the example span* on a database without M2_aug's CH1_A1 gives a Source row marked "cached" with an empty ±1 mV plot and no error, and the footer says "no stages" with three on the canvas. The real database has the recording, so this does not affect the walk. | low | night fixture: empty canvas → *Use the example span* → import any template | `analyse/ChainPage.tsx:173`, `analyse/rowState.ts:89` |

Checked and fine:
- **Signal span edges.** Nonsense, negative, `1e3`, a comma decimal, reversed, out-of-range and empty values are all refused in place, and the view does not move. ↑/↓ steps by the last digit. → pans; `]` steps one motif.
- **Band toggles.** All six turn off and on.
- **Take span.** Writes, and the seed picker's *Explore selection* tab offers the span.
- **Cross-channel.** The overlay shows all 16 channels. Click and shift-click set the bold channels. A box with nothing bold has a grey strip. Align by lag prints shifts and names who is left out of the box. Max lag 1 s says "nothing to move". *Mark artifact* starts on the bold channels and writes.
- **Send unjudged.** Zero motifs says "nothing to send". Over 2 000 is refused in words (a 422; the browser logs it as a console resource error, which the smoke gate counts).
- **Build sequences.** Gap 0 gives "0 sequences" with *Keep* grey. Keep, then keep again, is grey ("already kept"). The kept family opens.
- **Intervals and Trains** with 0, 1 and 2 events paint with no red card. Trains says "no trains" honestly.
- **Templates search.** It finds hits, shows a no-match line, and one group opens again when cleared.
- **Equal depths** give one "all" class with the sentence saying so.

## Load times

Each row is the time until the page's main `data-testid` paints and the number of API requests in the first 10 s.
Every page made 1 more request in the following 5 s (the `/api/runs` poll, R6).

| Page | Night fixture (97 k det on ch 1), before → after | FULL (385 k det on ch 1), fresh bridge | FULL, warm bridge, after F3 |
|---|---|---|---|
| Signal `explore/signal/1` | 1.98 s / 19 req (spans ×3) → 2.30 s / 18 (spans ×1) | 13.7 s / 7 | 3.4 s / 18 |
| Cross-channel `/1` | 4.2 s / 18 (spans ×2) → 1 spans read | 45.1 s / 10 (`/channels/1` ×2) | 7.2 s / 16 |
| Atlas | groupings ×10 → 1.13 s / 12 (groupings ×1) | 4.7 s / 12 | 0.49 s / 12 |
| Atlas · sequences | 0.69 s / 14 | 0.53 s / 14 | — |
| Family F-01 | 1.18 s / 8 | 44.7 s / 8 before F4 → 19.1 s after (cold, busy) | F-03: 5.3 s / 8 |
| Recurrence | 0.64 s / 11 | 0.47 s / 11 | — |
| Chain (seeded) | 0.58 s / 10 | 0.58 s / 9 | — |
| Block 0 / 1 / 2 | 0.52 / 0.52 / 0.60 s, 8–9 req | 0.47 / 0.51 / 0.47 s | — |

Over 2 s on a database of the real size: Signal (R2, R3), Cross-channel (R2, R3) and the family's first open
(R5). `/api/review/counts` is read 2–3× on every page (C's shell; C reports a shared read for it).

## Tests added (interpreter)

- `tests/test_webui_night_b_groupings_read.py` (5): conda python; node runs `groupingsRead.ts`.
- `tests/test_webui_night_b_spans_once.py` (5): conda python; node runs `coalesce.ts`.
- `tests/test_webui_night_b_links.py` (8): conda python; source-level.
- `tests/test_webui_night_b_polish.py` (4): conda python; one builds an intervals payload through the adapter.
- `tests/test_webui_night_b_fmtnum.py` (4): conda python; node runs `fmtNum.ts`.
- `tests/test_webui_night_b_family_cold.py` (2): **webui/.venv**, because it imports `server.library`.

Other runs:
- With the conda interpreter, the night-b files above (all but `test_webui_night_b_family_cold.py`), plus
  `tests/test_import_boundaries.py` and `tests/test_serialize_interval_classes.py`, gave 41 passed in one run.
- With webui/.venv: `tests/test_webui_library.py` plus `tests/test_webui_library_family_actions.py` gave
  66 passed, 3 xpassed; `tests/test_library_background_null.py` gave 41 passed.

`tsc -b` and `vite build` pass from the worktree, through the junction.

## Smoke

No smoke state files were changed. `explore.cross-channel / unknown-channel` still expects `cross-unknown`, which
is kept; only its words changed. The Signal page no longer shows `demo-chip` on live channels, and no state
expects it there.

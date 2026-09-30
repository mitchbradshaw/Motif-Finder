# Report — Fixup E: Interrogation › Aggregate stops inventing its measurements

Run 2026-09-30 on `main`, in the main checkout, in parallel with prompt `G` (Review; port 8766). Commit prefix
`fixup-e:`. The first commit, `0392dd0`, touches only `tests/` and fails 1 adapter test at collection order plus 6
route tests (the parameter, the column and the route did not exist). The bridge ran in `--sandbox` on port 8765
throughout. Nothing wrote to the real `DATA/db/annotations.sqlite`; it was read once, read-only, to count
`motif_features` (71,980 values over 3,599 hashes, 1,238 of them a null `recovery_time_s`).

**What is true now, in one paragraph.** Every number on the Aggregate page is read: the store's slope measures for
01 Resolve spans, `interrogation.event_shape`'s measures for 01 Event shape, served by a new route
`GET /api/interrogation/families/{key}/shape` (from `motif_features` by the snippet's content hash where the Library
carries them, otherwise measured on the store's own snippet from the detector's anchors — never written). The three
constants (`half_width = 0.84 × duration`, `rise = 0.31 ×`, `isi = 4.2 ×`) and the browser's recovery are deleted.
An event the core did not measure is **absent** from that distribution and **counted**, with the rule that made it
null, on every panel whose `n` is smaller than the family. Rise time is a parameter of the shape block and null for a
drop. "Spike shape" is gone: the second upstream is Event shape, a block that really differs, and the upstream is
carried on every walk between the three pages. The members-overlaid plots draw the stored context on a measured y.

---

## 1. What the page used to invent against what it now measures — the same events

`scripts/fixup_e_evidence.py` → `webui/screenshots/fixup/E/fabricated-vs-measured.{json,md}`. For every one of the
410 seed events it reproduces the four numbers the page drew (the three constants, and the browser's recovery exactly
as `memberFrom` computed it: 90 % of the depth, on the 400-point decimated snippet, 0 when never reached) and puts the
core's measurement beside each (`Working.library.features.measure_snippet`: FWHM, rise time, recovery at 50 % within
10 widths; and the real onset-to-onset interval within the span).

**The default family, id001 (sharkfin, 17 events) — what the researcher has been reading:**

| event | fall s | half_width = 0.84×fall | FWHM (core) | rise = 0.31×fall | rise (core) | isi = 4.2×fall | interval before (core) | recovery (browser) | recovery (core) |
|---|---|---|---|---|---|---|---|---|---|
| id001_r1_1213252 | 99 | 83.2 | **not measured** | 30.7 | **not measured** | 416 | **not measured** (first) | 0.0 | **not measured** |
| id001_r1_1214169 | 120 | 100.8 | **not measured** | 37.2 | **not measured** | 504 | 917 | 0.0 | **not measured** |
| id001_r1_1215146 | 113 | 94.9 | **not measured** | 35.0 | **not measured** | 475 | 977 | 0.0 | **not measured** |
| id001_r1_1216093 | 135 | 113.4 | **not measured** | 41.9 | **not measured** | 567 | 947 | 0.0 | **not measured** |
| id001_r1_1217026 | 126 | 105.8 | **not measured** | 39.1 | **not measured** | 529 | 933 | 0.0 | **not measured** |
| id001_r1_1217981 | 109 | 91.6 | **not measured** | 33.8 | **not measured** | 458 | 955 | 0.0 | **not measured** |
| id001_r1_1218975 | 124 | 104.2 | **not measured** | 38.4 | **not measured** | 521 | 994 | 0.0 | **not measured** |
| id001_r1_1220047 | 159 | 133.6 | **not measured** | 49.3 | **not measured** | 668 | 1072 | 0.0 | **not measured** |
| id001_r1_1221280 | 136 | 114.2 | **not measured** | 42.2 | **not measured** | 571 | 1233 | 0.0 | **not measured** |
| id001_r1_1222732 | 101 | 84.8 | **not measured** | 31.3 | **not measured** | 424 | 1452 | 0.0 | **not measured** |
| id001_r1_1224460 | 175 | 147.0 | **not measured** | 54.2 | **not measured** | 735 | 1728 | 0.0 | **not measured** |
| id001_r1_1226559 | 172 | 144.5 | **not measured** | 53.3 | **not measured** | 722 | 2099 | 0.0 | **not measured** |
| id001_r1_1229009 | 219 | 184.0 | **not measured** | 67.9 | **not measured** | 920 | 2450 | 0.0 | **not measured** |
| id001_r1_1231748 | 234 | 196.6 | **not measured** | 72.5 | **not measured** | 983 | 2739 | 0.0 | **not measured** |
| id001_r1_1234786 | 248 | 208.3 | **not measured** | 76.9 | **not measured** | 1042 | 3038 | 0.0 | **not measured** |
| id001_r1_1238198 | 200 | 168.0 | **not measured** | 62.0 | **not measured** | 840 | 3412 | 0.0 | **not measured** |
| id001_r1_1244389 | 111 | 93.2 | **not measured** | 34.4 | **not measured** | 466 | 6191 | 0.0 | **not measured** |

On the default family the page drew **51 half-width / rise / ISI values and 17 recoveries, and not one of them was a
measurement**: the sharkfin falls and stays low until the next rise, so no id001 event re-crosses its half level or
recovers inside the bound, and a drop has no rise. The "Half-width" histogram (median 8.4 s in the frame's recorded
verdict; 83–208 s on the live page) was a rescaled copy of the fall-duration histogram, and `amplitude ~ half-width`
was a straight line at gradient 0.84 dressed as a scaling law (β 0.88 [0.61–1.15] was the frame's recorded number,
reprinted over live points). The ISI the page drew was 0.44× the real interval (median), and 0.03× at the 10th
percentile.

**Over all 410 seed events:**

| the page drew | against the core's | measured on | not measured (the page drew a number anyway) | median error, s | p90 abs error, s | drawn / measured, median [p10–p90] |
|---|---|---|---|---|---|---|
| `half_width_s` | `fwhm_s` | 240 | **170** | −14.2 | 109 | 0.43 [0.23–0.61] |
| `rise_s` | `rise_time_s` | 0 | **410** (a drop has no rise) | — | — | — |
| `isi_s` | `interval_before_s` | 394 | 16 (first of a channel) | −58.6 | 4081 | 0.44 [0.03–1.37] |
| browser `recovery_s` | `recovery_time_s` | 240 | **170** | −7.3 | 60.8 | 0.00 [0.00–3.29] |

The browser's recovery read **0 s on 305 of 410 events**: the 170 the core says never recover, *and* 135 where the core
measures a recovery — the 90 % level is stricter than the core's 50 % and the decimated snippet rarely reaches it. So
the page's "recovery" distribution had a spike at zero holding three quarters of the family, at the wrong end, and
nothing on the page said what zero meant.

## 2. Rise time on the shape block, and how null flows through

`interrogation.event_shape` gains `rise_time_frac` (`ParamSpec`, float, default **0.1**, bounds 0–0.49) and a
`rise_time_s` column (in `COLUMNS` and therefore `MEASURES`, so the Library backfill stores it). The rule, printed
in `meta["rules"]` and on the page:

> a spike's rise only: from the crossing of 0.1 × amplitude to the crossing of 0.9 × amplitude on the way from onset
> to extremum, interpolated, s (the 10–90 % rise time). A drop has no rise: NaN, never 0 (a rise of no height is a
> different statement); counted as n_no_rise

It is measured in the oriented frame (a spike is measured on −x, so its rise is the oriented fall from onset to
extremum) with the same `_crossing_down` FWHM uses, and assigned only when the **recorded** polarity is a spike —
so a drop the chain inverted (`upstream_inverted`) has one, and a genuine drop never does. `rise_time_frac = 0` makes
it the whole onset → extremum, the event width. Hand-worked test: the synthetic spike rises 0.0005 V per sample over
samples 50–70 at 10 Hz; 10 % is crossed at 52 and 90 % at 68, so 1.6 s (2.0 s at frac 0).

**Null flows through as null.** Core: NaN in the frame, `n_no_rise` in `meta`. Route: JSON `null`, `counts.n_no_rise`.
Client: `EventMeasures.rise_time_s: number | null`; `featureOf` returns `null`; the histogram's `valuesFor` drops the
event and counts it; the scatter drops the point and counts it; the timeline draws a hollow stub with the title "not
measured"; the table cell is "—" with the reason on hover. Every drop family therefore shows "Rise time · n 0 of N"
with "a drop has no rise: null, not 0 (Q19)", which is what the decision asked for. The stored `motif_features` rows
written by fixup-d predate the column; the route fills the missing measure from the same snippet the row was
measured on and says which (`completed_from_snippet`) — for a drop that is null either way.

## 3. How many events do not recover within the bound

| store | events | `recovery_time_s` null | `fwhm_s` null |
|---|---|---|---|
| seed store `drop_motifs5` (the 16 families this page reads) | 410 | **170 (41 %)** | 170 |
| the real Library `motif_features` (read-only count) | 3,599 | **1,238 (34 %)** | 1,238 |
| … of which `Plots/drop_motifs10/motifs` | 3,189 | 1,068 (33 %) | |

By family it is all-or-nothing: **id001 17/17, id003 16/16, id021 14/14, id024 40/40, id026 2/2, id028 19/19, id029
48/48** never recover; id010 1/84, id020 1/4, id022 3/24, id025 1/26, id034 7/40, id035 1/18; id008, id033, id385
0. Those are the sharkfin spans (the morphology column says so) against the trough spans. **This is a finding about
the data, not a rendering detail:** on a sharkfin the trace does not return half-way to the onset level before the
next rise begins, so "recovery" and "FWHM" as defined (fixup-d §1) do not exist for that morphology, and the default
family is one. The page says so in an amber callout at the top ("Not measured, not zero"), and the width-vs-recovery
scatter on id001 draws nothing and says why. On id010 (84 trough events) it draws 83 points with
**β 0.28 [0.16–0.40], R² 0.23, n 83** against a null β of 0.25 — the recovery of a trough event grows weakly with its
width and does not clear the null drawn. Whether a sharkfin's recovery should be measured to the *next onset* instead,
or to a lower fraction, is the researcher's call and a parameter already (`recovery_frac`).

## 4. Resolve spans and Spike shape (U10)

Two blocks now, genuinely. **01 Resolve spans** is the store's slope analysis (detect5's anchors, `gradients` — depth,
fall duration, max / onset / chord slope, peakedness). **01 Event shape** is `interrogation.event_shape` (amplitude,
precursor, width, onset→recovery duration, FWHM, recovery, rise time, slopes, peakedness) declaring only what the core
measures — `UPSTREAMS['event-shape']` in `fixtures/interrogation.ts`. `recovery_s` is the core's on both. `max_slope`
and `peakedness` exist on both and are measured by different code (they agree on 408/410, fixup-d §2); `featureOf`
takes the upstream and does not mix them. The old key `spike-shape` is accepted as an alias so a saved link opens the
shape block, which is what its label promised.

The revert: `ChainCard.onSelect` on all three pages, the member tiles, "Open 02 Aggregate", and the Slope page's
"02 Aggregate →" built hashes by hand and most dropped `?upstream=`. All go through `draft.ts::interrogationHref(page,
family, upstream, extra)` now. A smoke state clicks the ribbon chip from Aggregate (event-shape) to block 1 and expects
the Event shape footer.

## 5. The scatter (item 5) and the window (item 6, U11)

`width ~ recovery` is the Event shape upstream's first pair (`width_s` = onset → extremum, `recovery_s`), with
`amplitude ~ FWHM` and `amplitude ~ width` beside it. The fit is `fitLogLog` on the drawn points (never the frame's
recorded β, which `adjustedFit` used to anchor on), the null β is the same fit on the null points drawn, β per
recording is computed when colour-by is recording. Under 12 points there is no fit, and the card says how many events
have no point and why.

The window. Source settings › context padding is now **the stored context** by default (what the store kept around
each event: median 55 s before / 61 s after, up to 46 min), with ± 60 / 300 / 1000 s and the three proportional
options beside it (`api/interrogation.ts::PADDING_OPTIONS`; a proportional pad cannot show a slow precursor to a fast
event, and the option says so). The three overlays (Source › Members overlaid, Slope › strip and Events overlaid) draw
the store's own decimated samples inside that window — nothing interpolated, nothing held flat past a snippet's end —
at 340 px tall, and their y is `charts/domain.ts::measuredDomain` over the traces drawn, replacing `liveYDomain`'s own
5 % pad over the whole family. Before/after: `webui/screenshots/fixup/E/before-source-overlay.png` (−20 … +40 s, flat)
against `after-source-overlay.png` (−679 … +863 s, the sharkfin rise and fall). The synthetic "medoid" curve drawn in
black over the real members on the Source page was a fixture shape and is removed. The Source page's `align` control
now aligns on the onset or the trough (both the store's own indices); `steepest` is disabled with the reason.

## 6. Defaults taken

| default | value | why |
|---|---|---|
| `rise_time_frac` | 0.1 (10–90 %) | the electrophysiological convention; 0 gives onset → extremum |
| rise time assigned to | recorded polarity = spike | a drop has no rise; an inverted drop is a spike in the recorded frame |
| context padding | `snippet` (the stored context) | the store kept it for exactly this; proportional pads hid the precursor |
| overlay height | 340 px | "narrower and taller" |
| histogram domain | measured from the drawn values | the frame's recorded domains were in the wrong decade for live data |
| fit | `fitLogLog(used)`, none under `MIN_FIT_N` = 12 | the recorded β was the frame's |
| null β | the same fit on the null points drawn | never a recorded constant (the null's own construction is unchanged, §8) |
| the shape route's anchors | the detector's `onset_idx` / `trough_idx` | fixup-d: 410/410 depths agree; own anatomy locks onto neighbours on 10 |
| stored vs measured | `motif_features` when the row exists, else measure, never write | a view writes nothing (fixup-d's rule) |

## 7. Out-of-scope files touched

- `webui/client/src/fixtures/interrogation.ts` — `InterrogationMember.recovery_s` nullable, `EventMeasures`, `Upstream`,
  the optional recorded verdict/fit fields, `CHAIN_EVENT_SHAPE`, and the `event-shape` upstream spec replacing
  `spike-shape`. The spec's feature list *was* the fabrication's declaration; the type is the member's home.
- `webui/client/src/api.ts` — append only (`getFamilyShape`, its types), committed on its own at once.
- `scripts/fixup_e_evidence.py` — the evidence, dev tooling.
- `webui/smoke_pages/interrogation.json` — mine by the prompt; 49 states (8 new, 3 renamed).
- **Not** touched: `kit/plots.tsx`, `charts/*` (called, not changed), `webui/smoke.py`, `review/**`.

## 8. Items left

1. **The Aggregate page's null is still a seeded jitter of the data**, labelled "matched random windows · 200×". The
   null β now comes from those drawn points rather than a recorded constant, and the histogram null is the same
   jitter behind the bars — but neither is 200 matched windows. P10's machinery is page-wide and not this prompt's;
   the label is the remaining claim on the page that is not earned.
2. **The Slope page's anatomy figure** still draws its chord, tangent and "steepest" marker from
   `fixtures/interrogation.ts::eventMarks` (steepest = duration / 2) over the real trace, and opens 10 s before the
   onset whatever the padding setting. Prompt `H` (blocks show their work) owns that figure.
3. **Fixture τ per recording** (`TIMELINE_TREND`) is keyed by fixture recording names; live recordings print
   "n N · no trend test", which is honest and useless. A Kendall τ from the core would be a two-line route.
4. **`motif_features` predates `rise_time_s`**: the stored rows lack it and the route fills it from the snippet per
   request. `scripts/fixup_d_backfill_features.py --real --only-missing` would store it, but every stored event is a
   drop, so it would store 3,599 nulls. `RULE_VERSION` in `Working/library/features.py` does not mention
   `rise_time_frac`; it should when a spike store is backfilled.
5. **The sharkfin morphology has no recovery under the current definition** (§3): 41 % of the seed store, 34 % of
   the Library. Whether the definition should reach the next onset for that morphology is a research decision.
6. **The shared client build.** Prompt `G` was active in this checkout (a bridge on 8766, uncommitted Review hunks in
   `smoke.py` and `review.json`). I built `webui/client/dist` three times (13:33, 13:37, 13:45); those builds compiled
   `G`'s uncommitted sources too. I could not build a private dist because `run_server.py` has no `--dist` option —
   `Runtime(client_dist=…)` exists but is not exposed. If `G`'s bridge serves the shared dist, my rebuilds changed it
   under them; `G` should rebuild before their own smoke.

## 9. The gate

| gate | result |
|---|---|
| `pytest -n 4` (conda), after every commit | **1799 passed, 7 skipped, 0 failed** (8 m 35 s) against the 1775 / 6 / 0 baseline (1786 after `M`). No failure set to compare: nothing fails. `-n 4`, not `auto`, because `G` shared the machine |
| `tests/test_webui_*.py` under `webui/.venv` (routes, the new shape route, api, serialize, discovery) | **79 passed, 1 failed**: `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`, the pre-existing failure the prompt names |
| `npx tsc -b`, `npm run build` | clean |
| `webui/smoke.py`, full, against a `--sandbox` bridge restarted immediately beforehand (port 8765; `SMOKE_SHOTS` in the scratchpad so `G`'s screenshots were not overwritten). **I took the machine for smoke 13:38–13:57; `pytest` ran 13:58–14:15, never together** | **562 screenshots, 5 failures, 0 browser console/page errors, 0 unexpected server tracebacks.** All 49 Interrogation states pass, including the 8 new ones (the alias, width~recovery on id010, the not-measured notes, the carried upstream, the overlay window notes, the disabled selectors). Four failures are the Settings registration-state states the prompt names (`datasets--import-check-fails-fs-unknown`, `datasets--import-check-passes-MJu26a`, `models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`), failing the same way on every bridge. The fifth is `discovery.runs--default`, **a settle-time failure, not a paint failure**: the state allows 900 ms; probed with Playwright on the same bridge the page had 13 `fires-cell`s and the browser trace by 4.4 s with no console error, and every `/api/discovery/*` call took 3.0 s (`/api/runs?limit=1` took 26 s) on a bridge an hour into a full smoke. The same state failed again alone on that bridge and is not comparable on a fresh sandbox (`--pages-only` skips the flows that create the runs it reads). Nothing under `discovery/` or `webui/server/discovery.py` is touched by this prompt; `fixtures/interrogation.ts` and `api/interrogation.ts` are imported by nothing outside `src/interrogation/` (`api.ts` was appended only) |

The evidence: `webui/screenshots/fixup/E/before-*.png` / `after-*.png` for the Aggregate page (default, the old
`spike-shape` key, id010, width~recovery on id010), the Slope page (id001, the id010 overlay) and the Source page
(the id001 overlay), plus `fabricated-vs-measured.{json,md}` from `scripts/fixup_e_evidence.py` (§1).

## 10. In short

The Aggregate page drew 51 fabricated values and 17 zeros over the default family and called them measurements; now
it draws the core's numbers, leaves out what the core did not measure, and counts and explains every omission. That
exposed a finding: no sharkfin event in the seed store recovers half-way or has a FWHM under the current definition,
so the researcher's width-vs-recovery relationship exists on trough families (id010: β 0.28 [0.16–0.40], n 83, not
clear of its null) and is absent on sharkfins. Rise time is a parameter of the shape block and null for a drop. Spike
shape is gone; Event shape is a real block and the choice is carried. The overlays show the stored context, so the
sharkfin's rise is on the plot.

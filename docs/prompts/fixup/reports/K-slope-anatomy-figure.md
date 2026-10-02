# Report — Fixup K: the Slope page's anatomy figure stops making its marks up

Run 2026-10-02 on `main`, in the main checkout, alone on the machine. Commit prefix `fixup-k:`. The first commit,
`d82413b`, touches only `tests/` and fails 4 tests under conda and 7 under `webui/.venv` (the position of the
steepest sample did not exist anywhere, and the page's constants did). Every bridge ran in `--sandbox` on a private
client build (`run_server.py --dist`, the `CLIENT = …` banner checked). Nothing wrote to the real
`DATA/db/annotations.sqlite`; the evidence script reads the tracked seed store only.

**What is true now, in one paragraph.** Every mark on the anatomy figure is the store's measurement, drawn at the
sample it was measured at: the detector's `onset_idx` and `trough_idx`, the sample `gradients.fall_gradients` found
steepest, and the snippet's own height at each of the three. The chord runs from the trace at the onset to the trace
at the trough; the tangent touches the trace at the steepest sample at the measured slope; the depth line spans the
two heights. `fixtures/interrogation.ts::eventMarks` is deleted, as are the three constants beside it in
`SlopePage.tsx` (`-depth / 2`, `-depth`, a 0.012 mV "baseline band"). The figure's window follows Source settings ›
context padding. A mark the store did not measure is not drawn and is named on the face of the card. The smoke gate
measures the drawn marks against the payload in the browser.

---

## 1. Where each mark was drawn against where it is

`scripts/fixup_k_evidence.py table` → `webui/screenshots/fixup/K/drawn-vs-measured.{json,md}`: for all 410 seed
events, the position and height the page drew for each mark (reproduced from the deleted code) beside the store's.
Six events, chosen before looking — the page's default event, a second from the default family, and the default
event of one family per morphology and sampling regime:

| event | morphology | fall s | steepest drawn at | steepest measured at | moved | steepest height drawn / measured mV | trough height drawn / measured mV | window drawn | stored context |
|---|---|---|---|---|---|---|---|---|---|
| id001_r1_1216093 | sharkfin | 135 | +67.5 s (50 %) | **+2.0 s (1 %)** | −65.5 s | −9.95 / 8.79 | −19.90 / −9.77 | −10 … +149 s | −647 … +366 s |
| id001_r1_1234786 | sharkfin | 248 | +124.0 s (50 %) | **+0.0 s (0 %)** | −124.0 s | −22.19 / 46.34 | −44.38 / 1.95 | −10 … +262 s | −846 … +1735 s |
| id010_r4_1365139 | trough | 7 | +3.5 s (50 %) | **+1.0 s (14 %)** | −2.5 s | −1.41 / 0.32 | −2.81 / −1.93 | −10 … +21 s | −42 … +21 s |
| id024_r2_1459281 | sharkfin | 53 | +26.5 s (50 %) | **+1.0 s (2 %)** | −25.5 s | −5.01 / 7.54 | −10.02 / −1.65 | −10 … +67 s | −318 … +366 s |
| id029_r1_895398 | sharkfin | 37 | +18.5 s (50 %) | **+1.0 s (3 %)** | −17.5 s | −6.38 / 9.42 | −12.75 / −1.85 | −10 … +51 s | −21 … +229 s |
| id385_r385_2374 | trough | 6 | +3.0 s (50 %) | **+2.0 s (33 %)** | −1.0 s | −6.84 / −6.27 | −13.68 / −10.46 | −10 … +20 s | −36 … +41 s |

**Over all 410 seed events** (every one has a fall between its marks; none lacks a steepest sample):

| | |
|---|---|
| steepest sample, as a fraction of the fall | **median 0.05** [p10 0.00 – p90 0.25] |
| … in the first quarter of the fall | **372 of 410** |
| … within ±10 % of the half-way point the page drew | 18 of 410 |
| … in the last quarter | 5 of 410 |
| how far "steepest" moved | median 12 s, p90 62.5 s, max 148.5 s — **a median 45 % of the event's own fall** (p90 50 %) |
| how far the steepest point's height moved | median 6.3 mV, p90 29.7 mV |
| how far the trough end of the chord and the depth line moved | median 3.3 mV, p90 18.3 mV |
| `fall_duration_s` equals (`trough_idx` − `onset_idx`) / fs | 410 of 410 — the trough marker's *x* was already right |

**"Steepest" moved a long way, and in one direction.** These falls are front-loaded — a cliff, then a tail — so the
steepest sample is in the first few and the page drew it in the middle of every event. By family the median fraction
runs 0.00–0.20 with one exception (id026, two events, 0.51); the full per-family table is in `drawn-vs-measured.md`.
Peakedness (steepest ÷ chord slope) was already printed on the same card as 4.77 for the default event: a number that
says "front-loaded" beside a tangent drawn half-way down.

**The heights were wrong for a different reason.** The page drew the trough at `−depth` and the steepest point at
`−depth / 2`, which assumes the onset sits at 0 mV. The trace is the store's detrended snippet and the onset sits at
a median |3.3| mV (p90 18.3 mV) — so the chord's far end and the depth line missed the trace by exactly that much
(the default event: drawn to −19.90 mV, the trace is at −9.77 mV), and the tangent floated free of the curve.
`before-anatomy-id385_r385_2374.png` shows it plainly: a tangent through the whole panel that touches nothing.

Before/after of the figure on the same six events: `webui/screenshots/fixup/K/before-anatomy-*.png` /
`after-anatomy-*.png` (the "before" set from a build of the client at `a1bd40b`).

## 2. Which marks had no measurement, and what the figure does instead

| mark | measured? | what the figure does |
|---|---|---|
| onset | yes — the detector's `onset_idx`; the figure's time zero | drawn |
| trough | yes — the detector's `trough_idx` | drawn at (`trough_offset` − `onset_offset`) / fs |
| steepest | **the value was, its position was not served anywhere** | now measured in the core (§4) and drawn there; "steepest at +2 s · 1 % of the fall" on the readout |
| chord | yes — `mean_slope_mv_s`, between the two anchor samples | drawn between the snippet's own heights at those samples (a test pins that this *is* the served chord slope) |
| tangent | yes — `max_slope_mv_s` | through the steepest sample at that slope |
| depth | yes — `drop_depth_mv` | from the trace at the onset to the trace at the trough |
| **baseline band** (the "all marks" option) | **no** — it was a constant 0.012 mV line; the store serves no noise band for an event | **not drawn**; "all marks" prints *"not drawn: baseline band · the store serves no noise band for an event, so there is none to draw"* on the card |

On the seed store that is the only absence: all 410 events have every other mark. The figure is still written for
the cases that do not occur here, because the Library import will change the source: no slope row → no marks and one
line naming all five; a trough not after its onset → no trough, chord or depth; no steepest sample → no tangent; no
stored snippet → an amber callout instead of a plot (never the fixture's synthetic curve). Each is counted on the
card (`anatomy-absent`), never rendered at a plausible position.

**The rule rides beside the mark.** An info icon in the mark legend ("Where the marks come from") lists the store's
four rules verbatim from the payload and what the tangent's drawn length is. The `steepest` rule the route serves
now says what was differentiated: *"minimum of np.gradient × fs (a central difference, so one sample either side)
over [onset, trough], mV/s, and the sample that minimum is at"*.

## 3. Is the padding setting honoured

Yes. The figure draws `liveEventPoints(event, eventWindow(event, padding))` — the store's own samples inside the
window Source settings › context padding selects, the same function the overlays use since `E` — and says so under
the plot (*"window −647 s … +366 s from onset · context padding the stored context"*). The default is the stored
context, so the default event now shows its 10-minute rise instead of ten seconds of it. Two smoke states set ± 60 s
on the Source page, walk to block 1 in-app and read the window back (`fixup-k-padding-is-honoured`,
`…-restored`).

The trace is no longer resampled either: the old figure drew `curveOf`, a one-value-per-second interpolation of the
snippet; it now draws the stored (decimated to ≤ 400) samples as they are.

## 4. How big the wiring turned out to be

One page's worth, as the prompt hoped, with one thing it did not anticipate: **the prompt says `gradients.py`
"measures the max slope and where it occurs". It measured the value only.** The position existed in one place, a
matplotlib figure (`Pipelines/drop_motifs/casestudy9.py:665`), which re-derives it. So the smallest honest change
was in the core rather than a second derivative in the route:

- `Working/Detection/drop_motifs/gradients.py::fall_gradients` returns `max_slope_idx` beside `max_slope_mv_s`
  (+10 lines, additive). `None` when there is nothing to measure; the onset sample when there is no fall, which is
  where the reported value comes from in that case.
- `webui/server/interrogation_routes.py::family_slope` serves `steepest_offset`, `onset_mv`, `steepest_mv`,
  `trough_mv`, `n_samples` per member (+13 lines). The heights are read on the full-resolution snippet because the
  page holds a 400-point decimation.
- Client: `EventAnatomy` on the member, filled in `api/interrogation.ts::memberFrom`; `SlopePage.tsx`'s geometry
  block and its JSX rewritten (≈ 90 lines net).

Not the `/shape` route: the anchors the prompt points at (`onset_offset`, `trough_offset`) are on `/slope`, which
the page already fetched, and the slope the figure draws is the store's `max_slope_mv_s`, not the shape block's.

No `NaN` reached a React attribute: every mark is either a finite number or not in the series list.

## 5. Defaults taken

| default | value | why |
|---|---|---|
| where the steepest position is computed | the core, in `fall_gradients` | position and value are one measurement; a second `np.gradient` in the route could drift from it |
| tangent length | up to 16 % of the fall either side, at least one sample | the reach the researcher's own anatomy figure uses (`casestudy9.py:689`); the slope itself is a ±1-sample difference and would be invisible at that length |
| tangent at the plot edge | each end cut short (never bent) where it would leave the trace's y range | keeps the y domain measured from the trace alone (the one plot-domain rule); on a sharkfin the steepest sample is at the top of the trace |
| marker labels closer than 8 % of the window | share one label at the first (`onset · steepest`) | steepest is 0–2 s from the onset on a 1000 s axis; two labels printed on top of each other are unreadable. The lines are still drawn where they are |
| "all marks" | kept as an option; adds the not-drawn line | removing the option is `H`'s call |
| heights | the full-resolution snippet's samples | a mark can stand a pixel off a heavily decimated line; the info icon says so when the trace is decimated |

## 6. Items left

1. **The figure's trace is the route's ≤ 400-point decimation.** On the longest stored contexts (up to 46 min at
   1 Hz) that is one point in seven, taken by stride — a one-sample feature can be missed, and Round 7 Q12 decided
   on a min/max envelope. That is `H`'s idiom, and the marks are immune to it (they are read at full resolution).
2. **The strip thumbnails and the sampled overlay keep a fixture fallback** (`curveOf` / `overlayPoints` →
   `eventCurve`, a synthetic curve, when a member has no snippet). It cannot fire on the seed store — the slope
   route would fail first — but it is the same class of thing on `E`'s cards, not the anatomy figure, so I left it.
   The anatomy figure itself has no such fallback any more.
3. **`interrogation/Rose.tsx` and the figure's visual language** — untouched, as instructed; `H`'s.
4. **The rule selectors** remain disabled previews (`E`, I4). The "steepest window" slider no longer changes the
   tangent's drawn length, which was its only effect on a live family and was not the rule the slope is measured by.
5. **`casestudy9.py` still re-derives the steepest index** rather than reading `max_slope_idx`. One line; a thesis
   figure script outside this prompt.

## 7. Out-of-scope files touched

- `Working/Detection/drop_motifs/gradients.py` — core, +10 lines, additive (§4). Its other callers
  (`event_shape.py`, `casestudy9.py`, the aggregate route) read named keys; `event_shape.measure_event` spreads the dict
  into a row whose frame is built from an explicit column list, so nothing new is stored.
- `webui/client/src/api.ts` — the `SlopeMember` type gained the served fields (one line).
- `webui/client/src/fixtures/interrogation.ts` — `EventAnatomy`, `InterrogationMember.anatomy`, `snippet.n`;
  `eventMarks` deleted. The type is the member's home, as in `E`.
- `webui/smoke.py` — the `anatomy_marks` check and a `hash` action (an in-app walk without a reload), append-only.
- `scripts/fixup_k_evidence.py` — the evidence, dev tooling.
- `tests/test_drop_motifs_gradients.py` — two tests appended.
- **Not** touched: `kit/plots.tsx`, `charts/*`, `interrogation/Rose.tsx`, any other page.

## 8. The gate

| gate | result |
|---|---|
| `npx tsc -b`, `npm run build` | clean. The gate bridge served a private build (`npx vite build --outDir …`, `CLIENT = …scratchpad\\dist-k (a private build, not the shared client/dist)` in the banner); the shared `webui/client/dist` was then rebuilt from the same sources so the next `start.ps1` shows the fix |
| `webui/smoke.py`, full, against a `--sandbox` bridge started immediately beforehand on port 8765, alone on the machine, `SMOKE_SHOTS` in the scratchpad | **579 screenshots, 5 failures, 0 browser console/page errors, 0 unexpected server tracebacks.** The five are the standing ones the prompt names: the four Settings registration `Locator.click` timeouts and `discovery.runs--default`. All **55** Interrogation states pass (49 + 6 new), including `fixup-d-sequence-rose`, which did not flake on this run. The five states carrying `anatomy_marks` each report *"steepest drawn at 1 % [14 % on id010] of the fall, as served · tangent through it at the served slope"* |
| `pytest -n 4` (conda), after smoke had finished — never together | **1878 passed, 13 skipped, 0 failed** (3 m 45 s) against the 1874 / 8 / 0 baseline: +4 passed (two gradient tests, two client pins), +5 skipped (the route tests, which need FastAPI). The failure set is empty |
| `tests/test_webui_*.py` under `webui/.venv` | **304 passed, 1 failed, 3 xpassed**: `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`, the standing failure the prompt names. All 7 of `test_webui_slope_anatomy.py` pass |

The tracked Slope-page screenshots under `webui/screenshots/pages/interrogation/` are this gate run's (14 regenerated,
6 new); the rest of the tracked set is untouched.

**What the smoke check does and does not prove.** It fetches the slope payload inside the page and compares pixels:
the steepest marker divides onset → trough in the served ratio (±1.5 px), the chord runs marker to marker, and the
tangent's pixel slope stands to the chord's as `max_slope_mv_s` stands to `mean_slope_mv_s`. It is scale-free, so it
needs no axis read back from the DOM. It does not check the marks' heights against the payload independently of the
chord, and it was not run against the old client as a negative control (the old page has no `anatomy-figure`
wrapper, so it would fail on that rather than on the measurement).

## 9. In short

The anatomy figure drew "steepest" at half the fall on every event; measured, it is a median 5 % of the way in, and
in the first quarter on 372 of 410. The chord and depth line missed the trace by the onset's own level and the
tangent touched nothing. All of it is now the store's measurement, drawn at the sample it was measured at, inside
the window the padding setting selects; the one mark with no measurement behind it (the baseline band) is not drawn
and the card says so. The position of the steepest sample was not served anywhere — it is now returned by the core
beside the value. The smoke gate checks the drawn marks against the payload in pixels.

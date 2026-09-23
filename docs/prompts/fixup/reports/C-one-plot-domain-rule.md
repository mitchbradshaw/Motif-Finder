# Report — Fixup C: one plot-domain rule, per card, with the page's scale as a bar

Run 2026-09-23 on `main`, in the main checkout, from base `1da6f9f` (fixup-b's report commit, whose gate was green:
pytest 1683/6/0, smoke 4 known failures). Commit prefix `fixup-c:`. The first commit, `b60ce8d`, touches only
`tests/` and fails 22 tests; the implementation is `a9d346a`. Prompt `D` ran in parallel in the same checkout; the
two prompts share no source file, and each ran its own bridge on its own port against a private client build so
neither's `npm run build` could change the assets under the other's open pages.

**The decision implemented (Q-X2.1):** PRD D5 — one shared unnormalised mV domain per page — is replaced by **a
per-card domain measured from the card's own trace, with the page's shared scale drawn as a reference bar.**

**The acceptance test, measured:** on the Library Atlas with Fig2A declared (every card drawable), D5 left **66
traces pinned along their frame** by `MiniTrace`'s silent clamp and **38 `clipped` badges**. After: **0 and 0**, and
**300 of 300 traces sit inside their plot boxes**, measured in a real browser. The same holds on the Family page and
the Review inspector (§6), and smoke now fails if it ever stops holding.

---

## 1. The seam, and why there

**`webui/client/src/charts/domain.ts`** — one pure-TypeScript module with no imports:

| function | what it decides |
|---|---|
| `measuredDomain(...series)` | **the rule.** The extent of every finite sample of every series drawn on a card (the trace *and* its overlays — a medoid over a candidate must not be clipped either), padded by `padDomain`. `null` when nothing finite is drawn: the caller draws an empty plot, never an invented axis. |
| `padDomain(lo, hi)` | the one pad (`DOMAIN_PAD` = 6 %, the number `makeY` always used, so Explore's axes did not move) and the floor for a genuinely flat trace — **only** a zero-width extent is floored (±1 % of its level, or ±0.001 at zero). It is not a minimum domain. |
| `referenceScale(peaks)` / `referencePosition(scale, v)` | the page's shared scale, computed **once per page** from every card's peak and passed to every card: whole decades spanning every positive peak, and where a value sits on it, logarithmically. |
| `centreTrace`, `tracePeak`, `baselinePeak` | the one amplitude measure (peak deviation from the trace's own median), moved here from the Library's `chrome.tsx` so a Review candidate and a Library family are placed on their bars by the same measure. |

`webui/client/src/charts/ReferenceBar.tsx` draws the bar: the same track on every card of a page, a tick per decade,
and a mark at the card's own peak (tooltip: the peak in mV and the scale in words).

**Why `charts/`:** it is the only directory all three workspaces already import from (Explore's `makeY`, Review
and the Library through the kit's `Trace`/`MiniTrace`), and it sits below the kit, so the kit can use the rule as
its default without the rule knowing about React. **Why pure TS with no imports:** there is no Node test runner in
this repo, and the rule is too important to pin only by reading its source — `tests/test_webui_plot_domain.py` runs
it under Node (which strips TypeScript types natively) and skips where `node` is absent.

**Why the bar is logarithmic** (a default, §5): family peaks on this Library span four decades. On a linear bar
scaled to the page, every sub-mV family of a page whose largest is 100 mV sits at zero — D5's flat line, moved into
the bar. On a log bar equal ratios are equal steps, which is also the axis a scaling law is read on, and the
decade ticks make the position readable without a number.

**`webui/server/corpus.py::y_range` is not a second rule and was not changed.** It is a *measurement* — a channel's
full extent in its display unit — which Explore hands to `makeY` as the extent to use while a window's envelope is
still loading. Turning an extent into a domain is the rule's job, and in Explore that is `makeY → padDomain`.

## 2. Every place a second domain rule was removed

| where | what it was | now |
|---|---|---|
| `library/chrome.tsx::sharedMvDomain` (+ `ceilSig`) | **D5**: one domain per page at the 75th percentile of the family peaks | deleted; nothing references it (pinned) |
| `library/chrome.tsx::MotifPlot` | drawn on the page domain, with a `clippedPeak` badge ("clipped · N mV") | measures its own domain; takes a `reference` for the bar; the badge and its prop are gone |
| `library/AtlasPage.tsx` (motif + sequence atlas, both rails) | the shared domain, the clipped count, the "shared mV scale · ±N mV · K clipped" legend and its InfoTip | `referenceScale` once per page; the legend says what the bar means |
| `library/AtlasPage.tsx` sequence atlas | `thumbDomain = [-0.45, 0.45]` for the omitted thumbs | measured |
| `library/FamilyPage.tsx` | **two** domains — `yDomain` (sketch, from members' amplitudes via `niceMvDomain`) and `traceDomain` (`sharedMvDomain([peak], 1)`) | one rule; one `referenceScale` from every member's peak and the exemplar/medoid's |
| `library/chrome.tsx` omitted drawer and `OmittedThumb` | `[-0.45, 0.45]` for every sketch — after fixup-b that clipped every omitted entry above half a millivolt | measured per sketch; the drawer cells carry a bar over the list's recorded amplitudes |
| `library/RecurrencePage.tsx` | the row glyphs on `sharedMvDomain`; the omitted strip on `[-0.45, 0.45]` | measured per glyph |
| `library/ImportPage.tsx` | sample glyphs on `[-0.35, 0.35]` | measured per glyph |
| `review/parts.tsx::Y_MV` | `[-440, 440]` (hand-measured in volts, ×1000 by fixup-b) — context and shape traces | deleted; both measured. The Shape card centres candidate and medoid on their own baselines and carries the queue's scale as a bar |
| `review/Shell.tsx::THUMB_Y` | `[-450, 450]` — queue thumbnails, rail rows, other channels, nearest-family medoids, the reveal card, the cluster view | deleted; every one measured. Other-channels rows carry a bar across the recording's channels |
| `kit/plots.tsx::Trace` default | its own rule: extent + 8 %, or ±0.1 | `measuredDomain` |
| `kit/plots.tsx::MiniTrace` | `yDomain` **required**, and every sample **clamped** into it | optional (measured when omitted); **no clamp** — a sample outside a caller's domain leaves the box, which is measurable, instead of running along the frame where it read as data |
| `charts/scale.ts::makeY` (Explore) | its own copy: 6 %, and ±1 around a flat trace | `padDomain` |

Removed with them, because the new rule made them false: every `clipped` badge, the clipped-count note, the "shared
mV scale · ±N mV" captions (Atlas, Family page, omitted drawer, Review's other channels, Import), the D5 InfoTips,
and the Family page's `SKETCH_NOTE` / `shapeNote` ("drawn with the drop glyph") captions.

## 3. The Family page fetches real waveforms (Q-X2.3)

`GET /api/library/family/{id}` now carries `members[].trace` — each member's own decimated mV trace, read off its span
through `corpus.display_channel` exactly as the exemplar's is (`_trace`, ~120 points; `[]` for an undeclared unit) —
and `removed[].trace` for the removed strip. The member cards, the member rail, the removed strip and the summary's
right panel draw it; `memberTrace`/`motifShape` are gone from the page. The summary's right panel, which drew the
medoid alone because the read carried no member waveform, now overlays the page's ten members under the medoid,
each centred on its own baseline (it was the design's original panel; it had been emptied rather than drawn with
sketches). **The exemplar is now the same trace in the summary, on its own card and in the rail** — L3's complaint.

**Payload, measured on the same sandbox copy (`webui/screenshots/fixup/C/{before,after}.json`; warm reads re-timed
in isolation with `curl`):**

| family | members | before | after | warm read before → after |
|---|---|---|---|---|
| F-01 | 49 (40 drawable) | 30.0 KB | 86.6 KB | ~0.25 s → ~0.27 s |
| **F-30 (the largest)** | 79 (72 drawable) | 41.4 KB | **130.4 KB** | ~0.27 s → ~0.35 s |
| F-130 | 55 (17 drawable) | 32.8 KB | 51.9 KB | ~0.28 s → 0.64 s (timed under load only; not re-timed alone) |
| F-117 (Fig2A, undeclared) | 37 (0 drawable) | 22.4 KB | 22.8 KB | unchanged |

Roughly 1.1 KB per drawable member. **Not decimated**: the largest family in this installation costs about a tenth
of a second more. `library.py::MEMBER_TRACE_PX` is the knob if a family ever makes the read slow — lowering it
decimates the member traces; it does not bring back a sketch. (With Fig2A declared, F-117's members become
drawable too; the column above is the default, undeclared state.)

## 4. What the `drop_motifs10` population looks like now

`webui/screenshots/fixup/C/after-fig2a-declared-library-atlas.png` and `…-library-family-F-117.png` (Fig2A declared
V in the sandbox, as every detector run assumed; fixup-b left it undeclared, which withholds 67 % of the Library).

With every recording declared, the Atlas's 149 family peaks run from **0.012 mV to 68 mV** — nearly four
decades on one page, so the page's bar spans 0.01–100 mV. **30 families peak under the 0.1 mV instrument floor.**
The 21 families whose members are all on Fig2A (385 members) have a median peak of **0.058 mV** (p10 0.016, p90
0.46; 11 of 21 under 0.1 mV) against a median of 0.43 mV for the other 128 and a p90 of 14.7 mV.

Under D5 those families were flat lines at the bottom of a ±4 mV domain, indistinguishable from each other and from
an empty card. Now each fills its card: `F-11` (peak 0.037 mV), `F-100` (0.095 mV) and `F-102` (0.079 mV) draw
as clear single humps and troughs, as legible as `F-01`'s 15.6 mV drop beside them — and **the bar is where they
differ**: their marks sit in the lowest quarter of the 0.01–100 mV track, `F-01`'s at four fifths. On the Family
page, `F-117` (peak 0.025 mV, all Fig2A) shows every one of its ten members on the page as the same ramp, each on
its own 0.03 mV axis, all with their marks at the bottom of a 0.01–1 mV bar. Read together, the Atlas now says
plainly what Q-X2.4 measured: a large part of this Library is a population of events one to three orders of
magnitude smaller than the seed store's, many of them under the floor.

This is the rule working, as the prompt said it would. Nothing was added to tidy it: no floor, no filter, no
minimum domain, no marker. Whether those entries belong in the Library is Q-X2.5 / Q-X2.7 and the Library prompt's.

## 5. Defaults taken

1. **The reference bar is logarithmic, a tick per decade** (§1). The prompt said "a bar drawn to the page's shared
   scale"; a linear bar would have drawn most of the Library at zero. The mark's position is also printed as a number
   in its tooltip, and every card still prints its measured peak.
2. **The bar is "the page's scale with the card marked on it"**, not an electrophysiology scale bar of fixed mV drawn
   in each card's own units. A fixed-mV bar overflows every card smaller than it (a 10 mV bar on a 0.2 mV card is
   fifty plots tall), which would have reintroduced clipping in the bar.
3. **The page's scale is the page's cards**: the Atlas's families; the Family page's members plus its
   exemplar/medoid; the Review queue's candidates (by their thumbnails — the envelope keeps each bucket's extremes,
   so the peak survives decimation) plus the one open; the other-channels popover's channels over the window; the
   omitted drawer's whole list (not the ten on the current page of it).
4. **Review's Shape card centres the candidate and any medoid overlay on their own baselines**, like every Library
   card. The Context card keeps the absolute level (its labels read −420 / −430 mV) — that is where the reviewer
   sees the baseline; the Shape card is for the shape.
5. **Explore got the rule, not the bar.** Explore already drew each view on its own measured extent via `makeY`;
   it now pads and floors through `padDomain`, so its axes are unchanged except for a genuinely flat trace (±1 % of
   its level instead of ±1 mV). Explore draws one channel at a time, so there is no page of cards to put a shared
   scale across; the Cross-channel page's own shared/independent mode is a user choice and was left alone.
6. **Small glyphs get the domain, not the bar**: the queue-rail thumbnails (38 px), the Recurrence row glyphs
   (36 px) and the Import samples. At that size a thumbnail's job is to say which shape it is.
7. **The Family page's member cards carry no y labels** (they never did); each card's peak is in its tooltip and the
   member rail — on its own axis with labels — shows the open member.

## 6. The gate

| gate | result |
|---|---|
| `npx tsc -b`, `npm run build` (`webui/client`) | clean (also built into a private `--outDir` for this prompt's bridge, so prompt D's builds could not swap assets under it) |
| `webui/smoke.py` against a `--sandbox` bridge restarted immediately beforehand, nothing else running | **547 screenshots, 6 failures, 0 console errors, 0 unexpected server tracebacks.** Four are prompt A §7's four (`settings.datasets--import-check-fails-fs-unknown`, `…--import-check-passes-MJu26a`, `settings.models-registration--check-a-joblib`, `settings.storage-backups--scan-check-a-matrix-profile` — registration state in the database the sandbox copies). The other two are **prompt D's own new states** (`analyse.glyphs--fixup-d-feature-glyphs`, `analyse.interrogation--fixup-d-sequence-rose`), which were in the shared `smoke_pages/*.json` while D's client code was still being written and were not in this build; nothing of this prompt's is in either. |
| **the acceptance check** (`traces_in_box`, new) | **8 of 8 flagged states pass, 352 traces measured, 0 outside their box**: `library.atlas--motifs` (106), `--sequences` (7), `--omitted-drawer` (116), `library.family--member-selected` (22), `library.recurrence--default` (64), `review.inspector--1-candidate` (12), `--1b-other-channels` (13), `--4-evidence-rail` (12). **It can fail:** with one path appended 40 px above a real Atlas card in a real browser, it reports `1 of 107 traces leave their plot box: ['family-plot-F-01 -40/82']`. |
| `pytest -n auto` (conda), full suite | **1775 passed / 6 skipped / 0 failed.** Baseline 1683 / 6 / 0 (fixup-b's gate); +19 are this prompt's, the rest are prompt D's, whose uncommitted work was in the shared tree. No test that passed before fails. |
| FastAPI files under `webui/.venv` (`tests/test_webui_*.py -n auto`) | **259 passed, 1 failed** — `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`, the pre-existing one the prompt names. The three new Library tests pass. |

**Before / after, the same pins as fixup-b** (`webui/screenshots/fixup/C/`, full-page; `*.json` beside them holds
what each page printed about scale and the trace measurement; `before-*`/`after-*` are the default state,
`*-fig2a-declared-*` the state with Fig2A declared V in the sandbox):

| surface | before | after |
|---|---|---|
| Library Atlas (Fig2A declared) | 300 traces, **66 pinned along the frame**, **38 `clipped` badges**, "shared mV scale · ±4.10 mV" | 300 traces, **0 pinned, 0 outside**, no badge; each card its own axis, a log bar 0.01–100 mV |
| Library Atlas (default) | 106 traces, 24 pinned | 106 traces, 0 pinned, 0 outside |
| Family F-01 | real exemplar/medoid, 10 member *sketches* on a sketch domain | 24 real traces — members, rail, overlay — 0 outside |
| Family F-117 (Fig2A declared) | exemplar a ramp in the summary, flat noise on its own card and in the rail (±0.70 mV sketch domain set by one member) | the same ramp everywhere, each on its own ±0.03 mV axis |
| Review q2 · detection 100 | context and shape flat along the bottom of ±400 mV | context −418…−431 mV with the drop filling it; shape card "peak 12.6 mV", the queue bar beside it |
| Explore channel 1 | `−112.23 / −156.20 / −200.17 mV` | identical (the rule's pad is the 6 % `makeY` always used) |

## 7. Items left, and found

1. **`webui/client/src/api/interrogation.ts::liveYDomain`** (Analyse › Interrogation) measures its own padded extent
   (5 %) for a stacked overlay of a family's members. It is a shared domain for an overlay, which the rule allows,
   but its pad is its own. Left because Analyse is outside this prompt's three workspaces and prompt D was editing
   the Interrogation surfaces in parallel; a one-line change to `measuredDomain` when nobody else is in that file.
2. **The kit's `LineChart`, `Scatter`, `Histogram`, `SmallMultiples`** keep their own default extents. They draw
   numeric curves (training loss, calibration, distributions), not mV traces, so they are not this rule's; noted so
   nobody mistakes them for a missed case.
3. **The Analyse demo blocks** (`analyse/demo/blocks/{Baseline,Detection}Block.tsx`) still pass literal domains to
   `MiniTrace`. They draw the demo chain's fixture data, which the prompt puts out of scope; with the clamp gone, a
   fixture sample outside its literal domain now leaves the box instead of running along the frame.
4. **The Atlas card footer** ("… s · peak N mV · 0% judged") is cut off on the right at 1440 px. It was before this
   change too (the footer is unchanged); noted, not fixed.
5. **No display path fixup-b missed was found.** Every mV number drawn here comes through `display_channel`.

**Out-of-scope files touched, with reasons:** `webui/client/src/fixtures/library.ts` (the `Member`/`RemovedMember`
types gain an optional `trace` — the one place those types are declared); `webui/client/src/kit/plots.tsx` and
`charts/scale.ts` (the rule's consumers — the whole point); `webui/smoke.py`, `webui/smoke_pages/{library,review}.json`
(the acceptance check); `library/{RecurrencePage,ImportPage}.tsx`, `review/{Shell,Inspector,ClusterView}.tsx` (each
held one of the literal domains in §2). `scripts/fixup_c_domain_evidence.py` is new: the before/after evidence,
reproducible.

---

## Chat summary

PRD D5 is replaced. There is now exactly one function that decides a plot's y domain —
`webui/client/src/charts/domain.ts::measuredDomain`, run under Node by the headless suite — and Review, the Library
and Explore all go through it: each card is drawn on a domain measured from its own traces, and the page's shared
scale is a logarithmic reference bar beside each card with the card's peak marked on it. D5's percentile domain,
Review's `Y_MV`/`THUMB_Y`, every literal Library/Review domain, `MiniTrace`'s silent clamp and every `clipped`
badge are gone. On the Atlas with every recording declared, 66 traces were pinned along their frame and 38 cards
were badged clipped; now 0 and 0, and smoke measures "no trace leaves its plot box" on eight states (352 traces).

The Family page draws every member's real waveform: the sketch is dropped and the exemplar looks the same
everywhere. That costs the largest family 41 KB → 130 KB and about a tenth of a second, so nothing is decimated.
Review's candidate 100, a flat line on ±400 mV before, is a 12.6 mV drop filling its card. The `drop_motifs10`
population is now legible — 30 of 149 families peak under the 0.1 mV floor, visible at full size and placed low on
the bar — and nothing was added to hide it.

Gate: tsc/build clean; pytest 1775/6/0 (venv: only the known scoreboard failure); smoke 6 failures — prompt A's
four Settings ones and two of prompt D's in-progress states, none from this change.

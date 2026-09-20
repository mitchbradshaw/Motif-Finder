# Status — Analyse › Interrogation (builder)

Last full verification (**fix round 1**): `npx tsc --noEmit -p tsconfig.app.json` clean for
`src/interrogation/*`, `src/api/interrogation.ts`, `src/fixtures/interrogation.ts`;
`smoke.py --pages-only --only interrogation` → **40 screenshots, 0 failures**, 0 browser console errors.

## Fix round 1 (critique `webui/critique/interrogation/r1-*.json`)

**analyse.interrogation.slope** (was 7)
- `units` now recomputes instead of relabelling: `mV · s` is the frame's compressed convention, so every
  time divides by 10 and every slope multiplies by 10 — the anatomy axis, the readout, the per-event
  table and the rose reference all move together, and a `units-note` line states the convention. The
  angle is deliberately unchanged: the slope and the −45° reference scale together.
- Every parameter control (units, marks, the four rules, discard) is disabled while the run veil is up,
  with the shared reason *wait for the run*.
- "Re-run from 01" really runs. The bug was a race: `rerun()` cleared `?state`, and the `[stateQ]` effect
  that clears a *forced* run then reset the run that had just started. `rerun()` clears the flag first.

**analyse.interrogation.aggregate** (was 6)
- Every Parameters control recomputes: binning is a real Freedman–Diaconis / Sturges / fixed-20 rule
  (FD capped at 2√n), the interval definition really moves the interval (and the card prints the median
  so a small move is visible rather than invisible), outliers really drop or winsorise points and the
  fit is recomputed from what is left, the purity check drives its own tile, and the null method drives
  the null samples, the verdict lines, the null β tile and the toolbar chip.
- The fit is `adjustedFit`: the recorded frame fit, moved by what the current parameters actually change
  about the points. Under `MIN_FIT_N` (12) there is no fit at all — F-04's nine events now read
  *exponent β · not fitted*, its verdict lines read *too few to compare with the null*, and the recorded
  interval-CV tile is withheld.
- colour-by keeps the null: `interrogation/NullHistogram.tsx` draws the grey null at full bin width
  behind the stacked per-category bars over the same bins. The old path also mis-read `interval_h` per
  category (it fell through to depth), which is why colour-by re-binned the data.
- The feature wiring is live: slots `h1–h3`, `tl`, `p1–p3` rewire the three histograms, the timeline
  height and the scaling pairs, persist in the draft, mirror into `?wire=h3:peakedness` and reset from
  the popover. A rewired histogram carries no recorded verdict and says so.
- `?state=running` is honoured (veil + Cancel), and every run start clears the forced-run flag and
  raises a toast.

| page | route | status | states | what's left | last commit |
|---|---|---|---|---|---|
| analyse.interrogation | `#/analyse/interrogation` | done | default · source-picker (+ by click) · picker-prior-run · picker-review · picker-explore · swapped (`?family=`) · empty-scope (`?scope=none`, and by clicking "none") · scope-restored · running · failed · save-template · add-stage | the frame's `sort` control drops to a second row at 1440 px | `e4557fd` |
| analyse.interrogation.slope | `#/analyse/interrogation/block/1` | done | default · units-mv-s (`?units=mv-s`) · event-picked · jump-to-flagged · large-family (`?family=F-07`) · large-family-rose · stale-after-edit (`?state=stale`) · stale-discarded · upstream-spike-shape · marks-all · running | the frame's amber onset→trough band is not drawn (kit `LineChart` has no `bands` — see requests) | `7dc2eb7` |
| analyse.interrogation.aggregate | `#/analyse/interrogation/block/2` | done | default · histograms · colour-by-recording (`?colour=recording&pair=depth-maxslope`) · pair-by-click · linear-axes · wired-from-spike-shape (`?upstream=spike-shape`) · feature-wiring (+ by click) · nothing-to-aggregate (`?state=empty`) · small-family (`?family=F-04`) · running (`?state=running`) · null-shuffled (`?null=shuffled`) · outliers-excluded (`?outliers=excluded`) · rewired (`?wire=`) · wiring-reset · stage-outlier | the local `NullHistogram` should be a kit `Histogram` mode (see requests) | `53cd6d8` |

Screenshots for review: `webui/screenshots/build/interrogation/` (gitignored) —
`1-source-default`, `1b-source-picker`, `1c-picker-run`, `1d-swapped-F07`, `1e-empty-scope`, `1f-running`,
`1g-failed`, `2-slope-default`, `2b-slope-large`, `2c-slope-stale`, `3-aggregate-default`,
`3b-aggregate-recording`, `3c-aggregate-spike-wiring`, `3d-aggregate-empty`; the smoke's own are under
`webui/screenshots/pages/analyse.interrogation*`.

Files owned: `webui/client/src/interrogation/*` (index, SourcePage, SlopePage, AggregatePage, SourcePicker,
Rose, EventTimeline, chrome, draft, interrogation.css), `src/api/interrogation.ts`,
`src/fixtures/interrogation.ts`, `webui/smoke_pages/interrogation.json`,
`webui/pages/{status,fog,requests}/interrogation.md`, the three page sections of
`webui/pages/inventory/interrogation-training.md`, `webui/screenshots/build/interrogation/`.

Two things a later builder should know:
- The demo store is module-level, and the smoke harness navigates by hash **without reloading**, so an
  in-memory write made in one state is still there in the next. Every destructive state here is also a deep
  link (`?scope=none`, `?state=empty`) and the click-driven ones sit at the end of the manifest with a
  restoring state after them.
- `?state=running` / `?state=failed` force the shared `useSim`; `draft.ts` keeps a `simForced` flag so the
  next page arriving clears it, otherwise every later state looks busy.

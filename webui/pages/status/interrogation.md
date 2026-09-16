# Status — Analyse › Interrogation (builder)

Last full verification: `npx tsc --noEmit -p tsconfig.app.json` clean for `src/interrogation/*`,
`src/api/interrogation.ts`, `src/fixtures/interrogation.ts`; `smoke.py --pages-only --only interrogation`
→ **34 screenshots, 0 failures**, 0 browser console errors.

| page | route | status | states | what's left | last commit |
|---|---|---|---|---|---|
| analyse.interrogation | `#/analyse/interrogation` | done | default · source-picker (+ by click) · picker-prior-run · picker-review · picker-explore · swapped (`?family=`) · empty-scope (`?scope=none`, and by clicking "none") · scope-restored · running · failed · save-template · add-stage | the frame's `sort` control drops to a second row at 1440 px | `e4557fd` |
| analyse.interrogation.slope | `#/analyse/interrogation/block/1` | done | default · event-picked · jump-to-flagged · large-family (`?family=F-07`) · large-family-rose · stale-after-edit (`?state=stale`) · stale-discarded · upstream-spike-shape · marks-all · running | the frame's amber onset→trough band is not drawn (kit `LineChart` has no `bands` — see requests) | `7dc2eb7` |
| analyse.interrogation.aggregate | `#/analyse/interrogation/block/2` | done | default · histograms · colour-by-recording (`?colour=recording&pair=depth-maxslope`) · pair-by-click · linear-axes · wired-from-spike-shape (`?upstream=spike-shape`) · feature-wiring (+ by click) · nothing-to-aggregate (`?state=empty`) · small-family (`?family=F-04`) · stage-outlier | colour-by re-bins into stacked `Bars`, which loses the grey null behind (kit `Histogram` has no stacked mode) | `53cd6d8` |

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

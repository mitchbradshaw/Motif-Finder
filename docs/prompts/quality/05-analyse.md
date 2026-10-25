# tq-analyse — the Analyse figures' duplicated helpers and state

Package id for commits: `tq-analyse`. Read `docs/prompts/quality/00-common.md` first. The manager already merged one
extent rule: `charts/domain.ts::extentOf` takes typed arrays and has `maxOf`/`minOf`, `kit/extent.ts` is gone, and
`eventFigures.ts::normaliseSeries` imports the extent from `charts/domain.ts`. Build on that.

## The findings

1. **Formatters copied because of the "no imports" rule.**
   - `analyse/fmtNum.ts:4-11`: `fmtNum`'s numeric branch is character for character
     `analyse/views/common.tsx:~60 fmtN`
     (`a >= 1000 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : a >= 0.01 ? v.toFixed(3) : v.toExponential(2)`).
   - `views/EventShapeFigures.tsx:~36` adds a third formatter, `short`.
   - `analyse/pickTemplate.ts:~8` `short` "mirrors TemplatesPopover.tsx's" `shortName` (`TemplatesPopover.tsx:~11`).
   - Remedy: move `fmtN` into the pure `fmtNum.ts` and have `fmtNum` call it after its column rules. `common.tsx`
     re-exports or imports it, and `EventShapeFigures` uses it unless `short` is genuinely different (say why).
     Move `shortName` into the pure `pickTemplate.ts`, and have `TemplatesPopover` import it.
2. **More copies of the extent scan.**
   - `views/common.tsx:~52 finiteRange` (check whether it now equals `extentOf`; if so it becomes a re-export or its
     callers use `extentOf`).
   - `kit/plots.tsx:~83 extent()`.
   - `EventShapeFigures.tsx:~102-110` (the `geom` loop).
   - Use the one rule wherever the semantics match; where they do not (e.g. a different empty answer a caller relies
     on), keep the difference visible at the call site.
3. **The same "marked event" and "legend show/hide" state, written twice with opposite models.**
   Files: `IntervalFigures.tsx:~121-127` and `EventShapeFigures.tsx:~193-203`.
   - Marked event: both write `hover` / `picked` / `mark = hover ?? picked` with a toggle-pick.
   - Legend: IntervalFigures keeps a `hidden` Set. EventShapeFigures keeps `shown: Set | null` (null = default)
     plus a derived memo.
   - Remedy: export `useMarkedEvent()` (`{mark, setHover, pick}`) and `useSeriesToggle(keys, defaults)` from
     `MultiScatter.tsx`, the component both feed.
4. **Duplication inside `EventShapeFigures`.**
   - `MotifOverlay.rank` (~111-113) re-sorts the time `order` that `useMotifs` already built (~46). Return `order`
     from `useMotifs`.
   - `path` (~117) is `charts/scale.ts::polylinePath` with a clamp:
     `polylinePath(a.dt, a.z.map(z => z === null ? null : clamp(z, -6, 6)), x, y)`. Use it if the output is identical.
5. **Explore overlay.**
   - `explore/Overlay.tsx:~235` `g.gains[i]?.pxPerUnit ?? g.pxPerUnit`: `gains.rows` always has one entry per
     channel, so the optionality hides an invariant (verify in `overlayModel.ts`).
   - `explore/overlayModel.ts:~426, ~434`: `Math.min(gainLanes * lane, 0.9 * blockPx)` is computed twice, and its own
     comment says `fitCentre`'s "cannot fit" branch never runs. If so, delete the branch.

Left out on purpose:
- `IntervalFigures`' fallback for payloads without `next_within_gap_s`. Restored jobs persisted before 2026-10-20
  lack the field.
- `registry.tsx`'s `p.rose || isEventShapeTable(...)`.
- The `build:demo` flag in `vite.config.ts` (a decision for the researcher).

## Behaviour that must not change

Every number on screen formats exactly as now, for every column rule in `fmtNum` (`n_` columns, `k`). The overlays
draw the same paths. Marking and legend toggles behave the same, including EventShapeFigures' default-shown set
(three series) and IntervalFigures' all-shown default. Every test id stays.

## Files

`webui/client/src/analyse/fmtNum.ts`, `analyse/views/common.tsx`, `analyse/EventFeatures.tsx`,
`analyse/pickTemplate.ts`, `analyse/TemplatesPopover.tsx`, `analyse/views/EventShapeFigures.tsx`,
`analyse/views/IntervalFigures.tsx`, `analyse/views/MultiScatter.tsx`, `analyse/views/eventFigures.ts`,
`kit/plots.tsx`, `charts/scale.ts` (only if `clamp` is missing), `explore/Overlay.tsx`, `explore/overlayModel.ts`.

Tests: `tests/test_webui_night_b_fmtnum.py`, `tests/test_night_analyse_helpers.py`, `tests/test_night_analyse_payload.py`,
`tests/test_webui_night_b_critic.py`, `tests/test_webui_site_x_cross.py`, `tests/test_webui_plot_domain.py`, and
`grep -rln "fmtNum\|fmtN\b\|shortName\|finiteRange\|overlayModel\|Overlay.tsx\|kit/plots\|MultiScatter" tests/`.
Run them before your first change and record the failure set.

Smoke units for the manager: `zzzzzzzzzzz_night_analyse`, `zzzzzzzzzzz_ig_pages`, `analyse`, `zzzzzzzzzzz_overlay`,
`zzzzzzzzzzz_aq_cross_channel`.

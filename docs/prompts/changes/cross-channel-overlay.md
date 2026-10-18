# cross-channel-overlay — every channel on one tall axis: colours, bold and faded, aligned by lag, a box to act on

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix `overlay:`; every
commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Client-heavy; the one bridge change is
tested first. Runs AFTER `explore-review-actions.md` (it reuses that prompt's action strip).

## Why (the researcher, 2026-10-18)

> Cross-channel might be easier to compare channels on a single axis. Try and do overlay mode well. If it turns out
> well, I might even transfer it to the Discovery page too. I am imagining: each channel has a different colour; you
> can select channels which are bolder, unselected fade to the back; each channel is slightly vertically offset
> (height estimated by mean value, then offset such that CH1 is at the top of the overlaid signals, CH16 at the
> bottom); it can be a tall block. Then, like in the Signal section, the user can grab a box to explore spans across
> the channels. Would need to deal with lag/propagation — channels would have to shift left/right to show alignment.

## Facts (2026-10-18)

- `webui/client/src/explore/CrossChannelPage.tsx:268-367`: one `<svg>` per channel row on one x scale (`px()`,
  shared `ticks`), per-row y via `stackGeom` (`:189`; modes absolute / centred (default) / per-channel), one shared
  axis at the bottom (`:362`), a shared hover crosshair (`:331`); detections and the motif band drawn on the
  reference row only (`:309, :311`). The header says why one absolute y flattens the traces: ~3.9 V of DC offset
  between channels. The page measures each channel's lag and r against the reference (`data.lags`, the detrend
  note at `:273`, the classification card at `:372`). The window is `?t0=&t1=` (`:228`).
- Signal's box selection and its action strip: `explore/SpanView.tsx:212-248` (pan/zoom/brush) and
  `explore/SpanActions.tsx` (made shared by `explore-review-actions`).

## Decided with the researcher (grilling, 2026-10-18)

- **A third view mode of the Cross-channel plot, swapped in place** (`?view=overlay` beside the stacked rows),
  remembered in the address, so the component can be reused on Discovery later.
- **Geometry:** each channel centred on its own mean over the window, stacked by rank with EQUAL offsets (CH1 at
  the top, CH16 at the bottom), a tall block (≥ 28 px per channel, min 420 px); colour per channel from a fixed
  categorical palette (the same colour for the same channel everywhere on the page); **selected channels bold and
  full opacity, unselected faded** (click a name or a trace to toggle; shift-click for several; "all" / "none").
- **Align by lag:** a toggle that shifts each channel by its measured lag against the reference and prints the
  shift beside its name (`+12 s`); off by default; a hand drag is NOT built unless the measured lags prove wrong.
- **A box across the overlay** selects a time window on the selected channels and shows the shared action strip:
  Zoom · Send unjudged to Review · Mark artifact (channels pre-ticked = the bold ones) · Open in Analyse · Open in
  Signal (one channel: the topmost bold one, or a picker when several).
- Detections and the motif band are drawn on EVERY channel in overlay mode (thin caps in the channel's colour), not
  only the reference.

## The work

1. **`explore/Overlay.tsx`** (new): d3 scales, one path per channel (decimated envelope the page already fetches
   per row — reuse the rows' data, do not refetch), the rank offsets, the bold/faded state, the lag shift, the
   brush, the hover readout (time, each bold channel's value). Keyboard: ↑/↓ moves the bold channel, A toggles
   align.
2. **Page wiring:** the `Seg` gains `overlay`; the y-mode control hides in overlay mode; the lag toggle and the
   selection controls sit in the plot header; the action strip appears under the brush.
3. **Bridge (small):** if the rows' envelopes are fetched per channel at a width that is too coarse for a tall
   overlay, `GET /api/explore/cross-channel` gains `px` (it may already have it — check) so the overlay asks at
   its own width. Tested.
4. **Reusable:** export the component with a props-only interface (`channels: {name, colour, t, v, lag_s}[]`,
   `window`, `selected`, `onBrush`) so the Discovery page can mount it later without the page's state.

## Files

Yours: `webui/client/src/explore/Overlay.tsx` (new), `CrossChannelPage.tsx`, `explore.css`, `webui/client/src/api/
explore.ts`, `webui/server/explore_routes.py` only for `px` (say so), `tests/`.

## Method and gate

- Tests (venv) only for the bridge change. Client: `tsc -b`, `vite build`. Smoke in
  `webui/smoke_pages/zzzzzzzzzzz_overlay.json`: `?view=overlay` draws one path per channel in a block ≥ 420 px;
  clicking a name makes it bold and the rest faded (check a `data-bold` attribute); the align toggle changes a
  `data-shift` attribute and the printed shift; a brush shows the action strip.
- Run your files plus `tests/test_webui_explore*.py` if any, `tests/test_import_boundaries.py`.

## Stop and report if

the per-row envelopes are not enough to draw the overlay at a useful resolution and the bridge change would be more
than a `px` parameter.

## Report

`docs/prompts/changes/reports/overlay-report.md`: **Assumed**; a screenshot of the overlay on your synthetic data is
NOT possible in a worktree — describe the geometry in words and numbers; the props interface; smoke states; what is
left (the Discovery mount).

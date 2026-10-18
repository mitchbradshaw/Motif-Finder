# explore-span-plot — the Signal page's bands: the pile at t = 0, kinds you can switch, two greens, editable edges

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix `span-plot:`;
every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first for the bridge bug;
the client work is gated by `tsc`, build and the smoke states.

## Why (the researcher, 2026-10-18)

> In the Explore page, "show detections from ___": all detections in blue bars seem to cluster into the start of the
> signal. Also more generally need a way to toggle "detected", "annotated" etc. bars on the span plot. Also need a
> way to adjust the span plot more directly — fields for the left/right ends of the plot domain that live-update
> with the plot to 3 decimal places (right where the span time already is, but editable). … Separate key colours
> for annotated-interesting and annotated-not-interesting, and likewise separately toggle on/off.

This also closes the older `I` U4 item, Explore's fine span adjustment.

## Facts (2026-10-18)

- **The pile at t = 0.** `corpus.spans` (`webui/server/corpus.py:462`) returns seconds from the channel start for
  annotations and detections (`start_idx / fs`, `:486-489`) after shifting each row with `_absolute` (`:211-219`,
  `:480`), which treats a row as span-relative ONLY when `start_idx < span_start` (`:217`; the same rule in
  `Working/discovery/spans.py:29-31`). A legacy relative row with `start_idx >= span_start`, or a run whose
  `span_start` is 0/NULL while its indices are relative to something else, is left unshifted and lands between 0 and
  the span length. Second suspect: a detector that decimates internally and returns indices at the decimated rate
  (`Working/Detection/cwt_ridges.py`). The client uses `d.start_s` as absolute seconds (`explore/SignalPage.tsx:
  184-186`) and the x scale is the viewport (`SpanView.tsx:188-189`), so the API onwards is clean.
- **A side bug you will hit:** `getSignalDemo` is now `getSignalLive` (`api/explore.ts:120`), so `demo` is set on
  every live channel; the same detections are pushed twice (`SignalPage.tsx:184-193`, from `liveInView` and from
  `demo.detections`), and `liveInView` skips the run filter whenever `demo` is truthy (`:176`).
- **Bands:** fills at `SpanView.tsx:152`, caps `:153`, tokens `theme.css:17-43`: detected (blue), annotated
  (green), selected (amber), artifact (red), grey. Every verdict except `artifact` becomes green `'annotated'`
  (`SignalPage.tsx:182`): interesting and not-interesting share one colour. The legend is static (`SpanView.tsx:
  303`, popover `:309-318`); nothing can be switched off; detections are filtered only by run through the picker.
- **Domain:** pan by drag, wheel, −/+/fit, ← → + − keys (`SpanView.tsx:212-248`), the overview's span box
  (`Overview.tsx:39-59`); kept in app state (`SignalPage.tsx:116-119`), not the hash. No numeric edge field. The
  span text is `<span className="range" data-testid="span-range">{fmtRangeH(a, b)} · {fmtDuration(b - a)}</span>`
  (`SpanView.tsx:259`). Patterns to copy: the click-to-type chip `explore/TimeRange.tsx:1-20`, the numeric
  start/end with steppers in `explore/SpanEditPage.tsx`.

## The work

1. **The pile (bridge, test-first):** find the real cause on a fixture that reproduces it: build runs with
   (a) a legacy relative row whose `start_idx >= span_start`, (b) a run with `span_start` NULL, (c) a decimating
   detector's indices; assert after `_absolute` every detection lies inside `[span_start, span_end]` and at the
   right absolute second. Fix `_absolute` (and `spans.py`'s twin — one rule, imported, not two copies) so a row is
   shifted by what the RUN says (its `span_start` and whether its detector wrote relative indices — the run's
   config/version tells; if the database cannot tell for legacy rows, say so and treat them by the existing
   heuristic with a logged warning per run, once). Then remove the double push and the skipped run filter in
   `SignalPage.tsx`, with a client-side check that a detection at 1000 s draws at `x(1000)` on a view of
   [900, 1100].
2. **Band kinds you can switch:** a legend that is a row of toggles — detected · annotated interesting ·
   annotated not interesting · unsure · artifact · seed — each with its own colour (interesting green,
   not-interesting a distinct muted red-brown or purple from the theme, unsure grey, artifact red, seed the
   existing seed colour if one exists, else teal), each switchable; the state remembered in `localStorage` per
   workspace. The bands and caps read the verdict, not the collapsed `'annotated'`.
3. **Editable edges:** the span text becomes two numeric fields (left and right edge, seconds to three decimals,
   with the hours shown beside) plus the duration; typing moves the view live (debounced 150 ms), the view's
   changes update the fields; arrow keys step by the last digit; invalid input shows the reason in place. Keep
   the keyboard and the overview box working.

## Files

Yours: `webui/server/corpus.py` (`_absolute`), `Working/discovery/spans.py` (the one rule), `webui/client/src/
explore/SignalPage.tsx`, `SpanView.tsx`, `api/explore.ts` (the demo alias), `explore.css`, `theme.css` (one new
token at most), `tests/`.

## Method and gate

- Tests (conda for `spans.py`, venv for `corpus.spans`): the three fixture cases above; a verdict-keyed band list
  (the route already returns the verdict; assert it is not collapsed).
- `tsc -b`, `vite build`. Smoke in `webui/smoke_pages/zzzzzzzzzzz_span_plot.json` (sorted last: it zooms): the
  legend has six toggles; switching "detected" off removes the blue bands (count `rect[data-kind=detected]`);
  typing a right edge moves the view (check `span-range` fields and the x-axis label).
- Run your files plus `tests/test_webui_corpus.py`, `tests/test_webui_explore*.py` if any,
  `tests/test_import_boundaries.py`.

## Stop and report if

legacy rows genuinely cannot be told from absolute ones: then say which runs (by detector and date) and propose a
one-time migration script for the manager to run, rather than guessing in the read path.

## Report

`docs/prompts/changes/reports/span-plot-report.md`: **Assumed**; the real cause of the pile with the fixture that
proved it; the toggle and colour table; tests; smoke states; what is left.

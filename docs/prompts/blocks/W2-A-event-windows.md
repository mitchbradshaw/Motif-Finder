# W2-A — `catalogue.event_windows`: a window around every detected event (the SpanSet → WindowSet bridge)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w2-a:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 7 (the paragraph on `catalogue.event_windows`) and §7.1. Round 1 of wave 2; W2-C (MiniRocket) and W2-E (families)
build on what you deliver, so **your core function is a public API**: name it, document it, keep it stable.

## In plain words

Every window block on the site — clustering, the classifier, window images, and the MiniRocket block being built
beside you — works on a *WindowSet*: equal-length pieces of a recording. Today those pieces come from a fixed grid
(every 10 minutes, say), so an event is usually cut in half or sits at a random place in its window. This block cuts
one window **around each detected event**, lined up on the event (its onset, by default), so every window block can
work on detected events instead of a grid. It also carries each event's measurements (depth, width, recovery…) onto
its window, so clustering on those numbers works the day this lands.

## The block

`catalogue.event_windows`, **SpanSet → WindowSet**. Stage: the one `catalogue.*` blocks use (check
`Working/recipes.py::STAGES`); `category` as the other window producers (check `Adapters/base.py::CATEGORIES`);
`page_name="Event windows"`.

Core: `Working/catalogue/event_windows.py` (or the package the catalogue blocks' cores already live in — grep), a
plain function, e.g. `event_windows(x, fs, spans, *, anchor, length_s, pre_frac, ...) -> (starts_rel, kept_idx,
omitted)` that W2-E can call to cut waveforms for a SpanSet **without** going through a WindowSet.

Parameters (bounds on every one):
- `anchor` — `onset` (default; the `onset_idx` column Event shape writes), `extremum` (`extremum_idx`), or `start`
  (the span start). An event lacking the requested column falls back to its span start **and is counted**; a whole
  SpanSet lacking it says so once in `meta`, in words, naming Event shape as the fix.
- `length_s` — window length; **0 = auto**: twice the median event duration (span `end − start`; or `duration_s`
  when Event shape ran), rounded up to a whole 10 s, clamped to [60 s, 7200 s]. State the rule in `meta["rules"]`.
- `pre_frac` — the share of the window before the anchor (default 0.2).
- the split: `split_rule`, `n_blocks`, `holdout_frac`, `validation_frac`, `seed` exactly as
  `preprocessing.sliding_windows` declares them — **import `assign_split`** from
  `Adapters/preprocessing_sliding_windows.py` (or move it to a core module both import; do not copy it). Blocked by
  time stays the default, so the Classifier downstream gets a leakage-safe split.
- `max_nan_frac` — a window with more NaN than this (default 0.1) is left out, counted.

Output WindowSet:
- `starts` **channel-absolute** (add `round(t[0]·fs)`, exactly as `preprocessing.sliding_windows` does — read
  `WindowSet`'s docstring); `length` in samples; `fs`.
- `features`: every column the SpanSet carried, **plus** `event_index` (the event's row in the input SpanSet),
  `anchor_offset` (samples from window start to the anchor), the split column (`split`), and `overlaps_next` (bool).
  SpanSet `*_idx` columns are span-relative; in a window they mean nothing as they stand — convert each to
  **window-relative** (`<name>_win`, index inside the window; NaN if outside it) and drop the span-relative original,
  and say so in the docstring. Non-numeric columns (`polarity`, `group`) ride unchanged.
- Events whose window would run past either end of the span are left out (WindowSet windows are fixed-length), counted
  by reason (`past_start`, `past_end`, `too_much_nan`). `meta` carries `n_events`, `n_windows`, `omitted` (a dict of
  counts by reason), `n_overlapping`, `length_s`, `anchor_used`, `rules`.

## Deliver

- Core module + `Adapters/catalogue_event_windows.py`.
- Tests `tests/test_event_windows.py` (core) and `tests/test_adapter_event_windows.py`; include the lessons-from-wave-1
  backgrounds (a dense chain of drops 30 min apart on an AR(1) background).
- A template test `tests/test_template_event_clusters.py` with
  `TEMPLATE = {"name": "event_clusters", "kind": "training", ...}` = the `noise_threshold` template's steps (copy them
  from `webui/server/templates.py`; read, do not edit) → `interrogation.event_shape` → `catalogue.event_windows` →
  `catalogue.cluster` (its defaults, on the carried Event-shape features). `kind` is what
  `webui/server/templates.py::kind_for_steps` implies for a Grouping terminal (`training`); check it.
- **The `spanset->windowset` modifier row — handed to you** (the exception in `00-common.md`), because
  `tests/test_block_standard.py` fails any block whose conversion has no row: add it to `webui/server/views.py::MODIFIERS`
  ("each window on the trace around its event, the anchor marked inside it"), map it in
  `webui/client/src/analyse/views/registry.tsx` to the **existing** `WindowSetProcess` component (no new component —
  W2-F refines the drawing), and raise the modifier count in `tests/test_block_standard.py`
  (`test_there_are_thirteen_modifiers…` → fourteen, renaming the test and adding a comment like the fixup-ag one). Those
  three lines are all you touch under `webui/` and in that test file.

## Acceptance

- [ ] Synthetic drops with known onsets: every kept window has its onset at exactly `anchor_offset` samples; starts are
      channel-absolute when the chain ran on a span that does not start at 0 (test with a non-zero span offset).
- [ ] Auto length follows the stated rule; events near the span ends are left out and counted by reason.
- [ ] Event-shape columns survive; `*_idx` become `*_win` correctly; `event_index` maps each window back to its event.
- [ ] The split matches `preprocessing.sliding_windows`' rule for the same starts (same function, same answer).
- [ ] `catalogue.cluster` and `catalogue.window_images` accept the output (run both in a test).
- [ ] An empty SpanSet gives an empty WindowSet with a `meta` that says why, not an error and not a blank.
- [ ] The block passes `tests/test_block_standard.py` and `tests/test_adapter_spec.py` (update the adapter count in
      `tests/test_adapter_spec.py` and `tests/test_end_to_end.py` — the manager reconciles counts across branches).

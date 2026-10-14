> Filed by the manager session, 2026-10-14 08:04 — the final message of implementer agent `a976297f07092286e`
> (branch `worktree-agent-a976297f07092286e`), verbatim.

## W2-A — `catalogue.event_windows` (SpanSet → WindowSet): report

Note on the base: my worktree started at 3cc2f62, which is behind 04948e3 and is an ancestor of it. I fast-forwarded the branch to 04948e3 (`git merge --ff-only`, so no merge commit) before doing anything else. My two commits sit on top of 04948e3.

### 1. In plain words
Until now, every block that works on equal-length pieces of a recording (clustering, the classifier, window images, and MiniRocket next) cut those pieces from a fixed grid, like slicing bread every 10 minutes whatever is in the loaf. An event usually ended up split across two slices, or sat at a random spot in its slice. This block cuts one slice **per detected event** instead, positioned so the event's onset is always the same distance into the slice: 20 % of the way in by default. Each slice also carries that event's measurements (depth, width, recovery and so on), so a clustering block can group events by shape straight away.

On synthetic data:
- On four backgrounds (white noise, a detrended random walk, AR(1) with φ = 0.97, and a slow sine drift), every kept window has its onset at exactly `anchor_offset` samples.
- A chain of 40 drops 30 min apart on the AR(1) background kept all 40 windows. The auto length came out at 1200 s, and no windows overlapped.
- Running the new `event_clusters` template end to end on drops of three depths (8, 20 and 45 mV) found all 15 events. Ward clustering with k = 3 put each depth class in its own cluster.
- Events too close to either end of the span, and windows with too many missing samples, are left out and counted by reason. An empty SpanSet gives an empty WindowSet whose `meta` says why.

### 2. Files
- created `Working/Catalogue/event_windows.py`: the core, a public API. It lives in the existing `Working/Catalogue` package, not a new `Working/catalogue/` (Windows paths are case-insensitive, so that name would land in the same folder anyway).
- created `Adapters/catalogue_event_windows.py`: the adapter.
- created `tests/_event_windows_synthetic.py`: the synthetic backgrounds and drops.
- created `tests/test_event_windows.py` (core), `tests/test_adapter_event_windows.py`, `tests/test_template_event_clusters.py`.
- modified `webui/server/views.py`: the `spanset->windowset` row added to MODIFIERS.
- modified `webui/client/src/analyse/views/registry.tsx`: `'spanset->windowset': WindowSetProcess`.
- modified `tests/test_block_standard.py`: the modifier test now expects fourteen (renamed `test_there_are_fourteen_modifiers…`, with a comment).
- modified `tests/test_adapter_spec.py` and `tests/test_end_to_end.py`: adapter count 49 → 50.
- **modified, outside my file list:** `Adapters/catalogue_cluster.py` and `Adapters/catalogue_classifier.py`. Both now drop `NOT_FEATURES` = (`split`, `event_index`, `anchor_offset`, `overlaps_next`) instead of only `split`. Without this, `event_index` (which simply counts events in time order) becomes a clustering or classifier feature and leaks time. The cluster test pins this: with the change, `n_features == 1` on a set where only the amplitude varies.

### 3. The algorithm as implemented
Public surface: `event_windows(x, fs, spans, *, anchor, length_s, pre_frac, max_nan_frac)` returns `EventWindows`, a NamedTuple with `starts, kept, omitted, length, anchor_offset, length_s, anchor_used, n_fallback, omitted_rows, length_basis, notes`. Alongside it: `cut(x, starts, length)` gives the (n, L) waveforms, plus `window_features`, `auto_length_s`, `overlaps_next`, `rules` and `NOT_FEATURES`. The core works span-relative (index 0 = the first sample the chain ran over) and imports no adapter.

The prompt suggested a 3-tuple return; I made it a NamedTuple with named fields, so W2-C and W2-E read attributes rather than unpacking.

1. **Anchor.** Uses `onset_idx`, `extremum_idx` or the span start, rounded to a sample. An event with NaN in that column falls back to its span start and is counted. If the column is missing entirely, one note in words names Event shape as the fix.
2. **Length.** `length_s = 0` means auto: 2 × the median of Event shape's finite `duration_s` (else the median span length), rounded up to a whole 10 s, clamped to [60, 7200] s. With no events there is no median, so it uses the 60 s floor. A length under 2 samples raises an error.
3. **Placement.** `anchor_offset = round(pre_frac·L)`, the same for every window.
4. **Left out.** Checked in the order `past_start`, `past_end`, `too_much_nan` (more NaN than `max_nan_frac`); each event is counted once. The rows left out are listed in `omitted_rows`.
5. **Order.** Kept windows are sorted by start; `event_index` maps each back to its input row.
6. **Overlap.** `overlaps_next` is true when the next window starts before this one ends.
7. **Columns.** Each `<name>_idx` column becomes `<name>_win`, the index inside the window, NaN when outside it (never clipped); the `_idx` original is dropped. All other columns ride unchanged (including `group` and `polarity`). The SpanSet's `scores` and `labels` ride as `span_score` and `span_label`; that is my addition.
8. **Adapter.** Adds `round(t[0]·fs)` to make starts channel-absolute. The split uses `assign_split` imported from `preprocessing_sliding_windows` (it is the same function object, and a test checks that), with span-relative starts and `len(x)`. A random split needs `allow_random_split`, as in sliding windows.

There is no paper to deviate from. Deviations from the prompt:
- the extra columns `span_score`/`span_label`;
- an `allow_random_split` parameter, to match sliding windows;
- a `meta["n_split_leaks"]` count: overlapping windows with different train/test roles share samples. Unlike sliding windows this block cannot refuse overlap, so it counts it instead.

### 4. Tests
- **Red:** `146845d`. 7 failed, 211 passed, 12 errors. The core import failed, the adapter was unknown, the template steps were unknown, and the modifier and adapter counts were wrong.
- **Green:** `24459c7`. The three new files: 37 passed. Block_standard, adapter_spec, import_boundaries, templates, end_to_end, sliding_windows, manual_labels, the grouping and model adapters and webui_block_views together: 288 passed, 4 skipped.
- **Two test fixes after the red commit:**
  - one test built a SpanSet with its end before its start;
  - the template's drops were deepened from 4/12/30 mV to 8/20/45 mV, because the noise_threshold steps do not find a 4 mV drop on that background.
- **What the tests pin:**
  - the onset sits at exactly `anchor_offset` on all four backgrounds;
  - the extremum and start anchors;
  - per-event fallback counted, and the whole-set note naming Event shape;
  - the auto rule (rounding, both clamps, prefers `duration_s`, non-1 Hz sampling);
  - `past_start`/`past_end`/`too_much_nan` counts and rows;
  - a window longer than the span gives counts, not an error;
  - the empty set;
  - parameter checks;
  - `_idx` → `_win`, NaN outside the window;
  - columns carried, including non-numeric ones;
  - overlap in a 10-min chain and none in a 30-min chain;
  - out-of-order input spans;
  - a 40-event dense chain;
  - the rules text;
  - the core imports no adapter or UI;
  - the adapter's spec and bounds;
  - channel-absolute starts at offset 50 000;
  - the split equals `assign_split` for three different settings;
  - a random split is refused;
  - the meta fields and summary;
  - an empty WindowSet;
  - the derive readout;
  - cluster, classifier feature matrix and window_images accept the output;
  - the step cache round-trip (the `overlaps_next` bool survives the round trip);
  - the template end to end: depth classes map one-to-one onto clusters, and a non-zero span gives channel-absolute anchors within 60 s of the planted onsets.

### 5. Integration snippets
**Template** (verbatim from `tests/test_template_event_clusters.py`; its `kind` matches what `kind_for_steps` implies, which is asserted):
```python
{
    "name": "event_clusters", "kind": "training", "version": 1,
    "description": "Detected events grouped by their shape measures: baseline removal → noise threshold (every "
                   "stretch more than 4 σ_n below the detrended trace's median, as the noise_threshold template) → "
                   "Event shape (amplitude, width, duration, FWHM, recovery, slopes per event) → Event windows (one "
                   "window around each event, its onset 20 % of the way in; length twice the median event "
                   "duration; a blocked-by-time split) → Hierarchical cluster (Ward, k = 3) on the measures each "
                   "window carries. Set k first: it is how many kinds of event you expect.",
    "steps": [
        _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
        _step("detection", "noise_threshold", {"k_sigma": 4.0, "direction": "below",
                                               "min_duration_s": 30.0, "merge_gap_s": 60.0}),
        _step("interrogation", "event_shape", {}),
        _step("catalogue", "event_windows", {}),
        _step("catalogue", "cluster", {}),
    ],
}
```
**Glyph** (`BY_NAME['catalogue.event_windows']`, 44 × 26): a grey trace across the full width with two dips (around x = 14 and x = 32). Around each dip, a blue rectangle outline about 12 wide, from y = 4 to y = 22. Inside each rectangle, a short amber vertical tick at about 20 % of its width, which is the anchor, sitting at the dip's onset.

**Smoke state:** the `event_clusters` template on the smoke recording, stopped at step 3 (`catalogue.event_windows`). The pane should show a non-zero window count and `meta.summary` (for example "N of M event(s) windowed, L s each"), and the WindowSet view should paint.

**COSTED:** none. The block is O(n_events × L) and needs no estimate.

### 6. Open questions and risks
- **The view row is still a stand-in.** `WindowSetProcess` draws a WindowSet the generic way; it does not yet mark the anchor or the reasons for omission. That is W2-F's job. The data it needs is all in `meta`: `anchor_offset`, `omitted_rows`, `n_overlapping`, `n_split_leaks`.
- **The client type-check (`npx tsc -b`) was not run**, because this worktree has no `node_modules`. The change is a single mapping line pointing at an existing component.
- **The auto length can be shorter than the event.** On noise_threshold spans, Event shape's `duration_s` measured about 70 s for drops whose recovery constant is 200 s, so auto picked a 150 s window that does not contain the whole recovery. Please check on real data (M2_aug rec 3 at 500–530 h; L_LM_Jul_26_J at 380–480 h) whether auto lengths contain the recovery. If they don't, the rule might be better based on `recovery_time_s`, or a larger multiplier.
- **Onsets land late.** In the template, Event shape put the onset 8–14 s after the planted onset, at the threshold crossing, because the noise-threshold span begins there. That is upstream behaviour, not this block's, but it shifts every anchor. Worth checking on real drops.
- **Split leaks on dense stretches.** In dense chains, windows overlap and can straddle a train/test boundary. This is counted (`n_split_leaks`) but not refused. The researcher may want a "refuse when the split leaks" option before the classifier is trained on event windows.
- **I widened two shipped blocks.** `NOT_FEATURES` in cluster and classifier is outside my brief; please confirm. W2-C and other future feature consumers should import `NOT_FEATURES` from `Working.Catalogue.event_windows`.
- **RQ files were not updated**, because `docs/rq_roundA/` is on the do-not-touch list. This block affects RQ2/RQ3-style "families of events" questions; the manager should note it there.

### 7. Commits
```
24459c7 w2-a: catalogue.event_windows - a window around every detected event (SpanSet -> WindowSet)
146845d w2-a: tests - catalogue.event_windows, a window around every detected event
```

"""
event_windows.py
=================
A window around every detected event: the geometry under `catalogue.event_windows`
(SpanSet -> WindowSet), the bridge that lets every window block (Cluster, Classifier,
Window images, MiniRocket) work on **detected events** instead of a fixed grid
(`docs/research/analysis-blocks-from-literature.md` §5 row 7, §7.1).

**This is a public API.** W2-C (MiniRocket) and W2-E (families) call it to cut
waveforms for a SpanSet without going through a WindowSet. The stable surface:

* `event_windows(x, fs, spans, *, anchor, length_s, pre_frac, max_nan_frac)` ->
  `EventWindows` (a NamedTuple: `starts`, `kept`, `omitted`, `length`,
  `anchor_offset`, `length_s`, `anchor_used`, `n_fallback`, `omitted_rows`,
  `length_basis`, `notes`);
* `cut(x, starts, length)` -> the `(n_windows, length)` waveforms;
* `window_features(spans, ew)` -> the per-window table (`split` is NOT in it: the
  split is the adapter's, from `preprocessing.sliding_windows.assign_split`);
* `auto_length_s(spans, fs)`, `duration_unmeasured(spans)`, `recovery_outside(spans, ew)`,
  `overlaps_next(starts, length)`, `rules(...)`;
* `NOT_FEATURES` - the bookkeeping columns a feature consumer must drop.

Index frames. Everything here is in the frame of `x`, i.e. **span-relative**, like a
SpanSet's `starts` and its `*_idx` columns (`docs/BLOCK_INTEGRATION.md` §1). The
WindowSet convention is channel-absolute; the adapter adds `round(t[0] * fs)` to the
starts, as `preprocessing.sliding_windows` does. A caller that only cuts waveforms
never needs the channel frame.

The rules (all printed by `rules()` into the block's meta):

1. **Anchor.** Each event's anchor is its `onset_idx` (`anchor="onset"`, the column
   Event shape writes), its `extremum_idx` (`"extremum"`) or its span start
   (`"start"`). An event whose anchor column holds NaN falls back to its span start
   and is counted (`n_fallback`); a SpanSet with no such column at all falls back for
   every event and says so once, in words, naming Event shape as the fix (`notes`).
   A fractional index (Event shape's are floats) is rounded to the nearest sample.
2. **Length.** `length_s > 0` is taken as given. `length_s = 0` (auto) is twice the
   median event duration, rounded UP to a whole 10 s, clamped to [60 s, 7200 s]. The
   duration is Event shape's `duration_s` when that column holds at least one finite
   value, else the span length `(end - start) / fs`. With no events there is no
   median: the floor, 60 s.
   **What it covers.** Event shape's `duration_s` runs onset -> *half recovery*
   (`recovery_frac = 0.5`), so with `pre_frac = 0.2` the default window holds the
   onset, the trough and about the first half of the recovery - **not** the return
   to baseline. The multiplier 2 is a **placeholder** until it is checked against
   real recoveries (the critic measured 35-90 % of the depth still missing at the
   window's end for recovery constants of 50-1200 s on synthetic drops). Set
   `length_s` when the whole recovery matters (a waveform consumer: window images,
   MiniRocket, families). Clustering on the carried measures is unaffected: Event
   shape measured those on the span, not on the window.
   **Unmeasured durations.** A NaN `duration_s` is an event that never reached half
   recovery inside its measuring window - longer than measurable, not absent. It is
   counted (`n_duration_unmeasured`) and enters the median as longer than every
   finite duration; when more than half are NaN the median is "longer than
   measurable" and the length is the ceiling. Only when none is finite do the span
   lengths stand in.
   **Coverage reported.** `recovery_outside(spans, ew)` counts the kept windows whose
   recovery point (`recovery_idx`) lies outside them (or was never found); the
   adapter warns when that is more than a quarter of the windows.
3. **Placement.** `anchor_offset = round(pre_frac * length)` samples precede the
   anchor; the window is `[anchor - anchor_offset, anchor - anchor_offset + length)`.
   The offset is the same for every window, so the anchor sits at one column of the
   stacked waveforms.
4. **Left out, counted by reason.** A window that would start before the span
   (`past_start`) or end after it (`past_end`) - a WindowSet's windows are all one
   length, so an edge event cannot be padded without inventing samples - and a window
   whose NaN fraction exceeds `max_nan_frac` (`too_much_nan`). Checked in that order;
   each event is counted once.
5. **Order.** Kept windows come out sorted by start (stable), so a window set reads in
   time order whatever order the spans arrived in; `kept[i]` is the input row of
   window `i` (`event_index` in the table).
6. **Overlap.** Windows around events closer together than one window length share
   samples; nothing is refused for it (a dense chain of drops is the common case on
   these recordings), but `overlaps_next[i]` says whether the next window in time
   starts before window `i` ends.
7. **`*_idx` -> `*_win`.** A SpanSet's index columns are span-relative and mean
   nothing inside a window as they stand: each `<name>_idx` becomes `<name>_win`, the
   index inside the window (`idx - window start`), NaN when it falls outside
   `[0, length)` (never clipped), and the span-relative original is dropped. Every
   other column rides unchanged, non-numeric ones (`group`) included; the SpanSet's
   `scores` and `labels` ride as `span_score` / `span_label`.

Why not reuse. `preprocessing.sliding_windows.plan_windows` plans a fixed grid (and
refuses overlap, P12) - a different geometry. `Working/training/windows.py` cuts
grid windows for the training pool from the database. `Pipelines/drop_motifs`
cuts snippets around its own detections with its own (report-only) conventions.
None anchors a fixed-length window on an arbitrary SpanSet's measured onset.
"""

from typing import NamedTuple, Optional

import numpy as np
import pandas as pd

ANCHORS = ("onset", "extremum", "start")
ANCHOR_COLUMN = {"onset": "onset_idx", "extremum": "extremum_idx", "start": None}
OMIT_REASONS = ("past_start", "past_end", "too_much_nan")

#: Columns that describe where a window sits, never what the event looks like. A
#: consumer that treats a window set's table as features (`catalogue.cluster`,
#: `catalogue.classifier`) drops them: `event_index` is a time order and `split` the
#: train/test role, so a clustering that saw either would recover time or the split.
NOT_FEATURES = ("split", "event_index", "anchor_offset", "overlaps_next")

AUTO_MULT = 2.0
AUTO_ROUND_S = 10.0
AUTO_MIN_S = 60.0
AUTO_MAX_S = 7200.0

DEFAULT_PRE_FRAC = 0.2
DEFAULT_MAX_NAN_FRAC = 0.1


class EventWindows(NamedTuple):
    """The windows cut around a SpanSet's events, in the frame of `x` (span-relative).

    starts : int64 array, one per kept window, sorted
    kept : int64 array, the input SpanSet row of each window (`event_index`)
    omitted : dict reason -> count, every reason in `OMIT_REASONS` present
    length : int, samples
    anchor_offset : int, samples from a window's start to its anchor
    length_s : float, the window length in seconds (as asked, or the auto rule's)
    anchor_used : str, `"onset_idx"`, `"extremum_idx"` or `"span start"`
    n_fallback : int, events whose anchor fell back to their span start
    omitted_rows : dict reason -> list of input rows left out for it
    length_basis : str, what the length came from, in words
    notes : tuple of str, whole-set statements (an empty set, a missing anchor column)
    n_duration_unmeasured : int, events whose Event-shape duration_s is NaN (fix round 1)
    """
    starts: np.ndarray
    kept: np.ndarray
    omitted: dict
    length: int
    anchor_offset: int
    length_s: float
    anchor_used: str
    n_fallback: int
    omitted_rows: dict
    length_basis: str
    notes: tuple
    n_duration_unmeasured: int = 0


def _features(spans):
    f = getattr(spans, "features", None)
    return None if f is None else f.reset_index(drop=True)


def duration_unmeasured(spans):
    """Events whose Event-shape `duration_s` is NaN (never reached half recovery);
    0 when the column is absent (nothing was measured, so nothing went unmeasured)."""
    f = _features(spans)
    if f is None or "duration_s" not in f.columns:
        return 0
    return int((~np.isfinite(pd.to_numeric(f["duration_s"], errors="coerce").to_numpy(dtype=float))).sum())


def auto_length_s(spans, fs):
    """`(length_s, basis)` by the auto rule (module docstring, rule 2). A NaN
    `duration_s` enters the median as longer than every finite one."""
    f = _features(spans)
    durations = None
    basis = None
    if f is not None and "duration_s" in f.columns:
        d = pd.to_numeric(f["duration_s"], errors="coerce").to_numpy(dtype=float)
        n_nan = int((~np.isfinite(d)).sum())
        if n_nan < d.size:
            durations = np.where(np.isfinite(d), d, np.inf)
            basis = (f"Event shape's duration_s, onset -> half recovery (median of {d.size}, {n_nan} unmeasured "
                     f"counted as longer than every measured one)")
    if durations is None:
        d = (np.asarray(spans.ends, dtype=float) - np.asarray(spans.starts, dtype=float)) / float(fs)
        if d.size:
            durations, basis = d, f"the span length, end - start (median of {d.size})"
            if f is not None and "duration_s" in f.columns:
                basis += f"; Event shape's duration_s was unmeasured for all {d.size}"
    if durations is None:
        return AUTO_MIN_S, "no events, so no median: the floor"
    med = float(np.median(durations))
    if not np.isfinite(med):
        return AUTO_MAX_S, (f"{basis}: the median is longer than measurable (most events never reached half "
                            f"recovery) -> the ceiling, {AUTO_MAX_S:g} s")
    raw = AUTO_MULT * med
    length = float(np.ceil(raw / AUTO_ROUND_S - 1e-9) * AUTO_ROUND_S)
    length = float(min(AUTO_MAX_S, max(AUTO_MIN_S, length)))
    return length, f"{basis}: {med:.4g} s; x {AUTO_MULT:g} (a placeholder) = {raw:.4g} s -> {length:g} s"


def recovery_outside(spans, ew):
    """Kept windows whose recovery point (`recovery_idx`, span-relative) lies outside
    the window or was never found; None when the SpanSet carries no `recovery_idx`
    (not measured is not the same statement as none outside)."""
    f = _features(spans)
    if f is None or "recovery_idx" not in f.columns:
        return None
    kept = np.asarray(ew.kept, dtype=np.int64)
    rec = pd.to_numeric(f["recovery_idx"], errors="coerce").to_numpy(dtype=float)[kept]
    rel = rec - np.asarray(ew.starts, dtype=float)
    inside = np.isfinite(rel) & (rel >= 0) & (rel < ew.length)
    return int((~inside).sum())


def overlaps_next(starts, length):
    """Per window (in the given order, which must be sorted): does the next window
    start before this one ends? The last window has no next one: False."""
    s = np.asarray(starts, dtype=np.int64)
    out = np.zeros(len(s), dtype=bool)
    if len(s) > 1:
        out[:-1] = s[1:] < s[:-1] + int(length)
    return out


def _anchors(spans, anchor):
    starts = np.asarray(spans.starts, dtype=float)
    n = len(starts)
    col = ANCHOR_COLUMN[anchor]
    f = _features(spans)
    notes = []
    if col is None:
        return starts.astype(np.int64), 0, "span start", notes
    if f is None or col not in f.columns:
        if n:
            notes.append(f"the SpanSet carries no {col} column, so every event is anchored on its span start "
                         f"instead of its {anchor}: put Event shape before this block to measure each event's "
                         f"{anchor}.")
        return starts.astype(np.int64), n, "span start", notes
    a = pd.to_numeric(f[col], errors="coerce").to_numpy(dtype=float)
    missing = ~np.isfinite(a)
    a = np.where(missing, starts, a)
    return np.rint(a).astype(np.int64), int(missing.sum()), col, notes


def event_windows(x, fs, spans, *, anchor="onset", length_s=0.0, pre_frac=DEFAULT_PRE_FRAC,
                  max_nan_frac=DEFAULT_MAX_NAN_FRAC):
    """One fixed-length window around each event of `spans`, in the frame of `x`.

    Parameters
    ----------
    x : array, the trace the spans index (the chain's span)
    fs : float, Hz
    spans : SpanSet (span-relative starts / ends / `*_idx` columns)
    anchor : `"onset"` | `"extremum"` | `"start"`
    length_s : float, seconds; 0 = auto (rule 2)
    pre_frac : float in [0, 1), the share of the window before the anchor
    max_nan_frac : float in [0, 1], a window with more NaN than this is left out

    Returns `EventWindows`. Never raises for an empty SpanSet or for windows that all
    fall outside the span - those are counted; it raises `ValueError` for a parameter
    outside its range or a length under two samples.
    """
    if anchor not in ANCHORS:
        raise ValueError(f"anchor={anchor!r}; use one of {ANCHORS}")
    if not (0.0 <= float(pre_frac) < 1.0):
        raise ValueError(f"pre_frac={pre_frac} must be in [0, 1): the share of the window before the anchor")
    if not (0.0 <= float(max_nan_frac) <= 1.0):
        raise ValueError(f"max_nan_frac={max_nan_frac} must be in [0, 1]")
    if length_s is None or float(length_s) < 0:
        raise ValueError(f"length_s={length_s}; give seconds, or 0 for the auto rule")
    x = np.asarray(x, dtype=float)
    n = len(x)
    n_events = len(spans.starts)
    notes = []
    if float(length_s) == 0.0:
        length_s, basis = auto_length_s(spans, fs)
    else:
        length_s, basis = float(length_s), "as set"
    length = int(round(float(length_s) * float(fs)))
    if length < 2:
        raise ValueError(f"length_s={length_s} at fs={fs} is {length} sample(s); a window needs at least 2.")
    offset = int(round(float(pre_frac) * length))
    if n_events == 0:
        notes.append("the SpanSet holds no events, so there is nothing to cut a window around: the window set is "
                     "empty. Loosen the detector upstream, or check the span holds events.")
    anchors, n_fallback, anchor_used, anchor_notes = _anchors(spans, anchor)
    notes.extend(anchor_notes)

    win_starts = anchors - offset
    rows = {r: [] for r in OMIT_REASONS}
    keep = []
    nan = np.isnan(x)
    csum = np.concatenate([[0], np.cumsum(nan, dtype=np.int64)])
    for i, s in enumerate(win_starts):
        if s < 0:
            rows["past_start"].append(i)
        elif s + length > n:
            rows["past_end"].append(i)
        elif (csum[s + length] - csum[s]) / length > float(max_nan_frac):
            rows["too_much_nan"].append(i)
        else:
            keep.append(i)
    keep = np.asarray(keep, dtype=np.int64)
    order = np.argsort(win_starts[keep], kind="stable") if keep.size else keep
    kept = keep[order]
    if n_events and not kept.size:
        notes.append(f"every one of the {n_events} event(s) was left out "
                     f"({', '.join(f'{r} {len(v)}' for r, v in rows.items() if v)}): the window "
                     f"({length_s:g} s) does not fit around them inside this span.")
    return EventWindows(
        starts=win_starts[kept].astype(np.int64), kept=kept, omitted={r: len(v) for r, v in rows.items()},
        length=length, anchor_offset=offset, length_s=float(length_s), anchor_used=anchor_used,
        n_fallback=int(n_fallback), omitted_rows=rows, length_basis=basis, notes=tuple(notes),
        n_duration_unmeasured=duration_unmeasured(spans))


def cut(x, starts, length):
    """The `(n_windows, length)` waveforms of `x` at `starts` (frame of `x`)."""
    x = np.asarray(x, dtype=float)
    s = np.asarray(starts, dtype=np.int64)
    if not len(s):
        return np.empty((0, int(length)), dtype=float)
    return x[s[:, None] + np.arange(int(length))[None, :]]


def window_features(spans, ew: EventWindows, extra: Optional[dict] = None):
    """The per-window table (rule 7): the SpanSet's columns for each kept event, its
    `*_idx` columns window-relative as `*_win`, plus `event_index`, `anchor_offset`
    and `overlaps_next`. `extra` columns (the adapter's `split`) are appended."""
    kept = np.asarray(ew.kept, dtype=np.int64)
    starts = np.asarray(ew.starts, dtype=np.int64)
    f = _features(spans)
    out = f.iloc[kept].reset_index(drop=True) if f is not None else pd.DataFrame(index=range(len(kept)))
    for c in [c for c in out.columns if isinstance(c, str) and c.endswith("_idx")]:
        rel = pd.to_numeric(out[c], errors="coerce").to_numpy(dtype=float) - starts
        rel = np.where((rel >= 0) & (rel < ew.length), rel, np.nan)
        out = out.drop(columns=[c])
        out[c[: -len("_idx")] + "_win"] = rel
    if spans.scores is not None:
        out["span_score"] = np.array([np.nan if spans.scores[k] is None else float(spans.scores[k]) for k in kept],
                                     dtype=float)
    if spans.labels is not None:
        out["span_label"] = [spans.labels[k] for k in kept]
    out = out.drop(columns=[c for c in NOT_FEATURES if c in out.columns])
    out["event_index"] = kept
    out["anchor_offset"] = np.full(len(kept), int(ew.anchor_offset), dtype=np.int64)
    out["overlaps_next"] = overlaps_next(starts, ew.length)
    for k, v in (extra or {}).items():
        out[k] = v
    return out


def rules(*, anchor="onset", pre_frac=DEFAULT_PRE_FRAC, max_nan_frac=DEFAULT_MAX_NAN_FRAC, length_s=0.0,
          length_basis=None):
    """The rule behind every number this block puts on a window, as printed in meta."""
    col = ANCHOR_COLUMN[anchor] or "the span start"
    length_rule = (f"{float(length_s):g} s, as set" if length_s else
                   f"auto: twice the median event duration (Event shape's duration_s when it ran - onset to half "
                   f"recovery, an unmeasured one counted as longer than every measured one - else the span length "
                   f"end - start), rounded up to a whole {AUTO_ROUND_S:g} s, clamped to [{AUTO_MIN_S:g} s, "
                   f"{AUTO_MAX_S:g} s]. It covers the onset, the trough and about the first half of the recovery, "
                   f"not the return to baseline; the multiplier {AUTO_MULT:g} is a placeholder until checked on real "
                   f"recordings - set length_s when the whole recovery matters")
    if length_basis:
        length_rule += f" ({length_basis})"
    return [
        {"name": "length", "rule": length_rule},
        {"name": "anchor", "rule": f"{anchor}: each window is placed on the event's {col}, rounded to a sample; "
                                   f"an event with no value there falls back to its span start and is counted"},
        {"name": "anchor_offset", "rule": f"round({float(pre_frac):g} x length) samples of the window precede the "
                                          f"anchor, the same for every window"},
        {"name": "left out", "rule": f"a window that would start before the span (past_start) or end after it "
                                     f"(past_end) - every window is one length, so an edge event is not padded - "
                                     f"or holds more than {float(max_nan_frac):g} NaN (too_much_nan); counted "
                                     f"by reason"},
        {"name": "*_win", "rule": "each span-relative <name>_idx column becomes <name>_win, the index inside the "
                                  "window (NaN when outside it, never clipped); the _idx original is dropped"},
        {"name": "overlaps_next", "rule": "the next window in time starts before this one ends (events closer "
                                          "together than one window length share samples)"},
        {"name": "event_index", "rule": "the event's row in the input SpanSet; windows are in time order"},
    ]

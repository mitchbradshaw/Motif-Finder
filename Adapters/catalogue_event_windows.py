"""
catalogue_event_windows.py
============================
`catalogue.event_windows` — SpanSet -> WindowSet (w2-a): one fixed-length window
around every detected event, lined up on the event (its onset by default), so every
window block — Hierarchical cluster, Classifier, Window images, MiniRocket — works on
detected events instead of a fixed grid. Each window carries its event's measures
(Event shape's amplitude, width, recovery, ...) as its feature row, so clustering on
those numbers works without a feature block in between.

The work is `Working.Catalogue.event_windows` (the public core W2-C and W2-E import);
this file maps the chain onto it and adds the two things a WindowSet needs that a
waveform cutter does not:

* **channel-absolute starts** — the core's starts are span-relative (the SpanSet's
  frame); `round(t[0] * fs)` is added here exactly as `preprocessing.sliding_windows`
  does (`Working/types/windowset.py`);
* **the split** — `assign_split` imported from `preprocessing.sliding_windows`, not
  copied, called with the same arguments (span-relative starts, `len(x)`), so the same
  starts get the same roles. Blocked by time is the default and a random split needs
  `allow_random_split`, as there. Unlike a sliding grid, event windows may overlap
  (a dense chain of drops): a window that shares samples with a neighbour of a
  different role is a leak, and is counted in `meta["n_split_leaks"]`, not refused.

Index convention: the SpanSet's `*_idx` columns are span-relative and become
window-relative `*_win` columns (NaN outside the window); the `_idx` originals are
dropped — see the core's rule 7.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.preprocessing_sliding_windows import SPLIT_COLUMN, SPLIT_NAMES, assign_split
from Adapters.registry import register
from Working.Catalogue import event_windows as EW
from Working.types import SpanSet, WindowSet

NAME = "catalogue.event_windows"
#: more than this share of the windows ending before their event recovered -> a warning naming length_s
RECOVERY_WARN_FRAC = 0.25


def _require(value):
    if value is None:
        raise ValueError(f"{NAME} requires a SpanSet input from a prior step (input_kind='spanset'): "
                         "put a detector before it.")
    if not isinstance(value, SpanSet):
        raise ValueError(f"{NAME} cuts a window around each span of a SpanSet; got {type(value).__name__}. "
                         "Put a detector (a block that emits spans) before it.")
    return value


def _check_split(split_rule, allow_random_split):
    if split_rule == "random" and not allow_random_split:
        raise ValueError(
            "split_rule='random' leaks autocorrelated neighbours between train and test (B7/P12); "
            "use blocked_by_time, or set allow_random_split=True to accept that explicitly.")


def _split_leaks(starts, length, labels):
    """Windows that share samples with a later window of a DIFFERENT role (starts sorted)."""
    s = np.asarray(starts, dtype=np.int64)
    n = 0
    for i in range(len(s)):
        j = i + 1
        while j < len(s) and s[j] < s[i] + length:
            if labels[j] != labels[i]:
                n += 1
                break
            j += 1
    return n


def _summary(n_events, ew):
    left = sum(ew.omitted.values())
    why = ", ".join(f"{r} {c}" for r, c in ew.omitted.items() if c)
    return (f"{len(ew.starts)} of {n_events} event(s) windowed, {ew.length_s:g} s each"
            + (f"; {left} left out ({why})" if left else ""))


def _run(x, t, fs, anchor="onset", length_s=0.0, pre_frac=EW.DEFAULT_PRE_FRAC, max_nan_frac=EW.DEFAULT_MAX_NAN_FRAC,
         split_rule="blocked_by_time", n_blocks=5, holdout_frac=0.2, validation_frac=0.0, allow_random_split=False,
         seed=0, value=None):
    spans = _require(value)
    _check_split(split_rule, allow_random_split)
    x = np.asarray(x)
    ew = EW.event_windows(x, fs, spans, anchor=anchor, length_s=length_s, pre_frac=pre_frac,
                          max_nan_frac=max_nan_frac)
    labels, blocks = assign_split(ew.starts, len(x), split_rule, n_blocks, holdout_frac, validation_frac, seed)
    feats = EW.window_features(spans, ew, extra={SPLIT_COLUMN: labels})
    span_start = int(round(float(t[0]) * fs)) if t is not None and len(t) else 0
    ws = WindowSet(starts=ew.starts + span_start, length=ew.length, fs=float(fs), features=feats)
    n_events = len(spans.starts)
    n_rec_out = EW.recovery_outside(spans, ew)
    warnings = []
    if n_rec_out is not None and len(ew.starts) and n_rec_out > RECOVERY_WARN_FRAC * len(ew.starts):
        warnings.append(
            f"{n_rec_out} of {len(ew.starts)} windows end before their event has recovered (its recovery point "
            f"lies outside the window): the window ({ew.length_s:g} s) cuts the recovery off. Raise length_s "
            f"if the waveform after the trough matters (window images, MiniRocket, families).")
    meta = {
        "n_events": n_events, "n_windows": int(len(ew.starts)), "omitted": dict(ew.omitted),
        "omitted_rows": {r: [int(i) for i in v[:4096]] for r, v in ew.omitted_rows.items()},
        "n_overlapping": int(feats["overlaps_next"].sum()), "n_split_leaks": _split_leaks(ew.starts, ew.length, labels),
        "length_s": ew.length_s, "length": ew.length, "length_basis": ew.length_basis,
        "anchor": anchor, "anchor_used": ew.anchor_used, "anchor_offset": ew.anchor_offset,
        "anchor_fallback": ew.n_fallback, "pre_frac": float(pre_frac), "span_start": span_start,
        "split_rule": split_rule, "blocks": blocks, "seed": int(seed),
        "split_counts": {name: int((labels == i).sum()) for i, name in enumerate(SPLIT_NAMES)},
        "n_recovery_outside_window": n_rec_out, "n_duration_unmeasured": ew.n_duration_unmeasured,
        "warnings": warnings,
        "notes": list(ew.notes), "summary": _summary(n_events, ew),
        "rules": EW.rules(anchor=anchor, pre_frac=pre_frac, max_nan_frac=max_nan_frac, length_s=length_s,
                          length_basis=ew.length_basis),
        "carried": [c for c in feats.columns if c not in EW.NOT_FEATURES],
    }
    return AdapterResult(output_kind="windowset", value=ws, meta=meta)


def _derive(x, t, fs, params, value=None):
    if value is None:
        return [("Events", "run a detector first — this block cuts a window around each span it is given", "warn")]
    try:
        ew = EW.event_windows(x, fs, value, anchor=params["anchor"], length_s=params["length_s"],
                              pre_frac=params["pre_frac"], max_nan_frac=params["max_nan_frac"])
    except ValueError as e:
        return [("Windows", str(e), "error")]
    n = len(value.starts)
    left = sum(ew.omitted.values())
    rows = [("Windows", f"{len(ew.starts)} of {n} events", "warn" if left else ""),
            ("Length", f"{ew.length_s:g} s ({ew.length} samples) · anchor {ew.anchor_offset} samples in", "")]
    if left:
        rows.append(("Left out", ", ".join(f"{r} {c}" for r, c in ew.omitted.items() if c), "warn"))
    if ew.n_fallback:
        rows.append(("Anchor", f"{ew.n_fallback} event(s) on their span start, not their {params['anchor']}", "warn"))
    nov = int(EW.overlaps_next(ew.starts, ew.length).sum())
    if nov:
        rows.append(("Overlapping", f"{nov} window(s) run into the next", ""))
    return rows


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Event windows (SpanSet -> WindowSet)",
    stage="catalogue",
    category="cluster",
    page_name="Event windows",
    params=[
        ParamSpec("anchor", str, "onset",
                  "What each window is lined up on: the event's onset (Event shape's onset_idx), its extremum "
                  "(extremum_idx), or its span start. An event without the column falls back to its span start, "
                  "counted", choices=list(EW.ANCHORS)),
        ParamSpec("length_s", float, 0.0,
                  "Window length in seconds. 0 = auto: twice the median event duration (Event shape's onset to "
                  "half recovery), rounded up to 10 s, clamped to 60-7200 s - it holds the onset, the trough and "
                  "about half the recovery, not the return to baseline (the 2x is a placeholder). Set it when "
                  "the whole recovery matters", min=0.0, max=86400.0),
        ParamSpec("pre_frac", float, EW.DEFAULT_PRE_FRAC, "Share of the window before the anchor (0.2: a fifth "
                  "before, four fifths after)", min=0.0, max=0.95),
        ParamSpec("max_nan_frac", float, EW.DEFAULT_MAX_NAN_FRAC,
                  "Leave out a window with more than this fraction of missing samples", min=0.0, max=1.0),
        ParamSpec("split_rule", str, "blocked_by_time", "How windows are assigned to train / validation / test "
                  "(as Sliding windows)", choices=["blocked_by_time", "random"]),
        ParamSpec("n_blocks", int, 5, "Contiguous time blocks the span is cut into (blocked_by_time)", min=1, max=1000),
        ParamSpec("holdout_frac", float, 0.2, "Fraction of blocks (or windows) held out as test", min=0.0, max=0.9),
        ParamSpec("validation_frac", float, 0.0, "Fraction held out as validation", min=0.0, max=0.9),
        ParamSpec("allow_random_split", bool, False, "Accept the leakage a random split carries (B7)"),
        ParamSpec("seed", int, 0, "Random-split seed", min=0, max=2**31 - 1),
    ],
    run=_run,
    derive=_derive,
    input_kind="spanset",
    output_kind="windowset",
    description=(
        "One window around every detected event, lined up on its onset, so the window blocks (cluster, "
        "classifier, window images) work on events instead of a fixed grid. Each window carries its event's "
        "measures — put Event shape before this block to cluster on amplitude, width or recovery. Tune "
        "length_s first: 0 picks twice the median event duration. Events too near the span's ends to fit a "
        "whole window are left out and counted."
    ),
))

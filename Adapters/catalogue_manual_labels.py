"""
catalogue_manual_labels.py
===========================
The manual-label arm of RQ1: `WindowSet -> Grouping`, one label per window
taken from the HUMAN verdicts already in the store — `annotations` (the
600-sample `imported_10min` set, the Excel catalogue, spans drawn in Review or
Explore) and `window_verdicts` (verdicts Review wrote on a saved window set).
`catalogue.classifier` trains from this Grouping exactly as it trains from
`catalogue.cluster`'s, so swapping the upstream block is the whole difference
between the two arms (`catalogue_classifier.py`'s docstring).

The rule (QUESTIONS.md Q41 and Round 10 Q-W1, the researcher's, 2026-10-03)
----------------------------------------------------------------------------
* Classes: `interesting` (with `seed`, a subset of it) vs `not_interesting`.
  `artifact` is excluded from training and counted; `unsure` labels nothing.
* A window takes a label only if it WHOLLY CONTAINS at least one labelled span
  and every span it wholly contains agrees. A span the window only partly
  overlaps does not label it: an `interesting` span whose event sits at its far
  end must not label a window that misses the end.
* A window wholly INSIDE a longer `not_interesting` span is `not_interesting`
  (nothing is anywhere in it); inside a longer `artifact` span it is excluded as
  artifact (the artifact may be in it); inside a longer `interesting` span it is
  unlabelled (the event could be anywhere in the span). What a window contains
  and what it lies inside must agree, or the window is conflicting.
* Time nobody labelled is unlabelled — never `not_interesting`.
* A training set keeps no two overlapping windows (`non_overlapping`, on by
  default), LABELLED WINDOWS FIRST: left to right, a labelled window is kept
  unless it overlaps one already kept; then every unlabelled window that
  overlaps nothing kept fills the gaps. The rest are counted as dropped for
  overlap.

  Q-W1 first decided a single phase of the grid (every third window of the
  labels' 600/200 grid, the phase with the most labels). Measured on the 16
  M2_aug channels (2026-10-03) that kept 3,906 of the 11,110 labelled windows —
  the labels are sparse and spread over all three phases, and only 1,135 of
  them overlap a neighbour — while labelled-first keeps 10,077 under the same
  no-overlap guarantee. The researcher chose labelled-first the same day
  (QUESTIONS.md, Q-W1 revised).

Every window gets exactly one fate, so the counts add up to the window count:
`interesting · not_interesting · unlabelled · conflicting · artifact · dropped
for overlap`. The Grouping's labels are 1 = interesting, 0 = not_interesting and
-1 = excluded (any of the other four); `catalogue.classifier` trains on the
labelled windows only and says how many it left out.

What it reads, and that it writes nothing (rule 5)
--------------------------------------------------
`_run` declares `conn` and `recording`: the executor hands a step that declares
them the run's connection and the recording row, and — because the output then
depends on the live store and not only on the recipe — runs that step and every
later one without the step cache (`Working/execution.py`). This module only
selects; a human verdict is never written into a machine table or the reverse.
"""

import math
import os
from dataclasses import dataclass, field

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import Grouping

LABEL_INTERESTING = 1
LABEL_NOT_INTERESTING = 0
LABEL_EXCLUDED = -1
CLASS_NAMES = {str(LABEL_NOT_INTERESTING): "not_interesting", str(LABEL_INTERESTING): "interesting"}

# human verdict -> the class it votes for. `unsure` votes for nothing.
_VOTE = {"seed": "interesting", "interesting": "interesting",
         "not_interesting": "not_interesting", "artifact": "artifact"}

FATES = ("interesting", "not_interesting", "unlabelled", "conflicting", "artifact", "dropped_for_overlap")

RULES = [
    {"name": "classes",
     "rule": "interesting (seed counts as interesting) vs not_interesting; artifact windows are excluded "
             "from training and counted; an 'unsure' verdict labels nothing"},
    {"name": "containment",
     "rule": "a window takes a label only if it wholly contains at least one labelled span and every span "
             "it wholly contains agrees; a span the window only partly overlaps does not label it"},
    {"name": "longer spans",
     "rule": "a window wholly inside a longer not_interesting span is not_interesting; inside a longer "
             "artifact span it is excluded as artifact; inside a longer interesting span it is unlabelled "
             "(the event could be anywhere in it)"},
    {"name": "conflicting",
     "rule": "a window whose contained spans, or whose contained and enclosing spans, disagree is left out "
             "and counted as conflicting"},
    {"name": "unlabelled",
     "rule": "time nobody labelled is unlabelled, never not_interesting; excluded and counted"},
    {"name": "dropped for overlap",
     "rule": "a training set keeps no two overlapping windows, labelled windows first: left to right, a labelled "
             "window is kept unless it overlaps one already kept, then unlabelled windows fill the gaps; the "
             "others are dropped for overlap and counted"},
]


@dataclass
class WindowLabels:
    """The outcome of `label_windows`: `labels` (1 / 0 / -1 per window), the
    `fate` of each window (one of `FATES`) and the `counts` that partition them."""
    labels: np.ndarray
    fate: np.ndarray
    counts: dict = field(default_factory=dict)


def _span_arrays(spans):
    starts, ends, votes = [], [], []
    for s in spans:
        start, end, verdict = int(s[0]), int(s[1]), str(s[2])
        vote = _VOTE.get(verdict)
        if vote is None or end <= start:
            continue
        starts.append(start); ends.append(end); votes.append(vote)
    order = np.argsort(np.asarray(starts, dtype=np.int64), kind="stable")
    return (np.asarray(starts, dtype=np.int64)[order], np.asarray(ends, dtype=np.int64)[order],
            np.asarray(votes, dtype=object)[order])


def _fate_of(ws, we, starts, ends, votes, max_len):
    """The fate of one window [ws, we) against spans sorted by start. Only a
    span starting in [ws - max_len, we) can contain or enclose the window."""
    lo = int(np.searchsorted(starts, ws - max_len, side="left"))
    hi = int(np.searchsorted(starts, we, side="left"))
    s, e, v = starts[lo:hi], ends[lo:hi], votes[lo:hi]
    contained = (s >= ws) & (e <= we)
    enclosing = (s <= ws) & (e >= we) & ~contained
    vote_set = set(v[contained].tolist())
    # a longer interesting span says the event is somewhere in it: no vote
    vote_set |= set(v[enclosing].tolist()) - {"interesting"}
    if not vote_set:
        return "unlabelled"
    if len(vote_set) > 1:
        return "conflicting"
    return next(iter(vote_set))


NON_OVERLAP_RULE = "labelled-first"


def non_overlapping_keep(starts, length, labelled):
    """Which windows a non-overlapping training set keeps: `keep_mask`.

    Labelled windows first — left to right, each kept unless it overlaps one
    already kept (for windows of one length this is the largest non-overlapping
    subset of the labelled windows) — then every unlabelled window that overlaps
    nothing kept. A set that already tiles keeps everything."""
    starts = np.asarray(starts, dtype=np.int64)
    labelled = np.asarray(labelled, dtype=bool)
    n = len(starts)
    keep = np.zeros(n, dtype=bool)
    if n == 0:
        return keep
    length = int(length)
    order = np.argsort(starts, kind="stable")
    last_end = None
    for i in order:
        if labelled[i] and (last_end is None or starts[i] >= last_end):
            keep[i] = True
            last_end = int(starts[i]) + length
    kept_starts = np.sort(starts[keep])
    for i in order:
        if keep[i] or labelled[i]:
            continue
        s = int(starts[i])
        # the nearest kept window on either side must not reach into [s, s + length)
        j = int(np.searchsorted(kept_starts, s, side="right"))
        before_ok = j == 0 or kept_starts[j - 1] + length <= s
        after_ok = j == len(kept_starts) or kept_starts[j] >= s + length
        if before_ok and after_ok:
            keep[i] = True
            kept_starts = np.insert(kept_starts, j, s)
    return keep


def label_windows(starts, length, spans, non_overlapping=False):
    """Label each window `[start, start + length)` from human `spans`
    (`(start, end, verdict)`, channel-absolute, end exclusive) by the rule in the
    module docstring. Pure; reads nothing."""
    starts = np.asarray(starts, dtype=np.int64)
    s_arr, e_arr, v_arr = _span_arrays(spans)
    max_len = int((e_arr - s_arr).max()) if len(s_arr) else 0
    n = len(starts)
    fate = np.empty(n, dtype=object)
    seed_starts = np.asarray([int(s[0]) for s in spans if str(s[2]) == "seed"], dtype=np.int64)
    seed_ends = np.asarray([int(s[1]) for s in spans if str(s[2]) == "seed"], dtype=np.int64)
    is_seed = np.zeros(n, dtype=bool)
    for i, ws in enumerate(starts):
        we = int(ws) + int(length)
        f = _fate_of(int(ws), we, s_arr, e_arr, v_arr, max_len)
        fate[i] = f
        if f == "interesting" and len(seed_starts):
            is_seed[i] = bool(np.any((seed_starts >= ws) & (seed_ends <= we)))
    labelled = np.isin(fate, ["interesting", "not_interesting"])
    if non_overlapping:
        keep = non_overlapping_keep(starts, length, labelled)
        fate[~keep] = "dropped_for_overlap"
    labels = np.full(n, LABEL_EXCLUDED, dtype=np.int64)
    labels[fate == "interesting"] = LABEL_INTERESTING
    labels[fate == "not_interesting"] = LABEL_NOT_INTERESTING
    counts = {f: int((fate == f).sum()) for f in FATES}
    counts["n_windows"] = int(n)
    counts["labelled"] = counts["interesting"] + counts["not_interesting"]
    counts["seed"] = int((is_seed & (fate == "interesting")).sum())
    counts["non_overlap_rule"] = NON_OVERLAP_RULE if non_overlapping else None
    return WindowLabels(labels=labels, fate=fate, counts=counts)


def human_spans(conn, recording_id):
    """Every human-labelled span on one recording, channel-absolute:
    `[(start, end, verdict, source)]` from `annotations` and from the
    `window_verdicts` written on any saved window set of that recording (whose
    bounds are read from the set's own files on disk)."""
    out = [(int(r[0]), int(r[1]), str(r[2]), str(r[3])) for r in conn.execute(
        "SELECT start_idx, end_idx, verdict, source FROM annotations WHERE recording_id = ?",
        (int(recording_id),))]
    sets = conn.execute(
        "SELECT ws.id, ws.path, ws.window_length FROM window_sets ws WHERE ws.recording_id = ? "
        "AND EXISTS (SELECT 1 FROM window_verdicts wv WHERE wv.window_set_id = ws.id)",
        (int(recording_id),)).fetchall()
    for set_id, path, window_length in sets:
        starts, length = _saved_window_bounds(path, window_length)
        for idx, verdict in conn.execute(
                "SELECT window_index, verdict FROM window_verdicts WHERE window_set_id = ?", (int(set_id),)):
            if 0 <= int(idx) < len(starts):
                s = int(starts[int(idx)])
                out.append((s, s + int(length), str(verdict), "window_verdicts"))
    return out


def _saved_window_bounds(path, window_length):
    """A saved window set's starts and length, from `windowset.npz` (the
    `WindowSet.to_path` layout) or the bridge's `windows.npz`. A set whose
    files are missing raises — a verdict whose window cannot be placed is not
    silently dropped."""
    for fname in ("windowset.npz", "windows.npz"):
        p = os.path.join(str(path), fname)
        if os.path.isfile(p):
            with np.load(p, allow_pickle=False) as z:
                length = int(z["length"]) if "length" in z.files else int(window_length)
                return np.asarray(z["starts"], dtype=np.int64), length
    raise FileNotFoundError(
        f"catalogue.manual_labels: the saved window set at {path!r} has window verdicts but no "
        "windowset.npz / windows.npz to place them with")


def coverage_summary(counts, n_spans=None):
    """The one line the Grouping row and the block page print."""
    c = counts
    line = (f"{c['n_windows']:,} windows · {c['labelled']:,} labelled "
            f"(interesting {c['interesting']:,}"
            + (f", of which seed {c['seed']:,}" if c.get("seed") else "")
            + f" · not_interesting {c['not_interesting']:,}) · unlabelled {c['unlabelled']:,} · "
            f"conflicting {c['conflicting']:,} · artifact {c['artifact']:,} · "
            f"dropped for overlap {c['dropped_for_overlap']:,}")
    if c.get("non_overlap_rule"):
        line += f" (no two windows overlap · {c['non_overlap_rule']})"
    return line


def _grid_hint(starts, length, spans):
    """Why a window set took no label from spans it clearly overlaps: windows off
    the labels' grid only ever partly overlap them. Returns a sentence or None."""
    starts = np.asarray(starts, dtype=np.int64)
    if not len(starts) or not spans:
        return None
    lo, hi = int(starts.min()), int(starts.max()) + int(length)
    inside = [s for s in spans if s[0] < hi and s[1] > lo and (s[1] - s[0]) <= length]
    if not inside:
        return None
    contained = sum(1 for s in inside if np.any((starts <= s[0]) & (starts + length >= s[1])))
    if contained:
        return None
    widths = sorted({int(s[1] - s[0]) for s in inside})
    return (f"{len(inside):,} labelled span(s) of width {', '.join(map(str, widths[:3]))} sample(s) lie in "
            "these windows' range but no window wholly contains one: the windows are off the labels' grid. "
            "Put the windows on it (the 10-minute set: window 600 samples, step 200, span start a multiple "
            "of 200).")


def _run(x, t, fs, non_overlapping=True, value=None, conn=None, recording=None):
    if value is None:
        raise ValueError(
            "catalogue.manual_labels requires a WindowSet input from a prior step (input_kind='windowset') — "
            "the windows to label.")
    if conn is None or recording is None:
        raise ValueError(
            "catalogue.manual_labels reads the human verdicts in the store; it must be run by the executor, "
            "which hands it the run's connection and recording.")
    spans = human_spans(conn, recording["id"])
    result = label_windows(value.starts, value.length, spans, non_overlapping=bool(non_overlapping))
    counts = dict(result.counts)
    sources = {}
    for s in spans:
        sources[s[3]] = sources.get(s[3], 0) + 1
    summary = coverage_summary(counts)
    hint = _grid_hint(value.starts, value.length, spans)
    rules = list(RULES) + [{"name": "coverage", "rule": summary}]
    if hint:
        rules.append({"name": "grid", "rule": hint})
    coverage = dict(counts, sources=sources, n_spans=len(spans))
    return AdapterResult(
        output_kind="grouping",
        value=Grouping(labels=result.labels),
        meta={
            "coverage": coverage,
            "class_names": dict(CLASS_NAMES),
            "excluded_label": LABEL_EXCLUDED,
            "fates": [str(f) for f in result.fate],
            "rules": rules,
            "summary": summary + (f" · {hint}" if hint else ""),
            "non_overlapping": bool(non_overlapping),
        },
    )


SPEC = register(AdapterSpec(
    name="catalogue.manual_labels",
    display_name="Manual labels (WindowSet -> Grouping)",
    stage="catalogue",
    category="cluster",
    page_name="Manual labels",
    params=[
        ParamSpec(
            "non_overlapping", bool, True,
            "Keep no two overlapping windows (a training set): labelled windows first, each kept unless it "
            "overlaps one already kept, then unlabelled windows fill the gaps; the rest are counted as dropped for "
            "overlap. Off labels every window, overlapping neighbours included.",
        ),
    ],
    run=_run,
    input_kind="windowset",
    output_kind="grouping",
    description=(
        "Labels each window from the human verdicts in the store (annotations and window verdicts): "
        "interesting vs not_interesting, by containment — a window takes a label only if it wholly contains "
        "a labelled span and every span it contains agrees. Unlabelled, conflicting and artifact windows, and "
        "windows dropped to keep the set non-overlapping, are excluded (label -1) and counted. The manual-label "
        "arm of RQ1: catalogue.classifier trains from it exactly as from catalogue.cluster."
    ),
))

"""
sequences.py
============
Sequences among the confident candidates of one channel.

In plain words: a sequence is a drum roll rather than single hits — candidates that come close together, with a
long silence before the next group. The tool's logISI train finder (`Working.interrogation.trains`, automatic mode:
no neuronal 100 ms ceiling) reads the cut from the channel's own gaps: a histogram of the gaps on a log scale has
two humps when there are trains, and the valley between them is the cut. When it finds no valley it says so, and
the fixed rule the Library analysis used takes over: consecutive candidates join when the next starts within an
hour (``FALLBACK_GAP_S``).

Only candidates at or above ``MIN_CONFIDENCE`` (more likely than not) take part, and a sequence needs
``MIN_EVENTS`` of them (the researcher's choice, 2026-11-19, Q14 (a)). A sequence is drawn as a band with its member
count and its members' mean confidence.

Caveat the train finder states itself: when the timing inside a train is irregular, the gaps between trains must be
roughly 30-100x those inside before a valley can show at all, so "no trains" there means "not resolvable".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from Working.interrogation.trains import _labels_from_runs, _runs_below, find_trains

MIN_CONFIDENCE = 0.5
MIN_EVENTS = 5
FALLBACK_GAP_S = 3600.0

SEQUENCE_COLUMNS = ("sequence_id", "start", "end", "start_s", "end_s", "n_members", "mean_confidence",
                    "min_confidence", "median_gap_s", "rule")


RULES = ("logisi", "gap")


def find_sequences(candidates, fs, *, min_confidence=MIN_CONFIDENCE, min_events=MIN_EVENTS,
                   fallback_gap_s=FALLBACK_GAP_S, rule="logisi"):
    """Sequences of ``candidates`` (a frame with ``start``, ``end`` (samples) and ``confidence``).

    ``rule="logisi"`` (the default) tries the train finder first and falls back to the fixed gap; ``rule="gap"`` uses
    the fixed gap only — for ACCEPTED events, which are a sample of what was reviewed and so show no real within- and
    between-train gap split for logISI to cut (the sequence-queue session, 2026-11-23: it cut at 19 h and 64 h gaps).

    Returns ``(labels, sequences, info)``: ``labels`` aligned with ``candidates`` (-1 = in no sequence, or below
    the confidence cut), one row per sequence (`SEQUENCE_COLUMNS`), and what the finder did (``rule``, ``cut_s``,
    ``reason``).
    """
    if rule not in RULES:
        raise ValueError(f"rule must be one of {RULES}, got {rule!r}")
    labels = np.full(len(candidates), -1, dtype=np.int64)
    empty = pd.DataFrame({c: pd.Series(dtype=float) for c in SEQUENCE_COLUMNS})
    if not len(candidates):
        return labels, empty, {"rule": None, "cut_s": None, "reason": "no candidates", "n_in": 0}
    conf = candidates["confidence"].to_numpy(dtype=float)
    take = np.flatnonzero(conf >= float(min_confidence))
    info = {"min_confidence": float(min_confidence), "min_events": int(min_events), "n_in": int(len(take))}
    if len(take) < int(min_events):
        info.update(rule=None, cut_s=None, reason=f"{len(take)} candidates at or above {min_confidence:g}; "
                                                  f"a sequence needs {min_events}")
        return labels, empty, info
    starts = candidates["start"].to_numpy(dtype=np.int64)[take]
    order = np.argsort(starts, kind="stable")
    t = starts[order] / float(fs)
    res = find_trains(t, rule="logisi", min_events=int(min_events)) if rule == "logisi" else None
    if res is not None and res["n_trains"]:
        sub = np.asarray(res["train_id"], dtype=np.int64)
        info.update(rule="logisi", cut_s=res.get("cut_s"), void=res.get("void"), reason=None)
    else:
        runs = _runs_below(np.diff(t), float(fallback_gap_s), strict=False)
        sub = _labels_from_runs(len(t), runs, int(min_events))
        info.update(rule=f"gap <= {fallback_gap_s:g} s", cut_s=float(fallback_gap_s),
                    reason=(f"logISI found no trains ({res.get('no_trains_reason')}); the fixed-gap rule was used"
                            if res is not None else "the fixed-gap rule was asked for"))
    labels[take[order]] = sub
    rows = []
    for sid in sorted(set(sub[sub >= 0].tolist())):
        members = take[order][sub == sid]
        g = candidates.iloc[members]
        ts = np.sort(g["start"].to_numpy(dtype=np.int64)) / float(fs)
        rows.append({"sequence_id": int(sid), "start": int(g["start"].min()), "end": int(g["end"].max()),
                     "start_s": float(g["start"].min()) / fs, "end_s": float(g["end"].max()) / fs,
                     "n_members": int(len(g)), "mean_confidence": float(g["confidence"].mean()),
                     "min_confidence": float(g["confidence"].min()),
                     "median_gap_s": float(np.median(np.diff(ts))) if len(ts) > 1 else float("nan"),
                     "rule": info["rule"]})
    seqs = pd.DataFrame(rows, columns=list(SEQUENCE_COLUMNS)) if rows else empty
    info["n_sequences"] = int(len(seqs))
    return labels, seqs, info

"""
candidates.py
=============
Proposals from every source merged into candidates; agreement, R4's score and the blended confidence attached.

In plain words
--------------
The detectors and the seed searches each mark stretches. Where several mark the same stretch, that is one
candidate, not several. Three steps, the first and last of which are the tool's own:

1. **The same event** is the rule Review and the candidate tables already use (`Working.discovery.matching`, §4.6:
   reciprocal overlap and onset agreement scaled to the candidate's duration), through
   `candidate_events.build_events`: settings are taken rarest first and each proposal joins the candidate it
   matches best, so a dense source can never chain a channel into one candidate.
2. **One event drawn twice.** Two candidates of similar length (within ``NEAR_DUPLICATE_RATIO``) that overlap by
   half of the shorter are one event drawn at a small offset — two seed families matching one 10 s drop a few
   samples apart — and fold into the one with more proposals behind it (`fold_near_duplicates`; the survivor keeps
   its own span, so a train cannot chain). Some sources also draw a loose box around an event (drop v1's windows
   start on a 98 s grid, often minutes before the fall) where others draw it tightly; the same-event rule keeps such
   a pair apart because their overlap is small relative to the loose box. A candidate that holds exactly one tighter
   candidate, at least ``ABSORB_MIN_RATIO`` of its length, is folded into it: one event, drawn by its tighter box.
   A loose box that holds two or more candidates is kept as it is (it may be a train or a region).
3. **Agreement** is `candidate_events.add_agreement` (rule 4): a source agrees with a candidate when one of its
   proposals overlaps at least half of the shorter of the two. Once candidates are redrawn around their events
   (`reanchor`), a proposal vouches only for the events it mainly points at (`agreement_by_main_events`).

Then every candidate gets R4's probability for its own span and the blended confidence (`blend`). R4's window-scan
hits that overlap a candidate add nothing to it (R4 has already scored that candidate's own span; their best score
is kept as ``scan_p`` for information); the rest become candidates of their own, kind ``r4_scan``, with R4's score
as their confidence.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from Working.autodetect import blend
from Working.discovery.candidate_events import AGREE_SHARE, FAMILY_SEP, add_agreement, build_events, family_of

#: A candidate folds into the single tighter candidate it holds only if that one is at least this share of its length.
ABSORB_MIN_RATIO = 0.1
#: Two candidates whose lengths are within this factor and that overlap by half of the shorter are one event drawn
#: twice at a small offset (two seed families matching one 10 s drop a few samples apart, a seed and drop v5 around
#: the same fall). Added 2026-11-19 after the first runs: without it, 314 of MJu26a CH14's 528 accepted events were
#: covered by two or more candidates.
NEAR_DUPLICATE_RATIO = 2.5

KIND_PROPOSAL = "proposal"
KIND_SCAN = "r4_scan"


def _detections(proposals):
    """`proposals` (``start``, ``end``, ``variant``) in the shape `build_events` reads."""
    d = proposals[["start", "end", "variant"]].copy().reset_index(drop=True)
    d["start"] = d["start"].astype(np.int64)
    d["end"] = d["end"].astype(np.int64)
    d.insert(0, "detection_id", np.arange(len(d), dtype=np.int64))
    d.insert(1, "run_id", np.int64(0))
    d.insert(2, "recording_id", np.int64(0))
    return d


def _inside(a_start, a_end, b_start, b_end, share=AGREE_SHARE):
    """Is span a (the shorter) at least ``share`` inside span b?"""
    inter = min(a_end, b_end) - max(a_start, b_start)
    return inter > 0 and inter >= share * max(1, a_end - a_start)


def absorb_loose(starts, ends, *, min_ratio=ABSORB_MIN_RATIO, share=AGREE_SHARE):
    """Step 2. ``into[i]`` is the candidate ``i`` folds into (itself when it stays). Candidates are visited shortest
    first, so a box around a box around an event folds, step by step, into the event."""
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.asarray(ends, dtype=np.int64)
    n = len(starts)
    into = np.arange(n)
    alive = np.ones(n, dtype=bool)
    lengths = ends - starts
    by_start = np.argsort(starts, kind="stable")
    sorted_starts = starts[by_start]
    for b in np.lexsort((starts, lengths)):
        lb = int(lengths[b])
        lo = np.searchsorted(sorted_starts, starts[b] - lb, side="left")
        hi = np.searchsorted(sorted_starts, ends[b], side="left")
        held = []
        for j in by_start[lo:hi]:
            if j == b or not alive[j] or lengths[j] > lb:
                continue
            if lengths[j] == lb and j > b:      # equal lengths: only the earlier-listed one can hold the other
                continue
            if _inside(starts[j], ends[j], starts[b], ends[b], share):
                held.append(int(j))
                if len(held) > 1:
                    break
        if len(held) == 1 and lengths[held[0]] >= float(min_ratio) * lb:
            alive[b] = False
            into[b] = held[0]
    # resolve chains: b -> a -> a' ...
    for i in range(n):
        k = i
        while into[k] != k:
            k = into[k]
        into[i] = k
    return into


def fold_near_duplicates(starts, ends, priority, *, ratio=NEAR_DUPLICATE_RATIO, share=AGREE_SHARE):
    """``into[i]``: the candidate ``i`` folds into (itself when it stays). Candidates are visited by ``priority``
    (higher first); each survivor folds every lower-priority candidate that overlaps it by ``share`` of the shorter
    and whose length is within ``ratio`` of its own. A survivor keeps its own span, so a run of events can never chain
    into one candidate."""
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.asarray(ends, dtype=np.int64)
    n = len(starts)
    into = np.arange(n)
    gone = np.zeros(n, dtype=bool)
    lengths = np.maximum(ends - starts, 1)
    by_start = np.argsort(starts, kind="stable")
    sorted_starts = starts[by_start]
    longest = int(lengths.max()) if n else 0
    for a in np.argsort(-np.asarray(priority, dtype=float), kind="stable"):
        if gone[a]:
            continue
        lo = np.searchsorted(sorted_starts, starts[a] - longest, side="left")
        hi = np.searchsorted(sorted_starts, ends[a], side="left")
        for j in by_start[lo:hi]:
            if j == a or gone[j]:
                continue
            la, lj = lengths[a], lengths[j]
            if max(la, lj) > ratio * min(la, lj):
                continue
            inter = min(ends[a], ends[j]) - max(starts[a], starts[j])
            if inter > 0 and inter >= share * min(la, lj):
                gone[j] = True
                into[j] = a
    return into


def merge(proposals, *, rule=None, min_ratio=ABSORB_MIN_RATIO, near_ratio=NEAR_DUPLICATE_RATIO):
    """Steps 1-3. Returns one row per candidate: ``start``, ``end`` (relative), ``anchor_variant``,
    ``member_variants`` (every proposal folded into it), ``sources`` (the agreeing sources, ``|``-joined) and
    ``n_sources``."""
    cols = ["start", "end", "anchor_variant", "member_variants", "n_members", "sources", "n_sources"]
    if proposals is None or not len(proposals):
        return pd.DataFrame({c: pd.Series(dtype=object) for c in cols})
    det = _detections(proposals)
    events, members = build_events(det, rule=rule)
    # near-duplicates first (the event with more proposals behind it survives; then the shorter), then loose boxes
    size = members.groupby("event_id").size().reindex(events["event_id"]).fillna(0).to_numpy()
    span = (events["end"] - events["start"]).to_numpy(dtype=float)
    first = fold_near_duplicates(events["start"].to_numpy(), events["end"].to_numpy(),
                                 size - span / (span.max() + 1.0), ratio=near_ratio) if near_ratio else \
        np.arange(len(events))
    alive = np.flatnonzero(first == np.arange(len(events)))
    second = absorb_loose(events["start"].to_numpy()[alive], events["end"].to_numpy()[alive], min_ratio=min_ratio)
    into = first.copy()
    pos = {int(k): i for i, k in enumerate(alive)}
    for i in range(len(events)):
        root = int(first[i])
        into[i] = int(alive[second[pos[root]]])
    keep = np.flatnonzero(into == np.arange(len(events)))
    remap = {int(k): i for i, k in enumerate(keep)}
    ev_of_member = members["event_id"].map(lambda e: remap[int(into[int(e)])])
    kept = events.iloc[keep].reset_index(drop=True)
    variants = members.assign(final=ev_of_member.to_numpy()).groupby("final")["variant"]
    kept["member_variants"] = [FAMILY_SEP.join(sorted(set(variants.get_group(i)))) if i in variants.groups else ""
                               for i in range(len(kept))]
    kept["n_members"] = [int(len(variants.get_group(i))) if i in variants.groups else 0 for i in range(len(kept))]
    kept = add_agreement(kept[["event_id", "recording_id", "start", "end", "anchor_variant", "member_variants",
                               "n_members"]], det)
    kept = kept.rename(columns={"agree_families": "sources", "n_agree": "n_sources"})
    return kept[cols].sort_values(["start", "end"]).reset_index(drop=True)


ANCHOR_COLUMNS = ("orig_start", "orig_end", "anchored", "polarity", "onset", "extremum", "event_end", "recovered",
                  "depth_mv")
#: A proposal vouches for the events it overlaps (rule 4) only when they are at least this share as deep as the
#: deepest event it overlaps: a long detector window drawn round one big drop does not vouch for every small fall
#: inside it (2026-11-23: without this, MJu26a CH14's candidates at >= 0.5 rose from 2,854 to 3,921, median depth
#: 0.26 mV, on agreement the detectors never gave).
MAIN_EVENT_FRAC = 0.5


def agreement_by_main_events(events, proposals, *, share=AGREE_SHARE, main_frac=MAIN_EVENT_FRAC):
    """``(sources, n_sources)`` per event: rule 4 (a source agrees when one of its proposals overlaps at least
    ``share`` of the shorter of the two), counted only for the events a proposal mainly points at - those at least
    ``main_frac`` as deep as the deepest event it overlaps."""
    es = events["start"].to_numpy(np.int64)
    ee = events["end"].to_numpy(np.int64)
    dep = events["depth_mv"].to_numpy(dtype=float)
    order = np.argsort(es, kind="stable")
    es_sorted = es[order]
    longest = int((ee - es).max()) if len(es) else 0
    found = [set() for _ in range(len(es))]
    for ps, pe, var in zip(proposals["start"].to_numpy(np.int64), proposals["end"].to_numpy(np.int64),
                           proposals["variant"].to_numpy(dtype=object)):
        lo = np.searchsorted(es_sorted, ps - longest, side="left")
        hi = np.searchsorted(es_sorted, pe, side="left")
        hit = []
        for j in order[lo:hi]:
            inter = min(pe, ee[j]) - max(ps, es[j])
            if inter > 0 and inter >= share * max(1, min(pe - ps, ee[j] - es[j])):
                hit.append(j)
        if not hit:
            continue
        deepest = max(dep[j] for j in hit)
        fam = family_of(var)
        for j in hit:
            if dep[j] >= main_frac * deepest:
                found[j].add(fam)
    return [FAMILY_SEP.join(sorted(s)) for s in found], [len(s) for s in found]


def reanchor(cands, proposals, x_mv, fs, *, is_event=None):
    """Every candidate redrawn around EVERY event it points at (`anchor.anchor_events`: the Library's whole drop,
    the researcher's Q1 (b), 2026-11-23) - a long detector box holding three train members gives three candidates -
    then boxes that hold the same event, or a step inside a much deeper event, made one, and agreement recomputed on
    the new boxes. A candidate that points at no event is dropped (and counted).

    ``is_event`` (anchored rows -> bool mask) drops what the run's own rules say is no event BEFORE events are made
    one: a slow climb the sharp-rises rule removes would otherwise fold the next real drop into itself as "the fall
    back after a spike" and take it away with it (M4 CH1 64:00 h, 2026-11-23). Counted as ``not_events``.

    Returns ``(cands, report)``. ``orig_start`` / ``orig_end`` cover every proposal box that went into a candidate."""
    from Working.autodetect import anchor as AN

    cols = ["start", "end", "anchor_variant", "member_variants", "n_members", "sources", "n_sources",
            *ANCHOR_COLUMNS]
    empty = pd.DataFrame({c: pd.Series(dtype=object) for c in cols})
    if cands is None or not len(cands):
        return empty, {"candidates": 0, "with_events": 0, "no_event": 0, "events": 0, "same_event": 0}
    c = cands.reset_index(drop=True)
    rows, src = [], []
    for k, (s, e) in enumerate(zip(c["start"].to_numpy(np.int64), c["end"].to_numpy(np.int64))):
        for ev in AN.anchor_events(x_mv, s, e, fs):
            rows.append(ev)
            src.append(k)
    src = np.asarray(src, dtype=np.int64)
    report = {"candidates": int(len(c)), "with_events": int(len(set(src.tolist()))),
              "no_event": int(len(c) - len(set(src.tolist()))), "events": int(len(rows))}
    if not rows:
        report["same_event"] = 0
        return empty, report
    an = pd.DataFrame(rows, columns=list(AN.COLUMNS))
    if is_event is not None:
        keep = np.asarray(is_event(an), dtype=bool)
        report["not_events"] = int((~keep).sum())
        an, src = an[keep].reset_index(drop=True), src[keep]
        if not len(an):
            report["same_event"] = 0
            return empty, report
    span = (an["box_end"] - an["box_start"]).to_numpy(dtype=float)
    priority = c["n_members"].to_numpy(dtype=float)[src] - span / (span.max() + 1.0)
    into = AN.fold(an, AN.same_event(an, priority))
    out_rows = []
    for r in sorted(set(into.tolist())):
        members = np.unique(src[into == r])
        variants = sorted({v for m in members for v in str(c.at[int(m), "member_variants"]).split(FAMILY_SEP) if v})
        out_rows.append({
            "start": int(an.at[r, "box_start"]), "end": int(an.at[r, "box_end"]),
            "anchor_variant": c.at[int(src[r]), "anchor_variant"], "member_variants": FAMILY_SEP.join(variants),
            "n_members": int(c.loc[members, "n_members"].sum()),
            "orig_start": int(c.loc[members, "start"].min()), "orig_end": int(c.loc[members, "end"].max()),
            "anchored": True, "polarity": an.at[r, "polarity"], "onset": an.at[r, "onset"],
            "extremum": an.at[r, "extremum"], "event_end": an.at[r, "end"], "recovered": an.at[r, "recovered"],
            "depth_mv": an.at[r, "depth_mv"],
        })
    out = pd.DataFrame(out_rows)
    out["sources"], out["n_sources"] = agreement_by_main_events(out, proposals)
    report["same_event"] = int(len(rows) - len(out))
    return out[cols].sort_values(["start", "end"]).reset_index(drop=True), report


def attach_scan(cands, hits):
    """R4's scan hits (``start``, ``end``, ``p``, ``duration_s``): those overlapping a candidate set its ``scan_p``;
    the rest are returned as new candidates of kind ``r4_scan``."""
    cands = cands.copy()
    cands["scan_p"] = np.nan
    if hits is None or not len(hits):
        return cands, hits.iloc[0:0] if hits is not None else None
    cs, ce = cands["start"].to_numpy(np.int64), cands["end"].to_numpy(np.int64)
    order = np.argsort(cs, kind="stable")
    cs_sorted = cs[order]
    longest = int((ce - cs).max()) if len(cs) else 0
    scan_p = cands["scan_p"].to_numpy(dtype=float)
    own = []
    for r in hits.itertuples(index=False):
        s, e, p = int(r.start), int(r.end), float(r.p)
        lo = np.searchsorted(cs_sorted, s - max(longest, e - s), side="left")
        hi = np.searchsorted(cs_sorted, e, side="left")
        hit_any = False
        for j in order[lo:hi]:
            inter = min(e, ce[j]) - max(s, cs[j])
            shorter = max(1, min(e - s, ce[j] - cs[j]))
            if inter > 0 and inter >= AGREE_SHARE * shorter:
                hit_any = True
                scan_p[j] = p if not np.isfinite(scan_p[j]) else max(scan_p[j], p)
        if not hit_any:
            own.append(r)
    cands["scan_p"] = scan_p
    return cands, pd.DataFrame(own, columns=hits.columns) if own else hits.iloc[0:0]


def score(cands, p_r4, *, precision=None, damping=blend.DAMPING):
    """R4's probability and the blended confidence, with the formula's steps (``lifts``, JSON) and its floor."""
    cands = cands.copy()
    p = np.asarray(p_r4, dtype=float)
    cands["p_r4"] = p
    srcs = [[s for s in str(v).split(FAMILY_SEP) if s] if isinstance(v, str) else [] for v in cands["sources"]]
    cands["confidence"] = [blend.confidence(pi, s, precision, damping) for pi, s in zip(p, srcs)]
    cands["floor"] = [blend.floor_of(s, precision, damping) for s in srcs]
    cands["lifts"] = [json.dumps([[k, round(v, 4)] for k, v in blend.contributions(pi, s, precision, damping)])
                      for pi, s in zip(p, srcs)]
    return cands


def source_of(variant):
    """The source a proposal's variant belongs to (a template's settings are one source; every seed family is
    ``seed``)."""
    return family_of(variant)

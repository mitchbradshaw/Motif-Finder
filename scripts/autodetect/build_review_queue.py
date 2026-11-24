"""
build_review_queue.py
=====================
The 24 Nov Auto-detect review queue. The researcher: "build a review queue from the auto-detected events across the
channels you have been using. Review queue should only include events I have not yet reviewed, prioritised by the
highest confidence scores, including both spikes and drops, prioritised also by sequences potentially like that of
M4, aiming for clean candidate windows with clear events, somewhere between 5000-8000 or so total."

    python scripts/autodetect/build_review_queue.py            # plan: choose, write docs/autodetect/20261124_queue/
    python scripts/autodetect/build_review_queue.py --write    # then: back up the database and write the queue

The candidates are the v4 reference runs' (docs/autodetect/20261123_v4, the four channels used since 19 Nov). The
plan reads the database only. ``--write`` backs it up first (the sqlite backup API, so the WAL comes along) and then
adds machine rows only: one config, one run per channel and lane, one detection per candidate, one listed queue.
Never a verdict (CLAUDE.md rule 5).

What "not yet reviewed" means here, since Review's own check cannot see across copies of a channel
(docs/autodetect/CHANNEL_COPIES.md):
* every event span judged on ANY copy of the channel, as an annotation or an adjudication, read through the thesis
  catalogue's `collect()` and `canonical_span()`. A candidate is that event when either box covers at least half of
  the shorter one and the two are within 4x of each other's length, or the project's matching rule pairs them;
* labelled 10-minute and blind-test windows are not event judgements and never hold a candidate back;
* an event still waiting in an open queue made in the last week is left out too, so nothing is asked twice.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as K  # noqa: E402

ROOT = K.ROOT
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Working.discovery.matching import rule_from_settings, spans_match  # noqa: E402
from Working.units import read_as_mv  # noqa: E402

V4 = K.OUT
OUT = os.path.join(ROOT, "docs", "autodetect", "20261124_queue")
DB = K.DB
BUILD = "20261124"

#: How many to put in front of the researcher ("somewhere between 5000-8000 or so total").
TARGET = (5000, 8000)
#: The lowest confidence put in front of the researcher. The pipeline's own line is 0.5, but the 24 Nov plan's last
#: few hundred at 0.50-0.60 were mostly noise-sized CH14 dips; 0.6 with the clarity bar below keeps 5,000+.
MIN_CONFIDENCE = 0.6
#: Already reviewed: a judged span covers at least half of the shorter of it and the box (`candidate_events._caught`'s
#: share, the labels the v4 viewers show) - unless the judged span is over an hour AND more than 4x the box: a whole
#: train accepted in one go (CH15's 21 train acceptances run up to 45 h) says nothing about each event inside it.
SAME_SHARE, SAME_RATIO, REGION_S = 0.5, 4.0, 3600.0
#: Two candidates whose boxes share at least this much of the shorter one show one muddled window: the higher
#: priority one is kept.
OVERLAP_SHARE = 0.2
#: Review's default context padding: the window the researcher sees is the box plus this either side.
PAD_S = 120.0
#: The longest box kept: 20 minutes, or less where the channel's accepted events are shorter (the 95th percentile of
#: the boxes that land on accepted events).
MAX_BOX_S, BOX_QUANTILE = 1200.0, 0.95
#: A stretch at least this long of one repeated value is a dropout.
FLAT_S = 60.0
#: An unclean window: a one-sample step outside the box this many times the channel's step noise AND this many
#: times the steepest step inside the box (a jump much bigger than the event itself).
JUMP_NOISE_K, JUMP_EVENT_K = 30.0, 3.0
#: Not an event of its own: a rise that starts within `RETURN_GAP_S` of the end of a drop at least `RECOVERY_SHARE`
#: as deep (that drop's recovery), or a drop that starts within it of a spike's end and is at most `RETURN_TOL` x
#: its height (that spike's way back down). The pipeline folds a return only when it starts within one fall of the
#: extremum, so a slow or late one stays a candidate of its own (seen in the 24 Nov plan's first 30).
RETURN_GAP_S, RECOVERY_SHARE, RETURN_TOL = 30.0, 0.8, 1.25
#: Clear against its own window: the event's depth at least this many times the window's noise (the robust spread,
#: outside the box, of the signal about a `CLARITY_SMOOTH_S` running median). A window with no noise at all is clear.
#: Calibrated on the 24 Nov plan: noise-level CH14 dips and M4 rises in noisy stretches scored 4.6-15, clear events
#: 26 to over 1,000.
CLARITY_MIN, CLARITY_SMOOTH_S = 15.0, 10.0
#: A rise whose box runs longer than this is a slow climb or a recovery, not the sharp rise asked for.
SLOW_RISE_S = 180.0
#: A box that swings the other way by more than this many times the event's own depth holds a bigger event than the
#: one it is about (a small rise whose box runs on into a 12 mV drop, seen at rank 36 of the first write).
SWING_K = 2.0
#: A candidate in an M4-like sequence ranks as if this much more confident.
M4_BONUS = 0.1
#: Open queues made since this day hold events the researcher will judge there.
RECENT = "2026-11-17"
#: The sequence features M4-likeness is measured on (log scales where the quantity spans decades).
SEQ_FEATURES = ("log_n", "log_gap", "gap_cv", "log_dur", "log_depth", "log_sharp")


# ── inputs ───────────────────────────────────────────────────────────────────

def connect_ro():
    conn = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_candidates():
    """The four references' v4 candidates and sequences, with each reference's run and canonical recording."""
    out = []
    for ref in K.REFERENCES:
        c = pd.read_csv(os.path.join(V4, ref["key"], "candidates.csv"))
        s = pd.read_csv(os.path.join(V4, ref["key"], "sequences.csv"))
        shift = (c["start_idx"] - c["start"]).unique()
        assert len(shift) == 1, f"{ref['key']}: start_idx - start is not one offset"
        c["ref"], c["rec"], c["canonical"] = ref["key"], int(ref["rec"]), int(ref["canonical"])
        out.append((ref, c, s))
    return out


def judged_and_artifacts(conn, refs):
    """Every judged event span on any copy of the four channels, in each run recording's samples; and every span
    judged an artifact (any kind), for the clean-window check. Read through the thesis catalogue."""
    mod = K._load_catalogue_module()
    rows, recs = mod.collect(conn)
    judged = {r["key"]: [] for r in refs}
    artifacts = {r["key"]: [] for r in refs}
    kinds = {}
    for r in rows:
        if r.get("placement_ambiguous") or not r.get("valid_bounds"):
            continue
        for ref in refs:
            if int(r["canonical_recording_id"]) != int(ref["canonical"]):
                continue
            f = float(recs[int(ref["rec"])]["fs"]) / float(recs[int(ref["canonical"])]["fs"])
            s = int(round(r["canonical_start"] * f))
            e = max(int(round(r["canonical_end"] * f)), s + 1)
            row = {"start": s, "end": e, "kind": r["kind"], "verdict": r["verdict"], "ref": r["ref"],
                   "source": r.get("source")}
            kinds[(ref["key"], r["kind"])] = kinds.get((ref["key"], r["kind"]), 0) + 1
            if r["kind"] == "event_span":
                judged[ref["key"]].append(row)
            if r["verdict"] == "artifact":
                artifacts[ref["key"]].append(row)
    cols = ["start", "end", "kind", "verdict", "ref", "source"]
    return ({k: pd.DataFrame(v, columns=cols) for k, v in judged.items()},
            {k: pd.DataFrame(v, columns=cols) for k, v in artifacts.items()}, recs, mod, kinds)


def pending_spans(conn, refs, recs, mod):
    """Events still waiting in an open, unarchived detection queue made since `RECENT`, in run samples."""
    from Working.review import queues as Q
    cols = [r[1] for r in conn.execute("PRAGMA table_info(review_queues)")]
    archived = " AND archived_at IS NULL" if "archived_at" in cols else ""
    from write_review_queue import QUEUE_NAME   # this script's own queue is not "elsewhere"
    qs = conn.execute("SELECT id, name, created_at FROM review_queues WHERE created_at >= ? AND closed_at IS NULL "
                      "AND writes_to = 'adjudications' AND name != ?" + archived + " ORDER BY id",
                      (RECENT, QUEUE_NAME)).fetchall()
    by = {r["key"]: [] for r in refs}
    per_queue = []
    for q in qs:
        items = Q.queue_items(conn, int(q["id"]))
        here = 0
        for it in items:
            rec = recs[int(it["recording_id"])]
            spans = it.get("member_spans") or [(it["start_idx"], it["end_idx"])]
            for s0, e0 in spans:
                crid, cs, ce = mod.canonical_span(rec, int(s0), int(e0), recs)
                for ref in refs:
                    if int(crid) != int(ref["canonical"]):
                        continue
                    f = float(recs[int(ref["rec"])]["fs"]) / float(recs[int(ref["canonical"])]["fs"])
                    s = int(round(cs * f))
                    by[ref["key"]].append({"start": s, "end": max(int(round(ce * f)), s + 1), "queue_id": int(q["id"])})
                    here += 1
        per_queue.append({"queue_id": int(q["id"]), "name": q["name"], "pending_items": len(items),
                          "pending_spans_on_these_channels": here})
    return {k: pd.DataFrame(v, columns=["start", "end", "queue_id"]) for k, v in by.items()}, per_queue


# ── tests on one candidate ───────────────────────────────────────────────────

def same_event(cs, ce, ref_spans, rule, region_len):
    """For each candidate box [cs, ce): is it an event in `ref_spans` (`SAME_SHARE`, with spans longer than
    `region_len` samples and `SAME_RATIO` x the box left out), or does the project's matching rule pair them?"""
    out = np.zeros(len(cs), dtype=bool)
    if not len(cs) or ref_spans is None or not len(ref_spans):
        return out
    rs = ref_spans["start"].to_numpy(np.int64)
    re_ = ref_spans["end"].to_numpy(np.int64)
    order = np.argsort(rs, kind="stable")
    rs, re_ = rs[order], re_[order]
    longest = int((re_ - rs).max())
    for i in range(len(cs)):
        a, b = int(cs[i]), int(ce[i])
        lo = np.searchsorted(rs, a - longest, side="left")
        hi = np.searchsorted(rs, b, side="left")
        if hi <= lo:
            continue
        s, e = rs[lo:hi], re_[lo:hi]
        inter = np.minimum(e, b) - np.maximum(s, a)
        lc = max(b - a, 1)
        lr = np.maximum(e - s, 1)
        shorter = np.minimum(lr, lc)
        region = (lr > SAME_RATIO * lc) & (lr > region_len)
        ok = (inter > 0) & (inter >= SAME_SHARE * shorter) & ~region
        if ok.any() or any(spans_match((a, b), (int(s[j]), int(e[j])), rule=rule) for j in range(len(s)) if inter[j] > 0):
            out[i] = True
    return out


def _segments(mask):
    """[start, end) runs where `mask` is True."""
    m = np.concatenate([[False], np.asarray(mask, bool), [False]])
    d = np.diff(m.astype(np.int8))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def _any_in(seg_s, seg_e, a, b):
    """Does any [seg_s, seg_e) meet [a, b)? (segments sorted, not overlapping)"""
    k = np.searchsorted(seg_e, a, side="right")
    return k < len(seg_s) and seg_s[k] < b


def context_flags(c, x_mv, fs, artifact_spans):
    """For each candidate, what spoils its window (the box +-`PAD_S`): a gap in the data, a dropout (one value
    repeated for `FLAT_S`), a span judged an artifact, or a one-sample jump far bigger than the event's own steps
    that no candidate's box explains (a neighbouring spike in a train is an event, not an artifact)."""
    n = len(x_mv)
    pad = int(round(PAD_S * fs))
    nan_s, nan_e = _segments(~np.isfinite(x_mv))
    d = np.diff(x_mv)
    dd = np.abs(d)
    finite = np.isfinite(dd)
    noise = 1.4826 * float(np.median(np.abs(d[finite] - np.median(d[finite])))) if finite.any() else 0.0
    eq = np.zeros(n, bool)
    eq[1:] = (d == 0)
    fs_s, fs_e = _segments(eq)
    long_flat = (fs_e - fs_s) >= int(round(FLAT_S * fs))
    flat_s, flat_e = fs_s[long_flat], fs_e[long_flat]
    cover = np.zeros(len(dd) + 1, np.int64)
    np.add.at(cover, np.clip(c["start_idx"].to_numpy(np.int64), 0, len(dd)), 1)
    np.add.at(cover, np.clip(c["end_idx"].to_numpy(np.int64) - 1, 0, len(dd)), -1)
    explained = np.cumsum(cover)[:len(dd)] > 0
    big = np.flatnonzero(finite & (dd > JUMP_NOISE_K * max(noise, 1e-12)) & ~explained)
    art = artifact_spans.sort_values("start") if artifact_spans is not None and len(artifact_spans) else None
    a_s = art["start"].to_numpy(np.int64) if art is not None else np.zeros(0, np.int64)
    a_e = np.maximum.accumulate(art["end"].to_numpy(np.int64)) if art is not None else np.zeros(0, np.int64)
    # the signal about its running median (gaps bridged for the filter, then put back as gaps)
    from scipy.ndimage import median_filter
    ok = np.isfinite(x_mv)
    filled = x_mv if ok.all() else np.interp(np.arange(n), np.flatnonzero(ok), x_mv[ok])
    resid = filled - median_filter(filled, size=max(3, int(round(CLARITY_SMOOTH_S * fs)) | 1), mode="nearest")
    resid[~ok] = np.nan
    depth = c["depth_mv"].to_numpy(float)
    out = {"nan": [], "flat": [], "artifact": [], "jump": []}
    clarity = []
    for i, (s, e) in enumerate(zip(c["start_idx"].to_numpy(np.int64), c["end_idx"].to_numpy(np.int64))):
        w0, w1 = max(0, s - pad), min(n, e + pad)
        r = np.concatenate([resid[w0:s], resid[e:w1]])
        r = r[np.isfinite(r)]
        spread = 1.4826 * float(np.median(np.abs(r - np.median(r)))) if len(r) > 10 else np.nan
        clarity.append(np.inf if spread == 0 else (depth[i] / spread if spread == spread else np.nan))
        out["nan"].append(_any_in(nan_s, nan_e, w0, w1))
        out["flat"].append(_any_in(flat_s, flat_e, w0, w1))
        k = np.searchsorted(a_s, w1, side="left")
        out["artifact"].append(bool(k > 0 and a_e[k - 1] > w0))
        jumped = False
        lo, hi = np.searchsorted(big, w0, side="left"), np.searchsorted(big, w1 - 1, side="left")
        if hi > lo:
            outside = big[lo:hi][(big[lo:hi] < s) | (big[lo:hi] >= e - 1)]
            if len(outside):
                inside = dd[s:max(s + 1, e - 1)]
                inside = inside[np.isfinite(inside)]
                own = float(inside.max()) if len(inside) else 0.0
                jumped = bool(dd[outside].max() > JUMP_EVENT_K * max(own, 1e-12))
        out["jump"].append(jumped)
    flags = {k: np.asarray(v, bool) for k, v in out.items()}
    return flags, noise, np.asarray(clarity, float)


def swings_back(c, x_mv):
    """For each candidate: does its box swing the other way, past where the event started, by more than `SWING_K`
    x its own depth (a rise whose box runs on into a deep drop, or a drop whose box runs up into a big spike)?"""
    a = int((c["start_idx"] - c["start"]).iloc[0])
    out = np.zeros(len(c), bool)
    for i, (s, e, on, pol, depth) in enumerate(zip(c["start_idx"].to_numpy(np.int64), c["end_idx"].to_numpy(np.int64),
                                                    c["onset"].to_numpy(float), c["polarity"].to_numpy(),
                                                    c["depth_mv"].to_numpy(float))):
        on = int(on + a) if on == on else int(s)
        seg = x_mv[s:e]
        pre = x_mv[max(0, on - 3):on + 1]
        if not len(seg) or not np.isfinite(pre).any() or not np.isfinite(seg).any():
            continue
        base = float(np.nanmean(pre))
        swing = (base - float(np.nanmin(seg))) if pol == "spike" else (float(np.nanmax(seg)) - base)
        out[i] = swing > SWING_K * max(float(depth), 1e-9)
    return out


def is_return(c, fs):
    """For each candidate: is it the recovery of the drop just before it, or the way back down of the spike just
    before it (`RETURN_GAP_S`, `RECOVERY_SHARE`, `RETURN_TOL`)? Every candidate of the channel counts as the one
    before, whatever its confidence or whether it was judged."""
    a = int((c["start_idx"] - c["start"]).iloc[0])
    gap = int(round(RETURN_GAP_S * fs))
    order = np.argsort(c["start_idx"].to_numpy(np.int64), kind="stable")
    s = c["start_idx"].to_numpy(np.int64)[order]
    e = c["end_idx"].to_numpy(np.int64)[order]
    ends_ev = (c["event_end"].to_numpy(float)[order] + a)
    onset = (c["onset"].to_numpy(float)[order] + a)
    pol = c["polarity"].to_numpy()[order]
    depth = c["depth_mv"].to_numpy(float)[order]
    out_sorted = np.zeros(len(c), bool)
    longest = int((e - s).max()) if len(c) else 0
    for k in range(len(c)):
        on = onset[k] if onset[k] == onset[k] else s[k]
        lo = np.searchsorted(s, s[k] - longest - gap, side="left")
        for j in range(lo, k):
            if pol[j] == pol[k]:
                continue
            end_j = max(e[j], ends_ev[j] if ends_ev[j] == ends_ev[j] else e[j])
            if not (on - gap <= end_j <= on + gap):
                continue
            if pol[k] == "spike" and depth[j] >= RECOVERY_SHARE * depth[k]:
                out_sorted[k] = True
                break
            if pol[k] == "drop" and depth[k] <= RETURN_TOL * depth[j]:
                out_sorted[k] = True
                break
    out = np.zeros(len(c), bool)
    out[order] = out_sorted
    return out


# ── sequences like M4's ──────────────────────────────────────────────────────

def sequence_table(c, s, ref_key):
    """Each sequence's make-up: kind, how many, how far apart and how regularly, how long, how deep, how sharp."""
    rows = []
    for q in s.itertuples(index=False):
        m = c[c["sequence_id"] == q.sequence_id].sort_values("start_s")
        if not len(m):
            continue
        gaps = np.diff(m["start_s"].to_numpy(float))
        rows.append({"ref": ref_key, "sequence_id": int(q.sequence_id), "polarity": q.polarity, "n": len(m),
                     "span_h": float((q.end_s - q.start_s) / 3600.0),
                     "med_gap_s": float(np.median(gaps)) if len(gaps) else np.nan,
                     "gap_cv": float(np.std(gaps) / np.mean(gaps)) if len(gaps) > 1 and np.mean(gaps) > 0 else np.nan,
                     "med_dur_s": float(m["duration_s"].median()), "med_depth_mv": float(m["depth_mv"].median()),
                     "med_sharp": float(m["sharpness"].median()), "mean_conf": float(m["confidence"].mean())})
    t = pd.DataFrame(rows)
    if not len(t):
        return t
    t["log_n"] = np.log10(t["n"])
    t["log_gap"] = np.log10(t["med_gap_s"].clip(lower=1))
    t["log_dur"] = np.log10(t["med_dur_s"].clip(lower=0.5))
    t["log_depth"] = np.log10(t["med_depth_mv"].clip(lower=1e-3))
    t["log_sharp"] = np.log10(t["med_sharp"].clip(lower=0.1))
    return t


def m4_likeness(seqs, m4_key):
    """Distance from each sequence to the nearest of M4's sequences of the same kind (drops or rises), in units of
    M4's own spread on each feature; M4-like when that is no further than three in four of M4's sequences are from
    their own nearest neighbour. M4's sequences are M4-like by definition."""
    t = seqs.copy()
    m4 = t[t["ref"] == m4_key]
    feats = list(SEQ_FEATURES)
    fill = m4[feats].median()
    z_all = t[feats].fillna(fill)
    mu, sd = m4[feats].fillna(fill).mean(), m4[feats].fillna(fill).std().replace(0, 1.0)
    z = (z_all - mu) / sd
    zm = z.loc[m4.index]
    nn = []
    for i in m4.index:
        same = zm[(m4["polarity"] == m4.loc[i, "polarity"]) & (m4.index != i)]
        nn.append(float(np.sqrt(((same - zm.loc[i]) ** 2).sum(axis=1)).min()) if len(same) else np.nan)
    threshold = float(np.nanquantile(nn, 0.75))
    dist = []
    for i in t.index:
        same = zm[m4["polarity"] == t.loc[i, "polarity"]]
        if t.loc[i, "ref"] == m4_key:
            dist.append(0.0)
        elif len(same):
            dist.append(float(np.sqrt(((same - z.loc[i]) ** 2).sum(axis=1)).min()))
        else:
            dist.append(np.inf)
    t["m4_distance"] = dist
    t["m4_like"] = t["m4_distance"] <= threshold
    return t, threshold


# ── the choice ───────────────────────────────────────────────────────────────

def overlap_keep(c, order):
    """Walk the candidates in `order` (best first) and keep one unless its box shares `OVERLAP_SHARE` of the
    shorter box with one already kept on the same channel."""
    import bisect
    kept = np.zeros(len(c), bool)
    by_ref = {}
    s_all, e_all = c["start_idx"].to_numpy(np.int64), c["end_idx"].to_numpy(np.int64)
    refs = c["ref"].to_numpy()
    for i in order:
        starts, ends, longest = by_ref.setdefault(refs[i], ([], [], [0]))
        s, e = int(s_all[i]), int(e_all[i])
        lo = bisect.bisect_left(starts, s - longest[0])
        hi = bisect.bisect_left(starts, e)
        clash = False
        for j in range(lo, hi):
            ks, ke = starts[j], ends[j]
            inter = min(e, ke) - max(s, ks)
            if inter > 0 and inter >= OVERLAP_SHARE * max(1, min(e - s, ke - ks)):
                clash = True
                break
        if not clash:
            kept[i] = True
            k = bisect.bisect_left(starts, s)
            starts.insert(k, s)
            ends.insert(k, e)
            longest[0] = max(longest[0], e - s)
    return kept


def plan(conn):
    t0 = time.perf_counter()
    loaded = load_candidates()
    refs = [r for r, _, _ in loaded]
    rule = rule_from_settings(conn)
    judged, artifacts, recs, mod, kinds = judged_and_artifacts(conn, refs)
    pending, per_queue = pending_spans(conn, refs, recs, mod)
    frames, seq_tables = [], []
    caps = {}
    for ref, c, s in loaded:
        key = ref["key"]
        rec = recs[int(ref["rec"])]
        fs = float(rec["fs"])
        factor, _note = read_as_mv(rec.get("units"))
        x = np.asarray(np.load(os.path.join(ROOT, rec["npy_path"]), mmap_mode="r"), dtype=np.float64) * factor
        cs, ce = c["start_idx"].to_numpy(np.int64), c["end_idx"].to_numpy(np.int64)
        region_len = int(round(REGION_S * fs))
        c["reviewed"] = same_event(cs, ce, judged[key], rule, region_len)
        c["pending"] = same_event(cs, ce, pending[key], rule, region_len)
        flags, noise, clarity = context_flags(c, x, fs, artifacts[key])
        for k, v in flags.items():
            c[f"ctx_{k}"] = v
        c["clarity"] = clarity
        c["unclear"] = ~(np.nan_to_num(clarity, nan=0.0) >= CLARITY_MIN)
        c["slow_rise"] = (c["polarity"] == "spike") & (c["duration_s"] > SLOW_RISE_S)
        c["swings_back"] = swings_back(c, x)
        on_acc = c[(c["known"] == "accepted")]
        q = float(on_acc["duration_s"].quantile(BOX_QUANTILE)) if len(on_acc) >= 10 else MAX_BOX_S
        caps[key] = min(MAX_BOX_S, q)
        c["too_long"] = c["duration_s"] > caps[key]
        src = c["sources"].fillna("").astype(str)
        c["no_source"] = (c["kind"] != "proposal") | (src == "")
        c["is_return"] = is_return(c, fs)
        c["step_noise_mv"] = noise
        frames.append(c)
        seq_tables.append(sequence_table(c, s, key))
    allc = pd.concat(frames, ignore_index=True)
    seqs, threshold = m4_likeness(pd.concat(seq_tables, ignore_index=True), "M4_CH1_A1")
    like = {(r.ref, int(r.sequence_id)): (bool(r.m4_like), float(r.m4_distance)) for r in seqs.itertuples(index=False)}
    allc["m4_like"] = [like.get((r, int(q)), (False, np.nan))[0] if q >= 0 else False
                       for r, q in zip(allc["ref"], allc["sequence_id"])]
    allc["m4_distance"] = [like.get((r, int(q)), (False, np.nan))[1] if q >= 0 else np.nan
                           for r, q in zip(allc["ref"], allc["sequence_id"])]
    allc["priority"] = allc["confidence"] + M4_BONUS * allc["m4_like"].astype(float)

    # the reason each candidate is left out, the first that applies
    reasons = [(f"below {MIN_CONFIDENCE:g} confidence", allc["confidence"] < MIN_CONFIDENCE),
               ("no detector, seed or rule vouched for it (R4 alone)", allc["no_source"]),
               ("the recovery or way back of the event just before it", allc["is_return"]),
               ("already reviewed (any copy)", allc["reviewed"]),
               ("waiting in an open queue (54-56)", allc["pending"]),
               ("box longer than the channel's cap", allc["too_long"]),
               ("a slow rise, not a spike (box over 3 minutes)", allc["slow_rise"]),
               ("its box runs into a bigger event the other way", allc["swings_back"]),
               ("gap in the data in its window", allc["ctx_nan"]),
               ("dropout (flat line) in its window", allc["ctx_flat"]),
               ("a span you judged an artifact in its window", allc["ctx_artifact"]),
               ("a jump far bigger than the event in its window", allc["ctx_jump"]),
               ("not clear against the noise around it", allc["unclear"])]
    allc["left_out"] = ""
    for name, mask in reasons:
        allc.loc[(allc["left_out"] == "") & mask.to_numpy(bool), "left_out"] = name
    eligible = allc.index[allc["left_out"] == ""].to_numpy()
    order = sorted(eligible, key=lambda i: (-allc.at[i, "priority"], -allc.at[i, "confidence"],
                                            -(allc.at[i, "sharpness"] if allc.at[i, "sharpness"] == allc.at[i, "sharpness"] else 0)))
    kept = overlap_keep(allc, order)
    lost = [i for i in order if not kept[i]]
    allc.loc[lost, "left_out"] = "its box overlaps a better candidate's"
    chosen = [i for i in order if kept[i]]
    if len(chosen) > TARGET[1]:
        allc.loc[chosen[TARGET[1]:], "left_out"] = f"beyond the first {TARGET[1]:,}"
        chosen = chosen[:TARGET[1]]
    sel = allc.loc[chosen].copy()
    sel["rank"] = np.arange(1, len(sel) + 1)
    return {"all": allc, "selected": sel, "sequences": seqs, "m4_threshold": threshold, "caps": caps,
            "per_queue": per_queue, "rule": rule, "kinds": {f"{k[0]}|{k[1]}": v for k, v in kinds.items()},
            "judged_counts": {k: int(len(v)) for k, v in judged.items()},
            "artifact_counts": {k: int(len(v)) for k, v in artifacts.items()},
            "pending_counts": {k: int(len(v)) for k, v in pending.items()}, "seconds": time.perf_counter() - t0}


def report(p):
    allc, sel = p["all"], p["selected"]
    by_ref = {}
    for key, g in allc.groupby("ref"):
        s = sel[sel["ref"] == key]
        by_ref[key] = {"candidates": int(len(g)),
                       "left_out": {k: int(v) for k, v in g["left_out"].value_counts().items() if k},
                       "selected": int(len(s)), "selected_drops": int((s["polarity"] == "drop").sum()),
                       "selected_rises": int((s["polarity"] == "spike").sum()),
                       "selected_m4_like": int(s["m4_like"].sum()), "box_cap_s": round(p["caps"][key], 1),
                       "judged_event_spans": p["judged_counts"][key], "artifact_spans": p["artifact_counts"][key],
                       "pending_spans": p["pending_counts"][key]}
    return {"built": dt.datetime.now().isoformat(timespec="seconds"), "selected": int(len(sel)),
            "drops": int((sel["polarity"] == "drop").sum()), "rises": int((sel["polarity"] == "spike").sum()),
            "m4_like": int(sel["m4_like"].sum()),
            "confidence": {q: round(float(sel["confidence"].quantile(v)), 3) for q, v in
                           (("min", 0.0), ("p10", 0.1), ("median", 0.5))} if len(sel) else {},
            "by_channel": by_ref, "open_queues_checked": p["per_queue"], "m4_threshold": round(p["m4_threshold"], 3),
            "matching_rule": p["rule"], "seconds": round(p["seconds"], 1),
            "settings": {"min_confidence": MIN_CONFIDENCE, "same_share": SAME_SHARE, "same_ratio": SAME_RATIO, "region_s": REGION_S,
                         "overlap_share": OVERLAP_SHARE, "pad_s": PAD_S, "max_box_s": MAX_BOX_S,
                         "box_quantile": BOX_QUANTILE, "flat_s": FLAT_S, "jump_noise_k": JUMP_NOISE_K,
                         "jump_event_k": JUMP_EVENT_K, "return_gap_s": RETURN_GAP_S,
                         "recovery_share": RECOVERY_SHARE, "return_tol": RETURN_TOL, "clarity_min": CLARITY_MIN,
                         "clarity_smooth_s": CLARITY_SMOOTH_S, "slow_rise_s": SLOW_RISE_S, "swing_k": SWING_K, "m4_bonus": M4_BONUS, "recent": RECENT, "target": TARGET}}


SELECTED_COLUMNS = ["rank", "ref", "rec", "candidate_id", "start_idx", "end_idx", "start_s", "duration_s", "polarity",
                    "confidence", "priority", "p_r4", "sources", "sharpness", "depth_mv", "clarity", "sequence_id", "m4_like",
                    "m4_distance", "run", "runs"]


def save_plan(p):
    os.makedirs(OUT, exist_ok=True)
    p["selected"][SELECTED_COLUMNS].to_csv(os.path.join(OUT, "selected.csv"), index=False)
    cols = ["ref", "candidate_id", "start_idx", "end_idx", "polarity", "confidence", "priority", "duration_s",
            "sequence_id", "m4_like", "clarity", "left_out", "reviewed", "pending", "too_long", "slow_rise", "swings_back", "unclear",
            "no_source", "is_return", "ctx_nan",
            "ctx_flat", "ctx_artifact", "ctx_jump"]
    p["all"][cols].to_csv(os.path.join(OUT, "all_candidates.csv"), index=False)
    p["sequences"].to_csv(os.path.join(OUT, "sequences_m4_likeness.csv"), index=False)
    rep = report(p)
    with open(os.path.join(OUT, "plan.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, default=str)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="back up the database, then write the queue")
    ap.add_argument("--update", metavar="WHY", help="back up, then bring the written queue in line with this plan")
    args = ap.parse_args(argv)
    conn = connect_ro()
    conn.execute("BEGIN")          # one cutoff for every read, even while Review is in use
    try:
        p = plan(conn)
    finally:
        conn.rollback()
        conn.close()
    rep = save_plan(p)
    print(json.dumps({k: rep[k] for k in ("selected", "drops", "rises", "m4_like", "confidence", "m4_threshold",
                                          "seconds")}, indent=1))
    for key, b in rep["by_channel"].items():
        print(key, json.dumps(b))
    print("open queues:", json.dumps(rep["open_queues_checked"]))
    if args.write:
        from write_review_queue import write  # noqa: E402  (beside this file)
        print(json.dumps(write(p, db=DB, out=OUT, settings=rep["settings"]), indent=1, default=str))
    elif args.update:
        from write_review_queue import update  # noqa: E402
        print(json.dumps(update(p, db=DB, out=OUT, settings=rep["settings"], reason=args.update), indent=1, default=str))


if __name__ == "__main__":
    main()

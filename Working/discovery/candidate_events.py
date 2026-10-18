"""
candidate_events.py
===================
Round A_2, RQ1b / RQ4b (2026-10-18): the RQ4b detector sweep's detections on one recording, merged into
**candidate events**; the researcher's existing verdicts attached to the events they cover; a seeded, stratified
sample of the events nobody has judged, put to Review blind and shuffled; and the estimator that turns the answers
(with the existing verdicts counted as a census) into a precision per agreement level, per detector family and per
setting.

In plain words
--------------
Forty-odd detector settings ran over every channel. Where several of them mark the same stretch, that is one
candidate event, not forty, and one verdict on it scores every detector that found it. Some events have been judged
already (a Library review, a seed search, the old 10-minute labels): those verdicts are kept as training data and the
event is never asked about again. Of the rest, a fixed number is drawn at random from each agreement level and from
each selective detector, so that the share you accept is an honest estimate of how often that kind of event is real.
That estimate is what lets the hundreds of thousands of events nobody will look at be used at all.

The rules, each one stated once
-------------------------------
1. **The sweep.** A recording's live, completed, real template runs: Discovery runs of kind ``template`` not taken
   off their session, runs not discarded (``superseded_at``), no paired null (``queries.not_surrogate``), no window
   of a windowed application (``queries.not_window_part``; its stitched run is the result). One run per setting and
   channel: the one covering the longest span, then the newest. ``NEGATIVE_CONTROLS`` are left out (the 1-minute
   CNNs call ~96 % of minutes interesting, W4-A). Seed searches are not detectors: their verdicts arrive as labels.
2. **The same event** is §4.6 (``Working.discovery.matching``: reciprocal IoU and onset agreement scaled to the
   candidate's duration, thresholds from Settings › Analysis defaults), the rule Review uses to call a detection
   "already judged". One rule, so the two never disagree about what was judged.
3. **Events.** Per channel, settings are taken rarest first. Each detection joins the event whose anchor it matches
   best (``matching.match_span_sets``, one-to-one), else it founds an event and becomes its anchor. So an event holds
   at most one detection per setting, a setting's own overlapping detections never merge (a dense detector cannot
   chain a recording into one event), a long detection never swallows a short one, and the anchor (the span shown in
   Review and used for training) comes from the most selective detector that found the event.
4. **Agreement** is looser than membership: a family agrees with an event when one of its detections overlaps at
   least half of the shorter of the two (a broad detection covering the event, or a short one inside a long event).
   Settings of one template are one family, and so are the four CNN models of one scale.
5. **Existing verdicts** (annotations and adjudications, deleted spans ignored): an adjudication on one of the event's
   own detections, or a human span that is the same event (rule 2), labels it; a seed verdict is interesting (Q41).
   Otherwise the human spans that wholly hold the event decide, the most specific first: of those, the shortest and
   any at most ``SPECIFIC_FACTOR`` times as long. If they say ``not_interesting`` (or ``artifact``), that is the
   event's label (Q-W1); if they say interesting, the event stays unjudged (Q-W1). Either way an event held by any
   interesting span is flagged ``inside_interesting``. Two same-event verdicts that disagree, or specific spans that
   disagree (two overlapping 10-minute windows, one yes and one no), are a ``conflict``: unjudged, never resolved
   silently. ``unsure`` is kept as unsure and is neither asked again nor counted. Each label says what it rests on
   (``label_basis``): ``window`` when every verdict behind it was given on a judged window (``WINDOW_SOURCES``: the
   old 10-minute labels, the blind test), else ``event``. The researcher's decision (2026-10-18): a window label
   says something happened in that stretch, not what shape it was, so it teaches event-versus-background only, never
   a shape class.
6. **The sample.** Only unjudged events (conflicts included) are drawn. Strata: the first ``SELECTIVE_FAMILIES``
   family among an event's own detectors, else its agreement level (``AGREEMENT_LEVELS``). A simple random sample in
   each, weight N_h / n_h, served in a seeded random order through one blind queue over each event's anchor
   detection, so a verdict lands in ``adjudications`` like any other.
7. **The estimate.** Per group, (judged-before positives + Σ w·y) / (judged-before count + Σ w), weights recomputed
   over the answered items of each stratum; unsure and unanswered items are counted and left out. 95 % intervals by
   resampling the answered items within each stratum; a stratum answered in full has no sampling error.

The held-out recording (``Working.config.HELD_OUT_RECORDING_FILE``) is refused by name, whatever Settings ›
Datasets' lock says: it is RQ1b's exam (2026-10-18).

Bulk stays on disk (CLAUDE.md rule 4): a table is ``events.parquet`` + ``members.parquet`` + ``meta.json`` under its
key; a sample is ``sample.parquet`` + ``labels.parquet`` (the labels its frame was drawn against) + ``meta.json``.

Headless: numpy and pandas only; no UI library (CLAUDE.md rule 1).
"""

from __future__ import annotations

import datetime as _dt
import fnmatch
import json
import math
import os
from bisect import bisect_left, bisect_right

import numpy as np
import pandas as pd

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database import queries as _queries
from Working.discovery.matching import match_quality, match_span_sets, normalise_rule, rule_from_settings
from Working.discovery.spans import absolute_bounds

TABLE_VERSION = 2

#: rule 5: verdicts given on WINDOWS someone judged, not on events. A label resting only on these says something
#: happened in the stretch, not what shape it was; the researcher (2026-10-18, decision 3): such labels teach
#: event-versus-background only, never shape classes (``label_basis`` = "window")
WINDOW_SOURCES = ("imported_10min", "blind_test_review")

#: fnmatch patterns over template names left out of the sweep: W4-A's 1-minute CNNs, a negative control
NEGATIVE_CONTROLS = ("cnn_*_1min",)

#: the families sampled on their own, rarest-firing first: an event goes to the first of these among its own
#: detectors (rule 6), so each gets enough verdicts for its own precision
SELECTIVE_FAMILIES = ("drop_detection_v1", "drop_detection_v5", "wavelet_encoded", "symbol_search",
                      "BEADs_invert_detect_v1", "signal_threshold")

#: agreement levels as (low, high) family counts, inclusive; high None = open-ended
AGREEMENT_LEVELS = ((1, 2), (3, 4), (5, 6), (7, 8), (9, None))
DEFAULT_PER_LEVEL = 100
DEFAULT_PER_FAMILY = 50

#: rule 4: a family agrees when one detection overlaps at least this share of the shorter span
AGREE_SHARE = 0.5

#: rule 5: of the human spans that wholly hold an event, those at most this many times the shortest one's length
#: decide (a 90-hour catalogue region says little about one event; a 10-minute window judged around it says a lot)
SPECIFIC_FACTOR = 2.0

FAMILY_SEP = "|"
LABEL_OF = {"interesting": "interesting", "seed": "interesting", "not_interesting": "not_interesting",
            "artifact": "artifact", "unsure": "unsure"}
Y_OF = {"interesting": 1.0, "seed": 1.0, "not_interesting": 0.0, "artifact": 0.0}
JUDGED = ("interesting", "not_interesting", "artifact")

_ID_CHUNK = 400
_MAX_PAIRS = 4_000_000

EVENT_COLUMNS = ("event_id", "recording_id", "channel", "start", "end", "anchor_detection_id", "anchor_variant",
                 "n_members", "matched_families", "n_matched_families", "agree_families", "n_agree", "label",
                 "label_kind", "label_basis", "label_refs", "inside_interesting")


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _chunks(ids, size=_ID_CHUNK):
    ids = list(ids)
    for i in range(0, len(ids), size):
        yield ids[i:i + size]


def _atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    os.replace(tmp, path)


# ── families ────────────────────────────────────────────────────────────────

def family_of(variant):
    """The detector family of a template variant: the template before ``__`` (its settings are one family); the
    four CNN models of one scale are one family (``cnn_10min``); every matrix-profile template is one."""
    base = str(variant).split("__", 1)[0]
    if base.startswith("cnn_"):
        return "cnn_" + base.rsplit("_", 1)[1]
    if base.startswith("mp_"):
        return "matrix_profile"
    return base


def _families(cell):
    return set(str(cell).split(FAMILY_SEP)) if isinstance(cell, str) and cell else set()


# ── rule 1: the sweep ───────────────────────────────────────────────────────

def _refuse_held_out(source_file):
    if str(source_file) == HELD_OUT_RECORDING_FILE:
        raise PermissionError(
            f"{source_file} is the held-out exam (RQ1b, 2026-10-18): no candidate events, sample or queue are made "
            "from it, whatever Settings › Datasets' lock says")


def load_sweep_detections(conn, source_file, *, exclude=NEGATIVE_CONTROLS):
    """Rule 1. Returns ``{recordings: {id: {channel, n_samples, fs}}, runs: [...], skipped: [...],
    excluded_variants: [...], n_degenerate: int, detections: DataFrame}``; the detections carry
    ``detection_id, run_id, recording_id, variant, start, end`` in channel-absolute samples."""
    _refuse_held_out(source_file)
    recordings = {int(r[0]): {"channel": int(r[1]), "n_samples": int(r[2]), "fs": float(r[3])}
                  for r in conn.execute("SELECT id, channel, n_samples, fs FROM recordings WHERE source_file = ? "
                                        "ORDER BY channel", (str(source_file),)).fetchall()}
    if not recordings:
        raise ValueError(f"no recording {source_file!r} in this database")
    names = {}
    for gid, name in conn.execute(
            "SELECT DISTINCT run_group_id, template_name FROM discovery_runs WHERE kind = 'template' "
            "AND template_name IS NOT NULL AND run_group_id IS NOT NULL AND removed_at IS NULL "
            "AND superseded_at IS NULL").fetchall():
        names.setdefault(int(gid), set()).add(str(name))
    ids = ",".join(str(r) for r in recordings)
    rows = conn.execute(
        f"SELECT r.id, r.recording_id, r.run_group_id, r.span_start, r.span_end FROM runs r "
        f"WHERE r.recording_id IN ({ids}) AND r.status = 'completed' AND r.superseded_at IS NULL "
        f"AND r.run_group_id IS NOT NULL AND {_queries.not_surrogate('r')} AND {_queries.not_window_part('r')} "
        f"ORDER BY r.id").fetchall()
    chosen, skipped, excluded = {}, [], set()
    for run_id, rid, gid, s0, s1 in rows:
        templates = names.get(int(gid))
        if not templates:
            continue                                # not a template run: a seed search, an Analyse run
        if len(templates) > 1:
            skipped.append({"run_id": int(run_id), "variant": FAMILY_SEP.join(sorted(templates)),
                            "recording_id": int(rid), "reason": "its run group names more than one template"})
            continue
        variant = next(iter(templates))
        if any(fnmatch.fnmatchcase(variant, p) for p in exclude):
            excluded.add(variant)
            continue
        key = (variant, int(rid))
        rank = (int(s1) - int(s0), int(run_id))     # the longest span, then the newest
        prev = chosen.get(key)
        if prev is None or rank > prev["rank"]:
            if prev is not None:
                skipped.append({"run_id": prev["run_id"], "variant": variant, "recording_id": int(rid),
                                "reason": f"run {int(run_id)} of the same setting on this channel covers a longer "
                                          "span or is newer"})
            chosen[key] = {"rank": rank, "run_id": int(run_id), "span_start": int(s0 or 0)}
        else:
            skipped.append({"run_id": int(run_id), "variant": variant, "recording_id": int(rid),
                            "reason": f"run {prev['run_id']} of the same setting on this channel covers a longer "
                                      "span or is newer"})
    by_run = {c["run_id"]: (key, c["span_start"]) for key, c in chosen.items()}
    out = []
    for chunk in _chunks(sorted(by_run)):
        marks = ",".join("?" * len(chunk))
        for d_id, run_id, s, e in conn.execute(
                f"SELECT id, run_id, start_idx, end_idx FROM detections WHERE run_id IN ({marks})", chunk):
            (variant, rid), s0 = by_run[int(run_id)]
            a, b = absolute_bounds(s, e, s0)
            out.append((int(d_id), int(run_id), rid, variant, a, b))
    det = pd.DataFrame(out, columns=["detection_id", "run_id", "recording_id", "variant", "start", "end"])
    for c in ("detection_id", "run_id", "recording_id", "start", "end"):
        det[c] = det[c].astype(np.int64)
    degenerate = det["end"] <= det["start"]
    n_degenerate = int(degenerate.sum())
    det = det[~degenerate].sort_values(["recording_id", "variant", "start", "detection_id"]).reset_index(drop=True)
    counts = det.groupby("run_id").size().to_dict()
    runs = sorted(({"run_id": c["run_id"], "variant": key[0], "recording_id": key[1],
                    "n_detections": int(counts.get(c["run_id"], 0))} for key, c in chosen.items()),
                  key=lambda r: (r["variant"], r["recording_id"], r["run_id"]))
    return {"recordings": recordings, "runs": runs, "skipped": skipped, "excluded_variants": sorted(excluded),
            "n_degenerate": n_degenerate, "detections": det}


# ── rule 3: events ──────────────────────────────────────────────────────────

def _events_of_recording(d, rule):
    counts = d.groupby("variant").size()
    order = sorted(counts.index, key=lambda v: (int(counts[v]), str(v)))
    a_start, a_end, a_det, a_var = [], [], [], []
    m_event, m_det = [], []
    for variant in order:
        dv = d[d["variant"] == variant].sort_values(["start", "end", "detection_id"])
        cands = list(zip(dv["start"].tolist(), dv["end"].tolist()))
        det_ids = dv["detection_id"].tolist()
        got = match_span_sets(cands, list(zip(a_start, a_end)), rule=rule) if a_start else \
            {"pairs": [], "candidate_only": list(range(len(cands)))}
        for p in got["pairs"]:
            m_event.append(p["reference"])
            m_det.append(det_ids[p["candidate"]])
        for ci in got["candidate_only"]:
            m_event.append(len(a_start))
            m_det.append(det_ids[ci])
            a_start.append(cands[ci][0])
            a_end.append(cands[ci][1])
            a_det.append(det_ids[ci])
            a_var.append(variant)
    ev = pd.DataFrame({"tmp": np.arange(len(a_start)), "start": a_start, "end": a_end, "anchor_detection_id": a_det,
                       "anchor_variant": a_var})
    ev = ev.sort_values(["start", "end", "anchor_detection_id"]).reset_index(drop=True)
    new_id = np.empty(len(ev), dtype=np.int64)
    new_id[ev["tmp"].to_numpy()] = np.arange(len(ev))
    mem = pd.DataFrame({"event_id": new_id[np.asarray(m_event, dtype=np.int64)] if m_event else
                        np.zeros(0, np.int64), "detection_id": np.asarray(m_det, dtype=np.int64)})
    return ev.drop(columns="tmp"), mem


def build_events(detections, *, rule=None):
    """Rule 3. ``detections`` as `load_sweep_detections` returns them. Returns ``(events, members)``: one row per
    event (anchor span, anchor detection and setting, members, the families that found it) and one row per
    detection (its event)."""
    rule = normalise_rule(rule)
    ev_parts, mem_parts, base = [], [], 0
    for rid, d in detections.groupby("recording_id", sort=True):
        ev, mem = _events_of_recording(d, rule)
        ev.insert(0, "event_id", np.arange(base, base + len(ev), dtype=np.int64))
        ev.insert(1, "recording_id", np.int64(rid))
        mem["event_id"] = mem["event_id"] + base
        base += len(ev)
        ev_parts.append(ev)
        mem_parts.append(mem)
    if not ev_parts:
        events = pd.DataFrame({c: pd.Series(dtype="int64") for c in ("event_id", "recording_id", "start", "end",
                                                                      "anchor_detection_id")})
        events["anchor_variant"] = pd.Series(dtype=object)
        members = pd.DataFrame({c: pd.Series(dtype="int64") for c in ("event_id", "detection_id")})
    else:
        events = pd.concat(ev_parts, ignore_index=True)
        members = pd.concat(mem_parts, ignore_index=True)
    members = members.merge(detections[["detection_id", "run_id", "recording_id", "variant", "start", "end"]],
                            on="detection_id", how="left")
    members["family"] = members["variant"].map(family_of)
    members = members.sort_values(["event_id", "detection_id"]).reset_index(drop=True)
    fams = members.groupby("event_id")["family"].agg(lambda s: FAMILY_SEP.join(sorted(set(s))))
    events["n_members"] = events["event_id"].map(members.groupby("event_id").size()).fillna(0).astype(np.int64)
    events["matched_families"] = events["event_id"].map(fams).astype(object)
    events["n_matched_families"] = [len(_families(f)) for f in events["matched_families"]]
    return events, members


# ── rule 4: agreement ───────────────────────────────────────────────────────

def _pairs(lo, hi):
    """Index pairs (row, j) for every row and every j in [lo[row], hi[row])."""
    c = np.maximum(hi - lo, 0)
    n = int(c.sum())
    rows = np.repeat(np.arange(len(lo)), c)
    offs = np.arange(n) - np.repeat(np.cumsum(c) - c, c)
    return rows, np.repeat(lo, c) + offs


def _chunked(counts, limit=_MAX_PAIRS):
    """Row ranges whose candidate counts sum to at most `limit` (a single heavier row is its own range)."""
    cs = np.cumsum(counts)
    start = 0
    while start < len(counts):
        base = cs[start - 1] if start else 0
        stop = max(int(np.searchsorted(cs, base + limit, side="right")), start + 1)
        yield start, stop
        start = stop


def _caught(es, ee, ds, de, share=AGREE_SHARE):
    """For each event [es, ee): does a detection [ds, de) overlap at least `share` of the shorter of the two?"""
    out = np.zeros(len(es), dtype=bool)
    if not len(es) or not len(ds):
        return out
    order = np.argsort(ds, kind="stable")
    ds, de = ds[order], de[order]
    dlen = np.maximum(de - ds, 1)
    lo = np.searchsorted(ds, es - int(dlen.max()), side="left")
    hi = np.searchsorted(ds, ee, side="left")
    for a, b in _chunked(np.maximum(hi - lo, 0)):
        r, j = _pairs(lo[a:b], hi[a:b])
        if not len(r):
            continue
        r = r + a
        inter = np.minimum(de[j], ee[r]) - np.maximum(ds[j], es[r])
        shorter = np.minimum(dlen[j], np.maximum(ee[r] - es[r], 1))
        ok = (inter > 0) & (inter >= share * shorter)
        out[r[ok]] = True
    return out


def add_agreement(events, detections, *, share=AGREE_SHARE):
    """Rule 4: ``agree_families`` (the families that agree) and ``n_agree`` on a copy of `events`."""
    events = events.copy()
    det = detections.assign(family=detections["variant"].map(family_of))
    families = sorted(det["family"].unique())
    rec = events["recording_id"].to_numpy()
    es, ee = events["start"].to_numpy(np.int64), events["end"].to_numpy(np.int64)
    hits = np.zeros((len(events), len(families)), dtype=bool)
    where = {int(r): np.flatnonzero(rec == r) for r in np.unique(rec)}
    for (rid, fam), g in det.groupby(["recording_id", "family"]):
        idx = where.get(int(rid))
        if idx is None or not len(idx):
            continue
        hits[idx, families.index(fam)] = _caught(es[idx], ee[idx], g["start"].to_numpy(np.int64),
                                                  g["end"].to_numpy(np.int64), share)
    events["agree_families"] = [FAMILY_SEP.join(f for f, h in zip(families, row) if h) for row in hits]
    events["n_agree"] = hits.sum(axis=1).astype(np.int64)
    return events


# ── rule 5: existing verdicts ───────────────────────────────────────────────

def _human_spans(conn, recording_ids, skip_adjudications=()):
    """`{recording_id: DataFrame(start, end, label, ref, basis)}`: live annotations, and adjudications on any real
    run's detections (in channel-absolute samples), except the adjudications in `skip_adjudications`. `basis` is
    "window" for a verdict on a judged window (`WINDOW_SOURCES`), else "event"."""
    rows = []
    ids = sorted(int(r) for r in recording_ids)
    for chunk in _chunks(ids):
        marks = ",".join("?" * len(chunk))
        for aid, rid, s, e, verdict, source in conn.execute(
                f"SELECT id, recording_id, start_idx, end_idx, verdict, source FROM annotations "
                f"WHERE deleted_at IS NULL AND recording_id IN ({marks})", chunk):
            if verdict in LABEL_OF:
                rows.append((int(rid), int(s), int(e), LABEL_OF[verdict], f"annotation:{int(aid)}",
                             "window" if source in WINDOW_SOURCES else "event"))
        for adj_id, rid, s, e, s0, verdict in conn.execute(
                f"SELECT a.id, r.recording_id, d.start_idx, d.end_idx, r.span_start, a.verdict FROM adjudications a "
                f"JOIN detections d ON d.id = a.detection_id JOIN runs r ON r.id = d.run_id "
                f"WHERE r.recording_id IN ({marks}) AND {_queries.not_surrogate('r')}", chunk):
            if int(adj_id) in skip_adjudications or verdict not in LABEL_OF:
                continue
            a, b = absolute_bounds(s, e, s0)
            rows.append((int(rid), a, b, LABEL_OF[verdict], f"adjudication:{int(adj_id)}", "event"))
    df = pd.DataFrame(rows, columns=["recording_id", "start", "end", "label", "ref", "basis"])
    return {int(r): g.sort_values(["start", "end", "ref"]).reset_index(drop=True)
            for r, g in df.groupby("recording_id")}


def _member_adjudications(conn, members):
    """`{event_id: [(label, ref)]}` for adjudications on the events' own detections, and their adjudication ids."""
    by_det = dict(zip(members["detection_id"].astype(np.int64), members["event_id"].astype(np.int64)))
    out, used = {}, set()
    for adj_id, det_id, verdict in conn.execute("SELECT id, detection_id, verdict FROM adjudications").fetchall():
        ev = by_det.get(int(det_id))
        if ev is None or verdict not in LABEL_OF:
            continue
        out.setdefault(int(ev), []).append((LABEL_OF[verdict], f"adjudication:{int(adj_id)}", "event"))
        used.add(int(adj_id))
    return out, used


def _length_buckets(lengths):
    """Spans grouped by length (powers of four) so a containment search never widens to the longest span's reach."""
    edges = 4.0 ** np.arange(3, 12)
    return np.searchsorted(edges, np.maximum(lengths, 1), side="left")


def attach_labels(conn, events, members, *, rule=None):
    """Rule 5, on a copy of `events`: ``label`` (interesting / not_interesting / artifact / unsure, or None),
    ``label_kind`` (member / same_event / inside_span / conflict, or None), ``label_refs`` and
    ``inside_interesting``. Idempotent: earlier label columns are replaced."""
    rule = normalise_rule(rule) if rule is not None else rule_from_settings(conn)
    events = events.copy()
    n = len(events)
    label = np.full(n, None, dtype=object)
    kind = np.full(n, None, dtype=object)
    basis = np.full(n, None, dtype=object)
    refs = np.full(n, None, dtype=object)
    inside_int = np.zeros(n, dtype=bool)
    member_adj, used = _member_adjudications(conn, members)
    human = _human_spans(conn, events["recording_id"].unique(), skip_adjudications=used)
    eids = events["event_id"].to_numpy(np.int64)
    es, ee = events["start"].to_numpy(np.int64), events["end"].to_numpy(np.int64)
    rec = events["recording_id"].to_numpy(np.int64)
    onset = rule["onset"]
    for rid in np.unique(rec):
        rows = np.flatnonzero(rec == rid)
        spans = human.get(int(rid))
        same = {}
        contain = {}
        if spans is not None and len(spans):
            hs, he = spans["start"].to_numpy(np.int64), spans["end"].to_numpy(np.int64)
            hl, hr, hb = (spans["label"].to_numpy(object), spans["ref"].to_numpy(object),
                          spans["basis"].to_numpy(object))
            starts = hs.tolist()
            for i in rows:                              # rule 2, exactly as Review's rediscovery check
                s, e = int(es[i]), int(ee[i])
                tol = onset * max(0, e - s)
                lo = bisect_left(starts, math.floor(s - tol))
                hi = bisect_right(starts, math.floor(s + tol))
                for j in range(lo, hi):
                    if match_quality((s, e), (int(hs[j]), int(he[j])), rule=rule)["ok"]:
                        same.setdefault(int(i), []).append((hl[j], hr[j], hb[j]))
            r_s, r_e = es[rows], ee[rows]
            bucket = _length_buckets(he - hs)           # Q-W1: the spans that wholly hold an event
            for b in np.unique(bucket):
                sel = np.flatnonzero(bucket == b)
                order = np.argsort(hs[sel], kind="stable")
                sel = sel[order]
                bs, be = hs[sel], he[sel]
                reach = int((be - bs).max())
                lo = np.searchsorted(bs, r_e - reach, side="left")
                hi = np.searchsorted(bs, r_s, side="right")
                for a, z in _chunked(np.maximum(hi - lo, 0)):
                    r, j = _pairs(lo[a:z], hi[a:z])
                    if not len(r):
                        continue
                    r = r + a
                    ok = be[j] >= r_e[r]
                    for ri, jj in zip(r[ok].tolist(), sel[j[ok]].tolist()):
                        contain.setdefault(int(rows[ri]), []).append(
                            (hl[jj], hr[jj], int(he[jj] - hs[jj]), hb[jj]))
        for i in rows:
            i = int(i)
            mine = member_adj.get(int(eids[i]), [])
            direct = mine + same.get(i, [])
            if direct:
                classes = {c for c, _r, _b in direct}
                refs[i] = ";".join(sorted({r for _c, r, _b in direct}))
                if len(classes) == 1:
                    label[i] = classes.pop()
                    kind[i] = "member" if mine else "same_event"
                    basis[i] = _basis_of(b for _c, _r, b in direct)
                else:
                    kind[i] = "conflict"
                continue
            held = [h for h in contain.get(i, []) if h[0] in JUDGED]
            if not held:
                continue
            inside_int[i] = any(c == "interesting" for c, _r, _n, _b in held)
            shortest = min(n for _c, _r, n, _b in held)  # the most specific spans decide (rule 5)
            specific = [(c, r, b) for c, r, n, b in held if n <= SPECIFIC_FACTOR * shortest]
            classes = {c for c, _r, _b in specific}
            negative = classes & {"not_interesting", "artifact"}
            if negative:
                refs[i] = ";".join(sorted({r for _c, r, _b in specific}))
                if "interesting" in classes or len(negative) > 1:
                    kind[i] = "conflict"
                else:
                    label[i] = negative.pop()
                    kind[i] = "inside_span"
                    basis[i] = _basis_of(b for _c, _r, b in specific)
    events["label"] = label
    events["label_kind"] = kind
    events["label_basis"] = basis
    events["label_refs"] = refs
    events["inside_interesting"] = inside_int
    return events


def _basis_of(bases):
    """A label rests on a window only when every verdict behind it was given on a window (decision 3)."""
    return "window" if all(b == "window" for b in bases) else "event"


def label_counts(events):
    """What the table's labels say, for a report: the counts per label, conflicts and events inside an interesting
    span, how many are still unjudged, and how many labels rest on an event or only on a window."""
    lab = events["label"]
    out = {k: int((lab == k).sum()) for k in ("interesting", "not_interesting", "artifact", "unsure")}
    out["conflict"] = int((events["label_kind"] == "conflict").sum())
    out["unjudged"] = int(lab.isna().sum())
    out["inside_interesting_unjudged"] = int((lab.isna() & events["inside_interesting"].astype(bool)).sum())
    if "label_basis" in events:
        out["basis"] = {b: int((events["label_basis"] == b).sum()) for b in ("event", "window")}
        out["interesting_on_events"] = int(((lab == "interesting") & (events["label_basis"] == "event")).sum())
    return out


# ── the table ───────────────────────────────────────────────────────────────

def build_table(conn, source_file, *, exclude=NEGATIVE_CONTROLS, rule=None):
    """Rules 1–5 for one recording. Returns ``(events, members, meta)``; `meta` says how the table was made."""
    from Working.recipes import short_hash
    _refuse_held_out(source_file)
    rule = normalise_rule(rule) if rule is not None else rule_from_settings(conn)
    sweep = load_sweep_detections(conn, source_file, exclude=exclude)
    det = sweep["detections"]
    events, members = build_events(det, rule=rule)
    events = add_agreement(events, det)
    events = attach_labels(conn, events, members, rule=rule)
    events["channel"] = events["recording_id"].map(lambda r: sweep["recordings"][int(r)]["channel"]).astype(np.int64)
    events = events[list(EVENT_COLUMNS)]
    identity = {"version": TABLE_VERSION, "source_file": str(source_file), "rule": rule,
                "exclude": sorted(exclude), "agree_share": AGREE_SHARE,
                "runs": [[r["run_id"], r["variant"], r["recording_id"], r["n_detections"]] for r in sweep["runs"]]}
    meta = {"key": f"{_safe(source_file)}_{short_hash(identity)}", "version": TABLE_VERSION,
            "source_file": str(source_file), "rule": rule, "agree_share": AGREE_SHARE,
            "specific_factor": SPECIFIC_FACTOR, "excluded_variants": sweep["excluded_variants"], "exclude": list(exclude), "runs": sweep["runs"],
            "skipped": sweep["skipped"], "n_degenerate": sweep["n_degenerate"],
            "families": sorted(members["family"].unique()) if len(members) else [],
            "recordings": {str(k): v for k, v in sweep["recordings"].items()},
            "n_detections": int(len(det)), "n_events": int(len(events)), "labels": label_counts(events),
            "created_at": _now()}
    return events, members, meta


def _safe(name):
    return "".join(ch if ch.isalnum() else "_" for ch in os.path.splitext(str(name))[0]).strip("_")


def save_table(out_root, events, members, meta):
    """Write ``events.parquet``, ``members.parquet`` and ``meta.json`` under ``<out_root>/<key>``; return the folder."""
    where = os.path.join(str(out_root), meta["key"])
    os.makedirs(where, exist_ok=True)
    events.to_parquet(os.path.join(where, "events.parquet"), index=False)
    members.to_parquet(os.path.join(where, "members.parquet"), index=False)
    _atomic_json(os.path.join(where, "meta.json"), meta)
    return where


def load_table(where):
    with open(os.path.join(str(where), "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    return (pd.read_parquet(os.path.join(str(where), "events.parquet")),
            pd.read_parquet(os.path.join(str(where), "members.parquet")), meta)


# ── rule 6: the sample ──────────────────────────────────────────────────────

def level_of(n_agree, levels=AGREEMENT_LEVELS):
    for lo, hi in levels:
        if n_agree >= lo and (hi is None or n_agree <= hi):
            return f"agree:{lo}-{hi}" if hi is not None else f"agree:{lo}+"
    return f"agree:{int(n_agree)}"


def assign_strata(events, *, levels=AGREEMENT_LEVELS, selective=SELECTIVE_FAMILIES):
    """Rule 6's stratum of each event: ``family:<f>`` for the first selective family among its own detectors, else
    its agreement level."""
    out = []
    for fams, n in zip(events["matched_families"], events["n_agree"]):
        mine = _families(fams)
        hit = next((f for f in selective if f in mine), None)
        out.append(f"family:{hit}" if hit else level_of(int(n), levels))
    return pd.Series(out, index=events.index, dtype=object)


def _stratum_rank(name, levels, selective):
    if name.startswith("family:"):
        f = name[len("family:"):]
        return (0, selective.index(f) if f in selective else len(selective), name)
    names = [level_of(lo, levels) for lo, _hi in levels]
    return (1, names.index(name) if name in names else len(names), name)


def draw_sample(events, *, seed=0, per_level=DEFAULT_PER_LEVEL, per_family=DEFAULT_PER_FAMILY,
                levels=AGREEMENT_LEVELS, selective=SELECTIVE_FAMILIES):
    """Rule 6. Returns one row per sampled event: its anchor detection (the queue item), stratum, the stratum's
    frame and sample sizes, the weight N_h / n_h and its place in the seeded serving order (``serve_rank``)."""
    frame = events[events["label"].isna()].sort_values("event_id")
    strata = assign_strata(frame, levels=levels, selective=selective).to_numpy(object)
    rng = np.random.default_rng(int(seed))
    parts = []
    for name in sorted(set(strata), key=lambda s: _stratum_rank(s, levels, selective)):
        idx = np.flatnonzero(strata == name)
        n_frame = len(idx)
        n_take = min(int(per_family if name.startswith("family:") else per_level), n_frame)
        if n_take <= 0:
            continue
        pick = idx if n_take == n_frame else idx[np.sort(rng.choice(n_frame, size=n_take, replace=False))]
        rows = frame.iloc[pick]
        parts.append(pd.DataFrame({
            "event_id": rows["event_id"].to_numpy(np.int64),
            "detection_id": rows["anchor_detection_id"].to_numpy(np.int64),
            "recording_id": rows["recording_id"].to_numpy(np.int64),
            "channel": rows["channel"].to_numpy(np.int64) if "channel" in rows else np.zeros(len(rows), np.int64),
            "start": rows["start"].to_numpy(np.int64), "end": rows["end"].to_numpy(np.int64),
            "stratum": name, "frame_size": np.int64(n_frame), "sample_size": np.int64(n_take),
            "weight": float(n_frame) / float(n_take)}))
    cols = ["event_id", "detection_id", "recording_id", "channel", "start", "end", "stratum", "frame_size",
            "sample_size", "weight"]
    sample = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame({c: [] for c in cols})
    sample["serve_rank"] = rng.permutation(len(sample)).astype(np.int64)
    return sample


def save_sample(table_dir, sample, labels, meta):
    """Write a sample under ``<table_dir>/<meta['name']>``: the sample, the labels its frame was drawn against (the
    census the estimate counts) and its meta. Refuses to overwrite a different sample of the same name."""
    where = os.path.join(str(table_dir), meta["name"])
    if os.path.isdir(where) and os.path.isfile(os.path.join(where, "sample.parquet")):
        old = pd.read_parquet(os.path.join(where, "sample.parquet"))
        if (sorted(old["event_id"].astype(int)) != sorted(sample["event_id"].astype(int))
                or list(old.sort_values("serve_rank")["detection_id"]) !=
                list(sample.sort_values("serve_rank")["detection_id"])):
            raise ValueError(f"{where} already holds a different sample (the labels changed since it was drawn?); "
                             "a drawn sample is fixed: give it another seed rather than redrawing it")
    os.makedirs(where, exist_ok=True)
    sample.to_parquet(os.path.join(where, "sample.parquet"), index=False)
    labels.to_parquet(os.path.join(where, "labels.parquet"), index=False)
    _atomic_json(os.path.join(where, "meta.json"), meta)
    return where


def load_sample(where):
    with open(os.path.join(str(where), "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    return (pd.read_parquet(os.path.join(str(where), "sample.parquet")),
            pd.read_parquet(os.path.join(str(where), "labels.parquet")), meta)


def check_sample_against(conn, sample):
    """Refuse a database whose detections are not the ones the sample names (a table built on another database):
    every anchor must exist, be real, and sit on the same recording and span."""
    ids = [int(d) for d in sample["detection_id"]]
    found = {}
    for chunk in _chunks(ids):
        marks = ",".join("?" * len(chunk))
        for d_id, rid, s, e, s0 in conn.execute(
                f"SELECT d.id, r.recording_id, d.start_idx, d.end_idx, r.span_start FROM detections d "
                f"JOIN runs r ON r.id = d.run_id WHERE d.id IN ({marks}) AND {_queries.not_surrogate('r')}", chunk):
            found[int(d_id)] = (int(rid),) + tuple(absolute_bounds(s, e, s0))
    bad = [int(d) for d, rid, s, e in zip(sample["detection_id"], sample["recording_id"], sample["start"],
                                          sample["end"]) if found.get(int(d)) != (int(rid), int(s), int(e))]
    if bad:
        raise ValueError(f"{len(bad)} of the sample's {len(ids)} detections are not in this database as the table "
                         f"recorded them (first: {bad[:5]}); was the table built on another database?")


def create_sample_queue(conn, sample, *, name, note=None):
    """The sample as one blind Review queue over its anchor detections, served in its seeded order (rule 6). A
    second call with the same sample returns the same open queue."""
    from Working.review import queues as _queues
    check_sample_against(conn, sample)
    ids = [int(d) for d in sample.sort_values("serve_rank")["detection_id"]]
    filters = {"detection_ids": ids, "order": "listed"}
    found = _queues.find_open_queue(conn, source_kind="discovery-run", filters=filters)
    if found is not None:
        return int(found)
    return int(_queues.create_queue(conn, name=name, source_kind="discovery-run", filters=filters, blind=True,
                                    note=note))


def read_sample_verdicts(conn, sample):
    """`{detection_id: verdict}`: the adjudications on the sample's anchor detections so far."""
    out = {}
    for chunk in _chunks(sorted({int(d) for d in sample["detection_id"]})):
        marks = ",".join("?" * len(chunk))
        for d_id, verdict in conn.execute(
                f"SELECT detection_id, verdict FROM adjudications WHERE detection_id IN ({marks})", chunk):
            out[int(d_id)] = verdict
    return out


# ── rule 7: the estimate ────────────────────────────────────────────────────

def _groups(events, members, levels):
    """Group name → boolean mask over `events`' rows: all; each agreement level; each family that found events;
    each setting that found events."""
    out = {"all": np.ones(len(events), dtype=bool)}
    lv = np.array([level_of(int(n), levels) for n in events["n_agree"]], dtype=object)
    known = [level_of(lo, levels) for lo, _hi in levels]
    for name in sorted(set(lv), key=lambda s: (known.index(s) if s in known else len(known), s)):
        out[name] = lv == name
    fams = [_families(f) for f in events["matched_families"]]
    for f in (sorted(set().union(*fams)) if fams else []):
        out[f"family:{f}"] = np.array([f in s for s in fams], dtype=bool)
    pos = pd.Series(np.arange(len(events)), index=events["event_id"].to_numpy(np.int64))
    for variant, g in members.groupby("variant"):
        mask = np.zeros(len(events), dtype=bool)
        rows = pos.reindex(g["event_id"].to_numpy(np.int64)).dropna().to_numpy(np.int64)
        mask[rows] = True
        out[f"variant:{variant}"] = mask
    return out


def estimate(events, members, sample, verdicts, *, n_boot=1000, seed=0, levels=AGREEMENT_LEVELS):
    """Rule 7. `events` carries the labels the sample's frame was drawn against (the census); `verdicts` maps the
    sample's anchor detections to the answers given so far. Returns ``{answered, unsure, pending, n_boot, seed,
    groups: {name: {n_events, n_judged_before, positives_before, n_unjudged, n_sampled, precision, ci}}}``."""
    ev = events.reset_index(drop=True)
    census_y = np.array([Y_OF.get(l, np.nan) if isinstance(l, str) else np.nan for l in ev["label"]], dtype=float)
    in_census = ~np.isnan(census_y)
    in_frame = ev["label"].isna().to_numpy()
    s = sample.copy()
    s["verdict"] = [verdicts.get(int(d)) for d in s["detection_id"]]
    s["y"] = [Y_OF.get(x, np.nan) if isinstance(x, str) else np.nan for x in s["verdict"]]
    unsure = int((s["verdict"] == "unsure").sum())
    pending = int(s["verdict"].isna().sum())
    ans = s[~s["y"].isna()].reset_index(drop=True)
    n_ans = ans.groupby("stratum").size()
    ans["w"] = ans["frame_size"].astype(float) / ans["stratum"].map(n_ans).astype(float)
    pos = pd.Series(np.arange(len(ev)), index=ev["event_id"].to_numpy(np.int64))
    ans_rows = pos.reindex(ans["event_id"].to_numpy(np.int64)).to_numpy()
    if np.isnan(ans_rows.astype(float)).any():
        raise ValueError("the sample names events this table does not hold")
    ans_rows = ans_rows.astype(np.int64)
    groups = _groups(ev, members, levels)
    names = list(groups)
    G = np.array([groups[g][ans_rows] for g in names], dtype=float).reshape(len(names), len(ans))
    Nc = np.array([float((groups[g] & in_census).sum()) for g in names])
    Yc = np.array([float(np.nansum(census_y[groups[g] & in_census])) for g in names])
    w, y = ans["w"].to_numpy(float), ans["y"].to_numpy(float)

    def point(counts):
        W = G @ (counts * w)
        WY = G @ (counts * w * y)
        den = Nc + W
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(den > 0, (Yc + WY) / np.where(den > 0, den, 1.0), np.nan)

    p = point(np.ones(len(ans)))
    rng = np.random.default_rng(int(seed))
    strata = ans["stratum"].to_numpy(object)
    by_h = {h: np.flatnonzero(strata == h) for h in pd.unique(strata)}
    frame_of = ans.groupby("stratum")["frame_size"].first().to_dict()
    boots = np.full((int(n_boot), len(names)), np.nan)
    for b in range(int(n_boot)):
        counts = np.zeros(len(ans))
        for h, idx in by_h.items():
            if len(idx) >= int(frame_of[h]):      # answered in full: no sampling error
                counts[idx] += 1.0
            else:
                counts[idx] += np.bincount(rng.integers(0, len(idx), len(idx)), minlength=len(idx))
        boots[b] = point(counts)
    out = {}
    for k, name in enumerate(names):
        col = boots[:, k]
        ci = [None, None] if np.isnan(p[k]) or np.isnan(col).all() else \
            [float(np.nanpercentile(col, 2.5)), float(np.nanpercentile(col, 97.5))]
        out[name] = {"n_events": int(groups[name].sum()), "n_judged_before": int(Nc[k]),
                     "positives_before": int(Yc[k]), "n_unjudged": int((groups[name] & in_frame).sum()),
                     "n_sampled": int(G[k].sum()), "precision": None if np.isnan(p[k]) else float(p[k]), "ci": ci}
    return {"answered": int(len(ans)), "unsure": unsure, "pending": pending, "n_boot": int(n_boot),
            "seed": int(seed), "groups": out}

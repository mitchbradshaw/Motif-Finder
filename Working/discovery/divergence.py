"""
divergence.py
=============
Where the human record and a run disagree, counted so that the count means
something — RQ5, and the precision column Q2 and Q4 read (fixup-X).

Two decisions this module implements rather than makes:

- **Q-D2 (answered 2026-09-23): two numbers, each printing its own rule.**
  11,234 of the 11,269 human annotations are the 600-sample windows of the
  10-minute CNN set (``annotations.source = 'imported_10min'``) — window
  *labels*, not event spans — and a 179-sample drop can never reach §4.6's
  IoU 0.5 against one. So (a) **containment over the window labels** answers
  *does the detector fire where a human saw something*, and (c) **extent
  agreement over the event-shaped rows** (§4.6) answers *does it get the
  extent right*, with the width distribution of those rows beside it — they
  run 126 to 324,000 samples, and a figure over them without it is the same
  uninterpretable number as the 0.00 it replaces (Q-D2's caveat).
- **Q41: unlabelled is never "not interesting".** A place no run covered, or
  no human reviewed, is *not comparable* — the fifth count, which is not a
  cell — rather than a disagreement.

The four cells, for a set of runs on one channel
------------------------------------------------
``machine_yes_*`` count **detections**; ``machine_no_*`` count **human
labels** the machine was silent on. That is the usual shape of the table (a
hit is a detection, a miss is a reference) and it is stated rather than
smoothed over.

A detection's human verdict is resolved in this order, and each detection
says which rule resolved it (``by``):

1. **adjudication** — a verdict given on this detection in Review. A rejected
   detection is *machine yes / human no* even when no annotation overlaps it
   (item 5). ``unsure`` is no verdict and falls through.
2. **extent** — matched one-to-one to an event-shaped row under §4.6
   (`matching.match_span_sets`, the detection as the candidate).
3. **containment** — the window labels that **wholly contain** it, every one
   of which must agree. This is Q41's own rule (the researcher's, for the same
   window/span mapping in the other direction): a span partially in a window
   does not take its label, and windows that disagree are left out and
   counted. The windows overlap (600 samples on a 200-sample stride), so a
   short detection is usually inside two or three.

"Human yes" is ``interesting`` or ``seed`` (P21: seed implies interesting);
"human no" is ``not_interesting`` or ``artifact``; ``unsure`` is neither.
A label a detection overlaps is *represented* by that detection and is not
counted again. "Machine no" requires that one of the runs **completed over a
span wholly containing the label** — a run that never reached a place was not
silent there. Surrogate runs are never machine findings (fixup-T).

Headless: plain SQL over an open connection, no UI import (rule 1).
"""

from bisect import bisect_left, bisect_right
import json

import numpy as np

from Working.database import queries as _q
from Working.discovery.matching import match_span_sets, normalise_rule, rule_from_settings
from Working.discovery.spans import absolute_bounds

HUMAN_YES = tuple(_q.ACCEPTED_VERDICTS)            # interesting, seed
HUMAN_NO = ("not_interesting", "artifact")

#: The sources whose rows are window labels rather than event spans (Q-D2's
#: table). Everything else in the human store is an event-shaped row.
WINDOW_SOURCES = (_q.SOURCE_IMPORTED_10MIN,)

CELLS = ("machine_yes_human_yes", "machine_yes_human_no", "machine_no_human_yes", "machine_no_human_no")
NOT_COMPARABLE = "not_comparable"
#: The two cells that are disagreements.
DISAGREE = ("machine_yes_human_no", "machine_no_human_yes")

CELL_LABEL = {
    "machine_yes_human_yes": "machine yes · human yes",
    "machine_yes_human_no": "machine yes · human no",
    "machine_no_human_yes": "machine no · human yes",
    "machine_no_human_no": "machine no · human no",
    NOT_COMPARABLE: "not comparable",
}

CONTAINMENT_RULE = (
    "containment over the window labels: a detection takes the verdict of the reviewed 600-sample windows "
    "(annotations.source = imported_10min) that wholly contain it, and every one of them must agree (Q41's rule); "
    "a verdict given on the detection in Review comes first")

STRUCTURE_NOTE = (
    "No test of structure and no null: this table says where the two disagreements fall, not whether they "
    "cluster more than chance would. There is no null to draw it against yet — what counts as \"structured\" is "
    "an open decision for the RQ5 round.")

#: Keys a detector might put its own morphology under in `detections.meta_json`.
MORPHOLOGY_KEYS = ("morphology", "kind", "shape", "class", "element")


def extent_rule_text(rule):
    return (f"extent agreement over the event-shaped rows (annotations not imported_10min): reciprocal IoU ≥ "
            f"{rule['iou']:g} with the onset within {rule['onset']:g} × the detection's duration (§4.6); a detection "
            f"that overlaps an event row without matching it got the extent wrong; a verdict given on the detection "
            f"in Review comes first")


def side_of(verdict):
    """'yes', 'no' or None for one verdict string."""
    if verdict in HUMAN_YES:
        return "yes"
    if verdict in HUMAN_NO:
        return "no"
    return None


def _cell(machine_yes, side):
    return f"machine_{'yes' if machine_yes else 'no'}_human_{side}"


# ── reads ───────────────────────────────────────────────────────────────────

def real_runs(conn, recording_id, run_ids=None):
    """The runs a divergence is over: ``run_ids`` restricted to this recording,
    or every run on it when None. Surrogate runs are dropped either way."""
    rows = conn.execute(
        "SELECT r.id, r.span_start, r.span_end, r.status FROM runs r WHERE r.recording_id = ? AND "
        + _q.not_surrogate("r") + " ORDER BY r.id", (int(recording_id),)).fetchall()
    if run_ids is not None:
        wanted = {int(i) for i in run_ids}
        rows = [r for r in rows if int(r["id"]) in wanted]
    return [dict(r) for r in rows]


def human_labels(conn, recording_id):
    """Every live annotation on the recording, split into window labels and
    event-shaped rows."""
    windows, events = [], []
    for r in conn.execute(
            "SELECT id, start_idx, end_idx, verdict, source FROM annotations "
            "WHERE recording_id = ? AND deleted_at IS NULL ORDER BY start_idx, id", (int(recording_id),)):
        item = {"id": int(r["id"]), "start": int(r["start_idx"]), "end": int(r["end_idx"]),
                "verdict": r["verdict"], "side": side_of(r["verdict"]), "source": r["source"],
                "width": int(r["end_idx"]) - int(r["start_idx"])}
        (windows if r["source"] in WINDOW_SOURCES else events).append(item)
    return windows, events


def _adjudications(conn, recording_id, run_ids):
    """detection id -> (verdict, side) for the runs' adjudicated detections.
    The rejections come through the core query that names them."""
    if not run_ids:
        return {}
    marks = ",".join("?" * len(run_ids))
    out = {int(r["detection_id"]): (r["verdict"], side_of(r["verdict"])) for r in conn.execute(
        "SELECT a.detection_id, a.verdict FROM adjudications a JOIN detections d ON d.id = a.detection_id "
        f"WHERE d.run_id IN ({marks})", list(run_ids)).fetchall()}
    for r in _q.divergence_rejected_detections(conn, recording_id, run_ids=run_ids, verdicts=HUMAN_NO):
        out[int(r["id"])] = (r["adjudication_verdict"], "no")
    return out


def _morphology(meta_json):
    try:
        meta = json.loads(meta_json) if meta_json else {}
    except (TypeError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    for k in MORPHOLOGY_KEYS:
        v = meta.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def _detections(conn, runs):
    if not runs:
        return []
    by_id = {int(r["id"]): r for r in runs}
    marks = ",".join("?" * len(by_id))
    out = []
    for r in conn.execute(f"SELECT id, run_id, start_idx, end_idx, score, meta_json FROM detections "
                          f"WHERE run_id IN ({marks}) ORDER BY start_idx, id", list(by_id)).fetchall():
        a, b = absolute_bounds(r["start_idx"], r["end_idx"], by_id[int(r["run_id"])]["span_start"])
        out.append({"id": int(r["id"]), "run_id": int(r["run_id"]), "start": a, "end": b,
                    "score": (float(r["score"]) if r["score"] is not None else None),
                    "morphology": _morphology(r["meta_json"])})
    out.sort(key=lambda d: (d["start"], d["id"]))
    return out


# ── the rules ───────────────────────────────────────────────────────────────

def _containing(windows, starts, max_w, d):
    """Windows that wholly contain detection ``d``."""
    lo = bisect_left(starts, d["end"] - max_w)
    hi = bisect_right(starts, d["start"])
    return [w for w in windows[lo:hi] if w["start"] <= d["start"] and d["end"] <= w["end"]]


#: Why an item is not comparable — the short key it is counted under, and the
#: sentence the page prints. "No human verdict here" has three causes worth
#: telling apart, because the second and third are the containment rule's
#: own blind spots rather than places nobody looked.
WHY = {
    "no window near it": "no human verdict here: no reviewed window is near it",
    "longer than a window": ("no human verdict here: it is longer than a review window, so no window can wholly "
                             "contain it (the spans-longer-than-the-window case, Q-W1)"),
    "straddles a window edge": ("no human verdict here: it touches reviewed windows but sticks out past the "
                                "edge of every one"),
    "windows disagree": "windows disagree: the windows that contain it say both yes and no",
    "unsure window": "no verdict: the windows that contain it are marked unsure",
    "unsure event row": "no verdict: the event row it matches is marked unsure",
    "no run covered it": "no run covered it: no run completed over a span that wholly contains it",
    "unsure label": "no verdict: the label is marked unsure",
}


def _containment(windows, starts, max_w, d):
    """(side, why, window ids) under the containment rule."""
    inside = _containing(windows, starts, max_w, d) if windows else []
    if not inside:
        if windows and _overlaps_any(windows, starts, max_w, d["start"], d["end"]):
            return None, ("longer than a window" if d["end"] - d["start"] > max_w else "straddles a window edge"), []
        return None, "no window near it", []
    ids = [w["id"] for w in inside]
    sides = {w["side"] for w in inside if w["side"]}
    if not sides:
        return None, "unsure window", ids
    if len(sides) > 1:
        return None, "windows disagree", ids
    return sides.pop(), "", ids


def _overlaps_any(spans_sorted, starts, max_w, a, b):
    lo = bisect_left(starts, a - max_w)
    hi = bisect_left(starts, b)
    return any(s["end"] > a for s in spans_sorted[lo:hi])


def _wholly_covered(runs, a, b):
    return any(r["status"] == "completed" and int(r["span_start"]) <= a and b <= int(r["span_end"]) for r in runs)


def _width_summary(values):
    vals = sorted(int(v) for v in values)
    if not vals:
        return {"n": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None, "values": []}
    arr = np.asarray(vals, dtype=float)
    med = float(np.median(arr))
    return {"n": len(vals), "min": vals[0], "p25": float(np.percentile(arr, 25)),
            "median": (int(med) if med.is_integer() else med), "p75": float(np.percentile(arr, 75)),
            "max": vals[-1], "values": vals}


def _figure(key, rule_text, yes, judged, by_adj, note):
    return {"key": key, "label": f"precision · {key}", "rule": rule_text, "yes": int(yes), "judged": int(judged),
            "by_adjudication": int(by_adj), "value": (yes / float(judged)) if judged else None,
            "note": None if judged else note}


def channel_divergence(conn, recording_id, run_ids=None, *, rule=None, span=None):
    """The divergence between the human record and ``run_ids`` on one channel.

    ``run_ids`` None pools every real run on the recording (``pooled`` says
    so); a list is the runs asked about, surrogates dropped. ``span`` narrows
    it to the items whose onset lies in ``[span[0], span[1])`` — the section a
    Discovery page has on screen.

    Returns
    -------
    dict
        ``cells`` (the four counts), ``not_comparable`` (``n`` and its reasons),
        ``items`` (every counted detection and label with its ``cell``, the
        rule that resolved it — ``by`` — and the human labels it rests on),
        ``precision`` (``containment`` and ``extent``, Q-D2's two figures, each
        carrying its rule; ``extent`` carries ``widths``), ``rule`` and
        ``run_ids``.
    """
    rule = normalise_rule(rule) if rule is not None else rule_from_settings(conn)
    runs = real_runs(conn, recording_id, run_ids)
    ids = [int(r["id"]) for r in runs]
    windows, events = human_labels(conn, recording_id)
    dets = _detections(conn, runs)
    adjud = _adjudications(conn, recording_id, ids)

    def in_scope(x):
        return span is None or int(span[0]) <= x["start"] < int(span[1])

    w_starts = [w["start"] for w in windows]
    max_w = max((w["width"] for w in windows), default=0)

    # §4.6 extent, one-to-one, over every detection against every event row
    pairing = match_span_sets([(d["start"], d["end"]) for d in dets], [(e["start"], e["end"]) for e in events],
                              rule=rule) if dets and events else {"pairs": []}
    event_of = {p["candidate"]: events[p["reference"]] for p in pairing["pairs"]}
    e_sorted = sorted(events, key=lambda e: e["start"])
    e_starts = [e["start"] for e in e_sorted]
    max_e = max((e["width"] for e in events), default=0)

    cells = {c: 0 for c in CELLS}
    nc = {"detections": {}, "labels": {}}
    items = []
    a_yes = a_judged = a_adj = 0
    c_yes = c_judged = c_adj = 0

    for i, d in enumerate(dets):
        if not in_scope(d):
            continue
        verdict, adj_side = adjud.get(d["id"], (None, None))
        c_side, c_why, c_ids = _containment(windows, w_starts, max_w, d)
        ev = event_of.get(i)
        e_side = ev["side"] if ev is not None else None

        # (a) containment, adjudication first
        if adj_side:
            a_judged += 1; a_adj += 1; a_yes += adj_side == "yes"
        elif c_side:
            a_judged += 1; a_yes += c_side == "yes"
        # (c) extent, adjudication first; an overlap without a match is a wrong extent
        if adj_side:
            c_judged += 1; c_adj += 1; c_yes += adj_side == "yes"
        elif ev is not None and e_side:
            c_judged += 1; c_yes += e_side == "yes"
        elif ev is None and _overlaps_any(e_sorted, e_starts, max_e, d["start"], d["end"]):
            c_judged += 1

        item = {"kind": "detection", "id": d["id"], "run_id": d["run_id"], "start": d["start"], "end": d["end"],
                "score": d["score"], "morphology": d["morphology"], "adjudication": verdict, "why": None}
        if adj_side:
            item.update(cell=_cell(True, adj_side), by="adjudication", reason="", human=[])
        elif e_side:
            item.update(cell=_cell(True, e_side), by="extent", reason="", human=[ev["id"]])
        elif c_side:
            item.update(cell=_cell(True, c_side), by="containment", reason="", human=c_ids)
        else:
            why = "unsure event row" if ev is not None and not e_side else c_why
            item.update(cell=NOT_COMPARABLE, by=None, why=why, reason=WHY[why], human=c_ids)
        if item["cell"] == NOT_COMPARABLE:
            nc["detections"][item["why"]] = nc["detections"].get(item["why"], 0) + 1
        else:
            cells[item["cell"]] += 1
        items.append(item)

    # the human side: labels the machine was silent on, where it could have spoken.
    # The two silent sets come through the core query that names them.
    silent = {}
    if ids:
        for side, verdicts in (("yes", HUMAN_YES), ("no", HUMAN_NO)):
            for r in _q.divergence_annotations_without_detection(conn, recording_id, run_ids=ids, verdicts=verdicts):
                silent[int(r["id"])] = side
    d_sorted = sorted(dets, key=lambda d: d["start"])
    d_starts = [d["start"] for d in d_sorted]
    max_d = max((d["end"] - d["start"] for d in dets), default=0)
    covered_events = []
    for lab in windows + events:
        if not in_scope(lab):
            continue
        covered = _wholly_covered(runs, lab["start"], lab["end"])
        if lab["source"] not in WINDOW_SOURCES and covered:
            covered_events.append(lab["width"])
        if dets and _overlaps_any(d_sorted, d_starts, max_d, lab["start"], lab["end"]):
            continue                                   # represented by the detection that overlaps it
        item = {"kind": "label", "id": lab["id"], "start": lab["start"], "end": lab["end"],
                "verdict": lab["verdict"], "source": lab["source"], "human": [lab["id"]], "by": None, "why": None}
        if lab["id"] in silent:
            item.update(cell=_cell(False, silent[lab["id"]]), reason="",
                        by=("containment" if lab["source"] in WINDOW_SOURCES else "extent"))
            cells[item["cell"]] += 1
        else:
            why = "no run covered it" if not covered else "unsure label"
            item.update(cell=NOT_COMPARABLE, why=why, reason=WHY[why])
            nc["labels"][why] = nc["labels"].get(why, 0) + 1
        items.append(item)

    nc["n"] = sum(nc["detections"].values()) + sum(nc["labels"].values())
    no_run = "no run on this channel" if not ids else None
    containment = _figure("containment", CONTAINMENT_RULE, a_yes, a_judged, a_adj,
                          no_run or "no detection lies wholly inside a reviewed window, and none is adjudicated")
    extent = _figure("extent", extent_rule_text(rule), c_yes, c_judged, c_adj,
                     no_run or "no detection overlaps an event-shaped row, and none is adjudicated")
    extent["widths"] = _width_summary(covered_events)
    return {
        "recording_id": int(recording_id), "run_ids": ids, "pooled": run_ids is None,
        "cells": cells, "not_comparable": nc, "items": items,
        "precision": {"containment": containment, "extent": extent},
        "rule": rule, "span": (list(span) if span is not None else None),
    }


# ── pooling ─────────────────────────────────────────────────────────────────

def pool_cells(divs):
    cells = {c: sum(d["cells"][c] for d in divs) for c in CELLS}
    nc = sum(d["not_comparable"]["n"] for d in divs)
    return cells, nc


def pool_precision(figures):
    """Q-D2's figures pooled over channels: the COUNTS are summed, never the
    ratios (the scoreboard's rule), and the extent figure's widths are the
    union of the channels' event rows."""
    figures = [f for f in figures if f]
    if not figures:
        return None
    first = figures[0]
    yes = sum(f["yes"] for f in figures)
    judged = sum(f["judged"] for f in figures)
    notes = [f["note"] for f in figures if f.get("note")]
    out = _figure(first["key"], first["rule"], yes, judged, sum(f["by_adjudication"] for f in figures),
                  notes[0] if notes else "nothing to score")
    if "widths" in first:
        out["widths"] = _width_summary([v for f in figures for v in (f.get("widths") or {}).get("values", [])])
    return out


def scope_text(n_runs, pooled):
    runs = f"{n_runs} run{'' if n_runs == 1 else 's'}"
    return (f"pooling every run on this recording — {runs}" if pooled else f"the {runs} picked")


# ── the breakdown ───────────────────────────────────────────────────────────

def _tags_by_annotation(conn, ids):
    out = {}
    ids = sorted({int(i) for i in ids})
    for k in range(0, len(ids), 900):
        chunk = ids[k:k + 900]
        for r in conn.execute(
                "SELECT at.annotation_id, tv.value FROM annotation_tags at JOIN tag_vocabulary tv ON tv.id = at.tag_id "
                "WHERE tv.category = 'element' AND at.annotation_id IN ({})".format(",".join("?" * len(chunk))), chunk):
            out.setdefault(int(r[0]), []).append(r[1])
    return out


def _tags_by_adjudicated_detection(conn, ids):
    out = {}
    ids = sorted({int(i) for i in ids})
    for k in range(0, len(ids), 900):
        chunk = ids[k:k + 900]
        for r in conn.execute(
                "SELECT a.detection_id, tv.value FROM adjudication_tags t JOIN adjudications a ON a.id = t.adjudication_id "
                "JOIN tag_vocabulary tv ON tv.id = t.tag_id WHERE tv.category = 'element' "
                "AND a.detection_id IN ({})".format(",".join("?" * len(chunk))), chunk):
            out.setdefault(int(r[0]), []).append(r[1])
    return out


def breakdown(conn, runs_by_recording, *, bins, n_samples, span=None, rule=None, names=None):
    """The two disagreement cells by channel, by time bin and by morphology,
    for a set of runs against the human record (item 4).

    ``runs_by_recording`` is ``{recording_id: [run ids] | None}``. Morphology
    is read where a side has one: on the human side the ``element`` tags of
    the labels a disagreement rests on (and of an adjudication's own tags); on
    the machine side the detector's own morphology from ``meta_json``, which
    no detector in this project writes yet — the payload says so rather than
    showing an empty column as a finding.
    """
    rule = normalise_rule(rule) if rule is not None else rule_from_settings(conn)
    lo, hi = (int(span[0]), int(span[1])) if span is not None else (0, int(n_samples))
    edges = np.linspace(lo, hi, int(bins) + 1)
    by_time = [{"bin": i, "start": float(edges[i]), "end": float(edges[i + 1]),
                **{c: 0 for c in DISAGREE}, NOT_COMPARABLE: 0} for i in range(int(bins))]
    by_channel, disagreements = [], []
    for rid, ids in runs_by_recording.items():
        div = channel_divergence(conn, rid, ids, rule=rule, span=span)
        row = {"recording_id": int(rid), "channel": (names or {}).get(rid), **div["cells"],
               NOT_COMPARABLE: div["not_comparable"]["n"], "run_ids": div["run_ids"]}
        by_channel.append(row)
        for it in div["items"]:
            mid = (it["start"] + it["end"]) / 2.0
            if not (lo <= mid < hi):
                continue
            b = min(int(bins) - 1, int((mid - lo) / max(1e-9, hi - lo) * int(bins)))
            if it["cell"] in DISAGREE:
                by_time[b][it["cell"]] += 1
                disagreements.append({**it, "recording_id": int(rid)})
            elif it["cell"] == NOT_COMPARABLE:
                by_time[b][NOT_COMPARABLE] += 1

    ann_tags = _tags_by_annotation(conn, [h for it in disagreements for h in it["human"]])
    adj_tags = _tags_by_adjudicated_detection(conn, [it["id"] for it in disagreements
                                                     if it["kind"] == "detection" and it["by"] == "adjudication"])
    human, machine = {}, {}
    for it in disagreements:
        tags = set()
        for h in it["human"]:
            tags.update(ann_tags.get(h, []))
        if it["kind"] == "detection":
            tags.update(adj_tags.get(it["id"], []))
            if it.get("morphology"):
                machine.setdefault(it["morphology"], {c: 0 for c in DISAGREE})[it["cell"]] += 1
        for t in sorted(tags):
            human.setdefault(t, {c: 0 for c in DISAGREE})[it["cell"]] += 1
    n_tagged = sum(1 for it in disagreements if any(ann_tags.get(h) for h in it["human"])
                   or (it["kind"] == "detection" and adj_tags.get(it["id"])))
    total_links = conn.execute(
        "SELECT COUNT(*) FROM annotation_tags at JOIN tag_vocabulary tv ON tv.id = at.tag_id "
        "WHERE tv.category = 'element'").fetchone()[0]
    return {
        "by_channel": by_channel,
        "by_time": by_time,
        "by_morphology": {
            "human": [{"tag": t, **v} for t, v in sorted(human.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))],
            "machine": [{"morphology": m, **v} for m, v in sorted(machine.items())],
            "human_note": (f"{n_tagged} of {len(disagreements)} disagreements rest on a human label carrying an "
                           f"`element` tag; the whole database holds {total_links} such tag links"),
            "machine_note": (None if machine else
                             "the detector stores no morphology on its detections, and a class or tag given in "
                             "Review is not stored yet (07 R3) — so the machine side has no morphology to break "
                             "down by"),
        },
        "n_disagreements": len(disagreements),
        "structure_note": STRUCTURE_NOTE,
        "cells": list(DISAGREE),
        "rule": rule,
    }

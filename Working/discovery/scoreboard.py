"""
scoreboard.py
=============
Spec §7.3 — Discovery's scoreboard, computed from the tables rather than
estimated: ``detections`` × ``annotations`` × ``reviewed_spans``, matched by
the §4.6 rule (``Working.discovery.matching``).

The columns, and what each is actually made of
-----------------------------------------------
``found``           every detection this run wrote.
``already judged``  detections that already carried a verdict **before the
                    run started** — a matching human annotation written
                    earlier, or an adjudication on a prior run's detection of
                    the same span. Its own column, because "without it, a high
                    precision on a re-run of familiar ground looks like a
                    property of the algorithm" (§7.3).
``reviewed``        detections a human could have judged: those whose **onset
                    lies inside the reviewed coverage** of this run's span.
                    The criterion is stated on every row (``reviewed_criterion``)
                    because it is a choice: the reviewed spans in this project
                    are ~600 s windows and detections run from seconds to
                    hours, so "the human saw most of it" would score almost
                    nothing, and "overlaps at all" would credit a detection
                    that merely brushed the edge of a reviewed window.
``interesting``     of those, the ones matching an annotation whose verdict is
                    in ``queries.ACCEPTED_VERDICTS`` (interesting or seed —
                    P21: the seed verdict implies interesting).
``precision``       ``interesting / reviewed``. **Labelled precision**, never
                    accuracy or effective rate (§7.3): the row carries
                    ``precision_label`` so the page cannot rename it.
``recall``          of the accepted annotations inside the reviewed overlap,
                    the fraction this run matched — **scoped to that overlap**,
                    with the hours it was computed over beside it. No overlap
                    reads ``no reviewed overlap``, never blank.
``null expects``    the paired surrogate run's detection count on the same
                    scope (``runs.surrogate_of_run_id``), and ``× null`` the
                    ratio. Not a bare "surrogate" count.

Matching is **one-to-one** (``match_span_sets``): a second detection over the
same annotation stays unmatched and is counted as a false positive, which is
the duplicate-suppression priority §4.6 names.

Every row records the rule it was computed under, because a precision figure
is a function of it (§4.6) and changing the rule is a versioned act.

Headless: plain SQL over an open connection, no UI import, no bridge import.
"""

from Working.database import queries as _q
from Working.database import runs as _runs
from Working.discovery.matching import match_span_sets, normalise_rule, rule_from_settings
from Working.discovery.spans import absolute_bounds, clip, contains, merged, total_length

#: A detection counts as reviewed when its onset falls inside the reviewed
#: coverage. Stated on every row rather than left implicit.
REVIEWED_CRITERION = ("onset inside reviewed coverage, or matching an annotation that is")

ACCEPTED = set(_q.ACCEPTED_VERDICTS)

NOT_SCORED = "not yet scored"
NO_OVERLAP = "no reviewed overlap"
NO_POSITIVES = "nothing marked interesting in the reviewed overlap"
NO_DETECTIONS_REVIEWED = "no detections in the reviewed overlap"


def _run_row(conn, run_id):
    row = _runs.get_run(conn, run_id)
    if row is None:
        raise ValueError(f"no run with id={run_id}")
    return row


def _detections(conn, run_id, span_start):
    rows = conn.execute(
        "SELECT id, start_idx, end_idx, score FROM detections WHERE run_id = ? ORDER BY start_idx, id",
        (int(run_id),)).fetchall()
    out = []
    for r in rows:
        a, b = absolute_bounds(r["start_idx"], r["end_idx"], span_start)
        out.append({"id": int(r["id"]), "start": a, "end": b,
                    "score": (float(r["score"]) if r["score"] is not None else None)})
    out.sort(key=lambda d: (d["start"], d["id"]))
    return out


def _annotations(conn, recording_id):
    has_deleted = any(c["name"] == "deleted_at" for c in conn.execute("PRAGMA table_info(annotations)"))
    sql = ("SELECT id, start_idx, end_idx, verdict, created_at FROM annotations WHERE recording_id = ?"
           + (" AND deleted_at IS NULL" if has_deleted else "")
           + " ORDER BY start_idx, id")
    return [{"id": int(r["id"]), "start": int(r["start_idx"]), "end": int(r["end_idx"]),
             "verdict": r["verdict"], "created_at": r["created_at"]}
            for r in conn.execute(sql, (int(recording_id),)).fetchall()]


def _reviewed_coverage(conn, recording_id, span_start, span_end):
    rows = conn.execute(
        "SELECT start_idx, end_idx FROM reviewed_spans WHERE recording_id = ?",
        (int(recording_id),)).fetchall()
    return merged(clip([(r["start_idx"], r["end_idx"]) for r in rows], span_start, span_end))


def _prior_adjudicated(conn, recording_id, started_at):
    """Spans on this recording that carried an adjudication before `started_at`
    — a verdict given on some earlier run's detection of the same place."""
    rows = conn.execute(
        "SELECT d.start_idx, d.end_idx, r.span_start FROM adjudications a "
        "JOIN detections d ON d.id = a.detection_id JOIN runs r ON r.id = d.run_id "
        "WHERE r.recording_id = ? AND a.created_at < ?",
        (int(recording_id), str(started_at or ""))).fetchall()
    return [absolute_bounds(r["start_idx"], r["end_idx"], r["span_start"]) for r in rows]


def _null_runs(conn, run_id):
    """**Every** surrogate run paired with this one, not the first.

    `run_paired_recipe` writes one surrogate per real run today, so the count
    is usually 1 — and a column called "null expects" carrying a single draw is
    not an expectation, which is why the row states `null_draws` beside it. If
    a caller ever pairs N surrogates, this averages them without a further
    change."""
    return [int(r["id"]) for r in conn.execute(
        "SELECT id FROM runs WHERE surrogate_of_run_id = ? ORDER BY id", (int(run_id),)).fetchall()]


def _ratio(num, den):
    return (float(num) / float(den)) if den else None


def shape_mismatch(candidate_widths, reference_widths, iou_threshold):
    """Can a typical detection and a typical annotation match **at all**?

    Two spans nested as well as they can be reach an IoU of
    ``min(w) / max(w)``. If that is already below the threshold, no alignment
    saves them: a precision of 0 over such a pair is a statement about the two
    span *shapes*, not about the algorithm, and a scoreboard that printed it
    without saying so would be the most misleading number on the page.

    This is not hypothetical here. 11,234 of this project's 11,269 annotations
    are the fixed 600-sample windows of the 10-minute CNN window set
    (``annotations.source = 'imported_10min'``) — window labels, not event
    spans — while a real drop runs 21 to 4,875 samples, median 179. Under
    §4.6's IoU >= 0.5 a 179-sample event against a 600-sample window reaches
    0.30 and can never be counted, however well it is placed.

    Returns None when the two are compatible, and a sentence when they are not.
    """
    cand = sorted(int(w) for w in candidate_widths if w)
    ref = sorted(int(w) for w in reference_widths if w)
    if not cand or not ref:
        return None
    mc, mr = cand[len(cand) // 2], ref[len(ref) // 2]
    best = min(mc, mr) / float(max(mc, mr))
    if best >= iou_threshold:
        return None
    # the medians alone hide bimodality, so say how much of the run is outside
    # the band that could match at all: [iou x mr, mr / iou] around the
    # reference width
    lo, hi = iou_threshold * mr, mr / iou_threshold
    outside = sum(1 for w in cand if not (lo <= w <= hi))
    return (f"the spans cannot match: this run's detections are {mc} samples long at the median and the "
            f"reviewed annotations are {mr}, so the best reachable overlap is IoU {best:.2f}, below the "
            f"rule's {iou_threshold:.2f}. {outside} of {len(cand)} detections are outside the "
            f"{lo:.0f}-{hi:.0f} sample band that could reach it at any alignment. Precision here is a "
            f"statement about the two span shapes, not about the algorithm")


def channel_score(conn, run_id, *, rule=None, null_run_id=None, span=None):
    """One channel row of §7.3 for one run. Every cell, and the words for the
    cells that have no number.

    ``span`` narrows the row to a section *inside* the run's own span — the
    Discovery page scores the section that is on screen, not the whole run, and
    a precision computed over hours the researcher is not looking at would not
    be the number the page claims. It is intersected with the run's span, never
    widened past it: a run cannot be credited with ground truth it never saw.
    """
    rule = normalise_rule(rule) if rule is not None else rule_from_settings(conn)
    run = _run_row(conn, run_id)
    rec = _q.get_recording_by_id(conn, run["recording_id"])
    span_start, span_end = int(run["span_start"]), int(run["span_end"])
    if span is not None:
        span_start = max(span_start, int(span[0]))
        span_end = min(span_end, int(span[1]))
        if span_end <= span_start:
            span_start = span_end = int(run["span_start"])
            return _empty_row(run, rec, rule, [span_start, span_end],
                              "this run does not reach the section on screen")
    fs = float(rec["fs"]) if rec and rec["fs"] else 1.0

    dets = [d for d in _detections(conn, run_id, int(run["span_start"]))
            if span_start <= d["start"] < span_end]
    anns = [a for a in _annotations(conn, run["recording_id"]) if span_start <= a["start"] < span_end]
    coverage = _reviewed_coverage(conn, run["recording_id"], span_start, span_end)
    reviewed_samples = total_length(coverage)
    reviewed_h = reviewed_samples / fs / 3600.0

    pairing = match_span_sets([(d["start"], d["end"]) for d in dets],
                              [(a["start"], a["end"]) for a in anns], rule=rule)
    ann_of_det = {p["candidate"]: p["reference"] for p in pairing["pairs"]}
    det_of_ann = {p["reference"]: p["candidate"] for p in pairing["pairs"]}

    started_at = str(run["started_at"] or "")
    prior_spans = _prior_adjudicated(conn, run["recording_id"], started_at)
    prior_pairing = match_span_sets([(d["start"], d["end"]) for d in dets], prior_spans, rule=rule)
    prior_det = {p["candidate"] for p in prior_pairing["pairs"]}

    # One criterion for both halves. A detection counts as judge-able when the
    # human could have judged it: its own onset is inside the reviewed coverage,
    # OR it matched an annotation that is. Gating precision on the detection's
    # onset and recall on the annotation's let one row print
    # "no detections in the reviewed overlap" beside a recall of 0.167 derived
    # from exactly such a detection — a long detection starting just before a
    # reviewed window is judge-able, and both halves now agree that it is.
    reviewed = interesting = already_judged = 0
    for i, d in enumerate(dets):
        ann = anns[ann_of_det[i]] if i in ann_of_det else None
        in_coverage = contains(coverage, d["start"]) or (
            ann is not None and contains(coverage, ann["start"]))
        if in_coverage:
            reviewed += 1
            if ann is not None and ann["verdict"] in ACCEPTED:
                interesting += 1
        if i in prior_det or (ann is not None and str(ann["created_at"] or "") < started_at):
            already_judged += 1

    positives = [j for j, a in enumerate(anns)
                 if a["verdict"] in ACCEPTED and contains(coverage, a["start"])]
    found_positives = [j for j in positives if j in det_of_ann]

    status = run["status"]
    running = status in ("running", "queued")
    recall = recall_note = None
    if running:
        recall_note = None
    elif not coverage:
        recall_note = NO_OVERLAP
    elif not positives:
        recall_note = NO_POSITIVES
    else:
        recall = _ratio(len(found_positives), len(positives))

    precision = None if running or not reviewed else _ratio(interesting, reviewed)
    precision_note = None
    if not running and coverage and not reviewed:
        precision_note = NO_DETECTIONS_REVIEWED
    elif not running and reviewed:
        # whenever the typical pair cannot match, whatever precision came out:
        # one lucky match among detections that are otherwise structurally
        # unmatchable gives 0.01, which is just as misleading as 0.00
        precision_note = shape_mismatch(
            [d["end"] - d["start"] for d in dets],
            [a["end"] - a["start"] for a in anns if contains(coverage, a["start"])],
            rule["iou"])

    note = None
    if running:
        note = "running"
    elif status == "failed":
        note = "failed"
    elif status == "cancelled":
        note = "cancelled"
    elif not coverage:
        note = NOT_SCORED

    null_ids = [null_run_id] if null_run_id is not None else _null_runs(conn, run_id)
    null_expects = null_draws = None
    if null_ids:
        counts = []
        for nid in null_ids:
            null_row = _run_row(conn, nid)
            counts.append(sum(1 for d in _detections(conn, nid, int(null_row["span_start"]))
                              if span_start <= d["start"] < span_end))
        null_draws = len(counts)
        null_expects = sum(counts) / float(null_draws)
        null_expects = int(null_expects) if float(null_expects).is_integer() else round(null_expects, 2)

    return {
        "run_id": int(run_id),
        "run_name": run["name"],
        "status": status,
        "recording_id": int(run["recording_id"]),
        "channel": int(rec["channel"]) if rec else None,
        "channel_name": f"CH{int(rec['channel'])}" if rec else None,
        "source_file": rec["source_file"] if rec else None,
        "fs": fs,
        "span": [span_start, span_end],
        "found": len(dets),
        "already_judged": already_judged,
        "reviewed": reviewed,
        "interesting": interesting,
        "precision": precision,
        "precision_label": "precision",
        "precision_note": precision_note,
        "recall": recall,
        "recall_note": recall_note,
        "recall_over_h": reviewed_h,
        "recall_positives": len(positives),
        "recall_found": len(found_positives),
        "reviewed_h": reviewed_h,
        "reviewed_criterion": REVIEWED_CRITERION,
        "null_run_id": (null_ids[0] if null_ids else None),
        "null_run_ids": null_ids,
        "null_draws": null_draws,
        "null_expects": null_expects,
        "x_null": _ratio(len(dets), null_expects) if null_expects else None,
        "note": note,
        "rule": rule,
    }


def _empty_row(run, rec, rule, span, note):
    """A row for a run the section does not reach: counts zero, every ratio a
    word. Never a 0.00 precision with no denominator behind it."""
    fs = float(rec["fs"]) if rec and rec["fs"] else 1.0
    return {
        "run_id": int(run["id"]), "run_name": run["name"], "status": run["status"],
        "recording_id": int(run["recording_id"]),
        "channel": int(rec["channel"]) if rec else None,
        "channel_name": f"CH{int(rec['channel'])}" if rec else None,
        "source_file": rec["source_file"] if rec else None, "fs": fs, "span": span,
        "found": 0, "already_judged": 0, "reviewed": 0, "interesting": 0,
        "precision": None, "precision_label": "precision", "precision_note": note,
        "recall": None, "recall_note": NO_OVERLAP, "recall_over_h": 0.0,
        "recall_positives": 0, "recall_found": 0, "reviewed_h": 0.0,
        "reviewed_criterion": REVIEWED_CRITERION, "null_run_id": None, "null_expects": None,
        "x_null": None, "note": note, "rule": rule,
    }


def run_total(conn, run_ids, *, rule=None, rows=None):
    """The run's total row: counts summed, recall pooled by reviewed hours.

    "The run total states the hours it pooled" (§7.3). A channel with no
    reviewed overlap contributes its counts but not its (absent) recall, and
    its hours are not in the pooled figure — an unreviewed channel must not
    dilute a recall computed somewhere else.
    """
    rows = rows if rows is not None else [channel_score(conn, r, rule=rule) for r in run_ids]
    if not rows:
        return {"found": 0, "already_judged": 0, "reviewed": 0, "interesting": 0,
                "precision": None, "precision_label": "precision", "recall": None,
                "recall_note": NO_OVERLAP, "pooled_h": 0.0, "reviewed_h": 0.0,
                "null_expects": None, "x_null": None, "n_channels": 0,
                "rule": normalise_rule(rule) if rule is not None else rule_from_settings(conn)}
    summed = {k: sum(int(r[k]) for r in rows) for k in ("found", "already_judged", "reviewed", "interesting")}
    # x null must be a ratio over ONE scope. Dividing every channel's `found` by
    # only the channels that carry a surrogate printed 4.0 under four rows that
    # each read 2.0, so the numerator is restricted to the same channels.
    with_null = [r for r in rows if r["null_expects"] is not None]
    null_expects = sum(r["null_expects"] for r in with_null) if with_null else None
    null_found = sum(r["found"] for r in with_null)
    null_partial = bool(with_null) and len(with_null) != len(rows)

    # Pool the COUNTS, not the ratios. An hours-weighted mean of per-channel
    # recalls is not a recall: one channel with ten positives in an hour and
    # another with ten in ten hours gave 0.09 where the run really found 10 of
    # 20, a 5.5x error. Precision on this row is count-pooled, and two cells
    # under the same heading cannot be pooled by two different rules. §7.3's
    # "the run total states the hours it pooled" is an instruction to state the
    # scope, not to weight by it — `pooled_h` still states it.
    scored = [r for r in rows if r["recall"] is not None]
    pooled_h = sum(r["recall_over_h"] for r in scored)
    positives = sum(r["recall_positives"] for r in scored)
    recall = (sum(r["recall_found"] for r in scored) / float(positives)) if positives else None
    recall_note = None if recall is not None else (
        NO_OVERLAP if not any(r["reviewed_h"] for r in rows) else NO_POSITIVES)

    notes = [r["precision_note"] for r in rows if r.get("precision_note")]
    recall_positives = sum(r["recall_positives"] for r in scored)
    recall_found = sum(r["recall_found"] for r in scored)
    return {
        **summed,
        "precision": _ratio(summed["interesting"], summed["reviewed"]),
        "precision_note": (notes[0] if notes and not summed["interesting"] else None),
        "precision_label": "precision",
        "recall": recall,
        "recall_note": recall_note,
        "pooled_h": pooled_h,
        "recall_positives": recall_positives,
        "recall_found": recall_found,
        "reviewed_h": sum(r["reviewed_h"] for r in rows),
        "null_expects": null_expects,
        "null_draws": (sum(r["null_draws"] or 0 for r in with_null) or None),
        "x_null": _ratio(null_found, null_expects) if null_expects else None,
        "x_null_scope": (f"{len(with_null)} of {len(rows)} channels carry a null" if null_partial else None),
        "n_channels": len(rows),
        "rule": rows[0]["rule"] if rows else (normalise_rule(rule) if rule is not None else rule_from_settings(conn)),
    }


def score_runs(conn, run_ids, *, rule=None, span=None):
    """The channel rows and the total for an explicit set of runs — what a
    Discovery run is made of when `execute_recipe` reused runs that already
    belong to an earlier fan-out's group."""
    rows = [channel_score(conn, int(r), rule=rule, span=span) for r in run_ids]
    rows = [r for r in rows if r["status"] != "surrogate"]
    rows.sort(key=lambda r: (r["channel"] if r["channel"] is not None else -1, r["run_id"]))
    return {"channels": rows, "total": run_total(conn, [r["run_id"] for r in rows], rule=rule, rows=rows)}


def group_score(conn, run_group_id, *, rule=None, span=None):
    """§7.1's "each template becomes one run across all channels in scope",
    scored: one channel row per member run, the surrogate members folded into
    their parent's ``null expects`` rather than shown as channels of their own.
    """
    members = _runs.list_run_group_runs(conn, run_group_id)
    real = [r for r in members if r["surrogate_of_run_id"] is None]
    rows = [channel_score(conn, int(r["id"]), rule=rule, span=span) for r in real]
    rows.sort(key=lambda r: (r["channel"] if r["channel"] is not None else -1, r["run_id"]))
    return {
        "run_group_id": int(run_group_id),
        "channels": rows,
        "total": run_total(conn, [r["run_id"] for r in rows], rule=rule, rows=rows),
        "n_runs": len(members),
        "n_surrogates": len(members) - len(real),
    }

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
REVIEWED_CRITERION = "onset inside reviewed coverage"

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


def _null_run_id(conn, run_id):
    row = conn.execute(
        "SELECT id FROM runs WHERE surrogate_of_run_id = ? ORDER BY id LIMIT 1", (int(run_id),)).fetchone()
    return int(row["id"]) if row else None


def _ratio(num, den):
    return (float(num) / float(den)) if den else None


def channel_score(conn, run_id, *, rule=None, null_run_id=None):
    """One channel row of §7.3 for one run. Every cell, and the words for the
    cells that have no number."""
    rule = normalise_rule(rule) if rule is not None else rule_from_settings(conn)
    run = _run_row(conn, run_id)
    rec = _q.get_recording_by_id(conn, run["recording_id"])
    span_start, span_end = int(run["span_start"]), int(run["span_end"])
    fs = float(rec["fs"]) if rec and rec["fs"] else 1.0

    dets = _detections(conn, run_id, span_start)
    anns = _annotations(conn, run["recording_id"])
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

    reviewed = interesting = already_judged = 0
    for i, d in enumerate(dets):
        in_coverage = contains(coverage, d["start"])
        ann = anns[ann_of_det[i]] if i in ann_of_det else None
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

    note = None
    if running:
        note = "running"
    elif status == "failed":
        note = "failed"
    elif status == "cancelled":
        note = "cancelled"
    elif not coverage:
        note = NOT_SCORED

    null_id = null_run_id if null_run_id is not None else _null_run_id(conn, run_id)
    null_expects = None
    if null_id is not None:
        null_expects = int(conn.execute(
            "SELECT COUNT(*) FROM detections WHERE run_id = ?", (int(null_id),)).fetchone()[0])

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
        "null_run_id": null_id,
        "null_expects": null_expects,
        "x_null": _ratio(len(dets), null_expects) if null_expects else None,
        "note": note,
        "rule": rule,
    }


def run_total(conn, run_ids, *, rule=None, rows=None):
    """The run's total row: counts summed, recall pooled by reviewed hours.

    "The run total states the hours it pooled" (§7.3). A channel with no
    reviewed overlap contributes its counts but not its (absent) recall, and
    its hours are not in the pooled figure — an unreviewed channel must not
    dilute a recall computed somewhere else.
    """
    rows = rows if rows is not None else [channel_score(conn, r, rule=rule) for r in run_ids]
    summed = {k: sum(int(r[k]) for r in rows) for k in ("found", "already_judged", "reviewed", "interesting")}
    nulls = [r["null_expects"] for r in rows if r["null_expects"] is not None]
    null_expects = sum(nulls) if nulls else None

    scored = [r for r in rows if r["recall"] is not None]
    pooled_h = sum(r["recall_over_h"] for r in scored)
    recall = (sum(r["recall"] * r["recall_over_h"] for r in scored) / pooled_h) if pooled_h else None
    recall_note = None if recall is not None else (
        NO_OVERLAP if not any(r["reviewed_h"] for r in rows) else NO_POSITIVES)

    return {
        **summed,
        "precision": _ratio(summed["interesting"], summed["reviewed"]),
        "precision_label": "precision",
        "recall": recall,
        "recall_note": recall_note,
        "pooled_h": pooled_h,
        "reviewed_h": sum(r["reviewed_h"] for r in rows),
        "null_expects": null_expects,
        "x_null": _ratio(summed["found"], null_expects) if null_expects else None,
        "n_channels": len(rows),
        "rule": rows[0]["rule"] if rows else (normalise_rule(rule) if rule is not None else rule_from_settings(conn)),
    }


def group_score(conn, run_group_id, *, rule=None):
    """§7.1's "each template becomes one run across all channels in scope",
    scored: one channel row per member run, the surrogate members folded into
    their parent's ``null expects`` rather than shown as channels of their own.
    """
    members = _runs.list_run_group_runs(conn, run_group_id)
    real = [r for r in members if r["surrogate_of_run_id"] is None]
    rows = [channel_score(conn, int(r["id"]), rule=rule) for r in real]
    rows.sort(key=lambda r: (r["channel"] if r["channel"] is not None else -1, r["run_id"]))
    return {
        "run_group_id": int(run_group_id),
        "channels": rows,
        "total": run_total(conn, [r["run_id"] for r in rows], rule=rule, rows=rows),
        "n_runs": len(members),
        "n_surrogates": len(members) - len(real),
    }

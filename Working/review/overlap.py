"""
overlap.py
==========
One judgement per event (review-carry, 2026-10-18). Two faces of one problem:

**Within a run, overlapping detections are one Review item.** Most detectors
emit overlapping spans for one event (only the two threshold blocks merge their
gaps). The detector's output stays exactly as emitted — honest and
reproducible — and Review groups it: `overlap_sets` is the transitive closure of
pairwise overlap among one run's detections on one channel, and the resolver
(`Working.review.queues`) serves each set as one item whose verdict is written
to every detection in it.

**Across runs, a verdict carries.** When a person judges detection A, every
other detection on the same channel (any run; a channel is one `recordings`
row) that is the same event by the scoreboard's matching rule receives the same
verdict as a written `adjudications` row of its own, with
`carried_from` = A's row and the note ``carried from detection A (rule ...)``.
Review then never asks about it, and the scoreboard counts it as the human
verdict it is. The rule is `Working.discovery.matching` — the one the
scoreboard and the rediscovery check read — never a second copy: `same_event`
delegates to it with the OTHER detection as the candidate (whose duration sets
the onset tolerance) and A as the reference, the way the scoreboard pairs a
run's detections against earlier verdicts (`scoreboard._prior_adjudicated`).

What carrying never does:

* overwrite a row that is already there — a person's own, or one carried from
  another verdict (the first verdict that covers an event keeps it);
* carry a carried row on (a carried row is not a judgement anybody made);
* write to a paired surrogate's spans (a null draw takes no verdict,
  `queries.not_surrogate`);
* invent a verdict word: the carried row holds the source's verdict, one of the
  five, and its class label.

`uncarry` takes back every row carried from one adjudication; the Review writer
(`Working.review.verdicts`) records exactly which rows each verdict created or
rewrote, so an undo restores those and nothing else.

Headless: plain SQL over an open connection, no UI import.
"""

import datetime
import math

from Working.database import queries as _queries
from Working.discovery.matching import rule_from_settings, spans_match
from Working.discovery.spans import absolute_bounds

__all__ = ["overlap_sets", "same_event", "carry_verdict", "carry", "uncarry", "carried_note"]


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _span(d):
    """(id, start, end) from a ``(id, start, end)`` tuple or a dict in either the
    `detections` row shape (``start_idx``/``end_idx``) or the scoreboard's
    (``start``/``end``)."""
    if isinstance(d, dict):
        start = d["start_idx"] if "start_idx" in d else d["start"]
        end = d["end_idx"] if "end_idx" in d else d["end"]
        return int(d["id"]), int(start), int(end)
    return int(d[0]), int(d[1]), int(d[2])


def overlap_sets(detections):
    """The overlap sets of ONE run's detections on ONE channel, as a list of id
    sets, ordered by the earliest onset in each set.

    Two detections overlap when they share a sample: ``[start, end)`` intervals,
    so one ending where the next begins does not. The set is the transitive
    closure: A~B and B~C put A and C in one set even when they do not overlap.
    The caller says which detections are one run on one channel; mixing runs or
    channels here would merge what the researcher decided stays apart.
    """
    spans = sorted((_span(d) for d in detections), key=lambda s: (s[1], s[0]))
    out, cur, reach = [], None, None
    for did, start, end in spans:
        if cur is not None and start < reach:
            cur.add(did)
            reach = max(reach, end)
            continue
        cur, reach = {did}, end
        out.append(cur)
    return out


def same_event(candidate, reference, rule=None):
    """The scoreboard's §4.6 rule (`matching.spans_match`): is the detection
    `candidate` the event `reference` already is? ``(start, end)`` pairs in one
    index space (channel-absolute). The candidate's duration sets the onset
    tolerance — it is the one being asked about."""
    return spans_match(candidate, reference, rule=rule)


def carried_note(source_detection_id, rule):
    """The note on a carried row: where it came from and under which rule."""
    return "carried from detection {} (rule {}: IoU >= {:.2f}, onset within {:g} x duration)".format(
        int(source_detection_id), rule["criterion"], float(rule["iou"]), float(rule["onset"]))


def _candidates(conn, recording_id, source_id, start, end, rule):
    """Every real detection on the recording that the rule could pair with
    ``[start, end)`` — read by index per run, never the channel's whole table
    when the rule allows a bound.

    A match needs IoU >= t. For t > 0 that needs an overlap, so the candidate
    starts before ``end``; and its duration is at most ``(end - start) / t``, so
    with the onset half it starts no earlier than ``start - onset x that``. A
    legacy span-relative row (`spans.absolute_bounds`) is stored ``span_start``
    lower, so the same window is read shifted for it. t = 0 reads every row.
    """
    iou = float(rule["iou"])
    base = ("SELECT d.id, d.start_idx, d.end_idx, r.span_start FROM runs r "
            "JOIN detections d ON d.run_id = r.id "
            "WHERE r.recording_id = ? AND d.id <> ? AND " + _queries.not_surrogate("r"))
    if iou <= 0:
        rows = conn.execute(base, (int(recording_id), int(source_id))).fetchall()
    else:
        reach = float(rule["onset"]) * max(0, end - start) / iou
        lo, hi = int(math.floor(start - reach)) - 1, int(end)
        rows = conn.execute(
            base + " AND ((d.start_idx >= ? AND d.start_idx < ?) "
                   "OR (r.span_start > 0 AND d.start_idx < r.span_start "
                   "AND d.start_idx >= ? - r.span_start AND d.start_idx < ? - r.span_start))",
            (int(recording_id), int(source_id), lo, hi, lo, hi)).fetchall()
    out = []
    for r in rows:
        a, b = absolute_bounds(r[1], r[2], r[3])
        out.append((int(r[0]), a, b))
    out.sort()
    return out


def carry(conn, adjudication_id, *, rule=None):
    """Carry one adjudication's verdict, and say exactly what was written:
    ``{"created": [detection ids], "updated": [{"detection_id", "verdict",
    "class_label", "note"}]}`` — `updated` holds the PRIOR state of a row this
    same source had carried before and now rewrites (a re-judgement of A), so
    the caller can put it back. Does not commit.

    Nothing is carried from a row that is itself carried, or that does not
    exist."""
    src = conn.execute(
        "SELECT a.id, a.detection_id, a.verdict, a.class_label, a.carried_from, d.start_idx, d.end_idx, "
        "r.recording_id, r.span_start FROM adjudications a JOIN detections d ON d.id = a.detection_id "
        "JOIN runs r ON r.id = d.run_id WHERE a.id = ?", (int(adjudication_id),)).fetchone()
    done = {"created": [], "updated": []}
    if src is None or src["carried_from"] is not None:
        return done
    rule = rule or rule_from_settings(conn)
    # `seed` names the ONE detection promoted to the Library (P21: it implies interesting). A carried row is not
    # a promotion — it has no Library entry — so it carries what the seed implies, never the word itself
    verdict = "interesting" if src["verdict"] == "seed" else src["verdict"]
    start, end = absolute_bounds(src["start_idx"], src["end_idx"], src["span_start"])
    note = carried_note(src["detection_id"], rule)
    matched = [did for did, a, b in _candidates(conn, src["recording_id"], src["detection_id"], start, end, rule)
               if same_event((a, b), (start, end), rule=rule)]
    if not matched:
        return done
    have = {}
    for i in range(0, len(matched), 400):
        chunk = matched[i:i + 400]
        for r in conn.execute("SELECT detection_id, verdict, class_label, note, carried_from FROM adjudications "
                              "WHERE detection_id IN ({})".format(",".join("?" * len(chunk))), chunk).fetchall():
            have[int(r[0])] = r
    now = _now()
    for did in matched:
        row = have.get(did)
        if row is None:
            conn.execute("INSERT INTO adjudications (detection_id, verdict, note, created_at, class_label, "
                         "carried_from) VALUES (?, ?, ?, ?, ?, ?)",
                         (did, verdict, note, now, src["class_label"], int(src["id"])))
            done["created"].append(did)
        elif row["carried_from"] is not None and int(row["carried_from"]) == int(src["id"]):
            done["updated"].append({"detection_id": did, "verdict": row["verdict"],
                                    "class_label": row["class_label"], "note": row["note"]})
            conn.execute("UPDATE adjudications SET verdict = ?, class_label = ?, note = ? WHERE detection_id = ?",
                         (verdict, src["class_label"], note, did))
        # else: a person's own row, or one another verdict carried first — never overwritten
    return done


def carry_verdict(conn, adjudication_id):
    """Write adjudication `adjudication_id`'s verdict (and class label) to every
    unjudged detection that is the same event on the same channel, and return
    the detection ids written (created or rewritten by this same source),
    ascending. Commits."""
    done = carry(conn, adjudication_id)
    conn.commit()
    return sorted(done["created"] + [u["detection_id"] for u in done["updated"]])


def uncarry(conn, adjudication_id, *, commit=True):
    """Delete every row carried from `adjudication_id` and return their
    detection ids, ascending. A row a person has since judged is theirs
    (`carried_from` cleared) and is not touched."""
    rows = conn.execute("SELECT id, detection_id FROM adjudications WHERE carried_from = ?",
                        (int(adjudication_id),)).fetchall()
    for r in rows:
        conn.execute("DELETE FROM adjudication_tags WHERE adjudication_id = ?", (int(r[0]),))
    conn.execute("DELETE FROM adjudications WHERE carried_from = ?", (int(adjudication_id),))
    if commit:
        conn.commit()
    return sorted(int(r[1]) for r in rows)


def undo_carry(conn, adjudication_id, done):
    """Reverse one `carry` result exactly: delete the rows it created and put
    back the rows it rewrote — each only while it is still carried from this
    source (a row a person judged since is theirs). Does not commit."""
    for did in done.get("created") or ():
        row = conn.execute("SELECT id, carried_from FROM adjudications WHERE detection_id = ?", (int(did),)).fetchone()
        if row is not None and row["carried_from"] is not None and int(row["carried_from"]) == int(adjudication_id):
            conn.execute("DELETE FROM adjudication_tags WHERE adjudication_id = ?", (int(row["id"]),))
            conn.execute("DELETE FROM adjudications WHERE id = ?", (int(row["id"]),))
    for u in done.get("updated") or ():
        conn.execute("UPDATE adjudications SET verdict = ?, class_label = ?, note = ? "
                     "WHERE detection_id = ? AND carried_from = ?",
                     (u["verdict"], u.get("class_label"), u.get("note"), int(u["detection_id"]),
                      int(adjudication_id)))

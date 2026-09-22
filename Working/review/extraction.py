"""
extraction.py
=============
The Library's *extract events* queue: resolving a catalogued sequence into the
singular events it claims to contain (stage-3 Prompt 05, spec §10; the queue
kind Prompt 03 created by flagging sequences `needs_extraction = 1`).

**An extraction is not a verdict, and that is the whole design.** A verdict
re-describes something that is already there; an extraction says *here are N
events I can now point at, inside a span that previously only claimed to hold
N of them*. So each event is a **new singular annotation** of its own, linked
to the parent span through `annotations.parent_annotation_id` — never a note on
the parent, and never an edit of it. The first implementation of this route
serialised each event into the parent's `note`, each overwriting the last, and
the reviewer's work was simply lost.

`needs_extraction` is cleared only when the reviewer says the sequence is
complete. That flag is what puts the sequence in the queue, so an extraction
that does not clear it leaves an item that can never drain, and one that clears
it too early throws away the honest record that the events are still unresolved
(see the `sequences` schema comment).

One gesture is **one** `review_audit` row. The reviewer marked a set of events
in a single act and one Ctrl-Z has to take that act back — children removed,
flag restored. `Working.review.verdicts.undo_last` reverses it through
`undo_extraction` below.

Rule 5 (CLAUDE.md): everything written here is a human observation and lands in
`annotations`. No detection is created, read or modified.
"""

import json

from Working.database import queries as _queries

#: An extracted event is a sub-window of the span its parent annotation covers.
#: `annotations.relation_kind` CHECKs this value, so it is not free text.
RELATION_KIND = "sub_window"

#: Extraction records where an event IS; it does not judge it. `unsure` is the
#: honest verdict for a span a person has pointed at but not yet ruled on, and
#: the reviewer can judge each child afterwards like any other span.
DEFAULT_VERDICT = "unsure"


def _sequence_row(conn, sequence_id):
    row = conn.execute(
        "SELECT * FROM sequences WHERE id = ?", (int(sequence_id),)).fetchone()
    if row is None:
        raise ValueError("no sequence with id {!r}".format(sequence_id))
    return row


def _parent_annotation_id(seq):
    ann = seq["annotation_id"]
    if ann is None:
        raise ValueError(
            "sequence {} has no annotation_id, so its extracted events have no "
            "parent span to hang from. Refusing rather than inventing one."
            .format(seq["id"]))
    return int(ann)


def extract_events(conn, queue_id, sequence_id, events, *, complete=False,
                   source=None, verdict=DEFAULT_VERDICT):
    """Write one annotation per event, linked to the sequence's own span.

    `events` is an iterable of mappings with `start_idx` and `end_idx` (and an
    optional `note`). Returns
    `{'sequence_id', 'parent_annotation_id', 'child_ids', 'complete',
    'audit_id'}`.

    Raises `ValueError` for an unknown sequence, a sequence with no parent
    annotation, an event outside its parent's span, or an empty event list on a
    gesture that is not marking the sequence complete.
    """
    from Working.review import verdicts as _verdicts

    queue = _verdicts._queue_row(conn, queue_id)
    if queue["writes_to"] != "annotations":
        raise PermissionError(
            "{}. Review queue {} writes {!r}; an extraction writes human spans "
            "into `annotations` and may not be done through it."
            .format(_verdicts._RULE_5, queue["id"], queue["writes_to"]))

    seq = _sequence_row(conn, sequence_id)
    parent_id = _parent_annotation_id(seq)
    parent = _queries.get_annotation(conn, parent_id)
    if parent is None:
        raise ValueError(
            "sequence {} names annotation {}, which does not exist"
            .format(seq["id"], parent_id))

    events = [dict(e) for e in (events or ())]
    if not events and not complete:
        raise ValueError(
            "an extraction with no events and complete=false would change "
            "nothing; say what was marked, or say the sequence is complete")

    lo, hi = int(parent["start_idx"]), int(parent["end_idx"])
    for e in events:
        s, t = int(e["start_idx"]), int(e["end_idx"])
        if s >= t:
            raise ValueError(
                "event {}-{} is empty or inverted".format(s, t))
        if s < lo or t > hi:
            raise ValueError(
                "event {}-{} falls outside the sequence's own span {}-{}: an "
                "extracted event is part of the span it was extracted from"
                .format(s, t, lo, hi))

    child_ids = []
    for e in events:
        child_ids.append(_queries.insert_annotation(
            conn, int(seq["recording_id"]), int(e["start_idx"]),
            int(e["end_idx"]), verdict,
            source or _queries.SOURCE_MANUAL_UI,
            note=e.get("note"),
            parent_annotation_id=parent_id,
            relation_kind=RELATION_KIND,
            commit=False))

    was = int(seq["needs_extraction"] or 0)
    if complete:
        conn.execute("UPDATE sequences SET needs_extraction = 0 WHERE id = ?",
                     (int(seq["id"]),))

    payload = {
        "writes_to": "annotations",
        "sequence_id": int(seq["id"]),
        "parent_annotation_id": parent_id,
        "child_ids": child_ids,
        "complete": bool(complete),
        "needs_extraction_before": was,
    }
    audit_id = _verdicts._audit(
        conn, queue["id"], "extract", "annotations", child_ids, payload)
    conn.commit()
    return {"sequence_id": int(seq["id"]), "parent_annotation_id": parent_id,
            "child_ids": child_ids, "complete": bool(complete),
            "audit_id": audit_id}


def undo_extraction(conn, audit_row):
    """Reverse one `extract` audit row: remove the children, restore the flag.

    The children are deleted outright rather than soft-deleted. They were
    created by the gesture being undone and were never judged by anyone — a
    tombstone for a span that existed for as long as it took to press Ctrl-Z
    would be noise in the human record, not provenance.
    """
    payload = json.loads(audit_row["payload_json"] or "{}")
    child_ids = [int(c) for c in payload.get("child_ids") or ()]
    for cid in child_ids:
        conn.execute("DELETE FROM annotation_tags WHERE annotation_id = ?",
                     (cid,))
        conn.execute("DELETE FROM annotations WHERE id = ?", (cid,))
    seq_id = payload.get("sequence_id")
    if seq_id is not None and payload.get("complete"):
        conn.execute("UPDATE sequences SET needs_extraction = ? WHERE id = ?",
                     (int(payload.get("needs_extraction_before") or 0),
                      int(seq_id)))
    return {"child_ids": child_ids, "sequence_id": seq_id}

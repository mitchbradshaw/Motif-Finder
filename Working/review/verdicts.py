"""
verdicts.py
===========
The one door every Review verdict goes through (stage-3 prompt 05).

Three things live here that nothing else owns:

**Rule 5, enforced by refusal.** CLAUDE.md rule 5: detections are machine-only,
annotations are human-only. This module decides where a verdict lands purely
from the QUEUE's `writes_to` column — the decision a person made once, at queue
creation, stored where it can be read (`review_queues.writes_to`, schema
comment) — and never from the shape of the target id. A caller that hands a
detection id to a queue that writes `annotations`, or an annotation id to a
queue that writes `adjudications`, gets a `PermissionError` naming rule 5.
It is an exception and not a silent no-op on purpose: a crossing that returns
quietly is the same crossing with the evidence removed, and a Review surface
that drops verdicts on the floor looks identical to one that is working.

**A batch is one act.** `write_batch` writes N verdicts under exactly ONE
`review_audit` row carrying the N target ids, because the person performed one
action and Ctrl-Z must reverse that one action, not the last of N.

**Undo restores, it does not delete.** `review_audit.payload_json` carries the
PRIOR state of every target the write touched, so undoing a re-judgement puts
the earlier verdict back rather than returning the item to unjudged — the same
semantics `Working.review.queue_state.undo` already has in memory, made
durable.

No UI library and no `webui` import: this is core code (CLAUDE.md rule 1). The
rule-5 vocabulary is shared with `webui/server/writes.py` but the enforcement
here is independent of it.
"""

import datetime
import json

from Working.database import adjudications as _adjudications
from Working.database import queries as _queries
from Working.database.schema import VERDICTS

__all__ = ["VERDICTS", "write_verdict", "write_batch", "undo_last"]


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


_RULE_5 = (
    "CLAUDE.md rule 5: detections are machine-only and annotations are "
    "human-only"
)


# ── queue lookup and target classification ─────────────────────────────────

def _queue_row(conn, queue_id):
    row = conn.execute(
        "SELECT * FROM review_queues WHERE id = ?", (queue_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"no review queue with id {queue_id}")
    return row


def _is_detection(conn, target_id):
    return conn.execute(
        "SELECT 1 FROM detections WHERE id = ?", (target_id,)
    ).fetchone() is not None


def _is_annotation(conn, target_id):
    return conn.execute(
        "SELECT 1 FROM annotations WHERE id = ?", (target_id,)
    ).fetchone() is not None


def _check_target(conn, writes_to, target_id):
    """Refuse a target that belongs to the other store. Raises
    `PermissionError` for a crossing, `ValueError` for an id that is in
    neither store."""
    if writes_to == "adjudications":
        if _is_detection(conn, target_id):
            return
        if _is_annotation(conn, target_id):
            raise PermissionError(
                f"{_RULE_5}. Annotation {target_id} cannot be adjudicated: "
                f"this queue writes `adjudications`, which is the machine "
                f"store, and a human annotation may not be written into it."
            )
        raise ValueError(f"no detection with id {target_id}")
    if writes_to == "annotations":
        if _is_annotation(conn, target_id):
            return
        if _is_detection(conn, target_id):
            raise PermissionError(
                f"{_RULE_5}. Detection {target_id} cannot be annotated: "
                f"this queue writes `annotations`, which is the human store, "
                f"and a machine detection may not be written into it."
            )
        raise ValueError(f"no annotation with id {target_id}")
    if writes_to == "window_verdicts":
        return
    raise ValueError(f"unknown writes_to {writes_to!r}")


def _check_verdict(verdict):
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")


# ── the per-store writers, each returning the PRIOR state ──────────────────

def _prior_adjudication(conn, detection_id):
    row = _adjudications.get_adjudication(conn, detection_id)
    if row is None:
        return None
    return {"verdict": row["verdict"], "note": row["note"]}


def _write_adjudication(conn, target_id, verdict, note, tags):
    prior = _prior_adjudication(conn, target_id)
    _adjudications.insert_adjudication(conn, target_id, verdict, note=note,
                                       tags=tags, commit=False)
    return prior


def _write_annotation(conn, target_id, verdict, note, tags):
    """A verdict on a HUMAN span re-describes that span's verdict in place.

    It deliberately does not insert a second annotation: the queue's items are
    spans a person already drew, and a verdict on one is a judgement of that
    same span, not a new observation. The prior verdict/note come back so undo
    can restore them.
    """
    row = _queries.get_annotation(conn, target_id)
    prior = {"verdict": row["verdict"], "note": row["note"]}
    conn.execute(
        "UPDATE annotations SET verdict = ?, note = COALESCE(?, note) "
        "WHERE id = ?",
        (verdict, note, target_id),
    )
    if tags:
        for category, values in tags.items():
            _queries.set_annotation_tags(conn, target_id, category, values,
                                         commit=False)
    return prior


def _write_window(conn, queue_id, target_id, window_index, verdict, note):
    from Working.review import window_verdicts as _wv
    if window_index is None:
        raise ValueError(
            "a window queue needs window_index alongside the window set id")
    prior = _wv.get_window_verdict(conn, target_id, window_index)
    if prior is not None:
        prior = {"verdict": prior["verdict"], "note": prior["note"]}
    _wv.write_window_verdict(conn, target_id, window_index, verdict,
                             note=note, queue_id=queue_id)
    return prior


def _restore_adjudication(conn, target_id, prior):
    if prior is None:
        adj = _adjudications.get_adjudication(conn, target_id)
        if adj is not None:
            conn.execute(
                "DELETE FROM adjudication_tags WHERE adjudication_id = ?",
                (adj["id"],))
            conn.execute("DELETE FROM adjudications WHERE detection_id = ?",
                         (target_id,))
    else:
        conn.execute(
            "UPDATE adjudications SET verdict = ?, note = ? "
            "WHERE detection_id = ?",
            (prior["verdict"], prior["note"], target_id))


def _restore_annotation(conn, target_id, prior):
    if prior is None:
        return
    conn.execute("UPDATE annotations SET verdict = ?, note = ? WHERE id = ?",
                 (prior["verdict"], prior["note"], target_id))


def _restore_window(conn, target_id, window_index, prior):
    from Working.review import window_verdicts as _wv
    if prior is None:
        _wv.delete_window_verdict(conn, target_id, window_index)
    else:
        _wv.write_window_verdict(conn, target_id, window_index,
                                 prior["verdict"], note=prior["note"])


# ── audit ───────────────────────────────────────────────────────────────────

def _audit(conn, queue_id, action, target_table, target_ids, payload):
    cur = conn.execute(
        """INSERT INTO review_audit
               (queue_id, action, target_table, target_ids, payload_json,
                created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (queue_id, action, target_table, json.dumps(list(target_ids)),
         json.dumps(payload), _now()),
    )
    return cur.lastrowid


# ── the public surface ──────────────────────────────────────────────────────

def _apply(conn, queue, target_id, verdict, note, tags, window_index):
    writes_to = queue["writes_to"]
    if writes_to == "adjudications":
        return _write_adjudication(conn, target_id, verdict, note, tags)
    if writes_to == "annotations":
        return _write_annotation(conn, target_id, verdict, note, tags)
    return _write_window(conn, queue["id"], target_id, window_index, verdict,
                         note)


def write_verdict(conn, queue_id, target_id, verdict, *, note=None, tags=None,
                  window_index=None):
    """Write one verdict through the queue that asked for it.

    Returns a dict describing what was written:
    `{'queue_id', 'target_id', 'verdict', 'writes_to', 'audit_id', 'prior'}`.

    Raises `PermissionError` on a rule-5 crossing (see the module docstring)
    and `ValueError` on an unknown verdict, queue or target.
    """
    queue = _queue_row(conn, queue_id)
    _check_verdict(verdict)
    _check_target(conn, queue["writes_to"], target_id)
    prior = _apply(conn, queue, target_id, verdict, note, tags, window_index)
    payload = {
        "writes_to": queue["writes_to"],
        "verdict": verdict,
        "note": note,
        "window_index": window_index,
        "targets": [{"target_id": target_id, "prior": prior,
                     "window_index": window_index}],
    }
    audit_id = _audit(conn, queue_id, "verdict", queue["writes_to"],
                      [target_id], payload)
    conn.commit()
    return {"queue_id": queue_id, "target_id": target_id, "verdict": verdict,
            "writes_to": queue["writes_to"], "audit_id": audit_id,
            "prior": prior}


def write_batch(conn, queue_id, target_ids, verdict, *, note=None, tags=None):
    """The same verdict against N targets, under ONE `review_audit` row.

    Every target is checked before anything is written, so a batch that
    contains a rule-5 crossing writes nothing at all.
    """
    queue = _queue_row(conn, queue_id)
    _check_verdict(verdict)
    target_ids = list(target_ids)
    for tid in target_ids:
        _check_target(conn, queue["writes_to"], tid)
    targets = []
    for tid in target_ids:
        prior = _apply(conn, queue, tid, verdict, note, tags, None)
        targets.append({"target_id": tid, "prior": prior,
                        "window_index": None})
    payload = {"writes_to": queue["writes_to"], "verdict": verdict,
               "note": note, "targets": targets}
    audit_id = _audit(conn, queue_id, "batch", queue["writes_to"],
                      target_ids, payload)
    conn.commit()
    return {"queue_id": queue_id, "verdict": verdict, "count": len(target_ids),
            "target_ids": target_ids, "writes_to": queue["writes_to"],
            "audit_id": audit_id}


def undo_last(conn, queue_id=None):
    """Reverse the newest un-undone Review write, optionally within one queue.

    Returns `{'audit_id','action','writes_to','target_ids','queue_id'}`, or
    None when there is nothing left to undo.
    """
    if queue_id is None:
        row = conn.execute(
            "SELECT * FROM review_audit WHERE undone_at IS NULL "
            "AND action != 'undo' ORDER BY id DESC LIMIT 1").fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM review_audit WHERE undone_at IS NULL "
            "AND action != 'undo' AND queue_id = ? "
            "ORDER BY id DESC LIMIT 1", (queue_id,)).fetchone()
    if row is None:
        return None
    payload = json.loads(row["payload_json"] or "{}")
    writes_to = payload.get("writes_to") or row["target_table"]
    for target in payload.get("targets", []):
        tid = target["target_id"]
        prior = target.get("prior")
        if writes_to == "adjudications":
            _restore_adjudication(conn, tid, prior)
        elif writes_to == "annotations":
            _restore_annotation(conn, tid, prior)
        elif writes_to == "window_verdicts":
            _restore_window(conn, tid, target.get("window_index"), prior)
    conn.execute("UPDATE review_audit SET undone_at = ? WHERE id = ?",
                 (_now(), row["id"]))
    conn.commit()
    return {"audit_id": row["id"], "action": row["action"],
            "writes_to": writes_to, "queue_id": row["queue_id"],
            "target_ids": json.loads(row["target_ids"] or "[]")}

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

**A window queue's target id IS its window index.** The window SET comes from
the queue's `source_ref`; the target id is the index into it. That is the
shape `Working.review.queues._resolve_windows` hands out, and the writer now
reads it the same way — it used to take the target id for the set id, which
made every window verdict either a foreign-key failure or a verdict filed
against the wrong set. `window_index=` is an optional restatement of the
target id (the bridge forwards the field whether or not the client sent it),
and a value that disagrees with the target id is refused.

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


def _check_window_target(conn, queue, target_id):
    """The window equivalent of "no detection with id X".

    A window queue's targets are indices into ONE set, so "does this target
    exist" means "is this index inside that set". An index outside it is a
    verdict on a window nobody was ever shown — and because
    `queues._resolve_windows` only ever lists `range(n_windows)`, such a row
    would never surface again to be noticed or undone. A set the queue names
    but that has since been deleted is a `ValueError` here rather than a bare
    foreign-key `IntegrityError` three frames down.
    """
    ws_id = _window_set_id(queue)
    row = conn.execute(
        "SELECT n_windows FROM window_sets WHERE id = ?", (ws_id,)).fetchone()
    if row is None:
        raise ValueError(
            f"review queue {queue['id']} names window set {ws_id}, which no "
            f"longer exists")
    index = int(target_id)
    if index < 0:
        raise ValueError(f"window index must be >= 0, got {index}")
    n_windows = row["n_windows"]
    if n_windows is not None and index >= int(n_windows):
        raise ValueError(
            f"window set {ws_id} has {int(n_windows)} windows; there is no "
            f"window {index} to give a verdict on")


def _check_target(conn, queue, target_id):
    """Refuse a target that belongs to the other store. Raises
    `PermissionError` for a crossing, `ValueError` for an id that is in
    neither store."""
    writes_to = queue["writes_to"]
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
        _check_window_target(conn, queue, target_id)
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


def _window_set_id(queue):
    """The window SET a window queue asks about.

    It is the queue's `source_ref` — "a window-set id" in the
    `review_queues.source_ref` schema comment — and NOT the target id. A queue
    asks about one set; its items are indices into that set.
    """
    ref = queue["source_ref"]
    if ref is None or str(ref).strip() == "":
        raise ValueError(
            f"review queue {queue['id']} writes window_verdicts but names no "
            f"window set in source_ref")
    return int(ref)


def _window_index_of(target_id, window_index):
    """The index within that set, which is the TARGET ID.

    `queues._resolve_windows` hands every window item out as
    `{'target_id': i, 'window_index': i, 'window_set_id': ...}`, so the id a
    caller sends back is the index. `window_index=` is an optional restatement
    of it — the bridge forwards the field whether or not the client set it —
    and a value that contradicts the target id is a caller bug, not a second
    coordinate, so it is refused rather than silently preferred.
    """
    idx = int(target_id)
    if window_index is not None and int(window_index) != idx:
        raise ValueError(
            f"window_index {window_index!r} contradicts target_id "
            f"{target_id!r}: for a window queue the target id IS the index "
            f"into the set named by the queue's source_ref")
    return idx


def _window_coords(queue, target_id, window_index):
    return (_window_set_id(queue),
            _window_index_of(target_id, window_index))


def _write_window(conn, queue, coords, verdict, note):
    from Working.review import window_verdicts as _wv
    ws_id, index = coords
    prior = _wv.get_window_verdict(conn, ws_id, index)
    if prior is not None:
        prior = {"verdict": prior["verdict"], "note": prior["note"],
                 "queue_id": prior["queue_id"]}
    _wv.write_window_verdict(conn, ws_id, index, verdict, note=note,
                             queue_id=queue["id"])
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


def _restore_window(conn, window_set_id, window_index, prior):
    """Put a window's verdict back the way the audit row found it.

    Both halves of the key come from the payload — the audit row has to be
    self-contained, because the queue it was written through can be closed or
    re-pointed by the time someone presses Ctrl-Z. `queue_id` is restored too:
    the row states which question the verdict answered, and a restored verdict
    that has forgotten its queue is not the row that was there before.
    """
    from Working.review import window_verdicts as _wv
    if prior is None:
        _wv.delete_window_verdict(conn, window_set_id, window_index)
    else:
        _wv.write_window_verdict(conn, window_set_id, window_index,
                                 prior["verdict"], note=prior.get("note"),
                                 queue_id=prior.get("queue_id"))


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
    """Write one verdict into whichever store the queue says it writes.

    Returns `(prior, coords)`: the state that was there before, and for a
    window queue the `(window_set_id, window_index)` the write landed on —
    because the audit payload must carry BOTH halves of that key or undo
    cannot find the row again.
    """
    writes_to = queue["writes_to"]
    if writes_to == "adjudications":
        return _write_adjudication(conn, target_id, verdict, note, tags), None
    if writes_to == "annotations":
        return _write_annotation(conn, target_id, verdict, note, tags), None
    coords = _window_coords(queue, target_id, window_index)
    return _write_window(conn, queue, coords, verdict, note), coords


def write_verdict(conn, queue_id, target_id, verdict, *, note=None, tags=None,
                  window_index=None):
    """Write one verdict through the queue that asked for it.

    Returns a dict describing what was written:
    `{'queue_id', 'target_id', 'verdict', 'writes_to', 'audit_id', 'prior'}`.

    For a window queue, `target_id` is the index into the window set named by
    the queue's `source_ref`; `window_index` is an optional restatement of it
    and may not contradict it.

    Raises `PermissionError` on a rule-5 crossing (see the module docstring)
    and `ValueError` on an unknown verdict, queue or target.
    """
    queue = _queue_row(conn, queue_id)
    _check_verdict(verdict)
    _check_target(conn, queue, target_id)
    prior, coords = _apply(conn, queue, target_id, verdict, note, tags,
                           window_index)
    payload = {
        "writes_to": queue["writes_to"],
        "verdict": verdict,
        "note": note,
        "window_set_id": coords[0] if coords else None,
        "window_index": coords[1] if coords else None,
        "targets": [{"target_id": target_id, "prior": prior,
                     "window_index": coords[1] if coords else None}],
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
        _check_target(conn, queue, tid)
    targets = []
    window_set_id = None
    for tid in target_ids:
        prior, coords = _apply(conn, queue, tid, verdict, note, tags, None)
        if coords is not None:
            window_set_id = coords[0]
        targets.append({"target_id": tid, "prior": prior,
                        "window_index": coords[1] if coords else None})
    payload = {"writes_to": queue["writes_to"], "verdict": verdict,
               "note": note, "window_set_id": window_set_id,
               "targets": targets}
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
            ws_id = payload.get("window_set_id")
            if ws_id is None:
                raise ValueError(
                    f"review_audit row {row['id']} writes window_verdicts but "
                    f"its payload names no window set, so the row it wrote "
                    f"cannot be located to undo it")
            _restore_window(conn, ws_id, target.get("window_index"), prior)
    conn.execute("UPDATE review_audit SET undone_at = ? WHERE id = ?",
                 (_now(), row["id"]))
    conn.commit()
    return {"audit_id": row["id"], "action": row["action"],
            "writes_to": writes_to, "queue_id": row["queue_id"],
            "target_ids": json.loads(row["target_ids"] or "[]")}

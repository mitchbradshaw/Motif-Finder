"""
queues.py
=========
Review queues: the descriptor store and the live source resolver
(stage-3 wiring prompt 05, PIPELINE_PRD §10.1).

**A queue holds no items of its own.** A row in `review_queues` records what a
queue *is* — its name, which kind of source it points at, which row that
source is, the unit a verdict lands on, which table that verdict writes, and
whether the machine's opinion is hidden (P20 blind) — and nothing about which
items are in it. `queue_items` resolves the source on every call. That is the
whole design: a verdict written anywhere else (Discovery's scoreboard, another
queue, a direct `adjudications` insert) immediately changes what this queue
shows, with nothing to keep in step (04-to-05 §1).

Rule 5 (CLAUDE.md) is carried in `writes_to`, decided ONCE at creation from
the source kind and stored where a person can read it, rather than re-inferred
at each verdict where a wrong inference would silently cross a machine
detection with a human verdict. Detection queues write `adjudications`; span
and sequence queues write `annotations`; window queues write `window_verdicts`
because a window is neither a detection nor a span a person drew.

Two exclusions are structural rather than cosmetic:

* **Superseded runs.** `queue_candidates` has no such filter and its existing
  callers do not want one, so the exclusion lives here, in the resolver: a run
  with `runs.superseded_at` set was *discarded*, and Discovery deliberately
  writes no verdicts when it discards (04-to-05 §2). Its detections stay in
  the table; without this filter they keep arriving in Review after the
  researcher threw them away.
* **The blind score.** A blind queue's items do not carry the machine score at
  all — the key is absent from the payload, not merely unrendered — because a
  number that reaches the browser is one inspector away from the eye it was
  meant to be kept from.

No UI library, no fastapi: `webui/server/review.py` calls into this, never the
other way round.
"""

import json
from datetime import datetime, timezone

from Working.database import queries as _queries
from Working.review.queue_state import ReviewQueue

# The six source kinds and what §10.1 says each one implies when the caller
# does not say otherwise: the unit a verdict lands on, the table it writes,
# and whether the machine's score is withheld.
SOURCE_KINDS = (
    "discovery-run",
    "seed-search",
    "explore-spans",
    "training-windows",
    "model-verification",
    "extract-events",
)

_DEFAULTS = {
    "discovery-run":      ("detection", "adjudications", 0),
    "seed-search":        ("detection", "adjudications", 0),
    "explore-spans":      ("human span", "annotations", 0),
    "training-windows":   ("window", "window_verdicts", 1),
    "model-verification": ("window", "window_verdicts", 1),
    "extract-events":     ("sequence", "annotations", 0),
}

_DETECTION_KINDS = ("discovery-run", "seed-search")
_WINDOW_KINDS = ("training-windows", "model-verification")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# ── the descriptor store ────────────────────────────────────────────────────

def create_queue(conn, *, name, source_kind, source_ref=None, unit=None,
                 writes_to=None, blind=None, cap=None, verdict_options=None,
                 filters=None, note=None):
    """Record a queue descriptor and return its id.

    `unit`, `writes_to` and `blind` are inferred from `source_kind` per §10.1
    unless given explicitly. `source_ref` is the row the kind keys on — a
    run-group id for a discovery run, a window-set id for a window queue, a
    session id for a seeded search — as TEXT, because the six kinds key on
    different things. `filters` is a dict passed through to the resolver.
    """
    if source_kind not in _DEFAULTS:
        raise ValueError(
            "source_kind must be one of {}, got {!r}".format(
                ", ".join(SOURCE_KINDS), source_kind))
    d_unit, d_writes, d_blind = _DEFAULTS[source_kind]
    cur = conn.execute(
        """INSERT INTO review_queues
               (name, source_kind, source_ref, unit, writes_to, blind, cap,
                verdict_options, filters_json, created_at, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, source_kind,
         None if source_ref is None else str(source_ref),
         unit or d_unit,
         writes_to or d_writes,
         d_blind if blind is None else int(bool(blind)),
         cap,
         None if verdict_options is None else json.dumps(list(verdict_options)),
         None if filters is None else json.dumps(filters),
         _now(), note),
    )
    conn.commit()
    return cur.lastrowid


def get_queue(conn, queue_id):
    """The descriptor as a dict (with `filters` decoded), or None."""
    row = conn.execute(
        "SELECT * FROM review_queues WHERE id = ?", (queue_id,)).fetchone()
    if row is None:
        return None
    q = _row_to_dict(row)
    q["filters"] = json.loads(q["filters_json"]) if q["filters_json"] else {}
    if q.get("verdict_options"):
        q["verdict_options"] = json.loads(q["verdict_options"])
    return q


def list_queues(conn, *, include_closed=False):
    """Every queue, newest last, each carrying its live total/judged/remaining."""
    sql = "SELECT * FROM review_queues"
    if not include_closed:
        sql += " WHERE closed_at IS NULL"
    sql += " ORDER BY id"
    out = []
    for row in conn.execute(sql).fetchall():
        q = _row_to_dict(row)
        q["filters"] = json.loads(q["filters_json"]) if q["filters_json"] else {}
        q.update(queue_counts(conn, q["id"]))
        out.append(q)
    return out


def close_queue(conn, queue_id):
    """Mark a queue closed. Closed queues leave the header and the list."""
    conn.execute("UPDATE review_queues SET closed_at = ? WHERE id = ?",
                 (_now(), queue_id))
    conn.commit()


# ── the resolver ────────────────────────────────────────────────────────────

def queue_items(conn, queue_id, *, limit=-1, offset=0, include_judged=False):
    """Resolve the queue's source NOW and return its items.

    Unjudged items only unless `include_judged`. Each item carries
    `target_id`, `unit` and `judged`; a blind queue's items carry no `score`
    key at all.
    """
    q = get_queue(conn, queue_id)
    if q is None:
        raise ValueError("no such queue: {!r}".format(queue_id))
    items = _resolve(conn, q)
    if not include_judged:
        items = [it for it in items if not it["judged"]]
    if offset:
        items = items[offset:]
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items


def queue_counts(conn, queue_id):
    """{'total', 'judged', 'remaining'} over the capped, resolved source."""
    q = get_queue(conn, queue_id)
    if q is None:
        raise ValueError("no such queue: {!r}".format(queue_id))
    items = _resolve(conn, q)
    judged = sum(1 for it in items if it["judged"])
    return {"total": len(items), "judged": judged,
            "remaining": len(items) - judged}


def header_counts(conn):
    """What the header badge shows: unjudged items across every open queue."""
    by_queue = []
    need_you = 0
    for row in conn.execute(
            "SELECT id, name FROM review_queues WHERE closed_at IS NULL "
            "ORDER BY id").fetchall():
        remaining = queue_counts(conn, row["id"])["remaining"]
        need_you += remaining
        by_queue.append({"id": row["id"], "name": row["name"],
                         "remaining": remaining})
    return {"need_you": need_you, "by_queue": by_queue}


# ── internals: one resolver per source kind ─────────────────────────────────

def _resolve(conn, q):
    kind = q["source_kind"]
    if kind in _DETECTION_KINDS:
        items = _resolve_detections(conn, q)
    elif kind in _WINDOW_KINDS:
        items = _resolve_windows(conn, q)
    elif kind == "explore-spans":
        items = _resolve_spans(conn, q)
    elif kind == "extract-events":
        items = _resolve_sequences(conn, q)
    else:                                   # pragma: no cover - CHECKed above
        raise ValueError("unresolvable source_kind: {!r}".format(kind))
    cap = q["cap"]
    if cap is not None and cap >= 0:
        items = items[:cap]
    return items


def _superseded_run_ids(conn):
    """Runs the researcher discarded (04-to-05 §2). Their detections stay in
    the table on purpose; they must not reach a queue."""
    return {r["id"] for r in conn.execute(
        "SELECT id FROM runs WHERE superseded_at IS NOT NULL").fetchall()}


def _resolve_detections(conn, q):
    filters = dict(q["filters"])
    if q["source_ref"] is not None and "run_group_id" not in filters:
        filters["run_group_id"] = int(q["source_ref"])
    # The same object Discovery's queue descriptor names, with the status
    # filter off so the queue can report `judged` as well as `remaining`.
    queue = ReviewQueue(conn, adjudication_status=None, **filters)
    superseded = _superseded_run_ids(conn)
    judged_ids = {r["detection_id"] for r in conn.execute(
        "SELECT detection_id FROM adjudications").fetchall()}
    blind = bool(q["blind"])
    items = []
    for cand in queue.candidates:
        if cand["run_id"] in superseded:
            continue
        item = {
            "target_id": cand["id"],
            "unit": q["unit"],
            "detection_id": cand["id"],
            "run_id": cand["run_id"],
            "recording_id": cand["recording_id"],
            "channel": cand["channel"],
            "start_idx": cand["start_idx"],
            "end_idx": cand["end_idx"],
            "judged": cand["id"] in judged_ids,
        }
        if not blind:
            item["score"] = cand["score"]
        items.append(item)
    return items


def _resolve_spans(conn, q):
    """Human spans a person marked `seed` in Explore (04-to-05 §4)."""
    params = []
    sql = ("SELECT id, recording_id, start_idx, end_idx, tag, note "
           "FROM annotations WHERE verdict = 'seed'")
    rec = q["filters"].get("recording_id")
    if rec is None and q["source_ref"] is not None:
        rec = int(q["source_ref"])
    if rec is not None:
        sql += " AND recording_id = ?"
        params.append(rec)
    sql += " ORDER BY id"
    judged = _audit_judged_ids(conn, q["id"])
    return [{
        "target_id": r["id"],
        "unit": q["unit"],
        "annotation_id": r["id"],
        "recording_id": r["recording_id"],
        "start_idx": r["start_idx"],
        "end_idx": r["end_idx"],
        "tag": r["tag"],
        "note": r["note"],
        "judged": r["id"] in judged,
    } for r in conn.execute(sql, params).fetchall()]


def _resolve_sequences(conn, q):
    """Catalogued spans whose singular events have not been resolved yet —
    `sequences.needs_extraction = 1`, the honest state for a claim recorded
    without inventing the events behind it."""
    params = []
    sql = ("SELECT id, sequence_key, recording_id, channel, start_idx, end_idx, "
           "n_events FROM sequences WHERE needs_extraction = 1")
    if q["source_ref"] is not None:
        sql += " AND id = ?"
        params.append(int(q["source_ref"]))
    sql += " ORDER BY id"
    judged = _audit_judged_ids(conn, q["id"])
    return [{
        "target_id": r["id"],
        "unit": q["unit"],
        "sequence_id": r["id"],
        "sequence_key": r["sequence_key"],
        "recording_id": r["recording_id"],
        "channel": r["channel"],
        "start_idx": r["start_idx"],
        "end_idx": r["end_idx"],
        "n_events": r["n_events"],
        "judged": r["id"] in judged,
    } for r in conn.execute(sql, params).fetchall()]


def _resolve_windows(conn, q):
    """Every index of a window set, minus those already in `window_verdicts`.

    A window queue carries no score whatever the `blind` flag says: the point
    of a verification pass is that the model's opinion is not in the room.
    """
    if q["source_ref"] is None:
        return []
    ws_id = int(q["source_ref"])
    row = conn.execute(
        "SELECT n_windows FROM window_sets WHERE id = ?", (ws_id,)).fetchone()
    if row is None or row["n_windows"] is None:
        return []
    judged = {r["window_index"] for r in conn.execute(
        "SELECT window_index FROM window_verdicts WHERE window_set_id = ?",
        (ws_id,)).fetchall()}
    return [{
        "target_id": i,
        "unit": q["unit"],
        "window_set_id": ws_id,
        "window_index": i,
        "judged": i in judged,
    } for i in range(int(row["n_windows"]))]


def _audit_judged_ids(conn, queue_id):
    """Which targets this queue has already been given a verdict on, for the
    kinds whose verdict table cannot be keyed back to the source row.

    A span verdict writes a NEW `annotations` row and an extraction writes
    `sequence_members`, so neither table says "this source item was judged".
    `review_audit` does: it is the ordered ledger of what Review wrote, and a
    row whose `undone_at` is set no longer counts. The ledger entry carries
    the source id under `target_id` / `target_ids` in `payload_json`.
    """
    out = set()
    for row in conn.execute(
            "SELECT payload_json FROM review_audit "
            "WHERE queue_id = ? AND undone_at IS NULL", (queue_id,)).fetchall():
        if not row["payload_json"]:
            continue
        try:
            payload = json.loads(row["payload_json"])
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("target_id") is not None:
            out.add(payload["target_id"])
        for tid in payload.get("target_ids") or ():
            out.add(tid)
    return out

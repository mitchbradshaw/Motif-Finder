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
from Working.database import vocabulary as _vocabulary
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


#: What each queue unit is MADE OF, and therefore the one store a verdict on
#: it may land in. This is rule 5 expressed as data. A queue whose `unit` and
#: `writes_to` disagree is itself the crossing, whatever else it says about
#: itself, and no verdict may be written through it.
_UNIT_STORE = {
    "detection": "adjudications",
    "human span": "annotations",
    "sequence": "annotations",
    "window": "window_verdicts",
}

#: The table a unit's ids are ids OF. A `sequence` target is a `sequences` row
#: even though its verdict lands in `annotations` — the two are different
#: questions and conflating them is what wrote a verdict onto a stranger.
_UNIT_SOURCE = {
    "detection": "detections",
    "human span": "annotations",
    "sequence": "sequences",
}

_UNIT_NOUN = {"detection": "detection", "human span": "annotation",
              "sequence": "sequence"}


def _row_exists(conn, table, row_id):
    return conn.execute(
        "SELECT 1 FROM {} WHERE id = ?".format(table), (row_id,)
    ).fetchone() is not None


def _target_int(target_id):
    try:
        return int(target_id)
    except (TypeError, ValueError):
        raise ValueError(
            f"a target id must be an integer, got {target_id!r}")


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


def _queue_is_itself_the_crossing(queue):
    """A queue whose `unit` and `writes_to` disagree is the crossing itself.

    `create_queue` infers `writes_to` from `source_kind`, but the column is
    settable from an HTTP body, and a queue that says "my items are detections
    and I write `annotations`" is a standing instruction to fabricate human
    verdicts. Refusing it here means no verdict can be written through it even
    if it reached the table.
    """
    unit = queue["unit"]
    if unit not in _UNIT_STORE:
        raise ValueError(f"unknown queue unit {unit!r}")
    expected = _UNIT_STORE[unit]
    if queue["writes_to"] != expected:
        raise PermissionError(
            f"{_RULE_5}. Review queue {queue['id']} says its unit is {unit!r} "
            f"but that it writes {queue['writes_to']!r}; a verdict on a {unit} "
            f"belongs in {expected!r}. The queue is itself the crossing, so no "
            f"verdict may be written through it.")


def _resolve_target(conn, queue, target_id):
    """What this queue's target id names, and which row a verdict lands on.

    Returns `(target_id, row_id)` — the same integer twice, except for a
    `sequence` queue, where the id names a `sequences` row and the verdict
    lands on that sequence's own `annotations` row.

    This replaces a check that asked "does a row with this id exist in the
    table I am about to write to" and returned as soon as it did. That is not
    a check: on the project database detections run 1..732 and annotations
    1..11269, so EVERY detection id is also a valid annotation id and the
    refusal branch was unreachable. The stage-1 tests passed only because they
    used synthetic ids that happened not to collide.

    The question is not "does this id exist somewhere" but **"is this the id of
    the thing this queue is made of"**, and the queue already says what that is
    in its `unit` column.
    """
    _queue_is_itself_the_crossing(queue)
    unit = queue["unit"]
    if unit == "window":
        _check_window_target(conn, queue, target_id)
        idx = _window_index_of(target_id, None)
        return idx, idx

    rid = _target_int(target_id)
    source = _UNIT_SOURCE[unit]
    if not _row_exists(conn, source, rid):
        # Not one of ours. If it is one of the OTHER stores' rows, the caller
        # crossed the line rather than mistyped, and the two deserve different
        # answers: a crossing is a PermissionError naming rule 5, a typo is a
        # ValueError.
        for other_unit, other_table in _UNIT_SOURCE.items():
            if other_table == source:
                continue
            if _row_exists(conn, other_table, rid):
                raise PermissionError(
                    f"{_RULE_5}. {_UNIT_NOUN[other_unit].capitalize()} {rid} "
                    f"was offered to review queue {queue['id']}, whose items "
                    f"are {_UNIT_NOUN[unit]}s writing {queue['writes_to']!r}. "
                    f"An id that exists in another store is not this queue's "
                    f"item; writing it would put a verdict on a row nobody was "
                    f"ever shown.")
        raise ValueError(f"no {_UNIT_NOUN[unit]} with id {rid}")

    if unit == "sequence":
        # `sequences.annotation_id` is the pointer; `sequences.id` is not. On
        # the project database every sequence id in the seeded extract-events
        # queue (119-148) is ALSO an annotation id, so taking the target id for
        # an annotation id wrote the reviewer's verdict onto an unrelated human
        # observation and left the intended one untouched.
        row = conn.execute(
            "SELECT annotation_id FROM sequences WHERE id = ?", (rid,)
        ).fetchone()
        ann = row["annotation_id"] if row is not None else None
        if ann is None:
            raise ValueError(
                f"sequence {rid} has no annotation_id, so there is no human "
                f"span for its verdict to land on. Refusing rather than "
                f"guessing at a row.")
        return rid, int(ann)

    return rid, rid


def _check_membership(conn, queue, target_ids):
    """Refuse a target this queue never showed anyone.

    The audit ledger is what undo and the judged-set are built on, so a row
    saying queue N judged an item it never listed is a false provenance trail —
    and on an annotations queue, where `judged` is READ from that ledger, it
    silently removes a stranger from somebody else's queue.
    """
    # NOT for an `explore-spans` queue. Its source predicate is
    # `annotations.verdict = 'seed'` -- the very field a verdict overwrites --
    # so membership there is self-invalidating: the first verdict removes the
    # span from its own queue and a second one could never be given. Where the
    # predicate is independent of the verdict (a run id, a window set, a
    # `needs_extraction` flag) the check is meaningful and is applied.
    if queue["unit"] == "human span":
        return
    from Working.review import queues as _queues
    members = {
        it["target_id"] for it in _queues.queue_items(
            conn, queue["id"], include_judged=True, include_prior_judged=True)
    }
    for tid in target_ids:
        if _target_int(tid) not in members:
            raise ValueError(
                f"review queue {queue['id']} never asked about target {tid}: "
                f"it is not among the items this queue resolves, so a verdict "
                f"attributed to it would be a false provenance trail.")


#: A bare list of tags carries no category, but the vocabulary is categorised
#: ("sharkfin" is an `element`, "clean" is a `quality`), so the category is
#: LOOKED UP per term rather than assumed. Dumping every bare tag into one
#: category silently loses the ones that belong elsewhere and rejects them as
#: unknown, which is what "Unknown vocabulary term: element='clean'" was.
_DEFAULT_TAG_CATEGORY = "element"


def _category_of(conn, value):
    row = conn.execute(
        "SELECT category FROM tag_vocabulary WHERE value = ? AND active = 1 "
        "ORDER BY category LIMIT 1", (value,)).fetchone()
    return row["category"] if row is not None else None


def _normalise_tags(conn, tags):
    """Accept `{category: [values]}` or a plain `[values]`, and return the
    former. A bare value is resolved to the category that defines it; one that
    no category defines is refused by name."""
    if tags is None:
        return None
    if isinstance(tags, dict):
        return {k: [v] if isinstance(v, str) else list(v)
                for k, v in tags.items()}
    if isinstance(tags, str):
        tags = [tags]
    out = {}
    for value in tags:
        category = _category_of(conn, value)
        if category is None:
            raise ValueError(
                f"Unknown vocabulary term: {value!r} is not in any tag "
                f"category")
        out.setdefault(category, []).append(value)
    return out


def _check_tags(conn, tags):
    """Validate every term BEFORE anything is written, so a bad tag does not
    leave a verdict behind with half its tags attached."""
    if not tags:
        return
    for category, values in tags.items():
        for value in values:
            if _vocabulary.get_term(conn, category, value) is None:
                raise ValueError(
                    f"Unknown vocabulary term: {category}={value!r}")


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
            _vocabulary.set_annotation_tags(conn, target_id, category, values,
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

def _apply(conn, queue, target_id, row_id, verdict, note, tags, window_index):
    """Write one verdict into whichever store the queue says it writes.

    `target_id` is what the queue handed out; `row_id` is the row the verdict
    lands on. They differ only for a sequence queue, where the target names a
    `sequences` row and the verdict belongs on that sequence's own annotation.

    Returns `(prior, coords)`: the state that was there before, and for a
    window queue the `(window_set_id, window_index)` the write landed on —
    because the audit payload must carry BOTH halves of that key or undo
    cannot find the row again.
    """
    writes_to = queue["writes_to"]
    if writes_to == "adjudications":
        return _write_adjudication(conn, row_id, verdict, note, tags), None
    if writes_to == "annotations":
        return _write_annotation(conn, row_id, verdict, note, tags), None
    coords = _window_coords(queue, target_id, window_index)
    return _write_window(conn, queue, coords, verdict, note), coords


def write_verdict(conn, queue_id, target_id, verdict, *, note=None, tags=None,
                  window_index=None):
    """Write one verdict through the queue that asked for it.

    Returns a dict describing what was written:
    `{'queue_id', 'target_id', 'row_id', 'verdict', 'writes_to', 'audit_id',
    'prior'}`. `row_id` is the row the verdict actually landed on, which is the
    target id except on a sequence queue.

    For a window queue, `target_id` is the index into the window set named by
    the queue's `source_ref`; `window_index` is an optional restatement of it
    and may not contradict it.

    Raises `PermissionError` on a rule-5 crossing (see the module docstring)
    and `ValueError` on an unknown verdict, queue, target or tag.
    """
    queue = _queue_row(conn, queue_id)
    _check_verdict(verdict)
    target_id, row_id = _resolve_target(conn, queue, target_id)
    _check_membership(conn, queue, [target_id])
    tags = _normalise_tags(conn, tags)
    _check_tags(conn, tags)
    prior, coords = _apply(conn, queue, target_id, row_id, verdict, note, tags,
                           window_index)
    payload = {
        "writes_to": queue["writes_to"],
        "verdict": verdict,
        "note": note,
        "window_set_id": coords[0] if coords else None,
        "window_index": coords[1] if coords else None,
        "targets": [{"target_id": target_id, "row_id": row_id, "prior": prior,
                     "window_index": coords[1] if coords else None}],
    }
    audit_id = _audit(conn, queue_id, "verdict", queue["writes_to"],
                      [target_id], payload)
    conn.commit()
    return {"queue_id": queue_id, "target_id": target_id, "row_id": row_id,
            "verdict": verdict, "writes_to": queue["writes_to"],
            "audit_id": audit_id, "prior": prior}


def write_batch(conn, queue_id, target_ids, verdict, *, note=None, tags=None):
    """The same verdict against N targets, under ONE `review_audit` row.

    Every target is resolved and checked before anything is written, so a batch
    containing a rule-5 crossing or a non-member writes nothing at all.

    Duplicate ids collapse: the person performed one action on one item, and N
    copies in the ledger would take N undos to reverse. An empty batch writes
    no audit row and returns `audit_id: None` — auditing a gesture that touched
    nothing puts an un-undoable row in the ledger.
    """
    queue = _queue_row(conn, queue_id)
    _check_verdict(verdict)
    seen, resolved = set(), []
    for tid in target_ids:
        t, row_id = _resolve_target(conn, queue, tid)
        if t in seen:
            continue
        seen.add(t)
        resolved.append((t, row_id))
    _check_membership(conn, queue, [t for t, _ in resolved])
    tags = _normalise_tags(conn, tags)
    _check_tags(conn, tags)
    if not resolved:
        return {"queue_id": queue_id, "verdict": verdict, "count": 0,
                "target_ids": [], "writes_to": queue["writes_to"],
                "audit_id": None}
    targets = []
    window_set_id = None
    for tid, row_id in resolved:
        prior, coords = _apply(conn, queue, tid, row_id, verdict, note, tags,
                               None)
        if coords is not None:
            window_set_id = coords[0]
        targets.append({"target_id": tid, "row_id": row_id, "prior": prior,
                        "window_index": coords[1] if coords else None})
    ids = [t for t, _ in resolved]
    payload = {"writes_to": queue["writes_to"], "verdict": verdict,
               "note": note, "window_set_id": window_set_id,
               "targets": targets}
    audit_id = _audit(conn, queue_id, "batch", queue["writes_to"], ids, payload)
    conn.commit()
    return {"queue_id": queue_id, "verdict": verdict, "count": len(ids),
            "target_ids": ids, "writes_to": queue["writes_to"],
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

    # A promotion is two halves — a verdict and a Library entry — and only
    # `promotion.unpromote` knows how to take both back. Undo used to fall
    # through this branch doing nothing and stamp `undone_at` anyway, burning
    # the one record that could have reversed it.
    if row["action"] == "promote":
        from Working.review import promotion as _promotion
        undone = dict(_promotion.unpromote(conn, row["id"]) or {})
        # Answer in `undo_last`'s own shape whatever `unpromote` returns, so a
        # caller reversing a mixed history does not have to know which kind of
        # act it just walked back.
        undone.setdefault("audit_id", row["id"])
        undone["action"] = "promote"
        undone.setdefault("writes_to", row["target_table"])
        undone.setdefault("queue_id", row["queue_id"])
        undone.setdefault("target_ids",
                          json.loads(row["target_ids"] or "[]"))
        return undone

    # An extraction is not a verdict: it created child spans and may have
    # cleared `needs_extraction`. Only `extraction` knows how to take that back.
    if row["action"] == "extract":
        from Working.review import extraction as _extraction
        undone = _extraction.undo_extraction(conn, row)
        conn.execute("UPDATE review_audit SET undone_at = ? WHERE id = ?",
                     (_now(), row["id"]))
        conn.commit()
        return {"audit_id": row["id"], "action": "extract",
                "writes_to": "annotations", "queue_id": row["queue_id"],
                "target_ids": json.loads(row["target_ids"] or "[]"),
                **undone}

    if writes_to not in ("adjudications", "annotations", "window_verdicts"):
        raise ValueError(
            f"review_audit row {row['id']} says it wrote {writes_to!r}, which "
            f"is not a store this function can reverse. Refusing to stamp it "
            f"undone: a row marked undone that was never reversed can never be "
            f"reversed again.")

    for target in payload.get("targets", []):
        # `row_id` is where the verdict actually landed; older rows predate it
        # and the two were the same then.
        rid = target.get("row_id", target["target_id"])
        prior = target.get("prior")
        if writes_to == "adjudications":
            _restore_adjudication(conn, rid, prior)
        elif writes_to == "annotations":
            _restore_annotation(conn, rid, prior)
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

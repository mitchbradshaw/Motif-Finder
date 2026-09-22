"""
promotion.py
============
Spec P21 — **an `S` verdict promotes.** The thing a person just called a seed
stops being a row in somebody's result set and becomes a motif in the Library:
one `motif_entry` for its shape, one `motif_member` for the place it was found,
revision 1 for the span the matcher will compare against.

Two rules shape every line below.

**There is one identity path, and it is the importer's.** `docs/LIBRARY_STORAGE.md`
§2 puts identity in two halves — the content hash says *which entry*, the
occurrence says *which member* — and Prompt 03 already wired that walk:
`Working.library.identity.hash_span` reads the span off disk and digests it,
`Working.library.dedupe.classify` asks whether that shape is already held,
`Working.database.runs.insert_motif_entry` / `get_or_create_motif_member` write
the two rows idempotently, and `Working.library.revisions.add_revision` gives
the member its rev 1. A promotion that re-derived any of that would be a second
answer to "is this the same shape", and the Library may only have one. So this
module contains no hashing, no span comparison and no INSERT into either motif
table that does not go through those functions.

**Rule 5 reaches all the way down here** (CLAUDE.md rule 5). What is promoted
is either a machine `detections` row or a human `annotations` row, and the
queue's own `writes_to` says which — it is the decision made once, at queue
creation, rather than guessed per verdict. A detection promotes as a `machine`
revision carrying its `detection_id`; an annotation promotes as a `human`
revision carrying its `annotation_id`. `revisions.add_revision` refuses the
crossing by name, and this module never gives it the chance.

**The verdict comes first, and the two halves undo together.** `promote` calls
`Working.review.verdicts.write_verdict` before it touches the Library — the
person's judgement is the fact, the Library rows are its consequence — and
records **one** `review_audit` row with action `'promote'` whose `payload_json`
carries enough to reverse both. `unpromote(conn, audit_id)` is P21's Ctrl-Z: it
removes the rows this promotion created (and only those: an entry another
member still hangs off is kept) and then reverses the verdict.

Nothing here imports a UI library or fastapi.
"""

import datetime
import json

from Working.database import runs as R
from Working.library import dedupe, revisions
from Working.library.identity import hash_span

#: The verdict a promotion writes when the caller does not say otherwise.
#: `S` in the Review vocabulary, `seed` in the database.
SEED = "seed"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _verdicts():
    """`Working.review.verdicts`, imported at call time.

    Deliberately not a module-level import: `promotion` is loaded by the API
    router and by tests that never promote anything, and the verdict writer is
    a sibling module that lands on its own schedule. Importing it lazily keeps
    "the verdict writer is missing" an error at the moment a verdict is
    written, naming that, rather than an import error three modules away.
    """
    from Working.review import verdicts

    return verdicts


# ── what is being promoted ───────────────────────────────────────────────────

def _queue_row(conn, queue_id):
    row = conn.execute(
        "SELECT * FROM review_queues WHERE id = ?", (int(queue_id),)
    ).fetchone()
    if row is None:
        raise ValueError(f"No review queue with id={queue_id}")
    return row


def resolve_target(conn, queue_id, target_id):
    """The span behind one queue item, and which side of rule 5 it is on.

    Returns `{'origin', 'recording_id', 'channel', 'start_idx', 'end_idx',
    'detection_id', 'annotation_id'}`. `origin` is `revisions.MACHINE` for a
    detection and `revisions.HUMAN` for an annotation, decided by the queue's
    stored `writes_to` rather than by looking for the id in both tables — a
    lookup that found a row in each would have to guess, and guessing is how a
    human verdict ends up on a machine row.

    A window queue has nothing to promote: a window is an index into a window
    set, not a span anyone drew, and it has no place in the Library. Refused by
    name.
    """
    queue = _queue_row(conn, queue_id)
    writes_to = queue["writes_to"]

    if writes_to == "window_verdicts":
        raise ValueError(
            f"Queue {queue_id} judges windows, and a window is an index into a "
            "window set rather than a span: there is nothing to promote into "
            "the Library. Promote the detection or the span a window covers."
        )

    if writes_to == "adjudications":
        row = conn.execute(
            """SELECT d.id AS detection_id, d.start_idx, d.end_idx,
                      r.recording_id
                 FROM detections d JOIN runs r ON r.id = d.run_id
                WHERE d.id = ?""",
            (int(target_id),),
        ).fetchone()
        if row is None:
            raise ValueError(f"No detection with id={target_id}")
        recording_id = row["recording_id"]
        detection_id, annotation_id = int(row["detection_id"]), None
        origin = revisions.MACHINE
    elif writes_to == "annotations":
        # The queue's unit decides what the id NAMES. On a sequence queue it
        # names a `sequences` row and the span lives on that sequence's own
        # annotation; taking it for an `annotations` id promoted whichever
        # unrelated human span happened to share the number. One resolver, in
        # `verdicts`, so the two cannot drift apart again.
        _, row_id = _verdicts()._resolve_target(conn, queue, target_id)
        row = conn.execute(
            "SELECT * FROM annotations WHERE id = ?", (int(row_id),)
        ).fetchone()
        if row is None:
            raise ValueError(f"No annotation with id={row_id}")
        recording_id = row["recording_id"]
        detection_id, annotation_id = None, int(row["id"])
        origin = revisions.HUMAN
    else:  # pragma: no cover - the CHECK constraint allows only three values
        raise ValueError(
            f"Queue {queue_id} writes to {writes_to!r}, which is not a table a "
            "promotion knows how to read a span out of."
        )

    recording = conn.execute(
        "SELECT channel FROM recordings WHERE id = ?", (int(recording_id),)
    ).fetchone()
    if recording is None:
        raise ValueError(
            f"Target {target_id} names recording {recording_id}, which is not "
            "registered; its span cannot be hashed."
        )

    return {
        "origin": origin,
        "recording_id": int(recording_id),
        "channel": int(recording["channel"]),
        "start_idx": int(row["start_idx"]),
        "end_idx": int(row["end_idx"]),
        "detection_id": detection_id,
        "annotation_id": annotation_id,
    }


# ── the promotion ────────────────────────────────────────────────────────────

def promote(conn, queue_id, target_id, *, verdict=SEED, note=None, tags=None):
    """Write the verdict, then put its target in the Library. P21.

    Returns `{'entry_id', 'member_id', 'created', 'verdict', 'audit_id'}`.
    `created` is True only when this call created the `motif_entry` — a
    recurrence of a shape already held is a new member of the *existing* entry
    and reports False, as does promoting the same target twice, which writes
    nothing at all the second time.

    One `review_audit` row is written, action `'promote'`, carrying both halves
    so `unpromote` can reverse them together.
    """
    target = resolve_target(conn, queue_id, target_id)

    # The judgement is the fact; the Library rows are its consequence. So the
    # verdict is written first, through the one writer, and never re-spelled
    # here.
    verdict_record = _verdicts().write_verdict(
        conn, queue_id, target_id, verdict, note=note, tags=tags
    )

    digest = hash_span(conn, target["recording_id"], target["channel"],
                       target["start_idx"], target["end_idx"])
    decision = dedupe.classify(
        conn, content_hash=digest, recording_id=target["recording_id"],
        channel=target["channel"], start_idx=target["start_idx"],
        end_idx=target["end_idx"],
    )

    created_at = _now()
    entry_id = decision["entry_id"]
    entry_created = entry_id is None
    if entry_created:
        entry_id = R.insert_motif_entry(
            conn, target["recording_id"], target["start_idx"],
            target["end_idx"], detection_id=target["detection_id"],
            created_at=created_at, commit=False)
        conn.execute(
            """UPDATE motif_entry
                  SET content_hash = ?, channel = ?, source_kind = 'review'
                WHERE id = ?""",
            (digest, target["channel"], entry_id),
        )

    member_before = conn.execute(
        """SELECT id FROM motif_member
            WHERE entry_id = ? AND recording_id = ? AND start_idx = ?
              AND end_idx = ?""",
        (entry_id, target["recording_id"], target["start_idx"],
         target["end_idx"]),
    ).fetchone()
    member_id = R.get_or_create_motif_member(
        conn, entry_id, target["recording_id"], target["start_idx"],
        target["end_idx"], commit=False)
    member_created = member_before is None
    conn.execute(
        "UPDATE motif_member SET content_hash = ?, channel = ? WHERE id = ?",
        (digest, target["channel"], member_id),
    )

    # Rev 1 is what the matcher compares against (§4.2 rule 4), so a member
    # that already has one keeps it: a second promotion of the same span is a
    # no-op, not a re-description.
    revision_row = conn.execute(
        "SELECT id FROM motif_member_revision WHERE member_id = ? AND revision = 1",
        (member_id,),
    ).fetchone()
    revision_created = revision_row is None
    revision_id = None if revision_row is None else revision_row["id"]
    if revision_created:
        revision_id = revisions.add_revision(
            conn, member_id, origin=target["origin"],
            start_idx=target["start_idx"], end_idx=target["end_idx"],
            detection_id=target["detection_id"],
            annotation_id=target["annotation_id"],
            content_hash=digest, created_at=created_at, commit=False)

    payload = {
        "queue_id": int(queue_id),
        "target_id": int(target_id),
        "entry_id": int(entry_id),
        "member_id": int(member_id),
        "revision_id": revision_id,
        "entry_created": bool(entry_created),
        "member_created": bool(member_created),
        "revision_created": bool(revision_created),
        "content_hash": digest,
        "origin": target["origin"],
        "verdict": _jsonable(verdict_record),
    }
    cur = conn.execute(
        """INSERT INTO review_audit
               (queue_id, action, target_table, target_ids, payload_json,
                created_at)
           VALUES (?, 'promote', 'motif_member', ?, ?, ?)""",
        (int(queue_id), json.dumps([int(member_id)]), json.dumps(payload),
         created_at),
    )
    audit_id = cur.lastrowid
    conn.commit()

    return {
        "entry_id": int(entry_id),
        "member_id": int(member_id),
        "created": bool(entry_created),
        "verdict": verdict_record,
        "audit_id": int(audit_id),
    }


# ── Ctrl-Z ───────────────────────────────────────────────────────────────────

def unpromote(conn, audit_id):
    """Reverse a promotion: the Library rows **and** the verdict. P21/§10.4.

    Only what that promotion created is removed. A member added to an entry
    that other occurrences still hang off leaves the entry alone, and a second
    promotion of an already-held span created nothing, so it removes nothing —
    but it still reverses its verdict, because the person's judgement was
    written either way.

    Refused with a `ValueError` on an audit row that is not a promotion or has
    already been undone: undoing an undo is not an undo.
    """
    row = conn.execute(
        "SELECT * FROM review_audit WHERE id = ?", (int(audit_id),)
    ).fetchone()
    if row is None:
        raise ValueError(f"No review_audit row with id={audit_id}")
    if row["action"] != "promote":
        raise ValueError(
            f"review_audit {audit_id} records a {row['action']!r}, not a "
            "promotion; unpromote reverses promotions only."
        )
    if row["undone_at"]:
        raise ValueError(
            f"Promotion {audit_id} was already undone at {row['undone_at']}."
        )

    payload = json.loads(row["payload_json"] or "{}")
    entry_id = payload.get("entry_id")
    member_id = payload.get("member_id")

    if payload.get("revision_created") and member_id is not None:
        conn.execute("UPDATE motif_member SET current_revision_id = NULL "
                     "WHERE id = ?", (member_id,))
        conn.execute("DELETE FROM motif_member_revision WHERE member_id = ?",
                     (member_id,))
    if payload.get("member_created") and member_id is not None:
        conn.execute("DELETE FROM motif_member WHERE id = ?", (member_id,))
    if payload.get("entry_created") and entry_id is not None:
        still_held = conn.execute(
            "SELECT COUNT(*) AS n FROM motif_member WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()["n"]
        if still_held == 0:
            conn.execute("DELETE FROM motif_entry WHERE id = ?", (entry_id,))

    # Stamped before the verdict half is reversed: the fallback route asks the
    # verdict writer for "the newest thing this queue has not undone", and
    # this promotion's own audit row is newer than the verdict it wrote.
    conn.execute("UPDATE review_audit SET undone_at = ? WHERE id = ?",
                 (_now(), int(audit_id)))
    _reverse_verdict(conn, payload)
    conn.commit()

    return {
        "audit_id": int(audit_id),
        "entry_id": entry_id,
        "member_id": member_id,
        "entry_removed": bool(payload.get("entry_created")),
        "member_removed": bool(payload.get("member_created")),
    }


def _reverse_verdict(conn, payload):
    """Take the verdict half back.

    `write_verdict` returns the queue's `writes_to`, the target it wrote and
    the **prior** state of that row — reversing to "unjudged" and reversing to
    "it was `interesting` before" are different acts, which is why the prior is
    carried rather than assumed. The restore is the verdict writer's own, taken
    by name from that module: a promotion must not hold a second opinion about
    what a verdict row looks like.

    If those restorers are ever renamed, the fallback is the public
    `undo_last`, which by this point reaches the verdict audit row — this
    promotion's own row is already stamped undone.
    """
    record = payload.get("verdict") or {}
    verdicts = _verdicts()

    writes_to = record.get("writes_to")
    target_id = record.get("target_id")
    prior = record.get("prior")
    restorer = {
        "adjudications": getattr(verdicts, "_restore_adjudication", None),
        "annotations": getattr(verdicts, "_restore_annotation", None),
        "window_verdicts": getattr(verdicts, "_restore_window", None),
    }.get(writes_to)

    if callable(restorer) and target_id is not None:
        if writes_to == "window_verdicts":
            restorer(conn, target_id, record.get("window_index"), prior)
        else:
            restorer(conn, target_id, prior)
    else:  # pragma: no cover - only if the verdict writer is restructured
        verdicts.undo_last(conn, payload.get("queue_id"))

    verdict_audit_id = record.get("audit_id")
    if verdict_audit_id is not None:
        conn.execute(
            "UPDATE review_audit SET undone_at = COALESCE(undone_at, ?) "
            "WHERE id = ?", (_now(), verdict_audit_id))


def _jsonable(value):
    """A verdict record, made storable without assuming its exact shape.

    `write_verdict` returns a dict, but whether its values are plain or carry a
    `sqlite3.Row` is that module's choice; a promotion must not lose its audit
    trail over it.
    """
    try:
        json.dumps(value)
        return value
    except TypeError:
        if hasattr(value, "keys"):
            return {k: _jsonable(value[k]) for k in value.keys()}
        if isinstance(value, (list, tuple)):
            return [_jsonable(v) for v in value]
        return str(value)

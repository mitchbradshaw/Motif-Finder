"""
sequence_queue.py
=================
The *sequence review* Review queue (2026-11-23, the researcher): "is this span a sequence?", asked once per
candidate, with an accepted sequence stored as a sequence in the Library.

In plain words: a sequence is a run of events in order on one channel, with gaps between them (the `sequences`
schema comment). Candidates come from anywhere a sequence can be proposed - accepted events chained by how close
they follow each other, accepted spans that turn out to hold several falls, a detector's proposals - and the
researcher's own hand-labelled sequences. Each is put to a person once. An accepted one becomes a HUMAN sequence
in the Library, its single events still to be resolved; that is what the candidate-event queue does next.

**A candidate is a machine claim, stored as one** (CLAUDE.md rule 5). `send_to_sequence_review` writes each
proposed span as a `sequences` row with `origin = 'machine'`, its events as `sequence_members` in order, through
the importer's one INSERT (`importers.sequences.insert_sequence`), keyed by provenance and span so sending it again
is a no-op. A hand-labelled sequence (`origin = 'human'`) joins the queue by id, as it is.

**The verdict is a person's, written in `annotations` over the sequence's span.**

* On a candidate it is a NEW row (`source = 'sequence_review'`, `event_count` = the candidate's events, so the
  accepted catalogue treats it as a reviewed region and never as one event), re-described in place by a later
  verdict. Nothing here writes a machine row: the candidate stays exactly as it was proposed.
* On a hand-labelled sequence it re-describes that sequence's own annotation in place - the existing rule for a
  `sequence` unit (`verdicts._resolve_target`), so the September catalogue's sequences are judged where they live.

**Accepting stores the sequence.** `interesting` on a candidate also writes a `sequences` row with
`origin = 'human'`, `annotation_id` = the verdict's row, `needs_extraction = 1` and `source_ref` = the candidate it
came from - the annotations importer's shape for a human sequence (`importers.annotations`). Rejecting stores none;
re-judging an accepted candidate as not a sequence takes its row back out (refused once events hang off it); undo
reverses every step through the audit payload (`restore_side_effects`).

**Five words, minus `seed`** (the vocabulary is fixed: researcher, 2026-10-05). A seed is a single event promoted
to the Library; a sequence is accepted as `interesting`, and `unsure` is answered here without a side.

**Judged.** A candidate is judged once a sequence-review annotation over its span exists (whichever queue wrote
it), so a second send does not ask again. A hand-labelled sequence already carries the catalogue's verdict, so it
counts as judged only through THIS queue's ledger (`review_audit`); the catalogue's word is shown beside it as
`catalogue_verdict`.

No UI library: `webui/server` calls into this, never the other way round.
"""

import datetime
import json

from Working.database import queries as _queries
from Working.library.importers.sequences import insert_sequence

#: `review_queues.source_kind` for this queue, and its unit.
SOURCE_KIND = "sequence-review"
UNIT = "sequence"
#: `annotations.source` on every verdict this queue writes, and `sequences.source_kind` of an accepted sequence.
REVIEW_SOURCE = "sequence_review"
#: The five-word vocabulary, minus `seed`: a seed is a single event.
VERDICT_OPTIONS = ("interesting", "not_interesting", "artifact", "unsure")
#: The verdicts that store a sequence.
ACCEPT = ("interesting",)
CANDIDATE_ORIGIN = "machine"
QUEUE_NOTE = ("Is each span a sequence - a run of events in order on one channel? Candidates are machine "
              "proposals; an accepted one is stored as a human sequence in the Library, its single events still to "
              "be resolved. Hand-labelled sequences are asked again here; the catalogue's word is shown beside them.")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


#: Every candidate's `sequence_key` starts with this. A candidate is a proposal awaiting review, not Library content:
#: the Library's reads of `sequences` (its counts, list, coverage and groupings) leave such rows out with
#: `NOT_CANDIDATE_SQL`, and an accepted one becomes Library content as the human sequence it is stored as.
CANDIDATE_KEY_PREFIX = "candidate:"
NOT_CANDIDATE_SQL = f"sequence_key NOT LIKE '{CANDIDATE_KEY_PREFIX}%'"


def candidate_key(provenance, recording_id, start_idx, end_idx):
    """The machine row's `sequence_key`: where it came from and where it is - so one proposal sent twice is one row."""
    return f"{CANDIDATE_KEY_PREFIX}{provenance}:{int(recording_id)}:{int(start_idx)}:{int(end_idx)}"


def accepted_key(annotation_id):
    """The stored human sequence's `sequence_key`: the verdict it came from (never collides with a catalogue key)."""
    return f"sequence_review_a{int(annotation_id)}"


# ── candidates and the queue ────────────────────────────────────────────────

def _checked(conn, span):
    rec = int(span["recording_id"])
    a, b = int(span["start_idx"]), int(span["end_idx"])
    events = sorted((int(e["start_idx"]), int(e["end_idx"])) for e in (span.get("events") or ()))
    if not events:
        raise ValueError(f"a sequence candidate names the events it is made of; the span {rec}:{a}-{b} names none")
    row = conn.execute("SELECT channel, fs, n_samples FROM recordings WHERE id = ?", (rec,)).fetchone()
    if row is None:
        raise ValueError(f"no recording {rec}")
    if not (0 <= a < b <= int(row["n_samples"])):
        raise ValueError(f"span {a}-{b} is not inside recording {rec} (0-{row['n_samples']})")
    for s, e in events:
        if not (a <= s < e <= b):
            raise ValueError(f"event {s}-{e} lies outside its candidate's own span {a}-{b} on recording {rec}")
    return rec, a, b, events, row


def register_candidates(conn, spans, *, provenance):
    """Write each proposed span as a machine `sequences` row with its events; return `(ids, n_created)`.

    `spans`: dicts with `recording_id`, `start_idx`, `end_idx` (absolute samples) and `events` (each a
    `start_idx`/`end_idx`, inside the span), optionally `note` and `evidence` (kept as JSON in `source_store`) and
    `source_ref`. A span already registered under this provenance is returned, not written again. Does not commit.
    """
    ids, created = [], 0
    now = _now()
    for span in spans:
        rec, a, b, events, row = _checked(conn, span)
        key = candidate_key(provenance, rec, a, b)
        hit = conn.execute("SELECT id FROM sequences WHERE sequence_key = ? AND origin = ?",
                           (key, CANDIDATE_ORIGIN)).fetchone()
        if hit is not None:
            ids.append(int(hit[0]))
            continue
        fs = float(row["fs"] or 1.0)
        gaps = [None] + [(e2[0] - e1[0]) / fs for e1, e2 in zip(events, events[1:])]
        store = {k: span[k] for k in ("note", "evidence") if span.get(k) is not None}
        sid = insert_sequence(
            conn,
            dict(sequence_key=key, origin=CANDIDATE_ORIGIN, recording_id=rec, channel=int(row["channel"]),
                 start_idx=a, end_idx=b, n_events=len(events), needs_extraction=0, source_kind=str(provenance),
                 source_store=json.dumps(store, sort_keys=True) if store else None,
                 source_ref=None if span.get("source_ref") is None else str(span["source_ref"]),
                 content_hash=None, created_at=now),
            [dict(member_id=None, start_idx=s, end_idx=e, gap_before=g) for (s, e), g in zip(events, gaps)])
        ids.append(int(sid))
        created += 1
    return ids, created


def open_queue(conn, name):
    """The id of the open sequence-review queue called `name`, or None."""
    row = conn.execute("SELECT id FROM review_queues WHERE closed_at IS NULL AND source_kind = ? AND name = ? "
                       "ORDER BY id DESC LIMIT 1", (SOURCE_KIND, name)).fetchone()
    return None if row is None else int(row[0])


def send_to_sequence_review(conn, *, spans=(), sequence_ids=(), provenance, name, note=None):
    """THE entry point: register `spans` as candidates (`register_candidates`), add `sequence_ids` (existing rows,
    e.g. hand-labelled sequences), and put them all in the open queue called `name` - made through
    `queues.create_queue`, or widened when it is already open. Commits.

    Returns `{"queue_id", "sequence_ids", "created"}`: the ids in the order given (spans first), and how many
    candidate rows this call wrote.
    """
    from Working.review import queues as Q

    ids, created = register_candidates(conn, spans, provenance=provenance)
    for sid in sequence_ids:
        if conn.execute("SELECT 1 FROM sequences WHERE id = ?", (int(sid),)).fetchone() is None:
            conn.rollback()
            raise ValueError(f"no sequence {sid}")
    ids = list(dict.fromkeys(ids + [int(s) for s in sequence_ids]))
    found = open_queue(conn, name)
    if found is None:
        conn.commit()
        found = Q.create_queue(conn, name=name, source_kind=SOURCE_KIND, verdict_options=list(VERDICT_OPTIONS),
                               filters={"sequence_ids": sorted(ids)}, note=note or QUEUE_NOTE)
    else:
        q = Q.get_queue(conn, found)
        have = [int(i) for i in (q["filters"].get("sequence_ids") or [])]
        union = sorted(set(have) | set(ids))
        if union != sorted(have):
            filters = dict(q["filters"])
            filters["sequence_ids"] = union
            conn.execute("UPDATE review_queues SET filters_json = ? WHERE id = ?", (json.dumps(filters), found))
    conn.commit()
    return {"queue_id": int(found), "sequence_ids": ids, "created": created}


# ── where a verdict lands ───────────────────────────────────────────────────

def _sequence(conn, sequence_id):
    row = conn.execute("SELECT * FROM sequences WHERE id = ?", (int(sequence_id),)).fetchone()
    if row is None:
        raise ValueError(f"no sequence {sequence_id}")
    return row


def _hand_labelled(seq):
    return seq["origin"] == "human" and seq["annotation_id"] is not None


def _review_row_over(conn, recording_id, start_idx, end_idx):
    row = conn.execute("SELECT id FROM annotations WHERE source = ? AND recording_id = ? AND start_idx = ? "
                       "AND end_idx = ? AND deleted_at IS NULL ORDER BY id DESC LIMIT 1",
                       (REVIEW_SOURCE, int(recording_id), int(start_idx), int(end_idx))).fetchone()
    return None if row is None else int(row[0])


def review_annotation_id(conn, sequence_id):
    """The annotation a verdict on this sequence lands on, or None (the first verdict writes a new one): a
    hand-labelled sequence's own row, else this queue's row over exactly the candidate's span."""
    seq = conn.execute("SELECT * FROM sequences WHERE id = ?", (int(sequence_id),)).fetchone()
    if seq is None:
        return None
    if _hand_labelled(seq):
        return int(seq["annotation_id"])
    return _review_row_over(conn, seq["recording_id"], seq["start_idx"], seq["end_idx"])


def _stored_for(conn, annotation_id):
    return conn.execute("SELECT * FROM sequences WHERE origin = 'human' AND source_kind = ? AND annotation_id = ?",
                        (REVIEW_SOURCE, int(annotation_id))).fetchone()


def _store(conn, seq, annotation_id):
    """The accepted candidate, as a human sequence over the verdict's own annotation (the annotations importer's
    shape: `needs_extraction = 1`, the events not invented)."""
    cur = conn.execute(
        """INSERT INTO sequences
               (sequence_key, origin, recording_id, channel, start_idx, end_idx, n_events, needs_extraction,
                source_kind, source_store, source_ref, annotation_id, content_hash, created_at)
           VALUES (?, 'human', ?, ?, ?, ?, ?, 1, ?, NULL, ?, ?, NULL, ?)""",
        (accepted_key(annotation_id), seq["recording_id"], seq["channel"], seq["start_idx"], seq["end_idx"],
         seq["n_events"], REVIEW_SOURCE, str(seq["id"]), int(annotation_id), _now()))
    return int(cur.lastrowid)


def verdict_note(seq, note=None):
    """The note every verdict row on a candidate carries: where the question came from."""
    text = (f"judged in Review as a sequence: {seq['source_kind']} candidate {seq['id']}, "
            f"{seq['n_events']} events")
    return f"{text} — {note}" if note else text


def write_sequence_verdict(conn, queue, sequence_id, verdict, note=None, tags=None):
    """One human verdict on one sequence, into `annotations` over its span; an accept also stores the sequence.

    Returns `(prior, annotation_id)`. `prior` is what undo needs: `{"inserted": True}` for a new row, else the
    row's old verdict/note/tags, plus `created_sequence_id` / `deleted_sequence` when the stored sequence followed
    the verdict. Does not commit (the verdict writer commits with its audit row).
    """
    from Working.database import vocabulary as _vocabulary

    if verdict not in VERDICT_OPTIONS:
        raise ValueError(f"a sequence-review queue takes {', '.join(VERDICT_OPTIONS)}; got {verdict!r} "
                         "(a seed is a single event: a sequence is accepted as interesting)")
    seq = _sequence(conn, sequence_id)
    if _hand_labelled(seq):
        aid = int(seq["annotation_id"])
        row = _queries.get_annotation(conn, aid)
        prior = {"verdict": row["verdict"], "note": row["note"],
                 "tags": _vocabulary.get_annotation_tags(conn, aid)}
        conn.execute("UPDATE annotations SET verdict = ?, note = COALESCE(?, note) WHERE id = ?",
                     (verdict, note, aid))
    else:
        text = verdict_note(seq, note)
        aid = review_annotation_id(conn, sequence_id)
        if aid is not None:
            row = _queries.get_annotation(conn, aid)
            prior = {"verdict": row["verdict"], "note": row["note"],
                     "tags": _vocabulary.get_annotation_tags(conn, aid)}
            conn.execute("UPDATE annotations SET verdict = ?, note = ? WHERE id = ?", (verdict, text, aid))
        else:
            aid = _queries.insert_annotation(conn, int(seq["recording_id"]), int(seq["start_idx"]),
                                             int(seq["end_idx"]), verdict, source=REVIEW_SOURCE, note=text,
                                             event_count=seq["n_events"], commit=False)
            prior = {"inserted": True}
        stored = _stored_for(conn, aid)
        if verdict in ACCEPT and stored is None:
            prior["created_sequence_id"] = _store(conn, seq, aid)
        elif verdict not in ACCEPT and stored is not None:
            if conn.execute("SELECT COUNT(*) FROM sequence_members WHERE sequence_id = ?",
                            (stored["id"],)).fetchone()[0]:
                raise ValueError(f"sequence {stored['id']} already has events resolved from it; it cannot be "
                                 "un-accepted here")
            prior["deleted_sequence"] = {k: stored[k] for k in stored.keys()}
            conn.execute("DELETE FROM sequences WHERE id = ?", (stored["id"],))
    if tags:
        for category, values in tags.items():
            _vocabulary.set_annotation_tags(conn, aid, category, values, commit=False)
    return prior, int(aid)


def restore_side_effects(conn, prior):
    """Undo's half for the stored sequence: take back a row an accept created, or put back one a rejection
    removed. The annotation itself is restored by `verdicts._restore_annotation`."""
    if not prior:
        return
    created = prior.get("created_sequence_id")
    if created is not None:
        conn.execute("DELETE FROM sequences WHERE id = ? AND origin = 'human' AND source_kind = ?",
                     (int(created), REVIEW_SOURCE))
    gone = prior.get("deleted_sequence")
    if gone:
        cols = list(gone)
        conn.execute(f"INSERT INTO sequences ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     [gone[c] for c in cols])


# ── the queue's items ───────────────────────────────────────────────────────

def accepted_sequences(conn):
    """Ids of the human sequences this queue has stored (accepted candidates), oldest first."""
    return [int(r[0]) for r in conn.execute(
        "SELECT id FROM sequences WHERE origin = 'human' AND source_kind = ? ORDER BY id", (REVIEW_SOURCE,))]


def resolve_items(conn, q):
    """The queue's items NOW: every sequence it was sent, with its span, its events as `members` /
    `member_spans` (what the Inspector draws inside the span), where it came from, and the verdict a person gave
    it (see the module docstring for what counts as judged)."""
    from Working.review.queues import _audit_judged_ids

    ids = [int(i) for i in (q["filters"].get("sequence_ids") or [])]
    if not ids:
        return []
    rows, events = {}, {}
    for k in range(0, len(ids), 400):
        chunk = ids[k:k + 400]
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(f"SELECT * FROM sequences WHERE id IN ({marks})", chunk):
            rows[int(r["id"])] = r
        for m in conn.execute(f"SELECT sequence_id, start_idx, end_idx FROM sequence_members "
                              f"WHERE sequence_id IN ({marks}) ORDER BY sequence_id, position", chunk):
            events.setdefault(int(m[0]), []).append([int(m[1]), int(m[2])])
    judged_here = {int(t) for t in _audit_judged_ids(conn, q["id"]) if str(t).lstrip("-").isdigit()}
    items = []
    for sid in ids:
        seq = rows.get(sid)
        if seq is None:
            continue                                    # a row that is gone takes no verdict
        aid = review_annotation_id(conn, sid)
        verdict = None
        if aid is not None:
            ann = conn.execute("SELECT verdict FROM annotations WHERE id = ? AND deleted_at IS NULL",
                               (aid,)).fetchone()
            verdict = ann[0] if ann is not None else None
        # NOT `prior_verdict`: that key means "the same event was judged elsewhere, do not ask" to
        # `queues.select_items`, and a hand-labelled sequence is asked again here on purpose
        if _hand_labelled(seq):
            judged, catalogue = sid in judged_here, verdict
            shown = verdict if judged else None
        else:
            judged, catalogue, shown = verdict is not None, None, verdict
        spans = events.get(sid, [])
        items.append({
            "target_id": sid, "unit": q["unit"], "sequence_id": sid, "sequence_key": seq["sequence_key"],
            "origin": seq["origin"], "provenance": seq["source_kind"],
            "recording_id": int(seq["recording_id"]), "channel": seq["channel"],
            "start_idx": int(seq["start_idx"]), "end_idx": int(seq["end_idx"]),
            "n_events": seq["n_events"], "members": list(range(1, len(spans) + 1)), "member_spans": spans,
            "judged": judged, "verdict": shown, "catalogue_verdict": catalogue, "tags": [],
        })
    return items

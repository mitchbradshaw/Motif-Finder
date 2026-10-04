"""
queries.py
==========
Plain functions for reading and writing the annotation database. No ORM,
no session objects — every function takes an open `sqlite3.Connection`
(from `schema.get_connection` / `schema.init_db`) and commits its own writes.

Callable from the UI, from Pipelines/ scripts, or from a plain shell —
nothing here imports a UI library.

Index convention
-----------------
Every `start_idx` / `end_idx` in this module is **channel-local**, never a
concatenated-file global index. Convert once, at import time, with
`global_to_local`.
"""

import datetime
import sqlite3

from Working.database.schema import VERDICTS  # noqa: F401  (re-exported)

SOURCE_IMPORTED_10MIN = "imported_10min"
SOURCE_MANUAL_UI = "manual_ui"

# The verdict subsets the divergence and queue semantics rest on. The PRD's
# verdict vocabulary maps `interesting` to accept and `not_interesting` to
# reject; `seed` marks exemplar-worthy and is a positive human verdict, so it
# also reads as accepted. `artifact` is retained as a first-class category, not
# as accept/reject. These are subsets of the shared `VERDICTS` constant, never
# a restatement of the five terms themselves.
ACCEPTED_VERDICTS = ("interesting", "seed")
REJECTED_VERDICTS = ("not_interesting",)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Index conversion ─────────────────────────────────────────────────────────

def global_to_local(global_start, channel_length):
    """Convert a concatenated-vector global start index to (channel, local).

    Parameters
    ----------
    global_start : int
        Start index into the full concatenated vector (all channels laid
        end-to-end, channel 0 first).
    channel_length : int
        L — the uniform per-channel sample count.

    Returns
    -------
    (channel, local_start) : (int, int)
    """
    channel, local_start = divmod(global_start, channel_length)
    return channel, local_start


def window_straddles_boundary(local_start, window_length, channel_length):
    """True if a window starting at `local_start` runs past the end of its
    channel (i.e. it would splice into the next channel's data)."""
    return local_start + window_length > channel_length


# ── recordings ────────────────────────────────────────────────────────────────

def insert_recording(conn, source_file, channel, fs, n_samples, global_offset,
                      npy_path, notes=None, commit=True, units=None, units_note=None):
    """Insert a recording row, or return the existing id if (source_file,
    channel) is already present (UNIQUE constraint) — idempotent.

    `commit=False` lets a caller doing many inserts in a loop (e.g. the
    channel materializer) batch them into one transaction instead of
    fsync-ing per row — commit yourself once the loop is done.

    `units` is the unit the samples are stored in (`Working.units`); None
    leaves it undeclared, which every page then says rather than assumes.
    """
    conn.execute(
        """INSERT OR IGNORE INTO recordings
               (source_file, channel, fs, n_samples, global_offset, npy_path, notes, units, units_note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (source_file, channel, fs, n_samples, global_offset, npy_path, notes, units, units_note),
    )
    if commit:
        conn.commit()
    return get_recording(conn, source_file, channel)["id"]


def get_recording(conn, source_file, channel):
    """Return the recording row for (source_file, channel), or None."""
    return conn.execute(
        "SELECT * FROM recordings WHERE source_file = ? AND channel = ?",
        (source_file, channel),
    ).fetchone()


def get_recording_by_id(conn, recording_id):
    return conn.execute(
        "SELECT * FROM recordings WHERE id = ?", (recording_id,)
    ).fetchone()


def list_recordings(conn, source_file=None):
    """List recordings, optionally filtered to one source file, ordered by
    channel."""
    if source_file is None:
        return conn.execute(
            "SELECT * FROM recordings ORDER BY source_file, channel"
        ).fetchall()
    return conn.execute(
        "SELECT * FROM recordings WHERE source_file = ? ORDER BY channel",
        (source_file,),
    ).fetchall()


# ── reviewed_spans ───────────────────────────────────────────────────────────

def reviewed_span_exists(conn, recording_id, start_idx, end_idx, source):
    row = conn.execute(
        """SELECT 1 FROM reviewed_spans
           WHERE recording_id = ? AND start_idx = ? AND end_idx = ? AND source = ?""",
        (recording_id, start_idx, end_idx, source),
    ).fetchone()
    return row is not None


def insert_reviewed_span(conn, recording_id, start_idx, end_idx, source,
                          scale_viewed=None, reviewed_at=None, commit=True):
    """Record a span as examined, independent of whether it was annotated.

    Callers that need idempotency (e.g. importers) should check
    `reviewed_span_exists` first — this function always inserts.

    `commit=False` lets a bulk caller batch many inserts into one transaction.
    """
    reviewed_at = reviewed_at or _now()
    cur = conn.execute(
        """INSERT INTO reviewed_spans
               (recording_id, start_idx, end_idx, scale_viewed, source, reviewed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (recording_id, start_idx, end_idx, scale_viewed, source, reviewed_at),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def list_reviewed_spans(conn, recording_id):
    return conn.execute(
        "SELECT * FROM reviewed_spans WHERE recording_id = ? ORDER BY start_idx",
        (recording_id,),
    ).fetchall()


def merge_intervals(spans):
    """Merge overlapping/touching (start, end) pairs into disjoint, sorted
    intervals. Shared by `reviewed_fraction` (below) and, headlessly, by
    `UI.plots.build_reviewed_ribbon`'s coverage ribbon — both must agree
    on what "reviewed" covers, so both compute it via this one function
    rather than two independently-written merge implementations that could
    quietly drift apart.
    """
    spans = sorted(spans)
    if not spans:
        return []
    merged = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def reviewed_fraction(conn, recording_id):
    """Fraction of a recording's samples covered by at least one reviewed
    span (overlaps merged, so double-reviewed regions aren't double-counted).

    Returns 0.0 for a recording with no reviewed spans.
    """
    rec = get_recording_by_id(conn, recording_id)
    if rec is None or rec["n_samples"] == 0:
        return 0.0
    spans = [(r["start_idx"], r["end_idx"]) for r in list_reviewed_spans(conn, recording_id)]
    if not spans:
        return 0.0
    covered = sum(e - s for s, e in merge_intervals(spans))
    return covered / rec["n_samples"]


# ── annotations ──────────────────────────────────────────────────────────────

def annotation_exists(conn, recording_id, start_idx, end_idx, source):
    row = conn.execute(
        """SELECT 1 FROM annotations
           WHERE recording_id = ? AND start_idx = ? AND end_idx = ? AND source = ?""",
        (recording_id, start_idx, end_idx, source),
    ).fetchone()
    return row is not None


def insert_annotation(conn, recording_id, start_idx, end_idx, verdict,
                       source, tag=None, note=None, scale_viewed=None,
                       created_at=None, event_count=None, status=None,
                       parent_annotation_id=None, relation_kind=None,
                       commit=True):
    """Insert one annotation. Always inserts — callers that need
    idempotency (e.g. importers) should check `annotation_exists` first.

    Parameters
    ----------
    verdict : str
        One of `VERDICTS` ('seed', 'interesting', 'not_interesting',
        'artifact', 'unsure').
    source : str
        e.g. `SOURCE_IMPORTED_10MIN` or `SOURCE_MANUAL_UI` — keeps imported
        and hand-made labels distinguishable.
    scale_viewed : str, optional
        The zoom span active when the call was made (e.g. "10min", "1hour").
    event_count : int, optional
        Number of discrete events in a spike train / cycle sequence, if
        known — drives the (computed, not stored) spike-train length band.
    status : str, optional
        One of the seeded `status` vocabulary values (candidate / examined /
        confirmed) — see `Working.database.vocabulary`.
    parent_annotation_id : int, optional
        Self-referencing FK — this annotation is a type-specimen or
        sub-window of another.
    relation_kind : str, optional
        'type_specimen' | 'sub_window' | None.
    commit : bool
        False lets a bulk caller batch many inserts into one transaction.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    created_at = created_at or _now()
    cur = conn.execute(
        """INSERT INTO annotations
               (recording_id, start_idx, end_idx, verdict, tag, note,
                scale_viewed, source, created_at, event_count, status,
                parent_annotation_id, relation_kind)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (recording_id, start_idx, end_idx, verdict, tag, note,
         scale_viewed, source, created_at, event_count, status,
         parent_annotation_id, relation_kind),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def get_annotation(conn, annotation_id):
    return conn.execute(
        "SELECT * FROM annotations WHERE id = ?", (annotation_id,)
    ).fetchone()


def list_annotations(conn, recording_id, include_deleted=False):
    """All annotations for a recording, ordered by start_idx. Excludes
    soft-deleted rows (`deleted_at IS NOT NULL`, see `delete_annotation`)
    unless `include_deleted=True` — the one place this filter is applied,
    so every caller (the table, the plot overlay, live counts, exports)
    automatically excludes deleted rows from all default views, per the
    brief, without each needing to remember to ask for it."""
    if include_deleted:
        return conn.execute(
            "SELECT * FROM annotations WHERE recording_id = ? ORDER BY start_idx",
            (recording_id,),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM annotations WHERE recording_id = ? AND deleted_at IS NULL ORDER BY start_idx",
        (recording_id,),
    ).fetchall()


def get_annotations_by_ids(conn, annotation_ids):
    """Bulk fetch, e.g. for rendering a selection highlight independent of
    whatever's currently filtered into view. Empty input -> empty output
    (skips the query — an empty `IN ()` is invalid SQL)."""
    ids = list(annotation_ids)
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    return conn.execute(
        f"SELECT * FROM annotations WHERE id IN ({placeholders})", ids,
    ).fetchall()


def update_annotation(conn, annotation_id, force=False, **fields):
    """Update an existing manual annotation's editable fields (verdict, tag,
    note, scale_viewed). Refuses to edit an imported annotation unless
    `force=True` — imported labels are protected from accidental edits.
    """
    row = get_annotation(conn, annotation_id)
    if row is None:
        raise ValueError(f"No annotation with id={annotation_id}")
    if row["source"] != SOURCE_MANUAL_UI and not force:
        raise PermissionError(
            f"Annotation {annotation_id} has source={row['source']!r}; "
            "only manual_ui annotations may be edited (pass force=True to override)."
        )
    allowed = {"verdict", "tag", "note", "scale_viewed", "event_count",
               "status", "parent_annotation_id", "relation_kind"}
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"Cannot update fields: {bad}")
    if "verdict" in fields and fields["verdict"] not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}, got {fields['verdict']!r}")
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE annotations SET {set_clause} WHERE id = ?",
        (*fields.values(), annotation_id),
    )
    conn.commit()


def delete_annotation(conn, annotation_id, force=False):
    """Soft-delete (Part E7): sets `deleted_at` rather than removing the
    row, so an accidental delete has an undo (`undelete_annotation`).
    Refuses to delete an imported annotation unless `force=True`. A
    no-op (not an error) if already deleted, matching the previous
    "delete a possibly-already-gone row" tolerance."""
    row = get_annotation(conn, annotation_id)
    if row is None or row["deleted_at"] is not None:
        return
    if row["source"] != SOURCE_MANUAL_UI and not force:
        raise PermissionError(
            f"Annotation {annotation_id} has source={row['source']!r}; "
            "only manual_ui annotations may be deleted (pass force=True to override)."
        )
    conn.execute("UPDATE annotations SET deleted_at = ? WHERE id = ?", (_now(), annotation_id))
    conn.commit()


def undelete_annotation(conn, annotation_id):
    """Part E7's undo — clears `deleted_at`. A no-op if the annotation
    isn't currently soft-deleted."""
    conn.execute(
        "UPDATE annotations SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
        (annotation_id,),
    )
    conn.commit()


def recording_summary(conn, recording_id):
    """Counts per verdict plus reviewed fraction for one recording.
    Excludes soft-deleted annotations, same as `list_annotations`.

    Returns
    -------
    dict : {"seed": int, "interesting": int, "not_interesting": int, "artifact": int,
            "unsure": int, "total": int, "reviewed_fraction": float}
    """
    counts = {v: 0 for v in VERDICTS}
    for row in conn.execute(
        "SELECT verdict, COUNT(*) AS n FROM annotations "
        "WHERE recording_id = ? AND deleted_at IS NULL GROUP BY verdict",
        (recording_id,),
    ):
        counts[row["verdict"]] = row["n"]
    counts["total"] = sum(counts.values())
    counts["reviewed_fraction"] = reviewed_fraction(conn, recording_id)
    return counts


# ── adjudication divergence queries ──────────────────────────────────────────
#
# The two divergence directions from the Review invariant, with equal standing
# over one read path. The PRD names a `v_spans` union view; that view was
# withdrawn (ticket 02) because an `origin` discriminator column violates
# standard 2.5, which is what lets a machine write land in a human store. These
# queries therefore read across both sources with a join at the call site — the
# same read, without the schema-level discriminator.

# ── a surrogate is never a detection ─────────────────────────────────────────

def not_surrogate(alias="r"):
    """The ONE statement of "this run is a real run, not a paired null", as a
    SQL predicate over a `runs` row aliased `alias`.

    A paired surrogate run is a real `runs` row (`surrogate_of_run_id` set), it
    joins its parent's run group, and the executor writes its spans to
    `detections` like any other run's — they are what the scoreboard's *null
    expects* counts. Every reader that means "what the machine found" must
    leave them out: Explore's coverage, spans and counts, Review's queues and
    *N need you*, the divergence queries, Library promotion, the run history.
    They all say so with this clause rather than each pasting its own
    (fixup-T; `tests/test_surrogate_never_a_detection.py` keeps it that way).

    The scoreboard and the seed page's null are the only readers that want a
    surrogate run's rows, and they reach them by `surrogate_of_run_id`.
    """
    return f"{alias}.surrogate_of_run_id IS NULL"


def is_surrogate_run(conn, run_id):
    """True when `run_id` is some run's paired null."""
    row = conn.execute("SELECT surrogate_of_run_id FROM runs WHERE id = ?", (int(run_id),)).fetchone()
    return bool(row is not None and row["surrogate_of_run_id"] is not None)


def _verdict_placeholders(verdicts):
    return ", ".join("?" * len(verdicts))


def _run_id_list(run_ids):
    return [int(i) for i in run_ids]


def divergence_rejected_detections(conn, recording_id=None, *, run_ids=None, verdicts=None):
    """Detections a human rejected — machine says yes, human says no.

    Reads the machine side joined to its adjudication verdict; the annotation
    store is deliberately not consulted (standard 2.5). Optionally scoped to a
    recording.

    ``run_ids`` restricts it to those runs' detections (an empty list is a
    question about no run, and answers nothing). ``verdicts`` is the set that
    counts as a rejection; it defaults to ``REJECTED_VERDICTS``, which the
    review queues share. The divergence module asks with ``artifact`` added —
    "human no" there is ``not_interesting`` or ``artifact`` (fixup-X).

    Returns
    -------
    list[sqlite3.Row] — detection rows (d.*) plus `adjudication_verdict`,
    `adjudication_note`, `recording_id` and `channel`.
    """
    query = """
        SELECT d.*, a.verdict AS adjudication_verdict,
               a.note AS adjudication_note,
               r.recording_id, rec.channel
        FROM detections d
        JOIN adjudications a ON a.detection_id = d.id
        JOIN runs r ON r.id = d.run_id
        JOIN recordings rec ON rec.id = r.recording_id
        WHERE a.verdict IN (__REJECTED__) AND __REAL__
    """
    rejected = tuple(verdicts) if verdicts is not None else REJECTED_VERDICTS
    query = query.replace("__REJECTED__", _verdict_placeholders(rejected) or "NULL").replace("__REAL__", not_surrogate("r"))
    params = list(rejected)
    if recording_id is not None:
        query += " AND r.recording_id = ?"
        params.append(recording_id)
    if run_ids is not None:
        ids = _run_id_list(run_ids)
        query += " AND d.run_id IN ({})".format(_verdict_placeholders(ids) or "NULL")
        params.extend(ids)
    query += " ORDER BY d.id"
    return conn.execute(query, params).fetchall()


def divergence_annotations_without_detection(conn, recording_id=None, *, run_ids=None, verdicts=None):
    """Annotations with no overlapping detection — human says yes, machine
    said nothing.

    Reads the human store and asks whether any machine detection (reached
    through its run's recording) overlaps the annotation's span. Soft-deleted
    annotations are excluded, same as `list_annotations`. Optionally scoped to
    a recording.

    Called bare, it is blind to two things, and the bare form is kept only
    for the callers that want exactly that: it counts an annotation whatever
    its verdict, and it counts one no run ever looked at. "The machine said
    nothing" is only true where a machine ran (fixup-X; Q41 — unlabelled is
    never "not interesting", and unlooked-at is never "missed"). So:

    ``run_ids``
        Ask about these runs only: their detections, and **only annotations
        wholly inside the span of one of them that completed**. A run that
        never reached a place cannot have been silent there. Surrogate runs in
        the list are ignored (`not_surrogate`). An empty list answers nothing.
    ``verdicts``
        Keep annotations with these verdicts — ``("interesting", "seed")``
        for "human says yes", ``("not_interesting", "artifact")`` for the
        agreeing silence.

    Returns
    -------
    list[sqlite3.Row] — annotation rows (a.*).
    """
    ids = _run_id_list(run_ids) if run_ids is not None else None
    in_runs = (" AND d.run_id IN ({})".format(_verdict_placeholders(ids) or "NULL")) if ids is not None else ""
    query = """
        SELECT a.*
        FROM annotations a
        WHERE a.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM detections d
              JOIN runs r ON r.id = d.run_id
              WHERE r.recording_id = a.recording_id AND __REAL__ __IN_RUNS__
                AND a.start_idx < d.end_idx AND d.start_idx < a.end_idx
          )
    """.replace("__REAL__", not_surrogate("r")).replace("__IN_RUNS__", in_runs)
    params = list(ids) if ids is not None else []
    if ids is not None:
        query += """
          AND EXISTS (
              SELECT 1 FROM runs c
              WHERE c.recording_id = a.recording_id AND c.status = 'completed' AND __REAL_C__
                AND c.id IN ({}) AND c.span_start <= a.start_idx AND a.end_idx <= c.span_end
          )""".replace("__REAL_C__", not_surrogate("c")).format(_verdict_placeholders(ids) or "NULL")
        params.extend(ids)
    if verdicts is not None:
        vs = tuple(verdicts)
        query += " AND a.verdict IN ({})".format(_verdict_placeholders(vs) or "NULL")
        params.extend(vs)
    if recording_id is not None:
        query += " AND a.recording_id = ?"
        params.append(recording_id)
    query += " ORDER BY a.id"
    return conn.execute(query, params).fetchall()


# ── candidate queue query ─────────────────────────────────────────────────────

def queue_candidates(conn, run_id=None, run_group_id=None, method=None,
                     score_min=None, score_max=None, channel=None,
                     adjudication_status=None, limit=50, offset=0, run_ids=None,
                     detection_ids=None):
    """Paginated candidate queue for adjudication.

    Filters compose: run, run set, run group, method (the recipe's detection
    algorithm), score range, channel, and adjudication status. Detections are
    ordered by id for stable paging.

    Parameters
    ----------
    run_ids : iterable of int, optional
        The exact set of runs the queue is over. A Discovery run is MADE OF a
        set of runs, and its run group also holds the paired surrogate runs
        and their detections, so a group filter alone would put
        phase-randomised noise in front of the researcher (fixup-L). An
        empty set is a queue over nothing, not over everything.
    detection_ids : iterable of int, optional
        An exact set of detections (fixup-Z): Discovery › Compare's *Send
        only-B unjudged to Review* is a queue over exactly the regions only one
        side found, one detection per region. Empty is a queue over nothing.
    adjudication_status : str, optional
        None (no filter), 'unadjudicated', 'adjudicated', 'accepted', or
        'rejected'.
    limit, offset : int
        Paging window over the ordered, filtered candidate list.

    Returns
    -------
    list[sqlite3.Row] — detection rows (d.*) plus `recording_id`, `channel`
    and `config_json`.
    """
    # A surrogate run's spans are never candidates — not through its run group
    # (which it shares with its parent), and not when asked for by run or by
    # detection id either: there is no verdict a human can give a
    # phase-randomised signal that means anything (fixup-T).
    clauses = [not_surrogate("r")]
    params = []

    if run_id is not None:
        clauses.append("d.run_id = ?")
        params.append(run_id)
    if run_ids is not None:
        ids = [int(i) for i in run_ids]
        if not ids:
            clauses.append("0")
        else:
            # A fan-out is a few dozen runs at most; SQLite's host-parameter
            # ceiling (999) is nowhere near.
            clauses.append("d.run_id IN ({})".format(",".join("?" * len(ids))))
            params.extend(ids)
    if detection_ids is not None:
        ids = [int(i) for i in detection_ids]
        if not ids:
            clauses.append("0")
        else:
            # past SQLite's 999 host parameters the ids (already coerced to
            # int above, so nothing else can reach the SQL) are inlined
            if len(ids) > 900:
                clauses.append("d.id IN ({})".format(",".join(str(i) for i in ids)))
            else:
                clauses.append("d.id IN ({})".format(",".join("?" * len(ids))))
                params.extend(ids)
    if run_group_id is not None:
        clauses.append("r.run_group_id = ?")
        params.append(run_group_id)
    if score_min is not None:
        clauses.append("d.score >= ?")
        params.append(score_min)
    if score_max is not None:
        clauses.append("d.score <= ?")
        params.append(score_max)
    if channel is not None:
        clauses.append("rec.channel = ?")
        params.append(channel)
    if method is not None:
        clauses.append(
            """EXISTS (
                SELECT 1 FROM json_each(c.config_json, '$.steps') AS s
                WHERE json_extract(s.value, '$.algorithm') = ?
            )"""
        )
        params.append(method)

    if adjudication_status is not None:
        status = adjudication_status
        if status == "unadjudicated":
            clauses.append(
                "NOT EXISTS (SELECT 1 FROM adjudications ad WHERE ad.detection_id = d.id)"
            )
        elif status == "adjudicated":
            clauses.append(
                "EXISTS (SELECT 1 FROM adjudications ad WHERE ad.detection_id = d.id)"
            )
        elif status == "accepted":
            clauses.append(
                """EXISTS (
                    SELECT 1 FROM adjudications ad
                    WHERE ad.detection_id = d.id
                      AND ad.verdict IN (__ACCEPTED__)
                )""".replace("__ACCEPTED__", _verdict_placeholders(ACCEPTED_VERDICTS))
            )
            params.extend(ACCEPTED_VERDICTS)
        elif status == "rejected":
            clauses.append(
                """EXISTS (
                    SELECT 1 FROM adjudications ad
                    WHERE ad.detection_id = d.id
                      AND ad.verdict IN (__REJECTED__)
                )""".replace("__REJECTED__", _verdict_placeholders(REJECTED_VERDICTS))
            )
            params.extend(REJECTED_VERDICTS)
        else:
            raise ValueError(
                "adjudication_status must be one of 'unadjudicated', 'adjudicated', "
                "'accepted', 'rejected', got {!r}".format(adjudication_status)
            )

    query = """
        SELECT d.*, r.recording_id, rec.channel, c.config_json
        FROM detections d
        JOIN runs r ON r.id = d.run_id
        JOIN recordings rec ON rec.id = r.recording_id
        JOIN configs c ON c.id = r.config_id
    """
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY d.id LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return conn.execute(query, params).fetchall()

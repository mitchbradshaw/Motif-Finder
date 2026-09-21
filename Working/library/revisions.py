"""
revisions.py
============
`docs/LIBRARY_STORAGE.md` §2.5 and spec §4.2 — a member's span, re-described.

    "A `motif_member` row is the identity of a motif. It carries a current
    span pointer and a revision list. Revisions are spans, not edits to a
    span."

So a human redrawing an extent does not mutate anything: it appends a revision,
moves `motif_member.current_revision_id` to it, and stamps `superseded_at` on
the revision it replaced. The detection stays exactly as its run produced it,
and the run still reproduces from its recipe.

**Rev 1 is what the matcher compares against; the current revision is what the
researcher sees.** That is the one sentence to keep: a re-run producing a span
that matches rev 1 resolves onto this same member (§4.2 rule 4) rather than
creating a second one, so `matching_revision` returns rev 1 and not the newest
row. A matcher pointed at the current revision would stop recognising its own
earlier detections the moment a person adjusted an extent.

`origin` decides which provenance pointer may be set — `machine` carries a
`detections` id, `human` carries an `annotations` id, never the other way
round. That is CLAUDE.md rule 5 at the level where it is easiest to break
quietly, so it is refused here by name rather than left to the CHECK
constraint, which only polices the vocabulary and not the pairing.

Editing an extent invalidates that member's `motif_edge` distances (§2.5, spec
§4.2 rule 5). This module does not recompute them — it is the span store, not
the distance engine — and it does not mark them either: `motif_edge` has no
staleness column and `add_revision` does not touch the edge table. What exists
is `stale_edges(conn, member_id)`, which **returns the edge ids an edit has
invalidated**; the caller asks for them and is then on the hook for them.
`add_revision` itself returns only the new revision's row id. Whoever writes
the extent-edit route owns that call — there is no mechanism here that will
make the obligation visible on its own.
"""

import datetime

MACHINE = "machine"
HUMAN = "human"
ORIGINS = (MACHINE, HUMAN)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _check_origin(origin, detection_id, annotation_id):
    """Refuse a revision whose provenance pointer contradicts its origin, or
    whose human claim has no provenance at all.

    Named error, naming the rule: `detections` is machine-only and
    `annotations` is human-only (CLAUDE.md rule 5), and a revision is precisely
    the row where a careless writer would put a human verdict on a machine span
    or the reverse.

    A **human** revision must carry its `annotation_id`. It is one person's
    claim about where a motif is, and a claim with nothing behind it puts a
    span on the member rail that nobody can account for. A **machine** revision
    may carry no `detection_id`: an event store is a catalogue of shapes and
    not a run, so the importer that wrote most of this library has no
    `detections` row to point at, and demanding one would mean inventing it.
    """
    if origin not in ORIGINS:
        raise ValueError(
            f"origin must be one of {ORIGINS}, got {origin!r}"
        )
    if origin == MACHINE and annotation_id is not None:
        raise ValueError(
            "A machine revision cannot carry an annotation_id: detections are "
            "machine-only and annotations are human-only (CLAUDE.md rule 5). "
            "A human extent edit is its own revision with origin='human'."
        )
    if origin == HUMAN and detection_id is not None:
        raise ValueError(
            "A human revision cannot carry a detection_id: annotations are "
            "human-only and detections are machine-only (CLAUDE.md rule 5). "
            "A human edit writes a new annotation and never mutates the "
            "detection — the run still reproduces from its recipe."
        )
    if origin == HUMAN and annotation_id is None:
        raise ValueError(
            "A human revision needs an annotation_id: a redrawn extent is a "
            "person's claim, and the annotation is the claim. Write the "
            "annotation first and point this revision at it (§2.5)."
        )


def add_revision(conn, member_id, *, origin, start_idx, end_idx,
                 detection_id=None, annotation_id=None, content_hash=None,
                 created_at=None, commit=True):
    """Append the next revision of a member's span and make it current.

    Three writes in one transaction, because a member whose pointer lags its
    revision list is a member showing the researcher the wrong span:

      1. insert the revision at `max(revision) + 1`;
      2. stamp `superseded_at` on the revision that was current;
      3. move `motif_member.current_revision_id`.

    Returns the new revision's row id — and nothing about edges: the edges an
    extent edit invalidates are `stale_edges(conn, member_id)`' answer, asked
    for by the caller, and nothing here marks them.

    Raises `ValueError` for an unknown member, an unknown origin, a provenance
    pointer that contradicts or is missing for the origin (see
    `_check_origin`), an empty or inverted span, or a span that does not
    overlap revision 1 — a redrawing is a redrawing *of this motif*.
    """
    _check_origin(origin, detection_id, annotation_id)

    member = conn.execute(
        "SELECT id, current_revision_id FROM motif_member WHERE id = ?",
        (int(member_id),),
    ).fetchone()
    if member is None:
        raise ValueError(f"No motif_member with id={member_id}")

    start_idx, end_idx = int(start_idx), int(end_idx)
    if end_idx <= start_idx:
        raise ValueError(
            f"Revision span [{start_idx}, {end_idx}) is empty or inverted; a "
            "revision is a span, so its end must exceed its start."
        )

    original = conn.execute(
        """SELECT start_idx, end_idx FROM motif_member_revision
           WHERE member_id = ? AND revision = 1""",
        (int(member_id),),
    ).fetchone()
    if original is not None and (end_idx <= original["start_idx"]
                                 or start_idx >= original["end_idx"]):
        raise ValueError(
            f"Revision span [{start_idx}, {end_idx}) does not overlap this "
            f"member's revision 1 [{original['start_idx']}, "
            f"{original['end_idx']}). A revision re-describes THIS motif's "
            "extent; a span somewhere else is a different motif and belongs "
            "to its own member."
        )

    created_at = created_at or _now()
    previous = conn.execute(
        """SELECT id, revision FROM motif_member_revision
           WHERE member_id = ? ORDER BY revision DESC LIMIT 1""",
        (int(member_id),),
    ).fetchone()
    next_revision = 1 if previous is None else int(previous["revision"]) + 1

    cur = conn.execute(
        """INSERT INTO motif_member_revision
               (member_id, revision, origin, detection_id, annotation_id,
                start_idx, end_idx, content_hash, created_at, superseded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
        (int(member_id), next_revision, origin, detection_id, annotation_id,
         start_idx, end_idx, content_hash, created_at),
    )
    revision_id = cur.lastrowid

    if previous is not None:
        conn.execute(
            "UPDATE motif_member_revision SET superseded_at = ? WHERE id = ?",
            (created_at, previous["id"]),
        )
    conn.execute(
        "UPDATE motif_member SET current_revision_id = ? WHERE id = ?",
        (revision_id, int(member_id)),
    )
    if commit:
        conn.commit()
    return revision_id


def current_revision(conn, member_id):
    """The revision the researcher sees: the one `current_revision_id` points
    at, falling back to the highest un-superseded revision for a member
    written before the pointer existed."""
    row = conn.execute(
        """SELECT r.* FROM motif_member m
           JOIN motif_member_revision r ON r.id = m.current_revision_id
           WHERE m.id = ?""",
        (int(member_id),),
    ).fetchone()
    if row is not None:
        return row
    return conn.execute(
        """SELECT * FROM motif_member_revision
           WHERE member_id = ? AND superseded_at IS NULL
           ORDER BY revision DESC LIMIT 1""",
        (int(member_id),),
    ).fetchone()


def revision_list(conn, member_id):
    """Every revision of one member, oldest first — the member rail's history
    (§8.6). Superseded rows stay; the list is the record of what was thought,
    not only of what is thought now."""
    return conn.execute(
        """SELECT * FROM motif_member_revision
           WHERE member_id = ? ORDER BY revision""",
        (int(member_id),),
    ).fetchall()


def matching_revision(conn, member_id):
    """**Rev 1** — the span a re-run's output is compared against (§4.2 rule 4).

    Deliberately not the current revision. A detector re-run under its own
    recipe reproduces the span it originally found, so matching against a
    human's later redrawing would fail to recognise the member and create a
    duplicate — which is the exact failure the revision list exists to prevent.
    """
    return conn.execute(
        "SELECT * FROM motif_member_revision WHERE member_id = ? AND revision = 1",
        (int(member_id),),
    ).fetchone()


def stale_edges(conn, member_id):
    """The `motif_edge` ids whose distance an extent edit has invalidated
    (§2.5, spec §4.2 rule 5).

    Reported rather than acted on: recomputing is a recipe-carrying act that
    belongs to whoever owns the distance, and the alternative the spec allows
    is marking the family partially stale. Either way the caller needs the
    list, and a silent "the numbers are still fine" is the one answer that is
    wrong.
    """
    rows = conn.execute(
        """SELECT id FROM motif_edge
           WHERE member_a_id = ? OR member_b_id = ?""",
        (int(member_id), int(member_id)),
    ).fetchall()
    return [row["id"] for row in rows]

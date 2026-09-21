"""
Working.review.window_verdicts — the verdict store for training/verification
windows (stage-3 wiring, fog A13).

Why this module exists at all
-----------------------------
A window is not a detection and it is not a span a person drew. It is one
index into a saved `window_sets` row: the extent was chosen by the windowing
recipe, not by a machine detector and not by a human dragging a selection.
So it has no `detections` row to adjudicate and no human-chosen extent to
annotate, and writing a window verdict into either of those tables would be
exactly the crossing CLAUDE.md rule 5 forbids — an invented detection, or an
invented human span. It gets its own table, `window_verdicts`, keyed by
`(window_set_id, window_index)`, and nothing in this module writes to
`detections`, `adjudications` or `annotations`.

The UNIQUE constraint on that key is the other design fact: a window carries
*the* verdict, not a history of verdicts. Changing your mind is an UPSERT of
the one row, not a second row — so `window_verdict_counts` can read progress
straight off the table without deduplicating first. Reversing a verdict is a
delete, and `delete_window_verdict` reports whether there was anything to
delete so undo can tell a reversal from a no-op.

Headless and UI-free: plain `sqlite3` over a connection the caller owns.
"""

import datetime

# The Review vocabulary (S/I/N/A/U). The table carries no CHECK constraint —
# the schema keeps the column free so the vocabulary can widen without a
# destructive rebuild — so the guard lives here.
VERDICTS = ("seed", "interesting", "not_interesting", "artifact", "unsure")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _rows(cur):
    """Rows as plain dicts, whatever `row_factory` the caller's connection has.

    The bridge may open its own `sqlite3.connect` without `sqlite3.Row`; the
    dict shape this module returns is ours to build, not the caller's to have
    configured.
    """
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _check(window_index, verdict):
    if verdict not in VERDICTS:
        raise ValueError(
            f"unknown verdict {verdict!r}; expected one of {VERDICTS}")
    if not isinstance(window_index, int) or isinstance(window_index, bool):
        raise ValueError(f"window_index must be an int, got {window_index!r}")
    if window_index < 0:
        raise ValueError(f"window_index must be >= 0, got {window_index}")


def write_window_verdict(conn, window_set_id, window_index, verdict, *,
                         note=None, queue_id=None):
    """Record (or replace) the verdict on one window of one window set.

    Re-verdicting the same window edits the existing row — the UNIQUE
    `(window_set_id, window_index)` key means a window has one current
    verdict, never a stack of them. The note and queue_id given here replace
    whatever was there, including with `None`: the row states the current
    verdict, and a note left over from a verdict that was overwritten would
    describe a judgement no longer recorded.

    Raises
    ------
    ValueError
        Unknown verdict, or a negative/non-integer window index.
    sqlite3.IntegrityError
        `window_set_id` names no row in `window_sets` (foreign keys are ON,
        so the orphan is refused rather than written).

    Returns
    -------
    int
        The `window_verdicts.id`, stable across a re-verdict.
    """
    _check(window_index, verdict)
    conn.execute(
        """
        INSERT INTO window_verdicts
            (window_set_id, window_index, verdict, note, queue_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (window_set_id, window_index) DO UPDATE SET
            verdict    = excluded.verdict,
            note       = excluded.note,
            queue_id   = excluded.queue_id,
            created_at = excluded.created_at
        """,
        (window_set_id, window_index, verdict, note, queue_id, _now()),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM window_verdicts "
        "WHERE window_set_id = ? AND window_index = ?",
        (window_set_id, window_index),
    ).fetchone()[0]


def get_window_verdict(conn, window_set_id, window_index):
    """The current verdict on one window, or None if it is unjudged."""
    rows = _rows(conn.execute(
        "SELECT id, window_set_id, window_index, verdict, note, queue_id, "
        "       created_at "
        "FROM window_verdicts WHERE window_set_id = ? AND window_index = ?",
        (window_set_id, window_index),
    ))
    return rows[0] if rows else None


def delete_window_verdict(conn, window_set_id, window_index):
    """Remove the verdict on one window.

    Returns
    -------
    bool
        True if a row was removed, False if the window was already unjudged.
        Undo depends on the difference: reversing a write and reversing
        nothing are different acts.
    """
    cur = conn.execute(
        "DELETE FROM window_verdicts "
        "WHERE window_set_id = ? AND window_index = ?",
        (window_set_id, window_index),
    )
    conn.commit()
    return cur.rowcount > 0


def window_verdict_counts(conn, window_set_id):
    """Progress over one window set: `{'judged': int, 'by_verdict': {...}}`.

    `by_verdict` omits verdicts with no rows rather than carrying zeros, so
    the readout describes what was actually judged.
    """
    rows = _rows(conn.execute(
        "SELECT verdict, COUNT(*) AS n FROM window_verdicts "
        "WHERE window_set_id = ? GROUP BY verdict",
        (window_set_id,),
    ))
    by_verdict = {r["verdict"]: r["n"] for r in rows}
    return {"judged": sum(by_verdict.values()), "by_verdict": by_verdict}

"""
test_review_promotion.py
========================
Spec P21 — an `S` (seed) verdict in Review **promotes** the thing judged into
the motif Library, and Ctrl-Z takes both halves back.

What is guarded here:

* the promotion walks the **importer's** identity path (`identity.hash_span` ->
  `dedupe.classify` -> `runs.insert_motif_entry` / `get_or_create_motif_member`
  -> `revisions.add_revision`). A second identity rule would be a second answer
  to "is this the same shape", which is the one question the Library may only
  answer once;
* **determinism**: promoting the same target twice leaves one entry, one
  member and one revision — the second call is a no-op that still reports the
  ids;
* the same shape at another place is the **same entry, a new member** (§2.1);
* **rule 5**: a detection promotes as a `machine` revision carrying its
  `detection_id`; an annotation promotes as a `human` revision carrying its
  `annotation_id`. Neither ever carries the other's pointer;
* `unpromote` reverses **both** halves — library rows and the verdict — and
  marks the audit row undone.

Headless: one temp database plus two small `.npy` channels on disk (bulk
arrays never enter the database, CLAUDE.md rule 4).
"""

import json
import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q
from Working.database import runs as R
from Working.database.schema import init_db
from Working.review import promotion


# ── fixtures ─────────────────────────────────────────────────────────────────

def _channel_file(tmp_path, name, values):
    path = tmp_path / name
    np.save(str(path), np.asarray(values, dtype=float))
    return str(path) + ("" if str(path).endswith(".npy") else ".npy")


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "promotion.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _wave(n=400, phase=0.0):
    t = np.linspace(0.0, 8.0, n)
    return np.sin(t + phase) + 0.1 * np.cos(3.0 * t)


def _recording(conn, tmp_path, channel, values, source_file="M_promo.mat"):
    npy = _channel_file(tmp_path, f"{source_file}_ch{channel}.npy", values)
    return q.insert_recording(
        conn, source_file, channel, fs=1.0, n_samples=len(values),
        global_offset=0, npy_path=npy,
    )


def _queue(conn, *, source_kind="discovery-run", unit="detection",
           writes_to="adjudications", name="q"):
    cur = conn.execute(
        """INSERT INTO review_queues
               (name, source_kind, source_ref, unit, writes_to, blind,
                created_at)
           VALUES (?, ?, NULL, ?, ?, 0, '2026-09-22T00:00:00+00:00')""",
        (name, source_kind, unit, writes_to),
    )
    conn.commit()
    return cur.lastrowid


def _detection(conn, recording_id, start_idx, end_idx):
    config_id, _ = R.get_or_create_config(conn, {"blocks": [], "name": "promo"})
    run_id = R.insert_run(conn, config_id, recording_id, 0, 10_000)
    return R.insert_detection(conn, run_id, start_idx, end_idx, score=1.0)


def _counts(conn):
    def one(sql):
        return conn.execute(sql).fetchone()[0]
    return (one("SELECT COUNT(*) FROM motif_entry"),
            one("SELECT COUNT(*) FROM motif_member"),
            one("SELECT COUNT(*) FROM motif_member_revision"))


# ── the promotion itself ─────────────────────────────────────────────────────

def test_promote_creates_entry_member_and_revision_one(conn, tmp_path):
    rec = _recording(conn, tmp_path, 0, _wave(2_000))
    qid = _queue(conn)
    det = _detection(conn, rec, 100, 356)

    out = promotion.promote(conn, qid, det)

    assert out["created"] is True
    assert isinstance(out["entry_id"], int) and isinstance(out["member_id"], int)
    assert _counts(conn) == (1, 1, 1)

    entry = conn.execute("SELECT * FROM motif_entry WHERE id = ?",
                         (out["entry_id"],)).fetchone()
    assert entry["content_hash"], "the exemplar keeps its content hash (P21)"
    assert entry["start_idx"] == 100 and entry["end_idx"] == 356

    rev = conn.execute(
        "SELECT * FROM motif_member_revision WHERE member_id = ?",
        (out["member_id"],)).fetchone()
    assert rev["revision"] == 1
    # Rule 5, at the level where it is easiest to break quietly.
    assert rev["origin"] == "machine"
    assert rev["detection_id"] == det
    assert rev["annotation_id"] is None


def test_promote_writes_one_audit_row_carrying_both_halves(conn, tmp_path):
    rec = _recording(conn, tmp_path, 0, _wave(2_000))
    qid = _queue(conn)
    det = _detection(conn, rec, 100, 356)

    out = promotion.promote(conn, qid, det)

    rows = conn.execute(
        "SELECT * FROM review_audit WHERE action = 'promote'").fetchall()
    assert len(rows) == 1
    audit = rows[0]
    assert audit["id"] == out["audit_id"]
    assert audit["queue_id"] == qid
    payload = json.loads(audit["payload_json"])
    assert payload["entry_id"] == out["entry_id"]
    assert payload["member_id"] == out["member_id"]
    assert payload["target_id"] == det
    assert "verdict" in payload


def test_promoting_the_same_target_twice_is_one_entry(conn, tmp_path):
    """Determinism: the second promote writes no second shape and no second
    occurrence — it reports the ids the first one made."""
    rec = _recording(conn, tmp_path, 0, _wave(2_000))
    qid = _queue(conn)
    det = _detection(conn, rec, 100, 356)

    first = promotion.promote(conn, qid, det)
    second = promotion.promote(conn, qid, det)

    assert second["entry_id"] == first["entry_id"]
    assert second["member_id"] == first["member_id"]
    assert second["created"] is False
    assert _counts(conn) == (1, 1, 1)


def test_the_same_shape_elsewhere_is_a_new_member_of_the_same_entry(conn, tmp_path):
    """§2.1: same hash -> same entry; same hash AND same place -> same member.
    A recurrence on another channel is the Library's whole point."""
    values = _wave(2_000)
    rec0 = _recording(conn, tmp_path, 0, values)
    rec1 = _recording(conn, tmp_path, 1, values)
    qid = _queue(conn)

    first = promotion.promote(conn, qid, _detection(conn, rec0, 100, 356))
    second = promotion.promote(conn, qid, _detection(conn, rec1, 100, 356))

    assert second["entry_id"] == first["entry_id"]
    assert second["member_id"] != first["member_id"]
    entries, members, revs = _counts(conn)
    assert (entries, members, revs) == (1, 2, 2)


def test_a_human_span_promotes_as_a_human_revision(conn, tmp_path):
    rec = _recording(conn, tmp_path, 0, _wave(2_000))
    qid = _queue(conn, source_kind="explore-spans", unit="human span",
                 writes_to="annotations")
    ann = q.insert_annotation(conn, rec, 500, 756, "interesting", "explore")

    out = promotion.promote(conn, qid, ann)

    rev = conn.execute(
        "SELECT * FROM motif_member_revision WHERE member_id = ?",
        (out["member_id"],)).fetchone()
    assert rev["origin"] == "human"
    assert rev["annotation_id"] == ann
    assert rev["detection_id"] is None


# ── Ctrl-Z ───────────────────────────────────────────────────────────────────

def test_unpromote_removes_the_library_rows_and_the_verdict(conn, tmp_path):
    rec = _recording(conn, tmp_path, 0, _wave(2_000))
    qid = _queue(conn)
    det = _detection(conn, rec, 100, 356)

    out = promotion.promote(conn, qid, det)
    before = conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0]
    assert before == 1, "the verdict half is written first (P21)"

    promotion.unpromote(conn, out["audit_id"])

    assert _counts(conn) == (0, 0, 0)
    assert conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == 0
    audit = conn.execute("SELECT * FROM review_audit WHERE id = ?",
                         (out["audit_id"],)).fetchone()
    assert audit["undone_at"], "an undone promote says so on its audit row"


def test_unpromote_keeps_an_entry_another_member_still_needs(conn, tmp_path):
    """Reversing one promotion must not delete a shape someone else's
    occurrence is still hanging off."""
    values = _wave(2_000)
    rec0 = _recording(conn, tmp_path, 0, values)
    rec1 = _recording(conn, tmp_path, 1, values)
    qid = _queue(conn)

    first = promotion.promote(conn, qid, _detection(conn, rec0, 100, 356))
    second = promotion.promote(conn, qid, _detection(conn, rec1, 100, 356))

    promotion.unpromote(conn, second["audit_id"])

    entries, members, revs = _counts(conn)
    assert (entries, members, revs) == (1, 1, 1)
    assert conn.execute("SELECT id FROM motif_entry").fetchone()["id"] \
        == first["entry_id"]


def test_unpromote_is_refused_twice(conn, tmp_path):
    rec = _recording(conn, tmp_path, 0, _wave(2_000))
    qid = _queue(conn)
    out = promotion.promote(conn, qid, _detection(conn, rec, 100, 356))

    promotion.unpromote(conn, out["audit_id"])
    with pytest.raises(ValueError):
        promotion.unpromote(conn, out["audit_id"])

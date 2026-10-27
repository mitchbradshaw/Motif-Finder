"""
test_promotion_library_only.py
==============================
The verdict-free promote (researcher, 2026-10-26, Q5 A): a detection a person
has ALREADY accepted in Review becomes a Library entry without a second verdict.

`promotion.promote` writes a verdict first (new `adjudications` rows with
`carried_from` NULL, i.e. new "own looks", carried to other runs). The
Library-only half must not: it hashes the span, asks `dedupe.classify`, writes
the entry, member and revision 1 (machine, with `detection_id`) and one
`audit_log` row that `unpromote_to_library` reverses. Twins and spans already
held are skipped; the held-out recording is refused by name.
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

HELD_OUT = "M4_aug_concat_fs1.mat"


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "promo_lib.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _wave(n=2_000, phase=0.0):
    t = np.linspace(0.0, 40.0, n)
    return np.sin(t + phase) + 0.1 * np.cos(3.7 * t) + 0.01 * t


def _recording(conn, tmp_path, values, source_file="M_lib.mat", channel=0):
    path = tmp_path / f"{source_file}_ch{channel}.npy"
    np.save(str(path), np.asarray(values, dtype=float))
    return q.insert_recording(conn, source_file, channel, fs=1.0, n_samples=len(values),
                              global_offset=0, npy_path=str(path))


def _detection(conn, recording_id, start_idx, end_idx):
    config_id, _ = R.get_or_create_config(conn, {"blocks": [], "name": "lib"})
    run_id = R.insert_run(conn, config_id, recording_id, 0, 10_000)
    return R.insert_detection(conn, run_id, start_idx, end_idx, score=1.0)


def _accept(conn, det):
    """The researcher's own look, already in the database before the promotion."""
    conn.execute("INSERT INTO adjudications (detection_id, verdict, note, created_at, carried_from) "
                 "VALUES (?, 'interesting', NULL, '2026-10-20T00:00:00', NULL)", (det,))
    conn.commit()


def _n(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_promote_writes_entry_and_revision_and_no_verdict(conn, tmp_path):
    rec = _recording(conn, tmp_path, _wave())
    det = _detection(conn, rec, 100, 356)
    _accept(conn, det)
    adj_before = [tuple(r) for r in conn.execute("SELECT * FROM adjudications ORDER BY id")]
    ann_before = _n(conn, "annotations")

    out = promotion.promote_to_library(conn, det, actor="test", note="blind queue 25")

    assert out["status"] == "promoted"
    assert [tuple(r) for r in conn.execute("SELECT * FROM adjudications ORDER BY id")] == adj_before
    assert _n(conn, "annotations") == ann_before
    entry = conn.execute("SELECT * FROM motif_entry WHERE id = ?", (out["entry_id"],)).fetchone()
    assert entry["detection_id"] == det
    assert entry["content_hash"]
    assert (entry["start_idx"], entry["end_idx"]) == (100, 356)
    rev = conn.execute("SELECT * FROM motif_member_revision WHERE member_id = ?",
                       (out["member_id"],)).fetchone()
    assert rev["revision"] == 1 and rev["origin"] == "machine"
    assert rev["detection_id"] == det and rev["annotation_id"] is None
    # the verdict-free path never writes a review_audit row (Review's Ctrl-Z must not find it)
    assert _n(conn, "review_audit") == 0


def test_audit_row_and_undo(conn, tmp_path):
    rec = _recording(conn, tmp_path, _wave())
    det = _detection(conn, rec, 100, 356)
    _accept(conn, det)
    out = promotion.promote_to_library(conn, det, actor="test")

    row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (out["audit_id"],)).fetchone()
    assert row["kind"] == promotion.LIBRARY_PROMOTE_KIND
    detail = json.loads(row["detail_json"])
    assert detail["entry_id"] == out["entry_id"] and detail["detection_id"] == det

    undone = promotion.unpromote_to_library(conn, out["audit_id"])
    assert undone["entry_removed"] is True
    assert _n(conn, "motif_entry") == 0
    assert _n(conn, "motif_member") == 0
    assert _n(conn, "motif_member_revision") == 0
    assert _n(conn, "adjudications") == 1  # the researcher's verdict is untouched
    with pytest.raises(ValueError):
        promotion.unpromote_to_library(conn, out["audit_id"])


def test_twin_and_held_span_are_skipped(conn, tmp_path):
    rec = _recording(conn, tmp_path, _wave())
    first = _detection(conn, rec, 100, 356)
    twin = _detection(conn, rec, 104, 358)       # same event detected again: a near-duplicate
    same = _detection(conn, rec, 100, 356)       # the identical span from another run: exact
    for d in (first, twin, same):
        _accept(conn, d)

    assert promotion.promote_to_library(conn, first, actor="t")["status"] == "promoted"
    counts = (_n(conn, "motif_entry"), _n(conn, "motif_member"), _n(conn, "audit_log"))
    near = promotion.promote_to_library(conn, twin, actor="t")
    exact = promotion.promote_to_library(conn, same, actor="t")
    assert near["status"] == "skipped" and near["dedupe"] == "near"
    assert exact["status"] == "skipped" and exact["dedupe"] == "exact"
    assert (_n(conn, "motif_entry"), _n(conn, "motif_member"), _n(conn, "audit_log")) == counts


def test_held_out_recording_is_refused(conn, tmp_path):
    rec = _recording(conn, tmp_path, _wave(), source_file=HELD_OUT)
    det = _detection(conn, rec, 100, 356)
    with pytest.raises(ValueError, match="held-out"):
        promotion.promote_to_library(conn, det, actor="t")
    assert _n(conn, "motif_entry") == 0 and _n(conn, "audit_log") == 0

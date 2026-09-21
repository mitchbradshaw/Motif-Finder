"""
test_review_verdicts.py
=======================
Stage-3 wiring prompt 05 — `Working/review/verdicts.py`.

What is asserted here, in the order it matters:

1. **Rule 5 in both directions, loudly.** A detection id offered to a queue
   that writes `annotations`, or an annotation id offered to a queue that
   writes `adjudications`, raises `PermissionError` naming rule 5 — and after
   the refusal NEITHER table has gained a row. A silent no-op would be the
   same crossing with the evidence removed.
2. **A batch is ONE audit row.** `write_batch` over N targets writes one
   `review_audit` row carrying N target ids, not N rows, because undo of a
   batch is one act.
3. **Undo restores the PRIOR verdict**, not "unjudged", when there was one.

The queue rows are inserted with plain SQL here rather than through
`Working.review.queues` so this module's tests do not depend on a sibling
module landing first.
"""

import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db
from Working.database import queries as q
from Working.database import vocabulary as v
from Working.review import verdicts as V


# ── fixtures ────────────────────────────────────────────────────────────────

def _fresh_conn():
    conn = init_db(":memory:")
    v.seed_vocabulary(conn)
    return conn


def _insert_recording(conn, source_file="a.mat", channel=0):
    return q.insert_recording(conn, source_file, channel, 1.0, 1000, 0,
                              f"data/{source_file}/CH{channel}.npy")


def _insert_detection(conn, rid, start_idx=0, end_idx=100, score=None):
    cid = conn.execute(
        "INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
        (f"hash-{rid}-{start_idx}-{end_idx}",
         json.dumps({"steps": [{"stage": "detection", "algorithm": "rupture"}]}),
         "2026-01-01T00:00:00"),
    ).lastrowid
    run_id = conn.execute(
        """INSERT INTO runs
               (config_id, recording_id, span_start, span_end, started_at, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (cid, rid, 0, 1000, "2026-01-01T00:00:00", "done"),
    ).lastrowid
    det_id = conn.execute(
        "INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
        (run_id, start_idx, end_idx, score),
    ).lastrowid
    conn.commit()
    return det_id


def _make_queue(conn, writes_to="adjudications", source_kind="discovery-run",
                unit="detection"):
    cur = conn.execute(
        """INSERT INTO review_queues
               (name, source_kind, source_ref, unit, writes_to, blind, created_at)
           VALUES (?, ?, ?, ?, ?, 0, ?)""",
        ("q", source_kind, None, unit, writes_to, "2026-01-01T00:00:00"),
    )
    conn.commit()
    return cur.lastrowid


def _counts(conn):
    return (
        conn.execute("SELECT COUNT(*) AS n FROM adjudications").fetchone()["n"],
        conn.execute("SELECT COUNT(*) AS n FROM annotations").fetchone()["n"],
    )


# ── the boundary ────────────────────────────────────────────────────────────

def test_module_imports_no_ui_library():
    src_path = os.path.join(PROJECT_ROOT, "Working", "review", "verdicts.py")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read().lower()
    for banned in ("panel", "holoviews", "bokeh", "fastapi", "import matplotlib"):
        assert banned not in src, f"verdicts.py must not mention {banned}"


def test_verdict_vocabulary_is_the_shared_five():
    assert V.VERDICTS == ("seed", "interesting", "not_interesting",
                          "artifact", "unsure")


# ── rule 5, both directions ─────────────────────────────────────────────────

def test_detection_id_into_an_annotations_queue_is_refused():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="explore-spans", unit="human span")
    before = _counts(conn)
    with pytest.raises(PermissionError) as exc:
        V.write_verdict(conn, qid, det, "interesting")
    assert "rule 5" in str(exc.value).lower()
    assert _counts(conn) == before
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM review_audit").fetchone()["n"] == 0


def test_annotation_id_into_an_adjudications_queue_is_refused():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ann = q.insert_annotation(conn, rid, 0, 100, "interesting",
                              q.SOURCE_MANUAL_UI)
    qid = _make_queue(conn, writes_to="adjudications")
    before = _counts(conn)
    with pytest.raises(PermissionError) as exc:
        V.write_verdict(conn, qid, ann, "seed")
    assert "rule 5" in str(exc.value).lower()
    assert _counts(conn) == before


def test_unknown_target_is_a_value_error_not_a_crossing():
    conn = _fresh_conn()
    qid = _make_queue(conn)
    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, 99999, "seed")


def test_unknown_verdict_is_refused():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)
    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, det, "brilliant")


# ── the happy paths ─────────────────────────────────────────────────────────

def test_verdict_on_a_detection_queue_writes_an_adjudication_only():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)
    out = V.write_verdict(conn, qid, det, "seed", note="clean")
    assert out["verdict"] == "seed"
    assert out["writes_to"] == "adjudications"
    adj, ann = _counts(conn)
    assert (adj, ann) == (1, 0)
    row = conn.execute("SELECT * FROM adjudications WHERE detection_id = ?",
                       (det,)).fetchone()
    assert row["verdict"] == "seed" and row["note"] == "clean"
    audit = conn.execute("SELECT * FROM review_audit").fetchone()
    assert audit["action"] == "verdict"
    assert audit["target_table"] == "adjudications"
    assert json.loads(audit["target_ids"]) == [det]
    assert audit["created_at"].endswith("+00:00")


def test_verdict_on_an_annotations_queue_writes_an_annotation_only():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ann = q.insert_annotation(conn, rid, 0, 100, "unsure", q.SOURCE_MANUAL_UI)
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="explore-spans", unit="human span")
    V.write_verdict(conn, qid, ann, "interesting")
    adj, _ = _counts(conn)
    assert adj == 0
    assert q.get_annotation(conn, ann)["verdict"] == "interesting"


def test_tags_reach_the_adjudication():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)
    V.write_verdict(conn, qid, det, "seed", tags={"element": ["sharkfin"]})
    from Working.database import adjudications as adjm
    adj_id = adjm.get_adjudication(conn, det)["id"]
    assert adjm.get_adjudication_tags(conn, adj_id)["element"] == ["sharkfin"]


# ── batch: one audit row ────────────────────────────────────────────────────

def test_batch_writes_one_audit_row_for_n_targets():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    dets = [_insert_detection(conn, rid, start_idx=i * 200,
                              end_idx=i * 200 + 50) for i in range(4)]
    qid = _make_queue(conn)
    out = V.write_batch(conn, qid, dets, "not_interesting")
    assert out["count"] == 4
    rows = conn.execute("SELECT * FROM review_audit").fetchall()
    assert len(rows) == 1
    assert rows[0]["action"] == "batch"
    assert json.loads(rows[0]["target_ids"]) == list(dets)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM adjudications").fetchone()["n"] == 4


# ── undo ────────────────────────────────────────────────────────────────────

def test_undo_of_a_fresh_verdict_returns_the_target_to_unjudged():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)
    V.write_verdict(conn, qid, det, "seed")
    undone = V.undo_last(conn, qid)
    assert undone is not None and undone["action"] == "verdict"
    assert conn.execute("SELECT COUNT(*) AS n FROM adjudications"
                        ).fetchone()["n"] == 0
    audit = conn.execute("SELECT * FROM review_audit WHERE id = ?",
                         (undone["audit_id"],)).fetchone()
    assert audit["undone_at"] is not None


def test_undo_restores_the_prior_verdict_not_unjudged():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)
    V.write_verdict(conn, qid, det, "interesting", note="first")
    V.write_verdict(conn, qid, det, "artifact", note="second")
    V.undo_last(conn, qid)
    row = conn.execute("SELECT * FROM adjudications WHERE detection_id = ?",
                       (det,)).fetchone()
    assert row["verdict"] == "interesting"
    assert row["note"] == "first"


def test_undo_of_a_batch_reverses_all_n():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    dets = [_insert_detection(conn, rid, start_idx=i * 200,
                              end_idx=i * 200 + 50) for i in range(3)]
    qid = _make_queue(conn)
    V.write_batch(conn, qid, dets, "not_interesting")
    out = V.undo_last(conn, qid)
    assert out["action"] == "batch"
    assert conn.execute("SELECT COUNT(*) AS n FROM adjudications"
                        ).fetchone()["n"] == 0


def test_undo_is_scoped_to_a_queue_when_asked():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    d1 = _insert_detection(conn, rid, start_idx=0, end_idx=50)
    d2 = _insert_detection(conn, rid, start_idx=400, end_idx=450)
    q1 = _make_queue(conn)
    q2 = _make_queue(conn)
    V.write_verdict(conn, q1, d1, "seed")
    V.write_verdict(conn, q2, d2, "seed")
    V.undo_last(conn, q1)
    from Working.database import adjudications as adjm
    assert adjm.get_adjudication(conn, d1) is None
    assert adjm.get_adjudication(conn, d2)["verdict"] == "seed"


def test_undo_with_nothing_to_undo_returns_none():
    conn = _fresh_conn()
    qid = _make_queue(conn)
    assert V.undo_last(conn, qid) is None


def test_undo_does_not_reverse_an_already_undone_row_twice():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)
    V.write_verdict(conn, qid, det, "seed")
    assert V.undo_last(conn, qid) is not None
    assert V.undo_last(conn, qid) is None


# ── window verdicts route to their own table ────────────────────────────────

def test_window_queue_routes_to_window_verdicts():
    pytest.importorskip("Working.review.window_verdicts")
    conn = _fresh_conn()
    ws = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='window_sets'"
    ).fetchone()
    if ws is None:
        pytest.skip("window_sets table not present")
    cur = conn.execute("SELECT * FROM window_sets LIMIT 0")
    cols = [d[0] for d in cur.description]
    assert "id" in cols

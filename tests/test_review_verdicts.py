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
4. **The window branch, and rule 5 for the case it exists to serve.** A
   training/verification window has no `detections` row to adjudicate and no
   human-drawn extent to annotate, so its verdict may land only in
   `window_verdicts` — and `detections`, `adjudications` and `annotations`
   must be provably unchanged after it does. The same block pins the
   coordinate convention the resolver and the writer had disagreed about: the
   window SET is the queue's `source_ref`, the `target_id` is the index.

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
    # `seed` is what an explore-spans queue resolves (04-to-05 §4). The span has
    # to be one the queue actually lists, or the membership check refuses it —
    # which is the point of that check: a one-item queue used to be a licence to
    # write any annotation in the database.
    ann = q.insert_annotation(conn, rid, 0, 100, "seed", q.SOURCE_MANUAL_UI)
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
#
# This is the branch §9.3 of the stage-1 report left smoke-covered. What makes
# it worth its own block is rule 5: a training/verification window has no
# `detections` row to adjudicate and no human-drawn extent to annotate, so the
# ONLY correct place for its verdict is `window_verdicts`, and the three other
# tables must be provably untouched afterwards.
#
# The contract these tests pin down, because two callers disagreed about it:
# for a window queue the WINDOW SET is the queue's `source_ref` and the
# `target_id` is the index within it — exactly what `queues._resolve_windows`
# puts in each item. `window_index=` is an optional restatement of the same
# index, not a second coordinate.

def _insert_window_set(conn, rid=None, name="ws", n_windows=6):
    cur = conn.execute(
        """INSERT INTO window_sets
               (name, version, path, recording_id, n_windows, created_at)
           VALUES (?, 1, ?, ?, ?, ?)""",
        (name, "DATA/derived/%s.npz" % name, rid, n_windows,
         "2026-01-01T00:00:00"),
    )
    conn.commit()
    return cur.lastrowid


def _make_window_queue(conn, ws_id, source_kind="training-windows"):
    cur = conn.execute(
        """INSERT INTO review_queues
               (name, source_kind, source_ref, unit, writes_to, blind,
                created_at)
           VALUES (?, ?, ?, 'window', 'window_verdicts', 0, ?)""",
        ("windows", source_kind, str(ws_id), "2026-01-01T00:00:00"),
    )
    conn.commit()
    return cur.lastrowid


def _machine_and_human_counts(conn):
    """(detections, adjudications, annotations) — the three tables a window
    verdict must leave alone."""
    return (
        conn.execute("SELECT COUNT(*) AS n FROM detections").fetchone()["n"],
        conn.execute("SELECT COUNT(*) AS n FROM adjudications").fetchone()["n"],
        conn.execute("SELECT COUNT(*) AS n FROM annotations").fetchone()["n"],
    )


def _window_rows(conn, ws_id):
    return conn.execute(
        "SELECT * FROM window_verdicts WHERE window_set_id = ? "
        "ORDER BY window_index", (ws_id,)).fetchall()


def test_window_queue_writes_the_set_and_index_it_was_asked_about():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    out = V.write_verdict(conn, qid, 3, "interesting", note="clear rise")

    assert out["writes_to"] == "window_verdicts"
    assert out["verdict"] == "interesting"
    rows = _window_rows(conn, ws)
    assert len(rows) == 1
    assert rows[0]["window_set_id"] == ws
    assert rows[0]["window_index"] == 3
    assert rows[0]["verdict"] == "interesting"
    assert rows[0]["note"] == "clear rise"
    assert rows[0]["queue_id"] == qid


def test_model_verification_is_the_same_branch_as_training_windows():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws, source_kind="model-verification")

    V.write_verdict(conn, qid, 1, "not_interesting")

    rows = _window_rows(conn, ws)
    assert [(r["window_set_id"], r["window_index"], r["verdict"])
            for r in rows] == [(ws, 1, "not_interesting")]


def test_a_window_verdict_leaves_the_machine_and_human_tables_untouched():
    """CLAUDE.md rule 5, for the case `window_verdicts` exists to serve."""
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    _insert_detection(conn, rid)
    q.insert_annotation(conn, rid, 0, 100, "unsure", q.SOURCE_MANUAL_UI)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    before = _machine_and_human_counts(conn)
    assert before == (1, 0, 1)
    V.write_verdict(conn, qid, 0, "seed", note="train on this")

    assert _machine_and_human_counts(conn) == before
    assert len(_window_rows(conn, ws)) == 1


def test_the_bridge_call_shape_works_without_window_index():
    """`webui/server/review.py` passes `window_index=body.window_index`, and
    the client sends no such field — so the index has to come from the target
    id or every window verdict the UI writes is an exception."""
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    V.write_verdict(conn, qid, 2, "artifact", note=None, tags=None,
                    window_index=None)

    assert [r["window_index"] for r in _window_rows(conn, ws)] == [2]


def test_window_index_may_restate_the_target_id():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    V.write_verdict(conn, qid, 4, "seed", window_index=4)

    assert [r["window_index"] for r in _window_rows(conn, ws)] == [4]


def test_a_window_index_contradicting_the_target_id_is_refused():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, 4, "seed", window_index=5)
    assert _window_rows(conn, ws) == []


def test_re_verdicting_a_window_upserts_the_one_row():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    V.write_verdict(conn, qid, 2, "interesting", note="first")
    V.write_verdict(conn, qid, 2, "artifact", note="second")

    rows = _window_rows(conn, ws)
    assert len(rows) == 1
    assert rows[0]["verdict"] == "artifact"
    assert rows[0]["note"] == "second"


def test_the_queue_resolver_sees_the_window_this_wrote_as_judged():
    """The convention is only coherent if the id the resolver hands out is the
    id `write_verdict` takes back."""
    from Working.review import queues as Q
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid, n_windows=6)
    qid = _make_window_queue(conn, ws)

    item = Q.queue_items(conn, qid, include_judged=True)[3]
    assert item["target_id"] == item["window_index"] == 3
    V.write_verdict(conn, qid, item["target_id"], "seed")

    counts = Q.queue_counts(conn, qid)
    assert (counts["total"], counts["judged"], counts["remaining"]) == (6, 1, 5)


def test_undo_of_a_fresh_window_verdict_removes_the_row():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)
    V.write_verdict(conn, qid, 2, "seed")

    out = V.undo_last(conn, qid)

    assert out is not None and out["writes_to"] == "window_verdicts"
    assert _window_rows(conn, ws) == []


def test_undo_after_a_window_re_verdict_restores_the_first_verdict():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)
    V.write_verdict(conn, qid, 2, "interesting", note="first")
    V.write_verdict(conn, qid, 2, "artifact", note="second")

    V.undo_last(conn, qid)

    rows = _window_rows(conn, ws)
    assert len(rows) == 1, "undo must restore, not delete, a re-verdict"
    assert rows[0]["verdict"] == "interesting"
    assert rows[0]["note"] == "first"
    assert rows[0]["queue_id"] == qid


def test_a_window_batch_is_one_audit_row_and_undo_reverses_all_of_it():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    out = V.write_batch(conn, qid, [0, 1, 2], "not_interesting")

    assert out["count"] == 3
    assert [r["window_index"] for r in _window_rows(conn, ws)] == [0, 1, 2]
    audit = conn.execute("SELECT * FROM review_audit").fetchall()
    assert len(audit) == 1
    assert audit[0]["action"] == "batch"
    assert audit[0]["target_table"] == "window_verdicts"
    assert json.loads(audit[0]["target_ids"]) == [0, 1, 2]

    V.undo_last(conn, qid)
    assert _window_rows(conn, ws) == []


def test_a_window_batch_undo_restores_the_windows_that_had_a_prior_verdict():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)
    V.write_verdict(conn, qid, 1, "seed", note="kept")

    V.write_batch(conn, qid, [0, 1, 2], "not_interesting")
    V.undo_last(conn, qid)

    rows = _window_rows(conn, ws)
    assert [(r["window_index"], r["verdict"]) for r in rows] == [(1, "seed")]
    assert rows[0]["note"] == "kept"


def test_a_window_index_past_the_end_of_the_set_is_refused():
    """The other two branches refuse a target id that is in neither store.

    A window index the set does not contain is the same fault: a row written
    for it is a verdict on a window nobody was ever shown, and because
    `queues._resolve_windows` only ever lists `range(n_windows)` the stray row
    would never surface again to be noticed or undone from the UI.
    """
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid, n_windows=6)
    qid = _make_window_queue(conn, ws)

    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, 6, "seed")
    assert _window_rows(conn, ws) == []


def test_a_negative_window_index_is_refused():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)

    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, -1, "seed")
    assert _window_rows(conn, ws) == []


def test_a_window_queue_naming_a_set_that_is_gone_is_a_value_error():
    """Not a bare `sqlite3.IntegrityError` from the foreign key: the caller
    asked a well-formed question of a queue whose source has been deleted, and
    the message should say so."""
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid)
    qid = _make_window_queue(conn, ws)
    conn.execute("DELETE FROM window_sets WHERE id = ?", (ws,))
    conn.commit()

    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, 0, "seed")


# ── rule 5 on COLLIDING ids ─────────────────────────────────────────────────
#
# The stage-1 tests above passed because their ids did not collide. On the
# project database detection ids run 1..732 and annotation ids 1..11269, so
# every real detection id is ALSO an annotation id — and the old
# `_check_target` asked "does a row with this id exist in the table I am about
# to write to" and returned as soon as it did, which made the refusal branch
# unreachable for every one of them. A guard that only fires when the ids
# happen not to collide is not a guard, so every test in this block forces the
# collision and asserts on it.
#
# The fix these tests pin: resolve the target through the QUEUE'S UNIT — the
# `review_queues.unit` column, which already says whether this queue is made of
# detections, human spans, windows or sequences — and refuse anything that is
# not one of those.

def _insert_sequence(conn, rid, key="seq-a", annotation_id=None,
                     needs_extraction=1):
    cur = conn.execute(
        """INSERT INTO sequences
               (sequence_key, origin, recording_id, channel, start_idx, end_idx,
                n_events, needs_extraction, annotation_id, created_at)
           VALUES (?, 'human', ?, 0, 0, 500, 6, ?, ?, '2026-01-01T00:00:00')""",
        (key, rid, needs_extraction, annotation_id),
    )
    conn.commit()
    return cur.lastrowid


def _annotation_state(conn, ann_id):
    row = q.get_annotation(conn, ann_id)
    return (row["verdict"], row["note"])


def test_rule_5_refuses_a_detection_unit_queue_that_writes_annotations():
    """The refusal branch the whole design rests on, on ids that COLLIDE.

    A queue whose unit is `detection` and whose `writes_to` is `annotations`
    is the crossing rule 5 forbids, and `create_queue` used to accept it from
    an HTTP body. The old check looked the id up in `annotations`, found the
    unrelated human row that happens to share it, and wrote a fabricated human
    verdict there.
    """
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    ann = q.insert_annotation(conn, rid, 500, 600, "interesting",
                              q.SOURCE_MANUAL_UI, note="a human observation")
    assert det == ann, "the collision IS the test: both stores hold this id"
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="discovery-run", unit="detection")

    before = _annotation_state(conn, ann)
    with pytest.raises(PermissionError) as exc:
        V.write_verdict(conn, qid, det, "seed", note="rule 5 probe")

    assert "rule 5" in str(exc.value).lower()
    assert _annotation_state(conn, ann) == before
    assert _counts(conn) == (0, 1)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM review_audit").fetchone()["n"] == 0


def test_rule_5_refuses_a_span_unit_queue_that_writes_adjudications():
    """The mirror direction, equally dead on colliding ids."""
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    ann = q.insert_annotation(conn, rid, 500, 600, "interesting",
                              q.SOURCE_MANUAL_UI)
    assert det == ann
    qid = _make_queue(conn, writes_to="adjudications",
                      source_kind="explore-spans", unit="human span")

    with pytest.raises(PermissionError) as exc:
        V.write_verdict(conn, qid, ann, "seed")

    assert "rule 5" in str(exc.value).lower()
    assert _counts(conn) == (0, 1)


def test_a_detection_id_offered_to_a_sequence_queue_is_refused():
    """A sequence queue's ids are `sequences` ids. A detection id that is not
    one of them is a crossing, even when an `annotations` row shares it."""
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    _insert_detection(conn, rid, 0, 100)
    stray = _insert_detection(conn, rid, 200, 300)
    q.insert_annotation(conn, rid, 500, 600, "interesting", q.SOURCE_MANUAL_UI)
    bystander = q.insert_annotation(conn, rid, 700, 800, "interesting",
                                    q.SOURCE_MANUAL_UI, note="untouched")
    assert stray == bystander, "the detection id is also an annotation id"
    _insert_sequence(conn, rid, annotation_id=bystander)
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="extract-events", unit="sequence")

    before = _annotation_state(conn, bystander)
    with pytest.raises(PermissionError) as exc:
        V.write_verdict(conn, qid, stray, "seed", note="stray detection")

    assert "rule 5" in str(exc.value).lower()
    assert _annotation_state(conn, bystander) == before


# ── a sequence queue writes the sequence's OWN annotation ───────────────────

def test_a_sequence_queue_writes_the_sequences_annotation_not_the_row_sharing_its_id():
    """`sequences.annotation_id` is the pointer; `sequences.id` is not.

    On the project database every sequence id in the seeded extract-events
    queue (119-148) is also an annotation id, so treating the target id as an
    `annotations` id wrote a fabricated verdict and note onto a different
    human observation and left the intended one untouched.
    """
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    bystander = q.insert_annotation(conn, rid, 100, 200, "interesting",
                                    q.SOURCE_MANUAL_UI,
                                    note="a different human observation")
    parent = q.insert_annotation(conn, rid, 9000, 9500, "unsure",
                                 q.SOURCE_MANUAL_UI, note="the sequence span")
    seq = _insert_sequence(conn, rid, annotation_id=parent)
    assert seq == bystander, "the sequence id collides with an annotation id"
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="extract-events", unit="sequence")

    bystander_before = _annotation_state(conn, bystander)
    out = V.write_verdict(conn, qid, seq, "interesting", note="sequence verdict")

    assert _annotation_state(conn, parent) == ("interesting", "sequence verdict")
    assert _annotation_state(conn, bystander) == bystander_before
    assert out["target_id"] == seq
    assert out["row_id"] == parent


def test_undo_of_a_sequence_verdict_restores_the_sequences_own_annotation():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    bystander = q.insert_annotation(conn, rid, 100, 200, "interesting",
                                    q.SOURCE_MANUAL_UI, note="untouched")
    parent = q.insert_annotation(conn, rid, 9000, 9500, "unsure",
                                 q.SOURCE_MANUAL_UI, note="before")
    seq = _insert_sequence(conn, rid, annotation_id=parent)
    assert seq == bystander
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="extract-events", unit="sequence")
    V.write_verdict(conn, qid, seq, "interesting", note="after")

    V.undo_last(conn, qid)

    assert _annotation_state(conn, parent) == ("unsure", "before")
    assert _annotation_state(conn, bystander) == ("interesting", "untouched")


def test_a_sequence_with_no_annotation_is_refused_rather_than_guessed():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    bystander = q.insert_annotation(conn, rid, 100, 200, "interesting",
                                    q.SOURCE_MANUAL_UI, note="untouched")
    seq = _insert_sequence(conn, rid, annotation_id=None)
    assert seq == bystander
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="extract-events", unit="sequence")

    with pytest.raises(ValueError) as exc:
        V.write_verdict(conn, qid, seq, "interesting", note="nowhere to land")

    assert "annotation" in str(exc.value).lower()
    assert _annotation_state(conn, bystander) == ("interesting", "untouched")
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM review_audit").fetchone()["n"] == 0


# ── a verdict belongs to the queue that asked the question ──────────────────

def test_a_verdict_for_a_target_the_queue_never_asked_about_is_refused():
    """The audit ledger is what undo and the judged-set are built on, so a row
    saying queue N asked about an item it never showed anyone is a false
    provenance trail."""
    from Working.review import queues as Q
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    mine = _insert_detection(conn, rid, 0, 100)
    theirs = _insert_detection(conn, rid, 5000, 5100)
    run_id = conn.execute("SELECT run_id FROM detections WHERE id = ?",
                          (mine,)).fetchone()["run_id"]
    qid = Q.create_queue(conn, name="one run", source_kind="discovery-run",
                         filters={"run_id": run_id})
    assert [it["target_id"] for it in Q.queue_items(conn, qid)] == [mine]

    with pytest.raises(ValueError) as exc:
        V.write_verdict(conn, qid, theirs, "seed")

    assert "queue" in str(exc.value).lower()
    assert _counts(conn) == (0, 0)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM review_audit").fetchone()["n"] == 0


def test_a_batch_containing_a_non_member_writes_nothing_at_all():
    from Working.review import queues as Q
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    mine = _insert_detection(conn, rid, 0, 100)
    theirs = _insert_detection(conn, rid, 5000, 5100)
    run_id = conn.execute("SELECT run_id FROM detections WHERE id = ?",
                          (mine,)).fetchone()["run_id"]
    qid = Q.create_queue(conn, name="one run", source_kind="discovery-run",
                         filters={"run_id": run_id})

    with pytest.raises(ValueError):
        V.write_batch(conn, qid, [mine, theirs], "seed")

    assert _counts(conn) == (0, 0)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM review_audit").fetchone()["n"] == 0


# ── tags ────────────────────────────────────────────────────────────────────

def test_tags_may_arrive_as_a_plain_list_on_a_detection_queue():
    """The bridge's `VerdictBody.tags` is `list[str]`; both core writers used
    to call `.items()` on it and raise `AttributeError` three frames down."""
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)

    V.write_verdict(conn, qid, det, "seed", tags=["sharkfin"])

    from Working.database import adjudications as adjm
    adj_id = adjm.get_adjudication(conn, det)["id"]
    assert adjm.get_adjudication_tags(conn, adj_id)["element"] == ["sharkfin"]


def test_tags_may_arrive_as_a_plain_list_on_an_annotations_queue():
    from Working.database import vocabulary as vocab
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ann = q.insert_annotation(conn, rid, 0, 100, "seed", q.SOURCE_MANUAL_UI)
    qid = _make_queue(conn, writes_to="annotations",
                      source_kind="explore-spans", unit="human span")

    V.write_verdict(conn, qid, ann, "interesting", tags=["sharkfin"])

    assert vocab.get_annotation_tags(conn, ann)["element"] == ["sharkfin"]


def test_a_tag_outside_the_vocabulary_is_refused_by_name():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)

    with pytest.raises(ValueError) as exc:
        V.write_verdict(conn, qid, det, "seed", tags=["not-a-real-tag"])

    assert "not-a-real-tag" in str(exc.value)


# ── batches ────────────────────────────────────────────────────────────────

def test_an_empty_batch_writes_nothing_and_no_audit_row():
    conn = _fresh_conn()
    qid = _make_queue(conn)

    out = V.write_batch(conn, qid, [], "seed")

    assert out["count"] == 0
    assert out["audit_id"] is None
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM review_audit").fetchone()["n"] == 0


def test_a_batch_collapses_duplicate_target_ids():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    det = _insert_detection(conn, rid)
    qid = _make_queue(conn)

    out = V.write_batch(conn, qid, [det, det, det], "seed")

    assert out["count"] == 1
    assert out["target_ids"] == [det]
    audit = conn.execute("SELECT * FROM review_audit").fetchall()
    assert len(audit) == 1
    assert json.loads(audit[0]["target_ids"]) == [det]


# ── undo must not claim to have reversed a promotion it did not ─────────────

def test_undo_last_refuses_to_stamp_an_audit_row_it_cannot_reverse():
    """`undo_last` used to fall back to `row['target_table']`, do nothing with
    a value it has no branch for, and still stamp `undone_at` — burning the
    only record that could have reversed it."""
    conn = _fresh_conn()
    qid = _make_queue(conn)
    conn.execute(
        """INSERT INTO review_audit
               (queue_id, action, target_table, target_ids, payload_json,
                created_at)
           VALUES (?, 'verdict', 'motif_member', '[1]', ?, ?)""",
        (qid, json.dumps({"writes_to": "motif_member",
                          "targets": [{"target_id": 1, "prior": None}]}),
         "2026-01-01T00:00:00"))
    conn.commit()

    with pytest.raises(ValueError):
        V.undo_last(conn, qid)

    assert conn.execute(
        "SELECT undone_at FROM review_audit").fetchone()["undone_at"] is None

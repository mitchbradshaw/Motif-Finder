"""
test_review_queues.py
=====================
Stage-3 wiring prompt 05 — `Working/review/queues.py`, the queue descriptor
store and its live source resolver.

The thing being asserted throughout: a queue holds NO items of its own. It is
a descriptor (name, source kind, source ref, unit, write target, blind, cap)
and `queue_items` RESOLVES the source on every call, so a verdict written
anywhere else immediately changes what the queue shows (04-to-05 §1).

Two rules get their own tests because they are silent when broken:
  * a run with `runs.superseded_at` set must never reach a queue (04-to-05 §2)
    — a discarded run's detections stay in the table on purpose;
  * a blind queue (P20) must omit the machine score from the payload ENTIRELY,
    not hide it downstream, or the number is one `console.log` from the eye it
    was meant to be kept from.

Run from the project root:
    python -m pytest tests/test_review_queues.py -q
"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db
from Working.database import adjudications as adj
from Working.database import queries as q
from Working.database import vocabulary as v
from Working.review import queues as qs


def _fresh_conn():
    conn = init_db(":memory:")
    v.seed_vocabulary(conn)
    return conn


def _insert_recording(conn, source_file="a.mat", channel=0):
    return q.insert_recording(conn, source_file, channel, 1.0, 1000, 0,
                              f"data/{source_file}/CH{channel}.npy")


def _insert_run_group(conn):
    cur = conn.execute(
        "INSERT INTO run_groups (created_at) VALUES (?)", ("2026-01-01T00:00:00",)
    )
    conn.commit()
    return cur.lastrowid


def _insert_detection(conn, rid, start_idx=0, end_idx=100, score=None,
                      method="rupture", run_group_id=None, superseded=False):
    cid = conn.execute(
        "INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
        (f"hash-{rid}-{start_idx}-{end_idx}-{method}-{superseded}",
         json.dumps({"steps": [{"stage": "detection", "algorithm": method}]}),
         "2026-01-01T00:00:00"),
    ).lastrowid
    run_id = conn.execute(
        """INSERT INTO runs
               (config_id, recording_id, span_start, span_end, started_at, status, run_group_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (cid, rid, 0, 1000, "2026-01-01T00:00:00", "done", run_group_id),
    ).lastrowid
    if superseded:
        conn.execute("UPDATE runs SET superseded_at = ? WHERE id = ?",
                     ("2026-01-02T00:00:00", run_id))
    det_id = conn.execute(
        "INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
        (run_id, start_idx, end_idx, score),
    ).lastrowid
    conn.commit()
    return det_id


def _insert_annotation(conn, rid, start_idx, end_idx, verdict="seed"):
    cur = conn.execute(
        """INSERT INTO annotations
               (recording_id, start_idx, end_idx, verdict, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (rid, start_idx, end_idx, verdict, "explore", "2026-01-01T00:00:00"),
    )
    conn.commit()
    return cur.lastrowid


def _insert_window_set(conn, rid, n_windows=4):
    cur = conn.execute(
        """INSERT INTO window_sets
               (name, version, path, recording_id, channel, n_windows, created_at)
           VALUES (?, 1, ?, ?, 0, ?, ?)""",
        ("ws", "derived/ws.npy", rid, n_windows, "2026-01-01T00:00:00"),
    )
    conn.commit()
    return cur.lastrowid


def _insert_sequence(conn, rid, key, needs_extraction=1):
    cur = conn.execute(
        """INSERT INTO sequences
               (sequence_key, origin, recording_id, channel, start_idx, end_idx,
                n_events, needs_extraction, created_at)
           VALUES (?, 'machine', ?, 0, 0, 500, 6, ?, ?)""",
        (key, rid, needs_extraction, "2026-01-01T00:00:00"),
    )
    conn.commit()
    return cur.lastrowid


# ── the no-UI-import boundary ───────────────────────────────────────────────

def test_module_imports_no_ui_library():
    src_path = os.path.join(PROJECT_ROOT, "Working", "review", "queues.py")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    for banned in ("panel", "holoviews", "bokeh", "fastapi"):
        assert "import {}".format(banned) not in src
        assert "from {}".format(banned) not in src


# ── creation: the per-kind defaults of spec §10.1 ───────────────────────────

def test_create_queue_infers_defaults_per_source_kind():
    conn = _fresh_conn()
    expected = {
        "discovery-run":      ("detection", "adjudications", 0),
        "seed-search":        ("detection", "adjudications", 0),
        "explore-spans":      ("human span", "annotations", 0),
        "training-windows":   ("window", "window_verdicts", 1),
        "model-verification": ("window", "window_verdicts", 1),
        "extract-events":     ("sequence", "annotations", 0),
    }
    for kind, (unit, writes_to, blind) in expected.items():
        qid = qs.create_queue(conn, name="q-" + kind, source_kind=kind)
        row = qs.get_queue(conn, qid)
        assert row["unit"] == unit, kind
        assert row["writes_to"] == writes_to, kind
        assert row["blind"] == blind, kind


def test_create_queue_rejects_unknown_source_kind():
    conn = _fresh_conn()
    try:
        qs.create_queue(conn, name="bad", source_kind="telepathy")
    except ValueError:
        return
    raise AssertionError("unknown source_kind should raise ValueError")


def test_explicit_arguments_override_the_inferred_defaults():
    conn = _fresh_conn()
    qid = qs.create_queue(conn, name="blind discovery", source_kind="discovery-run",
                          blind=True, cap=10, note="P20")
    row = qs.get_queue(conn, qid)
    assert row["blind"] == 1
    assert row["cap"] == 10
    assert row["note"] == "P20"


def test_list_queues_hides_closed_and_carries_counts():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    _insert_detection(conn, rid, 0, 100, score=0.5, run_group_id=gid)
    qid = qs.create_queue(conn, name="live", source_kind="discovery-run",
                          source_ref=str(gid))
    other = qs.create_queue(conn, name="dead", source_kind="discovery-run",
                            source_ref=str(gid))
    qs.close_queue(conn, other)
    rows = qs.list_queues(conn)
    assert [r["id"] for r in rows] == [qid]
    assert rows[0]["total"] == 1
    assert rows[0]["remaining"] == 1
    assert rows[0]["judged"] == 0
    assert len(qs.list_queues(conn, include_closed=True)) == 2


# ── the resolver ────────────────────────────────────────────────────────────

def test_discovery_queue_resolves_the_run_group_live():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    d1 = _insert_detection(conn, rid, 0, 100, score=0.9, run_group_id=gid)
    qid = qs.create_queue(conn, name="q", source_kind="discovery-run",
                          source_ref=str(gid))
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == [d1]
    # a detection added AFTER the queue was made still arrives: the queue is
    # a filter, not a copy.
    d2 = _insert_detection(conn, rid, 200, 300, score=0.7, run_group_id=gid)
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == [d1, d2]


def test_superseded_run_never_reaches_the_queue():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    live = _insert_detection(conn, rid, 0, 100, score=0.9, run_group_id=gid)
    discarded = _insert_detection(conn, rid, 400, 500, score=0.8,
                                  run_group_id=gid, superseded=True)
    qid = qs.create_queue(conn, name="q", source_kind="discovery-run",
                          source_ref=str(gid))
    ids = [it["target_id"] for it in qs.queue_items(conn, qid)]
    assert live in ids
    assert discarded not in ids
    assert qs.queue_counts(conn, qid)["total"] == 1


def test_blind_queue_omits_the_score_from_the_payload_entirely():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    _insert_detection(conn, rid, 0, 100, score=0.93, run_group_id=gid)
    blind = qs.create_queue(conn, name="blind", source_kind="discovery-run",
                            source_ref=str(gid), blind=True)
    sighted = qs.create_queue(conn, name="sighted", source_kind="discovery-run",
                              source_ref=str(gid))
    item = qs.queue_items(conn, blind)[0]
    assert "score" not in item
    assert 0.93 not in [vv for vv in item.values() if isinstance(vv, float)]
    assert qs.queue_items(conn, sighted)[0]["score"] == 0.93


def test_cap_truncates_the_resolved_list_and_the_counts():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    for i in range(5):
        _insert_detection(conn, rid, i * 100, i * 100 + 50, score=0.5,
                          run_group_id=gid)
    qid = qs.create_queue(conn, name="capped", source_kind="discovery-run",
                          source_ref=str(gid), cap=3)
    assert len(qs.queue_items(conn, qid)) == 3
    assert qs.queue_counts(conn, qid) == {"total": 3, "judged": 0, "remaining": 3}


def test_counts_and_header_counts_move_when_a_verdict_lands():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    d1 = _insert_detection(conn, rid, 0, 100, score=0.5, run_group_id=gid)
    _insert_detection(conn, rid, 200, 300, score=0.5, run_group_id=gid)
    qid = qs.create_queue(conn, name="q", source_kind="discovery-run",
                          source_ref=str(gid))
    assert qs.queue_counts(conn, qid) == {"total": 2, "judged": 0, "remaining": 2}
    assert qs.header_counts(conn)["need_you"] == 2

    adj.insert_adjudication(conn, d1, "interesting")

    assert qs.queue_counts(conn, qid) == {"total": 2, "judged": 1, "remaining": 1}
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == [d1 + 1]
    assert len(qs.queue_items(conn, qid, include_judged=True)) == 2
    header = qs.header_counts(conn)
    assert header["need_you"] == 1
    assert header["by_queue"] == [{"id": qid, "name": "q", "remaining": 1}]


def test_explore_spans_resolves_human_seed_annotations():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    seed = _insert_annotation(conn, rid, 0, 100, verdict="seed")
    _insert_annotation(conn, rid, 200, 300, verdict="not_interesting")
    qid = qs.create_queue(conn, name="spans", source_kind="explore-spans")
    ids = [it["target_id"] for it in qs.queue_items(conn, qid)]
    assert ids == [seed]


def test_extract_events_resolves_sequences_needing_extraction():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    needs = _insert_sequence(conn, rid, "seq-a", needs_extraction=1)
    _insert_sequence(conn, rid, "seq-b", needs_extraction=0)
    qid = qs.create_queue(conn, name="extract", source_kind="extract-events")
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == [needs]


def test_window_queue_resolves_indices_minus_those_already_judged():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid, n_windows=4)
    qid = qs.create_queue(conn, name="windows", source_kind="training-windows",
                          source_ref=str(ws))
    assert [it["window_index"] for it in qs.queue_items(conn, qid)] == [0, 1, 2, 3]
    conn.execute(
        """INSERT INTO window_verdicts
               (window_set_id, window_index, verdict, created_at)
           VALUES (?, 2, 'interesting', ?)""",
        (ws, "2026-01-01T00:00:00"),
    )
    conn.commit()
    assert [it["window_index"] for it in qs.queue_items(conn, qid)] == [0, 1, 3]
    assert qs.queue_counts(conn, qid) == {"total": 4, "judged": 1, "remaining": 3}


def test_window_queue_is_blind_by_default_and_carries_no_score():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    ws = _insert_window_set(conn, rid, n_windows=2)
    qid = qs.create_queue(conn, name="verify", source_kind="model-verification",
                          source_ref=str(ws))
    assert qs.get_queue(conn, qid)["blind"] == 1
    for item in qs.queue_items(conn, qid):
        assert "score" not in item


def test_queue_items_paging_and_get_queue_missing():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    for i in range(4):
        _insert_detection(conn, rid, i * 100, i * 100 + 50, score=0.5,
                          run_group_id=gid)
    qid = qs.create_queue(conn, name="q", source_kind="discovery-run",
                          source_ref=str(gid))
    assert len(qs.queue_items(conn, qid, limit=2)) == 2
    assert len(qs.queue_items(conn, qid, limit=2, offset=3)) == 1
    assert qs.get_queue(conn, 9999) is None


def test_closed_queue_is_absent_from_header_counts():
    conn = _fresh_conn()
    rid = _insert_recording(conn)
    gid = _insert_run_group(conn)
    _insert_detection(conn, rid, 0, 100, score=0.5, run_group_id=gid)
    qid = qs.create_queue(conn, name="q", source_kind="discovery-run",
                          source_ref=str(gid))
    assert qs.header_counts(conn)["need_you"] == 1
    qs.close_queue(conn, qid)
    assert qs.header_counts(conn) == {"need_you": 0, "by_queue": []}

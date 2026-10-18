"""
test_review_queue_listed_order.py
=================================
a2-rq1b: an exact-set detection queue (`filters = {"detection_ids": [...]}`) can be served in the order its ids are
LISTED, with `"order": "listed"`, instead of by detection id.

Why it exists. RQ1b's stratified sample of candidate events (`Working/discovery/candidate_events.py`) is put to the
researcher as one blind queue over each event's anchor detection. Detection ids are written run by run, so id order
groups the sample by detector and channel: the reviewer would see every drop-detector item together, and whatever
drifts over a session (fatigue, a stricter eye) would fall on some detectors and not others, biasing the per-detector
precision the sample exists to measure. A seeded shuffle, served as listed, spreads it evenly.

Without the key nothing changes: every existing queue keeps its id order (the paging contract of
`queries.queue_candidates`).

Run from the project root:
    python -m pytest tests/test_review_queue_listed_order.py -q
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
from Working.database import adjudications as adj
from Working.database import queries as q
from Working.database import vocabulary as v
from Working.review import queues as qs


def _conn():
    conn = init_db(":memory:")
    v.seed_vocabulary(conn)
    return conn


def _detections(conn, n=5):
    rid = q.insert_recording(conn, "a.mat", 0, 1.0, 100000, 0, "data/a.mat/CH0.npy")
    cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
                       ("h", json.dumps({"steps": []}), "2026-01-01T00:00:00")).lastrowid
    run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                       "VALUES (?, ?, 0, 100000, '2026-01-01T00:00:00', 'completed')", (cid, rid)).lastrowid
    ids = [conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                        (run, 1000 * i, 1000 * i + 100, 0.5)).lastrowid for i in range(n)]
    conn.commit()
    return ids


def test_a_listed_queue_is_served_in_the_listed_order():
    conn = _conn()
    ids = _detections(conn)
    listed = [ids[3], ids[0], ids[4], ids[1], ids[2]]
    qid = qs.create_queue(conn, name="sample", source_kind="discovery-run",
                          filters={"detection_ids": listed, "order": "listed"}, blind=True)
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == listed
    # the order holds for the judged-included listing the bridge ranks by, too
    assert [it["target_id"] for it in qs.queue_items(conn, qid, include_judged=True)] == listed


def test_without_the_key_an_exact_set_keeps_its_id_order():
    conn = _conn()
    ids = _detections(conn)
    listed = [ids[3], ids[0], ids[4], ids[1], ids[2]]
    qid = qs.create_queue(conn, name="picked", source_kind="discovery-run", filters={"detection_ids": listed})
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == sorted(listed)


def test_a_judged_item_leaves_the_listed_queue_and_the_rest_keep_their_order():
    conn = _conn()
    ids = _detections(conn)
    listed = [ids[2], ids[4], ids[0]]
    qid = qs.create_queue(conn, name="sample", source_kind="discovery-run",
                          filters={"detection_ids": listed, "order": "listed"}, blind=True)
    adj.insert_adjudication(conn, ids[4], "interesting")
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == [ids[2], ids[0]]
    assert qs.queue_counts(conn, qid) == {"total": 3, "judged": 1, "remaining": 2}


def test_a_blind_listed_queue_still_carries_no_score():
    conn = _conn()
    ids = _detections(conn, 2)
    qid = qs.create_queue(conn, name="sample", source_kind="discovery-run",
                          filters={"detection_ids": ids[::-1], "order": "listed"}, blind=True)
    assert all("score" not in it for it in qs.queue_items(conn, qid))


@pytest.mark.parametrize("filters, kind", [
    ({"detection_ids": [1], "order": "by-score"}, "discovery-run"),      # an order nobody implements
    ({"order": "listed"}, "discovery-run"),                               # nothing to list
    ({"run_ids": [1], "order": "listed"}, "discovery-run"),               # a run set has no listed order
    ({"detection_ids": [1], "order": "listed"}, "training-windows"),      # not a detection queue
])
def test_create_queue_refuses_an_order_it_cannot_serve(filters, kind):
    conn = _conn()
    with pytest.raises(ValueError):
        qs.create_queue(conn, name="bad", source_kind=kind, filters=filters)


def test_a_listed_queue_is_a_fixed_set_and_cannot_be_extended():
    conn = _conn()
    ids = _detections(conn)
    qid = qs.create_queue(conn, name="sample", source_kind="discovery-run",
                          filters={"detection_ids": ids[:2], "order": "listed"})
    with pytest.raises(ValueError):
        qs.extend_queue(conn, qid, [ids[3]])


def test_the_listed_order_is_part_of_a_queue_s_identity():
    conn = _conn()
    ids = _detections(conn)
    plain = qs.create_queue(conn, name="picked", source_kind="discovery-run", filters={"detection_ids": ids})
    listed = qs.create_queue(conn, name="sample", source_kind="discovery-run",
                             filters={"detection_ids": ids[::-1], "order": "listed"})
    assert qs.find_open_queue(conn, source_kind="discovery-run", filters={"detection_ids": ids}) == plain
    assert qs.find_open_queue(conn, source_kind="discovery-run",
                              filters={"detection_ids": ids, "order": "listed"}) == listed

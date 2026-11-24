"""
test_review_archive.py
======================
Queue archive (2026-11-24, the researcher: "implement functionality to archive queues with a button archive icon
next to the queue name in the dropdown queue list on review, and store them in a new block on the jobs page,
labelled 'archived queues', with the ability to restore them to review").

An archived queue leaves Review's queue list and the header's count, and nothing finds it as an open queue to widen:
a send after archiving makes a new queue rather than filling a hidden one. It is NOT closed - a blind test's page
still finds its queue, and its verdicts stay where they are. Restoring puts it back as it was.

Run from the project root:
    python -m pytest tests/test_review_archive.py -q
"""

import json
import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database import vocabulary as v  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.review import family_queue as fq  # noqa: E402
from Working.review import queues as qs  # noqa: E402
from Working.review import sequence_queue as sq  # noqa: E402


def _conn(path=":memory:"):
    conn = init_db(path)
    conn.row_factory = sqlite3.Row
    v.seed_vocabulary(conn)
    return conn


def _detections(conn, n=3, source_file="a.mat"):
    rid = q.insert_recording(conn, source_file, 0, 1.0, 10_000, 0, f"data/{source_file}/CH0.npy")
    cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, '{}', ?)",
                       (f"h-{source_file}", "2026-01-01T00:00:00")).lastrowid
    run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                       "VALUES (?, ?, 0, 10000, '2026-01-01T00:00:00', 'done')", (cid, rid)).lastrowid
    ids = [int(conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.9)",
                            (run, 1000 * k, 1000 * k + 50)).lastrowid) for k in range(n)]
    conn.commit()
    return ids


def _queue(conn, ids, name):
    return qs.create_queue(conn, name=name, source_kind="discovery-run", filters={"detection_ids": ids})


def test_the_column_is_added_once_and_a_new_queue_is_not_archived(tmp_path):
    path = str(tmp_path / "db.sqlite")
    init_db(path).close()
    conn = _conn(path)                       # init_db again: the migration is idempotent
    cols = [r[1] for r in conn.execute("PRAGMA table_info(review_queues)")]
    assert cols.count("archived_at") == 1
    qid = _queue(conn, _detections(conn), "fresh")
    assert qs.get_queue(conn, qid)["archived_at"] is None


def test_an_archived_queue_leaves_the_list_and_the_header_and_comes_back_on_restore():
    conn = _conn()
    keep = _queue(conn, _detections(conn, 2, "a.mat"), "keep")
    old = _queue(conn, _detections(conn, 3, "b.mat"), "old")
    assert qs.header_counts(conn)["need_you"] == 5

    assert qs.archive_queue(conn, old) is True
    assert [x["id"] for x in qs.list_queues(conn)] == [keep]
    assert [x["id"] for x in qs.list_queues(conn, archived="only")] == [old]
    assert sorted(x["id"] for x in qs.list_queues(conn, archived="include")) == [keep, old]
    assert qs.header_counts(conn)["need_you"] == 2
    assert [x["id"] for x in qs.header_counts(conn)["by_queue"]] == [keep]
    assert qs.archive_queue(conn, old) is False          # already archived: nothing changes, nothing fails

    assert qs.restore_queue(conn, old) is True
    assert sorted(x["id"] for x in qs.list_queues(conn)) == [keep, old]
    assert qs.get_queue(conn, old)["archived_at"] is None
    assert qs.header_counts(conn)["need_you"] == 5
    assert qs.restore_queue(conn, old) is False


def test_an_archived_queue_is_not_closed_and_still_opens_by_its_id():
    conn = _conn()
    qid = _queue(conn, _detections(conn), "exam")
    qs.archive_queue(conn, qid)
    row = qs.get_queue(conn, qid)
    assert row["archived_at"] and row["closed_at"] is None   # a blind test's own lookup (closed_at IS NULL) still finds it
    assert len(qs.queue_items(conn, qid)) == 3               # a direct link still shows its items


def test_nothing_widens_an_archived_queue():
    conn = _conn()
    ids = _detections(conn)
    qid = _queue(conn, ids, "send N")
    conn.execute("UPDATE review_queues SET note = 'picked' WHERE id = ?", (qid,))
    conn.commit()
    assert qs.find_open_queue(conn, source_kind="discovery-run", filters={"detection_ids": ids}) == qid
    assert qs.find_open_queue_by_note(conn, source_kind="discovery-run", note="picked") == qid
    seq = sq.send_to_sequence_review(conn, spans=[{"recording_id": 1, "start_idx": 0, "end_idx": 2050,
                                                   "events": [{"start_idx": 0, "end_idx": 50},
                                                              {"start_idx": 2000, "end_idx": 2050}]}],
                                     provenance="t", name="sequences")["queue_id"]
    assert sq.open_queue(conn, "sequences") == seq
    fam = qs.create_queue(conn, name="family", source_kind=fq.SOURCE_KIND, source_ref="F-01",
                          filters=json.loads(json.dumps({"family": "F-01"})))
    assert fq.open_family_queue(conn, "F-01") == fam

    for x in (qid, seq, fam):
        qs.archive_queue(conn, x)
    assert qs.find_open_queue(conn, source_kind="discovery-run", filters={"detection_ids": ids}) is None
    assert qs.find_open_queue_by_note(conn, source_kind="discovery-run", note="picked") is None
    assert sq.open_queue(conn, "sequences") is None
    assert fq.open_family_queue(conn, "F-01") is None
    # a send after archiving makes a new queue; the archived one keeps what it had
    again = sq.send_to_sequence_review(conn, spans=[], sequence_ids=[], provenance="t", name="sequences")["queue_id"]
    assert again != seq and qs.get_queue(conn, seq)["archived_at"]


def test_archiving_by_age_takes_only_the_open_queues_made_before_the_cutoff():
    conn = _conn()
    old = _queue(conn, _detections(conn, 1, "a.mat"), "old")
    old_closed = _queue(conn, _detections(conn, 1, "b.mat"), "old closed")
    new = _queue(conn, _detections(conn, 1, "c.mat"), "new")
    conn.execute("UPDATE review_queues SET created_at = '2026-11-01T09:00:00+00:00' WHERE id IN (?, ?)",
                 (old, old_closed))
    conn.execute("UPDATE review_queues SET created_at = '2026-11-23T09:00:00+00:00' WHERE id = ?", (new,))
    conn.commit()
    qs.close_queue(conn, old_closed)
    got = qs.archive_queues_before(conn, "2026-11-16T14:00:00+00:00")
    assert got == [old]
    assert qs.get_queue(conn, old_closed)["archived_at"] is None
    assert qs.get_queue(conn, new)["archived_at"] is None
    assert qs.archive_queues_before(conn, "2026-11-16T14:00:00+00:00") == []


def test_an_unknown_queue_is_refused():
    conn = _conn()
    with pytest.raises(ValueError):
        qs.archive_queue(conn, 999)
    with pytest.raises(ValueError):
        qs.restore_queue(conn, 999)

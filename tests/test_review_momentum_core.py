"""
test_review_momentum_core.py
============================
AS (2026-11-24), the core half (no FastAPI; runs under the conda pytest).

* `queues.item_view_many` reads the Inspector's window in one go - the structure and the verdict overlay once - and
  must answer, for every target, exactly what `item_view` answers for it alone.
* `verdicts.write_verdict(client_id=)` keeps the page's id for the gesture in the audit payload, and
  `audits_by_client_id` finds it again (undone or not), which is what makes a replayed save write nothing twice.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.review import queues as Q  # noqa: E402
from Working.review import verdicts as V  # noqa: E402
from tests.test_ar_speed_core import NOW, _db, _queues  # noqa: E402


def test_item_view_many_agrees_with_item_view_for_every_target(tmp_path):
    conn, info = _db(tmp_path)
    qids = _queues(conn, info)
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'seed', ?)",
                 (info["dets"][9], NOW))
    conn.execute("UPDATE review_queues SET cap = 40 WHERE id = ?", (qids[1],))
    conn.commit()
    for qid in qids:
        for held in (set(), {info["recs"][1]}):
            want = [str(d) for d in info["dets"][::3]] + ["0", "nonsense"]
            many = Q.item_view_many(conn, qid, want, exclude_recording_ids=held)
            for t in want:
                one = Q.item_view(conn, qid, t, exclude_recording_ids=held)
                assert (many["views"][t]["item"], many["views"][t]["rank"]) == (one["item"], one["rank"]), (qid, t)
                assert many["counts"] == one["counts"] and many["detections"] == one.get("detections")


def test_a_client_id_is_kept_on_the_audit_row_and_found_again_after_an_undo(tmp_path):
    conn, info = _db(tmp_path)
    qid = _queues(conn, info)[1]
    d = info["dets"]
    a = V.write_verdict(conn, qid, str(d[0]), "interesting", client_id="g-1", carry=False)
    V.write_verdict(conn, qid, str(d[1]), "artifact")
    b = V.write_verdict(conn, qid, str(d[2]), "not_interesting", client_id="g-2")
    V.undo_last(conn, qid)
    got = V.audits_by_client_id(conn, qid, ["g-1", "g-2", "g-3"])
    assert set(got) == {"g-1", "g-2"}
    assert got["g-1"]["audit_id"] == a["audit_id"] and got["g-1"]["undone"] is False
    assert got["g-1"]["payload"]["verdict"] == "interesting" and got["g-1"]["payload"]["carry_pending"] is True
    assert got["g-2"]["audit_id"] == b["audit_id"] and got["g-2"]["undone"] is True
    assert V.audits_by_client_id(conn, qid + 999, ["g-1"]) == {}, "a client id leaked across queues"

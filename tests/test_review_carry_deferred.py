"""
test_review_carry_deferred.py
=============================
review-carry, deferred (2026-11-24, the researcher: "it is related to 'carried to X other detections' ... any chance
this process can run in the background instead of between candidates?").

A verdict written with ``carry=False`` is the person's verdict at once - its row and its audit entry, committed - and
its carry waits on the audit entry (``carry_pending``) until `run_pending_carry` does it. The carry writes the
verdict AS GIVEN (the audit entry's), so carries run in audit order end exactly as carries done at once would,
through re-judgements and undos. An undo before the carry runs leaves nothing to carry. The pending list is what a
restarted bridge picks up again.

Core only (no FastAPI): runs under the conda pytest.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.review import queues as Q  # noqa: E402
from Working.review import verdicts as V  # noqa: E402
from test_review_carry_core import _adj, _db  # noqa: E402  (the shared two-run fixture)


def _queue_a(conn, info):
    return Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})


def test_a_deferred_verdict_is_written_at_once_and_carried_later(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = _queue_a(conn, info)
    out = V.write_verdict(conn, qa, d["a1"], "interesting", carry=False)
    assert out["carry_pending"] is True and out["carried"] == []
    assert _adj(conn, d["a1"])["verdict"] == "interesting"            # the person's verdict is in, now
    assert _adj(conn, d["b1"]) is None                                 # the same event in run B: not yet
    assert V.pending_carries(conn) == [out["audit_id"]]
    assert V.carry_status(conn, out["audit_id"]) == {"pending": True, "carried": []}

    got = V.run_pending_carry(conn, out["audit_id"])
    assert got["carried"] == [d["b1"]]
    assert _adj(conn, d["b1"])["carried_from"] == _adj(conn, d["a1"])["id"]
    assert V.pending_carries(conn) == []
    assert V.carry_status(conn, out["audit_id"]) == {"pending": False, "carried": [d["b1"]]}
    # running it again writes nothing more
    assert V.run_pending_carry(conn, out["audit_id"])["carried"] == [d["b1"]]
    assert conn.execute("SELECT COUNT(*) FROM adjudications WHERE carried_from IS NOT NULL").fetchone()[0] == 1

    V.undo_last(conn, qa)                                              # undo after the carry takes it back too
    assert _adj(conn, d["a1"]) is None and _adj(conn, d["b1"]) is None


def test_an_undo_before_the_carry_runs_leaves_nothing_to_carry(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = _queue_a(conn, info)
    out = V.write_verdict(conn, qa, d["a1"], "interesting", carry=False)
    V.undo_last(conn, qa)
    assert V.pending_carries(conn) == []                               # an undone verdict is never picked up again
    got = V.run_pending_carry(conn, out["audit_id"])
    assert got["carried"] == [] and got["skipped"] == "undone"
    assert _adj(conn, d["a1"]) is None and _adj(conn, d["b1"]) is None


def test_carries_run_later_in_order_end_as_carries_done_at_once(tmp_path):
    """The history of test_review_carry_core's exact-undo test - judge a4, judge a1, re-judge a1 - then two undos:
    every state matches, whether each carry ran at once or all three ran afterwards in audit order."""
    def snap(conn, d):
        out = {}
        for k in ("a1", "a4", "b1", "b2"):
            r = _adj(conn, d[k])
            out[k] = None if r is None else (r["verdict"], r["carried_from"] is not None)
        return out

    runs = []
    for defer in (False, True):
        conn, info = _db(tmp_path, f"defer_{defer}.sqlite")
        d = info["d"]
        qa = _queue_a(conn, info)
        outs = [V.write_verdict(conn, qa, d["a4"], "artifact", carry=not defer),
                V.write_verdict(conn, qa, d["a1"], "interesting", carry=not defer),
                V.write_verdict(conn, qa, d["a1"], "unsure", carry=not defer)]   # re-judged before any carry ran
        for o in outs:
            if defer:
                V.run_pending_carry(conn, o["audit_id"])
        states = [snap(conn, d)]
        V.undo_last(conn, qa)
        states.append(snap(conn, d))
        V.undo_last(conn, qa)
        states.append(snap(conn, d))
        runs.append(states)
        conn.close()
    assert runs[0] == runs[1]
    assert runs[1][0]["b1"] == ("unsure", True) and runs[1][1]["b1"] == ("interesting", True)
    assert runs[1][2]["b1"] is None and runs[1][2]["b2"] == ("artifact", True)


def test_a_deferred_batch_is_carried_later_and_its_undo_uncarries(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = _queue_a(conn, info)
    out = V.write_batch(conn, qa, [d["a1"], d["a4"]], "interesting", carry=False)
    assert out["carry_pending"] is True and out["carried"] == []
    assert _adj(conn, d["b1"]) is None and _adj(conn, d["b2"]) is None
    got = V.run_pending_carry(conn, out["audit_id"])
    assert sorted(got["carried"]) == sorted([d["b1"], d["b2"]])
    V.undo_last(conn, qa)
    assert _adj(conn, d["b1"]) is None and _adj(conn, d["b2"]) is None


def test_the_class_label_given_is_the_one_carried(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = _queue_a(conn, info)
    first = V.write_verdict(conn, qa, d["a1"], "interesting", class_label="burst", carry=False)
    V.write_verdict(conn, qa, d["a1"], "interesting", carry=False)          # re-judged without a class
    V.run_pending_carry(conn, first["audit_id"])
    assert _adj(conn, d["b1"])["class_label"] == "burst"                    # carried as given at the time
    V.run_pending_carry(conn, V.pending_carries(conn)[0])
    assert _adj(conn, d["b1"])["class_label"] is None                       # then as re-judged

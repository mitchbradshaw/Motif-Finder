"""
test_review_family_queue.py
===========================
Library › Family *Send N to Review as a queue*, wired: a `library-family`
Review queue over a family's unjudged members, made through `create_queue`.

- **Where the verdict lives — `annotations`, over the member's span** (rule
  5: a human row, never `motif_member` / `motif_edge` / `adjudications`). The
  Family page counts a member *judged* through THE one resolver
  (`Working.library.verdicts` → `divergence.resolve_spans`): a verdict on the
  member's detection, else the event-shaped row it matches by reciprocal IoU.
  A row over exactly the member's span matches at IoU 1, so a verdict given
  in this queue is what the Family page then counts as judged — the button's
  number and the page's are one number.
- **The vocabulary stays at five words** (researcher, 2026-10-05): the
  reviewer answers *interesting*, *not_interesting*, *artifact* or *unsure*;
  *seed* is not this queue's question (the member is already in the Library).
  *unsure* is answered in the queue (not asked again) but is not *judged* on
  the Family page — the resolver gives it no side.
- One queue per family: a second send returns the open one, widened to any
  member it did not yet hold.
- The queue table's CHECK learns the new kind through the idempotent rebuild.
"""

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest

from Working.database import queries as q
from Working.database import runs as R
from Working.database.schema import VERDICTS, init_db
from Working.library import verdicts as LV
from Working.review import family_queue as fq
from Working.review import queues as Q
from Working.review import verdicts as V


@pytest.fixture
def fam():
    """Three members of one family on two recordings, none with a detection
    and none judged — the Library's usual case (imported, or found by a run
    whose detections were never adjudicated)."""
    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(":memory:")
        recs = []
        for ch in range(2):
            path = os.path.join(tmp, f"ch{ch}.npy")
            np.save(path, np.random.default_rng(ch).standard_normal(8000) * 0.01)
            rid = q.insert_recording(conn, "a.mat", ch, 1.0, 8000, 0, path)
            conn.execute("UPDATE recordings SET units = 'mV' WHERE id = ?", (rid,))
            recs.append(rid)
        conn.commit()
        entry = R.insert_motif_entry(conn, recs[0], 990, 1070)
        m0 = R.get_or_create_motif_member(conn, entry, recs[0], 990, 1070)
        m1 = R.get_or_create_motif_member(conn, entry, recs[1], 2000, 2080)
        m2 = R.get_or_create_motif_member(conn, entry, recs[0], 4590, 4670)
        try:
            yield conn, (m0, m1, m2), recs
        finally:
            conn.close()


def _members(conn, ids):
    marks = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT id, recording_id, start_idx, end_idx FROM motif_member WHERE id IN ({marks})",
                        list(ids)).fetchall()
    return [{"member_id": r["id"], "recording_id": r["recording_id"], "start_idx": r["start_idx"],
             "end_idx": r["end_idx"]} for r in rows]


def _queue(conn, ids, family="F-01"):
    return fq.create_family_queue(conn, family=family, member_ids=ids, grouping="g-01")


def test_the_queue_is_made_through_create_queue_and_names_the_family(fam):
    conn, ids, _ = fam
    qid = _queue(conn, ids)
    row = Q.get_queue(conn, qid)
    assert row["source_kind"] == fq.SOURCE_KIND == "library-family"
    assert row["name"] == "Library · F-01 unjudged"
    assert row["unit"] == "member" and row["writes_to"] == "annotations" and not row["blind"]
    assert row["verdict_options"] == ["interesting", "not_interesting", "artifact", "unsure"]
    assert set(row["verdict_options"]) <= set(VERDICTS)        # no sixth word
    assert row["filters"]["family"] == "F-01" and row["filters"]["grouping"] == "g-01"
    assert _queue(conn, ids) == qid                             # a second send returns the same queue


def test_its_items_are_the_members_sent_each_unjudged(fam):
    conn, (m0, m1, m2), recs = fam
    qid = _queue(conn, [m0, m1, m2])
    items = Q.queue_items(conn, qid)
    assert sorted(it["target_id"] for it in items) == [m0, m1, m2]
    it = next(i for i in items if i["target_id"] == m1)
    assert it["unit"] == "member" and it["member_id"] == m1 and it["family"] == "F-01"
    assert it["recording_id"] == recs[1] and (it["start_idx"], it["end_idx"]) == (2000, 2080)
    assert it["judged"] is False and it["verdict"] is None
    assert Q.queue_counts(conn, qid) == {"total": 3, "judged": 0, "remaining": 3}


def test_a_verdict_lands_in_annotations_and_the_family_page_counts_it_judged(fam):
    conn, (m0, m1, m2), recs = fam
    assert not any(v["judged"] for v in LV.member_verdicts(conn, _members(conn, [m0, m1, m2])).values())
    qid = _queue(conn, [m0, m1, m2])
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("motif_member", "motif_edge", "motif_member_cooccurrence", "adjudications", "motif_entry")}
    out = V.write_verdict(conn, qid, m0, "interesting", note="a clean one")
    ann = q.get_annotation(conn, out["row_id"])
    assert (ann["recording_id"], ann["start_idx"], ann["end_idx"]) == (recs[0], 990, 1070)
    assert ann["verdict"] == "interesting" and ann["source"] == fq.REVIEW_SOURCE
    assert "F-01" in ann["note"] and f"m-{m0}" in ann["note"] and "a clean one" in ann["note"]
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
    assert after == before                                      # rule 5: no machine table touched
    # the Family page's resolver now says judged, by the event-shaped row the member matches
    res = LV.member_verdicts(conn, _members(conn, [m0, m1, m2]))
    assert res[m0]["judged"] is True and res[m0]["verdict"] == "interesting" and res[m0]["by"] == "extent"
    assert res[m1]["judged"] is False and res[m2]["judged"] is False
    assert Q.queue_counts(conn, qid) == {"total": 3, "judged": 1, "remaining": 2}
    it = next(i for i in Q.queue_items(conn, qid, include_judged=True) if i["target_id"] == m0)
    assert it["judged"] is True and it["verdict"] == "interesting"


def test_a_verdict_given_elsewhere_counts_as_judged_in_the_queue_too(fam):
    """A queue holds no verdicts of its own: a human row over the member's
    span from anywhere (Explore, another queue) is the member's verdict."""
    conn, (m0, m1, m2), recs = fam
    qid = _queue(conn, [m0, m1, m2])
    q.insert_annotation(conn, recs[1], 2000, 2080, "not_interesting", source="explore")
    conn.commit()
    assert Q.queue_counts(conn, qid) == {"total": 3, "judged": 1, "remaining": 2}
    it = next(i for i in Q.queue_items(conn, qid, include_judged=True) if i["target_id"] == m1)
    assert it["verdict"] == "not_interesting"


def test_unsure_is_answered_in_the_queue_but_not_judged_on_the_family_page(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    V.write_verdict(conn, qid, m1, "unsure")
    it = next(i for i in Q.queue_items(conn, qid, include_judged=True) if i["target_id"] == m1)
    assert it["judged"] is True and it["verdict"] == "unsure"   # not asked again
    assert Q.queue_counts(conn, qid)["judged"] == 1
    res = LV.member_verdicts(conn, _members(conn, [m1]))
    assert res[m1]["judged"] is False                           # the resolver gives unsure no side


def test_a_second_verdict_redescribes_the_same_row_and_undo_walks_back(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    first = V.write_verdict(conn, qid, m0, "interesting")
    second = V.write_verdict(conn, qid, m0, "artifact")
    assert second["row_id"] == first["row_id"]
    assert q.get_annotation(conn, first["row_id"])["verdict"] == "artifact"
    n = conn.execute("SELECT COUNT(*) FROM annotations WHERE source = ?", (fq.REVIEW_SOURCE,)).fetchone()[0]
    assert n == 1
    V.undo_last(conn, qid)
    assert q.get_annotation(conn, first["row_id"])["verdict"] == "interesting"
    V.undo_last(conn, qid)
    gone = conn.execute("SELECT deleted_at FROM annotations WHERE id = ?", (first["row_id"],)).fetchone()
    assert gone["deleted_at"] is not None                       # the inserted row is withdrawn, not left behind
    assert fq.member_verdicts(conn, [m0]) == {}
    assert Q.queue_counts(conn, qid) == {"total": 3, "judged": 0, "remaining": 3}


def test_seed_is_not_this_queues_question(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, m0, "seed")
    assert fq.member_verdicts(conn, [m0]) == {}


def test_a_member_the_queue_never_listed_is_refused(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1])
    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, m2, "interesting")


def test_batch_writes_one_audit_row(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    out = V.write_batch(conn, qid, [m0, m1], "not_interesting")
    assert out["count"] == 2
    assert fq.member_verdicts(conn, [m0, m1]) == {m0: "not_interesting", m1: "not_interesting"}
    assert conn.execute("SELECT COUNT(*) FROM review_audit WHERE queue_id = ?", (qid,)).fetchone()[0] == 1


def test_a_second_send_with_more_members_widens_the_one_queue(fam):
    """A member added by hand after the first send joins the family's queue
    rather than opening a second one over the same family."""
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1])
    assert _queue(conn, [m1, m2]) == qid
    assert sorted(it["target_id"] for it in Q.queue_items(conn, qid)) == [m0, m1, m2]
    assert fq.open_family_queue(conn, "F-01") == qid
    assert fq.open_family_queue(conn, "F-02") is None
    assert len(Q.list_queues(conn)) == 1


def _review_queues_before_this_kind(conn):
    """The table as fixup-AH left it: names `blind-test`, not `library-family`."""
    conn.executescript("""
        DROP TABLE IF EXISTS review_queues;
        CREATE TABLE review_queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            source_kind TEXT NOT NULL CHECK (source_kind IN ('discovery-run', 'seed-search', 'explore-spans',
                'training-windows', 'model-verification', 'extract-events', 'suspected-artifact', 'blind-test')),
            source_ref TEXT,
            unit TEXT NOT NULL CHECK (unit IN ('detection', 'human span', 'window', 'sequence', 'member',
                'test window')),
            writes_to TEXT NOT NULL CHECK (writes_to IN ('adjudications', 'annotations', 'window_verdicts')),
            blind INTEGER NOT NULL DEFAULT 0, cap INTEGER, verdict_options TEXT, filters_json TEXT,
            created_at TEXT NOT NULL, closed_at TEXT, note TEXT);
        INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at)
            VALUES ('old one', 'suspected-artifact', 'member', 'annotations', '2026-10-05');
    """)
    conn.commit()


def test_the_queue_table_learns_the_kind_and_keeps_its_rows():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "db.sqlite")
        conn = init_db(path)
        _review_queues_before_this_kind(conn)
        conn.execute("INSERT INTO review_audit (queue_id, action, created_at) VALUES (1, 'verdict', 'x')")
        conn.commit()
        conn.close()
        conn = init_db(path)                                    # the migration runs
        try:
            assert conn.execute("SELECT name FROM review_queues WHERE id = 1").fetchone()[0] == "old one"
            conn.execute("INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at) "
                         "VALUES ('new', 'library-family', 'member', 'annotations', 'x')")
            assert conn.execute("SELECT COUNT(*) FROM review_audit").fetchone()[0] == 1
            backups = [f for f in os.listdir(tmp) if "review-queues" in f]
            assert backups, "the file is backed up before the rebuild"
        finally:
            conn.close()
        conn = init_db(path)                                    # and a second start does nothing
        try:
            assert len([f for f in os.listdir(tmp) if "review-queues" in f]) == len(backups)
        finally:
            conn.close()

"""
test_review_suspected_artifact.py
=================================
fixup-AD §4: the machine only FLAGS a suspected artifact; a human decides, in a
Review queue made through `create_queue`.

- The queue is a `suspected-artifact` source kind whose items are the family
  members the cross-channel classifier flagged, resolved live.
- **The verdict is a human row (rule 5)**, in `annotations` over the member's
  span — the Library's members are mostly imported and have no detection, and a
  member from a run already carries the accepting adjudication that made it a
  member (Q39, one per detection), which an artifact verdict would overwrite.
  Never on `motif_member`, `motif_edge` or `motif_member_cooccurrence`.
- **The vocabulary stays at five words** (researcher, 2026-10-05): the reviewer
  answers *artifact*, or what the span really is (*interesting* /
  *not_interesting*), or *unsure*; every row carries a note saying it was
  flagged as a suspected artifact.
- The queue table's CHECK learns the new kind through an idempotent rebuild
  that keeps every row.
"""

import json
import os
import sqlite3
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
from Working.library import matching
from Working.review import artifact_queue as aq
from Working.review import queues as Q
from Working.review import verdicts as V

PULSE_N = 60


def _pulse():
    u = np.linspace(0.0, 2.0 * np.pi, PULSE_N)
    return -np.sin(u) * np.hanning(PULSE_N)


def _channel(n, plants, seed, noise=0.01):
    x = np.random.default_rng(seed).standard_normal(n) * noise
    for at, sign in plants:
        x[at:at + PULSE_N] += sign * _pulse()
    return x


@pytest.fixture
def fam():
    """Three members on one recording: m0/m1 a simultaneous copy (both
    flagged), m2 an independent event an hour later (not flagged)."""
    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(":memory:")
        recs = []
        for ch, plants in enumerate(([(1000, 1)], [(1000, 1)], [(4600, 1)])):
            path = os.path.join(tmp, f"ch{ch}.npy")
            np.save(path, _channel(8000, plants, seed=ch))
            rid = q.insert_recording(conn, "a.mat", ch, 1.0, 8000, 0, path)
            conn.execute("UPDATE recordings SET units = 'mV' WHERE id = ?", (rid,))
            recs.append(rid)
        conn.commit()
        entry = R.insert_motif_entry(conn, recs[0], 990, 1070)
        m0 = R.get_or_create_motif_member(conn, entry, recs[0], 990, 1070)
        m1 = R.get_or_create_motif_member(conn, entry, recs[1], 990, 1070)
        m2 = R.get_or_create_motif_member(conn, entry, recs[2], 4590, 4670)
        matching.classify_family_across_channels(conn, [m0, m1, m2])
        try:
            yield conn, (m0, m1, m2), recs
        finally:
            conn.close()


def _queue(conn, ids, family="F-01"):
    return aq.create_artifact_queue(conn, family=family, member_ids=ids, grouping="g-01")


def test_the_queue_is_made_through_create_queue_and_names_the_family(fam):
    conn, ids, _ = fam
    qid = _queue(conn, ids)
    row = Q.get_queue(conn, qid)
    assert row["source_kind"] == aq.SOURCE_KIND == "suspected-artifact"
    assert row["name"] == "Suspected artifact · F-01"
    assert row["unit"] == "member" and row["writes_to"] == "annotations"
    assert row["verdict_options"] == ["artifact", "interesting", "not_interesting", "unsure"]
    assert set(row["verdict_options"]) <= set(VERDICTS)        # no sixth word
    assert _queue(conn, ids) == qid                             # a second send returns the same queue


def test_its_items_are_the_flagged_members_with_what_flagged_them(fam):
    conn, (m0, m1, m2), recs = fam
    qid = _queue(conn, [m0, m1, m2])
    items = Q.queue_items(conn, qid)
    assert sorted(it["target_id"] for it in items) == [m0, m1]
    it = next(i for i in items if i["target_id"] == m0)
    assert it["recording_id"] == recs[0] and (it["start_idx"], it["end_idx"]) == (990, 1070)
    flag = it["flags"][0]
    assert flag["recording_id"] == recs[1]
    assert abs(flag["r"]) >= 0.98 and abs(flag["lag_s"]) <= 1.0
    assert flag["chance"]["k"] == 100 and flag["chance"]["percentile"] > 95
    assert flag["amplitude_ratio"] == pytest.approx(1.0, abs=0.2)
    assert Q.queue_counts(conn, qid) == {"total": 2, "judged": 0, "remaining": 2}


def test_a_verdict_lands_in_annotations_over_the_members_span_with_the_note(fam):
    conn, (m0, m1, m2), recs = fam
    qid = _queue(conn, [m0, m1, m2])
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("motif_member", "motif_edge", "motif_member_cooccurrence", "adjudications")}
    out = V.write_verdict(conn, qid, m0, "artifact", note="looks like the ground")
    ann = q.get_annotation(conn, out["row_id"])
    assert (ann["recording_id"], ann["start_idx"], ann["end_idx"]) == (recs[0], 990, 1070)
    assert ann["verdict"] == "artifact" and ann["source"] == aq.REVIEW_SOURCE
    assert "flagged as a suspected artifact" in ann["note"] and "looks like the ground" in ann["note"]
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
    assert after == before                                      # rule 5: no machine table touched
    assert Q.queue_counts(conn, qid) == {"total": 2, "judged": 1, "remaining": 1}


def test_a_second_verdict_redescribes_the_same_row_and_undo_walks_back(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    first = V.write_verdict(conn, qid, m0, "artifact")
    second = V.write_verdict(conn, qid, m0, "not_interesting")
    assert second["row_id"] == first["row_id"]
    assert q.get_annotation(conn, first["row_id"])["verdict"] == "not_interesting"
    V.undo_last(conn, qid)
    assert q.get_annotation(conn, first["row_id"])["verdict"] == "artifact"
    V.undo_last(conn, qid)
    gone = conn.execute("SELECT deleted_at FROM annotations WHERE id = ?", (first["row_id"],)).fetchone()
    assert gone["deleted_at"] is not None                       # the inserted row is withdrawn, not left behind
    assert aq.member_verdicts(conn, [m0]) == {}


def test_a_member_the_queue_never_listed_is_refused(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, m2, "artifact")              # not flagged: never asked


def test_seed_is_not_this_queues_question(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    with pytest.raises(ValueError):
        V.write_verdict(conn, qid, m0, "seed")
    assert aq.member_verdicts(conn, [m0]) == {}


def test_batch_writes_one_audit_row(fam):
    conn, (m0, m1, m2), _ = fam
    qid = _queue(conn, [m0, m1, m2])
    out = V.write_batch(conn, qid, [m0, m1], "artifact")
    assert out["count"] == 2
    assert aq.member_verdicts(conn, [m0, m1]) == {m0: "artifact", m1: "artifact"}
    assert conn.execute("SELECT COUNT(*) FROM review_audit WHERE queue_id = ?", (qid,)).fetchone()[0] == 1


def test_recurrence_moves_by_exactly_the_confirmed_ones(fam):
    conn, (m0, m1, m2), _ = fam
    ids = [m0, m1, m2]
    qid = _queue(conn, ids)
    assert matching.family_recurrence(conn, ids)["excluding_artifacts"] == 3
    V.write_verdict(conn, qid, m0, "artifact")
    rec = matching.family_recurrence(conn, ids)
    assert rec["confirmed"] == 1
    assert rec["excluding_artifacts"] == 1                      # m0 and its member twin m1 (Q40d-2)


def _old_review_queues(conn):
    """The table as `W` left it: the six kinds, the four units."""
    conn.executescript("""
        DROP TABLE IF EXISTS review_queues;
        CREATE TABLE review_queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            source_kind TEXT NOT NULL CHECK (source_kind IN ('discovery-run', 'seed-search', 'explore-spans',
                'training-windows', 'model-verification', 'extract-events')),
            source_ref TEXT,
            unit TEXT NOT NULL CHECK (unit IN ('detection', 'human span', 'window', 'sequence')),
            writes_to TEXT NOT NULL CHECK (writes_to IN ('adjudications', 'annotations', 'window_verdicts')),
            blind INTEGER NOT NULL DEFAULT 0, cap INTEGER, verdict_options TEXT, filters_json TEXT,
            created_at TEXT NOT NULL, closed_at TEXT, note TEXT);
        INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at)
            VALUES ('old one', 'discovery-run', 'detection', 'adjudications', '2026-10-01');
    """)
    conn.commit()


def test_the_queue_table_learns_the_new_kind_and_keeps_its_rows():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "db.sqlite")
        conn = init_db(path)
        _old_review_queues(conn)
        conn.execute("INSERT INTO review_audit (queue_id, action, created_at) VALUES (1, 'verdict', 'x')")
        conn.commit()
        conn.close()
        conn = init_db(path)                                    # the migration runs
        try:
            assert conn.execute("SELECT name FROM review_queues WHERE id = 1").fetchone()[0] == "old one"
            conn.execute("INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at) "
                         "VALUES ('new', 'suspected-artifact', 'member', 'annotations', 'x')")
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

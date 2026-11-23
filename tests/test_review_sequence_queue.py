"""
test_review_sequence_queue.py
==============================
The *sequence review* queue (2026-11-23, the researcher): "is this span a sequence?", asked once per candidate,
in Review, with an accepted sequence stored as a sequence in the Library.

- **A candidate is a machine claim.** Chains of neighbouring accepted events, spans holding several falls, and
  any tool's proposals (Auto-detect) arrive as `sequences` rows with `origin = 'machine'` and the events that
  make them up as `sequence_members` - the importer's one INSERT (`importers.sequences.insert_sequence`). The
  researcher's hand-labelled sequences (`origin = 'human'`, from the Excel catalogue) join the same queue by id.
- **The verdict is a person's - `annotations`, over the sequence's span** (rule 5: nothing here writes a machine
  row). On a candidate it is a NEW annotation (source `sequence_review`, `event_count` = its events); on a
  hand-labelled sequence it re-describes that sequence's own annotation in place.
- **Accepting stores the sequence.** `interesting` on a candidate also writes a `sequences` row with
  `origin = 'human'`, pointing at the verdict's annotation and flagged `needs_extraction = 1`: the Library now
  holds a human sequence whose single events are still to be resolved. Rejecting stores none, re-judging an
  accepted one as not a sequence takes it out, and undo walks every step back.
- **Five words, minus `seed`**: a seed is a single event; a sequence is accepted as `interesting`.
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
from Working.database.schema import init_db
from Working.review import queues as Q
from Working.review import sequence_queue as sq
from Working.review import verdicts as V

N = 20000


@pytest.fixture
def db():
    """Two channels; one hand-labelled sequence (human origin, its own annotation, events not yet extracted)."""
    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(":memory:")
        recs = []
        for ch in range(2):
            path = os.path.join(tmp, f"ch{ch}.npy")
            np.save(path, np.random.default_rng(ch).standard_normal(N) * 0.01)
            recs.append(q.insert_recording(conn, "a.mat", ch, 1.0, N, 0, path))
        aid = q.insert_annotation(conn, recs[0], 12000, 15000, "interesting", "excel_catalog",
                                  note="16 cycles", event_count=16, commit=False)
        conn.execute("INSERT INTO sequences (sequence_key, origin, recording_id, channel, start_idx, end_idx, "
                     "n_events, needs_extraction, source_kind, annotation_id, created_at) "
                     "VALUES ('human_r1_ch0_12000s', 'human', ?, 0, 12000, 15000, 16, 1, 'annotation', ?, 'x')",
                     (recs[0], aid))
        conn.commit()
        human = conn.execute("SELECT id FROM sequences WHERE origin = 'human'").fetchone()[0]
        try:
            yield conn, recs, human, aid
        finally:
            conn.close()


def _chain(rec, start=1000, n=5, period=300, width=60):
    """A candidate made of `n` events `period` samples apart."""
    events = [{"start_idx": start + k * period, "end_idx": start + k * period + width} for k in range(n)]
    return {"recording_id": rec, "start_idx": events[0]["start_idx"], "end_idx": events[-1]["end_idx"],
            "events": events, "note": "5 accepted events, next onset within 1 h"}


def _send(conn, spans=(), sequence_ids=(), provenance="chain_1h"):
    return sq.send_to_sequence_review(conn, spans=list(spans), sequence_ids=list(sequence_ids),
                                      provenance=provenance, name="Sequences · test")


def _items(conn, qid):
    return {it["target_id"]: it for it in Q.queue_items(conn, qid, include_judged=True)}


def test_a_send_registers_machine_candidates_with_their_events_and_makes_one_queue(db):
    conn, recs, human, _ = db
    out = _send(conn, spans=[_chain(recs[0]), _chain(recs[1], start=4000, n=3)])
    queue = Q.get_queue(conn, out["queue_id"])
    assert (queue["source_kind"], queue["unit"], queue["writes_to"]) == ("sequence-review", "sequence", "annotations")
    assert queue["verdict_options"] == ["interesting", "not_interesting", "artifact", "unsure"]
    assert len(out["sequence_ids"]) == 2 and out["created"] == 2
    row = conn.execute("SELECT * FROM sequences WHERE id = ?", (out["sequence_ids"][0],)).fetchone()
    assert row["origin"] == "machine" and row["annotation_id"] is None
    assert (row["recording_id"], row["start_idx"], row["end_idx"], row["n_events"]) == (recs[0], 1000, 2260, 5)
    assert row["needs_extraction"] == 0 and row["source_kind"] == "chain_1h"
    members = conn.execute("SELECT position, start_idx, end_idx, gap_before, member_id FROM sequence_members "
                           "WHERE sequence_id = ? ORDER BY position", (row["id"],)).fetchall()
    assert [tuple(m) for m in members] == [(0, 1000, 1060, None, None), (1, 1300, 1360, 300.0, None),
                                           (2, 1600, 1660, 300.0, None), (3, 1900, 1960, 300.0, None),
                                           (4, 2200, 2260, 300.0, None)]


def test_a_second_send_widens_the_one_queue_and_never_duplicates_a_candidate(db):
    conn, recs, human, _ = db
    first = _send(conn, spans=[_chain(recs[0])])
    again = _send(conn, spans=[_chain(recs[0]), _chain(recs[1], start=4000)], sequence_ids=[human])
    assert again["queue_id"] == first["queue_id"]
    assert again["created"] == 1 and again["sequence_ids"][0] == first["sequence_ids"][0]
    assert conn.execute("SELECT COUNT(*) FROM sequences WHERE origin = 'machine'").fetchone()[0] == 2
    assert set(_items(conn, first["queue_id"])) == {*again["sequence_ids"], human}
    assert conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0] == 1


def test_items_carry_the_span_its_events_and_where_it_came_from(db):
    conn, recs, human, _ = db
    out = _send(conn, spans=[_chain(recs[0])], sequence_ids=[human])
    items = _items(conn, out["queue_id"])
    cand = items[out["sequence_ids"][0]]
    assert cand["unit"] == "sequence" and cand["origin"] == "machine" and cand["provenance"] == "chain_1h"
    assert (cand["recording_id"], cand["start_idx"], cand["end_idx"], cand["n_events"]) == (recs[0], 1000, 2260, 5)
    assert cand["member_spans"] == [[1000, 1060], [1300, 1360], [1600, 1660], [1900, 1960], [2200, 2260]]
    assert len(cand["members"]) == 5 and not cand["judged"] and cand["verdict"] is None
    hand = items[human]
    assert hand["origin"] == "human" and hand["n_events"] == 16 and not hand["judged"]
    assert hand["catalogue_verdict"] == "interesting"     # what the catalogue said, shown; not this queue's answer
    assert hand.get("prior_verdict") is None              # which would mean "judged elsewhere, do not ask"


def test_accepting_a_candidate_stores_a_human_sequence_over_a_new_annotation(db):
    conn, recs, _, _ = db
    out = _send(conn, spans=[_chain(recs[0])])
    sid = out["sequence_ids"][0]
    w = V.write_verdict(conn, out["queue_id"], sid, "interesting", note="clean train")
    ann = conn.execute("SELECT * FROM annotations WHERE id = ?", (w["row_id"],)).fetchone()
    assert (ann["recording_id"], ann["start_idx"], ann["end_idx"]) == (recs[0], 1000, 2260)
    assert ann["verdict"] == "interesting" and ann["source"] == "sequence_review" and ann["event_count"] == 5
    assert "clean train" in ann["note"]
    stored = conn.execute("SELECT * FROM sequences WHERE origin = 'human' AND annotation_id = ?",
                          (w["row_id"],)).fetchone()
    assert stored is not None and stored["needs_extraction"] == 1 and stored["n_events"] == 5
    assert (stored["recording_id"], stored["start_idx"], stored["end_idx"]) == (recs[0], 1000, 2260)
    assert stored["source_kind"] == "sequence_review" and stored["source_ref"] == str(sid)
    assert conn.execute("SELECT annotation_id FROM sequences WHERE id = ?", (sid,)).fetchone()[0] is None
    item = _items(conn, out["queue_id"])[sid]
    assert item["judged"] and item["verdict"] == "interesting"
    assert sq.accepted_sequences(conn) == [stored["id"]]


def test_rejecting_a_candidate_records_the_verdict_and_stores_no_sequence(db):
    conn, recs, _, _ = db
    out = _send(conn, spans=[_chain(recs[0])])
    w = V.write_verdict(conn, out["queue_id"], out["sequence_ids"][0], "not_interesting")
    assert conn.execute("SELECT verdict FROM annotations WHERE id = ?", (w["row_id"],)).fetchone()[0] == "not_interesting"
    assert conn.execute("SELECT COUNT(*) FROM sequences WHERE origin = 'human' AND source_kind = 'sequence_review'"
                        ).fetchone()[0] == 0
    assert _items(conn, out["queue_id"])[out["sequence_ids"][0]]["judged"]


def test_rejudging_an_accepted_sequence_takes_it_out_and_undo_puts_it_back(db):
    conn, recs, _, _ = db
    out = _send(conn, spans=[_chain(recs[0])])
    qid, sid = out["queue_id"], out["sequence_ids"][0]
    first = V.write_verdict(conn, qid, sid, "interesting")
    stored = conn.execute("SELECT id FROM sequences WHERE annotation_id = ?", (first["row_id"],)).fetchone()[0]
    second = V.write_verdict(conn, qid, sid, "not_interesting")
    assert second["row_id"] == first["row_id"]                      # the same row, re-described
    assert conn.execute("SELECT COUNT(*) FROM sequences WHERE id = ?", (stored,)).fetchone()[0] == 0
    V.undo_last(conn, qid)
    back = conn.execute("SELECT * FROM sequences WHERE id = ?", (stored,)).fetchone()
    assert back is not None and back["annotation_id"] == first["row_id"] and back["origin"] == "human"
    assert conn.execute("SELECT verdict FROM annotations WHERE id = ?", (first["row_id"],)).fetchone()[0] == "interesting"


def test_undo_of_an_accept_withdraws_the_annotation_and_the_stored_sequence(db):
    conn, recs, _, _ = db
    out = _send(conn, spans=[_chain(recs[0])])
    qid, sid = out["queue_id"], out["sequence_ids"][0]
    w = V.write_verdict(conn, qid, sid, "interesting")
    V.undo_last(conn, qid)
    assert conn.execute("SELECT deleted_at FROM annotations WHERE id = ?", (w["row_id"],)).fetchone()[0] is not None
    assert conn.execute("SELECT COUNT(*) FROM sequences WHERE origin = 'human' AND source_kind = 'sequence_review'"
                        ).fetchone()[0] == 0
    item = _items(conn, qid)[sid]
    assert not item["judged"] and item["verdict"] is None


def test_a_hand_labelled_sequence_is_rejudged_in_place(db):
    conn, recs, human, aid = db
    out = _send(conn, sequence_ids=[human])
    n_ann = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
    w = V.write_verdict(conn, out["queue_id"], human, "not_interesting")
    assert w["row_id"] == aid
    assert conn.execute("SELECT verdict FROM annotations WHERE id = ?", (aid,)).fetchone()[0] == "not_interesting"
    assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == n_ann
    assert conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0] == 1     # nothing stored, nothing removed
    assert _items(conn, out["queue_id"])[human]["judged"]
    V.undo_last(conn, out["queue_id"])
    assert conn.execute("SELECT verdict FROM annotations WHERE id = ?", (aid,)).fetchone()[0] == "interesting"
    assert not _items(conn, out["queue_id"])[human]["judged"]


def test_seed_is_not_this_queues_question(db):
    conn, recs, _, _ = db
    out = _send(conn, spans=[_chain(recs[0])])
    with pytest.raises(ValueError):
        V.write_verdict(conn, out["queue_id"], out["sequence_ids"][0], "seed")
    assert conn.execute("SELECT COUNT(*) FROM review_audit").fetchone()[0] == 0


def test_a_sequence_the_queue_never_listed_is_refused(db):
    conn, recs, human, _ = db
    out = _send(conn, spans=[_chain(recs[0])])
    with pytest.raises(ValueError):
        V.write_verdict(conn, out["queue_id"], human, "interesting")


def test_a_batch_writes_one_audit_row_and_one_undo_takes_it_all_back(db):
    conn, recs, _, _ = db
    out = _send(conn, spans=[_chain(recs[0]), _chain(recs[1], start=4000)])
    qid = out["queue_id"]
    b = V.write_batch(conn, qid, out["sequence_ids"], "interesting")
    assert b["count"] == 2
    assert conn.execute("SELECT COUNT(*) FROM review_audit WHERE queue_id = ?", (qid,)).fetchone()[0] == 1
    assert len(sq.accepted_sequences(conn)) == 2
    V.undo_last(conn, qid)
    assert sq.accepted_sequences(conn) == []


def test_an_accepted_sequence_waits_in_the_extract_events_queue(db):
    """Accepted, its single events not yet resolved: the honest `needs_extraction = 1` state, which is what the
    Library's extract-events queue lists."""
    conn, recs, human, _ = db
    out = _send(conn, spans=[_chain(recs[0])])
    V.write_verdict(conn, out["queue_id"], out["sequence_ids"][0], "interesting")
    ex = Q.create_queue(conn, name="extract", source_kind="extract-events")
    stored = sq.accepted_sequences(conn)[0]
    assert {it["target_id"] for it in Q.queue_items(conn, ex, include_judged=True)} == {human, stored}


def test_a_candidate_with_no_events_listed_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(":memory:")
        path = os.path.join(tmp, "ch.npy")
        np.save(path, np.zeros(100))
        rec = q.insert_recording(conn, "a.mat", 0, 1.0, 100, 0, path)
        with pytest.raises(ValueError):
            sq.send_to_sequence_review(conn, spans=[{"recording_id": rec, "start_idx": 0, "end_idx": 50,
                                                     "events": []}], provenance="x", name="q")
        with pytest.raises(ValueError):                         # an event outside the candidate's own span
            sq.send_to_sequence_review(conn, spans=[{"recording_id": rec, "start_idx": 0, "end_idx": 50,
                                                     "events": [{"start_idx": 10, "end_idx": 20},
                                                                {"start_idx": 40, "end_idx": 60}]}],
                                       provenance="x", name="q")
        conn.close()


def _review_queues_before_this_kind(conn):
    """The table as fixup-FQ left it: names `library-family`, not `sequence-review`."""
    conn.executescript("""
        DROP TABLE IF EXISTS review_queues;
        CREATE TABLE review_queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            source_kind TEXT NOT NULL CHECK (source_kind IN ('discovery-run', 'seed-search', 'explore-spans',
                'training-windows', 'model-verification', 'extract-events', 'suspected-artifact', 'blind-test',
                'library-family')),
            source_ref TEXT,
            unit TEXT NOT NULL CHECK (unit IN ('detection', 'human span', 'window', 'sequence', 'member',
                'test window')),
            writes_to TEXT NOT NULL CHECK (writes_to IN ('adjudications', 'annotations', 'window_verdicts')),
            blind INTEGER NOT NULL DEFAULT 0, cap INTEGER, verdict_options TEXT, filters_json TEXT,
            created_at TEXT NOT NULL, closed_at TEXT, note TEXT);
        INSERT INTO review_queues (name, source_kind, unit, writes_to, created_at)
            VALUES ('old one', 'library-family', 'member', 'annotations', '2026-10-09');
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
                         "VALUES ('new', 'sequence-review', 'sequence', 'annotations', 'x')")
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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

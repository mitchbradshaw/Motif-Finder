"""
test_sequence_shape.py
========================
The rose over a sequence (fixup-d, seam 4). `gradients.rose_data`'s default
split is an analysed span, not a sequence; the researcher wants the steepest
slopes compared ACROSS THE EVENTS OF ONE SEQUENCE. Sequences live in the
`sequences` / `sequence_members` tables (no `motif_entry` has `scale='train'`),
so the rose keys off `sequences`.

`Working.interrogation.sequences.sequence_shape` reads a sequence's members in
position order, takes each member's per-event features from `motif_features`
where they are stored (and measures them from the Library snippet, saying so,
where they are not), and hands the rose to `gradients.rose_data` with the
sequence key as the group. It stores nothing: a comparison is a view.

Runnable standalone:  python tests/test_sequence_shape.py
"""

import datetime
import os
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.library import features as F  # noqa: E402
from Working.library.identity import content_hash  # noqa: E402

SEED_REL = "DATA/library_seed/drop_motifs5/motifs"
SEED = os.path.join(PROJECT_ROOT, *SEED_REL.split("/"))
pytestmark = pytest.mark.skipif(not os.path.isfile(os.path.join(SEED, "events.csv")),
                                reason="the tracked seed store is not on this machine")


def _build(conn, event_ids):
    from Working.Detection.drop_motifs import store as S
    events = {e["event_id"]: e for e in S.load_events(SEED)}
    snippets = S.load_snippets(SEED)
    rid = q.insert_recording(conn, "M2_aug_concat_fs1.mat", 0, 1.0, 3_000_000, 0, "nowhere.npy", units="V")
    now = datetime.datetime.now().isoformat()
    seq = conn.execute("INSERT INTO sequences (sequence_key, origin, recording_id, channel, n_events, created_at) "
                       "VALUES ('oyster_test', 'machine', ?, 0, ?, ?)", (rid, len(event_ids), now)).lastrowid
    hashes = []
    prev = None
    for pos, ev in enumerate(event_ids):
        e = events[ev]
        h = content_hash(snippets[ev]["detrended_mv"])
        hashes.append(h)
        s, t = int(e["snippet_start_idx"]), int(e["snippet_end_idx"])
        entry = conn.execute(
            "INSERT INTO motif_entry (recording_id, start_idx, end_idx, content_hash, source_kind, source_store, "
            "source_ref, fs, created_at) VALUES (?, ?, ?, ?, 'event_store', ?, ?, 1.0, ?)",
            (rid, s, t, h, SEED_REL, ev, now)).lastrowid
        member = conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, content_hash, "
                              "channel) VALUES (?, ?, ?, ?, ?, 0)", (entry, rid, s, t, h)).lastrowid
        onset = int(e["onset_idx"])
        conn.execute("INSERT INTO sequence_members (sequence_id, position, member_id, start_idx, end_idx, gap_before) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (seq, pos, member, s, t, None if prev is None else float(onset - prev)))
        prev = onset
    conn.commit()
    return seq, hashes


@pytest.fixture
def conn():
    d = tempfile.mkdtemp(prefix="seq_shape_")
    c = init_db(os.path.join(d, "t.sqlite"))
    yield c
    c.close()


IDS = ["id001_r1_1213252"]


def _first_ids(n):
    from Working.Detection.drop_motifs import store as S
    return [e["event_id"] for e in S.load_events(SEED) if e["span_key"] == "id001"][:n]


def test_the_rose_is_split_by_the_sequence(conn):
    from Working.interrogation.sequences import sequence_shape
    seq, _ = _build(conn, _first_ids(6))
    out = sequence_shape(conn, seq, repo_root=PROJECT_ROOT)
    assert out["sequence"]["sequence_key"] == "oyster_test" and out["sequence"]["n_members"] == 6
    rose = out["rose"]
    assert rose["n"] == 6 and sum(rose["counts"]) == 6
    assert list(rose["groups"]) == ["oyster_test"]
    g = rose["groups"]["oyster_test"]
    assert {"mean_deg", "resultant_length", "circular_sd_deg", "uniformity_p"} <= set(g)
    assert rose["caption"].startswith("45°")


def test_events_come_in_position_order_with_their_gap(conn):
    from Working.interrogation.sequences import sequence_shape
    seq, hashes = _build(conn, _first_ids(4))
    ev = sequence_shape(conn, seq, repo_root=PROJECT_ROOT)["events"]
    assert [e["position"] for e in ev] == [0, 1, 2, 3]
    assert [e["content_hash"] for e in ev] == hashes
    assert ev[0]["gap_before_s"] is None and ev[1]["gap_before_s"] > 0


def test_stored_features_are_used_and_missing_ones_are_measured_and_flagged(conn):
    from Working.interrogation.sequences import sequence_shape
    seq, hashes = _build(conn, _first_ids(3))
    F.backfill_library(conn, repo_root=PROJECT_ROOT)
    conn.execute("DELETE FROM motif_features WHERE content_hash = ?", (hashes[2],))
    conn.commit()
    ev = sequence_shape(conn, seq, repo_root=PROJECT_ROOT)["events"]
    assert [e["stored"] for e in ev] == [True, True, False]
    assert all("max_slope_mv_s" in e["features"] for e in ev)


def test_the_comparison_is_never_stored(conn):
    from Working.interrogation.sequences import sequence_shape
    seq, _ = _build(conn, _first_ids(3))
    before = conn.execute("SELECT COUNT(*) FROM motif_features").fetchone()[0]
    sequence_shape(conn, seq, repo_root=PROJECT_ROOT)
    assert conn.execute("SELECT COUNT(*) FROM motif_features").fetchone()[0] == before


def test_an_unknown_sequence_is_a_clear_error(conn):
    from Working.interrogation.sequences import sequence_shape
    with pytest.raises(LookupError, match="sequence 999"):
        sequence_shape(conn, 999, repo_root=PROJECT_ROOT)


def test_list_sequences_counts_members(conn):
    from Working.interrogation.sequences import list_sequences
    seq, _ = _build(conn, _first_ids(3))
    rows = list_sequences(conn)
    assert [(r["id"], r["n_members"]) for r in rows] == [(seq, 3)]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

"""
test_library_sequences.py
=========================
`Working/library/sequences.py` — sequences built from adjacent Library members
(the 2026-10-18 grilling): one channel's ordered run of MEMBERS (motifs that
carry a family label), joined while the gap between one member's end and the
next one's start is under a limit.

Pinned here:

* the fixed rule's default — 0 s with a tolerance of 10 % of the shorter
  member's length — joins touching members and refuses a pair 20 % apart;
* `min_len` holds;
* the two adaptive rules (`adamatzky`, `logisi`) group exactly as
  `Working.interrogation.trains.find_trains` does on the same onsets;
* only members with a family label join;
* `label_key` is order-sensitive (A-B is not B-A);
* keeping twice writes once (identity = recording + ordered member refs);
* the result is deterministic and NaN-free.

Conda interpreter; nothing here touches DATA/.
"""

import math
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.interrogation.trains import find_trains  # noqa: E402
from Working.library import sequences as S  # noqa: E402

FS = 1.0


def _db(tmp_path):
    conn = init_db(str(tmp_path / "lib.sqlite"))
    rid = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES ('Syn_concat_fs1.mat', 0, ?, 100000, 0, 'x.npy')", (FS,)).lastrowid
    other = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES ('Syn_concat_fs1.mat', 1, ?, 100000, 0, 'y.npy')", (FS,)).lastrowid
    gid = conn.execute(
        "INSERT INTO groupings (name, unit, basis, method, params_json, n_families, n_assigned, n_omitted, "
        "created_at) VALUES ('motifs', 'single_motifs', 'shape-distance', 'ward', '{}', 2, 0, 0, "
        "'2026-10-18T09:00:00')").lastrowid
    conn.commit()
    return conn, rid, other, gid


def _member(conn, gid, rid, start, end, label, *, family=True):
    """One motif member with an assignment in grouping `gid`; `label=None` is a
    member the grouping omitted (no family)."""
    entry = conn.execute(
        "INSERT INTO motif_entry (recording_id, start_idx, end_idx, created_at) VALUES (?, ?, ?, "
        "'2026-10-18T09:00:00')", (rid, start, end)).lastrowid
    mid = conn.execute(
        "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) VALUES (?, ?, ?, ?)",
        (entry, rid, start, end)).lastrowid
    conn.execute(
        "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_id, family_label, distance) "
        "VALUES (?, 'single_motifs', ?, ?, ?, 0.1)",
        (gid, mid, (1 if label == "F-01" else 2) if (label and family) else None, label))
    conn.commit()
    return mid


# ── the fixed rule ──────────────────────────────────────────────────────────

def test_touching_members_join_and_a_pair_twenty_percent_apart_does_not(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    a = _member(conn, gid, rid, 100, 160, "F-01")        # 60 s
    b = _member(conn, gid, rid, 160, 220, "F-02")        # touches a
    c = _member(conn, gid, rid, 225, 285, "F-01")        # 5 s gap < 10 % of 60 s
    # 12 s after c ends is 20 % of 60 s: past the 10 % tolerance
    d = _member(conn, gid, rid, 297, 357, "F-02")
    e = _member(conn, gid, rid, 357, 417, "F-02")        # touches d
    seqs = S.join_members(conn, rid, "fixed", 0.0, 0.1)
    assert [s.member_ids for s in seqs] == [(a, b, c), (d, e)]
    assert seqs[0].labels == ("F-01", "F-02", "F-01")
    assert seqs[0].gaps_s == (0.0, 5.0)
    assert seqs[1].gaps_s == (0.0,)


def test_the_gap_limit_is_a_number_you_can_change(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    a = _member(conn, gid, rid, 100, 160, "F-01")
    b = _member(conn, gid, rid, 172, 232, "F-02")        # 12 s gap
    assert S.join_members(conn, rid, "fixed", 0.0, 0.1) == []
    assert [s.member_ids for s in S.join_members(conn, rid, "fixed", 12.0, 0.0)] == [(a, b)]
    assert [s.member_ids for s in S.join_members(conn, rid, "fixed", 0.0, 0.2)] == [(a, b)]


def test_min_len_holds(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    _member(conn, gid, rid, 100, 160, "F-01")
    _member(conn, gid, rid, 160, 220, "F-02")
    _member(conn, gid, rid, 900, 960, "F-01")
    _member(conn, gid, rid, 960, 1020, "F-01")
    _member(conn, gid, rid, 1020, 1080, "F-02")
    assert [len(s) for s in S.join_members(conn, rid, "fixed", 0.0, 0.1)] == [2, 3]
    assert [len(s) for s in S.join_members(conn, rid, "fixed", 0.0, 0.1, min_len=3)] == [3]
    with pytest.raises(ValueError):
        S.join_members(conn, rid, "fixed", 0.0, 0.1, min_len=1)


def test_only_members_with_a_family_join_and_only_on_that_channel(tmp_path):
    conn, rid, other, gid = _db(tmp_path)
    a = _member(conn, gid, rid, 100, 160, "F-01")
    _member(conn, gid, rid, 160, 220, "F-02", family=False)   # omitted by the grouping: not a member
    _member(conn, gid, other, 160, 220, "F-02")                # the other channel
    c = _member(conn, gid, rid, 220, 280, "F-02")
    # a's end to c's start is 60 s: the omitted motif between them does not bridge them
    assert S.join_members(conn, rid, "fixed", 0.0, 0.1) == []
    assert [s.member_ids for s in S.join_members(conn, rid, "fixed", 60.0, 0.0)] == [(a, c)]


def test_an_unknown_rule_is_refused_by_name(tmp_path):
    conn, rid, _, _ = _db(tmp_path)
    with pytest.raises(ValueError, match="rule"):
        S.join_members(conn, rid, "maxinterval", 0.0, 0.1)
    with pytest.raises(ValueError):
        S.join_members(conn, rid, "fixed", -1.0, 0.1)
    with pytest.raises(ValueError):
        S.join_members(conn, rid, "fixed", 0.0, float("nan"))


# ── the adaptive rules reuse find_trains ────────────────────────────────────

@pytest.mark.parametrize("rule", ["adamatzky", "logisi"])
def test_the_adaptive_rules_agree_with_find_trains(tmp_path, rule):
    conn, rid, _, gid = _db(tmp_path)
    rng = np.random.default_rng(7)
    onsets, t = [], 100.0
    # bursts of 3–6 events 20–40 s apart, bursts 2–4 h apart: two humps in the gap histogram
    for _ in range(12):
        for _ in range(int(rng.integers(3, 7))):
            onsets.append(int(t))
            t += float(rng.uniform(20, 40))
        t += float(rng.uniform(7200, 14400))
    mids = [_member(conn, gid, rid, o, o + 10, "F-01" if i % 2 else "F-02") for i, o in enumerate(onsets)]
    want = find_trains(np.asarray(onsets, dtype=float) / FS, rule, min_events=2)
    groups = {}
    for mid, tid in zip(mids, want["train_id"]):
        if tid >= 0:
            groups.setdefault(int(tid), []).append(mid)
    expected = [tuple(groups[k]) for k in sorted(groups)]
    got = [s.member_ids for s in S.join_members(conn, rid, rule, 0.0, 0.1, min_len=2)]
    assert got == expected
    assert got, "the synthetic bursts should make at least one train"


# ── identity ────────────────────────────────────────────────────────────────

def test_label_key_is_order_sensitive(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    _member(conn, gid, rid, 100, 160, "F-01")
    _member(conn, gid, rid, 160, 220, "F-02")
    _member(conn, gid, rid, 5000, 5060, "F-02")
    _member(conn, gid, rid, 5060, 5120, "F-01")
    ab, ba = S.join_members(conn, rid, "fixed", 0.0, 0.1)
    assert S.label_key(ab) != S.label_key(ba)
    assert S.label_key(ab) == S.label_key(["F-01", "F-02"])
    assert S.edit_distance(["F-01", "F-02", "F-01"], ["F-01", "F-01"]) == 1
    assert S.edit_distance(ab.labels, ba.labels) == 2


def test_the_join_is_deterministic_and_nan_free(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    for k in range(6):
        _member(conn, gid, rid, 100 + 60 * k, 160 + 60 * k, "F-01" if k % 3 else "F-02")
    one = S.join_members(conn, rid, "fixed", 0.0, 0.1)
    two = S.join_members(conn, rid, "fixed", 0.0, 0.1)
    assert one == two
    for s in one:
        d = s.to_dict()
        assert all(math.isfinite(g) for g in d["gaps_s"])
        assert math.isfinite(d["start_s"]) and math.isfinite(d["end_s"])


# ── keeping ─────────────────────────────────────────────────────────────────

def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_keeping_twice_writes_once(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    a = _member(conn, gid, rid, 100, 160, "F-01")
    b = _member(conn, gid, rid, 160, 220, "F-02")
    c = _member(conn, gid, rid, 225, 285, "F-01")
    seqs = S.join_members(conn, rid, "fixed", 0.0, 0.1)
    prov = {"rule": "fixed", "gap_s": 0.0, "tol_frac": 0.1}
    first = S.keep_sequences(conn, seqs, prov)
    assert [r["created"] for r in first] == [True]
    assert _count(conn, "sequences") == 1 and _count(conn, "sequence_members") == 3
    row = conn.execute("SELECT * FROM sequences").fetchone()
    assert row["recording_id"] == rid and row["origin"] == "machine"
    assert row["source_kind"] == S.SOURCE_KIND and row["n_events"] == 3
    assert row["start_idx"] == 100 and row["end_idx"] == 285
    assert row["source_ref"] == S.label_key(seqs[0])
    assert '"rule": "fixed"' in row["source_store"], "the provenance note names the rule"
    members = conn.execute("SELECT member_id, position FROM sequence_members ORDER BY position").fetchall()
    assert [m["member_id"] for m in members] == [a, b, c]

    again = S.keep_sequences(conn, S.join_members(conn, rid, "fixed", 0.0, 0.1), prov)
    assert [r["created"] for r in again] == [False]
    assert again[0]["id"] == first[0]["id"]
    assert _count(conn, "sequences") == 1 and _count(conn, "sequence_members") == 3


def test_kept_sequences_read_back_with_the_joiners_gaps(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    _member(conn, gid, rid, 100, 160, "F-01")
    _member(conn, gid, rid, 160, 220, "F-02")
    _member(conn, gid, rid, 225, 285, "F-01")
    seqs = S.join_members(conn, rid, "fixed", 0.0, 0.1)
    kept = S.keep_sequences(conn, seqs, {"rule": "fixed"})
    back = S.read_sequences(conn, [kept[0]["id"]])
    assert back[0].gaps_s == seqs[0].gaps_s
    assert back[0].labels == seqs[0].labels
    assert back[0].member_ids == seqs[0].member_ids


def test_label_chain_families_group_kept_sequences_by_their_labels(tmp_path):
    conn, rid, _, gid = _db(tmp_path)
    for base in (100, 2000):
        _member(conn, gid, rid, base, base + 60, "F-01")
        _member(conn, gid, rid, base + 60, base + 120, "F-02")
    _member(conn, gid, rid, 5000, 5060, "F-02")
    _member(conn, gid, rid, 5060, 5120, "F-01")
    S.keep_sequences(conn, S.join_members(conn, rid, "fixed", 0.0, 0.1), {"rule": "fixed"})
    rows = S.label_chain_assignments(conn)
    by_key = {}
    for r in rows:
        by_key.setdefault(r["family_label"], []).append(r)
    assert sorted(by_key) == sorted([S.label_key(["F-01", "F-02"]), S.label_key(["F-02", "F-01"])])
    assert len(by_key[S.label_key(["F-01", "F-02"])]) == 2
    assert sum(r["is_medoid"] for r in by_key[S.label_key(["F-01", "F-02"])]) == 1
    near = S.nearest_family(S.label_key(["F-01", "F-02"]), list(by_key))
    assert near == (S.label_key(["F-02", "F-01"]), 2)


def test_a_kept_sequence_keeps_its_labels_after_the_motifs_are_regrouped(tmp_path):
    """critic: the family IS the label chain at keep time (`source_ref`). A later
    motif regroup that renames the elements must not rename the family's page —
    the strips, the title and the nearest family would otherwise disagree with
    the family id they were opened under."""
    conn, rid, _, gid = _db(tmp_path)
    a = _member(conn, gid, rid, 100, 160, "F-01")
    b = _member(conn, gid, rid, 160, 220, "F-02")
    kept = S.keep_sequences(conn, S.join_members(conn, rid, "fixed", 0.0, 0.1), {"rule": "fixed"})
    newer = conn.execute(
        "INSERT INTO groupings (name, unit, basis, method, params_json, n_families, n_assigned, n_omitted, "
        "created_at) VALUES ('regrouped', 'single_motifs', 'shape-distance', 'ward', '{}', 2, 0, 0, "
        "'2026-10-19T09:00:00')").lastrowid
    for mid, label in ((a, "F-07"), (b, "F-03")):
        conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_id, family_label, "
                     "distance) VALUES (?, 'single_motifs', ?, 1, ?, 0.1)", (newer, mid, label))
    conn.commit()
    back = S.read_sequences(conn, [kept[0]["id"]])
    assert back[0].labels == ("F-01", "F-02")
    assert S.label_key(back[0]) == kept[0]["key"]

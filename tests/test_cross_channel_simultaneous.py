"""
test_cross_channel_simultaneous.py
==================================
fixup-W: cross-channel classification on SIMULTANEOUS windows, under the rule
the researcher decided (QUESTIONS.md Q40a/b/c, Round 10 Q-W5, 2026-10-03).

- **Q40a** — lag is measured on the same absolute window on both channels. A
  family member is compared with its sibling channels at the member's own time;
  two members far apart in time are never "lag".
- **Q40b + Q-W5** — three bins, in seconds, with an r floor: artifact
  |lag| <= 1 s and |r| >= 0.5 (either sign); propagation 1 s < |lag| <= 50 s
  and |r| >= 0.5; independent everything else. The three numbers are Settings
  keys converted to samples with each recording's fs; the sign of r is stored.
- **Q40c** — a co-occurrence on a sibling channel with no family member there
  is counted on the family, never written as an edge.

PIPELINE_PRD.md "Testing Decisions": a synthetic pair with a known injected lag
classifying into the expected bin — *the test to insist on*. Every bin has one
here, including fixup-W Part 1's injected 5-sample offset, which the old
snippet-against-snippet path read as lag 0 / artifact, and the one-hour case,
which it read as lag 0 / artifact too.
"""

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest

from Working.database.schema import init_db
from Working.database import queries as q
from Working.database import runs as R
from Working.distances import DISTANCE_SCALE_INVARIANT
from Working import cross_channel as xc
from Working.cross_channel import ARTIFACT, INDEPENDENT_RECURRENCE, PROPAGATION
from Working.library import matching


PULSE_N = 60


def _pulse():
    """A biphasic pulse, PULSE_N samples: down then up, so its autocorrelation
    has one clear peak."""
    u = np.linspace(0.0, 2.0 * np.pi, PULSE_N)
    return -np.sin(u) * np.hanning(PULSE_N)


def _channel(n, plants, seed, noise=0.01):
    """`n` samples of small noise with the pulse planted at each `(at, sign)`."""
    x = np.random.default_rng(seed).standard_normal(n) * noise
    for at, sign in plants:
        x[at:at + PULSE_N] += sign * _pulse()
    return x


class _World:
    """One temporary database with recordings on disk and helpers to place
    family members on them."""

    def __init__(self, tmp):
        self.tmp = tmp
        self.conn = init_db(":memory:")
        self._entry = None

    def recording(self, source_file, channel, data, fs=1.0):
        path = os.path.join(self.tmp, f"{source_file}_{channel}.npy")
        np.save(path, np.asarray(data, dtype=float))
        rid = q.insert_recording(self.conn, source_file, channel, fs, len(data), 0, path)
        # fixup-AD: both swings are compared with the dataset's noise floor in mV
        self.conn.execute("UPDATE recordings SET units = 'mV' WHERE id = ?", (rid,))
        return rid

    def member(self, recording_id, start, end):
        if self._entry is None:
            self._entry = R.insert_motif_entry(self.conn, recording_id, start, end)
        return R.get_or_create_motif_member(self.conn, self._entry, recording_id, start, end)

    def seed_edge(self, a, b):
        return R.insert_motif_edge(self.conn, a, b, DISTANCE_SCALE_INVARIANT, 1.0, 0.1, "seed-recipe")

    def edges(self, a, b):
        return self.conn.execute(
            "SELECT * FROM motif_edge WHERE (member_a_id = ? AND member_b_id = ?) OR (member_a_id = ? AND member_b_id = ?)",
            (a, b, b, a)).fetchall()

    def close(self):
        self.conn.close()


@pytest.fixture
def world():
    with tempfile.TemporaryDirectory() as tmp:
        w = _World(tmp)
        try:
            yield w
        finally:
            w.close()


# ── the rule: named constants, in seconds, with an r floor ─────────────────

def test_the_rule_is_the_researchers_in_seconds_with_an_r_floor():
    assert xc.CROSS_CHANNEL_ARTIFACT_MAX_ABS_LAG_S == 1.0
    assert xc.CROSS_CHANNEL_MIN_ABS_CORRELATION == 0.5
    assert xc.CROSS_CHANNEL_PROPAGATION_MAX_ABS_LAG_S == 50.0
    assert xc.BINS == (ARTIFACT, PROPAGATION, INDEPENDENT_RECURRENCE)    # three bins, no common-mode


@pytest.mark.parametrize("lag_s, r, expected", [
    # fixup-AD (Round 12 Q1): the artifact test's floor is |r| >= 0.98, so W's
    # 0.95 / 0.5 / 0.7 at lag <= 1 s are no longer artifacts — nor propagation
    (0.0, 0.99, ARTIFACT),
    (0.0, -0.99, ARTIFACT),                     # an inverted copy at lag 0 is an artifact too (Q40b)
    (1.0, 0.98, ARTIFACT),                      # both boundaries inclusive
    (0.0, 0.95, INDEPENDENT_RECURRENCE),
    (-1.0, -0.7, INDEPENDENT_RECURRENCE),
    (0.0, 0.49, INDEPENDENT_RECURRENCE),        # under the r floor whatever its lag
    (1.5, 0.8, PROPAGATION),
    (-30.0, -0.6, PROPAGATION),
    (50.0, 0.5, PROPAGATION),
    (50.5, 0.9, INDEPENDENT_RECURRENCE),
    (10.0, 0.2, INDEPENDENT_RECURRENCE),        # the old rule called this propagation (Part 1: r 0.16)
])
def test_bin_for_reads_lag_in_seconds_and_r_by_magnitude(lag_s, r, expected):
    assert xc.bin_for(lag_s, r) == expected


def test_every_bin_prints_its_rule_from_the_values_used():
    rule = xc.CrossChannelRule(artifact_max_lag_s=2.0, min_abs_r=0.6, propagation_max_lag_s=30.0)
    words = rule.describe()
    assert set(words) == set(xc.BINS)
    assert "2 s" in words[ARTIFACT] and "0.6" in words[ARTIFACT]
    assert "30 s" in words[PROPAGATION]
    assert "0.6" in words[INDEPENDENT_RECURRENCE]


def test_the_three_numbers_are_settings_keys():
    conn = init_db(":memory:")
    try:
        assert xc.rule_from_settings(conn) == xc.DEFAULT_RULE
        from Working.registration.settings import put_settings
        put_settings(conn, xc.SETTINGS_PAGE, {
            xc.SETTINGS_KEYS["artifact_max_lag_s"]: 2,
            xc.SETTINGS_KEYS["min_abs_r"]: 0.7,
            xc.SETTINGS_KEYS["propagation_max_lag_s"]: 20,
        })
        rule = xc.rule_from_settings(conn)
        assert (rule.artifact_max_lag_s, rule.min_abs_r, rule.propagation_max_lag_s) == (2.0, 0.7, 20.0)
    finally:
        conn.close()


def test_a_saved_rule_that_is_not_a_rule_is_refused_loudly():
    with pytest.raises(ValueError):
        xc.CrossChannelRule(artifact_max_lag_s=60.0, min_abs_r=0.5, propagation_max_lag_s=50.0)
    with pytest.raises(ValueError):
        xc.CrossChannelRule(artifact_max_lag_s=1.0, min_abs_r=1.5, propagation_max_lag_s=50.0)


def test_classify_waveforms_converts_lag_to_seconds_with_fs():
    """At 10 Hz a 15-sample lag is 1.5 s — propagation; at 1 Hz it would be
    15 s. And 8 samples at 10 Hz is 0.8 s — an artifact, not propagation."""
    x = _channel(800, [(300, 1)], seed=1)
    y15 = _channel(800, [(315, 1)], seed=2)
    y8 = _channel(800, [(308, 1)], seed=3)
    lag, r, b = xc.classify_waveforms(x, y15, fs=10.0)
    assert lag == 15 and b == PROPAGATION and r > 0.5
    lag, r, b = xc.classify_waveforms(x, y8, fs=10.0)
    assert lag == 8 and b == ARTIFACT


# ── the family: simultaneous windows, written onto the members' edge ────────

def test_an_injected_five_sample_offset_is_recovered_and_binned_propagation(world):
    """fixup-W Part 1's case: the same pulse on two channels 5 samples apart.
    The old Library path cut each member's own snippet and returned lag 0 /
    artifact; on the same absolute window the lag is +5 s."""
    a_rec = world.recording("p.mat", 0, _channel(3000, [(1000, 1)], seed=10))
    b_rec = world.recording("p.mat", 1, _channel(3000, [(1005, 1)], seed=11))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 995, 1075)

    out = matching.classify_family_across_channels(world.conn, [a, b])

    pair = next(p for p in out["pairs"] if {p["member_a_id"], p["member_b_id"]} == {a, b})
    assert pair["member_a_id"] == a                     # lag is b relative to a: positive, b later
    assert pair["lag"] == 5 and pair["lag_s"] == 5.0
    assert pair["classification_bin"] == PROPAGATION
    assert pair["waveform_correlation"] > 0.9
    assert pair["window"] == (990, 1075)                # the union of the two spans, the same on both channels
    rows = world.edges(a, b)
    assert rows, "the classification is written onto the pair's edge"
    assert all(r["classification_bin"] == PROPAGATION and r["lag"] == 5 for r in rows)


def test_a_simultaneous_pair_is_an_artifact_and_an_inverted_one_too(world):
    a_rec = world.recording("s.mat", 0, _channel(3000, [(1000, 1)], seed=20))
    b_rec = world.recording("s.mat", 1, _channel(3000, [(1000, 1)], seed=21))
    c_rec = world.recording("s.mat", 2, _channel(3000, [(1000, -1)], seed=22))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 990, 1070)
    c = world.member(c_rec, 990, 1070)

    out = matching.classify_family_across_channels(world.conn, [a, b, c])
    by = {frozenset((p["member_a_id"], p["member_b_id"])): p for p in out["pairs"]}

    assert by[frozenset((a, b))]["classification_bin"] == ARTIFACT
    assert by[frozenset((a, b))]["lag"] == 0
    inv = by[frozenset((a, c))]
    assert inv["classification_bin"] == ARTIFACT
    assert inv["waveform_correlation"] < -0.9             # the sign is stored on the edge, not binned
    assert world.edges(a, c)[0]["waveform_correlation"] < -0.9


def test_an_existing_seed_edge_is_updated_in_place_not_duplicated(world):
    a_rec = world.recording("e.mat", 0, _channel(3000, [(1000, 1)], seed=30))
    b_rec = world.recording("e.mat", 1, _channel(3000, [(1005, 1)], seed=31))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 995, 1075)
    seed = world.seed_edge(a, b)

    matching.classify_family_across_channels(world.conn, [a, b])
    matching.classify_family_across_channels(world.conn, [a, b])     # idempotent

    rows = world.edges(a, b)
    assert [r["id"] for r in rows] == [seed]
    assert rows[0]["classification_bin"] == PROPAGATION and rows[0]["lag"] == 5
    assert rows[0]["distance_function"] == DISTANCE_SCALE_INVARIANT    # the seed's distance is untouched
    assert rows[0]["classification_json"]                              # the rule that produced the bin travels with it


def test_a_pair_with_no_edge_gets_one_cross_correlation_edge_once(world):
    a_rec = world.recording("n.mat", 0, _channel(3000, [(1000, 1)], seed=40))
    b_rec = world.recording("n.mat", 1, _channel(3000, [(1005, 1)], seed=41))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 995, 1075)

    matching.classify_family_across_channels(world.conn, [a, b])
    matching.classify_family_across_channels(world.conn, [a, b])

    rows = world.edges(a, b)
    assert len(rows) == 1
    assert rows[0]["distance_function"] == matching.CROSS_CHANNEL_DISTANCE
    assert rows[0]["distance_value"] == pytest.approx(1.0 - abs(rows[0]["waveform_correlation"]))


def test_members_an_hour_apart_are_never_lag(world):
    """Q40a, and fixup-W Part 1's second case: the old path returned lag 0 /
    artifact for events an hour apart. They are not simultaneous, so no lag is
    measured; an edge between them (a seed match) is independent recurrence."""
    a_rec = world.recording("h.mat", 0, _channel(6000, [(1000, 1)], seed=50))
    b_rec = world.recording("h.mat", 1, _channel(6000, [(4600, 1)], seed=51))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 4590, 4670)
    world.seed_edge(a, b)

    out = matching.classify_family_across_channels(world.conn, [a, b])

    row = world.edges(a, b)[0]
    assert row["classification_bin"] == INDEPENDENT_RECURRENCE
    assert row["lag"] is None and row["waveform_correlation"] is None
    pair = next(p for p in out["pairs"] if {p["member_a_id"], p["member_b_id"]} == {a, b})
    assert pair["simultaneous"] is False


def test_members_on_the_same_channel_are_not_cross_channel(world):
    rec = world.recording("one.mat", 0, _channel(3000, [(1000, 1), (1100, 1)], seed=60))
    a = world.member(rec, 990, 1070)
    b = world.member(rec, 1090, 1170)
    world.seed_edge(a, b)
    out = matching.classify_family_across_channels(world.conn, [a, b])
    assert out["pairs"] == []
    assert world.edges(a, b)[0]["classification_bin"] is None


def test_a_co_occurrence_with_no_member_is_counted_never_an_edge(world):
    """Q40c: the pulse is on channel 1 at the member's time, but no family
    member is there. Counted on the family; no edge, no member written."""
    a_rec = world.recording("c.mat", 0, _channel(3000, [(1000, 1)], seed=70))
    world.recording("c.mat", 1, _channel(3000, [(1000, 1)], seed=71))      # the same event, no member
    world.recording("c.mat", 2, _channel(3000, [(1020, 1)], seed=72))      # 20 s later, no member
    world.recording("c.mat", 3, _channel(3000, [], seed=73))               # nothing there
    a = world.member(a_rec, 990, 1100)
    n_members = world.conn.execute("SELECT COUNT(*) FROM motif_member").fetchone()[0]

    out = matching.classify_family_across_channels(world.conn, [a])

    assert out["pairs"] == []
    assert world.conn.execute("SELECT COUNT(*) FROM motif_edge").fetchone()[0] == 0
    assert world.conn.execute("SELECT COUNT(*) FROM motif_member").fetchone()[0] == n_members
    bins = sorted(w["classification_bin"] for w in out["withoutMember"])
    assert bins == [ARTIFACT, PROPAGATION]                  # channel 3's noise is not a co-occurrence
    assert out["counts"]["withoutMember"] == {ARTIFACT: 1, PROPAGATION: 1}
    # and the count survives the job: the family reads it back
    rec = matching.family_recurrence(world.conn, [a])
    assert rec["withoutMember"] == {ARTIFACT: 1, PROPAGATION: 1}


def test_progress_is_reported_per_channel(world):
    a_rec = world.recording("g.mat", 0, _channel(3000, [(1000, 1)], seed=80))
    b_rec = world.recording("g.mat", 1, _channel(3000, [(1005, 1)], seed=81))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 995, 1075)
    seen = []
    matching.classify_family_across_channels(world.conn, [a, b], progress=lambda done, total, msg: seen.append((done, total, msg)))
    assert seen[-1][0] == seen[-1][1] == 2
    assert any("ch" in m.lower() or "channel" in m.lower() for _d, _t, m in seen)


def test_a_held_out_file_is_never_read(world):
    a_rec = world.recording("M4_aug_concat_fs1.mat", 0, _channel(3000, [(1000, 1)], seed=90))
    b_rec = world.recording("M4_aug_concat_fs1.mat", 1, _channel(3000, [(1000, 1)], seed=91))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 990, 1070)
    out = matching.classify_family_across_channels(world.conn, [a, b],
                                                    exclude_source_files=("M4_aug_concat_fs1.mat",))
    assert out["pairs"] == [] and out["skipped"]


# ── recurrence with the bins taken out: one definition, in the core ─────────

def _three_way(world):
    """Members on four channels of one recording: ch0 and ch1 simultaneous (an
    artifact pair), ch2 10 s after ch0 (propagation from ch0 — and from ch1),
    and ch3 a different event an hour later."""
    r0 = world.recording("r.mat", 0, _channel(6000, [(1000, 1)], seed=100))
    r1 = world.recording("r.mat", 1, _channel(6000, [(1000, 1)], seed=101))
    r2 = world.recording("r.mat", 2, _channel(6000, [(1010, 1)], seed=102))
    r3 = world.recording("r.mat", 3, _channel(6000, [(4600, 1)], seed=103))
    m0 = world.member(r0, 990, 1070)
    m1 = world.member(r1, 990, 1070)
    m2 = world.member(r2, 1000, 1080)
    m3 = world.member(r3, 4590, 4670)
    return m0, m1, m2, m3


def test_recurrence_counts_with_the_bins_taken_out(world):
    m0, m1, m2, m3 = _three_way(world)
    ids = [m0, m1, m2, m3]
    before = matching.family_recurrence(world.conn, ids)
    assert before["classified"] is False
    assert before["all"] == before["excluding_artifacts"] == before["propagation_once"] == 4

    matching.classify_family_across_channels(world.conn, ids)
    rec = matching.family_recurrence(world.conn, ids)

    assert rec["classified"] is True
    assert rec["all"] == 4
    # m0 and m1 are one event seen on two electrodes at once: both FLAGGED (fixup-AD: the
    # machine flags, a human decides), so nothing is taken out until a human confirms
    assert rec["members"][m0]["flagged"] and rec["members"][m1]["flagged"]
    assert not rec["members"][m0]["artifact"]
    assert rec["excluding_artifacts"] == 4
    # m2 is propagation from both m0 and m1, so the three are one travelling event; m3 is an hour away
    assert rec["propagation_once"] == 2
    assert set(rec["rules"]) == {"all", "excluding_artifacts", "propagation_once"}


def test_a_propagation_chain_counts_once_on_the_channel_it_starts(world):
    r0 = world.recording("q.mat", 0, _channel(3000, [(1000, 1)], seed=110))
    r1 = world.recording("q.mat", 1, _channel(3000, [(1010, 1)], seed=111))
    r2 = world.recording("q.mat", 2, _channel(3000, [(1020, 1)], seed=112))
    m0 = world.member(r0, 990, 1070)
    m1 = world.member(r1, 1000, 1080)
    m2 = world.member(r2, 1010, 1090)
    matching.classify_family_across_channels(world.conn, [m0, m1, m2])
    rec = matching.family_recurrence(world.conn, [m0, m1, m2])
    assert rec["excluding_artifacts"] == 3
    assert rec["propagation_once"] == 1
    assert rec["members"][m0]["counted"]["propagation_once"] is True       # the earliest onset carries it
    assert rec["members"][m1]["counted"]["propagation_once"] is False
    assert rec["members"][m2]["counted"]["propagation_once"] is False


def test_recurrence_count_is_the_same_definition(world):
    m0, m1, m2, m3 = _three_way(world)
    matching.classify_family_across_channels(world.conn, [m0, m1, m2, m3])
    entry_id = world.conn.execute("SELECT entry_id FROM motif_member WHERE id = ?", (m0,)).fetchone()[0]
    assert matching.recurrence_count(world.conn, entry_id) == 4          # fixup-AD: no human has confirmed
    assert matching.recurrence_count(world.conn, entry_id, mode="propagation_once") == 2
    assert matching.recurrence_count(world.conn, entry_id, mode="all") == 4

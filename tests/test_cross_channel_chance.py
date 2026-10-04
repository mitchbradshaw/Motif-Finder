"""
test_cross_channel_chance.py
============================
fixup-AD: a cross-channel match must beat chance, and a human decides what is
an artifact (QUESTIONS.md Rounds 11-12, 2026-10-04).

W's rule called two electrodes "the same event" whenever their clips looked
alike at the same moment. Q40d measured that the same rule passes the same
sibling at a RANDOM other moment just as often (91 % vs 90 % on Fig2A), so it
found coincidence, not contamination. The decided fix:

1. **A per-pair chance test** — the same statistic `classify_waveforms`
   computes, on the same sibling at K random other times (member-length
   windows, >= 60 s from the member, inside the recording, never over a
   human-marked artifact region); K a Settings key (default 100), the draw
   seeded from the member id; a match counts only if |r| exceeds the pair's
   95th percentile (a Settings key). The percentile and K are stored with the
   result.
2. **The thresholds** — suspected artifact = |lag| <= 1 s and |r| >= 0.98 and
   beats chance and both swings clear the dataset's noise floor; propagation =
   1 s < |lag| <= 50 s and |r| >= 0.5 and beats chance and both clear the
   floor; independent everything else.
3. **Too short to tell** — a member under 30 samples (a Settings key) is not
   classified, is counted, is never binned and never padded.
4. **A human decides** — recurrence *excluding artifacts* takes out only
   members a human marked artifact, and prints flagged / confirmed / rejected /
   unjudged beside it; propagation counted once uses only propagation that beat
   chance; in a member-member artifact pair a human confirmed, both members go.
"""

import json
import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest

from Working import cross_channel as xc
from Working.cross_channel import ARTIFACT, INDEPENDENT_RECURRENCE, PROPAGATION
from Working.database import queries as q
from Working.database import runs as R
from Working.database.schema import init_db
from Working.library import matching
from Working.registration.settings import put_settings

PULSE_N = 60


def _pulse():
    u = np.linspace(0.0, 2.0 * np.pi, PULSE_N)
    return -np.sin(u) * np.hanning(PULSE_N)


def _channel(n, plants, seed, noise=0.01, drift=0.0):
    """`n` samples of small noise (plus an optional shared-looking linear drift)
    with the pulse planted at each `(at, sign)`."""
    x = np.random.default_rng(seed).standard_normal(n) * noise + drift * np.arange(n)
    for at, sign in plants:
        x[at:at + PULSE_N] += sign * _pulse()
    return x


class _World:
    def __init__(self, tmp):
        self.tmp = tmp
        self.conn = init_db(":memory:")
        self._entry = None

    def recording(self, source_file, channel, data, fs=1.0, units="mV"):
        path = os.path.join(self.tmp, f"{source_file}_{channel}.npy")
        np.save(path, np.asarray(data, dtype=float))
        rid = q.insert_recording(self.conn, source_file, channel, fs, len(data), 0, path)
        self.conn.execute("UPDATE recordings SET units = ? WHERE id = ?", (units, rid))
        self.conn.commit()
        return rid

    def member(self, recording_id, start, end):
        if self._entry is None:
            self._entry = R.insert_motif_entry(self.conn, recording_id, start, end)
        return R.get_or_create_motif_member(self.conn, self._entry, recording_id, start, end)

    def human(self, member_id, verdict):
        """A human verdict on the member's span, as the suspected-artifact queue
        writes it (`annotations`, source `cross_channel_review`)."""
        from Working.review import artifact_queue as aq
        m = self.conn.execute("SELECT * FROM motif_member WHERE id = ?", (member_id,)).fetchone()
        q.insert_annotation(self.conn, m["recording_id"], m["start_idx"], m["end_idx"], verdict,
                            source=aq.REVIEW_SOURCE, note="flagged as a suspected artifact")

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


# ── 1-2. the rule: new numbers, all Settings keys ─────────────────────────────

def test_the_decided_numbers_are_named_constants():
    assert xc.CROSS_CHANNEL_ARTIFACT_MIN_ABS_CORRELATION == 0.98
    assert xc.CROSS_CHANNEL_MIN_ABS_CORRELATION == 0.5          # the propagation floor is unchanged
    assert xc.CROSS_CHANNEL_NULL_K == 100
    assert xc.CROSS_CHANNEL_NULL_PERCENTILE == 95.0
    assert xc.CROSS_CHANNEL_MIN_SAMPLES == 30
    assert xc.CROSS_CHANNEL_NULL_MIN_GAP_S == 60.0


def test_every_new_number_is_a_settings_key():
    conn = init_db(":memory:")
    try:
        assert xc.rule_from_settings(conn) == xc.DEFAULT_RULE
        put_settings(conn, xc.SETTINGS_PAGE, {
            xc.SETTINGS_KEYS["artifact_min_abs_r"]: 0.95,
            xc.SETTINGS_KEYS["null_k"]: 40,
            xc.SETTINGS_KEYS["null_percentile"]: 99,
            xc.SETTINGS_KEYS["min_samples"]: 12,
        })
        rule = xc.rule_from_settings(conn)
        assert (rule.artifact_min_abs_r, rule.null_k, rule.null_percentile, rule.min_samples) == (0.95, 40, 99.0, 12)
        assert all(k.startswith("cross_channel.") for k in xc.SETTINGS_KEYS.values())
    finally:
        conn.close()


@pytest.mark.parametrize("kw", [
    {"artifact_min_abs_r": 1.2}, {"null_k": 0}, {"null_percentile": 100}, {"null_percentile": 0},
    {"min_samples": 2},
])
def test_a_saved_number_that_is_not_a_rule_is_refused(kw):
    with pytest.raises(ValueError):
        xc.CrossChannelRule(**kw)


@pytest.mark.parametrize("lag_s, r, chance, floor, expected", [
    (0.0, 0.99, True, True, ARTIFACT),
    (0.0, -0.99, True, True, ARTIFACT),                  # inverted, still a suspected artifact
    (1.0, 0.98, True, True, ARTIFACT),                   # boundaries inclusive
    (0.0, 0.95, True, True, INDEPENDENT_RECURRENCE),     # W called this artifact; under 0.98 it is not
    (0.5, 0.7, True, True, INDEPENDENT_RECURRENCE),      # simultaneous but not a copy: not propagation either
    (0.0, 0.99, False, True, INDEPENDENT_RECURRENCE),    # does not beat chance
    (0.0, 0.99, True, False, INDEPENDENT_RECURRENCE),    # a swing under the noise floor
    (10.0, 0.6, True, True, PROPAGATION),                # propagation keeps the 0.5 floor
    (10.0, 0.6, False, True, INDEPENDENT_RECURRENCE),
    (10.0, 0.6, True, False, INDEPENDENT_RECURRENCE),
    (10.0, 0.4, True, True, INDEPENDENT_RECURRENCE),
    (60.0, 0.9, True, True, INDEPENDENT_RECURRENCE),
])
def test_bin_for_needs_chance_and_the_floor(lag_s, r, chance, floor, expected):
    assert xc.bin_for(lag_s, r, beats_chance=chance, above_floor=floor) == expected


def test_every_rule_is_printed_with_its_numbers():
    words = xc.DEFAULT_RULE.describe()
    assert set(words) == set(xc.BINS)
    assert "0.98" in words[ARTIFACT] and "95" in words[ARTIFACT] and "100" in words[ARTIFACT]
    assert "noise floor" in words[ARTIFACT] and "noise floor" in words[PROPAGATION]
    assert "0.5" in words[PROPAGATION] and "chance" in words[PROPAGATION]
    assert "30" in xc.DEFAULT_RULE.describe_too_short()


# ── the chance test itself ──────────────────────────────────────────────────

def test_the_chance_null_is_drawn_from_the_same_sibling_at_random_other_times():
    rng = np.random.default_rng(0)
    n, start, end = 5000, 2000, 2080
    sib = rng.standard_normal(n)
    x = np.asarray(sib[start:end]).copy()
    null = xc.chance_null(x, sib, start, end, fs=1.0, rule=xc.DEFAULT_RULE, seed=17)
    assert null["k"] == 100 and null["k_requested"] == 100
    assert len(null["starts"]) == 100
    gap = 60
    for s in null["starts"]:
        assert 0 <= s and s + (end - start) <= n                  # inside the recording
        assert s + (end - start) <= start - gap or s >= end + gap  # at least 60 s from the member
    # the statistic is classify_waveforms' own: |r| at the cross-correlation peak
    s0 = null["starts"][0]
    assert null["abs_r"][0] == pytest.approx(abs(xc.cross_correlation_peak(x, sib[s0:s0 + 80])[1]))
    assert null["threshold"] == pytest.approx(np.percentile(null["abs_r"], 95.0))


def test_the_draw_is_reproducible_from_the_member_id():
    sib = np.random.default_rng(1).standard_normal(4000)
    x = sib[1000:1080].copy()
    a = xc.chance_null(x, sib, 1000, 1080, fs=1.0, rule=xc.DEFAULT_RULE, seed=42)
    b = xc.chance_null(x, sib, 1000, 1080, fs=1.0, rule=xc.DEFAULT_RULE, seed=42)
    c = xc.chance_null(x, sib, 1000, 1080, fs=1.0, rule=xc.DEFAULT_RULE, seed=43)
    assert a["starts"] == b["starts"] and a["abs_r"] == b["abs_r"]
    assert a["starts"] != c["starts"]


def test_the_null_never_cuts_a_human_marked_artifact_region():
    sib = np.random.default_rng(2).standard_normal(3000)
    x = sib[200:280].copy()
    forbidden = [(1000, 2900)]
    null = xc.chance_null(x, sib, 200, 280, fs=1.0, rule=xc.DEFAULT_RULE, seed=5, forbidden=forbidden)
    for s in null["starts"]:
        assert s + 80 <= 1000 or s >= 2900


def test_no_room_for_a_null_is_said_not_passed():
    sib = np.random.default_rng(3).standard_normal(150)
    null = xc.chance_null(sib[40:120].copy(), sib, 40, 120, fs=1.0, rule=xc.DEFAULT_RULE, seed=1)
    assert null["k"] == 0
    assert xc.beats_chance(0.99, null) is False          # no null, no claim: never passed by default
    assert null["reason"]


def test_a_real_copy_beats_chance_and_shared_drift_does_not():
    """The Q40d failure, in miniature: two channels sharing nothing but a slow
    drift correlate at |r| ~ 1 at the member's time AND at every random time,
    so the match does not beat chance; a pulse planted on both channels on
    quiet noise does."""
    n = 6000
    drift_a = _channel(n, [], seed=10, noise=0.001, drift=0.01)
    drift_b = _channel(n, [], seed=11, noise=0.001, drift=0.01)
    lag, r, _b = xc.classify_waveforms(drift_a[3000:3080], drift_b[3000:3080])
    null = xc.chance_null(drift_a[3000:3080], drift_b, 3000, 3080, fs=1.0, rule=xc.DEFAULT_RULE, seed=9)
    assert abs(r) > 0.98 and not xc.beats_chance(r, null)

    pa = _channel(n, [(3000, 1)], seed=12)
    pb = _channel(n, [(3000, 1)], seed=13)
    lag, r, _b = xc.classify_waveforms(pa[2990:3070], pb[2990:3070])
    null = xc.chance_null(pa[2990:3070], pb, 2990, 3070, fs=1.0, rule=xc.DEFAULT_RULE, seed=9)
    assert abs(r) > 0.98 and xc.beats_chance(r, null)
    assert null["percentile"] > 95.0


# ── the family: chance, floor and too-short, persisted ──────────────────────

def test_a_simultaneous_copy_on_quiet_noise_is_a_suspected_artifact_with_its_chance_stored(world):
    a_rec = world.recording("s.mat", 0, _channel(4000, [(1000, 1)], seed=20))
    b_rec = world.recording("s.mat", 1, _channel(4000, [(1000, 1)], seed=21))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 990, 1070)
    out = matching.classify_family_across_channels(world.conn, [a, b])
    pair = out["pairs"][0]
    assert pair["classification_bin"] == ARTIFACT
    assert pair["chance"]["beats"] is True and pair["chance"]["k"] == 100
    row = world.conn.execute("SELECT classification_json FROM motif_edge WHERE member_a_id = ?", (a,)).fetchone()
    info = json.loads(row[0])
    assert info["chance"]["k"] == 100 and info["chance"]["at"] == 95.0
    assert 0.0 <= info["chance"]["percentile"] <= 100.0
    assert info["floor"]["ok"] is True and info["floor"]["floor_mv"] == pytest.approx(0.1)


def test_shared_drift_at_the_same_instant_is_not_an_artifact(world):
    """W binned this artifact (|r| ~ 1 at lag 0); it does not beat the pair's
    own random times, so it is independent."""
    a_rec = world.recording("d.mat", 0, _channel(6000, [], seed=30, noise=0.001, drift=0.01))
    b_rec = world.recording("d.mat", 1, _channel(6000, [], seed=31, noise=0.001, drift=0.01))
    a = world.member(a_rec, 3000, 3080)
    b = world.member(b_rec, 3000, 3080)
    out = matching.classify_family_across_channels(world.conn, [a, b])
    assert out["pairs"][0]["classification_bin"] == INDEPENDENT_RECURRENCE
    assert out["pairs"][0]["chance"]["beats"] is False


def test_a_sibling_under_the_noise_floor_is_no_twin(world):
    """Q40d-3: the twin must itself be an event. A copy at 1/1000 of the size,
    under the 0.1 mV floor, is not an artifact, however well it correlates."""
    a_rec = world.recording("f.mat", 0, _channel(4000, [(1000, 1)], seed=40))
    tiny = _channel(4000, [(1000, 1)], seed=41) * 0.001
    world.recording("f.mat", 1, tiny)
    a = world.member(a_rec, 990, 1070)
    out = matching.classify_family_across_channels(world.conn, [a])
    co = world.conn.execute("SELECT classification_bin, classification_json FROM motif_member_cooccurrence").fetchone()
    assert co["classification_bin"] == INDEPENDENT_RECURRENCE
    assert json.loads(co["classification_json"])["floor"]["ok"] is False
    assert out["withoutMember"] == []


def test_the_floor_is_the_datasets_own_from_settings(world):
    a_rec = world.recording("g.mat", 0, _channel(4000, [(1000, 1)], seed=50))
    b_rec = world.recording("g.mat", 1, _channel(4000, [(1000, 1)], seed=51))
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 990, 1070)
    from Working.library.view_filter import dataset_floors
    stem = dataset_floors(world.conn)["g.mat"]["stem"]
    put_settings(world.conn, "datasets", {f"meta.{stem}.noise_floor": "5"})       # 5 mV: above the 1 mV pulse
    out = matching.classify_family_across_channels(world.conn, [a, b])
    assert out["pairs"][0]["classification_bin"] == INDEPENDENT_RECURRENCE
    assert out["pairs"][0]["floor"]["floor_mv"] == 5.0


def test_an_undeclared_unit_cannot_clear_the_floor(world):
    a_rec = world.recording("u.mat", 0, _channel(4000, [(1000, 1)], seed=52), units=None)
    b_rec = world.recording("u.mat", 1, _channel(4000, [(1000, 1)], seed=53), units=None)
    a = world.member(a_rec, 990, 1070)
    b = world.member(b_rec, 990, 1070)
    out = matching.classify_family_across_channels(world.conn, [a, b])
    assert out["pairs"][0]["classification_bin"] == INDEPENDENT_RECURRENCE
    assert out["pairs"][0]["floor"]["ok"] is False and "unit" in out["pairs"][0]["floor"]["reason"]


def test_a_member_under_thirty_samples_is_too_short_to_tell(world):
    a_rec = world.recording("t.mat", 0, _channel(4000, [(1000, 1)], seed=60))
    b_rec = world.recording("t.mat", 1, _channel(4000, [(1000, 1)], seed=61))
    world.recording("t.mat", 2, _channel(4000, [(1000, 1)], seed=62))
    short = world.member(a_rec, 1000, 1016)                # 16 samples, like a Fig2A member
    long_ = world.member(b_rec, 990, 1070)
    out = matching.classify_family_across_channels(world.conn, [short, long_])
    assert out["tooShort"] == [short]
    assert out["counts"]["tooShort"] == 1
    assert all(short not in (p["member_a_id"], p["member_b_id"]) for p in out["pairs"])
    n_co = world.conn.execute("SELECT COUNT(*) FROM motif_member_cooccurrence WHERE member_id = ?",
                              (short,)).fetchone()[0]
    assert n_co == 0                                       # never binned, not even without a member
    rec = matching.family_recurrence(world.conn, [short, long_])
    assert rec["tooShort"] == 1 and rec["members"][short]["tooShort"] is True


def test_a_stale_bin_on_a_too_short_member_is_cleared_on_reclassify(world):
    a_rec = world.recording("w.mat", 0, _channel(4000, [(1000, 1)], seed=63))
    b_rec = world.recording("w.mat", 1, _channel(4000, [(1000, 1)], seed=64))
    short = world.member(a_rec, 1000, 1016)
    other = world.member(b_rec, 1000, 1016)
    # as W left it: an artifact bin on a 16-sample pair
    eid = R.insert_motif_edge(world.conn, short, other, matching.CROSS_CHANNEL_DISTANCE, 0.5, 0.01, "w",
                              lag=0, waveform_correlation=0.99, classification_bin=ARTIFACT)
    world.conn.execute("INSERT INTO motif_member_cooccurrence (member_id, recording_id, lag, waveform_correlation, "
                       "classification_bin) VALUES (?, ?, 0, 0.99, 'artifact')", (short, b_rec))
    world.conn.commit()
    matching.classify_family_across_channels(world.conn, [short, other])
    assert world.conn.execute("SELECT COUNT(*) FROM motif_member_cooccurrence WHERE member_id = ?",
                              (short,)).fetchone()[0] == 0
    row = world.conn.execute("SELECT classification_bin FROM motif_edge WHERE id = ?", (eid,)).fetchone()
    assert row is None or row["classification_bin"] is None


# ── 4. recurrence: only a human takes a member out ─────────────────────────

def _artifact_pair_and_propagation(world):
    """ch0/ch1 a simultaneous copy (suspected artifact), ch2 ten seconds later
    (propagation from both), ch3 an independent event an hour later."""
    r0 = world.recording("r.mat", 0, _channel(8000, [(1000, 1)], seed=100))
    r1 = world.recording("r.mat", 1, _channel(8000, [(1000, 1)], seed=101))
    r2 = world.recording("r.mat", 2, _channel(8000, [(1010, 1)], seed=102))
    r3 = world.recording("r.mat", 3, _channel(8000, [(4600, 1)], seed=103))
    return (world.member(r0, 990, 1070), world.member(r1, 990, 1070),
            world.member(r2, 1000, 1080), world.member(r3, 4590, 4670))


def test_a_machine_flag_alone_takes_nothing_out(world):
    m0, m1, m2, m3 = _artifact_pair_and_propagation(world)
    ids = [m0, m1, m2, m3]
    matching.classify_family_across_channels(world.conn, ids)
    rec = matching.family_recurrence(world.conn, ids)
    assert rec["members"][m0]["flagged"] and rec["members"][m1]["flagged"]
    assert rec["flagged"] == 2 and rec["confirmed"] == 0 and rec["rejected"] == 0 and rec["unjudged"] == 2
    assert rec["excluding_artifacts"] == 4                 # nobody has confirmed anything yet
    assert not rec["members"][m0]["artifact"]


def test_a_confirmed_artifact_is_taken_out_with_its_member_twin(world):
    """Round 11 Q40d-2: in a member-member artifact pair a human confirmed,
    both members are artifacts."""
    m0, m1, m2, m3 = _artifact_pair_and_propagation(world)
    ids = [m0, m1, m2, m3]
    matching.classify_family_across_channels(world.conn, ids)
    world.human(m0, "artifact")
    rec = matching.family_recurrence(world.conn, ids)
    assert rec["confirmed"] == 1 and rec["unjudged"] == 1
    assert rec["members"][m0]["artifact"] and rec["members"][m1]["artifact"]
    assert rec["excluding_artifacts"] == 2                 # m2 and m3
    assert rec["propagation_once"] == 2


def test_a_rejected_flag_keeps_the_member_and_says_so(world):
    m0, m1, m2, m3 = _artifact_pair_and_propagation(world)
    ids = [m0, m1, m2, m3]
    matching.classify_family_across_channels(world.conn, ids)
    world.human(m0, "interesting")                          # "no, a real event"
    world.human(m1, "unsure")
    rec = matching.family_recurrence(world.conn, ids)
    assert rec["rejected"] == 1 and rec["unsure"] == 1 and rec["confirmed"] == 0
    assert rec["excluding_artifacts"] == 4
    assert rec["members"][m0]["verdict"] == "interesting"


def test_propagation_once_counts_only_propagation_that_beat_chance(world):
    """A propagation bin W wrote before the chance test existed (no `chance` on
    its classification) does not merge two members."""
    r0 = world.recording("p.mat", 0, _channel(4000, [(1000, 1)], seed=110))
    r1 = world.recording("p.mat", 1, _channel(4000, [(1010, 1)], seed=111))
    m0 = world.member(r0, 990, 1070)
    m1 = world.member(r1, 1000, 1080)
    R.insert_motif_edge(world.conn, m0, m1, matching.CROSS_CHANNEL_DISTANCE, 0.5, 0.2, "w-era",
                        lag=10, waveform_correlation=0.8, classification_bin=PROPAGATION)
    world.conn.execute("UPDATE motif_edge SET classification_json = ?",
                       (json.dumps({"rule": {"artifact_max_lag_s": 1, "min_abs_r": 0.5, "propagation_max_lag_s": 50}}),))
    world.conn.commit()
    rec = matching.family_recurrence(world.conn, [m0, m1])
    assert rec["propagation_once"] == 2                    # the W-era bin did not beat any chance test
    matching.classify_family_across_channels(world.conn, [m0, m1])
    rec = matching.family_recurrence(world.conn, [m0, m1])
    assert rec["propagation_once"] == 1                    # re-classified: beats chance, one travelling event


def test_the_caller_still_passes_the_member_ids(world):
    """AE's seam: `family_recurrence(conn, member_ids)` keeps its signature."""
    m0, m1, m2, m3 = _artifact_pair_and_propagation(world)
    matching.classify_family_across_channels(world.conn, [m0, m1, m2, m3])
    rec = matching.family_recurrence(world.conn, [m0, m2])
    assert rec["all"] == 2
    assert set(rec["rules"]) == {"all", "excluding_artifacts", "propagation_once"}
    assert "human" in rec["rules"]["excluding_artifacts"]

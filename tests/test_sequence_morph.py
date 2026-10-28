"""
test_sequence_morph.py
========================
Round-B B2 — the "morph" readout on Library sequences
(`Working.library.morph`).

In plain words: walk along a sequence of drops, one event to the next. If the
shape changes gradually (a morph), every single step is a small change, while
the first and the last event are far apart. So: the fraction of consecutive
steps whose shape distance is SMALLER than the end-to-end distance (first event
to last). A steady morph scores near 1; a sequence whose shapes are unrelated
scores whatever chance gives. The null is the same events in shuffled order
(seeded permutations); the per-sequence p is one-sided (does the real order
morph MORE than a shuffled one?). A summary counts how many sequences beat
their null at p < 0.05 against the number expected by chance.

The distance is the Library groupings' own (Ward's: resample to 256 points,
z-normalise, Euclidean, divided by 2 sqrt(256)) - imported, never re-written.

Runnable standalone:  python tests/test_sequence_morph.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.library import morph as M  # noqa: E402
from Working.library.grouping.methods import ward  # noqa: E402

T = np.linspace(0.0, 1.0, 90)


def _morphing(k=30, noise=0.0, seed=0):
    """A steady morph: one cycle whose phase slides by equal steps (0 to 0.9 pi),
    so the shape distance grows with every element apart - a straight path."""
    rng = np.random.default_rng(seed)
    return [np.sin(2 * np.pi * T + ph) + noise * rng.standard_normal(T.size) for ph in np.linspace(0, 0.9 * np.pi, k)]


def _random(k=30, seed=0):
    rng = np.random.default_rng(seed)
    return [np.convolve(rng.standard_normal(T.size + 9), np.ones(10) / 10, mode="valid") for _ in range(k)]


# ── the distance is the groupings' ──────────────────────────────────────────

def test_the_distance_is_the_ward_groupings_scale_invariant_distance():
    ws = _random(4, seed=3)
    d = M.shape_distances(ws)
    from scipy.spatial.distance import squareform
    ref = squareform(ward.condensed_distances(ward.shape_vectors(ws)))
    assert np.allclose(d, ref)
    assert M.DISTANCE_WORDS and "256" in M.DISTANCE_WORDS


# ── the readout ─────────────────────────────────────────────────────────────

def test_the_fraction_by_hand():
    # distances along a line: steps 1, 1, 1; end-to-end 3 -> every step is smaller
    d = np.abs(np.subtract.outer(np.arange(4.0), np.arange(4.0)))
    assert M.morph_fraction(d) == 1.0
    # a there-and-back walk: end-to-end 0, no step is smaller
    d2 = np.abs(np.subtract.outer(np.array([0.0, 1.0, 0.0]), np.array([0.0, 1.0, 0.0])))
    assert M.morph_fraction(d2, order=[0, 1, 2]) == 0.0


def test_a_steady_morph_beats_its_shuffle():
    r = M.morph_readout(_morphing(30, noise=0.02), n_draws=1000, seed=1)
    assert r["fraction"] == 1.0
    assert r["fraction"] >= r["hi"]
    assert r["null_mean"] < 0.6
    assert r["p"] < 0.05
    assert r["tested"] is True


def test_a_random_sequence_does_not_beat_its_shuffle():
    rows = [M.morph_readout(_random(30, seed=s), n_draws=500, seed=1) for s in range(20)]
    assert sum(r["p"] < 0.05 for r in rows) <= 3        # about 1 in 20 by chance; never most of them
    assert np.mean([r["fraction"] for r in rows]) == pytest.approx(0.5, abs=0.12)


def test_the_statistic_is_coarse_a_perfect_short_morph_cannot_reach_p_005():
    # A pinned property of the readout, not a bug: a shuffled order scores 1 too
    # whenever its ends happen to be far apart, so even a perfect 9-element
    # morph's p floor is about 0.1. Only long sequences (~20+) can beat it.
    r = M.morph_readout(_morphing(9, noise=0.02), n_draws=1000, seed=1)
    assert r["fraction"] == 1.0 and r["p"] > 0.05 and r["tested"] is False and r["note"]


def test_band_mean_and_p_are_reported_and_seeded():
    ws = _morphing(7, noise=0.05, seed=4)
    a = M.morph_readout(ws, n_draws=300, seed=9)
    b = M.morph_readout(ws, n_draws=300, seed=9)
    assert a == b
    for k in ("fraction", "null_mean", "lo", "hi", "p", "n_draws", "n_elements", "n_steps"):
        assert k in a
    assert a["lo"] <= a["null_mean"] <= a["hi"]
    assert a["n_elements"] == 7 and a["n_steps"] == 6


def test_short_sequences_enumerate_every_order_exactly():
    # 5 elements = 120 orders: fewer than the draws, so every order is used once
    r = M.morph_readout(_morphing(5, noise=0.02), n_draws=1000, seed=1)
    assert r["exact"] is True and r["n_draws"] == 120


def test_a_sequence_too_short_to_test_says_why_and_is_not_counted_as_failing():
    # two elements: the one step IS the end-to-end distance. Four: a sequence and
    # its reverse score alike, so the smallest p reachable is 2/24 > 0.05.
    r2 = M.morph_readout(_morphing(2), n_draws=100, seed=1)
    assert r2["fraction"] is None and r2["tested"] is False and r2["note"]
    r4 = M.morph_readout(_morphing(4, noise=0.01), n_draws=100, seed=1)
    assert r4["tested"] is False and r4["p_floor"] > 0.05 and r4["note"]


def test_the_summary_counts_beaters_against_the_number_expected_by_chance():
    rows = [M.morph_readout(_morphing(30, noise=0.02, seed=s), n_draws=1000, seed=s) for s in range(5)]
    rows += [M.morph_readout(_random(30, seed=s), n_draws=1000, seed=s) for s in range(5)]
    rows += [M.morph_readout(_morphing(3), n_draws=300, seed=1)]
    s = M.morph_summary(rows)
    assert s["n_sequences"] == 11
    assert s["n_tested"] >= 9
    assert s["n_beat"] >= 5
    # the chance count is at most alpha x the tested sequences (discrete nulls give less)
    assert 0 < s["expected"] <= 0.05 * s["n_tested"] + 1e-9
    assert s["alpha"] == 0.05
    assert str(s["n_beat"]) in s["words"] and "expected" in s["words"]


def test_a_flat_element_is_not_scored_and_the_row_says_so():
    # z-normalising a flat span gives all zeros, which would read as "a shape"
    ws = _morphing(6)
    ws[2] = np.zeros(T.size)
    r = M.morph_readout(ws, n_draws=50, seed=1)
    assert r["fraction"] is None and r["tested"] is False
    assert "flat" in r["note"]


def test_an_empty_waveform_is_refused_loudly():
    ws = _morphing(5)
    ws[1] = np.array([])
    with pytest.raises(ValueError):
        M.morph_readout(ws, n_draws=50, seed=1)


# ── the step-size companion (researcher, 2026-10-28) ────────────────────────
#
# In plain words: are neighbouring events more alike than random pairs of the
# same events? The mean shape distance between consecutive elements, against
# the same shuffled orders as the fraction; one-sided p = how often a shuffled
# order takes steps at least as small. A sequence and its reverse take the same
# steps, so the floor is 2/k! and five elements can be judged - which the morph
# fraction cannot do below about 20.

def test_the_step_score_by_hand():
    # distances along a line: steps 1, 1, 1 -> mean 1; the order 0, 3, 1, 2 steps 3, 2, 1 -> mean 2
    d = np.abs(np.subtract.outer(np.arange(4.0), np.arange(4.0)))
    assert M.mean_step(d) == 1.0
    assert M.mean_step(d, order=[0, 3, 1, 2]) == 2.0


def test_the_step_score_judges_a_short_steady_morph_the_fraction_cannot():
    r = M.morph_readout(_morphing(5, noise=0.02), n_draws=1000, seed=1)
    assert r["tested"] is False                                   # the fraction's floor is too high at 5
    s = r["steps"]
    assert s["tested"] is True and s["p_floor"] == pytest.approx(2 / 120)
    assert s["p"] == pytest.approx(2 / 120)                        # the real order and its reverse take the smallest steps
    assert s["mean_step"] < s["lo"] <= s["null_mean"] <= s["hi"]
    assert s["ratio"] == pytest.approx(s["mean_step"] / s["null_mean"]) and s["ratio"] < 1


def test_alternating_shapes_take_larger_steps_than_shuffled():
    a, b = np.sin(2 * np.pi * T), np.cos(6 * np.pi * T)
    s = M.morph_readout([a, b] * 4, n_draws=1000, seed=1)["steps"]
    assert s["tested"] is True and s["ratio"] > 1 and s["p"] > 0.5


def test_runs_of_like_events_also_take_smaller_steps_so_the_score_is_not_a_morph_test():
    # A pinned property, not a bug (critic, 2026-10-28): persistence passes too. Five near-copies of one shape, then
    # five of another (AAAAABBBBB), take small steps without any gradual change; the score cannot tell the two apart.
    rng = np.random.default_rng(0)
    a, b = np.sin(2 * np.pi * T), np.cos(6 * np.pi * T)
    ws = [a + 0.01 * rng.standard_normal(T.size) for _ in range(5)]
    ws += [b + 0.01 * rng.standard_normal(T.size) for _ in range(5)]
    s = M.morph_readout(ws, n_draws=1000, seed=1)["steps"]
    assert s["tested"] is True and s["ratio"] < 0.5 and s["p"] < 0.05


def test_four_elements_cannot_be_judged_by_steps_either():
    s = M.morph_readout(_morphing(4, noise=0.01), n_draws=100, seed=1)["steps"]
    assert s["tested"] is False and s["p_floor"] == pytest.approx(2 / 24) and s["note"]


def test_an_unscored_sequence_has_no_step_score():
    assert M.morph_readout(_morphing(2), n_draws=100, seed=1)["steps"] is None


def test_the_summary_counts_step_beaters_against_chance():
    rows = [M.morph_readout(_morphing(6, noise=0.02, seed=s), n_draws=1000, seed=s) for s in range(4)]
    rows += [M.morph_readout(_random(8, seed=s), n_draws=1000, seed=s) for s in range(4)]
    rows += [M.morph_readout(_morphing(2), n_draws=100, seed=1)]
    st = M.morph_summary(rows)["steps"]
    assert st["n_tested"] == 8 and st["n_beat"] >= 4
    assert 0 < st["expected"] <= 0.05 * st["n_tested"] + 1e-9
    assert str(st["n_beat"]) in st["words"] and "smaller steps" in st["words"]


# ── headless: stored sequences ──────────────────────────────────────────────

def test_stored_waveform_reads_a_relative_npy_path_from_any_working_directory(tmp_path, monkeypatch):
    """Recordings store `npy_path` relative to the repo root (`DATA/derived/channels/...`). A headless call from
    another folder must still find the samples, as `chain_job._resolve_npy` does, not report the sequence unscored."""
    import sqlite3

    from Working.database import queries as q
    from Working.database.schema import init_db
    from Working.hpc import job_export

    root = tmp_path / "repo"
    (root / "DATA").mkdir(parents=True)
    np.save(str(root / "DATA" / "ch0.npy"), np.arange(20, dtype=float))
    db = tmp_path / "m.sqlite"
    init_db(str(db))
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rid = q.insert_recording(conn, "R.mat", 0, fs=1.0, n_samples=20, global_offset=0, npy_path="DATA/ch0.npy")
        monkeypatch.setattr(job_export, "REPO_ROOT", str(root))
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        w = M.stored_waveform(conn)(rid, 2, 6)
    finally:
        conn.close()
    assert w is not None and list(w) == [2.0, 3.0, 4.0, 5.0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

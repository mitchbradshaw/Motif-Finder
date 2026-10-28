"""
test_cross_census_nulls.py
==========================
Cross-channel explorer S1: the census's nulls (D18 and X1 in `docs/prompts/changes/cross-channel-explorer-decisions.md`).

In plain words: every count the census prints sits beside what luck alone would give.
- **Rotation** slides one channel's whole train of events along the recording by at least an hour, which keeps each
  channel's own rhythm and destroys only their alignment; how often do they still co-occur?
- **The timetable** asks, of a pair that does co-occur, whether its lags keep time: the largest number of its lags
  within ±2 s of one value, against the same number of lags measured between the same channels at random times.
- **Breadth** asks how many channels have an onset near a random instant.
p = (1 + draws at or above the observed) / (K + 1); per-pair p-values are corrected with Benjamini–Hochberg
through the one existing implementation (`seeded_search.corrected_levels`).
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

from Working import cross_census as cc  # noqa: E402
from Working.discovery.seeded_search import corrected_levels  # noqa: E402

K = cc.DEFAULT_CONSTANTS


def test_p_is_one_plus_the_draws_at_or_above_over_k_plus_one():
    assert cc.p_value(5, np.array([0, 1, 5, 7])) == pytest.approx(3 / 5)
    assert cc.p_value(9, np.zeros(999)) == pytest.approx(1 / 1000)


def test_the_constants_are_the_decided_numbers():
    assert K.onset_window_s == (-60.0, 180.0)
    assert K.timetable_delta_s == 2.0
    assert K.rotation_k == 1000 and K.timetable_k == 1000 and K.breadth_k == 1000 and K.waveform_k == 100
    assert K.min_rotation_s == 3600.0 and K.timetable_pool_min == 2000
    assert K.breadth_fraction == 0.5 and K.amplitude_band == 2.0 and K.q == 0.05
    d = K.as_dict()
    assert d["census_version"] == cc.CENSUS_VERSION and d["onset_window_s"] == [-60.0, 180.0]


def test_rotation_offsets_keep_every_pair_of_channels_an_hour_apart():
    off = cc.rotation_offsets(16, 20 * 3600.0, 500, 3600.0, seed=7)
    assert off.shape == (500, 16)
    T = 20 * 3600.0
    for row in off[:50]:
        d = np.abs(row[:, None] - row[None, :]) % T
        d = np.minimum(d, T - d)
        assert (d[~np.eye(16, dtype=bool)] >= 3600.0 - 1e-6).all()
    assert np.array_equal(off, cc.rotation_offsets(16, T, 500, 3600.0, seed=7))       # seeded


def test_rotation_refuses_a_recording_too_short_to_rotate():
    with pytest.raises(ValueError, match="too short"):
        cc.rotation_offsets(16, 10 * 3600.0, 10, 3600.0, seed=0)


def test_count_co_counts_every_pair_of_onsets_within_the_window():
    assert cc.count_co(np.array([0.0, 100.0]), np.array([30.0, 60.0, 500.0]), 50.0) == 3


def test_rotation_counts_observed_and_drawn():
    T = 50 * 3600.0
    a = np.arange(10) * 3600.0 + 1800
    on = {1: a, 2: a + 10.0, 3: np.array([7000.0])}
    obs, draws = cc.rotation_counts(on, T, [(1, 2), (1, 3)], 50.0, K, seed=3)
    assert list(obs) == [10, 0]
    assert draws.shape == (K.rotation_k, 2)
    assert cc.p_value(obs[0], draws[:, 0]) <= 0.01
    assert cc.p_value(obs[1], draws[:, 1]) == 1.0


def test_timetable_scan_finds_the_shared_lag_and_reports_median_and_mad():
    lags = np.array([12.0, 12.5, 11.5, 12.0, -30.0, 40.0, 12.2])
    t = cc.timetable_scan(lags, 2.0, 1.0, 50.0)
    assert t["count"] == 5
    assert t["L_s"] == pytest.approx(12.0, abs=0.3) and t["median_lag_s"] == pytest.approx(12.0)
    assert t["mad_s"] == pytest.approx(0.2, abs=0.11)


def test_timetable_scan_never_centres_inside_the_artifact_line():
    t = cc.timetable_scan(np.array([0.0, 0.1, -0.2, 0.0]), 2.0, 1.0, 50.0)
    # L must satisfy 1 s < |L| <= 50 s: lags near 0 can still fall within ±2 s of L = ±1.x
    assert 1.0 < abs(t["window_centre_s"]) <= 50.0


def test_the_timetable_null_resamples_n_lags_from_the_pool():
    rng = np.random.default_rng(0)
    pool = rng.uniform(-50, 50, size=4000)
    null = cc.timetable_null(30, pool, K, 1.0, 50.0, seed=1)
    assert null.shape == (K.timetable_k,)
    assert null.max() < 30 and np.median(null) < 8
    assert cc.p_value(30, null) == pytest.approx(1 / (K.timetable_k + 1))
    assert np.array_equal(null, cc.timetable_null(30, pool, K, 1.0, 50.0, seed=1))


def test_the_timetable_pool_measures_lags_at_random_other_times():
    rng = np.random.default_rng(2)
    x = rng.standard_normal(40_000)
    y = rng.standard_normal(40_000)
    windows = [(1000, 1240), (5000, 5240)]
    pool = cc.timetable_pool(x, y, windows, 1.0, 50, size=K.timetable_pool_min, seed=4)
    assert len(pool) >= K.timetable_pool_min
    assert np.abs(pool).max() <= 50.0
    assert np.array_equal(pool, cc.timetable_pool(x, y, windows, 1.0, 50, size=K.timetable_pool_min, seed=4))


def test_breadth_null_counts_channels_near_a_random_instant():
    T = 100 * 3600.0
    on = {i: np.array([1800.0 + 7200.0 * k for k in range(40)]) + i * 3.0 for i in range(4)}
    null = cc.breadth_null(on, T, 50.0, K, seed=2)
    assert null.shape == (K.breadth_k,) and null.min() >= 1 and null.max() <= 4
    sparse = {i: np.array([1000.0 * (i + 1)]) for i in range(4)}
    assert cc.p_value(4, cc.breadth_null(sparse, T, 50.0, K, seed=2)) <= 0.01


def test_bh_goes_through_corrected_levels():
    ps = [0.001, 0.02, 0.04, 0.5]
    assert cc.bh(ps, 0.05) == corrected_levels(ps, alpha=0.05, correction="bh")
    assert cc.bh([], 0.05) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

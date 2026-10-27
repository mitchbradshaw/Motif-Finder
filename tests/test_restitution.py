"""Restitution test: does an event's recovery depend on the gap before it? (Pipelines/fhn/restitution.py)"""

import numpy as np
import pytest

from Pipelines.fhn import restitution as R


def _train(n, rng, slope=0.0, depth_effect=0.0, noise=1.0):
    """n events: onsets with random gaps, recovery = slope * gap_before (+ depth) + noise."""
    gaps = rng.uniform(50.0, 150.0, n - 1)
    onsets = np.concatenate([[0.0], np.cumsum(gaps)])
    depth = rng.uniform(1.0, 5.0, n)
    rec = 20.0 + depth_effect * depth + noise * rng.standard_normal(n)
    rec[1:] += slope * gaps
    return onsets, rec, depth


def test_pairs_take_the_gap_before_each_event_from_inter_event_intervals():
    onsets = np.array([0.0, 10.0, 25.0, 45.0])
    rec = np.array([1.0, 2.0, 3.0, np.nan])
    depth = np.array([5.0, 6.0, 7.0, 8.0])
    p = R.event_pairs(onsets, rec, depth=depth)
    np.testing.assert_allclose(p["gap"], [10.0, 15.0])          # the NaN recovery is dropped
    np.testing.assert_allclose(p["recovery"], [2.0, 3.0])
    np.testing.assert_allclose(p["depth"], [6.0, 7.0])
    np.testing.assert_array_equal(p["event_index"], [1, 2])


def test_pairs_split_at_a_gap_longer_than_max_gap():
    onsets = np.array([0.0, 10.0, 20.0, 1000.0, 1010.0])
    rec = np.ones(5)
    p = R.event_pairs(onsets, rec, max_gap=100.0)
    np.testing.assert_allclose(p["gap"], [10.0, 10.0, 10.0])    # the 980 gap is not a pair


def test_a_planted_positive_relation_is_found_and_its_null_is_calibrated():
    rng = np.random.default_rng(0)
    on, rec, depth = _train(40, rng, slope=0.2, noise=3.0)
    res = R.restitution(R.event_pairs(on, rec, depth=depth), n_perm=1000, seed=1)
    assert res["rho"] > 0.5
    assert res["p_two"] < 0.01 and res["p_greater"] < 0.01
    assert res["p_less"] > 0.9
    # with no relation the permutation p is uniform: about 5 % of independent trains fall below 0.05
    ps = []
    for k in range(200):
        on, rec, depth = _train(20, np.random.default_rng(100 + k))
        ps.append(R.restitution(R.event_pairs(on, rec, depth=depth), n_perm=199, seed=k)["p_two"])
    assert 0.01 <= np.mean(np.array(ps) < 0.05) <= 0.10


def test_the_permutation_null_is_seeded():
    on, rec, depth = _train(15, np.random.default_rng(3), slope=0.05)
    pr = R.event_pairs(on, rec, depth=depth)
    assert R.restitution(pr, n_perm=500, seed=7) == R.restitution(pr, n_perm=500, seed=7)


def test_partial_correlation_removes_a_depth_confound():
    """Recovery driven by depth only, and depth tracking the gap: the raw rho is strong, the
    rho controlling for depth is not."""
    rng = np.random.default_rng(5)
    n = 60
    gaps = rng.uniform(50, 150, n - 1)
    onsets = np.concatenate([[0.0], np.cumsum(gaps)])
    depth = np.concatenate([[3.0], 0.05 * gaps + 0.3 * rng.standard_normal(n - 1)])
    rec = 10.0 * depth + 0.5 * rng.standard_normal(n)
    res = R.restitution(R.event_pairs(onsets, rec, depth=depth), n_perm=1000, seed=0)
    assert res["rho"] > 0.6 and res["p_two"] < 0.01
    assert abs(res["partial_depth"]["rho"]) < 0.3
    assert res["partial_depth"]["p_two"] > 0.05


def test_partial_spearman_matches_the_residual_definition():
    rng = np.random.default_rng(2)
    z = rng.standard_normal(50)
    x = z + 0.5 * rng.standard_normal(50)
    y = z + 0.5 * rng.standard_normal(50)
    r = R.partial_spearman(x, y, z[:, None])
    assert -0.4 < r < 0.4
    assert R.partial_spearman(x, x, z[:, None]) == pytest.approx(1.0)


def test_combination_sign_count_stouffer_and_fisher():
    rng = np.random.default_rng(11)
    pos = [R.restitution(R.event_pairs(*_train(25, rng, slope=0.05, noise=3.0)), n_perm=500, seed=i)
           for i in range(12)]
    c = R.combine(pos)
    assert c["n_sequences"] == 12
    assert c["n_rho_negative"] <= 3
    assert c["sign_p_two"] < 0.05
    assert c["stouffer_z"] > 3 and c["stouffer_p_two"] < 0.01
    assert c["fisher_p"] < 0.01
    null = [R.restitution(R.event_pairs(*_train(25, rng)), n_perm=500, seed=i) for i in range(12)]
    cn = R.combine(null)
    assert cn["stouffer_p_two"] > 0.01
    assert abs(cn["stouffer_z"]) < 2.6


def test_too_few_pairs_is_refused_in_words_not_a_number():
    res = R.restitution(R.event_pairs(np.array([0.0, 10, 20]), np.ones(3)), n_perm=100)
    assert res["rho"] is None and "pairs" in res["why"]
    assert R.combine([res])["n_sequences"] == 0


def test_the_gap_after_control_pairs_each_event_with_the_next_gap():
    onsets = np.array([0.0, 10.0, 25.0, 45.0])
    rec = np.array([1.0, 2.0, 3.0, 4.0])
    p = R.event_pairs(onsets, rec, which="after")
    np.testing.assert_allclose(p["gap"], [10.0, 15.0, 20.0])
    np.testing.assert_allclose(p["recovery"], [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(p["event_index"], [0, 1, 2])
    with pytest.raises(ValueError):
        R.event_pairs(onsets, rec, which="sideways")

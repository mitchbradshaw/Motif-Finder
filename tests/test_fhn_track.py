"""Per-cycle model tracking: held-out-cycle prediction and parameter drift (Pipelines/fhn/track.py)."""

import numpy as np
import pytest

from Pipelines.fhn import fit as F
from Pipelines.fhn import track as T


def _cycles(n_cycles, noise, seed=0, n=100):
    tau = np.arange(n) / n
    clean = 5.0 * F.jump_exp_kernel(tau, 0.1, 0.15)
    rng = np.random.default_rng(seed)
    return tau, clean, clean + noise * rng.standard_normal((n_cycles, n))


def _kernel_curve(tau, y):
    f = F.fit_jump_exp(tau, y, rise=False)
    return f["fitted"], {"decay_frac": f["params"]["decay_frac"]}


def _identity(tau, y):
    return y.copy(), {}


def test_blocks_are_contiguous_and_cover_every_cycle():
    b = T.blocks(10, 3)
    assert [list(x) for x in b] == [[0, 1, 2], [3, 4, 5], [6, 7, 8, 9]]      # a short tail joins the last block
    assert [list(x) for x in T.blocks(9, 3)] == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]


def test_heldout_never_trains_on_the_cycle_it_predicts():
    tau, _, C = _cycles(12, 0.5)
    seen = []

    def spy(tau, y):
        seen.append(y.copy())
        return y.copy(), {}

    res = T.heldout(tau, C, spy, block=3)
    for i, row in enumerate(res["cycles"]):
        assert i not in row["train_cycles"]
        assert row["train_cycles"]                                  # every cycle has a neighbour block
    assert len(seen) == 4                                           # one fit per block, reused


def test_an_identity_model_ties_the_baseline_exactly():
    tau, _, C = _cycles(12, 0.5)
    res = T.heldout(tau, C, _identity, block=3)
    assert res["summary"]["median_ratio"] == pytest.approx(1.0)
    assert res["summary"]["pooled_ratio"] == pytest.approx(1.0)


def test_the_right_model_beats_the_mean_of_the_other_cycles_on_noisy_cycles():
    tau, clean, C = _cycles(15, 1.0, seed=1)
    res = T.heldout(tau, C, _kernel_curve, block=3)
    s = res["summary"]
    assert s["pooled_ratio"] < 0.95
    assert s["fraction_model_better"] > 0.6
    # its block parameters are the planted recovery
    assert np.median(res["params"]["decay_frac"]) == pytest.approx(0.15, rel=0.3)


def test_drift_test_finds_a_planted_trend():
    rng = np.random.default_rng(0)
    x = np.linspace(0, 3, 30) + 0.5 * rng.standard_normal(30)
    d = T.drift_test(x, n_perm=1000, seed=0)
    assert d["rho"] > 0.7 and d["p_rho"] < 0.01
    assert d["von_neumann"] < 1.0 and d["p_sssd"] < 0.01


def test_drift_test_is_calibrated_on_a_stationary_series():
    hits_rho = hits_sssd = 0
    for k in range(200):
        x = np.random.default_rng(1000 + k).standard_normal(20)
        d = T.drift_test(x, n_perm=199, seed=k)
        hits_rho += d["p_rho"] < 0.05
        hits_sssd += d["p_sssd"] < 0.05
    assert 2 <= hits_rho <= 20 and 2 <= hits_sssd <= 20


def test_drift_test_ignores_nan_entries_and_refuses_short_series():
    x = np.array([1.0, np.nan, 2.0, 3.0, np.nan, 4.0, 5.0, 6.0])
    d = T.drift_test(x, n_perm=200, seed=0)
    assert d["n"] == 6 and d["rho"] == pytest.approx(1.0)
    assert T.drift_test(np.array([1.0, 2.0, 3.0]), n_perm=10)["rho"] is None

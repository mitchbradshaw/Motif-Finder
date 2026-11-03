"""Spontaneous phase-timing estimate and return map (Pipelines/fhn/empirical_prc.py)."""

import numpy as np

from Pipelines.fhn import empirical_prc as E


def _train(n=150, coupled=True, seed=0):
    """Cycles of 100 points whose wiggle in bins 12-13 sets the cycle length (when coupled)."""
    rng = np.random.default_rng(seed)
    base = -np.exp(-np.arange(100) / 20.0)
    W = rng.standard_normal((n, 100)) * 0.2
    C = base + W
    bump = C[:, 60:70].mean(axis=1) - base[60:70].mean()
    L = 100.0 + (-30.0 * bump if coupled else 0.0) + rng.standard_normal(n) * 0.5
    return C, L


def test_timing_residuals_remove_a_slow_drift():
    L = 100 + np.arange(80) * 0.5
    dT = E.timing_residuals(L)
    assert np.max(np.abs(dT[5:-5])) < 1e-9


def test_recovers_a_planted_phase_timing_coupling():
    C, L = _train()
    r = E.estimate(C, L, n_shuffle=100, n_boot=100, seed=0)
    Z = np.array(r["Z_rad_per_mV"])
    # a positive deviation in bins 12-13 makes the cycle SHORTER: an advance, positive Z
    assert np.argmax(Z) in (12, 13)
    assert r["cv_r2"] > r["nulls"]["shuffle"]["cv_r2_q95"]
    assert r["train_clears"]
    assert any(r["bins_clear"][12:14])


def test_no_coupling_does_not_clear():
    C, L = _train(coupled=False, seed=3)
    r = E.estimate(C, L, n_shuffle=100, n_boot=50, seed=1)
    assert not r["train_clears"]


def test_fake_trains_enter_as_their_own_null():
    C, L = _train()
    rng = np.random.default_rng(5)
    fakes = {"surrogate": [C + rng.standard_normal(C.shape) * 0.2 for _ in range(5)]}
    r = E.estimate(C, L, fake_cycles=fakes, n_shuffle=50, n_boot=20)
    assert r["nulls"]["surrogate"]["draws"] == 5


def test_return_map_sees_alternation_and_ignores_drift():
    L = np.array([100.0, 120.0] * 40) + np.random.default_rng(0).standard_normal(80)
    rm = E.return_map(L, n_shuffle=200)
    assert rm["raw"]["rho"] < -0.8 and rm["raw"]["p_two"] < 0.01
    drift = 100 + np.arange(80) * 1.0 + np.random.default_rng(1).standard_normal(80) * 0.1
    rm = E.return_map(drift, n_shuffle=200)
    assert rm["raw"]["rho"] > 0.9                 # drift alone makes the raw map rise
    assert abs(rm["detrended"]["rho"]) < 0.5      # and the running median takes it out


def test_kept_index_breaks_the_running_windows_at_dropped_cycles():
    L = np.full(30, 100.0)
    kept = np.r_[np.arange(10), np.arange(20, 40)]
    rm = E.return_map(L + np.random.default_rng(0).standard_normal(30), kept=kept, n_shuffle=20)
    assert rm["n_pairs"] == 28

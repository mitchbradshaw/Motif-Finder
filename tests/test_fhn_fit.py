"""FitzHugh-Nagumo waveform fitter (Pipelines/fhn/fit.py)."""

import numpy as np
import pytest

from Pipelines.fhn import fit as F
from Pipelines.fhn import model as M


def _synthetic_cycle(alpha, b, c, gain, offset, phi, n=200, noise=0.0, seed=0):
    cyc = F.fast_cycle(alpha, b, c)
    tau = np.arange(n) / n
    m = np.interp((2 * np.pi * tau + phi) % (2 * np.pi), cyc.phases, cyc.states[:, 0], period=2 * np.pi)
    y = offset + gain * m
    rng = np.random.default_rng(seed)
    return tau, y + noise * np.std(y) * rng.standard_normal(n)


def test_alpha_round_trips_through_the_fixed_point_parameterisation():
    a, b, c, z = 0.7, 0.8, 3.0, -0.4
    u = F.u_from_alpha(a + b * z, b, c)
    assert -1 < u < 1
    assert F.alpha_from_u(u, b, c) == pytest.approx(a + b * z, abs=1e-12)


def test_oscillator_fit_recovers_known_parameters_from_a_noisy_synthetic_cycle():
    alpha, b, c = 0.7 - 0.8 * 0.4, 0.8, 3.0
    tau, y = _synthetic_cycle(alpha, b, c, gain=-8.0, offset=3.0, phi=1.1, noise=0.03)
    res = F.fit_oscillator(tau, y, restarts=4, seed=1)
    assert res["params"]["b"] == pytest.approx(b, abs=0.12)
    assert res["params"]["c"] == pytest.approx(c, rel=0.15)
    assert res["params"]["alpha"] == pytest.approx(alpha, abs=0.1)
    assert res["params"]["gain"] == pytest.approx(-8.0, rel=0.1)
    assert res["params"]["time_ratio"] == pytest.approx(1.0, abs=0.03)
    # the residual is the noise we put in, not more
    assert res["rmse"] < 1.3 * 0.03 * np.std(y)


def test_jump_exp_fit_recovers_its_own_recovery_time():
    tau = np.arange(200) / 200
    t0, td = 0.1, 0.15
    s = (tau - t0) % 1.0
    y = 2.0 - 5.0 * np.exp(-s / td) + 0.02 * np.random.default_rng(3).standard_normal(200)
    res = F.fit_jump_exp(tau, y, rise=False)
    assert res["params"]["t0_frac"] == pytest.approx(t0, abs=0.01)
    assert res["params"]["decay_frac"] == pytest.approx(td, rel=0.1)


def test_a_single_excursion_from_rest_prefers_the_excitable_regime():
    # one excitable FHN excursion, then a long rest: the excitable fit should win by AIC
    tau = np.arange(240) / 240
    y = F.excitable_waveform(tau, u_ex=0.25, b=0.8, c=3.0, kick=1.2, span=25.0, t0_frac=0.1, gain=4.0, offset=-1.0)
    y = y + 0.02 * np.std(y) * np.random.default_rng(5).standard_normal(tau.size)
    osc = F.fit_oscillator(tau, y, restarts=3, seed=2)
    exc = F.fit_excitable(tau, y, restarts=3, seed=2)
    assert exc["aic"] < osc["aic"]
    assert exc["r2"] > 0.99

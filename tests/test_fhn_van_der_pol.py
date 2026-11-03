"""van der Pol oscillator and its cycle fitter (Pipelines/fhn/van_der_pol.py, oscfit.py)."""

import numpy as np
import pytest

from Pipelines.fhn import fit as F
from Pipelines.fhn import oscfit as O
from Pipelines.fhn import van_der_pol as V


def test_small_mu_is_a_sinusoid_of_period_two_pi_and_amplitude_two():
    c = O.planar_cycle(V.vdp(0.1))
    assert c.T == pytest.approx(2 * np.pi, rel=2e-3)
    assert np.ptp(c.states[:, 0]) == pytest.approx(4.0, rel=2e-3)


def test_large_mu_period_follows_the_relaxation_law():
    c = O.planar_cycle(V.vdp(10.0))
    assert c.T == pytest.approx((3 - 2 * np.log(2)) * 10.0, rel=0.15)


def test_phase_zero_is_the_voltage_maximum():
    c = O.planar_cycle(V.vdp(2.0))
    assert int(np.argmax(c.states[:, 0])) == 0


def test_fit_recovers_a_synthetic_cycle_with_gain_and_offset():
    tau = np.arange(200) / 200
    cyc = O.planar_cycle(V.vdp(3.0))
    y = 2.0 + 5.0 * F.oscillator_model(tau, cyc, 1.0, 1.0)
    f = V.fit_vdp(tau, y)
    assert f["model"] == "van_der_pol"
    assert f["k"] == 5
    assert f["r2"] > 0.995
    assert f["params"]["gain"] == pytest.approx(5.0, rel=0.1)


def test_vdp_prc_is_type_ii_and_the_adjoint_agrees():
    _, pr, _, adj, agree = O.prc_bundle(V.vdp(3.0), n_base=60)
    t = O.prc_type(pr["ground_truth"])
    assert t["type"] == "II"
    assert agree["relative"] < 0.02

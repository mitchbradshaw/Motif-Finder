"""Morris-Lecar model, its two classes and their PRC types (Pipelines/fhn/morris_lecar.py, oscfit.py)."""

import numpy as np
import pytest

from Pipelines.fhn import morris_lecar as ML
from Pipelines.fhn import oscfit as O


def test_snic_class_rests_below_threshold_and_oscillates_above():
    with pytest.raises(RuntimeError):
        O.planar_cycle(ML.morris_lecar(35.0, cls="snic"))
    c = O.planar_cycle(ML.morris_lecar(41.0, cls="snic"))
    assert np.ptp(c.states[:, 0]) > 50                  # a full spike in mV
    # near the saddle-node the period is long; well above it, short
    assert c.T > 3 * O.planar_cycle(ML.morris_lecar(80.0, cls="snic")).T


def test_jacobian_matches_finite_differences():
    for cls in ("hopf", "snic"):
        osc = ML.morris_lecar(100.0, cls=cls)
        x = np.array([-20.0, 0.2])
        h = 1e-6
        J = np.stack([(osc.f(x + h * e) - osc.f(x - h * e)) / (2 * h) for e in np.eye(2)], axis=1)
        assert np.allclose(osc.jac(x), J, rtol=1e-5, atol=1e-8)


def test_snic_near_onset_is_type_i_and_hopf_is_type_ii():
    _, pr, _, _, ag = O.prc_bundle(ML.morris_lecar(41.0, cls="snic"), n_base=50)
    t1 = O.prc_type(pr["ground_truth"])
    assert t1["type"] == "I" and t1["sign"] == "advance"
    assert ag["relative"] < 0.05
    _, pr, _, _, _ = O.prc_bundle(ML.morris_lecar(95.0, cls="hopf"), n_base=50)
    assert O.prc_type(pr["ground_truth"])["type"] == "II"


def test_prc_type_reads_the_minority_area():
    ph = np.linspace(0, 2 * np.pi, 100, endpoint=False)
    assert O.prc_type(1 - np.cos(ph))["type"] == "I"
    assert O.prc_type(-np.sin(ph))["type"] == "II"
    assert O.prc_type(-(1 - np.cos(ph)))["sign"] == "delay"

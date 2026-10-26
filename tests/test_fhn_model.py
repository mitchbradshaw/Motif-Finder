"""FitzHugh-Nagumo model core (Pipelines/fhn/model.py).

Reference: Wilshin, Kvalheim & Revzen (2024), "Phase response curves and the role of
coordinates", Biol Cybern 118:311-330, doi:10.1007/s00422-024-00997-w. Eq. 17 is the
model; Appendix B the period; Sect. 6.1 the perturbation ("ground truth") PRC; Sect. 4.1
the Hopf example whose PRC is known in closed form; Sect. 6.2 the delay-coordinate PRC.
"""

import numpy as np
import pytest

from Pipelines.fhn import model as M


def test_paper_parameters_give_the_papers_period():
    # Appendix B's initial guess is 3 x 3.743 = 11.229; fmin on the loop distance refines it.
    cyc = M.limit_cycle(M.fhn(**M.PAPER), n=2000)
    assert cyc.T == pytest.approx(3 * 3.743, abs=0.02)
    # the sampled loop closes: the state one period on is the start
    end = M.integrate(cyc.osc, cyc.states[0], [0.0, cyc.T])[-1]
    assert np.linalg.norm(end - cyc.states[0]) < 1e-6


def test_a_and_z_enter_v_only_through_a_plus_bz():
    # w is hidden: shifting w by z leaves v(t) unchanged when a + b z is held fixed.
    b = 0.8
    p1 = dict(a=0.7, b=b, c=3.0, z=-0.4)
    p2 = dict(a=0.7 + b * 0.3, b=b, c=3.0, z=-0.4 - 0.3)
    t = np.linspace(0, 30, 301)
    x1 = M.integrate(M.fhn(**p1), [1.0, 0.0], t)
    x2 = M.integrate(M.fhn(**p2), [1.0, 0.0 + 0.3], t)  # the same state in shifted w
    assert np.max(np.abs(x1[:, 0] - x2[:, 0])) < 1e-7


def test_phase_projection_returns_the_cycles_own_phase():
    cyc = M.limit_cycle(M.fhn(**M.PAPER), n=2000)
    idx = np.arange(0, 2000, 37)
    ph = cyc.phase_of(cyc.states[idx])
    d = np.angle(np.exp(1j * (ph - cyc.phases[idx])))
    assert np.max(np.abs(d)) < 1e-9
    # half-way between two samples projects to the half-way phase
    mid = 0.5 * (cyc.states[100] + cyc.states[101])
    assert cyc.phase_of(mid[None])[0] == pytest.approx(0.5 * (cyc.phases[100] + cyc.phases[101]), abs=1e-9)


def test_hopf_perturbation_prc_matches_the_closed_form():
    # Sect. 4.1: theta' = w, r' = 1 - r; on r = 1 the PRCs are d theta/dx = -sin(phi), d theta/dy = cos(phi).
    cyc = M.limit_cycle(M.hopf(omega=1.3), n=2000)
    ph, rx = M.prc_perturbation(cyc, [1.0, 0.0], eps=1e-3, n_base=60)
    _, ry = M.prc_perturbation(cyc, [0.0, 1.0], eps=1e-3, n_base=60)
    ang = np.arctan2(cyc.state_at(ph)[:, 1], cyc.state_at(ph)[:, 0])
    assert np.max(np.abs(rx - (-np.sin(ang)))) < 2e-3
    assert np.max(np.abs(ry - np.cos(ang))) < 2e-3


def test_fhn_perturbation_prc_matches_the_adjoint():
    # Two independent estimates of the voltage PRC with w held fixed: finite perturbation
    # (the paper's ground truth, Sect. 6.1) and the adjoint equation Z' = -J^T Z.
    cyc = M.limit_cycle(M.fhn(**M.PAPER), n=2000)
    ph, rv = M.prc_perturbation(cyc, [1.0, 0.0], eps=1e-3, n_base=80)
    Z = M.prc_adjoint(cyc)
    zv = np.interp(ph, cyc.phases, Z[:, 0], period=2 * np.pi)
    scale = np.max(np.abs(zv))
    assert np.max(np.abs(rv - zv)) < 0.02 * scale
    # the adjoint is normalised so that Z . f = 2 pi / T everywhere on the cycle
    zf = np.sum(Z * cyc.osc.f(cyc.states), axis=1)
    assert np.allclose(zf, 2 * np.pi / cyc.T, rtol=1e-3)


def test_prc_on_the_papers_figure_axis_reproduces_fig4_range():
    # The paper's figures use coordinates centred on the fixed point and rotated by 9.5 degrees
    # (its figure code); along that rotated voltage axis, Fig. 4's ground-truth PRC runs from
    # about -2.2 to about 2.6 rad per unit. In eq. 17's own (v, w) it runs about -3.2 to 1.3.
    cyc = M.limit_cycle(M.fhn(**M.PAPER), n=2000)
    a = np.deg2rad(-9.5)
    _, r = M.prc_perturbation(cyc, [np.cos(a), np.sin(a)], eps=1e-2, n_base=200)
    assert r.min() == pytest.approx(-2.2, abs=0.1)
    assert r.max() == pytest.approx(2.6, abs=0.1)


def test_delay_coordinate_prc_differs_and_its_correction_recovers_the_ground_truth():
    # Sect. 6.2 / Fig. 4: holding the delayed voltage fixed is not holding w fixed; the
    # delay map's Jacobian converts one into the other.
    cyc = M.limit_cycle(M.fhn(**M.PAPER), n=2000)
    out = M.delay_prcs(cyc, delta=0.1, eps=1e-3, n_base=80)
    gt, cd, corr = out["ground_truth"], out["constant_delay"], out["corrected"]
    ok = out["well_conditioned"]
    assert ok.mean() > 0.9
    scale = np.max(np.abs(gt))
    assert np.max(np.abs(cd - gt)[ok]) > 0.2 * scale          # visibly a different curve
    assert np.max(np.abs(corr - gt)[ok]) < 0.03 * scale       # and the correction undoes it

"""Izhikevich (2003) simple model and its cycle fitter (Pipelines/fhn/izhikevich.py)."""

import numpy as np
import pytest

from Pipelines.fhn import izhikevich as IZ

RS = dict(a=0.02, b=0.2, c=-65.0, d=8.0)          # Izhikevich 2003, regular spiking


def test_below_rheobase_it_rests_and_never_spikes():
    # b = 0.2: the resting point is a root of 0.04 v^2 + 4.8 v + 140 + I = 0; it vanishes at I = 4
    sim = IZ.simulate(**RS, I=3.5, t_end=2000.0)
    assert len(sim["spike_times"]) == 0
    v_rest = (-4.8 + np.sqrt(4.8 ** 2 - 4 * 0.04 * (140 + 3.5))) / (2 * 0.04)
    assert sim["v"][-1] == pytest.approx(v_rest, abs=0.05)


def test_above_rheobase_it_spikes_and_resets():
    sim = IZ.simulate(**RS, I=10.0, t_end=1000.0)
    st = sim["spike_times"]
    assert len(st) > 5
    assert np.max(sim["v"]) <= IZ.V_PEAK + 1e-9          # v is cut at the peak, never past it
    # right after every spike v is at c and u has jumped by d
    for k in sim["reset_index"]:
        assert sim["v"][k] == pytest.approx(RS["c"])
        assert sim["u"][k] - sim["u_before_reset"][list(sim["reset_index"]).index(k)] == pytest.approx(RS["d"])
    # regular spiking adapts: the first interval is the shortest, then it settles
    isi = np.diff(st)
    assert isi[0] < isi[-1]
    assert isi[-1] == pytest.approx(isi[-2], rel=1e-3)


def test_the_periodic_orbit_is_the_settled_interval():
    orb = IZ.periodic_orbit(**RS, I=10.0, n=500)
    sim = IZ.simulate(**RS, I=10.0, t_end=3000.0)
    assert orb["T"] == pytest.approx(np.diff(sim["spike_times"])[-1], rel=2e-3)
    assert orb["v"][0] == pytest.approx(RS["c"])            # phase 0 is the reset
    assert orb["v"].max() < IZ.V_PEAK + 1e-9 and orb["v"].max() > 0


def test_no_orbit_below_rheobase():
    with pytest.raises(RuntimeError):
        IZ.periodic_orbit(**RS, I=3.0)


def test_fit_recovers_a_planted_waveform():
    tau = np.arange(200) / 200
    p = dict(a=0.03, b=0.22, c=-60.0, d=5.0, I=12.0)
    orb = IZ.periodic_orbit(**p, n=1000)
    y = 2.0 - 0.1 * IZ.waveform(tau, orb, 1.0, 1.3)
    y = y + 0.01 * np.std(y) * np.random.default_rng(0).standard_normal(tau.size)
    res = IZ.fit_izhikevich(tau, y, restarts=4, seed=0)
    assert res["model"] == "izhikevich" and res["k"] == 9
    assert res["r2"] > 0.99
    assert res["params"]["gain"] < 0
    assert set(("a", "b", "c", "d", "I", "time_ratio", "phase_shift", "gain", "offset")) <= set(res["params"])
    assert res["fitted"].shape == y.shape

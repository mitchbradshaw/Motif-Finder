"""Hindmarsh-Rose model and the bursting rule for drop trains (Pipelines/fhn/hindmarsh_rose.py)."""

import numpy as np

from Pipelines.fhn import hindmarsh_rose as HR


def test_standard_parameters_burst():
    orb = HR.bursting_orbit(r=0.005, I=2.0)
    assert orb["spikes_per_burst"] >= 3
    assert orb["states"].shape == (2000, 3)


def test_regular_train_is_not_bursting():
    rng = np.random.default_rng(0)
    on = np.cumsum(100 + 10 * rng.standard_normal(80))
    b = HR.burst_structure(on)
    assert not b["bursting"]
    assert b["n_groups"] == 1


def test_grouped_train_is_bursting():
    rng = np.random.default_rng(1)
    on, t = [], 0.0
    for _ in range(8):
        for _ in range(6):
            on.append(t)
            t += 10 + rng.uniform(-1, 1)
        t += 100
    b = HR.burst_structure(on)
    assert b["bursting"]
    assert b["n_groups"] == 8
    assert b["group_sizes"] == [6] * 8


def test_too_few_events_is_not_bursting():
    assert not HR.burst_structure([0, 1, 2, 30, 31])["bursting"]

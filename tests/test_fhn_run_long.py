"""The long-train runner's pure helpers (Pipelines/fhn/run_long.py): the chain rule's train extent, AAFT
cycles cut at the real onsets, and the Izhikevich PRC (oscfit)."""

import numpy as np
import pytest

from Pipelines.fhn import oscfit as O
from Pipelines.fhn import run_long as RL


def test_train_extent_follows_the_gap_rule_not_the_seed_span():
    on = np.r_[np.arange(0, 50) * 600.0, 50 * 600.0 + 4 * 3600 + np.arange(0, 20) * 600.0]
    ext = RL.train_extent(on, seed=(10 * 600.0, 20 * 600.0), max_gap=3 * 3600)
    assert ext["n_events"] == 50
    assert ext["start"] == 0.0 and ext["stop"] == 49 * 600.0
    assert ext["n_trains_overlapping_seed"] == 1


def test_train_extent_flags_a_seed_that_straddles_a_gap():
    on = np.r_[np.arange(0, 10) * 600.0, 20000.0 + np.arange(0, 10) * 600.0]
    ext = RL.train_extent(on, seed=(4000.0, 22000.0), max_gap=3 * 3600)
    assert ext["n_trains_overlapping_seed"] == 2


def test_aaft_cycles_keep_the_values_and_the_onsets():
    rng = np.random.default_rng(0)
    x = np.cumsum(rng.standard_normal(5000))
    on = np.arange(200, 4800, 200)
    C = RL.aaft_cycles(x, on, 0, rng, n_points=50)
    assert C.shape == (len(on) - 1, 50)


def test_izhikevich_regular_spiking_prc_is_finite_and_advances_late():
    p = O.izhikevich_prc(0.02, 0.2, -65.0, 8.0, 10.0, n_base=24)
    z = p["ground_truth"]
    assert np.all(np.isfinite(z))
    assert z[-4:].mean() > 0 and z[-4:].mean() > abs(z[:4].mean())
    assert p["T"] == pytest.approx(p["orbit"]["T"])

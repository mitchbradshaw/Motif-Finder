"""B5 (Chapter 10): what the Discovery Maps show about when the detectors fire - detector rates rising and falling
together over a recording, against random time shifts and the paired surrogate runs."""
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "thesis"))

import b5_map_timing as B5  # noqa: E402


def test_counts_fall_in_the_maps_bins():
    # fs 1 Hz, 3 h bins: 10,800 samples each; the last bin is short
    c = B5.bin_counts([0, 10_799, 10_800, 25_000], n_samples=25_001, fs=1.0, bin_h=3.0)
    assert c.tolist() == [2, 1, 1]


def test_rates_that_share_bursts_comodulate_beyond_shifts():
    rng = np.random.default_rng(0)
    burst = np.zeros(120)
    burst[20:30] = 30
    burst[70:85] = 25
    M = np.array([rng.poisson(2 + burst) for _ in range(6)])
    c = B5.comodulation(M)
    null = B5.shift_null(M, draws=200, rng=np.random.default_rng(1))
    assert c > 0.4 and (1 + np.sum(null >= c)) / 201 < 0.01


def test_independent_rates_do_not():
    rng = np.random.default_rng(2)
    M = rng.poisson(5, size=(6, 120))
    c = B5.comodulation(M)
    null = B5.shift_null(M, draws=200, rng=np.random.default_rng(3))
    assert abs(c) < 0.15 and (1 + np.sum(null >= c)) / 201 > 0.05


def test_a_flat_row_is_left_out_not_counted_as_agreement():
    M = np.array([[0] * 50, [1, 2] * 25, [2, 1] * 25])
    assert B5.comodulation(M) == pytest.approx(-1.0)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

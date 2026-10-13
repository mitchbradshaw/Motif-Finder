"""
test_oasis.py
==============
W1-B: the OASIS core (`Working/Detection/deconvolution/oasis.py`), written from
Friedrich, Zhou & Paninski 2017 (PLoS Comput Biol 13(3):e1005423) without the
authors' GPL code. Fidelity is checked against a GENERIC solver of the same
optimisation (scipy's NNLS) instead of against their implementation:

* AR(1), no threshold, no penalty: OASIS == argmin ||c - y||^2 s.t. s >= 0;
* AR(1), l1 penalty lam: OASIS == argmin 1/2||c - y||^2 + lam*sum(s) s.t. s >= 0,
  which a generic solver reaches as an NNLS on y - lam * K^-T 1 (K the kernel
  matrix, inverted numerically here, not by the closed form the core uses);
* noise-free input with known jumps is recovered exactly, AR(1) and AR(2),
  with and without a minimum jump size;
* the thresholded form never emits a non-zero jump below s_min.

Runnable standalone:  python tests/test_oasis.py
"""

import os
import sys
import time

import numpy as np
import pytest
from scipy.optimize import nnls

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.Detection.deconvolution import oasis as O  # noqa: E402
from tests._deconv_synthetic import FS, HALF_S, gamma_for, kernel_sum, troughs_12h  # noqa: E402


def _kernel_matrix(n, g1, g2=0.0):
    """K with c = K s for c_t = g1 c_{t-1} + g2 c_{t-2} + s_t, c_{-1} = c_{-2} = 0."""
    h = np.zeros(n)
    h[0] = 1.0
    for k in range(1, n):
        h[k] = g1 * h[k - 1] + (g2 * h[k - 2] if k >= 2 else 0.0)
    K = np.zeros((n, n))
    for j in range(n):
        K[j:, j] = h[: n - j]
    return K


def _random_ar1_problem(rng, n=40):
    g = rng.uniform(0.6, 0.98)
    s = np.where(rng.random(n) < 0.15, rng.uniform(0.5, 3.0, n), 0.0)
    y = _kernel_matrix(n, g) @ s + 0.3 * rng.standard_normal(n)
    return y, g


# -- the helpers ----------------------------------------------------------------

def test_decay_from_half_time_is_the_per_sample_factor_that_halves_in_that_time():
    d = O.decay_from_half_time(120.0, 1.0)
    assert d == pytest.approx(2.0 ** (-1.0 / 120.0))
    assert d ** 120 == pytest.approx(0.5)
    assert O.decay_from_half_time(120.0, 2.0) ** 240 == pytest.approx(0.5)


def test_ar_coefficients_of_ar1_and_ar2():
    assert O.ar_coefficients(0.9, 0.0) == pytest.approx((0.9, 0.0))
    g1, g2 = O.ar_coefficients(0.9, 0.5)
    assert (g1, g2) == pytest.approx((1.4, -0.45))


# -- fidelity against a generic solver ------------------------------------------

@pytest.mark.parametrize("seed", range(12))
def test_ar1_unpenalised_equals_nnls(seed):
    rng = np.random.default_rng(seed)
    y, g = _random_ar1_problem(rng)
    c, s = O.oasis(y, decay=g)
    K = _kernel_matrix(len(y), g)
    s_ref, _ = nnls(K, y, maxiter=10_000)
    np.testing.assert_allclose(c, K @ s_ref, atol=1e-6)
    np.testing.assert_allclose(s, s_ref, atol=1e-6)


@pytest.mark.parametrize("seed", range(12))
def test_ar1_l1_penalised_equals_generic_qp(seed):
    rng = np.random.default_rng(100 + seed)
    y, g = _random_ar1_problem(rng)
    lam = float(rng.uniform(0.05, 0.6))
    c, s = O.oasis(y, decay=g, lam=lam)
    K = _kernel_matrix(len(y), g)
    # 1/2||Ks - y||^2 + lam 1's  ==  1/2||Ks - (y - lam K^-T 1)||^2 + const
    s_ref, _ = nnls(K, y - lam * np.linalg.solve(K.T, np.ones(len(y))), maxiter=10_000)
    np.testing.assert_allclose(c, K @ s_ref, atol=1e-6)
    np.testing.assert_allclose(s, s_ref, atol=1e-6)


def test_ar1_solution_is_feasible_and_consistent():
    rng = np.random.default_rng(7)
    y, g = _random_ar1_problem(rng, n=300)
    c, s = O.oasis(y, decay=g)
    assert np.all(s >= -1e-12) and np.all(c >= -1e-12)
    np.testing.assert_allclose(s[1:], c[1:] - g * c[:-1], atol=1e-10)
    assert s[0] == pytest.approx(c[0])


# -- exact recovery of noise-free input -----------------------------------------

@pytest.mark.parametrize("s_min", [0.0, 0.2])
def test_ar1_noise_free_jumps_are_recovered_exactly(s_min):
    n, g = 400, 0.97
    s_true = np.zeros(n)
    s_true[[20, 60, 75, 200, 330]] = [1.0, 2.5, 0.8, 1.7, 3.0]
    y = _kernel_matrix(n, g) @ s_true
    c, s = O.oasis(y, decay=g, s_min=s_min)
    np.testing.assert_allclose(c, y, atol=1e-9)
    np.testing.assert_allclose(s, s_true, atol=1e-9)


@pytest.mark.parametrize("s_min", [0.0, 0.2])
def test_ar2_noise_free_jumps_are_recovered_exactly(s_min):
    n, d, r = 500, 0.97, 0.6
    g1, g2 = O.ar_coefficients(d, r)
    s_true = np.zeros(n)
    s_true[[30, 90, 100, 260, 400]] = [1.0, 2.0, 0.7, 1.5, 2.2]
    y = _kernel_matrix(n, g1, g2) @ s_true
    c, s = O.oasis(y, decay=d, rise=r, s_min=s_min)
    np.testing.assert_allclose(c, y, atol=1e-8)
    np.testing.assert_allclose(s, s_true, atol=1e-8)


def test_thresholded_form_never_emits_a_jump_below_s_min():
    rng = np.random.default_rng(3)
    y, g = _random_ar1_problem(rng, n=2000)
    s_min = 1.0
    c, s = O.oasis(y, decay=g, s_min=s_min)
    nz = s[1:][s[1:] > 1e-12]           # the first sample is the initial level, not a jump
    assert nz.size > 0
    assert np.all(nz >= s_min - 1e-9)
    np.testing.assert_allclose(s[1:], c[1:] - g * c[:-1], atol=1e-10)


def test_rise_not_shorter_than_the_decay_is_refused():
    with pytest.raises(ValueError, match="rise"):
        O.oasis(np.ones(10), decay=0.9, rise=0.95)


# -- the trace-level wrapper ------------------------------------------------------

def test_deconvolve_noise_free_troughs_finds_the_drops_in_noise_sd_units():
    n = 3000
    g = gamma_for(HALF_S, FS)
    onsets, depths = [300, 900, 960, 2000], [3e-3, 4e-3, 2e-3, 5e-3]
    rng = np.random.default_rng(0)
    x = 0.01 - kernel_sum(n, onsets, depths, g) + 1e-5 * rng.standard_normal(n)
    out = O.deconvolve(x, FS, polarity="drop", recovery_half_s=HALF_S, min_jump_sigma=3.0)
    big = np.flatnonzero(out.scores > 50)
    assert list(big) == onsets
    # scores are jumps in noise SDs: s / sigma, sigma in stored units
    np.testing.assert_allclose(out.scores[onsets] * out.sigma, depths, rtol=0.05)
    assert out.sigma == pytest.approx(1e-5, rel=0.25)
    assert out.decay == pytest.approx(g)
    assert out.estimated is False
    assert out.scores[0] == 0.0          # the initial level is not a jump


def test_spike_polarity_reads_the_signal_the_other_way_up():
    x, onsets, _ = troughs_12h(seed=1)
    a = O.deconvolve(x, FS, polarity="drop", recovery_half_s=HALF_S)
    b = O.deconvolve(-x, FS, polarity="spike", recovery_half_s=HALF_S)
    np.testing.assert_allclose(a.scores, b.scores, atol=1e-9)


def test_recovery_half_time_is_estimated_within_20_percent():
    x, _, _ = troughs_12h(seed=2)
    out = O.deconvolve(x, FS, polarity="drop", recovery_half_s=0.0)
    assert out.estimated is True
    assert out.half_s == pytest.approx(HALF_S, rel=0.20)


def test_nan_samples_split_the_trace_and_stay_nan():
    x, onsets, _ = troughs_12h(seed=3)
    x = x.copy()
    x[20000:20100] = np.nan
    out = O.deconvolve(x, FS, polarity="drop", recovery_half_s=HALF_S)
    assert np.all(np.isnan(out.scores[20000:20100]))
    assert np.isfinite(out.scores[:20000]).all() and np.isfinite(out.scores[20100:]).all()
    assert out.n_nan == 100 and out.n_segments == 2
    found = set(np.flatnonzero(np.nan_to_num(out.scores) > 4.0))
    for o in onsets:
        if not 20000 <= o < 20100:
            assert any(abs(o - f) <= 2 for f in found), f"onset {o} lost next to the NaN gap"


def test_unknown_polarity_is_refused():
    with pytest.raises(ValueError, match="polarity"):
        O.deconvolve(np.zeros(100), FS, polarity="sideways", recovery_half_s=60.0)


def test_linear_time_on_a_long_channel():
    """2.6 M samples (a month at 1 Hz) in seconds: the paper's O(T) claim, measured."""
    n = 2_600_000
    rng = np.random.default_rng(5)
    g = gamma_for(HALF_S, FS)
    s = np.where(rng.random(n) < 1 / 1500, rng.uniform(2e-3, 6e-3, n), 0.0)
    from scipy.signal import lfilter
    x = 0.01 - lfilter([1.0], [1.0, -g], s) + 1e-4 * rng.standard_normal(n)
    O.deconvolve(x[:5000], FS, recovery_half_s=HALF_S)        # warm any JIT
    t0 = time.perf_counter()
    out = O.deconvolve(x, FS, recovery_half_s=HALF_S)
    elapsed = time.perf_counter() - t0
    print(f"\n[oasis] 2.6 M samples deconvolved in {elapsed:.2f} s")
    assert out.scores.shape == (n,)
    assert elapsed < 30.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-s"]))

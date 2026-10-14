"""
test_surrogate.py
===================
Ticket 43 — surrogate generation block.

A signal-to-signal adapter that produces a null (surrogate) version of a
signal, reproducibly from its recipe. The PRD ("Surrogates") requires:
phase randomisation and block shuffling offered as a choice parameter, an
explicit RNG seed among the `ParamSpec` parameters so the recipe hash
reproduces the surrogate exactly, and a phase-randomised surrogate that
preserves the original's power spectrum.

These tests assert the external behaviour the reproducibility claim depends
on: the block declares `Signal -> Signal`, offers both surrogate methods as
a choice, exposes a seed parameter, reproduces a bit-identical surrogate for
a fixed seed, and phase randomisation preserves the power spectrum within a
stated tolerance.

Run from the project root:
    python -m pytest tests/test_surrogate.py -q
"""

import os
import sys

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter

discover_adapters()

SURROGATE_NAME = "preprocessing.surrogate"

# The surrogate methods the block must offer as a choice. w3-a fix round 1 added "aaft" (Theiler 1992's
# amplitude-adjusted Fourier transform, moved here from Pipelines/drop_motifs/nulls1.py) deliberately.
SURROGATE_METHODS = ("phase_randomize", "block_shuffle", "aaft")


def _signal(fs=100.0, n=512):
    """A deterministic signal with a non-flat power spectrum: two sinusoids
    plus a little noise, so the power-spectrum-preservation assertion is
    meaningful."""
    t = np.arange(n) / fs
    rng = np.random.RandomState(1)
    x = (np.sin(2 * np.pi * 5.0 * t)
         + 0.5 * np.sin(2 * np.pi * 13.0 * t)
         + 0.2 * rng.randn(n))
    return x, t, fs


def test_surrogate_declares_signal_to_signal():
    spec = get_adapter(SURROGATE_NAME)
    assert spec.input_kind == "signal"
    assert spec.output_kind == "signal"


def test_surrogate_offers_phase_randomise_and_block_shuffle_choice():
    spec = get_adapter(SURROGATE_NAME)
    method_params = [p for p in spec.params if p.name == "method"]
    assert len(method_params) == 1, "expected exactly one 'method' parameter"
    assert set(SURROGATE_METHODS) <= set(method_params[0].choices)


def test_surrogate_exposes_a_seed_param():
    spec = get_adapter(SURROGATE_NAME)
    assert any(p.name == "seed" for p in spec.params)


def test_fixed_seed_reproduces_bit_identical_surrogate():
    spec = get_adapter(SURROGATE_NAME)
    x, t, fs = _signal()
    for method in SURROGATE_METHODS:
        # block_s is stated: since fixup-T (Q-Null-1) block shuffle has no
        # default block length — an unset one is refused — and 1.0 s here is
        # the 100-sample block this test always ran at
        params = spec.validate_params({"method": method, "seed": 42, "block_s": 1.0})
        a = spec.run(x, t, fs, **params)
        b = spec.run(x, t, fs, **params)
        assert np.array_equal(a.value.x, b.value.x), method
        assert a.value.fs == fs, method


def test_phase_randomise_preserves_power_spectrum():
    spec = get_adapter(SURROGATE_NAME)
    x, t, fs = _signal()
    params = spec.validate_params({"method": "phase_randomize", "seed": 7})
    result = spec.run(x, t, fs, **params)
    # Phase randomisation multiplies each FFT bin by a unit-magnitude complex
    # exponential, so the magnitude spectrum (and hence power spectrum) is
    # preserved to floating-point precision. 1e-6 relative tolerance is far
    # looser than the actual error, which is ~1e-14.
    mag_original = np.abs(np.fft.rfft(x))
    mag_surrogate = np.abs(np.fft.rfft(result.value.x))
    assert np.allclose(mag_original, mag_surrogate, rtol=1e-6, atol=1e-8)


# ── AAFT (w3-a fix round 1, manager decision 8) ─────────────────────────────

def _skewed(n=4000, seed=3):
    """Coloured noise under one-sided excursions: a non-Gaussian marginal, as the real channels have."""
    rng = np.random.default_rng(seed)
    noise = np.cumsum(rng.normal(0, 1, n))
    noise = noise - np.convolve(noise, np.ones(101) / 101, mode="same")
    spikes = np.zeros(n)
    for onset in rng.choice(n - 40, 60, replace=False):
        spikes[onset:onset + 8] -= np.linspace(0, 3.0, 8)
    return noise * 0.2 + spikes


def _aaft_as_it_was(x, rng):
    """`Pipelines/drop_motifs/nulls1.py::aaft_surrogate` before the move, verbatim."""
    from Adapters.preprocessing_surrogate import _phase_randomise
    x = np.asarray(x, dtype=float).ravel()
    ranks = np.argsort(np.argsort(x))
    gaussian = np.sort(rng.standard_normal(len(x)))[ranks]
    randomised = _phase_randomise(gaussian, rng)
    return np.sort(x)[np.argsort(np.argsort(randomised))]


def test_the_default_method_is_unchanged():
    spec = get_adapter(SURROGATE_NAME)
    method = next(p for p in spec.params if p.name == "method")
    assert method.default == "phase_randomize"
    assert method.choices == ["phase_randomize", "block_shuffle", "aaft"]


def test_aaft_is_a_permutation_of_the_input_with_about_its_spectrum():
    spec = get_adapter(SURROGATE_NAME)
    x = _skewed()
    t = np.arange(len(x)) / 10.0
    y = spec.run(x, t, 10.0, **spec.validate_params({"method": "aaft", "seed": 4})).value.x
    assert np.array_equal(np.sort(y), np.sort(x))
    assert not np.array_equal(y, x)
    px, py = np.abs(np.fft.rfft(x)) ** 2, np.abs(np.fft.rfft(y)) ** 2
    bands = np.array_split(np.arange(1, len(px)), 20)
    ratio = np.array([py[b].sum() / px[b].sum() for b in bands])
    assert np.all((ratio > 0.5) & (ratio < 2.0)), ratio


def test_the_moved_aaft_is_bit_identical_to_nulls1s_own():
    from Adapters.preprocessing_surrogate import aaft_surrogate
    from Pipelines.drop_motifs import nulls1
    x = _skewed()
    want = _aaft_as_it_was(x, np.random.default_rng(20260902))
    assert np.array_equal(nulls1.aaft_surrogate(x, np.random.default_rng(20260902)), want)
    assert np.array_equal(aaft_surrogate(x, np.random.default_rng(20260902)), want)
    assert nulls1.aaft_surrogate is aaft_surrogate
    assert np.array_equal(nulls1.make_surrogate(x, 10.0, "aaft", 20260902), want)

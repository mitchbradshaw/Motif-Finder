"""
test_cross_channel_window.py
============================
fixup-AQ (X3): Explore › Cross-channel showed lag 0.0 s and r ≈ −0.97 on every pair of a 640 s window. Two
channels drifting over ten minutes — one up, one down — correlate near ±1 at lag 0 whatever their events do:
the z-normalised cross-correlation of two ramps peaks at zero lag. A window that long needs its trend taken out
before the lag means anything, so `classify_waveforms` takes a `detrend` and the window's rule text says what
was (and was not) applied to the pair.

The backgrounds are coloured (00-common.md, wave-1 lesson): AR(1) at phi 0.97 and a random walk, under drifts.
"""
import numpy as np
import pytest

from Working.cross_channel import (
    ARTIFACT, DEFAULT_RULE, INDEPENDENT_RECURRENCE, PROPAGATION, classify_waveforms,
)

FS = 1.0
N = 640


def _ar1(seed, phi=0.97, n=N, scale=0.05):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n) * scale
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _event(n=N, at=300, width=60, depth=3.0):
    u = np.zeros(n)
    k = np.arange(width)
    u[at:at + width] = -depth * np.sin(np.pi * k / width)
    return u


def test_opposite_drifts_correlate_at_lag_zero_as_recorded():
    """The symptom, reproduced: the window as recorded reads r near -1 at lag 0 — the drift, not an event."""
    ramp = np.linspace(0.0, 20.0, N)
    a = ramp + _ar1(1)
    b = -ramp + _ar1(2)
    lag, r, _ = classify_waveforms(a, b, fs=FS)
    assert lag == 0 and r < -0.9


def test_detrended_opposite_drifts_no_longer_look_like_one_signal():
    ramp = np.linspace(0.0, 20.0, N)
    a = ramp + _ar1(1)
    b = -ramp + _ar1(2)
    lag, r, cls = classify_waveforms(a, b, fs=FS, detrend="linear")
    assert abs(r) < 0.6, f"two independent AR(1) backgrounds must not read as one signal once the drift is out: r={r}"
    assert cls == INDEPENDENT_RECURRENCE


def test_a_lagged_event_under_opposite_drifts_is_found_at_its_lag_once_detrended():
    """The page's purpose: an event on the reference arriving 12 s later on the other channel, under drifts."""
    ramp = np.linspace(0.0, 15.0, N)
    a = ramp + _event(at=300) + _ar1(3, scale=0.02)
    b = -0.7 * ramp + _event(at=312) + _ar1(4, scale=0.02)
    lag_raw, _, _ = classify_waveforms(a, b, fs=FS)
    assert lag_raw != 12, "as recorded the drift should dominate (otherwise this test pins nothing)"
    lag, r, cls = classify_waveforms(a, b, fs=FS, detrend="linear")
    assert lag == 12 and r > 0.5 and cls == PROPAGATION


def test_detrend_on_a_random_walk_keeps_a_simultaneous_copy_an_artifact():
    rng = np.random.default_rng(7)
    walk = np.cumsum(rng.standard_normal(N)) * 0.1
    a = walk + _event()
    b = walk + _event() + rng.standard_normal(N) * 1e-4
    lag, r, cls = classify_waveforms(a, b, fs=FS, detrend="linear")
    assert lag == 0 and r > 0.98 and cls == ARTIFACT


def test_detrend_none_is_the_old_call_exactly():
    a, b = _ar1(5) + _event(), _ar1(6) + _event(at=305)
    assert classify_waveforms(a, b, fs=FS, detrend=None) == classify_waveforms(a, b, fs=FS)
    assert classify_waveforms(a, b, fs=FS, detrend="none") == classify_waveforms(a, b, fs=FS)


def test_an_unknown_detrend_is_refused():
    with pytest.raises(ValueError, match="detrend"):
        classify_waveforms(_ar1(1), _ar1(2), detrend="quadratic-ish")


def test_the_window_rule_says_what_the_pair_test_applied_and_what_it_did_not():
    """The page used to print the Library rule (chance test, noise floor) beside a bin the Explore route had
    produced without either. The window's words are the ones the call applied."""
    words = DEFAULT_RULE.describe_window(detrend="linear")
    assert set(words) == {ARTIFACT, PROPAGATION, INDEPENDENT_RECURRENCE}
    art = words[ARTIFACT]
    assert "1 s" in art and "0.98" in art, art
    assert "linear" in art.lower() and "detrend" in art.lower()
    assert "not run" in art and "chance" in art, "the chance test is not run on a window and must say so"
    assert "0.5" in words[PROPAGATION] and "50 s" in words[PROPAGATION]
    raw = DEFAULT_RULE.describe_window(detrend=None)
    assert "as recorded" in raw[ARTIFACT]

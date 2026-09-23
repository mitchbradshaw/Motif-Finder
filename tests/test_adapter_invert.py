"""
test_adapter_invert.py
========================
`preprocessing.invert` (fixup-d, seam 6) — Signal -> Signal, `-x`. The cheapest
item in the prompt and the one that makes every drop detector a spike detector:
put it before the drop detector and a spike becomes a drop.

Runnable standalone:  python tests/test_adapter_invert.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402

discover_adapters()
NAME = "preprocessing.invert"


def test_registered_as_a_signal_block():
    spec = get_adapter(NAME)
    assert spec.stage == "preprocessing"
    assert spec.input_kind == "signal" and spec.output_kind == "signal"
    assert spec.category == "preprocess"
    assert spec.params == []


def test_inverts_a_30s_signal_and_keeps_its_length_and_rate():
    fs = 10.0
    x = np.sin(np.arange(300) / 7.0) * 0.004 - 0.2
    spec = get_adapter(NAME)
    r = spec.run(x, np.arange(300) / fs, fs, **spec.validate_params({}))
    assert r.output_kind == "signal"
    np.testing.assert_array_equal(r.value.x, -x)
    assert r.value.fs == fs and len(r.value.x) == len(x)


def test_inverting_twice_is_the_identity():
    spec = get_adapter(NAME)
    x = np.random.default_rng(1).standard_normal(50)
    once = spec.run(x, np.arange(50.0), 1.0).value.x
    np.testing.assert_array_equal(spec.run(once, np.arange(50.0), 1.0).value.x, x)


def test_a_spike_becomes_a_drop_for_the_drop_detector():
    """What the block is for: the five-stage detector finds the inverted spikes."""
    from Working.Detection.drop_motifs.detect5 import Detect5Params, detect_drops5
    fs = 10.0
    t = np.arange(600) / fs
    phase = (t % 20.0) / 20.0
    spikes = np.where(phase < 0.15, phase / 0.15, 1.0 - (phase - 0.15) / 0.85) * 0.01    # fast rise, slow fall
    spikes += 0.00002 * np.random.default_rng(0).standard_normal(len(t))
    params = Detect5Params(detrend_window_s=0.0, segment_seconds=0.5, same_fraction=0.6, slope_sigma=8.0)
    as_is = detect_drops5(spikes, fs, params)
    inverted = detect_drops5(get_adapter(NAME).run(spikes, t, fs).value.x, fs, params)
    assert len(inverted.events) > len(as_is.events) or (
        np.median([e.fall_duration_s for e in inverted.events]) < np.median([e.fall_duration_s for e in as_is.events]))


def test_the_signal_input_is_the_chain_root():
    """A signal block receives no typed `value`; nothing to refuse, but it must not
    accept one silently either."""
    spec = get_adapter(NAME)
    import inspect
    assert "value" not in inspect.signature(spec.run).parameters


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

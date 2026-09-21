"""
test_adapter_stage_encoding.py
================================
`detection.stage_encoding` — Signal → Encoding (symbolic, alphabet 5): the
five-stage letters of `detect5.stage_letters` on an already-detrended
signal, one integer per segment, the noise floor in `meta` and `derive`.

Runnable standalone:  python tests/test_adapter_stage_encoding.py
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
from Working.Detection.drop_motifs.detect5 import STAGE_LETTERS, Detect5Params, stage_letters  # noqa: E402
from Working.Preprocessing.detrend import make_detrend_filter  # noqa: E402

discover_adapters()
NAME = "detection.stage_encoding"
FS = 10.0


def sharkfin(seconds=30.0, period=10.0, fs=FS, seed=0):
    """Slow rise, fast fall, three cycles in 30 s, with a little noise."""
    n = int(seconds * fs)
    t = np.arange(n) / fs
    phase = (t % period) / period
    x = np.where(phase < 0.85, phase / 0.85, 1.0 - (phase - 0.85) / 0.15) * 0.01
    x += 0.00002 * np.random.default_rng(seed).standard_normal(n)
    return x, t


def test_registered_with_the_standard_types():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "encoding"
    assert spec.category == "encode"
    names = {p.name for p in spec.params}
    assert {"segment_seconds", "same_fraction", "slope_sigma", "noise_estimator"} <= names


def test_emits_five_stage_symbols_equal_to_stage_letters_on_the_same_signal():
    x, t = sharkfin()
    xd = make_detrend_filter(FS, mode="rolling_mean_nearest", window_s=12.0)(x)
    spec = get_adapter(NAME)
    r = spec.run(xd, t, FS, **spec.validate_params({"segment_seconds": 0.5}))
    assert r.value.kind == "symbolic"
    letters, details = stage_letters(xd, FS, Detect5Params(detrend_window_s=0.0, segment_seconds=0.5))
    assert "".join(STAGE_LETTERS[int(s)] for s in r.value.values) == letters
    assert r.meta["letters"] == letters
    assert r.meta["details"]["samples_per_symbol"] == int(details["samples_per_symbol"])
    assert r.meta["sigma_slope"] == pytest.approx(float(details["sigma_slope"]))
    assert set(r.meta["letters"]) & {"d"}, "a sharkfin train must contain fast falls"


def test_segment_length_is_recoverable_from_the_shapes_alone():
    x, t = sharkfin()
    spec = get_adapter(NAME)
    r = spec.run(x, t, FS, **spec.validate_params({"segment_seconds": 0.7}))
    assert len(x) // len(r.value.values) == r.meta["details"]["samples_per_symbol"]


def test_detrend_window_zero_means_no_detrend_in_stage_letters():
    x, t = sharkfin()
    a, _ = stage_letters(x, FS, Detect5Params(detrend_window_s=0.0, segment_seconds=0.5))
    b, _ = stage_letters(x + 5.0, FS, Detect5Params(detrend_window_s=0.0, segment_seconds=0.5))
    assert a == b, "an offset changes nothing when the signal is taken as-is"


def test_derive_reports_the_noise_floor_and_the_cut():
    x, t = sharkfin()
    spec = get_adapter(NAME)
    rows = spec.derive(x, t, FS, spec.validate_params({}))
    labels = [r[0] for r in rows]
    assert any("σ" in l for l in labels) and any("cut" in l.lower() for l in labels)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

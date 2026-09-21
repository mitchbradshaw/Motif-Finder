"""
test_adapter_wavelet_summation.py
===================================
`detection.wavelet_summation` — Encoding(image) → Scores: Ω(τ) = Σ_s g(τ, s),
the one-value-per-timepoint quantity Algorithm 1 of Dehshibi & Adamatzky
(2021) finds its extrema on. The first block in the registry that CONSUMES
an Encoding (stage-3 D2).

Runnable standalone:  python tests/test_adapter_wavelet_summation.py
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
from Working.types import Encoding  # noqa: E402

discover_adapters()
NAME = "detection.wavelet_summation"


def test_registered_as_an_encoding_consumer():
    spec = get_adapter(NAME)
    assert spec.input_kind == "encoding"
    assert spec.output_kind == "scores"
    assert spec.category == "detect"


def test_sums_over_scales_and_keeps_nan_columns():
    g = np.arange(12, dtype=float).reshape(3, 4)
    g[:, 2] = np.nan
    spec = get_adapter(NAME)
    x = np.zeros(4)
    r = spec.run(x, np.arange(4.0), 1.0, value=Encoding(values=g, kind="image"), **spec.validate_params({}))
    assert r.output_kind == "scores"
    assert r.value.fs == 1.0
    np.testing.assert_allclose(r.value.values[[0, 1, 3]], g[:, [0, 1, 3]].sum(axis=0))
    assert np.isnan(r.value.values[2])


def test_refuses_a_symbolic_encoding_with_a_clear_message():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="image"):
        spec.run(np.zeros(4), np.arange(4.0), 1.0, value=Encoding(values=np.array([0, 1, 2, 1]), kind="symbolic"))


def test_refuses_a_missing_input():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="Encoding"):
        spec.run(np.zeros(4), np.arange(4.0), 1.0)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

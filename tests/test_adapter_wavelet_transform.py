"""
test_adapter_wavelet_transform.py
===================================
`preprocessing.wavelet_transform` — the first stage of the Dehshibi &
Adamatzky (2021) detector as its own block (stage-3 decision 2: a multi-stage
detector is a TEMPLATE of typed blocks, not one adapter).

Signal → Encoding(kind='image', shape (n_scales, n)): the Eq. (3)-normalised
Morse-wavelet coefficients g(τ, s), computed per histogram-sliced chunk
exactly as `detect_spikes` does, NaN where a chunk was too short to analyse.

Runnable standalone:  python tests/test_adapter_wavelet_transform.py
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
from Working.Detection.analysis.dehshibi_detection_analysis import (  # noqa: E402
    compute_morse_wavelet_transform, normalise_wavelet_coefficients, slice_signal,
)

discover_adapters()
NAME = "preprocessing.wavelet_transform"


def synthetic(fs=10.0, seconds=30.0, seed=0):
    """Two broad depolarisations each with a sharp core — the shape Algorithm 4
    confirms (an envelope region nested inside a wavelet region). Noise-free
    on purpose: a grid search over shapes found the monolithic detector
    confirms exactly this and nothing simpler (wiring report 01)."""
    n = int(fs * seconds)
    t = np.arange(n) / fs
    x = np.zeros(n)
    for centre in (0.3 * seconds, 0.7 * seconds):
        x += np.exp(-0.5 * ((t - centre) / (0.2 * seconds)) ** 2) + 0.3 * np.exp(-0.5 * ((t - centre) / (0.005 * seconds)) ** 2)
    return x, t


def test_registered_with_the_standard_types():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal"
    assert spec.output_kind == "encoding"
    assert spec.category == "encode"
    assert spec.estimate is not None, "the transform is FFT-bound and must declare a cost"
    names = {p.name for p in spec.params}
    assert {"beta", "gamma", "eta", "min_chunk_samples"} <= names


def test_defaults_are_the_papers_constants():
    p = get_adapter(NAME).validate_params({})
    assert p["beta"] == 20.0 and p["gamma"] == 3.0 and p["eta"] == 240.0


def test_output_is_an_image_encoding_with_one_column_per_sample():
    x, t = synthetic()
    spec = get_adapter(NAME)
    r = spec.run(x, t, 10.0, **spec.validate_params({"min_chunk_samples": 20}))
    assert r.output_kind == "encoding" and r.value.kind == "image"
    assert r.value.values.ndim == 2 and r.value.values.shape[1] == len(x)
    assert r.value.values.shape[0] == 64          # the paper implementation's scale count


def test_matches_the_monolithic_pipelines_per_chunk_coefficients():
    x, t = synthetic()
    spec = get_adapter(NAME)
    g_all = spec.run(x, t, 10.0, **spec.validate_params({"min_chunk_samples": 20})).value.values
    for c0, c1 in slice_signal(x):
        chunk = x[c0:c1 + 1]
        if len(chunk) < 20:
            assert np.isnan(g_all[:, c0:c1 + 1]).all()
            continue
        phi, _ = compute_morse_wavelet_transform(chunk, fs=10.0)
        g, _ = normalise_wavelet_coefficients(phi)
        np.testing.assert_allclose(g_all[:, c0:c1 + 1], g, rtol=1e-10, atol=1e-12)


def test_a_chunk_shorter_than_the_floor_is_nan_not_zero():
    x = np.zeros(50)
    spec = get_adapter(NAME)
    r = spec.run(x, np.arange(50.0), 1.0, **spec.validate_params({"min_chunk_samples": 120}))
    assert np.isnan(r.value.values).all()
    assert r.meta["n_chunks_skipped"] >= 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

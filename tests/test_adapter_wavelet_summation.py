"""
test_adapter_wavelet_summation.py
===================================
`detection.wavelet_summation` — Encoding(image) → Scores: Ω(τ), the sum of a
BAND of rows of a time-aligned image. The authors of Dehshibi & Adamatzky
(2021) sum only the frequencies at or below a quarter of the range
(`iApplyWavelet.m`, method 2); the band is a fraction of the image's rows so
that any low-to-high, one-column-per-sample image can feed it (fixup-J).

Runnable standalone:  python tests/test_adapter_wavelet_summation.py
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import Encoding  # noqa: E402

discover_adapters()
NAME = "detection.wavelet_summation"

with open(os.path.join(PROJECT_ROOT, "tests", "fixtures", "dehshibi", "reference.json")) as _f:
    REF = json.load(_f)


def case(name="a"):
    """A synthetic 1 Hz recording with known events and what the authors'
    MATLAB returned on it (see tests/test_dehshibi_authors.py)."""
    c = REF["cases"][name]
    x = np.asarray(c["x"], dtype=float)
    return c, x, np.arange(len(x), dtype=float)


def test_registered_as_an_encoding_consumer():
    spec = get_adapter(NAME)
    assert spec.input_kind == "encoding"
    assert spec.output_kind == "scores"
    assert spec.category == "detect"
    assert {"row_from", "row_to"} <= {p.name for p in spec.params}
    d = spec.validate_params({})
    assert d["row_from"] == 0.0 and d["row_to"] == 1.0, "on its own the block sums the whole image"


def test_sums_over_rows_and_keeps_nan_columns():
    g = np.arange(12, dtype=float).reshape(3, 4)
    g[:, 2] = np.nan
    spec = get_adapter(NAME)
    x = np.zeros(4)
    r = spec.run(x, np.arange(4.0), 1.0, value=Encoding(values=g, kind="image"), **spec.validate_params({}))
    assert r.output_kind == "scores"
    assert r.value.fs == 1.0
    np.testing.assert_allclose(r.value.values[[0, 1, 3]], g[:, [0, 1, 3]].sum(axis=0))
    assert np.isnan(r.value.values[2])


def test_sums_only_the_band_of_rows_it_is_given():
    g = np.arange(40, dtype=float).reshape(10, 4)
    spec = get_adapter(NAME)
    r = spec.run(np.zeros(4), np.arange(4.0), 1.0, value=Encoding(values=g, kind="image"),
                 **spec.validate_params({"row_from": 0.2, "row_to": 0.7}))
    np.testing.assert_allclose(r.value.values, g[2:7].sum(axis=0))
    assert r.meta["rows_used"] == [2, 7] and r.meta["n_rows"] == 10


def test_an_empty_band_is_refused_in_words():
    spec = get_adapter(NAME)
    g = np.ones((10, 4))
    with pytest.raises(ValueError, match="band"):
        spec.run(np.zeros(4), np.arange(4.0), 1.0, value=Encoding(values=g, kind="image"),
                 **spec.validate_params({"row_from": 0.6, "row_to": 0.6}))


def test_the_templates_band_gives_the_authors_omega():
    """Wavelet transform -> this block with the template's `row_to` is MATLAB's
    Omega for a 3000 s window."""
    from server.templates import canonical
    c, x, t = case("a")
    steps = canonical("dehshibi_spikes")["steps"]
    tr = get_adapter("preprocessing.wavelet_transform")
    enc = tr.run(x, t, 1.0, **tr.validate_params(steps[0]["params"])).value
    spec = get_adapter(NAME)
    r = spec.run(x, t, 1.0, value=enc, **spec.validate_params(steps[1]["params"]))
    assert np.abs(r.value.values - np.asarray(c["omega"])).max() <= 1.0


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

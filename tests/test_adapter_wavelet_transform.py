"""
test_adapter_wavelet_transform.py
===================================
`preprocessing.wavelet_transform` — stage 1 of the Dehshibi & Adamatzky
(2021) template (stage-3 decision 2: a multi-stage detector is a TEMPLATE of
typed blocks, not one adapter).

Signal → Encoding(kind='image', shape (rows, n)): the scaled Morse scalogram
the AUTHORS' code builds (`iApplyWavelet.m`; fixup-J, Q33), window by window,
rows ordered LOW to HIGH frequency, one column per sample, every sample of
the span analysed.

Runnable standalone:  python tests/test_adapter_wavelet_transform.py
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
from Working.Detection.analysis import dehshibi_authors as A  # noqa: E402
from Working.types import Encoding  # noqa: E402

discover_adapters()
NAME = "preprocessing.wavelet_transform"

with open(os.path.join(PROJECT_ROOT, "tests", "fixtures", "dehshibi", "reference.json")) as _f:
    REF = json.load(_f)


def case(name="a"):
    """A synthetic 1 Hz recording with known events and what the authors'
    MATLAB returned on it (see tests/test_dehshibi_authors.py)."""
    c = REF["cases"][name]
    x = np.asarray(c["x"], dtype=float)
    return c, x, np.arange(len(x), dtype=float)


def run(x, t, fs=1.0, **params):
    spec = get_adapter(NAME)
    return spec.run(x, t, fs, **spec.validate_params(params))


def test_registered_with_the_standard_types():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal"
    assert spec.output_kind == "encoding"
    assert spec.category == "encode"
    assert spec.estimate is not None, "the transform is FFT-bound and must declare a cost"
    names = {p.name for p in spec.params}
    assert {"beta", "gamma", "eta", "window_s", "slice_by_state"} <= names


def test_defaults_are_the_authors_constants_and_the_papers_window():
    p = get_adapter(NAME).validate_params({})
    assert p["beta"] == 20.0 and p["gamma"] == 3.0 and p["eta"] == 240.0
    assert p["window_s"] == 3000.0, "the paper works on 3000 s pieces (Fig. 5); Q29"
    assert p["slice_by_state"] is False, "Q29: fixed windows by default, state slicing as an option"


def test_an_old_recipes_parameter_is_still_accepted():
    """`min_chunk_samples` was a parameter before fixup-J; a saved recipe that
    carries it must still validate (Q32)."""
    get_adapter(NAME).validate_params({"min_chunk_samples": 120})


def test_output_is_a_time_aligned_image_low_frequency_first():
    c, x, t = case("a")
    r = run(x, t)
    assert r.output_kind == "encoding" and isinstance(r.value, Encoding) and r.value.kind == "image"
    img = r.value.values
    assert img.ndim == 2 and img.shape[1] == len(x), "one column per sample"
    assert img.shape[0] == len(c["frequencies"])
    f = np.asarray(r.meta["freqs_hz"])
    assert len(f) == img.shape[0] and (np.diff(f) > 0).all(), "rows run low to high frequency"
    np.testing.assert_allclose(f[::-1], c["frequencies"], rtol=1e-9)


def test_every_sample_of_the_span_is_analysed():
    """The 87 % (fixup-J report 2.2): the old slicing left most of a real span
    NaN. Fixed windows and the authors' partition both cover everything."""
    _, x, t = case("a")
    for slice_by_state in (False, True):
        img = run(np.concatenate([x, x]), np.arange(2.0 * len(x)), slice_by_state=slice_by_state).value.values
        assert np.isfinite(img).all()


def test_values_are_the_authors_scaled_coefficients():
    """1 + fix(240 * (|W| - min) / max) per frequency: whole numbers in 1..241,
    and their low-band sum is MATLAB's Omega."""
    c, x, t = case("a")
    r = run(x, t)
    img = r.value.values.astype(float)
    assert img.min() >= 1.0 and img.max() <= 241.0 and np.array_equal(img, np.round(img))
    k = r.meta["authors_band"]["rows"]
    assert k == c["band_rows"][1] - c["band_rows"][0] + 1
    assert r.meta["authors_band"]["row_to"] == pytest.approx(k / img.shape[0])
    assert np.abs(img[:k].sum(axis=0) - np.asarray(c["omega"])).max() <= 1.0


def test_matches_the_core_window_by_window():
    _, xa, _ = case("a")
    _, xb, _ = case("b")
    x = np.concatenate([xa, xb])
    r = run(x, np.arange(float(len(x))))
    assert r.meta["chunks"] == [[0, 3000], [3000, 6000]], "half-open, like every span the blocks report"
    for c0, c1 in r.meta["chunks"]:
        sw = A.scaled_scalogram(x[c0:c1], A.morse_scales(3000))
        np.testing.assert_array_equal(r.value.values[:, c0:c1], sw[::-1].astype(np.float32))


def test_a_span_too_short_to_transform_is_nan_not_zero():
    r = run(np.zeros(3), np.arange(3.0))
    assert np.isnan(r.value.values).all()
    assert r.meta["n_chunks_skipped"] == 1


# ------------------------------------------------------------ the span guard --
# Peak live bytes per span sample. The scalogram is built one frequency at a
# time (fixup-J), so the transient is a handful of padded complex rows, not a
# matrix; what is held is the float32 output:
#
#   image      up to 128 rows x 4 B          =  512 B/sample   held for the whole run
#   transient  the padded chunk's FFT, one filter, one product and one inverse
#              (2x the chunk, complex)       ~  112 B/sample
#                                              ----------------
#                                               624 B/sample
#
# 128 rows is the ceiling the block enforces (a 3000 s window is 87). The four
# gramian blocks cap themselves at 5,000 samples for a 200 MB matrix
# (`catalogue_gramian_gasf.py`). Same budget, same convention.
PEAK_BYTES_PER_SAMPLE = 624
GRAMIAN_BUDGET_BYTES = 5000 * 5000 * 8        # the 200 MB the gramian blocks cap at


def test_the_transform_declares_a_span_cap_from_the_gramian_memory_budget():
    cap = get_adapter(NAME).max_span_samples
    assert cap is not None, (
        "a block that holds a rows x n matrix and is then re-serialised by the step "
        "cache must declare max_span_samples so the bridge refuses the span loudly")
    peak = cap * PEAK_BYTES_PER_SAMPLE
    assert peak <= GRAMIAN_BUDGET_BYTES, (
        f"cap {cap} samples peaks at {peak / 1e6:.0f} MB, over the repo's 200 MB block budget")
    assert peak > GRAMIAN_BUDGET_BYTES * 0.9, (
        f"cap {cap} samples peaks at only {peak / 1e6:.0f} MB - needlessly refusing spans it could do")


def test_a_window_that_needs_more_rows_than_the_cap_assumes_is_refused():
    with pytest.raises(ValueError, match="rows"):
        run(np.zeros(200_000), np.arange(200_000.0), window_s=200_000.0)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

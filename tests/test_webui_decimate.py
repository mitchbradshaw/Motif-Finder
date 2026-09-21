"""
test_webui_decimate.py
======================
Pins the min/max decimator in `webui/server/decimate.py` against a verbatim
copy of the original Python loop it replaced. Ported from the Panel-era
`tests/test_plots_perf.py` (tag `archive/panel-ui`) when `UI/plots.py` was
retired; the algorithm under test is the one the web bridge's viewport
envelope serves, so the pin moves with it.

Why the oracle is a copy and not an import: the point of the first test is
that the fast implementation agrees with THIS loop, so the loop has to outlive
every rewrite of the fast one.
"""

import os
import sys
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from server import decimate as D  # noqa: E402  (webui/server; imports numpy only)


def _reference_minmax_decimate(x_slice, t_slice, max_points):
    """The original loop, kept verbatim as the oracle."""
    n = len(x_slice)
    if n <= max_points:
        return x_slice, t_slice
    n_buckets = max(1, max_points // 2)
    edges = np.unique(np.linspace(0, n, n_buckets + 1).astype(np.int64))
    starts = edges[:-1]
    xs_out = np.empty(2 * len(starts), dtype=x_slice.dtype)
    ts_out = np.empty(2 * len(starts), dtype=t_slice.dtype)
    ends = np.append(starts[1:], n)
    for i, (lo, hi) in enumerate(zip(starts, ends)):
        seg = x_slice[lo:hi]
        i_min = lo + int(np.argmin(seg))
        i_max = lo + int(np.argmax(seg))
        if i_min <= i_max:
            xs_out[2 * i], xs_out[2 * i + 1] = x_slice[i_min], x_slice[i_max]
            ts_out[2 * i], ts_out[2 * i + 1] = t_slice[i_min], t_slice[i_max]
        else:
            xs_out[2 * i], xs_out[2 * i + 1] = x_slice[i_max], x_slice[i_min]
            ts_out[2 * i], ts_out[2 * i + 1] = t_slice[i_max], t_slice[i_min]
    return xs_out, ts_out


def test_decimate_module_imports_no_ui_library():
    with open(D.__file__, encoding="utf-8") as f:
        src = f.read().lower()
    for banned in ("import panel", "import holoviews", "import bokeh", "import matplotlib",
                   "from panel", "from holoviews", "from bokeh", "from matplotlib"):
        assert banned not in src, f"webui/server/decimate.py must not `{banned}`"


# ── (a) the vectorised decimation draws exactly the same picture ────────

@pytest.mark.parametrize("n,max_points", [
    (10, 40_000),          # below the cap: passthrough
    (40_000, 40_000),      # exactly at the cap: passthrough
    (40_001, 40_000),      # one over: buckets of 1-2 samples, the ragged case
    (100_000, 40_000),
    (2_595_600, 40_000),   # a real full channel
    (123_457, 1_000),      # bucket count that does not divide evenly
    (5_000, 3),            # pathological: fewer buckets than 2
])
def test_vectorised_decimation_matches_the_loop(n, max_points):
    rng = np.random.default_rng(20260831)
    x = rng.standard_normal(n).astype(np.float64)
    t = np.arange(n, dtype=np.float64) / 3.0

    got_x, got_t = D._minmax_decimate(x, t, max_points)
    want_x, want_t = _reference_minmax_decimate(x, t, max_points)

    np.testing.assert_array_equal(got_x, want_x)
    np.testing.assert_array_equal(got_t, want_t)


def test_decimation_matches_the_loop_with_ties_and_plateaus():
    """Ties matter. `np.argmin` returns the FIRST occurrence, and the
    output ordering (min-then-max or max-then-min) is decided by which
    index comes first — so a signal full of repeated values, which a
    flat-lining electrode produces constantly, is exactly where a
    vectorised rewrite silently diverges."""
    x = np.repeat([0.0, 0.0, 1.0, 1.0, -1.0, -1.0, 0.0], 3_000).astype(np.float64)
    t = np.arange(len(x), dtype=np.float64)
    got_x, got_t = D._minmax_decimate(x, t, 1_000)
    want_x, want_t = _reference_minmax_decimate(x, t, 1_000)
    np.testing.assert_array_equal(got_x, want_x)
    np.testing.assert_array_equal(got_t, want_t)


def test_decimation_preserves_a_spike_a_stride_would_lose():
    """The property the whole min/max scheme exists for: a single-sample
    spike survives decimation. Simple striding would alias it away, and
    finding spikes is what this application is for."""
    x = np.zeros(500_000)
    x[123_456] = 42.0
    t = np.arange(len(x), dtype=np.float64)
    out_x, _out_t = D._minmax_decimate(x, t, 4_000)
    assert out_x.max() == 42.0


def test_decimation_is_not_quadratically_slow():
    """A ratio, not a budget. Ten times the input must not cost anywhere
    near ten times the work per sample — the old Python loop scaled with
    bucket count and dominated every pan of a wide viewport."""
    rng = np.random.default_rng(1)
    t0 = time.perf_counter()
    D._minmax_decimate(rng.standard_normal(200_000), np.arange(200_000.0), 40_000)
    small = time.perf_counter() - t0
    t0 = time.perf_counter()
    D._minmax_decimate(rng.standard_normal(2_000_000), np.arange(2_000_000.0), 40_000)
    large = time.perf_counter() - t0
    assert large < max(small * 40, 2.0), (
        f"decimation scaled badly: {small:.3f}s for 200k, {large:.3f}s for 2M")


# ── (b) the envelope the bridge actually serves keeps the same guarantees ──

def test_envelope_preserves_a_spike_and_stays_within_the_pixel_budget():
    x = np.zeros(500_000)
    x[123_456] = 42.0
    out = D.envelope(x, fs=1.0, start_idx=0, end_idx=len(x), px=1200)
    assert out["decimated"] is True
    assert max(out["v"]) == 42.0
    assert out["n_points"] <= 2 * 1200 + 2
    assert len(out["t"]) == len(out["v"]) == out["n_points"]


def test_envelope_fast_path_matches_the_loop_oracle_on_first_occurrence_ties():
    """`_fast_minmax` uses equal-width buckets, so compare it to the oracle
    on an input whose length divides evenly — the only case where both
    bucketings coincide — with ties and plateaus present."""
    x = np.repeat([0.0, 0.0, 1.0, 1.0, -1.0, -1.0, 0.0, 2.0], 1_000).astype(np.float64)
    n_buckets = 500                       # 8000 / 500 = 16 samples per bucket
    idx, vals = D._fast_minmax(x, n_buckets)
    t = np.arange(len(x), dtype=np.float64)
    want_x, want_t = _reference_minmax_decimate(x, t, 2 * n_buckets)
    np.testing.assert_array_equal(vals, want_x)
    np.testing.assert_array_equal(idx.astype(np.float64), want_t)

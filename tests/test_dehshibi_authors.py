"""
test_dehshibi_authors.py
==========================
`Working.Detection.analysis.dehshibi_authors` — the Dehshibi & Adamatzky
(2021) spike detector ported from the AUTHORS' MATLAB (Zenodo
10.5281/zenodo.3997031), checked against that MATLAB itself.

`tests/fixtures/dehshibi/reference.json` holds what the authors' unmodified
functions returned in MATLAB R2025b on three synthetic recordings with a
known set of events (`scripts/fixup_j_synthetic.py`), every intermediate
included. The port must reproduce them: the frequency grid, Omega, the
candidate regions, the spike / pseudo-spike split, the envelope regions and
the final spikes. (fixup-J; QUESTIONS.md Q28-Q33.)

Runnable standalone:  python tests/test_dehshibi_authors.py
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
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.Detection.analysis import dehshibi_authors as A  # noqa: E402

with open(os.path.join(PROJECT_ROOT, "tests", "fixtures", "dehshibi", "reference.json")) as _f:
    REF = json.load(_f)
CASES = sorted(REF["cases"])


def zero_based(regions):
    """MATLAB 1-based inclusive pairs -> the port's 0-based inclusive pairs."""
    return [(int(a) - 1, int(b) - 1) for a, b in regions]


def case(name):
    c = REF["cases"][name]
    return c, np.asarray(c["x"], dtype=float)


# ── the transform is MATLAB's cwt ───────────────────────────────────────────

@pytest.mark.parametrize("n", sorted(REF["grid"], key=int))
def test_the_scale_grid_is_the_one_matlabs_cwt_builds(n):
    rows, f_hi, f_lo = REF["grid"][n]
    f = A.scale_frequencies(A.morse_scales(int(n)))
    assert len(f) == rows
    assert f[0] == pytest.approx(f_hi, rel=1e-9) and f[-1] == pytest.approx(f_lo, rel=1e-9)


@pytest.mark.parametrize("name", CASES)
def test_the_coefficients_are_a_modulus_and_match_matlab(name):
    c, x = case(name)
    scales = A.morse_scales(len(x))
    np.testing.assert_allclose(A.scale_frequencies(scales), c["frequencies"], rtol=1e-9)
    mod = A.morse_cwt_modulus(x, scales)
    assert mod.shape == (len(scales), len(x))
    np.testing.assert_allclose(mod.sum(axis=1), c["abs_row_sums"], rtol=1e-6)


def test_a_step_at_the_edges_does_not_dominate_the_scalogram():
    """The signal is extended by reflection. A ramp's end-to-start jump must
    not be the largest thing in the window: one interior spike has to be."""
    n = 3000
    x = np.linspace(0.0, 10.0, n)
    x[1500:1520] += 1.0
    sw = A.scaled_scalogram(x, A.morse_scales(n))
    omega = sw.sum(axis=0)
    assert 1400 < int(np.argmax(omega)) < 1620, "Omega peaks at an edge: the transform wrapped around"


@pytest.mark.parametrize("name", CASES)
def test_omega_is_the_authors_low_band_sum(name):
    c, x = case(name)
    scales = A.morse_scales(len(x))
    f = A.scale_frequencies(scales)
    band = A.low_band_rows(f)
    assert [int(np.flatnonzero(band)[0]) + 1, int(np.flatnonzero(band)[-1]) + 1] == c["band_rows"]
    omega = A.scaled_scalogram(x, scales)[band].sum(axis=0)
    assert np.abs(omega - np.asarray(c["omega"])).max() <= 1.0, "Omega differs from MATLAB by more than one count"


# ── every stage after Omega, given MATLAB's Omega ───────────────────────────

@pytest.mark.parametrize("name", CASES)
def test_candidate_regions_match_the_authors(name):
    c, _ = case(name)
    B, _, _ = A.wavelet_regions(np.asarray(c["omega"], dtype=float), thr=0.05, peak_width=60)
    assert B == zero_based(c["ROIw"])


@pytest.mark.parametrize("name", CASES)
def test_the_spike_and_pseudo_spike_split_matches_the_authors(name):
    c, x = case(name)
    C, D = A.cluster_regions(x, zero_based(c["ROIw"]), peak_width=60)
    assert C == zero_based(c["ROI_ws"])
    assert D == zero_based(c["ROI_ps"])


@pytest.mark.parametrize("name", CASES)
def test_envelope_regions_match_the_authors(name):
    c, x = case(name)
    R, delta, _ = A.envelope_regions(x, peak_width=60)
    assert R == zero_based(c["ROIe"])
    np.testing.assert_allclose(delta, c["ROIe_delta"], rtol=1e-6, atol=1e-15)


@pytest.mark.parametrize("name", CASES)
def test_no_envelope_region_ends_before_it_starts(name):
    _, x = case(name)
    R, _, _ = A.envelope_regions(x, peak_width=60)
    assert R and all(a <= b for a, b in R)


@pytest.mark.parametrize("name", CASES)
def test_located_spikes_match_the_authors(name):
    c, x = case(name)
    S, _ = A.locate_spikes(zero_based(c["ROI_ws"]), zero_based(c["ROIe"]), c["ROIe_delta"])
    assert S == zero_based(c["spikes"])


# ── end to end ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", CASES)
def test_the_whole_detector_reproduces_the_authors_spikes(name):
    c, x = case(name)
    spikes, pseudo, info = A.detect_spikes(x, fs=1.0, window_s=float(len(x)))
    assert spikes == zero_based(c["spikes"])
    assert pseudo == zero_based(c["ROI_ps"])
    assert info["B"] == zero_based(c["ROIw"]) and info["R"] == zero_based(c["ROIe"])


@pytest.mark.parametrize("name", CASES)
def test_spikes_are_disjoint_and_in_order(name):
    """No staircase: one spike per event, none nested in another."""
    _, x = case(name)
    spikes, _, _ = A.detect_spikes(x, fs=1.0, window_s=float(len(x)))
    assert all(a < b for a, b in spikes)
    assert all(spikes[i][1] < spikes[i + 1][0] for i in range(len(spikes) - 1))


@pytest.mark.parametrize("name,at_least", [("a", 5), ("b", 4), ("c", 8)])
def test_the_known_events_are_found(name, at_least):
    """The fixtures carry the events that were injected. The authors' code finds
    5 of 6, 4 of 4 and 8 of 8; the port must find the same ones."""
    c, x = case(name)
    spikes, _, _ = A.detect_spikes(x, fs=1.0, window_s=float(len(x)))
    hit = [e for e in c["events"] if any(a < e["end"] and b >= e["start"] for a, b in spikes)]
    assert len(hit) >= at_least, f"{len(hit)} of {len(c['events'])} injected events overlap a detected spike"


def test_lengths_are_seconds_not_samples():
    """60 s is 600 samples at 10 Hz, not 60 — and the same recording resampled
    to 10 Hz still yields a spike on every injected event. (The spans are not
    identical: the envelope stage works on sample-to-sample curvature, which
    is not the same signal at another rate.)"""
    assert A.samples(60.0, 10.0) == 600 and A.samples(60.0, 1.0) == 60
    c, x = case("b")
    x10 = np.interp(np.arange(len(x) * 10) / 10.0, np.arange(len(x), dtype=float), x)
    spikes, _, _ = A.detect_spikes(x10, fs=10.0, window_s=float(len(x)))
    for e in c["events"]:
        assert any(a < e["end"] * 10 and b >= e["start"] * 10 for a, b in spikes), f"event {e} lost at 10 Hz"


# ── chunking keeps every sample ─────────────────────────────────────────────

def test_state_slicing_is_the_authors_partition():
    x = np.asarray(REF["pulse"]["x"], dtype=float)
    chunks = A.split_signal(x)
    assert chunks == zero_based(REF["pulse"]["chunks"])


@pytest.mark.parametrize("slice_by_state", [False, True])
def test_every_sample_is_in_exactly_one_chunk(slice_by_state):
    x = np.asarray(REF["pulse"]["x"], dtype=float)
    chunks = A.chunks_for(x, 1.0, window_s=1000.0, slice_by_state=slice_by_state)
    covered = np.zeros(len(x), dtype=int)
    for a, b in chunks:
        covered[a:b + 1] += 1
    assert (covered == 1).all(), "slicing discarded or double-counted part of the span"


def test_noise_about_the_midpoint_cuts_nothing():
    """A transition counts only between the two state bands (IEEE 181). The old
    reading cut at every sign change about the mid-reference; a stretch that
    hovers at the midpoint without reaching either state is not a pulse."""
    rng = np.random.default_rng(0)
    x = np.concatenate([np.zeros(1500), np.ones(1500), np.full(600, 0.5), np.zeros(1400)])
    x[3000:3600] += rng.normal(0.0, 0.05, 600)
    x += rng.normal(0.0, 0.005, len(x))
    assert A.split_signal(x) == [(0, len(x) - 1)]


def test_fixed_windows_fold_a_short_tail_into_the_last_window():
    assert A.fixed_windows(7000, 3000) == [(0, 2999), (3000, 6999)]
    assert A.fixed_windows(8000, 3000) == [(0, 2999), (3000, 5999), (6000, 7999)]
    assert A.fixed_windows(100, 3000) == [(0, 99)]


def test_a_two_window_span_is_detected_window_by_window():
    _, xa = case("a")
    _, xb = case("b")
    x = np.concatenate([xa, xb + (xa[-1] - xb[0])])
    spikes, _, info = A.detect_spikes(x, fs=1.0, window_s=3000.0)
    sa, _, _ = A.detect_spikes(xa, fs=1.0, window_s=3000.0)
    sb, _, _ = A.detect_spikes(xb, fs=1.0, window_s=3000.0)
    assert info["chunks"] == [(0, 2999), (3000, 5999)]
    assert spikes == sa + [(a + 3000, b + 3000) for a, b in sb]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

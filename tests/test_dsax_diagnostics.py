"""
test_dsax_diagnostics.py
========================
The UI-free half of what `tests/test_encoding_view_dsax.py` asserted before the
Panel tree was retired (tag `archive/panel-ui`, 2026-09-21). That file mixed
HoloViews rendering tests with these core assertions about the dSAX encoder,
its diagnostic rows and the noise-floor surrogate; the rendering tests died
with `UI/`, these were lifted out verbatim so the core behaviour stays pinned.

Nothing here imports Panel, HoloViews or Bokeh.
"""

import os
import sys

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters
from Adapters.detection_sax_dsax import (
    NOISE_FLOOR_RATIO_ALERT, delta_diagnostic_rows, noise_floor_surrogate_count,
)
from Adapters._sax_common import encoding_diagnostics
from Working.Detection.sax.csax_python.csax import csax
from Working.Detection.sax.psax_python.psax import psax
from Working.Detection.sax.dsax_python.dsax import (
    SYMBOL_LETTERS, SYMBOL_NAMES, dsax, same_band_halfwidth,
    same_fraction_under_halfwidth, working_domain_array,
)
from Working.Detection.sax.dsax_python.trend_estimators import surrogate_same_halfwidth

from tests.test_dsax_engineered import (
    CONSTANT, NOISE, NOISE_PLUS_DRIFT, NOISE_SPS, _detrend_linear,
)

discover_adapters()

SEED = 20260810

# A signal with real structure at the segment scale, used wherever a
# "typical" encoding is wanted rather than a pathological one.
_rng = np.random.default_rng(SEED)
STRUCTURED = (2.0 * np.sin(2 * np.pi * np.arange(4000) / 300.0)
              + _rng.normal(0.0, 0.5, 4000))


def _encode_dsax(x=None, sps=40, **kwargs):
    x = STRUCTURED if x is None else x
    np.random.seed(SEED)
    n_symbols = len(x) // sps
    return dsax(x, len(x), (n_symbols + 0.5) / len(x), return_details=True, **kwargs)


# ============================================================================
# Letters and alphabets
# ============================================================================

def test_declared_letter_maps_are_single_character_and_unique():
    for k, letters in SYMBOL_LETTERS.items():
        assert len(letters) == k, f"k={k}: {letters}"
        assert all(len(c) == 1 for c in letters), \
            f"k={k}: the string/RLE/strip all assume ONE char per symbol"
        assert len(set(letters)) == k, f"k={k}: letters must be unique, got {letters}"
        assert k in SYMBOL_NAMES and len(SYMBOL_NAMES[k]) == k


# ============================================================================
# Diagnostics
# ============================================================================

def test_pure_noise_trips_the_same_fraction_warning():
    symbols, details = _encode_dsax(x=NOISE, sps=NOISE_SPS)
    rows = delta_diagnostic_rows(symbols, details)
    row = [r for r in rows if r[0] == "SAME fraction"][0]
    assert row[2] == "warn", f"pure noise must be flagged, got {row}"
    assert "IMPLEMENTATION_NOTES.md 6.3" in row[1]
    assert "noise-floor" in row[1]


def test_undetrended_drift_trips_the_mean_delta_warning():
    symbols, details = _encode_dsax(x=NOISE_PLUS_DRIFT, sps=NOISE_SPS)
    row = [r for r in delta_diagnostic_rows(symbols, details) if r[0] == "Mean delta"][0]
    assert row[2] == "warn", f"undetrended drift must be flagged, got {row}"
    assert "Detrending is not optional" in row[1]

    # ... and detrending must clear it, or the warning is not actually
    # measuring what it claims to.
    symbols2, details2 = _encode_dsax(x=_detrend_linear(NOISE_PLUS_DRIFT), sps=NOISE_SPS)
    row2 = [r for r in delta_diagnostic_rows(symbols2, details2) if r[0] == "Mean delta"][0]
    assert row2[2] == "", f"detrended signal must NOT be flagged, got {row2}"


def test_constant_signal_names_the_right_degenerate_case():
    symbols, details = _encode_dsax(x=CONSTANT, sps=100)
    rows = delta_diagnostic_rows(symbols, details)
    row = [r for r in rows if r[0] == "Cutlines degenerate"][0]
    assert row[2] == "error", row
    assert "constant" in row[1], row[1]
    assert "straight ramp" not in row[1], "the two degenerate cases must not be collapsed"


def test_straight_ramp_names_the_other_degenerate_case():
    ramp = np.linspace(0.0, 10.0, 1000)
    symbols, details = _encode_dsax(x=ramp, sps=100, normalize=False)
    assert details["cutlines_degenerate"] is True
    row = [r for r in delta_diagnostic_rows(symbols, details)
           if r[0] == "Cutlines degenerate"][0]
    assert "straight ramp" in row[1], row[1]
    assert "constant" not in row[1], "the two degenerate cases must not be collapsed"


def test_diagnostics_are_appended_to_the_shared_rows_not_replacing_them():
    """The shared rows (occupancy entropy, self-transition rate, realised
    alphabet size) serve all three encoders and must survive."""
    from Adapters._sax_common import diagnostic_rows
    symbols, details = _encode_dsax()
    shared = diagnostic_rows(symbols, details)
    combined = list(shared) + delta_diagnostic_rows(symbols, details)
    labels = [label for label, _v, _s in combined]
    for required in ("Occupancy entropy", "Transition self-rate", "Realised alphabet size",
                     "SAME fraction", "SAME band half-width", "Mean delta"):
        assert required in labels, f"{required} missing from {labels}"


def test_entropy_no_longer_reports_negative_zero():
    """The one permitted change to `_sax_common` (IMPLEMENTATION_NOTES 4.2)."""
    diag = encoding_diagnostics(np.ones(50, dtype=int), 3)
    assert diag["occupancy_entropy_bits"] == 0.0
    assert not np.signbit(diag["occupancy_entropy_bits"]), "entropy must not be -0.0"
    assert not np.signbit(diag["occupancy_entropy_fraction"])


# ============================================================================
# Noise floor
# ============================================================================

def test_noise_floor_on_the_section_6_3_fixture_reports_roughly_three_times():
    """IMPLEMENTATION_NOTES.md 6.3 measured 3.1x on exactly this fixture:
    MSE-optimal Lloyd-Max puts the SAME band far narrower than a
    noise-floor justification supports."""
    symbols, details = _encode_dsax(x=NOISE, sps=NOISE_SPS)
    before_cutlines = np.array(details["cutlines"], copy=True)
    before_symbols = np.array(symbols, copy=True)

    learned = same_band_halfwidth(details)
    working = working_domain_array(NOISE, details)
    n_surrogates = noise_floor_surrogate_count(len(working))
    surrogate = surrogate_same_halfwidth(
        working, NOISE_SPS, trend_estimator=details["trend_estimator"],
        n_surrogates=n_surrogates, alpha=0.95, random_state=0,
    )
    ratio = surrogate / learned
    assert 2.0 < ratio < 4.5, f"expected ~3x, got {ratio:.2f}x"
    assert ratio > NOISE_FLOOR_RATIO_ALERT, "this fixture must trip the alert threshold"

    projected, widened = same_fraction_under_halfwidth(details, surrogate)
    assert projected > details["same_fraction_observed"], \
        "imposing a wider floor must increase the SAME fraction"
    assert projected > 0.85, f"a trendless signal should read as mostly SAME, got {projected}"

    # The measurement must not mutate what it measured.
    assert np.array_equal(details["cutlines"], before_cutlines)
    assert np.array_equal(symbols, before_symbols)
    assert widened is not None and widened[1] >= surrogate - 1e-12


def test_working_domain_array_undoes_only_the_encoders_own_normalisation():
    """A half-width estimated on the raw array would be wrong by a factor
    of norm_std -- the same class of units error `delta_scale` exists to
    prevent inside the encoder."""
    _s, details = _encode_dsax(x=NOISE, sps=NOISE_SPS, normalize=True)
    working = working_domain_array(NOISE, details)
    assert len(working) == details["data_len_trimmed"]
    assert abs(float(np.mean(working))) < 1e-9
    assert abs(float(np.std(working)) - 1.0) < 1e-6

    _s, raw_details = _encode_dsax(x=NOISE, sps=NOISE_SPS, normalize=False)
    assert raw_details["norm_std"] is None
    assert np.array_equal(working_domain_array(NOISE, raw_details),
                          NOISE[:raw_details["data_len_trimmed"]])


def test_surrogate_count_flexes_with_span_length_never_the_span():
    assert noise_floor_surrogate_count(6_000) == 50, "short spans get the full draw"
    assert noise_floor_surrogate_count(2_600_000) == 8, "long spans get the floor"
    assert noise_floor_surrogate_count(200_000) == 50
    assert 8 <= noise_floor_surrogate_count(500_000) <= 50


def test_same_fraction_under_halfwidth_is_a_floor_not_an_override():
    _s, details = _encode_dsax(x=NOISE, sps=NOISE_SPS)
    learned = same_band_halfwidth(details)
    narrower, _ = same_fraction_under_halfwidth(details, learned / 4.0)
    assert np.isclose(narrower, details["same_fraction_observed"]), \
        "a floor below the learned band must change nothing"


def test_same_band_helpers_return_none_without_a_same_bin():
    _s, details = _encode_dsax(alphabet_size=4)
    assert same_band_halfwidth(details) is None
    assert same_fraction_under_halfwidth(details, 0.5) == (None, None)


def test_even_alphabet_diagnostics_warn_that_there_is_no_same_band():
    """An even alphabet has a cutline AT zero, not a bin around it; the
    diagnostic rows must say so (a `SAME band` row, severity `warn`, naming
    EVEN) rather than report a half-width that does not exist."""
    symbols, details = _encode_dsax(alphabet_size=4)
    rows = delta_diagnostic_rows(symbols, details)
    labels = {label for label, _v, _s in rows}
    assert "SAME band" in labels
    band_row = [r for r in rows if r[0] == "SAME band"][0]
    assert "EVEN" in band_row[1] and band_row[2] == "warn", band_row


# ============================================================================
# Encoder contract: only dSAX declares a cutline domain
# ============================================================================

def _encode_csax(x=None, dim_ratio=1 / 20):
    x = STRUCTURED if x is None else x
    np.random.seed(SEED)
    return csax(x, len(x), dim_ratio, return_details=True)


def _encode_psax(x=None, dim_ratio=1 / 20, alphabet_size=8):
    x = STRUCTURED if x is None else x
    np.random.seed(SEED)
    return psax(x, len(x), dim_ratio, alphabet_size=alphabet_size, return_details=True)


def test_dsax_declares_its_cutline_domain_and_the_amplitude_encoders_do_not():
    """`webui/server/serialize.py` reads `details["cutline_domain"]` to decide
    which array the cutlines are drawn against. dSAX must DECLARE `delta` and
    carry the `deltas` it quantised; cSAX/pSAX must not have been edited to
    grow either key — their cutlines are in the amplitude domain by absence."""
    _sym, dsax_details = _encode_dsax()
    assert dsax_details["cutline_domain"] == "delta", "dSAX must DECLARE its domain"
    assert "deltas" in dsax_details

    for _s, details in (_encode_csax(), _encode_psax()):
        assert "cutline_domain" not in details, \
            "csax/psax must NOT have been edited to declare a domain"
        assert "deltas" not in details

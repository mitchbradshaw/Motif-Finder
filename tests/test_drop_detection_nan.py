"""
test_drop_detection_nan.py
============================
The drop detector when the span holds missing samples (NaN, inf): the canonical
`drop_detection_v1` chain (preprocessing.detrend rolling_mean_nearest -> detection.stage_encoding ->
detection.drop_detection), the one-call five-stage detector (`detect5.detect_drops5`), the older three-stage
detector (`detect.detect_drops`), and the dSAX encoder all three stand on.

Measured 2026-10-14 on a 4 h, 1 Hz synthetic (`_fluss_synthetic._regime_a` + noise + drift, a drop every 900 s):
14 events with no gap; one 60-sample NaN gap at sample 8000 -> 0 events, and nothing said so. The detrend already
kept a gap to its own length (tests/test_detrend_nan.py). Three whole-span statistics downstream did not:

1. the slope-noise floor (`detect.slope_noise_sigma`, a median of second differences) came out NaN, so no segment
   and no sample passed `slope_sigma x sigma`;
2. dSAX's z-normalisation (`data.mean()`, `data.std()`) came out NaN, so every segment's slope was NaN, not just
   the two segments the gap touches;
3. dSAX's cutlines (quantiles of those slopes) came out NaN, so every segment read 'U' (147 of 147); in dSAX's
   default learned mode k-means++ raised IndexError instead.

The researcher's decision (2026-10-14): skip the gaps. Pinned here:

- the noise floor, dSAX's normalisation and its cutlines are measured over the recorded samples and segments;
- a segment that touches a missing sample gets no letter: symbol -1, letter '-' (`dsax.MISSING_SYMBOL`,
  `dsax.MISSING_LETTER`), in every dSAX mode, in the five-stage encoding, in symbol search and in the UI's letters,
  and '-' is never read as a rise or a fall;
- no event is drawn across a gap: no rise, fall, trough search or window crosses a missing sample. A candidate
  whose fall runs into a gap, or whose shoulder lies in one, is left out and counted (`rejected_at_gap`); a window
  that would reach a gap ends at it;
- so a gap costs only the events it touches: on the synthetic the gap-free run's 14 events come back but the one
  whose run-up passes through the gap, at the same onsets and troughs;
- finite input gives what it gave before, bit for bit, against verbatim copies of today's functions
  (`tests/_drop_nan_today.py`); `tests/test_template_drop_detection.py` still reproduces the seed events where
  the real channel is on disk.

No recording in the database held a NaN on 2026-10-14, so no shipped result was wrong.

Runnable standalone:  python tests/test_drop_detection_nan.py
"""

import dataclasses
import importlib
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _drop_nan_today as today  # noqa: E402
from _fluss_synthetic import _regime_a  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Detection.drop_motifs.detect import (  # noqa: E402
    DetectionParams, detect_drops, dim_ratio_for_segments, robust_sigma, slope_noise_sigma,
)
from Working.Detection.drop_motifs.detect5 import (  # noqa: E402
    Detect5Params, detect_drops5, detect_from_letters, morphology_from_letters, stage_letters,
)
from Working.Detection.sax.dsax_python.dsax import dsax, dsax_letters  # noqa: E402
from Working.Preprocessing.detrend import make_detrend_filter  # noqa: E402
from Working.types import Encoding  # noqa: E402

DSAX = importlib.import_module("Working.Detection.sax.dsax_python.dsax")   # the module (the package exports the function)

discover_adapters()

# numpy says "Mean of empty slice" / "invalid value encountered" when a NaN reaches a statistic: none may
pytestmark = pytest.mark.filterwarnings("error::RuntimeWarning")

MISSING_SYMBOL, MISSING_LETTER = -1, "-"
MISSING = pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf], ids=["nan", "+inf", "-inf"])

FS = 1.0
N = 14400                       # 4 h at 1 Hz
GAP = (8000, 8060)              # the 2026-10-14 measurement's gap
TEMPLATE = dict(window_s=4916.67, segment_seconds=98.33, same_fraction=0.6, slope_sigma=8.0)   # drop_detection_v1
P5 = dict(detrend_window_s=4000.0, segment_seconds=20.0, same_fraction=0.5, slope_sigma=4.0)   # the detect5 tests'


# -- recordings -------------------------------------------------------------------------------------------------

def recording(gap=None, bad=np.nan, seed=0):
    """The measurement's recording: regime A (a sudden 1.0 fall, tau-300 s recovery, every 900 s from sample 100),
    N(0, 0.05) noise and a 0-2 linear drift; `gap` half-open, set to `bad`."""
    rng = np.random.default_rng(seed)
    x = _regime_a(N) + rng.normal(0.0, 0.05, N) + np.linspace(0.0, 2.0, N)
    if gap is not None:
        x[gap[0]:gap[1]] = bad
    return x


def sharkfins(n=4, rise=300, fall=60, flat=40, lead=200, amp=10.0, noise=0.02, seed=11):
    """Linear rise, fast linear fall, flat; returns (x, true onsets). As in test_drop_motifs_detect5."""
    cyc = np.concatenate([np.linspace(0.0, amp, rise, endpoint=False), np.linspace(amp, 0.0, fall, endpoint=False),
                          np.zeros(flat)])
    x = np.concatenate([np.zeros(lead)] + [cyc] * n)
    return x + np.random.default_rng(seed).normal(0.0, noise, len(x)), [lead + i * len(cyc) + rise for i in range(n)]


def troughs(n=4, flat=200, fall=40, bottom=60, rise=120, lead=200, amp=10.0, noise=0.02, seed=11):
    """Flat, fast fall, flat bottom, slow recovery; returns (x, true onsets). As in test_drop_motifs_detect5."""
    cyc = np.concatenate([np.zeros(flat), np.linspace(0.0, -amp, fall, endpoint=False), np.full(bottom, -amp),
                          np.linspace(-amp, 0.0, rise, endpoint=False)])
    x = np.concatenate([np.zeros(lead)] + [cyc] * n)
    return x + np.random.default_rng(seed).normal(0.0, noise, len(x)), [lead + i * len(cyc) + flat for i in range(n)]


def with_gap(x, lo, hi, bad=np.nan):
    x = np.array(x, dtype=float)
    x[lo:hi] = bad
    return x


def detrended(x, window_s=TEMPLATE["window_s"]):
    return make_detrend_filter(FS, mode="rolling_mean_nearest", window_s=window_s)(x)


def chain(x, **over):
    """drop_detection_v1's three blocks, run one after another: (detrended x, encoding result, detection result)."""
    p = {**TEMPLATE, **over}
    t = np.arange(len(x)) / FS
    xd = detrended(x, p["window_s"])
    enc = get_adapter("detection.stage_encoding").run(
        xd, t, FS, segment_seconds=p["segment_seconds"], same_fraction=p["same_fraction"], slope_sigma=p["slope_sigma"])
    det = get_adapter("detection.drop_detection").run(xd, t, FS, slope_sigma=p["slope_sigma"], value=enc.value)
    return xd, enc, det


def touched_segments(n_symbols, sps, lo, hi):
    """The segments [i*sps, (i+1)*sps) that share a sample with [lo, hi)."""
    starts = np.arange(n_symbols) * sps
    return np.flatnonzero((starts < hi) & (starts + sps > lo)).tolist()


def recorded(x, lo, hi):
    return bool(np.isfinite(np.asarray(x)[lo:hi]).all())


def event_reach(e):
    """[first, last] sample an event's anatomy uses: from its rise (rise trigger) or onset, to its trough."""
    up = e["up_region_start_idx"] if e["up_region_start_idx"] >= 0 else e["onset_idx"]
    return min(up, e["onset_idx"]), e["trough_idx"]


def rows(events):
    return [dataclasses.asdict(e) for e in events]


def same(a, b):
    """Equal, with NaN equal to NaN, recursively through dicts, lists, tuples and arrays."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(u, v) for u, v in zip(a, b))
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a, b = np.asarray(a), np.asarray(b)
        if a.shape != b.shape or a.dtype.kind != b.dtype.kind:
            return False
        return bool(np.array_equal(a, b, equal_nan=a.dtype.kind in "fc"))
    if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
        return True
    return type(a) is type(b) and a == b


# ===============================================================================================================
# finite input: what it gave before, bit for bit
# ===============================================================================================================

def _finite_signals():
    sf, _ = sharkfins()
    tr, _ = troughs()
    rng = np.random.default_rng(3)
    return {
        "regime_a": recording(),
        "regime_a_detrended": detrended(recording()),
        "sharkfins": sf,
        "troughs": tr,
        "random_walk": rng.normal(size=6000).cumsum(),
        "piecewise_linear": np.concatenate([np.linspace(0, 5, 400), np.linspace(5, -2, 50), np.linspace(-2, 0, 300)]),
        "constant": np.full(500, 3.0),
    }


FINITE = _finite_signals()


@pytest.mark.parametrize("name", sorted(FINITE))
def test_finite_noise_floor_is_what_it_was_bit_for_bit(name):
    x = FINITE[name]
    for estimator in ("second_difference", "gradient"):
        for fs in (1.0, 10.0):
            assert slope_noise_sigma(x, fs, estimator) == today.slope_noise_sigma(x, fs, estimator), (estimator, fs)
    for v in (x, np.diff(x, 2), np.array([]), np.array([1.0]), np.r_[np.zeros(50), 1e6]):
        assert robust_sigma(v) == today.robust_sigma(v)


DSAX_FINITE_CASES = [
    dict(threshold_mode="quantile", same_fraction=0.6),
    dict(threshold_mode="quantile", same_fraction=0.6, force_symmetric=False),
    dict(threshold_mode="quantile", alphabet_size=5),
    dict(threshold_mode="learned"),
    dict(threshold_mode="learned", alphabet_size=5),
    dict(threshold_mode="learned", alphabet_size=4, normalize=False),
    dict(threshold_mode="absolute", absolute_threshold=0.05),
    dict(threshold_mode="quantile", same_fraction=0.5, trend_estimator="endpoints"),
    dict(threshold_mode="learned", trend_estimator="robust_endpoints", endpoint_k=3),
    dict(threshold_mode="quantile", same_fraction=0.5, trend_estimator="theil_sen"),
    dict(threshold_mode="learned", min_same_halfwidth=0.2),
]


@pytest.mark.parametrize("name", sorted(FINITE))
@pytest.mark.parametrize("case", DSAX_FINITE_CASES, ids=lambda c: "-".join(f"{k}={v}" for k, v in c.items()))
def test_finite_dsax_is_what_it_was_bit_for_bit(name, case):
    x = FINITE[name]
    ratio = dim_ratio_for_segments(len(x), 25)
    got, got_d = dsax(x, len(x), ratio, return_details=True, **case)
    ref, ref_d = today.dsax(x, len(x), ratio, return_details=True, **case)
    assert np.array_equal(got, ref) and got.dtype == ref.dtype
    assert {k: got_d[k] for k in ref_d}.keys() == ref_d.keys()
    for k in ref_d:
        assert same(got_d[k], ref_d[k]), k
    assert got_d.get("n_missing_segments", 0) == 0
    assert dsax_letters(got, case.get("alphabet_size", 3)) == today.dsax_letters(ref, case.get("alphabet_size", 3))
    assert np.array_equal(dsax(x, len(x), ratio, **case), ref)


def test_finite_letters_render_as_they_did():
    for k in (2, 3, 4, 5, 7, 26, 30):
        s = np.arange(k)
        assert dsax_letters(s, k) == today.dsax_letters(s, k)


def _detect5_cases():
    sf, _ = sharkfins()
    tr, _ = troughs()
    template = dict(detrend_window_s=4916.67, segment_seconds=98.33, same_fraction=0.6, slope_sigma=8.0)
    return [
        ("regime_a", recording(), template),
        ("regime_a/old-flags", recording(), dict(template, bracket_on_fall_runs=False, walk_onset_back=False)),
        ("sharkfins", sf, P5),
        ("sharkfins/no-tighten", sf, dict(P5, tighten_windows=False, min_separation_s=30.0)),
        ("troughs", tr, P5),
        ("troughs/rise-separation", tr, dict(P5, bracket_rise_on_separation=True, min_separation_s=30.0)),
        ("troughs/forced-sharkfin", tr, dict(P5, morphology="sharkfin")),
        ("random_walk", np.random.default_rng(5).normal(size=5000).cumsum(), P5),
        ("constant", np.full(500, 2.0), P5),
    ]


@pytest.mark.parametrize("name,x,kw", _detect5_cases(), ids=[c[0] for c in _detect5_cases()])
def test_finite_five_stage_detector_is_what_it_was_bit_for_bit(name, x, kw):
    p = Detect5Params(**kw)
    got, ref = detect_drops5(x, FS, p), today.detect_drops5(x, FS, p)
    assert same(rows(got.events), rows(ref.events))
    assert {k: got.counts[k] for k in ref.counts} == ref.counts
    assert got.counts.get("rejected_at_gap", 0) == 0 and got.counts.get("missing_segments", 0) == 0
    assert got.letters == ref.letters and got.morphology == ref.morphology
    assert np.array_equal(got.x_detrended, ref.x_detrended)
    drop = {"elapsed_s"}
    assert same({k: v for k, v in got.diagnostics.items() if k not in drop},
                {k: v for k, v in ref.diagnostics.items() if k not in drop})
    letters, details = stage_letters(x, FS, p)
    ref_letters, ref_details = today.stage_letters(x, FS, p)
    assert letters == ref_letters
    for k in ref_details:
        assert same(details[k], ref_details[k]), k


@pytest.mark.parametrize("name,x,kw", _detect5_cases()[:7], ids=[c[0] for c in _detect5_cases()[:7]])
def test_finite_block_form_is_what_it_was_bit_for_bit(name, x, kw):
    """The two blocks' halves (`morphology_from_letters`, `detect_from_letters`) on letters in hand."""
    p = Detect5Params(**kw)
    xd = detrended(x, kw["detrend_window_s"])
    block = dataclasses.replace(p, detrend_window_s=0.0)
    letters, details = today.stage_letters(xd, FS, block)
    sps = int(details["samples_per_symbol"])
    sigma = today.slope_noise_sigma(xd, FS)
    assert morphology_from_letters(letters, xd, sps, block) == today.morphology_from_letters(letters, xd, sps, block)
    morph = today.morphology_from_letters(letters, xd, sps, block)
    got = detect_from_letters(xd, FS, letters, sps, sigma, morph, block)
    ref = today.detect_from_letters(xd, FS, letters, sps, sigma, morph, block)
    assert same(rows(got.events), rows(ref.events))
    assert {k: got.counts[k] for k in ref.counts} == ref.counts


def test_finite_template_chain_gives_the_frozen_detectors_events():
    """The three blocks on a finite recording give exactly what today's functions give."""
    x = recording()
    xd, enc, det = chain(x)
    block = Detect5Params(detrend_window_s=0.0, segment_seconds=TEMPLATE["segment_seconds"],
                          same_fraction=TEMPLATE["same_fraction"], slope_sigma=TEMPLATE["slope_sigma"])
    letters, details = today.stage_letters(xd, FS, block)
    assert enc.meta["letters"] == letters
    assert enc.meta.get("missing_segments", 0) == 0
    sps = len(xd) // len(letters)
    params = dataclasses.replace(block, segment_seconds=sps / FS, same_fraction=float("nan"))
    ref = today.detect_from_letters(xd, FS, letters, sps, today.slope_noise_sigma(xd, FS),
                                    today.morphology_from_letters(letters, xd, sps, params), params)
    expect = rows(ref.events)
    for r in expect:
        r["same_fraction"] = None
    assert same(det.meta["events"], expect)
    assert len(expect) == 14


def _old_cases():
    sf, _ = sharkfins()
    return [
        ("regime_a", recording(), dict(detrend_window_s=4916.67, segment_seconds=98.33, same_fraction=0.6)),
        ("sharkfins", sf, dict(detrend_window_s=4000.0, segment_seconds=20.0, same_fraction=0.5, slope_sigma=4.0)),
        ("sharkfins/dedup", sf, dict(detrend_window_s=4000.0, segment_seconds=20.0, min_separation_s=200.0,
                                     merge_gap_segments=1, noise_estimator="gradient")),
        ("constant", np.full(300, 1.0), dict(detrend_window_s=100.0, segment_seconds=10.0)),
    ]


@pytest.mark.parametrize("name,x,kw", _old_cases(), ids=[c[0] for c in _old_cases()])
def test_finite_three_stage_detector_is_what_it_was_bit_for_bit(name, x, kw):
    p = DetectionParams(**kw)
    got, ref = detect_drops(x, FS, p), today.detect_drops(x, FS, p)
    assert same(rows(got.events), rows(ref.events))
    assert {k: got.counts[k] for k in ref.counts} == ref.counts
    assert got.counts.get("rejected_at_gap", 0) == 0 and got.counts.get("missing_segments", 0) == 0
    assert np.array_equal(got.x_detrended, ref.x_detrended)
    drop = {"elapsed_s"}
    assert same({k: v for k, v in got.diagnostics.items() if k not in drop},
                {k: v for k, v in ref.diagnostics.items() if k not in drop})


# ===============================================================================================================
# the noise floor, over the recorded samples
# ===============================================================================================================

def _noise_floor_by_definition(x, fs=1.0):
    """The second-difference estimate written out over the recorded samples only: the MAD of the finite second
    differences, / sqrt(6) to an amplitude, / sqrt(2) for a central difference, floored at 1% of the MAD of the
    finite gradient (the smooth-signal guard)."""
    x = np.where(np.isfinite(x), x, np.nan)

    def mad_sigma(v):
        v = v[np.isfinite(v)]
        return 1.4826 * float(np.median(np.abs(v - np.median(v))))

    gradient_sigma = mad_sigma(np.gradient(x)) * fs
    sigma = mad_sigma(np.diff(x, 2)) / np.sqrt(6.0) / np.sqrt(2.0) * fs
    return max(sigma, gradient_sigma * 0.01)


@MISSING
def test_the_noise_floor_is_measured_over_the_recorded_samples(bad):
    clean = detrended(recording())
    gapped = detrended(recording(GAP, bad))
    sigma = slope_noise_sigma(gapped, FS)
    assert np.isfinite(sigma)
    assert sigma == pytest.approx(_noise_floor_by_definition(gapped), rel=1e-12)
    assert sigma == pytest.approx(slope_noise_sigma(clean, FS), rel=0.03)      # the same noise, 60 samples fewer
    assert np.isfinite(slope_noise_sigma(gapped, FS, "gradient"))


def test_robust_sigma_reads_the_finite_values_only():
    v = np.random.default_rng(1).normal(size=400)
    holed = v.copy()
    holed[[3, 50, 51, 200]] = [np.nan, np.inf, -np.inf, np.nan]
    assert robust_sigma(holed) == robust_sigma(np.delete(v, [3, 50, 51, 200]))
    assert robust_sigma(np.full(10, np.nan)) == 0.0


def test_an_unrecorded_span_has_a_noise_floor_of_zero_not_nan():
    assert slope_noise_sigma(np.full(500, np.nan), FS) == 0.0


# ===============================================================================================================
# dSAX: the segments a gap touches get no letter; everything else is measured over what was recorded
# ===============================================================================================================

def test_the_missing_symbol_and_letter_are_named_once_in_dsax():
    assert DSAX.MISSING_SYMBOL == MISSING_SYMBOL and DSAX.MISSING_LETTER == MISSING_LETTER


DSAX_MODES = [
    dict(threshold_mode="quantile", same_fraction=0.6),
    dict(threshold_mode="quantile", alphabet_size=5),
    dict(threshold_mode="learned"),
    dict(threshold_mode="learned", alphabet_size=5),
    dict(threshold_mode="absolute", absolute_threshold=0.05),
    dict(threshold_mode="quantile", same_fraction=0.6, trend_estimator="endpoints"),
    dict(threshold_mode="quantile", same_fraction=0.6, trend_estimator="theil_sen"),
]


@MISSING
@pytest.mark.parametrize("case", DSAX_MODES, ids=lambda c: "-".join(f"{k}={v}" for k, v in c.items()))
def test_dsax_marks_exactly_the_segments_a_gap_touches(case, bad):
    x = detrended(recording(GAP, bad))
    ratio = dim_ratio_for_segments(len(x), 98)
    k = case.get("alphabet_size", 3)
    symbols, details = dsax(x, len(x), ratio, return_details=True, **case)
    sps, n = details["samples_per_symbol"], details["n_symbols"]
    gone = touched_segments(n, sps, *GAP)
    assert len(gone) == 2                                             # 97-sample segments 82 and 83
    assert np.flatnonzero(symbols == MISSING_SYMBOL).tolist() == gone
    kept = np.delete(symbols, gone)
    assert ((kept >= 0) & (kept < k)).all()
    letters = dsax_letters(symbols, k)
    assert [i for i, c in enumerate(letters) if c == MISSING_LETTER] == gone
    assert details["n_missing_segments"] == len(gone)
    assert np.isfinite(details["cutlines"]).all() and np.isfinite(details["representatives"]).all()
    assert np.isnan(details["deltas"][gone]).all() and np.isfinite(np.delete(details["deltas"], gone)).all()
    assert np.isnan(details["paa"][gone]).all() and np.isfinite(np.delete(details["paa"], gone)).all()
    assert 0.0 < details["same_fraction_observed"] <= 1.0
    assert np.isfinite(details["delta_mean"])


def test_dsax_learns_its_normalisation_and_cutlines_from_the_recorded_segments_only():
    """Quantile mode written out by hand over the recorded samples and segments."""
    x = recording(GAP)
    ratio = dim_ratio_for_segments(len(x), 98)
    symbols, details = dsax(x, len(x), ratio, alphabet_size=3, threshold_mode="quantile", same_fraction=0.6,
                            return_details=True)
    sps, n = details["samples_per_symbol"], details["n_symbols"]
    xt = x[:n * sps]
    rec = xt[np.isfinite(xt)]
    mu, sd = rec.mean(), rec.std()
    seg = ((xt - mu) / sd).reshape(n, sps)
    present = np.isfinite(seg).all(axis=1)
    idx = np.arange(sps, dtype=float) - (sps - 1) / 2.0
    deltas = seg[present] @ idx / (idx @ idx) * (sps - 1)
    lo, hi = np.quantile(deltas, [0.2, 0.8])
    cut = np.array([(lo - hi) / 2.0, (hi - lo) / 2.0])
    assert details["norm_mean"] == pytest.approx(mu, rel=1e-12)
    assert details["norm_std"] == pytest.approx(sd, rel=1e-12)
    np.testing.assert_allclose(details["cutlines"], cut, rtol=1e-9, atol=0)
    assert np.array_equal(symbols[present], np.searchsorted(cut, deltas, side="right"))
    assert details["same_fraction_observed"] == pytest.approx(float(np.mean(symbols[present] == 1)))


@pytest.mark.parametrize("case", DSAX_MODES, ids=lambda c: "-".join(f"{k}={v}" for k, v in c.items()))
def test_an_unrecorded_span_encodes_as_all_missing(case):
    x = np.full(3000, np.nan)
    symbols, details = dsax(x, len(x), 0.05, return_details=True, **case)
    assert (symbols == MISSING_SYMBOL).all()
    assert details["n_missing_segments"] == len(symbols) == details["n_symbols"]
    assert set(dsax_letters(symbols, case.get("alphabet_size", 3))) == {MISSING_LETTER}


def test_letters_spell_the_missing_symbol_at_any_alphabet_size():
    for k in (3, 5, 7, 30):
        assert dsax_letters(np.array([MISSING_SYMBOL, 0, MISSING_SYMBOL]), k)[::2] == MISSING_LETTER * 2


# ===============================================================================================================
# the five-stage encoding
# ===============================================================================================================

@MISSING
def test_the_five_stage_encoding_marks_the_gap_and_keeps_its_noise_floor(bad):
    _, enc0, _ = chain(recording())
    _, enc, _ = chain(recording(GAP, bad))
    letters = enc.meta["letters"]
    sps = enc.meta["details"]["samples_per_symbol"]
    gone = touched_segments(len(letters), sps, *GAP)
    assert [i for i, c in enumerate(letters) if c == MISSING_LETTER] == gone
    assert set(np.delete(np.array(list(letters)), gone)) <= set("dDSUu")
    assert np.flatnonzero(np.asarray(enc.value.values) == MISSING_SYMBOL).tolist() == gone
    assert enc.meta["missing_segments"] == len(gone)
    assert np.isfinite(enc.meta["sigma_slope"])
    assert enc.meta["sigma_slope"] == pytest.approx(enc0.meta["sigma_slope"], rel=0.03)
    assert enc.meta["same_fraction_observed"] == pytest.approx(enc0.meta["same_fraction_observed"], abs=0.05)
    away = [i for i in range(len(letters)) if i not in gone]
    assert np.mean([letters[i] == enc0.meta["letters"][i] for i in away]) >= 0.95   # a whole-span statistic moved a little


# ===============================================================================================================
# the drop detector: a gap costs only the events it touches, and no event is drawn across one
# ===============================================================================================================

@MISSING
def test_a_gap_costs_drop_detection_v1_only_the_event_it_touches(bad):
    _, _, free = chain(recording())
    x = recording(GAP, bad)
    _, enc, gapped = chain(x)
    ev0, ev1 = free.meta["events"], gapped.meta["events"]
    assert len(ev0) == 14
    hit = [e for e in ev0 if event_reach(e)[0] < GAP[1] and event_reach(e)[1] >= GAP[0]]
    assert [e["onset_idx"] for e in hit] == [8198]          # the drop whose run-up passes through the gap
    assert [(e["onset_idx"], e["trough_idx"]) for e in ev1] == \
        [(e["onset_idx"], e["trough_idx"]) for e in ev0 if e not in hit]
    for e in ev1:
        assert recorded(x, *event_reach(e)) and recorded(x, e["window_start_idx"], e["window_end_idx"])
    for s, t in zip(gapped.value.starts, gapped.value.ends):
        assert recorded(x, s, t)
    assert gapped.meta["counts"]["missing_segments"] == enc.meta["missing_segments"] == 2


@MISSING
def test_the_one_call_five_stage_detector_skips_the_gap_too(bad):
    p = Detect5Params(detrend_window_s=TEMPLATE["window_s"], segment_seconds=TEMPLATE["segment_seconds"],
                      same_fraction=TEMPLATE["same_fraction"], slope_sigma=TEMPLATE["slope_sigma"])
    x = recording(GAP, bad)
    r0, r1 = detect_drops5(recording(), FS, p), detect_drops5(x, FS, p)
    ev0, ev1 = rows(r0.events), rows(r1.events)
    hit = [e for e in ev0 if event_reach(e)[0] < GAP[1] and event_reach(e)[1] >= GAP[0]]
    assert len(ev0) == 14 and len(hit) == 1
    assert [(e["onset_idx"], e["trough_idx"]) for e in ev1] == \
        [(e["onset_idx"], e["trough_idx"]) for e in ev0 if e not in hit]
    assert all(recorded(x, e["window_start_idx"], e["window_end_idx"]) for e in ev1)
    assert r1.counts["missing_segments"] == 2
    assert MISSING_LETTER * 2 in r1.letters
    assert np.isfinite(r1.diagnostics["sigma_slope_mv_per_s"])


@MISSING
def test_the_three_stage_detector_skips_the_gap_too(bad):
    p = DetectionParams(detrend_window_s=TEMPLATE["window_s"], segment_seconds=TEMPLATE["segment_seconds"],
                        same_fraction=TEMPLATE["same_fraction"], slope_sigma=TEMPLATE["slope_sigma"])
    x = recording(GAP, bad)
    r0, r1 = detect_drops(recording(), FS, p), detect_drops(x, FS, p)
    hit = [e for e in r0.events if e.up_region_start_idx < GAP[1] and e.trough_idx >= GAP[0]]
    assert len(r0.events) == 15 and [e.onset_idx for e in hit] == [8199]
    assert [e.onset_idx for e in r1.events] == [e.onset_idx for e in r0.events if e not in hit]
    for e in r1.events:
        assert recorded(x, e.up_region_start_idx, e.trough_idx + 1)
        assert recorded(x, e.snippet_start_idx, e.snippet_end_idx)
        assert np.isfinite([e.peak_to_peak_mv, e.drop_depth_mv, e.onset_slope_raw]).all()
    assert r1.counts["missing_segments"] == 2
    assert np.isfinite(r1.diagnostics["sigma_slope_mv_per_s"])
    assert np.isfinite(r1.diagnostics["cutlines_raw_mv"]).all()


@MISSING
def test_a_rise_before_a_gap_and_a_fall_after_it_are_not_one_event(bad):
    x, onsets = sharkfins()
    r0 = detect_drops5(x, FS, Detect5Params(**P5))
    assert [e.onset_idx for e in r0.events] == [500, 900, 1299, 1700]
    gapped = with_gap(x, onsets[1] - 10, onsets[1] + 5, bad)          # the peak of the second fin
    r1 = detect_drops5(gapped, FS, Detect5Params(**P5))
    assert [e.onset_idx for e in r1.events] == [500, 1299, 1700]
    assert all(recorded(gapped, e.up_region_start_idx, e.window_end_idx) for e in r1.events)


@MISSING
def test_a_fall_that_runs_into_a_gap_is_left_out_and_counted(bad):
    x, onsets = sharkfins()
    gapped = with_gap(x, onsets[1] + 25, onsets[1] + 40, bad)         # part-way down the second fin's fall
    r1 = detect_drops5(gapped, FS, Detect5Params(**P5))
    assert [e.onset_idx for e in r1.events] == [500, 1299, 1700]
    assert r1.counts["rejected_at_gap"] == 1


@MISSING
def test_a_fall_whose_shoulder_lies_in_a_gap_is_left_out_and_counted(bad):
    x, onsets = troughs()
    r0 = detect_drops5(x, FS, Detect5Params(**P5))
    assert r0.morphology == "trough" and [e.onset_idx for e in r0.events] == [399, 820, 1239, 1659]
    gapped = with_gap(x, onsets[1] - 10, onsets[1] + 5, bad)          # the second trough's shoulder
    r1 = detect_drops5(gapped, FS, Detect5Params(**P5))
    assert [e.onset_idx for e in r1.events] == [399, 1239, 1659]
    assert r1.counts["rejected_at_gap"] == 1


@MISSING
def test_a_window_that_would_reach_a_gap_ends_at_it(bad):
    x, onsets = troughs()
    r0 = detect_drops5(x, FS, Detect5Params(**P5))
    lo = onsets[1] + 40 + 60 + 40                                      # part-way up the second trough's recovery
    gapped = with_gap(x, lo, lo + 15, bad)
    r1 = detect_drops5(gapped, FS, Detect5Params(**P5))
    assert [(e.onset_idx, e.trough_idx) for e in r1.events] == [(e.onset_idx, e.trough_idx) for e in r0.events]
    second = r1.events[1]
    assert r0.events[1].window_end_idx > lo and second.window_end_idx == lo
    assert all(recorded(gapped, e.window_start_idx, e.window_end_idx) for e in r1.events)


@MISSING
def test_the_old_detector_does_not_join_a_rise_and_a_fall_across_a_gap(bad):
    x, onsets = sharkfins()
    p = DetectionParams(detrend_window_s=4000.0, segment_seconds=20.0, same_fraction=0.5, slope_sigma=4.0)
    r0 = detect_drops(x, FS, p)
    assert onsets[1] in [e.onset_idx for e in r0.events]
    gapped = with_gap(x, onsets[1] - 10, onsets[1] + 5, bad)
    r1 = detect_drops(gapped, FS, p)
    assert [e.onset_idx for e in r1.events] == [e.onset_idx for e in r0.events if e.onset_idx != onsets[1]]
    assert all(recorded(gapped, e.up_region_start_idx, e.snippet_end_idx) for e in r1.events)


def test_an_unrecorded_span_finds_nothing_and_says_why():
    x = np.full(6000, np.nan)
    _, enc, det = chain(x)
    assert set(enc.meta["letters"]) == {MISSING_LETTER}
    assert det.meta["n_events"] == 0
    assert det.meta["counts"]["missing_segments"] == enc.meta["n_segments"] == len(enc.meta["letters"])
    r5 = detect_drops5(x, FS, Detect5Params(**P5))
    assert r5.events == [] and np.isnan(r5.x_detrended).all()
    r3 = detect_drops(x, FS, DetectionParams(detrend_window_s=600.0, segment_seconds=20.0))
    assert r3.events == [] and r3.counts.get("degenerate_span")


# ===============================================================================================================
# every reader of the letters: a missing segment is '-', never a rise, a fall or an error
# ===============================================================================================================

def test_the_drop_detection_block_reads_a_missing_segment_as_a_gap():
    from Adapters.detection_drop_detection import letters_from_encoding
    assert letters_from_encoding(Encoding(values=np.array([-1, 2, 3, 0, 4, -1]), kind="symbolic")) == "-SUdu-"
    for wrong in ([-2, 2], [5, 1]):
        with pytest.raises(ValueError):
            letters_from_encoding(Encoding(values=np.array(wrong), kind="symbolic"))


def test_a_rise_is_never_bridged_across_a_missing_segment():
    from Working.Detection.drop_motifs.detect import merge_up_runs, up_regions
    from Working.Detection.drop_motifs.detect5 import fall_runs, up_runs
    assert merge_up_runs("UU-UU", 2) == "UU-UU" and merge_up_runs("UUSUU", 2) == "UUUUU"
    assert up_regions("UU-UU") == [(0, 2), (3, 5)] and up_runs("Uu-uU") == [(0, 2), (3, 5)]
    assert fall_runs("dD-Dd") == [(0, 2), (3, 5)]


def test_symbol_search_never_reads_a_missing_segment_as_a_letter():
    enc = Encoding(values=np.array([3, 3, -1, 0, 4, -1]), kind="symbolic")
    search = get_adapter("detection.symbol_search")
    five = search.run(np.zeros(60), None, FS, pattern="u", alphabet="dDSUu", value=enc)
    assert five.meta["string"] == "UU-du-"
    assert list(zip(five.value.starts, five.value.ends)) == [(40, 50)]
    plain = search.run(np.zeros(60), None, FS, pattern="z", value=enc)
    assert plain.meta["string"] == "dd-ae-" and plain.meta["n_matches"] == 0


def test_the_ui_spells_a_missing_segment_with_a_dash():
    from server.serialize import to_payload
    x = detrended(recording(GAP))
    t = np.arange(N) / FS
    ctx = {"fs": FS, "n_samples": N, "span_start": 0}
    plain = get_adapter("detection.sax_dsax").run(x, t, FS, seconds_per_symbol=98.33, threshold_mode="quantile",
                                                  same_fraction=0.6)
    gone = np.flatnonzero(np.asarray(plain.value.values) == MISSING_SYMBOL).tolist()
    assert gone
    payload = to_payload("encoding", plain.value, plain.meta, ctx)
    assert [payload["letters"][i] for i in gone] == [MISSING_LETTER] * len(gone)
    assert set(payload["letters"]) == set("abc-")
    assert all(payload["paa"][i] is None for i in gone)
    _, enc, _ = chain(recording(GAP))
    five = to_payload("encoding", enc.value, enc.meta, ctx)
    assert [i for i, c in enumerate(five["letters"]) if c == MISSING_LETTER] == touched_segments(
        len(enc.meta["letters"]), enc.meta["details"]["samples_per_symbol"], *GAP)


def _derive_rows(name, x, value=None):
    spec = get_adapter(name)
    params = {p.name: p.default for p in spec.params}
    t = np.arange(len(x)) / FS
    return spec.derive(x, t, FS, params) if value is None else spec.derive(x, t, FS, params, value=value)


def test_the_block_pages_say_how_much_is_missing_before_a_run():
    x = detrended(recording(GAP))
    _, enc, _ = chain(recording(GAP))
    for name, value in (("detection.stage_encoding", None), ("detection.drop_detection", enc.value)):
        got = _derive_rows(name, x, value)
        assert not any("nan" in str(v).lower() for _, v, _ in got), (name, got)
        missing = [r for r in got if r[0] == "Missing samples"]
        assert len(missing) == 1 and missing[0][1].startswith("60 in 1 gap") and missing[0][2] == "warn", got
    clean = detrended(recording())
    assert not [r for r in _derive_rows("detection.stage_encoding", clean) if r[0] == "Missing samples"]


# ===============================================================================================================
# the whole chain, through the executor
# ===============================================================================================================

@pytest.fixture
def scratch():
    tmp = tempfile.mkdtemp(prefix="drop_nan_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_drop_detection_v1_through_the_executor_skips_the_gap(scratch):
    from Working.database import queries as q
    from Working.database.schema import init_db
    from Working.execution import execute_recipe
    from Working.templates import apply_template
    from server.templates import canonical

    x = recording(GAP)
    npy = os.path.join(scratch, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(scratch, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic_gap.mat", 0, FS, len(x), 0, npy)
    conn.close()
    out = execute_recipe(apply_template(None, canonical("drop_detection_v1"), recording_id=1), db_path=db, force=True)
    onsets = [int(label.split(";")[0].split("=")[1]) for label in out["result"].value.labels]
    _, _, direct = chain(x)
    assert onsets == [e["onset_idx"] for e in direct.meta["events"]] and len(onsets) == 13


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

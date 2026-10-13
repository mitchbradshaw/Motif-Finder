"""
test_beads.py
==============
`Working.Preprocessing.beads` — baseline removal by BEADS (Ning, Selesnick &
Duval 2014): the trace is split into a slow baseline, a sparse layer of events
and noise, and the block passes on the trace with the baseline removed.

What is pinned here:

* the banded port reproduces a plain dense transcription of `beads.m`;
* the acceptance trace of the W1-A prompt — 48 h at 1 Hz, a 6-hour sinusoidal
  drift of 5 units, 20 drops (a 20 s fall, exponential recovery τ = 200 s,
  depth 1) and white noise σ = 0.05 — loses its drift (residual RMS < 0.1 of
  the drop depth away from the drops) and keeps every drop (≥ 85 % of its
  depth);
* on that trace a 600 s rolling-mean detrend leaves a larger overshoot beside
  the drops than BEADS — the reason the block exists;
* it is unit-free: ×1000 in, ×1000 out, nothing else changes;
* `polarity` matters: on drops, `drop` keeps them truer than `spike`, and
  only `drop` puts the drops (and little else) in the event layer;
* a 2.6 M-sample channel runs well inside the time and memory budget;
* NaNs, short spans and impossible periods are handled loudly.

Self-contained: synthetic signals only, no DATA/.
"""

import os
import sys
import time
import tracemalloc

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.Preprocessing.beads import beads, remove_baseline  # noqa: E402
from Working.Preprocessing.detrend import make_detrend_filter  # noqa: E402

N_HOURS = 48
N_DROPS = 20
DEPTH = 1.0
SIGMA = 0.05


def acceptance_trace(seed=0):
    """48 h at 1 Hz: 6 h sinusoidal drift (amplitude 5) + 20 drops + noise."""
    n = N_HOURS * 3600
    t = np.arange(n, dtype=float)
    drift = 5.0 * np.sin(2 * np.pi * t / (6 * 3600.0))
    events = np.zeros(n)
    onsets = (np.arange(N_DROPS) * (n // N_DROPS) + 4000).astype(int)
    for o in onsets:
        events[o:o + 20] += np.linspace(0.0, -DEPTH, 21)[1:]          # ~20 s fall
        k = np.arange(n - o - 20)
        events[o + 20:] += -DEPTH * np.exp(-k / 200.0)               # τ = 200 s recovery
    noise = np.random.default_rng(seed).normal(0.0, SIGMA, n)
    return drift + events + noise, drift, events, onsets


@pytest.fixture(scope="module")
def trace():
    y, drift, events, onsets = acceptance_trace()
    away = np.ones(len(y), bool)
    for o in onsets:
        away[max(0, o - 300):o + 1500] = False      # 1500 s ≈ fall + 7τ
    return {"y": y, "drift": drift, "events": events, "onsets": onsets, "away": away}


@pytest.fixture(scope="module")
def drop_run(trace):
    return remove_baseline(trace["y"], 1.0, polarity="drop")


def drop_depths(out, onsets):
    """Depth of each drop in `out`: the level just before it minus its lowest point."""
    return np.array([np.median(out[o - 300:o - 20]) - out[o:o + 300].min() for o in onsets])


def event_distortion(out, events, onsets, away):
    """How far the corrected trace strays from the true events, near the drops:
    per drop, the largest excursion of the (61 s-smoothed) difference from its
    own level just before the drop; and the RMS of that difference over every
    drop window."""
    sm = np.convolve(out - events, np.ones(61) / 61, mode="same")
    per_drop = np.array([np.max(np.abs(sm[o - 600:o + 1500] - np.median(sm[o - 1200:o - 600])))
                         for o in onsets])
    window = ~away
    rms = float(np.sqrt(np.mean((sm[window] - np.mean(sm[window])) ** 2)))
    return per_drop, rms


# ── the port ────────────────────────────────────────────────────────────────

def _dense_beads(y, d, fc, r, lam0, lam1, lam2, n_iter, eps0=1e-6, eps1=1e-6):
    """`beads.m` transcribed with dense matrices — the reference the banded
    port must reproduce."""
    n = len(y)
    b1 = np.array([1.0, -1.0])
    for _ in range(d - 1):
        b1 = np.convolve(b1, [-1.0, 2.0, -1.0])
    b = np.convolve(b1, [-1.0, 1.0])
    omc = 2 * np.pi * fc
    t = ((1 - np.cos(omc)) / (1 + np.cos(omc))) ** d
    a = np.array([1.0])
    for _ in range(d):
        a = np.convolve(a, [1.0, 2.0, 1.0])
    a = b + t * a

    def band(c):
        M = np.zeros((n, n))
        for j, v in enumerate(c):
            M += v * np.eye(n, k=j - d)
        return M

    A, B = band(a), band(b)
    D1 = (np.eye(n, k=1) - np.eye(n))[:n - 1]
    D2 = (np.eye(n) - 2 * np.eye(n, k=1) + np.eye(n, k=2))[:n - 2]
    D = np.vstack([D1, D2])
    BTB = B.T @ B
    w = np.r_[lam1 * np.ones(n - 1), lam2 * np.ones(n - 2)]
    bv = (1 - r) / 2 * np.ones(n)
    rhs = BTB @ np.linalg.solve(A, y) - lam0 * A.T @ bv
    x = y.copy()
    for _ in range(n_iter):
        Lam = np.diag(w / np.sqrt((D @ x) ** 2 + eps1))
        ax = np.abs(x)
        gamma = np.where(ax > eps0, (1 + r) / 4 / np.maximum(ax, eps0), (1 + r) / 4 / eps0)
        M = 2 * lam0 * np.diag(gamma) + D.T @ Lam @ D
        x = A @ np.linalg.solve(BTB + A.T @ M @ A, rhs)
    f = y - x - B @ np.linalg.solve(A, y - x)
    return x, f


@pytest.mark.parametrize("d", [1, 2])
def test_the_banded_port_reproduces_a_dense_transcription_of_beads_m(d):
    rng = np.random.default_rng(3)
    n = 240
    y = np.cumsum(rng.normal(0, 0.05, n)) + 4.0 * (rng.random(n) < 0.03)
    y -= np.linspace(y[0], y[-1], n)
    kw = dict(fc=0.03, r=6.0, lam0=0.5, lam1=5.0, lam2=4.0)
    x_ref, f_ref = _dense_beads(y, d, n_iter=6, **kw)
    x, f, info = beads(y, d=d, max_iter=6, tol=0.0, **kw)
    assert info["iterations"] == 6
    scale = np.max(np.abs(y))
    assert np.max(np.abs(x - x_ref)) < 1e-6 * scale
    assert np.max(np.abs(f - f_ref)) < 1e-6 * scale


def test_beads_reports_its_cost_and_whether_it_converged():
    rng = np.random.default_rng(4)
    y = rng.normal(0, 1, 400)
    y[100:110] += 20.0
    x, f, info = beads(y, fc=0.02, d=2, r=6.0, lam0=1.5, lam1=15.0, lam2=12.0, max_iter=50, tol=1e-3)
    assert set(info) >= {"iterations", "converged", "cost"}
    assert len(info["cost"]) == info["iterations"]
    assert info["converged"] and info["iterations"] < 50
    assert np.all(np.diff(info["cost"]) <= 1e-9 * abs(info["cost"][0])), "MM never increases the cost"
    # the pulse is the event layer (shrunk, as an ℓ1 penalty shrinks); elsewhere x is ~0
    outside = np.r_[0:90, 120:400]
    assert x[100:110].mean() > 5.0
    assert np.abs(x[outside]).max() < 0.5 * x[100:110].mean()


# ── acceptance ──────────────────────────────────────────────────────────────

def test_the_drift_is_removed_away_from_the_drops(trace, drop_run):
    residual = drop_run["baseline"] - trace["drift"]          # estimated − true baseline
    rms = float(np.sqrt(np.mean(residual[trace["away"]] ** 2)))
    assert rms < 0.1 * DEPTH, f"residual drift RMS {rms:.3f} away from the drops"
    assert np.allclose(drop_run["corrected"], trace["y"] - drop_run["baseline"])


def test_every_drop_keeps_at_least_85_percent_of_its_depth(trace, drop_run):
    depths = drop_depths(drop_run["corrected"], trace["onsets"])
    assert depths.min() >= 0.85 * DEPTH, f"shallowest drop kept {depths.min():.3f} of {DEPTH}"


def test_a_rolling_mean_leaves_a_bigger_overshoot_beside_the_drops_than_beads(trace, drop_run):
    rolling = make_detrend_filter(1.0, mode="rolling_mean", window_s=600.0)(trace["y"])
    over_rm, _ = event_distortion(rolling, trace["events"], trace["onsets"], trace["away"])
    over_bd, _ = event_distortion(drop_run["corrected"], trace["events"], trace["onsets"], trace["away"])
    # measured 2026-10-13: rolling mean ≈ 0.34 at every drop, BEADS ≈ 0.06
    assert np.median(over_rm) > 0.25 * DEPTH
    assert over_bd.max() < 0.5 * np.median(over_rm)
    assert np.median(over_bd) < 0.25 * np.median(over_rm)


def test_meta_reports_the_solve(drop_run):
    m = drop_run["meta"]
    for key in ("fc_cycles_per_sample", "r", "lam0", "lam1", "lam2", "iterations", "converged",
                "sigma", "baseline_min", "baseline_max", "event_fraction_3sigma", "grid_factor", "n_nan"):
        assert key in m, key
    assert m["fc_cycles_per_sample"] == pytest.approx(1 / 7200.0)
    assert m["r"] == 6.0 and m["polarity"] == "drop"
    assert m["lam1"] / m["lam0"] == pytest.approx(10.0) and m["lam2"] / m["lam0"] == pytest.approx(8.0)
    assert m["converged"] and m["iterations"] <= 30
    assert m["sigma"] == pytest.approx(SIGMA, rel=0.1), "robust σ is the noise, not the drift or the drops"
    assert -5.5 < m["baseline_min"] < -4.5 and 4.5 < m["baseline_max"] < 5.5
    # the drops occupy ~12 % of the trace; the event layer holds their deep
    # part and nothing else (measured 2026-10-13 after review F1: 0.052)
    assert 0.02 < m["event_fraction_3sigma"] < 0.2
    assert m["n_nan"] == 0
    assert m["warnings"] == [] and m["longest_gap_s"] == 0.0


def test_the_span_ends_carry_no_edge_artefact(trace, drop_run):
    """The drift is steepest exactly at the span's ends (sin at 0 and 16π):
    the padding and the linear continuation of the grid keep the edges true."""
    residual = drop_run["baseline"] - trace["drift"]
    # measured 2026-10-13: 0.047 and 0.051
    assert np.abs(residual[:600]).max() < 0.1 * DEPTH
    assert np.abs(residual[-600:]).max() < 0.1 * DEPTH


# ── drift far larger than the noise (review F1) ─────────────────────────────

def _sine_drift(sigma, period_h, amplitude, hours=48, seed=0):
    n = hours * 3600
    t = np.arange(n, dtype=float)
    drift = amplitude * np.sin(2 * np.pi * t / (period_h * 3600.0))
    return drift + np.random.default_rng(seed).normal(0.0, sigma, n), drift


@pytest.mark.parametrize("sigma, period_h, amplitude, rms_limit", [
    # drift at 2× the 2 h period: the order-2 filter itself lets ~6 % of it
    # through (|H|² = 1/17 at fc/2), so 6 % RMS is the floor any λ can reach
    (0.05, 4, 20.0, 0.06),
    (0.01, 4, 5.0, 0.06),
    (0.002, 4, 20.0, 0.06),        # A/σ = 10 000
    (0.002, 6, 20.0, 0.015),
    # 1.5× the period: the filter's own leak is ~12 %
    (0.05, 3, 5.0, 0.15),
])
def test_a_drift_huge_against_the_noise_stays_in_the_baseline(sigma, period_h, amplitude, rms_limit):
    """Pure drift + white noise, no events. Before the review the λ were in
    units of a grid noise level σ/√q so small that the fidelity term won and
    the whole drift went into the event layer (measured: 56–97 % baseline error,
    event fraction 0.99, converged=True)."""
    y, drift = _sine_drift(sigma, period_h, amplitude)
    out = remove_baseline(y, 1.0)
    err = out["baseline"] - drift
    rms = float(np.sqrt(np.mean(err ** 2)))
    assert rms < rms_limit * amplitude, f"baseline RMS error {rms / amplitude:.1%} of the drift"
    assert out["meta"]["event_fraction_3sigma"] < 0.3
    assert out["meta"]["warnings"] == []


def _ar(phi, sigma, n, seed):
    from scipy.signal import lfilter
    return lfilter([1.0], [1.0, -phi], np.random.default_rng(seed).normal(0.0, sigma, n))


def test_ar_noise_with_drift_and_troughs_is_no_worse_than_a_rolling_mean():
    """AR(0.95) noise reads as 0.22× its true level to a first-difference MAD;
    measured on the grid the scale is the real one."""
    n = N_HOURS * 3600
    t = np.arange(n, dtype=float)
    noise = _ar(0.95, SIGMA, n, seed=7)
    drift = 5.0 * np.sin(2 * np.pi * t / (6 * 3600.0))
    _, _, events, onsets = acceptance_trace()
    y = drift + events + noise
    away = np.ones(n, bool)
    for o in onsets:
        away[max(0, o - 300):o + 1500] = False
    bd = remove_baseline(y, 1.0)
    rm = make_detrend_filter(1.0, mode="rolling_mean", window_s=600.0)(y)

    def err(c):
        e = c - events - noise
        return float(np.sqrt(np.mean((e - np.median(e)) ** 2)))

    # measured 2026-10-13: BEADS 0.047, rolling mean 0.081
    assert err(bd["corrected"]) <= err(rm)
    over_rm, _ = event_distortion(rm, events + noise, onsets, away)
    over_bd, _ = event_distortion(bd["corrected"], events + noise, onsets, away)
    assert np.median(over_bd) <= np.median(over_rm)
    assert bd["meta"]["event_fraction_3sigma"] < 0.3, "the noise is not events"


def test_a_random_walk_without_events_is_not_all_events():
    y = np.cumsum(np.random.default_rng(11).normal(0.0, SIGMA, N_HOURS * 3600))
    out = remove_baseline(y, 1.0)
    # before the review: 0.98
    assert out["meta"]["event_fraction_3sigma"] < 0.3
    assert out["meta"]["converged"]


def test_an_event_layer_covering_most_of_the_span_is_a_loud_warning():
    """If x holds most of the span on a drop/spike run, it is drift, not events.
    The defaults no longer get there; a sparsity far below 1 still does
    (measured 2026-10-13: 0.91 at sparsity 0.01 on a 6 h drift)."""
    y, _ = _sine_drift(0.05, 6, 5.0, hours=24)
    out = remove_baseline(y, 1.0, sparsity=0.01)
    m = out["meta"]
    assert m["event_fraction_3sigma"] > 0.8, m["event_fraction_3sigma"]
    assert any("event" in w and "drift" in w for w in m["warnings"]), m["warnings"]


def test_the_acceptance_run_carries_no_warnings(drop_run):
    assert drop_run["meta"]["warnings"] == []


# ── units and polarity ──────────────────────────────────────────────────────

def test_multiplying_the_input_by_1000_multiplies_the_output_by_1000_and_nothing_else():
    y, *_ = acceptance_trace(seed=1)
    y = y[:12 * 3600]
    a = remove_baseline(y, 1.0)
    # a power of two scales every float exactly: the result is bit-identical,
    # so no constant anywhere in the solve carries a unit
    exact = remove_baseline(1024.0 * y, 1.0)
    assert np.array_equal(exact["corrected"], 1024.0 * a["corrected"])
    # ×1000 rounds differently at 1e-16, and the stopping iterate of the
    # (tolerance-stopped) MM solve carries that through at ~1e-4 of the noise
    # level's... measured 2026-10-13: 4.5e-4 units against σ = 0.05, so < 2 % σ
    b = remove_baseline(1000.0 * y, 1.0)
    sigma = a["meta"]["sigma"]
    assert np.max(np.abs(b["corrected"] / 1000.0 - a["corrected"])) < 0.02 * sigma
    assert np.max(np.abs(b["baseline"] / 1000.0 - a["baseline"])) < 0.02 * sigma
    assert b["meta"]["sigma"] == pytest.approx(1000.0 * sigma)
    for key in ("iterations", "converged", "event_fraction_3sigma", "lam0", "lam1", "lam2", "grid_factor"):
        assert b["meta"][key] == a["meta"][key], key


def test_polarity_drop_keeps_drops_truer_than_spike(trace, drop_run):
    spike_run = remove_baseline(trace["y"], 1.0, polarity="spike")
    _, rms_drop = event_distortion(drop_run["corrected"], trace["events"], trace["onsets"], trace["away"])
    _, rms_spike = event_distortion(spike_run["corrected"], trace["events"], trace["onsets"], trace["away"])
    # measured 2026-10-13: drop ≈ 0.0457, spike ≈ 0.0484 — these drops are
    # fast against the 2 h period, so the filter alone separates most of them
    assert rms_drop < rms_spike
    # only `drop` puts the drops in the event layer. (Before review F1 the
    # wrong polarity filled the layer with drift — spike 0.46 against drop
    # 0.12 — and this test pinned that as the polarity signal; with the scale
    # measured on the grid neither run takes drift: drop 0.052, spike 0.030.)
    assert drop_run["meta"]["event_fraction_3sigma"] > spike_run["meta"]["event_fraction_3sigma"]
    assert spike_run["meta"]["event_fraction_3sigma"] < 0.3
    assert spike_run["meta"]["r"] == 6.0
    both = remove_baseline(trace["y"][:24 * 3600], 1.0, polarity="both")
    assert both["meta"]["r"] == 1.0


def test_polarity_matters_most_for_slow_drops():
    """Drops recovering with τ = 1200 s: the filter can no longer separate them
    from drift on its own, and the polarity decides who gets them."""
    n = 48 * 3600
    t = np.arange(n, dtype=float)
    drift = 5.0 * np.sin(2 * np.pi * t / 21600.0)
    events = np.zeros(n)
    onsets = (np.arange(12) * (n // 12) + 4000).astype(int)
    for o in onsets:
        events[o:o + 20] += np.linspace(0.0, -DEPTH, 21)[1:]
        events[o + 20:] += -DEPTH * np.exp(-np.arange(n - o - 20) / 1200.0)
    y = drift + events + np.random.default_rng(0).normal(0.0, SIGMA, n)
    window = np.zeros(n, bool)
    for o in onsets:
        window[o - 300:o + 8400] = True

    def error(polarity):
        err = remove_baseline(y, 1.0, polarity=polarity)["corrected"] - events
        return float(np.sqrt(np.mean((err[window] - err[window].mean()) ** 2)))

    e_drop, e_spike, e_both = error("drop"), error("spike"), error("both")
    # measured 2026-10-13: drop 0.074, both 0.086, spike 0.154
    assert e_drop < 0.6 * e_spike
    assert e_drop < e_both < e_spike


# ── long spans ──────────────────────────────────────────────────────────────

def test_a_whole_channel_of_2_6_million_samples_is_fast_and_lean():
    n = 2_600_000
    rng = np.random.default_rng(5)
    t = np.arange(n, dtype=float)
    y = 5 * np.sin(2 * np.pi * t / 21600.0) + rng.normal(0, 0.05, n)
    for o in range(5000, n - 700, 9000):
        y[o:o + 600] -= np.exp(-np.arange(600) / 200.0)
    tracemalloc.start()
    t0 = time.perf_counter()
    out = remove_baseline(y, 1.0)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # measured 2026-10-13: 0.5 s and 108 MB of numpy allocations
    assert elapsed < 30.0, f"{elapsed:.1f} s"
    assert peak < 400e6, f"{peak / 1e6:.0f} MB"
    assert out["corrected"].shape == (n,) and np.isfinite(out["corrected"]).all()
    assert out["meta"]["converged"]


# ── honesty at the edges ────────────────────────────────────────────────────

def test_nan_samples_stay_nan_and_are_counted():
    y, *_ = acceptance_trace(seed=2)
    y = y[:6 * 3600].copy()
    y[1000:1100] = np.nan
    out = remove_baseline(y, 1.0)
    assert np.isnan(out["corrected"][1000:1100]).all()
    assert np.isnan(out["baseline"][1000:1100]).all()
    finite = np.ones(len(y), bool)
    finite[1000:1100] = False
    assert np.isfinite(out["corrected"][finite]).all()
    assert out["meta"]["n_nan"] == 100


def test_a_trailing_gap_does_not_bend_the_baseline_before_it(trace):
    """Review F3: a trailing hour of NaN used to be held flat at the last value,
    then solved as if it were data. Now NaN at either end is trimmed from the
    solve: the result is the result on the span without it."""
    n = 26 * 3600
    y = trace["y"][:n].copy()
    away = trace["away"][:n]
    y[24 * 3600:] = np.nan
    y[:600] = np.nan
    gapped = remove_baseline(y, 1.0)
    trimmed = remove_baseline(y[600:24 * 3600], 1.0)
    assert np.isnan(gapped["baseline"][24 * 3600:]).all() and np.isnan(gapped["baseline"][:600]).all()
    assert np.array_equal(gapped["baseline"][600:24 * 3600], trimmed["baseline"])
    err = gapped["baseline"] - trace["drift"][:n]
    keep = away & np.isfinite(err)
    # measured 2026-10-13: 0.075 (before: the 2 h held flat, 0.6 at the end)
    assert np.abs(err[keep]).max() < 0.1 * DEPTH
    assert gapped["meta"]["warnings"] == [], "an end gap is trimmed, not bridged"
    assert gapped["meta"]["trimmed_end_samples"] == 600 + 2 * 3600


def test_an_event_at_the_span_edge_is_named_in_the_warnings(trace):
    """The end padding point-reflects the trace about its last value; a drop in
    the last quarter period is reflected with it and bends the baseline there
    (measured 2026-10-13: a span cut 1040 s after a drop onset — max baseline
    error 0.63 of the depth, against 0.075 for a cut clear of the drops)."""
    out = remove_baseline(trace["y"][:23 * 3600], 1.0)
    assert any("edge" in w or "span's end" in w for w in out["meta"]["warnings"]), out["meta"]["warnings"]


def test_a_long_interior_gap_is_named_in_the_warnings():
    y, *_ = acceptance_trace(seed=2)
    y = y[:24 * 3600].copy()
    y[40000:41800] = np.nan                      # 30 min > period / 10 = 12 min
    m = remove_baseline(y, 1.0)["meta"]
    assert m["longest_gap_s"] == pytest.approx(1800.0)
    assert any("gap" in w for w in m["warnings"]), m["warnings"]
    y2, *_ = acceptance_trace(seed=2)
    y2 = y2[:24 * 3600].copy()
    y2[40000:40100] = np.nan                     # 100 s: harmless
    assert remove_baseline(y2, 1.0)["meta"]["warnings"] == []


def test_a_span_too_short_is_refused_with_a_reason():
    with pytest.raises(ValueError, match="at least 64 samples"):
        remove_baseline(np.zeros(30), 1.0)


def test_a_period_shorter_than_two_samples_is_refused():
    with pytest.raises(ValueError, match="baseline_period_s"):
        remove_baseline(np.random.default_rng(0).normal(size=500), 0.01, baseline_period_s=100.0)


def test_unknown_polarity_and_order_are_refused():
    y = np.random.default_rng(0).normal(size=500)
    with pytest.raises(ValueError, match="polarity"):
        remove_baseline(y, 1.0, polarity="up")
    with pytest.raises(ValueError, match="filter_order"):
        remove_baseline(y, 1.0, filter_order=3)


def test_a_span_shorter_than_the_period_still_runs_and_says_so():
    y, drift, *_ = acceptance_trace(seed=3)
    y = y[:1800]
    out = remove_baseline(y, 1.0)
    assert np.isfinite(out["corrected"]).all()
    assert out["meta"]["span_shorter_than_period"] is True


def test_a_flat_trace_gives_a_zero_output():
    for y in (np.full(1000, 3.0), np.linspace(-2.0, 7.0, 1000)):
        out = remove_baseline(y, 1.0)
        assert np.allclose(out["corrected"], 0.0, atol=1e-9), "a straight line is all baseline"
        assert out["meta"]["sigma_source"] == "flat_trace"
        assert out["meta"]["iterations"] == 0

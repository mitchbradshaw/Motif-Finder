"""
test_multiscale_entropy.py
==========================
w3-a: the core of `catalogue.multiscale_entropy` (`Working/Catalogue/multiscale_entropy.py`) —
multiscale entropy (Costa, Goldberger & Peng 2005) and its refined composite form (Wu et al. 2014,
as restated by Azami et al. 2017) per window of a WindowSet.

What is pinned, and why each could fail:
* the numba sorted-template counts equal a naive O(N^2) loop (several m, r, tau; ties; a template
  subset; RCMSE's pooled counts) — the speed trick must never change a count;
* Costa's two benchmark shapes (Fig. 1, N = 2 x 10^4, m = 2, r = 0.15 SD): white noise falls with
  scale, within 0.06 of its closed form -ln(2 Phi(0.15 sqrt(tau) / sqrt 2) - 1) at every scale;
  1/f noise stays flat (range < 0.25 nats over scales 1-20);
* RCMSE leaves fewer scales undefined than MSE on short series (Wu 2014's point);
* the same process at 1 Hz (block means of the 10 Hz one) and at 10 Hz gives the same curve at
  shared scales (within 0.03);
* the collapse guard on coloured backgrounds: SD on a drifting AR(1) window fires, MAD on the
  detrended window does not; a detrended random walk fires at the smallest scales only (named);
* structure against its own phase-randomised null (the manager's statistic, 20 draws, defaults,
  24 h): sharp drops with slow recovery on AR(1) lie outside the surrogates' spread; plain AR(1)
  and a further surrogate do not;
* undefined scales are NaN and counted by reason; gappy windows filled or left out by reason; flat
  windows left out; cancel raises the executor's `RecipeCancelled`; progress fires once per window;
* the columns, the complexity index's and slopes' rules, upstream pass-through, the 64-curve
  payload, the cost cap (templates spread across the window, estimate within tolerance).

Runnable standalone:  python -m pytest tests/test_multiscale_entropy.py -q
"""

import math
import os
import sys

import numpy as np
import pandas as pd
import pytest
from scipy.signal import lfilter
from scipy.stats import norm

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.Catalogue import multiscale_entropy as ME  # noqa: E402
from Working.Preprocessing.detrend import make_detrend_filter  # noqa: E402
from Working.library.grouping.methods.kshape import phase_randomised_rows  # noqa: E402
from Working.types import WindowSet  # noqa: E402

DAY = 24 * 3600


# ── synthetic signals ───────────────────────────────────────────────────────

def ar1(phi, n, seed):
    return lfilter([1.0], [1.0, -phi], np.random.default_rng(seed).standard_normal(n))


def pink(n, seed):
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n)
    F = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
    F[1:] /= np.sqrt(f[1:])
    F[0] = 0.0
    return np.fft.irfft(F, n=n)


def drops(n, amp, seed, rec_s=300.0, lo=1200, hi=3600):
    """Sharp falls with exponential recovery every 20-60 min (dense: the 'mostly events' case)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    t = 200
    while t < n:
        out[t:] -= amp * np.exp(-np.arange(n - t) / rec_s)
        t += int(rng.uniform(lo, hi))
    return out


def one_window(x, fs=1.0):
    return WindowSet(starts=np.array([0]), length=len(x), fs=fs, features=None)


def naive_counts(y, m, r, starts=None):
    starts = range(len(y) - m) if starts is None else list(starts)
    starts = list(starts)
    A = B = 0
    for a in range(len(starts)):
        for b in range(a + 1, len(starts)):
            i, j = starts[a], starts[b]
            if max(abs(y[i + k] - y[j + k]) for k in range(m)) <= r:
                B += 1
                if abs(y[i + m] - y[j + m]) <= r:
                    A += 1
    return A, B


def curve(x, fs=1.0, **kw):
    taus, _ = ME.scale_taus(fs, kw.pop("scale_min_s", ME.DEFAULT_SCALE_MIN_S),
                            kw.pop("scale_max_s", ME.DEFAULT_SCALE_MAX_S), kw.pop("n_scales", ME.DEFAULT_N_SCALES))
    c = ME.window_curve(x, fs, taus, **kw)
    return np.array([s["value"] for s in c["scales"]]), c


# ── exact counts ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("m", [1, 2, 3])
@pytest.mark.parametrize("r", [0.05, 0.2, 0.6])
def test_sorted_counts_equal_a_naive_loop(m, r):
    y = np.random.default_rng(10 * m).standard_normal(260)
    assert ME.sampen_counts(y, m, r) == naive_counts(y, m, r)


def test_counts_with_ties_and_a_template_subset_equal_naive():
    y = np.random.default_rng(3).integers(0, 4, 300).astype(float)       # many exact ties
    for r in (0.0, 1.0):
        assert ME.sampen_counts(y, 2, r) == naive_counts(y, 2, r)
    st = ME.template_starts(300, 2, max_points=100)
    assert len(st) <= 100
    assert ME.sampen_counts(y, 2, 1.0, st) == naive_counts(y, 2, 1.0, st)


@pytest.mark.parametrize("tau", [2, 3, 5])
def test_rcmse_pools_every_offset_like_a_naive_loop(tau):
    x = ar1(0.8, 900, seed=tau)
    m, r = 2, 0.15 * np.std(x)
    A = B = 0
    for k in range(tau):
        y = ME.coarse_grain(x, tau, k)
        assert np.allclose(y, [x[k + j * tau:k + (j + 1) * tau].mean() - np.median(x)
                               for j in range((len(x) - k) // tau)])
        a, b = naive_counts(y, m, r)
        A, B = A + a, B + b
    got = ME.entropy_at_scale(x, tau, m, r, method="rcmse", min_coarse_len=1, max_points=None)
    assert (got["A"], got["B"], got["n_offsets"]) == (A, B, tau)
    assert got["value"] == pytest.approx(-math.log(A / B))
    one = ME.entropy_at_scale(x, tau, m, r, method="mse", min_coarse_len=1, max_points=None)
    assert (one["A"], one["B"]) == naive_counts(ME.coarse_grain(x, tau, 0), m, r)


# ── Costa 2005's benchmarks ─────────────────────────────────────────────────

def test_white_noise_falls_with_scale_as_its_closed_form():
    x = np.random.default_rng(1).standard_normal(20_000)
    v, _ = curve(x, method="mse", r_scale="sd", scale_min_s=1, scale_max_s=20, n_scales=20)
    scales = np.arange(1, 21)
    closed = np.array([-math.log(2 * norm.cdf(0.15 * math.sqrt(s) / math.sqrt(2)) - 1) for s in scales])
    taus, _ = ME.scale_taus(1.0, 1, 20, 20)
    closed = closed[taus - 1]
    assert np.all(np.isfinite(v))
    assert np.max(np.abs(v - closed)) < 0.06
    assert v[0] - v[-1] > 1.2


def test_pink_noise_stays_flat():
    v_pink, _ = curve(pink(20_000, 2), method="mse", r_scale="sd", scale_min_s=1, scale_max_s=20, n_scales=20)
    v_white, _ = curve(np.random.default_rng(1).standard_normal(20_000), method="mse", r_scale="sd",
                       scale_min_s=1, scale_max_s=20, n_scales=20)
    assert np.all(np.isfinite(v_pink))
    assert v_pink.max() - v_pink.min() < 0.25
    assert v_pink[-1] > v_white[-1] + 0.5


def test_rcmse_leaves_fewer_scales_undefined_than_mse_on_short_series():
    undefined = {"mse": 0, "rcmse": 0}
    for s in range(10):
        y = np.random.default_rng(100 + s).standard_normal(150)
        for method in undefined:
            v, _ = curve(y, method=method, r_scale="sd", scale_min_s=1, scale_max_s=20, n_scales=20,
                         min_coarse_len=1)
            undefined[method] += int(np.isnan(v).sum())
    assert undefined["mse"] >= 20
    assert undefined["rcmse"] < undefined["mse"] / 4


@pytest.mark.parametrize("method", ["mse", "rcmse"])
def test_the_same_process_at_1_hz_and_10_hz_gives_the_same_curve(method):
    x10 = lfilter([1.0], [1.0, -np.exp(-0.1 / 30.0)], np.random.default_rng(3).standard_normal(400_000))
    x1 = x10.reshape(-1, 10).mean(axis=1)                                 # a 1 Hz logger's block means
    v1, _ = curve(x1, 1.0, method=method, scale_min_s=2, scale_max_s=32, n_scales=5)
    v10, _ = curve(x10, 10.0, method=method, scale_min_s=2, scale_max_s=32, n_scales=5)
    assert np.all(np.isfinite(v1)) and np.all(np.isfinite(v10))
    assert np.max(np.abs(v1 - v10)) < 0.03


# ── the collapse guard on coloured backgrounds ──────────────────────────────
#
# Fix round 1 (critic F2/Q2, manager decision 9): the guard judges INFLATION — the r rule's own spread
# of the window as it arrives over the same spread after a 2 h rolling mean is taken out — and flags
# EVERY scale of an inflated window. Several seeds per case: a single seed encoded a coin toss.

DETREND = make_detrend_filter(1.0, "rolling_mean", 7200.0)
SEEDS = (1, 2, 3)


def _guard_run(x, r_scale="mad"):
    return ME.multiscale_entropy(one_window(x), x, np.arange(len(x), dtype=float), 1.0, r_scale=r_scale)


def _sqrt_t_case(kind, seed, n=DAY):
    if kind == "raw random walk":
        return np.cumsum(np.random.default_rng(seed).standard_normal(n))
    bg = ar1(0.97, n, seed=seed)
    tt = np.arange(n) / n
    return bg + 30 * np.std(bg) * (0.6 * tt + 0.4 * np.sin(2 * np.pi * tt / 0.8))   # a smooth drift


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("kind", ["raw random walk", "raw AR(1) 0.97 + smooth drift"])
def test_the_sqrt_t_cases_flag_every_collapsed_scale(kind, seed):
    out = _guard_run(_sqrt_t_case(kind, seed), r_scale="sd")
    meta = out.meta
    defined = np.array(meta["defined_per_scale"]) > 0
    assert defined.sum() >= 6
    assert (np.array(meta["collapse"])[defined] == 1).all(), meta["collapse"]
    assert meta["inflation_max"] > ME.DEFAULT_INFLATION_LIMIT
    F = out.windows.features
    assert F["mse_n_collapsed"].iloc[0] == defined.sum()
    assert F["mse_inflation"].iloc[0] > ME.DEFAULT_INFLATION_LIMIT
    w = [s for s in meta["warnings"] if "collapse" in s]
    assert w and "r_scale" not in w[0]                      # MAD does not help (0.043 against 0.044)
    assert "collapse" in meta["summary"]


def _not_collapsed_case(kind, seed, n=DAY):
    if kind == "detrended random walk":
        return DETREND(np.cumsum(np.random.default_rng(seed).standard_normal(n)))
    if kind == "AR(1) 0.95":
        return ar1(0.95, n, seed=seed)
    if kind == "AR(1) 0.99":
        return ar1(0.99, n, seed=seed)
    return pink(n, seed)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("kind", ["detrended random walk", "AR(1) 0.95", "AR(1) 0.99", "raw pink"])
def test_stationary_and_template_detrended_backgrounds_do_not_flag(kind, seed):
    out = _guard_run(_not_collapsed_case(kind, seed))
    assert sum(out.meta["collapse"]) == 0, (out.meta["inflation_max"], out.meta["collapse"])
    assert not any("collapse" in w for w in out.meta["warnings"])
    assert out.windows.features["mse_inflation"].iloc[0] <= ME.DEFAULT_INFLATION_LIMIT


def test_rho_stays_in_meta_as_information_not_a_warning():
    x = DETREND(np.cumsum(np.random.default_rng(5).standard_normal(DAY)))
    out = _guard_run(x)
    assert out.meta["rho_median"][0] > 3                 # smooth at 1 s: the step is small against r
    assert sum(out.meta["collapse"]) == 0
    assert any(r["name"] == "smooth" for r in out.meta["rules"])


def test_the_drift_share_still_says_why():
    n = DAY
    bg = ar1(0.95, n, seed=4)
    x = bg + 50 * np.std(bg) * np.arange(n) / n
    raw = _guard_run(x, r_scale="sd")
    det = _guard_run(DETREND(x))
    assert raw.windows.features["mse_drift_share"].iloc[0] > 0.9
    assert det.windows.features["mse_drift_share"].iloc[0] < 0.05


def test_unit_bearing_and_guard_columns_are_bookkeeping():
    from Working.types.windowset import BOOKKEEPING_COLUMNS
    for c in ("mse_r", "mse_drift_share", "mse_inflation", "mse_n_scales", "mse_n_collapsed"):
        assert c in BOOKKEEPING_COLUMNS, c


# ── structure against its own phase-randomised null ─────────────────────────

def _distance_test(real, surrogates):
    ok = np.isfinite(real) & np.isfinite(surrogates).all(axis=0)
    S = surrogates[:, ok]
    d_real = float(np.linalg.norm(real[ok] - S.mean(axis=0)))
    d_s = np.array([np.linalg.norm(S[i] - np.delete(S, i, axis=0).mean(axis=0)) for i in range(len(S))])
    return (1 + int((d_s >= d_real).sum())) / (len(S) + 1), d_real, d_s, int(ok.sum())


def _surrogate_curves(x, n_draws=20, seed=11):
    rows = phase_randomised_rows(np.repeat(x[None, :], n_draws, axis=0), np.random.default_rng(seed))
    return np.array([curve(row)[0] for row in rows])


@pytest.fixture(scope="module")
def ar_bg():
    return ar1(0.97, DAY, seed=7)


def test_drops_with_slow_recovery_lie_outside_their_own_surrogates(ar_bg):
    x = ar_bg + drops(DAY, 5 * np.std(ar_bg), seed=8)
    real, _ = curve(x)
    S = _surrogate_curves(x)
    p, d_real, d_s, n_common = _distance_test(real, S)
    assert n_common >= 6
    assert p == pytest.approx(1 / 21), (d_real, d_s.max())
    # a further phase-randomised copy agrees with the 20 within their own spread
    extra = _surrogate_curves(x, n_draws=1, seed=99)[0]
    ok = np.isfinite(extra) & np.isfinite(S).all(axis=0)
    assert np.linalg.norm(extra[ok] - S[:, ok].mean(axis=0)) <= d_s.max()
    # and the run is deterministic: the same curve twice
    again, _ = curve(x)
    assert np.array_equal(np.nan_to_num(again, nan=-1), np.nan_to_num(real, nan=-1))


def test_plain_ar1_is_not_separated_from_its_surrogates(ar_bg):
    real, _ = curve(ar_bg)
    p, _, _, _ = _distance_test(real, _surrogate_curves(ar_bg))
    assert p > 0.1


# ── undefined, gaps, flat, refusals ─────────────────────────────────────────

def test_too_short_scales_are_nan_and_counted():
    n = 2 * 3600
    x = ar1(0.9, n, seed=1)
    ws = WindowSet(starts=np.array([0, 3600]), length=3600, fs=1.0, features=None)
    out = ME.multiscale_entropy(ws, x, np.arange(n, dtype=float), 1.0)
    taus = np.array(out.meta["taus"])
    short = 3600 // taus < ME.DEFAULT_MIN_COARSE_LEN
    assert short.any() and not short.all()
    cols = out.meta["columns"]
    F = out.windows.features
    for j, c in enumerate(cols):
        assert F[c].isna().all() == bool(short[j])
    assert out.meta["undefined_per_scale"]["too_short"] == [2 * int(s) for s in short]
    assert out.meta["blank_scales_s"] == [float(s) for s, b in zip(out.meta["scales_s"], short) if b]
    assert any("blank" in w for w in out.meta["warnings"])


def test_no_match_is_its_own_reason():
    y = np.random.default_rng(0).standard_normal(60)
    got = ME.entropy_at_scale(y, 1, 2, 1e-9, min_coarse_len=1)
    assert np.isnan(got["value"]) and got["reason"] == "no_m_match"
    y2 = np.repeat(np.random.default_rng(1).standard_normal(30), 2)      # pairs repeat, the next rarely does
    got2 = ME.entropy_at_scale(y2, 1, 1, 1e-9, method="mse", min_coarse_len=1)
    assert got2["B"] > 0 and got2["A"] == 0 and got2["reason"] == "no_m1_match" and np.isnan(got2["value"])


def test_gappy_and_flat_windows():
    L = 3600
    x = ar1(0.9, 4 * L, seed=2)
    x[L + 100:L + 110] = np.nan                    # 10 s: bridged
    x[2 * L + 500:2 * L + 600] = np.nan            # 100 s: left out
    x[3 * L:4 * L] = 1.0                           # flat
    ws = WindowSet(starts=np.arange(4) * L, length=L, fs=1.0, features=pd.DataFrame({"split": [0, 0, 0, 2]}))
    out = ME.multiscale_entropy(ws, x, np.arange(4 * L, dtype=float), 1.0, scale_max_s=3)
    F = out.windows.features
    assert len(F) == 4 and list(F["split"]) == [0, 0, 0, 2]
    assert np.isfinite(F["mse_1s"].iloc[[0, 1]]).all()
    assert F.iloc[2].drop("split").isna().all() and F.iloc[3].drop("split").isna().all()
    assert out.meta["left_out"] == {"gap_over_max": 1, "flat": 1}
    assert out.meta["n_interpolated"] == 1 and out.meta["n_kept"] == 2
    assert any("left out" in w and "gap over max" in w for w in out.meta["warnings"])


def test_a_window_more_than_5pct_filled_is_left_out_and_fills_reach_the_face():
    L = 3000
    x = ar1(0.9, 3 * L, seed=3)
    x[np.arange(0, L, 10)] = np.nan                     # window 0: 10 % filled, every gap 1 sample
    x[L + np.arange(0, L, 50)] = np.nan                 # window 1: 2 % filled: kept, counted
    ws = WindowSet(starts=np.arange(3) * L, length=L, fs=1.0)
    out = ME.multiscale_entropy(ws, x, np.arange(3 * L, dtype=float), 1.0, scale_max_s=2)
    F = out.windows.features
    assert F["mse_1s"].isna().tolist() == [True, False, False]
    assert out.meta["left_out"] == {"filled_over_5pct": 1}
    assert out.meta["n_interpolated"] == 1
    assert any("filled" in w and "1 of 3" in w for w in out.meta["warnings"]), out.meta["warnings"]
    assert "filled" in out.meta["summary"]
    assert any("5 %" in r["rule"] and "placeholder" in r["rule"] for r in out.meta["rules"] if r["name"] == "gaps")


def test_mad_zero_is_its_own_reason():
    L = 3000
    x = np.zeros(2 * L)
    x[:L] = ar1(0.9, L, seed=1)
    x[L + np.arange(0, L, 300)] = 5.0                   # mostly constant with rare steps: MAD 0, SD > 0
    ws = WindowSet(starts=np.arange(2) * L, length=L, fs=1.0)
    out = ME.multiscale_entropy(ws, x, np.arange(2 * L, dtype=float), 1.0, scale_max_s=2)
    assert out.meta["left_out"] == {"mad_zero": 1}
    assert any("MAD = 0" in w for w in out.meta["warnings"]), out.meta["warnings"]


def test_the_scales_where_rcmse_is_mse_are_named():
    x = ar1(0.95, DAY, seed=2)
    out = ME.multiscale_entropy(one_window(x), x, np.arange(DAY, dtype=float), 1.0)
    one = [s for s, k in zip(out.meta["scales_s"], out.meta["n_offsets"]) if k == 1]
    assert one and out.meta["rcmse_equals_mse_scales_s"] == one
    rule = next(r for r in out.meta["rules"] if r["name"] == "rcmse = mse")
    assert f"{one[-1]:g} s" in rule["rule"]
    assert "= MSE" in out.meta["summary"]


def test_window_lengths_are_printed_readably():
    assert ME.readable_seconds(600) == "10 min"
    assert ME.readable_seconds(20_000) == "5.6 h"
    assert ME.readable_seconds(45) == "45 s"
    assert ME.readable_seconds(72 * 3600) == "72 h"
    L = 600
    x = ar1(0.9, 2 * L, seed=1)
    ws = WindowSet(starts=np.arange(2) * L, length=L, fs=1.0)
    out = ME.multiscale_entropy(ws, x, np.arange(2 * L, dtype=float), 1.0, scale_max_s=4, min_coarse_len=300)
    w = [s for s in out.meta["warnings"] if "blank" in s]
    assert w and "10 min window" in w[0], w


def test_refusals_are_in_words():
    x = np.zeros(100)
    with pytest.raises(ValueError, match="Sliding windows"):
        ME.multiscale_entropy(None, x, np.arange(100.0), 1.0)
    pool = WindowSet(starts=np.array([0]), length=50, fs=1.0, features=pd.DataFrame({"pool_member": [1]}))
    with pytest.raises(ValueError, match="pool"):
        ME.multiscale_entropy(pool, x, np.arange(100.0), 1.0)
    outside = WindowSet(starts=np.array([80]), length=50, fs=1.0)
    with pytest.raises(ValueError, match="outside this span.*Multiscale entropy"):
        ME.multiscale_entropy(outside, x, np.arange(100.0), 1.0)


def test_minirocket_still_refuses_windows_outside_its_span_in_its_own_name():
    from Working.Catalogue.minirocket import _slice_x
    with pytest.raises(ValueError, match="run MiniRocket on the span"):
        _slice_x(WindowSet(starts=np.array([80]), length=50, fs=1.0), np.zeros(100), np.arange(100.0), 1.0)


# ── cancel and progress ─────────────────────────────────────────────────────

def test_cancel_between_windows_raises_the_executors_cancellation_and_progress_fires_per_window():
    from Working.execution import RecipeCancelled
    L = 1200
    x = ar1(0.9, 5 * L, seed=4)
    ws = WindowSet(starts=np.arange(5) * L, length=L, fs=1.0)
    seen = []
    ME.multiscale_entropy(ws, x, np.arange(5 * L, dtype=float), 1.0, scale_max_s=1,
                          on_progress=lambda d, n, s: seen.append((d, n, s)))
    assert seen == [(i, 5, "multiscale_entropy") for i in range(1, 6)]
    calls = []

    def cancel():
        calls.append(1)
        return len(calls) > 2

    seen.clear()
    with pytest.raises(RecipeCancelled, match="2 of 5"):
        ME.multiscale_entropy(ws, x, np.arange(5 * L, dtype=float), 1.0, scale_max_s=1, should_cancel=cancel,
                              on_progress=lambda d, n, s: seen.append(d))
    assert seen == [1, 2]


# ── columns, summaries, payload ─────────────────────────────────────────────

def test_columns_index_and_slopes_follow_their_rules():
    L = 6000
    x = ar1(0.95, 3 * L, seed=6)
    ws = WindowSet(starts=np.arange(3) * L + 1000, length=L, fs=1.0,
                   features=pd.DataFrame({"split": [0, 0, 2], "catch22_x": [1.0, 2.0, 3.0], "mse_old": [9, 9, 9]}))
    t = np.arange(1000, 1000 + 3 * L, dtype=float)               # the span starts at channel sample 1000
    out = ME.multiscale_entropy(ws, x, t, 1.0, scale_min_s=1, scale_max_s=6, n_scales=11)  # rounds to 1..6 s
    F = out.windows.features
    names = out.meta["columns"]
    assert names == ["mse_1s", "mse_2s", "mse_3s", "mse_4s", "mse_5s", "mse_6s"]
    assert list(F["catch22_x"]) == [1.0, 2.0, 3.0] and "mse_old" not in F.columns
    assert any("replaced" in w for w in out.meta["warnings"])
    for c in ("mse_ci", "mse_slope_small", "mse_slope_large", "mse_r", "mse_n_scales", "mse_drift_share",
              "mse_n_collapsed"):
        assert c in F.columns
    E = F[names].to_numpy()
    assert out.meta["n_ci_scales"] == 6
    assert np.allclose(F["mse_ci"], E.sum(axis=1))
    s = np.array(out.meta["scales_s"])
    assert np.allclose(F["mse_slope_small"], [np.polyfit(np.log10(s[:3]), e[:3], 1)[0] for e in E])
    assert np.allclose(F["mse_slope_large"], [np.polyfit(np.log10(s[3:]), e[3:], 1)[0] for e in E])
    for i in range(3):
        w = x[i * L:(i + 1) * L]
        assert F["mse_r"].iloc[i] == pytest.approx(0.15 * 1.4826 * np.median(np.abs(w - np.median(w))))
    assert (F["mse_n_scales"] == 6).all()
    # the window slice is span-relative: window 0 is x[0:L]
    v0, _ = curve(x[:L], scale_min_s=1, scale_max_s=6, n_scales=11)
    assert np.allclose(E[0], v0)
    from Working.types.windowset import BOOKKEEPING_COLUMNS
    assert "mse_n_scales" in BOOKKEEPING_COLUMNS and "mse_n_collapsed" in BOOKKEEPING_COLUMNS


def test_index_over_scales_defined_in_every_window_only(monkeypatch):
    """The second window's 2 s scale is made undefined (as a no-match would): the index and the slopes
    then use only the scales defined in BOTH windows, for both windows."""
    real = ME.window_curve
    calls = []

    def second_window_loses_a_scale(*a, **k):
        c = real(*a, **k)
        calls.append(1)
        if len(calls) == 2:
            c["scales"][1].update(value=float("nan"), reason=ME.UNDEF_NO_M1)
        return c

    monkeypatch.setattr(ME, "window_curve", second_window_loses_a_scale)
    L = 4000
    x = ar1(0.9, 2 * L, seed=9)
    ws = WindowSet(starts=np.array([0, L]), length=L, fs=1.0)
    out = ME.multiscale_entropy(ws, x, np.arange(2 * L, dtype=float), 1.0, scale_min_s=1, scale_max_s=4,
                                n_scales=3, min_coarse_len=500)
    F = out.windows.features
    assert out.meta["ci_scales_s"] == [1.0, 4.0] and out.meta["n_ci_scales"] == 2
    assert out.meta["undefined_per_scale"]["no_m1_match"] == [0, 1, 0]
    assert out.meta["defined_per_scale"] == [2, 1, 2]
    assert np.isfinite(F["mse_2s"].iloc[0]) and np.isnan(F["mse_2s"].iloc[1])
    assert np.allclose(F["mse_ci"], F["mse_1s"] + F["mse_4s"])
    assert list(F["mse_n_scales"]) == [3, 2]


def test_curve_payload_is_capped_seeded_and_json_safe():
    import json
    L = 600
    x = ar1(0.9, 70 * L, seed=1)
    ws = WindowSet(starts=np.arange(70) * L, length=L, fs=1.0)
    kw = dict(scale_min_s=1, scale_max_s=2, n_scales=2, min_coarse_len=200)
    a = ME.multiscale_entropy(ws, x, np.arange(70 * L, dtype=float), 1.0, **kw).meta
    b = ME.multiscale_entropy(ws, x, np.arange(70 * L, dtype=float), 1.0, **kw).meta
    c = a["curves"]
    assert c["sampled"] and len(c["windows"]) == ME.MAX_CURVES and c["n_windows"] == 70
    assert [w["index"] for w in c["windows"]] == [w["index"] for w in b["curves"]["windows"]]
    assert len(c["median"]) == len(c["scales_s"]) == 2
    json.dumps(a, allow_nan=False)


def test_the_cost_cap_spreads_templates_and_keeps_the_estimate():
    st = ME.template_starts(100_000, 2, max_points=2_000)
    assert len(st) <= 2_000 and st.min() == 0 and st.max() == 100_000 - 3
    x = ar1(0.9, 60_000, seed=12)
    full, cf = curve(x, scale_min_s=1, scale_max_s=4, n_scales=3, max_points=None, min_coarse_len=100)
    capped, cc = curve(x, scale_min_s=1, scale_max_s=4, n_scales=3, max_points=5_000, min_coarse_len=100)
    assert max(s["n_templates"] for s in cc["scales"]) <= 5_000
    assert np.max(np.abs(full - capped)) < 0.05
    # RCMSE pools only as many offsets as the cap allows when the series are long
    assert ME.n_offsets_for(20, 3_000, 20_000) == 20 and ME.n_offsets_for(20, 20_000, 20_000) == 1
    assert ME.n_offsets_for(200, 4_000, 20_000) == 25


def test_scale_names_are_stable_seconds():
    taus, s = ME.scale_taus(10.0, 1, 1200, 12)
    assert len(set(taus)) == len(taus)
    assert [ME.scale_label(v) for v in s][:2] == ["mse_1s", "mse_1.9s"]
    with pytest.raises(ValueError):
        ME.scale_taus(1.0, 10, 5, 3)

"""
test_cwt_ridges.py
====================
`Working.Detection.cwt_ridges` — multi-scale peaks and troughs by CWT ridge
lines (Du, Kibbe & Lin 2006), the core under `detection.cwt_ridges`.

What is pinned (W1-C acceptance):

* the Ricker is the Mexican hat normalised by 1/a (the module's A0), and the
  duration rule (duration_s = 1.665 x best_scale_s, the FWHM of a Gaussian
  whose response peaks at that scale) is calibrated on isolated Gaussian bumps;
* a 1 Hz, 24 h trace with linear + quadratic drift (>= 10x the smallest event),
  noise, and events of ~24 s, ~8 min and ~43 min of both polarities plus a
  sharkfin-like asymmetric drop: every event found, polarity right, duration
  within a factor of 1.5 of the truth;
* the same drift and noise with no events: no event away from the span edges,
  and at most a measured rate of edge-flagged ones;
* on the day of events, every reported event that is not one of the injected
  ones is flagged (`edge_flag` or `step_pair`) — nothing extra goes unmarked;
* a fast event riding on a slow one gives two events at two scales;
* the hat's side lobes are never reported as events of the other polarity;
* chunked and unchunked processing give the same events;
* 2.6 M samples complete (chunked).

Every signal is synthetic; nothing reads DATA/.

Runnable standalone:  python tests/test_cwt_ridges.py
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

from Working.Detection import cwt_ridges as CR  # noqa: E402

FS = 1.0
DAY = 86400
FWHM_PER_SIGMA = 2.0 * np.sqrt(2.0 * np.log(2.0))


# ── synthetic recordings ────────────────────────────────────────────────────

def gauss(n, centre, fwhm, amp):
    t = np.arange(n)
    return amp * np.exp(-0.5 * ((t - centre) / (fwhm / FWHM_PER_SIGMA)) ** 2)


def sharkfin(n, fall_end, fall_s=30, floor_s=200, climb_s=300, amp=1.0):
    """A drop, a floor for about half the event, then a slow climb (the catalogue's sharkfin)."""
    t = np.arange(n, dtype=float)
    y = np.zeros(n)
    fall = (t >= fall_end - fall_s) & (t < fall_end)
    y[fall] = -amp * (t[fall] - (fall_end - fall_s)) / fall_s
    y[(t >= fall_end) & (t < fall_end + floor_s)] = -amp
    climb = (t >= fall_end + floor_s) & (t < fall_end + floor_s + climb_s)
    y[climb] = -amp * (1.0 - (t[climb] - fall_end - floor_s) / climb_s)
    return y


def fwhm_and_centre(y):
    idx = np.flatnonzero(np.abs(y) >= np.abs(y).max() / 2.0)
    return float(idx[-1] - idx[0] + 1), float(idx.mean())


# (centre s, FWHM s, polarity, amplitude): Adamatzky's three S. commune families, both polarities
EVENTS = [(2 * 3600, 24, +1, 1.0), (3 * 3600, 24, -1, 1.0), (5.5 * 3600, 480, +1, 1.0), (8.5 * 3600, 480, -1, 1.0),
          (12 * 3600, 2580, +1, 1.0), (17 * 3600, 2580, -1, 1.0), (21 * 3600, 24, +1, 1.0)]
NOISE_SD = 0.15


def drift(n=DAY):
    t = np.arange(n) / n
    return 7.0 * t + 9.0 * (t - 0.3) ** 2          # 10.6 peak to peak, monotonic, curved


def day_trace(seed=0, events=True):
    rng = np.random.default_rng(seed)
    x = drift() + NOISE_SD * rng.standard_normal(DAY)
    truth = []
    if events:
        for c, w, p, a in EVENTS:
            x += gauss(DAY, c, w, p * a)
            truth.append((c, float(w), p))
        y = sharkfin(DAY, 23 * 3600 - 2000)
        x += y
        w, c = fwhm_and_centre(y)
        truth.append((c, w, -1))
    return x, truth


def match(events, centre, width, polarity):
    near = [e for e in events if e["polarity"] == polarity and abs(e["peak_idx"] - centre) <= max(0.5 * width, 30)]
    return max(near, key=lambda e: e["snr"]) if near else None


# ── the wavelet and the duration rule ───────────────────────────────────────

def test_ricker_is_the_zero_mean_mexican_hat_normalised_by_one_over_a():
    for a in (10.0, 57.3, 400.0):
        w = CR.ricker(a)
        assert len(w) == 2 * int(np.ceil(5 * a)) + 1, "truncated to the paper's support [-5a, 5a]"
        assert abs(w.sum()) < 1e-12, "zero mean: a constant offset cancels exactly"
        assert a * np.sum(w ** 2) == pytest.approx(1.0, rel=0.02), "psi_a = a^-1 psi(t/a): energy 1/a"
        assert np.argmax(w) == len(w) // 2
        k = np.arange(len(w)) - len(w) // 2
        assert abs(np.sum(k * w)) < 1e-9, "zero first moment: a straight drift cancels"


def test_an_events_peak_coefficient_is_its_amplitude_whatever_its_width():
    """A0: under 1/a the SNR reads as height over noise, not height x sqrt(width)."""
    peaks = []
    for fwhm in (24.0, 480.0, 2580.0):
        n = int(max(30 * fwhm, 6000))
        r = CR.detect(gauss(n, n // 2, fwhm, 1.0) + 1e-3 * np.random.default_rng(0).standard_normal(n), FS,
                      max_scale_s=min(7200.0, n / 4.5))
        peaks.append(match(r.events, n // 2, fwhm, +1)["peak_coef"])
    assert max(peaks) / min(peaks) < 1.1, peaks


def test_the_duration_rule_is_calibrated_on_isolated_gaussian_bumps():
    """duration_s = 2 sqrt(ln 2) x best_scale_s recovers the FWHM of a Gaussian."""
    assert CR.FWHM_PER_SCALE == pytest.approx(1.6651, abs=1e-4)
    rng = np.random.default_rng(3)
    for fwhm in (24.0, 100.0, 480.0, 2580.0):
        n = int(max(30 * fwhm, 6000))
        x = gauss(n, n // 2, fwhm, 1.0) + 0.01 * rng.standard_normal(n)
        r = CR.detect(x, FS, max_scale_s=min(7200.0, n / 4.5))
        e = match(r.events, n // 2, fwhm, +1)
        assert e is not None, f"FWHM {fwhm} s: not found"
        assert e["duration_s"] == pytest.approx(fwhm, rel=0.10), (fwhm, e["duration_s"], e["best_scale_s"])
        assert e["start"] < n // 2 < e["end"]
        assert e["end"] - e["start"] == pytest.approx(2 * fwhm, rel=0.12), "span = peak +/- duration_s"


# ── acceptance 1: three widths, both polarities, a sharkfin, on drift ───────

@pytest.mark.parametrize("seed", [0, 1, 2])
def test_every_event_of_three_widths_and_both_polarities_is_found_on_a_drifting_day(seed):
    x, truth = day_trace(seed)
    assert np.ptp(drift()) >= 10 * min(a for *_, a in EVENTS), "the drift must dwarf the smallest event"
    r = CR.detect(x, FS)
    for centre, width, polarity in truth:
        e = match(r.events, centre, width, polarity)
        assert e is not None, f"seed {seed}: missed the {width:g} s {'spike' if polarity > 0 else 'drop'} at {centre:g} s"
        assert e["ridge_polarity"] == ("spike" if polarity > 0 else "drop")
        ratio = e["duration_s"] / width
        assert 1 / 1.5 <= ratio <= 1.5, f"seed {seed}: {width:g} s event read as {e['duration_s']:.0f} s"
        assert e["snr"] >= 3.0 and e["ridge_scales"] >= 6
        assert not e["edge_flag"]


@pytest.mark.parametrize("seed", [0, 1])
def test_every_extra_event_on_the_day_is_flagged(seed):
    """Beyond the eight injected events, the block may report an edge ridge (`edge_flag`)
    or the corner of the sharkfin's abrupt fall (`step_pair`, the module's A14) — never
    an unmarked extra. Measured over 20 seeds: exactly one extra a day, the sharkfin's
    corner."""
    x, truth = day_trace(seed)
    r = CR.detect(x, FS)
    real = {id(match(r.events, c, w, p)) for c, w, p in truth}
    extra = [e for e in r.events if id(e) not in real]
    assert all(e["edge_flag"] or e["step_pair"] for e in extra), [
        (e["peak_idx"], e["ridge_polarity"], e["best_scale_s"]) for e in extra]


def test_the_three_families_land_at_three_separated_scales():
    x, truth = day_trace(0)
    r = CR.detect(x, FS)
    scale = {w: match(r.events, c, w, p)["best_scale_s"] for c, w, p in truth[:-1]}
    # a* = FWHM / 1.665: about 14 s, 290 s and 1550 s
    assert scale[24.0] < 25 < 150 < scale[480.0] < 450 < 900 < scale[2580.0] < 2400


# ── acceptance 2: no events, the same drift and noise ───────────────────────

def test_drift_and_noise_alone_give_no_event_away_from_the_edges_and_few_at_them():
    """Measured over 20 seeds at the defaults: 0 unflagged events; 0-1 edge-flagged ones
    a day (mean 0.15) — large-scale ridges where the trace was extended past its ends.
    Pinned over 10 seeds: none unflagged, at most 0.5 flagged a day on average."""
    flagged = []
    for seed in range(10):
        x, _ = day_trace(seed, events=False)
        r = CR.detect(x, FS)
        assert all(e["edge_flag"] for e in r.events), (
            f"seed {seed}: an event away from the span edges on drift + noise alone: "
            f"{[(e['peak_idx'], e['best_scale_s']) for e in r.events if not e['edge_flag']]}")
        flagged.append(len(r.events))
    assert np.mean(flagged) <= 0.5, flagged


def test_a_flat_trace_and_a_straight_ramp_give_nothing():
    assert CR.detect(np.zeros(20000), FS).events == []
    ramp = np.linspace(-3.0, 5.0, 20000) + 2.0
    assert [e for e in CR.detect(ramp, FS).events if not e["edge_flag"]] == [], \
        "the hat's zero mean and zero first moment cancel a straight drift"


# ── acceptance 3: nested events ─────────────────────────────────────────────

@pytest.mark.parametrize("slow_fwhm, slow_amp, offset",
                         [(2580, 3.0, 0), (2580, 3.0, 300), (480, 2.0, 0), (480, 2.0, 120), (480, 2.0, 300)])
def test_a_fast_event_riding_on_a_slow_one_gives_two_events_at_two_scales(slow_fwhm, slow_amp, offset):
    n = 6 * 3600
    rng = np.random.default_rng(0)
    x = 0.15 * rng.standard_normal(n) + gauss(n, n // 2, slow_fwhm, slow_amp) + gauss(n, n // 2 + offset, 24, 1.0)
    r = CR.detect(x, FS)
    fast = match([e for e in r.events if e["best_scale_s"] < 100], n // 2 + offset, 24, +1)
    slow = match([e for e in r.events if e["best_scale_s"] > 100], n // 2, slow_fwhm, +1)
    assert fast is not None and slow is not None, [(e["peak_idx"], e["best_scale_s"]) for e in r.events]
    assert fast is not slow
    assert 1 / 1.5 <= fast["duration_s"] / 24 <= 1.5
    assert 1 / 1.5 <= slow["duration_s"] / slow_fwhm <= 1.5
    assert slow["best_scale_s"] > 10 * fast["best_scale_s"]


# ── side lobes, polarity, NaN, scale range ──────────────────────────────────

@pytest.mark.parametrize("fwhm", [24, 480])
def test_the_side_lobes_of_a_spike_are_not_reported_as_drops(fwhm):
    n = 6 * 3600
    rng = np.random.default_rng(1)
    x = 0.15 * rng.standard_normal(n) + gauss(n, n // 2, fwhm, 2.0)
    r = CR.detect(x, FS)
    assert [e for e in r.events if e["polarity"] < 0 and not e["edge_flag"]] == []
    assert r.counts["side_lobes"] >= 1, "the lobes were there and were vetoed, not missed"
    inv = CR.detect(-x, FS)
    assert [e for e in inv.events if e["polarity"] > 0 and not e["edge_flag"]] == []


def test_polarity_filters_what_is_reported_and_nothing_else():
    x, _ = day_trace(0)
    both = CR.detect(x, FS)
    spikes = CR.detect(x, FS, polarity="spike")
    drops = CR.detect(x, FS, polarity="drop")
    assert [e for e in both.events if e["polarity"] > 0] == spikes.events
    assert [e for e in both.events if e["polarity"] < 0] == drops.events
    with pytest.raises(ValueError, match="polarity"):
        CR.detect(x, FS, polarity="up")


def test_nan_samples_are_bridged_for_the_transform_and_flagged_on_the_event():
    n = 4 * 3600
    rng = np.random.default_rng(2)
    x = 0.15 * rng.standard_normal(n) + gauss(n, 5000, 480, 2.0) + gauss(n, 11000, 480, 2.0)
    x[5100:5110] = np.nan
    r = CR.detect(x, FS)
    assert r.n_nan == 10
    a, b = match(r.events, 5000, 480, +1), match(r.events, 11000, 480, +1)
    assert a["nan_in_support"] and not b["nan_in_support"]
    with pytest.raises(ValueError, match="NaN"):
        CR.detect(np.full(5000, np.nan), FS)


def test_scales_too_large_for_the_span_are_dropped_and_counted():
    x = np.random.default_rng(0).standard_normal(4000)
    r = CR.detect(x, FS)        # default 10 s .. 7200 s, 40 scales
    assert r.scales_s.max() <= 4000 / 4
    assert r.scales_dropped == 40 - len(r.scales_s) > 0
    tiny = CR.detect(np.zeros(30), FS)
    assert tiny.events == [] and len(tiny.scales_s) < 3
    with pytest.raises(ValueError, match="min_scale_s"):
        CR.detect(x, FS, min_scale_s=0.5)
    with pytest.raises(ValueError, match="max_scale_s"):
        CR.detect(x, FS, min_scale_s=100.0, max_scale_s=50.0)


# ── chunks and long spans ───────────────────────────────────────────────────

def test_chunked_and_unchunked_processing_give_the_same_events():
    x, _ = day_trace(0)
    kw = dict(max_scale_s=600.0, noise_window_s=600.0)
    whole = CR.detect(x, FS, **kw)
    parts = CR.detect(x, FS, chunk_samples=20000, **kw)
    assert whole.n_chunks == 1 and parts.n_chunks == 5
    assert len(whole.events) >= 5
    key = ("peak_idx", "start", "end", "polarity", "ridge_scales", "edge_flag")
    assert [tuple(e[k] for k in key) for e in parts.events] == [tuple(e[k] for k in key) for e in whole.events]
    for a, b in zip(parts.events, whole.events):
        assert a["best_scale_s"] == pytest.approx(b["best_scale_s"], rel=1e-9)
        assert a["snr"] == pytest.approx(b["snr"], rel=1e-9)
    assert parts.counts == whole.counts
    assert np.allclose(parts.scalogram["values"], whole.scalogram["values"], atol=1e-5)


def test_two_point_six_million_samples_complete_in_chunks():
    """A month at 1 Hz (the longest channel): two chunks, O(chunk) memory."""
    x, truth = day_trace(0)
    n = 2_600_000
    big = np.tile(x, n // DAY + 1)[:n]
    r = CR.detect(big, FS)
    assert r.n_chunks == 2
    found = sum(match(r.events, k * DAY + c, w, p) is not None
                for k in range(n // DAY) for c, w, p in truth)
    assert found >= 0.95 * (n // DAY) * len(truth)


# ── what the result carries for the page ────────────────────────────────────

def test_the_result_carries_ridges_a_coarse_scalogram_and_the_rules():
    x, _ = day_trace(0)
    r = CR.detect(x, FS)
    assert len(r.ridges) == len(r.events) <= CR.MAX_RIDGES_IN_META
    rd = r.ridges[0]
    assert len(rd["cols"]) == len(rd["scales_s"]) >= 6
    vals = r.scalogram["values"]
    assert vals.dtype == np.float32 and vals.shape == (len(r.scales_s), r.scalogram["n_columns"])
    assert vals.shape[1] <= 1024, "a coarse picture: at most 1024 columns (the meta stays small)"
    names = {d["name"] for d in CR.rules()}
    assert {"duration_s", "snr", "best_scale_s", "peak_idx", "edge_flag", "side lobe", "nested", "step_pair",
            "coefficient baseline"} <= names


# ── A15: SNR is detectability at the event's own scale (critic F1, F2) ──────
# The noise an event is judged against is the robust spread (1.96 x 1.4826 x MAD)
# of the coefficients at the event's OWN best scale around it, not the 95th
# percentile of the smallest scale's. Wander (random-walk-like, as fungal traces
# tend to be) is large at large scales and small at small ones; measured at the
# smallest scale it let slow wander through as events (125 a day at min_snr 3)
# while coloured noise hid amplitude-1 events, and the events of a train raised
# their own p95 "noise" until none passed.

def wander(seed, white=0.15, step=0.01):
    rng = np.random.default_rng(seed)
    return white * rng.standard_normal(DAY) + np.cumsum(step * rng.standard_normal(DAY))


def ar1(seed, phi=0.95, sd=0.3):
    from scipy.signal import lfilter
    rng = np.random.default_rng(seed)
    return lfilter([1.0], [1.0, -phi], sd * np.sqrt(1.0 - phi ** 2) * rng.standard_normal(DAY))


@pytest.mark.parametrize("white", [0.0, 0.15])
def test_wander_alone_gives_at_most_two_unflagged_events_a_day(white):
    """A pure random walk (step 0.01 a second) and the same walk under white noise
    0.15: before A15, 125 / 46 / 21 / 7 events a day at min_snr 3 / 5 / 8 / 12 on
    the walk, 25 on walk + white. A walk has no events, but its excursions are
    bumps at every scale, so a rare large one may still pass; the bound is 2 a
    day per seed (a 24 s-event family alone gives tens a day on the catalogue's
    channels, so 2 is a few per cent of a real day's count), over 3 seeds."""
    for seed in range(3):
        r = CR.detect(wander(100 + seed, white=white), FS)
        unflagged = [e for e in r.events if not e["edge_flag"]]
        assert len(unflagged) <= 2, (seed, [(e["peak_idx"], round(e["best_scale_s"]), round(e["snr"], 1))
                                            for e in unflagged])


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_coloured_noise_does_not_hide_amplitude_one_events(seed):
    """AR(1), phi 0.95, standard deviation 0.3 (strong at the 24 s family's own
    scale): before A15 0.3 of the seven amplitude-1 events were found."""
    x = ar1(200 + seed)
    for c, w, p, a in EVENTS:
        x += gauss(DAY, c, w, p * a)
    r = CR.detect(x, FS)
    missed = [(c, w, p) for c, w, p, _ in EVENTS if match(r.events, c, w, p) is None]
    assert missed == [], missed


def test_a_train_of_24_s_drops_every_300_s_is_fully_recalled():
    """Amplitude 1 on white 0.15 (an isolated one has SNR ~7.6): before A15 the
    train's own drops raised the p95 noise and 0 of 286 were found."""
    rng = np.random.default_rng(300)
    x = 0.15 * rng.standard_normal(DAY)
    centres = np.arange(300, DAY - 300, 300)
    for c in centres:
        x += gauss(DAY, c, 24, -1.0)
    r = CR.detect(x, FS)
    missed = [int(c) for c in centres if match(r.events, c, 24, -1) is None]
    assert missed == [], f"{len(missed)} of {len(centres)} missed"


def test_the_noise_is_measured_at_the_events_own_scale_and_the_small_scale_p95_is_kept_as_a_diagnostic():
    x, truth = day_trace(0)
    r = CR.detect(x, FS)
    slow = match(r.events, *truth[4])               # the 43 min spike
    fast = match(r.events, *truth[0])               # a 24 s spike
    assert "noise_min_scale" in slow and slow["noise_min_scale"] > 0
    assert slow["snr"] == pytest.approx(slow["peak_coef"] / slow["noise"])
    # white noise shrinks with scale (a^-1/2): the slow event's own-scale noise is far below the 10 s row's
    assert slow["noise"] < 0.5 * slow["noise_min_scale"]
    assert slow["noise"] < fast["noise"]
    assert {"snr", "noise_min_scale"} <= {d["name"] for d in CR.rules()}


# ── edges and NaN (critic F6, F7) ───────────────────────────────────────────

def test_the_odd_reflection_hinges_on_a_robust_edge_level_not_one_sample():
    """An outlier in the first or last sample used to be the hinge: the reflected
    trace jumped to twice it, a step the hat read as a slow edge event."""
    n = 6 * 3600
    rng = np.random.default_rng(4)
    x = 0.15 * rng.standard_normal(n)
    x[0], x[-1] = 5.0, -5.0
    r = CR.detect(x, FS)
    assert [e for e in r.events if e["best_scale_s"] > 30] == [], [
        (e["peak_idx"], round(e["best_scale_s"]), e["ridge_polarity"]) for e in r.events]


def test_a_span_more_than_half_nan_is_refused_in_words():
    n = 4 * 3600
    x = 0.15 * np.random.default_rng(6).standard_normal(n) + gauss(n, 2000, 480, 2.0)
    x[n // 3:] = np.nan
    with pytest.raises(ValueError, match="more than half"):
        CR.detect(x, FS)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

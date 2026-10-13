"""
test_deconvolve_noise_scale.py
===============================
w1-b follow-up: `detection.deconvolve`'s `noise_scale`. On real 1 Hz fungal
recordings the background is strongly coloured (each sample close to the last),
so the noise SD read from first differences (`sigma`) was 1/46, 1/38 and 1/3.4 of
the background's own spread (`sigma_level`) and "3 sigma" jumps were noise
wiggles: 1,716 jumps in 4 h on rec 385. The default unit is now `level`.

Synthetic acceptance, through the template's own first three blocks (1 h
rolling-mean detrend -> Deconvolve, 120 s given, 30 min running baseline ->
Impulse events): 30 troughs on AR(1) (phi 0.95, 0.99) and 1/f backgrounds give
~30 events; the same backgrounds with no troughs give at most 1 event an hour;
the white-noise 12 h synthetic still gives 30 with the 8 overlapping pairs
separated. `diff` keeps the old reading, and on the same coloured traces it
still fragments -- the reason for the change, pinned.

Runnable standalone:  python tests/test_deconvolve_noise_scale.py
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
from Working.Detection.deconvolution import oasis as O  # noqa: E402
from tests._deconv_synthetic import (BASELINE_V, FS, N_12H, ar1_noise, pink_noise,  # noqa: E402
                                     troughs_12h)

discover_adapters()
LEVEL_SD = 2e-4                  # the troughs are 2-6 mV: 10-30 background SDs deep
HOURS = N_12H / 3600.0
BACKGROUNDS = ["ar0.95", "ar0.99", "pink"]


def _chain(x, **deconv):
    """Detrend (1 h rolling mean) -> Deconvolve (120 s, 30 min running baseline) -> Impulse events."""
    t = np.arange(len(x), dtype=float) / FS
    det, dec, imp = (get_adapter(n) for n in ("preprocessing.detrend", "detection.deconvolve",
                                               "detection.impulse_events"))
    xd = det.run(x, t, FS, **det.validate_params({"mode": "rolling_mean", "window_s": 3600.0})).value
    xd = np.asarray(getattr(xd, "x", xd), dtype=float)
    params = dict({"recovery_half_s": 120.0, "baseline_window_s": 1800.0}, **deconv)
    sc = dec.run(xd, t, FS, **dec.validate_params(params))
    ev = imp.run(xd, t, FS, value=sc.value, **imp.validate_params({}))
    return sc.meta, ev.value


def _background(kind):
    if kind == "ar0.95":
        return ar1_noise(N_12H, 0.95, LEVEL_SD, seed=1)
    if kind == "ar0.99":
        return ar1_noise(N_12H, 0.99, LEVEL_SD, seed=1)
    return pink_noise(N_12H, LEVEL_SD, seed=2)


def test_noise_scale_is_a_bounded_choice_defaulting_to_level():
    spec = get_adapter("detection.deconvolve")
    assert spec.validate_params({})["noise_scale"] == "level"
    assert spec.validate_params({"noise_scale": "diff"})["noise_scale"] == "diff"
    with pytest.raises(ValueError):
        spec.validate_params({"noise_scale": "psd"})
    with pytest.raises(ValueError, match="noise_scale"):
        O.deconvolve(np.arange(100.0), FS, recovery_half_s=60.0, noise_scale="psd")


@pytest.mark.parametrize("phi", [0.95, 0.99])
def test_level_sigma_reads_coloured_noise_at_full_size_where_differences_do_not(phi):
    bg = ar1_noise(N_12H, phi, LEVEL_SD, seed=3)
    true_sd = float(np.std(bg))
    assert O.level_sigma([bg]) == pytest.approx(true_sd, rel=0.2)
    assert O.noise_sigma([bg]) < 0.5 * true_sd


def test_level_sigma_clips_the_troughs_away():
    """On the white-noise trough train the troughs are clipped: their tails inflate it only a little."""
    x, _, _ = troughs_12h(seed=0)
    y = -x
    z = y - O.running_floor(y, 1800)
    assert O.level_sigma([z]) == pytest.approx(1e-4, rel=0.3)


@pytest.mark.parametrize("kind", BACKGROUNDS)
def test_thirty_troughs_on_a_coloured_background_give_about_thirty_events(kind):
    clean, onsets, _ = troughs_12h(seed=0, noise=0.0)
    meta, ev = _chain(clean + _background(kind))
    assert meta["noise_scale"] == "level"
    assert meta["scale"] == pytest.approx(meta["sigma_level"])
    assert meta["sigma_level"] > 2.0 * meta["sigma"]               # the background is coloured
    assert 27 <= len(ev.starts) <= 33, len(ev.starts)
    for o in onsets:
        assert any(s <= o - 1 < e for s, e in zip(ev.starts, ev.ends)), f"onset {o} not in an event"


@pytest.mark.parametrize("kind", BACKGROUNDS)
def test_event_free_coloured_background_gives_at_most_one_event_an_hour(kind):
    meta, ev = _chain(BASELINE_V + _background(kind))
    assert len(ev.starts) <= HOURS, len(ev.starts)
    assert meta["residual_sd_sigma"] < 1.5


@pytest.mark.parametrize("kind", ["ar0.95", "ar0.99"])
def test_the_diff_scale_still_fragments_coloured_noise_which_is_why_level_is_the_default(kind):
    meta, ev = _chain(BASELINE_V + _background(kind), noise_scale="diff")
    assert meta["noise_scale"] == "diff" and meta["scale"] == pytest.approx(meta["sigma"])
    assert len(ev.starts) > 10 * HOURS


def test_white_noise_acceptance_holds_with_level_thirty_troughs_and_the_pairs_separated():
    x, onsets, pairs = troughs_12h(seed=0, drift=4e-3)
    meta, ev = _chain(x)
    assert meta["noise_scale"] == "level"
    assert len(ev.starts) == 30
    onset_idx = np.asarray(ev.starts) + 10          # impulse_events keeps pre_s = 10 s before each onset
    for first, second in pairs:
        a = int(np.argmin(np.abs(onset_idx - first)))
        b = int(np.argmin(np.abs(onset_idx - second)))
        assert a != b, (first, second)
        assert abs(onset_idx[a] - first) <= 3 and abs(onset_idx[b] - second) <= 3, (first, second)


def test_scores_are_jumps_in_the_chosen_unit():
    clean, _, _ = troughs_12h(seed=0, noise=0.0)
    x = clean + ar1_noise(N_12H, 0.99, LEVEL_SD, seed=1)
    lv = O.deconvolve(x, FS, recovery_half_s=120.0, baseline_window_s=1800.0)
    df = O.deconvolve(x, FS, recovery_half_s=120.0, baseline_window_s=1800.0, noise_scale="diff")
    assert lv.noise_scale == "level" and df.noise_scale == "diff"
    assert lv.scale == pytest.approx(lv.sigma_level) and df.scale == pytest.approx(df.sigma)
    assert lv.sigma == pytest.approx(df.sigma) and lv.sigma_level == pytest.approx(df.sigma_level)
    assert lv.s_min == pytest.approx(3.0 * lv.scale)
    at = np.flatnonzero(np.nan_to_num(lv.scores) > 0)
    np.testing.assert_allclose(lv.scores[at] * lv.scale, lv.s[at], rtol=1e-9)


def test_the_summary_names_the_unit_and_the_level_to_difference_ratio():
    clean, _, _ = troughs_12h(seed=0, noise=0.0)
    meta, _ = _chain(clean + ar1_noise(N_12H, 0.99, LEVEL_SD, seed=1))
    assert "level" in meta["summary"] and "first-difference" in meta["summary"]
    assert any(r["name"].startswith("sigma_level") for r in meta["rules"])


def test_a_too_short_recovery_is_flagged_by_its_follow_on_jumps():
    """True half-time 300 s, 120 s given: with the level unit the troughs split into a jump plus
    smaller follow-ons on its fade (~2 per trough, too few for the jumps-per-hour flag); say so.
    The right half-time draws no such flag."""
    x, _, _ = troughs_12h(seed=0, drift=4e-3, half_s=300.0)
    wrong, _ = _chain(x)
    assert wrong["follow_on_share"] > 0.35
    assert any("follow-on" in w for w in wrong["warnings"])
    right, ev = _chain(x, recovery_half_s=300.0)
    assert right["follow_on_share"] < 0.35
    assert not any("follow-on" in w for w in right["warnings"])
    assert 27 <= len(ev.starts) <= 33


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

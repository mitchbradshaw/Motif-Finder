"""
test_adapter_wavelet_bands.py
==============================
fixup-AC: `preprocessing.wavelet_bands`, a Signal -> Signal block that splits the
span into octave layers with a STATIONARY (undecimated) wavelet transform and
passes ONE layer on down the chain (RQ4, Q-W3).

What it pins:

* **Every layer stays sample-aligned with the recording.** The transform is
  `pywt.swt`, not `pywt.wavedec`: no layer is downsampled, so a detection on a
  layer is at the right time on the raw trace. A sharp drop in the input sits at
  the same sample on the layers that carry it.
* **The decomposition is complete.** `iswt` of the full set of coefficients gives
  back the input, and the layers (the details plus the residual approximation)
  add up to it — nothing is lost and nothing is invented.
* **Padding is to the length `swt` needs and trimmed back**, and `meta` says so.
* **`level` chooses the layer that goes on**; `0` is the residual approximation.
* **Every layer's frequency range is in `meta`, in Hz**, from `fs` and the level,
  so a layer reads as "about 0.03–0.06 Hz", not only as "level 4".
* **`levels = 0` is chosen from the span length and `fs`**: deep enough to reach
  the slowest named band's lower edge (0.001 Hz), never deeper than the span
  allows, never shallower than the chosen level.
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402

discover_adapters()

import Adapters.preprocessing_wavelet_bands as WB  # noqa: E402
from Working.types import Signal  # noqa: E402

NAME = "preprocessing.wavelet_bands"


def _spec():
    return get_adapter(NAME)


def _noise(n, seed=0, scale=1.0):
    return np.random.default_rng(seed).standard_normal(n) * scale


# ── the contract ─────────────────────────────────────────────────────────────

def test_it_is_a_signal_to_signal_preprocessing_block():
    spec = _spec()
    assert (spec.stage, spec.category) == ("preprocessing", "preprocess")
    assert (spec.input_kind, spec.output_kind) == ("signal", "signal")
    assert spec.page_name == "Wavelet bands"
    assert spec.known_broken is None


def test_its_defaults_are_db4_auto_levels_and_a_mid_level():
    p = _spec().validate_params({})
    assert p == {"wavelet": "db4", "levels": 0, "level": 4}


def test_the_wavelet_is_one_of_a_short_list_and_db4_is_on_it():
    wav = next(ps for ps in _spec().params if ps.name == "wavelet")
    assert wav.default == "db4" and "db4" in wav.choices and "haar" in wav.choices
    assert 3 <= len(wav.choices) <= 10
    with pytest.raises(ValueError):
        _spec().validate_params({"wavelet": "morl"})      # a continuous wavelet has no SWT


def test_level_and_levels_cannot_be_negative():
    with pytest.raises(ValueError):
        _spec().validate_params({"level": -1})
    with pytest.raises(ValueError):
        _spec().validate_params({"levels": -1})


# ── frequency ranges, in Hz ──────────────────────────────────────────────────

def test_a_detail_level_is_one_octave_below_the_one_above_it():
    # at 1 Hz: level 1 is 0.25-0.5 Hz (up to Nyquist), level 4 is "about 0.03-0.06 Hz"
    assert WB.layer_range_hz(1.0, 1, 9) == (0.25, 0.5)
    assert WB.layer_range_hz(1.0, 4, 9) == (0.03125, 0.0625)
    # at 10 Hz every edge is ten times higher
    assert WB.layer_range_hz(10.0, 1, 13) == (2.5, 5.0)
    assert WB.layer_range_hz(10.0, 4, 13) == (0.3125, 0.625)


def test_the_residual_is_everything_slower_than_the_deepest_detail():
    assert WB.layer_range_hz(1.0, 0, 9) == (0.0, 1.0 / 1024)
    assert WB.layer_range_hz(10.0, 0, 13) == (0.0, 10.0 / 2 ** 14)


def test_auto_levels_reach_the_slowest_named_band_within_the_span():
    # 4 h at 1 Hz: level 9 bottoms out at 1/1024 Hz ~ 0.00098 Hz, the first below 0.001 Hz
    assert WB.auto_levels(14400, 1.0, "db4") == 9
    # 4 h at 10 Hz: level 13 is the first whose lower edge is below 0.001 Hz
    assert WB.auto_levels(144000, 10.0, "db4") == 13
    # a short span stops where the filter no longer fits (pywt.dwt_max_level)
    assert WB.auto_levels(600, 1.0, "db4") == 6
    # never shallower than the level asked for, if the span allows it
    assert WB.auto_levels(14400, 1.0, "db4", level=10) == 10


# ── the decomposition ────────────────────────────────────────────────────────

def test_iswt_of_the_full_decomposition_reconstructs_the_input():
    import pywt

    x = _noise(3000, seed=1).cumsum()          # a wandering trace, not a power-of-two length
    coeffs, pad = WB.swt_coeffs(x, "db4", 6)
    back = pywt.iswt(coeffs, "db4", norm=True)
    np.testing.assert_allclose(back[pad["left"]:pad["left"] + len(x)], x, rtol=0, atol=1e-8)


def test_the_layers_add_up_to_the_input():
    x = _noise(3000, seed=2).cumsum()
    dec = WB.decompose(x, "db4", 6)
    names = [layer["name"] for layer in dec["layers"]]
    assert names == ["D1", "D2", "D3", "D4", "D5", "D6", "A6"], names
    total = np.sum([layer["x"] for layer in dec["layers"]], axis=0)
    assert all(len(layer["x"]) == len(x) for layer in dec["layers"]), "every layer is the span's length"
    np.testing.assert_allclose(total, x, rtol=0, atol=1e-8)


def test_padding_is_to_the_length_swt_needs_and_is_trimmed_back():
    x = _noise(3000, seed=3)
    _, pad = WB.swt_coeffs(x, "db4", 6)
    assert pad["n"] == 3000
    assert pad["padded_to"] % 2 ** 6 == 0 and pad["padded_to"] >= 3000
    assert pad["padded_to"] - 3000 == pad["left"] + pad["right"] < 2 ** 6
    assert pad["mode"] == "symmetric"


# ── the block ────────────────────────────────────────────────────────────────

def test_the_chosen_level_goes_on_down_the_chain():
    x = _noise(3000, seed=4).cumsum()
    t = np.arange(len(x)) / 1.0
    res = _spec().run(x, t, 1.0, **_spec().validate_params({"level": 3, "levels": 6}))
    assert res.output_kind == "signal" and isinstance(res.value, Signal)
    assert len(res.value.x) == len(x) and res.value.fs == 1.0
    want = next(layer["x"] for layer in WB.decompose(x, "db4", 6)["layers"] if layer["name"] == "D3")
    np.testing.assert_allclose(res.value.x, want, rtol=0, atol=1e-12)
    assert res.meta["level"] == 3 and res.meta["layer"] == "D3" and res.meta["levels"] == 6


def test_level_zero_passes_the_residual_approximation_on():
    x = _noise(3000, seed=5).cumsum()
    res = _spec().run(x, np.arange(len(x)), 1.0, **_spec().validate_params({"level": 0, "levels": 6}))
    want = next(layer["x"] for layer in WB.decompose(x, "db4", 6)["layers"] if layer["name"] == "A6")
    np.testing.assert_allclose(res.value.x, want, rtol=0, atol=1e-12)
    assert res.meta["layer"] == "A6"


def test_meta_carries_every_layers_range_in_hz_and_marks_the_chosen_one():
    x = _noise(3000, seed=6)
    res = _spec().run(x, np.arange(len(x)), 1.0, **_spec().validate_params({"level": 4, "levels": 6}))
    layers = res.meta["layers"]
    assert [L["name"] for L in layers] == ["D1", "D2", "D3", "D4", "D5", "D6", "A6"]
    d4 = next(L for L in layers if L["name"] == "D4")
    assert (d4["low_hz"], d4["high_hz"]) == (0.03125, 0.0625) and d4["chosen"] is True
    assert sum(L["chosen"] for L in layers) == 1
    a6 = layers[-1]
    assert a6["kind"] == "residual" and a6["level"] == 0 and (a6["low_hz"], a6["high_hz"]) == (0.0, 1.0 / 128)
    assert all(L["label"].endswith("Hz") for L in layers), [L["label"] for L in layers]


def test_meta_says_how_it_padded_and_that_it_trimmed_back():
    x = _noise(3000, seed=7)
    res = _spec().run(x, np.arange(len(x)), 1.0, **_spec().validate_params({"levels": 6}))
    pad = res.meta["padding"]
    assert pad["n"] == 3000 and pad["padded_to"] % 64 == 0 and pad["mode"] == "symmetric"
    assert "trim" in res.meta["padding_note"]


def test_meta_carries_a_drawable_min_max_envelope_per_layer():
    """Every layer's picture rides in `meta` as a min/max envelope of sample
    indices (span-relative) — small enough to survive the bridge's meta sidecar
    (arrays over 4096 values are dropped there), true to rule 2 (never a stride)."""
    n = 20000
    x = _noise(n, seed=8)
    x[12345] = -50.0                            # one narrow event a stride would delete
    res = _spec().run(x, np.arange(n), 1.0, **_spec().validate_params({"level": 1, "levels": 4}))
    d1 = res.meta["layers"][0]
    env = d1["envelope"]
    assert env["decimated"] is True and env["n_source"] == n
    assert len(env["i"]) == len(env["v"]) == env["n_points"] <= 4096
    assert all(0 <= i < n for i in env["i"]) and env["i"] == sorted(env["i"])
    # the narrow event survives the envelope: its layer minimum is drawn
    lo = int(np.argmin(res.value.x))
    assert lo in env["i"] and min(env["v"]) == pytest.approx(float(res.value.x[lo]))


def test_a_short_layer_ships_every_sample():
    x = _noise(600, seed=9)
    res = _spec().run(x, np.arange(600), 1.0, **_spec().validate_params({"levels": 4}))
    env = res.meta["layers"][0]["envelope"]
    assert env["decimated"] is False and env["i"] == list(range(600))


def test_a_drop_on_the_raw_trace_sits_at_the_same_sample_on_the_layers_that_carry_it():
    """Alignment, the reason for the stationary transform: a narrow dip at a
    known sample is at that sample (within its own half-width) on every layer
    that carries a large share of it."""
    n, at, half = 4096, 2500, 6
    x = _noise(n, seed=10, scale=0.01)
    x[at - half:at + half + 1] -= np.hanning(2 * half + 1) * 5.0
    res = _spec().run(x, np.arange(n), 1.0, **_spec().validate_params({"level": 2, "levels": 6}))
    dec = WB.decompose(x, "db4", 6)
    deepest = max(abs(float(np.min(L["x"]))) for L in dec["layers"])
    carriers = [L for L in dec["layers"] if abs(float(np.min(L["x"]))) >= 0.25 * deepest]
    assert carriers, "some layer carries the dip"
    for L in carriers:
        assert abs(int(np.argmin(L["x"])) - at) <= half, (L["name"], int(np.argmin(L["x"])))
    assert abs(int(np.argmin(res.value.x)) - at) <= half


def test_auto_levels_are_resolved_and_recorded():
    x = _noise(14400, seed=11)
    res = _spec().run(x, np.arange(14400), 1.0, **_spec().validate_params({}))
    assert res.meta["levels"] == 9 and res.meta["levels_auto"] is True
    assert len(res.meta["layers"]) == 10


def test_a_level_deeper_than_the_span_allows_is_refused_by_name():
    x = _noise(600, seed=12)
    with pytest.raises(ValueError) as e:
        _spec().run(x, np.arange(600), 1.0, **_spec().validate_params({"level": 9}))
    msg = str(e.value)
    assert "level 9" in msg and "600" in msg, msg


def test_a_level_deeper_than_the_levels_asked_for_is_refused():
    x = _noise(3000, seed=13)
    with pytest.raises(ValueError) as e:
        _spec().run(x, np.arange(3000), 1.0, **_spec().validate_params({"level": 7, "levels": 5}))
    assert "level 7" in str(e.value) and "5" in str(e.value)


def test_a_span_with_missing_samples_is_refused_loudly():
    x = _noise(3000, seed=14)
    x[100] = np.nan
    with pytest.raises(ValueError) as e:
        _spec().run(x, np.arange(3000), 1.0, **_spec().validate_params({"levels": 4}))
    assert "NaN" in str(e.value) or "finite" in str(e.value)

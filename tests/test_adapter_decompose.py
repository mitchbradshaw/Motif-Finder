"""
test_adapter_decompose.py
==========================
fixup-AO: `preprocessing.decompose`, a Signal -> Signal block that splits the
span into three layers that ADD UP to it -- the slow wander (baseline), the fast
fuzz (noise) and what is left (signal, where the events live) -- draws all
three, and passes ONE of them on down the chain through `pass_on`.

What it pins:

* **The three layers add up to the input** to 1e-9, on white noise, a random
  walk, an AR(1) background with phi = 0.98, a slow drift under drops, at a
  volts-sized offset, at 1 Hz and 10 Hz, with either baseline estimator.
* **No second filter.** The baseline is the running median the core already has
  (`Working.Detection.analysis.data_analysis.make_smooth`) -- or, on request,
  the detrend block's rolling mean (`make_detrend_filter`); the noise is the
  highpass block's own Butterworth (`make_highpass_filter`) applied to the
  input with its baseline taken off.
* **`noise_cut_hz = 0` means a quarter of Nyquist** (fs / 8), and `meta` says
  it was chosen automatically.
* **`pass_on` chooses the layer that goes on**, and the next block in a real
  chain (`execute_recipe`) reads exactly that layer: a detrend after the
  baseline sees an almost flat line; an invert after the noise gives -noise.
* **`meta.layers` is in the wavelet block's shape** (name, label, kind, chosen,
  rms, a min/max envelope over span-relative indices) plus the parameter a
  click on a layer sets (`layer_param`, each layer's `param_value`), so the
  block page draws it with the wavelet block's drawing code.
* **A gap is refused loudly**, as is a noise cut at or above Nyquist.
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402

discover_adapters()

from Working.Detection.analysis.data_analysis import make_smooth  # noqa: E402
from Working.Detection.analysis.freq_analysis import make_highpass_filter  # noqa: E402
from Working.Preprocessing.detrend import make_detrend_filter  # noqa: E402

NAME = "preprocessing.decompose"


def _spec():
    return get_adapter(NAME)


def _run(x, fs=1.0, **params):
    spec = _spec()
    return spec.run(x, np.arange(len(x)) / fs, fs, **spec.validate_params(params))


def _layers(res):
    return {L["name"]: L for L in res.meta["layers"]}


# -- the backgrounds a fungal recording actually has (00-common, wave-1 lesson) --

def _white(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n)


def _random_walk(n, seed=1):
    w = np.random.default_rng(seed).standard_normal(n).cumsum()
    return w - np.polyval(np.polyfit(np.arange(n), w, 1), np.arange(n))


def _ar1(n, phi=0.98, seed=2):
    e = np.random.default_rng(seed).standard_normal(n)
    out = np.empty(n)
    out[0] = e[0]
    for i in range(1, n):
        out[i] = phi * out[i - 1] + e[i]
    return out


def _drift_with_drops(n, fs=1.0, seed=3):
    t = np.arange(n) / fs
    x = 2.0 * np.sin(2 * np.pi * t / 20000.0) + 0.1 * np.random.default_rng(seed).standard_normal(n)
    for c in range(1500, n - 1500, 2400):                 # a drop every 40 min, ~5 min wide
        x[c:c + int(300 * fs)] -= 1.0 * np.hanning(int(300 * fs))
    return x


BACKGROUNDS = {
    "white": lambda n, fs: _white(n),
    "random_walk": lambda n, fs: _random_walk(n),
    "ar1_0.98": lambda n, fs: _ar1(n),
    "drift_and_drops": _drift_with_drops,
    "volts_offset": lambda n, fs: -0.447 + 1e-3 * _random_walk(n),
}


# -- the contract --------------------------------------------------------------

def test_it_is_a_signal_to_signal_preprocessing_block():
    spec = _spec()
    assert (spec.stage, spec.category) == ("preprocessing", "preprocess")
    assert (spec.input_kind, spec.output_kind) == ("signal", "signal")
    assert spec.page_name == "Decompose"
    assert spec.known_broken is None


def test_its_defaults_pass_the_signal_on_with_a_600_s_running_median_and_an_auto_cut():
    p = _spec().validate_params({})
    assert p["pass_on"] == "signal"
    assert p["baseline_window_s"] == 600.0
    assert p["noise_cut_hz"] == 0.0
    assert p["baseline_method"] == "rolling_median"
    pass_on = next(ps for ps in _spec().params if ps.name == "pass_on")
    assert list(pass_on.choices) == ["signal", "baseline", "noise"]
    with pytest.raises(ValueError):
        _spec().validate_params({"pass_on": "D3"})


def test_the_description_points_at_wavelet_bands_for_frequency_layers():
    d = _spec().description.lower()
    assert "wavelet bands" in d and "pass_on" in d


# -- the three layers add up to the input --------------------------------------

@pytest.mark.parametrize("fs", [1.0, 10.0])
@pytest.mark.parametrize("method", ["rolling_median", "rolling_mean"])
@pytest.mark.parametrize("bg", sorted(BACKGROUNDS))
def test_baseline_plus_noise_plus_signal_is_the_input(bg, method, fs):
    n = int(6 * 3600 * fs) if fs == 1.0 else 36000
    x = BACKGROUNDS[bg](n, fs)
    res = _run(x, fs=fs, baseline_method=method)
    from Working.Preprocessing.decompose import decompose
    parts = decompose(x, fs, baseline_window_s=600.0, noise_cut_hz=0.0, baseline_method=method)
    total = parts["baseline"] + parts["noise"] + parts["signal"]
    assert np.max(np.abs(total - x)) < 1e-9
    assert res.meta["reconstruction_error"] < 1e-9


def test_the_baseline_is_the_cores_running_median():
    x = _drift_with_drops(20000)
    from Working.Preprocessing.decompose import decompose
    parts = decompose(x, 1.0, baseline_window_s=600.0)
    np.testing.assert_allclose(parts["baseline"], make_smooth(300)(x), atol=0, rtol=0)


def test_the_rolling_mean_baseline_is_the_detrend_blocks_own():
    x = _random_walk(20000)
    from Working.Preprocessing.decompose import decompose
    parts = decompose(x, 1.0, baseline_window_s=600.0, baseline_method="rolling_mean")
    detrended = make_detrend_filter(1.0, mode="rolling_mean", window_s=600.0)(x)
    np.testing.assert_allclose(parts["baseline"], x - detrended, atol=1e-12)


def test_the_noise_is_the_highpass_blocks_filter_on_the_input_without_its_baseline():
    x = _ar1(20000)
    from Working.Preprocessing.decompose import decompose
    parts = decompose(x, 1.0, baseline_window_s=600.0, noise_cut_hz=0.05)
    want = make_highpass_filter(1.0, 0.05, order=4)(x - parts["baseline"])
    np.testing.assert_allclose(parts["noise"], want, atol=1e-12)


def test_noise_cut_zero_is_a_quarter_of_nyquist_and_meta_says_so():
    res = _run(_white(5000), fs=2.0)
    assert res.meta["split"]["noise_cut_hz"] == pytest.approx(2.0 / 8)
    assert res.meta["split"]["noise_cut_auto"] is True
    res = _run(_white(5000), fs=2.0, noise_cut_hz=0.1)
    assert res.meta["split"]["noise_cut_hz"] == pytest.approx(0.1)
    assert res.meta["split"]["noise_cut_auto"] is False


def test_the_layers_hold_what_their_names_say():
    """Slow sine + white fuzz + 5-min drops: the baseline follows the sine, the
    noise holds the fuzz and not the drops, the drops stay in the signal."""
    n, fs = 6 * 3600, 1.0
    t = np.arange(n)
    slow = 2.0 * np.sin(2 * np.pi * t / 20000.0)
    fuzz = 0.1 * _white(n, seed=9)
    drops = np.zeros(n)
    for c in range(1500, n - 1500, 2400):
        drops[c:c + 300] -= 1.0 * np.hanning(300)
    from Working.Preprocessing.decompose import decompose
    p = decompose(slow + fuzz + drops, fs)
    core = slice(1000, n - 1000)
    assert np.sqrt(np.mean((p["baseline"][core] - slow[core]) ** 2)) < 0.2, "the baseline follows the slow wander"
    assert np.corrcoef(p["signal"][core], drops[core])[0, 1] > 0.9, "the drops stay in the signal layer"
    assert np.corrcoef(p["noise"][core], fuzz[core])[0, 1] > 0.6, "the fuzz goes to the noise layer"
    assert abs(np.corrcoef(p["noise"][core], drops[core])[0, 1]) < 0.1, "the drops do not leak into the noise"


# -- pass_on and the payload ----------------------------------------------------

@pytest.mark.parametrize("which", ["signal", "baseline", "noise"])
def test_pass_on_chooses_the_layer_that_goes_on(which):
    x = _drift_with_drops(8000)
    from Working.Preprocessing.decompose import decompose
    parts = decompose(x, 1.0)
    res = _run(x, pass_on=which)
    np.testing.assert_allclose(res.value.x, parts[which], atol=0, rtol=0)
    assert res.value.fs == 1.0
    assert res.meta["layer"] == which


def test_meta_layers_are_in_the_wavelet_blocks_shape_plus_the_click_parameter():
    res = _run(_drift_with_drops(200_000), pass_on="noise")
    m = res.meta
    assert m["layer_param"] == "pass_on"
    assert [L["name"] for L in m["layers"]] == ["noise", "signal", "baseline"], "fastest first, as the wavelet block"
    assert [L["chosen"] for L in m["layers"]] == [True, False, False]
    for L in m["layers"]:
        assert {"name", "label", "kind", "chosen", "rms", "envelope", "param_value"} <= set(L)
        assert L["param_value"] == L["name"]
        assert L["kind"] == L["name"]
        assert L["label"].startswith(L["name"])
        env = L["envelope"]
        assert {"i", "v", "n_source", "n_points", "decimated"} <= set(env)
        assert env["n_source"] == 200_000 and env["decimated"] is True
        assert env["n_points"] <= 2400 and len(env["i"]) == len(env["v"]) == env["n_points"]
        assert all(0 <= i < 200_000 for i in (env["i"][0], env["i"][-1]))
    assert "split" in m and m["split"]["baseline_window_s"] == 600.0


def test_a_short_span_ships_every_sample_of_every_layer():
    res = _run(_white(1000))
    for L in res.meta["layers"]:
        assert L["envelope"]["decimated"] is False and L["envelope"]["i"] == list(range(1000))


# -- refusals --------------------------------------------------------------------

def test_a_gap_is_refused_with_its_count():
    x = _white(3000)
    x[[10, 20]] = np.nan
    with pytest.raises(ValueError, match="2 NaN"):
        _run(x)


def test_a_noise_cut_at_or_above_nyquist_is_refused():
    with pytest.raises(ValueError, match="Nyquist"):
        _run(_white(3000), fs=1.0, noise_cut_hz=0.5)


# -- through a real chain --------------------------------------------------------

@pytest.fixture
def db_with(request):
    from Working.database import queries as q
    from Working.database.schema import init_db
    import Working.config as cfg

    tmp = tempfile.mkdtemp(prefix="decompose_")
    x = _drift_with_drops(6 * 3600)
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic.mat", 0, 1.0, len(x), 0, npy)
    conn.close()
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield db, x
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def _chain(db, steps):
    from Working.execution import execute_recipe
    from Working.recipes import make_recipe
    seen = {}
    out = execute_recipe(make_recipe(1, steps), db_path=db, force=True,
                         on_step_result=lambda i, r: seen.__setitem__(i, r))
    return out, seen


def test_pass_on_baseline_hands_the_next_block_the_baseline_and_a_detrend_sees_a_flat_line(db_with):
    db, x = db_with
    from Working.Preprocessing.decompose import decompose
    parts = decompose(x, 1.0)
    out, seen = _chain(db, [
        {"stage": "preprocessing", "algorithm": "decompose", "params": {"pass_on": "baseline"}},
        {"stage": "preprocessing", "algorithm": "detrend", "params": {}},
    ])
    np.testing.assert_allclose(seen[0].value.x, parts["baseline"], atol=1e-12)
    flat = out["result"].value.x
    want = make_detrend_filter(1.0, mode="rolling_mean", window_s=600.0)(parts["baseline"])
    np.testing.assert_allclose(flat, want, atol=1e-12)
    assert np.std(flat) < 0.05 * np.std(x), "a detrend of the baseline is (almost) a flat line"


def test_pass_on_noise_hands_the_next_block_the_noise(db_with):
    db, x = db_with
    from Working.Preprocessing.decompose import decompose
    parts = decompose(x, 1.0)
    out, _ = _chain(db, [
        {"stage": "preprocessing", "algorithm": "decompose", "params": {"pass_on": "noise"}},
        {"stage": "preprocessing", "algorithm": "invert", "params": {}},
    ])
    np.testing.assert_allclose(out["result"].value.x, -parts["noise"], atol=1e-12)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

"""
test_adapter_minirocket.py
==========================
w2-c: the `catalogue.minirocket` adapter — WindowSet -> WindowSet (a feature
block: the same windows, the MiniRocket fingerprint added to the feature
table), its parameters and bounds, its cost model, its readout, and one run on
the windows `preprocessing.sliding_windows` makes.

Runnable standalone:  python -m pytest tests/test_adapter_minirocket.py -q
"""

import json
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
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _minirocket_synthetic as syn  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402

NAME = "catalogue.minirocket"


@pytest.fixture(scope="module")
def spec():
    discover_adapters()
    return get_adapter(NAME)


def _windows(x, spec_sw=None, **params):
    sw = spec_sw or get_adapter("preprocessing.sliding_windows")
    t = np.arange(len(x), dtype=float) / syn.FS
    return sw.run(x, t, syn.FS, **sw.validate_params(params)).value, t


def test_registered_as_a_windowset_to_windowset_feature_block(spec):
    assert spec.input_kind == "windowset" and spec.output_kind == "windowset"
    assert spec.stage == "catalogue"
    assert spec.category == "encode"
    assert spec.page_name == "MiniRocket"
    d = spec.description.lower()
    assert "n_features" in d, "the description names the one parameter to tune first"
    assert "train" in d


def test_the_defaults_are_the_papers_and_bounded(spec):
    p = spec.validate_params({})
    assert p["n_features"] == 10_000 and p["max_dilations"] == 32 and p["seed"] == 0
    assert p["normalise"] is True and p["max_cells"] == 50_000_000
    by = {ps.name: ps for ps in spec.params}
    assert by["n_features"].min == 84
    assert by["max_dilations"].min == 1
    assert by["max_cells"].min >= 1
    with pytest.raises(ValueError):
        spec.validate_params({"n_features": 10})


def test_a_run_on_sliding_windows_keeps_the_split_and_adds_the_fingerprint(spec):
    x, _ = syn.recording(n_per_class=4, seed=21)
    ws, t = _windows(x, window_s=600.0, n_blocks=4, holdout_frac=0.25)
    r = spec.run(x, t, syn.FS, **spec.validate_params({"n_features": 840}), value=ws)
    assert r.output_kind == "windowset"
    out = r.value
    assert np.array_equal(out.starts, ws.starts) and out.length == ws.length
    cols = [c for c in out.features.columns if c.startswith("mr_")]
    assert len(cols) == r.meta["n_features"] == 840
    assert out.features["split"].tolist() == ws.features["split"].tolist()
    assert r.meta["fit_on"] == "train"
    assert r.meta["n_fit_windows"] == int((ws.features["split"] == 0).sum())
    assert all(set(rule) == {"name", "rule"} for rule in r.meta["rules"])


def test_no_windows_in_is_refused_in_words(spec):
    x = np.zeros(1200)
    with pytest.raises(ValueError, match="WindowSet"):
        spec.run(x, np.arange(1200.0), 1.0, **spec.validate_params({}))


def test_the_readout_says_how_big_the_table_will_be_and_flags_the_ceiling(spec):
    x, _ = syn.recording(n_per_class=4, seed=21)
    ws, t = _windows(x)
    rows = dict((k, (v, s)) for k, v, s in spec.derive(x, t, syn.FS, spec.validate_params({}), value=ws))
    assert "9,996" in rows["Features"][0]
    over = dict((k, (v, s)) for k, v, s in spec.derive(
        x, t, syn.FS, spec.validate_params({"max_cells": 1_000}), value=ws))
    assert over["Table"][1] == "error"
    bare = spec.derive(x, t, syn.FS, spec.validate_params({}))
    assert bare and bare[0][2] == "warn"


def test_it_declares_a_cost_model_and_estimates_none_until_calibrated(spec, monkeypatch):
    """The calibration times `CAL_WINDOWS_PER_LENGTH` windows per window length of the calibration signal, so
    k is that many times the seconds per window-sample; the estimate assumes the densest shipped grid (the labels'
    600/200 grid: every sample in `GRID_OVERLAP` windows)."""
    import Adapters.catalogue_minirocket as A
    import Working.block_cost as bc
    assert NAME in bc.MODELS and bc.MODELS[NAME][0] == 1.0
    assert A.CAL_WINDOWS_PER_LENGTH == 120 and A.GRID_OVERLAP == 3
    tmp = tempfile.mkdtemp(prefix="w2c_cost_")
    try:
        monkeypatch.setattr(bc, "CALIBRATION_PATH", os.path.join(tmp, "cal.json"))
        x = np.zeros(36_000)
        assert spec.estimate(x, None, 1.0, **spec.validate_params({})) is None
        with open(bc.CALIBRATION_PATH, "w", encoding="utf-8") as f:
            json.dump({bc._key(NAME): {"k": 1e-4, "exponent": 1.0}}, f)
        full = spec.estimate(x, None, 1.0, **spec.validate_params({}))
        tenth = spec.estimate(x, None, 1.0, **spec.validate_params({"n_features": 1_000}))
        assert full == pytest.approx(1e-4 * 36_000 * 3 / 120)          # 0.09 s
        assert tenth == pytest.approx(0.09 * 924 / 9_996)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_calibration_warms_up_untimed_then_times_thousands_of_windows(spec, monkeypatch):
    """Critic finding 1: the timed call must not pay the aeon import, and must do enough work to dominate."""
    import Working.block_cost as bc
    from Working.Catalogue import minirocket as MR
    assert NAME in bc.WARM_UPS, "catalogue.minirocket registers an untimed warm-up"
    calls = []
    real_warm = bc.WARM_UPS[NAME]

    def warm():
        calls.append("warm")
        real_warm()                                    # really imports aeon and runs a tiny transform

    def timed(ws, x, t, fs, **kw):
        calls.append(("timed", int(ws.n_windows), int(ws.length), kw.get("n_features", MR.DEFAULT_N_FEATURES)))

    monkeypatch.setitem(bc.WARM_UPS, NAME, warm)
    monkeypatch.setattr(MR, "fingerprint", timed)
    tmp = tempfile.mkdtemp(prefix="w2c_cal_")
    try:
        monkeypatch.setattr(bc, "CALIBRATION_PATH", os.path.join(tmp, "cal.json"))
        bc.calibrate([NAME], force=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert calls[0] == "warm" and calls[1][0] == "timed"
    _, n_windows, length, n_features = calls[1]
    assert length == 600 and n_features == MR.DEFAULT_N_FEATURES
    # 120 windows per 600 samples of the 20,000-sample calibration signal (stride 5): 3,881 windows
    assert n_windows == (bc.CALIBRATION_N - 600) // 5 + 1 >= 3_000

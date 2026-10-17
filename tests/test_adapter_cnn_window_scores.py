"""
test_adapter_cnn_window_scores.py
==================================
`catalogue.cnn_window_scores` (W4-A), WindowSet → Scores: the spec, the
geometry of the Scores it lays down (channel-absolute window starts, one
value per sample of the span, NaN where no window reaches), its hand-off to
Threshold, the cost model, and the one-class refusal it shares with
`catalogue.cnn_score`.

Runnable standalone:  python tests/test_adapter_cnn_window_scores.py
"""

import inspect
import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("torch")

import _cnn_checkpoints as ck  # noqa: E402
from _calibration_isolation import scratch_calibration  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working import block_cost  # noqa: E402
from Working.types import Encoding, WindowSet  # noqa: E402

discover_adapters()
NAME = "catalogue.cnn_window_scores"


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    return ck.write_model_set(str(tmp_path_factory.mktemp("cnn_models")))


def spec():
    return get_adapter(NAME)


def walk(n, seed=0):
    x = np.cumsum(np.random.default_rng(seed).standard_normal(n))
    return x - np.linspace(x[0], x[-1], n)


def run(x, t, fs, ws, **params):
    s = spec()
    return s.run(x, t, fs, value=ws, **s.validate_params(params))


# ── the spec ────────────────────────────────────────────────────────────────

def test_registered_as_windowset_to_scores_beside_cnn_score():
    s = spec()
    assert s.input_kind == "windowset" and s.output_kind == "scores"
    assert s.stage == "catalogue"
    assert s.category == get_adapter("catalogue.cnn_score").category
    assert s.page_name == "CNN window scores"
    assert s.estimate is not None
    accepted = inspect.signature(s.run).parameters
    assert "on_progress" in accepted and "should_cancel" in accepted


def test_defaults_are_the_training_geometry_and_the_two_class_fusion_model():
    p = spec().validate_params({})
    assert p["image_type"] == "fusion"
    assert p["model_path"] == os.path.join("MODELS", "fusion_cnn_3.pth")
    assert p["resample_to"] == 600 and p["img_size"] == 224 and p["batch_size"] == 64
    assert p["positive_class"] == 0


def test_every_numeric_parameter_is_bounded():
    for ps in spec().params:
        if ps.type in (int, float):
            assert ps.min is not None and ps.max is not None, ps.name
    choices = {ps.name: ps.choices for ps in spec().params}
    assert set(choices["image_type"]) == {"fusion", "GASF", "GADF", "recurrence"}
    with pytest.raises(ValueError):
        spec().validate_params({"resample_to": 4096})
    with pytest.raises(ValueError):
        spec().validate_params({"batch_size": 0})


def test_the_description_names_the_knob_and_the_training_scale():
    d = spec().description.lower()
    assert "threshold" in d and "600" in d and "10-minute" in d


def test_a_missing_window_set_is_refused():
    s = spec()
    with pytest.raises(ValueError, match="WindowSet"):
        s.run(walk(100), None, 1.0, **s.validate_params({}))


def test_a_resample_target_between_1_and_15_is_refused(models):
    x = walk(1200)
    ws = WindowSet(starts=np.array([0, 600]), length=600, fs=1.0, features=pd.DataFrame({"split": [0, 0]}))
    with pytest.raises(ValueError, match="resample_to"):
        run(x, None, 1.0, ws, model_path=models["fusion3"], resample_to=8)


# ── geometry ────────────────────────────────────────────────────────────────

def test_a_span_that_does_not_start_at_zero_maps_its_windows(models):
    """WindowSet starts are channel-absolute; the span starts at channel sample 5,000. Each window's score
    fills exactly its own samples of the span, and the tail no whole window reaches is NaN."""
    fs, offset, L = 1.0, 5000, 600
    x = walk(2000, seed=1)
    t = (offset + np.arange(len(x))) / fs
    ws = WindowSet(starts=offset + np.array([0, 600, 1200]), length=L, fs=fs,
                   features=pd.DataFrame({"split": [0, 0, 0]}))
    r = run(x, t, fs, ws, model_path=models["fusion3"], img_size=64)
    v = r.value.values
    assert r.output_kind == "scores" and len(v) == len(x) and r.value.fs == fs
    p = r.meta["window_scores"]
    for i in range(3):
        assert np.all(v[i * L:(i + 1) * L] == pytest.approx(p[i]))
    assert np.isnan(v[1800:]).all()
    assert r.meta["starts"] == [5000, 5600, 6200]
    assert r.meta["window_s"] == 600.0


def test_overlapping_windows_the_later_one_wins(models):
    x = walk(900, seed=2)
    ws = WindowSet(starts=np.array([0, 300]), length=600, fs=1.0, features=pd.DataFrame({"split": [0, 0]}))
    r = run(x, None, 1.0, ws, model_path=models["fusion3"], img_size=64)
    v, p = r.value.values, r.meta["window_scores"]
    assert v[0] == pytest.approx(p[0]) and v[299] == pytest.approx(p[0])
    assert v[300] == pytest.approx(p[1]) and v[899] == pytest.approx(p[1])


def test_threshold_spans_are_unions_of_whole_windows(models):
    """Ten tiling 60-s windows through Threshold at the median window score: every span starts and ends on a
    window boundary, and is scored by its highest window."""
    L = 60
    x = walk(10 * L + 25, seed=3)
    ws = WindowSet(starts=np.arange(0, 10 * L, L), length=L, fs=1.0, features=pd.DataFrame({"split": [0] * 10}))
    r = run(x, None, 1.0, ws, model_path=models["gadf"], image_type="GADF", img_size=64)
    p = np.asarray(r.meta["window_scores"])
    cut = float(np.median(p))
    th = get_adapter("detection.threshold")
    spans = th.run(x, None, 1.0, value=r.value, **th.validate_params({"threshold": cut})).value
    assert len(spans.starts) >= 1
    for s, e, sc in zip(spans.starts, spans.ends, spans.scores):
        assert s % L == 0 and e % L == 0
        assert sc == pytest.approx(p[s // L:e // L].max())
    covered = sum(e - s for s, e in zip(spans.starts, spans.ends))
    assert covered == L * int((p > cut).sum())


def test_an_empty_window_set_gives_all_nan_scores_and_says_why(models):
    x = walk(500)
    ws = WindowSet(starts=np.array([], dtype=np.int64), length=600, fs=1.0,
                   features=pd.DataFrame({"split": np.array([], dtype=int)}))
    r = run(x, None, 1.0, ws, model_path=models["fusion3"])
    assert len(r.value.values) == 500 and np.isnan(r.value.values).all()
    assert r.meta["n_windows"] == 0
    assert "no window" in r.meta["note"].lower()
    assert "no window" in r.meta["summary"].lower()


def test_skipped_windows_reach_the_summary_and_warnings(models):
    x = walk(1800, seed=4)
    x[100] = np.nan
    ws = WindowSet(starts=np.array([0, 600, 1200]), length=600, fs=1.0, features=pd.DataFrame({"split": [0] * 3}))
    r = run(x, None, 1.0, ws, model_path=models["fusion3"], img_size=64)
    assert np.isnan(r.value.values[:600]).all() and np.isfinite(r.value.values[600:]).all()
    assert r.meta["skipped"]["nan"] == 1
    assert "2 of 3" in r.meta["summary"]
    assert any("NaN" in w for w in r.meta["warnings"])


def test_a_window_scale_off_the_training_scale_is_flagged(models):
    x = walk(600, seed=5)
    ws = WindowSet(starts=np.arange(0, 600, 60), length=60, fs=1.0, features=pd.DataFrame({"split": [0] * 10}))
    r = run(x, None, 1.0, ws, model_path=models["fusion3"], img_size=32)
    assert any("training scale" in w for w in r.meta["warnings"])
    on = WindowSet(starts=np.array([0]), length=600, fs=1.0, features=pd.DataFrame({"split": [0]}))
    r2 = run(x, None, 1.0, on, model_path=models["fusion3"], img_size=32)
    assert not any("training scale" in w for w in r2.meta.get("warnings", []))


# ── cnn_score shares the refusal ────────────────────────────────────────────

def test_cnn_score_refuses_a_one_class_checkpoint(models):
    x = walk(600)
    ws = WindowSet(starts=np.array([0]), length=600, fs=1.0, features=pd.DataFrame({"split": [0]}))
    stack = Encoding(values=np.zeros((1, 32, 32, 3), dtype=np.uint8), kind="image")
    cnn = get_adapter("catalogue.cnn_score")
    with pytest.raises(ValueError, match=r"(?s)fusion_cnn\.pth.*\b1 output class"):
        cnn.run(x, None, 1.0, value=stack, windows=ws,
                **cnn.validate_params({"model_path": models["one_class"], "img_size": 32}))


# ── cost ────────────────────────────────────────────────────────────────────

def test_the_estimate_is_none_until_calibrated_then_linear_in_the_span():
    """Calibrated on random weights in memory (no checkpoint file needed), the torch import and the model
    build untimed; then a span twice as long costs twice as much."""
    from Adapters import catalogue_cnn_window_scores as mod
    s = spec()
    with scratch_calibration(block_cost):
        assert s.estimate(np.zeros(36_000), None, 1.0, **s.validate_params({})) is None
        block_cost.calibrate([mod.COST_MODEL])
        a = s.estimate(np.zeros(36_000), None, 1.0, **s.validate_params({}))
        b = s.estimate(np.zeros(72_000), None, 1.0, **s.validate_params({}))
    assert a is not None and a > 0
    assert b == pytest.approx(2 * a)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

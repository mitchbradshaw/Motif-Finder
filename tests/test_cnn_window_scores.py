"""
test_cnn_window_scores.py
==========================
The core of `catalogue.cnn_window_scores` (W4-A),
`Working.Catalogue.cnn.window_scores`: every window resampled to the training
geometry (600 points), encoded exactly as the CNN training set was, scored a
batch at a time, with the refusals and the left-out windows counted.

The checkpoints are random-weight two-class networks with the `EEG_CNN`
layout written to a temporary directory (`tests/_cnn_checkpoints.py`):
`MODELS/` is not in a worktree, and what these tests pin is the plumbing
(pixels, geometry, batching, refusals), not what a trained model says.

Runnable standalone:  python tests/test_cnn_window_scores.py
"""

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

torch = pytest.importorskip("torch")

import _cnn_checkpoints as ck  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Catalogue.cnn import window_scores as WS  # noqa: E402
from Working.types import WindowSet  # noqa: E402

discover_adapters()


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    return ck.write_model_set(str(tmp_path_factory.mktemp("cnn_models")))


def drop_and_recovery(u):
    """A slow drop and recovery on u ∈ [0, 1]: a fall to -1 by u = 0.35, then an exponential climb back."""
    u = np.asarray(u, dtype=float)
    fall = -np.clip(u / 0.35, 0, 1) ** 2
    climb = np.where(u > 0.35, (1 - np.exp(-(u - 0.35) / 0.15)), 0.0)
    return fall + climb


def random_walk(n, seed=0):
    x = np.cumsum(np.random.default_rng(seed).standard_normal(n))
    return x - np.linspace(x[0], x[-1], n)


# ── resampling ──────────────────────────────────────────────────────────────

def test_resampling_to_the_window_length_is_the_identity():
    w = random_walk(600)
    np.testing.assert_array_equal(WS.resample_window(w, 600), w)


@pytest.mark.parametrize("L", [60, 480, 3600, 2880, 36000, 36001])
def test_every_window_length_reaches_600_points(L):
    assert len(WS.resample_window(random_walk(L), 600)) == 600


@pytest.mark.parametrize("L", [60, 480, 3600, 2880, 36000, 36001])
def test_a_known_waveform_keeps_its_shape(L):
    """A slow drop and recovery sampled at L points and resampled to 600 matches its analytic 600-point
    version (correlation > 0.99), whether the window was stretched (60, 480), squeezed by a whole multiple
    (3600, 36000) or by an awkward ratio (2880 = 4.8 × 600, 36001)."""
    got = WS.resample_window(drop_and_recovery(np.linspace(0, 1, L)), 600)
    want = drop_and_recovery(np.linspace(0, 1, 600))
    assert np.corrcoef(got, want)[0, 1] > 0.99


@pytest.mark.parametrize("L", [3600, 3601])
def test_downsampling_is_anti_aliased(L):
    """A ripple faster than the 600-point grid can carry (period 6.5 samples of a 3600-sample window, i.e.
    about 1.1 cycles per output point) must not survive as a slow false wave. Picking or interpolating
    samples (np.interp) would keep most of its amplitude; block means and a polyphase low-pass remove it."""
    n = np.arange(L)
    ripple = np.sin(2 * np.pi * n / 6.5)
    out = WS.resample_window(ripple, 600)
    assert np.std(out[5:-5]) < 0.2 * np.std(ripple)


def test_downsampling_does_not_droop_at_the_window_edges():
    """A level window stays level at its edges (a zero-padded low-pass would pull the ends toward 0 and draw
    a false drop at both sides of every window)."""
    level = np.full(36001, 5.0) + 1e-3 * np.random.default_rng(0).standard_normal(36001)
    out = WS.resample_window(level, 600)
    assert np.abs(out - 5.0).max() < 0.01


# ── the pixels the model sees ───────────────────────────────────────────────

@pytest.mark.parametrize("image_type", WS.IMAGE_TYPES)
def test_a_600_sample_window_gives_the_window_images_pixels(image_type):
    """Same pixels as training: for a 600-sample window at 1 Hz the image equals `catalogue.window_images`'
    image, and resample_to 600 and 0 agree when L = 600."""
    x = random_walk(1200, seed=3)
    ws = WindowSet(starts=np.array([0, 600]), length=600, fs=1.0, features=pd.DataFrame({"split": [0, 0]}))
    imgs = get_adapter("catalogue.window_images")
    stack = imgs.run(x, None, 1.0, value=ws, **imgs.validate_params({"image_type": image_type})).value.values
    for i, s in enumerate((0, 600)):
        mine = np.asarray(WS.window_image(x[s:s + 600], image_type, img_size=224, resample_to=600))
        as_is = np.asarray(WS.window_image(x[s:s + 600], image_type, img_size=224, resample_to=0))
        np.testing.assert_array_equal(mine, stack[i])
        np.testing.assert_array_equal(as_is, stack[i])


@pytest.mark.parametrize("image_type", ["GASF", "GADF", "recurrence"])
def test_the_grey_training_transform_equals_the_rgb_one_on_these_images(image_type):
    """Training used `get_transforms(is_rgb=False)` for the single-channel types and `catalogue.cnn_score`
    uses `is_rgb=True` for everything: on an L → RGB image (three equal channels) both give the same tensor."""
    from Working.Catalogue.cnn.cnn_rangapur import get_transforms
    img = WS.window_image(random_walk(600, seed=4), image_type, img_size=224, resample_to=600)
    a = get_transforms(224, is_train=False, is_rgb=False)(img)
    b = get_transforms(224, is_train=False, is_rgb=True)(img)
    assert torch.equal(a, b)


@pytest.mark.parametrize("L", [60, 3600, 36000])
def test_every_window_reaches_the_encoder_as_600_points(models, monkeypatch, L):
    seen = []
    real = WS._pil

    def spy(w, image_type):
        seen.append(len(w))
        return real(w, image_type)

    monkeypatch.setattr(WS, "_pil", spy)
    x = random_walk(3 * L, seed=5)
    probs, meta = WS.score_windows(x, np.array([0, L, 2 * L]), L, image_type="fusion", model_path=models["fusion3"],
                                   img_size=32)
    assert seen == [600, 600, 600]
    assert meta["resample_to"] == 600 and meta["window_length"] == L
    assert meta["resample_factor"] == pytest.approx(600 / L)
    assert np.isfinite(probs).all()


# ── the score ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("image_type,key", [("fusion", "fusion3"), ("GADF", "gadf")])
def test_the_score_equals_cnn_score_on_the_same_checkpoint(models, image_type, key):
    """One implementation: Window images → CNN score and this block give the same P(interesting) for
    600-sample windows."""
    x = random_walk(1800, seed=6)
    starts = np.array([0, 600, 1200])
    ws = WindowSet(starts=starts, length=600, fs=1.0, features=pd.DataFrame({"split": [0, 0, 0]}))
    imgs = get_adapter("catalogue.window_images")
    stack = imgs.run(x, None, 1.0, value=ws, **imgs.validate_params({"image_type": image_type})).value
    cnn = get_adapter("catalogue.cnn_score")
    theirs = cnn.run(x, None, 1.0, value=stack, windows=ws,
                     **cnn.validate_params({"model_path": models[key]})).meta["window_scores"]
    mine, _ = WS.score_windows(x, starts, 600, image_type=image_type, model_path=models[key])
    np.testing.assert_allclose(mine, theirs, rtol=0, atol=1e-6)
    assert np.all((mine > 0) & (mine < 1))


def test_positive_class_one_is_the_complement(models):
    x = random_walk(1200, seed=7)
    p0, _ = WS.score_windows(x, np.array([0, 600]), 600, image_type="fusion", model_path=models["fusion3"], img_size=64)
    p1, m1 = WS.score_windows(x, np.array([0, 600]), 600, image_type="fusion", model_path=models["fusion3"],
                              img_size=64, positive_class=1)
    np.testing.assert_allclose(p0 + p1, 1.0, atol=1e-6)
    assert m1["positive_class"] == 1 and m1["n_classes"] == 2


# ── refusals ────────────────────────────────────────────────────────────────

def _score(path, image_type="fusion", **kw):
    x = random_walk(600)
    return WS.score_windows(x, np.array([0]), 600, image_type=image_type, model_path=path, img_size=32, **kw)


def test_a_one_class_checkpoint_is_refused_naming_the_file_and_the_count(models):
    with pytest.raises(ValueError, match=r"(?s)fusion_cnn\.pth.*\b1 output class"):
        _score(models["one_class"])


def test_a_fourteen_class_checkpoint_is_refused_naming_the_file_and_the_count(models):
    with pytest.raises(ValueError, match=r"(?s)fusion_prediction_cnn\.pth.*\b14 output classes"):
        _score(models["fourteen"])


@pytest.mark.parametrize("bad", [2, -1])
def test_a_positive_class_out_of_range_is_refused(models, bad):
    with pytest.raises(ValueError, match=r"(?s)positive_class.*2 classes"):
        _score(models["fusion3"], positive_class=bad)


def test_a_checkpoint_named_for_another_image_type_is_refused(models):
    with pytest.raises(ValueError, match=r"(?s)GADF_cnn\.pth.*gadf.*fusion"):
        _score(models["gadf"], image_type="fusion")
    with pytest.raises(ValueError, match=r"(?s)fusion_cnn_3\.pth.*fusion.*recurrence"):
        _score(models["fusion3"], image_type="recurrence")


def test_a_file_name_that_names_no_image_type_is_accepted(models, tmp_path):
    neutral = ck.write_checkpoint(str(tmp_path / "model_v7.pth"), 2)
    probs, _ = _score(neutral, image_type="GASF")
    assert np.isfinite(probs).all()


def test_a_missing_checkpoint_is_refused():
    with pytest.raises(ValueError, match=r"(?s)no_such_cnn\.pth.*does not exist"):
        _score(os.path.join("nowhere", "no_such_cnn.pth"))


def test_an_unknown_image_type_and_a_tiny_resample_target_are_refused(models):
    with pytest.raises(ValueError, match="image_type"):
        _score(models["fusion3"], image_type="spectrogram")
    with pytest.raises(ValueError, match="resample_to"):
        _score(models["fusion3"], resample_to=8)


def test_as_is_refuses_a_window_too_long_to_encode(models):
    """resample_to = 0 keeps the window's own length; a 36,000-sample window would be a 10 GB matrix."""
    x = random_walk(3000)
    with pytest.raises(ValueError, match=r"(?s)3000.*2048"):
        WS.score_windows(x, np.array([0]), 3000, image_type="GASF", model_path=models["gasf"], resample_to=0)


def test_a_window_outside_the_span_is_refused(models):
    x = random_walk(1000)
    with pytest.raises(ValueError, match="past the span"):
        WS.score_windows(x, np.array([0, 600]), 600, image_type="fusion", model_path=models["fusion3"])


# ── left out, counted ───────────────────────────────────────────────────────

def test_nan_and_flat_windows_score_nan_and_are_counted_by_reason(models):
    x = random_walk(3000, seed=8)
    x[700] = np.nan                     # window 1 holds a gap
    x[1200:1800] = 0.25                 # window 2 is flat
    probs, meta = WS.score_windows(x, np.arange(0, 3000, 600), 600, image_type="GASF", model_path=models["gasf"],
                                   img_size=64)
    assert np.isnan(probs[1]) and np.isnan(probs[2])
    assert np.isfinite(probs[[0, 3, 4]]).all()
    assert meta["skipped"] == {"nan": 1, "flat": 1}
    assert meta["n_windows"] == 5 and meta["n_scored"] == 3
    assert any("flat" in r["rule"] for r in meta["rules"])


def test_an_empty_window_set_scores_nothing_and_says_why(models):
    probs, meta = WS.score_windows(random_walk(100), np.array([], dtype=np.int64), 600, image_type="fusion",
                                   model_path=models["fusion3"])
    assert probs.shape == (0,)
    assert meta["n_windows"] == 0 and meta["n_scored"] == 0
    assert "no window" in meta["note"].lower()


# ── memory, cancel, progress ────────────────────────────────────────────────

def test_twenty_thousand_windows_never_hold_more_than_one_batch_of_images(monkeypatch):
    """At most `batch_size` images exist at once: the network is handed batches no larger than batch_size,
    and every image encoded is consumed by the next forward pass before more are made."""
    net = ck.tiny_net()
    encoded_since_forward = []
    count = {"n": 0}
    real_pil, real_forward = WS._pil, net.forward

    def spy_pil(w, image_type):
        count["n"] += 1
        return real_pil(w, image_type)

    def spy_forward(batch):
        encoded_since_forward.append(count["n"])
        count["n"] = 0
        return real_forward(batch)

    monkeypatch.setattr(WS, "_pil", spy_pil)
    net.forward = spy_forward
    n, L = 20_000, 16
    x = np.sin(np.arange(n * L) / 3.0) + 0.01 * np.arange(n * L) % 1.7
    probs, meta = WS.score_windows(x, np.arange(0, n * L, L), L, image_type="GADF", model_path="tiny.pth",
                                   resample_to=16, img_size=8, batch_size=64, model=net)
    assert len(probs) == n and np.isfinite(probs).all()
    assert max(s[0] for s in net.shapes) <= 64
    assert sum(s[0] for s in net.shapes) == n
    assert max(encoded_since_forward) <= 64
    assert meta["n_scored"] == n


def test_progress_fires_once_a_batch_and_a_cancel_between_batches_stops_the_run():
    from Working.execution import RecipeCancelled
    x = random_walk(16 * 100, seed=9)
    starts = np.arange(0, 16 * 100, 16)
    calls = []
    WS.score_windows(x, starts, 16, image_type="GASF", model_path="tiny.pth", resample_to=16, img_size=8,
                     batch_size=32, model=ck.tiny_net(), on_progress=lambda d, t, s: calls.append((d, t)))
    assert calls == [(1, 4), (2, 4), (3, 4), (4, 4)]

    net = ck.tiny_net()
    asked = {"n": 0}

    def cancel_after_two():
        asked["n"] += 1
        return asked["n"] > 2

    with pytest.raises(RecipeCancelled, match="2 of 4"):
        WS.score_windows(x, starts, 16, image_type="GASF", model_path="tiny.pth", resample_to=16, img_size=8,
                         batch_size=32, model=net, should_cancel=cancel_after_two)
    assert len(net.shapes) == 2


# ── no network ──────────────────────────────────────────────────────────────

def test_loading_a_checkpoint_never_downloads(models, monkeypatch):
    from torchvision.models._api import WeightsEnum

    def no_download(*a, **k):
        raise RuntimeError("download attempted")

    monkeypatch.setattr(WeightsEnum, "get_state_dict", no_download)
    monkeypatch.setattr(torch.hub, "load_state_dict_from_url", no_download)
    model, n_classes = WS.load_scorer(models["fusion3"], "fusion")
    assert n_classes == 2
    probs, _ = _score(models["fusion3"])
    assert np.isfinite(probs).all()


def test_eeg_cnn_still_builds_pretrained_by_default_and_not_when_told(monkeypatch):
    """Training is untouched (the default still asks for ImageNet weights); `pretrained=False` asks for none."""
    from torchvision.models._api import WeightsEnum
    from Working.Catalogue.cnn.cnn_rangapur import EEG_CNN

    class Asked(Exception):
        pass

    def asked(*a, **k):
        raise Asked()

    monkeypatch.setattr(WeightsEnum, "get_state_dict", asked)
    with pytest.raises(Asked):
        EEG_CNN(num_classes=2)
    net = EEG_CNN(num_classes=2, pretrained=False)
    assert net.backbone.classifier[1].out_features == 2


# ── meta ────────────────────────────────────────────────────────────────────

def test_meta_carries_the_scale_and_the_distribution(models):
    x = random_walk(3600, seed=10)
    probs, meta = WS.score_windows(x, np.arange(0, 3600, 60), 60, image_type="recurrence",
                                   model_path=models["recurrence"], img_size=32)
    for k in ("model_path", "n_classes", "positive_class", "image_type", "resample_to", "resample_factor",
              "window_length", "n_windows", "n_scored", "skipped", "window_scores", "p_range", "p_quantiles",
              "seconds_per_window", "training_scale", "rules"):
        assert k in meta, k
    assert meta["n_windows"] == 60 and len(meta["window_scores"]) == 60
    assert meta["p_range"] == [pytest.approx(np.nanmin(probs)), pytest.approx(np.nanmax(probs))]
    assert set(meta["p_quantiles"]) == {"5", "50", "95"}
    assert "600" in meta["training_scale"] and "M2_aug" in meta["training_scale"]
    assert "out-of-sample" in meta["training_scale"]
    assert meta["seconds_per_window"] > 0
    assert any(r["name"] == "resampling" for r in meta["rules"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

"""
test_adapter_cnn_score.py
===========================
`catalogue.window_images` (WindowSet → image stack) and `catalogue.cnn_score`
(image stack + windows → Scores). The stack test is pure numpy/PIL; the
inference test needs torch and scores with a random-weight two-class
checkpoint written to a temp directory (`tests/_cnn_checkpoints.py`).

W4-A: this test used to score with `MODELS/fusion_cnn.pth`, which has ONE
output class, so every window scored 1.0 and the test could not tell. A
one-class checkpoint is now refused (`Working.Catalogue.cnn.window_scores`),
so the test brings its own two-class checkpoint and runs without `MODELS/`
or the cached ImageNet weights (loading builds the network unpretrained).

Runnable standalone:  python tests/test_adapter_cnn_score.py
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

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import Encoding, WindowSet  # noqa: E402

discover_adapters()


def windows(n=3, L=64, fs=1.0):
    x = np.sin(np.linspace(0, 20, n * L)) + 0.05 * np.random.default_rng(0).standard_normal(n * L)
    ws = WindowSet(starts=np.arange(0, n * L, L), length=L, fs=fs, features=pd.DataFrame({"split": [0] * n}))
    return x, ws


def test_cnn_score_registered_with_the_windows_side_input():
    spec = get_adapter("catalogue.cnn_score")
    assert spec.input_kind == "encoding" and spec.output_kind == "scores"
    assert [s.name for s in spec.side_inputs] == ["windows"]
    assert spec.category == "model"


def test_cnn_score_refuses_a_missing_stack_windows_or_checkpoint():
    spec = get_adapter("catalogue.cnn_score")
    x, ws = windows()
    stack = Encoding(values=np.zeros((3, 8, 8, 3), dtype=np.uint8), kind="image")
    with pytest.raises(ValueError, match="Window images"):
        spec.run(x, None, 1.0, **spec.validate_params({}))
    with pytest.raises(ValueError, match="windows"):
        spec.run(x, None, 1.0, value=stack, **spec.validate_params({}))
    with pytest.raises(ValueError, match="does not exist"):
        spec.run(x, None, 1.0, value=stack, windows=ws, **spec.validate_params({"model_path": "no/such.pth", "img_size": 8}))


def test_cnn_score_lays_probabilities_onto_the_time_axis(tmp_path):
    pytest.importorskip("torch")
    import _cnn_checkpoints as ck
    ckpt = ck.write_checkpoint(str(tmp_path / "fusion_cnn_3.pth"), 2)
    x, ws = windows(n=2, L=64)
    imgs = get_adapter("catalogue.window_images")
    stack = imgs.run(x, None, 1.0, value=ws, **imgs.validate_params({"img_size": 224})).value
    spec = get_adapter("catalogue.cnn_score")
    r = spec.run(x, None, 1.0, value=stack, windows=ws, **spec.validate_params({"model_path": ckpt}))
    v = r.value.values
    assert len(v) == len(x) and np.isfinite(v).all()
    assert (v[:64] == v[0]).all() and (v[64:] == v[64]).all()
    assert 0.0 <= v.min() and v.max() <= 1.0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

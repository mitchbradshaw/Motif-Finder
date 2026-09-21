"""
test_adapter_window_images.py
===============================
`catalogue.window_images` — WindowSet → Encoding image stack (n, H, W, 3), the
stack `catalogue.cnn_score` consumes; the starts are channel-absolute.

Runnable standalone:  python tests/test_adapter_window_images.py
"""

import glob
import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.types import Encoding, WindowSet  # noqa: E402

discover_adapters()
CKPT = os.path.join(PROJECT_ROOT, "MODELS", "fusion_cnn.pth")
HUB = glob.glob(os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "checkpoints", "efficientnet_b0*"))


def windows(n=3, L=64, fs=1.0):
    x = np.sin(np.linspace(0, 20, n * L)) + 0.05 * np.random.default_rng(0).standard_normal(n * L)
    ws = WindowSet(starts=np.arange(0, n * L, L), length=L, fs=fs, features=pd.DataFrame({"split": [0] * n}))
    return x, ws


def test_window_images_registered_and_builds_the_stack():
    spec = get_adapter("catalogue.window_images")
    assert spec.input_kind == "windowset" and spec.output_kind == "encoding"
    x, ws = windows()
    r = spec.run(x, None, 1.0, value=ws, **spec.validate_params({"img_size": 32}))
    assert r.value.kind == "image" and r.value.values.shape == (3, 32, 32, 3) and r.value.values.dtype == np.uint8
    assert r.value.values.std() > 0


def test_window_images_refuses_too_many_windows_with_the_size():
    spec = get_adapter("catalogue.window_images")
    x, ws = windows(n=5)
    with pytest.raises(ValueError, match="MB"):
        spec.run(x, None, 1.0, value=ws, **spec.validate_params({"img_size": 32, "max_windows": 2}))


def test_window_images_subtracts_the_spans_offset_from_absolute_starts():
    spec = get_adapter("catalogue.window_images")
    x, ws = windows(n=2, L=64)
    span_start = 1000
    ws_abs = WindowSet(starts=ws.starts + span_start, length=ws.length, fs=ws.fs, features=ws.features)
    t = np.arange(span_start, span_start + len(x)) / 1.0
    r = spec.run(x, t, 1.0, value=ws_abs, **spec.validate_params({"img_size": 16}))
    ref = spec.run(x, None, 1.0, value=ws, **spec.validate_params({"img_size": 16}))
    assert np.array_equal(r.value.values, ref.value.values)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

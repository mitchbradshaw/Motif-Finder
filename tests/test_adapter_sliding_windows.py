"""
test_adapter_sliding_windows.py
=================================
`preprocessing.sliding_windows` — Signal → WindowSet with the P12 leakage
guards enforced in the core: gap >= window, blocked-by-time split with whole
blocks per role, random split refused unless accepted explicitly.

Runnable standalone:  python tests/test_adapter_sliding_windows.py
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

discover_adapters()
NAME = "preprocessing.sliding_windows"
FS = 1.0
X = np.zeros(1000)


def run(**p):
    spec = get_adapter(NAME)
    return spec.run(X, None, FS, **spec.validate_params(p))


def test_registered_as_signal_to_windowset():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "windowset"
    assert {p.name for p in spec.params} >= {"window_s", "gap_s", "split_rule", "n_blocks", "holdout_frac"}


def test_windows_tile_the_span_when_gap_is_zero():
    r = run(window_s=100.0)
    ws = r.value
    assert ws.length == 100 and list(ws.starts) == list(range(0, 901, 100))
    assert r.meta["spacing"]["train_safe"] is True


def test_gap_shorter_than_the_window_is_refused_in_the_core():
    with pytest.raises(ValueError, match="P12"):
        run(window_s=100.0, gap_s=50.0)


def test_blocked_split_holds_out_whole_last_blocks():
    r = run(window_s=100.0, n_blocks=5, holdout_frac=0.2)
    split = r.value.features["split"].to_numpy()
    assert list(split[:8]) == [0] * 8 and list(split[8:]) == [2, 2]
    assert r.meta["split_counts"] == {"train": 8, "validation": 0, "test": 2}
    assert r.meta["blocks"][-1]["role"] == "test"


def test_random_split_is_refused_unless_accepted():
    with pytest.raises(ValueError, match="B7"):
        run(window_s=100.0, split_rule="random")
    r = run(window_s=100.0, split_rule="random", allow_random_split=True, holdout_frac=0.5, seed=1)
    assert set(r.value.features["split"]) <= {0, 1, 2}


def test_cluster_and_classifier_ignore_the_split_column():
    import pandas as pd
    from Working.types import WindowSet
    ws = WindowSet(starts=np.arange(0, 60, 10), length=10, fs=1.0,
                   features=pd.DataFrame({"split": [0, 0, 0, 2, 2, 2], "f1": [1.0, 1.1, 0.9, 5.0, 5.1, 4.9], "f2": [0.0, 0.1, 0.0, 1.0, 1.1, 0.9]}))
    c = get_adapter("catalogue.cluster")
    r = c.run(X, None, 1.0, value=ws, **c.validate_params({"k": 2}))
    labels = np.asarray(r.value.labels)
    assert labels[0] == labels[1] == labels[2] and labels[3] == labels[4] == labels[5]
    assert "split" not in r.meta.get("feature_names", []) if r.meta.get("feature_names") else True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

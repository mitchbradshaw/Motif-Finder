"""
test_spanset_features.py
==========================
`SpanSet.features` (fixup-d, seam 1): an optional per-span feature table,
mirroring `WindowSet.features` exactly — one row per span, parquet beside the
JSON, frames compared by `__eq__`. No eighth interchange type: the feature
blocks are `SpanSet -> SpanSet` and carry their measures here.

The regression risk is every existing caller, which builds a SpanSet with no
features at all; those must keep constructing, serialising and comparing
exactly as they did.

Runnable standalone:  python tests/test_spanset_features.py
"""

import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.types import SpanSet  # noqa: E402


def _frame(n=2):
    return pd.DataFrame({"event_amplitude_mv": np.arange(n, dtype=float) + 1.5,
                         "event_width_s": np.linspace(2.0, 3.0, n)})


def test_features_default_to_none_and_old_callers_still_construct():
    s = SpanSet(starts=(1, 5), ends=(3, 9), labels=("a", "b"), scores=(0.5, 1.0))
    assert s.features is None
    positional = SpanSet((1,), (2,), ("x",), (0.1,))
    assert positional.features is None


def test_one_feature_row_per_span_is_enforced():
    with pytest.raises(ValueError, match="one feature row per span"):
        SpanSet(starts=(1, 5), ends=(3, 9), features=_frame(3))


def test_a_spanset_with_features_round_trips_through_disk():
    s = SpanSet(starts=(1, 5), ends=(3, 9), labels=("a", "b"), scores=(0.5, 1.0), features=_frame())
    with tempfile.TemporaryDirectory() as d:
        s.to_path(d)
        assert os.path.isfile(os.path.join(d, "features.parquet"))
        back = SpanSet.from_path(d)
    assert back == s
    pd.testing.assert_frame_equal(back.features.reset_index(drop=True), s.features.reset_index(drop=True))


def test_a_spanset_without_features_writes_no_parquet_and_reads_back_none():
    s = SpanSet(starts=(1, 5), ends=(3, 9))
    with tempfile.TemporaryDirectory() as d:
        path = s.to_path(d)
        assert not os.path.exists(os.path.join(d, "features.parquet"))
        with open(path) as f:
            assert set(json.load(f)) == {"starts", "ends", "labels", "scores"}
        back = SpanSet.from_path(d)
    assert back.features is None
    assert back == s


def test_equality_compares_the_feature_frames():
    a = SpanSet(starts=(1, 5), ends=(3, 9), features=_frame())
    b = SpanSet(starts=(1, 5), ends=(3, 9), features=_frame())
    assert a == b
    other = _frame(); other.loc[1, "event_width_s"] = 99.0
    assert a != SpanSet(starts=(1, 5), ends=(3, 9), features=other)
    assert a != SpanSet(starts=(1, 5), ends=(3, 9))
    assert SpanSet(starts=(1,), ends=(2,)) == SpanSet(starts=(1,), ends=(2,))
    assert SpanSet(starts=(1,), ends=(2,)) != SpanSet(starts=(1,), ends=(3,))


def test_a_stale_parquet_from_an_earlier_write_is_not_resurrected():
    """The step cache rewrites a directory in place; a feature table left there by an
    earlier write must not attach itself to a SpanSet written without one."""
    with tempfile.TemporaryDirectory() as d:
        SpanSet(starts=(1, 5), ends=(3, 9), features=_frame()).to_path(d)
        SpanSet(starts=(1, 5), ends=(3, 9)).to_path(d)
        assert SpanSet.from_path(d).features is None


def test_existing_spanset_callers_still_run():
    """The adapters that emit a SpanSet today construct it without features."""
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    spec = get_adapter("detection.threshold")
    from Working.types import Scores
    x = np.zeros(100)
    vals = np.zeros(100); vals[40:50] = 10.0
    r = spec.run(x, np.arange(100.0), 1.0, value=Scores(values=vals, fs=1.0), **spec.validate_params({"threshold": 5.0}))
    assert r.value.features is None and len(r.value.starts) >= 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

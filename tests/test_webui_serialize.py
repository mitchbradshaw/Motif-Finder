"""
test_webui_serialize.py
=========================
`webui/server/serialize.py::to_payload`, the one server-side seam over the
seven types, exercised directly (the contract critic found it had no direct
tests): the 4-D image-stack contact sheet, the empty stack, the symbolic
strip using the encoder's own letters, and the SpanSet offset.

No FastAPI needed; runs under the conda pytest.

Runnable standalone:  python tests/test_webui_serialize.py
"""

import base64
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from server.serialize import STACK_TILES, to_payload  # noqa: E402
from Working.types import Encoding, SpanSet  # noqa: E402


def test_a_4d_image_stack_ships_a_contact_sheet_with_n_images():
    stack = np.random.default_rng(0).integers(0, 255, size=(7, 32, 32, 3), dtype=np.uint8)
    p = to_payload("encoding", Encoding(values=stack, kind="image"), {}, {"fs": 1.0})
    assert p["kind"] == "image" and p["ndim"] == 4 and p["n_images"] == 7 and p["shape"] == [7, 32, 32, 3]
    assert p["pixels_b64"] and p["channels"] == 3
    rows, cols = p["display_shape"]
    assert rows >= 32 and cols >= 32 and "contact sheet" in p["summary"]


def test_a_stack_larger_than_the_tile_cap_shows_only_the_first_tiles():
    stack = np.zeros((STACK_TILES + 5, 8, 8, 3), dtype=np.uint8)
    p = to_payload("encoding", Encoding(values=stack, kind="image"), {}, {"fs": 1.0})
    assert p["n_images"] == STACK_TILES + 5 and f"first {STACK_TILES}" in p["summary"]


def test_an_empty_stack_is_a_payload_not_a_traceback():
    p = to_payload("encoding", Encoding(values=np.zeros((0, 32, 32, 3), dtype=np.uint8), kind="image"), {}, {"fs": 1.0})
    assert p["n_images"] == 0 and "empty" in p["summary"] and "pixels_b64" not in p


def test_symbolic_strip_uses_the_encoders_own_letters_when_given():
    syms = np.array([2, 3, 4, 0, 1, 2])
    p = to_payload("encoding", Encoding(values=syms, kind="symbolic"),
                   {"letters": "SUudDS", "alphabet": "dDSUu", "details": {"samples_per_symbol": 10, "alphabet_size": 5}}, {"fs": 1.0, "n_samples": 60})
    assert p["letters"] == "SUudDS" and p["alphabet"] == "dDSUu" and p["alphabet_size"] == 5
    q = to_payload("encoding", Encoding(values=syms, kind="symbolic"), {}, {"fs": 1.0, "n_samples": 60})
    assert q["letters"] == "cdeabc"


def test_spanset_payload_adds_the_spans_offset():
    p = to_payload("spanset", SpanSet(starts=(10, 40), ends=(20, 50), labels=("a", "b")), {}, {"fs": 2.0, "span_start": 100})
    assert p["start_s"] == [55.0, 70.0] and p["end_s"] == [60.0, 75.0]
    e = to_payload("spanset", SpanSet(starts=(), ends=()), {}, {"fs": 1.0})
    assert e["n"] == 0 and "threshold" not in e["summary"]


# ----------------------------------------------- a sparse image (fixup-a 1) --
# `preprocessing.wavelet_transform` leaves roughly half its columns NaN by
# design (a chunk is falling-edge -> next rising-edge, so every rising -> next
# falling interval is never covered). Block-averaging that with `.mean()` makes
# every output cell NaN as soon as the block factor is > 1, which is the case on
# every real span: the image goes black and `value_range` reports [0, 1], a
# number that is not true of the data. The existing tests cannot see it because
# they all use a 300-sample synthetic where the block factor is 1.

def _sparse(h=64, w=1200, lo=10.0, hi=20.0, seed=3):
    """A wide image with every other column NaN — the Dehshibi pattern."""
    vals = np.random.default_rng(seed).uniform(lo, hi, size=(h, w))
    vals[:, 1::2] = np.nan
    return vals


def _pixels(p):
    return np.frombuffer(base64.b64decode(p["pixels_b64"]), dtype=np.uint8)


def test_a_wide_image_with_nan_columns_still_paints_its_finite_values():
    vals = _sparse()
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0})
    assert p["display_shape"][1] < vals.shape[1], "the block factor must be > 1 or this test proves nothing"
    assert p["value_range"] is not None, "half the columns are finite; the range is knowable"
    lo, hi = p["value_range"]
    assert 10.0 <= lo < hi <= 20.0, f"range {p['value_range']} is not the data's range"
    assert _pixels(p).max() > 0, "the image painted uniform black over finite data"


def test_an_all_nan_block_is_marked_rather_than_painted_as_a_value():
    vals = np.random.default_rng(4).uniform(10.0, 20.0, size=(64, 512))
    vals[:, 10:12] = np.nan          # exactly one output cell column (block width 2)
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0})
    rows, cols = p["display_shape"]
    assert p["nan_cells"] == rows, f"one blanked column of {rows} cells should be marked, got {p['nan_cells']}"
    assert p["all_nan"] is False
    mask = np.frombuffer(base64.b64decode(p["nan_b64"]), dtype=np.uint8).reshape(rows, cols)
    assert mask[:, 5].all() and mask.sum() == rows, "the mask must name the blank cells and only those"


def test_an_entirely_nan_image_says_so_in_words_instead_of_claiming_a_range():
    vals = np.full((64, 512), np.nan)
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0})
    assert p["all_nan"] is True
    assert p["value_range"] is None, "there is no range; [0, 1] would be a claim about data that is not there"
    assert "no finite" in p["summary"].lower(), f"the payload must say so in words: {p['summary']!r}"


def test_a_capped_grouping_says_so_in_its_summary():
    """fixup-a item 10: `serialize.py` ships `labels[:5000]` with
    `capped: true` and `GroupingR` never surfaced it, so past 5,000 windows the
    colour strip truncated in silence."""
    from Working.types import Grouping
    labels = np.arange(6000) % 3
    p = to_payload("grouping", Grouping(labels=labels), {}, {"fs": 1.0})
    assert p["capped"] is True and len(p["labels"]) == 5000
    assert p["n_shown"] == 5000
    assert "5,000" in p["summary"] and "6,000" in p["summary"], p["summary"]


# ------------------------------------------- a SpanSet with features (fixup-d) --
# `SpanSet.features` is a new shape inside the SpanSet type: the feature blocks
# (`interrogation.event_shape`, `interrogation.intervals`) carry one row of
# measures per span. The payload ships them the way a WindowSet ships its own
# (columns, a capped matrix, per-column ranges), and passes the blocks' printed
# rules, the rose and the interval statistics through from `meta`, so the page
# draws the measurement it was given and never re-derives one.

def test_a_spanset_with_features_ships_the_feature_table():
    import pandas as pd
    feats = pd.DataFrame({"polarity": [-1, 1], "event_amplitude_mv": [10.0, 4.5], "recovery_time_s": [3.5, np.nan]})
    ss = SpanSet(starts=(10, 40), ends=(20, 50), features=feats)
    meta = {"rules": [{"name": "recovery", "rule": "half recovery"}],
            "rose": {"n": 2, "counts": [0] * 18, "bin_centres_deg": list(range(18)), "caption": "45° = 1 mV/s"},
            "interval_stats": {"all": {"n_events": 2, "cv": None}}, "events": "not passed through"}
    p = to_payload("spanset", ss, meta, {"fs": 2.0, "span_start": 100})
    f = p["features"]
    assert f["columns"] == ["polarity", "event_amplitude_mv", "recovery_time_s"] and f["n_columns"] == 3
    assert f["matrix"] == [[-1.0, 10.0, 3.5], [1.0, 4.5, None]]
    assert f["col_range"][2] == [3.5, 3.5]
    assert p["rules"] == meta["rules"] and p["rose"]["caption"] == "45° = 1 mV/s"
    assert p["interval_stats"] == {"all": {"n_events": 2, "cv": None}}
    assert "events" not in p
    assert "3 features" in p["summary"]


def test_a_spanset_without_features_says_none_and_nothing_else_changes():
    p = to_payload("spanset", SpanSet(starts=(10,), ends=(20,)), {}, {"fs": 1.0})
    assert p["features"] is None
    assert "rules" not in p and "rose" not in p
    assert "features" not in p["summary"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

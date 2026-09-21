"""
test_discovery_window_chain.py
================================
Prompt 04 / spec §7.8 — "the same window pushed through both runs".
`Working.discovery.window_chain.run_window` runs a recipe's steps over one
in-memory window and reports each step, writing no run row. What is under
test is that a step sees what it would see in a real run (the same typed
values, the same side-input resolution) and that a step which blows up is
*recorded* rather than propagated — the loud-failure contract the
Compare-every-stage page draws a stage card from.

Run from the project root:
    pytest tests/test_discovery_window_chain.py
"""

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
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q
from Working.database.schema import init_db
from Working.discovery.window_chain import run_window
from Working.recipes import make_recipe


FS = 1.0
N = 400  # a few hundred samples: the "few tens of seconds" window of §7.8


def _window(seed=0, n=N):
    return np.asarray(np.random.default_rng(seed).standard_normal(n), dtype=float)


def _recipe(steps, recording_id=1):
    # Built through make_recipe so the side-input bindings are normalised
    # exactly as a real recipe's are.
    return make_recipe(recording_id, steps, span=(0, N))


def test_two_step_chain_returns_one_ok_entry_per_step_with_the_declared_kinds():
    recipe = _recipe([
        {"stage": "preprocessing", "algorithm": "lowpass",
         "params": {"cutoff_hz": 0.05}},
        {"stage": "detection", "algorithm": "matrix_profile",
         "params": {"window_min": 0.2}},
    ])

    entries = run_window(None, recipe, _window(), FS)

    assert [e["index"] for e in entries] == [0, 1]
    assert all(e["ok"] for e in entries), [e["error"] for e in entries]
    assert [e["kind"] for e in entries] == ["signal", "scores"]
    assert [e["algorithm"] for e in entries] == \
        ["preprocessing.lowpass", "detection.matrix_profile"]
    assert entries[0]["value"].x.shape == (N,)
    assert entries[1]["value"].values.shape == (N,)
    assert entries[0]["error"] is None


def test_a_step_that_cannot_work_on_a_short_window_is_recorded_not_raised():
    # window_min=10 minutes at fs=1 Hz is a 600-sample window over a
    # 400-sample span: the adapter refuses. The chain must report it.
    recipe = _recipe([
        {"stage": "preprocessing", "algorithm": "lowpass",
         "params": {"cutoff_hz": 0.05}},
        {"stage": "detection", "algorithm": "matrix_profile",
         "params": {"window_min": 10.0}},
        {"stage": "detection", "algorithm": "threshold",
         "params": {"threshold": 1.0}},
    ])

    entries = run_window(None, recipe, _window(), FS)

    assert len(entries) == 3
    assert entries[0]["ok"] is True
    assert entries[1]["ok"] is False
    assert entries[1]["error"] and "600" in entries[1]["error"]
    assert entries[1]["value"] is None
    assert entries[2]["ok"] is False
    assert entries[2]["error"] == "skipped: step 1 failed"


def test_earlier_step_side_input_resolves():
    recipe = _recipe([
        {"stage": "preprocessing", "algorithm": "lowpass",
         "params": {"cutoff_hz": 0.05}},
        {"stage": "detection", "algorithm": "seed_matches",
         "params": {"k": 3},
         "side_inputs": {"exemplar": {"source_kind": "earlier_step",
                                      "step_index": 0}}},
    ])

    entries = run_window(None, recipe, _window(), FS)

    assert all(e["ok"] for e in entries), [e["error"] for e in entries]
    assert entries[1]["kind"] == "spanset"
    # The exemplar was the lowpassed signal itself, so its own position is
    # the best match — proof the binding resolved to the earlier step's
    # output rather than to the raw root signal.
    assert entries[1]["value"].starts[0] == 0


def test_library_exemplar_side_input_resolves_off_disk():
    tmpdir = tempfile.mkdtemp(prefix="window_chain_")
    try:
        x = _window(seed=3)
        npy_path = os.path.join(tmpdir, "exemplar.npy")
        np.save(npy_path, x)
        conn = init_db(os.path.join(tmpdir, "test.sqlite"))
        q.insert_recording(conn, "exemplar.mat", 0, FS, len(x), 0, npy_path)

        recipe = _recipe([
            {"stage": "detection", "algorithm": "seed_matches",
             "params": {"k": 3},
             "side_inputs": {"exemplar": {
                 "source_kind": "library_exemplar", "entry_id": 0,
                 "source_file": "exemplar.mat", "channel": 0,
                 "start_idx": 100, "end_idx": 150}}},
        ])

        entries = run_window(conn, recipe, x, FS)

        assert entries[0]["ok"] is True, entries[0]["error"]
        assert entries[0]["kind"] == "spanset"
        # The exemplar is a literal slice of the window, so the match at
        # index 100 is exact — the binding was resolved off disk, not
        # substituted by the root signal.
        assert 100 in [int(s) for s in entries[0]["value"].starts]
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

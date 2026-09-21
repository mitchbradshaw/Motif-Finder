"""
test_adapter_seed_matches.py
==============================
`detection.seed_matches` — Signal + exemplar side input → SpanSet, the block
Discovery's seeded search calls. Direct call, and a real recipe run with a
`library_exemplar` binding through `execute_recipe`.

Runnable standalone:  python tests/test_adapter_seed_matches.py
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

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.recipes import make_recipe  # noqa: E402
from Working.types import Signal  # noqa: E402

discover_adapters()
NAME = "detection.seed_matches"
M = 20


def bursts(n=600, seed=0):
    rng = np.random.default_rng(seed)
    x = 0.1 * rng.standard_normal(n)
    burst = np.sin(np.linspace(0, 4 * np.pi, M))
    for s in (100, 300, 480):
        x[s:s + M] += burst
    return x


def test_registered_with_one_signal_side_input():
    spec = get_adapter(NAME)
    assert spec.input_kind == "signal" and spec.output_kind == "spanset"
    assert [s.name for s in spec.side_inputs] == ["exemplar"]
    assert spec.side_inputs[0].type_kind == "signal"
    assert set(spec.side_inputs[0].sources) >= {"library_exemplar"}


def test_finds_the_planted_copies_closest_first():
    x = bursts()
    spec = get_adapter(NAME)
    r = spec.run(x, None, 1.0, exemplar=Signal(x=x[100:120], fs=1.0), **spec.validate_params({"k": 3}))
    assert r.value.starts[0] == 100 and r.value.scores[0] == pytest.approx(0.0, abs=1e-6)
    assert set(r.value.starts) >= {100, 300}
    assert all(e - s == M for s, e in zip(r.value.starts, r.value.ends))
    assert list(r.value.scores) == sorted(r.value.scores)


def test_refuses_an_unbound_exemplar_and_an_overlong_one():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="exemplar"):
        spec.run(np.zeros(100), None, 1.0, **spec.validate_params({}))
    with pytest.raises(ValueError, match="longer than the span"):
        spec.run(np.zeros(10), None, 1.0, exemplar=Signal(x=np.zeros(20), fs=1.0), **spec.validate_params({}))


def test_runs_through_execute_recipe_with_a_library_exemplar_binding():
    tmp = tempfile.mkdtemp(prefix="seed_matches_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT; cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        db = os.path.join(tmp, "t.sqlite")
        conn = init_db(db)
        x = bursts()
        np.save(os.path.join(tmp, "target.npy"), x)
        q.insert_recording(conn, "target.mat", 0, 1.0, len(x), 0, os.path.join(tmp, "target.npy"))
        ex = np.zeros(200); ex[50:70] = np.sin(np.linspace(0, 4 * np.pi, M))
        np.save(os.path.join(tmp, "ex.npy"), ex)
        q.insert_recording(conn, "ex.mat", 0, 1.0, len(ex), 0, os.path.join(tmp, "ex.npy"))
        conn.close()
        recipe = make_recipe(1, [{
            "stage": "detection", "algorithm": "seed_matches", "params": {"k": 2},
            "side_inputs": {"exemplar": {"source_kind": "library_exemplar", "entry_id": 0,
                                         "source_file": "ex.mat", "channel": 0, "start_idx": 50, "end_idx": 70}},
        }])
        out = execute_recipe(recipe, db_path=db, force=True)
        starts = set(out["result"].value.starts)
        assert starts & {100, 300, 480}
        assert out["detections_written"] == 2
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

"""
test_template_motif_lengths.py
================================
The `motif_lengths` TEMPLATE: baseline removal (rolling mean, 7200 s) ->
`detection.pan_matrix_profile` (30 s -> 1 h, 12 lengths, exact, one null
draw), run end to end through `execute_recipe` in a temporary database. The
manager moves the constant into `webui/server/templates.py::CANONICAL`.

Why a 2 h rolling mean: it must be longer than the longest window (1 h), or
the detrend would carve the 1 h shapes it is meant to leave for the pan
profile to compare — a centred rolling mean of width W removes what changes
over about W and longer, and a 1 h hump under a 1 h mean is half removed.
Twice the longest length keeps an hour's shape mostly intact while still
removing drift over several hours, which would otherwise make every long
window a z-normalised ramp that matches every other (the "smooth shapes"
blind spot).

Runnable standalone:  python tests/test_template_motif_lengths.py
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

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from tests import _pan_synthetic as syn  # noqa: E402

FS = syn.FS

TEMPLATE = {
    "name": "motif_lengths", "kind": "encoding", "version": 1,
    "description": "At which window lengths does anything repeat? Baseline removal (2 h rolling mean, longer "
                   "than the longest window so an hour's shape survives) → the pan matrix profile (Madrid et al. "
                   "2019): the matrix profile at 12 lengths from 30 s to 1 h, one image row per length (longest "
                   "at the top), bright where the window starting there has a close look-alike. Each length is "
                   "compared with three amplitude-adjusted copies of the span (its own values reshuffled: the same "
                   "colour of noise, no shapes); the answer is the band of lengths that repeat beyond them "
                   "('clears from A to B s, strongest at C'). The strongest length is not the event's length: it "
                   "leans long when an event dominates long windows and toward edges on chains — read the band "
                   "and the picture. Tune max_window_s first: a length is judged only when the span is 14 windows "
                   "long (4 h: up to 17 min; 8 h: up to 34 min, so a drop chain's ~30 min unit needs a span of "
                   "24 h or more). 'No length stands out' means nothing repeats more than coloured noise does at "
                   "any tested length — not that nothing happens. Two occurrences must have the same length to "
                   "match, and loudness is ignored (each window is z-normalised).",
    "steps": [
        {"stage": "preprocessing", "algorithm": "detrend",
         "params": {"mode": "rolling_mean", "window_s": 7200.0}},
        {"stage": "detection", "algorithm": "pan_matrix_profile",
         "params": {"min_window_s": 30.0, "max_window_s": 3600.0, "n_lengths": 12, "null_draws": 3,
                    "null": "aaft", "seed": 0, "max_fill_s": 5.0}},
    ],
}


@pytest.fixture
def run_on():
    tmp = tempfile.mkdtemp(prefix="pan_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    counter = {"n": 0}

    def _run(x):
        counter["n"] += 1
        npy = os.path.join(tmp, f"CH{counter['n']}.npy")
        np.save(npy, x)
        db = os.path.join(tmp, f"t{counter['n']}.sqlite")
        conn = init_db(db)
        q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
        conn.close()
        recipe = apply_template(None, TEMPLATE, recording_id=1)
        return execute_recipe(recipe, db_path=db, force=True)

    try:
        yield _run
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_template_is_a_two_step_encoding_chain():
    assert TEMPLATE["kind"] == "encoding"
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "detection.pan_matrix_profile"]
    detrend_s = TEMPLATE["steps"][0]["params"]["window_s"]
    assert detrend_s > TEMPLATE["steps"][1]["params"]["max_window_s"]
    assert "max_window_s" in TEMPLATE["description"] and "No length stands out" in TEMPLATE["description"]
    assert "amplitude-adjusted" in TEMPLATE["description"]
    assert "chain" in TEMPLATE["description"]                     # what an 8 h span cannot judge


def test_the_template_finds_the_planted_lengths_end_to_end(run_on):
    x, _, _ = syn.planted(4 * 3600, seed=0)
    x = x + np.linspace(0.0, 40.0, len(x))                   # a drift the detrend must take away
    out = run_on(x)
    res = out["result"]
    assert res.output_kind == "encoding" and res.value.kind == "image"
    img = res.value.values
    assert img.shape == (12, len(x))
    meta = res.meta
    assert meta["alignment"] == "start"
    s = meta["suggested_window_s"]
    assert s is not None, meta["verdict"]
    cleared = [d["length_s"] for d in meta["per_length"] if d["clears"]]
    # after the 2 h detrend the 90 s motif clears at a neighbouring rung of the ladder (x1.54 apart): 46 s and
    # 171 s on seed 0, so within a factor of 2 of 90 s; the 20 min motif at the 16 min row
    assert any(45 <= v <= 180 for v in cleared), cleared
    assert any(900 <= v <= 1600 for v in cleared), cleared


def test_the_template_on_a_random_walk_says_no_length_stands_out(run_on):
    rng = np.random.default_rng(5)
    x = np.cumsum(rng.standard_normal(4 * 3600))             # raw: the template's detrend does the rest
    out = run_on(x)
    meta = out["result"].meta
    assert meta["suggested_window_s"] is None, [(d["length_s"], d["gap"]) for d in meta["per_length"]]
    assert "no length stands out" in meta["summary"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

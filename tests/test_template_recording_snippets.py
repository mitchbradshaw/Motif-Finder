"""
test_template_recording_snippets.py
=====================================
The `recording_snippets` TEMPLATE (W2-D): baseline removal (rolling mean,
6 h) → sliding windows (1 h, gap 0) → `catalogue.snippets` (k automatic), run
end to end through `execute_recipe` in a temporary database.

Why 6 h for the detrend: the pieces are 1 h and MPdist compares 21-minute
sub-pieces (0.35 × 1 h); a centred rolling mean of width W takes out of the
signal what varies more slowly than about W and flattens shape on that scale,
so W must be several pieces long to leave a piece's own shape alone — 6 h is
six pieces — and short enough to take out drift over half a day or more. On
the drifting synthetic set below (a 20-hour swing of ±3 plus a ramp of 2,
against behaviour of amplitude ~1) the template recovers the three regimes in
every seed tried (0-3), as the block does on the raw recording; detrending is
there for real recordings, whose level wanders more than this.

The template is defined here as a module-level constant; the manager moves it
into `webui/server/templates.py::CANONICAL` after merging (00-common.md).

The synthetic recordings are sampled at 0.1 Hz (`tests/_snippets_synthetic.py`):
every duration is real, only the sample count is ten times smaller than at
1 Hz, so a run takes seconds. Every parameter of the template is in seconds.

Runnable standalone:  python tests/test_template_recording_snippets.py
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

from tests import _snippets_synthetic as syn  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402

FS = syn.FS

TEMPLATE = {
    "name": "recording_snippets", "kind": "training", "version": 1,
    "description": "What kinds of behaviour does this recording hold, and where? Baseline removal (6 h rolling "
                   "mean) → 1-hour pieces → snippets (Imani et al. 2018, matrix profile XIII): the few most "
                   "typical pieces, and every hour coloured by the one it most resembles. k is chosen by the "
                   "paper's knee; k = 1 means no evidence of more than one kind of behaviour. Read the regime "
                   "run lengths beside the labels: a label that flickers hour to hour is not a regime. Costs "
                   "O(n²) — about 25 s for 24 h at 1 Hz; refused above 7 days. Check NaN gaps first: the "
                   "rolling-mean baseline removal spreads a NaN, and windows more than half NaN are left "
                   "unlabelled (−1).",
    "steps": [
        {"stage": "preprocessing", "algorithm": "detrend",
         "params": {"mode": "rolling_mean", "window_s": 21600.0}},
        {"stage": "preprocessing", "algorithm": "sliding_windows",
         "params": {"window_s": 3600.0, "gap_s": 0.0}},
        {"stage": "catalogue", "algorithm": "snippets",
         "params": {"k": 0, "k_max": 6, "subseq_frac": 0.35, "mpdist_percentage": 0.05}},
    ],
}


@pytest.fixture
def run_on():
    tmp = tempfile.mkdtemp(prefix="snippets_tpl_")
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


def test_template_is_a_three_step_training_chain():
    assert [f"{s['stage']}.{s['algorithm']}" for s in TEMPLATE["steps"]] == [
        "preprocessing.detrend", "preprocessing.sliding_windows", "catalogue.snippets"]
    # the kind the chain's terminal type implies (a Grouping -> training)
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    assert get_adapter("catalogue.snippets").output_kind == "grouping"
    assert TEMPLATE["kind"] == "training"


def test_the_description_says_what_it_cannot_do():
    d = TEMPLATE["description"]
    # the rolling-mean detrend is a cumulative sum: one NaN blanks the whole trace
    assert "one missing sample" in d and "whole" in d
    assert "no recording stored today has a gap" in d
    # z-normalised shapes: amplitude-only differences are not separated
    assert "amplitude" in d
    assert "24 h" in d


def test_three_regimes_end_to_end(run_on):
    x, truth = syn.three_regimes(0, with_drift=True)
    out = run_on(x)
    res = out["result"]
    assert res.output_kind == "grouping"
    labels = np.asarray(res.value.labels)
    assert len(labels) == 48
    assert res.meta["k"] == 3, (res.meta["change_k"], res.meta["k_reason"])
    assert syn.agreement(labels, truth) >= 0.9
    assert res.meta["run_length_mean"] >= 6


def test_no_structure_end_to_end(run_on):
    out = run_on(syn.random_walk_null(0))
    res = out["result"]
    assert res.meta["k"] == 1
    assert "no knee" in res.meta["k_reason"]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_template_chain_recovers_the_regimes(seed):
    """The same three blocks run directly (no database), more seeds."""
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    x, truth = syn.three_regimes(seed, with_drift=True)
    t = np.arange(len(x), dtype=float) / FS
    value, meta = None, None
    for step in TEMPLATE["steps"]:
        spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
        kw = spec.validate_params(step["params"])
        res = spec.run(x, t, FS, **kw) if value is None else spec.run(x, t, FS, value=value, **kw)
        if res.output_kind == "signal":
            x = res.value.x
        else:
            value, meta = res.value, res.meta
    assert meta["k"] == 3
    assert syn.agreement(value.labels, truth) >= 0.9


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

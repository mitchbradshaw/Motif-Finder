"""
test_webui_job_estimate.py
==========================
A chain run's job carries the recipe's time estimate from the moment it starts
(the researcher, 2026-10-13: Jobs wants "another column for estimated time, if
available"). The estimate is the one Analyse already computes per step
(`server.chain.estimate`). What it pins:

* a new `Job` snapshot carries `estimate_s`, the recipe's total over its span;
* it is None — not 0 — when a step cannot be estimated on this machine or
  when no step has an estimator at all: a blank column, never a column that
  reads "0 s" for a run that will take an hour;
* a job restored from the jobs table after a restart still has it.
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from server import chain as chain_mod  # noqa: E402
from server import runs as runs_mod  # noqa: E402
from server.jobs import JobManager  # noqa: E402

RECIPE = {"steps": [{"stage": "detection", "algorithm": "matrix_profile", "params": {"window_s": 600}}],
          "span": [0, 36000]}
RECORDING = {"id": 1, "fs": 1.0, "n_samples": 36000, "units": "V"}


def _estimate(total, per_step, unknown):
    return lambda recipe, n_samples, fs: {"total_s": total, "per_step_s": per_step, "unknown": unknown,
                                          "errors": {}, "route": "unknown" if unknown else "local"}


def test_a_new_job_carries_the_recipes_estimate(monkeypatch):
    seen = {}
    def est(recipe, n_samples, fs):
        seen.update(n=n_samples, fs=fs)
        return _estimate(42.0, [42.0], [])(recipe, n_samples, fs)
    monkeypatch.setattr(chain_mod, "estimate", est)
    job = runs_mod.Job(RECIPE, RECORDING, 1200)
    assert job.snapshot()["estimate_s"] == 42.0
    assert seen == {"n": 36000, "fs": 1.0}, "the estimate is over the recipe's span at the recording's rate"


def test_a_job_with_no_span_is_estimated_over_the_whole_recording(monkeypatch):
    seen = {}
    monkeypatch.setattr(chain_mod, "estimate", lambda recipe, n, fs: (seen.update(n=n), _estimate(1.0, [1.0], [])(recipe, n, fs))[1])
    runs_mod.Job({"steps": RECIPE["steps"]}, {**RECORDING, "n_samples": 99}, 1200)
    assert seen["n"] == 99


def test_an_unestimable_step_reads_none_not_zero(monkeypatch):
    monkeypatch.setattr(chain_mod, "estimate", _estimate(0.0, [None], [0]))
    assert runs_mod.Job(RECIPE, RECORDING, 1200).snapshot()["estimate_s"] is None


def test_a_recipe_with_no_estimator_reads_none(monkeypatch):
    monkeypatch.setattr(chain_mod, "estimate", _estimate(0.0, [0.0], []))
    assert runs_mod.Job(RECIPE, RECORDING, 1200).snapshot()["estimate_s"] is None


def test_an_estimator_that_raises_does_not_stop_the_run(monkeypatch):
    def boom(recipe, n, fs):
        raise RuntimeError("uncalibrated")
    monkeypatch.setattr(chain_mod, "estimate", boom)
    assert runs_mod.Job(RECIPE, RECORDING, 1200).snapshot()["estimate_s"] is None


def test_a_restored_job_keeps_its_estimate():
    row = {"id": 7, "kind": "chain_run", "status": "completed", "created_at": "t", "started_at": "t",
           "finished_at": "t", "cancelled": 0, "error_json": None, "run_id": None,
           "meta_json": json.dumps({"recipe": RECIPE, "recording_id": 1, "px": 1200}),
           "progress_json": json.dumps({"steps": [], "n_steps": 1, "estimate_s": 42.0})}
    assert JobManager._from_row(row)["estimate_s"] == 42.0

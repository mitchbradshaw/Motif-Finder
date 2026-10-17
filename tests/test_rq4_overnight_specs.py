"""
test_rq4_overnight_specs.py
===========================
The golden guard of round A_2's P2 (fix round, 2026-10-18): the researcher's overnight RQ4 sweep — 43 chain specs,
674 tasks over M2_aug, tracked under ``HPC/Detection/generated/rq4_overnight/`` — was exported with this branch's
code at 151ace3 and is running on rangpur. Its results must import with whatever code comes after. The import
(`chain_job.verify_results`, `local_plan`) recomputes, from the spec and this machine:

* the spec's hash (each task's result names it; the file name ends with its first six hex; job.json holds it);
* every target's config hash and step-prefix hashes (the cluster asserted the same ones on its scratch database);
* the plan the local sweep runs, whose per-target recipes must be the exported ones;
* each null draw's config hash and prefix hashes (the cache entries the draws left are keyed by them).

Every one of those must reproduce, for every spec, or that job's results are refused. The draw hashes are not in the
specs (the cluster reports them), so they are frozen in ``tests/fixtures/rq4_overnight/draw_hashes.json``, computed
with 151ace3's code and cross-checked against an independent probe of that tree (0 differences). If this test fails,
the change that made it fail would refuse those results: take a compatible route instead (read both forms, or an
optional key the old specs do not carry).

No channel data is read: the plan's database holds the specs' recording rows with a dummy file.
"""

import glob
import hashlib
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working import run_groups as RG  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import chain_job, fanout  # noqa: E402
from Working.execution import _recipe_prefix_hash  # noqa: E402
from Working.recipes import short_hash  # noqa: E402

SPECS_DIR = os.path.join(PROJECT_ROOT, "HPC", "Detection", "generated", "rq4_overnight")
GOLDEN = os.path.join(PROJECT_ROOT, "tests", "fixtures", "rq4_overnight", "draw_hashes.json")
PATHS = sorted(glob.glob(os.path.join(SPECS_DIR, "*" + chain_job.SPEC_SUFFIX)))
NAMES = [os.path.basename(p)[:-len(chain_job.SPEC_SUFFIX)] for p in PATHS]


def _spec(name):
    with open(os.path.join(SPECS_DIR, name + chain_job.SPEC_SUFFIX), encoding="utf-8") as f:
        return json.load(f)


def _digest(prefixes):
    return hashlib.sha1(",".join(prefixes).encode("utf-8")).hexdigest()[:16]


@pytest.fixture(scope="module")
def golden():
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)["specs"]


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    """One database holding every recording row the specs name, as their targets describe them."""
    tmp = tmp_path_factory.mktemp("rq4_specs")
    dummy = tmp / "dummy.npy"
    dummy.write_bytes(b"")
    c = init_db(str(tmp / "annotations.sqlite"))
    seen = {}
    for name in NAMES:
        for t in _spec(name)["targets"]:
            row = (t["sourceFile"], int(t["channel"]), float(t["fs"]), int(t["nSamples"]), int(t["globalOffset"]),
                   t["units"])
            if int(t["recordingId"]) in seen:
                assert seen[int(t["recordingId"])] == row, f"two specs describe recording {t['recordingId']} apart"
                continue
            seen[int(t["recordingId"])] = row
            c.execute("INSERT INTO recordings (id, source_file, channel, fs, n_samples, global_offset, npy_path, "
                      "units) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (int(t["recordingId"]), *row[:5], str(dummy), row[5]))
    c.commit()
    yield c
    c.close()


def test_the_overnight_specs_are_all_here_cpu_cnn_and_the_gpu_profile_among_them():
    assert len(NAMES) == 43, f"{len(NAMES)} specs under {SPECS_DIR}"
    kinds = {n: [f"{s['stage']}.{s['algorithm']}" for s in _spec(n)["steps"]] for n in NAMES}
    assert any("detection.drop_detection" in k for k in kinds.values()), "a CPU template"
    assert any("catalogue.cnn_window_scores" in k for k in kinds.values()), "a CNN template"
    mp = [n for n, k in kinds.items() if "detection.matrix_profile" in k]
    assert mp and all(_spec(n)["steps"][1]["params"]["backend"] == "auto" for n in mp), "the backend: auto profile"
    assert sum(len(_spec(n)["targets"]) for n in NAMES) == 674


@pytest.mark.parametrize("name", NAMES)
def test_the_spec_hash_reproduces(name, golden):
    h = chain_job.spec_hash(_spec(name))
    assert name.endswith("_" + h[:6]), "the file name carries the spec's hash"
    with open(os.path.join(SPECS_DIR, name + chain_job.OUT_SUFFIX, chain_job.JOB_NAME), encoding="utf-8") as f:
        assert json.load(f)["specHash"] == h, "job.json names the same spec"
    assert golden[name]["specHash"] == h


@pytest.mark.parametrize("name", NAMES)
def test_every_targets_config_and_prefix_hashes_reproduce(name):
    for t in _spec(name)["targets"]:
        r = t["recipe"]
        assert short_hash(r) == t["configHash"], f"task {t['index']}'s config hash"
        assert [_recipe_prefix_hash(r, k, t["units"]) for k in range(len(r["steps"]))] == t["prefixHashes"], \
            f"task {t['index']}'s step-cache keys"


@pytest.mark.parametrize("name", NAMES)
def test_the_local_plan_rebuilds_the_exported_recipes(name, conn):
    spec = _spec(name)
    plan = chain_job.local_plan(conn, spec)           # refuses (ImportRefused) on any recipe that moved
    paired = bool(spec["null"]["paired"])
    assert [t["recording_id"] for t in plan["targets"]] == [t["recordingId"] for t in spec["targets"]]
    for i, t in enumerate(spec["targets"]):
        assert fanout.target_recipe(plan["recipe"], i, paired) == t["recipe"]
    assert plan["null"]["draws"] == spec["null"]["draws"] and plan["null"]["params"] == spec["null"]["params"]


@pytest.mark.parametrize("name", NAMES)
def test_the_null_draw_hashes_reproduce(name, golden):
    spec = _spec(name)
    want = golden[name]["targets"]
    for t in spec["targets"]:
        draws = []
        if spec["null"]["paired"]:
            base, skipped = RG.surrogate_draw_params(None, None, spec["null"]["params"])
            assert skipped is None
            for j in range(int(spec["null"]["draws"])):
                dr = RG.surrogate_recipe(t["recipe"], dict(base, seed=int(base["seed"]) + j))
                draws.append([short_hash(dr), _digest([_recipe_prefix_hash(dr, k, t["units"])
                                                       for k in range(len(dr["steps"]))])])
        assert draws == want[str(t["index"])], f"task {t['index']}'s null draws"

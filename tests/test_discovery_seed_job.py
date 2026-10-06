"""
test_discovery_seed_job.py
==========================
RQ2's seed search on the HPC (the researcher, 2026-10-06): a seed search that
would take more than the local ceiling is a SLURM job — the distance profile
and its null computed on the cluster, the result brought back and imported.

`Working.discovery.seed_job` is the headless half: a **spec** that carries
everything the cluster needs (the exemplar's own samples, the channels by file
and index, the span, the parameters, the null), `run_spec` that computes the
candidates and the null draws per channel from it, `write_job` that writes
the spec and an `sbatch` script around `python -m Working.discovery.seed_job`,
and `main` for the cluster side. No UI, no bridge — the import-boundary test
keeps it that way.
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.discovery import seed_job  # noqa: E402

FS = 1.0
N = 6000
M = 60
PLANTS = (600, 1800, 3400)


def _planted(seed):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(N) * 0.02
    shape = -np.sin(np.linspace(0.0, np.pi, M))
    for p in PLANTS:
        x[p:p + M] += shape
    return x


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "annotations.sqlite"
    conn = init_db(str(path))
    for ch in range(2):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _planted(ch))
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, ?, ?, 0, ?)", (ch, FS, N, str(npy)))
    conn.commit()
    conn.close()
    return str(path)


def _channels():
    return [{"source_file": "syn.mat", "channel": 0, "name": "CH1", "fs": FS},
            {"source_file": "syn.mat", "channel": 1, "name": "CH2", "fs": FS}]


def _spec():
    exemplar = _planted(0)[PLANTS[0]:PLANTS[0] + M]
    return seed_job.build_spec(seed_id="library:1:600:660", exemplar=exemplar, channels=_channels(),
                               span=(0, N), k=20, max_distance=None,
                               null={"method": "phase_randomize", "draws": 2, "seed": 0}, exclusion=0.5)


def test_the_spec_carries_everything_the_cluster_needs():
    spec = _spec()
    assert spec["version"] == seed_job.SPEC_VERSION
    assert len(spec["exemplar"]) == M, "the exemplar travels as its own samples, not as a row id"
    assert [c["name"] for c in spec["channels"]] == ["CH1", "CH2"]
    assert all("npy_path" not in c for c in spec["channels"]), "a local path means nothing on the cluster"
    assert spec["null"] == {"method": "phase_randomize", "draws": 2, "seed": 0, "blockS": None}
    assert spec["span"] == [0, N] and spec["k"] == 20 and spec["exclusion"] == 0.5
    assert json.loads(json.dumps(spec)) == spec, "the spec is plain JSON"


def test_run_spec_finds_the_planted_motifs_and_draws_the_null(db):
    spec = _spec()
    seen = []
    result = seed_job.run_spec(spec, loader=seed_job.db_loader(db), on_progress=lambda d, t, m: seen.append((d, t)))
    assert result["specHash"] == seed_job.spec_hash(spec)
    assert [c["name"] for c in result["perChannel"]] == ["CH1", "CH2"]
    for ch in result["perChannel"]:
        near = [c["index"] for c in ch["candidates"] if min(abs(c["index"] - p) for p in PLANTS) <= 5]
        assert len(near) == 3, f"{ch['name']} should find the three planted motifs, found {ch['candidates'][:5]}"
        assert ch["null"]["draws"] == 2 and len(ch["null"]["distances"]) > 0
    # progress is in units of work: the search plus every draw, per channel
    assert seen[-1][1] == 2 * (1 + 2)
    assert result["elapsedS"] >= 0


def test_the_job_script_runs_the_seed_job_module(tmp_path):
    spec = _spec()
    out = seed_job.write_job(spec, out_dir=str(tmp_path / "hpc"), base_name="seed_abc_2ch", est_seconds=120.0)
    assert os.path.isfile(out["spec_path"]) and os.path.isfile(out["script_path"])
    with open(out["spec_path"], encoding="utf-8") as f:
        assert json.load(f) == spec
    script = out["script"]
    assert script.startswith("#!/bin/bash") and "#SBATCH --job-name=seed_abc_2ch" in script
    assert "python -m Working.discovery.seed_job" in script
    assert "--spec" in script and "--out" in script
    assert out["result_path"].endswith("seed_abc_2ch.result.json")
    assert "\\" not in out["result_path"], "the result path is repo-relative with forward slashes"
    assert "#SBATCH --array" not in script, "one job: the channels run in series inside it"


def test_main_writes_the_result_file(db, tmp_path):
    spec = _spec()
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    out_path = tmp_path / "result.json"
    rc = seed_job.main(["--spec", str(spec_path), "--out", str(out_path), "--db", db])
    assert rc == 0 and out_path.is_file()
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert result["version"] == seed_job.SPEC_VERSION
    assert [c["name"] for c in result["perChannel"]] == ["CH1", "CH2"]
    assert result["perChannel"][0]["null"]["draws"] == 2

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


# ── 2026-10-07: the cluster's own files, checkpoints, and what the script needs ──

def _channels_with_paths():
    return [dict(c, npy_path=f"DATA/derived/channels/syn/CH{c['channel']}.npy") for c in _channels()]


def test_the_spec_names_each_channels_repo_relative_npy():
    chans = _channels_with_paths()
    chans[1]["npy_path"] = os.path.join(PROJECT_ROOT, "DATA", "derived", "channels", "syn", "CH1.npy")
    spec = seed_job.build_spec(seed_id="library:1:600:660", exemplar=_planted(0)[:M], channels=chans, span=(0, N),
                               k=20, max_distance=None, null={"method": "phase_randomize", "draws": 2})
    assert [c["npy"] for c in spec["channels"]] == ["DATA/derived/channels/syn/CH0.npy", "DATA/derived/channels/syn/CH1.npy"]
    assert all("npy_path" not in c for c in spec["channels"]), "a local absolute path means nothing on the cluster"


def test_the_file_loader_reads_the_spec_path_before_asking_a_database(db, tmp_path):
    spec = _spec()
    for c in spec["channels"]:
        c["npy"] = str(tmp_path / f"CH{c['channel']}.npy")        # the fixture's own files
    loader = seed_job.file_loader(db_path=None)
    assert len(loader(spec["channels"][0])) == N


def test_run_spec_checkpoints_and_resumes_to_the_same_answer(db, tmp_path):
    spec = _spec()
    loader = seed_job.db_loader(db)
    straight = seed_job.run_spec(spec, loader=loader)
    ck = tmp_path / "partial.json"
    # cancelled after the first channel's first draw: the checkpoint holds that much
    seen = {"n": 0}

    def cancel_after_first_draw():
        return seen["n"] >= 2

    def progress(done, total, msg):
        seen["n"] = done
    partial = seed_job.run_spec(spec, loader=loader, checkpoint=str(ck), on_progress=progress,
                                should_cancel=cancel_after_first_draw)
    assert partial["complete"] is False
    assert ck.is_file()
    saved = json.loads(ck.read_text(encoding="utf-8"))
    assert saved["complete"] is False and len(saved["perChannel"]) >= 1
    assert saved["perChannel"][0]["null"]["draws"] < 2 or len(saved["perChannel"]) == 1
    calls = []
    resumed = seed_job.run_spec(spec, loader=lambda ch: (calls.append(ch["name"]), loader(ch))[1], checkpoint=str(ck))
    assert resumed["complete"] is True
    assert resumed["perChannel"] == straight["perChannel"], "a resumed run is the same draws, in the same order"
    assert "CH1" in calls and len(calls) <= 2


def test_main_resumes_from_its_own_output_and_stops_when_complete(db, tmp_path):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    out_path = tmp_path / "result.json"
    assert seed_job.main(["--spec", str(spec_path), "--out", str(out_path), "--db", db]) == 0
    first = json.loads(out_path.read_text(encoding="utf-8"))
    assert first["complete"] is True
    # a second run over a complete result does nothing and leaves it as it was
    assert seed_job.main(["--spec", str(spec_path), "--out", str(out_path), "--db", db]) == 0
    assert json.loads(out_path.read_text(encoding="utf-8")) == first


def test_the_job_script_says_what_it_needs_and_resubmits_itself(tmp_path):
    spec = seed_job.build_spec(seed_id="library:1:600:660", exemplar=_planted(0)[:M], channels=_channels_with_paths(),
                               span=(0, N), k=20, max_distance=None, null={"method": "phase_randomize", "draws": 2})
    out = seed_job.write_job(spec, out_dir=str(tmp_path / "hpc"), base_name="seed_dep", est_seconds=120.0)
    script = out["script"]
    head = script.split("mkdir -p logs", 1)[0]
    assert "needs on the cluster" in head
    assert "Working/discovery/seed_job.py" in head and "Working/discovery/seeded_search.py" in head
    assert "Adapters/detection_seed_matches.py" in head
    assert "DATA/derived/channels/syn/CH0.npy" in head and "DATA/derived/channels/syn/CH1.npy" in head
    assert "seed_dep.spec.json" in head and "seed_dep.result.json" in head
    assert "DATA/db/annotations.sqlite" not in head, "the spec names the files; the job needs no database"
    # killed at the wall, it continues from its own result file on the next submission
    assert "MAX_CHAIN" in script and "sbatch" in script
    assert out["dependencies"]["code"] and out["dependencies"]["inputs"] and out["dependencies"]["outputs"]


# ── 2026-10-09: a 20-minute wall — one channel per submission, a time budget, the chain ──

def test_main_does_one_channel_per_submission_when_asked(db, tmp_path):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    out = tmp_path / "result.json"
    args = ["--spec", str(spec_path), "--out", str(out), "--db", db, "--max-channels", "1"]
    assert seed_job.main(args) == 0
    first = json.loads(out.read_text(encoding="utf-8"))
    assert first["complete"] is False and [c["name"] for c in first["perChannel"]] == ["CH1"]
    assert seed_job.main(["--status", str(out)]) == 1, "incomplete: the script resubmits"
    assert seed_job.main(args) == 0
    second = json.loads(out.read_text(encoding="utf-8"))
    assert second["complete"] is True and [c["name"] for c in second["perChannel"]] == ["CH1", "CH2"]
    assert seed_job.main(["--status", str(out)]) == 0
    assert seed_job.main(args) == 0 and json.loads(out.read_text(encoding="utf-8")) == second


def test_run_spec_stops_at_its_time_budget_and_resumes_to_the_same_answer(db, tmp_path):
    spec = _spec()
    loader = seed_job.db_loader(db)
    straight = seed_job.run_spec(spec, loader=loader)
    ck = tmp_path / "budget.json"
    partial = seed_job.run_spec(spec, loader=loader, checkpoint=str(ck), budget_s=0.0)
    assert partial["complete"] is False, "a spent budget stops at the first checkpoint"
    assert len(partial["perChannel"]) >= 1
    resumed = seed_job.run_spec(spec, loader=loader, checkpoint=str(ck))
    assert resumed["complete"] is True and resumed["perChannel"] == straight["perChannel"]


def test_the_job_script_runs_one_channel_per_job_and_chains(tmp_path):
    spec = seed_job.build_spec(seed_id="library:1:600:660", exemplar=_planted(0)[:M], channels=_channels_with_paths(),
                               span=(0, N), k=20, max_distance=None, null={"method": "phase_randomize", "draws": 2})
    out = seed_job.write_job(spec, out_dir=str(tmp_path / "hpc"), base_name="seed_chain", est_seconds=120.0)
    script = out["script"]
    assert "--max-channels 1" in script, "one channel per submission, well inside a 20-minute wall"
    assert "--budget-s" in script, "and a budget under the wall, so a long channel still checkpoints and exits"
    assert "sbatch" in script and "--status" in script
    assert out["max_chain"] >= len(spec["channels"]) + 2

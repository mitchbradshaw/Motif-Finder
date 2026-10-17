"""
test_webui_rq4_adopt.py
=======================
The RQ4 overnight sweep comes back into Discovery (2026-10-18). Its 43 chain jobs were written by
``scripts/rq4_overnight.py build``, outside the bridge, so no Discovery run waits for them, and P2's import
(`import_chain_result_for`) only imports a job a run row waits for. Adopting a job registers that row; the import
is then P2's own, unchanged.

* ``POST /api/discovery/chain/adopt`` ``{path, dryRun}``: one waiting template run per spec, in the newest
  Discovery session for the spec's recording, labelled with the spec's label and template, status *on cluster*,
  ``params.hpc`` with exactly the keys *Create SLURM script* writes. The template must be a row whose chain is
  the job's. A dry run writes nothing and says what would be imported: every task's state, the bytes the restore
  copies and the disk free where it copies them. Adopting twice is one row.
* ``POST /api/discovery/chain/local`` ``{template, like, dryRun}``: a template run here over a chain job's own
  channels, span and null, planned by P2's `local_plan`, and run only when nothing over a cap is left to compute.
  This is how the ``backend: "auto"`` copies of the other matrix-profile templates read the profiles the
  overnight ``mp_threshold__backend_auto`` job brought back.
* ``python scripts/rq4_overnight.py adopt``: the whole round over HTTP. Dry by default; ``--apply`` registers
  every job, imports the complete ones one at a time through Jobs' import, then runs the matrix-profile variants.
  A missing or refused task is named, never skipped.

FastAPI lives only in ``webui/.venv``:

    "C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest tests/test_webui_rq4_adopt.py -q -p no:cacheprovider
"""

import importlib.util
import json
import os
import sqlite3
import sys
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Adapters.registry import get_adapter  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import chain_job, fanout  # noqa: E402
from server import templates as T  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

FS = 1.0
N = 3000
CH = ["CH1", "CH2"]
SECTION = [0.0, N / 3600.0]
#: the overnight sweep's null: phase randomisation, seed 0, one draw (Settings here say otherwise)
NULL = {"paired": True, "params": {"method": "phase_randomize", "seed": 0}, "draws": 1}
MP_AUTO = "mp_threshold__backend_auto"
MP_AUTO_VARIANTS = ["mp_threshold__threshold_6__backend_auto", "mp_threshold__threshold_10__backend_auto",
                    "mp_motifs__backend_auto"]


def _script(name):
    """A script under scripts/ as a module, ONE module object per name (rq4_overnight finds create_rq4_variants's
    HTTP helper under the same name, so patching it here patches it there)."""
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, "scripts", name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


def _coloured(seed, n=N):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(n) * 0.01
    x = np.empty(n)
    x[0] = 0.0
    for i in range(1, n):
        x[i] = 0.97 * x[i - 1] + e[i]
    drop = -0.2 * np.exp(-np.linspace(0, 4, 90))
    for a in range(200, n - 200, 470):
        x[a:a + 90] += drop
    return x


@pytest.fixture
def client(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for ch in range(2):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _coloured(ch))
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                     "VALUES ('syn.mat', ?, ?, ?, 0, ?, 'V')", (ch, FS, N, str(npy)))
    conn.commit()
    conn.close()
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261018-rq4-adopt", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            r = c.put("/api/discovery/session", json={"name": "rq4", "recording": "syn", "channels": CH,
                                                      "section": SECTION})
            assert r.status_code == 200, r.text
            yield c
    finally:
        rt.restore()


@pytest.fixture
def bridge(client, monkeypatch):
    """The scripts' HTTP helper, answered by the test client."""
    V = _script("create_rq4_variants")

    def call(base_url, method, path, body=None):
        r = client.request(method, path, json=body)
        if r.status_code >= 400:
            raise V.BridgeError(f"{method} {path} -> HTTP {r.status_code}: {r.text[:600]}")
        return r.json()

    monkeypatch.setattr(V, "call", call)
    return V


def _q(client, sql, args=()):
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _wait_job(client, job_id, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not finish")


def _runs(client):
    r = client.get("/api/discovery/runs")
    assert r.status_code == 200, r.text
    return {x["key"]: x for x in r.json()}


def _row_by_hash(client, h):
    rows = _q(client, "SELECT * FROM discovery_runs WHERE json_extract(params_json, '$.hpc.specHash') = ?", (h,))
    return rows


def _template(client, name):
    conn = init_db(client.app.state.rt.db_path)
    try:
        return next((t for t in T.list_all(conn) if t["name"] == name), None)
    finally:
        conn.close()


def _overnight_job(client, out_dir, template, *, tasks=(0, 1), steps=None, label=None):
    """A chain job written the way `scripts/rq4_overnight.py build` writes one — outside the bridge, no run key,
    no session, the sweep's own null — with ``tasks`` computed as the cluster would."""
    conn = init_db(client.app.state.rt.db_path)
    try:
        if steps is None:
            steps = _template(client, template)["steps"]
        plan = fanout.plan(conn, steps=steps, recording_ids=[1, 2], span=(0, N), ceiling_s=fanout.ceiling_s(conn),
                           null_draws=NULL["draws"], surrogate=True, surrogate_params=NULL["params"])
        plan["null"] = dict(NULL, reason=None)
        plan["template"] = template
        spec = chain_job.build_spec(conn, plan, label=label or template, null=NULL, template=template)
    finally:
        conn.close()
    h = chain_job.spec_hash(spec)
    made = chain_job.write_job(spec, out_dir=str(out_dir), base_name=f"{label or template}_2ch_0-{N}_{h[:6]}")
    results = [chain_job.run_task(spec, task=i, out_dir=made["result_dir"]) for i in tasks]
    return spec, made, results


def _adopt(client, path, dry=False):
    return client.post("/api/discovery/chain/adopt", json={"path": path, "dryRun": dry})


def _local(client, template, like, dry=False):
    return client.post("/api/discovery/chain/local", json={"template": template, "like": like, "dryRun": dry})


# ── adopting a job: the row P2's import waits for ──────────────────────────

def test_adopting_registers_one_waiting_run_with_the_record_create_slurm_script_writes(client, tmp_path):
    # the record *Create SLURM script* writes, for comparison
    r = client.post("/api/discovery/templates/apply", json={"templates": ["noise_threshold"], "channels": CH,
                                                            "t0": SECTION[0], "t1": SECTION[1], "run": False})
    key = r.json()[0]["run_key"]
    r = client.post("/api/discovery/slurm", json={"template": "noise_threshold", "channels": CH, "t0": SECTION[0],
                                                  "t1": SECTION[1], "runKey": key})
    assert r.status_code == 200, r.text
    slurm_hpc = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?",
                              (key,))[0]["params_json"])["hpc"]

    spec, made, _ = _overnight_job(client, tmp_path / "overnight", "noise_threshold", tasks=())
    r = _adopt(client, made["spec_path"])
    assert r.status_code == 200, r.text
    out = r.json()
    rows = _row_by_hash(client, chain_job.spec_hash(spec))
    assert len(rows) == 1
    row = rows[0]
    assert out["runKey"] == row["run_key"] and out["registered"] is True
    assert row["status"] == "on cluster" and row["kind"] == "template"
    assert row["label"] == "noise_threshold" and row["template_name"] == "noise_threshold"
    assert row["template_id"] == _template(client, "noise_threshold")["id"]
    session_id = _q(client, "SELECT id FROM discovery_sessions WHERE source_file = 'syn.mat' "
                            "ORDER BY id DESC LIMIT 1")[0]["id"]
    assert row["session_id"] == session_id
    params = json.loads(row["params_json"])
    hpc = params["hpc"]
    assert set(hpc) == set(slurm_hpc), "params.hpc carries exactly the keys Create SLURM script writes"
    assert hpc["kind"] == "chain" and hpc["specHash"] == chain_job.spec_hash(spec)
    assert os.path.normcase(hpc["specPath"]) == os.path.normcase(made["spec_path"])
    assert os.path.normcase(hpc["resultDir"]) == os.path.normcase(made["result_dir"])
    assert hpc["tasks"] == 2 and hpc["draws"] == 1 and hpc["paired"] is True
    # the spec's own null, not Settings › Nulls (twenty draws here)
    assert params["null"]["paired"] is True and params["null"]["draws"] == 1
    assert params["null"]["params"] == NULL["params"]
    assert params["route"] == "cluster"
    for gone in ("importedAt", "importStartedAt", "counts", "imported", "refused"):
        assert gone not in hpc, f"the import writes {gone} itself"
    run = _runs(client)[row["run_key"]]
    assert run["status"] == "on cluster" and run["hpc"]["kind"] == "chain"


def test_a_dry_run_writes_nothing_and_adopting_twice_is_one_row(client, tmp_path):
    spec, made, _ = _overnight_job(client, tmp_path / "overnight", "noise_threshold", tasks=())
    before = _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"]
    r = _adopt(client, made["spec_path"], dry=True)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["dryRun"] is True and out["registered"] is False and out["runKey"]
    assert out["specHash"] == chain_job.spec_hash(spec)
    assert out["tasks"]["total"] == 2 and out["tasks"]["complete"] == 0
    assert [(t["index"], t["channelName"], t["state"]) for t in out["tasks"]["notComplete"]] == \
        [(0, "CH1", "missing"), (1, "CH2", "missing")]
    assert out["importable"] is False and "task 1 (CH2)" in out["refusal"]
    assert out["disk"]["freeBytes"] > 0 and out["disk"]["root"]
    assert _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"] == before, "a dry run writes nothing"
    first = _adopt(client, made["spec_path"]).json()
    again = _adopt(client, made["spec_path"]).json()
    assert first["runKey"] == again["runKey"] and again["registered"] is True
    assert len(_row_by_hash(client, chain_job.spec_hash(spec))) == 1, "adopting twice is one row"
    dry = _adopt(client, made["spec_path"], dry=True).json()
    assert dry["runKey"] == first["runKey"] and dry["registered"] is True and dry["status"] == "on cluster"


def test_an_adopted_job_imports_through_p2s_import_with_the_specs_own_null(client, tmp_path):
    spec, made, results = _overnight_job(client, tmp_path / "overnight", "noise_threshold")
    dry = _adopt(client, made["spec_path"], dry=True).json()
    assert dry["importable"] is True and dry["refusal"] is None
    assert dry["bytesToCopy"] > 0 and dry["entries"] > 0
    key = _adopt(client, made["spec_path"]).json()["runKey"]
    r = client.post("/api/hpc/chain/import", json={"path": made["spec_path"]})   # Jobs' import: P2's, unchanged
    assert r.status_code == 200, r.text
    assert r.json()["run_key"] == key
    assert _wait_job(client, r.json()["job_id"])["status"] == "completed"
    run = _runs(client)[key]
    assert run["status"] == "done" and run["hpcImported"] is True and run.get("clusterAgrees") is True
    assert run["found"] == sum(t["run"]["detections"] for t in results)
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?",
                           (key,))[0]["params_json"])
    assert params["null"]["drawn"] == 1, "the sweep here drew the spec's one draw, not Settings' twenty"
    after = _adopt(client, made["spec_path"], dry=True).json()
    assert after["imported"] is True and after["status"] == "done"


def test_a_missing_or_refused_task_is_named_and_the_import_refuses(client, tmp_path):
    spec, made, _ = _overnight_job(client, tmp_path / "overnight", "noise_threshold", tasks=(0, 1))
    res_path = os.path.join(made["result_dir"], "return", "task1", "result.json")
    with open(res_path, encoding="utf-8") as f:
        res = json.load(f)
    res["error"] = "ChainJobRefused: the channel file is not the exported one"
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(res, f)
    dry = _adopt(client, made["spec_path"], dry=True).json()
    assert dry["importable"] is False and dry["tasks"]["complete"] == 1
    assert dry["tasks"]["notComplete"] == [{"index": 1, "channelName": "CH2", "state": "refused",
                                            "reason": "ChainJobRefused: the channel file is not the exported one"}]
    assert "task 1 (CH2)" in dry["refusal"]
    key = _adopt(client, made["spec_path"]).json()["runKey"]
    r = client.post("/api/hpc/chain/import", json={"path": made["spec_path"]})
    assert r.status_code == 422 and "task 1 (CH2)" in r.text, r.text
    assert _runs(client)[key]["status"] == "on cluster"


def test_a_job_whose_template_is_not_a_row_or_not_its_chain_is_refused_by_name(client, tmp_path):
    steps = [dict(s) for s in _template(client, "mp_threshold")["steps"]]
    steps[1] = dict(steps[1], params=dict(steps[1].get("params") or {}, backend="auto"))
    spec, made, _ = _overnight_job(client, tmp_path / "a", MP_AUTO, tasks=(), steps=steps)
    before = _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"]
    r = _adopt(client, made["spec_path"], dry=True)
    assert r.status_code == 422, r.text
    assert MP_AUTO in r.text and "create_rq4_variants" in r.text
    assert _adopt(client, made["spec_path"]).status_code == 422
    changed = [dict(s) for s in _template(client, "noise_threshold")["steps"]]
    changed[-1] = dict(changed[-1], params=dict(changed[-1].get("params") or {}, k_sigma=9.0))
    spec2, made2, _ = _overnight_job(client, tmp_path / "b", "noise_threshold", tasks=(), steps=changed,
                                     label="noise_threshold_k9")
    r = _adopt(client, made2["spec_path"])
    assert r.status_code == 422 and "noise_threshold" in r.text and "chain" in r.text, r.text
    assert _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"] == before, "nothing was written"


# ── the backend: auto copies read the imported profiles ───────────────────

def test_the_backend_auto_variants_run_here_from_the_imported_profiles_and_stump_ones_do_not(
        client, bridge, tmp_path, monkeypatch):
    mp = get_adapter("detection.matrix_profile")
    monkeypatch.setattr(mp, "max_span_samples", 500)          # the whole span is over this machine's cap
    bridge.main(["--url", "http://bridge", "--apply"])
    spec, made, _ = _overnight_job(client, tmp_path / "overnight", MP_AUTO)
    stump = _local(client, "mp_threshold__threshold_6", made["spec_path"], dry=True)
    assert stump.status_code == 200, stump.text
    assert stump.json()["runsHere"] is False, "before the import nothing is cached"
    assert _adopt(client, made["spec_path"]).status_code == 200
    r = client.post("/api/hpc/chain/import", json={"path": made["spec_path"]})
    assert r.status_code == 200, r.text
    assert _wait_job(client, r.json()["job_id"])["status"] == "completed"
    real_run = mp.run

    def boom(*a, **k):
        raise AssertionError("the profile was computed here; the imported cache entry was not used")

    monkeypatch.setattr(mp, "run", boom)
    for name in MP_AUTO_VARIANTS:
        dry = _local(client, name, made["spec_path"], dry=True)
        assert dry.status_code == 200, dry.text
        d = dry.json()
        assert d["runsHere"] is True and d["route"] != "cluster" and d["capped"] == [], d
        assert d["like"]["specHash"] == chain_job.spec_hash(spec)
        for t in d["targets"]:
            assert "detection.matrix_profile" in t["cached"], t
            assert t["drawsCached"] >= 0 and t["draws"] == 1
        r = _local(client, name, made["spec_path"])
        assert r.status_code == 200, r.text
        started = r.json()
        assert _wait_job(client, started["jobId"])["status"] == "completed"
        run = _runs(client)[started["runKey"]]
        assert run["status"] == "done" and run["template"] == name
        params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?",
                               (started["runKey"],))[0]["params_json"])
        assert params["null"]["drawn"] == 1 and params["like"]["specHash"] == chain_job.spec_hash(spec)
        again = _local(client, name, made["spec_path"])
        assert again.status_code == 200 and again.json()["runKey"] == started["runKey"], "one run per template"
        assert again.json().get("jobId") is None
    # a `stump` template keys its profile apart: it would compute the profile here, over the cap
    stump = _local(client, "mp_threshold__threshold_6", made["spec_path"], dry=True).json()
    assert stump["runsHere"] is False and "detection.matrix_profile" in stump["reason"]
    r = _local(client, "mp_threshold__threshold_6", made["spec_path"])
    assert r.status_code == 422 and "detection.matrix_profile" in r.text, r.text
    monkeypatch.setattr(mp, "run", real_run)


# ── the driver: scripts/rq4_overnight.py adopt ─────────────────────────────

def _manifest(folder, jobs, refused=()):
    m = {"source": "syn.mat", "span": [0, N], "packs": [], "refused": list(refused),
         "jobs": [{"label": spec["label"], "template": spec["template"], "specHash": chain_job.spec_hash(spec),
                   "kind": "cpu", "spec": f"HPC/Detection/generated/rq4_overnight/{os.path.basename(made['spec_path'])}",
                   "out": f"HPC/Detection/generated/rq4_overnight/{os.path.basename(made['result_dir'])}",
                   "channels": CH, "draws": 1} for spec, made in jobs]}
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(m, f)


def test_the_adopt_command_dry_runs_names_every_gap_and_writes_nothing(client, bridge, tmp_path, capsys):
    folder = tmp_path / "rq4_overnight"
    a, made_a, _ = _overnight_job(client, folder, "noise_threshold")
    b, made_b, _ = _overnight_job(client, folder, "signal_threshold", tasks=(0,))
    _manifest(folder, [(a, made_a), (b, made_b)],
              refused=[{"label": "dehshibi_spikes", "reason": "wavelet_transform: over its 320,000-sample cap"}])
    rq4 = _script("rq4_overnight")
    before = _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"]
    rq4.main(["adopt", "--url", "http://bridge", "--out", str(folder)])
    out = capsys.readouterr().out
    assert "noise_threshold" in out and "signal_threshold" in out
    assert "task 1 (CH2)" in out, "the missing task is named"
    assert "dehshibi_spikes" in out, "a job refused before the cluster is named too"
    assert "free" in out and "dry run" in out.lower()
    assert _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"] == before


def test_the_adopt_command_refuses_to_apply_to_the_real_database_unless_told(client, bridge, tmp_path, monkeypatch,
                                                                             capsys):
    folder = tmp_path / "rq4_overnight"
    a, made_a, _ = _overnight_job(client, folder, "noise_threshold")
    _manifest(folder, [(a, made_a)])
    real = bridge.call

    def as_project(base_url, method, path, body=None):
        out = real(base_url, method, path, body)
        return dict(out, mode="project") if path == "/api/runtime" else out

    monkeypatch.setattr(bridge, "call", as_project)
    rq4 = _script("rq4_overnight")
    assert rq4.main(["adopt", "--url", "http://bridge", "--out", str(folder), "--apply"]) == 2
    assert "--allow-project" in capsys.readouterr().out
    assert not _row_by_hash(client, chain_job.spec_hash(a)), "nothing was registered"


def test_the_adopt_command_applies_imports_the_complete_jobs_and_runs_the_mp_variants(
        client, bridge, tmp_path, monkeypatch, capsys):
    mp = get_adapter("detection.matrix_profile")
    monkeypatch.setattr(mp, "max_span_samples", 500)
    bridge.main(["--url", "http://bridge", "--apply"])
    folder = tmp_path / "rq4_overnight"
    a, made_a, _ = _overnight_job(client, folder, "noise_threshold")
    b, made_b, _ = _overnight_job(client, folder, "signal_threshold", tasks=(0,))
    m, made_m, _ = _overnight_job(client, folder, MP_AUTO)
    _manifest(folder, [(a, made_a), (b, made_b), (m, made_m)])
    rq4 = _script("rq4_overnight")
    monkeypatch.setattr(rq4, "POLL_S", 0.2)
    capsys.readouterr()
    code = rq4.main(["adopt", "--url", "http://bridge", "--out", str(folder), "--apply"])
    out = capsys.readouterr().out
    assert code == 1, "a job is left waiting, so the command does not report success"
    assert "task 1 (CH2)" in out
    runs = _runs(client)
    by_hash = {s["label"]: _row_by_hash(client, chain_job.spec_hash(s))[0] for s in (a, b, m)}
    assert runs[by_hash["noise_threshold"]["run_key"]]["status"] == "done"
    assert runs[by_hash[MP_AUTO]["run_key"]]["status"] == "done"
    assert runs[by_hash["signal_threshold"]["run_key"]]["status"] == "on cluster", "registered, waiting"
    for name in MP_AUTO_VARIANTS:
        mine = [r for r in runs.values() if r.get("template") == name]
        assert len(mine) == 1 and mine[0]["status"] == "done", (name, mine)
    n_rows = _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"]
    rq4.main(["adopt", "--url", "http://bridge", "--out", str(folder), "--apply"])
    assert _q(client, "SELECT COUNT(*) AS n FROM discovery_runs")[0]["n"] == n_rows, "a second round adds nothing"
    assert "already imported" in capsys.readouterr().out

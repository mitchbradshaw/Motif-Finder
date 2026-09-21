"""
test_webui_registration.py
==========================
Bridge routes of stage-3 Prompt 02 (`webui/server/registration.py`):

* `GET /api/registry` (the kinds) and `GET /api/registry/{kind}` (registered
  rows + scan candidates), `POST …/check`, `POST …/register`, `DELETE …/{id}`;
* `GET|PUT /api/settings/{page}` over the `settings` table, with the held-out
  unlock refused (409) until the recording's name is typed;
* `GET|POST /api/audit`, `GET /api/audit.csv`;
* `GET /api/about`, `GET /api/storage`.

Both runtime modes are exercised against a fresh `init_db()` database in a
temp directory; the scan roots are pointed at temp trees through
`app.state.registry_roots`. FastAPI lives only in `webui/.venv`, so under the
conda `pytest` this file skips; run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_registration.py
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402


def _fresh_db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES (?, 0, 1.0, 10, 0, 'held.npy')", (HELD_OUT_FILE,))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES ('M1.mat', 0, 1.0, 14401, 0, 'M1/CH0.npy')")
    conn.commit(); conn.close()
    return db


def _fake_dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


def _trees(tmp_path):
    chans = tmp_path / "channels"; chans.mkdir()
    d = chans / "NEW"; d.mkdir()
    np.save(str(d / "CH0.npy"), np.cumsum(np.random.default_rng(0).standard_normal(3000)))
    (d / "manifest.json").write_text(json.dumps({"source_file": "NEW.mat", "n_channels": 1, "fs": 10.0, "n_samples_per_channel": 3000, "dtype": "float64"}), encoding="utf-8")
    mp = tmp_path / "mp"; mp.mkdir()
    n, m = 14401, 60
    np.savez(str(mp / "mp_v2_M1_CH0_WIN1min.npz"), mp=np.ones(n - m + 1, np.float32), mpi=np.zeros(n - m + 1, np.int32), m=np.int32(m), fs=np.float32(1.0),
             n_samples=np.int64(n), source_file="M1.mat", channel=np.int64(0), recording_id=np.int64(2), config_hash="3d99be78")
    return {"recording": [str(chans)], "matrix_profile": [str(mp)]}


@pytest.fixture(params=["sandbox", "project"])
def bridge(request, tmp_path):
    db = _fresh_db(tmp_path)
    rt = Runtime(mode=request.param, stamp=f"20260921-{request.param}", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_fake_dist(tmp_path)))
    rt.setup()
    try:
        app = create_app(rt)
        app.state.registry_roots = _trees(tmp_path)
        with TestClient(app) as client:
            yield client, rt
    finally:
        rt.restore()


# -------------------------------------------------------------- registry --

def test_registry_lists_kinds_and_a_kind_lists_registered_and_candidates(bridge):
    client, _ = bridge
    kinds = client.get("/api/registry").json()["kinds"]
    names = {k["name"] for k in kinds}
    assert {"recording", "raw", "model", "matrix_profile", "window_matrix", "window_set", "encoding", "drop_motif_store", "catalogue_spreadsheet", "hpc_result"} <= names
    assert all(k["label"] and k["table"] and k["ui"] and k["roots"] for k in kinds)
    r = client.get("/api/registry/recording")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "recording"
    reg = {x["name"] for x in body["registered"]}
    assert "M1" in reg and HELD_OUT_FILE[:-4] in reg
    held = [x for x in body["registered"] if x["name"] == HELD_OUT_FILE[:-4]][0]
    assert held["held_out"] is True
    cands = {c["name"]: c for c in body["candidates"]}
    assert "NEW" in cands and cands["NEW"]["registered"] is False and cands["NEW"]["facts"]["fs"] == 10.0
    assert client.get("/api/registry/no-such-kind").status_code == 404


def test_check_then_register_then_unregister_a_recording_and_it_appears_in_explore(bridge):
    client, rt = bridge
    cand = [c for c in client.get("/api/registry/recording").json()["candidates"] if c["name"] == "NEW"][0]
    r = client.post("/api/registry/recording/check", json={"path": cand["path"]})
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["ok"] is True and rep["sha1"] and any(c["name"] == "hash" for c in rep["checks"])
    r = client.post("/api/registry/recording/register", json={"path": cand["path"], "provenance": {"producer": "test"}})
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["id"] and row["kind"] == "recording" and row["name"] == "NEW"
    # Explore's recording list picks it up with no client change
    files = {x["source_file"] for x in client.get("/api/recordings").json()}
    assert "NEW.mat" in files
    # the audit log says so
    entries = client.get("/api/audit").json()["entries"]
    assert any(e["kind"] == "registration" and "NEW" in e["what"] for e in entries)
    # registered now; a second register is refused with the failing checks in the body
    r2 = client.post("/api/registry/recording/register", json={"path": cand["path"]})
    assert r2.status_code == 422, r2.text
    assert any(c["name"] == "not_registered" and not c["ok"] for c in r2.json()["detail"]["checks"])
    r3 = client.delete(f"/api/registry/recording/{row['id']}")
    assert r3.status_code == 200 and r3.json()["active"] == 0
    files = {x["source_file"] for x in client.get("/api/recordings").json()}
    assert "NEW.mat" not in files


def test_register_refuses_a_failing_candidate_with_422(bridge):
    client, _ = bridge
    r = client.post("/api/registry/recording/register", json={"path": "channels/does-not-exist"})
    assert r.status_code in (404, 422), r.text
    assert r.headers["content-type"].startswith("application/json")


def test_matrix_profile_registers_bound_to_the_recording_row(bridge):
    client, _ = bridge
    body = client.get("/api/registry/matrix_profile").json()
    cand = body["candidates"][0]
    rep = client.post("/api/registry/matrix_profile/check", json={"path": cand["path"]}).json()
    assert rep["ok"], [c for c in rep["checks"] if not c["ok"]]
    assert rep["facts"]["recording_id"] == 2
    row = client.post("/api/registry/matrix_profile/register", json={"path": cand["path"]}).json()
    assert row["recording_id"] == 2 and row["kind"] == "matrix_profile"
    reg = client.get("/api/registry/matrix_profile").json()["registered"]
    assert len(reg) == 1 and reg[0]["id"] == row["id"] and reg[0]["manifest"]["kind"] == "matrix_profile"


# -------------------------------------------------------------- settings --

def test_settings_get_put_round_trip(bridge):
    client, _ = bridge
    r = client.get("/api/settings/nulls")
    assert r.status_code == 200 and r.json()["page"] == "nulls" and r.json()["values"] == {}
    r = client.put("/api/settings/nulls", json={"values": {"alpha": 0.05, "tokens": ["<a>"]}})
    assert r.status_code == 200, r.text
    assert set(r.json()["changed"]) == {"alpha", "tokens"}
    assert client.get("/api/settings/nulls").json()["values"] == {"alpha": 0.05, "tokens": ["<a>"]}
    assert client.put("/api/settings/nulls", json={"values": {"alpha": 0.05}}).json()["changed"] == []
    assert client.get("/api/settings/not%20a%20page!").status_code == 404
    # a save is audited (kind settings, where the page)
    entries = client.get("/api/audit?kind=settings").json()["entries"]
    assert entries and entries[0]["where"] == "Nulls" and "alpha" in entries[0]["what"]


def test_datasets_settings_carry_the_registry_and_the_held_out_lock(bridge):
    client, _ = bridge
    body = client.get("/api/settings/datasets").json()
    assert body["held_out"]["on"] is True and body["held_out"]["recording"] == HELD_OUT_FILE[:-4]
    assert body["defaults"]["heldout.on"] is True and body["defaults"]["heldout.recording"] == HELD_OUT_FILE[:-4]
    names = {r["name"] for r in body["recordings"]}
    assert {"M1", HELD_OUT_FILE[:-4]} <= names
    assert any(c["name"] == "NEW" for c in body["candidates"])


def test_unlocking_the_held_out_recording_needs_the_typed_name(bridge):
    client, _ = bridge
    r = client.put("/api/settings/datasets", json={"values": {"heldout.on": False}})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["name"] == HELD_OUT_FILE[:-4]
    assert client.get("/api/settings/datasets").json()["held_out"]["on"] is True
    r = client.put("/api/settings/datasets", json={"values": {"heldout.on": False}, "confirm_name": "wrong"})
    assert r.status_code == 409
    r = client.put("/api/settings/datasets", json={"values": {"heldout.on": False}, "confirm_name": HELD_OUT_FILE[:-4]})
    assert r.status_code == 200, r.text
    assert client.get("/api/settings/datasets").json()["held_out"]["on"] is False
    locks = client.get("/api/audit?kind=lock").json()["entries"]
    assert len(locks) == 1 and "turned off" in locks[0]["what"]
    # the routes still refuse the held-out FILE (rule of the routes, not of the lock): 423 in both modes
    held_id = [x for x in client.get("/api/registry/recording").json()["registered"] if x["name"] == HELD_OUT_FILE[:-4]][0]["ids"][0]
    assert client.get(f"/api/channels/{held_id}").status_code == 423


# ----------------------------------------------------------------- audit --

def test_audit_post_get_and_csv(bridge):
    client, _ = bridge
    r = client.post("/api/audit", json={"kind": "hand edit", "what": "Added m-1850 to F-03", "where": "Library › F-03", "route": "library/family/F-03"})
    assert r.status_code == 200 and r.json()["id"]
    entries = client.get("/api/audit").json()["entries"]
    assert entries[0]["kind"] == "hand edit" and entries[0]["by"] == "this installation" and entries[0]["route"] == "library/family/F-03"
    assert client.post("/api/audit", json={"kind": "", "what": "x", "where": "y"}).status_code == 422
    csv_r = client.get("/api/audit.csv")
    assert csv_r.status_code == 200 and csv_r.headers["content-type"].startswith("text/csv")
    assert csv_r.text.splitlines()[0].startswith("when,kind,what,where") and "Added m-1850" in csv_r.text
    assert client.delete("/api/audit/1").status_code in (404, 405)   # append-only: no delete route


# --------------------------------------------------------- about/storage --

def test_about_and_storage_report_the_real_installation(bridge):
    client, rt = bridge
    about = client.get("/api/about").json()
    assert about["mode"] == rt.mode and about["db_path"] == rt.db_path
    assert about["code"]["version"] and about["schema"]["tables"] >= 20 and about["schema"]["settings_rows"] == 0
    assert about["blocks"]["registered"] >= 20 and about["python"].startswith("3.")
    assert isinstance(about["packages"], dict) and "numpy" in about["packages"]
    assert about["held_out_file"] == HELD_OUT_FILE
    assert "\n" in about["diagnostics"] and "mode" in about["diagnostics"]
    storage = client.get("/api/storage").json()
    ids = {r["id"] for r in storage["roots"]}
    assert {"database", "recordings", "channels", "step_cache", "matrix_profiles", "window_matrices", "models", "window_sets", "hpc_results"} <= ids
    for r in storage["roots"]:
        assert "path" in r and "exists" in r and "bytes" in r and "n_files" in r
    assert "free_gb" in storage and isinstance(storage["backups"], list)
    if rt.mode == "project":
        assert storage["backups"] and storage["backups"][0]["path"] == rt.db_backup

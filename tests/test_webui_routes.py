"""
test_webui_routes.py
======================
The routes stage-3 prompt 01 adds to the bridge, against a synthetic
database: templates as rows (seeded, CRUD, builtin protection, apply), the
job routes, Explore's live regions (runs/methods, tags + reviewed coverage,
siblings, cross-channel, "take span for Review" through the human door),
Interrogation's seed families, and "Save window set".

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_routes.py
"""

import datetime as _dt
import os
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

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from server.templates import CANONICAL  # noqa: E402

SEED_DIR = os.path.join(PROJECT_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    fs, n = 1.0, 3000
    rng = np.random.default_rng(0)
    base = np.cumsum(rng.standard_normal(n)) * 0.01
    for ch in (0, 1):
        x = base + (0.002 * rng.standard_normal(n) if ch else 0.0)
        if ch == 1:
            x = np.roll(x, 5)     # channel 1 lags channel 0 by 5 samples
        npy = tmp_path / f"CH{ch}.npy"; np.save(npy, x)
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES ('syn.mat', ?, ?, ?, 0, ?)",
                     (ch, fs, n, str(npy)))
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conn.execute("INSERT INTO tag_vocabulary (category, value) VALUES ('element', 'drop')")
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) VALUES (1, 100, 200, 'interesting', 'test', ?)", (now,))
    conn.execute("INSERT INTO annotation_tags (annotation_id, tag_id) VALUES (1, 1)")
    conn.execute("INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) VALUES (1, 0, 1500, 'test', ?)", (now,))
    conn.commit(); conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def client(tmp_path):
    db = _db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20260921-routes", db_source=str(db), runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _wait_job(client, job_id, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.2)
    raise AssertionError("job did not finish")


# ── templates ────────────────────────────────────────────────────────────────

def test_templates_are_seeded_rows_with_kind_and_version(client):
    rows = client.get("/api/templates").json()
    names = {r["name"] for r in rows}
    assert {t["name"] for t in CANONICAL} <= names
    row = next(r for r in rows if r["name"] == "drop_detection_v1")
    assert row["builtin"] is True and row["kind"] == "detection" and row["version"] == 1 and isinstance(row["id"], int)
    assert all(r["valid"] for r in rows if r["builtin"]), "every canonical template validates"


def test_template_crud_and_builtin_protection(client):
    rows = client.get("/api/templates").json()
    builtin = next(r for r in rows if r["builtin"])
    assert client.put(f"/api/templates/{builtin['id']}", json={"description": "x"}).status_code == 403
    assert client.delete(f"/api/templates/{builtin['id']}").status_code == 403
    r = client.post("/api/templates", json={"name": "mine", "steps": builtin["steps"], "description": "copy"})
    assert r.status_code == 200, r.text
    mine = r.json()
    assert mine["builtin"] is False and mine["kind"] == builtin["kind"]
    r = client.put(f"/api/templates/{mine['id']}", json={"steps": builtin["steps"][:1]})
    assert r.status_code == 200 and r.json()["version"] == 2 and len(r.json()["steps"]) == 1
    bad = client.post("/api/templates", json={"name": "bad", "steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]})
    assert bad.status_code == 422
    assert client.delete(f"/api/templates/{mine['id']}").status_code == 200
    assert client.get(f"/api/templates/{mine['id']}").status_code == 404


def test_apply_template_builds_a_validated_recipe(client):
    tid = next(r["id"] for r in client.get("/api/templates").json() if r["name"] == "dsax_encoding")
    r = client.post(f"/api/templates/{tid}/apply", json={"recording_id": 1, "span": [0, 600]})
    assert r.status_code == 200, r.text
    recipe = r.json()["recipe"]
    assert recipe["recording_id"] == 1 and recipe["span"] == [0, 600] and recipe["steps"][1]["algorithm"] == "sax_dsax"


# ── jobs ─────────────────────────────────────────────────────────────────────

def test_a_run_is_a_job_with_a_row_and_events(client):
    steps = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "linear"}}]
    job = client.post("/api/runs", json={"recording_id": 1, "span": [0, 600], "steps": steps}).json()
    snap = _wait_job(client, job["job_id"])
    assert snap["status"] == "completed" and snap["db_run_id"]
    jobs = client.get("/api/jobs").json()
    assert any(j["job_id"] == job["job_id"] and j.get("kind", "chain_run") == "chain_run" for j in jobs)
    with client.stream("GET", f"/api/jobs/{job['job_id']}/events") as r:
        body = "".join(r.iter_text())
    assert "event: hello" in body and "event: run_end" in body
    assert client.get("/api/jobs/999999").status_code == 404
    assert client.post("/api/runs/999999/cancel").status_code == 404


# ── explore ──────────────────────────────────────────────────────────────────

def test_runs_methods_and_coverage_filters(client):
    steps = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "linear"}},
             {"stage": "detection", "algorithm": "rupture", "params": {}}]
    job = client.post("/api/runs", json={"recording_id": 1, "span": [0, 1500], "steps": steps}).json()
    _wait_job(client, job["job_id"])
    runs = client.get("/api/corpus/syn.mat/runs").json()
    assert runs["runs"] and "rupture" in runs["methods"]
    rid = runs["runs"][0]["id"]
    cov_all = client.get("/api/corpus/syn.mat/coverage").json()
    cov_run = client.get(f"/api/corpus/syn.mat/coverage?run={rid}").json()
    cov_none = client.get("/api/corpus/syn.mat/coverage?method=no_such_method").json()
    assert cov_run["run_filter"] == [rid]
    assert sum(cov_none["rows"][0]["detections"]) == 0
    assert sum(cov_all["rows"][0]["detections"]) == sum(cov_run["rows"][0]["detections"])


def test_tags_and_reviewed_coverage_read_the_database(client):
    r = client.get("/api/channels/1/tags?t0=0&t1=3000").json()
    assert r["annotations"][0]["tags"] == [{"category": "element", "value": "drop"}]
    assert r["reviewed"][0]["end_s"] == 1500.0 and r["reviewed_pct"] == pytest.approx(50.0)
    assert r["tag_counts"] == {"element:drop": 1}
    assert any(v["value"] == "drop" for v in r["vocabulary"])


def test_siblings_and_cross_channel_from_real_channels(client):
    sib = client.get("/api/channels/1/siblings").json()
    assert [c["channel"] for c in sib["channels"]] == [0, 1]
    x = client.get("/api/cross/1?t0=0&t1=1000&px=300").json()
    assert [c["is_reference"] for c in x["channels"]] == [True, False]
    other = x["channels"][1]
    assert other["envelope"]["t"] and other["r"] > 0.7
    assert abs(abs(other["lag_s"]) - 5.0) <= 1.0, other


def test_take_span_for_review_writes_a_seed_annotation_through_the_human_door(client):
    r = client.post("/api/annotations/seed", json={"recording_id": 1, "start_idx": 700, "end_idx": 900, "note": "looks like a drop"})
    assert r.status_code == 200, r.text
    spans = client.get("/api/channels/1/spans?t0=690&t1=910").json()
    mine = [a for a in spans["annotations"] if a["id"] == r.json()["id"]]
    assert mine and mine[0]["verdict"] == "seed" and mine[0]["source"] == "explore.take_for_review"
    assert client.post("/api/annotations/seed", json={"recording_id": 1, "start_idx": 900, "end_idx": 700}).status_code == 422


# ── interrogation ────────────────────────────────────────────────────────────

@pytest.mark.skipif(not os.path.isdir(SEED_DIR), reason="seed store absent")
def test_interrogation_families_are_the_seed_spans_and_marked_seed(client):
    fams = client.get("/api/interrogation/families").json()
    assert fams["source"] == "seed" and len(fams["families"]) == 16
    id001 = next(f for f in fams["families"] if f["id"] == "id001")
    assert id001["n_members"] == 17 and id001["morphology"] == "sharkfin"
    mem = client.get("/api/interrogation/families/id001/members").json()
    assert len(mem["members"]) == 17 and mem["members"][0]["snippet"]["t_s"]
    slope = client.get("/api/interrogation/families/id001/slope").json()
    assert {f["name"] for f in slope["features"]} >= {"onset_slope_mv_s", "max_slope_mv_s", "drop_depth_mv"}
    assert len(slope["members"]) == 17 and slope["members"][0]["max_slope_mv_s"] < 0
    assert sum(slope["rose"]["counts"]) == 17
    agg = client.get("/api/interrogation/families/id001/aggregate").json()
    assert agg["distributions"]["inter_event_interval_s"]["n"] == 16 and agg["n"] == 17
    assert client.get("/api/interrogation/families/nope/members").status_code == 404


# ── training ─────────────────────────────────────────────────────────────────

def test_save_window_set_writes_files_and_registers_the_artifact(client):
    steps = [{"stage": "preprocessing", "algorithm": "sliding_windows", "params": {"window_s": 100.0, "n_blocks": 5}}]
    job = client.post("/api/runs", json={"recording_id": 1, "span": [0, 2000], "steps": steps}).json()
    _wait_job(client, job["job_id"])
    r = client.post("/api/windowsets", json={"job_id": job["job_id"], "step": 0, "name": "ws_test"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["n_windows"] == 20 and os.path.isfile(os.path.join(d["path"], "windows.npz")) and os.path.isfile(os.path.join(d["path"], "manifest.json"))
    runtime = client.get("/api/runtime").json()
    assert d["path"].replace("\\", "/").startswith(runtime["runtime_dir"].replace("\\", "/")), "sandbox mode keeps saved sets inside the runtime dir"
    lst = client.get("/api/windowsets").json()
    assert any(w["name"] == "ws_test" and w["manifest"]["spacing"]["train_safe"] for w in lst["window_sets"])
    assert client.post("/api/windowsets", json={"job_id": job["job_id"], "step": 0, "name": "ws_test"}).status_code == 409
    assert client.post("/api/windowsets", json={"job_id": job["job_id"], "step": 0, "name": "bad name"}).status_code == 422


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

"""
test_webui_training_paired.py
=============================
fixup-ab, seams (ii) and (iii): the bridge routes Models › Launch, Results and
Compare read — over the core's paired training job (`Working/training/`).

* `GET  /api/models/setup` — the training templates and whether each sits on
  the labels' grid, every recording's channels with hours, human verdicts and
  classes seen (the held-out recording is listed only as a locked slot), the
  saved multi-channel window sets, the runs;
* `POST /api/models/windowsets` — a window set ACROSS channels, saved from
  Launch with its split, as a `training` job (one `window_sets` row, a member
  per channel); Library › Window sets lists it with its channels;
* `POST /api/models/propose` — the cut proposal on the training windows;
* `POST /api/models/checks` — the Before-launch checks and the estimate;
* `POST /api/models/train` — a `training` job with per-stage progress; a
  changed cut on a set already scored is refused (409);
* `POST /api/models/slurm` — the CPU script, repo-relative;
* `GET  /api/models/runs`, `/runs/{id}`, `/runs/{id}/compare` — what Results and
  Compare draw.

FastAPI lives only in `webui/.venv`:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_training_paired.py -q
"""

import datetime as _dt
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

from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

N = 36_000
L = 600
SOURCE = "syn_aug_concat_fs1.mat"
CHANNELS = (0, 1, 2, 3)


def _labels(ch):
    out, j = [], 0
    for s in range(200, N - L, L):
        if j % 4 != 3:
            out.append((s, s + L, "interesting" if (j + ch) % 3 == 0 else "not_interesting"))
        j += 1
    return out


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    now = _dt.datetime.now().isoformat(timespec="seconds")
    for source, chans in ((SOURCE, CHANNELS), (HELD_OUT_RECORDING_FILE, (0,))):
        for ch in chans:
            rng = np.random.default_rng(10 + ch)
            x = 0.05 * rng.standard_normal(N)
            labels = _labels(ch)
            for s, _, v in labels:
                if v == "interesting":
                    x[s + 250:s + 500] -= np.linspace(3.0, 0.0, 250)
            npy = tmp_path / f"{source}_{ch}.npy"
            np.save(npy, x)
            cur = conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                               "VALUES (?, ?, 1.0, ?, 0, ?)", (source, ch, N, str(npy)))
            for s, e, v in labels:
                conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                             "VALUES (?, ?, ?, ?, 'imported_10min', ?)", (cur.lastrowid, s, e, v, now))
    conn.commit(); conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def client(tmp_path):
    db = _db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261003-ab", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            c.rt = rt
            yield c
    finally:
        rt.restore()


def _wait_job(client, job_id, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            assert s["status"] == "completed", s
            return s
        time.sleep(0.25)
    raise AssertionError("job did not finish")


def _save_set(client, name="ws_ab"):
    body = {"name": name, "source_file": SOURCE, "channels": [0, 1, 2], "exam_channels": [3],
            "length": 600, "grid": 200, "stages": ["fast_entropy"],
            "split": {"n_blocks": 10, "test_frac": 0.2, "validation_frac": 0.1, "gap_windows": 1}}
    r = client.post("/api/models/windowsets", json=body)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["kind"] == "training"
    done = _wait_job(client, job["job_id"])
    return done["result"]


def _train(client, ws_id, k=3, **extra):
    body = {"window_set_id": ws_id, "k": k, "n_estimators": 40, "rf_shuffles": 5, "bootstrap_n": 100, **extra}
    return client.post("/api/models/train", json=body)


def test_setup_lists_templates_channels_and_a_locked_held_out_slot(client):
    s = client.get("/api/models/setup").json()
    names = {t["name"]: t for t in s["templates"]}
    assert names["manual_labels_model"]["on_label_grid"] is True
    assert names["manual_labels_model"]["length"] == 600 and names["manual_labels_model"]["grid"] == 200
    assert names["windows_model"]["on_label_grid"] is False and names["windows_model"]["reason"]
    recs = {r["source_file"]: r for r in s["recordings"]}
    assert HELD_OUT_RECORDING_FILE not in recs, "the held-out recording is never a source"
    chans = recs[SOURCE]["channels"]
    assert [c["channel"] for c in chans] == list(CHANNELS)
    c0 = chans[0]
    assert c0["hours"] == pytest.approx(10.0) and c0["verdicts"] == len(_labels(0))
    assert c0["interesting"] + c0["not_interesting"] == len(_labels(0))
    assert s["held_out"]["locked"] is True and "Settings" in s["held_out"]["where"]
    assert s["local_limit_s"] == 7200


def test_a_window_set_across_channels_is_saved_by_a_training_job(client):
    res = _save_set(client)
    ws_id = res["window_set_id"]
    conn = sqlite3.connect(client.rt.db_path); conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (ws_id,)).fetchone()
        members = conn.execute("SELECT channel, role FROM window_set_members WHERE window_set_id = ? ORDER BY channel",
                               (ws_id,)).fetchall()
    finally:
        conn.close()
    assert row["recording_id"] is None and row["n_windows"] == res["n_windows"]
    assert [(m["channel"], m["role"]) for m in members] == [(0, "train"), (1, "train"), (2, "train"), (3, "exam")]
    assert row["path"].startswith(client.rt.dir), "a sandbox bridge writes inside its runtime"
    lib = client.get("/api/library/windowsets").json()
    mine = [w for w in lib if w["id"] == "ws_ab"][0]
    assert len(mine["channels"]) == 4 and mine["splitLabel"] == "blocked"
    listed = client.get("/api/models/setup").json()["window_sets"]
    assert [w["id"] for w in listed] == [ws_id] and len(listed[0]["members"]) == 4


def test_the_held_out_recording_cannot_be_a_source(client):
    r = client.post("/api/models/windowsets", json={"name": "nope", "source_file": HELD_OUT_RECORDING_FILE,
                                                    "channels": [0], "exam_channels": [], "length": 600, "grid": 200,
                                                    "stages": ["fast_entropy"]})
    assert r.status_code == 423


def test_propose_checks_train_results_and_compare(client):
    ws_id = _save_set(client)["window_set_id"]
    prop = client.post("/api/models/propose", json={"window_set_id": ws_id, "k_min": 2, "k_max": 4}).json()
    assert [r["k"] for r in prop["by_k"]] == [2, 3, 4] and prop["n_windows_clustered"] > 0

    chk = client.post("/api/models/checks", json={"window_set_id": ws_id, "k": 3, "rf_shuffles": 5}).json()
    names = {c["name"] for c in chk["checks"]}
    assert {"test block unseen", "gap >= window", "label-derived features off", "arms paired"} <= names
    assert chk["estimate"]["where"] == "local" and chk["recipe_hash"]

    r = _train(client, ws_id)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["kind"] == "training"
    done = _wait_job(client, job["job_id"])
    run_id = done["result"]["run_id"]

    runs = client.get("/api/models/runs").json()["runs"]
    assert runs[0]["run_id"] == run_id and runs[0]["status"] == "completed"
    got = client.get(f"/api/models/runs/{run_id}").json()
    ex = got["results"]["exams"]["i_later_block"]
    assert set(ex["arms"]) == {"A", "B"} and ex["paired"]["mcnemar"]
    assert got["results"]["exams"]["iii_held_out"]["status"] == "locked"

    cmp_ = client.get(f"/api/models/runs/{run_id}/compare").json()
    assert cmp_["attributable"] is True
    assert [d["name"] for d in cmp_["differs"] if not d["same"]] == ["label source"]
    assert cmp_["exams"]["i_later_block"]["agreement"]
    assert cmp_["cluster"]["contingency"]

    dis = client.get(f"/api/models/runs/{run_id}/disagreements", params={"filter": "both_wrong", "i": 1})
    assert dis.status_code in (200, 404)
    if dis.status_code == 200:
        d = dis.json()
        assert len(d["trace"]) > 0 and d["human"] in ("interesting", "not_interesting")

    # the cut is frozen once a test score exists
    r2 = _train(client, ws_id, k=4)
    assert r2.status_code == 409 and "k = 3" in r2.text


def test_the_slurm_script_is_a_cpu_job_with_repo_relative_paths(client):
    ws_id = _save_set(client)["window_set_id"]
    r = client.post("/api/models/slurm", json={"window_set_id": ws_id, "k": 3})
    assert r.status_code == 200, r.text
    out = r.json()
    s = out["script"]
    assert "python -m Working.training run --db DATA/db/annotations.sqlite" in s and "--gres" not in s
    # this test's runtime sits in a temp dir outside the repo: the export says the
    # paths will not resolve there; a real bridge's runtime (webui/runtime/) is inside it
    rt_inside = os.path.abspath(client.rt.dir).lower().startswith(PROJECT_ROOT.lower())
    assert (":/" not in s.replace("#!/bin/bash", "")) if rt_inside else out["warnings"]
    assert "Manifest inbox" in out["note"]

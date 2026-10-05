"""
test_webui_window_pools.py
==========================
fixup-af: Library › Window sets › *New window set* — the bridge routes that
build an UNLABELLED window set (one recording, one scale, its channels, a
non-overlapping grid, artifact spans left out, a sample and seed where the
supply is large) as a background job, and the Library row that lists it with
its scale and counts. A pool saved by `python -m Working.training combine`
is listed too, with its roles and members.

FastAPI lives only in `webui/.venv`:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_window_pools.py -q
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

from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

N = 36_000
SOURCE = "syn_aug_concat_fs1.mat"


def _db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    now = _dt.datetime.now().isoformat(timespec="seconds")
    for source, chans in ((SOURCE, range(16)), (HELD_OUT_RECORDING_FILE, (0,))):
        d = tmp_path / "channels" / os.path.splitext(source)[0]
        d.mkdir(parents=True)
        for ch in chans:
            npy = d / f"CH{ch}.npy"
            np.save(npy, 0.05 * np.random.default_rng(ch).standard_normal(N))
            cur = conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                               "VALUES (?, ?, 1.0, ?, 0, ?)", (source, ch, N, str(npy)))
            if source == SOURCE and ch == 0:
                conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                             "VALUES (?, 1000, 1100, 'artifact', 'manual_ui', ?)", (cur.lastrowid, now))
    conn.commit(); conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def client(tmp_path):
    db = _db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261005-af", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            c.rt = rt
            yield c
    finally:
        rt.restore()


def _wait_job(client, job_id, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            assert s["status"] == "completed", s
            return s
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_the_sources_list_supply_per_scale_and_the_held_out_recording_only_as_locked(client):
    r = client.get("/api/windowsets/unlabelled/sources")
    assert r.status_code == 200, r.text
    body = r.json()
    files = [x["source_file"] for x in body["recordings"]]
    assert SOURCE in files and HELD_OUT_RECORDING_FILE not in files
    assert body["held_out"]["file"] == HELD_OUT_RECORDING_FILE and body["held_out"]["locked"] is True
    rec = next(x for x in body["recordings"] if x["source_file"] == SOURCE)
    assert len(rec["channels"]) == 16 and rec["packs"]["D"] == [12, 13, 14, 15]
    assert rec["supply"]["1"] == 16 * 600 and rec["supply"]["10"] == 16 * 60 and rec["supply"]["30"] == 16 * 20
    assert body["scales_min"] == [1, 10, 30]


def test_new_window_set_builds_the_three_scales_as_a_job_and_the_library_lists_them(client):
    r = client.post("/api/windowsets/unlabelled", json={
        "source_file": SOURCE, "channels": list(range(16)), "scales_min": [1, 10, 30], "exclude_artifacts": True,
        "sample": {"1": 2000}, "seed": 4})
    assert r.status_code == 200, r.text
    job = _wait_job(client, r.json()["job_id"])
    built = job["result"]["sets"]
    assert [b["scale_min"] for b in built] == [1, 10, 30]
    assert built[0]["n_windows"] == 2000 and built[1]["counts"]["artifact_human"] == 1
    rows = client.get("/api/library/windowsets").json()
    mine = [w for w in rows if w.get("setKind") == "unlabelled"]
    assert sorted(w["scaleMin"] for w in mine) == [1, 10, 30]
    ten = next(w for w in mine if w["scaleMin"] == 10)
    assert ten["windows"] == 16 * 60 - 1 and len(ten["channels"]) == 16
    assert ten["check"] == "roles at pool" and "pool" in ten["checkReason"]
    assert ten["counts"]["artifact_human"] == 1


def test_new_window_set_refuses_the_held_out_recording_and_a_bad_scale(client):
    r = client.post("/api/windowsets/unlabelled", json={"source_file": HELD_OUT_RECORDING_FILE, "channels": [0],
                                                        "scales_min": [10]})
    assert r.status_code == 423
    r = client.post("/api/windowsets/unlabelled", json={"source_file": SOURCE, "channels": [0], "scales_min": [0]})
    assert r.status_code == 422


def test_a_saved_pool_is_listed_with_its_roles_and_members(client):
    from Working.training import pool as tpool
    from Working.training import store as ts
    from server import corpus
    c = corpus.connect(client.rt.db_path)
    try:
        ids = [ts.save_window_set(c, tpool.build_unlabelled_set(c, SOURCE, scale_min=s), client.rt.window_sets_root,
                                  f"u{s}") for s in (10, 30)]
        pool = tpool.combine(c, ids, tpool.plan_for(c, [SOURCE], hold_out_pack="D"))
        ts.save_window_set(c, pool, client.rt.window_sets_root, "pool_d")
    finally:
        c.close()
    rows = client.get("/api/library/windowsets").json()
    p = next(w for w in rows if w["id"] == "pool_d")
    assert p["setKind"] == "pool" and p["check"] == "train-safe"
    assert p["split"] and abs(sum(p["split"].values()) - 1.0) < 1e-6
    assert p["poolMembers"] == ["u10", "u30"] and p["holdOutPack"] == "D"
    assert sorted(p["scalesMin"]) == [10, 30]

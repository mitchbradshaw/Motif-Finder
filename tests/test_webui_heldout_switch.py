"""
test_webui_heldout_switch.py
============================
a2-p1 — every bridge refusal of the held-out recording obeys Settings ›
Datasets' lock switch, read per request: off opens M4_aug in every workspace,
on closes it again, with no bridge restart in between.

The lock is toggled the way the page does it — ``PUT /api/settings/datasets``,
the recording's name typed to turn it off — and every test runs all three
phases (locked, unlocked, locked again) against ONE app, so a module that
cached the lock state at import or at start would fail the second or third.

What each workspace must do while unlocked (the prompt's list): Explore lists
M4 and ``GET /api/channels/{id}/spans`` answers 200; Analyse validates a chain
on it; Discovery lists it, scopes it and can plan a run on it; the Map's
dataset map includes it; Library and Review list its rows. While locked, every
route that answered 423 before still does, and its refusal says how to unlock.

FastAPI lives only in ``webui/.venv`` (system-site-packages over conda), so
under the conda ``pytest`` this file skips; run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_heldout_switch.py

Nothing here touches ``DATA/``: the database and every channel are written
into the test's own temporary directory.
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

FS = 1.0
N = 7200                      # two hours at 1 Hz
HELD_STEM = HELD_OUT_FILE[:-4]
OTHER = "normal.mat"
UNLOCK_WORDS = "Settings › Datasets"


def _channel(path, seed):
    rng = np.random.default_rng(seed)
    t = np.arange(N, dtype=float)
    x = 0.2 * np.sin(t / 97.0) + 0.01 * rng.standard_normal(N)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, x)
    return path


def _seed(tmp_path):
    """One ordinary recording (one channel, reviewed, so it is Discovery's
    default scope whatever the lock says) and the held-out one (two channels),
    each a real array on disk, with one run and three detections on the
    held-out recording's first channel."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    ins = ("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
           "VALUES (?, ?, ?, ?, 0, ?)")
    other = conn.execute(ins, (OTHER, 0, FS, N, _channel(str(tmp_path / "normal" / "CH0.npy"), 1))).lastrowid
    held = [conn.execute(ins, (HELD_OUT_FILE, ch, FS, N, _channel(str(tmp_path / HELD_STEM / f"CH{ch}.npy"), 10 + ch))).lastrowid
            for ch in (0, 1)]
    conn.execute("INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) "
                 "VALUES (?, 0, 3600, 'test', '2026-10-01T00:00:00')", (other,))
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) "
                       "VALUES ('cfg-heldout', '{}', '2026-10-17T09:00:00')").lastrowid
    run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                       "VALUES (?, ?, 0, ?, '2026-10-17T09:00:00', 'completed')", (cfg, held[0], N)).lastrowid
    dets = [conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                         "VALUES (?, ?, ?, 0.8, '{}')", (run, 600 + 900 * k, 660 + 900 * k)).lastrowid
            for k in range(3)]
    conn.commit()
    conn.close()
    return {"db": str(db), "other": other, "held": held, "held_run": run, "held_detections": dets}


@pytest.fixture()
def bridge(tmp_path):
    info = _seed(tmp_path)
    rt = Runtime("sandbox", stamp="test-heldout-switch", db_source=info["db"],
                 runtime_root=str(tmp_path / "runtime")).setup()
    try:
        app = create_app(rt)
        with TestClient(app) as client:
            yield client, info
    finally:
        rt.restore()


def _lock(client, on):
    """Settings › Datasets' switch, as the page writes it."""
    if on:
        r = client.put("/api/settings/datasets", json={"values": {"heldout.on": True}})
    else:
        r = client.put("/api/settings/datasets", json={"values": {"heldout.on": False}, "confirm_name": HELD_STEM})
    assert r.status_code == 200, r.text
    assert r.json()["held_out"]["on"] is on


def _detail_text(r):
    d = r.json().get("detail")
    return d if isinstance(d, str) else json.dumps(d)


def _assert_423_with_the_way_out(r, what):
    assert r.status_code == 423, f"{what}: {r.status_code} {r.text[:200]}"
    assert UNLOCK_WORDS in _detail_text(r), f"{what}'s refusal does not say how to unlock: {r.text[:300]}"


# ── the state the header chip reads ─────────────────────────────────────────

def test_the_lock_state_route_follows_the_switch(bridge):
    client, _ = bridge
    st = client.get("/api/held-out")
    assert st.status_code == 200, st.text
    body = st.json()
    assert body["locked"] is True and body["file"] == HELD_OUT_FILE
    assert UNLOCK_WORDS in body["unlock"]
    _lock(client, False)
    assert client.get("/api/held-out").json()["locked"] is False
    _lock(client, True)
    assert client.get("/api/held-out").json()["locked"] is True


# ── Explore ─────────────────────────────────────────────────────────────────

def test_explore_lists_and_serves_the_held_out_recording_only_while_unlocked(bridge):
    client, info = bridge
    held = info["held"][0]

    def m4():
        return [f for f in client.get("/api/recordings").json() if f["source_file"] == HELD_OUT_FILE][0]

    # locked: listed as held out, every data door 423, each refusal naming the way out
    assert m4()["held_out"] is True and UNLOCK_WORDS in m4()["held_out_reason"]
    _assert_423_with_the_way_out(client.get(f"/api/channels/{held}"), "GET /api/channels/{id}")
    _assert_423_with_the_way_out(client.get(f"/api/channels/{held}/spans"), "GET /api/channels/{id}/spans")
    _assert_423_with_the_way_out(client.get(f"/api/channels/{held}/window", params={"t0": 0, "t1": 600}),
                                 "GET /api/channels/{id}/window")
    _assert_423_with_the_way_out(client.get(f"/api/corpus/{HELD_OUT_FILE}/coverage"), "GET coverage")
    _assert_423_with_the_way_out(client.get(f"/api/corpus/{HELD_OUT_FILE}/runs"), "GET corpus runs")

    _lock(client, False)
    assert m4()["held_out"] is False and m4()["held_out_reason"] is None, "Explore lists M4 as an ordinary recording"
    assert client.get(f"/api/channels/{held}").status_code == 200
    spans = client.get(f"/api/channels/{held}/spans")
    assert spans.status_code == 200, spans.text
    assert len(spans.json()["detections"]) == 3, "its spans are served, detections included"
    w = client.get(f"/api/channels/{held}/window", params={"t0": 0, "t1": 600})
    assert w.status_code == 200, w.text
    cov = client.get(f"/api/corpus/{HELD_OUT_FILE}/coverage")
    assert cov.status_code == 200, cov.text
    assert cov.json()["held_out"] is False
    assert client.get(f"/api/corpus/{HELD_OUT_FILE}/runs").status_code == 200

    # on again: refused again, no restart
    _lock(client, True)
    assert m4()["held_out"] is True
    _assert_423_with_the_way_out(client.get(f"/api/channels/{held}"), "GET /api/channels/{id} (re-locked)")
    _assert_423_with_the_way_out(client.get(f"/api/channels/{held}/spans"), "GET spans (re-locked)")
    _assert_423_with_the_way_out(client.get(f"/api/corpus/{HELD_OUT_FILE}/coverage"), "GET coverage (re-locked)")


# ── Analyse ─────────────────────────────────────────────────────────────────

LOWPASS = [{"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.05}}]


def test_analyse_takes_the_held_out_recording_only_while_unlocked(bridge):
    client, info = bridge
    held = info["held"][0]
    body = {"recording_id": held, "span": [0, 1200], "steps": LOWPASS}

    def history_ids():
        return {r["recording_id"] for r in client.get("/api/runs").json()["db_runs"]}

    _assert_423_with_the_way_out(client.post("/api/chain/validate", json=body), "POST /api/chain/validate")
    assert held not in history_ids(), "the run history hides the held-out recording's runs while locked"

    _lock(client, False)
    v = client.post("/api/chain/validate", json=body)
    assert v.status_code == 200, v.text
    assert v.json()["ok"] is True
    assert held in history_ids(), "unlocked, its runs are in the run history"
    assert client.get("/api/runs", params={"recording_id": held}).status_code == 200

    _lock(client, True)
    _assert_423_with_the_way_out(client.post("/api/chain/validate", json=body), "POST /api/chain/validate (re-locked)")
    assert held not in history_ids()


# ── Discovery and its Map ───────────────────────────────────────────────────

def test_discovery_scopes_plans_and_maps_the_held_out_recording_only_while_unlocked(bridge):
    client, info = bridge

    def option():
        s = client.get("/api/discovery/session")
        assert s.status_code == 200, s.text
        return [r for r in s.json()["recordings"] if r["file"] == HELD_OUT_FILE][0]

    def omitted():
        m = client.get("/api/discovery/map")
        assert m.status_code == 200, m.text
        return m.json()

    # locked
    opt = option()
    assert opt["heldOut"] is True
    chans = opt["channels"]
    _assert_423_with_the_way_out(client.put("/api/discovery/session", json={"recording": HELD_STEM, "channels": chans}),
                                 "PUT /api/discovery/session")
    _assert_423_with_the_way_out(client.get("/api/discovery/overview", params={"recording": HELD_STEM}),
                                 "GET /api/discovery/overview")
    assert omitted()["heldOutOmitted"] == [HELD_OUT_FILE]
    _assert_423_with_the_way_out(client.get("/api/discovery/map/dataset", params={"recording": HELD_STEM}),
                                 "GET /api/discovery/map/dataset")

    # unlocked: listed, scoped, overviewed, planned, mapped
    _lock(client, False)
    assert option()["heldOut"] is False
    r = client.put("/api/discovery/session", json={"recording": HELD_STEM, "channels": chans, "section": [0.0, 1.0]})
    assert r.status_code == 200, r.text
    assert r.json()["session"]["recordingFile"] == HELD_OUT_FILE
    ov = client.get("/api/discovery/overview", params={"recording": HELD_STEM})
    assert ov.status_code == 200, ov.text
    plan = client.post("/api/discovery/plan", json={"template": "mp_threshold", "channels": chans[:1],
                                                    "t0": 0.0, "t1": 1.0})
    assert plan.status_code == 200, plan.text
    p = plan.json()
    assert p["runnable"] is True and p["refused"] == []
    assert [t["recording_id"] for t in p["targets"]] == [info["held"][0]]
    m = omitted()
    assert m["heldOutOmitted"] == [], "the dataset map no longer omits it"
    assert HELD_OUT_FILE in {d["file"] for d in m["datasets"] + m["withoutRuns"]}, "the dataset map includes it"
    assert client.get("/api/discovery/map/dataset", params={"recording": HELD_STEM}).status_code == 200

    # on again: the same doors refuse, with the session still scoped to it
    _lock(client, True)
    assert option()["heldOut"] is True
    _assert_423_with_the_way_out(client.post("/api/discovery/plan", json={"template": "mp_threshold",
                                                                          "channels": chans[:1], "t0": 0.0, "t1": 1.0}),
                                 "POST /api/discovery/plan (re-locked)")
    _assert_423_with_the_way_out(client.get("/api/discovery/overview", params={"recording": HELD_STEM}),
                                 "GET /api/discovery/overview (re-locked)")
    assert omitted()["heldOutOmitted"] == [HELD_OUT_FILE]
    # and the session can still be moved off it
    back = client.put("/api/discovery/session", json={"recording": "normal", "channels": ["CH1"]})
    assert back.status_code == 200, back.text


# ── Library ─────────────────────────────────────────────────────────────────

def test_library_lists_the_held_out_recording_rows_only_while_unlocked(bridge):
    client, _ = bridge

    def m4_row():
        r = client.get("/api/library/recurrence")
        assert r.status_code == 200, r.text
        return [g for g in r.json()["recordings"] if g["file"] == HELD_OUT_FILE][0]

    row = m4_row()
    assert row.get("heldOut") is True and row["channels"] == []

    _lock(client, False)
    row = m4_row()
    assert not row.get("heldOut"), "unlocked, the recurrence matrix does not mark it held out"
    assert row["channels"] == ["CH1", "CH2"], "and lists its channels"

    _lock(client, True)
    row = m4_row()
    assert row.get("heldOut") is True and row["channels"] == []


# ── Review ──────────────────────────────────────────────────────────────────

def test_review_lists_and_judges_the_held_out_recording_rows_only_while_unlocked(bridge):
    client, info = bridge
    q = client.post("/api/review/queues", json={"name": "M4 detections", "source_kind": "discovery-run",
                                                "source_ref": None, "filters": {"run_id": info["held_run"]}})
    assert q.status_code == 200, q.text
    qid = q.json()["queue"]["id"]
    target = info["held_detections"][0]

    def rows():
        r = client.get(f"/api/review/queues/{qid}")
        assert r.status_code == 200, r.text
        return r.json()

    data = rows()
    assert data["rows"] == [] and data["queue"]["total"] == 0
    v = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": target, "verdict": "interesting"})
    assert v.status_code == 409, v.text
    assert "held out (D6)" in v.text and UNLOCK_WORDS in v.text, "the refusal says how to unlock"

    _lock(client, False)
    data = rows()
    assert len(data["rows"]) == 3 and data["queue"]["total"] == 3, "unlocked, Review lists its rows"
    item = client.get(f"/api/review/queues/{qid}/items/{target}")
    assert item.status_code == 200, item.text
    assert not item.json().get("refused")
    v = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": target, "verdict": "interesting"})
    assert v.status_code == 200, v.text

    _lock(client, True)
    data = rows()
    assert data["rows"] == [] and data["queue"]["total"] == 0
    v = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": info["held_detections"][1],
                                                               "verdict": "interesting"})
    assert v.status_code == 409, v.text


# ── Settings › Datasets: its unit follows the same switch as its metadata ───

def test_the_held_out_recordings_unit_is_declared_only_while_unlocked(bridge):
    client, info = bridge
    held = info["held"][0]
    _assert_423_with_the_way_out(client.put(f"/api/registry/recording/{held}/units", json={"units": "V"}),
                                 "PUT units")
    _lock(client, False)
    r = client.put(f"/api/registry/recording/{held}/units", json={"units": "V", "note": "test"})
    assert r.status_code == 200, r.text
    assert r.json()["units"] == "V"
    _lock(client, True)
    _assert_423_with_the_way_out(client.put(f"/api/registry/recording/{held}/units", json={"units": "mV"}),
                                 "PUT units (re-locked)")


# ── Jobs: a seed result on the held-out recording ───────────────────────────

def test_a_seed_result_path_is_refused_by_name_only_while_locked(bridge):
    client, _ = bridge
    body = {"path": f"x/{HELD_OUT_FILE}.result.json"}
    _assert_423_with_the_way_out(client.post("/api/hpc/seed/import", json=body), "POST /api/hpc/seed/import")
    _lock(client, False)
    r = client.post("/api/hpc/seed/import", json=body)
    assert r.status_code == 404, f"unlocked, the path is looked for like any other: {r.status_code} {r.text[:200]}"
    _lock(client, True)
    assert client.post("/api/hpc/seed/import", json=body).status_code == 423

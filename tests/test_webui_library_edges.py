"""
test_webui_library_edges.py
===========================
fixup-v, the routes: a seed run searched at other scales, its accepted
matches added to the Library entry it searched for, and the Family page
reading the edges back.

The walk this pins is the prompt's acceptance walk, on a synthetic recording:

1. the Seed page offers the scale bank from Settings (one key);
2. a seed run with the bank records its lengths, finds the shape at each, and
   the page's result carries each match's scale and the null per length;
3. Discovery › Runs › *Add N matches to E-xxxx* counts by verdict (Q39:
   accepting verdicts only, unjudged off) and writes members and an edge per
   distance function, once;
4. Library › Family shows the new members with their edge lists and the
   scale read-out filled from those rows; Recurrence's ``edges`` reads real
   rows, and the cross-channel bins in the core's spelling.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_library_edges.py
"""

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

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

FS = 1.0
N = 6000
M = 60
#: the shape planted at three lengths on each channel: 0.8x, 1x, 1.25x
PLANTS = ((800, 48), (2400, 60), (4200, 75))
EXEMPLAR = (2400, 2460)
BANK = [0.8, 1.0, 1.25]
CH = ["CH1", "CH2"]


def _shape(n):
    u = np.linspace(0.0, 1.0, n)
    fall = np.clip(u / 0.2, 0.0, 1.0)
    rise = np.clip((u - 0.2) / 0.8, 0.0, 1.0)
    return -(fall - rise ** 0.5) * (u < 0.2) - (1.0 - rise ** 0.5) * (u >= 0.2)


def _planted(seed):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(N) * 0.02
    for at, n in PLANTS:
        x[at:at + n] += _shape(n)
    return x


def _db(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for ch in range(2):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _planted(ch))
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, ?, ?, 0, ?)", (ch, FS, N, str(npy)))
    # the exemplar entry (the native planting on CH1) and one more entry in its family
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, source_kind, scale) "
                 "VALUES (1, ?, ?, 'trough exemplar', 'review', 'event')", EXEMPLAR)
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, source_kind, scale) "
                 "VALUES (2, 5000, 5060, 'other', 'event_store', 'event')")
    for eid, rid, a, b in ((1, 1, *EXEMPLAR), (2, 2, 5000, 5060)):
        conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, channel, content_hash) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (eid, rid, a, b, rid - 1, f"h{eid}"))
    conn.execute("INSERT INTO groupings (name, unit, basis, method, params_json, cut, n_families, n_assigned, "
                 "n_omitted, created_at) VALUES ('shape families', 'single_motifs', 'shape-distance', 'ward', "
                 "'{\"cut\": 0.6}', 0.6, 1, 2, 0, '2026-10-04')")
    conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                 "family_label, distance, is_medoid) VALUES (1, 'single_motifs', 1, 'h1', 1, 'F-01', 0.0, 1)")
    conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                 "family_label, distance, is_medoid) VALUES (1, 'single_motifs', 2, 'h2', 1, 'F-01', 0.2, 0)")
    conn.commit()
    conn.close()
    return db


def _dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


@pytest.fixture
def client(tmp_path):
    db = _db(tmp_path)
    rt = Runtime(mode="sandbox", stamp="20261004-library-edges", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            r = c.put("/api/discovery/session", json={
                "name": "test", "recording": "syn", "channels": CH, "section": [0.0, N / 3600.0],
                "null": {"method": "phase randomisation", "n": 2}})
            assert r.status_code == 200, r.text
            yield c
    finally:
        rt.restore()


def _q(client, sql, args=()):
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _x(client, sql, args=()):
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        conn.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


def _wait_job(client, job_id, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not finish")


SEED = f"library:1:{EXEMPLAR[0]}:{EXEMPLAR[1]}"


def _bank_run(client, cut=6.0):
    r = client.post("/api/discovery/seed/run", json={
        "seedId": SEED, "channels": CH, "t0": 0.0, "t1": N / 3600.0, "k": 20, "cut": cut,
        "scales": BANK, "overlap": "lowest"})
    assert r.status_code == 200, r.text
    out = r.json()
    snap = _wait_job(client, out["job_id"])
    assert snap["status"] == "completed", snap.get("error")
    return out


def _real_detections(client, run_key):
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?",
                           (run_key,))[0]["params_json"])
    marks = ",".join("?" * len(params["run_ids"]))
    return _q(client, f"SELECT d.*, r.recording_id FROM detections d JOIN runs r ON r.id = d.run_id "
                      f"WHERE d.run_id IN ({marks}) ORDER BY d.score", tuple(params["run_ids"]))


def _judge(client, run_key):
    """Accept the off-scale plantings, reject one, leave the rest unjudged."""
    dets = _real_detections(client, run_key)
    by = {}
    for d in dets:
        length = d["end_idx"] - d["start_idx"]
        by.setdefault((d["recording_id"], length), []).append(d)
    accepted = [by[(1, 48)][0], by[(1, 75)][0], by[(2, 75)][0]]
    rejected = [d for d in dets if d not in accepted and d["start_idx"] != EXEMPLAR[0]][:1]
    for d in accepted:
        _x(client, "INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'interesting', '2026-10-04')",
           (d["id"],))
    for d in rejected:
        _x(client, "INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'not_interesting', '2026-10-04')",
           (d["id"],))
    return accepted, rejected, dets


# ── 1. the bank on the Seed page ────────────────────────────────────────────

def test_the_seed_page_offers_the_bank_from_settings(client):
    setup = client.get("/api/discovery/seed/setup", params={"entry": 1}).json()
    bank = setup["recommended"]["bank"]
    assert bank["scales"] == BANK
    assert bank["label"] == "3 lengths · 0.8× 1× 1.25×"
    r = client.put("/api/settings/analysis-defaults", json={"seed.scale_bank": [0.5, 1, 2]})
    assert r.status_code == 200, r.text
    bank = client.get("/api/discovery/seed/setup", params={"entry": 1}).json()["recommended"]["bank"]
    assert bank["scales"] == [0.5, 1.0, 2.0]


def test_a_bank_run_records_its_lengths_and_finds_each(client):
    out = _bank_run(client)
    row = next(r for r in client.get("/api/discovery/runs").json() if r["key"] == out["run_key"])
    assert row["scales"] == BANK
    lengths = {d["end_idx"] - d["start_idx"] for d in _real_detections(client, out["run_key"])}
    assert {48, 60, 75} <= lengths


def test_a_bank_is_a_different_run_from_the_native_search(client):
    a = _bank_run(client)
    r = client.post("/api/discovery/seed/run", json={
        "seedId": SEED, "channels": CH, "t0": 0.0, "t1": N / 3600.0, "k": 20, "cut": 6.0})
    assert r.status_code == 200, r.text
    assert r.json()["run_key"] != a["run_key"]


def test_the_seed_result_carries_each_matchs_scale_and_a_null_per_length(client):
    body = {"seedId": SEED, "channels": CH, "t0": 0.0, "t1": N / 3600.0, "k": 20, "scales": BANK}
    r = client.post("/api/discovery/seed/results", json=body).json()
    if not r.get("ready"):
        _wait_job(client, r["job_id"])
        r = client.get("/api/discovery/seed/results", params={
            "seedId": SEED, "channels": ",".join(CH), "t0": 0.0, "t1": N / 3600.0, "k": 20,
            "scales": ",".join(str(s) for s in BANK)}).json()
    assert r["ready"], r
    assert {c["scale"] for c in r["candidates"]} >= set(BANK)
    by = r["null"]["byScale"]
    assert sorted(float(k) for k in by) == BANK
    assert all(v["draws"] == r["null"]["draws"] for v in by.values())


# ── 2. Add N matches to E-xxxx ──────────────────────────────────────────────

def test_the_summary_counts_by_verdict_and_names_the_entry(client):
    out = _bank_run(client)
    accepted, rejected, dets = _judge(client, out["run_key"])
    s = client.get(f"/api/library/runs/{out['run_key']}/matches").json()
    assert s["entryId"] == 1
    assert s["entryLabel"] == "E-0001"
    assert s["accepted"] == 3
    assert s["rejected"] == 1
    assert s["eligible"] == 3, "Q39: only accepting verdicts, unjudged off"
    assert s["unjudged"] >= 1
    assert s["includeUnjudged"] is False


def test_adding_writes_members_and_an_edge_per_distance_function_once(client):
    out = _bank_run(client)
    accepted, rejected, _ = _judge(client, out["run_key"])
    m0 = len(_q(client, "SELECT id FROM motif_member"))
    r = client.post(f"/api/library/runs/{out['run_key']}/matches", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["membersNew"] == 3
    assert body["edgesNew"] == 9
    assert len(_q(client, "SELECT id FROM motif_member")) == m0 + 3
    fns = _q(client, "SELECT detection_id, COUNT(DISTINCT distance_function) AS n FROM motif_edge GROUP BY detection_id")
    assert {f["n"] for f in fns} == {3}
    assert {f["detection_id"] for f in fns} == {d["id"] for d in accepted}
    again = client.post(f"/api/library/runs/{out['run_key']}/matches", json={}).json()
    assert again["membersNew"] == 0 and again["edgesNew"] == 0


def test_a_run_whose_seed_is_no_library_entry_cannot_add(client):
    r = client.post("/api/annotations/seed", json={"recording_id": 2, "start_idx": 2400, "end_idx": 2460})
    assert r.status_code == 200, r.text
    run = client.post("/api/discovery/seed/run", json={
        "seedId": "explore:2:2400:2460", "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 5, "cut": 6.0}).json()
    _wait_job(client, run["job_id"])
    s = client.get(f"/api/library/runs/{run['run_key']}/matches").json()
    assert s["entryId"] is None and s["eligible"] == 0 and s["reason"]
    r = client.post(f"/api/library/runs/{run['run_key']}/matches", json={})
    assert r.status_code == 409


# ── 3. the Family page reads the edges ─────────────────────────────────────

def test_the_family_names_its_exemplar_entry(client):
    d = client.get("/api/library/family/F-01").json()["detail"]
    assert d["family"]["exemplarEntryId"] == 1


def test_the_family_lists_the_new_members_with_their_edges_and_the_readout(client):
    out = _bank_run(client)
    accepted, _, _ = _judge(client, out["run_key"])
    client.post(f"/api/library/runs/{out['run_key']}/matches", json={})
    d = client.get("/api/library/family/F-01").json()["detail"]
    matched = d["matched"]
    assert len(matched) == 3
    for m in matched:
        assert len(m["edges"]) == 3
        for e in m["edges"]:
            assert {"function", "value", "threshold", "scale", "recipeHash", "recipe", "run"} <= set(e)
    assert {round(m["edges"][0]["scale"], 2) for m in matched} == {0.8, 1.25}
    ex = next(m for m in d["members"] if m["id"] == "m-1")
    assert len(ex["edges"]) == 9, "the exemplar's own edges, to every member it found"
    ro = d["scaleReadout"]
    assert ro["entryId"] == 1
    runs = ro["runs"]
    assert runs and runs[0]["runKey"] == out["run_key"]
    rows = {r["scale"]: r for r in runs[0]["rows"]}
    assert set(rows) == set(BANK)
    assert rows[1.25]["accepted"] == 2 and rows[0.8]["accepted"] == 1
    assert rows[1.25]["scale_invariant"]["n"] == 2
    assert "nullPerDraw" in rows[1.25]
    assert ro["morphology"] and ro["caveat"]


def test_recurrence_edges_read_real_rows(client):
    before = next(f for f in client.get("/api/library/recurrence").json()["families"] if f["id"] == "F-01")
    assert before["edges"] == "no edges"
    out = _bank_run(client)
    _judge(client, out["run_key"])
    client.post(f"/api/library/runs/{out['run_key']}/matches", json={})
    after = next(f for f in client.get("/api/library/recurrence").json()["families"] if f["id"] == "F-01")
    assert after["edges"] != "no edges"
    assert "3 pairs" in after["edges"]


def test_the_edges_label_reads_the_cores_bin_spelling():
    from Working.cross_channel import INDEPENDENT_RECURRENCE, PROPAGATION, ARTIFACT
    from server.library import _edges_label

    conn = init_db(":memory:")
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES ('a.mat', 0, 1, 100, 0, 'x.npy')")
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx) VALUES (1, 0, 10)")
    for i in range(4):
        conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) VALUES (1, 1, ?, ?)",
                     (10 * i, 10 * i + 10))
    for b, (ma, mb) in zip((INDEPENDENT_RECURRENCE, INDEPENDENT_RECURRENCE, PROPAGATION, ARTIFACT),
                           ((1, 2), (1, 3), (1, 4), (2, 3))):
        conn.execute("INSERT INTO motif_edge (member_a_id, member_b_id, distance_function, threshold, "
                     "distance_value, recipe_hash, classification_bin) VALUES (?, ?, 'scale_invariant', 1, 0.1, 'h', ?)",
                     (ma, mb, b))
    text, art, prop, ind = _edges_label(conn, [1, 2, 3, 4])
    assert (art, prop, ind) == (1, 1, 2)
    assert "independent_recurrence 2" in text

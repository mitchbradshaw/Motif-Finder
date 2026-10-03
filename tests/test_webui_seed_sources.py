"""
test_webui_seed_sources.py
==========================
fixup-y: the three seed sources of §7.6 reach the human, and the Seed page's
run is one run.

What it pins:

* **The picker reaches every Library entry.** It was `motif_entry ORDER BY id
  LIMIT 24`: the first 24 of 3,603 rows, all machine-extracted, so the entry
  Review had just promoted was never offered. Now it pages and filters, and the
  researcher's own exemplars (`source_kind` `review`, then `annotation`) come
  first.
* **The run records which entry it searched for.** A seed id stays
  content-addressed (`04-to-03.md` §2), but the binding carries the real
  `entry_id` rather than 0.
* **Explore's *Take span for Review* writes.** A human `annotations` row with
  verdict `seed`, offered under *Explore selection* at once, and in an
  `explore-spans` Review queue.
* **An unchanged search is the same run.** Re-running it added a second run
  with the same label; a changed cut is a new run whose label says how it
  differs.
* **A match card draws the match.** Every candidate was served `"trace": []`,
  so each card drew the seed alone.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_seed_sources.py
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
PLANTS = (600, 1800, 3400)
OLD = "2020-01-01T00:00:00+00:00"
CH = ["CH1", "CH2", "CH3", "CH4"]
#: machine-extracted entries, more than the old page of 24 so the review entry
#: sits past it by id
N_MACHINE = 30


def _planted(seed):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(N) * 0.02
    shape = -np.sin(np.linspace(0.0, np.pi, M))
    for p in PLANTS:
        x[p:p + M] += shape
    return x


def _db(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for ch in range(4):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, _planted(ch))
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, ?, ?, 0, ?)", (ch, FS, N, str(npy)))
    # 30 machine entries spread over channels 1 and 2 (recordings 1, 2)
    for i in range(N_MACHINE):
        rid = 1 + (i % 2)
        a = 100 + 150 * i
        conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, source_kind) "
                     "VALUES (?, ?, ?, ?, 'event_store')", (rid, a, a + M, f"machine {i}"))
    # one entry made from a human annotation, and the one Review promoted — the
    # promoted one has the highest id, so `ORDER BY id LIMIT 24` never reached it
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, source_kind) "
                 "VALUES (3, ?, ?, 'from annotation', 'annotation')", (PLANTS[1], PLANTS[1] + M))
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, source_kind) "
                 "VALUES (1, ?, ?, 'promoted in Review', 'review')", (PLANTS[0], PLANTS[0] + M))
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
    rt = Runtime(mode="sandbox", stamp="20261003-seed-sources", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            r = c.put("/api/discovery/session", json={
                "name": "test", "recording": "syn", "channels": [CH[0], CH[1]], "section": [0.0, N / 3600.0],
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
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
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


def _review_entry(client):
    return _q(client, "SELECT * FROM motif_entry WHERE source_kind = 'review'")[0]


def _library(client, **params):
    r = client.get("/api/discovery/seeds", params={"source": "library", **params})
    assert r.status_code == 200, r.text
    return r.json()


# ── 1. the picker reaches every Library entry ──────────────────────────────

def test_the_picker_counts_every_library_entry_not_the_first_page(client):
    page = _library(client)
    assert page["total"] == N_MACHINE + 2
    assert len(page["seeds"]) < page["total"], "a page, not the whole library"


def test_the_researchers_own_exemplars_come_first(client):
    seeds = _library(client)["seeds"]
    assert [s["sourceKind"] for s in seeds[:2]] == ["review", "annotation"]
    review = _review_entry(client)
    assert seeds[0]["entryId"] == review["id"]
    assert seeds[0]["id"] == f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"


def test_paging_reaches_the_last_entry(client):
    first = _library(client, limit=24)
    rest = _library(client, limit=24, offset=24)
    ids = [s["entryId"] for s in first["seeds"]] + [s["entryId"] for s in rest["seeds"]]
    assert len(ids) == len(set(ids)) == N_MACHINE + 2


def test_the_picker_filters_by_source_kind(client):
    page = _library(client, kind="review")
    assert page["total"] == 1
    assert page["seeds"][0]["sourceKind"] == "review"
    assert _library(client, kind="event_store")["total"] == N_MACHINE


def test_the_picker_filters_by_recording_and_channel(client):
    page = _library(client, channel=CH[1], limit=100)
    assert page["total"] == N_MACHINE // 2
    assert {s["channel"] for s in page["seeds"]} == {CH[1]}
    assert _library(client, recording="syn")["total"] == N_MACHINE + 2
    assert _library(client, recording="nothing")["total"] == 0


def test_the_picker_filters_by_family_in_the_current_grouping(client):
    review = _review_entry(client)
    gid = _x(client, "INSERT INTO groupings (name, unit, basis, method, params_json, created_at) "
                     "VALUES ('shape families', 'single_motifs', 'shape', 'hdbscan', '{}', ?)", (OLD,))
    mid = _x(client, "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) VALUES (?, ?, ?, ?)",
             (review["id"], review["recording_id"], review["start_idx"], review["end_idx"]))
    _x(client, "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_label, distance) "
               "VALUES (?, 'single_motifs', ?, 'F-07', 0.1)", (gid, mid))
    page = _library(client, family="F-07")
    assert page["total"] == 1
    assert page["seeds"][0]["entryId"] == review["id"]
    assert page["seeds"][0]["family"] == "F-07"
    assert "F-07" in page["families"]


# ── the binding carries the real entry ─────────────────────────────────────

def test_the_setup_opens_an_entry_by_its_id(client):
    review = _review_entry(client)
    r = client.get("/api/discovery/seed/setup", params={"entry": review["id"]})
    assert r.status_code == 200, r.text
    draft = r.json()["draft"]
    assert draft["seedId"] == f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"
    assert draft["seed"]["entryId"] == review["id"]


def test_an_unknown_entry_is_a_404_naming_it(client):
    r = client.get("/api/discovery/seed/setup", params={"entry": 99999})
    assert r.status_code == 404
    assert "99999" in r.text


def test_the_seed_run_records_which_entry_it_searched_for(client):
    """The binding handed to the run names the entry, and the Discovery run row
    keeps it. The stored `configs` row does not, by design: `recipes._normalize`
    strips `entry_id` from a `library_exemplar` binding so the recipe hash is
    content-addressed (ticket 14) — the same shape on another machine is the
    same recipe."""
    from server import discovery as DS
    review = _review_entry(client)
    seed_id = f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        steps, _, _ = DS._steps_for(conn, DS.PlanBody(seedId=seed_id, k=20))
    finally:
        conn.close()
    assert steps[0]["side_inputs"]["exemplar"]["entry_id"] == review["id"]
    run = client.post("/api/discovery/seed/run", json={
        "seedId": seed_id, "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20}).json()
    snap = _wait_job(client, run["job_id"])
    assert snap["status"] == "completed", snap.get("error")
    row = next(r for r in client.get("/api/discovery/runs").json() if r["key"] == run["run_key"])
    assert row["entryId"] == review["id"]
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?",
                           (run["run_key"],))[0]["params_json"])
    cfg = _q(client, "SELECT c.config_json FROM runs r JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
             (params["run_ids"][0],))[0]["config_json"]
    assert "entry_id" not in cfg, "the recipe hash stays content-addressed"


# ── 2. Explore's Take span for Review writes ───────────────────────────────

def _take(client, rid=2, a=PLANTS[2]):
    r = client.post("/api/annotations/seed", json={"recording_id": rid, "start_idx": a, "end_idx": a + M})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_taken_span_is_offered_under_explore_selection_at_once(client):
    took = _take(client)
    seeds = client.get("/api/discovery/seeds", params={"source": "explore"}).json()["seeds"]
    assert seeds and seeds[0]["id"] == f"explore:2:{PLANTS[2]}:{PLANTS[2] + M}"
    assert seeds[0]["annotationId"] == took["id"]


def test_a_taken_span_is_in_an_explore_spans_queue(client):
    took = _take(client)
    assert took["queue_id"], "the toast's Open Review needs the queue"
    body = client.get(f"/api/review/queues/{took['queue_id']}").json()
    assert body["queue"]["source_kind"] == "explore-spans"
    assert body["queue"]["total"] >= 1
    again = _take(client, a=PLANTS[1])
    assert again["queue_id"] == took["queue_id"], "one Explore spans queue, not one per span"


def test_taking_a_span_writes_a_human_row_only(client):
    det0 = _q(client, "SELECT COUNT(*) AS n FROM detections")[0]["n"]
    took = _take(client)
    row = _q(client, "SELECT verdict, source FROM annotations WHERE id = ?", (took["id"],))[0]
    assert row["verdict"] == "seed"
    assert _q(client, "SELECT COUNT(*) AS n FROM detections")[0]["n"] == det0


# ── 4. the Seed page's run is one run ──────────────────────────────────────

def _seed_run(client, cut=None, label=None):
    review = _review_entry(client)
    body = {"seedId": f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}",
            "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20}
    if cut is not None:
        body["cut"] = cut
    if label is not None:
        body["label"] = label
    r = client.post("/api/discovery/seed/run", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    if out.get("job_id"):
        snap = _wait_job(client, out["job_id"])
        assert snap["status"] == "completed", snap.get("error")
    return out


def test_an_unchanged_seed_search_is_the_same_run(client):
    a = _seed_run(client, cut=5.0, label="seed x")
    b = _seed_run(client, cut=5.0, label="seed x")
    assert b["run_key"] == a["run_key"]
    assert b["reused"] is True
    assert len(_q(client, "SELECT id FROM discovery_runs WHERE kind = 'seed'")) == 1


def test_a_changed_cut_is_a_new_run_whose_label_says_how_it_differs(client):
    a = _seed_run(client, cut=5.0, label="seed x")
    b = _seed_run(client, cut=2.5, label="seed x")
    assert b["run_key"] != a["run_key"]
    runs = {r["key"]: r for r in client.get("/api/discovery/runs").json()}
    assert runs[a["run_key"]]["label"] != runs[b["run_key"]]["label"]
    assert "2.5" in runs[b["run_key"]]["label"]


def test_a_seed_run_row_carries_its_seed_and_cut(client):
    a = _seed_run(client, cut=5.0)
    row = next(r for r in client.get("/api/discovery/runs").json() if r["key"] == a["run_key"])
    review = _review_entry(client)
    assert row["seedId"] == f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"
    assert row["cut"] == 5.0


def test_a_run_key_is_a_url_safe_slug(client):
    a = _seed_run(client, label="seed a9147c")
    assert " " not in a["run_key"], "Open in Runs navigated to seed_a9147c while the key was 'seed a9147c'"


def test_the_drafts_cut_survives_a_reload(client):
    review = _review_entry(client)
    seed_id = f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"
    setup = client.get("/api/discovery/seed/setup", params={"seed": seed_id}).json()["draft"]
    params = dict(setup["params"], threshold=14.5)
    r = client.put("/api/discovery/seed/draft", json={"seedId": seed_id, "params": params})
    assert r.status_code == 200, r.text
    again = client.get("/api/discovery/seed/setup").json()["draft"]
    assert again["seedId"] == seed_id
    assert again["params"]["threshold"] == 14.5


# ── a match card draws the match ───────────────────────────────────────────

def test_every_kept_candidate_carries_the_matchs_own_trace(client):
    review = _review_entry(client)
    seed_id = f"library:{review['recording_id']}:{review['start_idx']}:{review['end_idx']}"
    body = {"seedId": seed_id, "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20, "maxDistance": 0.0}
    started = client.post("/api/discovery/seed/results", json=body).json()
    if not started.get("ready"):
        snap = _wait_job(client, started["job_id"])
        assert snap["status"] == "completed", snap.get("error")
    res = client.get("/api/discovery/seed/results", params={**body, "channels": CH[0]}).json()
    assert res["ready"] is True
    x = np.load(_q(client, "SELECT npy_path FROM recordings WHERE id = 1")[0]["npy_path"])
    other = [c for c in res["candidates"] if abs(c["index"] - PLANTS[0]) > M]
    assert other, "the planted dips elsewhere are matches"
    for c in res["candidates"]:
        assert len(c["trace"]) > 1, f"{c['id']} was served no trace"
    c = other[0]
    assert c["trace"][0] == pytest.approx(x[c["index"]], abs=1e-4)
    assert c["trace"][-1] == pytest.approx(x[c["index"] + M - 1], abs=1e-4)

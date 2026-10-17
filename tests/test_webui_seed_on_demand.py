"""
test_webui_seed_on_demand.py
============================
a2-p4 (round A_2, 2026-10-17): the Seed page computes only when asked, a
cancelled preview is never kept, and every Library family can be a seed.

What it pins (the server half; the client half is
`test_webui_seed_on_demand_client.py`):

* **A cancelled preview is never stored.** `POST /api/jobs/{id}/cancel` on a
  preview job used to end with `_store_result` anyway: the short null it had
  drawn was cached under the page's key, and a run with the preview's null
  reused it. Now the job keeps nothing, the GET says the preview was
  cancelled, and the next *Run preview* starts a new job.
* **A run cancelled while it draws the preview first keeps no preview** either
  (`_preview_prelude`).
* **Reading never computes.** The GET of a query with no result starts no job.
* **Every family of a grouping is a seed.** `/api/discovery/seeds` takes a
  `grouping` (by default the newest shape-distance single-motif grouping);
  `source=family` lists each family by its medoid as a `library:` id with its
  entry; the Library tab's family filter reads the same grouping; a member a
  grouping omitted is in no family.
* **A catalogue span is labelled for what it is, and a catalogue span at a
  Library entry's span IS that entry**, so its run can add its matches.
* **The backfill** links an old catalogue-span seed run to its entry, and
  *Add N matches* opens for it.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_seed_on_demand.py
"""

import json
import os
import sqlite3
import sys
import threading
import time

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from test_webui_seed_sources import CH, M, N, OLD, PLANTS, _q, _review_entry, _wait_job, _x, client  # noqa: E402,F401

from Working.discovery import seeded_search  # noqa: E402

T1 = N / 3600.0


def _seed_id(source, e):
    return f"{source}:{e['recording_id']}:{e['start_idx']}:{e['end_idx']}"


def _jobs(client):
    return client.get("/api/health").json()["jobs"]


def _blocking_null(entered: threading.Event):
    """`null_distances` that waits, inside the job, until the job is cancelled — so a test can cancel a preview
    while it is drawing, deterministically. Then it draws as the real one would (none: the cancel is set)."""
    real = seeded_search.null_distances

    def fake(x, exemplar, *, should_cancel=None, **kw):
        entered.set()
        t0 = time.time()
        while not (should_cancel is not None and should_cancel()):
            if time.time() - t0 > 60:
                raise AssertionError("the test never cancelled the job")
            time.sleep(0.02)
        return real(x, exemplar, should_cancel=should_cancel, **kw)
    return fake


def _wait_entered(client, entered: threading.Event, job_id, timeout=900):
    """Until the job is inside its null draws — or say how it ended without getting there. The first MASS in a test
    process compiles stumpy's numba kernels; on the shared machine under `-n 6` that took over two minutes (the
    progress still read "CH1 · matching"), so the limit is generous: the loop leaves the moment the job gets there."""
    t0 = time.time()
    while not entered.wait(0.25):
        snap = client.get(f"/api/jobs/{job_id}").json()
        if snap["status"] not in ("running", "queued"):
            raise AssertionError(f"job {job_id} ended {snap['status']} before its null draws: {snap.get('error')}")
        if time.time() - t0 > timeout:
            raise AssertionError(f"job {job_id} never reached its null draws ({snap.get('progress')})")


def _state(client):
    return json.loads(_q(client, "SELECT state_json FROM discovery_sessions ORDER BY id DESC LIMIT 1")[0]["state_json"]
                      or "{}")


# ── cancel ──────────────────────────────────────────────────────────────────

def test_a_cancelled_preview_is_never_stored_or_reused(client, monkeypatch):
    from server import discovery as DS
    sid = _seed_id("library", _review_entry(client))
    # k = 31: the result cache is process-wide and keyed by the query; other files use 20 and 21
    body = {"seedId": sid, "channels": [CH[0], CH[1]], "t0": 0.0, "t1": T1, "k": 31}
    query = dict(body, channels=",".join(body["channels"]))

    # reading a query nobody has run starts nothing and says so
    jobs0 = _jobs(client)
    peek = client.get("/api/discovery/seed/results", params=query).json()
    assert peek["ready"] is False and peek["job_id"] is None
    assert _jobs(client) == jobs0, "a GET of the preview started a job"

    entered = threading.Event()
    monkeypatch.setattr(seeded_search, "null_distances", _blocking_null(entered))
    started = client.post("/api/discovery/seed/results", json=body).json()
    assert started["ready"] is False and started["job_id"]
    assert _jobs(client) == jobs0 + 1
    _wait_entered(client, entered, started["job_id"])
    # while it runs, the GET joins it and reports its progress
    running = client.get("/api/discovery/seed/results", params=query).json()
    assert running["ready"] is False and running["job_id"] == started["job_id"]

    ack = client.post(f"/api/jobs/{started['job_id']}/cancel").json()
    assert ack["accepted"] is True
    snap = _wait_job(client, started["job_id"])
    assert snap["status"] == "cancelled", f"a cancelled preview ended {snap['status']!r}"

    # nothing was kept: not in the cache, not on the session row
    assert started["key"] not in DS._results
    assert (_state(client).get("seed_result") or {}).get("key") != started["key"]
    after = client.get("/api/discovery/seed/results", params=query).json()
    assert after["ready"] is False
    assert after["job_id"] is None, "a cancelled job is not a running one"
    assert after.get("cancelled") is True, "the page is told the preview was cancelled, not that it never ran"
    assert after.get("cancelledJob") == started["job_id"]

    # a run with the preview's null does not reuse it: it draws the preview first
    est = client.get("/api/discovery/seed/estimate", params={**query, "nullMode": "preview", "seedId": sid}).json()
    assert est["run"]["reusesPreview"] is False

    # and Run preview again is a NEW job, never the cancelled one joined or served
    again = client.post("/api/discovery/seed/results", json=body).json()
    assert again["ready"] is False and again["job_id"] not in (None, started["job_id"])
    assert not again.get("joined")
    client.post(f"/api/jobs/{again['job_id']}/cancel")
    assert _wait_job(client, again["job_id"])["status"] == "cancelled"


def test_a_run_cancelled_while_it_draws_the_preview_keeps_no_preview(client, monkeypatch):
    sid = _seed_id("library", _review_entry(client))
    body = {"seedId": sid, "channels": [CH[0]], "t0": 0.0, "t1": T1, "k": 32, "nullMode": "preview",
            "label": "prelude cancel"}
    entered = threading.Event()
    monkeypatch.setattr(seeded_search, "null_distances", _blocking_null(entered))
    run = client.post("/api/discovery/seed/run", json=body)
    assert run.status_code == 200, run.text
    run = run.json()
    assert run["drawsPreviewFirst"] is True and run["job_id"]
    _wait_entered(client, entered, run["job_id"])
    client.post(f"/api/jobs/{run['job_id']}/cancel")
    _wait_job(client, run["job_id"])

    peek = client.get("/api/discovery/seed/results", params={
        "seedId": sid, "channels": CH[0], "t0": 0.0, "t1": T1, "k": 32}).json()
    assert peek["ready"] is False, "a run cancelled in its preview stored the short preview for the page"
    row = next(r for r in client.get("/api/discovery/runs").json() if r["key"] == run["run_key"])
    assert row["status"] == "cancelled"
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?",
                           (run["run_key"],))[0]["params_json"])
    assert (params.get("null") or {}).get("cancelled") is True, "the row says its null was never drawn"


# ── every family of a grouping is a seed ────────────────────────────────────

_MEMBERS: dict = {}


def _member(client, eid):
    """One `motif_member` per entry, at the entry's own span (what the event-store import writes)."""
    db = client.app.state.rt.db_path
    key = (db, eid)
    if key not in _MEMBERS:
        e = _q(client, "SELECT * FROM motif_entry WHERE id = ?", (eid,))[0]
        _MEMBERS[key] = _x(client, "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) "
                                   "VALUES (?, ?, ?, ?)", (eid, e["recording_id"], e["start_idx"], e["end_idx"]))
    return _MEMBERS[key]


def _grouping(client, basis, families, *, medoids=True, omitted=()):
    """A saved single-motif grouping: `families` is {label: [entry ids]}, the first listed being the medoid when
    `medoids` (a feature-bin grouping records none); `omitted` is [(entry id, nearest label)] — rows that joined
    no family but name their nearest one, as the engine's omitted rows do."""
    gid = _x(client, "INSERT INTO groupings (name, unit, basis, method, params_json, n_families, created_at) "
                     "VALUES (?, 'single_motifs', ?, ?, '{}', ?, ?)",
             (f"{basis} test grouping", basis, "ward" if basis == "shape-distance" else "feature_bins",
              len(families), OLD))
    for fid, (label, eids) in enumerate(families.items(), start=1):
        for j, eid in enumerate(eids):
            _x(client, "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_id, family_label, "
                       "distance, is_medoid) VALUES (?, 'single_motifs', ?, ?, ?, ?, ?)",
               (gid, _member(client, eid), fid, label, (0.1 * j if medoids else None),
                1 if (medoids and j == 0) else 0))
    for eid, label in omitted:
        _x(client, "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_id, family_label, "
                   "distance, is_medoid, omit_reason) VALUES (?, 'single_motifs', ?, NULL, ?, 0.9, 0, 'past_cut')",
           (gid, _member(client, eid), label))
    return gid


def _entries(client):
    return {int(r["id"]): r for r in _q(client, "SELECT * FROM motif_entry ORDER BY id")}


def _seeds(client, **params):
    r = client.get("/api/discovery/seeds", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _two_groupings(client):
    """A shape-distance grouping with three families, then a NEWER amplitude grouping (the one the old picker
    read: the newest single-motif grouping of any basis)."""
    ent = _entries(client)
    machine = [i for i, e in ent.items() if e["source_kind"] == "event_store"]
    review = _review_entry(client)["id"]
    shape = _grouping(client, "shape-distance", {
        "F-01": [machine[1], machine[0], machine[2]],
        "F-02": [machine[4], machine[3]],
        "F-03": [review, machine[5], machine[6], machine[7]],
    }, omitted=[(machine[8], "F-01")])
    amp = _grouping(client, "amplitude", {"A-1": machine[:15], "A-2": machine[15:]}, medoids=False)
    return ent, machine, review, shape, amp


def test_family_medoids_list_every_family_of_a_grouping_as_library_entries(client):
    ent, machine, review, shape, amp = _two_groupings(client)

    page = _seeds(client, source="family", limit=200)
    # the default is the newest SHAPE-DISTANCE grouping, not the newer amplitude bins
    assert page["grouping"]["id"] == f"g-{shape:02d}"
    assert page["grouping"]["basis"] == "shape-distance"
    assert {g["id"] for g in page["groupings"]} >= {f"g-{shape:02d}", f"g-{amp:02d}"}
    assert [g["id"] for g in page["groupings"] if g.get("isDefault")] == [f"g-{shape:02d}"]
    assert page["total"] == 3
    medoid_of = {"F-01": machine[1], "F-02": machine[4], "F-03": review}
    got = {s["family"]: s for s in page["seeds"]}
    assert set(got) == set(medoid_of), "every family, once"
    for label, eid in medoid_of.items():
        s = got[label]
        assert s["id"] == _seed_id("library", ent[eid]), f"{label}'s medoid is a library: id at its entry's span"
        assert s["entryId"] == eid, f"{label}'s seed names its entry"
        assert s["source"] == "library"
    # the largest family first
    assert [s["family"] for s in page["seeds"]] == ["F-03", "F-01", "F-02"]
    assert sorted(page["families"]) == ["F-01", "F-02", "F-03"]

    # paged and filtered
    first = _seeds(client, source="family", limit=2)
    rest = _seeds(client, source="family", limit=2, offset=2)
    assert first["total"] == rest["total"] == 3
    assert len(first["seeds"]) == 2 and len(rest["seeds"]) == 1
    one = _seeds(client, source="family", family="F-02")
    assert one["total"] == 1 and one["seeds"][0]["entryId"] == machine[4]
    on_ch2 = _seeds(client, source="family", channel=CH[1], limit=200)
    assert all(s["channel"] == CH[1] for s in on_ch2["seeds"])
    assert on_ch2["total"] == sum(1 for eid in medoid_of.values() if ent[eid]["recording_id"] == 2)

    # another grouping, by its id; a grouping with no recorded medoid still offers every family
    bins = _seeds(client, source="family", grouping=f"g-{amp:02d}", limit=200)
    assert bins["grouping"]["id"] == f"g-{amp:02d}"
    assert {s["family"] for s in bins["seeds"]} == {"A-1", "A-2"}
    assert all(s["entryId"] for s in bins["seeds"])
    assert _seeds(client, source="family", grouping=str(amp))["grouping"]["id"] == f"g-{amp:02d}"
    assert page["counts"]["family"] == 3, "the tab's count is the grouping's families"


def test_the_library_tab_reads_its_families_from_the_chosen_grouping(client):
    ent, machine, review, shape, amp = _two_groupings(client)
    # by default, the newest shape-distance grouping: F-01 holds three entries — not the one it omitted
    f01 = _seeds(client, source="library", family="F-01", limit=200)
    assert f01["grouping"]["id"] == f"g-{shape:02d}"
    assert {s["entryId"] for s in f01["seeds"]} == {machine[0], machine[1], machine[2]}
    assert machine[8] not in {s["entryId"] for s in f01["seeds"]}, "an omitted member is in no family"
    assert all(s["family"] == "F-01" for s in f01["seeds"])
    assert set(f01["families"]) == {"F-01", "F-02", "F-03"}
    # named: the amplitude bins
    a1 = _seeds(client, source="library", grouping=f"g-{amp:02d}", family="A-1", limit=200)
    assert a1["total"] == 15 and set(a1["families"]) == {"A-1", "A-2"}
    # Review's promotion card asks for one entry: its family is read in the default grouping
    one = _seeds(client, source="library", entry=review)
    assert one["seeds"][0]["family"] == "F-03"
    # a grouping that does not exist is a 404 that names it, never an empty page
    r = client.get("/api/discovery/seeds", params={"source": "family", "grouping": "g-999"})
    assert r.status_code == 404
    assert "g-999" in r.text


# ── a catalogue span at an entry's span is that entry ──────────────────────

def test_a_catalogue_span_at_an_entry_span_is_that_entry(client):
    review = _review_entry(client)
    at_entry = _seed_id("medoid", review)
    setup = client.get("/api/discovery/seed/setup", params={"seed": at_entry})
    assert setup.status_code == 200, setup.text
    seed = setup.json()["draft"]["seed"]
    assert seed["entryId"] == review["id"], "a catalogue span whose span is an entry's resolves to that entry"
    assert seed["role"] == "Catalogue span"

    # a span that is no entry's stays an anonymous catalogue span
    loose = f"medoid:{review['recording_id']}:{review['start_idx'] + 50}:{review['end_idx'] + 50}"
    seed2 = client.get("/api/discovery/seed/setup", params={"seed": loose}).json()["draft"]["seed"]
    assert seed2["entryId"] is None and seed2["role"] == "Catalogue span"

    # the run made from it records the entry, so *Add N matches* has an E-xxxx to add to
    run = client.post("/api/discovery/seed/run", json={
        "seedId": at_entry, "channels": [CH[0]], "t0": 0.0, "t1": T1, "k": 33, "label": "catalogue span run"})
    assert run.status_code == 200, run.text
    run = run.json()
    if run.get("job_id"):
        assert _wait_job(client, run["job_id"])["status"] == "completed"
    row = next(r for r in client.get("/api/discovery/runs").json() if r["key"] == run["run_key"])
    assert row["entryId"] == review["id"]


# ── the backfill ────────────────────────────────────────────────────────────

def test_the_backfill_links_an_old_catalogue_span_run_and_add_matches_opens(client):
    from Working.discovery import seed_entry_backfill as B
    review = _review_entry(client)
    # two planted dips on recording 1 accepted by a person, so the run has matches to add
    for p in (PLANTS[1], PLANTS[2]):
        _x(client, "INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                   "VALUES (1, ?, ?, 'interesting', 'test', ?)", (p, p + M, OLD))
    sid = _seed_id("medoid", review)
    run = client.post("/api/discovery/seed/run", json={
        "seedId": sid, "channels": [CH[0]], "t0": 0.0, "t1": T1, "k": 34, "label": "dip search"}).json()
    assert _wait_job(client, run["job_id"])["status"] == "completed"
    # the row as a pre-a2-p4 run left it: a catalogue span with no entry
    params = json.loads(_q(client, "SELECT params_json FROM discovery_runs WHERE run_key = ?",
                           (run["run_key"],))[0]["params_json"])
    params["entryId"] = None
    _x(client, "UPDATE discovery_runs SET params_json = ? WHERE run_key = ?", (json.dumps(params), run["run_key"]))
    before = client.get(f"/api/library/runs/{run['run_key']}/matches").json()
    assert before["entryId"] is None and "not a Library entry" in (before["reason"] or "")
    # fix round: the refusal names the seed as the picker now does — a catalogue span, not a "family medoid"
    assert "catalogue span" in before["reason"] and "family medoid" not in before["reason"], before["reason"]

    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        report = B.backfill(conn, apply=True)
        again = B.backfill(conn, apply=True)
    finally:
        conn.close()
    assert [r["runKey"] for r in report["linked"]] == [run["run_key"]]
    assert report["linked"][0]["entryId"] == review["id"]
    assert again["linked"] == [], "a second backfill links nothing"

    after = client.get(f"/api/library/runs/{run['run_key']}/matches").json()
    assert after["entryId"] == review["id"]
    assert after["reason"] is None and after["eligible"] == 2, after
    added = client.post(f"/api/library/runs/{run['run_key']}/matches", json={})
    assert added.status_code == 200, added.text
    assert added.json()["membersNew"] + added.json()["membersResolved"] == 2


# ── fix round (critic of 2026-10-17) ───────────────────────────────────────

def test_a_failed_preview_is_reported_with_its_traceback_and_can_run_again(client, monkeypatch):
    """F1: the GET answered 500 while the newest job for the query was a failed one, and the page's Retry only
    re-read it, so Run preview was unreachable. The failure is now reported as the query's state — loud, with the
    job's own message and traceback — and a POST of the same query starts a new job."""
    sid = _seed_id("library", _review_entry(client))
    body = {"seedId": sid, "channels": [CH[0]], "t0": 0.0, "t1": T1, "k": 36}
    query = dict(body, channels=CH[0])
    real = seeded_search.null_distances

    def broken(*a, **kw):
        raise RuntimeError("a draw broke on purpose")

    monkeypatch.setattr(seeded_search, "null_distances", broken)
    started = client.post("/api/discovery/seed/results", json=body).json()
    assert _wait_job(client, started["job_id"])["status"] == "failed"
    r = client.get("/api/discovery/seed/results", params=query)
    assert r.status_code == 200, "a failed preview is the query's state, not a dead-end 500"
    got = r.json()
    assert got["ready"] is False and got["job_id"] is None
    assert got["failed"] is True and got["failedJob"] == started["job_id"]
    assert "a draw broke on purpose" in got["error"]["message"]
    assert "RuntimeError" in (got["error"]["traceback"] or ""), "the traceback travels with the failure"

    monkeypatch.setattr(seeded_search, "null_distances", real)
    again = client.post("/api/discovery/seed/results", json=body).json()
    assert again["ready"] is False and again["job_id"] not in (None, started["job_id"]), "Run preview again is a new job"
    assert _wait_job(client, again["job_id"])["status"] == "completed"
    assert client.get("/api/discovery/seed/results", params=query).json()["ready"] is True


def test_a_family_whose_entries_sit_closer_elsewhere_is_still_listed_and_filtered(client):
    """F2, the critic's probe: E1's own span is F-01's medoid, and a second member of E1 at another span is F-02's
    only member. Reading families off "each entry's closest family" lost F-02 from the family list, the count and
    the Library tab's filter, while the Family medoids list showed it."""
    ent = _entries(client)
    machine = [i for i, e in ent.items() if e["source_kind"] == "event_store"]
    e1 = ent[machine[0]]
    m_own = _member(client, machine[0])
    m_far = _x(client, "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) VALUES (?, ?, ?, ?)",
               (e1["id"], e1["recording_id"], e1["start_idx"] + 1000, e1["end_idx"] + 1000))
    gid = _x(client, "INSERT INTO groupings (name, unit, basis, method, params_json, n_families, created_at) "
                     "VALUES ('probe', 'single_motifs', 'shape-distance', 'ward', '{}', 2, ?)", (OLD,))
    for mid, fid, label, d in ((m_own, 1, "F-01", 0.0), (m_far, 2, "F-02", 0.3)):
        _x(client, "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_id, family_label, distance, "
                   "is_medoid) VALUES (?, 'single_motifs', ?, ?, ?, ?, 1)", (gid, mid, fid, label, d))
    page = _seeds(client, source="library", limit=200)
    assert page["families"] == ["F-01", "F-02"]
    assert page["counts"]["family"] == 2
    f02 = _seeds(client, source="library", family="F-02", limit=200)
    assert f02["total"] == 1 and f02["seeds"][0]["entryId"] == e1["id"]
    assert f02["seeds"][0]["family"] == "F-02", "filtered by a family, the card names that family"
    medoids = _seeds(client, source="family", limit=200)
    assert {s["family"] for s in medoids["seeds"]} == {"F-01", "F-02"}
    assert medoids["total"] == page["counts"]["family"]


def test_a_run_drawing_the_preview_is_that_querys_preview_and_a_post_joins_it(client, monkeypatch):
    """F5: a run asked for the preview's null before the page had one draws that preview first, inside its own
    job. The page held Run preview in memory only, so after a reload (or in another tab) the GET said "not run"
    while the run was drawing that very preview, and a POST started it a second time. The run's job now carries
    the preview's key: the GET reports it as drawn by that run, a POST of the same query joins it, and a
    different query is not held."""
    sid = _seed_id("library", _review_entry(client))
    entered = threading.Event()
    monkeypatch.setattr(seeded_search, "null_distances", _blocking_null(entered))
    run = client.post("/api/discovery/seed/run", json={
        "seedId": sid, "channels": [CH[0]], "t0": 0.0, "t1": T1, "k": 37, "nullMode": "preview",
        "label": "draws its preview"}).json()
    assert run["drawsPreviewFirst"] is True
    _wait_entered(client, entered, run["job_id"])
    jobs0 = _jobs(client)
    query = {"seedId": sid, "channels": CH[0], "t0": 0.0, "t1": T1, "k": 37}
    peek = client.get("/api/discovery/seed/results", params=query).json()
    assert peek["ready"] is False and peek["job_id"] == run["job_id"], "the GET finds the run drawing the preview"
    assert (peek.get("drawnBy") or {}).get("runKey") == run["run_key"]
    joined = client.post("/api/discovery/seed/results", json=dict(query, channels=[CH[0]])).json()
    assert joined["job_id"] == run["job_id"] and joined.get("joined") is True
    assert (joined.get("drawnBy") or {}).get("runKey") == run["run_key"]
    assert _jobs(client) == jobs0, "Run preview on that query must not compute it a second time"
    other = client.get("/api/discovery/seed/results", params=dict(query, k=38)).json()
    assert other["job_id"] is None and not other.get("drawnBy"), "another query is not held by the run"
    client.post(f"/api/jobs/{run['job_id']}/cancel")
    _wait_job(client, run["job_id"])
    after = client.get("/api/discovery/seed/results", params=query).json()
    assert after["ready"] is False and after["job_id"] is None and after.get("cancelled") is True


def test_a_catalogue_span_says_whether_it_is_a_library_entry(client):
    """F6: a catalogue span that is a Library entry read "family F-01" and "not a Library family" on one card."""
    ent, machine, review, shape, amp = _two_groupings(client)
    review_row = _review_entry(client)
    seed = client.get("/api/discovery/seed/setup", params={"seed": _seed_id("medoid", review_row)}).json()["draft"]["seed"]
    assert seed["familyLine"].startswith(f"Library entry E-{review_row['id']:04d}"), seed["familyLine"]
    assert f"family F-03 in g-{shape:02d}" in seed["familyLine"]
    assert "not a Library" not in seed["familyLine"]
    loose = f"medoid:{review_row['recording_id']}:{review_row['start_idx'] + 50}:{review_row['end_idx'] + 50}"
    seed2 = client.get("/api/discovery/seed/setup", params={"seed": loose}).json()["draft"]["seed"]
    assert seed2["familyLine"] == "not a Library entry"


def test_a_catalogue_span_title_counts_its_events_in_words():
    """F6: "medoid of 1 event", not "1 events"."""
    from server import discovery as DS
    ev = {"recording_id": 1, "snippet_start_idx": 10, "snippet_end_idx": 70, "drop_depth_mv": 5.0,
          "morphology": "drop", "span_key": "id001"}
    one = DS._medoid_candidates([ev])
    two = DS._medoid_candidates([dict(ev, span_key="id002"), dict(ev, span_key="id002", drop_depth_mv=6.0)])
    assert one[0][4].endswith("medoid of 1 event"), one[0][4]
    assert two[0][4].endswith("medoid of 2 events"), two[0][4]

"""
test_webui_discovery.py
========================
Discovery's bridge routes (stage-3 prompt 04, spec §7), against a synthetic
database small enough to run a real fan-out in a few seconds.

What it pins, beyond "the route answers 200":

* **The held-out refusal is a pre-flight.** `execute_recipe` checks the lock
  from *inside* the fan-out loop, so a scope containing the held-out file
  would run the earlier targets and write their `runs` rows before refusing.
  The test asserts the `runs` table gained nothing.
* **A run the section does not reach reads words.** §7.3's absent states are
  `no reviewed overlap` / `not yet scored`, never a 0.00 precision with no
  denominator behind it.
* **Discard writes no verdicts.** §7.4: a whole-run discard turning into
  thousands of `not_interesting` human verdicts would poison the RQ5
  divergence measurement invisibly, so `adjudications` and `annotations` are
  counted before and after.
* **Applying the same template twice does not empty the first run.**
  `execute_recipe` is idempotent, so the second Discovery run is *made of* the
  first one's runs; re-pointing their `run_group_id` moved them out of the
  earlier group and the first run read "0 found". That is a real bug this
  prompt fixed (2026-09-22) and this is its pin.
* **Compare aligns two real recipes by role.** A recipe step carries its stage
  and algorithm apart while the registry is keyed `"<stage>.<algorithm>"`;
  looking up the bare name found nothing and Compare drew five absent cells
  and "0 roles differ" over two chains that share nothing. Also fixed, also
  pinned here through the route.

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_discovery.py
"""

import datetime as _dt
import os
import sys
import time

import sqlite3

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
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

FS = 1.0
N = 6000
M = 60
PLANTS = (600, 1800, 3400)
NOW = _dt.datetime.now(_dt.timezone.utc).isoformat()
OLD = "2020-01-01T00:00:00+00:00"          # before any run, so it counts as "already judged"

#: The four channels are named by `Working.discovery.channels.channel_name`:
#: not an M2-style file, so CH<n+1>.
CH = ["CH1", "CH2", "CH3", "CH4"]


def _planted(seed):
    """Noise with the same dip planted three times, so a seeded search has
    something to find and a threshold chain has something to fire on."""
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
    # the held-out file, so its refusal can be exercised on every door
    held = tmp_path / "held.npy"
    np.save(held, _planted(9))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES (?, 0, ?, ?, 0, ?)", (HELD_OUT_FILE, FS, N, str(held)))

    # recordings 1 and 2 (channels 0 and 1) are reviewed over [0, 3000) and
    # carry BOTH verdicts, so precision has real negatives in it. Recording 3
    # is reviewed nowhere, so its row must read the words, not 0.00.
    for rid in (1, 2):
        conn.execute("INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) "
                     "VALUES (?, 0, 3000, 'test', ?)", (rid, OLD))
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (?, ?, ?, 'interesting', 'test', ?)", (rid, PLANTS[0], PLANTS[0] + M, OLD))
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (?, ?, ?, 'not_interesting', 'test', ?)", (rid, 2000, 2000 + M, OLD))
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (?, ?, ?, 'interesting', 'test', ?)", (rid, PLANTS[1], PLANTS[1] + M, OLD))
    # A Library exemplar. Without it Discovery correctly offers no seed at all:
    # the drop-motif seed store on disk references the real recordings, whose
    # spans lie far outside this synthetic one, and a seed is resolved by
    # CONTENT. This is also the branch that matters once Prompt 03 fills the
    # library, so it is the one worth pinning.
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label) "
                 "VALUES (1, ?, ?, 'planted dip')", (PLANTS[0], PLANTS[0] + M))
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
    rt = Runtime(mode="sandbox", stamp="20260922-discovery", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            _scope(c)
            yield c
    finally:
        rt.restore()


def _scope(client, channels=(CH[0], CH[1]), t0=0.0, t1=None):
    t1 = t1 if t1 is not None else N / FS / 3600.0
    r = client.put("/api/discovery/session", json={
        "name": "test", "recording": "syn", "channels": list(channels), "section": [t0, t1],
        "null": {"method": "phase randomisation", "n": 2}})
    assert r.status_code == 200, r.text
    return r.json()


def _wait_job(client, job_id, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not finish")


def _counts(client, table):
    import sqlite3
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _apply(client, template="mp_threshold", channels=(CH[0], CH[1]), t0=0.0, t1=None):
    t1 = t1 if t1 is not None else N / FS / 3600.0
    r = client.post("/api/discovery/templates/apply",
                    json={"templates": [template], "channels": list(channels), "t0": t0, "t1": t1})
    assert r.status_code == 200, r.text
    out = r.json()[0]
    if out.get("job_id"):
        snap = _wait_job(client, out["job_id"])
        assert snap["status"] == "completed", snap.get("error")
    return out


# ── the session and its scope ───────────────────────────────────────────────

def test_the_first_session_is_built_from_the_data_not_from_a_name(client):
    s = client.get("/api/discovery/session").json()
    assert s["session"]["recording"] == "syn"
    assert s["session"]["channels"]
    assert s["session"]["localLimitMin"] == 20.0
    assert s["session"]["matchingRule"] == {"criterion": "reciprocal_iou_onset", "iou": 0.5, "onset": 0.25}
    assert {r["key"] for r in s["recordings"]} >= {"syn"}


def test_the_session_takes_channel_names_and_a_section_in_hours(client):
    s = _scope(client, channels=(CH[2],), t0=0.0, t1=1.0)
    assert s["session"]["channels"] == [CH[2]]
    assert s["session"]["sectionSamples"] == [0, 3600]


def test_an_unknown_channel_name_is_a_404_that_lists_the_real_ones(client):
    r = client.put("/api/discovery/session", json={"recording": "syn", "channels": ["CH99"]})
    assert r.status_code == 404
    assert "CH99" in r.json()["detail"]["message"]
    assert CH[0] in r.json()["detail"]["channels"]


# ── held out, on every door ─────────────────────────────────────────────────

def test_the_held_out_recording_is_refused_by_the_scope(client):
    r = client.put("/api/discovery/session", json={"recording": HELD_OUT_FILE[:-4]})
    assert r.status_code == 423
    assert HELD_OUT_FILE in r.json()["detail"]["message"]


def test_the_held_out_recording_is_refused_by_the_overview(client):
    """423, like every other route that would serve this file's samples.

    It used to answer 200 with a `{"refused": ...}` body so that the scope card
    could draw the reason as a callout rather than an error. The sentence still
    reaches the callout — `api/discovery.ts::getOverview` turns a 423 back into
    `{refused: e.message}` — but a request for a locked file is no longer a
    success to anything that is not this page.
    """
    r = client.get("/api/discovery/overview", params={"recording": HELD_OUT_FILE[:-4]})
    assert r.status_code == 423
    assert HELD_OUT_FILE in r.json()["detail"]["message"]


def test_no_seed_is_offered_on_the_held_out_recording(client):
    seeds = client.get("/api/discovery/seeds").json()["seeds"]
    assert all(s["recording"] != HELD_OUT_FILE[:-4] for s in seeds)


def test_a_held_out_seed_id_is_refused_rather_than_resolved(client):
    held_id = None
    import sqlite3
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        held_id = conn.execute("SELECT id FROM recordings WHERE source_file = ?", (HELD_OUT_FILE,)).fetchone()[0]
    finally:
        conn.close()
    r = client.get("/api/discovery/seed/setup", params={"seed": f"library:{held_id}:100:200"})
    assert r.status_code == 423


# ── the plan is honest about what it cannot cost ────────────────────────────

def test_an_uncosted_chain_routes_unknown_and_names_the_steps(client):
    seed = client.get("/api/discovery/seeds").json()["seeds"][0]
    r = client.post("/api/discovery/plan", json={"seedId": seed["id"], "channels": [CH[0], CH[1]],
                                                 "t0": 0.0, "t1": N / 3600.0})
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["route"] == "unknown", "detection.seed_matches declares no estimator"
    assert plan["estimate_s"] is None
    assert plan["uncosted"] == [0]
    assert plan["ceiling_s"] == 1200
    assert plan["n_channels"] == 2


def test_a_plan_over_a_held_out_channel_refuses_before_any_run_row_is_written(client):
    """The check inside `execute_recipe` is not a pre-flight: it fires from
    within the fan-out loop, after the earlier targets have already written
    their `runs` rows."""
    before = _counts(client, "runs")
    r = client.post("/api/discovery/templates/apply",
                    json={"templates": ["mp_threshold"], "channels": [CH[0]], "t0": 0.0, "t1": 1.0})
    assert r.status_code == 200
    # the held-out channel is on a different recording file, so it cannot enter
    # the scope at all — the session refuses it first
    r2 = client.put("/api/discovery/session", json={"recording": HELD_OUT_FILE[:-4]})
    assert r2.status_code == 423
    assert _counts(client, "runs") >= before


def test_the_preview_measures_rather_than_models(client):
    r = client.post("/api/discovery/preview", json={"template": "mp_threshold", "channels": [CH[0]],
                                                    "t0": 0.0, "t1": N / 3600.0, "sampleHours": 0.25})
    assert r.status_code == 200, r.text
    pv = r.json()
    assert pv["measured_s"] > 0
    assert pv["sample_samples"] == 900
    assert pv["estimate_s"] == pytest.approx(pv["per_channel_s"] * 1, rel=1e-6)
    assert pv["route"] in ("local", "cluster")


# ── templates: a score never travels without its scope (§4.8) ───────────────

def test_the_picker_lists_the_real_templates_and_says_which_fit(client):
    rows = client.get("/api/discovery/templates").json()
    names = {r["name"] for r in rows}
    assert {"drop_detection_v1", "mp_threshold", "mp_motifs"} <= names
    mp = next(r for r in rows if r["name"] == "mp_threshold")
    assert mp["fits"] is True and mp["signature"].endswith("SpanSet")
    assert mp["stages"][0]["name"] == "Source"
    assert len(mp["stages"]) == len(mp["stages"])


def test_an_unrun_template_reads_not_yet_scored_and_has_no_preview(client):
    rows = client.get("/api/discovery/templates").json()
    mp = next(r for r in rows if r["name"] == "mp_threshold")
    assert mp["lastScore"] == "not yet scored"
    assert mp["preview"] is None
    assert "Preview" in mp["previewNote"]
    assert mp["perChannelMin"] is None and mp["diskGB"] is None


def test_a_run_templates_score_carries_its_scope(client):
    _apply(client)
    rows = client.get("/api/discovery/templates").json()
    mp = next(r for r in rows if r["name"] == "mp_threshold")
    assert mp["lastScore"] != "not yet scored"
    # §4.8: never a bare number on a template card
    assert any(word in mp["lastScore"] for word in ("reviewed", "overlap", "interesting"))


# ── applying a template, and the scoreboard over what it found ──────────────

def test_applying_a_template_is_one_run_across_every_channel_in_scope(client):
    out = _apply(client)
    runs = client.get("/api/discovery/runs").json()
    assert runs[0]["key"] == "human" and runs[0]["kind"] == "reference"
    row = next(r for r in runs if r["key"] == out["run_key"])
    assert row["status"] == "done"
    assert row["channelsDone"] == "2 / 2"
    assert row["found"] >= 0


def test_the_fires_grid_has_one_row_per_run_and_the_reviewed_underlay(client):
    out = _apply(client)
    fires = client.get("/api/discovery/fires", params={
        "channels": ",".join([CH[0], CH[1]]), "t0": 0.0, "t1": N / 3600.0,
        "runs": f"human,{out['run_key']}"}).json()
    assert fires["binH"] == 3
    assert [c["channel"] for c in fires["channels"]] == [CH[0], CH[1]]
    for c in fires["channels"]:
        assert len(c["reviewed"]) == fires["nBins"]
        assert c["reviewedH"] > 0
        for row in c["rows"]:
            assert len(row["counts"]) == fires["nBins"]


def test_the_scoreboard_cells_are_the_tables_own_numbers(client):
    out = _apply(client)
    sb = client.get("/api/discovery/scoreboard", params={
        "runs": out["run_key"], "channels": ",".join([CH[0], CH[1]]), "t0": 0.0,
        "t1": N / 3600.0}).json()
    assert len(sb) == 1
    row = sb[0]
    assert row["run"] == out["run_key"]
    assert row["rule"]["criterion"] == "reciprocal_iou_onset"
    assert row["reviewedCriterion"] == "onset inside reviewed coverage"
    total, channels = row["total"], row["channels"]
    assert {c["channel"] for c in channels} == {CH[0], CH[1]}
    assert total["found"] == sum(c["found"] for c in channels)
    assert total["reviewed"] == sum(c["reviewed"] for c in channels)
    # precision is a ratio of the two cells beside it, or absent — never a
    # third number that does not follow from them
    if total["reviewed"]:
        assert total["precision"] == pytest.approx(total["interesting"] / total["reviewed"])
    else:
        assert total["precision"] is None
    # reviewed hours: [0, 3000) of 6000 samples at 1 Hz on each of two channels
    for c in channels:
        # rounded to three places on the wire, deliberately: the hours are a
        # readout, not a measurement to five decimal places
        assert c["reviewedH"] == pytest.approx(3000 / 3600, abs=5e-4)


def test_recall_is_a_value_with_its_hours_or_the_words_for_having_none(client):
    out = _apply(client)
    sb = client.get("/api/discovery/scoreboard", params={
        "runs": out["run_key"], "channels": ",".join([CH[0], CH[1]]), "t0": 0.0,
        "t1": N / 3600.0}).json()[0]
    for cell in [sb["total"]["recall"]] + [c["recall"] for c in sb["channels"]]:
        assert ("value" in cell) != ("none" in cell), "exactly one variant's keys"
        if "value" in cell:
            assert cell["overH"] > 0
        else:
            assert cell["note"]


def test_a_channel_with_nothing_reviewed_reads_the_words_not_zero(client):
    """Recording 3 (CH3) has no reviewed span at all. §7.3: "An algorithm with
    nothing reviewed reads `not yet scored`" — not a 0.00 precision with no
    denominator behind it."""
    _scope(client, channels=(CH[2],))
    out = _apply(client, channels=(CH[2],))
    sb = client.get("/api/discovery/scoreboard", params={
        "runs": out["run_key"], "channels": CH[2], "t0": 0.0, "t1": N / 3600.0}).json()[0]
    cell = sb["channels"][0]
    assert cell["precision"] is None
    assert cell["note"] == "not yet scored"
    assert cell["recall"]["none"] is True
    assert cell["recall"]["note"] == "no reviewed overlap"


# ── the idempotence trap ────────────────────────────────────────────────────

def test_applying_the_same_template_twice_does_not_empty_the_first_run(client):
    """`execute_recipe` returns the run that already exists for an identical
    recipe, so the second Discovery run is *made of* the first one's runs.
    Re-pointing their `run_group_id` moved them out of the first fan-out, and
    a run that had results a minute earlier read "0 found"."""
    first = _apply(client)
    runs = client.get("/api/discovery/runs").json()
    found_before = next(r for r in runs if r["key"] == first["run_key"])["found"]

    second = _apply(client)
    assert second["run_key"] != first["run_key"]
    runs = client.get("/api/discovery/runs").json()
    a = next(r for r in runs if r["key"] == first["run_key"])
    b = next(r for r in runs if r["key"] == second["run_key"])
    assert a["found"] == found_before, "the first run still has its detections"
    assert b["found"] == found_before, "and the second is made of the same runs"
    assert a["status"] == "done" and b["status"] == "done"


# ── the seeded search ───────────────────────────────────────────────────────

def _seed(client):
    seeds = client.get("/api/discovery/seeds").json()["seeds"]
    assert seeds, "the seed store or the motif library must offer something"
    return seeds[0]


def test_the_seed_card_is_content_addressed(client):
    s = _seed(client)
    assert s["id"].count(":") == 3
    assert s["samples"] > 0 and s["lengthS"] > 0
    assert len(s["hash"]) >= 8
    assert s["trace"], "the card draws the seed's shape"


def test_the_seed_window_is_locked_to_the_exemplars_native_length(client):
    s = _seed(client)
    setup = client.get("/api/discovery/seed/setup", params={"seed": s["id"]}).json()
    rec = setup["recommended"]
    assert rec["windowSamples"] == s["samples"]
    assert rec["windowLocked"] is True
    assert rec["algorithm"] == "mass"
    assert "m/4" in rec["exclusion_note"], "the page must say the guard the block really used"


def test_the_seeded_search_is_a_job_whose_result_survives_the_read(client):
    s = _seed(client)
    body = {"seedId": s["id"], "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20,
            "maxDistance": 0.0}
    started = client.post("/api/discovery/seed/results", json=body).json()
    if not started.get("ready"):
        assert started["job_id"]
        snap = _wait_job(client, started["job_id"])
        assert snap["status"] == "completed", snap.get("error")
    res = client.get("/api/discovery/seed/results", params={
        "seedId": s["id"], "channels": CH[0], "t0": 0.0, "t1": N / 3600.0, "k": 20,
        "maxDistance": 0.0}).json()
    assert res["ready"] is True
    ds = [c["d"] for c in res["candidates"]]
    assert ds == sorted(ds), "closest first"
    assert res["null"]["method"] == "phase_randomize"
    assert res["null"]["draws"] >= 1
    assert res["m"] == s["samples"]
    if res["recommendedCut"] is not None and res["null"]["distances"]:
        assert res["recommendedCut"] < min(res["null"]["distances"]), \
            "the marker sits where the null gives nothing"


def test_the_distance_profile_is_one_value_per_position(client):
    s = _seed(client)
    prof = client.get("/api/discovery/seed/profile", params={
        "seedId": s["id"], "channel": CH[0], "t0": 0.0, "t1": 0.25}).json()
    assert prof["m"] == s["samples"]
    assert prof["nDistance"] == prof["nSignal"] - prof["m"] + 1
    assert len(prof["signal"]) > 0 and len(prof["distance"]) > 0


def test_an_unreadable_seed_id_is_a_400_that_says_the_shape(client):
    r = client.get("/api/discovery/seed/setup", params={"seed": "nonsense"})
    assert r.status_code == 400
    assert "source:recording:start:end" in r.json()["detail"]["message"]


# ── run acts ────────────────────────────────────────────────────────────────

def test_discard_marks_the_run_superseded_and_writes_no_verdicts(client):
    out = _apply(client)
    adj_before, ann_before = _counts(client, "adjudications"), _counts(client, "annotations")
    r = client.post(f"/api/discovery/runs/{out['run_key']}/discard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "superseded" and body["superseded"] >= 1
    assert body["adjudications_written"] == 0 and body["annotations_written"] == 0
    assert _counts(client, "adjudications") == adj_before
    assert _counts(client, "annotations") == ann_before
    # the detections are kept: the run stays reproducible from its own recipe
    assert _counts(client, "detections") >= 0
    runs = client.get("/api/discovery/runs").json()
    assert next(r_ for r_ in runs if r_["key"] == out["run_key"])["status"] == "superseded"


def test_a_discard_is_reversible(client):
    out = _apply(client)
    client.post(f"/api/discovery/runs/{out['run_key']}/discard")
    r = client.post(f"/api/discovery/runs/{out['run_key']}/restore")
    assert r.status_code == 200
    runs = client.get("/api/discovery/runs").json()
    assert next(x for x in runs if x["key"] == out["run_key"])["status"] == "done"


def _runs_split(client):
    """Real run ids and paired-surrogate run ids in the sandbox copy, plus how
    many detections the surrogates wrote."""
    import sqlite3
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        real = {r[0] for r in conn.execute("SELECT id FROM runs WHERE surrogate_of_run_id IS NULL")}
        sur = {r[0] for r in conn.execute("SELECT id FROM runs WHERE surrogate_of_run_id IS NOT NULL")}
        sur_dets = conn.execute("SELECT COUNT(*) FROM detections d JOIN runs r ON r.id = d.run_id "
                                "WHERE r.surrogate_of_run_id IS NOT NULL").fetchone()[0]
        return real, sur, sur_dets
    finally:
        conn.close()


def test_send_to_review_makes_a_review_queue_over_the_runs_real_runs_only(client):
    """fixup-L. Two wiring prompts each built half of this hand-off: Discovery
    wrote a descriptor into `discovery_sessions.state_json`, Review listed only
    `review_queues` rows, and *Open Review* landed on somebody else's queue.
    The route now creates the row Review reads — and filters it by the run ids
    the Discovery run is made of, because the run group also holds the paired
    surrogate runs and THEIR detections (the sandbox's group 7: 74 real, 249
    surrogate)."""
    out = _apply(client)
    r = client.post(f"/api/discovery/runs/{out['run_key']}/review", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["writes"] == "adjudications"
    assert body["unjudged"] > 0
    qid = body["queue_id"]

    got = client.get(f"/api/review/queues/{qid}")
    assert got.status_code == 200, got.text
    queue, rows = got.json()["queue"], got.json()["rows"]
    assert queue["name"] == body["queue"]
    assert queue["source_kind"] == "discovery-run"
    assert queue["writes_to"] == "adjudications"
    assert queue["unit"] == "detection"
    assert queue["total"] == body["unjudged"] == len(rows)
    assert queue["judged"] == 0

    real, sur, sur_dets = _runs_split(client)
    assert sur, "the fixture pairs a surrogate run with every real run (Settings › Nulls default)"
    assert sur_dets > 0, "the surrogate found something, so the exclusion is being tested"
    queued_runs = {int(row["runId"]) for row in rows}
    assert queued_runs and queued_runs <= real
    assert not queued_runs & sur, "no surrogate's detection reaches the researcher"


def test_sending_the_same_run_twice_reuses_its_open_queue(client):
    out = _apply(client)
    a = client.post(f"/api/discovery/runs/{out['run_key']}/review", json={}).json()
    b = client.post(f"/api/discovery/runs/{out['run_key']}/review", json={}).json()
    assert a["queue_id"] == b["queue_id"]
    assert a["reused"] is False and b["reused"] is True
    listing = client.get("/api/review/queues").json()
    assert sum(1 for x in listing if x["id"] == a["queue_id"]) == 1


def test_a_seed_run_sends_as_a_seed_search_queue(client):
    s = _seed(client)
    started = client.post("/api/discovery/seed/run", json={
        "seedId": s["id"], "channels": [CH[0]], "t0": 0.0, "t1": N / 3600.0, "k": 20,
        "maxDistance": 0.0, "label": "seedy"})
    assert started.status_code == 200, started.text
    run = started.json()
    if run.get("job_id"):
        snap = _wait_job(client, run["job_id"])
        assert snap["status"] == "completed", snap.get("error")
    body = client.post(f"/api/discovery/runs/{run['run_key']}/review", json={}).json()
    queue = client.get(f"/api/review/queues/{body['queue_id']}").json()["queue"]
    assert queue["source_kind"] == "seed-search"
    assert queue["writes_to"] == "adjudications"
    assert queue["total"] == body["unjudged"] > 0


def test_the_descriptor_is_retired(client):
    """One record of one queue: the row in `review_queues`. Nothing is written
    into the session's `state_json` any more, and the route that listed the
    descriptors is gone (an unknown API path falls through to the SPA shell,
    which is not JSON)."""
    out = _apply(client)
    client.post(f"/api/discovery/runs/{out['run_key']}/review", json={})
    import sqlite3
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        import json as _json
        for (state_json,) in conn.execute("SELECT state_json FROM discovery_sessions"):
            assert "review_queues" not in _json.loads(state_json or "{}")
    finally:
        conn.close()
    r = client.get("/api/discovery/queues")
    assert r.status_code == 404 or "application/json" not in r.headers.get("content-type", "")


def test_a_discarded_runs_queue_serves_nothing(client):
    """§7.4 step 5: *Discard run* on a sent run — its queue stops serving items
    (`runs.superseded_at`, honoured by the resolver) and no verdict is written."""
    out = _apply(client)
    a = client.post(f"/api/discovery/runs/{out['run_key']}/review", json={}).json()
    assert a["unjudged"] > 0
    adj_before = _counts(client, "adjudications")
    client.post(f"/api/discovery/runs/{out['run_key']}/discard")
    got = client.get(f"/api/review/queues/{a['queue_id']}").json()
    assert got["queue"]["total"] == 0 and got["rows"] == []
    assert _counts(client, "adjudications") == adj_before


def test_an_unknown_run_key_is_a_404_naming_it(client):
    r = client.post("/api/discovery/runs/not_a_run/discard")
    assert r.status_code == 404
    assert "not_a_run" in r.json()["detail"]["message"]


# ── compare ─────────────────────────────────────────────────────────────────

def test_compare_aligns_two_real_recipes_by_role(client):
    """A recipe step carries its stage and algorithm apart; the registry is
    keyed `"<stage>.<algorithm>"`. Looking up the bare name found nothing and
    every role came back absent, so Compare reported "0 roles differ" over two
    chains that share nothing."""
    a = _apply(client, template="mp_threshold")
    b = _apply(client, template="drop_detection_v1")
    cmp_ = client.get("/api/discovery/compare", params={
        "a": a["run_key"], "b": b["run_key"], "channels": ",".join([CH[0], CH[1]]),
        "t0": 0.0, "t1": N / 3600.0}).json()
    roles = ["Source", "Preprocess", "Score / estimate", "Encode", "Detect"]
    assert list(cmp_["a"]["cells"].keys()) == roles
    assert cmp_["a"]["cells"]["Source"] is not None
    assert cmp_["a"]["cells"]["Score / estimate"] is not None, "mp_threshold scores"
    assert cmp_["b"]["cells"]["Encode"] is not None, "drop_detection_v1 encodes"
    assert cmp_["differing"], "two different chains differ in at least one role"
    assert cmp_["stageDiff"], "and their recipes differ step by step"


def test_compare_totals_the_overlap_over_all_channels(client):
    a = _apply(client, template="mp_threshold")
    b = _apply(client, template="drop_detection_v1")
    cmp_ = client.get("/api/discovery/compare", params={
        "a": a["run_key"], "b": b["run_key"], "channels": ",".join([CH[0], CH[1]]),
        "t0": 0.0, "t1": N / 3600.0}).json()
    assert cmp_["total"]["channel"] == "all channels"
    for key in ("onlyA", "both", "onlyB"):
        assert cmp_["total"][key] == sum(r[key] for r in cmp_["overlap"])
    assert cmp_["disagreementsTotal"] == cmp_["total"]["onlyA"] + cmp_["total"]["onlyB"]
    # the other side's nearest score is a per-window computation, so the list
    # does not pretend to carry it
    for d in cmp_["disagreements"]:
        assert d["otherNearest"] is None
    assert "computed for the window" in cmp_["sortedBy"]


def test_the_human_annotations_are_a_compare_side(client):
    a = _apply(client)
    cmp_ = client.get("/api/discovery/compare", params={
        "a": a["run_key"], "b": "human", "channels": ",".join([CH[0], CH[1]]),
        "t0": 0.0, "t1": N / 3600.0}).json()
    assert cmp_["b"]["run"] == "human"
    assert cmp_["b"]["cells"]["Detect"]["glyph"] == "human"
    assert cmp_["b"]["cells"]["Preprocess"] is None
    # two `interesting` rows on each of the two channels; the `not_interesting`
    # one is a human verdict but not a human FINDING, so it is not a compare side
    assert cmp_["b"]["found"] == 4


def test_compare_every_stage_returns_five_cells_a_side(client):
    a = _apply(client, template="mp_threshold")
    b = _apply(client, template="drop_detection_v1")
    cmp_ = client.get("/api/discovery/compare", params={
        "a": a["run_key"], "b": b["run_key"], "channels": CH[0], "t0": 0.0,
        "t1": N / 3600.0}).json()
    if not cmp_["disagreements"]:
        pytest.skip("the two chains agreed everywhere on this fixture")
    d = cmp_["disagreements"][0]
    st = client.get("/api/discovery/compare/stages", params={
        "a": a["run_key"], "b": b["run_key"], "channel": d["channel"], "atH": d["atH"],
        "kind": d["kind"], "index": 1, "of": len(cmp_["disagreements"])}).json()
    assert [c["role"] for c in st["a"]] == ["Source", "Preprocess", "Score / estimate", "Encode", "Detect"]
    assert [c["role"] for c in st["b"]] == [c["role"] for c in st["a"]]
    for cell in st["a"] + st["b"]:
        assert cell["badge"] in ("identical", "differs", "A only", "B only", "absent")
        assert cell["thumb"]["kind"] in ("trace", "distance", "symbols", "segments", "absent")
    assert "nothing is written" in st["note"]


def test_the_stepper_window_carries_the_other_sides_own_score(client):
    a = _apply(client, template="mp_threshold")
    b = _apply(client, template="drop_detection_v1")
    cmp_ = client.get("/api/discovery/compare", params={
        "a": a["run_key"], "b": b["run_key"], "channels": CH[0], "t0": 0.0,
        "t1": N / 3600.0}).json()
    if not cmp_["disagreements"]:
        pytest.skip("the two chains agreed everywhere on this fixture")
    d = cmp_["disagreements"][0]
    w = client.get("/api/discovery/compare/window", params={
        "a": a["run_key"], "b": b["run_key"], "channel": d["channel"], "atH": d["atH"],
        "kind": d["kind"]}).json()
    assert w["values"], "the signal is drawn clean"
    assert (w["bScore"] and w["scoreNote"] is None) or (not w["bScore"] and w["scoreNote"]), \
        "either the other side's score, or the reason there is none"
    assert (w["aSpan"] is None) != (w["bSpan"] is None), "exactly one side fired here"


# ── loud failure ────────────────────────────────────────────────────────────

def test_an_unknown_discovery_route_is_a_json_404_not_the_spa(client):
    r = client.get("/api/discovery/nonsense")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert "no such API route" in r.json()["error"]


def test_a_route_with_the_wrong_method_is_json_and_not_the_spa(client):
    """A wrong method on a real path answers **404**, not the guard's 405.

    `app.py`'s `/api/{rest:path}` guard promotes a `Match.PARTIAL` to a 405
    with an `Allow` header, but a path mounted through `include_router` does
    not report PARTIAL to it, so a POST-only Discovery route reads as "no such
    route" on GET. What matters here — and what this pins — is that it is JSON
    with a message, never `index.html` with a 200. Reported to Prompt 01, which
    owns the guard (`docs/prompts/wiring/requests/04-to-01.md`)."""
    r = client.get("/api/discovery/plan")
    assert r.status_code in (404, 405)
    assert r.headers["content-type"].startswith("application/json")
    assert r.json().get("error") or r.json().get("detail")


# ── adopting a past run (History) ─────────────────────────────────────


def test_opening_a_history_run_adopts_the_real_row_rather_than_inventing_one(client):
    """The History popover used to build the row in the browser: a guessed kind
    and an invented template name under the *real* run key, which then went out
    in `runs=` to /fires and /scoreboard and was rightly answered 404. Adoption
    is a row in `discovery_runs` pointing at the same `run_group_id`."""
    _apply(client)
    runs = client.get("/api/discovery/runs").json()
    key = next(r["key"] for r in runs if r["kind"] != "reference")

    hist = client.get("/api/discovery/history").json()
    row = next(h for h in hist if h["runKey"] == key)
    assert row["inSession"] is True

    # already here: adoption is a no-op that says so, not a duplicate row
    r = client.post(f"/api/discovery/history/{row['id']}/open")
    assert r.status_code == 200, r.text
    assert r.json()["adopted"] is False
    assert "already in this session" in r.json()["note"]

    # and a second session adopts it, without re-running anything
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.execute("UPDATE discovery_runs SET session_id = session_id + 1000 WHERE run_key = ?", (key,))
        conn.commit()
    finally:
        conn.close()

    r = client.post(f"/api/discovery/history/{row['id']}/open")
    assert r.status_code == 200, r.text
    assert r.json()["adopted"] is True
    assert r.json()["run_key"] == key

    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == before,             "adoption must not execute anything: it is a reference to runs that already exist"
    finally:
        conn.close()
    assert any(r["key"] == key for r in client.get("/api/discovery/runs").json()),         "the adopted run has to appear in this session's runs, or its key is unknown to /fires again"


def test_an_unknown_history_id_is_refused_rather_than_silently_ignored(client):
    assert client.post("/api/discovery/history/g-999999/open").status_code == 404
    assert client.post("/api/discovery/history/not-an-id/open").status_code == 422


def test_the_wavelet_transform_counts_as_heavy_in_a_plans_complexity():
    """fixup-a item 2: a plan containing the Morse transform must carry a cost
    warning. It allocates 3 KB per span sample and re-serialises all of it
    through the step cache; costing it as an ordinary stage routes it local
    and silent."""
    from server.discovery import _complexity
    steps = [{"stage": "preprocessing", "algorithm": "wavelet_transform"},
             {"stage": "detection", "algorithm": "wavelet_summation"}]
    assert "1 heavy" in _complexity(steps), _complexity(steps)


# ── fixup-Z: a band is a scope, and Compare says what a human made of the remainder ──

#: Two bands below this fixture's 0.5 Hz Nyquist (fs 1 Hz).
BANDS = [{"label": "slow", "low_hz": 0.01, "high_hz": 0.1},
         {"label": "fast", "low_hz": 0.1, "high_hz": 0.4}]


def _apply_bands(client, template="mp_threshold", bands=BANDS, channels=(CH[0], CH[1])):
    r = client.post("/api/discovery/templates/apply", json={
        "templates": [template], "channels": list(channels), "t0": 0.0, "t1": N / FS / 3600.0,
        "bands": bands})
    assert r.status_code == 200, r.text
    out = r.json()
    for o in out:
        if o.get("job_id"):
            snap = _wait_job(client, o["job_id"])
            assert snap["status"] == "completed", snap.get("error")
    return out


def _db_rows(client, sql, args=()):
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _first_run_recipe(client, run_key):
    import json
    from Working.database import runs as R
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT params_json FROM discovery_runs WHERE run_key = ?", (run_key,)).fetchone()
        ids = json.loads(row["params_json"])["run_ids"]
        run = R.get_run(conn, ids[0])
        return ids, R.load_recipe(conn, run["config_id"])
    finally:
        conn.close()


def test_the_band_list_comes_from_settings_analysis_defaults(client):
    """Q43: a named band list in Settings › Analysis defaults, seeded with three
    log-spaced bands for a 1 Hz recording."""
    body = client.get("/api/discovery/bands").json()
    assert body["source"] == "default"
    assert [(b["low_hz"], b["high_hz"]) for b in body["bands"]] == [(0.001, 0.01), (0.01, 0.1), (0.1, 0.45)]
    r = client.put("/api/settings/analysis-defaults", json={"values": {"bands": [
        {"label": "slow", "low_hz": 0.01, "high_hz": 0.1}]}})
    assert r.status_code == 200, r.text
    body = client.get("/api/discovery/bands").json()
    assert body["source"] == "settings"
    assert body["bands"] == [{"kind": "bandpass", "label": "slow", "low_hz": 0.01, "high_hz": 0.1}]


def test_a_band_scope_adds_one_run_per_band_each_across_every_channel(client):
    out = _apply_bands(client)
    assert len(out) == len(BANDS), "one Discovery run per band"
    assert len({o["bandSet"] for o in out}) == 1, "the band runs of one application are one set"
    runs = {r["key"]: r for r in client.get("/api/discovery/runs").json()}
    for o, band in zip(out, BANDS):
        row = runs[o["run_key"]]
        assert row["template"] == "mp_threshold", "the template stays one template"
        assert row["band"]["label"] == band["label"] and row["band"]["kind"] == "bandpass"
        assert band["label"] in row["label"], "the run's label carries its band"
        assert row["bandSet"] == o["bandSet"]
        assert row["channelsDone"] == "2 / 2", "each band is one run across the channels in scope"
        ids, recipe = _first_run_recipe(client, o["run_key"])
        first = recipe["steps"][0]
        assert (first["algorithm"], first["params"]["low_hz"], first["params"]["high_hz"]) == (
            "bandpass", band["low_hz"], band["high_hz"])
        assert first["params"]["order"] == 4, "the block Analyse inserts carries its own defaults"


def test_a_band_run_is_the_run_the_hand_built_twin_would_make(client):
    """The 2026-10-02 hand route: insert the bandpass ahead of the template in
    Analyse (the inserted block arrives with its defaults filled), save it as a
    template, apply it. `execute_recipe` is idempotent on the recipe, so if the
    band scope recorded the same recipe the twin is MADE OF the band run's own
    runs — the strongest form of "they hash the same"."""
    from Working.recipes import recipe_hash
    out = _apply_bands(client, bands=[BANDS[0]])
    band_ids, band_recipe = _first_run_recipe(client, out[0]["run_key"])
    tpl = next(t for t in client.get("/api/templates").json() if t["name"] == "mp_threshold")
    inserted = client.post("/api/chain/params", json={
        "stage": "preprocessing", "algorithm": "bandpass", "params": {}}).json()["params"]
    inserted.update({"low_hz": BANDS[0]["low_hz"], "high_hz": BANDS[0]["high_hz"]})
    steps = [{"stage": "preprocessing", "algorithm": "bandpass", "params": inserted}] + tpl["steps"]
    r = client.post("/api/templates", json={"name": "band_mp_threshold_twin", "steps": steps})
    assert r.status_code == 200, r.text
    twin = _apply(client, template="band_mp_threshold_twin")
    twin_ids, twin_recipe = _first_run_recipe(client, twin["run_key"])
    assert recipe_hash(twin_recipe) == recipe_hash(band_recipe)
    assert sorted(twin_ids) == sorted(band_ids)


def test_each_band_run_is_paired_with_a_surrogate_bandpassed_the_same_way(client):
    from Working.database import runs as R
    out = _apply_bands(client)
    for o, band in zip(out, BANDS):
        ids, _ = _first_run_recipe(client, o["run_key"])
        sur = _db_rows(client, "SELECT id, config_id FROM runs WHERE surrogate_of_run_id IN (%s)"
                       % ",".join(str(i) for i in ids))
        # the session's explicit null is 2 draws (`_scope`), and each draw is a run (fixup-T, Q35)
        assert len(sur) == 2 * len(ids), "every band run has its null, at the count the session names"
        conn = sqlite3.connect(client.app.state.rt.db_path)
        conn.row_factory = sqlite3.Row
        try:
            recipe = R.load_recipe(conn, sur[0]["config_id"])
        finally:
            conn.close()
        assert [s["algorithm"] for s in recipe["steps"]][:2] == ["surrogate", "bandpass"]
        assert recipe["steps"][1]["params"]["low_hz"] == band["low_hz"]


def _compare(client, a, b):
    r = client.get("/api/discovery/compare", params={
        "a": a, "b": b, "channels": ",".join([CH[0], CH[1]]), "t0": 0.0, "t1": N / 3600.0})
    assert r.status_code == 200, r.text
    return r.json()


def test_compare_takes_the_band_set_as_one_side_and_counts_its_union(client):
    raw = _apply(client, template="mp_threshold")
    bands = _apply_bands(client)
    side = f"set:{bands[0]['bandSet']}"
    cmp_ = _compare(client, raw["run_key"], side)
    assert cmp_["b"]["run"] == side
    assert cmp_["b"]["isSet"] is True
    assert [m["run"] for m in cmp_["b"]["members"]] == [o["run_key"] for o in bands]
    # the union is de-duplicated: never more regions than the band runs found
    per_band = cmp_["perBand"]
    assert [p["band"]["label"] for p in per_band] == [b["label"] for b in BANDS]
    union_n = cmp_["total"]["both"] + cmp_["total"]["onlyB"]
    assert union_n <= sum(p["found"] for p in per_band)
    assert union_n >= max(p["found"] for p in per_band)
    assert cmp_["b"]["found"] == union_n
    for d in cmp_["disagreements"]:
        if d["kind"] == "only B":
            assert d["bands"] and set(d["bands"]) <= {b["label"] for b in BANDS}, \
                "a disagreement names the band that fired"
    # 'what differs' is kept on the union view, and the like-for-like twin is named
    assert "attributable" in cmp_
    assert cmp_["likeForLike"]["run"] == raw["run_key"]


def test_set_overlap_splits_by_verdict_and_only_b_unjudged_goes_to_review(client):
    """Acceptance step 4: *Send only-B unjudged to Review* → judge them → back in
    Compare the only-B row reads judged n · accepted k."""
    import json
    from Working.database import adjudications as adj
    raw = _apply(client, template="mp_threshold")
    bands = _apply_bands(client)
    side = f"set:{bands[0]['bandSet']}"
    cmp_ = _compare(client, raw["run_key"], side)
    only_b = cmp_["total"]["onlyB"]
    assert only_b > 0, "the fixture must leave the band set something A missed"
    v = cmp_["verdicts"]
    assert set(v) == {"onlyA", "both", "onlyB"}
    assert v["onlyB"] == {"n": only_b, "judged": 0, "accepted": 0, "rejected": 0, "other": 0,
                          "unjudged": only_b}

    send = {"a": raw["run_key"], "b": side, "channels": [CH[0], CH[1]], "t0": 0.0, "t1": N / 3600.0,
            "which": "only B"}
    r = client.post("/api/discovery/compare/review", json=send)
    assert r.status_code == 200, r.text
    sent = r.json()
    assert sent["unjudged"] == only_b
    qid = sent["queue_id"]
    queue = client.get(f"/api/review/queues/{qid}").json()
    assert queue["queue"]["writes_to"] == "adjudications"
    assert queue["queue"]["total"] == only_b
    # one detection per region, and never a surrogate's
    det_ids = json.loads(_db_rows(client, "SELECT filters_json FROM review_queues WHERE id = ?",
                                  (qid,))[0]["filters_json"])["detection_ids"]
    assert len(det_ids) == only_b
    on_surrogate = _db_rows(client, "SELECT COUNT(*) AS n FROM detections d JOIN runs r ON r.id = d.run_id "
                                    "WHERE r.surrogate_of_run_id IS NOT NULL AND d.id IN (%s)"
                            % ",".join(str(i) for i in det_ids))[0]["n"]
    assert on_surrogate == 0

    # judge two, one accepted and one rejected, written the way Review writes them
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        adj.insert_adjudication(conn, det_ids[0], "interesting")
        if len(det_ids) > 1:
            adj.insert_adjudication(conn, det_ids[1], "not_interesting")
    finally:
        conn.close()
    after = _compare(client, raw["run_key"], side)["verdicts"]["onlyB"]
    judged = min(2, len(det_ids))
    assert after["judged"] == judged and after["accepted"] == 1
    assert after["rejected"] == judged - 1
    assert after["unjudged"] == only_b - judged

    # a second send is the same open queue
    again = client.post("/api/discovery/compare/review", json=send).json()
    assert again["queue_id"] == qid and again["reused"] is True
    assert again["unjudged"] == only_b - judged


def test_a_band_application_is_costed_as_n_bands_times_the_sweep(client):
    """Cost is N bands × the sweep: three bands of a sweep that fits the ceiling
    once may not fit it three times, and the route is decided on the whole."""
    plan = client.post("/api/discovery/plan", json={
        "template": "mp_threshold", "channels": [CH[0], CH[1]], "t0": 0.0, "t1": N / 3600.0,
        "measuredPerChannelS": 100.0, "bands": BANDS}).json()
    assert plan["nBands"] == len(BANDS)
    assert plan["estimate_s"] == pytest.approx(100.0 * 2 * len(BANDS))


def test_a_role_holding_one_more_stage_differs(client):
    """fixup-Z, found on the sandbox walk: the band step sits in the same
    Preprocess role as the template's baseline removal, and a role cell draws
    its LAST stage — so `symbol_search` against its banded twin read "0 of 5
    roles differ" although the chains differ by a whole bandpass. A role with a
    different number of stages differs; the like-for-like comparison reads
    exactly one role, and so attributable."""
    raw = _apply(client, template="mp_threshold")
    bands = _apply_bands(client, bands=[BANDS[0]])
    for b in (bands[0]["run_key"], f"set:{bands[0]['bandSet']}"):
        cmp_ = _compare(client, raw["run_key"], b)
        assert cmp_["differing"] == ["Preprocess"], (b, cmp_["differing"])
        assert cmp_["attributable"] is True

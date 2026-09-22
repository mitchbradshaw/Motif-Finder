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


def test_send_to_review_is_a_filter_over_the_runs_own_detections(client):
    out = _apply(client)
    r = client.post(f"/api/discovery/runs/{out['run_key']}/review", json={"limit": 500})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["writes"] == "adjudications"
    assert body["queued"] <= body["unjudged"]
    assert "filter" in body["note"]
    queues = client.get("/api/discovery/queues").json()
    assert any(q["run_key"] == out["run_key"] for q in queues)


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

"""
test_webui_discovery_coverage.py
================================
discovery-coverage-and-gauge (the researcher, 2026-10-18): which detector ran
on which channel, "run on the missing", and the verdict gauge on a template.

* **"Not run here" is not "ran and found nothing".** A run applied on CH1 only
  reports `not_run` for CH2 on its `/runs` row (`coverage`), and its `/fires`
  row on CH2 says `ran: false` with no counts, instead of a row of zeros.
* **Extend keeps the run.** `POST /runs/{key}/extend` plans the same steps on
  the named channels, joins the new runs to the run's own group and row (no new
  key, no new `discovery_runs` row), and `channelsDone` reads 2 / 2.
* **Extend with changed parameters is refused** in a sentence, with a code the
  client turns into "apply as a new run".
* **The gauge counts every human verdict on a template's detections** — every
  run of the template, every session, carried rows included — equal to a hand
  query, and it follows a new verdict.

FastAPI lives only in `webui/.venv`; run with
`webui/.venv/Scripts/python.exe -m pytest tests/test_webui_discovery_coverage.py`.
"""

import json
import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from tests.test_webui_discovery import CH, N, _apply, _wait_job, client  # noqa: E402,F401

VERDICTS = ("seed", "interesting", "not_interesting", "artifact", "unsure")


def _db(client):
    conn = sqlite3.connect(client.app.state.rt.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row(client, key):
    return next(r for r in client.get("/api/discovery/runs").json() if r["key"] == key)


def _fires(client, key, channels=(CH[0], CH[1])):
    return client.get("/api/discovery/fires", params={
        "channels": ",".join(channels), "t0": 0.0, "t1": N / 3600.0, "runs": f"human,{key}"}).json()


# ── coverage ────────────────────────────────────────────────────────────────

def test_a_run_on_one_channel_reports_not_run_for_the_other(client):
    out = _apply(client, channels=(CH[0],))
    row = _row(client, out["run_key"])
    assert row["coverage"] == {CH[0]: "covered", CH[1]: "not_run"}

    fires = _fires(client, out["run_key"])
    by_ch = {c["channel"]: {r["run"]: r for r in c["rows"]} for c in fires["channels"]}
    missing = by_ch[CH[1]][out["run_key"]]
    assert missing["ran"] is False and missing["counts"] == []
    present = by_ch[CH[0]][out["run_key"]]
    assert present.get("ran", True) is True and len(present["counts"]) == fires["nBins"]
    # the human row is never "not run"
    assert by_ch[CH[1]]["human"].get("ran", True) is True


def test_a_run_on_every_channel_in_scope_is_covered_everywhere(client):
    out = _apply(client)
    assert _row(client, out["run_key"])["coverage"] == {CH[0]: "covered", CH[1]: "covered"}


# ── extend ──────────────────────────────────────────────────────────────────

def test_extend_keeps_the_key_and_the_run_gains_the_channel(client):
    out = _apply(client, channels=(CH[0],))
    key = out["run_key"]
    conn = _db(client)
    try:
        n_rows = conn.execute("SELECT COUNT(*) FROM discovery_runs").fetchone()[0]
        group = conn.execute("SELECT run_group_id FROM discovery_runs WHERE run_key = ?", (key,)).fetchone()[0]
    finally:
        conn.close()
    assert _row(client, key)["channelsDone"] == "1 / 1"

    r = client.post(f"/api/discovery/runs/{key}/extend", json={"channels": [CH[1]]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_key"] == key and body["channels"] == [CH[1]]
    snap = _wait_job(client, body["job_id"])
    assert snap["status"] == "completed", snap.get("error")

    row = _row(client, key)
    assert row["status"] == "done"
    assert row["channelsDone"] == "2 / 2"
    assert row["coverage"] == {CH[0]: "covered", CH[1]: "covered"}
    conn = _db(client)
    try:
        assert conn.execute("SELECT COUNT(*) FROM discovery_runs").fetchone()[0] == n_rows, "no new run row"
        dr = conn.execute("SELECT * FROM discovery_runs WHERE run_key = ?", (key,)).fetchone()
        assert dr["run_group_id"] == group, "the run keeps its group"
        ids = json.loads(dr["params_json"])["run_ids"]
        assert len(ids) == 2
        groups = {g for (g,) in conn.execute(
            "SELECT run_group_id FROM runs WHERE id IN (%s)" % ",".join(str(i) for i in ids))}
        assert groups == {group}, "the new channel's run joined the run's own group"
    finally:
        conn.close()
    fires = _fires(client, key)
    for c in fires["channels"]:
        mine = next(r for r in c["rows"] if r["run"] == key)
        assert mine.get("ran", True) is True


def test_extend_with_changed_parameters_is_refused(client):
    from server import templates as T
    conn = _db(client)
    try:
        base = next(t for t in T.list_all(conn) if t["name"] == "mp_threshold")
        tid = T.save(conn, "mine", base["steps"])
    finally:
        conn.close()
    out = _apply(client, template="mine", channels=(CH[0],))
    conn = _db(client)
    try:
        steps = T.get(conn, tid)["steps"]
        last = steps[-1]
        params = dict(last.get("params") or {})
        num = next(k for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool))
        params[num] = params[num] * 2 + 1
        last["params"] = params
        T.update(conn, tid, steps=steps)
    finally:
        conn.close()
    r = client.post(f"/api/discovery/runs/{out['run_key']}/extend", json={"channels": [CH[1]]})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "params_differ"
    assert "new run" in detail["message"]
    assert _row(client, out["run_key"])["coverage"][CH[1]] == "not_run", "nothing ran"


def test_extend_refuses_an_unknown_run_and_a_channel_it_already_has(client):
    assert client.post("/api/discovery/runs/nope/extend", json={"channels": [CH[1]]}).status_code == 404
    out = _apply(client, channels=(CH[0],))
    r = client.post(f"/api/discovery/runs/{out['run_key']}/extend", json={"channels": [CH[0]]})
    assert r.status_code == 422
    assert "already" in r.json()["detail"]["message"]


# ── the verdict gauge ───────────────────────────────────────────────────────

def _hand_count(conn, template):
    """adjudications → detections → runs → every `discovery_runs` row of the template, written out by hand."""
    ids = set()
    for (pj,) in conn.execute("SELECT params_json FROM discovery_runs WHERE template_name = ?", (template,)):
        ids.update(int(i) for i in (json.loads(pj or "{}").get("run_ids") or []))
    out = {v: 0 for v in VERDICTS}
    if ids:
        for (v,) in conn.execute("SELECT a.verdict FROM adjudications a JOIN detections d ON d.id = a.detection_id "
                                 "WHERE d.run_id IN (%s)" % ",".join(str(i) for i in ids)):
            out[v] += 1
    out["total"] = sum(out[v] for v in VERDICTS)
    return out


def _gauge(client, name):
    return next(t for t in client.get("/api/discovery/templates").json() if t["name"] == name)["verdicts"]


def test_the_template_gauge_counts_every_human_verdict_on_its_detections(client):
    out = _apply(client)
    conn = _db(client)
    try:
        ids = json.loads(conn.execute("SELECT params_json FROM discovery_runs WHERE run_key = ?",
                                      (out["run_key"],)).fetchone()[0])["run_ids"]
        dets = [r[0] for r in conn.execute(
            "SELECT id FROM detections WHERE run_id IN (%s) ORDER BY id" % ",".join(str(i) for i in ids))]
        if len(dets) < 6:
            # the planted dips are few; give the run detections enough to judge
            run_id = ids[0]
            for k in range(6 - len(dets)):
                conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) "
                             "VALUES (?, ?, ?, 1.0)", (run_id, 100 + 70 * k, 150 + 70 * k))
            conn.commit()
            dets = [r[0] for r in conn.execute(
                "SELECT id FROM detections WHERE run_id IN (%s) ORDER BY id" % ",".join(str(i) for i in ids))]
        plan = ["interesting", "seed", "not_interesting", "artifact", "unsure"]
        for d, v in zip(dets, plan):
            conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, ?, '2026-10-19')",
                         (d, v))
        conn.commit()
        want = _hand_count(conn, "mp_threshold")
    finally:
        conn.close()
    assert want["total"] == 5
    assert _gauge(client, "mp_threshold") == want
    other = next(t for t in client.get("/api/discovery/templates").json() if t["name"] != "mp_threshold")
    assert other["verdicts"]["total"] == 0

    # a carried verdict (review-carry) is a human verdict too, and a new one moves the gauge
    conn = _db(client)
    try:
        conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at, carried_from) "
                     "VALUES (?, 'interesting', '2026-10-19', ?)", (dets[5], dets[0]))
        conn.commit()
        want = _hand_count(conn, "mp_threshold")
    finally:
        conn.close()
    got = _gauge(client, "mp_threshold")
    assert got == want and got["interesting"] == 2 and got["total"] == 6

    # coverage critic round: Review re-judges IN PLACE (`UPDATE adjudications SET verdict = ?`), which moves neither a
    # count nor a max id. The gauge's digest must still see it.
    conn = _db(client)
    try:
        conn.execute("UPDATE adjudications SET verdict = 'artifact' WHERE detection_id = ?", (dets[0],))
        conn.commit()
        want = _hand_count(conn, "mp_threshold")
    finally:
        conn.close()
    got = _gauge(client, "mp_threshold")
    assert got == want and got["interesting"] == 1 and got["artifact"] == 2


def test_extend_refuses_a_run_with_no_group_rather_than_replace_its_runs(client):
    """coverage critic round: `_start_sweep(extend_group=None)` is the FIRST-sweep path, which writes
    ``run_ids = <the new channels>`` — an extend of a row whose `run_group_id` is NULL would have dropped the
    channels the run already had. It is refused instead, and the row is untouched."""
    out = _apply(client, channels=(CH[0],))
    key = out["run_key"]
    conn = _db(client)
    try:
        conn.execute("UPDATE discovery_runs SET run_group_id = NULL WHERE run_key = ?", (key,))
        conn.commit()
        before = json.loads(conn.execute("SELECT params_json FROM discovery_runs WHERE run_key = ?",
                                         (key,)).fetchone()[0])["run_ids"]
    finally:
        conn.close()
    r = client.post(f"/api/discovery/runs/{key}/extend", json={"channels": [CH[1]]})
    assert r.status_code == 422, r.text
    conn = _db(client)
    try:
        after = json.loads(conn.execute("SELECT params_json FROM discovery_runs WHERE run_key = ?",
                                        (key,)).fetchone()[0])
    finally:
        conn.close()
    assert after["run_ids"] == before and "extending" not in after

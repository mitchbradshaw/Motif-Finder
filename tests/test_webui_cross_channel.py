"""
test_webui_cross_channel.py
===========================
fixup-W, the routes: Library › Family *Classify across channels* is a job with
per-channel progress that writes bins onto the family's edges; the family rail
and Library › Recurrence read real counts per bin and the recurrence count
with the bins taken out, each with its rule; Explore › Cross-channel on the
edge's window shows the same lag, r and bin the edge stores, under the same
rule in seconds (Q40, Q-W5).

The synthetic recording: one pulse planted on four channels —
ch0 and ch1 at the same instant (an artifact pair), ch2 ten seconds later
(propagation), ch3 at the same instant but with NO family member there (a
co-occurrence without a member, Q40c) and again an hour later where ch3 does
hold a member (independent recurrence).

FastAPI lives only in `webui/.venv`, so this file skips under the conda
pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_cross_channel.py
"""

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

from Working.cross_channel import ARTIFACT, INDEPENDENT_RECURRENCE, PROPAGATION  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

N = 6000
PULSE_N = 60
#: channel -> where the pulse is planted (sign)
PLANTS = {0: [(1000, 1)], 1: [(1000, 1)], 2: [(1010, 1)], 3: [(1000, 1), (4600, 1)]}
#: member id -> (channel, start, end); ch3's 1000 pulse has no member
MEMBERS = {1: (0, 990, 1070), 2: (1, 990, 1070), 3: (2, 1000, 1080), 4: (3, 4590, 4670)}


def _pulse():
    u = np.linspace(0.0, 2.0 * np.pi, PULSE_N)
    return -np.sin(u) * np.hanning(PULSE_N)


def _db(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    for ch in range(4):
        x = np.random.default_rng(ch).standard_normal(N) * 0.01
        for at, sign in PLANTS[ch]:
            x[at:at + PULSE_N] += sign * _pulse()
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, x)
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                     "VALUES ('syn.mat', ?, 1.0, ?, 0, ?, 'V')", (ch, N, str(npy)))
    for mid, (ch, a, b) in MEMBERS.items():
        conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, scale) VALUES (?, ?, ?, ?, 'event')",
                     (ch + 1, a, b, f"m{mid}"))
        conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, channel, content_hash) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (mid, ch + 1, a, b, ch, f"h{mid}"))
    conn.execute("INSERT INTO groupings (name, unit, basis, method, params_json, cut, n_families, n_assigned, "
                 "n_omitted, created_at) VALUES ('shape families', 'single_motifs', 'shape-distance', 'ward', "
                 "'{\"cut\": 0.6}', 0.6, 1, 4, 0, '2026-10-04')")
    for mid in MEMBERS:
        conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                     "family_label, distance, is_medoid) VALUES (1, 'single_motifs', ?, ?, 1, 'F-01', ?, ?)",
                     (mid, f"h{mid}", 0.1 * mid, 1 if mid == 1 else 0))
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
    rt = Runtime(mode="sandbox", stamp="20261004-cross-channel", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_dist(tmp_path)))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
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


def _wait_job(client, job_id, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("completed", "failed", "cancelled"):
            return s
        time.sleep(0.1)
    raise AssertionError(f"job {job_id} did not finish")


def _classify(client):
    r = client.post("/api/library/family/F-01/classify-cross-channel", json={"grouping": "g-01"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["kind"] == "cross_channel"
    snap = _wait_job(client, out["job_id"])
    assert snap["status"] == "completed", snap.get("error")
    return snap


def _family(client):
    r = client.get("/api/library/family/F-01")
    assert r.status_code == 200, r.text
    return r.json()["detail"]


def test_classify_across_channels_is_a_job_with_per_channel_progress(client):
    snap = _classify(client)
    res = snap["result"]
    assert res["channels"] == 4
    assert snap["progress"]["done"] == snap["progress"]["total"] == 4
    assert "ch" in snap["progress"]["message"].lower() or "channel" in snap["progress"]["message"].lower()
    assert res["counts"][ARTIFACT] == 1 and res["counts"][PROPAGATION] == 2
    # Q40c, counted per member x sibling channel: m1 and m2 each see ch3's
    # simultaneous pulse (artifact), m3 sees it 10 s earlier (propagation)
    assert res["counts"]["withoutMember"] == {ARTIFACT: 2, PROPAGATION: 1}


def test_the_bins_land_on_the_members_edges(client):
    _classify(client)
    rows = _q(client, "SELECT member_a_id, member_b_id, lag, waveform_correlation, classification_bin FROM motif_edge")
    by = {frozenset((r["member_a_id"], r["member_b_id"])): r for r in rows}
    assert by[frozenset((1, 2))]["classification_bin"] == ARTIFACT
    assert by[frozenset((1, 3))]["classification_bin"] == PROPAGATION and by[frozenset((1, 3))]["lag"] == 10
    assert by[frozenset((2, 3))]["classification_bin"] == PROPAGATION
    # Q40c: ch3's simultaneous pulse has no member, so no edge to it; and m4 is an hour away
    assert all(4 not in k for k in by)


def test_the_family_rail_reads_real_counts_per_bin_with_their_rules(client):
    before = _family(client)
    assert before["crossChannel"]["classified"] is False
    _classify(client)
    d = _family(client)
    cc = d["crossChannel"]
    assert cc["classified"] is True
    assert cc["counts"] == {ARTIFACT: 1, PROPAGATION: 2, INDEPENDENT_RECURRENCE: 0}
    assert cc["withoutMember"] == {ARTIFACT: 2, PROPAGATION: 1}
    assert set(cc["rules"]) == {ARTIFACT, PROPAGATION, INDEPENDENT_RECURRENCE}
    assert "1 s" in cc["rules"][ARTIFACT] and "50 s" in cc["rules"][PROPAGATION]
    assert cc["recurrence"]["all"] == 4
    assert cc["recurrence"]["excluding_artifacts"] == 2
    assert set(cc["recurrence"]["rules"]) == {"all", "excluding_artifacts", "propagation_once"}
    fam = d["family"]
    assert (fam["artifactChannels"], fam["propChannels"], fam["indChannels"]) == (1, 2, 0)
    # each member's edge list shows lag (in seconds) and r where a sibling member co-occurs
    m1 = next(m for m in d["members"] if m["id"] == "m-1")
    e13 = next(e for e in m1["edges"] if e["other"] == "m-3")
    assert e13["classification"] == PROPAGATION
    assert e13["lagS"] == pytest.approx(10.0) and e13["r"] > 0.5
    assert e13["window"]["t0S"] == pytest.approx(990.0) and e13["window"]["t1S"] == pytest.approx(1080.0)


def test_the_surrogate_count_is_stated_beside_it_or_why_there_is_none(client):
    _classify(client)
    null = _family(client)["crossChannel"]["null"]
    assert null["draws"] == 0
    assert "no run" in null["reason"].lower()            # these members were imported, not found by a run


def test_recurrence_cells_flag_artifacts_and_carry_the_counts_with_the_bins_out(client):
    _classify(client)
    rec = client.get("/api/library/recurrence").json()
    fam = next(f for f in rec["families"] if f["id"] == "F-01")
    cells = fam["cells"]
    keys = sorted(k for k in cells if cells[k]["count"])
    assert len(keys) == 4
    ch0, ch1, ch2, ch3 = keys
    assert cells[ch0]["artifact"] is True and cells[ch1]["artifactMembers"] == 1     # red, and still counted in `count`
    assert cells[ch2]["artifact"] is False
    assert cells[ch0]["count"] == 1
    assert cells[ch0]["countExArtifacts"] == 0 and cells[ch2]["countExArtifacts"] == 1
    assert sum(c.get("countPropOnce", 0) for c in cells.values()) == fam["recurrence"]["propagation_once"] == 2
    assert fam["recurrence"]["excluding_artifacts"] == 2
    assert "artifact" in fam["recurrence"]["rules"]["excluding_artifacts"]


def test_explore_on_the_edges_window_shows_what_the_edge_stores(client):
    _classify(client)
    edge = _q(client, "SELECT lag, waveform_correlation, classification_bin FROM motif_edge "
                      "WHERE (member_a_id = 1 AND member_b_id = 3)")[0]
    r = client.get("/api/cross/1", params={"t0": 990, "t1": 1080})
    assert r.status_code == 200, r.text
    body = r.json()
    row = next(c for c in body["channels"] if c["id"] == 3)
    assert row["classification"] == edge["classification_bin"]
    assert row["lag_s"] == pytest.approx(edge["lag"])
    assert row["r"] == pytest.approx(edge["waveform_correlation"], abs=1e-9)
    assert set(body["rules"]) == {ARTIFACT, PROPAGATION, INDEPENDENT_RECURRENCE}


def test_explore_bins_an_inverted_simultaneous_copy_as_an_artifact(client):
    """Q40b: the old rule tested the SIGNED r against 0.99 and could never call
    an inverted copy an artifact."""
    conn = sqlite3.connect(client.app.state.rt.db_path)
    try:
        path = conn.execute("SELECT npy_path FROM recordings WHERE id = 2").fetchone()[0]
    finally:
        conn.close()
    x = np.load(path)
    x[900:1100] *= -1
    np.save(path, x)
    body = client.get("/api/cross/1", params={"t0": 980, "t1": 1080}).json()
    row = next(c for c in body["channels"] if c["id"] == 2)
    assert row["r"] < -0.9 and row["classification"] == ARTIFACT


def test_the_three_numbers_are_settings_keys_the_job_reads(client):
    r = client.put("/api/settings/analysis-defaults", json={"values": {"cross_channel.propagation_max_lag_s": 5}})
    assert r.status_code == 200, r.text
    _classify(client)
    rows = _q(client, "SELECT classification_bin FROM motif_edge WHERE member_a_id = 1 AND member_b_id = 3")
    assert rows[0]["classification_bin"] == INDEPENDENT_RECURRENCE     # 10 s is past a 5 s ceiling
    rules = _family(client)["crossChannel"]["rules"]
    assert "5 s" in rules[PROPAGATION]


def test_an_unknown_family_is_refused(client):
    r = client.post("/api/library/family/F-99/classify-cross-channel", json={"grouping": "g-01"})
    assert r.status_code == 404

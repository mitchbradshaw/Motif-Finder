"""
test_discovery_detection_map.py
================================
The detection map (Discovery › Map, 2026-10-12): where each detection
algorithm fires, as rows of algorithms against datasets, channels and time.

`Working.discovery.detection_map` is the UI-free half. What it pins:

* **A row is an algorithm, not a run.** A `configs` row is per recording and
  span, so "the same algorithm on another channel or dataset" has no database
  key. The row key is the hash of the steps the runs actually executed, with
  recording and span stripped — identical across a fan-out's channels and
  across sessions, different the moment a cut, a k or a band differs. Two
  cuts of one seed are two rows; that is how parameter sweeps will appear.
* **"Not run here" and "ran and found nothing" are different facts.** A cell
  carries a `state`: `covered` (hours > 0, a count that may be 0), `not_run`,
  `running`, `failed`, `discarded`; `not_reviewed` for the human row. A map
  that merged them would lie about every empty channel.
* **What does not count.** Discovery runs that were removed or superseded,
  `runs` rows a discard marked superseded (they are shared between Discovery
  runs, so a sibling in another session still holds them), surrogate
  (paired-null) runs, deleted annotations, the held-out file.
* **Piecewise newest-wins.** When one row ran twice on one channel, coverage
  is the union of the live runs' spans and each sample range is counted from
  the newest run that covers it — so a newer 1 h run neither doubles the
  count nor blanks the older whole-channel run.
* **Human coverage is where a person looked**: the reviewed spans PLUS the
  span of every live annotation of any verdict. Nothing in the app writes
  `reviewed_spans` any more, so a Review verdict would otherwise read
  "not reviewed".

Headless: a temp sqlite built from `init_db()` and hand-written rows. No
signal is loaded — the map is a count of rows the executor already wrote.
The module is imported inside each test so each fails on its own
until the module exists (red first), rather than the file failing to collect.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

NOW = "2026-10-12T00:00:00+00:00"
OLD = "2026-10-01T00:00:00+00:00"
ALPHA, BETA, GAMMA, DELTA = "alpha.mat", "beta.mat", "gamma.mat", "delta.mat"
ALPHA_N, BETA_N = 7200, 3600         # 2 h and 1 h at 1 Hz

#: Four distinct recipes: a template, the same seed at two cuts, another template.
DROP = {"steps": [{"stage": "detection", "algorithm": "drop_detection", "params": {"slope_sigma": 4.0}}]}
SEED25 = {"steps": [{"stage": "detection", "algorithm": "seed_matches", "params": {"seed": "E0102", "cut": 2.5, "k": 50}}]}
SEED30 = {"steps": [{"stage": "detection", "algorithm": "seed_matches", "params": {"seed": "E0102", "cut": 3.0, "k": 50}}]}
OTHER = {"steps": [{"stage": "detection", "algorithm": "dehshibi_spikes", "params": {}}]}


def _session(conn, name, source_file):
    cur = conn.execute(
        "INSERT INTO discovery_sessions (name, source_file, channels_json, span_start, span_end, created_at, updated_at) "
        "VALUES (?, ?, '[]', 0, 0, ?, ?)", (name, source_file, NOW, NOW))
    return cur.lastrowid


def _drun(conn, session_id, key, kind, run_ids, *, template=None, params=None, superseded=False, removed=False, status="done"):
    params = dict(params or {})
    params["run_ids"] = list(run_ids)
    cur = conn.execute(
        "INSERT INTO discovery_runs (session_id, run_key, kind, label, colour, template_name, params_json, status, "
        "created_at, updated_at, superseded_at, removed_at) VALUES (?, ?, ?, ?, '#0a84ff', ?, ?, ?, ?, ?, ?, ?)",
        (session_id, key, kind, params.get("label") or key, template, json.dumps(params), status, NOW, NOW,
         NOW if superseded else None, NOW if removed else None))
    return cur.lastrowid


def _run(conn, recipe, recording_id, span, detections, *, surrogate_of=None, status="completed", superseded=False):
    cfg, _ = R.get_or_create_config(conn, recipe)
    rid = R.insert_run(conn, cfg, recording_id, span[0], span[1], status=status)
    if surrogate_of is not None:
        conn.execute("UPDATE runs SET surrogate_of_run_id = ? WHERE id = ?", (surrogate_of, rid))
    if superseded:
        conn.execute("UPDATE runs SET superseded_at = ? WHERE id = ?", (NOW, rid))
    for s in detections:
        R.insert_detection(conn, rid, s, s + 10, score=1.0, commit=False)
    conn.commit()
    return rid


def _dm():
    """The module under test, imported inside each test so a missing module FAILS that test rather than the collection."""
    from Working.discovery import detection_map
    return detection_map


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="detection_map_")
    path = os.path.join(tmpdir, "test.sqlite")
    conn = init_db(path)
    a = [q.insert_recording(conn, ALPHA, ch, 1.0, ALPHA_N, 0, os.path.join(tmpdir, f"a{ch}.npy")) for ch in range(3)]
    b = [q.insert_recording(conn, BETA, ch, 1.0, BETA_N, 0, os.path.join(tmpdir, f"b{ch}.npy")) for ch in range(2)]
    g = q.insert_recording(conn, GAMMA, 0, 1.0, BETA_N, 0, os.path.join(tmpdir, "g0.npy"))
    q.insert_recording(conn, DELTA, 0, 1.0, BETA_N, 0, os.path.join(tmpdir, "d0.npy"))
    held = q.insert_recording(conn, HELD_OUT_RECORDING_FILE, 0, 1.0, BETA_N, 0, os.path.join(tmpdir, "h0.npy"))

    s1, s2 = _session(conn, "alpha screen", ALPHA), _session(conn, "beta screen", BETA)
    s3, s4 = _session(conn, "held", HELD_OUT_RECORDING_FILE), _session(conn, "gamma", GAMMA)

    # drop_detection in session 1: the whole of alpha CH1, the first half of CH2, nothing on CH3
    r1 = _run(conn, DROP, a[0], (0, ALPHA_N), [100, 4000, 7000])
    r2 = _run(conn, DROP, a[1], (0, ALPHA_N // 2), [500])
    _drun(conn, s1, "drop_detection", "template", [r1, r2], template="drop_detection", params={"version": 1})
    # a paired-null surrogate of r1 with detections of its own: never counted
    _run(conn, DROP, a[0], (0, ALPHA_N), [1, 2, 3, 4, 5, 6], surrogate_of=r1)
    # the same recipe applied AGAIN on alpha CH1 over the first hour only: piecewise newest-wins
    r1b = _run(conn, DROP, a[0], (0, ALPHA_N // 2), [100, 500])
    _drun(conn, s1, "drop_detection_2", "template", [r1b], template="drop_detection", params={"version": 1})

    # the same recipe in session 2 on beta CH1, run twice over the same hour: the newer run alone counts
    _drun(conn, s2, "drop_detection", "template", [_run(conn, DROP, b[0], (0, BETA_N), [100, 200])],
          template="drop_detection", params={"version": 1})
    _drun(conn, s2, "drop_detection_2", "template", [_run(conn, DROP, b[0], (0, BETA_N), [10, 20, 30, 40, 50])],
          template="drop_detection", params={"version": 1})
    # beta CH2: an older completed run and a newer run that is still running — the completed one still shows
    rb2 = _run(conn, DROP, b[1], (0, BETA_N), [5])
    rb2_running = _run(conn, DROP, b[1], (0, BETA_N), [], status="running")
    _drun(conn, s2, "drop_detection_ch2", "template", [rb2], template="drop_detection", params={"version": 1})
    _drun(conn, s2, "drop_detection_ch2_again", "template", [rb2_running], template="drop_detection",
          params={"version": 1}, status="running")

    # two cuts of one seed: two rows
    _drun(conn, s1, "seed_E0102_c25", "seed", [_run(conn, SEED25, a[0], (0, ALPHA_N), [200])],
          params={"seedId": "E0102", "cut": 2.5, "label": "seed E0102 · cut 2.5"})
    _drun(conn, s1, "seed_E0102_c30", "seed", [_run(conn, SEED30, a[0], (0, ALPHA_N), [10, 20, 30, 40])],
          params={"seedId": "E0102", "cut": 3.0, "label": "seed E0102 · cut 3.0"})

    # a discarded run on alpha CH3: the Discovery row AND its runs row are superseded (what Discard does) —
    # and a live Discovery run in session 2 that reuses that same runs row still may not count it
    r_disc = _run(conn, DROP, a[2], (0, ALPHA_N), [50, 60, 70, 80, 90, 100, 110, 120, 130], superseded=True)
    _drun(conn, s1, "drop_detection_old", "template", [r_disc], template="drop_detection", params={"version": 1}, superseded=True)
    _drun(conn, s2, "drop_detection_shared", "template", [r_disc], template="drop_detection", params={"version": 1})
    # a removed template run: not a row at all
    _drun(conn, s1, "dehshibi_spikes", "template", [_run(conn, OTHER, a[2], (0, ALPHA_N), [55])],
          template="dehshibi_spikes", params={"version": 1}, removed=True)

    # gamma: a Discovery run whose only runs row is still running — listed, with a `running` cell
    _drun(conn, s4, "drop_detection", "template", [_run(conn, DROP, g, (0, BETA_N), [], status="running")],
          template="drop_detection", params={"version": 1}, status="running")

    # a run on the held-out file: left out of the map entirely
    _drun(conn, s3, "drop_detection", "template", [_run(conn, DROP, held, (0, BETA_N), [1, 2, 3])],
          template="drop_detection", params={"version": 1})

    # the human reference. alpha CH1: reviewed over the first hour; two interesting, one not, one deleted.
    # alpha CH2: NO reviewed span, but two live verdicts — a person looked there, so it is not "not reviewed".
    q.insert_reviewed_span(conn, a[0], 0, ALPHA_N // 2, "test")
    for s, v in ((100, "interesting"), (4000, "interesting"), (2000, "not_interesting")):
        q.insert_annotation(conn, a[0], s, s + 10, v, "test")
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at, deleted_at) "
                 "VALUES (?, 300, 310, 'interesting', 'test', ?, ?)", (a[0], OLD, NOW))
    q.insert_annotation(conn, a[1], 1000, 1010, "not_interesting", "test")
    q.insert_annotation(conn, a[1], 2000, 2010, "interesting", "test")
    conn.commit()
    conn.close()
    yield path
    shutil.rmtree(tmpdir, ignore_errors=True)


def _open(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _row(payload, **where):
    hits = [r for r in payload["rows"] if all(r.get(k) == v for k, v in where.items())]
    assert len(hits) == 1, f"{where} matched {len(hits)} rows: {[r['key'] for r in payload['rows']]}"
    return hits[0]


def _dataset(payload, file):
    hits = [d for d in payload["datasets"] if d["file"] == file]
    assert len(hits) == 1, f"{file} appears {len(hits)} times in {[d['file'] for d in payload['datasets']]}"
    return hits[0]


def _cell(c):
    return (c["count"], c["hours"], c["state"])


# ── rows ────────────────────────────────────────────────────────────────────

def test_rows_merge_by_executed_steps_across_sessions_and_recordings(db):
    dm = _dm()
    conn = _open(db)
    try:
        m = dm.dataset_map(conn, exclude_files=[HELD_OUT_RECORDING_FILE])
        assert m["rows"][0]["key"] == "human", "the human reference is the first row"
        assert [r["kind"] for r in m["rows"]].count("template") == 1, "drop_detection from three sessions is ONE row"
        assert not any(r.get("template") == "dehshibi_spikes" for r in m["rows"]), "a removed run is not a row"
        tpl = _row(m, kind="template", template="drop_detection")
        assert tpl["version"] == 1 and tpl["label"].startswith("drop_detection")
        assert sorted(tpl["sessions"]) == [1, 2, 4], "the row says which sessions it came from"
        alpha, beta = _dataset(m, ALPHA), _dataset(m, BETA)
        # alpha CH1: the newer 1 h run counts its hour (2), the older whole run the rest (4000, 7000)
        assert _cell(alpha["cells"][tpl["key"]]["CH1"]) == (4, 2.0, "covered")
        # beta CH1 ran twice over the same hour: the newer run's count, not the sum and not the first
        assert _cell(beta["cells"][tpl["key"]]["CH1"]) == (5, 1.0, "covered")
    finally:
        conn.close()


def test_seed_runs_with_different_cuts_are_different_rows(db):
    dm = _dm()
    conn = _open(db)
    try:
        m = dm.dataset_map(conn, exclude_files=[HELD_OUT_RECORDING_FILE])
        c25 = _row(m, kind="seed", seedId="E0102", cut=2.5)
        c30 = _row(m, kind="seed", seedId="E0102", cut=3.0)
        assert c25["key"] != c30["key"] and c25["label"] != c30["label"]
        alpha = _dataset(m, ALPHA)
        assert alpha["cells"][c25["key"]]["CH1"]["count"] == 1
        assert alpha["cells"][c30["key"]]["CH1"]["count"] == 4
    finally:
        conn.close()


# ── cells and their states ──────────────────────────────────────────────────

def test_a_channel_the_run_never_covered_is_not_run_not_a_zero_count(db):
    dm = _dm()
    conn = _open(db)
    try:
        m = dm.dataset_map(conn, exclude_files=[HELD_OUT_RECORDING_FILE])
        tpl = _row(m, kind="template", template="drop_detection")
        alpha = _dataset(m, ALPHA)
        assert _cell(alpha["cells"][tpl["key"]]["CH2"]) == (1, 1.0, "covered"), "half-covered: an hour of coverage, one detection"
        assert [c["name"] for c in alpha["channels"]] == ["CH1", "CH2", "CH3"], "every channel of the dataset is a column, run or not"
        c25 = _row(m, kind="seed", seedId="E0102", cut=2.5)
        assert _cell(alpha["cells"][c25["key"]]["CH2"]) == (0, 0.0, "not_run")
    finally:
        conn.close()


def test_discarded_running_and_surrogate_runs_read_as_what_they_are(db):
    dm = _dm()
    conn = _open(db)
    try:
        m = dm.dataset_map(conn, exclude_files=[HELD_OUT_RECORDING_FILE])
        tpl = _row(m, kind="template", template="drop_detection")
        alpha, beta, gamma = _dataset(m, ALPHA), _dataset(m, BETA), _dataset(m, GAMMA)
        assert alpha["cells"][tpl["key"]]["CH1"]["count"] == 4, "the paired null's six detections are not the run's"
        assert _cell(alpha["cells"][tpl["key"]]["CH3"]) == (0, 0.0, "discarded"), \
            "a discard supersedes the shared runs row: the live sibling in session 2 may not resurrect it"
        assert _cell(beta["cells"][tpl["key"]]["CH2"]) == (1, 1.0, "covered"), "a newer run still running does not blank the older completed one"
        assert _cell(gamma["cells"][tpl["key"]]["CH1"]) == (0, 0.0, "running")
    finally:
        conn.close()


def test_the_human_row_counts_live_verdicts_over_where_a_person_looked(db):
    dm = _dm()
    conn = _open(db)
    try:
        m = dm.dataset_map(conn, exclude_files=[HELD_OUT_RECORDING_FILE])
        human = _row(m, key="human")
        alpha = _dataset(m, ALPHA)
        ch1 = alpha["cells"][human["key"]]["CH1"]
        # the reviewed hour plus the ten samples of the verdict at 4000, which a person looked at too
        assert _cell(ch1) == (2, round((ALPHA_N // 2 + 10) / 3600.0, 3), "covered"), "interesting, not deleted, over where a person looked"
        assert ch1["interesting"] == 2 and ch1["seed"] == 0 and ch1["reviewedH"] == 1.0
        ch2 = alpha["cells"][human["key"]]["CH2"]
        assert ch2["state"] == "covered" and ch2["count"] == 1 and 0 < ch2["hours"] < 0.1, \
            "no reviewed span on CH2 but two live verdicts: a person looked there"
        assert _cell(alpha["cells"][human["key"]]["CH3"]) == (0, 0.0, "not_reviewed")
    finally:
        conn.close()


def test_the_payload_says_what_is_missing(db):
    dm = _dm()
    conn = _open(db)
    try:
        m = dm.dataset_map(conn, exclude_files=[HELD_OUT_RECORDING_FILE])
        assert [d["file"] for d in m["datasets"]] == [ALPHA, BETA, GAMMA]
        assert m["datasets"][0]["hours"] == 2.0 and m["datasets"][1]["hours"] == 1.0
        assert [d["file"] for d in m["withoutRuns"]] == [DELTA], "a dataset with no Discovery run is named, not a blank group"
        assert m["heldOutOmitted"] == [HELD_OUT_RECORDING_FILE]
    finally:
        conn.close()


# ── one dataset, chunked ────────────────────────────────────────────────────

def test_chunks_split_a_channel_into_equal_slices_that_sum_to_the_whole(db):
    dm = _dm()
    conn = _open(db)
    try:
        whole = dm.channel_map(conn, ALPHA, chunks=1)
        halves = dm.channel_map(conn, ALPHA, chunks=2)
        tpl = _row(halves, kind="template", template="drop_detection")
        assert halves["chunks"] == 2 and whole["chunks"] == 1
        ch1 = halves["cells"][tpl["key"]]["CH1"]
        assert [_cell(c) for c in ch1] == [(2, 1.0, "covered"), (2, 1.0, "covered")]
        assert sum(c["count"] for c in ch1) == whole["cells"][tpl["key"]]["CH1"][0]["count"] == 4
        ch2 = halves["cells"][tpl["key"]]["CH2"]
        assert [_cell(c) for c in ch2] == [(1, 1.0, "covered"), (0, 0.0, "not_run")], "the second half of CH2 was never run"
        assert [c["name"] for c in halves["channels"]] == ["CH1", "CH2", "CH3"]
        assert halves["file"] == ALPHA and halves["hours"] == 2.0
    finally:
        conn.close()


def test_chunks_must_be_a_power_of_two_up_to_eight(db):
    dm = _dm()
    conn = _open(db)
    try:
        with pytest.raises(ValueError):
            dm.channel_map(conn, ALPHA, chunks=3)
    finally:
        conn.close()


# ── one channel, over time ──────────────────────────────────────────────────

def test_the_timeline_spans_the_whole_recording_and_marks_coverage(db):
    dm = _dm()
    conn = _open(db)
    try:
        t = dm.timeline_map(conn, ALPHA, "CH2", bin_h=0.5)
        assert t["hours"] == 2.0 and t["binH"] == 0.5 and t["nBins"] == 4, "the WHOLE recording, not a session's section"
        tpl = _row(t, kind="template", template="drop_detection")
        cell = t["cells"][tpl["key"]]
        assert cell["counts"] == [1, 0, 0, 0]
        assert cell["covered"] == [1.0, 1.0, 0.0, 0.0], "the run stopped at the hour: the last two bins are not-run, not empty"
        assert cell["state"] == "covered"
        human = t["cells"]["human"]
        # a not_interesting verdict at 1000 and an interesting one at 2000: both bins were looked at, one counts
        assert human["counts"] == [0, 1, 0, 0] and human["covered"][:2] > [0.0, 0.0] and human["covered"][2:] == [0.0, 0.0]
        t1 = dm.timeline_map(conn, ALPHA, "CH1", bin_h=1.0)
        assert t1["nBins"] == 2 and t1["cells"][tpl["key"]]["counts"] == [2, 2]
        # the verdicts at 100 and 4000 fall one in each hour; the second hour was looked at only where the verdict is
        h = t1["cells"]["human"]
        assert h["counts"] == [1, 1] and h["covered"][0] == 1.0 and 0.0 < h["covered"][1] < 0.01
        t3 = dm.timeline_map(conn, ALPHA, "CH3", bin_h=1.0)
        assert t3["cells"][tpl["key"]] == {"counts": [0, 0], "covered": [0.0, 0.0], "state": "discarded"}
    finally:
        conn.close()


def test_the_timeline_refuses_an_unknown_channel_loudly(db):
    dm = _dm()
    conn = _open(db)
    try:
        with pytest.raises(KeyError):
            dm.timeline_map(conn, ALPHA, "CH9", bin_h=1.0)
    finally:
        conn.close()

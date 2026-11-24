"""
test_autodetect_service.py
==========================
Auto-detect as the app runs it (2026-11-23): R4's inference agrees with the training script's, the line-up is read
from the database, progress only moves forward, a result round-trips through disk into the page's payload, and a
send to Review writes machine rows only - a listed detection queue and candidate sequences - once.
"""

import importlib.util
import json
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

from Working.autodetect import r4, service
from Working.autodetect.pipeline import AutoDetectResult
from Working.database.schema import init_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── R4 against the training script ──────────────────────────────────────────

def _script():
    try:
        spec = importlib.util.spec_from_file_location("_t_rq1b", os.path.join(ROOT, "scripts", "rq1b_minirocket.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:  # noqa: BLE001 - the script needs the main checkout; a worktree without it skips
        pytest.skip(f"the training script cannot be loaded here: {type(e).__name__}: {e}")


def test_r4_inputs_are_the_training_scripts(tmp_path):
    mr = _script()
    rng = np.random.default_rng(3)
    x = np.cumsum(rng.normal(size=5000)) * 0.01
    x[2200:2210] = np.nan                                   # a gap under 5 % of a long span: filled
    x[4000:4400] = np.nan                                   # most of a short span: left out
    npy = tmp_path / "rec.npy"
    np.save(npy, x)
    conn = init_db(str(tmp_path / "db.sqlite"))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                 "VALUES ('syn.mat', 0, 2.0, ?, 0, ?, 'mV')", (len(x), str(npy)))
    conn.commit()
    starts, ends = np.array([100, 2000, 4100, 0]), np.array([400, 2800, 4300, 30])
    M0, side0, keep0 = mr.extract(conn, pd.DataFrame({"recording_id": 1, "start": starts, "end": ends}))
    M1, side1, keep1 = r4.inputs(x, 2.0, starts, ends)
    assert list(keep0) == list(keep1) == [True, True, False, True]
    np.testing.assert_allclose(M0, M1)
    pd.testing.assert_frame_equal(side0.reset_index(drop=True), side1.reset_index(drop=True))
    np.testing.assert_allclose(mr.resample(x[:37], 512), r4.resample(x[:37], 512))


def test_r4_probability_is_the_training_scripts():
    mr = _script()
    path = os.path.join(ROOT, r4.MODEL)
    if not os.path.isfile(path):
        pytest.skip("R4's model is not in this checkout's DATA")
    model = r4.load_model(path)
    rng = np.random.default_rng(4)
    x = np.cumsum(rng.normal(size=6000)) * 0.02
    starts, ends = np.array([100, 900, 3000]), np.array([300, 1500, 3100])
    M, side, keep = r4.inputs(x, 1.0, starts, ends)
    np.testing.assert_allclose(r4.probability(model, M, side), mr.probability(model, M, side), rtol=1e-6)
    sc = r4.Scorer(model, x, 1.0, offset=50)
    np.testing.assert_allclose(sc(starts - 50, ends - 50), mr.probability(model, M, side), rtol=1e-6)
    inv = r4.Scorer(model, x, 1.0, invert=True)(starts, ends)
    np.testing.assert_allclose(inv, mr.probability(model, -M, side), rtol=1e-6)


# ── what a run reads ────────────────────────────────────────────────────────

def _db(tmp_path, templates=("drop_detection_v1", "wavelet_encoded")):
    conn = init_db(str(tmp_path / "db.sqlite"))
    for k, name in enumerate(templates):
        conn.execute("INSERT INTO templates (name, kind, version, steps_json, created_at) VALUES (?, 'detection', 1, ?, "
                     "'2026-11-23')", (name, json.dumps([{"stage": "detection", "algorithm": f"a{k}", "params": {}}])))
    conn.commit()
    return conn


def test_the_line_up_comes_from_the_database_and_says_what_is_missing(tmp_path):
    conn = _db(tmp_path)
    specs, missing = service.detector_specs(conn)
    names = [s["variant"] for s in specs]
    assert names == ["drop_detection_v1", "wavelet_encoded", "drop_detection_v1__w6h", "beads_sigma"]
    assert missing == ["drop_detection_v5", "BEADs_invert_detect_v1"]
    assert [s["window_s"] for s in specs] == [None, None, 6 * 3600.0, None]


def test_the_seed_bank_ships_with_the_code():
    fams, meta = service.load_seed_bank()
    assert len(fams) == meta["n_families"] == 64
    assert all(f.exemplar_mv.ndim == 1 and len(f.exemplar_mv) > 0 for f in fams)


def test_setup_says_what_is_missing(tmp_path):
    conn = _db(tmp_path)
    out = service.setup(conn, model_path=str(tmp_path / "no_model.joblib"))
    assert not out["ready"] and "R4's model" in out["problems"][0]
    assert out["missing_detectors"] == ["drop_detection_v5", "BEADs_invert_detect_v1"]


def test_progress_moves_forward_and_never_claims_done():
    seen = []
    p = service.Progress(7, 1_900_000, lambda f, m, left: seen.append((f, m, left)))
    for run in ("normal", "inverted"):
        for stage in [f"detector d{k}" for k in range(7)] + [
                "seed search (64 families)", "the event rule as a finder", "merge (10 proposals)",
                "boxes (5 candidates)", "R4 window scan", "gates", "R4 on 5 candidates", "sequences"]:
            p(f"{run}: {stage}")
    fracs = [f for f, _, _ in seen]
    assert fracs == sorted(fracs) and fracs[0] == 0.0 and fracs[-1] < 1.0 and fracs[-1] > 0.9
    assert seen[0][1] == "the signal: detector d0" and seen[-1][1] == "the inverted signal: sequences"
    assert seen[0][2] == pytest.approx(service.estimate_s(1_900_000), rel=0.05)


# ── a result on disk, the page's payload, the send ──────────────────────────

def _result():
    c = pd.DataFrame({
        "candidate_id": [0, 1, 2, 3], "start": [100, 400, 700, 1500], "end": [140, 460, 760, 1530],
        "confidence": [0.95, 0.7, 0.3, 0.9], "p_r4": [0.9, 0.6, 0.3, 0.8], "kind": "proposal",
        "sources": ["drop_detection_v1|seed", "event_rule", "", "beads_sigma"], "sequence_id": [0, 0, -1, -1],
        "polarity": ["drop", "drop", "drop", "spike"], "depth_mv": [2.0, 1.0, 0.4, 0.8],
        "onset": [105, 410, 705, 1502], "extremum": [110, 420, 710, 1505], "event_end": [130, 450, 750, 1520],
        "recovered": True, "run": ["normal", "normal", "normal", "inverted"], "runs": ["normal", "normal", "normal", "both"],
        "sharpness": [20.0, 8.0, 3.0, 30.0], "member_variants": ["drop_detection_v1|seed__F-07", "event_rule", "", "beads_sigma"],
        "lifts": "[[\"r4\", 0.9]]", "scan_p": np.nan})
    s = pd.DataFrame({"sequence_id": [0], "start": [100], "end": [460], "start_s": [100.0], "end_s": [460.0],
                      "n_members": [2], "mean_confidence": [0.825], "min_confidence": [0.7], "median_gap_s": [300.0],
                      "rule": ["gap <= 3600 s"], "polarity": ["drop"]})
    res = AutoDetectResult(candidates=c, sequences=s, proposals=pd.DataFrame(), scan_windows=10,
                           scan_hits=pd.DataFrame(), timings={"normal:boxes": 1.0}, info={"rise_sharpness": 10.0})
    meta = {"version": "v4", "recording": {"id": 1, "source_file": "syn.mat", "channel": 0, "fs": 1.0, "units": "mV",
                                           "n_samples": 3000},
            "stretch": {"start_idx": 1000, "end_idx": 3000, "n_samples": 2000}, "floor_mv": 0.1,
            "floor_source": "test", "missing_detectors": [], "wall_s": 12.0, "timings": res.timings,
            "scan_windows": 10, "info": res.info, "whole_drop": {"sha256_12": "abc"}, "created_at": "2026-11-23T22:00:00"}
    return res, meta


def test_a_result_round_trips_into_the_pages_payload(tmp_path):
    res, meta = _result()
    out = service.result_dir(7, str(tmp_path))
    summary = service.save(out, res, meta)
    assert summary == {"candidates": 4, "at_05": 3, "drops_05": 2, "rises_05": 1, "sequences": 1, "wall_s": 12.0}
    listed = service.results(str(tmp_path), recording_id=1)
    assert [r["job_id"] for r in listed] == [7] and service.results(str(tmp_path), recording_id=2) == []
    body = service.payload(*service.load(out))
    cand = body["candidates"]
    assert cand["s"] == [100, 400, 700, 1500] and cand["pol"] == [0, 0, 0, 1] and cand["inv"] == [0, 0, 0, 1]
    assert cand["src"][0] == (1 << service.SOURCES.index("drop_detection_v1")) | (1 << service.SOURCES.index("seed"))
    assert cand["src"][2] == 0 and cand["fam"][0] == "F-07"
    assert body["sequences"]["s"] == [100] and body["start_idx"] == 1000 and body["n"] == 2000
    with pytest.raises(FileExistsError):   # a second save to the same job never replaces the first
        service.save(out, res, meta)


def test_a_send_writes_machine_rows_once(tmp_path):
    conn = init_db(str(tmp_path / "db.sqlite"))
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES ('syn.mat', 0, 1.0, 3000, 0, 'x.npy')")
    conn.commit()
    res, meta = _result()
    out = service.result_dir(7, str(tmp_path / "results"))
    service.save(out, res, meta)
    got = service.send_to_review(conn, out, job_id=7, min_confidence=0.5)
    assert got["detections"] == 3 and got["queue_id"] and got["sequences"] == 1 and got["sequence_queue_id"]
    rows = conn.execute("SELECT start_idx, end_idx, score, meta_json FROM detections ORDER BY start_idx").fetchall()
    assert [(r[0], r[1]) for r in rows] == [(1100, 1140), (1400, 1460), (2500, 2530)]   # absolute, in time order
    assert json.loads(rows[0][3])["candidate_id"] == 0 and rows[0][2] == pytest.approx(0.95)
    q = json.loads(conn.execute("SELECT filters_json FROM review_queues WHERE id = ?", (got["queue_id"],)).fetchone()[0])
    assert q["order"] == "listed" and len(q["detection_ids"]) == 3
    assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0          # never a human row
    seq = conn.execute("SELECT origin, start_idx, end_idx, n_events FROM sequences").fetchone()
    assert tuple(seq) == ("machine", 1100, 1460, 2)
    again = service.send_to_review(conn, out, job_id=7, min_confidence=0.5)
    assert again["detections"] == 0 and again["already_sent"] == 3 and again["sequences"] == 0
    assert conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 3
    assert len(service.load(out)[2]["sent"]) == 2
    # the sequence is not sent a second time either: the send says so and touches no sequence queue
    assert again["sequences_already_sent"] == 1 and again["sequence_queue_id"] is None
    assert service.load(out)[2]["sent"][0]["sequence_ids"] == [0] and service.load(out)[2]["sent"][1]["sequence_ids"] == []


def test_lanes_keep_overlapping_boxes_apart_and_reuse_a_free_lane():
    # [start, end) boxes: 0 and 1 share samples 150-159; 2 starts where 1's lane is free again; 3 touches 2's end
    starts, ends = [100, 150, 300, 340], [160, 200, 340, 380]
    assert service.lanes(starts, ends) == [0, 1, 0, 0]
    assert service.lanes([], []) == []


def test_overlapping_candidates_reach_review_as_separate_items(tmp_path):
    # Review serves overlapping detections of one run as ONE item (one verdict); a drop whose box runs into the next
    # rise must stay two items, so the send puts them in different runs (lanes)
    from Working.review import queues as Q
    conn = init_db(str(tmp_path / "db.sqlite"))
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES ('syn.mat', 0, 1.0, 3000, 0, 'x.npy')")
    conn.commit()
    res, meta = _result()
    c = res.candidates
    c.loc[1, ["start", "end", "polarity"]] = [120, 200, "spike"]     # overlaps candidate 0 (100-140)
    out = service.result_dir(9, str(tmp_path / "results"))
    service.save(out, res, meta)
    got = service.send_to_review(conn, out, job_id=9, min_confidence=0.5)
    assert got["detections"] == 3 and len(got["run_ids"]) == 2
    runs = [r[0] for r in conn.execute("SELECT run_id FROM detections ORDER BY start_idx")]
    assert runs[0] != runs[1] and runs[0] == runs[2]
    assert len(Q.queue_items(conn, got["queue_id"])) == 3 and got["items"] == 3 and got["held_back"] == 0


def test_a_send_names_the_channel_as_every_page_does_and_counts_what_review_holds_back(tmp_path):
    conn = init_db(str(tmp_path / "db.sqlite"))
    conn.row_factory = sqlite3.Row
    for ch in range(14):   # stored channel 13 of a fourteen-channel file is CH14 on every page
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, 1.0, 3000, 0, 'x.npy')", (ch,))
    rid = conn.execute("SELECT id FROM recordings WHERE channel = 13").fetchone()[0]
    # the researcher already judged the event candidate 0 is: Review holds that one back
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                 "VALUES (?, 1100, 1140, 'interesting', 'test', '2026-11-23')", (rid,))
    conn.commit()
    res, meta = _result()
    meta["recording"].update(id=rid, channel=13)
    out = service.result_dir(8, str(tmp_path / "results"))
    service.save(out, res, meta)
    got = service.send_to_review(conn, out, job_id=8, min_confidence=0.5)
    names = [r[0] for r in conn.execute("SELECT name FROM review_queues ORDER BY id")]
    assert names == ["Auto-detect · syn.mat CH14 · job 8", "Auto-detect sequences · syn.mat CH14"]
    assert got["detections"] == 3 and got["held_back"] == 1 and "held_back_error" not in got

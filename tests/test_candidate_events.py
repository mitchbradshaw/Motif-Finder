"""
test_candidate_events.py
========================
a2-rq1b: `Working/discovery/candidate_events.py` — the RQ4b sweep's detections on one recording merged into
CANDIDATE EVENTS, each carrying which detectors found it and which agree with it; the researcher's existing verdicts
attached to the events they cover; a seeded, stratified sample of the UNJUDGED events put to Review blind; and the
estimator that turns the answers (plus the existing verdicts, counted as a census) into a precision per agreement
level, per detector family and per setting.

What is pinned, and why each one is silent when broken:

* **One rule for "the same event".** Detections merge, and a human span labels an event, under §4.6
  (`Working.discovery.matching`: reciprocal IoU and onset agreement), the rule Review already uses to call a
  detection "already judged". A second rule would make the two disagree about what was judged.
* **No chaining.** A detector's own overlapping detections never merge (a dense detector would otherwise chain a
  whole recording into one event), a long detection never swallows a short one, and each event holds at most one
  detection per setting.
* **Existing verdicts are training data and are never re-asked** (the researcher, 2026-10-18). An event inherits a
  same-event verdict, or `not_interesting` from a human span that wholly holds it (Q-W1); an event inside an
  interesting span stays unjudged; contradictions are flagged and left unjudged rather than resolved silently.
* **The sample is honest.** Only unjudged events are drawn, at random within strata, with weights N_h / n_h, so the
  acceptance rates estimate precision without bias; the existing verdicts enter the estimate as a census.
* **Blind and shuffled.** The queue carries no score and is served in a seeded random order.
* **M4_aug is never touched** (the held-out exam, RQ1b 2026-10-18).

Run from the project root:
    python -m pytest tests/test_candidate_events.py -q
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database.schema import init_db
from Working.database import adjudications as adj
from Working.database import queries as q
from Working.database import vocabulary as v
from Working.discovery import candidate_events as ce
from Working.review import queues as qs

N = 100_000
T = "2026-10-18T00:00:00"


# ── fixtures ───────────────────────────────────────────────────────────────

def _conn():
    conn = init_db(":memory:")
    v.seed_vocabulary(conn)
    return conn


def _recording(conn, source_file="rec.mat", channel=0):
    return q.insert_recording(conn, source_file, channel, 1.0, N, 0, f"data/{source_file}/CH{channel}.npy")


def _session(conn, source_file="rec.mat"):
    cur = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                       "VALUES ('screen', ?, '[]', ?, ?)", (source_file, T, T))
    conn.commit()
    return cur.lastrowid


_KEY = [0]


def _run(conn, sid, rid, variant, spans, *, kind="template", removed=False, superseded=False, span=(0, N),
         status="completed", group=None, started_at=T):
    """A Discovery run of one template variant on one recording, with its detections. Returns (run, [det ids])."""
    _KEY[0] += 1
    gid = group or conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (T,)).lastrowid
    cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
                       (f"cfg-{_KEY[0]}", json.dumps({"template": variant}), T)).lastrowid
    run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                       "run_group_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (cid, rid, span[0], span[1], started_at, status, gid)).lastrowid
    if superseded:
        conn.execute("UPDATE runs SET superseded_at = ? WHERE id = ?", (T, run))
    dets = [conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 1.0)",
                         (run, s, e)).lastrowid for s, e in spans]
    if group is None:
        conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, template_name, run_group_id, "
                     "status, created_at, updated_at, removed_at) VALUES (?, ?, ?, ?, ?, ?, 'done', ?, ?, ?)",
                     (sid, f"k{_KEY[0]}", kind, variant or "seed", variant if kind == "template" else None, gid,
                      T, T, T if removed else None))
    conn.commit()
    return run, dets


def _annotation(conn, rid, s, e, verdict, source="library_review", deleted=False):
    aid = q.insert_annotation(conn, rid, s, e, verdict, source=source)
    if deleted:
        conn.execute("UPDATE annotations SET deleted_at = ? WHERE id = ?", (T, aid))
        conn.commit()
    return aid


def _dets(rows, recording_id=1):
    """A detections frame: rows of (detection_id, variant, start, end)."""
    runs = {}
    out = []
    for d, var, s, e in rows:
        runs.setdefault(var, 100 + len(runs))
        out.append({"detection_id": d, "run_id": runs[var], "recording_id": recording_id, "variant": var,
                    "start": s, "end": e})
    return pd.DataFrame(out)


def _by_anchor(events):
    return {int(r.anchor_detection_id): r for r in events.itertuples()}


# ── families ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, family", [
    ("noise_threshold", "noise_threshold"),
    ("noise_threshold__k_sigma_3", "noise_threshold"),
    ("drop_detection_v1__slope_sigma_4", "drop_detection_v1"),
    ("Wavelet_detection_prototype__epsilon_factor_0p02", "Wavelet_detection_prototype"),
    ("cnn_gasf_10min", "cnn_10min"),
    ("cnn_fusion3_60min", "cnn_60min"),
    ("cnn_recurrence_1min", "cnn_1min"),
    ("mp_threshold__threshold_6__backend_auto", "matrix_profile"),
    ("mp_motifs__backend_auto", "matrix_profile"),
])
def test_family_of_merges_a_template_s_settings_and_one_scale_s_cnns(name, family):
    assert ce.family_of(name) == family


def test_the_module_imports_no_ui_library():
    with open(os.path.join(PROJECT_ROOT, "Working", "discovery", "candidate_events.py"), encoding="utf-8") as f:
        src = f.read()
    for banned in ("panel", "holoviews", "bokeh", "fastapi", "uvicorn", "matplotlib"):
        assert f"import {banned}" not in src and f"from {banned}" not in src


# ── building events ────────────────────────────────────────────────────────

def test_two_detectors_on_one_event_make_one_event_anchored_by_the_rarer():
    dets = _dets([(1, "drop_detection_v1", 1000, 2000),
                  (2, "noise_threshold", 1050, 2050), (3, "noise_threshold", 5000, 5100),
                  (4, "noise_threshold", 9000, 9100)])
    events, members = ce.build_events(dets)
    assert len(events) == 3
    e = _by_anchor(events)[1]
    assert (e.anchor_variant, e.start, e.end, e.n_members) == ("drop_detection_v1", 1000, 2000, 2)
    assert e.matched_families == "drop_detection_v1|noise_threshold" and e.n_matched_families == 2
    # every detection belongs to exactly one event
    assert sorted(members["detection_id"]) == [1, 2, 3, 4]
    assert members.groupby("detection_id").size().max() == 1
    assert set(members.loc[members.detection_id == 2, "event_id"]) == {e.event_id}


def test_a_detector_s_own_overlapping_detections_never_merge():
    dets = _dets([(1, "OASIS_Deconvolution__threshold_3", 0, 600),
                  (2, "OASIS_Deconvolution__threshold_3", 60, 660),
                  (3, "OASIS_Deconvolution__threshold_3", 120, 720)])
    events, _ = ce.build_events(dets)
    assert len(events) == 3 and set(events.n_members) == {1}


def test_a_long_detection_does_not_swallow_a_short_one():
    dets = _dets([(1, "cnn_gasf_60min", 0, 7200), (2, "signal_threshold", 3000, 3040)])
    events, _ = ce.build_events(dets)
    assert len(events) == 2


def test_a_late_onset_is_not_the_same_event_even_with_a_good_overlap():
    # IoU 0.7, but the BEADs detection starts 600 samples early: over 0.25 x its own 2000 samples (§4.6)
    dets = _dets([(1, "wavelet_encoded", 1600, 3000),
                  (2, "BEADs_invert_detect_v1", 1000, 3000), (3, "BEADs_invert_detect_v1", 50000, 50100)])
    events, _ = ce.build_events(dets)
    assert len(events) == 3


def test_an_event_takes_at_most_one_detection_per_setting_the_best_fitting():
    dets = _dets([(1, "drop_detection_v5", 1000, 2000),
                  (2, "noise_threshold__k_sigma_3", 1100, 2000),      # IoU 0.90
                  (3, "noise_threshold__k_sigma_3", 1000, 1950)])     # IoU 0.95: this one joins
    events, members = ce.build_events(dets)
    assert len(events) == 2
    anchored = _by_anchor(events)[1]
    assert set(members.loc[members.event_id == anchored.event_id, "detection_id"]) == {1, 3}


def test_events_are_built_per_recording_and_never_across_channels():
    a = _dets([(1, "drop_detection_v1", 1000, 2000)], recording_id=1)
    b = _dets([(2, "noise_threshold", 1000, 2000)], recording_id=2)
    events, _ = ce.build_events(pd.concat([a, b], ignore_index=True))
    assert len(events) == 2 and sorted(events.recording_id) == [1, 2]


# ── agreement ──────────────────────────────────────────────────────────────

def test_agreement_counts_a_covering_detector_and_a_detector_inside_a_long_event():
    dets = _dets([(1, "OASIS_Deconvolution", 0, 1200),          # covers E entirely
                  (2, "signal_threshold", 100, 300),             # E
                  (3, "drop_detection_v1", 5000, 8000),          # F, a long event
                  (4, "noise_threshold", 5100, 5200),            # wholly inside F
                  (5, "BEADs_invert_detect_v1", 7900, 8500)])    # 100 of its 600 inside F: not agreeing
    events, members = ce.build_events(dets)
    events = ce.add_agreement(events, dets)
    e = _by_anchor(events)
    assert e[2].agree_families == "OASIS_Deconvolution|signal_threshold" and e[2].n_agree == 2
    assert e[3].agree_families == "drop_detection_v1|noise_threshold" and e[3].n_agree == 2
    assert e[4].n_agree == 2                                     # F covers it entirely
    assert e[5].agree_families == "BEADs_invert_detect_v1" and e[5].n_agree == 1


# ── existing verdicts ──────────────────────────────────────────────────────

def _label_fixture():
    conn = _conn()
    sid = _session(conn)
    rid = _recording(conn)
    spans = [(1010, 2000), (20000, 20100), (30000, 30100), (40000, 40100), (50000, 50500), (60000, 60500),
             (70000, 70500), (80000, 80500), (90000, 90500), (95000, 95500)]
    run, dets = _run(conn, sid, rid, "noise_threshold", spans)
    _seed_run, seed_dets = _run(conn, sid, rid, None, [(50000, 50500), (90000, 90500)], kind="seed")
    ids = {}
    ids["same"] = _annotation(conn, rid, 1000, 2000, "interesting")
    ids["inside_not"] = _annotation(conn, rid, 19800, 20400, "not_interesting", source="imported_10min")
    ids["inside_int"] = _annotation(conn, rid, 29900, 30500, "interesting", source="imported_10min")
    _annotation(conn, rid, 39800, 40400, "interesting", source="imported_10min")
    _annotation(conn, rid, 39900, 40500, "not_interesting", source="imported_10min")
    ids["adj_seed"] = adj.insert_adjudication(conn, seed_dets[0], "seed")
    ids["adj_member"] = adj.insert_adjudication(conn, dets[5], "not_interesting")
    _annotation(conn, rid, 70000, 70500, "unsure")
    _annotation(conn, rid, 80000, 80500, "interesting", deleted=True)
    _annotation(conn, rid, 90000, 90500, "interesting")
    adj.insert_adjudication(conn, seed_dets[1], "not_interesting")
    _annotation(conn, rid, 95000, 95500, "artifact", source="blind_test_review")
    events, members, _meta = ce.build_table(conn, "rec.mat")
    return conn, ce.attach_labels(conn, events, members), dets, ids


def test_a_same_event_verdict_labels_the_event():
    _c, ev, dets, ids = _label_fixture()
    e = _by_anchor(ev)[dets[0]]
    assert (e.label, e.label_kind) == ("interesting", "same_event")
    assert f"annotation:{ids['same']}" in e.label_refs


def test_an_event_inside_a_not_interesting_span_is_not_interesting():
    _c, ev, dets, ids = _label_fixture()
    e = _by_anchor(ev)[dets[1]]
    assert (e.label, e.label_kind) == ("not_interesting", "inside_span")
    assert f"annotation:{ids['inside_not']}" in e.label_refs


def test_an_event_inside_an_interesting_span_stays_unjudged_but_says_so():
    _c, ev, dets, _ids = _label_fixture()
    e = _by_anchor(ev)[dets[2]]
    assert pd.isna(e.label) and bool(e.inside_interesting)


def test_an_event_inside_both_an_interesting_and_a_not_interesting_span_is_a_conflict():
    _c, ev, dets, _ids = _label_fixture()
    e = _by_anchor(ev)[dets[3]]
    assert pd.isna(e.label) and e.label_kind == "conflict"


def test_an_adjudication_on_another_run_s_detection_of_the_same_event_labels_it():
    _c, ev, dets, ids = _label_fixture()
    e = _by_anchor(ev)[dets[4]]
    assert (e.label, e.label_kind) == ("interesting", "same_event")      # a seed verdict is interesting (Q41)
    assert f"adjudication:{ids['adj_seed']}" in e.label_refs


def test_an_adjudication_on_the_event_s_own_detection_labels_it():
    _c, ev, dets, _ids = _label_fixture()
    e = _by_anchor(ev)[dets[5]]
    assert (e.label, e.label_kind) == ("not_interesting", "member")


def test_unsure_is_kept_as_unsure_and_a_deleted_span_is_ignored():
    _c, ev, dets, _ids = _label_fixture()
    by = _by_anchor(ev)
    assert by[dets[6]].label == "unsure"
    assert pd.isna(by[dets[7]].label) and pd.isna(by[dets[7]].label_kind)


def test_two_verdicts_that_disagree_on_one_event_are_a_conflict_and_an_artifact_is_kept():
    _c, ev, dets, _ids = _label_fixture()
    by = _by_anchor(ev)
    assert pd.isna(by[dets[8]].label) and by[dets[8]].label_kind == "conflict"
    assert (by[dets[9]].label, by[dets[9]].label_kind) == ("artifact", "same_event")


# ── reading the sweep ──────────────────────────────────────────────────────

def test_the_sweep_is_read_from_live_real_template_runs_only():
    conn = _conn()
    sid = _session(conn)
    r1, r2 = _recording(conn, channel=0), _recording(conn, channel=1)
    _run(conn, sid, r1, "noise_threshold", [(100, 200), (300, 400)])
    nt2, _ = _run(conn, sid, r2, "noise_threshold", [(500, 600)])
    gid = conn.execute("SELECT run_group_id FROM runs WHERE id = ?", (nt2,)).fetchone()[0]
    sur = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                       "run_group_id, surrogate_of_run_id) VALUES (1, ?, 0, ?, ?, 'completed', ?, ?)",
                       (r2, N, T, gid, nt2)).lastrowid
    conn.execute("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, 7000, 7100)", (sur,))
    _run(conn, sid, r1, "cnn_gasf_1min", [(900, 960)])                       # the negative control
    _run(conn, sid, r1, "symbol_search", [(1100, 1200)], removed=True)        # taken off its session
    _run(conn, sid, r1, "signal_threshold", [(1300, 1400)], superseded=True)  # discarded
    _run(conn, sid, r1, "BEADs_invert_detect_v1", [(1500, 1600)], status="failed")
    part, _ = _run(conn, sid, r1, "wavelet_encoded", [(1700, 1800)])
    stitched, _ = _run(conn, sid, r1, "wavelet_encoded__level_3", [(1900, 2000)])
    conn.execute("INSERT INTO stitched_windows (run_id, window_index, window_run_id, span_start, span_end, "
                 "core_start, core_end) VALUES (?, 0, ?, 0, ?, 0, ?)", (stitched, part, N, N))
    _run(conn, sid, r1, None, [(2100, 2200)], kind="seed")                    # a seed search is not a detector
    _run(conn, sid, r1, "drop_detection_v5", [(2300, 2400)], span=(0, 5000))  # a short-span run ...
    whole, _ = _run(conn, sid, r1, "drop_detection_v5", [(2500, 2600)])       # ... and the whole-span one
    conn.commit()
    got = ce.load_sweep_detections(conn, "rec.mat")
    d = got["detections"]
    assert sorted(zip(d.variant, d.start)) == [("drop_detection_v5", 2500), ("noise_threshold", 100),
                                               ("noise_threshold", 300), ("noise_threshold", 500),
                                               ("wavelet_encoded__level_3", 1900)]
    assert "cnn_gasf_1min" in got["excluded_variants"]
    assert any(s["variant"] == "drop_detection_v5" and "span" in s["reason"] for s in got["skipped"])
    assert {r["run_id"] for r in got["runs"]} >= {whole, nt2}
    assert set(got["recordings"]) == {r1, r2}


def test_the_held_out_recording_is_refused_by_name():
    conn = _conn()
    _recording(conn, source_file=HELD_OUT_RECORDING_FILE)
    with pytest.raises(PermissionError):
        ce.load_sweep_detections(conn, HELD_OUT_RECORDING_FILE)
    with pytest.raises(PermissionError):
        ce.build_table(conn, HELD_OUT_RECORDING_FILE)


def test_build_table_records_how_the_table_was_made():
    conn = _conn()
    sid = _session(conn)
    rid = _recording(conn)
    _run(conn, sid, rid, "drop_detection_v1", [(1000, 2000)])
    _run(conn, sid, rid, "noise_threshold", [(1050, 2050), (5000, 5100)])
    events, members, meta = ce.build_table(conn, "rec.mat")
    assert len(events) == 2 and len(members) == 3
    assert {"source_file", "rule", "runs", "skipped", "excluded_variants", "families", "n_events", "key",
            "labels"} <= set(meta)
    assert meta["rule"]["criterion"] == "reciprocal_iou_onset"
    assert meta["n_events"] == 2 and set(events.columns) >= {"event_id", "recording_id", "channel", "start", "end",
                                                             "anchor_detection_id", "n_agree", "label"}


def test_a_table_round_trips_through_disk(tmp_path):
    conn = _conn()
    sid = _session(conn)
    rid = _recording(conn)
    _run(conn, sid, rid, "drop_detection_v1", [(1000, 2000)])
    _run(conn, sid, rid, "noise_threshold", [(1050, 2050), (5000, 5100)])
    events, members, meta = ce.build_table(conn, "rec.mat")
    where = ce.save_table(tmp_path, events, members, meta)
    e2, m2, meta2 = ce.load_table(where)
    pd.testing.assert_frame_equal(events.reset_index(drop=True), e2.reset_index(drop=True), check_dtype=False)
    pd.testing.assert_frame_equal(members.reset_index(drop=True), m2.reset_index(drop=True), check_dtype=False)
    assert meta2["key"] == meta["key"] and os.path.basename(str(where)) == meta["key"]


# ── the sample ─────────────────────────────────────────────────────────────

def _synthetic_events(n=600, seed=1):
    rng = np.random.default_rng(seed)
    fams = ["noise_threshold", "OASIS_Deconvolution", "drop_detection_v5", "drop_detection_v1"]
    rows = []
    for i in range(n):
        matched = sorted(set(rng.choice(fams, size=rng.integers(1, 3), replace=False)))
        rows.append({"event_id": i, "recording_id": 1, "channel": 0, "start": 1000 * i, "end": 1000 * i + 100,
                     "anchor_detection_id": 10_000 + i, "anchor_variant": matched[0],
                     "matched_families": "|".join(matched), "n_matched_families": len(matched),
                     "n_agree": int(rng.integers(1, 13)), "label": None, "label_kind": None})
    ev = pd.DataFrame(rows)
    ev.loc[ev.event_id % 10 == 0, "label"] = "interesting"
    ev.loc[ev.event_id % 10 == 1, "label"] = "not_interesting"
    ev.loc[ev.event_id % 10 == 2, "label"] = "unsure"
    ev.loc[ev.event_id % 10 == 3, "label_kind"] = "conflict"
    return ev


def test_strata_put_a_selective_family_first_then_the_agreement_level():
    ev = pd.DataFrame([
        {"matched_families": "drop_detection_v5|noise_threshold", "n_agree": 9},
        {"matched_families": "drop_detection_v1|drop_detection_v5", "n_agree": 2},
        {"matched_families": "noise_threshold", "n_agree": 4},
        {"matched_families": "OASIS_Deconvolution", "n_agree": 11},
        {"matched_families": "OASIS_Deconvolution", "n_agree": 1},
    ])
    assert list(ce.assign_strata(ev)) == ["family:drop_detection_v5", "family:drop_detection_v1", "agree:3-4",
                                         "agree:9+", "agree:1-2"]


def test_the_sample_draws_only_unjudged_events_with_honest_weights():
    ev = _synthetic_events()
    s = ce.draw_sample(ev, seed=0, per_level=20, per_family=10)
    frame = ev[ev.label.isna()]
    assert set(s.event_id) <= set(frame.event_id)
    assert set(s.event_id) & set(ev.loc[ev.label_kind == "conflict", "event_id"])  # a conflict may be drawn
    strata = ce.assign_strata(frame)
    for name, g in s.groupby("stratum"):
        n_frame = int((strata == name).sum())
        alloc = 10 if name.startswith("family:") else 20
        assert len(g) == min(alloc, n_frame)
        assert set(g.frame_size) == {n_frame} and set(g.sample_size) == {len(g)}
        assert np.allclose(g.weight, n_frame / len(g))
    assert list(s.detection_id) == list(ev.set_index("event_id").loc[s.event_id, "anchor_detection_id"])


def test_the_sample_is_seeded_and_served_shuffled():
    ev = _synthetic_events()
    a = ce.draw_sample(ev, seed=0, per_level=20, per_family=10)
    b = ce.draw_sample(ev, seed=0, per_level=20, per_family=10)
    c = ce.draw_sample(ev, seed=1, per_level=20, per_family=10)
    pd.testing.assert_frame_equal(a, b)
    assert set(a.event_id) != set(c.event_id)
    order = a.sort_values("serve_rank").event_id.tolist()
    assert sorted(a.serve_rank) == list(range(len(a)))
    assert order != sorted(order)


# ── the estimate ───────────────────────────────────────────────────────────

def _two_strata():
    rows = [{"event_id": i, "recording_id": 1, "channel": 0, "start": 10 * i, "end": 10 * i + 5,
             "anchor_detection_id": 1000 + i, "anchor_variant": "OASIS_Deconvolution",
             "matched_families": "OASIS_Deconvolution", "n_matched_families": 1, "n_agree": 1, "label": None,
             "label_kind": None} for i in range(1000)]
    rows += [{"event_id": 1000 + i, "recording_id": 1, "channel": 0, "start": 20000 + 10 * i, "end": 20005 + 10 * i,
              "anchor_detection_id": 3000 + i, "anchor_variant": "noise_threshold",
              "matched_families": "noise_threshold", "n_matched_families": 1, "n_agree": 4,
              "label": None, "label_kind": None} for i in range(100)]
    ev = pd.DataFrame(rows)
    members = pd.DataFrame({"event_id": ev.event_id, "detection_id": ev.anchor_detection_id,
                            "variant": ev.anchor_variant, "family": ev.anchor_variant})
    return ev, members


def test_the_estimate_weights_each_stratum_by_its_sampling_rate():
    ev, members = _two_strata()
    s = ce.draw_sample(ev, seed=0, per_level=10, per_family=10)
    s_big = ce.draw_sample(ev, seed=0, per_level=100, per_family=10)
    s = pd.concat([s[s.stratum == "agree:1-2"], s_big[s_big.stratum == "agree:3-4"]], ignore_index=True)
    s["serve_rank"] = range(len(s))
    low = s[s.stratum == "agree:1-2"].detection_id.tolist()
    high = s[s.stratum == "agree:3-4"].detection_id.tolist()
    verdicts = {d: ("interesting" if k < 5 else "not_interesting") for k, d in enumerate(low)}
    verdicts.update({d: ("interesting" if k < 90 else "not_interesting") for k, d in enumerate(high)})
    est = ce.estimate(ev, members, s, verdicts, n_boot=200, seed=0)
    g = est["groups"]
    assert g["agree:1-2"]["precision"] == pytest.approx(0.5)
    assert g["agree:3-4"]["precision"] == pytest.approx(0.9)
    assert g["all"]["precision"] == pytest.approx((0.5 * 1000 + 90) / 1100)
    assert g["variant:noise_threshold"]["precision"] == pytest.approx(0.9)
    # a stratum taken whole has no sampling error: its interval is the point
    assert g["agree:3-4"]["ci"][0] == pytest.approx(0.9) and g["agree:3-4"]["ci"][1] == pytest.approx(0.9)
    lo, hi = g["agree:1-2"]["ci"]
    assert lo < 0.5 < hi


def test_existing_verdicts_enter_the_estimate_as_a_census():
    ev, members = _two_strata()
    ev.loc[ev.event_id >= 1050, "label"] = "interesting"      # 50 judged before, all interesting
    s = ce.draw_sample(ev, seed=0, per_level=1000, per_family=10)
    verdicts = {d: "not_interesting" for d in s.detection_id}
    g = ce.estimate(ev, members, s, verdicts, n_boot=50, seed=0)["groups"]
    assert g["agree:3-4"]["precision"] == pytest.approx(50 / 100)
    assert g["agree:3-4"]["n_judged_before"] == 50 and g["agree:3-4"]["n_sampled"] == 50
    assert g["all"]["precision"] == pytest.approx(50 / 1100)


def test_unsure_and_unanswered_items_are_counted_and_left_out():
    ev, members = _two_strata()
    s = ce.draw_sample(ev, seed=0, per_level=10, per_family=10)
    ids = s.detection_id.tolist()
    verdicts = {ids[0]: "unsure", ids[1]: "interesting", ids[2]: "not_interesting"}
    est = ce.estimate(ev, members, s, verdicts, n_boot=20, seed=0)
    assert est["answered"] == 2 and est["unsure"] == 1 and est["pending"] == len(ids) - 3


# ── the queue ──────────────────────────────────────────────────────────────

def test_the_sample_goes_to_review_as_one_blind_shuffled_queue():
    conn = _conn()
    sid = _session(conn)
    rid = _recording(conn)
    _run(conn, sid, rid, "noise_threshold", [(1000 * i, 1000 * i + 100) for i in range(40)])
    events, members, _meta = ce.build_table(conn, "rec.mat")
    s = ce.draw_sample(events, seed=3, per_level=100, per_family=10)
    qid = ce.create_sample_queue(conn, s, name="RQ1b sample", note="rq1b:test")
    queue = qs.get_queue(conn, qid)
    assert (queue["source_kind"], queue["blind"], queue["writes_to"]) == ("discovery-run", 1, "adjudications")
    served = [it["target_id"] for it in qs.queue_items(conn, qid)]
    assert served == s.sort_values("serve_rank").detection_id.tolist()
    assert all("score" not in it for it in qs.queue_items(conn, qid))
    assert ce.create_sample_queue(conn, s, name="RQ1b sample", note="rq1b:test") == qid

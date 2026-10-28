"""
test_cross_census.py
====================
Cross-channel explorer S1 (`docs/prompts/changes/cross-channel-explorer.md`): the census of co-occurring detector
events across channels that answers round-B question B4 — is there a propagation lag between channels that is not
an artefact?

In plain words: every detected event on every channel is paired with every event on another channel that starts
within 50 s of it. Each pair is measured on the same stretch of both channels (lag and r), tested against luck, and
put in a bin: a copy at the same instant is an artifact (any packs); a delayed match within a pack is propagation; a
match across packs that is not a copy is a shared driver; the rest is independent. Copies at one instant are joined
into an instant, which is common mode when it is broad or spans packs. The planted cases below check each reading.

Runnable standalone:  python tests/test_cross_census.py
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _cross_census_synthetic as syn  # noqa: E402
from Working import config  # noqa: E402
from Working import cross_census as cc  # noqa: E402
from Working import cross_channel as xc  # noqa: E402
from Working.channel_layout import PAGE as LAYOUT_PAGE, pack_key  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.registration.settings import HELD_OUT_FILE, put_settings  # noqa: E402

M2A = "M2_aug_census_a.mat"     # an M2-style name: 16 channels named CH1_A1 … CH16_D2, packs A–D
M2B = "M2_aug_census_b.mat"
M2C = "M2_aug_census_c.mat"
FOUR = "CO_census.mat"          # four channels, no pack in their names: one unassigned pack


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STEP_CACHE_ROOT", str(tmp_path / "step_cache"))
    c = init_db(str(tmp_path / "census.sqlite"))
    yield c
    c.close()


def _ids_by_name(conn, sf):
    from Working.channel_layout import channel_layout
    return {row["name"]: rid for rid, row in channel_layout(conn, sf)["channels"].items()}


def _rows(conn, census_id, **where):
    sql = "SELECT * FROM cross_cooccurrence WHERE census_id = ?"
    args = [census_id]
    for k, v in where.items():
        sql += f" AND {k} = ?"
        args.append(v)
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


# ── (g) the restricted lag search, and the old behaviour pinned ─────────────

def test_g_cross_correlation_peak_default_is_unchanged_and_max_lag_restricts():
    rng = np.random.default_rng(3)
    x = rng.standard_normal(400)
    y = np.roll(x, 120) + 0.01 * rng.standard_normal(400)          # y is x, 120 samples later
    assert xc.cross_correlation_peak(x, y) == xc.cross_correlation_peak(x, y, max_lag=None)
    lag, r = xc.cross_correlation_peak(x, y)
    assert lag == 120 and r > 0.6
    lag_r, r_r = xc.cross_correlation_peak(x, y, max_lag=50)
    assert abs(lag_r) <= 50 and abs(r_r) < abs(r)
    near = np.roll(x, 7)
    assert xc.cross_correlation_peak(x, near, max_lag=50)[0] == 7


def test_g_chance_null_takes_the_same_restriction():
    rng = np.random.default_rng(4)
    sib = rng.standard_normal(5000)
    x = sib[1000:1240]
    rule = xc.CrossChannelRule(null_k=20)
    a = xc.chance_null(x, sib, 1000, 1240, 1.0, rule=rule, seed=1)
    b = xc.chance_null(x, sib, 1000, 1240, 1.0, rule=rule, seed=1, max_lag=None)
    assert a["abs_r"] == b["abs_r"]
    c = xc.chance_null(x, sib, 1000, 1240, 1.0, rule=rule, seed=1, max_lag=10)
    assert c["starts"] == a["starts"] and all(rc <= ra + 1e-12 for rc, ra in zip(c["abs_r"], a["abs_r"]))


def test_shared_driver_is_a_constant_outside_the_library_bins():
    assert xc.SHARED_DRIVER == "shared_driver"
    assert xc.SHARED_DRIVER not in xc.BINS and xc.BINS == (xc.ARTIFACT, xc.PROPAGATION, xc.INDEPENDENT_RECURRENCE)


# ── (f) onset recovery ──────────────────────────────────────────────────────

def test_f_a_padded_start_recovers_the_steepest_fall_and_says_so(conn, tmp_path):
    onsets = syn.every(6, 7200.0)
    built = syn.build(conn, tmp_path, FOUR, 4, {0: [(t, k) for k, t in enumerate(onsets)]}, hours=16)
    got = cc.census_events(conn, FOUR)
    evs = [e for e in got["events"] if e["recording_id"] == built["recording_ids"][0]]
    assert len(evs) == 6
    for e, planted in zip(sorted(evs, key=lambda e: e["onset"]), built["onsets"][built["recording_ids"][0]]):
        assert e["onset_from"] == "steepest_fall"
        assert e["start"] == planted - syn.PAD_S                   # the stored start is the padded one …
        assert abs(e["onset"] - planted) <= 5                       # … and the onset is recovered within 5 s


def test_f_a_stored_label_wins_over_the_fall(conn, tmp_path):
    syn.build(conn, tmp_path, FOUR, 4, {0: [(3600.0, 1)]}, hours=8)
    det = conn.execute("SELECT id, start_idx FROM detections").fetchone()
    conn.execute("UPDATE detections SET meta_json = ? WHERE id = ?",
                 (json.dumps({"label": f"onset={int(det[1]) + 33};trough=0;sharp"}), det[0]))
    conn.commit()
    (e,) = cc.census_events(conn, FOUR)["events"]
    assert (e["onset"], e["onset_from"]) == (int(det[1]) + 33, "label")


# ── (i), (j): refusals ──────────────────────────────────────────────────────

def test_i_the_held_out_file_is_refused(conn, tmp_path):
    syn.build(conn, tmp_path, HELD_OUT_FILE, 16, {}, hours=1)
    with pytest.raises(PermissionError):
        cc.census_events(conn, HELD_OUT_FILE)
    with pytest.raises(PermissionError):
        cc.run_census(conn, HELD_OUT_FILE)


def test_j_a_detector_without_a_run_on_every_channel_is_refused_in_words(conn, tmp_path):
    syn.build(conn, tmp_path, M2A, 16, {}, hours=1, channels_with_run={0, 1}, variant="drop_detection_v5")
    status = cc.detector_status(conn, M2A, "drop_detection_v5")
    assert status["full"] is False
    assert status["reason"] == "drop_detection_v5 has a real run on 2 of 16 channels"
    with pytest.raises(cc.CensusRefused, match="drop_detection_v5 has a real run on 2 of 16 channels"):
        cc.census_events(conn, M2A, "drop_detection_v5")
    offered = {d["detector"]: d for d in cc.detectors_offered(conn, M2A)}
    assert offered["drop_detection_v5"]["full"] is False
    assert offered[cc.DEFAULT_DETECTOR]["full"] is False             # never run: listed with its reason
    assert offered[cc.DEFAULT_DETECTOR]["reason"] == "drop_detection_v1 has a real run on 0 of 16 channels"


# ── co-occurrence is pure ───────────────────────────────────────────────────

def test_co_occurrences_pairs_events_on_different_channels_within_the_ceiling():
    ev = [{"detection_id": 1, "recording_id": 10, "onset_s": 100.0},
          {"detection_id": 2, "recording_id": 11, "onset_s": 149.0},
          {"detection_id": 3, "recording_id": 11, "onset_s": 151.0},
          {"detection_id": 4, "recording_id": 10, "onset_s": 120.0},       # same channel as 1: never paired with it
          {"detection_id": 5, "recording_id": 12, "onset_s": 50.0}]
    got = {(a["detection_id"], b["detection_id"]) for a, b in cc.co_occurrences(ev, 50.0)}
    assert got == {(1, 2), (4, 2), (4, 3), (1, 5)}
    for a, b in cc.co_occurrences(ev, 50.0):
        assert a["recording_id"] < b["recording_id"]                     # one orientation: lag is b relative to a


# ── (a) common mode ─────────────────────────────────────────────────────────

def test_a_the_same_waveform_on_all_four_packs_is_a_common_mode_artifact_instant(conn, tmp_path):
    onsets = syn.every(3, 14400.0)
    plant = {ch: [(t, k) for k, t in enumerate(onsets)] for ch in range(16)}
    syn.build(conn, tmp_path, M2A, 16, plant, hours=20)
    out = cc.run_census(conn, M2A)
    s = out["summary"]
    assert s["bins"][xc.ARTIFACT] == 3 * 120 and s["bins"][xc.PROPAGATION] == 0
    assert len(s["breadth"]) == 3
    for inst in s["breadth"]:
        assert inst["breadth"] == 16 and inst["packs"] == ["A", "B", "C", "D"] and inst["common_mode"] is True
    rows = _rows(conn, out["census_id"])
    assert {r["bin"] for r in rows} == {xc.ARTIFACT} and all(r["common_mode"] == 1 for r in rows)
    assert any(r["cross_pack"] == 1 for r in rows) and any(r["cross_pack"] == 0 for r in rows)
    assert all(abs(r["lag_s"]) <= 1 and abs(r["r"]) >= 0.98 for r in rows)


# ── (b) propagation within a pack, with a timetable ─────────────────────────

def test_b_a_delayed_arrival_on_the_packs_next_channel_is_propagation_with_a_timetable(conn, tmp_path):
    onsets = syn.every(30, 7200.0)
    plant = {0: [(t, k) for k, t in enumerate(onsets)], 1: [(t + 12.0, k) for k, t in enumerate(onsets)]}
    syn.build(conn, tmp_path, M2B, 16, plant, hours=62)
    out = cc.run_census(conn, M2B)
    s = out["summary"]
    ids = _ids_by_name(conn, M2B)
    assert s["bins"][xc.PROPAGATION] == 30
    (pair,) = [p for p in s["pairs"] if (p["a"], p["b"]) == (ids["CH1_A1"], ids["CH2_A1"])]
    assert pair["n"] == 30 and pair["pack"] == "A"
    assert pair["p"] <= 0.01 and pair["q"] is not None                  # co-occurs far more than rotation gives
    t = pair["timetable"]
    assert t["testable"] is True and t["count"] == 30
    assert abs(t["L_s"] - 12.0) <= 1.0 and abs(t["median_lag_s"] - 12.0) <= 1.0 and t["mad_s"] <= 1.0
    assert t["p"] <= 0.01 and t["q"] is not None                         # beats its null after BH
    rows = _rows(conn, out["census_id"], bin=xc.PROPAGATION)
    assert all(abs(r["lag_s"] - 12.0) <= 1.0 and r["cross_pack"] == 0 for r in rows)
    assert all(json.loads(r["chance_json"])["beats"] for r in rows)


# ── (c) between packs: never propagation ────────────────────────────────────

def test_c_the_same_wave_between_packs_is_an_artifact_copy_or_a_shared_driver_never_propagation(conn, tmp_path):
    copies = syn.every(10, 7200.0)
    delayed = [t + 3600.0 for t in copies]
    plant = {0: [(t, k) for k, t in enumerate(copies)] + [(t, 100 + k) for k, t in enumerate(delayed)],
             4: [(t, k) for k, t in enumerate(copies)] + [(t + 12.0, 100 + k) for k, t in enumerate(delayed)]}
    syn.build(conn, tmp_path, M2C, 16, plant, hours=24)
    out = cc.run_census(conn, M2C)
    s = out["summary"]
    assert s["bins"][xc.PROPAGATION] == 0
    assert s["bins"][xc.ARTIFACT] == 10 and s["bins"][xc.SHARED_DRIVER] == 10
    rows = _rows(conn, out["census_id"])
    assert all(r["cross_pack"] == 1 for r in rows)
    for r in rows:
        if r["bin"] == xc.SHARED_DRIVER:
            assert abs(r["lag_s"] - 12.0) <= 1.0
    (sd,) = [d for d in s["shared_driver"] if d["packs"] == ["A", "B"]]
    assert sd["n"] == 10 and sd["p"] <= 0.01
    # two channels of two packs at one instant: it spans two packs, so it is common mode (D7)
    assert all(i["common_mode"] for i in s["breadth"]) and all(i["breadth"] == 2 for i in s["breadth"])


# ── (d) independent events ──────────────────────────────────────────────────

def test_d_independent_poisson_events_show_no_excess_and_no_timetable(conn, tmp_path):
    rng = np.random.default_rng(11)
    hours = 100
    plant = {}
    key = 0
    for ch in range(4):
        times = np.sort(rng.uniform(1800, hours * 3600 - 1800, size=30))
        plant[ch] = []
        for t in times:
            plant[ch].append((float(t), key))
            key += 1
    syn.build(conn, tmp_path, FOUR, 4, plant, hours=hours, seed=5)
    s = cc.run_census(conn, FOUR)["summary"]
    assert len(s["pairs"]) == 6
    for p in s["pairs"]:
        assert p["p"] > 0.05
        assert p["timetable"]["testable"] is False or p["timetable"]["p"] > 0.05
    assert s["overall"]["within_pack"]["p"] > 0.05


# ── (e) an unassigned layout ────────────────────────────────────────────────

def test_e_an_unassigned_recording_allows_propagation_and_says_layout_unknown(conn, tmp_path):
    onsets = syn.every(12, 7200.0)
    plant = {0: [(t, k) for k, t in enumerate(onsets)], 2: [(t + 12.0, k) for k, t in enumerate(onsets)]}
    syn.build(conn, tmp_path, FOUR, 4, plant, hours=26)
    out = cc.run_census(conn, FOUR)
    s = out["summary"]
    assert s["layout_known"] is False and s["layout_note"] == "packs not set — layout unknown"
    assert s["bins"][xc.PROPAGATION] == 12 and s["bins"][cc.PACK_UNKNOWN] == 0
    assert all(p["pack"] == "unassigned" for p in s["pairs"])


def test_a_pair_with_exactly_one_unassigned_channel_is_pack_unknown_never_propagation_or_shared_driver(conn, tmp_path):
    syn.build(conn, tmp_path, FOUR, 4, {}, hours=1)
    put_settings(conn, LAYOUT_PAGE, {pack_key("CO_census", "CH1"): "east"})
    from Working.channel_layout import channel_layout
    layout = channel_layout(conn, FOUR)
    ids = _ids_by_name(conn, FOUR)
    pair = {"rec_a_id": ids["CH1"], "rec_b_id": ids["CH2"], "lag_s": 12.0, "r": 0.95,
            "chance": {"beats": True}, "floor": {"ok": True}}
    assert cc.census_bin(pair, layout, xc.DEFAULT_RULE) == (cc.PACK_UNKNOWN, None)
    copy = dict(pair, lag_s=0.0, r=0.995)
    assert cc.census_bin(copy, layout, xc.DEFAULT_RULE) == (xc.ARTIFACT, None)   # a copy is an artifact on any packs
    both = dict(pair, rec_a_id=ids["CH2"], rec_b_id=ids["CH3"])
    assert cc.census_bin(both, layout, xc.DEFAULT_RULE) == (xc.PROPAGATION, False)


# ── (h) the hash, and stale ─────────────────────────────────────────────────

def test_h_the_hash_is_stable_and_the_census_goes_stale_when_a_run_the_rule_or_a_pack_changes(conn, tmp_path):
    syn.build(conn, tmp_path, M2A, 16, {0: [(3600.0, 1)], 1: [(3612.0, 1)]}, hours=20)
    first = cc.run_census(conn, M2A)
    assert cc.census_hash(cc.census_inputs(conn, M2A, cc.DEFAULT_DETECTOR)) == first["hash"]
    again = cc.run_census(conn, M2A)
    assert again["hash"] == first["hash"]
    assert conn.execute("SELECT COUNT(*) FROM cross_census").fetchone()[0] == 1   # one row per hash
    row = cc.latest_census(conn, M2A, cc.DEFAULT_DETECTOR)
    assert cc.is_stale(conn, row) == {"stale": False, "why": []}

    put_settings(conn, xc.SETTINGS_PAGE, {xc.SETTINGS_KEYS["min_abs_r"]: 0.6})
    st = cc.is_stale(conn, row)
    assert st["stale"] is True and any("rule" in w for w in st["why"])
    put_settings(conn, xc.SETTINGS_PAGE, {xc.SETTINGS_KEYS["min_abs_r"]: 0.5})
    assert cc.is_stale(conn, row)["stale"] is False

    put_settings(conn, LAYOUT_PAGE, {pack_key("M2_aug_census_a", "CH1_A1"): "B"})
    st = cc.is_stale(conn, row)
    assert st["stale"] is True and any("pack" in w for w in st["why"])


def test_h_a_changed_run_marks_the_census_stale(conn, tmp_path):
    built = syn.build(conn, tmp_path, M2A, 16, {0: [(3600.0, 1)], 1: [(3612.0, 1)]}, hours=20)
    cc.run_census(conn, M2A)
    row = cc.latest_census(conn, M2A, cc.DEFAULT_DETECTOR)
    rid = built["recording_ids"][3]
    conn.execute("UPDATE runs SET superseded_at = '2026-10-28T01:00:00' WHERE recording_id = ?", (rid,))
    syn.add_run(conn, built["session_id"], rid, built["n_samples"], [], finished_at="2026-10-28T02:00:00")
    conn.commit()
    st = cc.is_stale(conn, row)
    assert st["stale"] is True and any("run" in w for w in st["why"])


# ── (k) progress, storage, the null draws on disk ───────────────────────────

def test_k_the_census_reports_done_of_total_and_keeps_its_draws_under_the_step_cache(conn, tmp_path):
    onsets = syn.every(5, 7200.0)
    plant = {0: [(t, k) for k, t in enumerate(onsets)], 1: [(t + 12.0, k) for k, t in enumerate(onsets)]}
    syn.build(conn, tmp_path, M2B, 16, plant, hours=20)
    calls = []
    out = cc.run_census(conn, M2B, progress=lambda d, t, m: calls.append((d, t, m)))
    assert calls and all(t and 0 <= d <= t for d, t, _ in calls)
    assert calls[-1][0] == calls[-1][1]
    assert [d for d, _, _ in calls] == sorted(d for d, _, _ in calls)
    row = conn.execute("SELECT * FROM cross_census WHERE id = ?", (out["census_id"],)).fetchone()
    assert row["status"] == "done" and row["finished_at"]
    path = row["null_path"]
    assert os.path.isfile(path)
    assert os.path.commonpath([os.path.abspath(path), os.path.abspath(config.STEP_CACHE_ROOT)]) == \
        os.path.abspath(config.STEP_CACHE_ROOT)
    with np.load(path) as z:
        assert z["rotation"].shape[0] == cc.DEFAULT_CONSTANTS.rotation_k
    consts = json.loads(row["consts_json"])
    assert consts["onset_window_s"] == [-60.0, 180.0] and consts["timetable_delta_s"] == 2.0
    assert consts["q"] == 0.05 and consts["census_version"] == cc.CENSUS_VERSION


def test_the_census_can_be_cancelled_and_writes_nothing(conn, tmp_path):
    syn.build(conn, tmp_path, M2B, 16, {0: [(3600.0, 1)], 1: [(3612.0, 1)]}, hours=20)
    assert cc.run_census(conn, M2B, cancel=lambda: True) is None
    assert conn.execute("SELECT COUNT(*) FROM cross_census").fetchone()[0] == 0


def test_cooccurrence_rows_filter_by_bin_and_pair(conn, tmp_path):
    onsets = syn.every(5, 7200.0)
    plant = {0: [(t, k) for k, t in enumerate(onsets)], 1: [(t + 12.0, k) for k, t in enumerate(onsets)],
             4: [(t, k) for k, t in enumerate(onsets)]}
    syn.build(conn, tmp_path, M2B, 16, plant, hours=20)
    out = cc.run_census(conn, M2B)
    ids = _ids_by_name(conn, M2B)
    allr = cc.cooccurrence_rows(conn, out["census_id"])
    assert allr["total"] == len(_rows(conn, out["census_id"]))
    prop = cc.cooccurrence_rows(conn, out["census_id"], bin=xc.PROPAGATION)
    assert prop["total"] == 5 and {r["bin"] for r in prop["rows"]} == {xc.PROPAGATION}
    ab = cc.cooccurrence_rows(conn, out["census_id"], a=ids["CH1_A1"], b=ids["CH5_B1"])
    assert ab["total"] == 5 and all(r["cross_pack"] for r in ab["rows"])
    page = cc.cooccurrence_rows(conn, out["census_id"], limit=2, offset=1)
    assert len(page["rows"]) == 2


def test_the_rules_come_in_words_from_the_core():
    words = cc.rules_in_words(xc.DEFAULT_RULE, cc.DEFAULT_CONSTANTS)
    for b in (xc.ARTIFACT, xc.PROPAGATION, xc.INDEPENDENT_RECURRENCE, xc.SHARED_DRIVER, cc.PACK_UNKNOWN):
        assert words["bins"][b]
    assert "50" in words["co_occurrence"] and "60 s before" in words["window"]
    assert "Benjamini" in words["correction"]
    for k in ("excess", "timetable", "breadth", "shared_driver", "waveform"):
        assert words["nulls"][k]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

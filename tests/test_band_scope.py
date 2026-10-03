"""
test_band_scope.py
===================
fixup-Z: a band is a SCOPE, and Compare says what a human made of the
remainder (RQ4).

What it pins, in the core:

* **A band is a typed entry.** `{kind: "bandpass", low_hz, high_hz}` today, so
  `AC` can add `{kind: "wavelet", level}` without reshaping this work. A band
  with no kind is a bandpass (every band written before fixup-Z); a kind the
  core does not know is refused by name rather than silently filtered as a
  bandpass.
* **A band run records the recipe a hand-built chain would.** The researcher's
  hand route (2026-10-02) was: insert `preprocessing.bandpass` ahead of the
  template in Analyse — the inserted block arrives with the adapter's own
  defaults filled, `order 4` included — save, apply in Discovery. The band
  scope must produce byte-for-byte that recipe, or the two routes hash apart
  and the step cache, the run history and "what have I already tried" all see
  two different experiments.
* **The band list lives in Settings › Analysis defaults** (Q43), seeded with
  three log-spaced bands below Nyquist for a 1 Hz recording.
* **The surrogate is bandpassed the same way**: the null prepends
  `preprocessing.surrogate` AHEAD of the band step, so the phase-randomised
  signal is then filtered exactly as the real one was.
* **A Review queue can be over an exact set of detections** (`detection_ids`),
  beside fixup-L's `run_ids`: *Send only-B unjudged to Review* is a queue over
  exactly the regions only the band set found.
* **A union of span sets is de-duplicated by the matching rule**, and each
  region remembers which sets fired it — Compare's "the band that fired".
* **The verdict split is read from `adjudications`**, per region.
"""

import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working import run_groups  # noqa: E402
from Working.database import adjudications as adj  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database import vocabulary as v  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import compare as D  # noqa: E402
from Working.recipes import make_recipe, recipe_hash  # noqa: E402
from Working.review import queues as qs  # noqa: E402
from Working.review.queue_state import ReviewQueue  # noqa: E402

#: A small chain every adapter in it can run on a 200-sample synthetic channel.
#: Its params are partial on purpose: a built-in template's steps carry only
#: what they set, and the band scope must not "tidy" them into a different hash.
STEPS = [
    {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.3}},
]


def _bandpass_as_analyse_inserts_it(low_hz, high_hz):
    """What Analyse's *+ insert* puts in the chain: the block with the
    adapter's own defaults filled (`validateParams({})`), then the two cut-offs
    set on the page."""
    from Adapters.registry import discover_adapters, get_adapter

    discover_adapters()
    params = get_adapter("preprocessing.bandpass").validate_params({})
    params.update({"low_hz": low_hz, "high_hz": high_hz})
    return {"stage": "preprocessing", "algorithm": "bandpass", "params": params}


# ── a band is a typed entry ──────────────────────────────────────────────────

def test_a_band_target_carries_its_kind():
    recipe = make_recipe(1, STEPS, span=(0, 100), fan_out={
        "kind": "bands", "targets": [{"kind": "bandpass", "label": "slow", "low_hz": 0.01, "high_hz": 0.1}]})
    assert recipe["fan_out"]["targets"] == [
        {"kind": "bandpass", "label": "slow", "low_hz": 0.01, "high_hz": 0.1}]


def test_a_band_with_no_kind_is_a_bandpass():
    recipe = make_recipe(1, STEPS, span=(0, 100), fan_out={
        "kind": "bands", "targets": [{"label": "slow", "low_hz": 0.01, "high_hz": 0.1}]})
    assert recipe["fan_out"]["targets"][0]["kind"] == "bandpass"


def test_an_unknown_band_kind_is_refused_by_name():
    with pytest.raises(ValueError) as e:
        make_recipe(1, STEPS, span=(0, 100), fan_out={
            "kind": "bands", "targets": [{"kind": "wavelet", "level": 3}]})
    msg = str(e.value)
    assert "wavelet" in msg and "bandpass" in msg, msg


def test_a_band_is_refused_above_its_upper_edge_and_below_zero():
    for bad in ({"low_hz": 0.1, "high_hz": 0.1}, {"low_hz": 0.0, "high_hz": 0.1}):
        with pytest.raises(ValueError):
            run_groups.normalize_band(bad)


def test_a_bands_label_defaults_to_its_edges():
    assert run_groups.normalize_band({"low_hz": 0.01, "high_hz": 0.1})["label"] == "0.01–0.1 Hz"


# ── a band run records the recipe a hand-built chain would ──────────────────

def test_the_band_step_is_the_block_analyse_inserts():
    band = {"kind": "bandpass", "label": "mid", "low_hz": 0.01, "high_hz": 0.1}
    assert run_groups.band_step(band) == _bandpass_as_analyse_inserts_it(0.01, 0.1)


def test_a_band_recipe_hashes_the_same_as_the_hand_built_chain():
    """The 2026-10-02 hand route, through the core: the band scope's per-band
    recipe for one channel against `make_recipe` over the chain a researcher
    builds by inserting the block in Analyse. Same dict, same hash."""
    bands = [{"label": "slow", "low_hz": 0.001, "high_hz": 0.01},
             {"label": "mid", "low_hz": 0.01, "high_hz": 0.1}]
    banded = run_groups.band_recipes(7, STEPS, span=(0, 100), bands=bands)
    assert len(banded) == 2
    for recipe, band in zip(banded, bands):
        hand = make_recipe(7, [_bandpass_as_analyse_inserts_it(band["low_hz"], band["high_hz"])] + STEPS,
                           span=(0, 100))
        assert recipe == hand
        assert recipe_hash(recipe) == recipe_hash(hand)
        assert "fan_out" not in recipe


def test_band_recipes_are_the_core_materialisation():
    """No second implementation: the band scope's recipes are
    `materialize_target` over a recipe whose fan-out is the band list."""
    bands = [{"label": "mid", "low_hz": 0.01, "high_hz": 0.1}]
    fan = make_recipe(7, STEPS, span=(0, 100), fan_out={"kind": "bands", "targets": bands})
    assert run_groups.band_recipes(7, STEPS, span=(0, 100), bands=bands) == [
        run_groups.materialize_target(fan, 0)]


def test_the_surrogate_of_a_band_run_is_bandpassed_the_same_way():
    band = {"label": "mid", "low_hz": 0.01, "high_hz": 0.1}
    recipe = run_groups.band_recipes(7, STEPS, span=(0, 100), bands=[band])[0]
    null = run_groups.surrogate_recipe(recipe)
    algos = [f"{s['stage']}.{s['algorithm']}" for s in null["steps"]]
    assert algos[:2] == ["preprocessing.surrogate", "preprocessing.bandpass"]
    assert null["steps"][1] == recipe["steps"][0]


# ── the band list in Settings › Analysis defaults (Q43) ─────────────────────

def _conn():
    conn = init_db(":memory:")
    v.seed_vocabulary(conn)
    return conn


def test_the_band_list_defaults_to_three_log_spaced_bands_for_a_1_hz_recording():
    bands = run_groups.bands_from_settings(_conn())
    # Q43 seeds "~0.1–0.5 Hz"; 0.5 Hz is Nyquist at 1 Hz and a Butterworth edge
    # must lie strictly below it, so the third band stops at 0.45 Hz
    assert [(b["kind"], b["low_hz"], b["high_hz"]) for b in bands] == [
        ("bandpass", 0.001, 0.01), ("bandpass", 0.01, 0.1), ("bandpass", 0.1, 0.45)]
    assert all(b["label"] for b in bands)


def test_the_band_list_is_read_from_settings():
    from Working.registration.settings import put_settings

    conn = _conn()
    put_settings(conn, run_groups.BANDS_SETTINGS_PAGE, {run_groups.BANDS_SETTINGS_KEY: [
        {"label": "infra", "low_hz": 0.002, "high_hz": 0.02}]})
    assert run_groups.bands_from_settings(conn) == [
        {"kind": "bandpass", "label": "infra", "low_hz": 0.002, "high_hz": 0.02}]


def test_a_saved_band_list_that_cannot_filter_is_refused_loudly():
    from Working.registration.settings import put_settings

    conn = _conn()
    put_settings(conn, run_groups.BANDS_SETTINGS_PAGE, {run_groups.BANDS_SETTINGS_KEY: [
        {"label": "upside down", "low_hz": 0.2, "high_hz": 0.1}]})
    with pytest.raises(ValueError):
        run_groups.bands_from_settings(conn)


# ── a band fan-out still runs, end to end ───────────────────────────────────

def test_a_band_runs_stored_recipe_is_the_hand_built_one():
    tmpdir = tempfile.mkdtemp(prefix="fixup_z_")
    try:
        db_path = os.path.join(tmpdir, "t.sqlite")
        conn = init_db(db_path)
        npy = os.path.join(tmpdir, "CH0.npy")
        np.save(npy, np.random.default_rng(0).standard_normal(200))
        rid = q.insert_recording(conn, "fake.mat", 0, 1.0, 200, 0, npy)
        conn.close()
        recipe = run_groups.band_recipes(rid, STEPS, span=(0, 200),
                                         bands=[{"label": "mid", "low_hz": 0.05, "high_hz": 0.2}])[0]
        out = run_groups.run_paired_recipe(recipe, db_path=db_path, surrogate=True)
        conn = init_db(db_path)
        try:
            stored = R.load_recipe(conn, R.get_run(conn, out["run_id"])["config_id"])
            hand = make_recipe(rid, [_bandpass_as_analyse_inserts_it(0.05, 0.2)] + STEPS, span=(0, 200))
            hand["surrogate"] = True        # the paired-run control every Discovery run records
            assert recipe_hash(stored) == recipe_hash(hand)
            sur = R.load_recipe(conn, R.get_run(conn, out["surrogate_run_id"])["config_id"])
            assert [s["algorithm"] for s in sur["steps"]][:2] == ["surrogate", "bandpass"]
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── a queue over an exact set of detections ─────────────────────────────────

def _insert_detection(conn, rid, start_idx, end_idx, score=None):
    cid = conn.execute(
        "INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
        (f"h-{rid}-{start_idx}-{end_idx}", json.dumps({"steps": [{"stage": "detection", "algorithm": "x"}]}),
         "2026-01-01T00:00:00")).lastrowid
    run_id = conn.execute(
        "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
        "VALUES (?, ?, 0, 1000, '2026-01-01T00:00:00', 'completed')", (cid, rid)).lastrowid
    det = conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                       (run_id, start_idx, end_idx, score)).lastrowid
    conn.commit()
    return det


def test_queue_candidates_filters_by_an_exact_set_of_detection_ids():
    conn = _conn()
    rid = q.insert_recording(conn, "a.mat", 0, 1.0, 1000, 0, "a/CH0.npy")
    d1, d2, d3 = (_insert_detection(conn, rid, a, a + 50) for a in (0, 200, 400))
    assert [r["id"] for r in q.queue_candidates(conn, detection_ids=[d3, d1])] == [d1, d3]
    assert list(q.queue_candidates(conn, detection_ids=[])) == [], "an empty set is a queue over nothing"
    # composes with the status filter: a judged one drops out of the review flow
    adj.insert_adjudication(conn, d1, "interesting")
    assert [r["id"] for r in q.queue_candidates(conn, detection_ids=[d1, d2],
                                                adjudication_status="unadjudicated")] == [d2]


def test_a_review_queue_over_detection_ids_serves_exactly_those():
    conn = _conn()
    rid = q.insert_recording(conn, "a.mat", 0, 1.0, 1000, 0, "a/CH0.npy")
    d1, d2, d3 = (_insert_detection(conn, rid, a, a + 50) for a in (0, 200, 400))
    assert [c["id"] for c in ReviewQueue(conn, detection_ids=[d2]).candidates] == [d2]
    qid = qs.create_queue(conn, name="only B", source_kind="discovery-run",
                          filters={"detection_ids": [d3, d1]})
    assert [it["target_id"] for it in qs.queue_items(conn, qid)] == [d1, d3]
    assert qs.queue_counts(conn, qid) == {"total": 2, "judged": 0, "remaining": 2}
    # the same set in another order is the same open queue
    assert qs.find_open_queue(conn, source_kind="discovery-run",
                              filters={"detection_ids": [d1, d3]}) == qid


# ── a union of span sets, de-duplicated by the matching rule ────────────────

def test_a_union_keeps_one_region_per_event_and_names_every_set_that_fired_it():
    slow = [(100, 200, 11), (1000, 1100, 12)]
    mid = [(105, 205, 21), (3000, 3050, 22)]
    fast = [(102, 198, 31)]
    regions = D.union_span_sets([("slow", slow), ("mid", mid), ("fast", fast)])
    assert [(r["start"], r["end"]) for r in regions] == [(100, 200), (1000, 1100), (3000, 3050)]
    first = regions[0]
    assert first["sets"] == ["slow", "mid", "fast"]
    assert [m["id"] for m in first["members"]] == [11, 21, 31]
    assert first["id"] == 11, "the region is drawn as the first set's span"
    assert regions[1]["sets"] == ["slow"] and regions[2]["sets"] == ["mid"]


def test_a_union_does_not_merge_what_the_rule_calls_two_events():
    # IoU of (0, 100) and (90, 300) is 10 / 300: two events under §4.6
    regions = D.union_span_sets([("a", [(0, 100, 1)]), ("b", [(90, 300, 2)])])
    assert len(regions) == 2


# ── the verdict split, read live from `adjudications` ──────────────────────

def test_the_verdict_split_counts_regions_by_their_human_verdict():
    conn = _conn()
    rid = q.insert_recording(conn, "a.mat", 0, 1.0, 1000, 0, "a/CH0.npy")
    d = [_insert_detection(conn, rid, a, a + 50) for a in (0, 100, 200, 300, 400, 500)]
    adj.insert_adjudication(conn, d[0], "interesting")
    adj.insert_adjudication(conn, d[1], "seed")
    adj.insert_adjudication(conn, d[2], "not_interesting")
    adj.insert_adjudication(conn, d[3], "unsure")
    # one region made of two band detections, one of them judged
    regions = [[d[0]], [d[1]], [d[2]], [d[3]], [d[4], d[0]], [d[5]]]
    split = D.verdict_split(conn, regions)
    assert split == {"n": 6, "judged": 5, "accepted": 3, "rejected": 1, "other": 1, "unjudged": 1}
    assert D.verdict_split(conn, []) == {"n": 0, "judged": 0, "accepted": 0, "rejected": 0,
                                         "other": 0, "unjudged": 0}

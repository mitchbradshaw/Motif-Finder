"""
test_discovery_fanout.py
=========================
Spec §7.1/§7.5 — "each template becomes **one run across all channels in
scope**", and §7.4's *Discard run*.

`Working.discovery.fanout` plans that scope and hands it to
`Working.run_groups.fan_out_recipe` rather than writing a second fan-out. What
it adds is everything the plan needs before a run starts and after it ends:

* the **pre-flight**. `execute_recipe` checks the held-out lock per recipe,
  inside the fan-out — a scope containing a held-out channel would run the
  earlier targets, write their run rows, and only then raise. The plan refuses
  the target before anything starts, and says which and why.
* the **span check**. `materialize_target` carries one absolute span to every
  channel; a span valid on one channel can run past another's end, where
  `_load_signal` silently returns a short array rather than raising.
* the **route**. `webui.server.chain.estimate` never returns 'cluster' and
  reads no ceiling; `Working.hpc.job_export.route_recipe` does, but its
  constant is 900 s and Discovery's ceiling is 20 minutes (§9.6). The plan
  takes the ceiling as an argument and reports `unknown` honestly rather than
  calling an uncosted block free.
* the **per-channel status**, and the discard that writes no verdicts.

Headless: temp sqlite + real .npy files, so `execute_recipe` genuinely runs.
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database import queries as q
from Working.database import runs as R
from Working.database.schema import init_db
from Working.discovery import fanout

LOWPASS = [{"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.05}}]


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="discovery_fanout_")
    db_path = os.path.join(tmpdir, "test.sqlite")
    conn = init_db(db_path)
    lengths = {0: 400, 1: 400, 2: 400, 3: 120}        # channel 3 is short on purpose
    for ch, n in lengths.items():
        npy = os.path.join(tmpdir, f"CH{ch}.npy")
        np.save(npy, np.random.default_rng(ch).standard_normal(n))
        q.insert_recording(conn, "fake.mat", ch, 1.0, n, 0, npy)
    held = os.path.join(tmpdir, "held.npy")
    np.save(held, np.random.default_rng(99).standard_normal(400))
    q.insert_recording(conn, HELD_OUT_RECORDING_FILE, 0, 1.0, 400, 0, held)
    conn.close()
    yield db_path
    shutil.rmtree(tmpdir, ignore_errors=True)


def _ids(db_path, source_file="fake.mat"):
    conn = init_db(db_path)
    try:
        return [r["id"] for r in q.list_recordings(conn, source_file)]
    finally:
        conn.close()


def _held_id(db_path):
    return _ids(db_path, HELD_OUT_RECORDING_FILE)[0]


# ── the plan ────────────────────────────────────────────────────────────────

def test_the_plan_is_one_target_per_channel_and_bakes_them_into_the_recipe(db):
    conn = init_db(db)
    try:
        ids = _ids(db)[:3]
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 200))
        assert [t["recording_id"] for t in plan["targets"]] == ids
        assert plan["n_channels"] == 3
        assert plan["recipe"]["fan_out"] == {"kind": "channels", "targets": ids}
        assert plan["recipe"]["span"] == [0, 200]
        assert [t["channel"] for t in plan["targets"]] == [0, 1, 2]
        assert all(t["channel_name"] for t in plan["targets"])
    finally:
        conn.close()


def test_a_held_out_channel_is_refused_before_anything_runs(db):
    """The check inside execute_recipe is not a pre-flight: a fan-out whose
    targets include the held-out file runs the earlier targets first and only
    then raises. The plan drops it, names it, and leaves the rest runnable."""
    conn = init_db(db)
    try:
        ids = _ids(db)[:2] + [_held_id(db)]
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 200))
        assert [t["recording_id"] for t in plan["targets"]] == ids[:2]
        assert len(plan["refused"]) == 1
        assert plan["refused"][0]["recording_id"] == ids[2]
        assert HELD_OUT_RECORDING_FILE in plan["refused"][0]["reason"]
    finally:
        conn.close()


def test_a_scope_that_is_only_held_out_refuses_the_whole_plan(db):
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=[_held_id(db)], span=(0, 200))
        assert plan["targets"] == []
        assert plan["runnable"] is False
        assert HELD_OUT_RECORDING_FILE in plan["reason"]
    finally:
        conn.close()


def test_a_channel_shorter_than_the_span_is_refused_with_its_length(db):
    """materialize_target carries one absolute span to every channel and
    _load_signal returns a short array rather than raising — so a channel that
    cannot hold the section is refused here, with the numbers."""
    conn = init_db(db)
    try:
        ids = _ids(db)
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 200))
        refused = {r["recording_id"]: r["reason"] for r in plan["refused"]}
        short = ids[3]
        assert short in refused
        assert "120" in refused[short] and "200" in refused[short]
        assert [t["recording_id"] for t in plan["targets"]] == ids[:3]
    finally:
        conn.close()


def test_a_whole_channel_scope_uses_each_channels_own_length(db):
    """span=None means the whole channel, and channels of different lengths
    are then all valid — the span check must not fire."""
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=_ids(db), span=None)
        assert plan["refused"] == []
        assert len(plan["targets"]) == 4
        assert plan["targets"][3]["span"] == [0, 120]
    finally:
        conn.close()


# ── the route ───────────────────────────────────────────────────────────────

def test_an_uncosted_chain_routes_unknown_not_local(db):
    """`detection.lowpass` and `detection.seed_matches` declare no estimator.
    Reporting 0 s and 'local' for a 16-channel whole-recording sweep is the
    silent lie; the plan says `unknown` and names the steps that could not
    be costed."""
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=_ids(db)[:2], span=(0, 200))
        assert plan["route"] == "unknown"
        assert plan["estimate_s"] is None
        assert plan["uncosted"] == [0]
    finally:
        conn.close()


def test_a_costed_chain_under_the_ceiling_routes_local(db):
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=_ids(db)[:2], span=(0, 200),
                           measured_per_channel_s=1.0, ceiling_s=1200)
        assert plan["estimate_s"] == pytest.approx(2.0)
        assert plan["route"] == "local"
        assert plan["ceiling_s"] == 1200
    finally:
        conn.close()


def test_over_the_ceiling_routes_to_cluster(db):
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=_ids(db)[:3], span=(0, 200),
                           measured_per_channel_s=600.0, ceiling_s=1200)
        assert plan["estimate_s"] == pytest.approx(1800.0)
        assert plan["route"] == "cluster"
    finally:
        conn.close()


def test_the_ceiling_comes_from_settings_when_not_passed(db):
    from Working.registration.settings import put_settings
    conn = init_db(db)
    try:
        assert fanout.ceiling_s(conn) == 20 * 60
        put_settings(conn, "compute-hpc", {"limit.Discovery": 5})
        assert fanout.ceiling_s(conn) == 5 * 60
    finally:
        conn.close()


# ── running it ──────────────────────────────────────────────────────────────

def test_start_writes_one_run_group_and_one_run_per_channel(db):
    conn = init_db(db)
    try:
        ids = _ids(db)[:3]
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 200))
    finally:
        conn.close()
    seen = []
    out = fanout.start(plan, db_path=db, on_progress=lambda i, n, label: seen.append((i, n, label)))
    conn = init_db(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM run_groups").fetchone()[0] == 1
        rows = R.list_run_group_runs(conn, out["run_group_id"])
        assert [r["recording_id"] for r in rows] == ids
        assert all(r["status"] == "completed" for r in rows)
    finally:
        conn.close()
    assert [s[0] for s in seen] == [0, 1, 2]
    assert all(s[1] == 3 for s in seen)


def test_start_refuses_a_plan_that_is_not_runnable(db):
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=[_held_id(db)], span=(0, 200))
    finally:
        conn.close()
    with pytest.raises(ValueError, match="held out"):
        fanout.start(plan, db_path=db)


def test_group_status_reports_per_channel(db):
    conn = init_db(db)
    try:
        ids = _ids(db)[:2]
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 200))
    finally:
        conn.close()
    out = fanout.start(plan, db_path=db)
    conn = init_db(db)
    try:
        st = fanout.group_status(conn, out["run_group_id"])
        assert st["total"] == 2 and st["done"] == 2
        assert st["status"] == "completed"
        assert [c["channel"] for c in st["channels"]] == [0, 1]
        assert all(c["status"] == "completed" for c in st["channels"])
        assert all(c["detections"] == 0 for c in st["channels"])     # a lowpass writes none
    finally:
        conn.close()


def test_cancelling_stops_between_targets_and_reports_partial(db):
    conn = init_db(db)
    try:
        ids = _ids(db)[:3]
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 200))
    finally:
        conn.close()
    calls = {"n": 0}

    def should_cancel():
        return calls["n"] > 1

    def on_progress(i, n, label):
        calls["n"] = i + 1

    out = fanout.start(plan, db_path=db, on_progress=on_progress, should_cancel=should_cancel)
    assert out["cancelled"] is True
    assert len(out["runs"]) == 2, "cancelled between targets, after the second"
    conn = init_db(db)
    try:
        st = fanout.group_status(conn, out["run_group_id"])
        assert st["total"] == 2 and st["done"] == 2
        # the group row alone cannot know a third target was planned — that is
        # why `discovery_runs` stores the plan (schema, prompt 04)
    finally:
        conn.close()


# ── discard writes no verdicts ──────────────────────────────────────────────

def test_discard_marks_every_run_superseded_and_writes_no_verdicts(db):
    conn = init_db(db)
    try:
        ids = _ids(db)[:2]
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 200))
    finally:
        conn.close()
    out = fanout.start(plan, db_path=db)
    conn = init_db(db)
    try:
        n = fanout.supersede(conn, out["run_group_id"], reason="discarded in Discovery")
        assert n == 2
        rows = R.list_run_group_runs(conn, out["run_group_id"])
        assert all(r["superseded_at"] for r in rows)
        # §7.4: whole-run discard writes NO adjudications and NO annotations
        assert conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0
        # the detections themselves stay — the run is still reproducible
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE run_group_id = ?",
                            (out["run_group_id"],)).fetchone()[0] == 2
    finally:
        conn.close()


def test_a_superseded_group_says_so_in_its_status(db):
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=_ids(db)[:1], span=(0, 200))
    finally:
        conn.close()
    out = fanout.start(plan, db_path=db)
    conn = init_db(db)
    try:
        fanout.supersede(conn, out["run_group_id"])
        assert fanout.group_status(conn, out["run_group_id"])["status"] == "superseded"
    finally:
        conn.close()


# ── the preview on a sample (§7.1) ──────────────────────────────────────────

def test_preview_runs_the_chain_on_a_sample_and_extrapolates(db):
    """"*Preview on a 4 h sample* runs the selected templates on a sample and
    extrapolates hit count and cost before anything is committed" (§7.1). The
    measured seconds are what an uncosted block's estimate has to come from."""
    conn = init_db(db)
    try:
        ids = _ids(db)[:2]
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=ids, span=(0, 400))
    finally:
        conn.close()
    pv = fanout.preview(plan, db_path=db, sample_samples=100)
    assert pv["sample_samples"] == 100
    assert pv["measured_s"] > 0
    assert pv["per_channel_s"] == pytest.approx(pv["measured_s"] * 4, rel=0.001)
    assert pv["estimate_s"] == pytest.approx(pv["per_channel_s"] * 2, rel=0.001)
    assert pv["spans_in_sample"] == 0
    assert pv["extrapolated_spans"] == 0
    assert pv["channel"] is not None

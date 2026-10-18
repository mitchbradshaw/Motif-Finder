"""
test_ar_speed_core.py
=====================
AR, the speed pass — the core half (no FastAPI; runs under the conda pytest).

Review stepping was a whole-queue resolve three times per item, and the page
re-read every row after every verdict (5.3 s and 3 MB per verdict at 3,195
items on the real database, 2026-10-18). The detection resolver now keeps its
**structure** — which detections, in what order, at what absolute bounds, which
are rediscoveries of a human span — against a fingerprint of every row that
structure was read from, and lays the verdicts (which change on every key
press) over it fresh on each call.

The pins are counts, not wall-clock: how often the candidate query runs, and
whether the answer equals the uncached answer after every kind of change the
fingerprint has to see (a test per input: change it in place, expect the
fresh answer). A read added to the resolver and not to its fingerprint is a
queue served stale.
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as _queries  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.review import queues as Q  # noqa: E402

NOW = "2026-10-18T09:00:00+00:00"


def _db(tmp_path, n_runs=3, per_run=40):
    conn = init_db(str(tmp_path / "q.sqlite"))
    recs = [conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                         "VALUES ('A_concat_fs1.mat', ?, 1.0, 100000, 0, 'x.npy', 'mV')", (ch,)).lastrowid
            for ch in range(2)]
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('c', '{}', ?)",
                       (NOW,)).lastrowid
    gid = conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (NOW,)).lastrowid
    runs, dets = [], []
    for i in range(n_runs):
        rid = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                           "run_group_id) VALUES (?, ?, 0, 100000, ?, 'completed', ?)",
                           (cfg, recs[i % 2], NOW, gid)).lastrowid
        runs.append(rid)
        for k in range(per_run):
            a = 1000 + k * 700 + i * 13
            dets.append(conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                                     (rid, a, a + 60, 0.5 + k / 1000)).lastrowid)
    conn.commit()
    return conn, {"recs": recs, "runs": runs, "dets": dets, "group": gid, "cfg": cfg}


def _fresh(conn, qid, **kw):
    getattr(Q, "clear_resolver_cache", lambda: None)()
    return Q.queue_items(conn, qid, **kw)


def _queues(conn, info):
    """One queue of each detection shape: an exact detection set, a run set, a run group (source ref)."""
    return [
        Q.create_queue(conn, name="picked", source_kind="discovery-run",
                       filters={"detection_ids": info["dets"][5:70]}),
        Q.create_queue(conn, name="runs", source_kind="discovery-run", filters={"run_ids": info["runs"][:2]}),
        Q.create_queue(conn, name="group", source_kind="discovery-run", source_ref=str(info["group"])),
    ]


def test_a_repeated_read_does_not_re_resolve_the_queue(tmp_path, monkeypatch):
    conn, info = _db(tmp_path)
    qid = _queues(conn, info)[0]
    calls = {"n": 0}
    real = _queries.queue_candidates

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(_queries, "queue_candidates", counted)
    getattr(Q, "clear_resolver_cache", lambda: None)()
    first = Q.queue_items(conn, qid, include_judged=True)
    n_first = calls["n"]
    for _ in range(5):
        assert Q.queue_items(conn, qid, include_judged=True) == first
        Q.queue_counts(conn, qid)
    assert n_first == 1
    assert calls["n"] == 1, f"{calls['n'] - 1} candidate reads for five unchanged re-reads: the queue is re-resolved"


def _mutations(conn, info):
    """Every input the detection resolver reads, changed in place, one at a time."""
    recs, runs, dets = info["recs"], info["runs"], info["dets"]
    # a verdict (the overlay, never the structure)
    yield "verdict", lambda: conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) "
                                          "VALUES (?, 'interesting', ?)", (dets[6], NOW))
    yield "verdict edited", lambda: conn.execute("UPDATE adjudications SET verdict = 'artifact' WHERE detection_id = ?",
                                                 (dets[6],))
    # new detections on a run of the queue
    yield "detection appended", lambda: conn.execute(
        "INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 95000, 95040, 0.7)", (runs[0],))
    # a human span 30 samples off a detection: not the same event under the default rule, the same under a
    # looser one — so the rule change below changes the queue
    yield "near annotation", lambda: conn.execute(
        "INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
        "SELECT r.recording_id, d.start_idx + 30, d.end_idx + 30, 'interesting', 't', ? FROM detections d "
        "JOIN runs r ON r.id = d.run_id WHERE d.id = ?", (NOW, dets[10]))
    def loose_rule():
        for k, v in (("iou", "0.2"), ("onset", "1.0")):
            conn.execute("INSERT OR REPLACE INTO settings (page, key, value_json, updated_at) "
                         "VALUES ('analysis-defaults', ?, ?, ?)", (k, v, NOW))
    yield "rule", loose_rule
    # a human span that makes a detection a rediscovery, then edited, then soft-deleted
    yield "annotation", lambda: conn.execute(
        "INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
        "SELECT r.recording_id, d.start_idx, d.end_idx, 'interesting', 't', ? FROM detections d "
        "JOIN runs r ON r.id = d.run_id WHERE d.id = ?", (NOW, dets[8]))
    yield "annotation verdict edited", lambda: conn.execute(
        "UPDATE annotations SET verdict = 'not_interesting' WHERE id = (SELECT MAX(id) FROM annotations)")
    yield "annotation moved", lambda: conn.execute(
        "UPDATE annotations SET start_idx = start_idx + 300, end_idx = end_idx + 300 "
        "WHERE id = (SELECT MAX(id) FROM annotations)")
    yield "annotation deleted", lambda: conn.execute(
        "UPDATE annotations SET deleted_at = ? WHERE id = (SELECT MAX(id) FROM annotations)", (NOW,))
    # a discarded run, then restored
    yield "superseded", lambda: conn.execute("UPDATE runs SET superseded_at = ? WHERE id = ?", (NOW, runs[1]))
    yield "restored", lambda: conn.execute("UPDATE runs SET superseded_at = NULL WHERE id = ?", (runs[1],))
    # a run turned into a paired surrogate (its spans stop being candidates)
    yield "surrogate", lambda: conn.execute("UPDATE runs SET surrogate_of_run_id = ? WHERE id = ?", (runs[0], runs[2]))
    # a legacy span-relative offset
    yield "span_start", lambda: conn.execute("UPDATE runs SET span_start = 50000 WHERE id = ?", (runs[0],))
    # a run joining the group late (fanout sets run_group_id after the run's detections are written)
    def late_join():
        rid = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                           "VALUES (?, ?, 0, 100000, ?, 'completed')", (info["cfg"], recs[0], NOW)).lastrowid
        conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 90000, 90050, 0.9)", (rid,))
        conn.commit()
        conn.execute("UPDATE runs SET run_group_id = ? WHERE id = ?", (info["group"], rid))
    yield "late group join", late_join
    # a window run of a stitched run (a run group queue drops window parts)
    yield "window part", lambda: conn.execute(
        "INSERT INTO stitched_windows (run_id, window_index, window_run_id, span_start, span_end, core_start, "
        "core_end) VALUES (?, 0, ?, 0, 1, 0, 1)", (runs[0], runs[1]))
    # the channel a recording row names
    yield "channel", lambda: conn.execute("UPDATE recordings SET channel = 7 WHERE id = ?", (recs[1],))
    # the queue's own descriptor
    yield "cap", lambda: conn.execute("UPDATE review_queues SET cap = 9")
    yield "filters", lambda: conn.execute("UPDATE review_queues SET filters_json = ? WHERE name = 'picked'",
                                          (json.dumps({"detection_ids": dets[:30]}),))
    yield "blind", lambda: conn.execute("UPDATE review_queues SET blind = 1")


def test_the_cached_resolver_answers_exactly_what_a_fresh_resolve_does(tmp_path):
    conn, info = _db(tmp_path)
    qids = _queues(conn, info)
    held = {info["recs"][1]}
    for name, change in _mutations(conn, info):
        for qid in qids:                      # warm the cache on the state before the change
            Q.queue_items(conn, qid, include_judged=True, include_prior_judged=True)
        change()
        conn.commit()
        views = ({}, {"include_judged": True}, {"include_judged": True, "include_prior_judged": True},
                 {"include_judged": True, "exclude_recording_ids": held})
        # every cached answer first (a fresh resolve clears the cache for every queue), then every fresh one
        got = {(qid, i): Q.queue_items(conn, qid, **kw) for qid in qids for i, kw in enumerate(views)}
        got_counts = {qid: Q.queue_counts(conn, qid, exclude_recording_ids=held) for qid in qids}
        for (qid, i), items in got.items():
            assert items == _fresh(conn, qid, **views[i]), (
                f"after '{name}', queue {qid} {views[i]}: the cached resolve served a stale queue")
        for qid in qids:
            assert got_counts[qid] == Q.queue_counts(conn, qid, exclude_recording_ids=held)


def test_two_databases_never_share_a_remembered_queue(tmp_path):
    """Queue 1 of one database is not queue 1 of another, even laid out identically (the fingerprint reads
    detections by id range, so only the database's identity tells them apart)."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a, ia = _db(tmp_path / "a")
    b, ib = _db(tmp_path / "b")
    b.execute("UPDATE detections SET score = 0.01")
    b.commit()
    qa, qb = _queues(a, ia)[0], _queues(b, ib)[0]
    assert qa == qb
    sa = {it["score"] for it in Q.queue_items(a, qa)}
    sb = {it["score"] for it in Q.queue_items(b, qb)}
    assert sb == {0.01} and 0.01 not in sa


def test_snapshot_agrees_with_the_three_reads_it_replaces(tmp_path):
    """`queue_snapshot` is what one item read uses: the served list (ranks, counts) and the deep-link list,
    from ONE resolve. Each must equal the read it replaces."""
    conn, info = _db(tmp_path)
    qid = _queues(conn, info)[1]
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                 "SELECT r.recording_id, d.start_idx, d.end_idx, 'interesting', 't', ? FROM detections d "
                 "JOIN runs r ON r.id = d.run_id WHERE d.id = ?", (NOW, info["dets"][3]))
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'seed', ?)",
                 (info["dets"][4], NOW))
    conn.execute("UPDATE review_queues SET cap = 50 WHERE id = ?", (qid,))
    conn.commit()
    for held in (set(), {info["recs"][1]}):
        snap = Q.queue_snapshot(conn, qid, exclude_recording_ids=held)
        assert snap["items"] == Q.queue_items(conn, qid, include_judged=True, exclude_recording_ids=held)
        assert snap["deep"] == Q.queue_items(conn, qid, include_judged=True, include_prior_judged=True)
        assert snap["counts"] == Q.queue_counts(conn, qid, exclude_recording_ids=held)


def test_item_view_agrees_with_the_snapshot_for_every_item(tmp_path):
    """`item_view` answers one item read from the structure without building every item; for every target
    (served, rediscovered, beyond the cap, held out, absent) it must say what the snapshot says."""
    conn, info = _db(tmp_path)
    qids = _queues(conn, info)
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                 "SELECT r.recording_id, d.start_idx, d.end_idx, 'interesting', 't', ? FROM detections d "
                 "JOIN runs r ON r.id = d.run_id WHERE d.id IN (?, ?)", (NOW, info["dets"][7], info["dets"][45]))
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'seed', ?)",
                 (info["dets"][9], NOW))
    conn.execute("UPDATE review_queues SET cap = 40 WHERE id = ?", (qids[1],))
    conn.commit()
    for qid in qids:
        for held in (set(), {info["recs"][1]}):
            snap = Q.queue_snapshot(conn, qid, exclude_recording_ids=held)
            for tid in [str(d) for d in info["dets"]] + ["0", "nonsense"]:
                v = Q.item_view(conn, qid, tid, exclude_recording_ids=held)
                deep = next((it for it in snap["deep"] if str(it["target_id"]) == tid), None)
                rank = next((i + 1 for i, it in enumerate(snap["items"]) if str(it["target_id"]) == tid), None)
                assert (v["item"], v["rank"], v["counts"]) == (deep, rank, snap["counts"]), (qid, held, tid)


def test_pace_reads_the_tail_and_agrees_with_the_whole_ledger(tmp_path):
    conn, info = _db(tmp_path)
    qid = _queues(conn, info)[0]
    rows = []
    for i in range(300):
        undone = NOW if i % 17 == 0 else None
        action = "undo" if i % 23 == 0 else "verdict"
        ts = "garbage" if i == 290 else f"2026-10-18T10:{i // 60:02d}:{i % 60:02d}+00:00"
        rows.append((qid, action, json.dumps([1, 2] if i % 5 == 0 else [1]), ts, undone))
    conn.executemany("INSERT INTO review_audit (queue_id, action, target_ids, created_at, undone_at) "
                     "VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()

    def whole():
        r = conn.execute("SELECT target_ids, created_at FROM review_audit WHERE queue_id = ? AND undone_at IS NULL "
                         "AND action <> 'undo' ORDER BY id", (qid,)).fetchall()
        per, prev = [], Q._parse_ts(r[0]["created_at"])
        for row in r[1:]:
            t = Q._parse_ts(row["created_at"])
            if prev is None or t is None:
                prev = t
                continue
            per.append(max(0.0, (t - prev).total_seconds()) / Q._n_targets(row["target_ids"]))
            prev = t
        return round(Q._median(per[-Q.PACE_WINDOW:]), 2) if per else None

    assert Q.queue_pace_s(conn, qid) == whole()
    seen = []
    conn.set_trace_callback(seen.append)
    Q.queue_pace_s(conn, qid)
    conn.set_trace_callback(None)
    assert any("LIMIT" in s.upper() for s in seen), "the pace reads the whole ledger to use its last 20 gestures"

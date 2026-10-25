"""
test_perf_scoring_reads.py
==========================
The reads behind Discovery's template picker and the header's "N need you"
must not grow with (detections x labels).

Measured 2026-10-17 on a copy of the real database: `GET /api/discovery/templates`
took 2+ minutes, 117 s of it scoring `deconvolved_troughs` (two runs, 17k and
42k detections, ~800 labels per channel). Profiling put all of it in
`match_span_sets`, which tried **every** (candidate, reference) pair — 15.9 M
`match_quality` calls for the 17k run — and a little in the "label with no
detection" query, whose NOT EXISTS walked every detection of the run for each
label. The long read held SQLite's lock, so job writes behind it failed with
"database is locked", and the picker timed out.

The pins here are counts, not wall-clock: how many pairs the matcher looks at,
and how many SQLite VM steps the query takes as the detection count grows. A
wall-clock budget fails under load for reasons that are not the code
(`docs`: the Trains budgets). The results must not change: the pruned matcher is
checked against the exhaustive one on random inputs, edge cases included.
"""

import math
import os
import random
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q
from Working.database import runs as run_db
from Working.database.schema import init_db
from Working.discovery import matching


# ── the matcher ──────────────────────────────────────────────────────────────

def _exhaustive(candidates, references, rule):
    """The pairing by definition: every pair tried, best IoU taken first —
    what `match_span_sets` did before it was pruned."""
    base = matching.normalise_rule(rule)
    scored = []
    for i, c in enumerate(candidates):
        for j, r in enumerate(references):
            qy = matching.match_quality(c, r, rule=base)
            if qy["ok"]:
                scored.append((-qy["iou"], i, j, qy))
    scored.sort(key=lambda s: (s[0], s[1], s[2]))
    taken_c, taken_r, pairs = set(), set(), []
    for _, i, j, qy in scored:
        if i in taken_c or j in taken_r:
            continue
        taken_c.add(i)
        taken_r.add(j)
        pairs.append({"candidate": i, "reference": j, "iou": qy["iou"], "onset_gap": qy["onset_gap"]})
    pairs.sort(key=lambda p: p["candidate"])
    return {"pairs": pairs,
            "candidate_only": [i for i in range(len(candidates)) if i not in taken_c],
            "reference_only": [j for j in range(len(references)) if j not in taken_r],
            "rule": base}


def _count_quality_calls(monkeypatch):
    calls = {"n": 0}
    real = matching.match_quality

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(matching, "match_quality", counted)
    return calls


def test_match_span_sets_does_not_try_every_pair(monkeypatch):
    """400 events against 400 labels, none near most of the others: the
    matcher must look at the pairs that could match, not all 160,000."""
    cands = [(i * 1000, i * 1000 + 100) for i in range(400)]
    refs = [(i * 1000 + 10, i * 1000 + 110) for i in range(400)]
    calls = _count_quality_calls(monkeypatch)
    out = matching.match_span_sets(cands, refs)
    assert len(out["pairs"]) == 400
    assert calls["n"] <= 10 * (len(cands) + len(refs)), (
        f"{calls['n']} pair checks for {len(cands)} x {len(refs)} spans: quadratic")


def _random_spans(rng, n, *, span=5000, max_w=400):
    out = []
    for _ in range(n):
        a = rng.randrange(0, span)
        w = rng.choice([0, 1, 2, rng.randrange(0, max_w), rng.randrange(0, max_w), max_w * 3])
        out.append((a, a + w))
    return out


@pytest.mark.parametrize("rule", [
    None,
    {"iou": 0.0, "onset": 0.25},       # IoU 0 accepts disjoint pairs: only the onset bounds them
    {"iou": 0.0, "onset": 10.0},
    {"iou": 0.3, "onset": 0.0},        # zero tolerance: same onset only
    {"iou": 1.0, "onset": 0.1},
    {"iou": 0.5, "onset": 3.3},        # a tolerance that is not a whole number of samples
])
@pytest.mark.parametrize("seed", range(6))
def test_the_pruned_pairing_is_the_exhaustive_pairing(rule, seed):
    rng = random.Random(seed)
    cands = _random_spans(rng, rng.randrange(0, 120))
    refs = _random_spans(rng, rng.randrange(0, 120))
    # duplicates and identical onsets, where the tie-breaks decide
    if cands and refs:
        cands += cands[:5]
        refs += [cands[0], cands[-1]]
    assert matching.match_span_sets(cands, refs, rule=rule) == _exhaustive(cands, refs, rule)


# ── the "label with no detection" query ─────────────────────────────────────

def _vm_steps(conn, fn):
    steps = {"n": 0}

    def tick():
        steps["n"] += 1
        return 0

    conn.set_progress_handler(tick, 100)
    try:
        fn()
    finally:
        conn.set_progress_handler(None, 0)
    return steps["n"] * 100


def _db_with(n_detections, n_labels=200):
    conn = init_db(":memory:")
    rec = q.insert_recording(conn, "perf.mat", 0, 1.0, 10_000_000, 0, "perf_CH0.npy")
    config_id, _ = run_db.get_or_create_config(
        conn, {"steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]})
    span = n_detections * 100
    run_id = run_db.insert_run(conn, config_id, rec, 0, span, status="completed")
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                     [(run_id, i * 100, i * 100 + 40, 0.5) for i in range(n_detections)])
    # labels spread over the span: half on a detection, half in the gaps
    stride = span // n_labels
    for k in range(n_labels):
        a = k * stride + (0 if k % 2 else 50)
        q.insert_annotation(conn, rec, a, a + 30, "interesting", "excel_catalog")
    conn.commit()
    return conn, rec, run_id


def test_labels_without_a_detection_do_not_walk_every_detection_per_label():
    """Four times the detections under the same 200 labels: the query's work
    may grow with the detections once (an index walk), not once per label."""
    steps = []
    for n in (2000, 8000):
        conn, rec, run_id = _db_with(n)
        try:
            rows = []
            steps.append(_vm_steps(conn, lambda: rows.extend(q.divergence_annotations_without_detection(
                conn, rec, run_ids=[run_id], verdicts=("interesting", "seed")))))
            assert len(rows) == 100            # the gap labels, and only those
        finally:
            conn.close()
    # walking every detection per label costs ~5 steps x 200 labels for each
    # added detection (~1000; 1052 before the fix); one pass over them, ~10
    per_detection = (steps[1] - steps[0]) / 6000.0
    assert per_detection < 50, (f"VM steps {steps[0]} -> {steps[1]} for 4x the detections: "
                                f"{per_detection:.0f} per added detection, so it grows per label")


# ── the template picker's last score, remembered while its inputs stand ─────
#
# Even linear, scoring deconvolved_troughs' 60k detections takes ~2 s, and the
# picker scores every template on every open. `score_runs_cached` answers from
# memory while nothing the score reads has changed, and rescores the moment
# anything has: the cases below each change one input in place (no new row id
# to give it away) and expect the fresh figure.

from Working.database import adjudications as adj_db
from Working.discovery import scoreboard as SB
from Working.registration.settings import put_settings

_STEPS = {"steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]}
_BEFORE = "2026-09-01T00:00:00"
_AFTER = "2026-09-20T00:00:00"


def _build_scored(conn):
    """The `scored` fixture's content, on any connection (in memory here; a file for the corpus-map worker's
    tests, which a child process must be able to open — corpus-map-off-the-request)."""
    rec = q.insert_recording(conn, "cache.mat", 0, 1.0, 100_000, 0, "cache_CH0.npy")
    other = q.insert_recording(conn, "cache.mat", 1, 1.0, 100_000, 0, "cache_CH1.npy")
    config_id, _ = run_db.get_or_create_config(conn, _STEPS)
    runs = [run_db.insert_run(conn, config_id, r, 0, 20_000, status="completed", started_at=_AFTER)
            for r in (rec, other)]
    dets = {}
    anns = {}
    for r, run in zip((rec, other), runs):
        for k in range(20):
            a = k * 1000
            q.insert_annotation(conn, r, a, a + 600, "interesting" if k % 3 else "not_interesting",
                                q.SOURCE_IMPORTED_10MIN, created_at=_BEFORE)
            q.insert_reviewed_span(conn, r, a, a + 600, q.SOURCE_IMPORTED_10MIN, reviewed_at=_BEFORE)
            dets[(r, k)] = run_db.insert_detection(conn, run, a + 100, a + 300, score=0.5)
        anns[r] = q.insert_annotation(conn, r, 15_000, 15_200, "interesting", "excel_catalog", created_at=_BEFORE)
    old = run_db.insert_run(conn, config_id, rec, 0, 20_000, status="completed", started_at=_BEFORE)
    old_det = run_db.insert_detection(conn, old, 5100, 5300, score=0.5)
    conn.commit()
    return {"conn": conn, "rec": rec, "runs": runs, "dets": dets, "anns": anns, "config": config_id,
            "old_det": old_det}


@pytest.fixture
def scored():
    conn = init_db(":memory:")
    s = _build_scored(conn)
    SB.clear_score_cache()
    yield s
    conn.close()


def _count_scores(monkeypatch):
    calls = {"n": 0}
    real = SB.channel_score

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(SB, "channel_score", counted)
    return calls


def test_an_unchanged_score_is_not_recomputed(scored, monkeypatch):
    conn, runs = scored["conn"], scored["runs"]
    first = SB.score_runs_cached(conn, runs)
    assert first == SB.score_runs(conn, runs)
    calls = _count_scores(monkeypatch)
    assert SB.score_runs_cached(conn, runs) == first
    assert calls["n"] == 0


def test_a_cached_score_is_a_copy_the_caller_cannot_spoil(scored):
    conn, runs = scored["conn"], scored["runs"]
    SB.score_runs_cached(conn, runs)["total"]["found"] = -1
    assert SB.score_runs_cached(conn, runs)["total"]["found"] == SB.score_runs(conn, runs)["total"]["found"]


def _verdict_in_place(s):
    aid = s["conn"].execute("SELECT id FROM annotations WHERE recording_id = ? AND start_idx = 3000",
                            (s["rec"],)).fetchone()[0]
    s["conn"].execute("UPDATE annotations SET verdict = 'interesting' WHERE id = ?", (aid,))


def _soft_delete(s):
    s["conn"].execute("UPDATE annotations SET deleted_at = ? WHERE recording_id = ? AND start_idx = 1000",
                      (_AFTER, s["rec"]))


def _new_annotation(s):
    q.insert_annotation(s["conn"], s["rec"], 19_000, 19_600, "interesting", q.SOURCE_IMPORTED_10MIN,
                        created_at=_BEFORE)


def _span_moved(s):
    s["conn"].execute("UPDATE annotations SET start_idx = 2250 WHERE recording_id = ? AND start_idx = 2000",
                      (s["rec"],))


def _adjudicated(s):
    adj_db.insert_adjudication(s["conn"], s["dets"][(s["rec"], 4)], "not_interesting")


def _adjudication_changed(s):
    adj_db.insert_adjudication(s["conn"], s["dets"][(s["rec"], 4)], "not_interesting")
    SB.score_runs_cached(s["conn"], s["runs"])
    s["conn"].execute("UPDATE adjudications SET verdict = 'interesting' WHERE detection_id = ?",
                      (s["dets"][(s["rec"], 4)],))


def _prior_run_adjudicated(s):
    adj_db.insert_adjudication(s["conn"], s["old_det"], "interesting")
    # given before the scored run started, so its detection there was already judged
    s["conn"].execute("UPDATE adjudications SET created_at = ? WHERE detection_id = ?", (_BEFORE, s["old_det"]))


def _reviewed(s):
    s["conn"].execute("UPDATE reviewed_spans SET end_idx = 900 WHERE recording_id = ? AND start_idx = 0",
                      (s["rec"],))


def _rule_changed(s):
    put_settings(s["conn"], "analysis-defaults", {"containment": "whole"})


def _detection_added(s):
    run_db.insert_detection(s["conn"], s["runs"][0], 9100, 9200, score=0.5)


def _detection_removed(s):
    # detections are append-only, so the id range is the set; dropping the newest moves it
    s["conn"].execute("DELETE FROM detections WHERE id = ?", (s["dets"][(s["rec"], 19)],))


def _run_status(s):
    s["conn"].execute("UPDATE runs SET status = 'running' WHERE id = ?", (s["runs"][0],))


def _null_drawn(s):
    null = run_db.insert_run(s["conn"], s["config"], s["rec"], 0, 20_000, status="completed", started_at=_AFTER)
    run_db.insert_detection(s["conn"], null, 100, 200, score=0.5)
    run_db.update_run(s["conn"], null, surrogate_of_run_id=s["runs"][0])


def _fs_changed(s):
    s["conn"].execute("UPDATE recordings SET fs = 2.0 WHERE id = ?", (s["rec"],))


@pytest.mark.parametrize("change", [
    _verdict_in_place, _soft_delete, _new_annotation, _span_moved, _adjudicated, _adjudication_changed,
    _prior_run_adjudicated, _reviewed, _rule_changed, _detection_added, _detection_removed, _run_status,
    _null_drawn, _fs_changed,
], ids=lambda f: f.__name__.strip("_"))
def test_any_change_to_what_the_score_reads_rescores(scored, change):
    conn, runs = scored["conn"], scored["runs"]
    before = SB.score_runs_cached(conn, runs)
    change(scored)
    conn.commit()
    fresh = SB.score_runs(conn, runs)
    assert fresh != before, "the change did not move the score, so this case proves nothing"
    assert SB.score_runs_cached(conn, runs) == fresh


# ── the picker's glyph strips: one package walk, not one per stage ──────────

def test_a_registered_block_is_looked_up_without_walking_the_package_again(monkeypatch):
    """`discover_adapters()` lists the package directory every call; the picker
    called it for every stage of every template (267 walks, ~1 s, per open)."""
    from Adapters import registry
    from Working.discovery import compare

    registry.discover_adapters()
    walks = {"n": 0}
    real = registry.discover_adapters

    def counted():
        walks["n"] += 1
        return real()

    monkeypatch.setattr(registry, "discover_adapters", counted)
    name = registry.list_adapters()[0].name
    for _ in range(5):
        assert compare._spec_for(name) is registry.get_adapter(name)
        assert registry.get_or_discover(name) is registry.get_adapter(name)
    assert walks["n"] == 0
    # an unknown name still walks once, and still answers None / KeyError as before
    assert compare._spec_for("detection.no_such_block") is None
    with pytest.raises(KeyError):
        registry.get_or_discover("detection.no_such_block")
    assert walks["n"] == 2


# ── the corpus map: the same rule over whole channels ──────────────────────
#
# `GET /api/corpus/<rec>/coverage` pools every run on every channel through the
# divergence; on M2_aug (16 channels, 472 runs on one of them) it took ~10 s on
# every Corpus open and every home-page load, and was the request that kept
# the home page from reaching network-idle in the smoke walk.

def _corpus():
    from webui.server import corpus
    getattr(corpus, "reset_coverage_worker", lambda: None)()
    corpus._COVERAGE_CACHE.clear()
    return corpus


def _without_timing(cov):
    return {k: v for k, v in cov.items() if k != "compute_ms"}


def test_an_unchanged_corpus_map_is_not_recomputed(scored, monkeypatch):
    corpus = _corpus()
    conn = scored["conn"]
    first = corpus.coverage(conn, "cache.mat", bins=10)
    calls = {"n": 0}
    real = corpus._coverage

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(corpus, "_coverage", counted)
    again = corpus.coverage(conn, "cache.mat", bins=10)
    assert calls["n"] == 0
    assert _without_timing(again) == _without_timing(first)
    # a different question is a different entry
    corpus.coverage(conn, "cache.mat", bins=10, verdicts=("interesting",))
    corpus.coverage(conn, "cache.mat", bins=10, run_ids=[scored["runs"][0]])
    assert calls["n"] == 2


def test_two_concurrent_reads_of_one_corpus_map_compute_it_once(monkeypatch):
    """ux-1018: the startup warm and a page's request for the same map used to compute it twice, side by side —
    on 2026-10-18 the warm took 462 s for 17 files while the home page recomputed the M2_aug map it was already
    building. A miss takes a per-key lock: the second reader waits and answers from the entry the first wrote."""
    import threading
    import time

    corpus = _corpus()
    calls = {"n": 0}

    def slow(conn, source_file, **kw):
        calls["n"] += 1
        time.sleep(0.3)
        return {"source_file": source_file, "rows": []}

    monkeypatch.setattr(corpus, "_coverage", slow)
    monkeypatch.setattr(corpus.q, "list_recordings", lambda conn, source_file=None: [{"id": 1}])
    monkeypatch.setattr(corpus.SB, "channels_fingerprint", lambda conn, ids, memo=None, **kw: "fp")
    out = []
    threads = [threading.Thread(target=lambda: out.append(corpus.coverage(None, "cache.mat", bins=10))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls["n"] == 1, f"the map was computed {calls['n']} times for two concurrent readers"
    assert len(out) == 2 and all(o["source_file"] == "cache.mat" for o in out)
    # a different key is its own flight
    corpus.coverage(None, "other.mat", bins=10)
    assert calls["n"] == 2


def _second_channel_verdict(s):
    other = s["conn"].execute("SELECT recording_id FROM runs WHERE id = ?", (s["runs"][1],)).fetchone()[0]
    s["conn"].execute("UPDATE annotations SET verdict = 'not_interesting' WHERE recording_id = ? AND start_idx = 4000",
                      (other,))


def _new_run_on_the_channel(s):
    run = run_db.insert_run(s["conn"], s["config"], s["rec"], 0, 20_000, status="completed", started_at=_AFTER)
    run_db.insert_detection(s["conn"], run, 12_100, 12_300, score=0.5)


def _run_stitched_into_another(s):
    # round A_2's windowed application: once a run is a stitched run's window, a pooled read drops it.
    # Only the stitched_windows row changes (no new run), so this pins that the fingerprint reads it.
    s["conn"].execute("INSERT INTO stitched_windows (run_id, window_index, window_run_id, span_start, span_end, "
                      "core_start, core_end) VALUES (?, 0, ?, 0, 20000, 0, 20000)", (s["runs"][1], s["runs"][0]))


@pytest.mark.parametrize("change", [
    _verdict_in_place, _soft_delete, _new_annotation, _adjudicated, _rule_changed,
    _detection_added, _second_channel_verdict, _new_run_on_the_channel, _run_stitched_into_another,
], ids=lambda f: f.__name__.strip("_"))
def test_any_change_on_the_channels_redraws_the_corpus_map(scored_file, change):
    """A change on the channels redraws the map. A library call (no `db_path`) computes in place, as before. The
    route's read (`db_path` given: corpus-map-off-the-request) never computes: right after the change it answers the
    LAST map, marked `stale: true` with `stale_since`, and once the worker has finished the next read is the fresh
    map, with no stale marker on it. A stale answer without its marker would fail here."""
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    read = lambda: corpus.coverage(conn, "cache.mat", bins=10, db_path=path)   # noqa: E731
    first = read()
    assert first.get("pending") is True, "the first read of a map nobody has computed must say so"
    assert corpus.wait_coverage_idle(120)
    before = _without_timing(read())
    assert "stale" not in before and "pending" not in before
    assert before == _without_timing(corpus.coverage(conn, "cache.mat", bins=10))     # the in-place call agrees
    change(scored_file)
    conn.commit()
    fresh = _without_timing(corpus._coverage(conn, "cache.mat", bins=10))
    assert fresh != before, "the change did not move the map, so this case proves nothing"
    stale = _without_timing(read())
    assert stale.get("stale") is True and stale.get("stale_since"), "a stale answer must carry its marker"
    assert {k: v for k, v in stale.items() if k not in ("stale", "stale_since")} == before
    assert corpus.wait_coverage_idle(120)
    assert _without_timing(read()) == fresh
    corpus.clear_coverage_cache()
    assert _without_timing(corpus.coverage(conn, "cache.mat", bins=10)) == fresh


@pytest.fixture
def scored_file(tmp_path):
    """The `scored` fixture in a file a worker process can open (corpus-map-off-the-request)."""
    path = str(tmp_path / "scored.sqlite")
    conn = init_db(path)
    s = _build_scored(conn)
    SB.clear_score_cache()
    yield {**s, "path": path}
    from webui.server import corpus
    corpus.wait_coverage_idle(120)
    conn.close()


def test_a_routed_read_never_computes_in_the_request(scored_file, monkeypatch):
    """The parent never computes a map for a read that names its database: the worker process does. The
    in-place computation is made to explode in the parent; the reads still answer, and the map arrives."""
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    from Working.discovery import coverage_map as CM

    def boom(*a, **kw):
        raise AssertionError("the request computed the map in the bridge's own interpreter")
    monkeypatch.setattr(corpus, "_coverage", boom)
    monkeypatch.setattr(CM, "compute_conn", boom)
    assert corpus.coverage(conn, "cache.mat", bins=10, db_path=path)["pending"] is True
    assert corpus.wait_coverage_idle(120)
    got = corpus.coverage(conn, "cache.mat", bins=10, db_path=path)
    assert "pending" not in got and got["rows"]
    assert corpus.coverage_status()["mode"] == "process"


def test_concurrent_reads_of_a_stale_map_schedule_one_recompute(scored_file):
    import threading
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    corpus.coverage(conn, "cache.mat", bins=10, db_path=path)
    assert corpus.wait_coverage_idle(120)
    done = corpus.coverage_status()["computed"]
    _new_annotation(scored_file)
    conn.commit()
    out = []

    def reader():                       # each on its own connection, as each route call is
        c = corpus.connect(path)
        try:
            out.append(corpus.coverage(c, "cache.mat", bins=10, db_path=path))
        finally:
            c.close()
    readers = [threading.Thread(target=reader) for _ in range(6)]
    for t in readers:
        t.start()
    for t in readers:
        t.join()
    status = corpus.coverage_status()
    assert len(status["pending"]) + (status["in_flight"] is not None) <= 1, status
    assert all(o.get("stale") is True for o in out if "pending" not in o)
    assert corpus.wait_coverage_idle(120)
    assert corpus.coverage_status()["computed"] == done + 1, "six readers of one stale map recomputed it more than once"


def test_a_poll_while_the_recompute_is_queued_does_not_fingerprint_again(scored_file, monkeypatch):
    """The page re-reads every 3 s while the map is stale; on 5 M detections each fingerprint holds the interpreter
    ~0.3-0.5 s. While the recompute of a key is queued or running a read answers the last map, still marked stale,
    without fingerprinting; the read after the worker finishes fingerprints again and is fresh."""
    import threading
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    monkeypatch.setattr(corpus.worker, "MODE", "thread")
    corpus.coverage(conn, "cache.mat", bins=10, db_path=path)
    assert corpus.wait_coverage_idle(120)
    before = _without_timing(corpus.coverage(conn, "cache.mat", bins=10, db_path=path))
    gate = threading.Event()
    real = corpus._coverage
    monkeypatch.setattr(corpus, "_coverage", lambda *a, **kw: gate.wait(60) and real(*a, **kw))
    _new_annotation(scored_file)
    conn.commit()
    try:
        assert corpus.coverage(conn, "cache.mat", bins=10, db_path=path)["stale"] is True    # this one schedules
        calls = {"n": 0}
        real_fp = corpus.SB.channels_fingerprint

        def counted(*a, **kw):
            calls["n"] += 1
            return real_fp(*a, **kw)
        monkeypatch.setattr(corpus.SB, "channels_fingerprint", counted)
        for _ in range(3):
            polled = _without_timing(corpus.coverage(conn, "cache.mat", bins=10, db_path=path))
            assert polled["stale"] is True and polled["stale_since"]
            assert {k: v for k, v in polled.items() if k not in ("stale", "stale_since")} == before
        assert calls["n"] == 0, "a poll of a queued recompute fingerprinted the channels again"
    finally:
        gate.set()
    assert corpus.wait_coverage_idle(120)
    after = _without_timing(corpus.coverage(conn, "cache.mat", bins=10, db_path=path))
    assert "stale" not in after and after != before and calls["n"] >= 1


def test_a_job_that_raises_any_base_exception_is_a_loud_failure_and_the_queue_lives_on(scored_file, monkeypatch):
    """Critic S2: a BaseException (a Ctrl-C through `.result()`, a KeyboardInterrupt in the job) used to escape the
    drain with the job still marked in flight: every later read of that map answered "pending" through the poll
    shortcut, and no other map ever drained — the page said "recomputing…" for ever with no red card."""
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    monkeypatch.setattr(corpus.worker, "MODE", "thread")

    class Halt(BaseException):
        pass

    real = corpus._coverage
    calls = {"n": 0}

    def halting(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise Halt("interrupted")
        return real(*a, **kw)
    monkeypatch.setattr(corpus, "_coverage", halting)
    assert corpus.coverage(conn, "cache.mat", bins=10, db_path=path)["pending"] is True
    assert corpus.wait_coverage_idle(120), "the queue never went idle after the job raised"
    assert corpus.coverage_status()["in_flight"] is None
    with pytest.raises(corpus.CoverageFailed, match="could not be computed: Halt: interrupted"):
        corpus.coverage(conn, "cache.mat", bins=10, db_path=path)
    # the queue still drains other maps
    assert corpus.coverage(conn, "cache.mat", bins=11, db_path=path)["pending"] is True
    assert corpus.wait_coverage_idle(120)
    assert "pending" not in corpus.coverage(conn, "cache.mat", bins=11, db_path=path)


def test_a_map_is_kept_under_the_state_it_read_not_the_state_that_asked(scored_file, monkeypatch):
    """Critic S5: the read that schedules a recompute fingerprints state A; if the database moves to B before the
    worker reads it, the map is B's. It was stored under A's fingerprint, so after a revert to A the B map was served
    as fresh. The worker now fingerprints what it read (one snapshot on WAL; before == after otherwise) and the map
    is kept under that."""
    import threading

    from Working.discovery import coverage_map as CM
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    monkeypatch.setattr(corpus.worker, "MODE", "thread")
    corpus.coverage(conn, "cache.mat", bins=10, db_path=path)
    assert corpus.wait_coverage_idle(120)
    gate = threading.Event()
    real_connect = CM.connect_read_only
    monkeypatch.setattr(CM, "connect_read_only", lambda p: gate.wait(60) and real_connect(p))
    put_settings(conn, "analysis-defaults", {"containment": "whole"})            # state A
    conn.commit()
    want_a = _without_timing(corpus._coverage(conn, "cache.mat", bins=10))
    try:
        assert corpus.coverage(conn, "cache.mat", bins=10, db_path=path)["stale"] is True    # scheduled at A
        put_settings(conn, "analysis-defaults", {"containment": "centre"})       # state B, before the worker reads
        conn.commit()
        want_b = _without_timing(corpus._coverage(conn, "cache.mat", bins=10))
        assert want_a != want_b
    finally:
        gate.set()
    assert corpus.wait_coverage_idle(120)
    put_settings(conn, "analysis-defaults", {"containment": "whole"})            # back to A
    conn.commit()
    got = _without_timing(corpus.coverage(conn, "cache.mat", bins=10, db_path=path))
    assert got.get("stale") is True or got == want_a, "B's map was served as A's fresh map"
    assert corpus.wait_coverage_idle(120)
    assert _without_timing(corpus.coverage(conn, "cache.mat", bins=10, db_path=path)) == want_a


def test_the_start_up_warm_goes_through_the_worker(scored_file, monkeypatch):
    """`warm_coverage` schedules every file's home map on the same queue; the parent computes none of them."""
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]

    def boom(*a, **kw):
        raise AssertionError("the warm computed a map in the bridge's own interpreter")
    monkeypatch.setattr(corpus, "_coverage", boom)
    assert corpus.warm_coverage(conn) == ["cache.mat"]
    assert corpus.wait_coverage_idle(120)
    got = corpus.coverage(conn, "cache.mat", db_path=path, **corpus.HOME_COVERAGE)
    assert "pending" not in got and "stale" not in got


def test_the_thread_fallback_yields_between_channels(scored_file, monkeypatch):
    """When no process can be started, the recompute runs on a daemon thread that waits for the pages to go quiet
    before every channel after the first; the map it lands is the same map."""
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    monkeypatch.setattr(corpus.worker, "MODE", "thread")
    waits = []
    monkeypatch.setattr(corpus, "wait_for_quiet", lambda quiet_s=2.0, max_wait_s=30.0: waits.append(1) or 0.0)
    assert corpus.coverage(conn, "cache.mat", bins=10, db_path=path)["pending"] is True
    assert corpus.wait_coverage_idle(120)
    assert corpus.coverage_status()["mode"] == "thread"
    got = _without_timing(corpus.coverage(conn, "cache.mat", bins=10, db_path=path))
    assert got == _without_timing(corpus._coverage(conn, "cache.mat", bins=10))
    assert len(waits) == len(got["rows"]) - 1


def test_a_failed_recompute_is_a_loud_error_not_a_blank(scored_file, monkeypatch):
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    monkeypatch.setattr(corpus.worker, "MODE", "thread")

    def broken(*a, **kw):
        raise ValueError("the divergence could not be read")
    monkeypatch.setattr(corpus, "_coverage", broken)
    assert corpus.coverage(conn, "cache.mat", bins=10, db_path=path)["pending"] is True
    assert corpus.wait_coverage_idle(120)
    with pytest.raises(corpus.CoverageFailed, match="could not be computed.*the divergence could not be read"):
        corpus.coverage(conn, "cache.mat", bins=10, db_path=path)


def test_a_pending_answer_has_the_maps_shape_with_empty_layers(scored_file, monkeypatch):
    corpus = _corpus()
    conn, path = scored_file["conn"], scored_file["path"]
    monkeypatch.setattr(corpus.worker, "MODE", "thread")
    gate = __import__("threading").Event()
    real = corpus._coverage
    monkeypatch.setattr(corpus, "_coverage", lambda *a, **kw: gate.wait(60) and real(*a, **kw))
    try:
        p = corpus.coverage(conn, "cache.mat", bins=10, db_path=path)
    finally:
        gate.set()
    assert p["pending"] is True and p["bins"] == 10 and len(p["bin_edges_h"]) == 11
    assert [r["name"] for r in p["rows"]] and all(sum(r["detections"]) == 0 and len(r["annotations"]) == 10
                                                  for r in p["rows"])
    assert corpus.wait_coverage_idle(120)
    full = corpus.coverage(conn, "cache.mat", bins=10, db_path=path)
    assert set(full) == set(p) - {"pending"}, "a pending answer's keys must be the map's keys and the marker"


def test_one_read_pass_reads_each_channel_once(scored, monkeypatch):
    """The picker fingerprints every template's runs; 60 templates over the
    same 14 channels re-read them 683 times. A pass shares one memo."""
    conn, runs = scored["conn"], scored["runs"]
    reads = {"n": 0}
    real = SB._read_channel_rows

    def counted(*a, **kw):
        reads["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(SB, "_read_channel_rows", counted)
    memo = {}
    for ids in ([runs[0]], [runs[1]], runs, [runs[0]], runs):
        SB.score_runs_cached(conn, ids, memo=memo)
    assert reads["n"] == 2                        # two channels, each read once
    # and the memo changes no answer
    assert SB.score_runs_cached(conn, runs, memo=memo) == SB.score_runs(conn, runs)


# ── window reads that fetched a whole channel to keep a slice ───────────────
#
# `corpus.spans` (Explore's span bands, every zoom step) and
# `detection_map._starts` (every Detection-map cell) fetched every detection of
# the channel or run and kept the window in Python: 5-9 s a call and 8-10 s a
# map open on the 2026-10-18 database. Both now ask SQL for the window, with
# the legacy span-relative shift (`spans.absolute_bounds`) stated in the query.
# The answers must be the old ones, legacy rows included.

def _legacy_db(path=":memory:"):
    conn = init_db(path)
    rec = q.insert_recording(conn, "legacy.mat", 0, 1.0, 100_000, 0, "legacy_CH0.npy")
    config_id, _ = run_db.get_or_create_config(conn, _STEPS)
    rng = random.Random(7)
    runs = []
    for span in ((0, 100_000), (20_000, 60_000), (50_000, 90_000), (0, 30_000)):
        run = run_db.insert_run(conn, config_id, rec, span[0], span[1], status="completed", started_at=_AFTER)
        runs.append(run)
        for _ in range(400):
            if span[0] and rng.random() < 0.4:           # a legacy row: span-relative, below span_start
                a = rng.randrange(0, min(span[0], span[1] - span[0]))
            else:
                a = rng.randrange(span[0], span[1])
            conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                         (run, a, a + rng.randrange(0, 900), 0.5))
    conn.commit()
    return conn, rec, runs


def test_the_span_window_is_the_one_the_whole_channel_filter_kept():
    from Working.discovery.spans import absolute_bounds
    from webui.server import corpus
    conn, rec, runs = _legacy_db()
    rng = random.Random(3)
    try:
        for _ in range(40):
            t0 = rng.uniform(0, 100_000)
            t1 = min(100_000, t0 + rng.choice([10, 500, 5000, 100_000]))
            got = corpus.spans(conn, rec, t0, t1, 1.0)
            s0, s1 = int(math.floor(t0)), int(math.ceil(t1))
            want = []
            for d in conn.execute("SELECT d.id, d.start_idx, d.end_idx, r.span_start FROM detections d "
                                  "JOIN runs r ON r.id = d.run_id ORDER BY d.start_idx"):
                a, b = absolute_bounds(d["start_idx"], d["end_idx"], d["span_start"])
                if b > s0 and a < s1:
                    want.append((d["id"], a, b))
            want.sort(key=lambda w: w[1])
            assert [(d["id"], d["start_s"], d["end_s"]) for d in got["detections"]] == \
                [(i, float(a), float(b)) for i, a, b in want]
    finally:
        conn.close()


def test_the_map_counts_the_starts_the_whole_run_filter_kept():
    from Working.discovery import detection_map as DM
    from Working.discovery.spans import absolute_bounds
    conn, rec, runs = _legacy_db()
    try:
        run_rows = [dict(r) for r in conn.execute("SELECT * FROM runs ORDER BY id")]
        claimed = DM._resolve(run_rows)
        assert any(lo for lo, _, _ in claimed), "the fixture must claim ranges off the channel start"
        span_start = {r["id"]: r["span_start"] for r in run_rows}
        want = []
        for lo, hi, rid in claimed:
            for d in conn.execute("SELECT start_idx, end_idx FROM detections WHERE run_id = ?", (rid,)):
                a, _ = absolute_bounds(d["start_idx"], d["end_idx"], span_start[rid])
                if lo <= a < hi:
                    want.append(a)
        assert sorted(DM._starts(conn, claimed, run_rows).tolist()) == sorted(float(a) for a in want)
        assert len(want) > 100
    finally:
        conn.close()

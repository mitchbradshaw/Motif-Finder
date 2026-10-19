"""
test_webui_ar_speed.py
======================
AR, the speed pass — route-level pins on the scale fixture (`tests/perf_fixture.py`, built small here).

What was slow, measured on a sandbox copy of the real database (2026-10-18), and what each test pins:

* Review: one item read resolved the whole queue three times (0.4–0.9 s at 3,195 items) and the page re-read
  every row with its thumbnail after each verdict (5.3 s, 3 MB). An item read's SQLite work must not grow with the
  queue; rows can be read without thumbnails and the thumbnails paged; the counts have a light read of their own.
* Discovery: `/runs` read `group_status` (a recording listing per member run); `/templates` rescored on open and
  waited minutes behind the warm; `/fires` built a dict per detection per channel per run.
* Corpus: the coverage map lived in memory only and any settings change threw every map away.

Counts, not wall-clock (wall-clock budgets fail under load): SQLite VM steps through a progress handler, calls to
a monkeypatched helper, and equality against the old computation so nothing the page shows changes.

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
"""
import json
import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
for p in (PROJECT_ROOT, WEBUI_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

import perf_fixture  # noqa: E402
from server import corpus, discovery, review  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from Working.discovery import fanout  # noqa: E402
from Working.discovery import scoreboard as SB  # noqa: E402
from Working.review import queues as Q  # noqa: E402

SMALL = dict(n_channels=4, hours=48.0, n_druns=6, n_detections=60_000, n_annotations=800, n_templates=6,
             n_adjudications=40, n_reviewed=60)


def _bridge(tmp_path, stamp, **sizes):
    info = perf_fixture.build(str(tmp_path / "scale.sqlite"), **{**SMALL, **sizes})
    rt = Runtime("sandbox", stamp=stamp, db_source=info["db"], runtime_root=str(tmp_path / "runtime")).setup()
    return info, rt


@pytest.fixture(scope="module")
def bridge(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ar")
    info, rt = _bridge(tmp, "ar-speed", queue_size=600)
    getattr(Q, "clear_resolver_cache", lambda: None)()
    with TestClient(create_app(rt)) as client:
        yield client, rt, info
    rt.restore()


class _Steps:
    """SQLite VM steps (in units of 100) over every connection the bridge opens while armed."""

    def __init__(self, monkeypatch):
        self.n = 0
        real = corpus.connect

        def connect(path):
            c = real(path)

            def tick():
                self.n += 1
                return 0
            c.set_progress_handler(tick, 100)
            return c
        monkeypatch.setattr(corpus, "connect", connect)


# ── Review ──────────────────────────────────────────────────────────────────

def _item_steps(tmp_path, monkeypatch, size):
    info, rt = _bridge(tmp_path, f"ar-{size}", queue_size=size)
    getattr(Q, "clear_resolver_cache", lambda: None)()
    try:
        with TestClient(create_app(rt)) as client:
            qid = info["queue_id"]
            rows = client.get(f"/api/review/queues/{qid}?thumbs=0").json()["rows"]
            ids = [r["id"] for r in rows[len(rows) // 2: len(rows) // 2 + 3]]
            client.get(f"/api/review/queues/{qid}/items/{ids[0]}?px=200&pad_s=60")      # warm
            steps = _Steps(monkeypatch)
            for i in ids[1:]:
                r = client.get(f"/api/review/queues/{qid}/items/{i}?px=200&pad_s=60")
                assert r.status_code == 200, r.text
            monkeypatch.undo()
            return steps.n
    finally:
        rt.restore()


def test_an_item_read_does_not_grow_with_the_queue(tmp_path, monkeypatch):
    # fix round S1: 40x the items, within 10 % (+20) - an O(N) read at even a few VM ops an item fails this
    small = _item_steps(tmp_path / "s", monkeypatch, 150)
    big = _item_steps(tmp_path / "b", monkeypatch, 6000)
    assert big <= 1.1 * small + 20, (
        f"two item reads cost {small} x100 VM steps at 150 items and {big} at 6,000: the read scans the queue")


def test_rows_without_thumbnails_read_no_channel_and_lose_nothing_else(bridge, monkeypatch):
    client, rt, info = bridge
    qid = info["queue_id"]
    full = client.get(f"/api/review/queues/{qid}").json()
    calls = {"n": 0}
    real = review._trace_env

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)
    monkeypatch.setattr(review, "_trace_env", counted)
    # fix round B1: a COLD read, as after a restart - nothing remembered about thumbnails or their peaks
    if review._THUMB_CACHE is not None:
        review._THUMB_CACHE.clear()
    review._PEAKS.clear() if hasattr(review, "_PEAKS") else None
    lean = client.get(f"/api/review/queues/{qid}?thumbs=0").json()
    assert calls["n"] == 0, f"{calls['n']} traces drawn for a rows-only read"
    assert lean["thumbsServed"] is False and full.get("thumbsServed", True) is True
    assert lean["queue"] == full["queue"]
    assert len(lean["rows"]) == len(full["rows"]) == lean["queue"]["total"]
    for a, b in zip(lean["rows"], full["rows"]):
        assert {**a, "thumb": None} == {**b, "thumb": None}, "a rows-only read must differ only by the thumbnail"
    # the Shape card's queue-wide reference bar reads only the two ends of every row's peak: both reads carry them
    peaks = [p for p in (review.baseline_peak(r["thumb"]) for r in full["rows"] if not r.get("heldOut")) if p > 0]
    assert full["thumbPeaks"] == [min(peaks), max(peaks)]
    # cold, the rows-only read does not know them yet (null) and /peaks works them out in the background
    assert lean["thumbPeaks"] is None
    first = client.get(f"/api/review/queues/{qid}/peaks").json()
    assert calls["n"] == 0 or first["ready"] is False
    done = client.get(f"/api/review/queues/{qid}/peaks?wait_s=60").json()
    assert done == {"thumbPeaks": [min(peaks), max(peaks)], "ready": True}
    # and once known, the next rows-only read carries them
    assert client.get(f"/api/review/queues/{qid}?thumbs=0").json()["thumbPeaks"] == [min(peaks), max(peaks)]


def test_thumbnails_are_paged_and_equal_the_full_reads(bridge):
    client, rt, info = bridge
    qid = info["queue_id"]
    full = client.get(f"/api/review/queues/{qid}").json()["rows"]
    want = {r["id"]: r["thumb"] for r in full[10:20]}
    got = client.get(f"/api/review/queues/{qid}/thumbs?ids=" + ",".join(want)).json()
    assert got["thumbs"] == want
    bad = client.get(f"/api/review/queues/{qid}/thumbs?ids=999999999")
    assert bad.status_code == 404, "an id that is not in the queue is refused, never answered with an empty thumb"


def test_the_counts_read_is_the_queue_reads_counts(bridge):
    client, rt, info = bridge
    qid = info["queue_id"]
    head = client.get(f"/api/review/queues/{qid}?thumbs=0").json()["queue"]
    c = client.get(f"/api/review/queues/{qid}/counts").json()
    assert {k: c[k] for k in ("total", "judged", "remaining", "pace_s")} == \
        {k: head[k] for k in ("total", "judged", "remaining", "pace_s")}
    rows = client.get(f"/api/review/queues/{qid}?thumbs=0").json()["rows"]
    row = next(r for r in rows if not r.get("judged"))
    ack = client.post(f"/api/review/queues/{qid}/verdict", json={"target_id": row["id"], "verdict": "unsure"})
    assert ack.status_code == 200, ack.text
    after = client.get(f"/api/review/queues/{qid}/counts").json()
    # review-carry: the verdict is also carried to the same event in other runs, which can judge other items of
    # this queue; exactly those, and the one asked about, are newly judged
    carried = set(ack.json()["carriedIds"])
    reached = sum(1 for r in rows if r is not row and not r.get("judged") and carried & set(r["members"]))
    assert after["judged"] == c["judged"] + 1 + reached and after["total"] == c["total"]
    assert ack.json()["counts"] == {k: after[k] for k in ("total", "judged", "remaining")}
    assert client.post(f"/api/review/queues/{qid}/undo").status_code == 200
    assert client.get(f"/api/review/queues/{qid}/counts").json()["judged"] == c["judged"]


def test_an_items_rank_is_its_place_in_the_listing(bridge):
    client, rt, info = bridge
    qid = info["queue_id"]
    rows = client.get(f"/api/review/queues/{qid}?thumbs=0").json()["rows"]
    for r in rows[:2] + rows[300:302] + rows[-2:]:
        d = client.get(f"/api/review/queues/{qid}/items/{r['id']}?px=200&pad_s=60").json()
        assert d["entry"]["rank"] == r["rank"]
        assert d["queue"]["total"] == len(rows)
        assert {**d["entry"], "thumb": None} == {**r, "thumb": None}


def test_the_request_clock_advances_on_a_request(bridge):
    """Fix round S7: the start-up warm waits on this clock; it must move when a page reads."""
    client, rt, info = bridge
    before = corpus.REQUEST_CLOCK["last"]
    assert client.get("/api/health").status_code == 200
    assert corpus.REQUEST_CLOCK["last"] > before
    assert corpus.REQUEST_CLOCK["inflight"] == 0


def test_the_warm_waits_for_the_pages_to_go_quiet(monkeypatch):
    """Fix round S7: a request inside the quiet window delays the warm; a quiet bridge does not; a page that never
    stops reading holds it at most `max_wait_s`."""
    import threading
    import time
    monkeypatch.setitem(corpus.REQUEST_CLOCK, "inflight", 0)
    monkeypatch.setitem(corpus.REQUEST_CLOCK, "last", time.monotonic() - 10)
    assert corpus.wait_for_quiet(quiet_s=0.5, max_wait_s=5) < 0.3            # quiet already: no wait
    corpus.REQUEST_CLOCK["last"] = time.monotonic()                          # a request just finished
    waited = corpus.wait_for_quiet(quiet_s=0.5, max_wait_s=5)
    assert 0.4 <= waited < 2.0, f"waited {waited:.2f} s after a request inside the quiet window"
    corpus.REQUEST_CLOCK["inflight"] = 1                                     # a read in flight the whole time
    stop = threading.Event()
    assert corpus.wait_for_quiet(quiet_s=0.1, max_wait_s=0.6) >= 0.55        # capped, never for ever
    stop.set()


# ── Discovery ───────────────────────────────────────────────────────────────

def test_the_runs_list_reads_status_without_group_status(bridge, monkeypatch):
    client, rt, info = bridge
    c = sqlite3.connect(rt.db_path)
    c.row_factory = sqlite3.Row
    want = {}
    for d in info["druns"]:
        st = fanout.group_status(c, run_ids=d["run_ids"])
        want[d["key"]] = (f"{st['done']} / {st['total']}", sum(x["detections"] for x in st["channels"]))
        light = getattr(fanout, "group_status_light", None)
        assert light is not None and light(c, run_ids=d["run_ids"]) == st, "the light status must be group_status's"
        assert light(c, run_ids=d["run_ids"]) == st, "and again from its count cache"
    # a detection appended to a run moves its id range, so the remembered count is not served
    d0 = info["druns"][0]
    c.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 10, 20, 0.5)", (d0["run_ids"][0],))
    c.commit()
    assert fanout.group_status_light(c, run_ids=d0["run_ids"]) == fanout.group_status(c, run_ids=d0["run_ids"])
    st = fanout.group_status(c, run_ids=d0["run_ids"])
    want[d0["key"]] = (f"{st['done']} / {st['total']}", sum(x["detections"] for x in st["channels"]))
    c.close()
    calls = {"n": 0}
    real = fanout.group_status

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)
    monkeypatch.setattr(fanout, "group_status", counted)
    runs = {r["key"]: r for r in client.get("/api/discovery/runs").json() if r["key"] != "human"}
    assert calls["n"] == 0, f"the runs list read group_status {calls['n']} times"
    for key, (done, found) in want.items():
        assert (runs[key]["channelsDone"], runs[key]["found"], runs[key]["status"]) == (done, found, "done")


def test_the_template_picker_never_scores_on_open(bridge, monkeypatch):
    client, rt, info = bridge
    SB.clear_score_cache()
    calls = {"n": 0}
    real = SB.score_runs

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)
    monkeypatch.setattr(SB, "score_runs", counted)
    discovery.SCORING_PAUSED = True                  # hold the background scoring until the open has answered
    try:
        first = client.get("/api/discovery/templates").json()
        assert calls["n"] == 0, f"the picker scored {calls['n']} templates on open"
        named = [t for t in first if t["name"].startswith("scale_template_")]
        assert named and all(t["scoring"] for t in named), "an unscored template says it is being scored"
    finally:
        discovery.SCORING_PAUSED = False
    assert discovery.wait_for_scoring(120), "the background scoring never finished"
    second = {t["name"]: t for t in client.get("/api/discovery/templates").json()}
    c = corpus.connect(rt.db_path)
    try:
        for t in named:
            assert second[t["name"]]["scoring"] is False
            assert second[t["name"]]["lastScore"] == discovery._last_score(c, t["name"])
    finally:
        c.close()


def test_fires_counts_by_sql_and_match_the_span_histogram(bridge, monkeypatch):
    client, rt, info = bridge
    s = client.get("/api/discovery/session").json()["session"]
    chans = s["channels"][:3]
    keys = ["human"] + [d["key"] for d in info["druns"]]
    t0, t1 = s["section"]
    url = (f"/api/discovery/fires?channels={','.join(chans)}&t0={t0}&t1={t1}&runs={','.join(keys)}")
    calls = {"n": 0}
    real = discovery._run_detections

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)
    monkeypatch.setattr(discovery, "_run_detections", counted)
    got = client.get(url).json()
    assert calls["n"] == 0, "fires materialised every detection of every run per channel"
    # the reference: the old computation, a histogram of every span's start
    c = corpus.connect(rt.db_path)
    try:
        sess = c.execute("SELECT * FROM discovery_sessions ORDER BY id DESC LIMIT 1").fetchone()
        span = (int(round(t0 * 3600)), int(round(t1 * 3600)))
        edges = np.array([(got["firstBin"] + i) * got["binH"] * 3600 for i in range(got["nBins"] + 1)])
        for ch_out, name in zip(got["channels"], chans):
            ch = discovery._ids_for(c, discovery._stem(sess["source_file"]), [name])[0]
            for row in ch_out["rows"]:
                spans = real(c, discovery._run_ids(c, discovery._dr_by_key(c, sess["id"], row["run"])),
                             int(ch["id"]), span) if row["run"] != "human" else discovery._human_spans(c, ch["id"], span)
                starts = np.array([sp["start"] for sp in spans], dtype=float)
                want = np.histogram(starts, bins=edges)[0].tolist() if len(starts) else [0] * got["nBins"]
                assert row["counts"] == want, f"{name} {row['run']}"
    finally:
        c.close()


def test_the_scoreboard_scores_only_the_channels_it_shows(bridge, monkeypatch):
    client, rt, info = bridge
    s = client.get("/api/discovery/session").json()["session"]
    chans = s["channels"][:2]
    keys = [d["key"] for d in info["druns"][:3]]
    t0, t1 = s["section"]
    SB.clear_score_cache()
    calls = {"n": 0}
    real = SB.channel_score

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)
    monkeypatch.setattr(SB, "channel_score", counted)
    got = client.get(f"/api/discovery/scoreboard?runs={','.join(keys)}&channels={','.join(chans)}&t0={t0}&t1={t1}")
    assert got.status_code == 200, got.text
    assert calls["n"] == len(keys) * len(chans), f"{calls['n']} channels scored to show {len(keys) * len(chans)}"
    # the old computation: every channel of the run scored, the asked-for ones kept, the total over those
    monkeypatch.setattr(SB, "channel_score", real)
    c = corpus.connect(rt.db_path)
    try:
        rule = discovery.rule_from_settings(c)
        span = (int(round(t0 * 3600)), int(round(t1 * 3600)))
        ids_of = {d["key"]: d["run_ids"] for d in info["druns"]}
        names = {i: n for i, n in zip(info["recordings"], info["channel_names"])}
        wanted = {i for i, n in names.items() if n in chans}
        for row, key in zip(got.json(), keys):
            full = SB.score_runs(c, ids_of[key], rule=rule, span=span)
            rows = [r for r in full["channels"] if r["recording_id"] in wanted]
            total = SB.run_total(c, [r["run_id"] for r in rows], rule=rule, rows=rows)
            assert row["total"] == discovery._score_row(total) | {"recall": discovery._recall_cell(total)}
            assert [x["channel"] for x in row["channels"]] == [names[r["recording_id"]] for r in rows]
            assert [{k: v for k, v in x.items() if k != "channel"} for x in row["channels"]] == \
                [discovery._score_row(r) for r in rows]
    finally:
        c.close()


# ── Corpus ──────────────────────────────────────────────────────────────────

def test_the_coverage_map_survives_a_restart_and_ignores_unrelated_settings(bridge, monkeypatch, tmp_path):
    """corpus-map-off-the-request changed how a miss shows, not what is kept: the route never computes, so a miss is
    `pending` (no map yet) or `stale` (the last map, marked) while the worker recomputes; "recomputed" is now counted
    by the worker (`coverage_status()["computed"]`) instead of by a monkeypatched `_coverage`, which the worker
    process cannot see."""
    client, rt, info = bridge
    sf = perf_fixture.SOURCE_FILE
    url = f"/api/corpus/{sf}/coverage?bins=57&verdicts=seed,interesting"
    corpus.reset_coverage_worker()
    corpus.clear_coverage_cache()
    for f in os.listdir(rt.cache_dir + "/coverage") if os.path.isdir(rt.cache_dir + "/coverage") else []:
        os.remove(os.path.join(rt.cache_dir, "coverage", f))
    assert client.get(url).json().get("pending") is True
    assert corpus.wait_coverage_idle(300)
    first = client.get(url).json()
    assert "pending" not in first and "stale" not in first
    corpus._COVERAGE_CACHE.clear()                      # a restart: the memory is gone, the disk is not
    computed = corpus.coverage_status()["computed"]
    again = client.get(url).json()
    assert {**again, "compute_ms": 0} == {**first, "compute_ms": 0}
    assert any(f.endswith(".json") for f in os.listdir(rt.cache_dir + "/coverage"))

    # a setting the map does not read: still a hit (memory, then disk)
    c = sqlite3.connect(rt.db_path)
    c.execute("INSERT OR REPLACE INTO settings (page, key, value_json, updated_at) "
              "VALUES ('appearance', 'theme', '\"dark\"', 'now')")
    c.commit()
    assert "stale" not in client.get(url).json()
    corpus._COVERAGE_CACHE.clear()
    assert "stale" not in client.get(url).json()
    assert corpus.wait_coverage_idle(300)
    assert corpus.coverage_status()["computed"] == computed, "an unchanged map was recomputed"
    # a setting it does read: a miss — served stale at once, recomputed behind the read
    c.execute("INSERT OR REPLACE INTO settings (page, key, value_json, updated_at) "
              "VALUES ('analysis-defaults', 'iou', '0.33', 'now')")
    c.commit()
    c.close()
    stale = client.get(url).json()
    assert stale.get("stale") is True and stale.get("stale_since")
    assert corpus.wait_coverage_idle(300)
    assert corpus.coverage_status()["computed"] == computed + 1
    assert "stale" not in client.get(url).json()


def _set_iou(rt, value):
    c = sqlite3.connect(rt.db_path)
    c.execute("INSERT OR REPLACE INTO settings (page, key, value_json, updated_at) "
              "VALUES ('analysis-defaults', 'iou', ?, 'now')", (json.dumps(value),))
    c.commit()
    c.close()


def test_the_coverage_route_answers_at_once_and_never_computes_in_the_bridge(bridge, monkeypatch):
    """corpus-map-off-the-request: after a change the map reads, the route answers the last map at once, marked
    stale, and the bridge's own interpreter computes nothing — the worker process does. The read's `compute_ms` is
    the read's own time."""
    import time

    from Working.discovery import coverage_map as CM
    client, rt, info = bridge
    url = f"/api/corpus/{perf_fixture.SOURCE_FILE}/coverage?bins=57&verdicts=seed,interesting"
    client.get(url)
    assert corpus.wait_coverage_idle(300)
    fresh = client.get(url).json()
    assert "pending" not in fresh

    def boom(*a, **kw):
        raise AssertionError("the request computed the corpus map in the bridge")
    monkeypatch.setattr(corpus, "_coverage", boom)
    monkeypatch.setattr(CM, "compute_conn", boom)
    _set_iou(rt, 0.41)
    try:
        t0 = time.perf_counter()
        got = client.get(url)
        took = time.perf_counter() - t0
        assert got.status_code == 200, got.text
        body = got.json()
        assert body.get("stale") is True and body.get("stale_since")
        assert {k: v for k, v in body.items() if k not in ("stale", "stale_since", "compute_ms")} == \
            {k: v for k, v in fresh.items() if k != "compute_ms"}
        assert took < 5.0, f"a stale read took {took:.1f} s: it waited on something"
        assert corpus.wait_coverage_idle(300)
        assert corpus.coverage_status()["mode"] == "process"
        assert "stale" not in client.get(url).json()
    finally:
        _set_iou(rt, 0.5)
        client.get(url)
        corpus.wait_coverage_idle(300)


def test_a_failed_recompute_reaches_the_page_as_a_loud_error(bridge, monkeypatch):
    client, rt, info = bridge
    url = f"/api/corpus/{perf_fixture.SOURCE_FILE}/coverage?bins=28"
    monkeypatch.setattr(corpus, "COVERAGE_WORKER", "thread")
    corpus.reset_coverage_worker()

    def broken(*a, **kw):
        raise ValueError("the divergence could not be read")
    monkeypatch.setattr(corpus, "_coverage", broken)
    corpus.clear_coverage_cache()
    for f in os.listdir(rt.cache_dir + "/coverage") if os.path.isdir(rt.cache_dir + "/coverage") else []:
        os.remove(os.path.join(rt.cache_dir, "coverage", f))
    assert client.get(url).json().get("pending") is True
    assert corpus.wait_coverage_idle(300)
    # the test client re-raises what the app's loud handler turns into a 500 with the sentence (app.py `_loud`)
    with pytest.raises(corpus.CoverageFailed, match="could not be computed.*the divergence could not be read"):
        client.get(url)
    corpus.reset_coverage_worker()


def test_the_background_scorer_yields_to_the_pages_between_templates(monkeypatch):
    """ux-1019: scoring 73 templates back to back held the interpreter for minutes and every page read stalled
    under it (the 2026-10-19 walk). The drain waits for a quiet gap before EACH template, so a busy page gets most
    of the time; the scores still land within minutes."""
    import threading
    from server import corpus
    from server import discovery as D

    waits, scored = [], []
    monkeypatch.setattr(corpus, "wait_for_quiet", lambda quiet_s=2.0, max_wait_s=30.0: waits.append((quiet_s, max_wait_s)) or 0.0)
    monkeypatch.setattr(corpus, "connect", lambda db: type("C", (), {"close": lambda self: None})())
    monkeypatch.setattr(D, "_last_score", lambda c, name, memo=None: scored.append(name))
    with D._SCORING_LOCK:
        D._SCORING["pending"] = ["t1", "t2", "t3"]
        D._SCORING["db"] = ":memory:"
        D._SCORING["thread"] = threading.current_thread()
    D._SCORING_IDLE.clear()
    D._drain_scoring()
    assert scored == ["t1", "t2", "t3"]
    assert len(waits) == 3, f"expected one quiet-wait per template, saw {len(waits)}"
    assert all(q <= 2.0 and m <= 10.0 for q, m in waits), "the wait must stay short or the scores never land"
    assert D.wait_for_scoring(timeout=1)

"""
test_perf_section_reads.py
==========================
Discovery's scoreboard scores the section on screen, and its cost must follow
the section, not the channel.

Measured 2026-10-18 on a database the size of the real one after the RQ4
import (251 MB: 4.5 M detections over 1,472 runs on M2_aug's 16 channels):
`GET /api/discovery/scoreboard`, which every Discovery tab loads, took 66 s
over a 4-hour section — 21 s of it in `_prior_adjudicated`, whose join SQLite
started from the channel's runs and so walked every detection on the channel
(4.5 M rows over 736 calls) to find 300 adjudications, and ~30 s reading
every detection of every run and null draw into Python to keep the ones in
the section.

The pins are counts, not wall-clock (as in `test_perf_scoring_reads.py`):
the rows a score fetches into Python, and the SQLite VM steps it takes, as
the detections *outside* the section grow. The figures must not change: the
section read is checked against the whole read on random data — legacy
span-relative rows, detections longer than the section, events at its edges,
a loose matching rule, prior adjudications and null draws.
"""

import json
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

from Working.database import adjudications as adj_db
from Working.database import queries as q
from Working.database import runs as run_db
from Working.database.schema import init_db
from Working.discovery import divergence as DIV
from Working.discovery import scoreboard as SB
from Working.discovery.spans import absolute_bounds

_STEPS = {"steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]}
_BEFORE = "2026-09-01T00:00:00"
_RUN_AT = "2026-09-10T00:00:00"
_AFTER = "2026-09-20T00:00:00"
N = 200_000
SECTION = (90_000, 93_600)          # one hour at 1 Hz


# ── counting what a read costs ──────────────────────────────────────────────

class _Counting:
    """A connection that counts the rows its statements hand to Python."""

    def __init__(self, conn):
        self._conn = conn
        self.rows = 0

    def execute(self, *a, **kw):
        return _Cursor(self, self._conn.execute(*a, **kw))

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _Cursor:
    def __init__(self, owner, cur):
        self._owner, self._cur = owner, cur

    def fetchall(self):
        rows = self._cur.fetchall()
        self._owner.rows += len(rows)
        return rows

    def fetchone(self):
        row = self._cur.fetchone()
        self._owner.rows += row is not None
        return row

    def __iter__(self):
        for row in self._cur:
            self._owner.rows += 1
            yield row

    def __getattr__(self, name):
        return getattr(self._cur, name)


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


def _channel(n_outside, *, other_run=0):
    """One channel with ten window labels and an event row in SECTION, a run
    with 20 detections there plus ``n_outside`` outside it, a null draw with
    the same, and an adjudicated detection. ``other_run`` adds that many
    detections in another run on the same channel (the 45 other jobs)."""
    conn = init_db(":memory:")
    rec = q.insert_recording(conn, "sec.mat", 0, 1.0, N, 0, "sec_CH0.npy")
    cfg, _ = run_db.get_or_create_config(conn, _STEPS)
    run = run_db.insert_run(conn, cfg, rec, 0, N, status="completed", started_at=_RUN_AT)
    null = run_db.insert_run(conn, cfg, rec, 0, N, status="completed", started_at=_RUN_AT)
    run_db.update_run(conn, null, surrogate_of_run_id=run)
    for k in range(10):
        a = SECTION[0] + k * 360
        q.insert_annotation(conn, rec, a, a + 300, "interesting" if k % 2 else "not_interesting",
                            q.SOURCE_IMPORTED_10MIN, created_at=_BEFORE, commit=False)
        q.insert_reviewed_span(conn, rec, a, a + 300, q.SOURCE_IMPORTED_10MIN, reviewed_at=_BEFORE, commit=False)
    q.insert_annotation(conn, rec, SECTION[0] + 1000, SECTION[0] + 1100, "interesting", "excel_catalog",
                        created_at=_BEFORE, commit=False)
    inside = [(SECTION[0] + k * 180 + 10, SECTION[0] + k * 180 + 90) for k in range(20)]
    # outside the section and nowhere near the event row: before it and after it
    outside = [(1000 + (k * 37) % 80_000, 1000 + (k * 37) % 80_000 + 50) if k % 2 else
               (100_000 + (k * 37) % 90_000, 100_000 + (k * 37) % 90_000 + 50) for k in range(n_outside)]
    for r in (run, null):
        conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                         [(r, a, b) for a, b in inside + outside])
    if other_run:
        other = run_db.insert_run(conn, cfg, rec, 0, N, status="completed", started_at=_RUN_AT)
        conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                         [(other, 50 + (k * 23) % (N - 100), 50 + (k * 23) % (N - 100) + 40)
                          for k in range(other_run)])
    det = conn.execute("SELECT id FROM detections WHERE run_id = ? ORDER BY start_idx DESC LIMIT 1",
                       (run,)).fetchone()[0]
    adj_db.insert_adjudication(conn, det, "interesting")
    conn.commit()
    return conn, rec, run


def test_a_section_score_fetches_the_section_not_the_run():
    """Four times the detections outside the section, the same rows fetched:
    the run's and its null draw's detections were read whole into Python."""
    fetched, scores = [], []
    for n in (2000, 8000):
        conn, rec, run = _channel(n)
        try:
            counting = _Counting(conn)
            scores.append(SB.channel_score(counting, run, span=SECTION))
            fetched.append(counting.rows)
        finally:
            conn.close()
    assert scores[0]["found"] == scores[1]["found"] == 20
    assert scores[0]["null_expects"] == scores[1]["null_expects"] == 20
    per = (fetched[1] - fetched[0]) / 6000.0
    assert per < 0.01, (f"{fetched[0]} -> {fetched[1]} rows fetched for 4x the detections outside the "
                        f"section: {per:.2f} per added detection, so the read follows the run, not the section")


def test_a_section_divergence_fetches_the_section_not_the_run():
    fetched = []
    for n in (2000, 8000):
        conn, rec, run = _channel(n)
        try:
            counting = _Counting(conn)
            div = DIV.channel_divergence(counting, rec, [run], span=SECTION)
            fetched.append(counting.rows)
            assert sum(div["cells"].values()) + div["not_comparable"]["n"] > 0
        finally:
            conn.close()
    per = (fetched[1] - fetched[0]) / 6000.0
    assert per < 0.01, f"{fetched[0]} -> {fetched[1]} rows fetched: {per:.2f} per added detection outside"


def test_finding_prior_adjudications_does_not_walk_the_channels_detections():
    """Another run on the channel gains 6,000 detections, none adjudicated:
    the score's work must not grow with them. `_prior_adjudicated`'s join
    walked every detection of every run on the channel to find the few
    adjudicated ones (~10 VM steps each, once per channel row)."""
    steps = []
    for n in (2000, 8000):
        conn, rec, run = _channel(50, other_run=n)
        try:
            steps.append(_vm_steps(conn, lambda: SB.channel_score(conn, run, span=SECTION)))
        finally:
            conn.close()
    per = (steps[1] - steps[0]) / 6000.0
    assert per < 1, f"VM steps {steps[0]} -> {steps[1]}: {per:.1f} per detection of another run on the channel"


def test_scoring_one_run_does_not_read_every_run_on_the_channel():
    """A windowed application writes one run per window (1,442 per channel for
    1-hour windows at 50 % over M2_aug), and the overnight import alone left
    ~90 runs on each M2_aug channel. A score asked about one run read every
    run on its channel and kept that one (`divergence.real_runs`)."""
    fetched = []
    for n in (20, 220):
        conn, rec, run = _channel(50)
        cfg = conn.execute("SELECT config_id FROM runs WHERE id = ?", (run,)).fetchone()[0]
        for _ in range(n):
            run_db.insert_run(conn, cfg, rec, 0, N, status="completed", started_at=_RUN_AT)
        try:
            counting = _Counting(conn)
            SB.channel_score(counting, run, span=SECTION)
            fetched.append(counting.rows)
        finally:
            conn.close()
    assert fetched[0] == fetched[1], f"{fetched[0]} -> {fetched[1]} rows fetched for 200 more runs on the channel"


def test_the_map_counts_a_channel_without_fetching_its_detections():
    """Discovery › Map's dataset and channel levels count a few cells per
    channel; they fetched every detection start to do it (2.37 M rows, 1.3 s
    per level on a database the size of the real one)."""
    from Working.discovery import detection_map as DM
    fetched = []
    for n in (2000, 8000):
        conn, rec, run = _channel(n)
        conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, span_start, span_end, "
                     "created_at, updated_at) VALUES ('s', 'sec.mat', '[]', 0, 0, ?, ?)", (_RUN_AT, _RUN_AT))
        conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, params_json, status, created_at, "
                     "updated_at) VALUES (1, 'r', 'template', 'r', ?, 'done', ?, ?)",
                     (json.dumps({"run_ids": [run]}), _RUN_AT, _RUN_AT))
        conn.commit()
        try:
            counting = _Counting(conn)
            top = DM.dataset_map(counting)
            eighths = DM.channel_map(counting, "sec.mat", chunks=8)
            fetched.append(counting.rows)
            key = next(r["key"] for r in top["rows"] if r["key"] != DM.HUMAN_KEY)
            assert top["datasets"][0]["cells"][key]["CH1"]["count"] == n + 20
            assert sum(c["count"] for c in eighths["cells"][key]["CH1"]) == n + 20
        finally:
            conn.close()
    assert fetched[0] == fetched[1], f"{fetched[0]} -> {fetched[1]} rows fetched for 6,000 more detections"


# ── the section read is the whole read, restricted ──────────────────────────
#
# The reference reads every detection of the run, as the scoreboard and the
# divergence did before they asked SQL for the section; everything downstream
# is the same code. On the code before the change the patches change nothing,
# so these pass there too: they are what keeps the faster read honest.

def _all_rows(conn, run_id, span_start, *args, **kwargs):
    rows = conn.execute("SELECT id, start_idx, end_idx, score FROM detections WHERE run_id = ? "
                        "ORDER BY start_idx, id", (int(run_id),)).fetchall()
    out = []
    for r in rows:
        a, b = absolute_bounds(r["start_idx"], r["end_idx"], span_start)
        out.append({"id": int(r["id"]), "start": a, "end": b,
                    "score": (float(r["score"]) if r["score"] is not None else None)})
    out.sort(key=lambda d: (d["start"], d["id"]))
    return out


def _all_count(conn, run_id, span_start, lo, hi):
    return sum(1 for d in _all_rows(conn, run_id, span_start) if lo <= d["start"] < hi)


def _all_div_rows(conn, runs, *args, **kwargs):
    if not runs:
        return []
    by_id = {int(r["id"]): r for r in runs}
    marks = ",".join("?" * len(by_id))
    out = []
    for r in conn.execute(f"SELECT id, run_id, start_idx, end_idx, score, meta_json FROM detections "
                          f"WHERE run_id IN ({marks}) ORDER BY start_idx, id", list(by_id)).fetchall():
        a, b = absolute_bounds(r["start_idx"], r["end_idx"], by_id[int(r["run_id"])]["span_start"])
        out.append({"id": int(r["id"]), "run_id": int(r["run_id"]), "start": a, "end": b,
                    "score": (float(r["score"]) if r["score"] is not None else None),
                    "morphology": DIV._morphology(r["meta_json"])})
    out.sort(key=lambda d: (d["start"], d["id"]))
    return out


def _whole_reads(monkeypatch):
    monkeypatch.setattr(SB, "_detections", _all_rows)
    monkeypatch.setattr(SB, "_count_in", _all_count, raising=False)
    monkeypatch.setattr(DIV, "_detections", _all_div_rows)


def _random_channel(seed):
    """A channel with a whole-channel run, a spanned run carrying legacy
    span-relative rows beside absolute ones, null draws of both, an older run
    with adjudications given before the others started, window labels and
    event rows clustered at the section edges, and detections from 5 to
    30,000 samples long."""
    rng = random.Random(seed)
    conn = init_db(":memory:")
    rec = q.insert_recording(conn, "rnd.mat", 0, 1.0, N, 0, "rnd_CH0.npy")
    cfg, _ = run_db.get_or_create_config(conn, _STEPS)
    edges = [SECTION[0], SECTION[1], 60_000, 140_000]

    def near():
        return max(0, min(N - 1, rng.choice(edges) + int(rng.gauss(0, 900))))

    def anywhere():
        return rng.randrange(0, N - 1)

    for _ in range(60):
        a = near() if rng.random() < 0.6 else anywhere()
        verdict = rng.choice(["interesting", "not_interesting", "unsure", "seed", "artifact"])
        q.insert_annotation(conn, rec, a, a + 600, verdict, q.SOURCE_IMPORTED_10MIN, created_at=_BEFORE,
                            commit=False)
        if rng.random() < 0.8:
            q.insert_reviewed_span(conn, rec, a, a + 600, q.SOURCE_IMPORTED_10MIN, reviewed_at=_BEFORE, commit=False)
    events = []
    for _ in range(25):
        a = near()
        w = rng.choice([30, 120, 400, 2500])
        events.append((a, a + w))
        q.insert_annotation(conn, rec, a, a + w, rng.choice(["interesting", "not_interesting", "unsure"]),
                            "excel_catalog", created_at=rng.choice([_BEFORE, _AFTER]), commit=False)

    def width():
        return rng.choice([5, 40, 180, 600, 3000, 30_000]) if rng.random() < 0.3 else rng.randrange(10, 400)

    def fill(run_id, n, span_start=0, legacy=0.0):
        rows = []
        for _ in range(n):
            pick = rng.random()
            if pick < 0.25 and events:                 # near an event: a pair the matcher may take
                ea, eb = rng.choice(events)
                a = max(0, ea + int(rng.gauss(0, 60)))
                b = a + max(1, int((eb - ea) * rng.uniform(0.3, 2.5)))
            else:
                a = near() if pick < 0.7 else anywhere()
                b = a + width()
            if legacy and rng.random() < legacy and a >= span_start:
                a, b = a - span_start, b - span_start   # written span-relative, before 2026-09-21
            meta = json.dumps({"morphology": rng.choice(["drop", "spike"])}) if rng.random() < 0.3 else None
            rows.append((run_id, a, b, rng.random(), meta))
        conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                         "VALUES (?, ?, ?, ?, ?)", rows)

    old = run_db.insert_run(conn, cfg, rec, 0, N, status="completed", started_at=_BEFORE)
    fill(old, 150)
    whole = run_db.insert_run(conn, cfg, rec, 0, N, status="completed", started_at=_RUN_AT)
    fill(whole, 400)
    spanned = run_db.insert_run(conn, cfg, rec, 70_000, 130_000, status="completed", started_at=_RUN_AT)
    fill(spanned, 300, span_start=70_000, legacy=0.5)
    for parent, span_start in ((whole, 0), (spanned, 70_000), (spanned, 70_000)):
        draw = run_db.insert_run(conn, cfg, rec, span_start, N if not span_start else 130_000,
                                 status="completed", started_at=_RUN_AT)
        run_db.update_run(conn, draw, surrogate_of_run_id=parent)
        fill(draw, 200, span_start=span_start, legacy=0.5 if span_start else 0.0)
    for r in (old, whole, spanned):
        ids = [x[0] for x in conn.execute("SELECT id FROM detections WHERE run_id = ?", (r,))]
        for det in rng.sample(ids, 12):
            adj_db.insert_adjudication(conn, det, rng.choice(["interesting", "not_interesting", "artifact"]),
                                       commit=False)
            conn.execute("UPDATE adjudications SET created_at = ? WHERE detection_id = ?",
                         (rng.choice([_BEFORE, _AFTER]), det))
    conn.commit()
    return conn, rec, [whole, spanned]


_SPANS = [SECTION, (0, 3600), (59_000, 61_000), (69_500, 70_500), (128_000, 135_000), (150_000, 199_000),
          (0, N), None]
_RULES = [None, {"iou": 0.0, "onset": 2.0}, {"iou": 0.3, "onset": 0.0}]


@pytest.mark.parametrize("rule", _RULES, ids=["default", "loose", "strict-onset"])
@pytest.mark.parametrize("seed", range(4))
def test_the_section_score_is_the_whole_read_restricted(seed, rule, monkeypatch):
    conn, rec, runs = _random_channel(seed)
    try:
        fast = {(r, s): SB.channel_score(conn, r, rule=rule, span=s) for r in runs for s in _SPANS}
        fast_div = {(r, s): DIV.channel_divergence(conn, rec, [r], rule=rule, span=s) for r in runs for s in _SPANS}
        fast_pooled = {s: DIV.channel_divergence(conn, rec, None, rule=rule, span=s) for s in _SPANS}
        _whole_reads(monkeypatch)
        for (r, s), got in fast.items():
            assert got == SB.channel_score(conn, r, rule=rule, span=s), f"channel_score run {r} span {s}"
        for (r, s), got in fast_div.items():
            assert got == DIV.channel_divergence(conn, rec, [r], rule=rule, span=s), f"divergence run {r} span {s}"
        for s, got in fast_pooled.items():
            assert got == DIV.channel_divergence(conn, rec, None, rule=rule, span=s), f"pooled divergence span {s}"
    finally:
        conn.close()


_S0, _S1 = SECTION
#: One case a section read could get wrong per channel, placed by hand at the
#: edges of SECTION — on the random channels a wrong bound can hide behind a
#: detection inside the section that overlaps the same labels. Each is
#: (labels, detections); a label is (start, end, verdict, source).
_EDGES = {
    # a window label ending past the section, overlapped only by a detection
    # that starts after it ends: the read is widened on by the longest label
    "label past the end": ([(_S1 - 100, _S1 + 500, "interesting", q.SOURCE_IMPORTED_10MIN)],
                           [(_S1 + 100, _S1 + 200), (_S0 + 900, _S0 + 950)]),
    # an event row inside, overlapped only by a detection that starts well
    # before the section: widened back by the longest detection
    "long detection from before": ([(_S0 + 200, _S0 + 260, "interesting", "excel_catalog")],
                                   [(_S0 - 5000, _S0 + 300)]),
    # under the loose rule an event before the section is claimed by a
    # detection further back (an earlier index at the same IoU, 0) over one
    # inside the section: the pairing is one-to-one over every detection
    "pairing across the start": ([(_S0 - 4000, _S0 - 3900, "interesting", "excel_catalog")],
                                 [(_S0 - 6000, _S0 - 5000), (_S0 + 3000, _S0 + 6600)]),
    # a matchable pair far outside the section, which must change nothing
    "far pair": ([(_S1 + 20_000, _S1 + 20_100, "not_interesting", "excel_catalog")],
                 [(_S1 + 20_000, _S1 + 20_090), (_S0 + 900, _S0 + 950)]),
    # no labels at all (nothing widens the read on), detections at the
    # section's first and last samples; with the fractional section (hours x
    # fs) the read must agree with the scope `channel_divergence` states
    "no labels, fractional end": ([], [(_S1, _S1 + 50), (_S0 - 1, _S0 + 20), (_S0 + 10, _S0 + 20)]),
}


def _edge_channel(case):
    labels, dets = _EDGES[case]
    conn = init_db(":memory:")
    rec = q.insert_recording(conn, "edge.mat", 0, 1.0, N, 0, "edge_CH0.npy")
    cfg, _ = run_db.get_or_create_config(conn, _STEPS)
    run = run_db.insert_run(conn, cfg, rec, 0, N, status="completed", started_at=_RUN_AT)
    for a, b, verdict, source in labels:
        q.insert_annotation(conn, rec, a, b, verdict, source, created_at=_BEFORE, commit=False)
        q.insert_reviewed_span(conn, rec, a, b, source, reviewed_at=_BEFORE, commit=False)
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                     [(run, a, b) for a, b in dets])
    conn.commit()
    return conn, rec, run


@pytest.mark.parametrize("span", [SECTION, (_S0 - 0.5, _S1 + 0.5)], ids=["whole samples", "fractional"])
@pytest.mark.parametrize("rule", _RULES, ids=["default", "loose", "strict-onset"])
@pytest.mark.parametrize("case", list(_EDGES))
def test_the_section_score_is_the_whole_read_at_the_edges(case, rule, span, monkeypatch):
    conn, rec, run = _edge_channel(case)
    try:
        fast = (SB.channel_score(conn, run, rule=rule, span=span),
                DIV.channel_divergence(conn, rec, [run], rule=rule, span=span),
                DIV.breakdown(conn, {rec: [run]}, bins=4, n_samples=N, span=span, rule=rule))
        _whole_reads(monkeypatch)
        assert fast[0] == SB.channel_score(conn, run, rule=rule, span=span)
        assert fast[1] == DIV.channel_divergence(conn, rec, [run], rule=rule, span=span)
        assert fast[2] == DIV.breakdown(conn, {rec: [run]}, bins=4, n_samples=N, span=span, rule=rule)
    finally:
        conn.close()


def test_the_prior_adjudications_are_read_in_one_stated_order():
    """The pairing breaks ties by reference index, so the order the prior
    spans come back in is part of the result; it is stated (oldest run, then
    detection), not left to the query plan."""
    conn, rec, runs = _random_channel(11)
    try:
        got = SB._prior_adjudicated(conn, rec, _AFTER)
        want = [absolute_bounds(r["start_idx"], r["end_idx"], r["span_start"]) for r in conn.execute(
            "SELECT d.start_idx, d.end_idx, r.span_start FROM adjudications a JOIN detections d "
            "ON d.id = a.detection_id JOIN runs r ON r.id = d.run_id WHERE r.recording_id = ? "
            "AND a.created_at < ? ORDER BY d.run_id, d.id", (rec, _AFTER))]
        assert got == want and got
    finally:
        conn.close()

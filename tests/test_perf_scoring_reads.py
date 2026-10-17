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
    assert steps[1] < 2 * steps[0], f"VM steps {steps[0]} -> {steps[1]} for 4x the detections"

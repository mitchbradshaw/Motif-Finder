"""
test_divergence.py
==================
fixup-X — divergence between the human record and a run, counted so that it
means something (QUESTIONS.md Q-D2, answered 2026-09-23: "(a) and (c)
together, reported as two numbers, each printing its own rule").

The fixture (fs = 1 Hz, so one sample is one second)
----------------------------------------------------
Recording R0 (channel 0), 10 000 samples. Run R is completed over
[0, 7200). Recording R1 (channel 1) carries one window label and no run.

Window labels (`source = imported_10min`, 600 samples — the CNN window set):

    W1  [   0,  600) interesting        D1 inside it
    W2  [ 600, 1200) not_interesting    D2 inside it
    W3  [1200, 1800) interesting        D9 inside it (adjudicated not_interesting)
    W4  [1800, 2400) not_interesting    D8 inside it (adjudicated interesting)
    W5  [2400, 3000) artifact           D3 inside it
    W6  [3000, 3600) unsure             D4 inside it
    W9  [4000, 4600) interesting  \\     D5 inside BOTH: the two windows
    W10 [4200, 4800) not_interesting /   disagree
    W11 [6000, 6600) interesting        silent (only the surrogate fires here)
    W12 [6600, 7200) not_interesting    silent
    W7  [8000, 8600) interesting        outside the run's span

Event-shaped rows (`source = excel_catalog`):

    E1  [5000, 5200) interesting        D6 matches it under §4.6 (IoU 0.95)
    E2  [5400, 5500) interesting        D7 overlaps it, IoU 0.2: no match
    E3  [5600, 9000) interesting        runs past the run's span

Detections of R:

    D1 [ 100,  300)   D2 [ 700,  900)   D3 [2500, 2700)   D4 [3100, 3300)
    D5 [4300, 4500)   D6 [5000, 5190)   D7 [5420, 5440)
    D8 [1900, 2100)  adjudicated interesting
    D9 [1300, 1500)  adjudicated not_interesting

A surrogate of R fires once at [6100, 6200), inside W11. It is never a
machine finding (fixup-T), so W11 stays silent.

The four cells, and the fifth that is not a cell
------------------------------------------------
Each detection is resolved adjudication first, then §4.6 extent against the
event-shaped rows, then containment in the window labels (a window that wholly
contains it; every containing window must agree — Q41's rule).

machine yes · human yes    D1 (containment) D6 (extent) D8 (adjudication)    3
machine yes · human no     D2 D3 (containment) D9 (adjudication)             3
machine no  · human yes    W11                                               1
machine no  · human no     W12                                               1
not comparable             D4 (unsure window) D5 (windows disagree)
                           D7 (no window, no event match)
                           W7, E3 (no run covered them)                      5

A label a detection overlaps is represented by that detection and is not
counted again (W1-W6, W9, W10, E1, E2).

The two precision figures
-------------------------
(a) containment: adjudication, else the containing windows.
    yes D1 D8 · no D2 D3 D9 · unscored D4 D5 D6 D7      -> 2 / 5 = 0.40
(c) extent: adjudication, else §4.6 against the event rows; a detection that
    overlaps an event row without matching it got the extent wrong.
    yes D6 D8 · no D7 D9 · unscored D1-D5               -> 2 / 4 = 0.50
    the denominator's event rows inside the run's span: E1 (200), E2 (100)
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import adjudications as adj
from Working.database import queries as q
from Working.database import runs as run_db
from Working.database import vocabulary as vocab
from Working.database.schema import init_db

WINDOWS = {
    "W1": (0, 600, "interesting"), "W2": (600, 1200, "not_interesting"),
    "W3": (1200, 1800, "interesting"), "W4": (1800, 2400, "not_interesting"),
    "W5": (2400, 3000, "artifact"), "W6": (3000, 3600, "unsure"),
    "W9": (4000, 4600, "interesting"), "W10": (4200, 4800, "not_interesting"),
    "W11": (6000, 6600, "interesting"), "W12": (6600, 7200, "not_interesting"),
    "W7": (8000, 8600, "interesting"),
}
EVENTS = {"E1": (5000, 5200, "interesting"), "E2": (5400, 5500, "interesting"),
          "E3": (5600, 9000, "interesting")}
DETECTIONS = {"D1": (100, 300), "D2": (700, 900), "D3": (2500, 2700), "D4": (3100, 3300),
              "D5": (4300, 4500), "D6": (5000, 5190), "D7": (5420, 5440),
              "D8": (1900, 2100), "D9": (1300, 1500)}
BEFORE = "2026-09-01T00:00:00"
AFTER = "2026-09-20T00:00:00"


def _run(conn, recording_id, span, status="completed"):
    config_id, _ = run_db.get_or_create_config(
        conn, {"steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]})
    return run_db.insert_run(conn, config_id, recording_id, span[0], span[1],
                             started_at=AFTER, status=status)


@pytest.fixture
def db():
    conn = init_db(":memory:")
    vocab.seed_vocabulary(conn)
    rec = q.insert_recording(conn, "fixture.mat", 0, 1.0, 10_000, 0, "fixture_CH0.npy")
    rec1 = q.insert_recording(conn, "fixture.mat", 1, 1.0, 10_000, 0, "fixture_CH1.npy")
    ann = {}
    for name, (a, b, v) in WINDOWS.items():
        ann[name] = q.insert_annotation(conn, rec, a, b, v, q.SOURCE_IMPORTED_10MIN, created_at=BEFORE)
        q.insert_reviewed_span(conn, rec, a, b, q.SOURCE_IMPORTED_10MIN, reviewed_at=BEFORE)
    for name, (a, b, v) in EVENTS.items():
        ann[name] = q.insert_annotation(conn, rec, a, b, v, "excel_catalog", created_at=BEFORE)
        q.insert_reviewed_span(conn, rec, a, b, "excel_catalog", reviewed_at=BEFORE)
    ann["R1W"] = q.insert_annotation(conn, rec1, 0, 600, "interesting", q.SOURCE_IMPORTED_10MIN, created_at=BEFORE)
    vocab.add_annotation_tag(conn, ann["W11"], "element", "sharkfin")
    run_id = _run(conn, rec, (0, 7200))
    det = {name: run_db.insert_detection(conn, run_id, a, b, score=0.9)
           for name, (a, b) in DETECTIONS.items()}
    adj.insert_adjudication(conn, det["D8"], "interesting")
    adj.insert_adjudication(conn, det["D9"], "not_interesting")
    null_id = _run(conn, rec, (0, 7200))
    run_db.insert_detection(conn, null_id, 6100, 6200, score=0.5)
    run_db.update_run(conn, null_id, surrogate_of_run_id=run_id)
    yield {"conn": conn, "rec": rec, "rec1": rec1, "run": run_id, "null": null_id, "det": det, "ann": ann}
    conn.close()


def _divergence():
    from Working.discovery import divergence
    return divergence


# ── the four cells and the fifth ────────────────────────────────────────────

def test_the_four_cells_and_the_not_comparable_count(db):
    out = _divergence().channel_divergence(db["conn"], db["rec"], [db["run"]])
    assert out["cells"] == {"machine_yes_human_yes": 3, "machine_yes_human_no": 3,
                            "machine_no_human_yes": 1, "machine_no_human_no": 1}
    assert out["not_comparable"]["n"] == 5


def test_each_detection_says_which_rule_resolved_it(db):
    out = _divergence().channel_divergence(db["conn"], db["rec"], [db["run"]])
    by_id = {it["id"]: it for it in out["items"] if it["kind"] == "detection"}
    d = db["det"]
    assert by_id[d["D1"]]["by"] == "containment" and by_id[d["D1"]]["cell"] == "machine_yes_human_yes"
    assert by_id[d["D6"]]["by"] == "extent" and by_id[d["D6"]]["cell"] == "machine_yes_human_yes"
    assert by_id[d["D8"]]["by"] == "adjudication" and by_id[d["D8"]]["cell"] == "machine_yes_human_yes"
    assert by_id[d["D9"]]["by"] == "adjudication" and by_id[d["D9"]]["cell"] == "machine_yes_human_no"
    assert by_id[d["D3"]]["cell"] == "machine_yes_human_no", "artifact is a human no"
    for name, reason in (("D4", "no verdict"), ("D5", "windows disagree"), ("D7", "no human verdict here")):
        assert by_id[d[name]]["cell"] == "not_comparable"
        assert reason in by_id[d[name]]["reason"], (name, by_id[d[name]]["reason"])


def test_an_unreviewed_or_uncovered_place_is_never_a_disagreement(db):
    out = _divergence().channel_divergence(db["conn"], db["rec"], [db["run"]])
    labels = {it["id"]: it for it in out["items"] if it["kind"] == "label"}
    a = db["ann"]
    assert labels[a["W11"]]["cell"] == "machine_no_human_yes"
    assert labels[a["W12"]]["cell"] == "machine_no_human_no"
    for name in ("W7", "E3"):
        assert labels[a[name]]["cell"] == "not_comparable"
        assert "no run covered it" in labels[a[name]]["reason"]
    # a label a detection overlaps is represented by the detection, not counted twice
    for name in ("W1", "W2", "W3", "W4", "W5", "W6", "W9", "W10", "E1", "E2"):
        assert a[name] not in labels


def test_a_surrogate_detection_is_never_a_machine_finding(db):
    out = _divergence().channel_divergence(db["conn"], db["rec"], [db["run"], db["null"]])
    assert db["null"] not in out["run_ids"]
    assert out["cells"]["machine_no_human_yes"] == 1     # W11 stays silent


def test_a_channel_no_run_touched_is_all_not_comparable(db):
    out = _divergence().channel_divergence(db["conn"], db["rec1"], None)
    assert out["run_ids"] == []
    assert sum(out["cells"].values()) == 0
    assert out["not_comparable"]["n"] == 1


def test_with_no_run_chosen_it_pools_every_real_run_and_says_so(db):
    out = _divergence().channel_divergence(db["conn"], db["rec"], None)
    assert out["run_ids"] == [db["run"]]
    assert out["pooled"] is True
    assert out["cells"]["machine_yes_human_yes"] == 3


# ── adjudications count ─────────────────────────────────────────────────────

def test_judging_five_detections_moves_the_cells_by_exactly_five(db):
    conn, d = db["conn"], db["det"]
    before = _divergence().channel_divergence(conn, db["rec"], [db["run"]])
    for name, v in (("D1", "not_interesting"), ("D2", "interesting"), ("D4", "interesting"),
                    ("D5", "artifact"), ("D7", "seed")):
        adj.insert_adjudication(conn, d[name], v)
    after = _divergence().channel_divergence(conn, db["rec"], [db["run"]])
    # D1 yes->no, D2 no->yes, D4 nc->yes, D5 nc->no, D7 nc->yes
    assert after["cells"]["machine_yes_human_yes"] == before["cells"]["machine_yes_human_yes"] - 1 + 1 + 1 + 1
    assert after["cells"]["machine_yes_human_no"] == before["cells"]["machine_yes_human_no"] + 1 - 1 + 1
    assert after["not_comparable"]["n"] == before["not_comparable"]["n"] - 3
    moved = [it for it in after["items"] if it["kind"] == "detection" and it["by"] == "adjudication"]
    assert len(moved) == 7


# ── Q-D2's two numbers, each printing its own rule ──────────────────────────

def test_containment_precision_over_the_window_labels(db):
    p = _divergence().channel_divergence(db["conn"], db["rec"], [db["run"]])["precision"]["containment"]
    assert p["yes"] == 2 and p["judged"] == 5
    assert p["value"] == pytest.approx(0.4)
    assert p["by_adjudication"] == 2
    assert "contain" in p["rule"].lower()


def test_extent_precision_over_the_event_rows_prints_its_widths(db):
    p = _divergence().channel_divergence(db["conn"], db["rec"], [db["run"]])["precision"]["extent"]
    assert p["yes"] == 2 and p["judged"] == 4
    assert p["value"] == pytest.approx(0.5)
    assert "iou" in p["rule"].lower()
    w = p["widths"]
    assert w["n"] == 2 and w["min"] == 100 and w["max"] == 200 and w["median"] == 150


def test_a_figure_with_no_denominator_is_words_not_zero(db):
    out = _divergence().channel_divergence(db["conn"], db["rec1"], None)
    for key in ("containment", "extent"):
        assert out["precision"][key]["value"] is None
        assert out["precision"][key]["note"]


# ── the core queries have callers and condition on what they must ───────────

def test_the_core_queries_condition_on_runs_and_verdict(db):
    conn = db["conn"]
    silent_yes = q.divergence_annotations_without_detection(
        conn, db["rec"], run_ids=[db["run"]], verdicts=("interesting", "seed"))
    assert [r["id"] for r in silent_yes] == [db["ann"]["W11"]]
    rejected = q.divergence_rejected_detections(conn, db["rec"], run_ids=[db["run"]],
                                                verdicts=("not_interesting", "artifact"))
    assert [r["id"] for r in rejected] == [db["det"]["D9"]]


# ── the breakdown ───────────────────────────────────────────────────────────

def test_the_breakdown_by_channel_time_and_morphology(db):
    out = _divergence().breakdown(db["conn"], {db["rec"]: [db["run"]], db["rec1"]: []}, bins=10,
                                  n_samples=10_000)
    ch0 = next(r for r in out["by_channel"] if r["recording_id"] == db["rec"])
    assert ch0["machine_yes_human_no"] == 3 and ch0["machine_no_human_yes"] == 1
    assert sum(b["machine_yes_human_no"] for b in out["by_time"]) == 3
    assert sum(b["machine_no_human_yes"] for b in out["by_time"]) == 1
    # W11 (machine silent, human yes) carries the human `element` tag sharkfin
    human = {r["tag"]: r for r in out["by_morphology"]["human"]}
    assert human["sharkfin"]["machine_no_human_yes"] == 1
    assert out["by_morphology"]["machine"] == []
    assert out["by_morphology"]["machine_note"]
    assert out["structure_note"], "the page must say there is no test of structure and no null"


# ── Explore › Corpus reads it ───────────────────────────────────────────────

def test_explore_disagree_is_the_two_cells_on_the_runs_picked(db):
    from webui.server import corpus
    cov = corpus.coverage(db["conn"], "fixture.mat", bins=10, run_ids=[db["run"]])
    r0 = next(r for r in cov["rows"] if r["id"] == db["rec"])
    r1 = next(r for r in cov["rows"] if r["id"] == db["rec1"])
    assert r0["counts"]["disagree"] == 4
    assert r0["counts"]["divergence"]["machine_yes_human_no"] == 3
    assert r0["counts"]["divergence"]["machine_no_human_yes"] == 1
    assert r0["counts"]["divergence"]["not_comparable"] == 5
    assert sum(r0["disagree"]) == 4
    assert r1["counts"]["disagree"] == 0 and sum(r1["disagree"]) == 0
    assert r1["counts"]["divergence"]["not_comparable"] == 1
    assert cov["divergence"]["pooled"] is False


def test_explore_with_no_run_picked_says_what_it_pools(db):
    from webui.server import corpus
    cov = corpus.coverage(db["conn"], "fixture.mat", bins=10)
    assert cov["divergence"]["pooled"] is True
    assert "1 run" in cov["divergence"]["scope"]


# ── the scoreboard carries both figures ─────────────────────────────────────

def test_the_scoreboard_row_carries_both_precision_figures(db):
    from Working.discovery.scoreboard import channel_score, run_total
    row = channel_score(db["conn"], db["run"])
    assert row["precisions"]["containment"]["value"] == pytest.approx(0.4)
    assert row["precisions"]["extent"]["value"] == pytest.approx(0.5)
    total = run_total(db["conn"], [db["run"]], rows=[row])
    assert total["precisions"]["containment"]["judged"] == 5
    assert total["precisions"]["extent"]["widths"]["n"] == 2


# ── Compare with the human record as a side ─────────────────────────────────

def test_compare_with_the_human_side_pairs_by_the_divergence_not_iou_alone(db):
    D = _divergence()
    div = D.channel_divergence(db["conn"], db["rec"], [db["run"]])
    a = db["ann"]
    human = [a[n] for n in ("W1", "W3", "W9", "W11", "E1", "E2")]       # the human-yes spans
    dets = [db["det"][n] for n in sorted(DETECTIONS)]
    m = D.human_pairing(div, human, dets, human_is_a=True)
    # both: D1 (in W1), D6 (E1), D8 (accepted in Review, no yes span under it)
    assert m["counts"]["both"] == 3
    # only human: W3 (its detection D9 was rejected), W9 (D5's windows disagree),
    # W11 (silent), E2 (D7 overlaps it without matching)
    assert sorted(human[j] for j in m["only_a"]) == sorted([a["W3"], a["W9"], a["W11"], a["E2"]])
    assert m["counts"]["only_b"] == len(DETECTIONS) - 3

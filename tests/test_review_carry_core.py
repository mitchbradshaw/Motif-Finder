"""
test_review_carry_core.py
=========================
review-carry (2026-10-18): one judgement per event.

* **Within a run** overlapping detections of one detector on one channel are ONE
  Review item (the transitive closure of pairwise overlap), and the verdict given
  to it is written to every detection in the set.
* **Across runs** a human verdict on detection A is written, as a carried
  adjudication row (`carried_from` = A's row, note "carried from detection A
  (rule ...)"), to every other detection on the same channel that is the same
  event by the scoreboard's matching rule (`Working.discovery.matching`), unless
  that detection already has a row of its own. Undo takes back exactly the
  carried rows the verdict wrote.
* The class label given in Review is stored on the row (`class_label`).

Core only (no FastAPI): runs under the conda pytest.
"""
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as _queries  # noqa: E402
from Working.database.adjudications import insert_adjudication  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.review import queues as Q  # noqa: E402
from Working.review import verdicts as V  # noqa: E402

NOW = "2026-10-18T09:00:00+00:00"


def _db(tmp_path, name="c.sqlite"):
    """Run A (channel 0): a1-a3 overlap in a chain (a1~a2, a2~a3, a1 !~ a3), a4 alone.
    Run B (channel 0): b1 is a1's event by the rule, b2 is a4's, b3 and b4 are nobody's.
    Run C (channel 1): c1 sits at a1's samples on ANOTHER channel.
    Run S: a paired surrogate of A on channel 0, s1 at a1's samples (a null draw, never judged)."""
    conn = init_db(str(tmp_path / name))
    recs = [conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                         "VALUES ('A_concat_fs1.mat', ?, 1.0, 100000, 0, 'x.npy', 'mV')", (ch,)).lastrowid
            for ch in range(2)]
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('c', '{}', ?)",
                       (NOW,)).lastrowid

    def run(rec, surrogate_of=None):
        return conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                            "surrogate_of_run_id) VALUES (?, ?, 0, 100000, ?, 'completed', ?)",
                            (cfg, rec, NOW, surrogate_of)).lastrowid

    def det(rid, a, b, score=0.5):
        return conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                            (rid, a, b, score)).lastrowid

    ra, rb, rc = run(recs[0]), run(recs[0]), run(recs[1])
    rs = run(recs[0], surrogate_of=ra)
    d = {
        "a1": det(ra, 1000, 1100), "a2": det(ra, 1050, 1150), "a3": det(ra, 1140, 1200), "a4": det(ra, 5000, 5100),
        "b1": det(rb, 1005, 1105), "b2": det(rb, 5000, 5100), "b3": det(rb, 8000, 8100), "b4": det(rb, 1300, 1400),
        "c1": det(rc, 1000, 1100),
        "s1": det(rs, 1000, 1100),
    }
    conn.commit()
    return conn, {"recs": recs, "ra": ra, "rb": rb, "rc": rc, "rs": rs, "d": d}


def _adj(conn, did):
    return conn.execute("SELECT * FROM adjudications WHERE detection_id = ?", (did,)).fetchone()


# ── the core module ────────────────────────────────────────────────────────

def test_overlap_sets_are_the_transitive_closure_of_any_overlap():
    from Working.review.overlap import overlap_sets
    dets = [(1, 1000, 1100), (2, 1050, 1150), (3, 1140, 1200), (4, 5000, 5100), (5, 1200, 1300)]
    sets = overlap_sets(dets)
    # 1~2 and 2~3 chain 1 to 3; 5 starts where 3 ends ([start, end) intervals): touching is not overlapping
    assert sorted(sorted(s) for s in sets) == [[1, 2, 3], [4], [5]]
    assert all(isinstance(s, set) for s in sets)
    # dicts in the detections-row shape are read the same way
    assert sorted(sorted(s) for s in overlap_sets(
        [{"id": i, "start_idx": a, "end_idx": b} for i, a, b in dets])) == [[1, 2, 3], [4], [5]]
    assert overlap_sets([]) == []


def test_same_event_is_the_scoreboards_rule():
    from Working.discovery.matching import spans_match
    from Working.review.overlap import same_event
    for cand, ref in (((1005, 1105), (1000, 1100)), ((1050, 1150), (1000, 1100)), ((1000, 1100), (1000, 1400))):
        assert same_event(cand, ref) == spans_match(cand, ref)
    assert same_event((1005, 1105), (1000, 1100)) is True
    assert same_event((1050, 1150), (1000, 1100)) is False


def test_init_db_twice_adds_the_two_columns_once(tmp_path):
    path = str(tmp_path / "twice.sqlite")
    init_db(path).close()
    conn = init_db(path)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(adjudications)")]
    assert cols.count("carried_from") == 1 and cols.count("class_label") == 1


# ── within a run: one item per overlap set ─────────────────────────────────

def test_a_detection_queue_serves_one_item_per_overlap_set(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qid = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    items = Q.queue_items(conn, qid, include_judged=True)
    assert [it["target_id"] for it in items] == [d["a1"], d["a4"]]
    assert items[0]["members"] == [d["a1"], d["a2"], d["a3"]]
    assert items[1]["members"] == [d["a4"]]
    # the set's item spans the whole event
    assert (items[0]["start_idx"], items[0]["end_idx"]) == (1000, 1200)
    assert Q.queue_counts(conn, qid) == {"total": 2, "judged": 0, "remaining": 2}
    # a set never crosses runs or channels: run B and C's detections at the same samples are their own items
    qall = Q.create_queue(conn, name="all", source_kind="discovery-run",
                          filters={"run_ids": [info["ra"], info["rb"], info["rc"]]})
    by_target = {it["target_id"]: it["members"] for it in Q.queue_items(conn, qall, include_judged=True)}
    assert by_target[d["b1"]] == [d["b1"]] and by_target[d["c1"]] == [d["c1"]]
    assert by_target[d["a1"]] == [d["a1"], d["a2"], d["a3"]]


def test_a_verdict_on_a_set_writes_every_member_and_one_undo_takes_it_back(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qid = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    out = V.write_verdict(conn, qid, d["a1"], "interesting")
    assert out["members"] == [d["a1"], d["a2"], d["a3"]]
    for k in ("a1", "a2", "a3"):
        row = _adj(conn, d[k])
        assert row["verdict"] == "interesting" and row["carried_from"] is None
    assert _adj(conn, d["a4"]) is None
    assert Q.queue_counts(conn, qid) == {"total": 2, "judged": 1, "remaining": 1}
    V.undo_last(conn, qid)
    assert all(_adj(conn, d[k]) is None for k in ("a1", "a2", "a3", "b1"))


# ── across runs: the verdict carries ───────────────────────────────────────

def test_a_carried_verdict_reaches_exactly_the_detections_the_rule_matches(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qid = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    out = V.write_verdict(conn, qid, d["a1"], "interesting")
    # b1 is a1's event; a2/a3 are judged as members, not carried; c1 is another channel; s1 a null draw;
    # b2-b4 are nobody's event
    assert out["carried"] == [d["b1"]]
    row = _adj(conn, d["b1"])
    src = _adj(conn, d["a1"])
    assert row["verdict"] == "interesting"
    assert row["carried_from"] == src["id"]
    assert row["note"].startswith(f"carried from detection {d['a1']} (rule ")
    for k in ("b2", "b3", "b4", "c1", "s1"):
        assert _adj(conn, d[k]) is None, k
    # a carried row does not carry on: nothing beyond b1 was written
    n = conn.execute("SELECT COUNT(*) FROM adjudications WHERE carried_from IS NOT NULL").fetchone()[0]
    assert n == 1


def test_carry_verdict_called_directly_finds_the_same_rows(tmp_path):
    from Working.review.overlap import carry_verdict, uncarry
    conn, info = _db(tmp_path)
    d = info["d"]
    adj_id = insert_adjudication(conn, d["a4"], "artifact")
    assert carry_verdict(conn, adj_id) == [d["b2"]]
    assert _adj(conn, d["b2"])["carried_from"] == adj_id
    assert carry_verdict(conn, adj_id) == [d["b2"]], "carrying twice rewrites its own row, it does not duplicate"
    assert conn.execute("SELECT COUNT(*) FROM adjudications WHERE detection_id = ?", (d["b2"],)).fetchone()[0] == 1
    assert uncarry(conn, adj_id) == [d["b2"]]
    assert _adj(conn, d["b2"]) is None and _adj(conn, d["a4"]) is not None


def test_an_existing_human_row_is_never_overwritten(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    human = insert_adjudication(conn, d["b2"], "artifact", note="mine")
    qid = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    out = V.write_verdict(conn, qid, d["a4"], "interesting")
    assert out["carried"] == []
    row = _adj(conn, d["b2"])
    assert (row["id"], row["verdict"], row["note"], row["carried_from"]) == (human, "artifact", "mine", None)


def test_a_human_verdict_on_a_carried_row_makes_it_human_and_undo_leaves_it(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    qb = Q.create_queue(conn, name="B", source_kind="discovery-run", filters={"run_ids": [info["rb"]]})
    V.write_verdict(conn, qa, d["a1"], "interesting")
    assert _adj(conn, d["b1"])["carried_from"] is not None
    V.write_verdict(conn, qb, d["b1"], "not_interesting")
    assert _adj(conn, d["b1"])["carried_from"] is None
    V.undo_last(conn, qa)
    row = _adj(conn, d["b1"])
    assert row is not None and row["verdict"] == "not_interesting", "the undo took back a human verdict"


def test_undo_removes_exactly_the_rows_its_verdict_wrote(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    V.write_verdict(conn, qa, d["a4"], "artifact")           # carries to b2
    V.write_verdict(conn, qa, d["a1"], "interesting")        # carries to b1
    V.write_verdict(conn, qa, d["a1"], "unsure")             # re-judged: b1's carried row follows
    assert _adj(conn, d["b1"])["verdict"] == "unsure"
    V.undo_last(conn, qa)                                    # back to interesting, b1 too
    assert _adj(conn, d["a1"])["verdict"] == "interesting"
    assert _adj(conn, d["b1"])["verdict"] == "interesting"
    V.undo_last(conn, qa)                                    # a1 unjudged: b1's row goes, b2's stays
    assert _adj(conn, d["a1"]) is None and _adj(conn, d["b1"]) is None
    assert _adj(conn, d["b2"])["verdict"] == "artifact"


def test_a_batch_carries_and_its_undo_uncarries(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    out = V.write_batch(conn, qa, [d["a1"], d["a4"]], "not_interesting")
    assert sorted(out["carried"]) == sorted([d["b1"], d["b2"]])
    assert out["count"] == 4, "a batch over two sets writes their four detections"
    V.undo_last(conn, qa)
    assert conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == 0


def test_the_second_runs_queue_no_longer_asks(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    qb = Q.create_queue(conn, name="B", source_kind="discovery-run", filters={"run_ids": [info["rb"]]})
    assert d["b1"] in [it["target_id"] for it in Q.queue_items(conn, qb)]
    V.write_verdict(conn, qa, d["a1"], "interesting")
    assert d["b1"] not in [it["target_id"] for it in Q.queue_items(conn, qb)]
    item = next(it for it in Q.queue_items(conn, qb, include_judged=True) if it["target_id"] == d["b1"])
    assert item["judged"] and item["verdict"] == "interesting"
    assert item["carried_from_detection"] == d["a1"]


# ── R3: the class label is stored ──────────────────────────────────────────

def test_the_class_label_is_stored_carried_and_served(tmp_path):
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    V.write_verdict(conn, qa, d["a1"], "interesting", class_label="burst")
    assert _adj(conn, d["a1"])["class_label"] == "burst"
    assert _adj(conn, d["a2"])["class_label"] == "burst"
    assert _adj(conn, d["b1"])["class_label"] == "burst"
    item = Q.item_view(conn, qa, d["a1"])["item"]
    assert item["class_label"] == "burst"
    # a re-judgement without a class clears it (the Inspector sends the class it shows)
    V.write_verdict(conn, qa, d["a1"], "interesting")
    assert _adj(conn, d["a1"])["class_label"] is None
    V.undo_last(conn, qa)
    assert _adj(conn, d["a1"])["class_label"] == "burst", "undo restores the class with the verdict"


# ── AR: a verdict, carried or not, leaves every remembered structure standing ──

def test_a_verdict_plain_or_carried_rebuilds_no_structure_and_every_queue_reads_right(tmp_path, monkeypatch):
    """The structure reads no adjudication (verdicts and carried rows are the overlay, read fresh), so neither a
    plain verdict nor one that carries may rebuild it: a carried verdict rebuilding every open queue's structure
    is the cold read AR removed (22 s for 20 queues on the scale fixture), after every verdict on a channel with
    several runs. Every queue's items and counts must still equal a fresh resolve on the next read."""
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    qb = Q.create_queue(conn, name="B", source_kind="discovery-run", filters={"run_ids": [info["rb"]]})
    qab = Q.create_queue(conn, name="AB", source_kind="discovery-run",
                         filters={"run_ids": [info["ra"], info["rb"]]})
    queues = (qa, qb, qab)
    calls = {"n": 0}
    real = _queries.queue_candidates

    def counted(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    def reads():
        return {q: (Q.queue_items(conn, q, include_judged=True), Q.queue_items(conn, q), Q.queue_counts(conn, q),
                    Q.item_view(conn, q, Q.queue_items(conn, q, include_judged=True)[0]["target_id"])["counts"])
                for q in queues}

    def fresh():
        Q.clear_resolver_cache()
        monkeypatch.setattr(_queries, "queue_candidates", real)
        out = reads()
        monkeypatch.setattr(_queries, "queue_candidates", counted)
        return out

    monkeypatch.setattr(_queries, "queue_candidates", counted)
    Q.clear_resolver_cache()
    reads()
    built = calls["n"]
    assert built == 3
    V.write_verdict(conn, qb, d["b3"], "unsure")              # carries nothing
    cached = reads()
    assert calls["n"] == built, "a plain verdict rebuilt a structure"
    assert cached == fresh()
    calls["n"] = built = 0
    reads()
    out = V.write_verdict(conn, qa, d["a1"], "interesting")   # carries to b1
    assert out["carried"] == [d["b1"]]
    cached = reads()
    assert calls["n"] == 0, "a carried verdict rebuilt a structure (it reads no adjudication)"
    assert cached == fresh()
    # and the carried row is seen: run B's queue no longer asks about b1, the joint queue counts it judged
    assert d["b1"] not in [it["target_id"] for it in cached[qb][1]]
    assert cached[qab][2]["judged"] == 3                      # a1's set, b1 (carried), b3


# ── the rule's edge: a near miss is not carried ────────────────────────────

def test_a_near_miss_by_the_rule_is_not_carried_and_a_near_hit_is(tmp_path):
    """The carry reaches exactly what `matching.spans_match` matches: one detection just inside the onset
    tolerance (carried), one just outside it, one with the onset exact but IoU just under the threshold."""
    from Working.discovery.matching import spans_match
    conn, info = _db(tmp_path)
    rec0 = info["recs"][0]
    cfg = conn.execute("SELECT id FROM configs").fetchone()[0]

    def run():
        return conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                            "VALUES (?, ?, 0, 100000, ?, 'completed')", (cfg, rec0, NOW)).lastrowid

    def det(rid, a, b):
        return conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 0.5)",
                            (rid, a, b)).lastrowid

    src_run = run()
    src = det(src_run, 20000, 20100)
    hit = det(run(), 20025, 20125)        # onset gap 25 = 0.25 x 100: inside; IoU 75/125 = 0.6
    late = det(run(), 20026, 20126)       # onset gap 26 > 25: outside
    wide = det(run(), 20000, 20201)       # onset exact; IoU 100/201 < 0.5
    conn.commit()
    ref = (20000, 20100)
    assert spans_match((20025, 20125), ref) and not spans_match((20026, 20126), ref) \
        and not spans_match((20000, 20201), ref)
    qs = Q.create_queue(conn, name="S", source_kind="discovery-run", filters={"run_ids": [src_run]})
    out = V.write_verdict(conn, qs, src, "interesting")
    assert out["carried"] == [hit]
    assert _adj(conn, late) is None and _adj(conn, wide) is None


# ── a sliding-window detector does not chain a run into one item ───────────

def test_a_sliding_window_chain_is_cut_into_event_sized_sets():
    """Transitive closure of any overlap is the rule, but a detector emitting a window every hop (hop < window)
    chains for as long as it keeps firing: one "item" spanned hours and dozens of events, and one key press wrote
    a verdict on all of them — and carried each. A set is cut where it would grow longer than twice its longest
    detection; a set within that bound (every set the rule was decided on) is unchanged."""
    from Working.review.overlap import overlap_sets
    windows = [(i, i * 150, i * 150 + 600) for i in range(40)]          # 40 windows of 600, hop 150: one chain
    sets = overlap_sets(windows)
    spans = {i: (a, b) for i, a, b in windows}
    assert len(sets) > 1
    for s in sets:
        ext = max(spans[i][1] for i in s) - min(spans[i][0] for i in s)
        assert ext <= 2 * 600, (sorted(s), ext)
    assert sorted(i for s in sets for i in s) == list(range(40)), "every window is in exactly one set"
    # a set within the bound is the transitive closure, as before
    assert sorted(sorted(s) for s in overlap_sets([(1, 1000, 1100), (2, 1050, 1150), (3, 1140, 1200)])) == [[1, 2, 3]]


# ── the scoreboard counts a carried verdict as a human one ────────────────

def test_a_carried_interesting_raises_the_second_runs_precision_as_a_hand_written_one_would(tmp_path):
    from Working.discovery import scoreboard as SB
    carried, info = _db(tmp_path, "carried.sqlite")
    qa = Q.create_queue(carried, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    V.write_verdict(carried, qa, info["d"]["a1"], "interesting")
    by_hand, info2 = _db(tmp_path, "hand.sqlite")
    insert_adjudication(by_hand, info2["d"]["b1"], "interesting")
    untouched, info3 = _db(tmp_path, "none.sqlite")

    def prec(conn, rb):
        SB.clear_score_cache()
        return SB.channel_score(conn, rb)["precisions"]

    assert prec(carried, info["rb"]) == prec(by_hand, info2["rb"])
    assert prec(carried, info["rb"]) != prec(untouched, info3["rb"])


def test_a_seed_is_the_named_detection_only_its_set_and_carried_rows_take_interesting(tmp_path):
    """`seed` is the one detection promoted to the Library (P21: it implies interesting). The rest of its set and
    the rows it carries are the same event but not the exemplar: they are written `interesting`, never a sixth
    word and never a seed with no Library entry behind it."""
    conn, info = _db(tmp_path)
    d = info["d"]
    qa = Q.create_queue(conn, name="A", source_kind="discovery-run", filters={"run_ids": [info["ra"]]})
    V.write_verdict(conn, qa, d["a1"], "seed")
    assert _adj(conn, d["a1"])["verdict"] == "seed"
    assert _adj(conn, d["a2"])["verdict"] == "interesting"
    assert _adj(conn, d["b1"])["verdict"] == "interesting"

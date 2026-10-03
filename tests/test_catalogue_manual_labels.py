"""
test_catalogue_manual_labels.py
================================
fixup-aa: the manual-label arm of RQ1 — `catalogue.manual_labels`, a
`WindowSet -> Grouping` block that turns the HUMAN verdicts already in the
store (`annotations`, `window_verdicts`) into one label per window.

The rule is the researcher's (QUESTIONS.md Q41 + Round 10 Q-W1, 2026-10-03):

* classes: `interesting` (with `seed`, a subset of it) vs `not_interesting`;
  `artifact` excluded and counted;
* a window takes a label only if it WHOLLY CONTAINS at least one labelled span
  and every span it wholly contains agrees — a span it only partly overlaps does
  not label it; disagreement is left out and counted;
* a window wholly INSIDE a longer `not_interesting` span is `not_interesting`;
  wholly inside a longer `interesting` span it is unlabelled (the event could be
  anywhere in it);
* time nobody labelled is unlabelled, never `not_interesting`;
* a training set keeps no two overlapping windows, LABELLED WINDOWS FIRST (each
  kept unless it overlaps one already kept, then unlabelled windows fill the
  gaps), the dropped counted. Q-W1 first said one phase of the 600/200 grid;
  measured on the 16 M2_aug channels that kept 3,906 of 11,110 labelled windows
  against 10,077 for labelled-first, and the researcher chose labelled-first
  (2026-10-03, Q-W1 revised).

Labels in the emitted Grouping: 1 = interesting, 0 = not_interesting, -1 =
excluded (unlabelled, artifact, conflicting, dropped for overlap) — so the
Grouping lines up with the WindowSet window for window, and the classifier
trains on the labelled windows only and says so.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_catalogue_manual_labels.py -q
"""

import datetime as _dt
import inspect
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.recipes import make_recipe  # noqa: E402

discover_adapters()

NAME = "catalogue.manual_labels"


def _ml():
    import Adapters.catalogue_manual_labels as ml
    return ml


def _fates(result):
    return list(result.fate)


# ── the rule, as a pure function ────────────────────────────────────────────

def test_a_window_that_wholly_contains_one_labelled_span_takes_its_label():
    ml = _ml()
    r = ml.label_windows([0, 600], 600, [(0, 600, "interesting"), (600, 1200, "not_interesting")])
    assert list(r.labels) == [1, 0]
    assert _fates(r) == ["interesting", "not_interesting"]


def test_seed_is_interesting():
    ml = _ml()
    r = ml.label_windows([0], 600, [(100, 300, "seed")])
    assert list(r.labels) == [1]
    assert r.counts["seed"] == 1, "seed is counted as the subset of interesting it is"


def test_a_span_the_window_only_partly_overlaps_does_not_label_it():
    """The researcher's reason: an interesting span whose event sits at its far
    end must not label a window that misses the end."""
    ml = _ml()
    r = ml.label_windows([200], 600, [(0, 600, "interesting")])
    assert list(r.labels) == [-1]
    assert _fates(r) == ["unlabelled"]


def test_contained_spans_that_disagree_leave_the_window_out_and_are_counted():
    ml = _ml()
    r = ml.label_windows([0], 600, [(0, 100, "interesting"), (300, 400, "not_interesting")])
    assert list(r.labels) == [-1]
    assert _fates(r) == ["conflicting"]
    assert r.counts["conflicting"] == 1


def test_contained_spans_that_agree_label_the_window():
    ml = _ml()
    r = ml.label_windows([0], 600, [(0, 100, "interesting"), (300, 400, "seed")])
    assert list(r.labels) == [1]


def test_a_window_inside_a_longer_not_interesting_span_is_not_interesting():
    ml = _ml()
    r = ml.label_windows([1000], 60, [(0, 5000, "not_interesting")])
    assert list(r.labels) == [0]


def test_a_window_inside_a_longer_interesting_span_is_unlabelled():
    """Q-W1: the event could be anywhere in the long span."""
    ml = _ml()
    r = ml.label_windows([1000], 60, [(0, 5000, "interesting")])
    assert list(r.labels) == [-1]
    assert _fates(r) == ["unlabelled"]


def test_time_nobody_labelled_is_unlabelled_never_not_interesting():
    ml = _ml()
    r = ml.label_windows([0, 600, 1200], 600, [(600, 1200, "interesting")])
    assert list(r.labels) == [-1, 1, -1]
    assert r.counts["unlabelled"] == 2
    assert r.counts["not_interesting"] == 0


def test_artifact_windows_are_excluded_and_counted():
    ml = _ml()
    r = ml.label_windows([0, 600], 600, [(0, 600, "artifact"), (600, 1200, "interesting")])
    assert list(r.labels) == [-1, 1]
    assert _fates(r) == ["artifact", "interesting"]
    assert r.counts["artifact"] == 1


def test_the_fates_partition_every_window():
    ml = _ml()
    spans = [(0, 600, "interesting"), (600, 1200, "not_interesting"), (1200, 1800, "artifact"),
             (1800, 1900, "interesting"), (1950, 2000, "not_interesting")]
    r = ml.label_windows([0, 600, 1200, 1800, 2400], 600, spans)
    c = r.counts
    assert c["n_windows"] == 5
    assert (c["interesting"] + c["not_interesting"] + c["unlabelled"] + c["conflicting"]
            + c["artifact"] + c["dropped_for_overlap"]) == 5
    assert c["labelled"] == c["interesting"] + c["not_interesting"] == 2


# ── non-overlapping training windows (Q-W1) ─────────────────────────────────

def _grid(n=30, stride=200):
    return np.arange(n, dtype=np.int64) * stride


def test_a_600_200_grid_keeps_its_labelled_windows_first():
    ml = _ml()
    starts = _grid()
    # labels only on windows whose start is 200 mod 600: those are kept, their overlapping neighbours dropped
    spans = [(int(s), int(s) + 600, "not_interesting" if k % 2 else "interesting")
             for k, s in enumerate(s for s in starts if s % 600 == 200)]
    r = ml.label_windows(starts, 600, spans, non_overlapping=True)
    kept = starts[r.fate != "dropped_for_overlap"]
    assert len(kept) == 10
    assert set(int(s) % 600 for s in kept) == {200}
    assert np.all(np.diff(kept) >= 600), "no two kept windows overlap"
    assert r.counts["non_overlap_rule"] == "labelled-first"
    assert r.counts["dropped_for_overlap"] == 20
    assert r.counts["labelled"] == 10


def test_sparse_labels_on_different_phases_are_all_kept():
    """The measured case: labels an hour apart sit on all three phases of the
    600/200 grid and overlap nothing. One phase would keep a third of them;
    labelled-first keeps every one, and still no two kept windows overlap."""
    ml = _ml()
    starts = _grid(n=200)
    labelled_starts = [0, 3800, 8200, 12000, 16400, 20800, 24600, 29000]   # 0, 200, 400 mod 600, far apart
    assert {s % 600 for s in labelled_starts} == {0, 200, 400}
    spans = [(s, s + 600, "interesting" if k % 2 else "not_interesting") for k, s in enumerate(labelled_starts)]
    r = ml.label_windows(starts, 600, spans, non_overlapping=True)
    assert r.counts["labelled"] == len(labelled_starts)
    kept = np.sort(starts[r.fate != "dropped_for_overlap"])
    assert np.all(np.diff(kept) >= 600)
    # the gaps between labels are filled with unlabelled windows, so later labels can land on them
    assert r.counts["unlabelled"] > 0


def test_non_overlap_is_a_no_op_on_a_grid_that_already_tiles():
    ml = _ml()
    starts = np.arange(5) * 600
    r = ml.label_windows(starts, 600, [(0, 600, "interesting"), (600, 1200, "not_interesting")],
                         non_overlapping=True)
    assert r.counts["dropped_for_overlap"] == 0


def test_without_non_overlap_every_grid_window_is_kept():
    ml = _ml()
    r = ml.label_windows(_grid(), 600, [(0, 600, "interesting")], non_overlapping=False)
    assert r.counts["dropped_for_overlap"] == 0
    assert r.counts["non_overlap_rule"] is None


# ── the block, through the executor, on a synthetic store ───────────────────

FS = 1.0
N = 7200


def _store(tmp):
    npy = os.path.join(tmp, "CH0.npy")
    rng = np.random.default_rng(3)
    np.save(npy, np.cumsum(rng.standard_normal(N)) * 0.01 + 0.05 * rng.standard_normal(N))
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "syn_fs1.mat", 0, FS, N, 0, npy)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    # the labels' own grid: 600-sample spans on a 200-sample stride, interesting on
    # every third phase-200 window, not_interesting on the rest of phase 200
    k = 0
    for s in range(200, N - 600, 600):
        verdict = "interesting" if k % 3 == 0 else "not_interesting"
        conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (1, ?, ?, ?, 'imported_10min', ?)", (s, s + 600, verdict, now))
        k += 1
    # one long excel-style region and one artifact on another phase
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                 "VALUES (1, 0, 200, 'artifact', 'excel_catalog', ?)", (now,))
    conn.commit(); conn.close()
    return db


def _recipe(non_overlapping=True, classifier=False):
    steps = [
        {"stage": "preprocessing", "algorithm": "window_matrix",
         "params": {"window_min": 10.0, "step_frac": 0.334, "catch22": False, "fast_entropy": True,
                    "slow_entropy": False, "cnn": False, "rf": False}},
        {"stage": "catalogue", "algorithm": "manual_labels", "params": {"non_overlapping": non_overlapping}},
    ]
    if classifier:
        steps.append({"stage": "catalogue", "algorithm": "classifier",
                      "params": {"n_estimators": 10, "holdout_frac": 0.0},
                      "side_inputs": {"windows": {"source_kind": "earlier_step", "step_index": 0}}})
    return make_recipe(1, steps, span=(0, N))


@pytest.fixture
def store(monkeypatch):
    import Adapters.preprocessing_window_matrix as wm
    import Adapters.catalogue_classifier as clf
    import Working.config as cfg
    tmp = tempfile.mkdtemp(prefix="aa_ml_")
    monkeypatch.setattr(wm, "RESULTS_DIR", os.path.join(tmp, "wm"))
    monkeypatch.setattr(clf, "MODEL_ROOT", os.path.join(tmp, "models"))
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", os.path.join(tmp, "cache"))
    # every step slow enough to cache: a cached manual-label step would be stale
    monkeypatch.setattr(cfg, "STEP_CACHE_WRITE_THRESHOLD_S", 0.0)
    try:
        yield _store(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_block_is_registered_as_windowset_to_grouping():
    spec = get_adapter(NAME)
    assert spec.input_kind == "windowset" and spec.output_kind == "grouping"
    assert spec.stage == "catalogue"
    assert spec.page_name == "Manual labels"


def test_the_block_labels_the_window_matrix_windows_from_the_human_store(store):
    out = execute_recipe(_recipe(), db_path=store, force=True)
    res = out["result"]
    assert res.output_kind == "grouping"
    labels = np.asarray(res.value.labels)
    cov = res.meta["coverage"]
    assert len(labels) == cov["n_windows"]
    assert cov["non_overlap_rule"] == "labelled-first"
    assert cov["labelled"] == int((labels >= 0).sum()) > 0
    assert cov["interesting"] == int((labels == 1).sum()) > 0
    assert cov["not_interesting"] == int((labels == 0).sum()) > 0
    assert cov["dropped_for_overlap"] > 0
    assert res.meta["class_names"] == {"0": "not_interesting", "1": "interesting"}


def test_the_rules_print_the_rule_and_the_coverage_in_words(store):
    res = execute_recipe(_recipe(), db_path=store, force=True)["result"]
    rules = res.meta["rules"]
    assert isinstance(rules, list) and all(set(r) >= {"name", "rule"} for r in rules)
    text = " ".join(r["rule"] for r in rules).lower()
    for word in ("wholly contains", "unlabelled", "conflicting", "dropped for overlap", "artifact"):
        assert word in text, word
    line = res.meta["summary"]
    for word in ("windows", "labelled", "interesting", "not_interesting", "unlabelled", "conflicting",
                 "dropped for overlap"):
        assert word in line, (word, line)


def test_the_block_writes_nothing(store):
    """Rule 5: it reads annotations and window_verdicts and writes no row."""
    conn = init_db(store)
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("annotations", "window_verdicts", "detections")}
    conn.close()
    execute_recipe(_recipe(), db_path=store, force=True)
    conn = init_db(store)
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
    conn.close()
    assert before == after
    src = inspect.getsource(_ml()).upper()
    for verb in ("INSERT ", "UPDATE ", "DELETE "):
        assert verb not in src, f"catalogue_manual_labels.py carries a {verb.strip()} statement"


def test_a_new_human_label_reaches_the_next_run_never_a_stale_cache(store):
    first = execute_recipe(_recipe(), db_path=store, force=True)["result"].meta["coverage"]
    conn = init_db(store)
    # the researcher changes their mind about one window
    conn.execute("UPDATE annotations SET verdict = 'interesting' WHERE id = "
                 "(SELECT MIN(id) FROM annotations WHERE verdict = 'not_interesting')")
    conn.commit(); conn.close()
    second = execute_recipe(_recipe(), db_path=store, force=True)["result"].meta["coverage"]
    assert second["interesting"] == first["interesting"] + 1


def test_window_verdicts_on_a_saved_set_are_read_as_human_spans(store):
    """A verdict Review wrote on a saved window set is a human label of that
    window's extent (bounds on disk, the row holds the path)."""
    from Working.types import WindowSet
    tmp = os.path.dirname(store)
    d = os.path.join(tmp, "ws_saved")
    # one window at 5000 that the 600/200 annotations never labelled on phase 200
    WindowSet(starts=np.array([5000 + 0], dtype=np.int64), length=600, fs=FS).to_path(d)
    conn = init_db(store)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    taken = {r[0] for r in conn.execute("SELECT start_idx FROM annotations")}
    conn.execute("DELETE FROM annotations WHERE start_idx = 5000")
    conn.execute("INSERT INTO window_sets (name, version, path, recording_id, channel, fs, window_length, "
                 "n_windows, created_at) VALUES ('ws', 1, ?, 1, 0, 1.0, 600, 1, ?)", (d, now))
    conn.execute("INSERT INTO window_verdicts (window_set_id, window_index, verdict, created_at) "
                 "VALUES (1, 0, 'interesting', ?)", (now,))
    conn.commit(); conn.close()
    assert 5000 % 600 == 200 and 5000 in taken
    res = execute_recipe(_recipe(), db_path=store, force=True)["result"]
    assert res.meta["coverage"]["sources"].get("window_verdicts") == 1


def test_the_classifier_trains_on_the_labelled_windows_only_and_says_so(store):
    out = execute_recipe(_recipe(classifier=True), db_path=store, force=True)
    meta = out["result"].meta
    labelled = meta["n_train"] + meta["n_holdout"]
    assert meta["n_excluded"] == meta["n_windows"] - labelled > 0
    assert set(meta["class_counts"]) == {0, 1}, "the -1 'excluded' label is never a class"
    assert "excluded" in meta["excluded_reason"]

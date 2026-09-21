"""
test_compare.py
================
Ticket 33 — the two-run set-overlap comparison.

`Working.compare` is the headless half: given two completed runs, it computes
the intersection and each run's exclusive remainder using the named overlap
criterion `similarity.interval_iou`. The Panel surface that rendered it
(`UI.workspaces.analyse.compare`) was retired with the Panel tree on
2026-09-21 (tag `archive/panel-ui`) together with its seven surface tests; the
web UI renders the same `Working.compare` result.

These tests are deliberately headless: an in-memory SQLite database and
synthetic detection rows.
"""

import inspect
import os
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
from Working.database.similarity import interval_iou
from Working.recipes import make_recipe


def _make_db():
    """A fresh in-memory database with one recording and two completed runs."""
    conn = init_db(":memory:")
    recording_id = q.insert_recording(conn, "fake.mat", 0, 1.0, 10_000, 0, "fake.npy")
    config_id, _ = run_db.get_or_create_config(conn, {"steps": []})
    run_a = run_db.insert_run(conn, config_id, recording_id, 0, 10_000, status="completed")
    run_b = run_db.insert_run(conn, config_id, recording_id, 0, 10_000, status="completed")
    return conn, run_a, run_b


def _add_detections(conn, run_id, spans):
    """Insert detections for `spans` and return their ids in order."""
    return [run_db.insert_detection(conn, run_id, s, e) for s, e in spans]


def _make_named_comparison_runs(steps_a, steps_b, name_a="tuned lowpass", name_b="raw"):
    """A fresh in-memory database with two completed, differently-named runs
    whose recipes are built from the supplied step lists."""
    conn = init_db(":memory:")
    recording_id = q.insert_recording(conn, "fake_compare.mat", 0, 1.0, 10_000, 0, "fake.npy")
    recipe_a = make_recipe(recording_id, steps_a)
    recipe_b = make_recipe(recording_id, steps_b)
    config_a, _ = run_db.get_or_create_config(conn, recipe_a)
    config_b, _ = run_db.get_or_create_config(conn, recipe_b)
    run_a = run_db.insert_run(conn, config_a, recording_id, 0, 10_000,
                              status="completed", name=name_a)
    run_b = run_db.insert_run(conn, config_b, recording_id, 0, 10_000,
                              status="completed", name=name_b)
    return conn, run_a, run_b


def _close(conn):
    conn.close()


# ── headless core: Working.compare ─────────────────────────────────────────

def test_exactly_one_run_set_overlap_implementation_in_repository():
    """Ticket 44 consumes the run-set overlap rather than reimplementing it.

    The only function named `compare_run_sets` in the core and web-bridge
    source trees must be the one in `Working/compare.py`.
    """
    import ast
    from pathlib import Path

    root = Path(PROJECT_ROOT)
    definitions = []
    for base in ("Working", "webui"):
        for path in (root / base).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and node.name == "compare_run_sets":
                    definitions.append(str(path.relative_to(root)))

    assert definitions == ["Working" + os.sep + "compare.py"], definitions


def test_compare_reports_intersection_and_exclusive_remainders():
    from Working.compare import compare_run_sets

    conn, run_a, run_b = _make_db()
    try:
        a_ids = _add_detections(conn, run_a, [(0, 10), (20, 30), (40, 50)])
        b_ids = _add_detections(conn, run_b, [(0, 10), (25, 35), (60, 70)])

        result = compare_run_sets(conn, run_a, run_b, iou_threshold=0.5)

        assert result.overlap_criterion == "interval_iou"
        assert result.iou_threshold == 0.5

        # [0,10) is identical in both runs; the other spans do not clear a
        # 0.5 IoU threshold.
        assert [(p.a_detection_id, p.b_detection_id) for p in result.intersection] == [
            (a_ids[0], b_ids[0])
        ]
        assert {row["id"] for row in result.a_only} == {a_ids[1], a_ids[2]}
        assert {row["id"] for row in result.b_only} == {b_ids[1], b_ids[2]}

        assert result.counts == {
            "a_total": 3,
            "b_total": 3,
            "intersection": 1,
            "a_only": 2,
            "b_only": 2,
        }
    finally:
        _close(conn)


def test_compare_matches_by_interval_iou_not_duplicate_counting():
    from Working.compare import compare_run_sets

    conn, run_a, run_b = _make_db()
    try:
        a_ids = _add_detections(conn, run_a, [(0, 10), (20, 30)])
        b_ids = _add_detections(conn, run_b, [(0, 10), (2, 12)])

        result = compare_run_sets(conn, run_a, run_b, iou_threshold=0.5)

        # Both B spans overlap A[0,10), but one match consumes A[0,10) and
        # leaves B[2,12) as an exclusive B remainder.
        assert [(p.a_detection_id, p.b_detection_id) for p in result.intersection] == [
            (a_ids[0], b_ids[0])
        ]
        assert {row["id"] for row in result.a_only} == {a_ids[1]}
        assert {row["id"] for row in result.b_only} == {b_ids[1]}
        assert result.counts["intersection"] == 1
    finally:
        _close(conn)


def test_compare_uses_interval_iou_values_for_matches():
    from Working.compare import compare_run_sets

    conn, run_a, run_b = _make_db()
    try:
        a_id = _add_detections(conn, run_a, [(0, 10)])[0]
        b_id = _add_detections(conn, run_b, [(0, 10)])[0]

        result = compare_run_sets(conn, run_a, run_b, iou_threshold=0.5)

        assert len(result.intersection) == 1
        pair = result.intersection[0]
        assert pair.a_detection_id == a_id
        assert pair.b_detection_id == b_id
        assert pair.iou == interval_iou(0, 10, 0, 10) == 1.0
    finally:
        _close(conn)


def test_compare_refuses_incomplete_runs():
    from Working.compare import compare_run_sets

    conn, run_a, run_b = _make_db()
    try:
        run_db.update_run(conn, run_b, status="running")
        with pytest.raises(ValueError):
            compare_run_sets(conn, run_a, run_b)
    finally:
        _close(conn)


def test_compare_rejects_an_unknown_overlap_criterion():
    from Working.compare import compare_run_sets

    conn, run_a, run_b = _make_db()
    try:
        with pytest.raises(ValueError):
            compare_run_sets(conn, run_a, run_b, overlap_criterion="shape_distance")
    finally:
        _close(conn)


# ── headless core: Working.compare recipe diff (ticket 68) ────────────────

def test_diff_recipes_reports_changed_parameter_with_both_values():
    """The motivating one-parameter sweep: identical chains, one value differs."""
    from Working.compare import diff_recipes

    a = make_recipe(1, [{"stage": "preprocessing", "algorithm": "bandpass",
                         "params": {"low_hz": 0.01, "high_hz": 0.1}}])
    b = make_recipe(1, [{"stage": "preprocessing", "algorithm": "bandpass",
                         "params": {"low_hz": 0.05, "high_hz": 0.1}}])

    diff = diff_recipes(a, b)
    assert len(diff) == 1
    step_diff = diff[0]
    assert step_diff.index == 0
    assert step_diff.a_step["params"]["low_hz"] == 0.01
    assert step_diff.b_step["params"]["low_hz"] == 0.05
    assert [(pc.name, pc.a_value, pc.b_value) for pc in step_diff.changed_params] == [
        ("low_hz", 0.01, 0.05)
    ]


def test_diff_recipes_reports_added_step():
    from Working.compare import diff_recipes

    a = make_recipe(1, [{"stage": "preprocessing", "algorithm": "lowpass"}])
    b = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "lowpass"},
        {"stage": "detection", "algorithm": "rupture"},
    ])

    diff = diff_recipes(a, b)
    assert len(diff) == 1
    step_diff = diff[0]
    assert step_diff.index == 1
    assert step_diff.a_step is None
    assert step_diff.b_step["algorithm"] == "rupture"


def test_diff_recipes_reports_removed_step():
    from Working.compare import diff_recipes

    a = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "lowpass"},
        {"stage": "detection", "algorithm": "rupture"},
    ])
    b = make_recipe(1, [{"stage": "preprocessing", "algorithm": "lowpass"}])

    diff = diff_recipes(a, b)
    assert len(diff) == 1
    step_diff = diff[0]
    assert step_diff.index == 1
    assert step_diff.a_step["algorithm"] == "rupture"
    assert step_diff.b_step is None


def test_diff_recipes_handles_chains_of_different_lengths():
    from Working.compare import diff_recipes

    a = make_recipe(1, [{"stage": "preprocessing", "algorithm": "lowpass"}])
    b = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "lowpass"},
        {"stage": "preprocessing", "algorithm": "bandpass"},
        {"stage": "detection", "algorithm": "rupture"},
    ])

    diff = diff_recipes(a, b)
    assert [d.index for d in diff] == [1, 2]
    assert all(d.a_step is None for d in diff)
    assert [d.b_step["algorithm"] for d in diff] == ["bandpass", "rupture"]


def test_diff_recipes_repeated_algorithm_not_mistaken_for_same_step():
    """Two lowpass steps in one chain stay distinct by position."""
    from Working.compare import diff_recipes

    a = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.05}},
        {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.10}},
    ])
    b = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.06}},
        {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.10}},
    ])

    diff = diff_recipes(a, b)
    assert len(diff) == 1
    assert diff[0].index == 0
    assert [(pc.name, pc.a_value, pc.b_value) for pc in diff[0].changed_params] == [
        ("cutoff_hz", 0.05, 0.06)
    ]


def test_diff_recipes_reports_parameter_present_in_one_absent_in_other():
    from Working.compare import MISSING, diff_recipes

    a = make_recipe(1, [{"stage": "detection", "algorithm": "rupture",
                         "params": {"penalty": 50.0}}])
    b = make_recipe(1, [{"stage": "detection", "algorithm": "rupture"}])

    diff = diff_recipes(a, b)
    assert len(diff) == 1
    changed = diff[0].changed_params
    assert len(changed) == 1
    assert changed[0].name == "penalty"
    assert changed[0].a_value == 50.0
    assert changed[0].b_value is MISSING

    # Symmetric case: the parameter exists only in the second recipe.
    diff_rev = diff_recipes(b, a)
    assert len(diff_rev) == 1
    changed_rev = diff_rev[0].changed_params
    assert changed_rev[0].name == "penalty"
    assert changed_rev[0].a_value is MISSING
    assert changed_rev[0].b_value == 50.0


def test_diff_recipes_distinguishes_absent_param_from_none_value():
    from Working.compare import MISSING, diff_recipes

    # A has penalty=None explicitly; B has no penalty parameter at all.
    a = make_recipe(1, [{"stage": "detection", "algorithm": "rupture",
                         "params": {"penalty": None}}])
    b = make_recipe(1, [{"stage": "detection", "algorithm": "rupture"}])

    diff = diff_recipes(a, b)
    assert len(diff) == 1
    changed = diff[0].changed_params
    assert len(changed) == 1
    assert changed[0].a_value is None
    assert changed[0].b_value is MISSING


def test_diff_recipes_identical_recipes_report_no_difference():
    from Working.compare import diff_recipes

    a = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.05}},
        {"stage": "detection", "algorithm": "rupture", "params": {"penalty": 50.0}},
    ])
    b = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.05}},
        {"stage": "detection", "algorithm": "rupture", "params": {"penalty": 50.0}},
    ])

    assert diff_recipes(a, b) == ()


def test_diff_recipes_reports_step_algorithm_change_at_same_position():
    from Working.compare import diff_recipes

    a = make_recipe(1, [{"stage": "preprocessing", "algorithm": "lowpass"}])
    b = make_recipe(1, [{"stage": "preprocessing", "algorithm": "bandpass"}])

    diff = diff_recipes(a, b)
    assert len(diff) == 1
    step_diff = diff[0]
    assert step_diff.index == 0
    assert step_diff.a_step["algorithm"] == "lowpass"
    assert step_diff.b_step["algorithm"] == "bandpass"
    assert step_diff.changed_params == ()


def test_diff_recipes_is_about_the_chain_not_run_scope():
    """The diff ignores recording_id/span — it compares chains, not runs."""
    from Working.compare import diff_recipes

    a = make_recipe(1, [{"stage": "preprocessing", "algorithm": "lowpass"}],
                    span=(0, 100))
    b = make_recipe(2, [{"stage": "preprocessing", "algorithm": "lowpass"}],
                    span=(0, 200))

    assert diff_recipes(a, b) == ()


def _run_all():
    fns = [obj for name, obj in sorted(globals().items())
           if name.startswith("test_") and inspect.isfunction(obj)]
    passed, failed = 0, []
    for fn in fns:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {fn.__name__}: {e!r}")
            failed.append(fn.__name__)
    print(f"\n{passed}/{len(fns)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    _run_all()

"""
test_discovery_compare.py
=========================
Spec §7.7/§7.8 — what the Compare view is allowed to say about two runs.

The tests that matter here are the ones that stop the two known ways this
surface goes wrong: a role assigned from a glyph or a name match rather than
from the block's declared types, and a span comparison that quietly drops the
§4.6 onset half by reimplementing overlap.
"""

import pytest

from Adapters.registry import discover_adapters, get_adapter
from Working.compare import MISSING
from Working.discovery import compare as dc


@pytest.fixture(scope="module", autouse=True)
def _registry():
    discover_adapters()


# ── roles ────────────────────────────────────────────────────────────────────


def test_roles_are_the_clients_five_in_the_clients_order():
    assert dc.ROLES == ("Source", "Preprocess", "Score / estimate", "Encode", "Detect")


def test_every_registered_block_lands_in_at_most_one_role():
    for spec in discover_adapters():
        role = dc.role_of(spec)
        assert role is None or role in dc.ROLES, f"{spec.name} -> {role!r}"
        # "at most one" is the real claim: role_of returns a single value, so
        # the failure mode to catch is a role outside the five.


def test_matrix_profile_scores_and_threshold_detects():
    # Both live under category 'detect'; only the declared output_kind tells
    # them apart, which is exactly what role_of must be reading.
    assert dc.role_of(get_adapter("detection.matrix_profile")) == "Score / estimate"
    assert dc.role_of(get_adapter("detection.threshold")) == "Detect"
    assert dc.role_of(get_adapter("preprocessing.detrend")) == "Preprocess"
    assert dc.role_of(get_adapter("detection.sax_dsax")) == "Encode"


def test_role_cells_fills_all_five_keys_and_leaves_encode_empty():
    recipe = {
        "steps": [
            {"stage": "preprocessing", "algorithm": "preprocessing.detrend",
             "params": {"window_s": 300.0}},
            {"stage": "detection", "algorithm": "detection.matrix_profile",
             "params": {"window_min": 5.0}},
            {"stage": "detection", "algorithm": "detection.threshold",
             "params": {"threshold": 0.5}},
        ]
    }
    cells = dc.role_cells(recipe, source_label="CH4_A2 · CH2_A1")

    assert set(cells) == set(dc.ROLES)
    assert cells["Encode"] is None

    assert cells["Source"]["param"] == "CH4_A2 · CH2_A1"
    assert cells["Source"]["signature"] == "— → Signal"
    assert cells["Source"]["glyph"] == "source"

    pre = cells["Preprocess"]
    assert pre["index"] == "01"
    assert pre["algorithm"] == "preprocessing.detrend"
    assert pre["signature"] == "Signal → Signal"
    assert pre["glyph"] == "baseline"
    assert "5 min" in pre["param"]

    score = cells["Score / estimate"]
    assert score["index"] == "02"
    assert score["signature"] == "Signal → Scores"
    assert score["glyph"] == "mp"

    det = cells["Detect"]
    assert det["index"] == "03"
    assert det["signature"] == "Scores → SpanSet"
    assert det["glyph"] == "threshold"
    assert det["n_stages"] == 1


def test_two_steps_in_one_role_the_last_wins_and_n_stages_counts():
    recipe = {
        "steps": [
            {"stage": "preprocessing", "algorithm": "preprocessing.lowpass", "params": {}},
            {"stage": "preprocessing", "algorithm": "preprocessing.detrend", "params": {}},
        ]
    }
    cell = dc.role_cells(recipe, source_label="CH2_A1")["Preprocess"]
    assert cell["algorithm"] == "preprocessing.detrend"
    assert cell["n_stages"] == 2


def test_glyph_for_never_invents_a_kind():
    kinds = {"human", "drop", "sax", "seed", "mp", "spike", "model",
             "threshold", "baseline", "noise", "source"}
    for spec in discover_adapters():
        assert dc.glyph_for(spec.name) in kinds, spec.name
    assert dc.glyph_for("human") == "human"
    assert dc.glyph_for("detection.drop_detection") == "drop"
    assert dc.glyph_for("catalogue.classifier") == "model"
    # Unmapped but registered: falls back to the role's generic glyph.
    assert dc.glyph_for("detection.rupture") == "threshold"


# ── spans ────────────────────────────────────────────────────────────────────


def test_compare_spans_shares_one_and_keeps_one_each_side():
    a = [(0, 100), (500, 600)]
    b = [(2, 101), (900, 1000)]
    out = dc.compare_spans(a, b)

    assert [p["a"] for p in out["pairs"]] == [0]
    assert [p["b"] for p in out["pairs"]] == [0]
    assert out["pairs"][0]["iou"] > 0.9
    assert out["only_a"] == [1]
    assert out["only_b"] == [1]
    assert out["rule"]["criterion"] == "reciprocal_iou_onset"


def test_compare_spans_applies_the_onset_half_not_overlap_alone():
    # IoU is comfortably above 0.5, but the onset gap is 40 % of the
    # candidate's duration — over §4.6's 0.25 — so this is not a match.
    a = [(0, 100)]
    b = [(40, 160)]
    out = dc.compare_spans(a, b)
    assert out["pairs"] == []
    assert out["only_a"] == [0] and out["only_b"] == [0]


def test_compare_spans_counts_are_usable_from_either_side():
    out = dc.compare_spans([(0, 100)], [(0, 100), (500, 600)])
    assert out["counts"] == {"a_total": 1, "b_total": 2, "both": 1,
                             "only_a": 0, "only_b": 1}


def test_overlap_rows_per_channel_plus_a_total_row():
    per_channel = [
        {"channel": "CH2_A1", "a": [(0, 100), (500, 600)], "b": [(0, 100)]},
        {"channel": "CH4_A2", "a": [(0, 100)], "b": [(0, 100), (800, 900)]},
    ]
    rows = dc.overlap_rows(per_channel)
    assert [r["channel"] for r in rows] == ["CH2_A1", "CH4_A2", "all channels"]
    assert rows[0] == {"channel": "CH2_A1", "onlyA": 1, "both": 1, "onlyB": 0}
    assert rows[1] == {"channel": "CH4_A2", "onlyA": 0, "both": 1, "onlyB": 1}
    assert rows[2] == {"channel": "all channels", "onlyA": 1, "both": 2, "onlyB": 1}


# ── stage diff ───────────────────────────────────────────────────────────────


def test_stage_diff_reports_a_changed_param_and_an_extra_step():
    recipe_a = {"steps": [
        {"stage": "preprocessing", "algorithm": "preprocessing.detrend",
         "params": {"window_s": 600.0}},
    ]}
    recipe_b = {"steps": [
        {"stage": "preprocessing", "algorithm": "preprocessing.detrend",
         "params": {"window_s": 300.0}},
        {"stage": "detection", "algorithm": "detection.threshold",
         "params": {"threshold": 0.5}},
    ]}
    rows = dc.stage_diff(recipe_a, recipe_b)

    assert [r["index"] for r in rows] == [0, 1]
    assert rows[0]["changed"] == [{"name": "window_s", "a": 600.0, "b": 300.0}]
    assert rows[0]["a"]["algorithm"] == "preprocessing.detrend"
    assert rows[1]["a"] is None
    assert rows[1]["b"]["algorithm"] == "detection.threshold"


def test_stage_diff_is_json_safe_missing_becomes_a_string():
    import json

    recipe_a = {"steps": [
        {"stage": "detection", "algorithm": "detection.threshold", "params": {}},
    ]}
    recipe_b = {"steps": [
        {"stage": "detection", "algorithm": "detection.threshold",
         "params": {"threshold": 0.5}},
    ]}
    rows = dc.stage_diff(recipe_a, recipe_b)
    assert rows[0]["changed"] == [{"name": "threshold", "a": "<missing>", "b": 0.5}]
    assert MISSING not in (rows[0]["changed"][0]["a"],)
    json.dumps(rows)  # a bridge route serialises this directly


# ── the bug that drew an empty Compare over two different chains ────────────

def test_role_cells_reads_a_real_recipes_bare_algorithm_names():
    """A recipe step carries `{"stage": "detection", "algorithm": "threshold"}`;
    the registry is keyed `"detection.threshold"`. Looking up the bare name
    finds nothing, and because an unknown block is deliberately skipped rather
    than raised on, the failure is silent: every role comes back None and
    Compare reports "0 roles differ" over two chains that share nothing. This
    is what the live drive showed on 2026-09-22."""
    from Working.recipes import make_recipe

    recipe = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "detrend", "params": {"window_s": 600.0}},
        {"stage": "detection", "algorithm": "matrix_profile", "params": {"window_min": 5.0}},
        {"stage": "detection", "algorithm": "threshold", "params": {"threshold": 0.5}},
    ], span=(0, 100000))
    cells = dc.role_cells(recipe, source_label="CH1_A1")
    assert cells["Preprocess"] is not None, "a bare 'detrend' must still resolve"
    assert cells["Score / estimate"] is not None
    assert cells["Detect"] is not None
    assert cells["Encode"] is None
    assert cells["Preprocess"]["algorithm"] == "preprocessing.detrend"
    assert cells["Score / estimate"]["glyph"] == "mp"
    assert cells["Detect"]["glyph"] == "threshold"


def test_two_real_recipes_differ_in_the_roles_they_actually_differ_in():
    from Working.recipes import make_recipe

    drop = make_recipe(1, [
        {"stage": "preprocessing", "algorithm": "detrend", "params": {"window_s": 4916.67}},
        {"stage": "detection", "algorithm": "stage_encoding", "params": {}},
        {"stage": "detection", "algorithm": "drop_detection", "params": {}},
    ], span=(0, 100000))
    seed = make_recipe(1, [
        {"stage": "detection", "algorithm": "seed_matches", "params": {"k": 10},
         "side_inputs": {"exemplar": {"source_kind": "library_exemplar", "entry_id": 0,
                                      "source_file": "fake.mat", "channel": 0,
                                      "start_idx": 0, "end_idx": 50}}},
    ], span=(0, 100000))
    a = dc.role_cells(drop, source_label="CH1_A1")
    b = dc.role_cells(seed, source_label="CH1_A1")
    differing = [r for r in dc.ROLES
                 if (a[r] is None) != (b[r] is None)
                 or (a[r] and b[r] and a[r]["name"] != b[r]["name"])]
    # the drop chain preprocesses and encodes; the seeded search does neither,
    # and its one stage is a Detect — so three roles differ, not zero
    assert set(differing) == {"Preprocess", "Encode", "Detect"}
    assert b["Detect"]["glyph"] == "seed"


def test_qualified_accepts_a_step_a_split_name_and_an_already_qualified_one():
    assert dc.qualified({"stage": "detection", "algorithm": "threshold"}) == "detection.threshold"
    assert dc.qualified("threshold", "detection") == "detection.threshold"
    assert dc.qualified("detection.threshold") == "detection.threshold"
    assert dc.qualified("detection.threshold", "preprocessing") == "detection.threshold"

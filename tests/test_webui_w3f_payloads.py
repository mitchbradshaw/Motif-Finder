"""
test_webui_w3f_payloads.py
==========================
W3-F: what wave 3's blocks put in `meta` reaches the page (`webui/server/serialize.py::to_payload`), read off the
payload, never off a block's name, and never re-derived:

* multiscale entropy — `meta["curves"]` ships as the WindowSet payload's `curves` (one line per sampled window,
  undefined scales null, the collapse flags kept); `meta["summary"]` / `meta["warnings"]` reach the face of a
  non-anchored WindowSet (they reached only an anchored one);
* cycle shapes — `meta["cycle_stack"]` ships as `cycle_stack`; the per-sequence verdicts ship exactly as the block
  gave them (`whole.verdict`, each group's `key` and `coherence.verdict`); the medoid cycles (`exemplar_events`,
  keyed `"t<train>:<g>"` with several trains) become `cycle_exemplars`, loudly refused when they name no event;
* the pan matrix profile / the wavelet transform — one row-axis convention for an image whose rows are not
  pixels: `row_axis = {values, unit, label}` from `meta["lengths_s"]` or `meta["freqs_hz"]`; the pan's
  per-length verdict ships as given (`row_verdict`), with `suggested_window_s` and `verdict`;
* the families' table — σ² and the quiet-stretch null's fields (`passed_by`, `null_kind`, `background_s`,
  `background`, `svd_entropy_variants`) are in every family row;
* `catalogue.cluster` labels a left-out (all-NaN) window −1: its cluster is named "no label".

No FastAPI needed; runs under the conda pytest.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from server.serialize import FAMILY_KEYS, to_payload  # noqa: E402
from Working.types import Encoding, Grouping, SpanSet, WindowSet  # noqa: E402


# ── multiscale entropy ──────────────────────────────────────────────────────────

def _mse_meta():
    scales = [1.0, 2.0, 4.0, 8.0]
    return {
        "scales_s": scales, "collapse": [2, 0, 0, 0], "blank_scales_s": [8.0], "inflation_limit": 1.5,
        "summary": "MSE · 3 windows · 3 of 4 scales defined", "warnings": ["scale 8 s undefined in every window"],
        "curves": {"scales_s": scales, "n_windows": 3, "sampled": False, "seed": 0,
                   "windows": [{"index": 0, "start_s": 0.0, "values": [1.2, 1.1, None, None],
                                "collapsed": [True, False, False, False], "inflation": 2.1},
                               {"index": 1, "start_s": 3600.0, "values": [1.3, 1.2, 1.0, None],
                                "collapsed": [False, False, False, False], "inflation": 1.0}],
                   "median": [1.25, 1.15, 1.0, None], "form": "values[j] is the entropy at scales_s[j]; null where undefined"},
    }


def _ws(n=3):
    feats = pd.DataFrame({"mse_1s": [1.2, 1.3, np.nan], "mse_ci": [3.3, 3.5, np.nan]})
    return WindowSet(starts=np.arange(n) * 3600, length=3600, fs=1.0, features=feats)


def test_mse_curves_ship_with_gaps_as_null():
    p = to_payload("windowset", _ws(), _mse_meta(), {"fs": 1.0})
    c = p["curves"]
    assert c["scales_s"] == [1.0, 2.0, 4.0, 8.0]
    assert c["windows"][0]["values"][2] is None, "an undefined scale stays null (a gap), never interpolated"
    assert c["windows"][0]["collapsed"][0] is True and c["median"][3] is None
    assert p["curve_flags"]["collapse"] == [2, 0, 0, 0] and p["curve_flags"]["blank_scales_s"] == [8.0]
    json.dumps(p, allow_nan=False)


def test_a_non_anchored_windowset_shows_its_blocks_summary_and_warnings():
    p = to_payload("windowset", _ws(), _mse_meta(), {"fs": 1.0})
    assert p["summary"].startswith("MSE · 3 windows"), p["summary"]
    assert p["warnings"] == ["scale 8 s undefined in every window"]


def test_a_windowset_without_curves_has_none():
    p = to_payload("windowset", _ws(), {}, {"fs": 1.0})
    assert p.get("curves") is None and p.get("warnings") in (None, [])


# ── cycle shapes ────────────────────────────────────────────────────────────────

def _verdict(beyond, tested=True):
    return {"tested": tested, "reason": None if tested else "null_draws = 0: no background null drawn",
            "beyond_noise": beyond, "beyond_noise_squared": beyond, "below_every_draw": beyond, "z": 4.0,
            "background_colour_mismatch": False if tested else None}


def _cycle_meta(prefix=""):
    rows = [{"event": i, "sequence": "1", "group": 1 if i < 3 else 2, "start_s": 100.0 * i, "length_s": 100.0,
             "before": [0.0] * 128, "after": [0.1] * 128} for i in range(6)]
    return {
        "summary": "6 cycles · 2 shapes · σ² first", "warnings": ["background fell back on 1 of 20 draws"],
        "omitted": {"gap_long": 1},
        "sequences": [{"key": "1", "n_cycles": 6, "n_used": 6, "k": 2, "k_note": None,
                       "k_null": {"source": "background", "draws": 20},
                       "background_colour_mismatch": False,
                       "change_points": [3], "change_points_s": [300.0],
                       "order_test": {"runs": 2, "p": 0.04, "n_perm": 1000, "note": "tests order, not shape"},
                       "whole": {"verdict": _verdict(True),
                                 "after_align": {"svd_entropy_norm": 0.81, "svd_entropy_squared_norm": 0.42},
                                 "nulls": {"background": {"eq17": {"median": 0.95}, "squared": {"median": 0.8}}}},
                       "groups": [{"group": 1, "key": f"{prefix}1", "size": 3, "medoid_event": 1,
                                   "floor_frac_median": 0.56, "half_recovery_frac_median": 0.7, "length_s_median": 100.0,
                                   "coherence": {"verdict": _verdict(True),
                                                 "after_align": {"svd_entropy_norm": 0.8, "svd_entropy_squared_norm": 0.4}}},
                                  {"group": 2, "key": f"{prefix}2~noise_like", "size": 3, "medoid_event": 4,
                                   "floor_frac_median": 0.1, "half_recovery_frac_median": 0.06, "length_s_median": 100.0,
                                   "coherence": {"verdict": _verdict(False),
                                                 "after_align": {"svd_entropy_norm": 0.93, "svd_entropy_squared_norm": 0.8}}}]}],
        "exemplar_events": {f"{prefix}1": 1, f"{prefix}2": 4},
        "exemplar_rule": "the group's medoid cycle",
        "cycle_stack": {"n_points": 128, "n_rows": 6, "n_cycles": 6, "sampled": False, "seed": 0,
                        "time_unit": "seconds from the span start", "rows": rows},
        "rules": [{"name": "verdict", "rule": "eq. 17 below every draw …"}],
    }


def _cycle_spans(n=6):
    feats = pd.DataFrame({"cycle_length_s": [100.0] * n, "cycle_group": [1, 1, 1, 2, 2, 2]})
    return SpanSet(starts=tuple(100 * i for i in range(n)), ends=tuple(100 * i + 30 for i in range(n)), features=feats)


def test_the_cycle_stack_ships_as_the_block_wrote_it():
    p = to_payload("spanset", _cycle_spans(), _cycle_meta(), {"fs": 1.0, "span_start": 50})
    st = p["cycle_stack"]
    assert st["n_rows"] == 6 and len(st["rows"][0]["before"]) == 128 and len(st["rows"][0]["after"]) == 128
    json.dumps(p, allow_nan=False)


def test_each_sequence_and_group_verdict_is_read_off_the_block_never_re_derived():
    p = to_payload("spanset", _cycle_spans(), _cycle_meta(), {"fs": 1.0})
    seq = p["cycle_sequences"][0]
    assert seq["whole_verdict"] == _verdict(True)
    assert seq["change_points_s"] == [300.0] and seq["order_test"]["p"] == 0.04
    g2 = seq["groups"][1]
    assert g2["key"] == "2~noise_like" and g2["verdict"]["beyond_noise"] is False
    assert seq["groups"][0]["scores"] == {"squared": 0.4, "eq17": 0.8}, "σ² first, eq. 17 beside it"
    assert p["summary"].startswith("6 cycles"), "the block's summary leads the row"
    assert p["warnings"] == ["background fell back on 1 of 20 draws"]


def test_the_medoid_cycles_ship_as_members_with_train_prefixed_keys():
    p = to_payload("spanset", _cycle_spans(), _cycle_meta(prefix="t1:"), {"fs": 1.0, "span_start": 50})
    ex = {e["key"]: e for e in p["cycle_exemplars"]}
    assert set(ex) == {"t1:1", "t1:2"}
    assert ex["t1:2"]["event"] == 4 and ex["t1:2"]["start_s"] == pytest.approx(450.0)
    assert ex["t1:2"]["end_s"] == pytest.approx(550.0), "the whole cycle: start + cycle_length_s"
    assert ex["t1:2"]["group_key"] == "t1:2~noise_like", "the exemplar carries its group's mark"


def test_an_exemplar_naming_no_event_is_refused_loudly():
    meta = _cycle_meta()
    meta["exemplar_events"] = {"1": 99}
    with pytest.raises(ValueError, match="exemplar"):
        to_payload("spanset", _cycle_spans(), meta, {"fs": 1.0})


# ── row axes: the pan matrix profile and the wavelet transform ─────────────────────

def _pan_meta():
    lengths = [900.0, 300.0, 100.0]
    # W3-C's final form (fix round 1, 617edc2): per-length `cut` and `reason_code`, the cleared band `cleared_s`,
    # `suggestion_rule`, `reasons`; no `percentage` / `approximate` / `approximate_note` (scrump is gone)
    per = [{"row": 0, "length_s": 900.0, "judged": False, "clears": False, "gap": None, "cut": None,
            "reason_code": "too_long", "reason": "too long to judge on this span: it holds 8.0 windows of this length, fewer than 14"},
           {"row": 1, "length_s": 300.0, "judged": True, "clears": True, "gap": 9.1, "cut": 6.4,
            "reason_code": "clears", "reason": "gap 9.1 >= cut 6.4 and better than every draw"},
           {"row": 2, "length_s": 100.0, "judged": True, "clears": True, "gap": 7.0, "cut": 6.2,
            "reason_code": "clears", "reason": "gap 7.0 >= cut 6.2 and better than every draw"}]
    return {"lengths_s": lengths, "per_length": per, "suggested_window_s": 300.0, "suggested_row": 1,
            "cleared_s": [100.0, 300.0], "suggestion_rule": "strongest", "reasons": {"too_long": 1, "clears": 2},
            "verdict": "clears from 100 to 300 s, strongest at 300 s (gap 9.1); suggested 300 s — 2 of 3 lengths repeat",
            "rows": "long first", "alignment": "start", "null": "aaft", "null_draws": 3,
            "summary": "3 lengths 100–900 s · clears from 100 to 300 s, strongest at 300 s · suggested 300 s",
            "rules": [{"name": "gap", "rule": "…"}]}


def test_the_pan_rows_carry_their_lengths_and_the_verdict_as_given():
    img = np.random.default_rng(0).random((3, 2000)).astype(np.float32)
    p = to_payload("encoding", Encoding(values=img, kind="image"), _pan_meta(), {"fs": 1.0, "n_samples": 2000})
    assert p["row_axis"] == {"values": [900.0, 300.0, 100.0], "unit": "s", "label": "window length",
                             "source": "lengths_s"}
    rv = p["row_verdict"]
    assert rv["suggested_window_s"] == 300.0 and rv["suggested_row"] == 1
    assert [r["clears"] for r in rv["rows"]] == [False, True, True]
    assert rv["rows"][0]["judged"] is False and "too long to judge" in rv["rows"][0]["reason"]
    assert rv["rows"][1]["cut"] == 6.4 and rv["rows"][0]["reason_code"] == "too_long"
    assert rv["cleared_s"] == [100.0, 300.0], "the band of lengths that clear, not just the one suggested"
    assert rv["suggestion_rule"] == "strongest" and rv["reasons"] == {"too_long": 1, "clears": 2}
    assert rv["verdict"].startswith("clears from 100 to 300 s")
    assert "approximate_note" not in rv, "scrump is gone from W3-C: nothing approximate to say"
    assert "not the event" in rv["caveat"], "the suggested length is never presented as the event's length"
    assert p["summary"].startswith("3 lengths"), "the block's summary reaches the face"


def test_no_length_stands_out_ships_as_none():
    meta = _pan_meta()
    meta.update(suggested_window_s=None, suggested_row=None, cleared_s=[], verdict="no length stands out: none of the 2 judged …")
    for r in meta["per_length"]:
        r["clears"] = False
    img = np.zeros((3, 500), dtype=np.float32)
    p = to_payload("encoding", Encoding(values=img, kind="image"), meta, {"fs": 1.0, "n_samples": 500})
    assert p["row_verdict"]["suggested_window_s"] is None and p["row_verdict"]["verdict"].startswith("no length")
    assert p["row_verdict"]["cleared_s"] == []


def test_the_wavelet_transform_rows_use_the_same_convention():
    img = np.random.default_rng(0).random((4, 600)).astype(np.float32)
    p = to_payload("encoding", Encoding(values=img, kind="image"), {"freqs_hz": [0.01, 0.02, 0.04, 0.08]},
                   {"fs": 1.0, "n_samples": 600})
    assert p["row_axis"] == {"values": [0.01, 0.02, 0.04, 0.08], "unit": "Hz", "label": "frequency",
                             "source": "freqs_hz"}
    assert p.get("row_verdict") is None


def test_a_row_axis_that_does_not_match_the_rows_is_refused_loudly():
    img = np.zeros((3, 500), dtype=np.float32)
    with pytest.raises(ValueError, match="rows"):
        to_payload("encoding", Encoding(values=img, kind="image"), {"lengths_s": [1.0, 2.0]}, {"fs": 1.0})


# ── the families' table and catalogue.cluster's left-out windows ───────────────────

def test_the_family_rows_carry_sigma_squared_first_and_the_quiet_null_fields():
    for k in ("passed_by", "null_kind", "background_s", "background", "svd_entropy_variants",
              "svd_entropy_squared_null_p05"):
        assert k in FAMILY_KEYS, f"{k} does not reach the families table"


def test_cluster_left_out_windows_are_named_no_label():
    labels = np.array([1, 2, -1, 1, -1])
    ws = WindowSet(starts=np.arange(5) * 10, length=10, fs=1.0, features=None)
    p = to_payload("grouping", Grouping(labels=labels),
                   {"n_left_out": 2, "left_out_reason": "every feature NaN", "summary": "2 clusters · 2 left out"},
                   {"fs": 1.0, "windowset": ws})
    c = {x["id"]: x for x in p["clusters"]}
    assert c[-1]["name"].startswith("no label")
    assert "2 left out" in p["summary"]


def test_the_pan_caveat_is_the_blocks_own_when_it_sends_one():
    """Re-critique nit 4: the caveat was a copy of W3-C's and would drift; it is read from the block's own
    "suggested window" rule, the copy only a fallback."""
    from server.serialize import SUGGESTION_CAVEAT
    img = np.zeros((3, 2000), dtype=np.float32)
    meta = _pan_meta()
    meta["rules"] = [{"name": "gap", "rule": "…"},
                     {"name": "suggested window", "rule": "The answer is the BAND of cleared lengths; the block's words."}]
    p = to_payload("encoding", Encoding(values=img, kind="image"), meta, {"fs": 1.0, "n_samples": 2000})
    assert p["row_verdict"]["caveat"] == "The answer is the BAND of cleared lengths; the block's words."
    meta["rules"] = [{"name": "gap", "rule": "…"}]
    q = to_payload("encoding", Encoding(values=img, kind="image"), meta, {"fs": 1.0, "n_samples": 2000})
    assert q["row_verdict"]["caveat"] == SUGGESTION_CAVEAT

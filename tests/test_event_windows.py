"""
test_event_windows.py
=======================
The core of `catalogue.event_windows` (w2-a): `Working.Catalogue.event_windows`,
the SpanSet -> window geometry bridge that W2-C (MiniRocket) and W2-E (families)
import. Pins: the anchor sits at exactly `anchor_offset` samples into every window,
whatever the background; the auto-length rule; events near the span ends left out
and counted by reason; NaN-heavy windows left out and counted; the anchor fallback
counted per event and named once for a whole SpanSet; `*_idx` -> `*_win`; the
overlap flag; an empty SpanSet.
"""

import math
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _event_windows_synthetic import BACKGROUNDS, FS, chain, spans_for  # noqa: E402
from Working.Catalogue import event_windows as EW  # noqa: E402
from Working.types import SpanSet  # noqa: E402


# ---------------------------------------------------------------- the anchor

@pytest.mark.parametrize("kind", BACKGROUNDS)
def test_every_kept_window_has_its_onset_at_exactly_anchor_offset(kind):
    x, onsets = chain(kind)
    spans = spans_for(onsets)
    ew = EW.event_windows(x, FS, spans, anchor="onset", length_s=600.0, pre_frac=0.2)
    assert ew.anchor_offset == 120 and ew.length == 600
    assert len(ew.starts) == len(onsets)
    for s, k in zip(ew.starts, ew.kept):
        assert s + ew.anchor_offset == onsets[k]
    cut = EW.cut(x, ew.starts, ew.length)
    assert cut.shape == (len(onsets), 600)
    for row, k in zip(cut, ew.kept):
        assert row[ew.anchor_offset] == x[onsets[k]]
        # the planted drop begins right after the anchor: the window is flat-ish before, falling after
        assert row[ew.anchor_offset + 20] < row[ew.anchor_offset] - 0.005


def test_extremum_and_start_anchors():
    x, onsets = chain("ar1")
    spans = spans_for(onsets)
    ew = EW.event_windows(x, FS, spans, anchor="extremum", length_s=600.0, pre_frac=0.5)
    assert ew.anchor_used == "extremum_idx" and ew.anchor_offset == 300
    assert all(s + 300 == onsets[k] + 20 for s, k in zip(ew.starts, ew.kept))
    ew = EW.event_windows(x, FS, spans, anchor="start", length_s=600.0, pre_frac=0.0)
    assert ew.anchor_used == "span start" and ew.anchor_offset == 0
    assert all(s == spans.starts[k] for s, k in zip(ew.starts, ew.kept))


def test_an_event_lacking_its_anchor_falls_back_to_its_span_start_and_is_counted():
    x, onsets = chain("ar1", n_events=4)
    spans = spans_for(onsets)
    f = spans.features.copy()
    f.loc[1, "onset_idx"] = np.nan
    spans = SpanSet(starts=spans.starts, ends=spans.ends, features=f)
    ew = EW.event_windows(x, FS, spans, anchor="onset", length_s=600.0)
    assert ew.n_fallback == 1
    i = list(ew.kept).index(1)
    assert ew.starts[i] + ew.anchor_offset == spans.starts[1]
    assert ew.notes == ()  # a per-event fallback is counted, not a whole-set note


def test_a_spanset_without_the_column_says_so_once_naming_event_shape():
    x, onsets = chain("ar1", n_events=4)
    spans = spans_for(onsets, with_onset_idx=False)
    ew = EW.event_windows(x, FS, spans, anchor="onset", length_s=600.0)
    assert ew.anchor_used == "span start"
    assert ew.n_fallback == 4
    assert len(ew.notes) == 1 and "Event shape" in ew.notes[0] and "onset_idx" in ew.notes[0]
    assert all(s + ew.anchor_offset == spans.starts[k] for s, k in zip(ew.starts, ew.kept))


# ---------------------------------------------------------------- length

def test_auto_length_is_twice_the_median_duration_rounded_up_to_ten_seconds_and_clamped():
    spans = SpanSet(starts=(0, 1000, 2000), ends=(100, 1133, 2140))  # durations 100, 133, 140 s
    assert EW.auto_length_s(spans, FS)[0] == 270.0  # 2 * 133 = 266 -> 270
    short = SpanSet(starts=(0, 100), ends=(5, 12))
    assert EW.auto_length_s(short, FS)[0] == 60.0  # clamped up
    long = SpanSet(starts=(0,), ends=(10_000,))
    assert EW.auto_length_s(long, FS)[0] == 7200.0  # clamped down


def test_auto_length_prefers_event_shapes_duration_when_it_ran():
    f = pd.DataFrame({"duration_s": [300.0, np.nan, 320.0, 310.0]})
    spans = SpanSet(starts=(0, 1000, 2000, 3000), ends=(50, 1050, 2050, 3050), features=f)
    length_s, basis = EW.auto_length_s(spans, FS)
    assert length_s == 620.0 and "duration_s" in basis  # 2 * 310 (finite rows only)


def test_auto_length_at_a_non_unit_sample_rate():
    spans = SpanSet(starts=(0, 1000), ends=(400, 1400))  # 400 samples at 2 Hz = 200 s
    ew = EW.event_windows(np.zeros(3000), 2.0, spans, anchor="start", length_s=0.0, pre_frac=0.0)
    assert ew.length_s == 400.0 and ew.length == 800


# ---------------------------------------------------------------- omissions

def test_events_near_the_span_ends_are_left_out_and_counted_by_reason():
    x, onsets = chain("ar1", n_events=3, first=100, spacing_s=1000, n=2400)
    # onsets 100, 1100, 2100; 600 s windows with 120 s before: 100 runs past the start, 2100 past the end
    ew = EW.event_windows(x, FS, spans_for(onsets, pre=10, post=200), anchor="onset", length_s=600.0)
    assert list(ew.kept) == [1]
    assert ew.omitted == {"past_start": 1, "past_end": 1, "too_much_nan": 0}
    assert ew.omitted_rows == {"past_start": [0], "past_end": [2], "too_much_nan": []}


def test_a_window_with_too_much_nan_is_left_out_and_counted():
    x, onsets = chain("ar1", n_events=3)
    x = x.copy()
    o = onsets[1]
    x[o + 100:o + 200] = np.nan  # 100 / 600 = 0.17 > 0.1
    x[onsets[2] + 300:onsets[2] + 330] = np.nan  # 30 / 600 = 0.05, kept
    ew = EW.event_windows(x, FS, spans_for(onsets), anchor="onset", length_s=600.0, max_nan_frac=0.1)
    assert list(ew.kept) == [0, 2]
    assert ew.omitted["too_much_nan"] == 1


def test_a_window_longer_than_the_span_is_refused_by_count_not_by_error():
    x, onsets = chain("ar1", n_events=2, n=1500, first=300, spacing_s=600)
    ew = EW.event_windows(x, FS, spans_for(onsets), anchor="onset", length_s=3600.0)
    assert len(ew.starts) == 0 and sum(ew.omitted.values()) == 2


def test_an_empty_spanset_gives_no_windows_and_a_note():
    ew = EW.event_windows(np.zeros(1000), FS, SpanSet(starts=(), ends=()), anchor="onset", length_s=0.0)
    assert len(ew.starts) == 0 and len(ew.kept) == 0
    assert sum(ew.omitted.values()) == 0
    assert any("no events" in n for n in ew.notes)
    assert ew.length_s == 60.0  # the auto rule's floor when there is no median to take
    f = EW.window_features(SpanSet(starts=(), ends=()), ew)
    assert len(f) == 0 and {"event_index", "anchor_offset", "overlaps_next"} <= set(f.columns)


def test_parameters_are_checked():
    x, onsets = chain("ar1", n_events=2)
    spans = spans_for(onsets)
    with pytest.raises(ValueError, match="anchor"):
        EW.event_windows(x, FS, spans, anchor="peak")
    with pytest.raises(ValueError, match="pre_frac"):
        EW.event_windows(x, FS, spans, pre_frac=1.0)
    with pytest.raises(ValueError, match="sample"):
        EW.event_windows(x, FS, spans, length_s=1.0)  # one sample is not a window


# ---------------------------------------------------------------- features

def test_idx_columns_become_window_relative_win_columns_and_the_originals_go():
    x, onsets = chain("ar1", n_events=4)
    spans = spans_for(onsets, extra={"recovery_idx": [float(o + 900) for o in onsets],  # outside a 600 s window
                                     "group": ["a", "b", "a", "b"]})
    ew = EW.event_windows(x, FS, spans, anchor="onset", length_s=600.0, pre_frac=0.2)
    f = EW.window_features(spans, ew)
    assert not [c for c in f.columns if c.endswith("_idx")]
    assert (f["onset_win"] == ew.anchor_offset).all()
    assert (f["extremum_win"] == ew.anchor_offset + 20).all()
    assert f["recovery_win"].isna().all()  # 900 s past the onset is outside the window: NaN, not a clipped index
    assert list(f["event_index"]) == list(ew.kept)
    assert (f["anchor_offset"] == ew.anchor_offset).all()
    # carried columns ride unchanged, the non-numeric ones too
    assert list(f["event_amplitude_mv"]) == [spans.features["event_amplitude_mv"][k] for k in ew.kept]
    assert list(f["group"]) == [spans.features["group"][k] for k in ew.kept]
    assert list(f["polarity"]) == [-1] * len(ew.kept)


def test_scores_and_labels_ride_as_columns():
    spans = SpanSet(starts=(100, 1000), ends=(200, 1100), scores=(1.5, 2.5), labels=("a", "b"))
    ew = EW.event_windows(np.zeros(2000), FS, spans, anchor="start", length_s=100.0, pre_frac=0.0)
    f = EW.window_features(spans, ew)
    assert list(f["span_score"]) == [1.5, 2.5] and list(f["span_label"]) == ["a", "b"]


def test_overlapping_windows_are_flagged_in_a_dense_chain():
    # a dense stretch: drops every 10 min, 20 min windows -> each window runs into the next one
    x, onsets = chain("ar1", spacing_s=600, n_events=10)
    ew = EW.event_windows(x, FS, spans_for(onsets, post=300), anchor="onset", length_s=1200.0)
    f = EW.window_features(spans_for(onsets, post=300), ew)
    ov = list(f["overlaps_next"])
    assert ov == [True] * (len(ov) - 1) + [False]  # the last window has no next one
    assert f["overlaps_next"].dtype == bool
    # 30 min apart with 20 min windows: none overlap
    x, onsets = chain("ar1", spacing_s=1800, n_events=10)
    ew = EW.event_windows(x, FS, spans_for(onsets), anchor="onset", length_s=1200.0)
    assert not EW.overlaps_next(ew.starts, ew.length).any()


def test_windows_come_out_in_time_order_and_event_index_maps_back():
    # spans handed over out of order: the windows are sorted by start, event_index still points at the input row
    x, onsets = chain("ar1", n_events=5)
    order = [3, 0, 4, 1, 2]
    spans = spans_for([onsets[i] for i in order])
    ew = EW.event_windows(x, FS, spans, anchor="onset", length_s=600.0)
    assert list(ew.starts) == sorted(ew.starts)
    for s, k in zip(ew.starts, ew.kept):
        assert s + ew.anchor_offset == spans.features["onset_idx"][k]


def test_the_dense_chain_on_ar1_keeps_every_event_with_the_auto_length():
    x, onsets = chain("ar1", spacing_s=1800, n_events=40)  # 20 h of drops every 30 min
    spans = spans_for(onsets)
    ew = EW.event_windows(x, FS, spans, anchor="onset", length_s=0.0)
    assert ew.length_s == 1200.0  # 2 * 600 s (duration_s) -> 1200 s
    assert len(ew.starts) == 40 and sum(ew.omitted.values()) == 0
    assert not EW.overlaps_next(ew.starts, ew.length).any()


def test_rules_state_the_auto_length_rule_and_the_anchor():
    names = {r["name"] for r in EW.rules(anchor="onset", pre_frac=0.2, max_nan_frac=0.1, length_s=0.0)}
    assert {"length", "anchor", "left out", "*_win", "overlaps_next"} <= names
    text = " ".join(r["rule"] for r in EW.rules(anchor="onset", pre_frac=0.2, max_nan_frac=0.1, length_s=0.0))
    assert "twice the median" in text and "60" in text and "7200" in text


def test_the_core_imports_no_adapter_and_no_ui():
    import ast
    src = open(EW.__file__, encoding="utf-8").read()
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not mods & {"Adapters", "webui", "panel", "fastapi", "matplotlib"}, mods
    assert math.isfinite(EW.AUTO_MIN_S) and EW.AUTO_MAX_S == 7200.0

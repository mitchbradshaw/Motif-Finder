"""
test_webui_serialize.py
=========================
`webui/server/serialize.py::to_payload`, the one server-side seam over the
seven types, exercised directly (the contract critic found it had no direct
tests): the 4-D image-stack contact sheet, the empty stack, the symbolic
strip using the encoder's own letters, and the SpanSet offset.

No FastAPI needed; runs under the conda pytest.

Runnable standalone:  python tests/test_webui_serialize.py
"""

import base64
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from server.serialize import STACK_TILES, to_payload  # noqa: E402
from Working.types import Encoding, SpanSet  # noqa: E402


def test_a_4d_image_stack_ships_a_contact_sheet_with_n_images():
    stack = np.random.default_rng(0).integers(0, 255, size=(7, 32, 32, 3), dtype=np.uint8)
    p = to_payload("encoding", Encoding(values=stack, kind="image"), {}, {"fs": 1.0})
    assert p["kind"] == "image" and p["ndim"] == 4 and p["n_images"] == 7 and p["shape"] == [7, 32, 32, 3]
    assert p["pixels_b64"] and p["channels"] == 3
    rows, cols = p["display_shape"]
    assert rows >= 32 and cols >= 32 and "contact sheet" in p["summary"]


def test_a_stack_larger_than_the_tile_cap_shows_only_the_first_tiles():
    stack = np.zeros((STACK_TILES + 5, 8, 8, 3), dtype=np.uint8)
    p = to_payload("encoding", Encoding(values=stack, kind="image"), {}, {"fs": 1.0})
    assert p["n_images"] == STACK_TILES + 5 and f"first {STACK_TILES}" in p["summary"]


def test_an_empty_stack_is_a_payload_not_a_traceback():
    p = to_payload("encoding", Encoding(values=np.zeros((0, 32, 32, 3), dtype=np.uint8), kind="image"), {}, {"fs": 1.0})
    assert p["n_images"] == 0 and "empty" in p["summary"] and "pixels_b64" not in p


def test_symbolic_strip_uses_the_encoders_own_letters_when_given():
    syms = np.array([2, 3, 4, 0, 1, 2])
    p = to_payload("encoding", Encoding(values=syms, kind="symbolic"),
                   {"letters": "SUudDS", "alphabet": "dDSUu", "details": {"samples_per_symbol": 10, "alphabet_size": 5}}, {"fs": 1.0, "n_samples": 60})
    assert p["letters"] == "SUudDS" and p["alphabet"] == "dDSUu" and p["alphabet_size"] == 5
    q = to_payload("encoding", Encoding(values=syms, kind="symbolic"), {}, {"fs": 1.0, "n_samples": 60})
    assert q["letters"] == "cdeabc"


def test_spanset_payload_adds_the_spans_offset():
    p = to_payload("spanset", SpanSet(starts=(10, 40), ends=(20, 50), labels=("a", "b")), {}, {"fs": 2.0, "span_start": 100})
    assert p["start_s"] == [55.0, 70.0] and p["end_s"] == [60.0, 75.0]
    e = to_payload("spanset", SpanSet(starts=(), ends=()), {}, {"fs": 1.0})
    assert e["n"] == 0 and "threshold" not in e["summary"]


# ----------------------------------------------- a sparse image (fixup-a 1) --
# `preprocessing.wavelet_transform` leaves roughly half its columns NaN by
# design (a chunk is falling-edge -> next rising-edge, so every rising -> next
# falling interval is never covered). Block-averaging that with `.mean()` makes
# every output cell NaN as soon as the block factor is > 1, which is the case on
# every real span: the image goes black and `value_range` reports [0, 1], a
# number that is not true of the data. The existing tests cannot see it because
# they all use a 300-sample synthetic where the block factor is 1.

def _sparse(h=64, w=1200, lo=10.0, hi=20.0, seed=3):
    """A wide image with every other column NaN — the Dehshibi pattern."""
    vals = np.random.default_rng(seed).uniform(lo, hi, size=(h, w))
    vals[:, 1::2] = np.nan
    return vals


def _pixels(p):
    return np.frombuffer(base64.b64decode(p["pixels_b64"]), dtype=np.uint8)


def test_a_wide_image_with_nan_columns_still_paints_its_finite_values():
    vals = _sparse()
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0})
    assert p["display_shape"][1] < vals.shape[1], "the block factor must be > 1 or this test proves nothing"
    assert p["value_range"] is not None, "half the columns are finite; the range is knowable"
    lo, hi = p["value_range"]
    assert 10.0 <= lo < hi <= 20.0, f"range {p['value_range']} is not the data's range"
    assert _pixels(p).max() > 0, "the image painted uniform black over finite data"


def test_an_all_nan_block_is_marked_rather_than_painted_as_a_value():
    vals = np.random.default_rng(4).uniform(10.0, 20.0, size=(64, 512))
    vals[:, 10:12] = np.nan          # exactly one output cell column (block width 2)
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0})
    rows, cols = p["display_shape"]
    assert p["nan_cells"] == rows, f"one blanked column of {rows} cells should be marked, got {p['nan_cells']}"
    assert p["all_nan"] is False
    mask = np.frombuffer(base64.b64decode(p["nan_b64"]), dtype=np.uint8).reshape(rows, cols)
    assert mask[:, 5].all() and mask.sum() == rows, "the mask must name the blank cells and only those"


def test_an_entirely_nan_image_says_so_in_words_instead_of_claiming_a_range():
    vals = np.full((64, 512), np.nan)
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0})
    assert p["all_nan"] is True
    assert p["value_range"] is None, "there is no range; [0, 1] would be a claim about data that is not there"
    assert "no finite" in p["summary"].lower(), f"the payload must say so in words: {p['summary']!r}"


def test_a_capped_grouping_says_so_in_its_summary():
    """fixup-a item 10: `serialize.py` ships `labels[:5000]` with
    `capped: true` and `GroupingR` never surfaced it, so past 5,000 windows the
    colour strip truncated in silence."""
    from Working.types import Grouping
    labels = np.arange(6000) % 3
    p = to_payload("grouping", Grouping(labels=labels), {}, {"fs": 1.0})
    assert p["capped"] is True and len(p["labels"]) == 5000
    assert p["n_shown"] == 5000
    assert "5,000" in p["summary"] and "6,000" in p["summary"], p["summary"]


# ------------------------------------------- a SpanSet with features (fixup-d) --
# `SpanSet.features` is a new shape inside the SpanSet type: the feature blocks
# (`interrogation.event_shape`, `interrogation.intervals`) carry one row of
# measures per span. The payload ships them the way a WindowSet ships its own
# (columns, a capped matrix, per-column ranges), and passes the blocks' printed
# rules, the rose and the interval statistics through from `meta`, so the page
# draws the measurement it was given and never re-derives one.

def test_a_spanset_with_features_ships_the_feature_table():
    import pandas as pd
    feats = pd.DataFrame({"polarity": [-1, 1], "event_amplitude_mv": [10.0, 4.5], "recovery_time_s": [3.5, np.nan]})
    ss = SpanSet(starts=(10, 40), ends=(20, 50), features=feats)
    meta = {"rules": [{"name": "recovery", "rule": "half recovery"}],
            "rose": {"n": 2, "counts": [0] * 18, "bin_centres_deg": list(range(18)), "caption": "45° = 1 mV/s"},
            "interval_stats": {"all": {"n_events": 2, "cv": None}}, "events": "not passed through"}
    p = to_payload("spanset", ss, meta, {"fs": 2.0, "span_start": 100})
    f = p["features"]
    assert f["columns"] == ["polarity", "event_amplitude_mv", "recovery_time_s"] and f["n_columns"] == 3
    assert f["matrix"] == [[-1.0, 10.0, 3.5], [1.0, 4.5, None]]
    assert f["col_range"][2] == [3.5, 3.5]
    assert p["rules"] == meta["rules"] and p["rose"]["caption"] == "45° = 1 mV/s"
    assert p["interval_stats"] == {"all": {"n_events": 2, "cv": None}}
    assert "events" not in p
    assert "3 features" in p["summary"]


def test_a_spanset_without_features_says_none_and_nothing_else_changes():
    p = to_payload("spanset", SpanSet(starts=(10,), ends=(20,)), {}, {"fs": 1.0})
    assert p["features"] is None
    assert "rules" not in p and "rose" not in p
    assert "features" not in p["summary"]


# ----------------------------------------- the detector's funnel (fixup-j) --
# `detection.summation_threshold` puts every stage's regions in `meta["funnel"]`
# in span samples, half-open. The page needs them where it draws the spans:
# in absolute seconds, with the count that was actually found beside the ones
# it was sent (the cap is the spans' own).

def test_a_spanset_with_a_funnel_ships_every_stage_in_absolute_seconds():
    meta = {"funnel": {"chunks": [[0, 100]], "omega_peaks": [30], "omega_valleys": [60],
                       "stages": [{"key": "B", "label": "candidate regions", "n": 2, "regions": [[10, 20], [40, 50]]},
                                  {"key": "S", "label": "spikes", "n": 1, "regions": [[10, 50]]}]}}
    p = to_payload("spanset", SpanSet(starts=(10,), ends=(50,)), meta, {"fs": 2.0, "span_start": 100})
    f = p["funnel"]
    assert [s["key"] for s in f["stages"]] == ["B", "S"]
    assert f["stages"][0] == {"key": "B", "label": "candidate regions", "n": 2, "capped": False,
                              "start_s": [55.0, 70.0], "end_s": [60.0, 75.0]}
    assert f["stages"][1]["start_s"] == [55.0] and f["stages"][1]["end_s"] == [75.0]
    assert f["chunks_s"] == [[50.0, 100.0]]
    assert f["peaks_s"] == [65.0] and f["valleys_s"] == [80.0]


def test_a_spanset_without_a_funnel_has_no_funnel_key():
    assert "funnel" not in to_payload("spanset", SpanSet(starts=(10,), ends=(20,)), {}, {"fs": 1.0})


# ----------------------------------------- what the seven views need (fixup-h) --
# Each type view draws from its payload alone. These are the fields the views
# added: a SpanSet says how many events each span's window holds (by SAMPLE
# RANGE, never by a window index), an image Encoding ships sampled frames with
# the chunk of signal each came from, a WindowSet separates its split from its
# features, a Grouping names one exemplar per cluster, and a Model's card keeps
# the per-class accuracy.

def test_a_spanset_counts_the_spans_in_each_window_by_sample_range():
    ss = SpanSet(starts=(0, 50, 60, 200), ends=(40, 100, 90, 240))
    p = to_payload("spanset", ss, {}, {"fs": 1.0})
    assert p["window_count_of"] == "spans"
    assert p["window_counts"] == [1, 2, 2, 1], "the second and third spans share samples; the others stand alone"


def test_a_detector_that_names_its_falls_is_counted_in_falls_not_in_windows():
    """`DETECTION_AND_FIGURES.md` 5b: overlapping snippet context is not double-counting (261 of 1058 snippet
    spans overlap, 1 onset->trough pair does). A window is impure when it holds more than one FALL."""
    ss = SpanSet(starts=(0, 50), ends=(100, 150))
    events = [{"onset_idx": 20, "trough_idx": 30}, {"onset_idx": 70, "trough_idx": 80}]
    p = to_payload("spanset", ss, {"events": events}, {"fs": 2.0, "span_start": 1000})
    assert p["window_count_of"] == "falls"
    assert p["window_counts"] == [2, 1], "window 0 holds both falls; window 1 holds only its own"
    assert p["marks"]["onset_s"] == [510.0, 535.0] and p["marks"]["extremum_s"] == [515.0, 540.0]


def test_a_feature_blocks_anchors_are_the_marks_when_the_table_carries_them():
    import pandas as pd
    feats = pd.DataFrame({"onset_idx": [12, 55], "extremum_idx": [18, 61], "event_amplitude_mv": [1.0, 2.0]})
    p = to_payload("spanset", SpanSet(starts=(10, 50), ends=(30, 70), features=feats), {}, {"fs": 1.0, "span_start": 100})
    assert p["marks"]["onset_s"] == [112.0, 155.0] and p["marks"]["extremum_s"] == [118.0, 161.0]
    assert p["window_count_of"] == "falls" and p["window_counts"] == [1, 1]


def test_a_spanset_with_no_anchors_has_no_marks():
    p = to_payload("spanset", SpanSet(starts=(10,), ends=(20,)), {}, {"fs": 1.0})
    assert p["marks"] is None


def test_a_windowset_ships_its_split_apart_from_its_features():
    """`preprocessing.sliding_windows` carries NO features: its table is the split column alone, and the heatmap
    used to draw that column as if it were a measure."""
    import pandas as pd
    from Working.types import WindowSet
    ws = WindowSet(starts=np.array([0, 600, 1200, 1800]), length=600, fs=1.0, features=pd.DataFrame({"split": [0, 0, 1, 2]}))
    p = to_payload("windowset", ws, {}, {"fs": 1.0})
    assert p["features"] is None, "a split column alone is not a feature matrix"
    assert p["split"]["labels"] == [0, 0, 1, 2]
    assert p["split"]["names"] == {"0": "train", "1": "validation", "2": "test"}
    assert p["split"]["counts"] == {"train": 2, "validation": 1, "test": 1}
    both = WindowSet(starts=np.array([0, 600]), length=600, fs=1.0, features=pd.DataFrame({"split": [0, 2], "mean": [1.0, 2.0]}))
    q = to_payload("windowset", both, {}, {"fs": 1.0})
    assert q["features"]["columns"] == ["mean"] and q["split"]["labels"] == [0, 2]
    plain = WindowSet(starts=np.array([0, 600]), length=600, fs=1.0, features=pd.DataFrame({"mean": [1.0, 2.0]}))
    assert to_payload("windowset", plain, {}, {"fs": 1.0})["split"] is None


def _frame_pixels(frame):
    h, w = frame["shape"]
    return np.frombuffer(base64.b64decode(frame["pixels_b64"]), dtype=np.uint8).reshape(h, w, -1)


def test_a_time_aligned_image_ships_three_sampled_chunks_and_where_each_came_from():
    """One column per sample: a frame is a chunk of columns at the image's own resolution, not the whole span
    block-averaged to 256 px, and each says which seconds of the signal it is."""
    from server.serialize import FRAME_COLUMNS, FRAMES_SHOWN
    n = 4 * FRAME_COLUMNS + 10
    vals = np.tile(np.arange(n, dtype=float), (16, 1))
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 2.0, "span_start": 100, "n_samples": n})
    fr = p["frames"]
    assert fr["axis"] == "time" and fr["n"] == 5
    assert [f["index"] for f in fr["shown"]] == [0, 2, 4] and len(fr["shown"]) == FRAMES_SHOWN
    first, last = fr["shown"][0], fr["shown"][-1]
    assert first["t0_s"] == 50.0 and first["t1_s"] == (100 + FRAME_COLUMNS) / 2.0
    assert last["t1_s"] == (100 + n) / 2.0, "the last chunk ends where the span ends"
    assert first["shape"] == [16, FRAME_COLUMNS], "a chunk is drawn at the image's own resolution"
    assert fr["value_range"] == [0.0, float(n - 1)], "one real range for every frame, so one colour bar is true of all of them"
    assert _frame_pixels(first).max() < _frame_pixels(last).min(), "frames share the range: a later chunk of a ramp is brighter"


def test_an_image_stack_ships_three_sampled_images_and_the_window_each_is():
    from Working.types import WindowSet
    stack = np.random.default_rng(0).integers(0, 255, size=(7, 32, 32, 3), dtype=np.uint8)
    ws = WindowSet(starts=np.arange(7) * 600, length=600, fs=1.0)
    p = to_payload("encoding", Encoding(values=stack, kind="image"), {}, {"fs": 1.0, "windowset": ws})
    fr = p["frames"]
    assert fr["axis"] == "stack" and fr["n"] == 7 and [f["index"] for f in fr["shown"]] == [0, 3, 6]
    assert fr["shown"][1]["t0_s"] == 1800.0 and fr["shown"][1]["t1_s"] == 2400.0
    assert fr["shown"][0]["channels"] == 3
    bare = to_payload("encoding", Encoding(values=stack, kind="image"), {}, {"fs": 1.0})["frames"]
    assert bare["shown"][0]["t0_s"] is None, "without the window set at hand the frame does not guess where it came from"


def test_an_image_that_is_not_time_aligned_is_one_frame_of_the_whole_span():
    vals = np.random.default_rng(1).uniform(size=(64, 64))
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0, "span_start": 0, "n_samples": 1000})
    fr = p["frames"]
    assert fr["axis"] == "whole" and fr["n"] == 1 and len(fr["shown"]) == 1
    assert fr["shown"][0]["t0_s"] == 0.0 and fr["shown"][0]["t1_s"] == 1000.0


def test_any_one_frame_can_be_asked_for_by_index():
    """The settings page scans through the frames that were not sampled."""
    from server.serialize import FRAME_COLUMNS, frame_payload
    n = 3 * FRAME_COLUMNS
    vals = np.tile(np.arange(n, dtype=float), (8, 1))
    ctx = {"fs": 1.0, "span_start": 0, "n_samples": n}
    f = frame_payload(Encoding(values=vals, kind="image"), {}, ctx, 1)
    assert f["index"] == 1 and f["t0_s"] == float(FRAME_COLUMNS) and f["shape"] == [8, FRAME_COLUMNS]
    with pytest.raises(IndexError):
        frame_payload(Encoding(values=vals, kind="image"), {}, ctx, 3)


def test_a_frame_marks_its_no_data_cells_rather_than_painting_them():
    from server.serialize import FRAME_COLUMNS
    vals = np.ones((8, 2 * FRAME_COLUMNS))
    vals[:, :10] = np.nan
    p = to_payload("encoding", Encoding(values=vals, kind="image"), {}, {"fs": 1.0, "n_samples": 2 * FRAME_COLUMNS})
    first = p["frames"]["shown"][0]
    mask = np.frombuffer(base64.b64decode(first["nan_b64"]), dtype=np.uint8).reshape(first["shape"])
    assert mask[:, :10].all() and mask.sum() == 80


def test_a_grouping_names_one_exemplar_per_cluster():
    """The window nearest its cluster's centroid in the feature space the clustering saw - a member, never an
    average - or the cluster's first window when the features are not at hand, and it says which."""
    import pandas as pd
    from Working.types import Grouping, WindowSet
    feats = pd.DataFrame({"a": [0.0, 1.0, 10.0, 20.0, 21.0, 30.0], "split": [0, 0, 0, 0, 0, 0]})
    ws = WindowSet(starts=np.arange(6) * 60, length=60, fs=1.0, features=feats)
    g = Grouping(labels=np.array([1, 1, 1, 2, 2, 2]))
    p = to_payload("grouping", g, {}, {"fs": 1.0, "windowset": ws})
    ex = {e["cluster"]: e for e in p["exemplars"]}
    assert set(ex) == {1, 2}
    assert ex[1]["window"] == 1 and ex[1]["start_s"] == 60.0 and ex[1]["length_s"] == 60.0
    assert ex[2]["window"] == 4 and "centroid" in ex[1]["rule"]
    bare = to_payload("grouping", g, {}, {"fs": 1.0})
    assert bare["exemplars"] == [], "with no window set there is no window to draw"


def test_a_model_card_keeps_the_accuracy_per_class():
    from Working.types import Model
    meta = {"holdout_accuracy": 0.75, "n_classes": 2, "per_class_accuracy": {1: 1.0, 2: 0.5}, "holdout_class_counts": {1: 4, 2: 4}}
    p = to_payload("model", Model(path="nowhere.joblib"), meta, {})
    assert p["card"]["per_class_accuracy"] == {"1": 1.0, "2": 0.5}
    assert p["card"]["holdout_class_counts"] == {"1": 4, "2": 4}


# ----------------------------------------- the frames a run holds for scanning --

def test_pruning_held_frames_survives_jobs_that_are_not_chain_runs():
    """The bridge keeps every kind of job in one table. A Discovery job has no `frame_sources`, and reading it
    off every job turned each chain run into a 500 once one existed."""
    from types import SimpleNamespace
    from server.runs import prune_frame_sources
    jobs = {1: SimpleNamespace(frame_sources={0: "a"}), 2: SimpleNamespace(kind="sweep"),
            3: SimpleNamespace(frame_sources={0: "b"}), 4: SimpleNamespace(frame_sources={}),
            5: SimpleNamespace(frame_sources={1: "c"}), 6: SimpleNamespace(frame_sources={0: "d"})}
    prune_frame_sources(jobs, keep=2)
    assert jobs[1].frame_sources == {} and jobs[3].frame_sources == {}, "the oldest holders are released"
    assert jobs[5].frame_sources == {1: "c"} and jobs[6].frame_sources == {0: "d"}, "the newest two keep theirs"
    assert not hasattr(jobs[2], "frame_sources"), "a job of another kind is left alone"


# ----------------------------------------- fixup-ac: a signal that carries its layers --

def test_a_signal_carrying_wavelet_layers_ships_each_on_the_absolute_time_axis():
    """`preprocessing.wavelet_bands` passes ONE layer on and puts every layer in
    `meta["layers"]` as a span-relative min/max envelope. The payload ships each
    layer on the channel's absolute seconds, converted to mV like the trace, with
    its Hz range and whether it is the one that went on."""
    from Adapters.registry import discover_adapters, get_adapter
    from Working.types import Signal

    discover_adapters()
    spec = get_adapter("preprocessing.wavelet_bands")
    x = np.random.default_rng(0).standard_normal(3000).cumsum() * 1e-3      # volts
    res = spec.run(x, np.arange(3000) / 2.0, 2.0, **spec.validate_params({"level": 3, "levels": 5}))
    p = to_payload("signal", res.value, res.meta, {"fs": 2.0, "span_start": 1000, "px": 400, "units": "V"})
    assert p["type"] == "signal" and p["unit"] == "mV"
    layers = p["layers"]
    assert [L["name"] for L in layers] == ["D1", "D2", "D3", "D4", "D5", "A5"]
    d3 = next(L for L in layers if L["name"] == "D3")
    assert d3["chosen"] is True and (d3["low_hz"], d3["high_hz"]) == (0.125, 0.25)
    env = d3["envelope"]
    assert env["t"][0] >= 1000 / 2.0 and env["t"][-1] < (1000 + 3000) / 2.0, "absolute seconds, span offset added"
    # the chosen layer's envelope is the value's own samples, in mV
    raw_lo = float(np.min(res.value.x)) * 1000.0
    assert min(v for v in env["v"] if v is not None) == pytest.approx(raw_lo)
    assert p["decomposition"]["wavelet"] == "db4" and p["decomposition"]["levels"] == 5
    assert p["decomposition"]["padding"]["padded_to"] % 32 == 0


def test_a_signal_without_layers_ships_none():
    from Working.types import Signal
    p = to_payload("signal", Signal(x=np.arange(10.0), fs=1.0), {}, {"fs": 1.0})
    assert "layers" not in p


def test_layers_lost_to_a_cached_step_say_so_rather_than_vanish():
    """On a step-cache hit the bridge reads `meta` back from a JSON sidecar; the
    layers survive it because each envelope is small. A sidecar written before
    they were (or one that lost them) must be said on the payload, not silently
    drawn as a plain signal."""
    from Working.types import Signal
    meta = {"layer": "D2", "level": 2, "levels": 4, "wavelet": "db4"}
    p = to_payload("signal", Signal(x=np.arange(10.0), fs=1.0), meta, {"fs": 1.0})
    assert p["layers"] == [] and "not in this step's record" in p["layers_note"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

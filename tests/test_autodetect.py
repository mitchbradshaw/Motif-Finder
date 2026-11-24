"""Auto-detect prototype (2026-11-19): the blend, R4's scan peaks, the merge, sequences, the seed search and the
in-memory chain runner. Headless and fast: no database, no channel files, fake adapters for the chain runner."""

import math
import types

import numpy as np
import pandas as pd
import pytest

from Working.autodetect import blend, candidates as C, chains, scan, seeds, sequences


# ── blend ───────────────────────────────────────────────────────────────────

def test_confidence_is_r4_alone_when_nothing_agrees():
    assert blend.confidence(0.37, []) == pytest.approx(0.37)


def test_confidence_worked_example_from_the_grilling():
    one = blend.confidence(0.10, ["drop_detection_v1"])
    assert one == pytest.approx(0.10 + 0.90 * 0.5 * 0.955)          # 0.52975
    two = blend.confidence(0.10, ["drop_detection_v1", "seed"])
    assert two == pytest.approx(1 - 0.90 * (1 - 0.4775) * (1 - 0.45))
    assert 0.74 < two < 0.75


def test_agreement_only_raises_and_r4_scan_never_reinforces():
    base = blend.confidence(0.6, [])
    assert blend.confidence(0.6, ["BEADs_invert_detect_v1"]) > base
    assert blend.confidence(0.6, [blend.R4_SCAN]) == pytest.approx(base)


def test_unreadable_r4_counts_as_zero_and_floor_matches():
    assert blend.confidence(float("nan"), ["seed"]) == pytest.approx(0.45)
    assert blend.floor_of(["seed"]) == pytest.approx(0.45)


def test_unknown_source_is_refused():
    with pytest.raises(KeyError):
        blend.confidence(0.5, ["no_such_detector"])


def test_contributions_end_at_the_confidence():
    steps = blend.contributions(0.2, ["seed", "drop_detection_v5"])
    assert [s for s, _ in steps] == ["r4", "drop_detection_v5", "seed"]
    assert steps[-1][1] == pytest.approx(blend.confidence(0.2, ["seed", "drop_detection_v5"]))


# ── scan ────────────────────────────────────────────────────────────────────

def test_windows_step_by_a_quarter_and_stay_inside():
    s, e, d = scan.windows(1000, 1.0, durations_s=(100.0, 400.0))
    assert set(d) == {100.0, 400.0}
    assert (e <= 1000).all() and (s >= 0).all()
    w100 = s[d == 100.0]
    assert np.all(np.diff(w100) == 25)


def test_peaks_keep_the_summit_of_overlapping_hits():
    starts = np.array([0, 50, 100, 1000])
    ends = np.array([200, 250, 300, 1200])
    p = np.array([0.6, 0.9, 0.7, 0.55])
    keep = scan.peaks(starts, ends, p, min_p=0.5)
    assert list(keep) == [1, 3]


def test_peaks_drop_below_min_p_and_nan():
    keep = scan.peaks([0, 500], [100, 600], [0.49, float("nan")], min_p=0.5)
    assert len(keep) == 0


def test_a_short_hit_inside_a_long_one_is_the_same_place():
    keep = scan.peaks([0, 400], [1800, 520], [0.8, 0.95], min_p=0.5)
    assert list(keep) == [1]


# ── candidates ──────────────────────────────────────────────────────────────

def test_absorb_folds_a_loose_box_into_its_one_tight_event():
    into = C.absorb_loose([0, 300], [1200, 677])          # loose drop-v1 box, a 377-sample match inside
    assert list(into) == [1, 1]


def test_absorb_keeps_a_box_that_holds_two_events():
    into = C.absorb_loose([0, 100, 700], [1200, 300, 900])
    assert into[0] == 0


def test_absorb_needs_the_tight_one_to_be_big_enough():
    into = C.absorb_loose([0, 500], [10_000, 520], min_ratio=0.1)
    assert into[0] == 0


def test_absorb_resolves_a_box_around_a_box():
    into = C.absorb_loose([0, 200, 300], [2000, 900, 677])
    assert list(into) == [2, 2, 2]


def _props(rows):
    return pd.DataFrame(rows, columns=["start", "end", "variant"])


def test_merge_draws_one_event_by_its_tight_box_with_both_sources():
    p = _props([(0, 1200, "drop_detection_v1"), (300, 677, "seed__F-02"), (5000, 5400, "BEADs_invert_detect_v1")])
    m = C.merge(p)
    assert len(m) == 2
    first = m.iloc[0]
    assert (first["start"], first["end"]) == (300, 677)
    assert set(first["sources"].split("|")) == {"drop_detection_v1", "seed"}
    assert m.iloc[1]["sources"] == "BEADs_invert_detect_v1"


def test_merge_joins_the_same_event_from_two_sources():
    p = _props([(100, 500, "drop_detection_v5"), (110, 505, "wavelet_encoded")])
    m = C.merge(p)
    assert len(m) == 1 and m.iloc[0]["n_sources"] == 2


def test_near_duplicates_fold_but_a_train_does_not_chain():
    # two seed families on one 20-sample drop, 8 samples apart (IoU 0.43: the same-event rule keeps them apart)
    into = C.fold_near_duplicates([100, 108], [120, 128], [2, 1])
    assert list(into) == [0, 0]
    # three events in a row, each overlapping the next by half: the survivor keeps its own span, so the third stays
    into = C.fold_near_duplicates([0, 10, 20], [20, 30, 40], [3, 2, 1])
    assert list(into) == [0, 0, 2]
    # a long box is not a near-duplicate of a short event inside it (that is absorb_loose's case)
    into = C.fold_near_duplicates([0, 50], [400, 70], [1, 2])
    assert list(into) == [0, 1]


def test_merge_folds_two_offset_seed_matches_into_one_candidate():
    p = _props([(100, 120, "seed__F-46"), (108, 128, "seed__F-47"), (5000, 5020, "seed__F-46")])
    m = C.merge(p)
    assert len(m) == 2
    assert set(m.iloc[0]["member_variants"].split("|")) == {"seed__F-46", "seed__F-47"}


def test_merge_of_nothing_is_an_empty_frame():
    assert len(C.merge(_props([]))) == 0


def test_scan_hits_on_a_candidate_add_nothing_but_their_score():
    cands = C.score(C.merge(_props([(1000, 1400, "drop_detection_v5")])), [0.3])
    hits = pd.DataFrame({"start": [900, 9000], "end": [1500, 9600], "p": [0.8, 0.7], "duration_s": [600.0, 600.0]})
    out, own = C.attach_scan(cands, hits)
    assert out.iloc[0]["scan_p"] == pytest.approx(0.8)
    assert out.iloc[0]["confidence"] == pytest.approx(blend.confidence(0.3, ["drop_detection_v5"]))
    assert list(own["start"]) == [9000]


# ── sequences ───────────────────────────────────────────────────────────────

def _cands(starts, conf):
    s = np.asarray(starts, dtype=np.int64)
    return pd.DataFrame({"start": s, "end": s + 5, "confidence": conf})


def test_too_few_confident_candidates_make_no_sequence():
    labels, seqs, info = sequences.find_sequences(_cands([0, 10, 20, 30], [0.9] * 4), 1.0)
    assert (labels == -1).all() and len(seqs) == 0


def test_bursts_are_found_by_logisi():
    rng = np.random.default_rng(1)
    starts = []
    for k in range(8):                                   # 8 bursts of 8 events, 10-20 s apart, bursts 1e5 s apart
        base = k * 100_000
        starts.extend(base + np.cumsum(rng.uniform(10, 20, 8)))
    labels, seqs, info = sequences.find_sequences(_cands(np.round(starts), [0.9] * len(starts)), 1.0)
    assert info["rule"] == "logisi"
    assert len(seqs) == 8 and (seqs["n_members"] == 8).all()


def test_one_hump_of_gaps_falls_back_to_the_one_hour_rule():
    rng = np.random.default_rng(2)
    gaps = rng.uniform(500, 1500, 29)                    # one hump: logISI finds no valley
    starts = np.round(np.concatenate([[0.0], np.cumsum(gaps)]))
    labels, seqs, info = sequences.find_sequences(_cands(starts, [0.9] * len(starts)), 1.0)
    assert info["rule"].startswith("gap <=")
    assert seqs["n_members"].tolist() == [30]


def test_the_gap_rule_skips_logisi_even_when_bursts_are_clear():
    starts = [k * 100_000 + j * 15 for k in range(4) for j in range(6)]
    labels, seqs, info = sequences.find_sequences(_cands(starts, [1.0] * len(starts)), 1.0, rule="gap")
    assert info["rule"].startswith("gap <=") and len(seqs) == 4
    with pytest.raises(ValueError):
        sequences.find_sequences(_cands(starts, [1.0] * len(starts)), 1.0, rule="nope")


def test_low_confidence_candidates_stay_out_of_sequences():
    starts = np.arange(0, 10) * 600
    conf = [0.9] * 5 + [0.4] * 5
    labels, seqs, info = sequences.find_sequences(_cands(starts, conf), 1.0)
    assert (labels[5:] == -1).all()
    assert info["n_in"] == 5


# ── seeds ───────────────────────────────────────────────────────────────────

def _drop(n):
    t = np.linspace(0, 1, n)
    return np.where(t < 0.3, 0.0, -np.exp(-(t - 0.3) * 6))


def test_seed_search_finds_planted_copies_and_respects_the_floor():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 0.01, 20_000)
    shape = _drop(100)
    for at in (2_000, 9_000, 15_000):
        x[at:at + 100] += 5.0 * shape
    x[12_000:12_100] += 0.02 * shape                       # a copy far below the floor
    fam = seeds.SeedFamily(label="F-T", exemplar_mv=shape * 3.0, exemplar_fs=1.0, durations_s=(100.0, 100.0, 100.0),
                           min_corr=0.96, n_members=10)
    matches, report = seeds.search(x, 1.0, [fam], floor_mv=0.5)
    found = sorted(int(s) for s in matches["start"])
    assert len(found) == 3
    assert all(min(abs(f - at) for at in (2_000, 9_000, 15_000)) <= 3 for f in found)
    assert report[0]["lengths"] == [100]                   # coinciding quartiles searched once
    assert set(matches["source"]) == {"seed"}
    assert all(v.startswith("seed__") for v in matches["variant"])


def test_a_loose_family_is_reported_not_searched():
    rng = np.random.default_rng(4)
    x = rng.normal(0, 1.0, 5_000)
    loose = seeds.SeedFamily(label="F-L", exemplar_mv=_drop(50), exemplar_fs=1.0, durations_s=(50.0,), min_corr=0.8,
                             n_members=12)
    matches, report = seeds.search(x, 1.0, [loose], floor_mv=0.0, min_family_line=0.95)
    assert len(matches) == 0
    assert report[0]["skipped"] and report[0]["lengths"] == []
    matches, report = seeds.search(x, 1.0, [loose], floor_mv=0.0, min_family_line=None)
    assert report[0]["skipped"] is None and report[0]["lengths"] == [50]


def test_to_length_shrinks_by_bin_means_and_stretches_linearly():
    assert np.allclose(seeds.to_length(np.arange(10.0), 5), [0.5, 2.5, 4.5, 6.5, 8.5])
    assert np.allclose(seeds.to_length(np.array([0.0, 1.0]), 3), [0.0, 0.5, 1.0])


def test_correlation_matches_the_distance_identity():
    rng = np.random.default_rng(3)
    a, b = rng.normal(size=64), rng.normal(size=64)
    za, zb = (a - a.mean()) / a.std(), (b - b.mean()) / b.std()
    d = np.linalg.norm(za - zb)
    assert seeds.correlation(a, b) == pytest.approx(1 - d ** 2 / (2 * 64))


# ── chains ──────────────────────────────────────────────────────────────────

def _fake_registry(monkeypatch, specs):
    monkeypatch.setattr(chains, "discover_adapters", lambda: None)
    monkeypatch.setattr(chains, "get_adapter", lambda name: specs[name])


def _spec(run, output_kind, input_kind="signal"):
    return types.SimpleNamespace(run=run, output_kind=output_kind, input_kind=input_kind, max_span_samples=None,
                                 validate_params=lambda p: dict(p or {}))


def test_chain_runner_threads_signal_value_and_units(monkeypatch):
    seen = {}

    def double(x, t, fs):
        return types.SimpleNamespace(output_kind="signal", value=types.SimpleNamespace(x=2 * x))

    def encode(x, t, fs, units=None):
        seen["units"] = units
        seen["x0"] = float(x[0])
        return types.SimpleNamespace(output_kind="encoding", value="ENC")

    def detect(x, t, fs, value=None, k=1):
        seen["value"] = value
        seen["t0"] = float(t[0])
        return types.SimpleNamespace(output_kind="spanset",
                                     value=types.SimpleNamespace(starts=(1, 5), ends=(3, 9), scores=(0.5, None)))

    _fake_registry(monkeypatch, {"preprocessing.double": _spec(double, "signal"),
                                 "detection.encode": _spec(encode, "encoding"),
                                 "detection.detect": _spec(detect, "spanset", input_kind="encoding")})
    steps = [{"stage": "preprocessing", "algorithm": "double", "params": {}},
             {"stage": "detection", "algorithm": "encode", "params": {}},
             {"stage": "detection", "algorithm": "detect", "params": {"k": 2}}]
    out = chains.run_chain(steps, np.ones(20), 2.0, start_idx=10, units="V")
    assert seen == {"units": "V", "x0": 2.0, "value": "ENC", "t0": 5.0}
    assert list(out["starts"]) == [1, 5] and list(out["ends"]) == [3, 9]
    assert out["scores"][0] == 0.5 and math.isnan(out["scores"][1])
    assert len(out["timings"]) == 3


def test_chain_runner_refuses_side_inputs_and_a_shrinking_signal(monkeypatch):
    def shrink(x, t, fs):
        return types.SimpleNamespace(output_kind="signal", value=types.SimpleNamespace(x=x[:-1]))

    _fake_registry(monkeypatch, {"preprocessing.shrink": _spec(shrink, "signal")})
    with pytest.raises(chains.ChainError):
        chains.run_chain([{"stage": "preprocessing", "algorithm": "shrink", "params": {}, "side_inputs": {"a": 1}}],
                         np.ones(5), 1.0)
    with pytest.raises(chains.ChainError):
        chains.run_chain([{"stage": "preprocessing", "algorithm": "shrink", "params": {}}], np.ones(5), 1.0)


# ── v2 (2026-11-23): event boxes, gates, windows ───────────────────────────

from Working.autodetect import anchor as AN, gates as G  # noqa: E402


def _sharkfin(n=2000, at=1000, depth=5.0, fall=10, recover=200, noise=0.0, seed=0):
    """A flat baseline, a fall of `depth` over `fall` samples at `at`, and an exponential recovery."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    x[at:at + fall] = -depth * np.arange(1, fall + 1) / fall
    t = np.arange(n - at - fall)
    x[at + fall:] = -depth * np.exp(-t / (recover / 3.0))
    return x + noise * rng.normal(size=n)


def test_a_slice_of_the_steep_part_is_redrawn_onset_to_half_recovery():
    x = _sharkfin(noise=0.01)
    r = AN.anchor_one(x, 1003, 1008, 1.0)               # a 5-sample slice inside the fall
    assert r["ok"] and r["polarity"] == "drop"
    assert abs(r["onset"] - 999) <= 2                  # the shoulder the fall departs from
    assert abs(r["extremum"] - 1009) <= 2
    assert r["recovered"] and 1009 < r["end"] < 1009 + 200
    assert r["box_start"] < r["onset"] and r["box_end"] > r["end"]


def test_a_box_much_wider_than_its_event_shrinks_to_it():
    x = _sharkfin(noise=0.01)
    r = AN.anchor_one(x, 600, 1600, 1.0)
    assert r["ok"] and abs(r["extremum"] - 1009) <= 2
    assert r["box_end"] - r["box_start"] < 200


def test_an_upward_spike_is_boxed_like_a_drop():
    x = -_sharkfin(noise=0.01)
    r = AN.anchor_one(x, 990, 1030, 1.0)
    assert r["ok"] and r["polarity"] == "spike" and r["depth_mv"] == pytest.approx(5.0, rel=0.05)


def test_a_steep_start_with_a_slow_tail_is_boxed_to_the_tail_bottom():
    n = 4000
    x = np.zeros(n)
    x[1000:1005] = -np.linspace(1, 50, 5)                # the cliff
    t = np.arange(n - 1005)
    x[1005:] = -50 - 100 * (1 - np.exp(-t / 150.0))      # then a slow settle of another 100 to a floor
    x = x + 0.02 * np.random.default_rng(5).normal(size=n)
    r = AN.anchor_one(x, 995, 1395, 1.0)                 # a BEADS-like 400-sample box round the cliff
    assert r["ok"] and not r["recovered"]
    assert r["depth_mv"] > 120                           # the whole drop (the Library's rule), not just the cliff
    assert r["end"] > 1300


def _anchored(rows):
    return pd.DataFrame(rows, columns=list(AN.COLUMNS))


def test_boxes_with_one_trough_are_one_event_and_others_stay():
    a = _anchored([
        (True, None, "drop", 100, 110, 150, True, 5.0, 95, 155),
        (True, None, "drop", 99, 111, 152, True, 5.0, 94, 157),     # the same trough, one sample apart
        (True, None, "drop", 300, 310, 350, True, 5.0, 295, 355),   # another event
        (True, None, "spike", 100, 110, 150, True, 5.0, 95, 155),   # same place, other direction: not the same
    ])
    into = AN.same_event(a, [3, 1, 1, 1])
    assert list(into) == [0, 0, 2, 3]


def test_overlapping_falls_are_one_event_drawn_by_the_deepest_box():
    # one big drop redrawn from four different boxes: four slightly different troughs on one fall
    a = _anchored([
        (True, None, "drop", 1000, 1300, 3400, False, 152.0, 900, 3700),
        (True, None, "drop", 1020, 1290, 1900, False, 128.0, 990, 1990),
        (True, None, "drop", 1030, 1060, 1200, False, 75.0, 1010, 1220),
        (True, None, "drop", 5000, 5020, 5100, True, 5.0, 4990, 5110),
    ])
    assert list(AN.same_event(a)) == [0, 0, 0, 3]


def test_a_step_in_a_fall_folds_but_events_in_its_recovery_or_settle_do_not():
    a = _anchored([
        (True, None, "drop", 100, 300, 900, False, 100.0, 90, 980),   # deep drop: falls 100->300, settles to 900
        (True, None, "drop", 200, 202, 210, True, 5.0, 198, 212),     # a step part-way down its fall: folds
        (True, None, "drop", 500, 505, 530, True, 5.0, 495, 535),     # a small drop in its settle: stays
        (True, None, "spike", 302, 304, 310, True, 0.2, 300, 312),    # the other edge read as a tiny spike: folds
    ])
    into = AN.fold_nested(a, np.arange(4))
    assert list(into) == [0, 0, 2, 0]


def test_a_square_drop_is_a_drop_even_when_it_recovers_as_fast():
    x = np.zeros(60)
    x[20:21] = -4.0
    x[21:40] = -8.0
    x[40:41] = -4.0          # falls and recovers in two equal steps
    assert AN.polarity_of(x) is True
    x = x + 0.01 * np.random.default_rng(6).normal(size=60)
    r = AN.anchor_one(x, 10, 50, 1.0)
    assert r["polarity"] == "drop" and r["depth_mv"] == pytest.approx(8.0, abs=0.1)


def test_flat_drift_is_explained_by_a_curve_and_a_drop_is_not():
    t = np.linspace(0, 1, 1800)
    drift = 4.5 * t - 1.2 * t ** 2
    assert G.unexplained_fraction(drift, 0, 1800, 1.0) < G.MIN_UNEXPLAINED
    drop = _sharkfin(n=1800, at=900)
    assert G.unexplained_fraction(drop, 600, 1400, 1.0) > G.MIN_UNEXPLAINED
    ok, fr = G.flat_mask(drift + drop, [0], [1800], 1.0)
    assert ok[0]


def test_beads_sigma_has_a_provisional_precision():
    assert blend.PRECISION["beads_sigma"] == pytest.approx(0.75)


def test_windowed_chain_keeps_one_event_once(monkeypatch):
    calls = []

    def detect(x, t, fs):
        calls.append(float(t[0]))
        # every window reports the one big drop at absolute sample 5_000 when it holds it
        s0 = int(round(t[0] * fs))
        spans = [(5_000 - s0, 5_020 - s0)] if s0 <= 5_000 < s0 + len(x) - 20 else []
        return types.SimpleNamespace(output_kind="spanset", value=types.SimpleNamespace(
            starts=tuple(a for a, _ in spans), ends=tuple(b for _, b in spans), scores=None))

    _fake_registry(monkeypatch, {"detection.detect": _spec(detect, "spanset")})
    steps = [{"stage": "detection", "algorithm": "detect", "params": {}}]
    out = chains.run_chain_windowed(steps, np.zeros(20_000), 1.0, window_s=4_000, start_idx=0)
    assert out["windows"] > 3 and len(calls) == out["windows"]
    assert list(out["starts"]) == [5_000] and list(out["ends"]) == [5_020]


def test_reanchor_makes_one_candidate_per_event_with_every_source():
    x = np.concatenate([_sharkfin(n=2000, at=1000, noise=0.01), _sharkfin(n=2000, at=1000, noise=0.01, seed=1)])
    p = _props([(400, 1700, "drop_detection_v1"), (1003, 1008, "beads_sigma"), (2600, 3700, "drop_detection_v5")])
    merged = C.merge(p)
    out, rep = C.reanchor(merged, p, x, 1.0)
    assert len(out) == 2 and out["anchored"].all()
    first = out.iloc[0]
    assert set(first["sources"].split("|")) == {"drop_detection_v1", "beads_sigma"}
    assert first["orig_start"] == 400 and first["end"] - first["start"] < 300


def test_a_long_box_holding_two_drops_gives_both_events():
    x = np.concatenate([_sharkfin(n=1500, at=500, noise=0.01), _sharkfin(n=1500, at=500, depth=4.0, noise=0.01, seed=2)])
    evs = AN.anchor_events(x, 300, 2700, 1.0)
    tops = sorted(int(e["onset"]) for e in evs if e["polarity"] == "drop")
    assert len(tops) == 2 and abs(tops[0] - 500) <= 3 and abs(tops[1] - 2000) <= 3
    # both polarities are measured: each drop's climb back comes too, and folds into its drop as its return
    an = _anchored([tuple(e[c] for c in AN.COLUMNS) for e in evs])
    into = AN.fold(an, AN.same_event(an))
    assert sorted(an.loc[np.unique(into), "polarity"]) == ["drop", "drop"]


def test_a_tiny_slice_at_the_bottom_of_a_fall_still_finds_the_fall():
    x = _sharkfin(noise=0.01)
    evs = AN.anchor_events(x, 1008, 1011, 1.0)          # three samples at the foot of the fall
    assert len(evs) == 1 and abs(int(evs[0]["onset"]) - 1000) <= 3


def test_a_box_over_nothing_points_at_no_event():
    x = 0.01 * np.random.default_rng(7).normal(size=3000)
    assert AN.anchor_events(x, 1000, 1400, 1.0) == []


def test_a_long_window_vouches_for_its_main_event_not_every_wiggle_in_it():
    ev = pd.DataFrame({"start": [100, 300, 700], "end": [140, 320, 740], "depth_mv": [10.0, 0.5, 8.0]})
    props = pd.DataFrame({"start": [0, 290], "end": [1000, 330], "variant": ["drop_detection_v1", "beads_sigma"]})
    src, n = C.agreement_by_main_events(ev, props)
    assert src == ["drop_detection_v1", "beads_sigma", "drop_detection_v1"]
    assert n == [1, 1, 1]


def test_the_rise_back_after_a_drop_is_not_a_spike_of_its_own():
    a = _anchored([
        (True, None, "drop", 100, 120, 200, True, 5.0, 90, 210),     # a drop, bottom at 120, recovering to 200
        (True, None, "spike", 121, 190, 260, True, 3.0, 110, 270),   # its rise back, read as a spike
        (True, None, "spike", 600, 620, 700, True, 3.0, 590, 710),   # a real spike later: stays
    ])
    assert list(AN.fold(a, np.arange(3))) == [0, 0, 2]



# ── v3 (2026-11-23): sharp rises, the run on the inverted signal ───────────

from Working.autodetect import pipeline as P  # noqa: E402


def test_sharpness_reads_a_cliff_as_sharp_and_a_ramp_as_not():
    rng = np.random.default_rng(11)
    cliff = 0.05 * rng.normal(size=4000)
    cliff[2000:] += 3.0                                  # up 3 mV in one sample
    ramp = 0.05 * rng.normal(size=4000)
    ramp[1000:3000] += np.linspace(0.0, 3.0, 2000)       # the same 3 mV over 2000 samples
    ramp[3000:] += 3.0
    for x in (cliff, ramp):
        assert G.step_noise(x, 1.0) == pytest.approx(0.05 * math.sqrt(2.0), rel=0.15)
    assert G.sharpness(cliff, 1995, 2005, 1.0, G.step_noise(cliff, 1.0)) > G.MIN_RISE_SHARPNESS
    assert G.sharpness(ramp, 1000, 3000, 1.0, G.step_noise(ramp, 1.0)) < G.MIN_RISE_SHARPNESS


def _cand_rows(rows, run):
    """Candidates as a run returns them: (start, end, polarity, onset, extremum, event_end, depth, confidence)."""
    df = pd.DataFrame(rows, columns=["start", "end", "polarity", "onset", "extremum", "event_end", "depth_mv",
                                     "confidence"])
    return df.assign(recovered=True, run=run, kind=C.KIND_PROPOSAL)


def test_combining_the_runs_keeps_a_rise_once_and_folds_the_rise_back_after_a_drop():
    normal = _cand_rows([(90, 210, "drop", 100, 120, 200, 5.0, 0.9),       # a drop recovering to 200
                         (590, 700, "spike", 600, 610, 690, 3.0, 0.6)], "normal")   # a sharp rise
    inverted = _cand_rows([(592, 702, "spike", 601, 611, 692, 3.1, 0.8),   # the same rise, scored higher
                           (110, 270, "spike", 121, 190, 260, 3.0, 0.7)], "inverted")  # the drop's rise back
    out, rep = P.combine_runs(normal, inverted)
    assert len(out) == 2
    rise = out[out["polarity"] == "spike"].iloc[0]
    assert rise["run"] == "inverted" and rise["runs"] == "both" and rise["confidence"] == pytest.approx(0.8)
    assert out[out["polarity"] == "drop"].iloc[0]["run"] == "normal"
    assert rep == {"normal": 2, "inverted": 2, "rises_found_by_both": 1, "same_event_removed": 1,
                   "folded_across_runs": 1}


def _either_way(x, t, fs, level=1.0):
    """A fake detector: every stretch more than `level` from zero, either way."""
    far = np.abs(np.asarray(x, dtype=float)) > level
    edges = np.flatnonzero(np.diff(np.r_[0, far.astype(int), 0]))
    return types.SimpleNamespace(output_kind="spanset", value=types.SimpleNamespace(
        starts=tuple(int(a) for a in edges[::2]), ends=tuple(int(b) for b in edges[1::2]), scores=None))


def test_drops_and_sharp_rises_come_from_both_runs_and_a_slow_rise_does_not(monkeypatch):
    _fake_registry(monkeypatch, {"detection.either": _spec(_either_way, "spanset")})
    n = 9000
    x = _sharkfin(n=n, at=1000, fall=2, noise=0.02)                        # a sharp drop
    x = x - _sharkfin(n=n, at=3000, fall=2, seed=1)                       # a sharp rise
    slow = np.zeros(n)
    slow[5500:6300] = np.linspace(0.0, 5.0, 800)                          # a slow rise, as high
    slow[6300:] = 5.0 * np.exp(-np.arange(n - 6300) / 500.0)
    x = x + slow
    det = [{"variant": "drop_detection_v1", "steps": [{"stage": "detection", "algorithm": "either", "params": {}}]}]
    res = P.auto_detect_both(x, 1.0, units="mV", detectors=det, seed_families=[],
                             score_spans=lambda s, e: np.full(len(s), 0.4), floor_mv=0.1)
    c = res.candidates
    rises = c[c["polarity"] == "spike"]
    assert len(rises) == 1
    drop, rise = c[c["polarity"] == "drop"].iloc[0], rises.iloc[0]
    assert abs(int(drop["extremum"]) - 1002) <= 3 and drop["run"] == "normal"
    assert abs(int(rise["extremum"]) - 3002) <= 3 and rise["runs"] == "both"
    assert res.info["combined"]["rises_found_by_both"] == 1
    hump = c[(c["end"] > 5500) & (c["start"] < 7000)]
    assert (hump["polarity"] == "drop").all()        # the slow rise is not a rise; its 34-minute decay is a drop by
    #                                                  the researcher's rule (steady, and far below its surroundings)
    assert list(c["candidate_id"]) == list(range(len(c))) and (c["sequence_id"] == -1).all()
    assert set(res.proposals["run"]) == {"normal", "inverted"}


def _fixed_spans(spans):
    """A fake detector that always reports the same boxes."""
    def run(x, t, fs):
        return types.SimpleNamespace(output_kind="spanset", value=types.SimpleNamespace(
            starts=tuple(a for a, _ in spans), ends=tuple(b for _, b in spans), scores=None))
    return run


def _ramp(x, a, b, v0, v1):
    x[a:b] = np.linspace(v0, v1, b - a, endpoint=False)


def test_a_slow_rise_the_gates_remove_cannot_swallow_the_next_drop(monkeypatch):
    # M4 CH1 63:36-64:06 h (2026-11-23): drop A, a slow climb back (one small step in it) that ends HIGHER than A was
    # deep - so it is not folded into A as its rise back - a small dip, then drop B, which starts inside that climb's
    # "recovery" and was folded into it. The climb is no rise by the researcher's rule (sharp rises only); the gate
    # removed it and drop B with it. A thing the run's own rules reject must not absorb a real event.
    rng = np.random.default_rng(21)
    n = 5000
    x = np.zeros(n)
    _ramp(x, 1000, 1003, 0.0, -3.2)                  # drop A: sharp ...
    _ramp(x, 1003, 1300, -3.2, -3.8)                 # ... then settling
    _ramp(x, 1300, 1650, -3.8, -3.2)                 # the slow climb back
    _ramp(x, 1650, 1680, -3.2, -2.1)                 # a step in it (not sharp: about 0.04 mV a second)
    _ramp(x, 1680, 2100, -2.1, 0.6)                  # climbing on, to 4.4 above A's bottom
    _ramp(x, 2100, 2130, 0.6, 0.3)                   # a small dip (ends the climb)
    _ramp(x, 2130, 2500, 0.3, 0.6)                   # a gentle stretch
    _ramp(x, 2500, 2503, 0.6, -2.8)                  # drop B: sharp ...
    _ramp(x, 2503, 2750, -2.8, -3.7)                 # ... 4.3 mV in all, inside the climb's fall back
    _ramp(x, 2750, 3400, -3.7, 0.0)
    x = x + 0.02 * rng.normal(size=n)
    _fake_registry(monkeypatch, {"detection.boxes": _spec(_fixed_spans([(995, 1350), (1640, 1700), (2495, 2800)]),
                                                          "spanset")})
    det = [{"variant": "drop_detection_v1", "steps": [{"stage": "detection", "algorithm": "boxes", "params": {}}]}]
    res = P.auto_detect(x, 1.0, units="mV", detectors=det, seed_families=[], floor_mv=0.1,
                        score_spans=lambda s, e: np.full(len(s), 0.4), min_sharpness={"spike": 10.0})
    bottoms = sorted(int(v) for v in res.candidates.loc[res.candidates["polarity"] == "drop", "extremum"])
    assert any(1000 <= b <= 1310 for b in bottoms), bottoms           # drop A
    assert any(2500 <= b <= 2760 for b in bottoms), bottoms           # drop B is still there
    assert not (res.candidates["polarity"] == "spike").any()          # and the slow climb is not a rise



# ── the 23 Nov evening round: the researcher's event rule, returns, margins, the finder ──────────────────

from Working.autodetect import finder as F  # noqa: E402


def test_a_return_a_little_deeper_than_its_drop_still_folds_and_carries_nothing_off():
    # M4 CH1 63:37-64:06 h: drop A, its climb back 0.11 mV deeper than A, then drop B starting in that climb's own
    # "recovery". The climb is A's return; B stays its own event.
    a = _anchored([
        (True, None, "drop", 100, 120, 300, True, 4.27, 90, 320),
        (True, None, "spike", 140, 400, 700, True, 4.38, 110, 760),
        (True, None, "drop", 650, 660, 750, True, 4.34, 640, 760),
    ])
    assert list(AN.fold(a, np.arange(3))) == [0, 0, 2]


def test_the_fall_back_after_a_spike_folds_into_it_but_a_much_deeper_fall_does_not():
    a = _anchored([
        (True, None, "spike", 100, 104, 140, True, 1.23, 99, 145),
        (True, None, "drop", 104, 140, 900, False, 1.29, 100, 950),      # its fall back, a hair deeper
        (True, None, "spike", 2000, 2004, 2040, True, 1.0, 1999, 2045),
        (True, None, "drop", 2004, 2100, 2500, False, 3.0, 2000, 2600),  # three times as deep: an event of its own
    ])
    assert list(AN.fold(a, np.arange(4))) == [0, 0, 2, 3]


def test_margins_stop_at_the_neighbouring_event_but_never_cut_an_event():
    bs, be = AN.clip_margins([0, 2000, 2100], [2400, 2300, 2200], [100, 2050, 2120], [2000, 2060, 2150])
    assert list(be) == [2050, 2120, 2200]          # each box ends where the next event starts ...
    assert list(bs) == [0, 2000, 2100]             # ... and the second never starts inside the first's event
    bs, be = AN.clip_margins([0, 50], [300, 400], [10, 60], [200, 300])
    assert list(be) == [300, 400] and list(bs) == [0, 50]       # overlapping events: nothing to clip


def test_the_drop_rule_keeps_sharp_or_steady_drops_and_drops_noise():
    rng = np.random.default_rng(31)
    fs = 2.0
    x = 0.01 * rng.normal(size=6000)
    _ramp(x, 1000, 1002, 0.0, -1.3)                                   # a 1.3 mV cliff in one sample: sharp
    x[1002:1400] += -1.3
    _ramp(x, 3000, 3009, 0.0, -0.21)                                  # a 0.21 mV drop over 9 samples: steady
    _ramp(x, 3009, 3100, -0.21, 0.0)
    x[4000:4003] += np.array([-0.03, -0.08, -0.03])                   # a 0.08 mV blip over 3 samples
    wander = np.convolve(0.06 * rng.normal(size=1000), np.ones(8) / 8, mode="same")
    x[5000:6000] += wander                                            # a wandering stretch ...
    lo = 5000 + int(np.argmin(wander[50:950])) + 50                   # ... and its deepest wiggle
    noise = G.step_noise(x, fs)
    on = [999, 2999, 3999, lo - 4]
    ex = [1001, 3008, 4001, lo]
    en = [1001, 3050, 4003, lo + 4]
    sharp = [G.sharpness(x, o, e, fs, noise) for o, e in zip(on, ex)]
    ok = G.distinct(x, fs, on, ex, en, sharp)
    assert list(ok) == [True, True, False, False]
    assert G.steady_run(x, 2999, 3009) >= G.MIN_STEADY_SAMPLES


def test_the_finder_proposes_a_sawtooth_train_and_almost_nothing_in_noise():
    rng = np.random.default_rng(32)
    fs = 2.0
    quiet = 0.01 * rng.normal(size=8000)
    assert len(F.find(quiet, fs, floor_mv=0.03)) <= 2
    x = quiet.copy()
    tops = list(range(1000, 7000, 120))                               # a drop every minute: 0.21 mV over 9 samples
    for a in tops:
        _ramp(x, a, a + 9, 0.0, -0.21)
        _ramp(x, a + 9, a + 100, -0.21, 0.0)
    got = F.find(x, fs, floor_mv=0.03)
    hit = [any(s <= a + 4 < e for s, e in zip(got["start"], got["end"])) for a in tops]
    assert np.mean(hit) >= 0.9 and set(got["source"]) == {F.SOURCE}


def test_the_next_spike_is_not_the_previous_drops_return():
    # CH14 396:42 h, a train of two-phase spikes: a drop that recovers slowly has its half recovery at the moment the
    # next spike jumps up, so that spike sits inside the drop's recovery - but it starts long after the drop's bottom.
    # A return starts where the event bottoms out (within one fall of it).
    a = _anchored([
        (True, None, "drop", 173, 184, 294, True, 0.372, 161, 306),      # a drop, bottom at 184, slow climb back
        (True, None, "spike", 292, 295, 296, True, 0.261, 291, 297),     # the next spike, 108 samples later
        (True, None, "drop", 295, 302, 370, True, 0.413, 294, 371),      # its fall, overshooting
    ])
    assert list(AN.fold(a, np.arange(3))) == [0, 1, 2]

"""
test_trains.py
================
w1-e: the core of `interrogation.trains` - `Working.interrogation.trains`.
Trains (bursts, Adamatzky's "words") of events by three rules: logISI
(Pasquale et al. 2010 as restated by Cotterill et al. 2016; the default),
MaxInterval (Cotterill et al.'s first choice) and Adamatzky 2022's words.

Pinned here:
* Poisson event times -> logISI reports NO trains (one hump), never a
  spurious split; checked over many seeds, not one lucky draw;
* clear trains (~30 s inside, ~3000 s between) -> every train, right members;
* Adamatzky's words and MaxInterval reproduce hand-computed examples exactly;
* fewer than 10 gaps -> logISI refuses in words;
* the core-and-extend step (an explicit within-train ceiling);
* the ~200 s artefact warning (Buffi et al. 2025);
* the summary numbers (sizes, positions, distribution, LZ).

Runnable standalone:  python tests/test_trains.py
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.interrogation import trains as TR  # noqa: E402


def poisson_times(seed, n=300, mean_gap=100.0):
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.exponential(mean_gap, n))


def clear_trains(seed=0, n_trains=20):
    """Trains of 3-9 events with gaps 20-40 s inside, 2000-4000 s between."""
    rng = np.random.default_rng(seed)
    times, truth, t0 = [], [], 0.0
    for k in range(n_trains):
        m = int(rng.integers(3, 10))
        tt = t0 + np.concatenate([[0.0], np.cumsum(rng.uniform(20, 40, m - 1))])
        times += list(tt)
        truth += [k] * m
        t0 = tt[-1] + rng.uniform(2000, 4000)
    return np.array(times), np.array(truth)


# ── logISI ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", range(25))
def test_logisi_finds_no_trains_in_poisson_times(seed):
    r = TR.find_trains(poisson_times(seed), rule="logisi")
    assert r["n_trains"] == 0, f"a spurious split at {r['cut_s']} s (void {r['void']})"
    assert (r["train_id"] == -1).all()
    assert r["cut_s"] is None
    assert r["no_trains_reason"], "an absence must be said in words"
    assert r["refused"] is None, "a few hundred gaps is enough - this is a finding, not a refusal"


@pytest.mark.parametrize("seed", range(10))
def test_logisi_finds_every_clear_train_with_the_right_members(seed):
    times, truth = clear_trains(seed)
    r = TR.find_trains(times, rule="logisi")
    assert r["n_trains"] == truth.max() + 1
    assert list(r["train_id"]) == list(truth)
    assert 40.0 < r["cut_s"] < 2000.0
    assert r["void"] > TR.VOID_THRESHOLD
    assert r["fraction_in_trains"] == 1.0


def test_logisi_labels_follow_the_input_order_not_the_sorted_one():
    times, truth = clear_trains(3)
    perm = np.random.default_rng(1).permutation(len(times))
    r = TR.find_trains(times[perm], rule="logisi")
    assert list(r["train_id"]) == list(truth[perm])


def test_logisi_density_is_drawable_and_states_its_bandwidth():
    times, _ = clear_trains(0)
    r = TR.find_trains(times)
    d = r["density"]
    assert 2 <= len(d["log10_gap_s"]) == len(d["density"]) <= 512
    assert d["bandwidth_log10"] > 0
    json.dumps(d)


def test_logisi_refuses_fewer_than_ten_gaps_in_words():
    times = np.array([0, 30, 60, 3000, 3030, 3060, 6000, 6030, 6060, 6090], dtype=float)  # 9 gaps
    r = TR.find_trains(times, rule="logisi")
    assert r["n_gaps"] == 9
    assert (r["train_id"] == -1).all()
    assert r["refused"] and "9 gaps" in r["refused"] and "10" in r["refused"]
    assert r["n_trains"] == 0


def test_the_default_rule_is_logisi():
    times, truth = clear_trains(2)
    assert list(TR.find_trains(times)["train_id"]) == list(truth)
    assert TR.find_trains(times)["rule"] == "logisi"


def test_an_unknown_rule_is_refused_loudly():
    with pytest.raises(ValueError, match="rule"):
        TR.find_trains([0.0, 1.0, 2.0], rule="poisson_surprise")


def test_core_and_extend_with_an_explicit_ceiling():
    # 12 events; cores = >= 3 events joined by gaps < 10 s; extension over gaps < 100 s
    gaps = np.array([5, 5, 50, 50, 500, 50, 50, 50, 500, 5, 5], dtype=float)
    labels = TR.core_and_extend(gaps, ceiling=10.0, cut=100.0, min_events=3)
    # events 0-2 are a core and grow over the two 50 s gaps; events 5-8 are under the cut
    # but hold no core, so they are no train; events 9-11 are a core with nothing to grow into
    assert list(labels) == [0, 0, 0, 0, 0, -1, -1, -1, -1, 1, 1, 1]


# ── Adamatzky's words ───────────────────────────────────────────────────────

ADAMATZKY_TIMES = np.array([0, 10, 20, 100, 105, 300, 310, 320, 330], dtype=float)
# gaps 10 10 80 5 195 10 10 10 -> mean 41.25 s


def test_adamatzky_words_by_hand_theta_one_mean_gap():
    r = TR.find_trains(ADAMATZKY_TIMES, rule="adamatzky", theta_mult=1.0, min_events=3)
    assert r["theta_s"] == pytest.approx(41.25)
    assert list(r["word_id"]) == [0, 0, 0, 1, 1, 2, 2, 2, 2]
    assert list(r["train_id"]) == [0, 0, 0, -1, -1, 1, 1, 1, 1]
    assert r["word_length_distribution"] == {"2": 1, "3": 1, "4": 1}
    assert list(r["train_size"]) == [3, 3, 3, 0, 0, 4, 4, 4, 4]
    assert list(r["position_in_train"]) == [0, 1, 2, -1, -1, 0, 1, 2, 3]


def test_adamatzky_words_by_hand_theta_twice_the_mean_gap():
    r = TR.find_trains(ADAMATZKY_TIMES, rule="adamatzky", theta_mult=2.0, min_events=3)
    assert r["theta_s"] == pytest.approx(82.5)
    assert list(r["word_id"]) == [0, 0, 0, 0, 0, 1, 1, 1, 1]   # 80 <= 82.5 joins; 195 does not
    assert list(r["train_id"]) == [0, 0, 0, 0, 0, 1, 1, 1, 1]


def test_adamatzky_gap_equal_to_theta_joins_the_word():
    # "not more than theta": gaps 10, 30, 20 -> mean 20; the 20 s gap joins, the 30 s gap does not
    r = TR.find_trains(np.array([0, 10, 40, 60], dtype=float), rule="adamatzky", min_events=2)
    assert list(r["word_id"]) == [0, 0, 1, 1]


def test_adamatzky_allows_words_of_one_event():
    r = TR.find_trains(np.array([0, 3000, 3010, 3020, 9000], dtype=float), rule="adamatzky")
    assert list(r["word_id"]) == [0, 1, 1, 1, 2]
    assert r["word_length_distribution"] == {"1": 2, "3": 1}
    assert list(r["train_id"]) == [-1, 0, 0, 0, -1]


def test_adamatzky_runs_below_ten_gaps():
    """Only the histogram rule refuses on few gaps."""
    r = TR.find_trains(ADAMATZKY_TIMES, rule="adamatzky")
    assert r["refused"] is None and r["n_trains"] == 2


# ── MaxInterval ─────────────────────────────────────────────────────────────

MI_TIMES = np.array([0, 8, 25, 40, 100, 130, 135, 138, 300, 305, 400], dtype=float)
# gaps 8 17 15 60 30 5 3 162 5 95


def _mi(**over):
    p = dict(rule="maxinterval", mi_begin_gap_s=10.0, mi_end_gap_s=20.0, mi_min_ibi_s=50.0,
             mi_min_duration_s=5.0, min_events=3)
    p.update(over)
    return TR.find_trains(MI_TIMES, **p)


def test_maxinterval_by_hand():
    # bursts: events 0-3 (begin at 8 <= 10, continue over 17, 15 <= 20, stop at 60),
    # 5-7 (begin at 5, continue over 3, stop at 162), 8-9 (begin at 5, stop at 95);
    # IBIs 90 s and 162 s are >= 50: no merge; 8-9 has 2 events: removed
    assert list(_mi()["train_id"]) == [0, 0, 0, 0, -1, 1, 1, 1, -1, -1, -1]


def test_maxinterval_merges_bursts_closer_than_the_minimum_ibi():
    # IBI between burst 0-3 (ends t=40) and 5-7 (starts t=130) is 90 s < 100: one burst 0-7
    assert list(_mi(mi_min_ibi_s=100.0)["train_id"]) == [0, 0, 0, 0, 0, 0, 0, 0, -1, -1, -1]


def test_maxinterval_removes_bursts_shorter_than_the_minimum_duration():
    # burst 5-7 lasts 138 - 130 = 8 s < 10
    assert list(_mi(mi_min_duration_s=10.0)["train_id"]) == [0, 0, 0, 0, -1, -1, -1, -1, -1, -1, -1]


def test_maxinterval_states_its_thresholds_as_placeholders():
    r = TR.find_trains(MI_TIMES, rule="maxinterval")
    assert set(r["thresholds_s"]) >= {"begin_gap", "end_gap", "min_ibi", "min_duration", "min_events"}
    text = " ".join(x["rule"] for x in TR.rules("maxinterval", **TR.MI_DEFAULTS, min_events=3))
    assert "placeholder" in text.lower()


# ── summaries and honesty ───────────────────────────────────────────────────

def test_summary_numbers():
    times, truth = clear_trains(4, n_trains=12)
    r = TR.find_trains(times)
    sizes = np.bincount(truth)
    assert r["train_sizes"] == list(sizes)
    assert r["train_size_distribution"] == {str(s): int(c) for s, c in zip(*np.unique(sizes, return_counts=True))}
    assert list(r["train_size"]) == list(sizes[truth])
    assert r["lz_complexity"] is not None and r["lz_complexity"] > 0
    json.dumps({k: v for k, v in r.items() if not isinstance(v, np.ndarray)})


def test_lempel_ziv_reuses_the_kaspar_schuster_routine():
    from Working.Detection.analysis.dehshibi_detection_analysis import _lz76_complexity
    sizes = [3, 4, 3, 4, 3, 4, 5]
    assert TR.lempel_ziv(sizes) == pytest.approx(_lz76_complexity("".join(chr(0x100 + s) for s in sizes)))
    assert TR.lempel_ziv([3]) is None


def test_a_within_train_gap_near_200_s_carries_the_control_channel_warning():
    times = np.concatenate([np.arange(5) * 200.0 + k * 20000.0 for k in range(3)])
    r = TR.find_trains(times, rule="adamatzky")
    assert r["n_trains"] == 3
    assert r["warnings"] and "200 s" in r["warnings"][0] and "Buffi" in r["warnings"][0]
    r2 = TR.find_trains(times / 10.0, rule="adamatzky")
    assert r2["warnings"] == []


def test_every_rule_prints_its_rules():
    for rule in TR.RULE_NAMES:
        rows = TR.rules(rule, **TR.MI_DEFAULTS, min_events=3, theta_mult=1.0, max_core_gap_s=0.0)
        assert rows and all(set(r) == {"name", "rule"} for r in rows)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

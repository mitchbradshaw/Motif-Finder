"""
test_intervals_nulls.py
=========================
Round-B B1 — LV and CV2 reported against two nulls, per group
(`Working.interrogation.intervals.interval_nulls`, and through the
`interrogation.intervals` block's meta).

In plain words: an LV of 0.6 means nothing on its own; it means something
beside "what would random timing with this many events have given". Two
references:

* **rate-matched Poisson** — the same number of onsets dropped uniformly over
  the group's own observed span (a homogeneous Poisson process conditioned on
  n). Asks: is the timing more regular, or burstier, than random?
* **shuffled intervals** — the group's own gaps in random order. Asks: is the
  ORDER of the gaps more regular than the gap distribution alone implies?

Each reports the null mean, the 2.5-97.5 % band and a two-sided p for LV and
for CV2, seeded, with the draw count.

Runnable standalone:  python tests/test_intervals_nulls.py
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.interrogation import intervals as IV  # noqa: E402
from Working.types import SpanSet  # noqa: E402

discover_adapters()
NAME = "interrogation.intervals"
FS = 10.0
KEYS = ("observed", "null_mean", "lo", "hi", "p")


def _run(ss, n=4000, **params):
    spec = get_adapter(NAME)
    return spec.run(np.zeros(n), np.arange(n) / FS, FS, value=ss, **spec.validate_params(params))


# ── the shape of the answer ─────────────────────────────────────────────────

def test_both_nulls_report_mean_band_and_p_for_lv_and_cv2():
    rng = np.random.default_rng(1)
    onsets = np.cumsum(rng.exponential(10.0, size=60))
    nl = IV.interval_nulls(onsets, n_draws=200, seed=3)
    for which in ("poisson", "shuffle"):
        block = nl[which]
        assert block["n_draws"] == 200
        for m in ("lv", "cv2"):
            assert set(KEYS) <= set(block[m])
            r = block[m]
            assert r["lo"] <= r["null_mean"] <= r["hi"]
            assert 0.0 < r["p"] <= 1.0
    assert nl["seed"] == 3
    assert nl["poisson"]["lv"]["observed"] == pytest.approx(IV.local_variation(IV.inter_event_intervals(onsets)))


def test_the_default_is_about_a_thousand_draws():
    assert 500 <= IV.NULL_DRAWS <= 2000
    nl = IV.interval_nulls(np.arange(0, 300, 7.0))
    assert nl["poisson"]["n_draws"] == IV.NULL_DRAWS


def test_seeded_so_the_same_seed_gives_the_same_answer():
    onsets = np.cumsum(np.random.default_rng(5).exponential(3.0, size=40))
    a = IV.interval_nulls(onsets, n_draws=150, seed=11)
    b = IV.interval_nulls(onsets, n_draws=150, seed=11)
    c = IV.interval_nulls(onsets, n_draws=150, seed=12)
    assert a == b
    assert a["poisson"]["lv"]["null_mean"] != c["poisson"]["lv"]["null_mean"]


# ── what each null says ─────────────────────────────────────────────────────

def test_the_poisson_null_centres_on_one_for_both_measures():
    onsets = np.arange(0, 2000, 10.0)
    nl = IV.interval_nulls(onsets, n_draws=400, seed=1)
    assert nl["poisson"]["lv"]["null_mean"] == pytest.approx(1.0, abs=0.08)
    assert nl["poisson"]["cv2"]["null_mean"] == pytest.approx(1.0, abs=0.08)


def test_a_clockwork_train_is_more_regular_than_poisson():
    nl = IV.interval_nulls(np.arange(0, 600, 10.0), n_draws=400, seed=2)
    p = nl["poisson"]
    assert p["lv"]["observed"] == 0.0 and p["lv"]["observed"] < p["lv"]["lo"]
    assert p["lv"]["p"] < 0.01 and p["cv2"]["p"] < 0.01


def test_a_poisson_train_is_not_told_apart_from_poisson():
    # calibrated, not merely "usually passes": over 40 genuinely Poisson trains
    # the p < 0.05 rate is about 1 in 20
    rejected = 0
    for s in range(40):
        onsets = np.cumsum(np.random.default_rng(100 + s).exponential(10.0, size=120))
        nl = IV.interval_nulls(onsets, n_draws=300, seed=s)
        rejected += nl["poisson"]["lv"]["p"] < 0.05
    assert rejected <= 6


def test_alternating_gaps_beat_their_shuffle_and_a_shuffled_train_does_not():
    # 5, 20, 5, 20, ...: every neighbour pair differs maximally - LV far above
    # what the same gaps in random order give. The same gaps already shuffled
    # sit inside their own shuffle band.
    iv = np.tile([5.0, 20.0], 40)
    onsets = np.concatenate([[0.0], np.cumsum(iv)])
    nl = IV.interval_nulls(onsets, n_draws=400, seed=5)
    assert nl["shuffle"]["lv"]["observed"] > nl["shuffle"]["lv"]["hi"]
    assert nl["shuffle"]["lv"]["p"] < 0.01

    mixed = np.random.default_rng(9).permutation(iv)
    nl2 = IV.interval_nulls(np.concatenate([[0.0], np.cumsum(mixed)]), n_draws=400, seed=5)
    assert nl2["shuffle"]["lv"]["p"] > 0.05


def test_two_sided_p_flags_a_burstier_than_poisson_train_too():
    # tight bursts of three 1-s gaps separated by 60-s silences: LV well above 1
    rng = np.random.default_rng(3)
    bursts = np.arange(0, 3000, 60.0)
    onsets = np.sort(np.concatenate([bursts + k * 1.0 + rng.uniform(0, 0.2) for k in range(3)]))
    nl = IV.interval_nulls(onsets, n_draws=400, seed=6)
    assert nl["poisson"]["lv"]["observed"] > nl["poisson"]["lv"]["hi"]
    assert nl["poisson"]["lv"]["p"] < 0.01


# ── the module's existing rules carry over ──────────────────────────────────

def test_too_few_events_is_not_measured_with_the_reason_never_zero():
    nl = IV.interval_nulls([0.0, 5.0], n_draws=50, seed=1)
    for which in ("poisson", "shuffle"):
        assert nl[which]["lv"] is None and nl[which]["cv2"] is None
        assert nl[which]["note"]


def test_coincident_onsets_are_handled_as_the_observed_value_is():
    # three events at one instant inside an otherwise regular train: the
    # observed LV/CV2 leave the 0/0 pair out (n_local_pairs), and so must the null
    onsets = np.array([0, 10, 20, 20, 20, 30, 40, 50, 60, 70, 80], dtype=float)
    nl = IV.interval_nulls(onsets, n_draws=200, seed=7)
    st = IV.interval_statistics(IV.inter_event_intervals(onsets))
    assert nl["shuffle"]["lv"]["observed"] == pytest.approx(st["lv"])
    assert nl["n_local_pairs"] == st["n_local_pairs"]
    assert nl["local_note"] == st["local_note"] and nl["local_note"]
    assert np.isfinite(nl["shuffle"]["lv"]["null_mean"])


def test_few_gaps_and_the_sampling_grid_are_said():
    nl = IV.interval_nulls(np.arange(0, 60, 10.0), n_draws=100, seed=1, resolution_s=1.0)
    assert "indicative" in (nl["caveat"] or "")
    assert nl["resolution_s"] == 1.0


def test_the_poisson_null_is_drawn_on_the_onsets_grid_when_one_is_given():
    # on a 1-s grid a drawn onset lands on whole seconds, as the observed ones do
    nl = IV.interval_nulls(np.arange(0, 100, 5.0), n_draws=50, seed=1, resolution_s=1.0, keep_draws=True)
    d = np.asarray(nl["poisson"]["draws_onsets"][0])
    assert np.allclose(d, np.round(d))


def test_the_docstring_says_what_each_null_tests_in_plain_words():
    doc = IV.interval_nulls.__doc__.lower()
    assert "more regular" in doc and "burstier" in doc and "random" in doc
    assert "order" in doc and "gap distribution" in doc


# ── through the block ───────────────────────────────────────────────────────

def test_the_block_reports_the_nulls_per_group_never_pooled():
    a = np.arange(0, 3000, 100)                     # clockwork
    b = np.cumsum(np.random.default_rng(2).exponential(40, size=60)).astype(int) + 3
    starts = np.concatenate([a, b])
    feats = pd.DataFrame({"group": ["a"] * len(a) + ["b"] * len(b)})
    r = _run(SpanSet(starts=tuple(int(s) for s in starts), ends=tuple(int(s) + 2 for s in starts), features=feats),
             n=int(starts.max()) + 10, null_draws=200)
    st = r.meta["interval_stats"]
    assert set(st) == {"a", "b"}
    assert st["a"]["nulls"]["poisson"]["lv"]["p"] < 0.01
    assert st["b"]["nulls"]["poisson"]["lv"]["p"] > 0.01
    assert st["a"]["nulls"]["poisson"]["n_draws"] == 200
    # the block's grid is its sampling rate
    assert st["a"]["nulls"]["resolution_s"] == pytest.approx(1 / FS)


def test_the_block_defaults_to_the_core_draw_count_and_zero_turns_it_off():
    spec = get_adapter(NAME)
    p = spec.validate_params({})
    assert p["null_draws"] == IV.NULL_DRAWS
    r = _run(SpanSet(starts=(0, 100, 250, 300, 420), ends=(50, 150, 280, 350, 450)), null_draws=0)
    assert r.meta["interval_stats"]["all"]["nulls"] is None


def test_the_rules_name_both_nulls():
    names = {rule["name"] for rule in IV.RULES}
    assert {"null_poisson", "null_shuffle"} <= names


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

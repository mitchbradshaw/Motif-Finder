"""
test_intervals_lv.py
=====================
W1-G — LV (Shinomoto, Shima & Tanji 2003; formula as in Shinomoto et al. 2009
eq. 2) and the local CV2 (Holt, Softky, Koch & Douglas 1996) in each group's
interval statistics, so `interrogation.intervals` and every other caller of
`Working.interrogation.intervals.interval_statistics` get them.

Both compare each gap only with the next one, so a slow change of rate does not
read as irregularity the way CV does. Both are ~0 for clockwork and ~1 for a
Poisson train; both need at least two gaps (three events), and fewer is null
with the reason said, never 0.

Runnable standalone:  python tests/test_intervals_lv.py
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


def _run(ss, n=400, **params):
    spec = get_adapter(NAME)
    return spec.run(np.zeros(n), np.arange(n) / FS, FS, value=ss, **spec.validate_params(params))


# ── the formulas, by hand ───────────────────────────────────────────────────

def test_lv_and_cv2_match_the_published_formulas_on_a_small_case():
    iv = np.array([1.0, 3.0, 2.0, 2.0])
    pairs = list(zip(iv[:-1], iv[1:]))
    lv = 3.0 / (len(iv) - 1) * sum(((a - b) / (a + b)) ** 2 for a, b in pairs)
    cv2 = float(np.mean([2 * abs(b - a) / (b + a) for a, b in pairs]))
    assert IV.local_variation(iv) == pytest.approx(lv)
    assert IV.local_cv2(iv) == pytest.approx(cv2)
    st = IV.interval_statistics(iv)
    assert st["lv"] == pytest.approx(lv) and st["cv2"] == pytest.approx(cv2)
    assert st["local_note"] is None


def test_a_perfectly_regular_train_has_lv_and_cv2_of_zero():
    st = IV.interval_statistics(np.full(20, 3.0))
    assert st["lv"] == 0.0 and st["cv2"] == 0.0


def test_poisson_gaps_give_lv_and_cv2_near_one():
    rng = np.random.default_rng(20031)
    iv = rng.exponential(5.0, size=5000)
    st = IV.interval_statistics(iv)
    assert st["lv"] == pytest.approx(1.0, abs=0.1)
    assert st["cv2"] == pytest.approx(1.0, abs=0.1)


def test_a_tenfold_rate_rise_fools_cv_but_not_lv_or_cv2():
    # Inhomogeneous Poisson by time rescaling: rate(t) = r0 * (1 + 9 t / T) rises
    # tenfold over the span. Unit-rate arrivals in the rescaled time Λ(t) are
    # mapped back through Λ⁻¹.
    rng = np.random.default_rng(1996)
    r0, T = 1.0, 2000.0
    lam_total = r0 * (T + 4.5 * T)                      # Λ(T) = r0 (T + 9T/2)
    big = np.cumsum(rng.exponential(1.0, size=int(lam_total * 1.2)))
    big = big[big < lam_total]
    # Λ(t) = r0 (t + 4.5 t²/T)  ->  t = (-1 + sqrt(1 + 18 Λ/(r0 T))) T / 9
    onsets = (-1.0 + np.sqrt(1.0 + 18.0 * big / (r0 * T))) * T / 9.0
    st = IV.interval_statistics(IV.inter_event_intervals(onsets))
    assert st["n_intervals"] > 5000
    assert st["cv"] > 1.15                                # CV calls it irregular
    assert st["lv"] == pytest.approx(1.0, abs=0.1)        # the local measures do not
    assert st["cv2"] == pytest.approx(1.0, abs=0.1)


def test_fewer_than_two_gaps_is_null_with_the_reason_never_zero():
    one_gap = IV.interval_statistics([4.0])
    assert one_gap["lv"] is None and one_gap["cv2"] is None
    assert "2 events" in one_gap["local_note"] and "3" in one_gap["local_note"]
    none = IV.interval_statistics([], n_events=1)
    assert none["lv"] is None and none["cv2"] is None and none["local_note"]
    assert IV.local_variation([4.0]) is None and IV.local_cv2([]) is None


def test_the_existing_statistics_are_unchanged():
    iv = np.array([10.0, 15.0, 5.0])
    st = IV.interval_statistics(iv)
    cv, r2 = IV.regularity(iv)
    assert st["cv"] == pytest.approx(cv) and st["r2_trend"] == pytest.approx(r2)
    assert st["drift_ratio"] == pytest.approx(0.5)
    assert st["n_events"] == 4 and st["n_intervals"] == 3 and st["median_s"] == pytest.approx(10.0)


# ── through the block ───────────────────────────────────────────────────────

def test_the_block_reports_lv_and_cv2_per_group_never_pooled():
    # a: perfectly regular, 4 events (3 gaps) -> 0; b: only 2 events -> null, counted.
    feats = pd.DataFrame({"group": ["a", "b", "a", "a", "b", "a"]})
    starts = (0, 5, 100, 200, 400, 300)
    r = _run(SpanSet(starts=starts, ends=tuple(s + 3 for s in starts), features=feats))
    st = r.meta["interval_stats"]
    assert st["a"]["lv"] == 0.0 and st["a"]["cv2"] == 0.0
    assert st["b"]["lv"] is None and st["b"]["cv2"] is None
    assert st["b"]["n_events"] == 2 and st["b"]["local_note"]
    assert r.meta["n_groups_local_unmeasured"] == 1


def test_pooling_would_have_given_a_different_answer():
    # Two individually regular groups at different rates, interleaved: pooled they
    # would not be regular; per group they are exactly 0.
    a = np.arange(0, 1000, 100)
    b = np.arange(7, 1000, 30)
    starts = np.concatenate([a, b])
    feats = pd.DataFrame({"group": ["a"] * len(a) + ["b"] * len(b)})
    r = _run(SpanSet(starts=tuple(int(s) for s in starts), ends=tuple(int(s) + 2 for s in starts),
                     features=feats), n=1100)
    st = r.meta["interval_stats"]
    # (sample index / fs leaves ~1e-32 of float residue, hence approx)
    assert st["a"]["lv"] == pytest.approx(0.0, abs=1e-12) and st["b"]["lv"] == pytest.approx(0.0, abs=1e-12)
    assert IV.local_variation(IV.inter_event_intervals(starts)) > 0.1


def test_the_rules_name_lv_and_cv2_and_not_lvr():
    r = _run(SpanSet(starts=(0, 100, 250), ends=(50, 150, 280)))
    names = {rule["name"] for rule in r.meta["rules"]}
    assert {"lv", "cv2"} <= names
    assert "lvr" not in names
    text = " ".join(rule["rule"] for rule in r.meta["rules"] if rule["name"] in ("lv", "cv2"))
    assert "Shinomoto" in text and "Holt" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

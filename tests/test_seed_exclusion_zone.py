"""
test_seed_exclusion_zone.py
===========================
fixup-AD §6 (QUESTIONS.md Round 11, exclusion zone (b)): `detection.seed_matches`
takes an exclusion parameter, a fraction of m, default **m/2** (§7.6), passed to
`stumpy.match`. Until now the block exposed none and the search ran under
stumpy's own m/4 while the Seed page's card said so beside §7.6's m/2.

The test signal is a sine whose period is m/4, so a match recurs every m/4
samples: under an m/4 zone (ceil, inclusive) every second one survives; under
m/2 every third.
"""

import math
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest
import stumpy

from Adapters import detection_seed_matches as sm
from Working.discovery import seeded_search as ss

M = 40
PERIOD = M // 4


def _periodic(n=1200, seed=0):
    t = np.arange(n)
    return np.sin(2 * np.pi * t / PERIOD) + np.random.default_rng(seed).standard_normal(n) * 0.01


def _min_gap(rows):
    idx = sorted(int(r[1]) for r in rows)
    return min(b - a for a, b in zip(idx, idx[1:]))


def test_the_default_zone_is_half_the_exemplar():
    x = _periodic()
    q = x[200:200 + M].copy()
    rows = sm.match_exemplar(x, q, k=20)
    assert _min_gap(rows) > math.ceil(M / 2)
    assert sm.DEFAULT_EXCLUSION == 0.5


def test_the_zone_is_a_parameter_that_reaches_stumpy():
    x = _periodic()
    q = x[200:200 + M].copy()
    wide = sm.match_exemplar(x, q, k=20, exclusion=0.5)
    narrow = sm.match_exemplar(x, q, k=20, exclusion=0.25)
    assert _min_gap(narrow) <= math.ceil(M / 2) < _min_gap(wide)
    assert len(narrow) > len(wide)
    assert stumpy.config.STUMPY_EXCL_ZONE_DENOM == 4           # stumpy's global is put back


@pytest.mark.parametrize("bad", [0, -0.5, 3])
def test_a_zone_that_is_not_one_is_refused(bad):
    x = _periodic()
    with pytest.raises(ValueError):
        sm.match_exemplar(x, x[200:240].copy(), k=5, exclusion=bad)


def test_the_block_carries_the_zone_in_its_params_and_its_meta():
    spec = next(p for p in sm.SPEC.params if p.name == "exclusion")
    assert spec.default == 0.5
    from Working.types import Signal
    x = _periodic()
    sig = Signal(x=x[200:240].copy(), fs=1.0)
    out = sm._run(x, np.arange(len(x), dtype=float), 1.0, k=5, exemplar=sig, exclusion=0.25)
    assert out.meta["exclusion"] == 0.25 and out.meta["exclusion_samples"] == math.ceil(M * 0.25)
    bank = sm._run(x, np.arange(len(x), dtype=float), 1.0, k=5, exemplar=sig, scales="0.8,1", exclusion=0.5)
    assert bank.meta["exclusion"] == 0.5


def test_a_seed_recipe_records_the_zone():
    seed = {"binding": {"source_kind": "library_exemplar", "entry_id": 0, "source_file": "a.mat",
                        "channel": 0, "start_idx": 0, "end_idx": M}}
    assert ss.seed_steps(seed, k=10)[0]["params"]["exclusion"] == 0.5
    assert ss.seed_steps(seed, k=10, exclusion=0.25)[0]["params"]["exclusion"] == 0.25


def test_the_card_reports_m_over_2_and_lets_it_be_set():
    seed = {"samples": 60, "fs": 1.0}
    p = ss.recommended_params(seed)
    assert p["exclusionSamples"] == 30 and p["exclusionS"] == pytest.approx(30.0)
    assert p["exclusion"] == 0.5
    assert p["exclusionSettable"] is True
    assert "m/4" not in p["exclusion_note"] and "differ" not in p["exclusion_note"]

"""
test_library_coherence.py
===========================
`Working.library.coherence.svd_entropy` — the SVD entropy of a family's
member matrix as a shape-coherence score (Colominas & Wu 2023, eq. 17:
p_i = sigma_i / sum sigma, H = -sum p_i ln p_i, normalised by ln min(P, L)).

What these tests pin:
  * scaled copies of one shape score ~0; a 50/50 mixture of two shapes scores
    clearly higher — on a white AND a coloured (AR(1), random-walk) background;
  * alignment lowers the score of shifted copies (and is on by default);
  * amplitude does not enter; the singular values are not squared (eq. 17) and
    `squared=True` is the labelled variant;
  * NaN rows are dropped and counted, a family under two rows says why, and a
    family over `max_members` is sampled (seeded) and says so.

The score's weakness at higher noise (the noise floor's singular values count
in proportion to themselves) is measured in the module docstring, not hidden
in a loose threshold here: these tests run at <= 1 % background noise.

Runnable standalone:  python tests/test_library_coherence.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
for p in (PROJECT_ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import pytest

from Working.library.coherence import svd_entropy
from _shape_families import background

T = np.linspace(0.0, 1.0, 150)


def _bump(centre=0.5):
    return np.exp(-((T - centre) / 0.08) ** 2)


def _wavelet(centre=0.5):
    return np.sin(2 * np.pi * 3 * T) * np.exp(-((T - centre) / 0.15) ** 2)


def _members(shape_fn, n, rng, *, noise=0.0, kind="white", max_shift=0.0):
    return [rng.uniform(0.5, 3.0) * (shape_fn(0.5 + rng.uniform(-max_shift, max_shift))
                                     + noise * background(T.size, kind, rng))
            for _ in range(n)]


@pytest.mark.parametrize("kind", ["white", "ar1_095", "random_walk"])
def test_copies_score_near_zero_and_a_mixture_clearly_higher(kind):
    rng = np.random.default_rng(1)
    copies = _members(_bump, 40, rng, noise=0.01, kind=kind)
    mix = copies[:20] + _members(_wavelet, 20, rng, noise=0.01, kind=kind)
    c = svd_entropy(copies)
    m = svd_entropy(mix)
    assert c["svd_entropy_norm"] < 0.3, c          # 1 % noise is not 0: the noise floor counts (eq. 17)
    assert m["svd_entropy_norm"] > c["svd_entropy_norm"] + 0.05, (c, m)
    exact = svd_entropy(_members(_bump, 40, rng))
    assert exact["svd_entropy"] == pytest.approx(0.0, abs=1e-6)
    assert svd_entropy(copies[:20] + _members(_wavelet, 20, rng))["svd_entropy_norm"] > 0.1


def test_alignment_lowers_it_for_shifted_copies():
    rng = np.random.default_rng(2)
    shifted = _members(_bump, 40, rng, noise=0.01, kind="ar1_095", max_shift=0.2)
    raw = svd_entropy(shifted, align=False)
    aligned = svd_entropy(shifted)
    assert aligned["aligned"] and not raw["aligned"]
    assert aligned["svd_entropy_norm"] < raw["svd_entropy_norm"] - 0.2, (raw, aligned)
    assert 0.5 <= aligned["overlap"] < 1.0, "aligned rows are cut to the span they all cover"
    assert "cut to" in aligned["rule"]


def test_amplitude_does_not_enter():
    rng = np.random.default_rng(3)
    rows = _members(_bump, 10, rng, noise=0.01) + _members(_wavelet, 10, rng, noise=0.01)
    a = svd_entropy(rows)
    b = svd_entropy([r * 50.0 + 7.0 for r in rows])
    assert a["svd_entropy"] == pytest.approx(b["svd_entropy"], abs=1e-9)


def test_it_is_eq_17_unsquared_with_the_stated_normalisation():
    from Working.library.grouping.methods.ward import shape_vectors
    rng = np.random.default_rng(4)
    rows = _members(_bump, 12, rng, noise=0.05) + _members(_wavelet, 8, rng, noise=0.05)
    out = svd_entropy(rows, align=False)
    sigma = np.linalg.svd(shape_vectors(rows), compute_uv=False)
    p = sigma / sigma.sum()
    H = -(p * np.log(p)).sum()
    assert out["svd_entropy"] == pytest.approx(H, rel=1e-9)
    assert out["svd_entropy_norm"] == pytest.approx(H / np.log(min(20, 256)), rel=1e-9)
    assert out["top_share"] == pytest.approx(p[0])
    assert "not squared" in out["rule"] and out["squared"] is False
    sq = svd_entropy(rows, align=False, squared=True)
    q = sigma ** 2 / (sigma ** 2).sum()
    assert sq["svd_entropy"] == pytest.approx(-(q * np.log(q)).sum(), rel=1e-9)
    assert "SQUARED" in sq["rule"]


def test_rows_of_any_length_and_a_2d_array_both_work():
    rng = np.random.default_rng(5)
    rows = [np.interp(np.linspace(0, 1, n), T, _bump()) for n in (90, 150, 200)]
    assert svd_entropy(rows)["n_used"] == 3
    assert svd_entropy(np.vstack(_members(_bump, 5, rng)))["n_used"] == 5


def test_nan_rows_are_dropped_and_too_few_rows_say_why():
    rng = np.random.default_rng(6)
    rows = _members(_bump, 5, rng)
    rows[2] = rows[2].copy()
    rows[2][10] = np.nan
    out = svd_entropy(rows)
    assert out["n_members"] == 5 and out["n_used"] == 4 and out["n_dropped"] == 1
    one = svd_entropy(rows[:1])
    assert one["svd_entropy"] is None and one["svd_entropy_norm"] is None
    assert "at least two" in one["reason"]
    assert svd_entropy([])["reason"]


def test_a_large_family_is_sampled_seeded_and_says_so():
    rng = np.random.default_rng(7)
    rows = _members(_bump, 60, rng, noise=0.01)
    out = svd_entropy(rows, max_members=25, seed=3)
    assert out["sampled"] and out["n_used"] == 25 and out["n_members"] == 60
    again = svd_entropy(rows, max_members=25, seed=3)
    assert again["svd_entropy"] == out["svd_entropy"]
    assert not svd_entropy(rows)["sampled"]


def test_a_named_medoid_is_the_alignment_anchor():
    rng = np.random.default_rng(8)
    rows = _members(_bump, 15, rng, noise=0.01, max_shift=0.15)
    out = svd_entropy(rows, medoid=4)
    assert out["medoid_index"] == 4


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

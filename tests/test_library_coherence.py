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
    # fix round 1: each shifted row is padded with its own edge value, never cut
    assert aligned["padding"] == "edge" and "edge value" in aligned["rule"]
    assert aligned["n_misaligned"] == 0, "no shift here exceeds a quarter of the length"


def test_a_few_stragglers_do_not_decide_the_alignment_for_the_family():
    """Critic finding 4: under the old cut-to-common-span rule, 3 noise members
    in 63 dropped the kept span under half and the score jumped 0.39 -> 0.55.
    With edge padding a straggler costs about its own share."""
    from _shape_families import drop, member
    rng = np.random.default_rng(9)
    family = [member(drop, rng, noise=0.02, kind="ar1_095", max_shift=0.2) for _ in range(60)]
    base = svd_entropy(family)["svd_entropy_norm"]
    strays = [background(150, "ar1_095", rng) for _ in range(3)]
    with_strays = svd_entropy(family + strays)["svd_entropy_norm"]
    assert with_strays - base < 0.08, (base, with_strays)


def test_clean_shifted_copies_are_not_counted_misaligned_and_a_far_one_is():
    """Fix round 2: the threshold is set from the shift distribution of clean
    families — 1,800 members of drop/sharkfin/square families, each edge off by
    up to 20 % of its window, needed at most 0.30 of the length — and the rule
    is 0.4 of the length (two members each 20 % off can sit 0.4 apart)."""
    from _shape_families import drop, member
    from Working.library import coherence
    assert coherence.MISALIGNED_FRACTION == 0.4
    rng = np.random.default_rng(12)
    clean = [member(drop, rng, noise=0.05, kind="ar1_095", max_shift=0.2) for _ in range(100)]
    assert svd_entropy(clean)["n_misaligned"] == 0
    rows = _members(_bump, 20, rng, noise=0.01)
    rows.append(_bump(0.04) + 0.01 * rng.normal(size=T.size))      # 0.46 of the length off
    assert svd_entropy(rows, medoid=0)["n_misaligned"] == 1


def test_pure_coloured_noise_is_not_more_coherent_than_its_own_null():
    """Re-critique finding 2: 100 pure AR(1) phi 0.99 windows scored 0.813
    against a phase-randomised null p05 of 0.821 — "more coherent than noise".
    The null is now trend-kept, the same surrogate HDBSCAN uses."""
    rng = np.random.default_rng(13)
    noise = [background(150, "ar1_099", rng) for _ in range(100)]
    out = svd_entropy(noise)
    assert out["null_kind"] == "trend-kept phase-randomised"
    assert out["svd_entropy_norm"] >= out["null_p05"], out


def test_the_score_comes_with_its_own_noise_null_and_the_squared_variant():
    """Critic finding 5: beside eq. 17, the same score on 5 phase-randomised
    surrogates of the members ("noise like these members' scores X"), the
    sigma^2-weighted variant, and the sigma^2 share of the main component."""
    rng = np.random.default_rng(11)
    copies = _members(_bump, 40, rng, noise=0.01, kind="ar1_095")
    c = svd_entropy(copies)
    assert c["null_draws"] == 5
    assert c["svd_entropy_norm"] < c["null_p05"] <= c["null_median"], c
    noise = [background(150, "ar1_095", rng) for _ in range(40)]
    n = svd_entropy(noise)
    assert n["svd_entropy_norm"] > n["null_p05"] - 0.05, "noise scores like its own surrogates"
    for out in (c, n):
        assert 0.0 <= out["svd_entropy_squared_norm"] <= 1.0
        assert out["null_squared_median"] is not None
    noisy_copies = _members(_bump, 40, rng, noise=0.05, kind="ar1_095")
    noisy_mix = noisy_copies[:20] + _members(_wavelet, 20, rng, noise=0.05, kind="ar1_095")
    assert (svd_entropy(noisy_mix)["svd_entropy_squared_norm"]
            > svd_entropy(noisy_copies)["svd_entropy_squared_norm"] + 0.03)
    again = svd_entropy(copies)
    assert again["null_median"] == c["null_median"], "the null is seeded"


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
    assert "not squared" in out["rule"] and out["squared"] is False
    q = sigma ** 2 / (sigma ** 2).sum()
    # fix round 1: top_share is the sigma^2 share of the main component, and says so
    assert out["top_share"] == pytest.approx(q[0])
    assert "sigma^2" in out["top_share_is"]
    assert out["svd_entropy_squared_norm"] == pytest.approx(
        -(q * np.log(q)).sum() / np.log(min(20, 256)), rel=1e-9)
    sq = svd_entropy(rows, align=False, squared=True)
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

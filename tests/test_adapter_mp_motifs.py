"""
test_adapter_mp_motifs.py
===========================
`detection.mp_motifs` — Scores (a matrix profile) → SpanSet of motif groups,
the block form of `motif_groups.build_motif_groups`.

Runnable standalone:  python tests/test_adapter_mp_motifs.py
"""

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

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Detection.matrix_profiling.motif_groups import build_motif_groups  # noqa: E402
from Working.types import Scores  # noqa: E402

discover_adapters()
NAME = "detection.mp_motifs"
FS = 1.0
M = 20


def bursts(n=600, seed=0):
    """Noise with the same 20-sample sine burst planted three times."""
    rng = np.random.default_rng(seed)
    x = 0.1 * rng.standard_normal(n)
    burst = np.sin(np.linspace(0, 4 * np.pi, M))
    for s in (100, 300, 480):
        x[s:s + M] += burst
    return x


@pytest.fixture(scope="module")
def profile():
    import stumpy
    x = bursts()
    mp = stumpy.stump(x, M)[:, 0].astype(float)
    padded = np.full(len(x), np.nan); padded[:len(mp)] = mp
    return x, mp, Scores(values=padded, fs=FS)


def test_registered_as_a_scores_consumer():
    spec = get_adapter(NAME)
    assert spec.input_kind == "scores" and spec.output_kind == "spanset"
    assert spec.category == "detect"


def test_recovers_m_from_the_nan_tail_and_reproduces_build_motif_groups(profile):
    x, mp, scores = profile
    spec = get_adapter(NAME)
    r = spec.run(x, np.arange(len(x), dtype=float), FS, value=scores, **spec.validate_params({"max_motifs": 2, "n_neighbors": 2}))
    assert r.meta["m"] == M
    ref = build_motif_groups(x, mp, M, max_motifs=2, n_neighbors=2)
    assert [g["seed_idx"] for g in r.meta["groups"]] == [g["seed_idx"] for g in ref]
    assert [g["neighbours"] for g in r.meta["groups"]] == [[[i, d] for i, d in g["neighbours"]] for g in ref]


def test_spans_are_labelled_by_group_and_cover_the_planted_bursts(profile):
    x, mp, scores = profile
    spec = get_adapter(NAME)
    r = spec.run(x, None, FS, value=scores, **spec.validate_params({"max_motifs": 1, "n_neighbors": 2}))
    assert r.value.labels[0] == "G0:seed"
    assert all(e - s == M for s, e in zip(r.value.starts, r.value.ends))
    found = sorted(set(r.value.starts))
    assert len(found) == len(r.value.starts), "the seed must not be repeated as its own neighbour"
    # the seed lands wherever the profile is lowest, a few samples into a burst
    assert sum(any(abs(f - b) <= M // 2 for f in found) for b in (100, 300, 480)) >= 2


def test_window_min_overrides_the_recovered_m(profile):
    x, mp, scores = profile
    spec = get_adapter(NAME)
    r = spec.run(x, None, FS, value=scores, **spec.validate_params({"max_motifs": 1, "window_min": 0.5}))
    assert r.meta["m"] == 30


def test_refuses_a_missing_input():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="Matrix profile"):
        spec.run(np.zeros(100), None, FS, **spec.validate_params({}))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

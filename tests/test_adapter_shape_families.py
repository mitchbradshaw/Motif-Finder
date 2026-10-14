"""
test_adapter_shape_families.py
================================
`catalogue.shape_families` (w2-e), WindowSet -> Grouping: the Library's
clustering on a chain's windows. Pinned: the spec (method choices read from
the grouping registry, every method param flattened with bounds), windows
sliced from `x` with channel-absolute starts, the Trace-shape vectors used
when `shape_file` is there, windows outside the span counted, and the meta a
page reads — flags, SVD entropy beside its null, medoid-member exemplars,
rules, an honest summary — plus a declared estimate.
"""

import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _event_families_synthetic import equal_length, two_shapes  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Catalogue import shape_families as SF  # noqa: E402
from Working.library.grouping import methods as registry  # noqa: E402
from Working.types import Grouping, WindowSet  # noqa: E402

NAME = "catalogue.shape_families"
L = 150
GAP = 100


@pytest.fixture(scope="module")
def spec():
    discover_adapters()
    return get_adapter(NAME)


def _recording(per=30, seed=0, kind="ar1_095"):
    waves, truth = two_shapes(per=per, seed=seed, kind=kind)
    W = equal_length(waves, L)
    x = np.concatenate([np.concatenate([w, np.zeros(GAP)]) for w in W])
    starts = np.array([i * (L + GAP) for i in range(len(W))], dtype=np.int64)
    return x, starts, W, truth


def _run(spec, x, t, ws, **params):
    return spec.run(x, t, 1.0, **spec.validate_params(params), value=ws)


def test_the_spec(spec):
    assert spec.stage == "catalogue" and spec.category == "cluster" and spec.page_name == "Shape families"
    assert spec.input_kind == "windowset" and spec.output_kind == "grouping"
    by = {p.name: p for p in spec.params}
    assert by["method"].choices == [m.name for m in registry.methods_for("shape-distance")]
    assert by["method"].default == "hdbscan"
    for f in SF.flat_param_specs():
        assert f["flat"] in by, f["flat"]
        assert by[f["flat"]].default == f["spec"]["default"]
    for p in spec.params:
        if p.type in (int, float):
            assert p.min is not None and p.max is not None, f"{p.name} has no bounds"
    assert spec.estimate is not None
    assert "method" in spec.description and "noise" in spec.description


def test_windows_sliced_from_x_with_channel_absolute_starts(spec):
    x, starts, W, truth = _recording()
    offset = 40_000
    t = (offset + np.arange(len(x))) / 1.0
    ws = WindowSet(starts=starts + offset, length=L, fs=1.0)
    res = _run(spec, x, t, ws)
    assert isinstance(res.value, Grouping) and len(res.value.labels) == len(W)
    assert adjusted_rand_score(truth, res.value.labels) >= 0.9
    # the same answer as the core on the same windows: one implementation
    direct = SF.shape_families(W, method="hdbscan")
    assert (np.asarray(res.value.labels) == direct.labels).all()


def test_windows_outside_the_span_are_counted_not_guessed(spec):
    x, starts, W, truth = _recording()
    starts = np.concatenate([starts, [len(x) - 10, -5]])
    ws = WindowSet(starts=starts, length=L, fs=1.0)
    res = _run(spec, x, np.arange(len(x), dtype=float), ws)
    lab = np.asarray(res.value.labels)
    assert lab[-1] == -1 and lab[-2] == -1
    assert res.meta["omitted"]["outside_span"] == 2
    assert sum(res.meta["omitted"].values()) == int((lab == -1).sum())


def test_the_trace_shape_vectors_are_used_when_present(spec, tmp_path):
    """With `shape_file` on the windows, the block clusters THOSE vectors (Trace shape's), not slices of x:
    here x is pure noise and only the vectors hold the two shapes."""
    from Working.training import shape as tshape
    x, starts, W, truth = _recording()
    V = SF.prepared_vectors(W)                  # the Library's preparation (ward.shape_vectors)
    n = len(W)
    frame = pd.DataFrame({"recording_id": np.ones(n, dtype=np.int64), "source_file": ["a.mat"] * n,
                          "channel": np.zeros(n, dtype=np.int64), "start": starts, "length": np.full(n, L),
                          "fs": np.ones(n), "scale_min": np.full(n, 2.5), "role": ["train"] * n,
                          "set_id": np.ones(n, dtype=np.int64), "raw_range_mv": np.ones(n), "peak_frac": np.zeros(n),
                          "shape_row": np.arange(n)[::-1]})
    shapes = tshape.ShapeSet(frame=frame, vectors=V[::-1].astype(np.float32), meta={"resample_length": V.shape[1]})
    path = shapes.save(str(tmp_path / "shapes"))
    feats = pd.DataFrame({"shape_file": [path] * n, "shape_row": np.arange(n)[::-1]})
    noise = np.random.default_rng(0).standard_normal(len(x))
    res = _run(spec, noise, np.arange(len(x), dtype=float), WindowSet(starts=starts, length=L, fs=1.0, features=feats))
    assert adjusted_rand_score(truth, res.value.labels) >= 0.9
    assert res.meta["vectors_from"] == "shape_file"


def test_meta_carries_flags_coherence_with_its_null_and_member_exemplars(spec):
    x, starts, W, truth = _recording()
    ws = WindowSet(starts=starts, length=L, fs=1.0)
    m = _run(spec, x, np.arange(len(x), dtype=float), ws).meta
    assert m["method"] == "hdbscan" and m["k"] == 2
    assert m["method_params"]["min_cluster_size"] == 10
    assert sorted(m["family_sizes"].values(), reverse=True) == [30, 30]
    assert m["omitted"] == {}, "all 60 windows are in a family: nothing to count"
    for fam in m["families"]:
        for key in ("family", "size", "noise_like", "unstable", "tested", "why", "svd_entropy",
                    "svd_entropy_norm", "svd_entropy_null_median", "svd_entropy_null_p05",
                    "svd_entropy_squared_norm", "svd_entropy_beyond_noise", "svd_entropy_rule", "top_share",
                    "confident"):
            assert key in fam, key
        assert fam["noise_like"] is False and fam["svd_entropy_beyond_noise"] is True and fam["confident"] is True
    labels = np.asarray(_run(spec, x, np.arange(len(x), dtype=float), ws).value.labels)
    # the serializer's format (W2-F, W2-D's snippets): {"<label>": <window index>} + a rule string
    ex_map = m["exemplar_windows"]
    assert isinstance(ex_map, dict) and set(ex_map) == {"1", "2"}
    for label, w in ex_map.items():
        assert isinstance(label, str) and isinstance(w, int)
        assert labels[w] == int(label), "an exemplar is a member of its family"
    assert isinstance(m["exemplar_rule"], str) and "medoid" in m["exemplar_rule"]
    # the richer list rides under its own key
    for ex in m["exemplars"]:
        assert ex_map[str(ex["family"])] == ex["window"]
        assert ex["start"] == int(starts[ex["window"]])
    assert m["fraction_placed"] == pytest.approx(1.0) and m["fraction_confident"] == pytest.approx(1.0)
    names = [r["name"] for r in m["rules"]]
    assert "svd_entropy" in names and "noise_like" in names
    assert "fit_summary" in m and "seconds" in m
    s = m["summary"]
    assert "2 families" in s and "hdbscan" in s and "SVD entropy" in s and "noise" in s


def test_a_noise_like_family_is_said_in_the_summary(spec, monkeypatch):
    x, starts, W, truth = _recording()
    real = SF.shape_families

    def flagged(*a, **k):
        r = real(*a, **k)
        r.families[0].flags.update(noise_like=True, why="no better than noise of the same colour: test")
        return r

    monkeypatch.setattr(SF, "shape_families", flagged)
    m = _run(spec, x, np.arange(len(x), dtype=float), WindowSet(starts=starts, length=L, fs=1.0)).meta
    assert m["n_noise_like"] == 1
    assert "noise-like" in m["summary"] or "no better than noise" in m["summary"]
    assert any("no better than noise" in w for w in m["warnings"])


def test_an_empty_window_set_says_why(spec):
    x = np.zeros(1000)
    res = _run(spec, x, np.arange(1000.0), WindowSet(starts=np.array([], dtype=np.int64), length=L, fs=1.0))
    assert len(res.value.labels) == 0 and res.meta["k"] == 0
    assert "no window" in res.meta["summary"].lower()


def test_the_method_params_reach_the_engine(spec):
    x, starts, W, truth = _recording()
    ws = WindowSet(starts=starts, length=L, fs=1.0)
    res = _run(spec, x, np.arange(len(x), dtype=float), ws, method="kshape", kshape_k=2)
    assert res.meta["method"] == "kshape" and res.meta["method_params"]["k"] == 2
    assert adjusted_rand_score(truth, res.value.labels) >= 0.9
    res3 = _run(spec, x, np.arange(len(x), dtype=float), ws, method="kshape", kshape_k=3, min_group=2)
    assert res3.meta["k"] == 3


def test_the_estimate_is_honest_and_local_at_defaults(spec):
    n = 120 * 3600
    x = np.zeros(n)
    t = np.arange(n, dtype=float)
    p = spec.validate_params({})
    sec = spec.estimate(x, t, 1.0, **p)
    assert np.isfinite(sec) and 0 < sec < 15 * 60
    p_auto = spec.validate_params({"method": "kshape"})
    assert spec.estimate(x, t, 1.0, **p_auto) > spec.estimate(x[: n // 10], t[: n // 10], 1.0, **p_auto)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

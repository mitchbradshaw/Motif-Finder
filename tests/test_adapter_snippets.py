"""
test_adapter_snippets.py
=========================
`catalogue.snippets` (W2-D) as a block: its spec (types, category, page name,
parameters and bounds, cost), one run behind `preprocessing.sliding_windows`
(gap 0) on a synthetic recording, the channel-absolute WindowSet convention
(a span that does not start at sample 0), what lands in `meta`, and the
refusals in words.
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from tests import _snippets_synthetic as syn  # noqa: E402
from Working.types import Grouping, Scores, WindowSet  # noqa: E402

FS = syn.FS


@pytest.fixture(scope="module")
def spec():
    discover_adapters()
    return get_adapter("catalogue.snippets")


def _windows(x, t, window_s=3600.0, gap_s=0.0):
    sw = get_adapter("preprocessing.sliding_windows")
    return sw.run(x, t, FS, **sw.validate_params({"window_s": window_s, "gap_s": gap_s})).value


def _run(spec, x, t0=0.0, **params):
    t = t0 + np.arange(len(x)) / FS
    ws = _windows(x, t)
    return spec.run(x, t, FS, value=ws, **spec.validate_params(params)), ws


def test_types_category_and_names(spec):
    assert spec.input_kind == "windowset"
    assert spec.output_kind == "grouping"
    assert spec.stage == "catalogue"
    assert spec.category == "cluster"
    assert spec.page_name == "Snippets"
    assert "subseq_frac" in spec.description and "Tune" in spec.description


def test_defaults_and_bounds(spec):
    p = spec.validate_params({})
    assert p == {"k": 0, "k_max": 6, "subseq_frac": 0.35, "mpdist_percentage": 0.05}
    for bad in ({"subseq_frac": 0.0}, {"subseq_frac": 1.5}, {"k": -1}, {"k_max": 1},
                {"mpdist_percentage": 1.5}):
        with pytest.raises(ValueError):
            spec.validate_params(bad)


def test_declares_its_cost(spec):
    assert spec.estimate is not None
    assert spec.max_span_samples == 7 * 24 * 3600
    # uncalibrated in a fresh worktree: None, never a guessed number
    est = spec.estimate(np.zeros(1000), np.arange(1000.0), 1.0, **spec.validate_params({}))
    assert est is None or est > 0


def test_a_run_labels_every_window_and_fills_meta(spec):
    x, truth = syn.three_regimes(0)
    res, ws = _run(spec, x)
    assert res.output_kind == "grouping"
    assert isinstance(res.value, Grouping)
    labels = np.asarray(res.value.labels)
    assert len(labels) == ws.n_windows == 48
    assert syn.agreement(labels, truth) >= 0.9
    meta = res.meta
    assert meta["k"] == 3 and meta["k_chosen_by"] == "knee"
    for key in ("areas", "change_k", "fractions", "snippet_starts_s", "subseq_frac", "m_s",
                "run_length_mean", "run_length_median", "run_length_vs_shuffled", "runs_by_k",
                "exemplar_windows", "exemplar_rule", "rules", "elapsed_s", "summary", "k_reason"):
        assert key in meta, key
    assert meta["m_s"] == 3600.0
    assert meta["subseq_frac"] == 0.35 and meta["s"] == 126
    assert len(meta["areas"]) == 7 and sorted(meta["change_k"]) == [str(k) for k in range(2, 8)]
    for lab, w in meta["exemplar_windows"].items():
        assert labels[w] == int(lab)
        assert meta["snippet_starts_s"][int(lab) - 1] == pytest.approx(ws.starts[w] / FS)
    assert {r["name"] for r in meta["rules"]} >= {"MPdist", "k (knee)", "window label", "regime run length"}
    assert meta["summary"].startswith("k = 3 snippets (knee)")


def test_a_span_that_does_not_start_at_zero_gives_the_same_labels(spec):
    x, _ = syn.three_regimes(1)
    a, _ = _run(spec, x, t0=0.0)
    b, ws = _run(spec, x, t0=7200.0)
    assert ws.starts[0] == int(7200 * FS)                 # channel-absolute
    np.testing.assert_array_equal(a.value.labels, b.value.labels)
    assert b.meta["snippet_starts_s"][0] == pytest.approx(a.meta["snippet_starts_s"][0] + 7200.0)


def test_k_set_by_hand(spec):
    x, _ = syn.three_regimes(0)
    res, _ = _run(spec, x, k=2)
    assert res.meta["k"] == 2 and res.meta["k_chosen_by"] == "parameter"
    assert set(np.unique(res.value.labels)) <= {1, 2}


def test_no_structure_says_so_on_the_face(spec):
    res, _ = _run(spec, syn.ar1_null(0))
    assert res.meta["k"] == 1
    assert res.meta["summary"].startswith("k = 1 snippet (knee)")
    assert "no knee" in res.meta["k_reason"]


def test_mostly_nan_windows_are_minus_one_and_on_the_face(spec):
    x, _ = syn.three_regimes(0)
    x = x.copy()
    x[10 * syn.PIECE:11 * syn.PIECE] = np.nan
    res, _ = _run(spec, x)
    assert res.value.labels[10] == -1
    assert res.meta["n_windows_nan"] == 1
    assert "1 of 48 windows mostly NaN" in res.meta["summary"]


def test_requires_a_windowset(spec):
    x = np.zeros(1000)
    t = np.arange(1000.0)
    with pytest.raises(ValueError, match="requires a WindowSet"):
        spec.run(x, t, 1.0, **spec.validate_params({}))
    with pytest.raises(ValueError, match="needs a WindowSet"):
        spec.run(x, t, 1.0, value=Scores(values=x, fs=1.0), **spec.validate_params({}))


def test_too_few_windows_is_refused_in_words(spec):
    x = syn.ar1_null(0, hours=8)
    with pytest.raises(ValueError, match="too few pieces"):
        _run(spec, x)


def test_a_window_outside_the_span_is_refused(spec):
    x = np.zeros(20 * syn.PIECE)
    ws = WindowSet(starts=np.arange(20) * syn.PIECE + 10 ** 6, length=syn.PIECE, fs=FS)
    with pytest.raises(ValueError, match="do not lie inside the span"):
        spec.run(x, np.arange(len(x)) / FS, FS, value=ws, **spec.validate_params({"k_max": 3}))

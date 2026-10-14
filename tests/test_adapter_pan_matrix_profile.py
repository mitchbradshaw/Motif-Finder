"""
test_adapter_pan_matrix_profile.py
====================================
The adapter `detection.pan_matrix_profile` (Signal -> Encoding image): its
spec, its meta, its cost hooks, its cancellation through the executor's
channel, and the pan -> `detection.wavelet_summation` chain (the band of rows
maps onto the intended window lengths).

Runnable standalone:  python tests/test_adapter_pan_matrix_profile.py
"""

import json
import os
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from tests import _pan_synthetic as syn  # noqa: E402

discover_adapters()
NAME = "detection.pan_matrix_profile"
FS = 1.0


def _spec():
    return get_adapter(NAME)


def _run(x, **params):
    spec = _spec()
    kw = spec.validate_params(params)
    return spec.run(x, np.arange(len(x)) / FS, FS, **kw)


def _small(n=3000, seed=2):
    return syn.no_structure("ar97", n, seed=seed)


def test_spec_is_a_signal_to_image_encoding_block():
    spec = _spec()
    assert spec.input_kind == "signal" and spec.output_kind == "encoding"
    assert spec.category == "encode" and spec.page_name == "Pan matrix profile"
    assert spec.estimate is not None and spec.max_span_samples is not None
    assert spec.recommend is not None and spec.derive is not None
    defaults = spec.validate_params({})
    assert defaults == {"min_window_s": 30.0, "max_window_s": 3600.0, "n_lengths": 12, "null_draws": 3,
                        "null": "aaft", "seed": 0, "max_fill_s": 5.0}
    with pytest.raises(ValueError):
        spec.validate_params({"percentage": 0.5})                 # no approximate mode (F5)
    d = spec.description
    assert "amplitude-adjusted" in d
    assert "m − 1" in d and "starting at" in d                    # the summed band's NaN tail; column i (F8)
    assert "8 h" in d and "chain" in d                            # what an 8 h span cannot judge (F3)
    assert "max_window_s" in spec.description and "no length stands out" in spec.description


def test_meta_names_the_rows_the_alignment_and_the_rules():
    x = _small()
    res = _run(x, min_window_s=20, max_window_s=200, n_lengths=4)
    img = res.value.values
    assert res.output_kind == "encoding" and res.value.kind == "image"
    assert img.shape == (4, len(x))
    m = res.meta
    assert m["alignment"] == "start" and m["rows"] == "long first"
    assert m["lengths_s"] == sorted(m["lengths_s"], reverse=True) and len(m["lengths_s"]) == 4
    assert len(m["per_length"]) == 4
    for d in m["per_length"]:
        for k in ("length_s", "best", "p05", "median", "gap", "judged", "clears", "reason", "n_windows_nan"):
            assert k in d
    assert "suggested_window_s" in m and "verdict" in m and "summary" in m
    assert {r["name"] for r in m["rules"]} >= {"brightness", "gap to the null", "clears the null"}
    assert m["approximate"] is False
    json.dumps({k: v for k, v in m.items()})                  # meta must be JSON-able for the bridge


def test_no_structure_says_so_in_meta_and_the_summary():
    x = _small(7200, seed=11)
    res = _run(x, max_window_s=900)
    assert res.meta["suggested_window_s"] is None
    assert "no length stands out" in res.meta["summary"]


def test_the_band_and_the_suggestion_caveat_are_on_the_face():
    x, _, _ = syn.planted(4 * 3600, seed=0)
    res = _run(x)
    m = res.meta
    assert m["cleared_s"] and m["suggested_window_s"] in m["cleared_s"]
    assert "clears" in m["summary"] and "strongest at" in m["summary"]
    rules = {r["name"]: r["rule"] for r in m["rules"]}
    assert "suggested window" in rules and "not the event" in rules["suggested window"]
    assert m["null"] == "aaft" and "reasons" in m and "n_stalled" in m


def test_estimate_is_the_matrix_profile_model_times_the_profiles(monkeypatch):
    from Working.Detection.matrix_profiling import cost
    spec = _spec()
    x = np.zeros(14400)
    t = np.arange(len(x)) / FS
    tmp = tempfile.mkdtemp(prefix="pan_cost_")
    monkeypatch.setattr(cost, "CALIBRATION_PATH", os.path.join(tmp, "mp_calibration.json"))
    from Working.Detection.matrix_profiling import pan as P
    monkeypatch.setattr(P, "first_call_seconds", lambda: 0.0)           # pinned separately below
    assert spec.estimate(x, t, FS, **spec.validate_params({})) is None        # uncalibrated: never a guess
    k = 3.5e-9
    with open(cost.CALIBRATION_PATH, "w") as f:
        json.dump({cost._calibration_key("stump"): {"k": k, "n0": 1}}, f)
    one = k * len(x) ** 2
    est = spec.estimate(x, t, FS, **spec.validate_params({}))
    from Working.Detection.matrix_profiling import pan as PP
    judged = sum(1 for m in PP.window_lengths(len(x), FS, 30, 3600, 12)[0] if PP.judgeable(len(x), m))
    assert judged < 12
    assert est == pytest.approx(one * (12 + 3 * judged))     # every length once; 3 null draws per judged length
    est0 = spec.estimate(x, t, FS, **spec.validate_params({"null_draws": 0, "n_lengths": 6}))
    assert est0 == pytest.approx(one * 6)


def test_the_first_call_in_a_process_adds_stumpys_compile_time():
    """The cost model times warm calls; a fresh process pays numba's compile of `stump` once (35-46 s here)."""
    import stumpy
    from Working.Detection.matrix_profiling import pan as P
    stumpy.stump(np.random.default_rng(0).standard_normal(200), 16)    # compiled now, in this process
    assert P.first_call_seconds() == 0.0
    import sys
    disp = sys.modules["stumpy.stump"]._stump
    assert len(disp.signatures) >= 1                                    # what first_call_seconds reads
    assert P.FIRST_CALL_S > 0


def test_the_bridge_sees_the_matrix_profile_cost_model():
    """`webui/server/chain.py::_uses_mp_cost` reads the adapter module for a value imported from the
    matrix-profile cost module; that is what lets the bridge calibrate it on first need."""
    import importlib
    from Working.Detection.matrix_profiling import cost
    mod = importlib.import_module(_spec().estimate.__module__)
    assert any(getattr(v, "__module__", None) == cost.__name__ for v in vars(mod).values())


def test_memory_guard_is_a_constant_not_the_calibration():
    from Adapters import detection_pan_matrix_profile as A
    assert _spec().max_span_samples == A.MAX_SPAN_SAMPLES == 1_000_000


def test_recommend_caps_the_longest_length_at_what_the_span_can_judge():
    spec = _spec()
    x = np.zeros(4 * 3600)
    assert spec.recommend(x, np.arange(len(x)), 1.0) == {"max_window_s": 1028.0}
    x = np.zeros(48 * 3600)
    assert spec.recommend(x, np.arange(len(x)), 1.0) == {"max_window_s": 3600.0}
    assert spec.recommend(np.zeros(100), np.arange(100), 1.0) == {}


def test_derive_lists_the_lengths_and_how_many_are_judged():
    spec = _spec()
    x = np.zeros(4 * 3600)
    rows = spec.derive(x, np.arange(len(x)), 1.0, spec.validate_params({}))
    labels = {r[0]: r for r in rows}
    assert "Lengths (s)" in labels and "Judged against the null" in labels
    assert labels["Judged against the null"][1].startswith("9 of 12")
    assert labels["Judged against the null"][2] == "warn"


def test_cancel_through_run_kwargs_raises_recipe_cancelled_and_progress_fires_per_length():
    from Working.execution import RecipeCancelled
    spec = _spec()
    x = _small()
    kw = spec.validate_params({"min_window_s": 20, "max_window_s": 200, "n_lengths": 4, "null_draws": 0})
    seen = []
    spec.run(x, np.arange(len(x)), FS, on_progress=lambda d, t, s: seen.append(d), **kw)
    assert seen == [1, 2, 3, 4]
    with pytest.raises(RecipeCancelled):
        spec.run(x, np.arange(len(x)), FS, should_cancel=lambda: True, **kw)


def test_cancel_inside_execute_recipe_is_a_cancellation_not_a_failure():
    import shutil
    import Working.config as cfg
    from Working.database import queries as q
    from Working.database.schema import init_db
    from Working.execution import RecipeCancelled, execute_recipe
    tmp = tempfile.mkdtemp(prefix="pan_cancel_")
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        x = _small()
        npy = os.path.join(tmp, "CH1.npy")
        np.save(npy, x)
        db = os.path.join(tmp, "t.sqlite")
        conn = init_db(db)
        q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
        conn.close()
        from Working.templates import apply_template
        recipe = apply_template(None, {"name": "pan_only", "kind": "encoding", "version": 1, "steps": [
            {"stage": "detection", "algorithm": "pan_matrix_profile",
             "params": {"min_window_s": 20.0, "max_window_s": 200.0, "n_lengths": 4, "null_draws": 0}}]},
            recording_id=1)
        calls = []
        with pytest.raises(RecipeCancelled):
            execute_recipe(recipe, db_path=db, force=True,
                           run_kwargs={"on_progress": lambda d, t, s: calls.append(d),
                                       "should_cancel": lambda: len(calls) >= 1})
        assert calls == [1]
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_pan_then_wavelet_summation_sums_the_intended_lengths():
    x, _, _ = syn.planted(2 * 3600, seed=3)
    t = np.arange(len(x)) / FS
    pan = _run(x, min_window_s=30, max_window_s=900, n_lengths=8, null_draws=0)
    img = pan.value.values
    ls = pan.meta["lengths_s"]
    summ = get_adapter("detection.wavelet_summation")
    # the longer half of the lengths: rows 0..3 (row 0 = the longest)
    res = summ.run(x, t, FS, value=pan.value, **summ.validate_params({"row_from": 0.0, "row_to": 0.5}))
    lo, hi = res.meta["rows_used"]
    assert (lo, hi) == (0, 4)
    assert min(ls[lo:hi]) > max(ls[hi:])                        # the band is the long lengths, not the short
    omega = res.value.values
    assert len(omega) == len(x)
    np.testing.assert_allclose(omega, img[lo:hi].astype(float).sum(axis=0))
    m_longest_in_band = int(round(ls[lo] * FS))
    assert np.all(np.isnan(omega[len(x) - m_longest_in_band + 1:]))   # the band's longest row's tail
    assert np.all(np.isfinite(omega[:len(x) - m_longest_in_band + 1]))
    # the short half (row_from 0.5) reads the short lengths
    res2 = summ.run(x, t, FS, value=pan.value, **summ.validate_params({"row_from": 0.5, "row_to": 1.0}))
    lo2, hi2 = res2.meta["rows_used"]
    assert max(ls[lo2:hi2]) < min(ls[:lo2])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

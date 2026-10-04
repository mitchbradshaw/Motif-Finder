"""
test_wavelet_band_scope.py
===========================
fixup-AC: a wavelet level is a band in `Z`'s band scope (Q-W3).

`Z` made a band a typed entry so this could be one more kind and one more step
builder, not a reshaping. What it pins:

* **`{kind: "wavelet", wavelet, level}` is a band.** It normalises like a
  bandpass does (a default label, a kind refused by name when unknown), and a
  bad wavelet or level is refused before anything runs.
* **The step a wavelet band prepends is the block Analyse inserts** —
  `preprocessing.wavelet_bands` with the adapter's own defaults filled and the
  wavelet and level set — so a wavelet band run hashes the same as the chain a
  researcher builds by hand, exactly as `Z` made a bandpass band do.
* **`materialize_target` prepends it** for a wavelet target, as it prepends a
  bandpass for a bandpass target, and the paired surrogate goes AHEAD of it.
* **A wavelet band is resolved against a recording**: its label carries the
  level and its Hz range at that `fs` ("db4 level 4 · 0.031–0.062 Hz"), and a
  level deeper than the scope's span allows is refused by name.
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working import run_groups  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.recipes import BAND_KINDS, make_recipe, normalize_band, recipe_hash  # noqa: E402

STEPS = [
    {"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.3}},
]


def _wavelet_as_analyse_inserts_it(level, wavelet="db4"):
    """What Analyse's *+ insert* puts in the chain: the block with the
    adapter's own defaults filled, then the level (and wavelet) set on the page."""
    from Adapters.registry import discover_adapters, get_adapter

    discover_adapters()
    params = get_adapter("preprocessing.wavelet_bands").validate_params({})
    params.update({"level": level, "wavelet": wavelet})
    return {"stage": "preprocessing", "algorithm": "wavelet_bands", "params": params}


# ── a wavelet level is a typed band ─────────────────────────────────────────

def test_wavelet_is_a_band_kind():
    assert BAND_KINDS == ("bandpass", "wavelet")


def test_a_wavelet_band_normalises_with_a_default_wavelet_and_label():
    assert normalize_band({"kind": "wavelet", "level": 4}) == {
        "kind": "wavelet", "label": "db4 level 4", "wavelet": "db4", "level": 4}
    assert normalize_band({"kind": "wavelet", "wavelet": "sym4", "level": 0})["label"] == "sym4 residual"
    assert normalize_band({"kind": "wavelet", "level": 2, "label": "fast"})["label"] == "fast"


def test_a_wavelet_band_rides_in_a_fan_out_scope():
    recipe = make_recipe(1, STEPS, span=(0, 100), fan_out={
        "kind": "bands", "targets": [{"kind": "wavelet", "level": 3},
                                     {"label": "mid", "low_hz": 0.01, "high_hz": 0.1}]})
    kinds = [t["kind"] for t in recipe["fan_out"]["targets"]]
    assert kinds == ["wavelet", "bandpass"]


@pytest.mark.parametrize("bad", [
    {"kind": "wavelet"},                                  # no level
    {"kind": "wavelet", "level": -1},
    {"kind": "wavelet", "level": 2.5},
    {"kind": "wavelet", "level": True},
    {"kind": "wavelet", "level": 2, "wavelet": "morl"},  # continuous: no stationary transform
    {"kind": "wavelet", "level": 2, "wavelet": "not-a-wavelet"},
])
def test_a_bad_wavelet_band_is_refused(bad):
    with pytest.raises(ValueError):
        normalize_band(bad)


def test_an_unknown_wavelet_is_refused_by_name():
    with pytest.raises(ValueError) as e:
        normalize_band({"kind": "wavelet", "level": 2, "wavelet": "not-a-wavelet"})
    assert "not-a-wavelet" in str(e.value) and "db4" in str(e.value)


# ── the step it prepends is the block Analyse inserts ───────────────────────

def test_the_wavelet_band_step_is_the_block_analyse_inserts():
    assert run_groups.band_step({"kind": "wavelet", "level": 4}) == _wavelet_as_analyse_inserts_it(4)
    assert run_groups.band_step({"kind": "wavelet", "wavelet": "sym4", "level": 0}) == \
        _wavelet_as_analyse_inserts_it(0, "sym4")


def test_a_wavelet_band_recipe_hashes_the_same_as_the_hand_built_chain():
    bands = [{"kind": "wavelet", "level": 3}, {"kind": "wavelet", "level": 5}]
    banded = run_groups.band_recipes(7, STEPS, span=(0, 100), bands=bands)
    for recipe, band in zip(banded, bands):
        hand = make_recipe(7, [_wavelet_as_analyse_inserts_it(band["level"])] + STEPS, span=(0, 100))
        assert recipe == hand and recipe_hash(recipe) == recipe_hash(hand)


def test_materialize_target_prepends_the_wavelet_step():
    fan = make_recipe(7, STEPS, span=(0, 100), fan_out={"kind": "bands", "targets": [
        {"kind": "wavelet", "level": 4}, {"label": "mid", "low_hz": 0.01, "high_hz": 0.1}]})
    first = run_groups.materialize_target(fan, 0)
    second = run_groups.materialize_target(fan, 1)
    assert [s["algorithm"] for s in first["steps"]] == ["wavelet_bands", "lowpass"]
    assert first["steps"][0]["params"]["level"] == 4
    assert [s["algorithm"] for s in second["steps"]] == ["bandpass", "lowpass"]


def test_the_surrogate_of_a_wavelet_band_run_is_decomposed_the_same_way():
    recipe = run_groups.band_recipes(7, STEPS, span=(0, 100), bands=[{"kind": "wavelet", "level": 2}])[0]
    null = run_groups.surrogate_recipe(recipe)
    assert [s["algorithm"] for s in null["steps"]][:2] == ["surrogate", "wavelet_bands"]
    assert null["steps"][1] == recipe["steps"][0]


# ── resolved against a recording: the label carries the level and its Hz ───

def test_a_wavelet_band_resolves_to_its_hz_range_at_the_recordings_rate():
    b = run_groups.resolve_band({"kind": "wavelet", "level": 4}, fs=1.0, n_samples=14400)
    assert (b["low_hz"], b["high_hz"]) == (0.03125, 0.0625)
    assert b["label"] == "db4 level 4 · 0.031–0.062 Hz"
    assert b["levels"] == 9
    b10 = run_groups.resolve_band({"kind": "wavelet", "level": 4}, fs=10.0, n_samples=144000)
    assert b10["label"] == "db4 level 4 · 0.31–0.62 Hz"


def test_a_wavelet_residual_resolves_to_everything_below_the_deepest_level():
    b = run_groups.resolve_band({"kind": "wavelet", "level": 0}, fs=1.0, n_samples=14400)
    assert (b["low_hz"], b["high_hz"]) == (0.0, 1.0 / 1024)
    assert b["label"] == "db4 residual · below 0.00098 Hz"


def test_a_named_wavelet_band_keeps_its_name_and_gains_its_range():
    b = run_groups.resolve_band({"kind": "wavelet", "level": 4, "label": "mid"}, fs=1.0, n_samples=14400)
    assert b["label"] == "mid · 0.031–0.062 Hz"


def test_resolving_a_bandpass_band_leaves_it_alone():
    band = {"kind": "bandpass", "label": "mid", "low_hz": 0.01, "high_hz": 0.1}
    assert run_groups.resolve_band(band, fs=1.0, n_samples=14400) == band


def test_a_wavelet_level_deeper_than_the_span_allows_is_refused_by_name():
    with pytest.raises(ValueError) as e:
        run_groups.resolve_band({"kind": "wavelet", "level": 12}, fs=1.0, n_samples=14400)
    msg = str(e.value)
    assert "level 12" in msg and "11" in msg, msg


def test_the_wavelet_levels_a_scope_can_offer():
    levels = run_groups.wavelet_levels(fs=1.0, n_samples=14400)
    assert [b["level"] for b in levels] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
    assert all(b["kind"] == "wavelet" and b["wavelet"] == "db4" and "Hz" in b["label"] for b in levels)
    assert levels[0]["label"] == "db4 level 1 · 0.25–0.5 Hz"


# ── a wavelet band run, end to end ──────────────────────────────────────────

def test_a_wavelet_band_runs_stored_recipe_is_the_hand_built_one():
    tmpdir = tempfile.mkdtemp(prefix="fixup_ac_")
    try:
        db_path = os.path.join(tmpdir, "t.sqlite")
        conn = init_db(db_path)
        npy = os.path.join(tmpdir, "CH0.npy")
        np.save(npy, np.random.default_rng(0).standard_normal(600).cumsum())
        rid = q.insert_recording(conn, "fake.mat", 0, 1.0, 600, 0, npy)
        conn.close()
        recipe = run_groups.band_recipes(rid, STEPS, span=(0, 600), bands=[{"kind": "wavelet", "level": 3}])[0]
        out = run_groups.run_paired_recipe(recipe, db_path=db_path, surrogate=True)
        conn = init_db(db_path)
        try:
            stored = R.load_recipe(conn, R.get_run(conn, out["run_id"])["config_id"])
            hand = make_recipe(rid, [_wavelet_as_analyse_inserts_it(3)] + STEPS, span=(0, 600))
            hand["surrogate"] = True
            assert recipe_hash(stored) == recipe_hash(hand)
            sur = R.load_recipe(conn, R.get_run(conn, out["surrogate_run_id"])["config_id"])
            assert [s["algorithm"] for s in sur["steps"]][:2] == ["surrogate", "wavelet_bands"]
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_the_recipe_layer_offers_exactly_the_blocks_wavelets():
    """`Working.recipes` restates the block's wavelet list so the recipe layer
    stays free of the adapters; the two must not drift apart."""
    from Adapters import preprocessing_wavelet_bands as WB
    from Working.recipes import WAVELET_BAND_WAVELETS

    assert list(WAVELET_BAND_WAVELETS) == list(WB.WAVELETS)


def test_resolving_a_resolved_wavelet_band_changes_nothing():
    once = run_groups.resolve_band({"kind": "wavelet", "level": 4}, fs=1.0, n_samples=14400)
    assert run_groups.resolve_band(once, fs=1.0, n_samples=14400) == once

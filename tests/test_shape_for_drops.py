"""ux-1019 (the researcher, 2026-10-19; site-fixes item 3 as refined): "line windows on trough third,
automatically, with a 'for drops' switch".

The Trace shape block carries a ``for_drops`` switch. ON lines every window up on the bottom of its drop, a third
of the way in (``trough``, 0.333); OFF keeps the centre at the middle (``centre``, 0.5). An align or anchor set on
the card (anything other than the block's own default) wins over the switch. ONE resolver in the core
(``Working.training.shape.resolve_alignment``) is read by the block (an Analyse run), by the B.2 recipe (the
trained model's identity) and by Models > Launch, so the same chain is cut the same way everywhere.
"""

import json

import pytest


def _sh():
    from Working.training import shape as sh
    return sh


def _validated(params):
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    return get_adapter("preprocessing.trace_shape").validate_params(params)


def test_the_block_offers_the_for_drops_switch_off_by_default():
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    p = {s.name: s for s in get_adapter("preprocessing.trace_shape").params}
    assert "for_drops" in p and p["for_drops"].type is bool and p["for_drops"].default is False
    assert "trough" in p["for_drops"].description and "0.333" in p["for_drops"].description


def test_a_non_drop_chain_resolves_to_centre_at_the_middle():
    r = _sh().resolve_alignment(_validated({}))
    assert (r["align"], r["anchor_frac"], r["for_drops"]) == ("centre", 0.5, False)
    assert "for drops: off" in r["from"]


def test_the_switch_on_resolves_to_the_trough_a_third_in():
    r = _sh().resolve_alignment(_validated({"for_drops": True}))
    assert (r["align"], r["anchor_frac"], r["for_drops"]) == ("trough", 0.333, True)
    assert "for drops: on" in r["from"] and "set on the card" in r["from"]


def test_an_explicit_align_or_anchor_wins_over_the_switch_and_says_so():
    sh = _sh()
    r = sh.resolve_alignment(_validated({"for_drops": True, "align": "peak"}))
    assert r["align"] == "peak" and r["anchor_frac"] == 0.333 and "align peak set on the card" in r["from"]
    r = sh.resolve_alignment(_validated({"for_drops": True, "anchor_frac": 0.25}))
    assert r["align"] == "trough" and r["anchor_frac"] == 0.25 and "anchor 0.25 set on the card" in r["from"]
    # forcing it OFF with explicit drop settings keeps them: the card's explicit values are what runs
    r = sh.resolve_alignment(_validated({"for_drops": False, "align": "trough", "anchor_frac": 0.333}))
    assert (r["align"], r["anchor_frac"]) == ("trough", 0.333)
    # grid re-cuts nothing: no anchor
    r = sh.resolve_alignment(_validated({"for_drops": True, "align": "grid"}))
    assert r["align"] == "grid" and r["anchor_frac"] is None


def _steps(shape_params):
    mapping = {"k": 2, "clusters": {"1": {"name": "a", "class": "interesting"},
                                    "2": {"name": "b", "class": "not_interesting"}}}
    return [{"stage": "preprocessing", "algorithm": "window_pool", "params": {"pool": "1"}},
            {"stage": "preprocessing", "algorithm": "trace_shape", "params": shape_params},
            {"stage": "catalogue", "algorithm": "shape_cluster", "params": {"k": 2, "mapping": json.dumps(mapping)}}]


def test_launch_and_the_recipe_read_the_same_resolution_and_the_model_identity_moves_with_the_switch():
    from Working.training import shape_forest as sf
    pool_ref = {"id": 1, "name": "p", "version": 1, "key": "k"}
    on = sf.make_recipe(pool_ref, {"id": 1, "name": "t", "steps": _steps({"for_drops": True})})
    off = sf.make_recipe(pool_ref, {"id": 1, "name": "t", "steps": _steps({})})
    assert on["shape"]["align"] == "trough" and on["shape"]["anchor_frac"] == pytest.approx(0.333)
    assert off["shape"]["align"] == "centre" and "anchor_frac" not in off["shape"]   # AG's recipes unchanged
    assert json.dumps(on, sort_keys=True) != json.dumps(off, sort_keys=True)
    shp, _clu, _m = sf.chain_settings(_steps({"for_drops": True}))
    launch = sf.launch_shape(shp)
    assert (launch["align"], launch["anchor_frac"], launch["for_drops"]) == ("trough", 0.333, True)
    assert "for drops: on" in launch["alignment_from"]


def test_the_block_run_cuts_at_the_resolved_alignment(monkeypatch):
    """An Analyse run goes through the block; it must hand trace_shapes the same (align, anchor) Launch shows."""
    import Adapters.preprocessing_trace_shape as tsh
    sh = _sh()
    seen = {}

    class _Stop(Exception):
        pass

    def fake(conn, frame, **kw):
        seen.update(kw)
        raise _Stop()

    monkeypatch.setattr(sh, "pool_frame", lambda v: v)
    monkeypatch.setattr(sh, "trace_shapes", fake)
    for params, want in (({"for_drops": True}, ("trough", 0.333)), ({}, ("centre", 0.5)),
                         ({"for_drops": True, "align": "peak", "anchor_frac": 0.25}, ("peak", 0.25))):
        seen.clear()
        with pytest.raises(_Stop):
            tsh._run(None, None, 1.0, value=object(), conn=object(), **_validated(params))
        assert (seen["align"], seen["anchor_frac"]) == want
        r = sh.resolve_alignment(_validated(params))
        assert (r["align"], r["anchor_frac"]) == want

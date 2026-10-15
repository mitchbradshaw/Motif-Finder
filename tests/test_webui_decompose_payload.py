"""
test_webui_decompose_payload.py
================================
fixup-AO: `preprocessing.decompose` (baseline / noise / signal) reaches the
block page through `webui/server/serialize.py::to_payload` as the same
`layers` payload convention the wavelet block uses, so `SignalView` draws it
with its existing layer rows -- plus the parameter a click on a layer sets
(`layer_param`, each layer's `param_value`), and its own `split` description
instead of the wavelet block's `decomposition`.

No FastAPI needed; runs under the conda pytest.
"""

import json
import os
import sys

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from server.serialize import _clean, to_payload  # noqa: E402

CLIENT = os.path.join(PROJECT_ROOT, "webui", "client", "src")


def _run(x, fs=1.0, **params):
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    spec = get_adapter("preprocessing.decompose")
    return spec.run(x, np.arange(len(x)) / fs, fs, **spec.validate_params(params))


def test_the_three_layers_ship_on_absolute_seconds_in_mv_with_the_click_parameter():
    x = -0.447 + 1e-3 * np.random.default_rng(0).standard_normal(8000).cumsum()      # volts
    res = _run(x, fs=1.0, pass_on="baseline")
    p = to_payload("signal", res.value, res.meta, {"fs": 1.0, "span_start": 500, "px": 400, "units": "V"})
    assert p["unit"] == "mV"
    assert [L["name"] for L in p["layers"]] == ["noise", "signal", "baseline"]
    assert [L["chosen"] for L in p["layers"]] == [False, False, True]
    assert p["layer_param"] == "pass_on"
    assert [L["param_value"] for L in p["layers"]] == ["noise", "signal", "baseline"]
    base = p["layers"][2]["envelope"]
    assert base["t"][0] >= 500.0, "absolute seconds, span offset added"
    assert min(v for v in base["v"] if v is not None) == min(res.value.x) * 1000.0
    assert p["split"]["pass_on"] == "baseline" and p["split"]["noise_cut_auto"] is True
    assert "decomposition" not in p, "the wavelet block's description is not borrowed with empty fields"


def test_the_layers_survive_the_meta_sidecar_of_a_step_cache_hit():
    x = np.random.default_rng(1).standard_normal(200_000).cumsum()
    res = _run(x)
    side = json.loads(json.dumps(_clean(res.meta)))
    p = to_payload("signal", res.value, side, {"fs": 1.0, "span_start": 0, "px": 800})
    assert [L["name"] for L in p["layers"]] == ["noise", "signal", "baseline"]
    assert "layers_note" not in p and p["layer_param"] == "pass_on"


def test_a_click_on_a_layer_row_sets_the_blocks_parameter():
    """The page wiring: a layer row is clickable when the payload names the
    parameter it sets, and the block page hands the click to the same setParam
    the Parameters panel uses (so the step goes stale and re-runs like any edit)."""
    with open(os.path.join(CLIENT, "analyse", "views", "SignalView.tsx"), encoding="utf-8") as f:
        sv = f.read()
    with open(os.path.join(CLIENT, "analyse", "views", "registry.tsx"), encoding="utf-8") as f:
        reg = f.read()
    assert "onPick" in sv and 'data-pickable' in sv
    assert "layer_param" in reg and "q.setParam(" in reg.split("function DecompositionLayers", 1)[1].split("/* ----", 1)[0]

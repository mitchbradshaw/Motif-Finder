"""
test_block_standard.py
========================
Every registered adapter obeys `docs/BLOCK_INTEGRATION.md` — the standard a
researcher follows to add an algorithm. These are the contract's teeth: a
block that slips past them is a block the web UI will mis-file, mis-cost or
fail to draw.

* every block declares exactly one `input_kind` (no `None` — the root signal
  is `'signal'`, the same string the chain validator uses);
* every block carries its own `category` (the insert-modal tab) and
  `page_name` (what the concept pages call it) on the spec, so the bridge
  keeps no side table of names; an unknown category is refused loudly;
* a block that is known not to run declares `known_broken` with the reason;
* every block that is not O(n)-cheap declares a cost — an `estimate` or a
  `max_span_samples` ceiling;
* the bridge's catalog reads all of this off the spec and nothing else.

Runnable standalone:  python tests/test_block_standard.py
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.base import CATEGORIES, AdapterResult, AdapterSpec  # noqa: E402
from Adapters.registry import discover_adapters, get_adapter, list_adapters  # noqa: E402

discover_adapters()

# Blocks whose cost is not O(n)-trivial: each must declare an `estimate` (it
# may answer None = uncalibrated) or a `max_span_samples` ceiling. The list
# is the standard's "Cost" section made checkable.
COSTED = (
    "detection.matrix_profile", "preprocessing.window_matrix", "detection.dehshibi_spikes",
    "catalogue.cluster", "catalogue.classifier",
    "catalogue.gramian_gasf", "catalogue.gramian_gadf", "catalogue.gramian_recurrence",
    "catalogue.gramian_fusion", "detection.wavelet_scattering",
    # stage-3 prompt 01 blocks that are not O(n)-cheap, and Pelt (worst-case O(n²))
    "preprocessing.wavelet_transform", "catalogue.window_images", "catalogue.cnn_score", "detection.rupture",
)


def _stub(**overrides):
    kwargs = dict(
        name="test.stub", display_name="Stub", stage="preprocessing", params=[],
        run=lambda x, t, fs, **params: AdapterResult(output_kind="signal"),
        output_kind="signal", input_kind="signal", category="preprocess", page_name="Stub",
    )
    kwargs.update(overrides)
    return AdapterSpec(**kwargs)


# ── the spec carries category and page_name ─────────────────────────────────

def test_spec_has_category_and_page_name_fields():
    s = _stub()
    assert s.category == "preprocess"
    assert s.page_name == "Stub"


def test_categories_are_the_six_modal_tabs():
    assert set(CATEGORIES) == {"preprocess", "encode", "detect", "cluster", "model", "control"}


def test_unknown_category_is_refused_loudly():
    with pytest.raises(ValueError, match="category"):
        _stub(category="misc")


def test_page_name_defaults_to_display_name():
    s = _stub(page_name=None)
    assert s.page_name == "Stub"


def test_known_broken_is_none_by_default_and_carries_a_reason():
    assert _stub().known_broken is None
    assert _stub(known_broken="needs kymatio").known_broken == "needs kymatio"


# ── every registered adapter ────────────────────────────────────────────────

@pytest.mark.parametrize("spec", list_adapters(), ids=lambda s: s.name)
def test_every_adapter_declares_an_input_kind(spec):
    assert spec.input_kind is not None, f"{spec.name}: input_kind=None is not allowed; the root signal is 'signal'"


@pytest.mark.parametrize("spec", list_adapters(), ids=lambda s: s.name)
def test_every_adapter_declares_a_category_and_page_name(spec):
    assert spec.category in CATEGORIES, spec.name
    assert isinstance(spec.page_name, str) and spec.page_name.strip(), spec.name


@pytest.mark.parametrize("name", COSTED)
def test_costed_blocks_declare_an_estimate_or_a_ceiling(name):
    spec = get_adapter(name)
    assert spec.estimate is not None or spec.max_span_samples is not None, (
        f"{name} is not O(n)-cheap and declares neither `estimate` nor `max_span_samples`")


def test_wavelet_scattering_is_either_runnable_or_marked_broken_with_a_reason():
    import numpy as np
    spec = get_adapter("detection.wavelet_scattering")
    x = np.random.default_rng(0).standard_normal(4096)
    try:
        spec.run(x, np.arange(4096.0), 1.0, **spec.validate_params({}))
    except ImportError as e:
        assert spec.known_broken, f"wavelet_scattering fails to run ({e}) but is not marked known_broken"
        assert "sph_harm" in spec.known_broken or "kymatio" in spec.known_broken
    else:
        assert spec.known_broken is None, "wavelet_scattering runs; the known_broken flag is stale"


# ── the bridge reads the spec, nothing else ─────────────────────────────────

def test_bridge_catalog_reads_category_and_page_name_off_the_spec():
    from server import chain as chain_mod
    for attr in ("_CATEGORY", "_PAGE_NAME", "_KNOWN_BROKEN"):
        assert not hasattr(chain_mod, attr), f"server/chain.py still carries the {attr} side table"
    cards = {c["name"]: c for c in chain_mod.catalog()}
    for spec in list_adapters():
        card = cards[spec.name]
        assert card["category"] == spec.category
        assert card["page_name"] == spec.page_name
        assert card["known_broken"] == spec.known_broken
        assert card["input_kind"] == spec.input_kind


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

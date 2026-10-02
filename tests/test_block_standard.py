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
    # fixup-d: the feature blocks and the inversion, each with a calibrated model
    "interrogation.event_shape", "interrogation.intervals", "preprocessing.invert",
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


# ── the drawing standard (fixup-h) ──────────────────────────────────────────
# "The OUTPUT type decides what kind of picture you get. The INPUT type decides
# what one thing is in that picture, and whether there is a before/after to
# show." Seven type views and twelve modifiers, so every block - including one
# nobody has written yet - is drawn from its type signature alone. The table
# lives in `webui/server/views.py`, rides on every catalog card, and the
# client's registry (`analyse/views/registry.tsx`) must name a component for
# every key of it. The acceptance criterion is a caption: no block may fall
# through to "this signature has no bespoke process view yet".

CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
REGISTRY_TSX = os.path.join(CLIENT_SRC, "analyse", "views", "registry.tsx")
BLOCK_PAGE_TSX = os.path.join(CLIENT_SRC, "analyse", "BlockPage.tsx")
SEVEN = {"signal", "scores", "spanset", "encoding", "windowset", "grouping", "model"}


def _views():
    from server import views
    return views


def _registry_keys(const_name):
    """The keys of `export const <const_name> ... = { ... }` in the client's registry, one entry per line."""
    import re
    with open(REGISTRY_TSX, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"export const %s\b[^=]*=\s*\{(.*?)\n\}" % const_name, src, re.S)
    assert m, f"{REGISTRY_TSX} declares no `export const {const_name} = {{ ... }}`"
    return {k for k in re.findall(r"^\s*'?([a-z]+(?:->[a-z]+)?)'?\s*:", m.group(1), re.M)}


def test_there_are_seven_type_views_one_per_interchange_type():
    assert set(_views().VIEWS) == SEVEN


def test_there_are_twelve_modifiers_and_each_names_two_interchange_types():
    mods = _views().MODIFIERS
    assert len(mods) == 12, sorted(mods)
    for key in mods:
        a, b = key.split("->")
        assert a in SEVEN and b in SEVEN, key


@pytest.mark.parametrize("spec", list_adapters(), ids=lambda s: s.name)
def test_every_adapter_resolves_to_a_type_view_and_a_modifier(spec):
    views = _views()
    r = views.resolve(spec)
    assert r["view"] == spec.output_kind and r["view"] in views.VIEWS, (
        f"{spec.name}: no type view for output {spec.output_kind!r}")
    assert r["modifier"] in views.MODIFIERS, (
        f"{spec.name}: the conversion {spec.input_kind}->{spec.output_kind} has no modifier row; "
        f"add one to webui/server/views.py and to analyse/views/registry.tsx")


def test_the_twelve_modifiers_are_exactly_the_registered_conversions():
    """No block without a modifier, and no modifier nobody uses."""
    have = {f"{s.input_kind}->{s.output_kind}" for s in list_adapters()}
    assert set(_views().MODIFIERS) == have


def test_a_conversion_nobody_has_written_yet_still_gets_its_type_view():
    """A future `scores -> scores` block is drawn by the Scores view, with no modifier and no error."""
    r = _views().resolve_kinds("scores", "scores")
    assert r == {"view": "scores", "modifier": None}
    with pytest.raises(ValueError, match="interchange type"):
        _views().resolve_kinds("signal", "features")


def test_the_catalog_card_carries_the_view_and_the_modifier():
    from server import chain as chain_mod
    cards = {c["name"]: c for c in chain_mod.catalog()}
    for spec in list_adapters():
        assert cards[spec.name]["view"] == spec.output_kind
        assert cards[spec.name]["modifier"] == f"{spec.input_kind}->{spec.output_kind}"


def test_the_client_registry_has_a_component_for_every_view_and_modifier():
    views = _views()
    assert _registry_keys("VIEWS") == set(views.VIEWS)
    assert _registry_keys("MODIFIERS") == set(views.MODIFIERS)


def test_no_block_falls_through_to_a_generic_process_view():
    """The caption is the acceptance criterion: when it cannot appear, the standard holds."""
    hits = []
    for root, _dirs, files in os.walk(CLIENT_SRC):
        for fn in files:
            if fn.endswith((".ts", ".tsx")):
                with open(os.path.join(root, fn), encoding="utf-8") as f:
                    if "no bespoke process view yet" in f.read():
                        hits.append(os.path.relpath(os.path.join(root, fn), CLIENT_SRC))
    assert not hits, f"the generic-view caption is still in {hits}"
    with open(BLOCK_PAGE_TSX, encoding="utf-8") as f:
        page = f.read()
    assert "GenericProcess" not in page, "BlockPage.tsx still carries the generic process view"


def test_the_block_page_picks_its_view_by_signature_never_by_block_name():
    """Three bespoke views used to be selected by `name === 'detection.threshold'` and its siblings, so a new
    block of the same signature got none of them."""
    import re
    with open(BLOCK_PAGE_TSX, encoding="utf-8") as f:
        page = f.read()
    named = re.findall(r"name\s*===\s*'[a-z_]+\.[a-z_0-9]+'", page)
    assert not named, f"BlockPage.tsx dispatches on block names: {named}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

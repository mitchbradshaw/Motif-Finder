"""
test_webui_w2f_ui.py
=====================
w2-f: the client pins for wave 2's UI. They read the client's sources and the
smoke manifests, so they run anywhere (no FastAPI, no node):

* every wave-2 block has a glyph of its own;
* `spanset->windowset` draws the windows around their events with the anchor
  marked (its own component, not the generic WindowSet view);
* the Library's omission reasons include the three wave-2 ones;
* the grouping editor offers the registered methods (no hard-coded Ward
  select), sends the fit summary back on save, offers the refusal's cheaper
  settings, and gives HDBSCAN its own epsilon rather than the tree cut;
* the Family page draws coherence beside its noise null;
* the smoke manifests carry a state per wave-2 template and the Library's
  HDBSCAN state.

The server halves are in `test_webui_serialize.py` (conda) and
`test_webui_library.py` (FastAPI: `webui/.venv`).
"""

import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
SMOKE = os.path.join(PROJECT_ROOT, "webui", "smoke_pages")


def _src(*parts):
    with open(os.path.join(CLIENT_SRC, *parts), encoding="utf-8") as f:
        return f.read()


# tq-grouping: the grouping editor is split across these modules (the page, its draft model, the job hook, the tree
# panel, section 3's parameters); a pin on "the editor" reads all of them
GROUPING_EDITOR = ("GroupingPage.tsx", "groupingDraft.ts", "useGroupingJob.ts", "TreePanel.tsx", "GroupingParams.tsx")


def _grouping_editor_src():
    return "\n".join(_src("library", f) for f in GROUPING_EDITOR)


def _smoke(name):
    with open(os.path.join(SMOKE, name), encoding="utf-8") as f:
        return json.load(f)


WAVE2_BLOCKS = ("catalogue.event_windows", "catalogue.minirocket", "catalogue.snippets")


def test_every_wave2_block_has_a_glyph_of_its_own():
    src = _src("analyse", "glyphs.tsx")
    by_name = src[src.index("const BY_NAME"):src.index("const BY_SIG")]
    for name in WAVE2_BLOCKS:
        assert f"'{name}'" in by_name, f"{name} has no glyph in BY_NAME"


def test_spans_to_windows_draws_the_windows_around_their_events_with_the_anchor():
    src = _src("analyse", "views", "registry.tsx")
    row = re.search(r"'spanset->windowset':\s*([A-Za-z]+)", src)
    assert row and row.group(1) != "WindowSetProcess", "spanset->windowset still draws the generic WindowSet"
    view = _src("analyse", "views", "WindowSetView.tsx")
    assert "data-testid=\"window-anchor\"" in view, "the anchor is marked inside each window"
    assert "data-testid=\"event-windows\"" in view
    assert "omitted" in view, "the events left out are drawn, not hidden"


def test_the_three_wave2_omission_reasons_have_plain_labels():
    src = _src("library", "chrome.tsx")
    table = src[src.index("export const OMIT_REASON_LABEL"):]
    table = table[:table.index("}")]
    for reason in ("not_in_a_dense_family", "infinite_values", "missing_values"):
        assert reason in table, f"{reason} has no plain label"


def test_the_grouping_editor_offers_the_registered_methods_not_a_hard_coded_ward():
    src = _grouping_editor_src()
    assert "value=\"ward\" onChange={() => undefined}" not in src, "the linkage select is still a fixed Ward"
    assert "methods" in src and "testid=\"param-method\"" in src
    # the read seam maps the editor payload field by field: a field it does not map never reaches the page
    assert "methods: e.methods" in _src("api", "library.ts"), "getGroupingEditor drops the methods list"
    assert "no-tree-line" in src, "a method with no tree says why there is no histogram"
    assert "fit_summary" in src, "the job's fitSummary goes back on save"
    assert "cheaper" in src and "regroup-refused" in src, "the 422 offers its cheaper settings"
    assert "epsilon" in src, "HDBSCAN's epsilon is its own input"
    assert "noise-badge" in src or "NoiseBadge" in src, "the preview flags a family no better than noise"


def test_the_family_page_draws_coherence_beside_its_null():
    src = _src("library", "FamilyPage.tsx")
    assert "family-coherence" in src
    assert ("How much the members are copies of one shape: 0 = all the same shape, 1 = no shared shape. "
            "Ignores amplitude.") in src
    assert "no more coherent than noise" in src
    assert "null_p05" in src and "null_median" in src
    assert "coherence-error" in src, "a failed coherence is a red card"
    chrome = _src("library", "chrome.tsx")
    assert "export function NoiseBadge" in chrome, "one badge for the atlas, the family page and the editor"
    assert "NoiseBadge" in _src("library", "AtlasPage.tsx")
    assert "NoiseBadge" in src


def test_smoke_carries_a_state_per_wave2_block_and_the_hdbscan_editor():
    """fix 1 (critic 8): only SEEDED templates are imported by name. minirocket_manual_labels is seeded;
    recording_snippets and event_clusters are experimental, so their blocks get hand-built chains."""
    states = _smoke("zz_analyse_run.json")
    text = json.dumps(states)
    assert "template-minirocket_manual_labels" in text
    for unseeded in ("recording_snippets", "event_clusters"):
        assert f"template-{unseeded}" not in text, f"{unseeded} is not seeded: a state cannot import it"
    assert "modal-card-catalogue.event_windows" in text, "Event windows has a block-level state"
    assert "modal-card-catalogue.snippets" in text, "Snippets has a block-level state"
    ew = [s for s in states if "event-windows" in json.dumps(s.get("expect", []))]
    assert any(s["page"] == "analyse.block" for s in ew), "the Event windows block page is asserted"
    sn = next(s for s in states if s["state"].startswith("w2-snippets") and s["page"] == "analyse.chain")
    zooms = sum(1 for a in sn["actions"] if a.get("click") == '[data-testid="zoom-out"]')
    assert zooms == 5, "five zoom-outs: about 15 h, at least 12 one-hour pieces, seconds of work"
    lib = _smoke("library.json")
    assert "hdbscan" in json.dumps(lib) and "no-tree-line" in json.dumps(lib)
    ward = next(s for s in lib if s["state"] == "w2-method-ward-unchanged")
    assert {"select": ['[data-testid="param-method"]', "ward"]} in ward["actions"], (
        "the Ward state follows the HDBSCAN one on the same hash: it must select Ward back")


def test_fix1_coherence_reads_the_cores_verdict_with_its_margin_and_caveat():
    src = _src("library", "FamilyPage.tsx")
    assert "v >= c.null_p05" not in src, "the verdict is the core's beyond_noise, not a bare comparison"
    assert "beyond_noise === false" in src and "no null" in src
    assert "null_margin" in src and "coherence-caveat" in src and "smooth_caveat" in src
    assert "quarter of the length" not in src and "misaligned_fraction" in src
    api = _src("api.ts")
    coh = api[api.index("export interface LibFamilyCoherence"):]
    coh = coh[:coh.index("}")]
    for k in ("beyond_noise", "null_margin", "null_kind", "smooth_caveat", "misaligned_fraction"):
        assert k in coh, k
    flags = api[api.index("export interface LibFamilyFlags"):]
    flags = flags[:flags.index("}")]
    assert "ratio" in flags and "margin" in flags and "null_max_separation" not in flags


def test_fix1_badges_seeds_and_the_refusal_card():
    chrome = _src("library", "chrome.tsx")
    assert "verdict not saved" in chrome, "a method with a null but no saved flags says so"
    gp = _grouping_editor_src()
    assert "parseParamsText(g.params, " in gp, "string params are parsed against the method's declared str params"
    assert "clearRefusal" in gp, "the refusal card goes when the settings change"
    view = _src("analyse", "views", "WindowSetView.tsx")
    assert "event-windows-note" in view and "event-windowless" in view
    gv = _src("analyse", "views", "GroupingView.tsx")
    assert "exemplar_note" in gv


def test_families_have_glyphs_and_views_of_their_own():
    """w2-f families: both W2-E blocks are drawn — the family table (badge per family, coherence beside its null,
    the block's own verdict), and Event families' events coloured by family with the unplaced ones' reasons."""
    glyphs = _src("analyse", "glyphs.tsx")
    by_name = glyphs[glyphs.index("const BY_NAME"):glyphs.index("const BY_SIG")]
    for name in ("catalogue.shape_families", "interrogation.event_families"):
        assert f"'{name}'" in by_name, f"{name} has no glyph"
    reg = _src("analyse", "views", "registry.tsx")
    assert "FamilyTable" in reg and "EventFamiliesView" in reg
    gv = _src("analyse", "views", "GroupingView.tsx")
    for tid in ("family-table", "family-badge-", "family-null-not-trusted", "family-coherence-"):
        assert tid in gv, tid
    assert "svd_entropy_beyond_noise" in gv and "null_caveat" in gv
    assert "svd_entropy_norm >=" not in gv and "svd_entropy_norm <" not in gv, "the verdict is the block's"
    sv = _src("analyse", "views", "SpanSetView.tsx")
    for tid in ("event-families", "event-family-none", "event-family-exemplar", "event-families-none"):
        assert tid in sv, tid
    assert "~noise_like" in sv and "~untested" in sv, "the marked group keys read as marked"


def test_family_smoke_states_are_block_level_chains():
    states = _smoke("zz_analyse_run.json")
    text = json.dumps(states)
    assert "template-event_families" not in text, "event_families is experimental: not seeded"
    assert "modal-card-catalogue.shape_families" in text and "modal-card-interrogation.event_families" in text
    block = [s for s in states if s["page"] == "analyse.block" and s["state"].startswith("w2-")]
    assert any("family-table" in json.dumps(s["expect"]) for s in block)
    assert any("event-families" in json.dumps(s["expect"]) for s in block)

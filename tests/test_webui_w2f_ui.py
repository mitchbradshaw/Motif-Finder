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
    src = _src("library", "GroupingPage.tsx")
    assert "value=\"ward\" onChange={() => undefined}" not in src, "the linkage select is still a fixed Ward"
    assert "methods" in src and "testid=\"param-method\"" in src
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


def test_smoke_carries_a_state_per_wave2_template_and_the_hdbscan_editor():
    states = _smoke("zz_analyse_run.json")
    text = json.dumps(states)
    for template in ("minirocket_manual_labels", "recording_snippets"):
        assert f"template-{template}" in text, f"no smoke state runs {template}"
    assert "modal-card-catalogue.event_windows" in text, "Event windows has a block-level state"
    ew = [s for s in states if "event-windows" in json.dumps(s.get("expect", []))]
    assert any(s["page"] == "analyse.block" for s in ew), "the Event windows block page is asserted"
    lib = json.dumps(_smoke("library.json"))
    assert "hdbscan" in lib and "no-tree-line" in lib

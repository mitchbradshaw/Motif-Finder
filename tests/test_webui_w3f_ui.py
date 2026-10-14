"""
test_webui_w3f_ui.py
====================
W3-F: the client pins for wave 3's UI. They read the client's sources and the smoke manifests, so they run
anywhere (no FastAPI, no node). The server halves are `test_webui_run_cancel.py`, `test_webui_run_routing.py`
and `test_webui_w3f_payloads.py`.

* every wave-3 block has a glyph of its own;
* the three new drawings are chosen off the payload (`curves`, `cycle_stack`, `row_axis`), never off a block's
  name, and live in components beside `DetectorFunnel.tsx`;
* undefined MSE scales are gaps: the curve path is broken at a null, never joined across it;
* the run panel shows the in-step fraction (`step_progress`), and the stream listens for it — and for
  `null_progress`, which it never subscribed to;
* the estimate prints the estimator's own words and "calibrating", not a blanket "uncalibrated";
* the insert modal reads a side input's `required`;
* the families' table and the Family page put σ² first; the families table shows `passed_by`;
* MPdist: an edge with no "within" prints "—" in a neutral colour, its footing as the tooltip;
* the smoke manifest carries a state per wave-3 drawing and a cancel state.
"""
import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
SMOKE = os.path.join(PROJECT_ROOT, "webui", "smoke_pages", "zz_analyse_run.json")


def _src(*parts):
    with open(os.path.join(CLIENT_SRC, *parts), encoding="utf-8") as f:
        return f.read()


WAVE3_BLOCKS = ("catalogue.multiscale_entropy", "interrogation.cycle_shapes", "detection.pan_matrix_profile")


def test_every_wave3_block_has_a_glyph_of_its_own():
    src = _src("analyse", "glyphs.tsx")
    by_name = src[src.index("const BY_NAME"):src.index("const BY_SIG")]
    for name in WAVE3_BLOCKS:
        assert f"'{name}'" in by_name, f"{name} has no glyph in BY_NAME"


def test_the_three_drawings_are_chosen_off_the_payload_never_the_block_name():
    reg = _src("analyse", "views", "registry.tsx")
    for name in WAVE3_BLOCKS:
        assert name not in reg and name.split(".")[1] not in reg, f"registry.tsx names {name}"
    assert "curvesOf(" in reg and "MseCurves" in reg
    assert "cycleStackOf(" in reg and "CycleStack" in reg
    assert os.path.isfile(os.path.join(CLIENT_SRC, "analyse", "MseCurves.tsx"))
    assert os.path.isfile(os.path.join(CLIENT_SRC, "analyse", "CycleStack.tsx"))
    enc = _src("analyse", "views", "EncodingView.tsx")
    assert "row_axis" in enc and 'data-testid="row-axis"' in enc
    assert "row_verdict" in reg or "row_verdict" in enc


def test_undefined_mse_scales_are_gaps_never_joined():
    mse = _src("analyse", "MseCurves.tsx")
    assert "polylinePath" in mse, "the curve is drawn with the shared path that breaks at a null"
    assert 'data-testid="mse-curves"' in mse and 'data-testid="mse-collapsed"' in mse
    assert "log" in mse.lower(), "scale on a log axis"
    prim = _src("charts", "scale.ts")
    assert re.search(r"null", prim), "polylinePath breaks the line at a null"


def test_the_cycle_stack_draws_before_and_after_with_the_groups_and_the_change_points():
    cs = _src("analyse", "CycleStack.tsx")
    for tid in ("cycle-stack-before", "cycle-stack-after", "cycle-group-strip", "cycle-change-point",
                "cycle-exemplars", "cycle-verdicts"):
        assert f"'{tid}'" in cs or f'"{tid}"' in cs, f"{tid} missing"
    assert "<ScaleBar" in cs, "each medoid cycle on its own y, with a scale bar (drawing rule 4)"
    assert "beyond_noise" in cs and "whole_verdict" in cs, "the verdict is read off the payload"
    assert "null_p05" not in cs and "< 0.9" not in cs, "no verdict re-derived from a score and a null"


def test_the_run_panel_follows_a_step_from_inside():
    api = _src("api.ts")
    listen = api[api.index("export function subscribeRun"):]
    listen = listen[:listen.index("es.onerror")]
    assert "'step_progress'" in listen and "'null_progress'" in listen
    store = _src("analyse", "store.ts")
    assert "case 'step_progress'" in store
    page = _src("analyse", "ChainPage.tsx")
    assert "the core reports no within-step fraction" not in page
    assert 'data-testid={`step-fraction-' in page
    assert "cancel is checked between steps, never mid-step" not in page


def test_the_estimate_prints_the_estimators_words_and_calibrating():
    page = _src("analyse", "ChainPage.tsx")
    assert "calibrating" in page and "estimate?.errors" in page
    api = _src("api.ts")
    assert "calibrating?: number[]" in api and "errors?: Record<string, string>" in api


def test_the_insert_modal_reads_whether_a_side_input_is_required():
    modal = _src("analyse", "InsertStageModal.tsx")
    assert "required" in modal
    api = _src("api.ts")
    assert re.search(r"side_inputs: \{ name: string; type_kind: TypeKind; sources: string\[\]; required\?: boolean", api)


def test_sigma_squared_leads_on_the_family_page_and_the_families_table():
    fp = _src("library", "FamilyPage.tsx")
    body = fp[fp.index("export function FamilyCoherence"):]
    assert "variants" in body and 'data-testid="coherence-squared"' in body
    assert body.index('data-testid="coherence-squared"') < body.index('data-testid="coherence-value"')
    assert 'data-testid="coherence-passed-by"' in body and 'data-testid="coherence-context"' in body
    gv = _src("analyse", "views", "GroupingView.tsx")
    table = gv[gv.index("export function FamilyTable"):]
    assert table.index("σ²") < table.index("eq. 17")
    assert "passed_by" in gv and 'data-testid={`family-passed-by-' in gv


def test_an_mpdist_edge_with_no_within_prints_a_dash_in_a_neutral_colour():
    edges = _src("library", "Edges.tsx")
    assert "within === null" in edges and "footing" in edges
    assert "'—'" in edges or '"—"' in edges or ">—<" in edges
    assert "k could not be compared" in edges and "run Add N matches again" in edges


def test_the_add_matches_result_shows_the_refusals_as_a_neutral_line():
    add = _src("discovery", "AddMatches.tsx")
    assert "refusalSummary" in add and "edgesRefused" in add, "the refusals do not reach the Add N matches result"
    assert 'data-testid="matches-refused"' in add
    api = _src("api.ts")
    assert "refusalSummary" in api and "edgesRefused" in api


def _states():
    with open(SMOKE, encoding="utf-8") as f:
        return {s["state"]: s for s in json.load(f)}


def test_the_smoke_manifest_has_a_state_per_wave3_drawing_and_a_cancel_state():
    st = _states()
    names = " ".join(st)
    for want in ("w3-mse", "w3-cycle", "w3-pan", "w3-cancel"):
        assert want in names, f"no {want} state"
    cancel = next(s for k, s in st.items() if "w3-cancel" in k)
    flat = json.dumps(cancel)
    assert "cancel-button" in flat and "cancelled" in flat
    for k, s in st.items():
        if k.startswith("w3-") and s["hash"] == "analyse/chain":
            assert "template-motif_lengths" not in json.dumps(s) and "template-complexity_fingerprint" not in json.dumps(s) \
                and "template-chain_cycles" not in json.dumps(s), \
                f"{k} clicks a wave-3 template, which is clickable only once seeded"


# ── W3-F fix round 1 ────────────────────────────────────────────────────────────

def test_the_cancel_state_runs_a_long_finely_grained_step():
    """Critic finding 2: 2 windows of 6 h made the step 1.35 s long and the cancel a race. 3 h windows over a span
    zoomed out to ~389 h (~130 windows, measured 14.9 s, a fraction every ~0.1 s) keep `step-fraction-*` alive.
    (Hour windows, the first try, measured 3.3 s for 259 windows: too short.)"""
    st = _states()
    cancel = next(s for k, s in st.items() if "w3-cancel" in k)
    flat = json.dumps(cancel)
    assert '"21600"' not in flat and '"10800"' in flat
    zooms = sum(1 for a in cancel["actions"] if a.get("click") == "[data-testid=\"zoom-out\"]")
    assert zooms >= 10, f"only {zooms} zoom-outs: 2 h x 1.5^{zooms} is too short a span"


def test_the_pan_rows_show_the_cleared_band_and_never_call_the_suggestion_the_events_length():
    enc = _src("analyse", "views", "EncodingView.tsx")
    assert "cleared_s" in enc and 'data-testid="row-verdict-band"' in enc
    assert "approximate_note" not in enc, "W3-C removed scrump: nothing approximate to show"
    assert "caveat" in enc


def test_the_runtime_checks_the_block_cost_calibration_path_at_start():
    """Critic finding 7: redirected, but not in `_core_paths`, so the refuse-if-outside check missed it."""
    with open(os.path.join(PROJECT_ROOT, "webui", "server", "runtime.py"), encoding="utf-8") as f:
        src = f.read()
    core = src[src.index("def _core_paths"):]
    core = core[:core.index("\n    def ", 10)]
    assert "block_cost.CALIBRATION_PATH" in core


def test_the_pan_view_never_sells_the_suggestion():
    """Re-critique finding 3: "· suggested C (strongest of the band)" and a "suggested" cell still sold one length.
    The view says "strongest at C s — not an event length", on the same line as the number, and nowhere "suggested"
    or "use this window"."""
    enc = _src("analyse", "views", "EncodingView.tsx")
    view = enc[enc.index("function RowAxisLabels"):enc.index("/** The settings-tier evidence")]
    words = re.sub(r"suggested_(window_s|row)|row-suggested|const sug\b", "", view)
    assert "suggested" not in words.lower(), "the pan view still says 'suggested'"
    assert "strongest at" in view and "not an event length" in view
    line = view[view.index('data-testid="row-verdict-headline"'):]
    line = line[:line.index("</span>")]
    assert "not an event length" in line, "the warning is not on the same line as the number"
    assert "use this window" not in enc.lower()

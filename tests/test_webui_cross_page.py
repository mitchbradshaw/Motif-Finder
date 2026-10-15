"""
test_webui_cross_page.py
========================
fixup-AQ: Explore › Cross-channel must plot its rows, pick its window and tell the truth about its bins.
The researcher's screenshot (2026-10-13) showed six near-flat rows under a "shared gain · 20.74 mV per row" note
while every row printed a 5-10 mV range (X1), a window picker that changed nothing (X2), lag 0.0 s / r -0.97 /
"independent" on every pair (X3, pinned in test_cross_channel_window.py and test_webui_cross_window.py), a
lag-aligned mode that could not move anything (X4), a greyed hand-off card with no reason (X5) and a padlock on
the reference row that said nothing (X6).

The behavioural half RUNS `webui/client/src/explore/crossModel.ts` under Node (which strips TypeScript types
natively), as test_webui_plot_domain.py does for charts/domain.ts; it skips when `node` is not on PATH. The
source-level half always runs.

    python -m pytest tests/test_webui_cross_page.py
"""
import io
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
MODEL_TS = os.path.join(CLIENT_SRC, "explore", "crossModel.ts")
SMOKE = os.path.join(PROJECT_ROOT, "webui", "smoke_pages", "zzzzzzzzzzzz_aq_cross_channel.json")


def _read(*parts):
    path = os.path.join(CLIENT_SRC, *parts)
    assert os.path.isfile(path), f"{os.path.relpath(path, PROJECT_ROOT)} is missing"
    return io.open(path, encoding="utf-8").read()


def _node(expr: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH; the page's model is exercised by webui/smoke.py instead")
    assert os.path.isfile(MODEL_TS), "webui/client/src/explore/crossModel.ts does not exist"
    url = "file:///" + MODEL_TS.replace("\\", "/").lstrip("/")
    script = f"import * as M from {json.dumps(url)};\nconst out = ({expr});\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ── X1: the shared gain is the largest drawn row's range ───────────────────────────────────────────────────

ROWS = "[[-1532.0, -1530.1, -1526.64, -1531.9, -1531.95], [-402.0, -397.0, -401.9, -401.95], [-88.1, -78.0, -88.0, -88.05, null]]"


def test_the_shared_gain_equals_the_largest_per_row_range_of_the_drawn_rows():
    """An asymmetric transient (median at one end) made the old gain twice the widest range, plus the plot pad:
    the 20.74 mV note over 5-10 mV rows. The gain is now the widest row's own range, exactly."""
    g = _node(f"M.centredStack({ROWS}.map(M.rowStat))")
    ranges = [-1526.64 - -1532.0, -397.0 - -402.0, -78.0 - -88.1]
    assert g["gainMv"] == pytest.approx(max(ranges))
    assert g["setBy"] == 2


def test_every_drawn_row_sits_inside_its_bounds_and_the_widest_fills_them():
    g = _node(f"M.centredStack({ROWS}.map(M.rowStat))")
    stats = _node(f"{ROWS}.map(M.rowStat)")
    for row, s in zip(g["rows"], stats):
        assert row["lo"] <= s["extent"][0] + 1e-9 and s["extent"][1] <= row["hi"] + 1e-9
        assert row["hi"] - row["lo"] == pytest.approx(g["gainMv"])
    widest = g["rows"][g["setBy"]]
    s = stats[g["setBy"]]
    assert widest["lo"] == pytest.approx(s["extent"][0]) and widest["hi"] == pytest.approx(s["extent"][1])


def test_a_row_with_nothing_finite_is_skipped_and_an_empty_stack_has_no_gain():
    g = _node("M.centredStack([[null, null], [1, 3]].map(M.rowStat))")
    assert g["rows"][0] is None and g["gainMv"] == pytest.approx(2.0) and g["setBy"] == 1
    assert _node("M.centredStack([[null]].map(M.rowStat))") is None


def test_the_note_prints_the_gain_the_rows_are_drawn_at():
    scale = _read("explore", "crossScale.ts")
    assert "centredStack(" in scale, "stackGeom's centred mode takes its gain from crossModel.centredStack"
    note = scale[scale.index("export function scaleNote"):]
    assert "gainMv" in note, "the note prints the gain itself, not the span of a padded y domain"
    assert "span(rows[0].y)" not in scale, "the padded domain's height is not the gain"


# ── X2: the window picker and the deep links drive one state ──────────────────────────────────────────────

SPANS = ("M.orderSpans(["
         "{id: 7, start_s: 2808, end_s: 3408, verdict: 'interesting'},"
         "{id: 3, start_s: 100, end_s: 700, verdict: 'not_interesting'},"
         "{id: 9, start_s: 9000, end_s: 9060, verdict: 'seed'}],"
         "[{id: 41, start_s: 5000, end_s: 5030}, {id: 42, start_s: 50, end_s: 80}])")


def test_spans_are_numbered_in_time_order_as_signal_numbers_its_motifs():
    spans = _node(SPANS)
    assert [s["start_s"] for s in spans] == [50, 100, 2808, 5000, 9000]
    assert [s["key"] for s in spans] == ["d:42", "a:3", "a:7", "d:41", "a:9"]


def test_the_default_window_is_the_best_human_span():
    i = _node(f"M.anchorIndex({SPANS})")
    assert i == 4, "a seed outranks an interesting span, as api/explore's ANCHOR_RANK did"


def test_window_motif_n_picks_the_nth_span_and_the_pad_is_said_in_one_phrase_the_axis_agrees_with():
    w = _node(f"M.resolveCrossWindow({{spans: {SPANS}, durationS: 20000, sel: 'motif-3', padS: 20, explicit: null}})")
    assert (w["spanS"], w["spanE"]) == (2808, 3408)
    assert (w["t0"], w["t1"]) == (2788, 3428)
    assert w["index"] == 2 and w["total"] == 5 and w["param"] == "motif-3"
    assert w["selError"] is None
    assert "600 s span + 20 s each side = 640 s" in w["phrase"], w["phrase"]
    assert "interesting span at 0.78 h" in w["label"]
    w60 = _node(f"M.resolveCrossWindow({{spans: {SPANS}, durationS: 20000, sel: 'motif-3', padS: 60, explicit: null}})")
    assert (w60["t0"], w60["t1"]) == (2748, 3468) and "= 720 s" in w60["phrase"]


def test_no_window_param_is_the_anchor_and_a_bad_one_says_so():
    w = _node(f"M.resolveCrossWindow({{spans: {SPANS}, durationS: 20000, sel: '', padS: 20, explicit: null}})")
    assert w["index"] == 4 and w["param"] == "motif-5" and w["selError"] is None
    bad = _node(f"M.resolveCrossWindow({{spans: {SPANS}, durationS: 20000, sel: 'motif-99', padS: 20, explicit: null}})")
    assert bad["index"] == 4 and bad["selError"] and "99" in bad["selError"]


def test_a_pad_cut_by_the_recording_edge_is_stated_as_it_is():
    w = _node(f"M.resolveCrossWindow({{spans: {SPANS}, durationS: 20000, sel: 'motif-1', padS: 60, explicit: null}})")
    assert w["t0"] == 0 and w["padBefore"] == 50 and w["padAfter"] == 60
    assert "50 s before" in w["phrase"] and "60 s after" in w["phrase"]


def test_a_long_span_is_opened_on_its_first_ten_minutes_and_says_so():
    w = _node("M.resolveCrossWindow({spans: M.orderSpans([{id: 1, start_s: 0, end_s: 72000, verdict: 'interesting'}], []),"
              " durationS: 80000, sel: '', padS: 20, explicit: null})")
    assert w["spanE"] - w["spanS"] == 600 and w["clamped"] and "first 10 min" in w["label"]


def test_an_explicit_edge_window_is_unpadded_and_wins():
    w = _node(f"M.resolveCrossWindow({{spans: {SPANS}, durationS: 20000, sel: 'motif-2', padS: 60, explicit: {{t0: 322.6, t1: 373}}}})")
    assert (w["t0"], w["t1"]) == (322.6, 373) and w["padBefore"] == 0 and w["padAfter"] == 0
    assert "unpadded" in w["phrase"] and w["index"] == -1


def test_the_page_reads_the_window_from_the_url_and_the_picker_writes_it():
    page = _read("explore", "CrossChannelPage.tsx")
    head = page[page.index("export function CrossChannelPage"):page.index("function CrossBody")]
    assert re.search(r"useQueryState<string>\('window'", head), "the fetch reads ?window="
    deps = re.search(r"getCrossChannel\([^)]*\)[^\]]*\[([^\]]*)\]", head)
    assert deps and "windowQ" in deps.group(1), "a change of ?window= refetches"
    body = page[page.index("function CrossBody"):]
    assert 'testid="window-select"' in body and "setWindowQ(" in body
    assert 'testid="pad-select"' in body
    assert "selected span 276.4" not in page, "the fixture-era option is gone"
    api = _read("api", "explore.ts")
    assert "resolveCrossWindow(" in api, "getCrossChannel resolves the window through the one model"


# ── X3: the bin is the core's, its words are the bridge's ─────────────────────────────────────────────────

def test_the_page_never_rebins_a_row_and_asks_for_the_detrended_window():
    page = _read("explore", "CrossChannelPage.tsx")
    bin_of = page[page.index("const binOf"):]
    bin_of = bin_of[:bin_of.index("\n  }\n")]
    assert "0.95" not in bin_of and "0.6" not in bin_of, "no client-side rule beside the core's"
    api = _read("api", "explore.ts")
    assert "crossDetrendFor(" in api, "the page's windows are detrended; an edge's window is as the edge stored it (fix round: decided by crossModel.crossDetrendFor, pinned above)"
    assert 'testid={`bin-rule-${r.name}`}' in page or "bin-rule-" in page, "the bin tip is addressable for smoke"


# ── X4: lag-aligned moves rows by their lag ───────────────────────────────────────────────────────────────

def test_lag_aligned_shifts_a_row_by_its_lag_and_never_the_reference():
    assert _node("M.lagShift(12, false, 'lag', 30)") == 12
    assert _node("M.lagShift(-4.5, false, 'lag', 30)") == -4.5
    assert _node("M.lagShift(12, true, 'lag', 30)") == 0
    assert _node("M.lagShift(12, false, 'recorded', 30)") == 0
    assert _node("M.lagShift(45, false, 'lag', 30)") == 0, "past max lag a row stays as recorded"
    assert _node("M.lagShift(null, false, 'lag', 30)") == 0
    page = _read("explore", "CrossChannelPage.tsx")
    assert "lagShift(" in page


# ── X5 / X6 ───────────────────────────────────────────────────────────────────────────────────────────────

def test_a_disabled_hand_off_card_prints_its_reason_under_it():
    page = _read("explore", "CrossChannelPage.tsx")
    action = page[page.index("function ActionRow"):]
    assert "-why" in action, "the reason is printed on the page, not only in a hover"


def test_the_reference_lock_says_why_and_how_to_change_it():
    page = _read("explore", "CrossChannelPage.tsx")
    lock = page[page.index("grip locked"):][:400]
    assert "reference" in lock and "dropdown" in lock


# ── the smoke walk ────────────────────────────────────────────────────────────────────────────────────────

def test_the_smoke_walk_carries_a_state_per_symptom():
    with io.open(SMOKE, encoding="utf-8") as f:
        states = json.load(f)
    names = {s["state"] for s in states}
    for need in ("aq-gain-equals-widest-row", "aq-pick-a-window", "aq-window-deep-link", "aq-bin-tip-names-its-rule",
                 "aq-lag-aligned-moves-rows", "aq-disabled-card-says-why"):
        assert need in names, f"smoke state {need} missing"
    for s in states:
        assert s["page"] == "explore.cross-channel" and s["expect"]


# ── fix round (the critic, 2026-10-16) ────────────────────────────────────────────────────────────────────

def test_a_window_is_an_edges_and_as_recorded_only_with_an_edge_context():
    """A picked window reopened as ?t0=&t1= used to come back unpadded, as recorded, called an 'edge window' — and
    with a different lag, r and bin. Only an edge link (family= / grouping=) keeps the edge's as-recorded reading."""
    assert _node("M.crossDetrendFor(true, true)") == "none"
    assert _node("M.crossDetrendFor(true, false)") == "linear"
    assert _node("M.crossDetrendFor(false, false)") == "linear"
    assert _node("M.crossDetrendFor(false, true)") == "linear"
    plain = _node("M.resolveCrossWindow({spans: [], durationS: 20000, sel: '', padS: 20, explicit: {t0: 2788, t1: 3428}, edge: false})")
    assert "edge" not in plain["label"] and "unpadded" in plain["phrase"]
    edge = _node("M.resolveCrossWindow({spans: [], durationS: 20000, sel: '', padS: 20, explicit: {t0: 2788, t1: 3428}, edge: true})")
    assert "edge window" in edge["label"]
    api = _read("api", "explore.ts")
    assert "crossDetrendFor(" in api and "explicit ? 'none' : 'linear'" not in api
    page = _read("explore", "CrossChannelPage.tsx")
    head = page[page.index("export function CrossChannelPage"):page.index("function CrossBody")]
    assert "familyQ" in head or "family" in head.split("getCrossChannel(")[1][:200], "the fetch is told whether an edge opened it"


def test_a_row_flagged_as_possible_curved_drift_says_so_beside_its_bin():
    page = _read("explore", "CrossChannelPage.tsx")
    assert "driftSuspect" in page and "may be curved drift" in page
    assert "drift-suspect-" in page


def test_the_picker_tip_says_it_renumbers_and_lists_forty():
    page = _read("explore", "CrossChannelPage.tsx")
    assert "renumber" in page and "first 40" in page


def test_the_old_cross_read_without_a_detrend_is_gone():
    api = _read("api.ts")
    assert "export const getCross =" not in api

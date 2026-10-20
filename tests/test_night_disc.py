"""
test_night_disc.py
==================
night-disc (2026-10-20, the researcher's second list, the night before the demo): the Discovery runs list as the
researcher drew it, the Seed page's cut-off card text, the Scope card's recording switch, and the map's top scrollbar.
Source checks only (the layout itself is measured by the smoke unit `zzzzzzzzzzz_a1_night_disc.json`); conda pytest.

Item 1. "each template box ... left column icon, then under the tag, e.g. 'seed', then under that the '1 of 3 ch'
indicator but without the grey text; then middle column title as is, below bare info (how many found, etc); then
right column 'x' close button in utmost right corner, beneath is select button, then report button beneath."

Item 2. On *Choose the cut* the histogram's y-axis label "count" was clipped at the left edge; on *Keep the matches*
the lede and the buttons sat against the card's border (the card has no padding of its own).

Item 3. "49 matches, not 155": switching the recording in the Scope card wrote `channels: first three, section:
[0, min(hours, 174)]` with the recording, and the bridge opened the TARGET recording's existing session and overwrote
its saved channels and section with those defaults -- so switching to M2_aug clobbered "demo · talk"'s 5-channel,
0-721 h scope, and the next seed search ran on 3 channels x 174 h. A change of recording now sends the recording only.

Item 4. Level 3 of the map (all datasets) has a thin horizontal scrollbar ABOVE the dataset names, synced both ways
with the table's own horizontal scroll.
"""
import io
import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
PAGES = os.path.join(PROJECT_ROOT, "webui", "smoke_pages")


def _src(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


def _between(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i)]


def _run_row():
    return _between(_src("discovery", "chrome.tsx"), "function RunRow",
                    "/* ------------------------------------------------------------------ coverage strip")


# ── item 1: three columns ───────────────────────────────────────────────────

def test_a_run_row_is_three_columns():
    body = _run_row()
    for col in ("dsc-run-left", "dsc-run-mid", "dsc-run-right"):
        assert f'className="{col}"' in body, f"{col} is not a column of the run row"
    left = _between(body, 'className="dsc-run-left"', 'className="dsc-run-mid"')
    mid = _between(body, 'className="dsc-run-mid"', 'className="dsc-run-right"')
    right = body[body.index('className="dsc-run-right"'):]
    # left: the glyph, under it the kind tag, under that the coverage
    assert left.index("RunGlyph") < left.index("kindBadge") < left.index("CoverageStrip")
    # middle: the name, its bare facts, and the run's extra actions as small buttons
    assert "title={run.label}" in mid and "dsc-run-line" in mid
    for tid in ("run-missing-", "chain-import-", "retry-", "open-in-jobs-"):
        assert tid in mid, f"{tid} is not in the middle column"
    assert "report-" not in mid, "the Report button belongs to the right column"
    # right: the x in the corner, beneath it the A/B box, beneath that the Report icon
    assert right.index("remove-") < right.index("pick-") < right.index("report-")


def test_the_report_button_is_an_icon_titled_report():
    right = _run_row()
    right = right[right.index('className="dsc-run-right"'):]
    m = re.search(r"<IconButton[^>]*testid=\{`report-\$\{run\.key\}`\}[^>]*>", right, re.S) or \
        re.search(r"<IconButton[^>]*report-[^>]*/>", right, re.S)
    assert m, "the Report button is not an IconButton"
    assert 'icon="file"' in m.group(0) and 'label="Report"' in m.group(0)


def test_the_coverage_count_is_body_text_not_grey():
    strip = _between(_src("discovery", "chrome.tsx"), "function CoverageStrip", "/* ------------------------------------------------------------------ SLURM")
    assert 'className="muted"' not in strip
    assert "dsc-cov-n" in strip


def test_the_band_set_and_draft_rows_take_the_same_columns():
    chrome = _src("discovery", "chrome.tsx")
    band = _between(chrome, "function BandSetRow", "function RunRow")
    for col in ("dsc-run-left", "dsc-run-mid", "dsc-run-right"):
        assert col in band, f"the band-set row has no {col}"
    seed = _src("discovery", "SeedPage.tsx")
    draft = _between(seed, "function DraftRow", "/* ------------------------------------------------------------------ seed card")
    for col in ("dsc-run-left", "dsc-run-mid", "dsc-run-right"):
        assert col in draft, f"the draft row has no {col}"
    assert 'data-testid="draft-name"' in draft


def test_the_run_row_css_is_three_columns_and_wraps_rather_than_clips():
    css = _src("discovery", "discovery.css")
    rule = re.search(r"\.dsc-run\s*\{[^}]*\}", css).group(0)
    assert "display: grid" in rule
    assert re.search(r"grid-template-columns:\s*\d+px\s+minmax\(0,\s*1fr\)\s+(auto|\d+px)", rule), rule
    line = re.findall(r"\.dsc-run-line\s*\{[^}]*\}", css)[-1]
    assert "white-space: normal" in line, "a run's facts wrap: nothing is clipped"


# ── item 2: the seed cards ──────────────────────────────────────────────────

def test_the_histogram_leaves_room_for_its_count_label():
    seed = _src("discovery", "SeedPage.tsx")
    hist = _between(seed, "function CutHistogram", "</svg>")
    pad = int(re.search(r"padL\s*=\s*(\d+)", hist).group(1))
    assert pad >= 42, f"padL {pad}: 'count' (5 mono characters, ~31 px) ends at padL-6 and starts off the card"
    assert "cutLabelX" in hist, "the cut label is placed so it never runs off the right edge"


def test_the_keep_card_has_its_own_inner_margin():
    css = _src("discovery", "discovery.css")
    assert re.search(r"\.dsc-keep\s*>\s*:not\(\.dsc-card-head\)\s*\{[^}]*margin-(inline|left)", css)
    assert re.search(r"\.dsc-keep\s*\{[^}]*padding-bottom", css)


# ── item 3: a change of recording does not overwrite the target session's scope ─

def test_a_change_of_recording_sends_the_recording_only():
    chrome = _src("discovery", "chrome.tsx")
    fn = _between(chrome, "const changeRecording", "const runPreview")
    calls = re.findall(r"dx\.setScope\(\{[^}]*\}\)", fn)
    assert "dx.setScope({ recording: key })" in calls, calls
    # only a held-out recording (never written to the bridge, shown from the client's copy) keeps defaults
    for call in calls:
        if "channels" in call or "section" in call:
            assert "if (r.heldOut) " + call in fn, f"a non-held-out switch still writes a scope: {call}"
    sess = _src("discovery", "session.ts")
    assert "putRecording(" in sess, "the session writes a bare recording through putRecording"
    api = _src("api", "discovery.ts")
    m = re.search(r"export const putRecording = \(recording: string\) =>\s*putDiscoverySession\(\{ recording \}\)", api)
    assert m, "putRecording sends { recording } alone"


def test_the_confirm_no_longer_says_it_clears_the_channels():
    chrome = _src("discovery", "chrome.tsx")
    pop = _between(chrome, 'title="Change the recording?"', "</Popover>")
    assert "clears" not in pop
    assert "as it was left" in pop


def test_the_deep_link_still_writes_its_channels():
    api = _src("api", "discovery.ts")
    assert "export const putScopeLink" in api
    link = _between(api, "export const putScopeLink", ".then(")
    assert "channels: body.channels" in link


# ── item 4: the map's top scrollbar ─────────────────────────────────────────

def test_level_3_has_a_top_scrollbar_synced_with_the_table():
    page = _src("discovery", "MapPage.tsx")
    lvl = _between(page, "function DatasetsLevel", "/* ------------------------------------------------------------------ level 2")
    assert "<TopScrollbar" in lvl
    assert lvl.index("<TopScrollbar") < lvl.index('data-testid="map-wrap"'), "the bar sits above the table"
    bar = _between(page, "function TopScrollbar", "\n}\n")
    assert 'data-testid="map-top-scroll"' in bar
    assert "scrollLeft" in bar and "addEventListener('scroll'" in bar and "ResizeObserver" in bar


# ── the smoke unit ──────────────────────────────────────────────────────────

def test_the_smoke_unit_measures_each_item():
    rows = json.load(io.open(os.path.join(PAGES, "zzzzzzzzzzz_a1_night_disc.json"), encoding="utf-8"))
    names = {r["state"] for r in rows}
    for s in ("night-disc-run-rows-three-columns-at-1024", "night-disc-seed-cut-card-not-clipped",
              "night-disc-seed-keep-card-not-squished", "night-disc-map-top-scrollbar"):
        assert s in names, f"{s} is missing"
    # every state is read-only: no write, no zoom, no span sent (the unit may sort anywhere)
    for r in rows:
        for a in r.get("actions", []):
            assert "click" not in a or "recording-confirm-change" not in json.dumps(a), "a state never switches the recording"

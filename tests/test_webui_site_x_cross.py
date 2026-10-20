"""
test_webui_site_x_cross.py
==========================
site-x (2026-10-20, the researcher's list on the eve of the demo): Explore › Cross-channel.

Item 1 — "make overlay plot by default": the page opens on the overlay; ?view=stacked is the stacked rows, and every
smoke state that opens the page names the view it checks.

Item 2 — "cross channel plotting errors?". Reproduced on the real CO_fs2.mat, CH1, window #1 (detection 6236294,
0–80 s, detrend linear), overlay, four channels:
  * CH1/CH3/CH4 span 0.15–0.25 mV over the window, CH2 drifts 35 mV (−409 → −444 mV). The overlay's one shared gain is
    set by the MEDIAN channel's range, so CH2 was drawn 145 lanes tall about its mean: everything but the moment it
    crossed its own mean fell outside the block — "a flat orange line and one near-vertical stroke at about +33 s".
    A channel whose range cannot fit the block at the shared gain is now drawn at its own gain and SAYS so (÷ factor).
  * every channel carries detections that span the whole window (6 of CH1's 17 start at 0 s and end at 128–7860 s;
    CH2 has 235). The overlay drew each as a solid 2.5 px bar in the channel's own colour at the top of its lane —
    "a straight horizontal line at the top of its band", indistinguishable from a trace. They are merged into one mark
    per run of overlap, drawn as a dashed bracket, open-ended where they run past the window, with a legend.
  * the stacked view on the same window: 'centred' takes its gain from the widest row (CH2, 35 mV), so the other three
    rows draw 0.2–0.3 px tall — flat with nothing said. A row flatter than FLAT_PX says so in words on the row.

The behavioural half RUNS webui/client/src/explore/overlayModel.ts under Node (types stripped natively), as
test_webui_cross_page.py does for crossModel.ts; it skips when `node` is not on PATH.

    python -m pytest tests/test_webui_site_x_cross.py
"""
import glob
import io
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
MODEL_TS = os.path.join(CLIENT_SRC, "explore", "overlayModel.ts")
SMOKE_DIR = os.path.join(PROJECT_ROOT, "webui", "smoke_pages")
SITE_X_SMOKE = os.path.join(SMOKE_DIR, "zzzzzzzzzzz_site_x.json")


def _read(*parts):
    path = os.path.join(CLIENT_SRC, *parts)
    assert os.path.isfile(path), f"{os.path.relpath(path, PROJECT_ROOT)} is missing"
    return io.open(path, encoding="utf-8").read()


def _node(expr: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH; the overlay's model is exercised by webui/smoke.py instead")
    assert os.path.isfile(MODEL_TS), "webui/client/src/explore/overlayModel.ts does not exist"
    url = "file:///" + MODEL_TS.replace("\\", "/").lstrip("/")
    script = f"import * as M from {json.dumps(url)};\nconst out = ({expr});\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# the ranges measured on CO_fs2.mat, window #1, in mV: CH1, CH2, CH3, CH4
CO_SPANS = [0.152, 34.97, 0.190, 0.244]
LANE, BLOCK, GAIN_LANES = 100.0, 420.0, 1.6


# ── item 2a: a channel that cannot fit the block at the shared gain ──────────────────────────────────────────

def test_a_channel_that_runs_past_the_block_is_drawn_at_its_own_gain_and_says_by_how_much():
    g = _node(f"M.overlayGains({json.dumps(CO_SPANS)}, {LANE}, {BLOCK}, {GAIN_LANES})")
    ch2 = g["rows"][1]
    assert ch2["ownScale"] is True
    # drawn at its own gain it fills GAIN_LANES lanes, as the median channel does at the shared one
    assert ch2["pxPerUnit"] * CO_SPANS[1] == pytest.approx(GAIN_LANES * LANE)
    # the factor is how much smaller than the shared gain it is drawn — what the name column prints
    assert ch2["factor"] == pytest.approx(g["shared"] / ch2["pxPerUnit"])
    assert ch2["factor"] > 100


def test_channels_that_fit_keep_the_one_shared_gain():
    g = _node(f"M.overlayGains({json.dumps(CO_SPANS)}, {LANE}, {BLOCK}, {GAIN_LANES})")
    for i in (0, 2, 3):
        row = g["rows"][i]
        assert row["ownScale"] is False and row["factor"] == 1
        assert row["pxPerUnit"] == pytest.approx(g["shared"])
        assert row["pxPerUnit"] * CO_SPANS[i] <= BLOCK


def test_a_channel_with_no_range_keeps_the_shared_gain_and_an_all_empty_overlay_still_has_one():
    g = _node(f"M.overlayGains([null, 0, 2], {LANE}, {BLOCK}, {GAIN_LANES})")
    assert [r["ownScale"] for r in g["rows"]] == [False, False, False]
    assert g["shared"] == pytest.approx(GAIN_LANES * LANE / 2)
    e = _node(f"M.overlayGains([null, null], {LANE}, {BLOCK}, {GAIN_LANES})")
    assert e["shared"] > 0 and all(r["pxPerUnit"] == e["shared"] for r in e["rows"])


# ── item 2b: detection marks that read as a trace ────────────────────────────────────────────────────────────

def test_overlapping_detections_merge_into_one_mark_and_say_where_they_run_past_the_window():
    marks = _node("M.mergeDetectionMarks([{t0: 0, t1: 368}, {t0: 0, t1: 128}, {t0: 10, t1: 20}, {t0: 90, t1: 95}], 0, 80)")
    assert len(marks) == 1, "every mark overlaps the first, which covers the whole window"
    m = marks[0]
    assert (m["t0"], m["t1"], m["n"]) == (0, 80, 3)
    assert m["openRight"] is True and m["openLeft"] is False
    two = _node("M.mergeDetectionMarks([{t0: 5, t1: 10}, {t0: 8, t1: 12}, {t0: 30, t1: 40}, {t0: -50, t1: 1}], 0, 80)")
    assert [(m["t0"], m["t1"], m["n"]) for m in two] == [(0, 1, 1), (5, 12, 2), (30, 40, 1)]
    assert two[0]["openLeft"] is True and not two[1]["openLeft"] and not two[1]["openRight"]


def test_the_overlay_draws_detections_as_brackets_with_a_legend_never_as_a_solid_bar_in_trace_colour():
    src = _read("explore", "Overlay.tsx")
    assert "mergeDetectionMarks(" in src, "the overlay draws merged marks, not one bar per detection"
    assert 'data-testid="ov-detection"' in src
    assert "strokeDasharray" in src[src.index('data-testid="ov-detection"') - 600:src.index('data-testid="ov-detection"')], \
        "a detection mark is dashed so it cannot be read as a trace"
    page = _read("explore", "CrossChannelPage.tsx")
    assert 'data-testid="ov-det-legend"' in page, "the overlay head says what the dashed marks are"


def test_a_channel_drawn_at_its_own_scale_or_not_drawn_at_all_says_so_in_words():
    src = _read("explore", "Overlay.tsx")
    assert "overlayGains(" in src, "the overlay takes its per-channel gain from overlayModel.overlayGains"
    assert "ov-own-scale-" in src, "a channel at its own gain prints ÷factor beside its name"
    assert "ov-lane-note-" in src, "a channel that cannot be drawn (read failed, nothing finite) says why in its lane"


# ── item 2c: the stacked view on the same window ─────────────────────────────────────────────────────────────

def test_a_stacked_row_flatter_than_two_pixels_at_the_shared_gain_says_so():
    # CH1's 0.152 mV in a 52 px row at CH2's 34.97 mV per row
    px = _node("M.drawnRowPx([54.566, 54.718], 34.97, 52)")
    assert px == pytest.approx(0.152 / 34.97 * 52, rel=1e-3)
    assert px < _node("M.FLAT_PX")
    assert _node("M.drawnRowPx(null, 34.97, 52)") is None
    page = _read("explore", "CrossChannelPage.tsx")
    assert "drawnRowPx(" in page and "xrow-flat-" in page, "a row too flat to read at the shared gain says so on the row"


# ── item 1: overlay by default ───────────────────────────────────────────────────────────────────────────────

def test_the_page_opens_on_the_overlay_and_view_stacked_is_the_stacked_rows():
    page = _read("explore", "CrossChannelPage.tsx")
    assert re.search(r"const overlay = viewQ !== 'stacked'", page), "absent ?view= is the overlay"
    assert "setViewQ(v === 'stacked' ? 'stacked' : null)" in page, "the switch writes ?view=stacked, and clears it for the overlay"


def _cross_states():
    for path in sorted(glob.glob(os.path.join(SMOKE_DIR, "*.json"))):
        with io.open(path, encoding="utf-8") as f:
            for s in json.load(f):
                h = s.get("hash", "")
                if h.startswith("explore/cross-channel/"):
                    yield os.path.basename(path), s


def test_every_smoke_state_on_the_page_names_its_view_except_the_one_that_pins_the_default():
    unnamed = [(f, s["state"]) for f, s in _cross_states() if "view=" not in s["hash"]]
    assert unnamed == [("zzzzzzzzzzz_site_x.json", "site-x-overlay-is-default")], unnamed


def test_the_site_x_smoke_unit_pins_the_default_and_the_co_window():
    with io.open(SITE_X_SMOKE, encoding="utf-8") as f:
        states = {s["state"]: s for s in json.load(f)}
    d = states["site-x-overlay-is-default"]
    assert '[data-testid="overlay"]' in d["expect"] and '[data-testid="reference-trace"]' in d["expect_absent"]
    assert "site-x-stacked-on-request" in states
    assert '[data-testid="reference-trace"]' in states["site-x-stacked-on-request"]["expect"]

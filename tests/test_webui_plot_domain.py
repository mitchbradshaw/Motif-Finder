"""
test_webui_plot_domain.py
=========================
fixup-c: ONE plot-domain rule, across Review, the Library and Explore.

PRD D5 (one shared unnormalised mV domain per page) is replaced by the
researcher's call of 2026-09-23 (`docs/prompts/fixup/QUESTIONS.md` Q-X2.1):
**a per-card domain measured from the card's own trace, with the page's shared
scale drawn as a reference bar.** The acceptance test is that no motif is ever
clipped in its own thumbnail.

What this file pins:

* the rule itself — `webui/client/src/charts/domain.ts` — by RUNNING it under
  Node (which strips TypeScript types natively since v22.18), not by reading
  it: a measured domain contains every sample of every series it was measured
  from; a genuinely flat trace gets a finite, non-degenerate domain; a tiny
  trace (a 0.005 mV `drop_motifs10` event) is NOT floored up to some minimum
  domain, because hiding that population inside a display rule would bury a
  research finding; the reference scale holds every page peak, and places them
  in order.
* that the old rules are gone rather than left beside the new one: D5's
  `sharedMvDomain`, Review's `Y_MV` / `THUMB_Y`, the hard-coded domains the
  Library passed to its thumbnails, `MiniTrace`'s silent clamp, and the Family
  page's shape sketch.
* that the smoke gate measures the acceptance test in a real browser.

There is no Node test runner in this repo (the client's gate is `tsc -b`,
`npm run build` and `webui/smoke.py`). The behavioural half skips when `node`
is not on PATH; the source-level half always runs.

Runnable standalone:  python tests/test_webui_plot_domain.py
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
DOMAIN_TS = os.path.join(CLIENT_SRC, "charts", "domain.ts")


def _read(*parts):
    path = os.path.join(CLIENT_SRC, *parts)
    assert os.path.isfile(path), f"{os.path.relpath(path, PROJECT_ROOT)} is missing"
    return io.open(path, encoding="utf-8").read()


def _client_files(*subdirs):
    roots = [os.path.join(CLIENT_SRC, s) for s in subdirs] if subdirs else [CLIENT_SRC]
    for root in roots:
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                if name.endswith((".ts", ".tsx")):
                    yield os.path.join(dirpath, name)


# ── the rule, run ───────────────────────────────────────────────────────────

def _node(expr: str):
    """Evaluate `expr` against the domain module under Node; return its JSON."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH; the client's rule is exercised by webui/smoke.py instead")
    assert os.path.isfile(DOMAIN_TS), "webui/client/src/charts/domain.ts (the one rule) does not exist"
    url = "file:///" + DOMAIN_TS.replace("\\", "/").lstrip("/")
    script = f"import * as D from {json.dumps(url)};\nconst out = ({expr});\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_a_measured_domain_contains_every_sample_of_every_series():
    lo, hi = _node("D.measuredDomain([-420.4, -418.2, -421.9, null], [-419, -417.5])")
    assert lo < -421.9 and hi > -417.5, "the trace and its overlay must both sit inside"
    # padded, but by a pad — not by the ±440 a hand-set constant gave a 4 mV swing
    width = -417.5 - -421.9
    assert (hi - lo) < 1.5 * width


def test_the_pad_is_the_rules_one_pad_on_both_sides():
    pad = _node("D.DOMAIN_PAD")
    lo, hi = _node("D.measuredDomain([0, 10])")
    assert 0 < pad < 0.25
    assert lo == pytest.approx(-10 * pad) and hi == pytest.approx(10 + 10 * pad)


def test_a_tiny_trace_is_not_floored_up_to_a_minimum_domain():
    """`drop_motifs10`'s median event is 0.219 mV and a third sit under the
    0.1 mV floor. The rule draws them large and legible; it does not hide them
    by imposing a minimum domain (prompt C, "a thing you will see")."""
    lo, hi = _node("D.measuredDomain([0.0021, -0.0029, 0.0004])")
    assert lo < -0.0029 and hi > 0.0021
    assert (hi - lo) < 0.01, "a 0.005 mV trace must get a domain of its own size, not a floor"


def test_a_flat_trace_gets_a_finite_non_degenerate_domain():
    for values in ("[0, 0, 0]", "[-112.2, -112.2]", "[5]"):
        lo, hi = _node(f"D.measuredDomain({values})")
        v = json.loads(values)[0]
        assert lo < v < hi, f"a flat trace sits inside its domain: {values}"
        assert hi - lo > 0 and hi - lo < max(1.0, abs(v)), f"and the floor is small, not a made-up scale: {values}"


def test_nothing_finite_is_no_domain_rather_than_an_invented_one():
    assert _node("D.measuredDomain([], [null, null])") is None
    assert _node("D.measuredDomain([NaN, Infinity])") is None


def test_pad_domain_is_what_every_measured_extent_goes_through():
    lo, hi = _node("D.padDomain(-1, 1)")
    assert lo < -1 and hi > 1
    lo, hi = _node("D.padDomain(3, 3)")
    assert lo < 3 < hi


def test_the_reference_scale_holds_every_page_peak_and_orders_them():
    s = _node("D.referenceScale([0.02, 0.9, 15.6, 120, 0, -1, NaN])")
    assert s["lo"] <= 0.02 and s["hi"] >= 120, "every positive peak on the page is on the shared scale"
    pos = _node("[0.02, 0.9, 15.6, 120].map(v => D.referencePosition(D.referenceScale([0.02, 0.9, 15.6, 120]), v))")
    assert all(0 <= p <= 1 for p in pos)
    assert pos == sorted(pos) and len(set(pos)) == 4, "a bigger card sits higher on the bar"


def test_equal_ratios_are_equal_steps_on_the_reference_bar():
    """Four decades on one bar: a linear bar would draw every sub-mV family at
    zero, which is the flat line D5 drew, moved. Equal ratios, equal steps."""
    a, b, c = _node("[0.1, 1, 10].map(v => D.referencePosition(D.referenceScale([0.1, 10]), v))")
    assert (b - a) == pytest.approx(c - b)


def test_no_reference_scale_without_a_positive_peak():
    assert _node("D.referenceScale([0, -3, NaN])") is None
    assert _node("D.referencePosition(D.referenceScale([1, 10]), 0)") is None


def test_the_baseline_peak_is_the_largest_deviation_from_the_traces_own_median():
    assert _node("D.baselinePeak([-420, -420, -415, -420, -425.5])") == pytest.approx(5.5)
    assert _node("D.centreTrace([2, 4, 6])") == [-2, 0, 2]


# ── one rule, and the old ones gone ─────────────────────────────────────────

def test_d5s_percentile_domain_is_not_left_beside_the_new_rule():
    offenders = [os.path.relpath(p, PROJECT_ROOT) for p in _client_files()
                 if re.search(r"\bsharedMvDomain\b", io.open(p, encoding="utf-8").read())]
    assert not offenders, f"sharedMvDomain (PRD D5's rule) is still referenced in {offenders}"


def test_reviews_hand_measured_constants_are_gone():
    offenders = []
    for p in _client_files("review"):
        src = io.open(p, encoding="utf-8").read()
        if re.search(r"\b(?:const|let|var)\s+(?:Y_MV|THUMB_Y)\b", src) or re.search(r"\b(?:Y_MV|THUMB_Y)\b", src):
            offenders.append(os.path.relpath(p, PROJECT_ROOT))
    assert not offenders, f"Review still draws on a hand-set domain in {offenders}"


def test_no_library_or_review_plot_is_handed_a_literal_domain():
    """`yDomain={[-0.45, 0.45]}` and friends: every one was a second rule."""
    pat = re.compile(r"yDomain=\{\s*\[\s*-?\d|:\s*\[number,\s*number\]\s*=\s*\[\s*-?\d")
    offenders = []
    for p in _client_files("library", "review"):
        for i, line in enumerate(io.open(p, encoding="utf-8"), 1):
            if pat.search(line):
                offenders.append(f"{os.path.relpath(p, PROJECT_ROOT)}:{i}")
    assert not offenders, f"hard-coded plot domains remain: {offenders}"


def test_minitrace_no_longer_clamps_a_trace_silently():
    src = _read("kit", "plots.tsx")
    body = src[src.index("export function MiniTrace"):src.index("/* ================= LineChart")]
    assert not re.search(r"Math\.max\(\s*yDomain\[0\]\s*,\s*Math\.min\(\s*yDomain\[1\]", body), (
        "a clamped sample draws along the frame and reads as data; out of domain must be out of the box")
    assert "measuredDomain" in body, "a MiniTrace with no domain handed in measures its own, by the one rule"
    assert "data-plot-box" in body and "data-trace" in body, "smoke must be able to find the box and the trace"


def test_the_kits_trace_and_explores_scale_use_the_one_rule():
    plots = _read("kit", "plots.tsx")
    trace = plots[plots.index("export function Trace("):plots.index("/* ================= MiniTrace")]
    assert "measuredDomain" in trace, "the big Trace's default domain is the rule, not its own 8 % extent"
    assert "data-plot-box" in trace and "data-trace" in trace
    scale = _read("charts", "scale.ts")
    make_y = scale[scale.index("export function makeY"):]
    make_y = make_y[:make_y.index("\n}\n")]
    assert "padDomain" in make_y, "Explore's y scales pad and floor through the one rule"


def test_the_family_page_draws_real_member_waveforms_not_a_sketch():
    src = _read("library", "FamilyPage.tsx")
    assert "motifShape" not in src, "a member card that is not the member's waveform is not worth its space (Q-X2.3)"
    assert "SKETCH_NOTE" not in src
    assert re.search(r"\bm\.trace\b|\.trace\b", src), "the member card draws the member's own trace"


def test_the_clip_scaffolding_d5_needed_is_removed():
    for rel in (("library", "chrome.tsx"), ("library", "AtlasPage.tsx"), ("library", "FamilyPage.tsx")):
        src = _read(*rel)
        assert "clippedPeak" not in src, f"{'/'.join(rel)}: no card is clipped any more, so none is marked"
        assert "plot-clipped" not in src
        assert not re.search(r"shared mV scale", src), f"{'/'.join(rel)}: the shared scale is the bar, not a caption"


def test_every_library_and_review_card_can_draw_the_reference_bar():
    uses = [os.path.relpath(p, PROJECT_ROOT) for p in _client_files("library", "review")
            if "ReferenceBar" in io.open(p, encoding="utf-8").read()]
    for need in ("chrome.tsx", "FamilyPage.tsx", "parts.tsx"):
        assert any(u.endswith(need) for u in uses), f"{need} draws no reference bar"


# ── the acceptance test is measured in a browser ────────────────────────────

def test_smoke_measures_that_no_trace_leaves_its_plot_box():
    smoke = io.open(os.path.join(PROJECT_ROOT, "webui", "smoke.py"), encoding="utf-8").read()
    assert "traces_in_box" in smoke and "getBoundingClientRect" in smoke
    flagged = {}
    for fn in ("library.json", "review.json"):
        with open(os.path.join(PROJECT_ROOT, "webui", "smoke_pages", fn), encoding="utf-8") as fh:
            flagged[fn] = [e["page"] for e in json.load(fh) if e.get("traces_in_box")]
    assert "library.atlas" in flagged["library.json"]
    assert "library.family" in flagged["library.json"]
    assert any(p.startswith("review.") for p in flagged["review.json"]), "the Review inspector"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

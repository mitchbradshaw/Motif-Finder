"""
test_webui_review_axis.py
=========================
fixup-g: a Review trace and everything drawn beside it — the highlight band,
the crosshair, the axis labels — are in ONE coordinate system.

The defect (`docs/prompts/fixup/QUESTIONS.md`, Round 4 findings, U1/U2/U3):
the bridge served a decimated envelope's VALUES and discarded its `t`, on a
contract that "the x axis is implied"; the client drew point `i` at `t0 + i`
seconds while `decimate.envelope` returns fewer, non-uniformly spaced points
once a span exceeds 2 x px. Detection 102's drop was drawn at 0.6294 h; it is
at 0.6619 h, inside the band the reviewer thought had missed it. The padding
segmented control sliced envelope POINTS as though they were seconds (U3), and
each bucket's min and max — meant to sit on nearly the same x — were drawn a
whole "second" apart (U1's zigzag).

What this file pins:

* the client's context slice, `webui/client/src/review/axis.ts`, by RUNNING it
  under Node (which strips TypeScript types natively since v22.18): it slices
  by absolute time, so a point keeps the `t` the server gave it; the padding is
  the padding asked for on both sides; a feature drawn at index `i` of a
  decimated trace sits at ITS time, not at `t0 + i`; a window clipped at the
  recording's start is honestly asymmetric rather than shifted;
* the crosshair's nearest-point lookup on a non-uniform axis;
* that the old contract is gone rather than left beside the new one: no
  `CONTEXT_PAD_MAX - pad` index slicing in `parts.tsx`, the kit's `Trace` and
  `MiniTrace` accept a `t` axis (ADDITIVELY — a caller passing no `t` keeps
  today's behaviour, which is what `tests/test_webui_plot_domain.py`'s Node
  tests and Interrogation's pages rely on), and `ItemDetail.context` is no
  longer a bare `values` list.

There is no Node test runner in this repo (the client's gate is `tsc -b`,
`npm run build` and `webui/smoke.py`). The behavioural half skips when `node`
is not on PATH; the source-level half always runs.

Runnable standalone:  python tests/test_webui_review_axis.py
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
AXIS_TS = os.path.join(CLIENT_SRC, "review", "axis.ts")


def _read(*parts):
    path = os.path.join(CLIENT_SRC, *parts)
    assert os.path.isfile(path), f"{os.path.relpath(path, PROJECT_ROOT)} is missing"
    return io.open(path, encoding="utf-8").read()


def _node(expr: str):
    """Evaluate `expr` against the axis module under Node; return its JSON."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH; the client's slice is exercised by webui/smoke.py instead")
    assert os.path.isfile(AXIS_TS), "webui/client/src/review/axis.ts (the context slice) does not exist"
    url = "file:///" + AXIS_TS.replace("\\", "/").lstrip("/")
    script = f"import * as A from {json.dumps(url)};\nconst out = ({expr});\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ── a decimated context, as `decimate.envelope` would serve detection 102 ────
#
# 660 samples [2033, 2693) in 220 buckets of 3 (the window's edges are t0_s = 2033
# and t1_s = 2693, the exclusive end in seconds); each bucket emits its min and
# its max at THEIR OWN sample times, so the axis is non-uniform. The one real
# feature is a drop to -1 at t = 2382, inside the detection [2333, 2393).

_CONTEXT_JS = """(() => {
  const t = [], v = [];
  for (let b = 0; b < 220; b++) {
    const s = 2033 + 3 * b;
    if (s <= 2382 && 2382 < s + 3) { t.push(s, 2382); v.push(0.01, -1) }
    else { t.push(s, s + 2); v.push(0.01, 0.02) }
  }
  return { t, v, t0_s: 2033, t1_s: 2693, fs: 1, n_source: 660, n_points: t.length, decimated: true }
})()"""
_BAND = "{ start_s: 2333, end_s: 2393 }"


def test_the_slice_is_by_absolute_time_and_the_padding_is_symmetric():
    for pad in (30, 120, 300):
        s = _node(f"A.sliceContext({_CONTEXT_JS}, {_BAND}, {pad})")
        assert s["t0"] == pytest.approx(2333 - pad), f"pad {pad}: left edge"
        assert s["t1"] == pytest.approx(2393 + pad), f"pad {pad}: right edge"
        assert s["bandStart"] == 2333 and s["bandEnd"] == 2393
        assert len(s["t"]) == len(s["v"]) > 0
        assert min(s["t"]) >= s["t0"] and max(s["t"]) <= s["t1"], "every kept point is inside the window"


def test_a_feature_is_drawn_at_its_own_time_not_at_t0_plus_its_index():
    """The U2 reproduction. Before: the drop at 2382 s was drawn at
    2033 + (its index in the decimated list) — a third of the way early."""
    s = _node(f"A.sliceContext({_CONTEXT_JS}, {_BAND}, 300)")
    i = min(range(len(s["v"])), key=lambda k: s["v"][k])
    assert s["t"][i] == 2382, "the drop keeps the time the server gave it"
    assert s["bandStart"] <= s["t"][i] <= s["bandEnd"], "and sits inside the highlight band"
    assert s["t0"] + i != 2382, "the old `t0 + i` contract would have drawn it somewhere else"


def test_a_window_clipped_at_the_recording_start_is_honestly_asymmetric():
    """The bridge clips the context at sample 0. The slice must not shift the
    band to make the padding look even — the band is where the event is."""
    ctx = "{ t: [0, 1, 2, 100, 130, 160, 460], v: [0, 0, 0, -1, 0, 0, 0], t0_s: 0, t1_s: 460, fs: 1, n_source: 461, n_points: 7, decimated: true }"
    s = _node(f"A.sliceContext({ctx}, {{ start_s: 100, end_s: 160 }}, 300)")
    assert s["t0"] == 0 and s["t1"] == 460
    assert s["bandStart"] == 100 and s["bandEnd"] == 160
    assert s["t"][s["v"].index(-1)] == 100


def test_the_crosshair_finds_the_nearest_point_on_a_non_uniform_axis():
    t = "[2033, 2035, 2036, 2038, 2382, 2383, 2690, 2692]"
    assert _node(f"A.nearestIndex({t}, 2381.6)") == 4
    assert _node(f"A.nearestIndex({t}, 2034.4)") == 1
    assert _node(f"A.nearestIndex({t}, 1000)") == 0
    assert _node(f"A.nearestIndex({t}, 9999)") == 7
    assert _node("A.nearestIndex([], 5)") == -1


# ── the old contract is gone, and the kit change stayed additive ────────────

def test_the_padding_is_no_longer_an_index_slice():
    parts = _read("review", "parts.tsx")
    assert "CONTEXT_PAD_MAX - pad" not in parts, (
        "parts.tsx still slices envelope points as though they were seconds (U3)")
    assert not re.search(r"values\.slice\(\s*off", parts), "the index slice against `off` is still there"
    assert "sliceContext" in parts and "./axis" in parts, "the context card slices through review/axis.ts"


def test_the_kit_traces_take_a_time_axis_additively():
    plots = _read("kit", "plots.tsx")
    trace_props = plots[plots.index("export interface TraceProps"):plots.index("export function Trace(")]
    assert re.search(r"\bt\?:\s*number\[\]", trace_props), "TraceProps has no optional `t` axis"
    mini_props = plots[plots.index("export interface MiniTraceProps"):plots.index("export function MiniTrace(")]
    assert re.search(r"\bt\?:\s*number\[\]", mini_props), "MiniTraceProps has no optional `t` axis"
    # additive: `values` is still the required series and `fs`/`t0` are still accepted
    assert re.search(r"\bvalues:\s*number\[\]", trace_props)
    assert "fs?: number" in trace_props and "t0?: number" in trace_props


def test_the_item_detail_context_is_a_trace_with_an_axis():
    api = _read("api", "review.ts")
    detail = api[api.index("export interface ItemDetail"):]
    detail = detail[:detail.index("}\n", detail.index("{")) + 2]
    assert not re.search(r"context:\s*\{\s*values:\s*number\[\]", detail), (
        "ItemDetail.context is still a bare value list with an implied axis")
    assert "shapeSource" in detail, "the higher-resolution source shape is not in the contract"
    other = api[api.index("export interface OtherChannelRow"):]
    other = other[:other.index("}") + 1]
    assert "values: number[]" not in other, "OtherChannelRow still carries a bare value list"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

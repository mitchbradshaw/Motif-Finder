"""
test_night_analyse_helpers.py
=============================
night-analyse (2026-10-20, the researcher's second list): the pure helpers behind the new Event shape and
Intervals figures and the span-set slideshow's highlighted band (`webui/client/src/analyse/views/eventFigures.ts`).

* **Motif overlay** - each event's waveform z-scored on its own and aligned on its steepest-slope sample (the
  largest |np.gradient|, inside onset -> extremum when the bridge names them: the slope the rose reads).
* **Multi-series scatter** - each measure normalised to 0..1 over its own finite range for display only; a flat
  series sits at 0.5, a missing value stays missing.
* **Class transition matrix** - for each class, the class of the NEXT event in time order, inside one group.
* **Even sampling** - at most `cap` events drawn, spread over the whole set, first and last kept.
* **Slideshow window** - the detection is the band; the window adds about 15 % of its width either side (never
  fewer than 3 samples), clipped to the run's span.

Runs the TypeScript helper under Node (v22.6+ strips types natively); skips without node. Conda or venv python.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = os.path.join(PROJECT_ROOT, "webui", "client", "src", "analyse", "views")
HELPERS_TS = os.path.join(VIEWS, "eventFigures.ts")


def _node(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(HELPERS_TS), "analyse/views/eventFigures.ts is missing"
    url = "file:///" + HELPERS_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as M from {json.dumps(url)};\n(async () => {{ {body} }})()"
              ".then(v => console.log(JSON.stringify(v)), e => { console.error(e); process.exit(1) })")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_steepest_sample_is_the_largest_gradient_like_numpy():
    # a drop: flat, then a fall whose steepest step is between samples 4 and 5, then flat
    out = _node("const v = [0, 0, 0, -1, -2, -6, -7, -7, -7];"
                " return [M.steepestIndex(v), M.steepestIndex(v, 6, 8), M.steepestIndex([1, 1, 1]), M.steepestIndex([])]")
    # np.gradient: [0, 0, -0.5, -1, -2.5, -2.5, -0.5, 0, 0] -> first of the two -2.5 is sample 4
    assert out[0] == 4, out
    assert out[1] == 6, out          # restricted to 6..8: |-0.5| at 6 is the largest
    assert out[2] == 0, out          # a flat trace: no slope, the first sample
    assert out[3] == -1, out


def test_a_spike_aligns_on_its_rise_and_the_waveform_is_zscored():
    out = _node("const t = [10, 11, 12, 13, 14, 15]; const v = [1, 1, 1, 9, 9, 9];"
                " const a = M.alignOnSteepest(t, v, null);"
                " const b = M.alignOnSteepest(t, v, [13, 15]);"
                " return [a, b, M.alignOnSteepest([], [], null)]")
    a = out[0]
    # np.gradient [0, 0, 4, 4, 0, 0] -> sample 2 (t = 12): dt = t - 12
    assert a["dt"] == [-2, -1, 0, 1, 2, 3], a
    z = a["z"]
    assert abs(sum(z)) < 1e-9 and abs(sum(x * x for x in z) / len(z) - 1) < 1e-9, z
    assert out[1]["dt"][0] == -3, out[1]       # inside [13, 15] the steepest is sample 3 (t = 13)
    assert out[2] is None


def test_every_series_is_normalised_on_its_own_range_and_a_gap_stays_a_gap():
    out = _node("return [M.normaliseSeries([2, 4, null, 6, NaN]), M.normaliseSeries([3, 3]), M.normaliseSeries([null])]")
    a = out[0]
    assert a["y"] == [0, 0.5, None, 1, None] and a["lo"] == 2 and a["hi"] == 6, a
    assert out[1]["y"] == [0.5, 0.5], out[1]
    assert out[2]["y"] == [None] and out[2]["lo"] is None, out[2]


def test_the_transition_matrix_counts_what_comes_next_in_time_within_a_group():
    # time order is by t, not by index; the untimed event is skipped; a group boundary is not a transition
    out = _node("const cls = ['small', 'large', 'small', 'small', 'large', 'small'];"
                " const t = [0, 10, 20, 30, null, 5];"
                " const g = ['a', 'a', 'a', 'a', 'a', 'b'];"
                " return [M.transitionMatrix(cls, t, ['small', 'large'], g), M.transitionMatrix(cls, t, ['small', 'large'], null)]")
    m = out[0]
    # group a in time order: small(0) large(10) small(20) small(30) -> s->l, l->s, s->s
    assert m["keys"] == ["small", "large"]
    assert m["counts"] == [[1, 1], [1, 0]], m
    assert m["rowTotal"] == [2, 1]
    assert m["rowPct"][0] == [50, 50] and m["rowPct"][1] == [100, 0], m
    # one group: small(0) small(5) large(10) small(20) small(30) -> s->s, s->l, l->s, s->s
    assert out[1]["counts"] == [[2, 1], [1, 0]], out[1]


def test_a_class_with_no_successor_has_no_percentages():
    out = _node("return M.transitionMatrix(['a', 'b'], [0, 1], ['a', 'b'], null)")
    assert out["counts"] == [[0, 1], [0, 0]] and out["rowPct"][1] == [None, None], out


def test_even_sampling_keeps_the_ends_and_never_exceeds_the_cap():
    out = _node("return [M.evenSample(5, 300), M.evenSample(1000, 300), M.evenSample(0, 10), M.evenSample(10, 1)]")
    assert out[0] == [0, 1, 2, 3, 4]
    s = out[1]
    assert len(s) == 300 and s[0] == 0 and s[-1] == 999 and s == sorted(set(s)), s[:5]
    assert out[2] == [] and out[3] == [0]


def test_the_slideshow_window_is_the_detection_plus_fifteen_percent_each_side():
    out = _node("return [M.slideWindow(100, 200, 1, 0, 1000), M.slideWindow(100, 102, 1, 0, 1000),"
                " M.slideWindow(5, 105, 1, 0, 1000), M.slideWindow(100, 200, 10, 0, 1000)]")
    assert out[0] == [85, 215], out          # 15 % of 100 s
    assert out[1] == [97, 105], out          # 15 % of 2 s is 0.3 s: at least 3 samples (3 s at 1 Hz)
    assert out[2] == [0, 120], out           # clipped to the run's span
    assert out[3] == [85, 215], out


def test_the_time_ramp_runs_from_early_to_late():
    out = _node("return [M.rampColour(0), M.rampColour(1), M.rampColour(0.5), M.rampColour(-3), M.rampColour(7)]")
    assert all(re.fullmatch(r"rgb\(\d+, \d+, \d+\)", c) for c in out), out
    assert out[0] != out[1] and out[3] == out[0] and out[4] == out[1], out


# ── the pages read the helpers (source checks; the browser smoke judges the drawing) ──────────────────────────

def _src(name):
    with open(os.path.join(VIEWS, name), encoding="utf-8") as f:
        return f.read()


def test_the_span_set_slideshow_draws_a_band_not_onset_and_extremum_lines():
    code = _src("SpanSetView.tsx")
    assert "slideWindow(" in code, "spanEvents does not pad its window by the shared 15 % rule"
    body = code[code.index("export function spanEvents"):code.index("export function SpanSlideshow")]
    assert "onset: null" in body and "extremum: null" in body, "the slideshow still draws onset / extremum lines"
    assert "highlight: true" in body, "the detection is not drawn as the highlighted band"


def test_event_shape_leads_with_the_motifs_the_rose_and_the_signal_with_its_scatter():
    reg = _src("registry.tsx")
    assert "EventShapeFigures" in reg, "the Event shape page does not draw the new figures"
    figs = _src("EventShapeFigures.tsx")
    for testid in ("motif-overlay", "event-shape-signal", "measure-scatter"):
        assert testid in figs, f"no {testid} on the Event shape page"


def test_intervals_draw_the_signal_the_class_scatter_and_the_transition_matrix():
    figs = _src("IntervalFigures.tsx")
    for testid in ("interval-signal", "interval-scatter", "class-transitions"):
        assert testid in figs, f"no {testid} on the Intervals page"
    assert "next_within_gap_s" in figs, "the class scatter does not plot the time until the next event of the class"


# ── demo check (2026-10-21): the W1 chain's Event shape step came back from the step cache with no meta (no rose,
#    no rules), and the page fell back to the old histogram view. The view is chosen by the feature table too. ──

def test_an_event_shape_table_is_known_by_its_columns_without_a_rose():
    out = _node("return [M.isEventShapeTable(['polarity', 'onset_idx', 'event_amplitude_mv', 'max_slope_mv_s']),"
                " M.isEventShapeTable(['interval_before_s']), M.isEventShapeTable([]), M.isEventShapeTable(null)]")
    assert out == [True, False, False, False], out


def test_the_page_kind_reads_the_feature_table_and_says_when_the_rose_is_missing():
    reg = _src("registry.tsx")
    kind = reg[reg.index("const kind = cycleStackOf(p)"):]
    kind = kind[:kind.index("\n")]
    assert "isEventShapeTable(" in kind, "the Event shape view is still chosen by the rose alone"
    assert "rose-missing" in _src("EventShapeFigures.tsx"), "a missing rose is not said on the page"

"""
test_whole_drop.py
==================
`Working.interrogation.whole_drop` - drop EVENTS and the WHOLE DROP of each, the researcher's definition
(2026-11-23, approved on the diagram `docs/library_analysis/20261123/whole_drop_vs_steep_core.png`).

A drop event is one unbroken fall: a pause (the trace goes flat) or a rebound (it climbs back) ends it, and the next
fall is the next event. Its whole drop runs from its top to the bottom of its tail. The researcher's own
corrections, rebuilt on synthetic traces (1 Hz, mV, a little seeded noise):

- a steep start with a slow tail is ONE event, to the bottom of the tail;
- a slow decline, a pause and a sharp drop are TWO events;
- a staircase (fall, pause, fall) is TWO events;
- four falls separated by rebounds are FOUR events;
- a span drawn round the start of a long fall holds that fall, run on to its real bottom;
- a window that starts mid-fall keeps the fall's real top, before the window.

Runnable standalone:  python tests/test_whole_drop.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest

from Working.interrogation import whole_drop as WD

FS = 1.0


def trace(*parts, noise=0.01, seed=0):
    """Concatenate ("flat", n, level) / ("ramp", n, from, to) pieces, plus seeded white noise (mV)."""
    out = []
    for p in parts:
        if p[0] == "flat":
            out.append(np.full(p[1], float(p[2])))
        else:
            out.append(np.linspace(float(p[2]), float(p[3]), p[1], endpoint=False))
    x = np.concatenate(out)
    return x + np.random.default_rng(seed).normal(0.0, noise, len(x))


def measure(x, a, b, **kw):
    return WD.measure(x, a, b, FS, to_mv=1.0, **kw)


def depths(m):
    return [round(e["depth_mv"]) for e in m["events"]]


def test_a_steep_start_with_a_slow_tail_is_one_event_to_the_bottom_of_the_tail():
    x = trace(("flat", 300, 0), ("ramp", 10, 0, -8), ("ramp", 200, -8, -10), ("flat", 100, -10),
              ("ramp", 200, -10, 0), ("flat", 300, 0))
    m = measure(x, 250, 520)
    assert m["ok"] and m["n_events"] == 1
    assert m["depth_mv"] == pytest.approx(10.0, abs=0.2)
    assert 297 <= m["top_idx"] <= 302 and 505 <= m["bottom_idx"] <= 515
    assert m["half_recovery_s"] == pytest.approx(200.0, abs=8)          # 100 s flat + half of a 200 s recovery


def test_a_slow_decline_a_pause_and_a_sharp_drop_are_two_events():
    x = trace(("flat", 200, 0), ("ramp", 1200, 0, -6), ("flat", 100, -6), ("ramp", 20, -6, -15),
              ("flat", 300, -15))
    m = measure(x, 150, 1600)
    assert depths(m) == [6, 9] and m["n_events"] == 2
    assert m["depth_mv"] == pytest.approx(9.0, abs=0.2)                 # the span's main event is the deepest
    assert 1495 <= m["top_idx"] <= 1502


def test_a_staircase_is_two_events():
    x = trace(("flat", 200, 0), ("ramp", 10, 0, -3), ("flat", 150, -3), ("ramp", 10, -3, -6), ("flat", 200, -6))
    assert depths(measure(x, 150, 450)) == [3, 3]


def test_four_falls_separated_by_rebounds_are_four_events():
    x = trace(("flat", 200, 0), ("ramp", 10, 0, -6), ("ramp", 10, -6, -4), ("ramp", 10, -4, -7),
              ("ramp", 10, -7, -6), ("ramp", 10, -6, -8), ("ramp", 30, -8, -5), ("ramp", 10, -5, -9),
              ("flat", 200, -9))
    m = measure(x, 150, 330)
    assert depths(m) == [6, 3, 2, 4]
    assert m["depth_mv"] == pytest.approx(6.0, abs=0.2)


def test_a_window_that_starts_mid_fall_keeps_the_falls_real_top():
    x = trace(("flat", 400, 0), ("ramp", 400, 0, -40), ("ramp", 400, -40, 0), ("flat", 400, 0))
    m = measure(x, 500, 1000)                                           # the fall began 100 s before the window
    assert m["n_events"] == 1 and m["top_extended"]
    assert 395 <= m["top_idx"] <= 405 and m["depth_mv"] == pytest.approx(40.0, abs=0.5)


def test_a_span_round_the_start_of_a_long_fall_holds_it_and_its_real_bottom():
    x = trace(("flat", 500, 0), ("ramp", 500, 0, -10), ("flat", 500, -10))
    m = measure(x, 450, 800)                                            # 60 % of the fall's depth is inside
    assert m["n_events"] == 1 and m["bottom_extended"]
    assert 995 <= m["bottom_idx"] <= 1005 and m["depth_mv"] == pytest.approx(10.0, abs=0.2)


def test_a_neighbour_that_only_begins_in_the_spans_last_moments_is_not_its_event():
    x = trace(("flat", 300, 0), ("ramp", 20, 0, -5), ("flat", 300, -5), ("ramp", 100, -5, -25), ("flat", 300, -25))
    m = measure(x, 250, 630)                                            # holds A whole and 10 % of B's depth
    assert m["n_events"] == 1 and m["depth_mv"] == pytest.approx(5.0, abs=0.2)


def test_a_wiggle_under_a_sixth_of_the_spans_deepest_drop_is_not_an_event():
    x = trace(("flat", 200, 0), ("ramp", 10, 0, -10), ("ramp", 30, -10, -8), ("ramp", 10, -8, -9),
              ("flat", 200, -9))
    assert depths(measure(x, 150, 300)) == [10]


def test_noise_alone_holds_no_event():
    x = trace(("flat", 600, 0), noise=0.05)
    m = measure(x, 100, 500)
    assert not m["ok"] and m["why"] == "no_fall" and m["n_events"] == 0


def test_a_rise_first_window_is_flagged_and_spike_polarity_measures_the_rise():
    x = trace(("flat", 200, 0), ("ramp", 50, 0, 8), ("ramp", 300, 8, 6), ("flat", 200, 6))
    m = measure(x, 150, 600)
    assert m["rise_dominated"] and m["polarity"] == -1
    s = measure(x, 150, 600, polarity="spike")
    assert s["polarity"] == 1 and s["depth_mv"] == pytest.approx(8.0, abs=0.2)


def test_a_recovery_is_never_searched_into_the_next_event():
    x = trace(("flat", 200, 0), ("ramp", 10, 0, -10), ("ramp", 40, -10, -6), ("ramp", 10, -6, -16),
              ("ramp", 200, -16, 0), ("flat", 200, 0))
    m = measure(x, 150, 300)
    first = m["events"][0]
    assert np.isnan(first["half_recovery_s"])                           # back to -5 never happens before the second
    # the second falls 10 mV (-6 to -16): half recovery is -11, 5 mV up a 0.08 mV/s climb
    assert m["events"][1]["depth_mv"] == pytest.approx(10.0, abs=0.2)
    assert m["events"][1]["half_recovery_s"] == pytest.approx(62.5, abs=4)


def test_span_events_lists_every_event_of_a_long_span():
    x = trace(("flat", 100, 0), *[p for k in range(5) for p in (("ramp", 10, -k, -k - 4), ("ramp", 40, -k - 4, -k - 1))],
              ("flat", 100, -5))
    ev = WD.span_events(x, 0, len(x), FS, to_mv=1.0)
    assert len(ev) == 5 and all(e["depth_mv"] == pytest.approx(4.0, abs=0.2) for e in ev)
    assert all(ev[i]["bottom_idx"] < ev[i + 1]["top_idx"] + 2 for i in range(4))


def test_an_unknown_polarity_is_refused():
    with pytest.raises(ValueError):
        measure(trace(("flat", 100, 0)), 0, 100, polarity="sideways")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

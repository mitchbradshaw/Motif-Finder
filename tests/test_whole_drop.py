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


def test_a_sharp_fall_with_a_slow_settle_is_one_event_when_noise_flattens_its_first_seconds():
    """Auto-detect's drop B (M4 CH1 63:36-64:06 h shape, seed 21): one noise-flat second right after a 3 s fall was
    15 % of the event so far - a 'pause' - and the 247 s settle came out as an event of its own. A pause is at least
    PAUSE_MIN_S long."""
    x = trace(("flat", 300, 0.6), ("ramp", 3, 0.6, -2.8), ("ramp", 247, -2.8, -3.7), ("ramp", 650, -3.7, 0),
              ("flat", 300, 0), noise=0.02, seed=21)
    for seed in range(6):
        y = x + np.random.default_rng(100 + seed).normal(0.0, 0.02, len(x))
        m = measure(y, 295, 600)
        assert m["n_events"] == 1 and m["depth_mv"] == pytest.approx(4.3, abs=0.15), seed
        assert 540 <= m["bottom_idx"] <= 552, seed


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


def test_a_slow_decline_running_straight_into_a_sharp_drop_is_two_events():
    """No pause between them (accepted spans 0b74cddd, 4a863d57, 752b0182, b7483034): the slow decline is its own
    event and the sharp drop starts where the fall suddenly steepens."""
    x = trace(("flat", 300, 0), ("ramp", 1200, 0, -6), ("ramp", 15, -6, -20), ("flat", 300, -20))
    assert [round(e["depth_mv"]) for e in WD.span_events(x, 0, len(x), FS, to_mv=1.0)] == [6, 14]
    m = measure(x, 1400, 1600)
    assert m["depth_mv"] == pytest.approx(14.0, abs=0.3) and 1495 <= m["top_idx"] <= 1502


def test_a_drops_slow_tail_running_into_a_second_sharp_drop_is_two_events():
    """M4 873cd70d, M2_aug d3ac70db, f238e01e: the tail has slowed to a crawl when a second sharp drop begins."""
    x = trace(("flat", 300, 0), ("ramp", 10, 0, -10), ("ramp", 600, -10, -12), ("ramp", 10, -12, -22),
              ("ramp", 300, -22, -23), ("flat", 300, -23))
    assert [round(e["depth_mv"]) for e in WD.span_events(x, 0, len(x), FS, to_mv=1.0)] == [12, 11]
    assert measure(x, 250, 1300)["n_events"] == 2


def test_a_drop_that_is_still_falling_fast_and_speeds_up_is_one_event():
    """M2_concat 082f06a6 / M2_aug 62b336c8: a fall that eases to 30 % of its pace and plunges again had not become a
    tail; a lead-in under LEAD_MERGE_FRAC of the drop it runs into is its shoulder (SO CH2, the researcher's
    first rebound-separated fall)."""
    x = trace(("flat", 300, 0), ("ramp", 10, 0, -10), ("ramp", 100, -10, -40), ("ramp", 10, -40, -55),
              ("flat", 300, -55))
    assert [round(e["depth_mv"]) for e in WD.span_events(x, 0, len(x), FS, to_mv=1.0)] == [55]
    shoulder = trace(("flat", 300, 0), ("ramp", 60, 0, -1), ("ramp", 10, -1, -11), ("flat", 300, -11))
    m = measure(shoulder, 250, 450)
    assert m["n_events"] == 1 and m["depth_mv"] == pytest.approx(11.0, abs=0.3) and 295 <= m["top_idx"] <= 305


def test_a_clear_climb_ends_even_a_very_deep_drop():
    """M2_aug cf7ceb24: after a 105 mV artifact spike in the context, nothing short of a 10 mV climb ended it and the
    real 1.2 mV drop in the span was swallowed. A climb of REBOUND_SIGMAS noise-widths ends any drop."""
    x = trace(("flat", 300, 0), ("ramp", 10, 0, -100), ("flat", 200, -100), ("ramp", 10, -100, -98), ("flat", 100, -98),
              ("ramp", 10, -98, -99.5), ("flat", 300, -99.5))
    m = measure(x, 600, 700)
    assert m["ok"] and m["depth_mv"] == pytest.approx(1.5, abs=0.1)


def test_a_span_holds_a_sharp_drop_whose_tail_runs_far_past_it():
    """LM 2a1dc6b4, M2_concat 8d1f50aa: the span is drawn round a sharp drop whose slow tail runs on for an hour, so
    most of the whole drop's depth lies outside it - but the moment it falls fastest is inside."""
    x = trace(("flat", 300, 0), ("ramp", 20, 0, -4), ("ramp", 3000, -4, -20), ("flat", 300, -20))
    m = measure(x, 250, 600)
    assert m["ok"] and m["n_events"] == 1 and m["depth_mv"] == pytest.approx(20.0, abs=0.5)
    assert 295 <= m["top_idx"] <= 305


def test_a_step_on_a_slide_that_was_already_there_is_the_step_alone():
    """The researcher, 23 Nov (Q1, LM 99f61fa6 / 725bbdbe): the trace slides steadily, steps down, settles, and slides
    on at the same pace. The drop is the step - from where it leaves the slide to where it is back on it - not the
    step plus an hour of slide."""
    x = trace(("flat", 300, 0), ("ramp", 1200, 0, -2), ("ramp", 10, -2, -5), ("ramp", 60, -5, -5.5),
              ("ramp", 3000, -5.5, -10.5), ("flat", 300, -10.5))
    m = measure(x, 1450, 1650)
    assert m["depth_mv"] == pytest.approx(3.7, abs=0.4) and 1490 <= m["top_idx"] <= 1505
    assert m["bottom_idx"] <= 1750


def test_a_drop_with_nothing_sliding_before_it_keeps_its_whole_tail_and_flags_it_long():
    """The researcher, 23 Nov (Q2): a long tail after a sharp drop is the drop's, to its bottom (M4 CH1's 80-minute
    tail), and flagged `long_tail` - over LONG_TAIL_MULT x its steep part - so a plot can leave it out. A shoulder
    accelerating into a drop is no slide (Q1 does not apply)."""
    x = trace(("flat", 300, 0), ("ramp", 120, 0, -1.5), ("ramp", 20, -1.5, -6), ("ramp", 1800, -6, -9),
              ("flat", 300, -9))
    m = measure(x, 250, 600)
    assert m["n_events"] == 1 and m["depth_mv"] == pytest.approx(9.0, abs=0.3) and m["long_tail"]
    short = measure(trace(("flat", 300, 0), ("ramp", 20, 0, -6), ("ramp", 40, -6, -6.5), ("flat", 300, -6.5)), 250, 500)
    assert not short["long_tail"] and short["steep_s"] == pytest.approx(20, abs=8)


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


def test_a_sharp_drop_with_a_slow_recovery_keeps_its_half_recovery():
    """Auto-detect, 23 Nov: the half-recovery search stopped after ten fall times, so a shark fin falling in a few
    seconds lost the recovery it reached 80 s later while the same fin falling in 10 s kept it. Only the next event
    and RECOVERY_MAX_S bound the search."""
    for fall in (2, 4, 10):
        t = np.arange(900)
        x = np.concatenate([np.zeros(300), np.linspace(0, -5, fall, endpoint=False),
                            -5 * np.exp(-t * np.log(2) / 80), np.zeros(300)])
        x = x + np.random.default_rng(1).normal(0, 0.02, len(x))
        m = measure(x, 290, 400)
        assert m["n_events"] == 1 and m["half_recovery_s"] == pytest.approx(80.0, abs=5), fall


def test_span_events_lists_every_event_of_a_long_span():
    teeth = [p for k in range(5) for p in (("ramp", 10, -k, -k - 4), ("ramp", 40, -k - 4, -k - 1))]
    x = trace(("flat", 100, 0), *teeth, ("flat", 100, -5))
    ev = WD.span_events(x, 0, len(x), FS, to_mv=1.0)
    assert len(ev) == 5 and all(e["depth_mv"] == pytest.approx(4.0, abs=0.2) for e in ev)
    assert all(ev[i]["bottom_idx"] < ev[i + 1]["top_idx"] + 2 for i in range(4))


def test_a_slow_continuous_decline_with_brief_hesitations_is_one_event():
    """Auto-detect, 23 Nov (M4 CH1, 281:22-283:00 h): on a quiet channel a long decline has brief flat hesitations;
    each one ended the event and the drop came out in four. A hesitation is not a pause: it is short against the
    drop it interrupts and the fall carries on at the same pace."""
    parts, level = [("flat", 300, 0)], 0.0
    for _ in range(10):
        parts += [("ramp", 490, level, level - 5), ("flat", 10, level - 5)]
        level -= 5
    x = trace(*parts, ("flat", 300, level), noise=0.01)
    m = measure(x, 250, 5400)
    assert m["n_events"] == 1 and m["depth_mv"] == pytest.approx(50.0, abs=0.5)


def test_a_drop_that_has_flattened_into_wiggles_ends_at_its_last_new_low():
    """Auto-detect, 23 Nov (M4 CH1, 282:45 h): the drop flattens, the trace wiggles up and down by a few tenths of a
    mV, then drifts slowly lower for an hour. Counted piece by piece, each wiggle's fall carried the drop on, into the
    drift; only a fall to a new low is the drop going on."""
    wiggle = [p for _ in range(15) for p in (("ramp", 30, -20, -19.7), ("ramp", 30, -19.7, -20))]
    x = trace(("flat", 300, 0), ("ramp", 600, 0, -20), *wiggle, ("ramp", 1800, -20, -22.5), ("flat", 300, -22.5))
    for m in (measure(x, 250, 950), {"events": WD.span_events(x, 250, 950, FS, to_mv=1.0)}):
        assert [round(e["depth_mv"]) for e in m["events"]] == [20]
        assert 890 <= m["events"][0]["bottom_idx"] <= 910


def test_span_events_reads_context_so_an_edge_event_keeps_its_real_top():
    x = trace(("flat", 400, 0), ("ramp", 400, 0, -40), ("ramp", 400, -40, 0), ("flat", 400, 0))
    ev = WD.span_events(x, 500, 1000, FS, to_mv=1.0)                  # the fall began 100 s before the span
    assert len(ev) == 1 and 395 <= ev[0]["top_idx"] <= 405 and ev[0]["depth_mv"] == pytest.approx(40.0, abs=0.5)


def test_one_fall_gives_one_answer_whatever_window_it_is_measured_in():
    """Auto-detect, 23 Nov: re-measuring a candidate in its own box moved its top or bottom for a third to a half of
    candidates. The noise is read from a fixed stretch round the window and every window gets context."""
    x = trace(("flat", 2000, 0), ("ramp", 300, 0, -12), ("ramp", 600, -12, -14), ("flat", 2000, -14), noise=0.02)
    got = [measure(x, a, b) for a, b in ((1990, 2320), (1900, 2400), (1500, 3500), (2050, 2250))]
    # a box round the onset alone holds 17 % of the fall's depth - not its span - unless it names its moment
    got.append(measure(x, 1990, 2060, anchor=2010))
    assert measure(x, 1990, 2060)["why"] == "no_fall"
    assert all(m["ok"] and m["n_events"] == 1 for m in got)
    tops, bottoms = [m["top_idx"] for m in got], [m["bottom_idx"] for m in got]
    depths = [m["depth_mv"] for m in got]
    # the tail's last seconds fall by under 2 sigma, so its exact bottom is noise-ambiguous: 2 % of the 900 s fall
    assert max(tops) - min(tops) <= 3 and max(bottoms) - min(bottoms) <= 18
    assert max(depths) - min(depths) <= 0.1 and all(d == pytest.approx(14.0, abs=0.3) for d in depths)


def test_an_anchor_picks_its_own_event_next_to_a_deeper_one():
    """A machine box names the moment it is about; its event is the one there, even beside a deeper drop (whose
    15 % floor would otherwise remove it)."""
    x = trace(("flat", 300, 0), ("ramp", 20, 0, -1.5), ("ramp", 60, -1.5, 0), ("flat", 40, 0), ("ramp", 20, 0, -13),
              ("flat", 300, -13))
    assert measure(x, 280, 460)["depth_mv"] == pytest.approx(13.0, abs=0.3)
    m = measure(x, 280, 460, anchor=310)
    assert m["depth_mv"] == pytest.approx(1.5, abs=0.2) and 298 <= m["top_idx"] <= 302


def test_an_unknown_polarity_is_refused():
    with pytest.raises(ValueError):
        measure(trace(("flat", 100, 0)), 0, 100, polarity="sideways")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

"""
test_webui_night_b_polish.py
============================
night-b, small polish found driving the Library on the night fixture (source-level; conda python):

* a kept label-chain family's id is its whole chain (`F-09.F-11.F-08…`, 26 labels on the fixture), one token with
  no break, and the Library section bar's breadcrumb printed it in full across the *Templates* tab;
* Build sequences' preview said "1 sequences in 1 label chains".
"""
import io
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(PROJECT_ROOT, "webui", "client", "src", "library")


def _read(name):
    return io.open(os.path.join(LIB, name), encoding="utf-8").read()


def test_the_library_crumb_ellipsises_a_long_id():
    css = _read("library.css")
    m = re.search(r'\[data-testid="library-crumbs"\][^{]*\.cur[^{]*\{([^}]*)\}', css)
    assert m, "library.css has no rule for the section bar crumb's current item"
    body = m.group(1)
    for decl in ("text-overflow: ellipsis", "overflow: hidden", "white-space: nowrap"):
        assert decl in body, decl


def test_build_sequences_counts_in_the_singular_when_there_is_one():
    src = _read("BuildSequences.tsx")
    assert "sequences in {fmtInt(preview.families.length)} label chains" not in src


def test_the_intervals_within_control_has_one_all():
    """With nothing to colour by, the bridge's one class IS `all`, and the control listed its own *all* plus that
    one: two "all" buttons (and two React children keyed `all`). Seen on the one-event intervals page."""
    src = io.open(os.path.join(PROJECT_ROOT, "webui", "client", "src", "analyse", "views", "IntervalTimeline.tsx"),
                  encoding="utf-8").read()
    assert "...ic.classes.filter(c => c.key !== 'all')]" in src


def test_no_events_is_said_as_no_events():
    """The zero-event intervals page said "no family on every event, and no depth or score measured"."""
    import sys
    for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import numpy as np
    import pandas as pd
    from Adapters.registry import discover_adapters, get_adapter
    from server.serialize import to_payload
    from Working.types import SpanSet
    discover_adapters()
    spec = get_adapter("interrogation.intervals")
    ss = SpanSet(starts=(), ends=(), features=pd.DataFrame({"event_amplitude_mv": []}))
    res = spec.run(np.zeros(10), np.arange(10.0), 1.0, value=ss, **spec.validate_params({}))
    ic = to_payload("spanset", res.value, res.meta, {"fs": 1.0, "span_start": 0})["interval_classes"]
    assert ic["rule"] == "none"
    assert ic["rule_words"] == "nothing to colour: the span holds no event", ic["rule_words"]

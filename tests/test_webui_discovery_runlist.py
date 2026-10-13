"""
test_webui_discovery_runlist.py
===============================
fixup-unpick: the run list's two trailing controls must not sit on top of each other.

Since `fixup-rq2` (0152df5) every Discovery run row carries a *remove from this
session* button (`remove-<key>`, `.dsc-run-remove`) beside the A/B pick button
(`pick-<key>`, `.dsc-pick`). The remove button was positioned absolutely in the
row's top-right corner — exactly where the pick button already sat — so at
1440 px the two overlapped (pick x 340–360, remove x 346–364) and the remove
button intercepted every click meant for the badge: B could not be unpicked in
the run list, and a click on the B badge removed the run from the session.
The smoke state `discovery.compare--unpick-b` fails on this with a 30 s click
timeout.

The behaviour is geometric, so the pin is measured in a real browser by the
smoke gate, the same way `test_webui_plot_domain.py` pins "no trace leaves its
plot box". This file asserts that the gate measures it:

* `webui/smoke.py` implements a generic `no_overlap` state assertion — a list
  of selector pairs whose bounding boxes must not intersect (a selector that
  matches nothing fails too, so the assertion cannot pass vacuously);
* `webui/smoke_pages/discovery.json` carries a Compare state that names the
  remove and pick controls of the B run under it.

There is no Node test runner in this repo (the client's gate is `tsc -b`,
`npm run build` and `webui/smoke.py`), so the layout itself is not run here.
"""
from __future__ import annotations

import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMOKE = os.path.join(PROJECT_ROOT, "webui", "smoke.py")
MANIFEST = os.path.join(PROJECT_ROOT, "webui", "smoke_pages", "discovery.json")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_smoke_measures_that_two_controls_do_not_overlap():
    smoke = _read(SMOKE)
    assert "no_overlap" in smoke, "smoke.py has no `no_overlap` state assertion"
    assert re.search(r"def no_overlap\(self, page", smoke), "the assertion is a Smoke method, like traces_in_box"
    # the measurement is a bounding-box intersection in the browser, and a selector that matches nothing is a failure
    assert "getBoundingClientRect" in smoke
    assert re.search(r"no_overlap.*?matched nothing|matched nothing.*?no_overlap", smoke, re.S), \
        "a selector that matches nothing must fail the state, or an absent control passes vacuously"


def test_the_compare_page_pins_the_remove_and_pick_controls_apart():
    with open(MANIFEST, encoding="utf-8") as fh:
        states = json.load(fh)
    pinned = [e for e in states if e.get("no_overlap")]
    assert pinned, "no discovery state carries a `no_overlap` assertion"
    compare = [e for e in pinned if e["page"] == "discovery.compare" and "{run:b}" in e["hash"]]
    assert compare, "the pin must live on the Compare page with both runs picked — the page where B is unpicked"
    pairs = [tuple(p) for e in compare for p in e["no_overlap"]]
    assert any('remove-{run:b}' in a and 'pick-{run:b}' in b or 'pick-{run:b}' in a and 'remove-{run:b}' in b
               for a, b in pairs), f"the pair must name run B's remove and pick controls, got {pairs}"
    # the unpick state itself is still the behavioural check: B is unpicked by a click on its badge
    unpick = [e for e in states if e["page"] == "discovery.compare" and e["state"] == "unpick-b"]
    assert unpick and any(a.get("click") == '[data-testid="pick-{run:b}"]' for a in unpick[0]["actions"])
    assert '[data-testid="compare-empty"]' in unpick[0]["expect"]

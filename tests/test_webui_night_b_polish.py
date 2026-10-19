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

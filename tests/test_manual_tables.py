"""
test_manual_tables.py
=====================
`scripts/manual_tables.py` writes the parts of the user manual (`docs/manual/`)
that are read off the adapter registry -- each block's metadata and parameter
table, and the catalogue that orders them -- and creates the hand-written stubs
a block's card and appendix entry start from. These tests pin the three
promises the manual leans on: registry text reaches LaTeX escaped (or the
script refuses loudly), a regenerate never touches hand-written prose, and
`--check` reports drift without writing anything.
"""

import importlib.util
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.base import AdapterSpec, ParamSpec, SideInputSpec  # noqa: E402


def _load():
    path = os.path.join(PROJECT_ROOT, "scripts", "manual_tables.py")
    spec = importlib.util.spec_from_file_location("manual_tables", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mt = _load()


def _run(x, t, fs, width_s=2.5):
    return None


def _run_units(x, t, fs, units=None):
    return None


def _spec(**over):
    kw = dict(
        name="detection.fake_thing",
        display_name="Fake thing (Doe 2020)",
        stage="detection",
        params=[ParamSpec("width_s", float, 2.5, "Window width (s) & more", min=0.0)],
        run=_run,
        output_kind="spanset",
        category="detect",
        page_name="Fake thing",
        description="Finds 50% of things.",
    )
    kw.update(over)
    return AdapterSpec(**kw)


# -- escaping -----------------------------------------------------------------

def test_escape_handles_every_latex_special():
    assert mt.latex_escape(r"a_b & c% $d# {e} ~f ^g \h") == (
        r"a\_b \& c\% \$d\# \{e\} \textasciitilde{}f \textasciicircum{}g \textbackslash{}h"
    )


def test_escape_maps_the_symbols_the_registry_uses():
    assert mt.latex_escape("k × robust σ") == r"k \ensuremath{\times} robust \ensuremath{\sigma}"
    assert mt.latex_escape("Signal → SpanSet — done") == r"Signal \ensuremath{\to} SpanSet --- done"
    assert mt.latex_escape("Ω(τ) ≥ −1") == (
        r"\ensuremath{\Omega}(\ensuremath{\tau}) \ensuremath{\geq} \ensuremath{-}1"
    )


def test_escape_passes_accented_latin_through():
    assert mt.latex_escape("Selesnick & Duval, Fréchet") == r"Selesnick \& Duval, Fréchet"


def test_escape_refuses_an_unmapped_character_loudly():
    with pytest.raises(ValueError, match=r"U\+2603"):
        mt.latex_escape("a snowman ☃ here")


# -- the parameter table's cells ----------------------------------------------

@pytest.mark.parametrize("param, expected", [
    (ParamSpec("w", int, 20, "", min=1), "whole number, at least 1"),
    (ParamSpec("w", int, 20, "", max=10), "whole number, at most 10"),
    (ParamSpec("p", float, 0.5, "", min=0.0, max=1.0), "number from 0 to 1"),
    (ParamSpec("x", float, 1.0, ""), "any number"),
    (ParamSpec("m", str, "a", "", choices=["a", "b_c"]), r"one of \texttt{a}, \texttt{b\_c}"),
    (ParamSpec("o", int, 1, "", choices=[1, 2]), "one of 1, 2"),
    (ParamSpec("f", bool, True, ""), "yes or no"),
    (ParamSpec("s", str, "", ""), "text"),
])
def test_allowed_text_reads_type_range_and_choices(param, expected):
    assert mt.allowed_text(param) == expected


@pytest.mark.parametrize("value, expected", [
    (True, "yes"), (False, "no"), (None, "none"), ("abs", r"\texttt{abs}"),
    ("", r"\textit{empty}"), (0.01, "0.01"), (20, "20"), (2.0, "2.0"), ([1, 2], "1, 2"),
])
def test_format_default(value, expected):
    assert mt.format_default(value) == expected


# -- one block's generated file -----------------------------------------------

def test_render_block_carries_names_kinds_description_and_rows():
    out = mt.render_block(_spec(), module_path="Adapters/detection_fake_thing.py")
    assert r"\ubblock{detection.fake_thing}" in out
    assert "{Fake thing}" in out and "{Fake thing (Doe 2020)}" in out
    assert "{detect}" in out and "{Signal}" in out and "{SpanSet}" in out
    assert r"{Adapters/detection\_fake\_thing.py}" in out
    assert r"Finds 50\% of things." in out
    assert r"\ubparam{width\_\allowbreak{}s}{2.5}{number, at least 0}{Window width (s) \& more}" in out


def test_render_block_flags_what_the_spec_declares():
    out = mt.render_block(
        _spec(run=_run_units, params=[], source=True, max_span_samples=1000,
              known_broken="kymatio no longer imports",
              side_inputs=[SideInputSpec("exemplar", "signal", ["library_exemplar"], required=False)]),
        module_path="Adapters/x.py",
    )
    assert r"\ubflag{source}" in out
    assert r"\ubflag{units}" in out
    assert r"\ubflag{maxspan}{1000}" in out
    assert r"\ubblockbroken{detection.fake_thing}{kymatio no longer imports}" in out
    assert r"\ubsideinput{exemplar}{Signal}{a library exemplar}{optional}" in out
    assert r"\ubparam" not in out  # no settings: the table says so instead of an empty grid


def test_split_name_refuses_a_name_without_a_stage():
    assert mt.split_name("detection.fake_thing") == ("detection", "fake_thing")
    with pytest.raises(ValueError):
        mt.split_name("nostage")


def test_catalogue_follows_the_insert_modal_tab_order():
    specs = [
        _spec(name="detection.b", page_name="Beta", category="detect"),
        _spec(name="preprocessing.z", page_name="Zed", stage="preprocessing", category="preprocess"),
        _spec(name="detection.a", page_name="alpha", category="detect"),
    ]
    out = mt.render_catalogue(specs)
    order = [line for line in out.splitlines() if line.startswith("\\ub")]
    assert order == [
        r"\ubblocktotal{3}",
        r"\ubcategory{preprocess}{1}",
        r"\ubcatalogueitem{preprocessing.z}",
        r"\ubcategory{detect}{2}",
        r"\ubcatalogueitem{detection.a}",
        r"\ubcatalogueitem{detection.b}",
    ]


# -- writing to disk ------------------------------------------------------------

def test_build_writes_generated_files_and_never_overwrites_handwritten(tmp_path):
    spec = _spec()
    mt.build([spec], manual_root=tmp_path, repo_root=PROJECT_ROOT, write=True)

    generated = tmp_path / "generated" / "blocks" / "detection" / "fake_thing.tex"
    card = tmp_path / "blocks" / "detection" / "fake_thing" / "card.tex"
    entry = tmp_path / "blocks" / "detection" / "fake_thing" / "entry.tex"
    assert generated.exists() and (tmp_path / "generated" / "catalogue.tex").exists()
    assert r"\cardfield{What it does}" in card.read_text(encoding="utf-8")
    assert r"\entryfield{Algorithm}" in entry.read_text(encoding="utf-8")

    card.write_text("HAND WRITTEN", encoding="utf-8")
    spec.params[0].description = "changed in the code"
    report = mt.build([spec], manual_root=tmp_path, repo_root=PROJECT_ROOT, write=True)
    assert card.read_text(encoding="utf-8") == "HAND WRITTEN"
    assert "changed in the code" in generated.read_text(encoding="utf-8")
    assert report.stubs_created == []


def test_check_reports_drift_and_orphans_without_writing(tmp_path):
    spec = _spec()
    mt.build([spec], manual_root=tmp_path, repo_root=PROJECT_ROOT, write=True)
    generated = tmp_path / "generated" / "blocks" / "detection" / "fake_thing.tex"
    before = generated.read_text(encoding="utf-8")

    spec.params[0].description = "drifted"
    (tmp_path / "blocks" / "detection" / "gone").mkdir(parents=True)
    report = mt.build([spec], manual_root=tmp_path, repo_root=PROJECT_ROOT, write=False)

    assert "generated/blocks/detection/fake_thing.tex" in report.stale
    assert "blocks/detection/gone" in report.orphans
    assert generated.read_text(encoding="utf-8") == before
    assert not report.ok


def test_every_registered_block_renders(tmp_path):
    """The live registry: every block's strings escape cleanly. If this fails on
    an unmapped character, add it to UNICODE_MAP in scripts/manual_tables.py."""
    from Adapters.registry import discover_adapters
    specs = discover_adapters()
    report = mt.build(specs, manual_root=tmp_path, repo_root=PROJECT_ROOT, write=True)
    catalogue = (tmp_path / "generated" / "catalogue.tex").read_text(encoding="utf-8")
    for spec in specs:
        stage, short = mt.split_name(spec.name)
        assert (tmp_path / "generated" / "blocks" / stage / f"{short}.tex").exists()
        assert catalogue.count(f"\\ubcatalogueitem{{{spec.name}}}") == 1
    assert report.ok

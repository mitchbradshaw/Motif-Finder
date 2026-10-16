"""
manual_tables.py
================
Writes the parts of the user manual (`docs/manual/`) that are read off the
adapter registry instead of written by hand, so they cannot drift from the
code, and creates the stubs a block's hand-written text starts from:

    generated/blocks/<stage>/<short>.tex   one block: what the app calls it, its
                                           registry name, category, input and
                                           output types, flags, side inputs, the
                                           registry's own description and every
                                           parameter (default, allowed values,
                                           description)
    generated/blocks.tex                   inputs every block file above
    generated/catalogue.tex                every block once, grouped in the
                                           insert modal's tab order
    generated/version.tex                  the commit the tables were read from
    blocks/<stage>/<short>/card.tex        hand-written; created as a stub only
    blocks/<stage>/<short>/entry.tex       when missing, never overwritten

Usage, from the repo root with the conda python:

    python scripts/manual_tables.py            regenerate, create missing stubs
    python scripts/manual_tables.py --check    write nothing; exit 1 if a generated
                                               file is stale, a block lacks its card
                                               or entry, or a hand-written folder
                                               names no registered block

A character the escaper has no mapping for is refused with its code point, so a
symbol never reaches the PDF as a blank or a compile error three steps later:
add it to UNICODE_MAP. The manual itself is described in docs/manual/README.md.
"""

import argparse
import datetime
import inspect
import pathlib
import pkgutil
import subprocess
import sys
from dataclasses import dataclass, field

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import Working.types as _types  # noqa: E402
from Adapters.base import CATEGORIES  # noqa: E402

MANUAL_ROOT = REPO_ROOT / "docs" / "manual"

# 'spanset' -> 'SpanSet': the interchange types as the code and the UI spell them.
KIND_LABEL = {name.lower(): name for name in _types.__all__}

SOURCE_TEXT = {
    "root_signal": "the chain's own signal",
    "earlier_step": "an earlier step",
    "library_exemplar": "a library exemplar",
}

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&",
    "#": r"\#", "%": r"\%", "_": r"\_", "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
}


def _math(command):
    return r"\ensuremath{" + command + "}"


UNICODE_MAP = {
    "\u2014": "---", "\u2013": "--", "\u2500": "---", "\u2026": r"\ldots{}",
    "\u2018": "`", "\u2019": "'", "\u201c": "``", "\u201d": "''", "\u00a0": "~",
    "\u00b7": r"\textperiodcentered{}", "\u00a7": r"\S{}", "\u00b0": r"\textdegree{}",
    "\u203a": r"\guilsinglright{}", "\u2039": r"\guilsinglleft{}",
    "\u00d7": _math(r"\times"), "\u00f7": _math(r"\div"), "\u2212": _math("-"),
    "\u00b1": _math(r"\pm"), "\u00b2": _math("^2"), "\u00b3": _math("^3"),
    "\u00b5": _math(r"\mu"), "\u2192": _math(r"\to"), "\u2190": _math(r"\leftarrow"),
    "\u2194": _math(r"\leftrightarrow"), "\u21d2": _math(r"\Rightarrow"),
    "\u2248": _math(r"\approx"), "\u2264": _math(r"\leq"), "\u2265": _math(r"\geq"),
    "\u2260": _math(r"\neq"), "\u221a": _math(r"\surd"), "\u221e": _math(r"\infty"),
    "\u2032": _math(r"^\prime"), "\u2208": _math(r"\in"), "\u2211": _math(r"\sum"),
}
_GREEK = {
    "\u03b1": "alpha", "\u03b2": "beta", "\u03b3": "gamma", "\u03b4": "delta",
    "\u03b5": "varepsilon", "\u03b6": "zeta", "\u03b7": "eta", "\u03b8": "theta",
    "\u03b9": "iota", "\u03ba": "kappa", "\u03bb": "lambda", "\u03bc": "mu",
    "\u03bd": "nu", "\u03be": "xi", "\u03c0": "pi", "\u03c1": "rho", "\u03c2": "varsigma",
    "\u03c3": "sigma", "\u03c4": "tau", "\u03c5": "upsilon", "\u03c6": "varphi",
    "\u03c7": "chi", "\u03c8": "psi", "\u03c9": "omega", "\u0393": "Gamma",
    "\u0394": "Delta", "\u0398": "Theta", "\u039b": "Lambda", "\u039e": "Xi",
    "\u03a0": "Pi", "\u03a3": "Sigma", "\u03a5": "Upsilon", "\u03a6": "Phi",
    "\u03a8": "Psi", "\u03a9": "Omega",
}
UNICODE_MAP.update({ch: _math("\\" + name) for ch, name in _GREEK.items()})


def latex_escape(text):
    """Registry text -> LaTeX. Runs of whitespace collapse to one space (a blank
    line inside a macro argument would end the paragraph). Accented Latin letters
    pass through (inputenc + T1 set them); any other non-ASCII character must be
    in UNICODE_MAP, or this raises naming its code point."""
    text = " ".join(str(text).split())
    out = []
    for ch in text:
        if ch in LATEX_SPECIALS:
            out.append(LATEX_SPECIALS[ch])
        elif ord(ch) < 128:
            out.append(ch)
        elif ch in UNICODE_MAP:
            out.append(UNICODE_MAP[ch])
        elif ch.isalpha() and 0xC0 <= ord(ch) <= 0x24F:
            out.append(ch)
        else:
            raise ValueError(
                f"no LaTeX mapping for {ch!r} (U+{ord(ch):04X}) in {text!r}; "
                f"add it to UNICODE_MAP in scripts/manual_tables.py"
            )
    return "".join(out)


def param_name(name):
    """A parameter name in a narrow table column: may break after underscores."""
    return latex_escape(name).replace(r"\_", r"\_\allowbreak{}")


def _num(value):
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else latex_escape(repr(value))
    return latex_escape(str(value))


def format_default(value):
    """A parameter's default as the table shows it."""
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if value is None:
        return "none"
    if isinstance(value, str):
        return r"\textit{empty}" if value == "" else r"\texttt{" + latex_escape(value) + "}"
    if isinstance(value, (list, tuple)):
        return ", ".join(format_default(v) for v in value)
    if isinstance(value, float):
        return latex_escape(repr(value))
    return latex_escape(str(value))


def allowed_text(param):
    """What values a parameter accepts, in words: type, range or choices."""
    if param.choices is not None:
        items = [r"\texttt{" + latex_escape(c) + "}" if isinstance(c, str) else _num(c)
                 for c in param.choices]
        return "one of " + ", ".join(items)
    if param.type is bool:
        return "yes or no"
    if param.type is str:
        return "text"
    word = {int: "whole number", float: "number"}.get(param.type, "value")
    low, high = param.min, param.max
    if low is not None and high is not None:
        return f"{word} from {_num(low)} to {_num(high)}"
    if low is not None:
        return f"{word}, at least {_num(low)}"
    if high is not None:
        return f"{word}, at most {_num(high)}"
    return f"any {word}"


def split_name(name):
    """'detection.spike_v1' -> ('detection', 'spike_v1'): the folder the block's
    hand-written and generated files live under."""
    stage, sep, short = name.partition(".")
    if not (sep and stage and short):
        raise ValueError(f"block name {name!r} is not '<stage>.<short_name>'")
    return stage, short


def kind_label(kind):
    return latex_escape(KIND_LABEL.get(kind, kind))


def _declares_units(fn):
    if fn is None:
        return False
    try:
        return "units" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def module_path(spec, repo_root=REPO_ROOT):
    """The file a block's `run` lives in, relative to the repo root."""
    fn = getattr(spec.run, "func", spec.run)  # unwrap a functools.partial
    module = sys.modules.get(getattr(fn, "__module__", None) or "")
    path = getattr(module, "__file__", None)
    if not path:
        return "?"
    try:
        return pathlib.Path(path).resolve().relative_to(pathlib.Path(repo_root).resolve()).as_posix()
    except ValueError:
        return pathlib.Path(path).name


_GENERATED = ("% GENERATED by scripts/manual_tables.py from the adapter registry. Do not edit:\n"
              "% rerun the script.")


def render_block(spec, module_path):
    """One block's generated file: metadata, flags, side inputs, parameters."""
    stage, short = split_name(spec.name)
    name = spec.name
    lines = [
        _GENERATED + f" Hand-written text: blocks/{stage}/{short}/",
        rf"\ubblock{{{name}}}%",
        f"  {{{latex_escape(spec.page_name)}}}% what the app calls it",
        f"  {{{latex_escape(spec.display_name)}}}% registry display name",
        f"  {{{spec.category}}}% insert-modal tab",
        f"  {{{kind_label(spec.input_kind)}}}% input",
        f"  {{{kind_label(spec.output_kind)}}}% output",
        f"  {{{latex_escape(module_path)}}}% code",
        f"  {{{stage}/{short}}}% hand-written folder under blocks/",
        rf"\ubblockdescription{{{name}}}{{{latex_escape(spec.description)}}}",
    ]

    flags = []
    if spec.source:
        flags.append(r"\ubflag{source}{}")
    if _declares_units(spec.run) or _declares_units(spec.derive):
        flags.append(r"\ubflag{units}{}")
    if spec.max_span_samples:
        flags.append(rf"\ubflag{{maxspan}}{{{int(spec.max_span_samples)}}}")
    if spec.recommend is not None:
        flags.append(r"\ubflag{recommend}{}")
    if spec.derive is not None:
        flags.append(r"\ubflag{derive}{}")
    if spec.estimate is not None:
        flags.append(r"\ubflag{estimate}{}")
    if spec.persist is not None:
        flags.append(r"\ubflag{persist}{}")
    lines.append(rf"\ubblockflags{{{name}}}{{%")
    lines += [f"  {flag}%" for flag in flags]
    lines.append("}")

    lines.append(rf"\ubblocksideinputs{{{name}}}{{%")
    for side in spec.side_inputs:
        sources = " or ".join(SOURCE_TEXT.get(s, latex_escape(s)) for s in side.sources)
        need = "required" if side.required else "optional"
        lines.append(rf"  \ubsideinput{{{param_name(side.name)}}}{{{kind_label(side.type_kind)}}}"
                     rf"{{{sources}}}{{{need}}}%")
    lines.append("}")

    if spec.known_broken:
        lines.append(rf"\ubblockbroken{{{name}}}{{{latex_escape(spec.known_broken)}}}")

    lines.append(rf"\ubblockparams{{{name}}}{{%")
    for p in spec.params:
        desc = latex_escape(p.description) if p.description.strip() else \
            r"\textit{no description in the code}"
        lines.append(rf"  \ubparam{{{param_name(p.name)}}}{{{format_default(p.default)}}}"
                     rf"{{{allowed_text(p)}}}{{{desc}}}%")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_catalogue(specs):
    """Every block once, grouped by category in the insert modal's tab order,
    alphabetical by what the app calls it within a category."""
    lines = [_GENERATED, rf"\ubblocktotal{{{len(specs)}}}"]
    for category in CATEGORIES:
        members = sorted((s for s in specs if s.category == category),
                         key=lambda s: (s.page_name.casefold(), s.name))
        if not members:
            continue
        lines.append(rf"\ubcategory{{{category}}}{{{len(members)}}}")
        lines += [rf"\ubcatalogueitem{{{s.name}}}" for s in members]
    return "\n".join(lines) + "\n"


def render_index(specs):
    lines = [_GENERATED, rf"\ubblocktotal{{{len(specs)}}}"]
    for spec in sorted(specs, key=lambda s: s.name):
        stage, short = split_name(spec.name)
        lines.append(rf"\input{{generated/blocks/{stage}/{short}}}")
    return "\n".join(lines) + "\n"


def render_version(version, generated_on):
    return (f"{_GENERATED}\n\\renewcommand\\ubversion{{{latex_escape(version)}}}\n"
            f"\\renewcommand\\ubgeneratedon{{{generated_on}}}\n")


def card_stub(spec):
    return (
        "% !TEX root = ../../../main.tex\n"
        f"% Block card: {spec.name} -- \"{spec.page_name}\" (Part I, the blocks chapter).\n"
        "% Plain language, no maths, half a page at most. The title, category, input and\n"
        "% output types and the link to the appendix entry come from the registry.\n"
        "% Replace each \\towrite{...}. Guide: docs/manual/AUTHORING.md\n"
        "\\cardfield{What it does}\n\\towrite{One plain sentence.}\n\n"
        "\\cardfield{When to use it}\n\\towrite{}\n\n"
        "\\cardfield{What goes in, what comes out}\n\\towrite{In everyday words.}\n\n"
        "\\cardfield{Settings that matter}\n\\towrite{The two or three worth knowing, in plain words.}\n\n"
        "\\cardfield{Watch out for}\n\\towrite{}\n"
    )


def entry_stub(spec):
    return (
        "% !TEX root = ../../../main.tex\n"
        f"% Appendix entry: {spec.name} -- \"{spec.page_name}\" (Appendix A).\n"
        "% Generated above this text: registry name, code path, category, input and\n"
        "% output types, flags, side inputs, the registry's description and every\n"
        "% parameter. Write the rest; cite code by path and function name.\n"
        "% Guide: docs/manual/AUTHORING.md\n"
        "\\entryfield{Algorithm}\n\\towrite{The method step by step: maths or pseudocode.}\n\n"
        "\\entryfield{Assumptions}\n\\towrite{Units, sampling rate, missing values (NaN), span length.}\n\n"
        "\\entryfield{Outputs}\n\\towrite{What it returns, what goes in meta, where results are stored.}\n\n"
        "\\entryfield{Cost}\n\\towrite{Time and memory as the span grows.}\n\n"
        "\\entryfield{Failure modes}\n\\towrite{}\n\n"
        "\\entryfield{Validation}\n\\towrite{Evidence that it does what it claims.}\n\n"
        "\\entryfield{References}\n\\towrite{}\n\n"
        "\\entryfield{Tests}\n\\towrite{}\n"
    )


@dataclass
class Report:
    written: bool
    stale: list = field(default_factory=list)          # generated files that differed from disk
    stubs_created: list = field(default_factory=list)  # hand-written stubs written this run
    missing: list = field(default_factory=list)        # hand-written files absent (check mode)
    orphans: list = field(default_factory=list)        # hand-written folders naming no block

    @property
    def ok(self):
        return not self.orphans and not self.missing and (self.written or not self.stale)


def build(specs, manual_root=MANUAL_ROOT, repo_root=REPO_ROOT, write=True, version=None):
    """Plan every generated file, compare with disk, and (when `write`) bring disk
    up to date. Hand-written stubs are created only where missing."""
    manual_root = pathlib.Path(manual_root)
    report = Report(written=write)

    planned = {}
    for spec in specs:
        stage, short = split_name(spec.name)
        planned[f"generated/blocks/{stage}/{short}.tex"] = render_block(spec, module_path(spec, repo_root))
    planned["generated/blocks.tex"] = render_index(specs)
    planned["generated/catalogue.tex"] = render_catalogue(specs)

    generated_blocks = manual_root / "generated" / "blocks"
    on_disk = ({p.relative_to(manual_root).as_posix() for p in generated_blocks.rglob("*.tex")}
               if generated_blocks.exists() else set())
    for rel in sorted(on_disk - set(planned)):  # a block that left the registry
        report.stale.append(rel)
        if write:
            (manual_root / rel).unlink()

    for rel, content in planned.items():
        path = manual_root / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            report.stale.append(rel)
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")

    if write and version is not None:
        path = manual_root / "generated" / "version.tex"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_version(version, datetime.date.today().isoformat()),
                        encoding="utf-8", newline="\n")

    by_folder = {split_name(s.name): s for s in specs}
    for (stage, short), spec in sorted(by_folder.items()):
        for part, stub in (("card", card_stub), ("entry", entry_stub)):
            rel = f"blocks/{stage}/{short}/{part}.tex"
            path = manual_root / rel
            if path.exists():
                continue
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(stub(spec), encoding="utf-8", newline="\n")
                report.stubs_created.append(rel)
            else:
                report.missing.append(rel)

    blocks_dir = manual_root / "blocks"
    if blocks_dir.exists():
        for stage_dir in sorted(p for p in blocks_dir.iterdir() if p.is_dir()):
            for short_dir in sorted(p for p in stage_dir.iterdir() if p.is_dir()):
                if (stage_dir.name, short_dir.name) not in by_folder:
                    report.orphans.append(short_dir.relative_to(manual_root).as_posix())
    return report


def _git_version(repo_root=REPO_ROOT):
    try:
        commit = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain", "--", "Adapters"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit} + uncommitted Adapters/ changes" if dirty else commit


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate the manual's registry tables.")
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if anything is stale, missing or orphaned")
    parser.add_argument("--manual", default=str(MANUAL_ROOT), help="the manual's root folder")
    args = parser.parse_args(argv)

    import Adapters
    from Adapters.registry import discover_adapters
    specs = discover_adapters()
    failed = [m for _, m, _ in pkgutil.iter_modules(Adapters.__path__)
              if m not in ("base", "registry") and f"Adapters.{m}" not in sys.modules]
    if failed:
        print(f"error: adapter module(s) failed to import, so their blocks would vanish "
              f"from the manual: {', '.join(failed)}", file=sys.stderr)
        return 2

    try:
        report = build(specs, args.manual, REPO_ROOT, write=not args.check,
                       version=None if args.check else _git_version())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verb = "stale" if args.check else "rewritten"
    print(f"{len(specs)} blocks; {len(report.stale)} generated file(s) {verb}; "
          f"{len(report.stubs_created)} stub(s) created")
    for label, items in (("stale" if args.check else "rewritten", report.stale),
                         ("missing hand-written file", report.missing),
                         ("orphaned hand-written folder (no such block)", report.orphans)):
        for item in items:
            print(f"  {label}: {item}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

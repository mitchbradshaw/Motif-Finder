"""
manual_check.py
===============
Compiles one slice of the user manual (`docs/manual/`) on its own, so a writer
can check the files they touched without building the whole book, and without
colliding with anyone else's build:

    python scripts/manual_check.py blocks detection.spike_v1 detection.fluss --outdir DIR
    python scripts/manual_check.py chapter chapters/04-explore.tex --outdir DIR

It writes a small driver .tex into DIR, runs pdflatex twice from docs/manual (so
cross-references within the slice settle), and prints every LaTeX error with its
file and line, plus references the slice could not resolve (those pointing
outside the slice are expected). Citations are not checked: the full build runs
BibTeX. Exit 0 when the slice compiles without errors, 1 otherwise. Needs only
pdflatex on PATH; it imports nothing from the project.
"""

import argparse
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MANUAL = REPO_ROOT / "docs" / "manual"

PREAMBLE = r"""\documentclass[11pt,a4paper,oneside]{report}
\usepackage{ubmanual}
\InputIfFileExists{generated/version}{}{}
\begin{document}
\input{generated/blocks}
"""

# -file-line-error form, "c:/path/file.sty:76: message" (a drive letter allowed), or
# the plain "! message" form some errors still take.
ERROR_LINE = re.compile(r"^(?P<file>(?:[A-Za-z]:)?[^:\s][^:]*\.(?:tex|sty|cls|def|cfg|bbl|aux))"
                        r":(?P<line>\d+): (?P<msg>.*)$")
BANG_LINE = re.compile(r"^! (?P<msg>.*)$")


def driver(kind, items):
    if kind == "blocks":
        body = "\n".join(rf"\ubcheckblock{{{name}}}" for name in items)
    else:
        rels = []
        for item in items:
            path = pathlib.Path(item)
            if path.is_absolute():
                path = path.relative_to(MANUAL)
            rels.append(path.with_suffix("").as_posix())
        body = "\n".join(rf"\input{{{rel}}}" for rel in rels)
    return PREAMBLE + body + "\n\\end{document}\n"


def compile_slice(text, outdir, jobname="check"):
    outdir = pathlib.Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    tex = outdir / f"{jobname}.tex"
    tex.write_text(text, encoding="utf-8")
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-file-line-error",
             f"-output-directory={outdir}", str(tex)],
            cwd=MANUAL, capture_output=True, timeout=600,
        )
    log = (outdir / f"{jobname}.log").read_text(encoding="utf-8", errors="replace")
    errors, lines = [], log.splitlines()
    for i, line in enumerate(lines):
        match = ERROR_LINE.match(line)
        bang = BANG_LINE.match(line)
        if match or bang:
            context = " ".join(l.strip() for l in lines[i + 1:i + 3] if l.strip())
            where = f"{match['file']}:{match['line']}: " if match else ""
            errors.append(f"{where}{(match or bang)['msg']}  {context}".strip())
    undefined = sorted(set(re.findall(r"Reference `([^']+)' on page \d+ undefined", log)))
    return errors, undefined, outdir / f"{jobname}.pdf"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compile a slice of the manual on its own.")
    parser.add_argument("kind", choices=["blocks", "chapter"])
    parser.add_argument("items", nargs="+", help="registry names, or chapter files under docs/manual")
    parser.add_argument("--outdir", required=True, help="a folder of your own for the build")
    args = parser.parse_args(argv)

    errors, undefined, pdf = compile_slice(driver(args.kind, args.items), args.outdir)
    for error in errors:
        print("ERROR", error)
    if undefined:
        print(f"{len(undefined)} reference(s) not resolved inside this slice "
              f"(fine if they point elsewhere in the book): {', '.join(undefined)}")
    print(f"{'FAILED' if errors else 'OK'}: {len(errors)} error(s); PDF: {pdf}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

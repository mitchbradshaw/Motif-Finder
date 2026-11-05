"""
overleaf_zip.py - package docs/thesis for upload to Overleaf as one .zip.

Takes exactly the project files the last build read (build/main.fls, plus the .bib and any local .bst/.cls/.sty),
so the 27 MB of JSON and logs under docs/thesis/data/ stay out. latexmkrc is left out (its out_dir = 'build' is for
the local build only); Overleaf compiles main.tex with pdfLaTeX + BibTeX by default.

    python scripts/thesis/overleaf_zip.py            # writes docs/thesis/build/thesis-overleaf.zip
Run a local build first (latexmk in docs/thesis), so build/main.fls is current.
"""
import os
import sys
import zipfile
from pathlib import Path

THESIS = Path(__file__).resolve().parents[2] / "docs" / "thesis"
OUT = THESIS / "build" / "thesis-overleaf.zip"


def project_inputs():
    fls = (THESIS / "build" / "main.fls").read_text(encoding="utf-8", errors="replace").splitlines()
    pwd = next((l[4:].strip() for l in fls if l.startswith("PWD ")), str(THESIS))
    files = set()
    for line in fls:
        if not line.startswith("INPUT "):
            continue
        p = Path(line[6:].strip())
        if not p.is_absolute():
            p = Path(pwd) / p
        try:
            rel = p.resolve().relative_to(THESIS.resolve())
        except ValueError:
            continue                                  # a TeX Live file: Overleaf has its own
        if rel.parts and rel.parts[0] == "build":
            continue                                  # aux/toc/bbl: Overleaf regenerates them
        files.add(rel)
    for pat in ("bib/*.bib", "*.bst", "*.cls", "*.sty"):
        files.update(p.relative_to(THESIS) for p in THESIS.glob(pat))
    files.add(Path("main.tex"))
    return sorted(files)


def main():
    files = project_inputs()
    missing = [f for f in files if not (THESIS / f).is_file()]
    if missing:
        sys.exit(f"missing: {missing}")
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(THESIS / f, f.as_posix())
    size = OUT.stat().st_size / 1e6
    print(f"{len(files)} files, {size:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()

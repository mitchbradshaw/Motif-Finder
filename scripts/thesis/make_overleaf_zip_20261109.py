"""Pack the thesis for Overleaf (9 Nov): every file the clean build read (from build/main-clean.fls), the bibliography,
and a main.tex that hides the author's instruction notes by default. pdfLaTeX + BibTeX (IEEEtran), as built here.
Writes docs/thesis/MycoWave_thesis_overleaf.zip."""
from __future__ import annotations

import io
import os
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
THESIS = os.path.join(ROOT, "docs", "thesis")
FLS = os.path.join(THESIS, "build", "main-clean.fls")
OUT = os.path.join(THESIS, "MycoWave_thesis_overleaf.zip")

files = set()
for line in io.open(FLS, encoding="utf-8", errors="replace"):
    if not line.startswith("INPUT "):
        continue
    p = line[6:].strip()
    full = os.path.normpath(p if os.path.isabs(p) else os.path.join(THESIS, p))
    rel = os.path.relpath(full, THESIS)
    if rel.startswith("..") or rel.startswith("build" + os.sep) or not os.path.isfile(full):
        continue
    if rel.endswith((".aux", ".toc", ".lof", ".lot", ".out", ".bbl", ".log", ".fls")):
        continue
    files.add(rel.replace(os.sep, "/"))
files.add("bib/thesis.bib")
files.discard("main.tex")

main = io.open(os.path.join(THESIS, "main.tex"), encoding="utf-8").read()
main = ("% Overleaf copy (9 Nov 2026): compiler pdfLaTeX, bibliography BibTeX (IEEEtran).\n"
        "% The author's instruction notes are hidden by the next line; delete it to show them.\n"
        "\\def\\hideinstructions{}\n" + main)

total = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("main.tex", main)
    for rel in sorted(files):
        z.write(os.path.join(THESIS, rel), rel)
        total += os.path.getsize(os.path.join(THESIS, rel))
print(len(files) + 1, "files,", round(total / 1e6, 1), "MB uncompressed;", round(os.path.getsize(OUT) / 1e6, 1),
      "MB zip ->", OUT)
exts = {}
for rel in files:
    e = os.path.splitext(rel)[1]
    exts[e] = exts.get(e, 0) + 1
print(exts)

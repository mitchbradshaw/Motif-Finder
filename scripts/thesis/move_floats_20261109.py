"""Move supporting figures and tables from the chapters into Appendix I (9 Nov page cut), verbatim.

Each float is cut whole (from its \\begin{figure|table} line to its \\end line) by the label it carries, so every
\\ref keeps resolving; nothing is rewritten. Three empty screenshot placeholders in Chapter 4 are deleted (the
chapter's own fallback note). The appendix groups the moved floats by the chapter they came from, in their original
order. Run once; it refuses if a label is missing (already moved).

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/move_floats_20261109.py
"""
from __future__ import annotations

import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
THESIS = os.path.join(ROOT, "docs", "thesis")
APPENDIX = os.path.join(THESIS, "appendices", "I_supplementary.tex")

MOVES = [
    ("02_background.tex", "Chapter~\\ref{ch:litreview}: background", ["fig:encodings"]),
    ("03_early_work.tex", "Chapter~\\ref{ch:early}: early experimental work",
     ["fig:handlabels", "fig:cnnscoretrace", "fig:mpseed", "fig:windowmatrix", "fig:dendroplan", "fig:sax",
      "fig:atlas", "fig:sequence", "fig:droptrio"]),
    ("04_mycowave.tex", "Chapter~\\ref{ch:pipeline}: \\tool{}",
     ["tab:blockstages", "fig:atlasscreen", "fig:analysescreen", "tab:scope"]),
    ("06_rq1_detectors.tex", "Chapter~\\ref{ch:rq1}: detectors", ["tab:surr20", "fig:surr20", "tab:windowtouch"]),
    ("07_rq2_seeds.tex", "Chapter~\\ref{ch:rq2}: seeds", ["tab:seedchannels"]),
    ("08_rq3_classifiers.tex", "Chapter~\\ref{ch:rq3}: classifiers",
     ["tab:forests", "tab:forestblind", "tab:cnns", "tab:cnnvsr4", "tab:faircnn"]),
    ("09_events.tex", "Chapter~\\ref{ch:events}: events", ["fig:familyf30"]),
    ("10_roundb.tex", "Chapter~\\ref{ch:roundb}: the signal studies",
     ["tab:roundb", "fig:b1train", "fig:ch14individuals", "tab:ch14sensitivity", "fig:b3restitution",
      "fig:b12waves", "fig:b4bins", "fig:b5timeline", "fig:b10motif", "fig:b9hist"]),
]
DELETE = [("04_mycowave.tex", ["fig:lineage", "fig:templatepages", "fig:pages"])]


def cut(text, label):
    """Return (text without the float, the float's text)."""
    at = text.find("\\label{" + label + "}")
    if at < 0:
        raise ValueError(f"label {label} not found (already moved?)")
    begins = [m for m in re.finditer(r"\\begin\{(figure|table)\*?\}", text[:at])]
    if not begins:
        raise ValueError(f"no float begins before {label}")
    b = begins[-1]
    kind = b.group(1)
    end = re.compile(r"\\end\{" + kind + r"\*?\}").search(text, at)
    if not end:
        raise ValueError(f"no float end after {label}")
    start = text.rfind("\n", 0, b.start()) + 1
    stop = text.find("\n", end.end())
    stop = len(text) if stop < 0 else stop + 1
    block = text[start:stop]
    if "\\begin{figure" in block[1:] and kind == "figure" and block.count("\\begin{figure") > 1:
        raise ValueError(f"{label}: nested float?")
    before, after = text[:start], text[stop:]
    if before.endswith("\n\n") and after.startswith("\n"):
        after = after[1:]
    return before + after, block


def main():
    groups = []
    for name, heading, labels in MOVES:
        path = os.path.join(THESIS, "chapters", name)
        text = open(path, encoding="utf-8").read()
        blocks = []
        for lab in labels:
            text, block = cut(text, lab)
            blocks.append(block)
        open(path, "w", encoding="utf-8").write(text)
        groups.append((heading, blocks))
        print(f"{name}: moved {len(blocks)}")
    for name, labels in DELETE:
        path = os.path.join(THESIS, "chapters", name)
        text = open(path, encoding="utf-8").read()
        for lab in labels:
            text, _ = cut(text, lab)
        open(path, "w", encoding="utf-8").write(text)
        print(f"{name}: deleted {len(labels)} placeholders")
    out = ["\\chapter{Supplementary figures and tables}", "\\label{app:supp}", "",
           "These figures and tables support the chapters named in each heading and are referred to from them; they "
           "were moved here to keep the main text short. Each keeps its full caption.", ""]
    for heading, blocks in groups:
        out += [f"\\section*{{From {heading}}}", ""]
        for block in blocks:
            out += [block.rstrip("\n"), ""]
        out += ["\\clearpage", ""]
    open(APPENDIX, "w", encoding="utf-8").write("\n".join(out))
    main_tex = os.path.join(THESIS, "main.tex")
    m = open(main_tex, encoding="utf-8").read()
    if "appendices/I_supplementary" not in m:
        m = m.replace("\\input{appendices/H_detector_overlap}",
                      "\\input{appendices/H_detector_overlap}\n\\input{appendices/I_supplementary}")
        open(main_tex, "w", encoding="utf-8").write(m)
    print("appendix written:", APPENDIX)


if __name__ == "__main__":
    main()

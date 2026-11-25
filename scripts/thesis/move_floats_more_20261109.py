"""Second page cut (9 Nov, 12:40): move five more supporting figures into Appendix I, each into its chapter's group.

Same rule as move_floats_20261109.py: each float is cut whole by its label and pasted unchanged, so every reference
still resolves.
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import APPENDIX, THESIS, cut  # noqa: E402

MOVES = [
    ("06_rq1_detectors.tex", "fig:realvssurr", "\\section*{From Chapter~\\ref{ch:rq1}: detectors}"),
    ("07_rq2_seeds.tex", "fig:dropdistribution", "\\section*{From Chapter~\\ref{ch:rq2}: seeds}"),
    ("08_rq3_classifiers.tex", "fig:r4examples", "\\section*{From Chapter~\\ref{ch:rq3}: classifiers}"),
    ("09_events.tex", "fig:cataloguecontext", "\\section*{From Chapter~\\ref{ch:events}: events}"),
    ("09_events.tex", "fig:rec385", "\\section*{From Chapter~\\ref{ch:events}: events}"),
]


def main():
    app = io.open(APPENDIX, encoding="utf-8").read()
    for name, label, heading in MOVES:
        path = os.path.join(THESIS, "chapters", name)
        text = io.open(path, encoding="utf-8").read()
        text, block = cut(text, label)
        io.open(path, "w", encoding="utf-8").write(text)
        at = app.find(heading)
        if at < 0:
            raise SystemExit(f"appendix group missing: {heading}")
        end = app.find("\\clearpage", at)
        app = app[:end] + block.rstrip("\n") + "\n\n" + app[end:]
        print(f"{name}: moved {label}")
    io.open(APPENDIX, "w", encoding="utf-8").write(app)


if __name__ == "__main__":
    main()

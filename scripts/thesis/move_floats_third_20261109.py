"""Third page cut (9 Nov, 12:55): Fig 4.7 restored into Appendix I from the pre-move backup (a failed run had cut it
from Chapter 4 without pasting it), and four more illustrative figures moved into their chapters' groups."""
from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import APPENDIX, THESIS, cut  # noqa: E402

BACKUP = ("C:/Users/mmebr/AppData/Local/Temp/claude/3a41d06cc6096a2e/55c783cf-2a76-451d-bb08-e09ff21dd7b9/"
          "scratchpad/pre_move/04_mycowave.tex")
CH4 = "\\section*{From Chapter~\\ref{ch:pipeline}: \\tool{}}"
MOVES = [
    ("06_rq1_detectors.tex", "fig:agreementexcerpt", "\\section*{From Chapter~\\ref{ch:rq1}: detectors}"),
    ("08_rq3_classifiers.tex", "fig:m4beforeafter", "\\section*{From Chapter~\\ref{ch:rq3}: classifiers}"),
    ("09_events.tex", "fig:eventhierarchy", "\\section*{From Chapter~\\ref{ch:events}: events}"),
    ("10_roundb.tex", "fig:b6species", "\\section*{From Chapter~\\ref{ch:roundb}: the signal studies}"),
]


def paste(app, heading, block):
    at = app.find(heading)
    if at < 0:
        raise SystemExit(f"appendix group missing: {heading}")
    end = app.find("\\clearpage", at)
    return app[:end] + block.rstrip("\n") + "\n\n" + app[end:]


def main():
    app = io.open(APPENDIX, encoding="utf-8").read()
    ch4_now = io.open(os.path.join(THESIS, "chapters", "04_mycowave.tex"), encoding="utf-8").read()
    if "fig:reviewscreen" not in app and "\\label{fig:reviewscreen}" not in ch4_now:
        _, block = cut(io.open(BACKUP, encoding="utf-8").read(), "fig:reviewscreen")
        block = re.sub(r"\\caption\{", lambda m: "\\caption[{A Review queue in \\tool{}.}]{", block, count=1)
        app = paste(app, CH4, block)
        print("restored fig:reviewscreen into Appendix I")
    for name, label, heading in MOVES:
        path = os.path.join(THESIS, "chapters", name)
        text = io.open(path, encoding="utf-8").read()
        text, block = cut(text, label)
        app = paste(app, heading, block)
        io.open(path, "w", encoding="utf-8").write(text)
        print(f"{name}: moved {label}")
    io.open(APPENDIX, "w", encoding="utf-8").write(app)


if __name__ == "__main__":
    main()

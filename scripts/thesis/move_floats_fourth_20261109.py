"""Fourth page cut (9 Nov, 12:50): Table 10.3 (2 Hz counts by family) and Fig 9.4 (716-cohort statistics) to Appendix I;
the 2 Hz paragraph and the new typical-event table carry their content in the body."""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import APPENDIX, THESIS, cut  # noqa: E402

MOVES = [
    ("10_roundb.tex", "tab:rq4partialreturns", "\\section*{From Chapter~\\ref{ch:roundb}: the signal studies}"),
    ("09_events.tex", "fig:catalogue", "\\section*{From Chapter~\\ref{ch:events}: events}"),
]
app = io.open(APPENDIX, encoding="utf-8").read()
for name, label, heading in MOVES:
    path = os.path.join(THESIS, "chapters", name)
    text = io.open(path, encoding="utf-8").read()
    text, block = cut(text, label)
    at = app.find(heading)
    if at < 0:
        raise SystemExit(f"appendix group missing: {heading}")
    end = app.find("\\clearpage", at)
    app = app[:end] + block.rstrip("\n") + "\n\n" + app[end:]
    io.open(path, "w", encoding="utf-8").write(text)
    print("moved", label)
io.open(APPENDIX, "w", encoding="utf-8").write(app)

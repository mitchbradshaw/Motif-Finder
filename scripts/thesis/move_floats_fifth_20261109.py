"""Fifth page cut (9 Nov, 13:52): three figures whose content the body now carries in other form move to Appendix I."""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import APPENDIX, THESIS, cut  # noqa: E402

MOVES = [
    ("09_events.tex", "fig:acceptedgallery", "\\section*{From Chapter~\\ref{ch:events}: events}"),
    ("10_roundb.tex", "fig:b4stack", "\\section*{From Chapter~\\ref{ch:roundb}: the signal studies}"),
    ("10_roundb.tex", "fig:b12shape", "\\section*{From Chapter~\\ref{ch:roundb}: the signal studies}"),
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

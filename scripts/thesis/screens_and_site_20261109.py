"""Final pass (9 Nov, author's review): site screenshots back in Chapter 4 and a Discovery Map in Chapter 6; Chapters 6-10
name the MycoWave workflow where it produced the results; abstract counts eight recordings; Figure 5.1 takes the two
grow-kit photos once saved as figures/new/ch5_kit_a.jpg and ch5_kit_b.jpg."""
from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import APPENDIX, THESIS, cut  # noqa: E402

CH = os.path.join(THESIS, "chapters")


def rd(p):
    return io.open(p, encoding="utf-8").read()


def wr(p, t):
    io.open(p, "w", encoding="utf-8").write(t)


def rep(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"{text.count(old)} matches for {old[:70]!r}")
    return text.replace(old, new)


def before(text, anchor, block):
    if text.count(anchor) != 1:
        raise SystemExit(f"{text.count(anchor)} matches for anchor {anchor[:60]!r}")
    return text.replace(anchor, block.strip() + "\n\n" + anchor)


p4, p5, p6, p7, p8, p9, p10 = (os.path.join(CH, f) for f in (
    "04_mycowave.tex", "05_methodology.tex", "06_rq1_detectors.tex", "07_rq2_seeds.tex", "08_rq3_classifiers.tex",
    "09_events.tex", "10_roundb.tex"))
pab = os.path.join(THESIS, "frontmatter", "abstract.tex")

app = rd(APPENDIX)
app, f_an = cut(app, "fig:analysescreen")
app, f_rv = cut(app, "fig:reviewscreen")
app, f_at = cut(app, "fig:atlasscreen")


def pin(b):
    return re.sub(r"\\begin\{figure\}\[[a-zA-Z!]*\]", r"\\begin{figure}[H]", b, count=1)


EXPLORE = r"""\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{screens/explore_signal_span.jpg}
\caption[{Explore: one channel and a selected span.}]{Explore in \tool{}: one channel of M2\_aug (CH4\_A2) over its 721 hours, with a 4-hour span selected (377--381\,h) and the detections and verdicts on it drawn as coloured bands. From here a span is saved, sent to Review or opened in Analyse.}
\label{fig:explorescreen}
\end{figure}"""
DMAP = r"""\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{screens/discovery_map_m2aug.jpg}
\caption[{Discovery Map: where each detector setting fires on M2\_aug.}]{Discovery $\rightarrow$ Map in \tool{}: where each detector setting fires on M2\_aug, one row per setting and one cell per channel, shaded within each row from the fewest to the most detections. The top row shows where human verdicts lie; hatched cells were not run on that channel.}
\label{fig:discoverymap}
\end{figure}"""

t4 = rd(p4)
t4 = before(t4, "\\section{Propose and adjudicate in the data model}", pin(f_an))
t4 = before(t4, "\\section{Recipes, provenance and the step cache}", pin(f_rv))
t4 = before(t4, "\\section{The workflow through the pages}", pin(f_at))
t4 = before(t4, "\\section{How MycoWave was built}", EXPLORE)
wr(p4, t4)

t6 = rd(p6)
t6 = rep(t6, "\\section{Methods}\n\\label{sec:rq1methods}\n\n",
         "\\section{Methods}\n\\label{sec:rq1methods}\n\nEvery run in this chapter was made through the \\tool{} workflow "
         "of Chapter~\\ref{ch:pipeline}: the detectors ran as Discovery sweeps over whole recordings, their candidates were "
         "assembled and compared on the Discovery pages (Figure~\\ref{fig:discoverymap}), and every blind verdict was given "
         "on the Review page.\n\n")
t6 = rep(t6, "\\subsection{Scale and coverage}\n\n", "\\subsection{Scale and coverage}\n\n" + DMAP + "\n\n")
wr(p6, t6)

t7 = rd(p7)
t7 = rep(t7, "\\section{Methods}\n\n", "\\section{Methods}\n\nThe seeds were drawn from reviewed spans in \\tool{}, their "
         "matches were found with the site's seed search, and every match and random control was judged blind on its "
         "Review page (Chapter~\\ref{ch:pipeline}).\n\n")
wr(p7, t7)

t8 = rd(p8)
t8 = rep(t8, "\\section{Methods}\n\n", "\\section{Methods}\n\nThe classifiers were trained and scored on candidates "
         "assembled by \\tool{}'s detector sweeps, and the R4 classifier on the verdicts given on its Review page "
         "(Chapter~\\ref{ch:pipeline}).\n\n")
wr(p8, t8)

t9 = rd(p9)
t9 = rep(t9, "Every single event was measured automatically with the tool's event-shape block",
         "Every single event was measured automatically with \\tool{}'s event-shape block")
wr(p9, t9)

t10 = rd(p10)
t10 = rep(t10, "Each is answered with the site as it stands", "Each is answered with the \\tool{} site as it stands")
wr(p10, t10)

# Figure 5.1: the two grow-kit photos when they are saved, the lab photo until then
t5 = rd(p5)
t5 = rep(t5, "\\includegraphics[height=7.5cm]{new/ch5_setup.jpg}",
         "\\IfFileExists{figures/new/ch5_kit_b.jpg}{\\includegraphics[width=0.49\\textwidth]{new/ch5_kit_a.jpg}\\hfill"
         "\\includegraphics[width=0.49\\textwidth]{new/ch5_kit_b.jpg}}{\\includegraphics[height=7.5cm]{new/ch5_setup.jpg}}")
wr(p5, t5)

ab = rd(pab)
ab = rep(ab, "applies the tool to nine recordings", "applies the tool to eight recordings")
wr(pab, ab)

# references that pointed to the appendix for figures now back in the body
pat = re.compile(r"(\\ref\{fig:(?:analysescreen|reviewscreen|atlasscreen|b3restitution|b4stack|b9hist)\})"
                 r"(?:,\s*Appendix~\\ref\{app:supp\}|\s*\(Appendix~\\ref\{app:supp\}\))")
n = 0
for f in sorted(os.listdir(CH)):
    if f.endswith(".tex"):
        p = os.path.join(CH, f)
        t = rd(p)
        t2, k = pat.subn(r"\1", t)
        if k:
            wr(p, t2)
            n += k
wr(APPENDIX, app)
print("done; appendix pointers removed:", n)

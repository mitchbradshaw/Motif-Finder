"""Chapter 10 (9 Nov): the author's edits (the site as it stands; the question-choice paragraph merged into the
opening; the events section promoted), and B6/B12 re-read on the 2,459-event inventory (b6_b12_inventory_20261109.py).
"""
from __future__ import annotations

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH10 = os.path.join(ROOT, "docs", "thesis", "chapters", "10_roundb.tex")
t = io.open(CH10, encoding="utf-8").read()


def rep(old, new):
    global t
    if t.count(old) != 1:
        raise SystemExit(f"{t.count(old)} matches for {old[:70]!r}")
    t = t.replace(old, new)


merged = ("The studies of this chapter were fixed on 27 October from the questions the earlier chapters left open, under "
          "four rules: each had to be answerable on the site with little new building, and to have one null, one figure, "
          "and a stated claim and non-claim (Table~\\ref{tab:roundb}, Appendix~\\ref{app:supp}).")
rep("Each is answered with the site as it stood, and each is judged against a null.",
    "Each is answered with the site as it stands, and each is judged against a null. " + merged)
rep("\\section{How the questions were chosen}\n\n" + merged + "\n", "")
rep("\\subsection{Which events each study uses}", "\\section{Which events each study uses}")
rep("so the shape comparisons (B6, B12) can be repeated on them once they are regrouped.",
    "and the shape comparisons (B6, B12) were repeated on them once they had been measured and regrouped "
    "(Section~\\ref{sec:families}), with the same reading.")

old_b612 = t[t.index("Are shapes shared between recordings and species?"):]
old_b612 = old_b612[:old_b612.index("\n")]
rep(old_b612, r"""Are shapes shared between recordings and species? On the full inventory's 2,459 accepted single events and their twelve shape families (Section~\ref{sec:families}), every family holds events from at least two recordings, ten hold events from all eight, and eleven from all three species (Figure~\ref{fig:inventoryfamilies}). Families are not spread at random, though: which family an event falls in depends on its recording (0.42 bits of mutual information, against 0.02 for shuffled labels). The timing measures differ strongly between recordings, while depth hardly does (Table~\ref{tab:inventorymeasures}). Much of both comes from one unusual source, MJu26a's train of fast spikes. Without MJu26a, the lean by recording falls to 0.13 bits, of which species accounts for about half, and the species differ in timing far less than the recordings do (effect sizes $\varepsilon^2\le0.02$ between species, against 0.04--0.08 between recordings). The first read, on the 716 accepted blind-panel events and the earlier g-11 families (Figures~\ref{fig:b6species} and~\ref{fig:b12shape}), reached the same conclusion. For the mushrooms, the same shapes occur across recordings and species, and once a single unusual train is set aside, the differences between cultures and setups are at least as large as the differences between species.""")

rep("39 of 42 families on two or more recordings, 28 on both species; the mix is not random (0.22 against 0.13 bits by "
    "recording, $p=0.0001$), and the lean by species is no larger than by recording",
    "full inventory: 12 of 12 families on two or more recordings, 10 on all eight, 11 on all three species; the mix "
    "leans by recording (0.42 against 0.02 bits, $p=0.001$), and without MJu26a's spike train species explains about "
    "half of a smaller lean (0.06 of 0.13 bits); first read on g-11 the same")
rep("recordings differ a little (11 of 15 features pass BH; $\\varepsilon^2\\le0.06$); species: 1 of 15 (share of falls, "
    "carried by LM), against 7 of 15 between recordings of one species;",
    "full inventory: timing differs strongly by recording ($\\varepsilon^2$ up to 0.47), depth hardly (0.04), largely "
    "through MJu26a's spike train; without it species differ less than recordings ($\\varepsilon^2\\le0.02$ against "
    "0.04--0.08); first read on 716 events the same;")
io.open(CH10, "w", encoding="utf-8").write(t)
print("Chapter 10 updated")

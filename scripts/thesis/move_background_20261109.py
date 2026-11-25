"""Move detailed theory out of Chapter 2 and the detail of RQ3's 8.3.1 and 8.3.4 into a new appendix (9 Nov, author's
direction), leaving short overviews in the body."""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import THESIS  # noqa: E402

P2 = os.path.join(THESIS, "chapters", "02_background.tex")
P8 = os.path.join(THESIS, "chapters", "08_rq3_classifiers.tex")
PJ = os.path.join(THESIS, "appendices", "J_background.tex")
PM = os.path.join(THESIS, "main.tex")


def rd(p):
    return io.open(p, encoding="utf-8").read()


def wr(p, t):
    io.open(p, "w", encoding="utf-8").write(t)


t2 = rd(P2)
moved2 = []
for title in ("Frequency, wavelet and entropy analysis", "Image encodings and convolutional networks",
              "Classification without hand-crafted features", "Distance, normalisation and scale invariance",
              "Evaluation statistics"):
    key = "\\section{" + title + "}"
    if t2.count(key) != 1:
        raise SystemExit("missing " + title)
    a = t2.index(key)
    b = t2.index("\\section{", a + len(key))
    moved2.append(t2[a:b].rstrip() + "\n\n")
    t2 = t2[:a] + t2[b:]
POINTER = r"""\section{Further methods}
\label{sec:furthermethods}

Several further families of methods are used in this thesis, and their theory is given in Appendix~\ref{app:background}: frequency, wavelet and entropy analysis, which describe how a signal's power and complexity are spread across time scales; image encodings, which turn a window of signal into a picture that a convolutional network can read; classifiers that learn their own features instead of relying on hand-crafted ones; the distance and normalisation choices that decide when two shapes count as alike; and the evaluation statistics used to score detectors and classifiers.

"""
key = "\\section{Gaps in knowledge}"
if t2.count(key) != 1:
    raise SystemExit("no Gaps section")
t2 = t2.replace(key, POINTER + key)

t8 = rd(P8)
O1 = r"""\subsection{Cluster labels against manual labels}

Random forests trained on the manual labels outperformed forests trained on cluster-derived labels (unseen-channel macro F1 0.793 against 0.635, Table~\ref{tab:forests}), largely because the cluster labels already disagreed with the human ones: 77\,\% of the windows marked interesting by hand fell in clusters mapped to not interesting. A later forest built on seven waveform-shape clusters beat its permutation null on the blind window labels (macro F1 0.450 against 0.368, $p=0.001$), but it failed in the opposite direction to the manual forest: it recovered 93\,\% of the interesting windows with only 24\,\% of its positives accepted, while the manual forest was selective, with 89\,\% of its positives accepted but only 41\,\% of the interesting windows found (Table~\ref{tab:forestblind}). Giving a whole shape group one label did not reproduce the finer distinctions of human review. The full comparison is in Appendix~\ref{app:ch8detail}.

"""
O2 = r"""\subsection{CNN against MiniRocket on the same events}

On the 2,456 events used to evaluate R4, the original reference CNNs reached a pooled AUC of 0.722--0.790, against R4's 0.971 (Table~\ref{tab:cnnvsr4}), but they had learned from earlier fixed-window labels rather than from reviewed spans. Retrained on R4's own examples and recording folds, the CNNs reached 0.970--0.973, and every paired interval with R4 included zero (Table~\ref{tab:faircnn}). The initial gap came from the training examples, not the architecture; the details are in Appendix~\ref{app:ch8detail}.

"""
moved8 = []
for start, end, ov in (("\\subsection{Cluster labels against manual labels}", "\\subsection{The CNNs}", O1),
                       ("\\subsection{CNN against MiniRocket on the same events}", "\\subsection{The held-out exam}", O2)):
    if t8.count(start) != 1 or t8.count(end) != 1:
        raise SystemExit("ch8 anchor " + start)
    a = t8.index(start)
    b = t8.index(end)
    moved8.append(t8[a:b].rstrip() + "\n\n")
    t8 = t8[:a] + ov + t8[b:]

J = (r"""\chapter{Background theory and classifier comparisons in detail}
\label{app:background}

This appendix holds the detailed theory and comparisons that the body summarises: the methods background of Chapter~2, and two comparisons from Chapter~\ref{ch:rq3}.

""" + "".join(moved2) + r"""\section{Classifier comparisons in full}
\label{app:ch8detail}

""" + "".join(moved8))

tm = rd(PM)
key = "\\input{appendices/I_supplementary}"
if tm.count(key) != 1:
    raise SystemExit("main.tex anchor")
tm = tm.replace(key, key + "\n\\input{appendices/J_background}")

wr(PJ, J)
wr(P2, t2)
wr(P8, t8)
wr(PM, tm)
print("moved", len(moved2), "Ch2 sections and", len(moved8), "Ch8 subsections")

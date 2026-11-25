"""Rewrite Chapter 9's catalogue and events sections (9 Nov, author's direction): one overview of the reviews, one
section on what an accepted span holds, and one on the measures and shape families of all accepted single events
(ch9_inventory_events_20261109.py). The spiking-families and g-11 sections are replaced; the event-anatomy figure
moves here from Chapter 5."""
from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import THESIS, cut  # noqa: E402

CH9 = os.path.join(THESIS, "chapters", "09_events.tex")
CH5 = os.path.join(THESIS, "chapters", "05_methodology.tex")
CH10 = os.path.join(THESIS, "chapters", "10_roundb.tex")

t9 = io.open(CH9, encoding="utf-8").read()
t5 = io.open(CH5, encoding="utf-8").read()
t5, anatomy = cut(t5, "fig:anatomyevent")


def block(text, label):
    m = re.search(r"\\begin\{figure\}\[htbp\]\n(?:(?!\\end\{figure\}).)*?\\label\{" + re.escape(label) + r"\}\n\\end\{figure\}\n",
                  text, flags=re.S)
    if not m:
        raise SystemExit(f"figure {label} not found")
    return m.group(0)


catalogue_fig = block(t9, "fig:combinedcatalogue")
gallery_fig = block(t9, "fig:acceptedgallery")
para1_start = t9.index("Three counting units appear in this chapter.")
para1 = t9[para1_start:t9.index("\n", para1_start) + 1]

middle = "\\subsection{A combined inventory of the reviewed material}\n\n" + para1 + "\n" + catalogue_fig + "\n" + r"""The inventory comes from five kinds of review. The blind detector panels judged stratified samples of detector candidates on five recordings (Chapter~\ref{ch:rq1}), and the seed panels judged search matches beside random windows, including the cross-recording drop panel, which accepted 455 of 457 matches (Chapter~\ref{ch:rq2}). A review of the long MJu26a CH14 spike train accepted 515 of its 559 proposed spikes (Section~\ref{sec:mjuch14train}). A review of 322 earlier Library proposals that had never been judged accepted 280, rejected 24 and marked 17 unsure, and the 280 acceptances became 127 spans once overlapping proposals were combined. Finally, 750 new detector proposals were drawn from the recordings with the least accepted material (200 each from SH and SO, 150 from MJu26a and 25--75 from each of the others) and shuffled with 54 random windows of matched duration on the same channels, with their sources hidden. Of the proposals, 231 were accepted, against 5 of the random windows, adding 237 spans, mostly on SH (from 27 spans to 79) and SO (from 22 to 97). MJu26a exists in several copies (10\,Hz, 2\,Hz, a five-channel copy and a four-hour excerpt), and all are mapped back to the one physical recording before counting, so an event reviewed in two copies counts once.

\subsection{What an accepted span holds}

Accepting a stretch of signal as interesting does not fix where an event in it begins and ends. Some accepted spans hold only the recovery from a preceding drop or end just before the next deflection, and others hold several substantial excursions or part of a train (Figures~\ref{fig:cataloguecontext} and~\ref{fig:eventhierarchy}, Appendix~\ref{app:supp}). During the later reviews the extents of 165 spans were redrawn by hand. Figure~\ref{fig:acceptedgallery} shows what accepted events typically look like: most are falls in potential, from seconds to tens of minutes long and from a few to a hundred millivolts deep, and many carry smaller deflections. For the measurements and the grouping that follow, spans unlikely to be a single event were left out, because their shapes are not comparable with those of single events: 45 region-length spans of more than an hour, and 455 spans holding more than one fall of at least half the depth of their largest. That leaves 2,459 single events. The earlier blind detector panels' 716 accepted events remain the one comparison of accepted with rejected candidates under a single sampling design (Figure~\ref{fig:catalogue}): accepted events are larger than rejected ones, partly because size was one of the things judged.

""" + gallery_fig + "\n" + r"""\section{Measures and shape families of the accepted events}
\label{sec:families}

Every single event was measured automatically with the tool's event-shape block, by the rules Figure~\ref{fig:anatomyevent} shows on one drop. Each event is first turned so that its fastest edge is a fall. The steepest point of the fall is found, and the trough is the lowest point before the fall levels off. The onset is the shoulder the fall leaves, found by walking back from the steepest point, and the half-recovery point is the first return halfway from the trough to the onset level, searched forward but never into the next accepted event. From these come the depth (onset to trough), the fall time (onset to trough) and the half-recovery time (trough to half recovery).

""" + anatomy + "\n" + r"""Table~\ref{tab:inventorymeasures} and Figure~\ref{fig:inventorymeasures} give the results. The typical accepted event is a fall of about 7\,mV (5--95\,\%: 0.4--68\,mV) over about 16 seconds, which recovers halfway about 18 seconds later, and 94\,\% of single events are falls. The recordings differ more in timing than in depth. MJu26a's events, dominated by the CH14 spike train, fall in about two seconds and recover halfway in about four, while those of M2\_concat, M4 and SH take a minute or more to recover halfway. For 39\,\% of events the half-recovery point was not reached before the next event or within the search limit, so the recovery times describe the events that recovered.

\begin{table}[htbp]
\caption[{Measures of the accepted single events, by recording.}]{Measures of the 2,459 accepted single events, by recording, from the tool's event-shape block: medians, with the 5--95\,\% range in brackets. Falls are events whose fastest edge is a fall. Half-recovery times are over the events that recovered halfway before the next event.}
\label{tab:inventorymeasures}
\small
\begin{tabularx}{\textwidth}{@{}X r r l l l@{}}
\toprule
\textbf{Recording} & \textbf{$n$} & \textbf{Falls} & \textbf{Depth (mV)} & \textbf{Fall time (s)} & \textbf{Half-recovery (s)}\\
\midrule
M2\_aug & 951 & 91\,\% & 7.6 (0.7--76) & 26 (6--169) & 30 (8--616)\\
M2\_concat & 136 & 98\,\% & 9.6 (0.9--112) & 43 (6--136) & 118 (10--762)\\
M4 & 105 & 91\,\% & 3.6 (0.6--70) & 40 (7--188) & 109 (5--489)\\
LM & 308 & 91\,\% & 9.5 (0.8--79) & 30 (2.5--80) & 9 (4--510)\\
CO & 112 & 96\,\% & 5.7 (0.6--83) & 9.8 (2.6--85) & 25 (1.6--406)\\
MJu26a & 722 & 97\,\% & 8.1 (0.1--19) & 1.9 (0.3--48) & 4.2 (0.2--134)\\
SH & 55 & 91\,\% & 3.0 (0.2--24) & 36 (1.4--91) & 120 (1.2--469)\\
SO & 70 & 93\,\% & 3.1 (0.2--19) & 14 (1.0--90) & 20 (0.8--221)\\
\midrule
All & 2,459 & 94\,\% & 7.4 (0.4--68) & 16.5 (1.3--116) & 18 (0.7--490)\\
\bottomrule
\end{tabularx}
\end{table}

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{new/ch9_inventory_measures.pdf}
\caption[{Depth, fall time and half-recovery of the accepted single events.}]{Depth, fall time and half-recovery time of the 2,459 accepted single events, by recording (number of events in brackets). Boxes span the middle half, whiskers the 5--95\,\% range, and the line is the median; each axis is logarithmic. MJu26a's events are dominated by the fast spikes of one reviewed train.}
\label{fig:inventorymeasures}
\end{figure}

The single events were then grouped by shape. Each was cut from a quarter of its length before the onset to its half-recovery point (or to twice its fall time after the trough where it did not recover), resampled to 100 points and z-normalised, so that only its shape remains. The 2,454 events with a usable cut were grouped by Ward clustering, the method of the Library's earlier groupings, and cut into 12 families (Figure~\ref{fig:inventoryfamilies}). Ten of the twelve families hold events from all eight recordings. Most are variations of one fall and recovery, differing in how sharp the fall is and how far and how fast the signal returns. One family (F3) is almost entirely MJu26a's CH14 spikes, sharp falls that stay low and then return abruptly; the largest (F9) holds falls that do not recover within the cut; and a small one (F6) holds a brief rise before the fall. The grouping is an imposed partition rather than a discovered taxonomy: the tree's cophenetic correlation is 0.48, and re-running it on waveforms jittered by 1--2\,\% keeps the families with an adjusted Rand index of about 0.71. The earlier studies of Chapter~\ref{ch:roundb} used g-11, a grouping of 1,097 Library events from four recordings into 42 families, which was fixed before the later reviews.

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{new/ch9_inventory_families.pdf}
\caption[{Shape families of the accepted single events.}]{Shape families of the accepted single events. Top: the Ward tree of 2,454 events, cut into 12 families (family and number of events beneath each branch). Below: each family's members (grey, up to 40 drawn at random) and their median shape (black), each event cut from a quarter of its length before the onset to its half-recovery point, resampled to 100 points and z-normalised, so amplitude and duration are removed. Ten families hold events from all eight recordings.}
\label{fig:inventoryfamilies}
\end{figure}

"""

a = t9.index("\\subsection{A combined inventory of the reviewed material}")
b = t9.index("\\section{Events no one has judged}")
t9 = t9[:a] + middle + t9[b:]

t9 = t9.replace(
    "Firstly, the accepted catalogue and its sources are described, together with what a typical accepted event looks like. "
    "One recording is then examined in detail, followed by the shape families the events fall into.",
    "Firstly, the accepted catalogue and the reviews behind it are described. Every accepted single event is then "
    "measured, and the events are grouped into shape families.")
for old, new in [
    ("The typical accepted event on these recordings is a fall in potential of roughly ten to twenty millivolts that "
     "recovers more slowly than it fell, from seconds to tens of minutes long, often with smaller deflections riding on "
     "it; by the tool's fastest-edge rule, 91\\,\\% of the accepted blind-panel events are falls.",
     "The typical accepted event on these recordings is a fall in potential of about 7\\,mV over about 16 seconds that "
     "recovers halfway about 18 seconds later, often with smaller deflections riding on it, and 94\\,\\% of the accepted "
     "single events are falls."),
    ("The same kind of fall appears on every recording and species,",
     "The same kinds of fall appear on every recording and species, and ten of the twelve shape families span all eight "
     "recordings,"),
    ("What generalises across recordings is that drops dominate, and the ranges of their sizes and durations; the two "
     "amplitude regimes of MJu26a CH14 are a case study.",
     "What generalises across recordings is that drops dominate, and the ranges of their sizes and durations; MJu26a's "
     "fast spikes are a case study of one train."),
]:
    if t9.count(old) != 1:
        raise SystemExit(f"Ch9 anchor missing: {old[:60]!r}")
    t9 = t9.replace(old, new)

t10 = io.open(CH10, encoding="utf-8").read()
old10 = "Section~\\ref{sec:spikingfamilies} looked at four hours of MJu26a CH14 in detail."
if old10 in t10:
    t10 = t10.replace(old10, "An early pass looked at four hours of MJu26a CH14 in detail.")
io.open(CH10, "w", encoding="utf-8").write(t10)
io.open(CH5, "w", encoding="utf-8").write(t5)
io.open(CH9, "w", encoding="utf-8").write(t9)
print("Chapter 9 rewritten; notes left:", t9.count("\\begin{instructions}"))

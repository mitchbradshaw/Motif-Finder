"""Chapter 10 final edits (9 Nov, author's review): the question list at the start, each section names its questions,
10.4/10.7/10.8/summary rewritten, Figure 10.1 on the reviewed CH14 train, three figures back from the appendix, Ch10
figures pinned to their sections; Chapter 5 drops its figure references to Ch9/10 and the setup photo caption."""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import APPENDIX, THESIS, cut  # noqa: E402

CH5 = os.path.join(THESIS, "chapters", "05_methodology.tex")
CH10 = os.path.join(THESIS, "chapters", "10_roundb.tex")


def rep(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"{text.count(old)} matches for {old[:70]!r}")
    return text.replace(old, new)


def para_replace(text, start, end, new):
    i = text.index(start)
    j = text.index(end, i) + len(end)
    if text.count(start) != 1:
        raise SystemExit(f"start not unique: {start[:60]!r}")
    return text[:i] + new + text[j:]


t = io.open(CH10, encoding="utf-8").read()
app = io.open(APPENDIX, encoding="utf-8").read()
app, f_b3 = cut(app, "fig:b3restitution")
app, f_b4 = cut(app, "fig:b4stack")
app, f_b9 = cut(app, "fig:b9hist")

QTABLE = r"""

\begin{table}[H]
\caption[{The questions of this chapter.}]{The questions of this chapter, numbered as they were fixed on 27 October, and the sections that answer them. B7 and B8 were not run and are left for further work; each study's null, claim and non-claim are in Table~\ref{tab:roundb}.}
\label{tab:rbquestions}
\small
\begin{tabularx}{\textwidth}{@{}l X l@{}}
\toprule
 & \textbf{Question} & \textbf{Section}\\
\midrule
B1 & How are events spaced in time: regularly, in bursts, or at random? & \ref{sec:rb_sequences}, \ref{sec:mjuch14train}\\
B2 & Do drops in a sequence change shape step by step? & \ref{sec:rb_sequences}\\
B3 & Does a drop recover more slowly after a longer rest? & \ref{sec:rb_models}\\
B4 & Does activity travel from one electrode to another? & \ref{sec:rb_channels}\\
B5 & When and where do the detectors fire? & \ref{sec:rb_detectors}\\
B6 & Do the same shape families recur across recordings and species? & \ref{sec:rb_families}\\
B9 & Do events prefer particular durations? & \ref{sec:rb_methods}\\
B10 & At which time scales does the signal hold structure? & \ref{sec:rb_methods}\\
B11 & Do the detectors find the same events on the newer recordings? & \ref{sec:rb_detectors}\\
B12 & Do event shapes and intervals differ between recordings and species? & \ref{sec:rb_families}\\
\bottomrule
\end{tabularx}
\end{table}
"""
t = rep(t, "and a stated claim and non-claim (Table~\\ref{tab:roundb}, Appendix~\\ref{app:supp}).\n",
        "and a stated claim and non-claim (Table~\\ref{tab:roundb}, Appendix~\\ref{app:supp}). Table~\\ref{tab:rbquestions} "
        "lists the questions in plain words, numbered B1 to B12 as they were fixed, with the section that answers each, "
        "and each section below names the questions it addresses." + QTABLE)

t = rep(t, "How are events spaced in time? The census uses one detector",
        "How are events spaced in time (B1)? The census uses one detector")
t = rep(t, "and the gaps between consecutive events on a channel are measured (Figure~\\ref{fig:anatomytrain}).",
        "and the gaps between consecutive events on a channel are measured (Figure~\\ref{fig:anatomytrain} shows these "
        "measures on a stretch of the reviewed train of Section~\\ref{sec:mjuch14train}).")
t = rep(t, "Sequences of drops told a similar story:", "Sequences of drops told a similar story (B2):")

NEWTRAIN = r"""\begin{figure}[H]
\centering
\includegraphics[width=\textwidth]{new/ch10_train_example.pdf}
\caption[{How a train of events is measured.}]{How a train of events is measured: three hours (388--391\,h) of the reviewed MJu26a CH14 train of Section~\ref{sec:mjuch14train}, with each of its seven spikes marked at its onset and the gap to the next, in minutes. Interval measures summarise such a sequence: the coefficient of variation (CV) compares the spread of the gaps to their mean, while CV2 and the local variation (LV) compare each gap only with its neighbour, so a slowly drifting rate does not inflate them. A random (Poisson) train has CV, CV2 and LV of about 1, like raindrops on a roof; a perfectly regular one has 0, like a dripping tap. This stretch is a dripping tap: gaps of 25--26 minutes give CV 0.02, CV2 0.01 and LV 0.00. The smaller deflections of 1--2\,mV between the spikes are not part of the reviewed train.}
\label{fig:anatomytrain}
\end{figure}"""
i = t.index("{new/ch5_anatomy_train.pdf}")
a = t.rindex("\\begin{figure}", 0, i)
b = t.index("\\end{figure}", i) + len("\\end{figure}")
t = t[:a] + NEWTRAIN + t[b:]

t = rep(t, "The longest reviewed sequence in the thesis is a train of spikes on MJu26a CH14",
        "B1 can also be asked of a single train that was reviewed spike by spike. The longest reviewed sequence in the "
        "thesis is a train of spikes on MJu26a CH14")

NEW_B3 = r"""Does a drop recover more slowly when the gap before it was long, as heart muscle recovers according to how long it has rested (B3)? Within the reviewed trains (the 74 of the Library's 117 reviewed drop sequences in which drops recover at least halfway before the next one, 987 consecutive pairs of drops), the gap after a drop predicted its recovery time far more strongly than the gap before, as a recovery is usually cut shorter when the next drop arrives (Figure~\ref{fig:b3restitution}). Although across the longer gaps between events flagged by the detector census there seemed to be a weak link on the two M2 recordings, this was halved once the duration of the fall was accounted for. There is therefore no evidence that a drop's recovery depends on the rest before it within trains, and only a bounded hint across long gaps. The excitable-system models first planned for this question were set aside when they fitted surrogate noise as well as the data.

""" + f_b3.strip() + "\n"
t = para_replace(t, "Does a drop recover more slowly when the gap before it was long",
                 "they fitted surrogate noise as well as the data.\n", NEW_B3)

t = rep(t, "Are shapes shared between recordings and species? On the full",
        "Are shapes shared between recordings and species (B6), and do their measures differ between them (B12)? On "
        "the full")

t = rep(t, "Does activity travel from one electrode to another? A census",
        "Does activity travel from one electrode to another (B4)? A census")
t = rep(t, "looks like the setup or the room, not the culture.\n",
        "looks like the setup or the room, not the culture.\n\n" + f_b4.strip() + "\n")

NEW_DET = r"""When and where do the detectors fire (B5), and do they find the same events on the newer recordings (B11)? Across the eight recordings, about 40 detector settings ran on every channel, each beside a phase-randomised copy of the channel, which keeps its spectrum but not its events (Chapter~\ref{ch:rq1}). The detectors fire on every channel and in every three-hour stretch, but not evenly: on every channel their rates rise and fall together over hours to days, far more than on the copies (a median co-modulation of 0.21--0.35 per recording, against 0.02--0.04 on the copies). A whole recording grows busier and quieter, and every detector follows it. The detectors also differ in what they respond to. On the 2\,Hz recordings, as on the judged ones, OASIS, the deconvolved troughs, the noise and matrix-profile thresholds, the drop detector and the 60-minute CNNs found from about twice to over a hundred times more on the recordings than on their copies, while the wavelet-encoded setting, symbol search, BEADs, the signal threshold and the 1-minute CNNs found more on the copies (Table~\ref{tab:rq4partialreturns}). Where several detector families mark the same stretch of signal, that stretch is far more likely to lie on a recording than on its copy: seven or more families mark 17--29\,\% of candidates on the five judged recordings and 10--16\,\% on the three 2\,Hz recordings, against 2--4\,\% on their copies. On the judged recordings this agreement tracked acceptance, from 0--5\,\% of candidates judged real where one or two families agree to 40--63\,\% where nine or more do (Figure~\ref{fig:ladder}); no 2\,Hz candidate has yet been reviewed. Further work requires reviewing more of these detected candidates to better evaluate their acceptance rates."""
t = para_replace(t, "\\paragraph{The 2\\,Hz recordings.}", "None of these detections has been reviewed.", NEW_DET)

NEW_METH = r"""Do fungal events prefer particular durations (B9), and at which time scales does the signal hold structure (B10)? Both questions need a fair reference for what a method finds in a signal without real events. The AAFT copy provides it: it keeps every value of the recording and how much the signal wanders slowly or quickly, but scrambles the order in which the values arrive, so the copy has the same ingredients but no real events. Whatever a method still finds in the copy comes from those ingredients, not from the fungus. A wavelet-ridge method borrowed from mass spectrometry, which marks drops of any duration, seemed to find drops clustered at particular durations. On the AAFT copies, however, it found even more drops (1,087 against 632 on the recordings), with the same spread of durations and the same apparent clusters (Figure~\ref{fig:b9hist}); only on M2\_concat did the real drops run somewhat longer. The clusters come from the signal's values, not from events preferring one duration. The matrix profile, which looks for the closest repeat of every stretch of a chosen length, was run at lengths from 30 seconds to tens of minutes. On four recordings, stretches repeated more closely than in the AAFT copies at every length from 30 seconds up to between 4 and 25 minutes, most strongly at the shortest, with no length standing out (Figure~\ref{fig:b10motif}, Appendix~\ref{app:supp}); on MJu26a, whose stretch is a steady oscillation of about 20 minutes that the copy keeps, no length did. The CNN templates agree: those reading 10- and 60-minute windows find more on the recordings than on their copies, and those reading 1-minute windows do not. So on no recording, and in neither species, did the events prefer one time scale over another: structure spans every scale from seconds to minutes, and, as for the detectors, the verdict depends on the choice of null.

""" + f_b9.strip() + "\n"
t = para_replace(t, "Is there a preferred time scale? A wavelet-ridge method",
                 "the choice of null decides the verdict.\n", NEW_METH)

NEW_SUM = r"""Table~\ref{tab:rbsummary} shows the summarised questions and results discussed in this chapter. For the sake of brevity, many of the detailed explanations of these results and their corresponding figures can be viewed in Appendix~\ref{app:supp}. It was found from these experiments that, largely, signal events recur in shared shapes across recordings and species. The intervals between events (limited by the accuracy of the drop detector for event detection) are numerically random, and overall activity can drift over hours to days. Structure is seen at every time scale from seconds to minutes, and event shapes are not seen to travel between electrodes. Each verdict is compared to a stated null, the choice of which the results were sensitive to. These results are to be seen as a tentative exploration of potential questions the large candidate base across recordings and species allows; more rigorous statistical analysis and event definitions are necessary."""
t = para_replace(t, "Table~\\ref{tab:rbsummary} gathers the studies.", "several changed when the null changed.", NEW_SUM)

n_pin = t.count("\\begin{figure}[htbp]")
t = t.replace("\\begin{figure}[htbp]", "\\begin{figure}[H]")

t5 = io.open(CH5, encoding="utf-8").read()
t5 = rep(t5, "Figure~\\ref{fig:anatomyevent} shows how an event is measured from its span, and Figure~\\ref{fig:anatomytrain} "
             "how a train of events is summarised.",
         "An event is measured from its span by its depth, the speed of its fall, its width at half depth and its "
         "recovery (Chapter~\\ref{ch:events}), and a train of events by the gaps between consecutive onsets "
         "(Chapter~\\ref{ch:roundb}).")
t5 = rep(t5, "with electrodes inserted into their fruiting bodies and wired out of the tent.}",
         "with electrodes inserted into their fruiting bodies and wired out of the tent to the recording computer, whose "
         "screens show recorded potentials.}")

io.open(CH10, "w", encoding="utf-8").write(t)
io.open(APPENDIX, "w", encoding="utf-8").write(app)
io.open(CH5, "w", encoding="utf-8").write(t5)
print("done; figures pinned:", n_pin)

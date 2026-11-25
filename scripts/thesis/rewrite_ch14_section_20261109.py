"""Replace Chapter 10's CH14 section with the whole-train reading and the two-band analysis (9 Nov, author's direction).
Numbers: docs/thesis/data/ch14_bands_20261109/ (ch14_bands_20261109.py) and the 530-spike measurements."""
from __future__ import annotations

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH10 = os.path.join(ROOT, "docs", "thesis", "chapters", "10_roundb.tex")
t = io.open(CH10, encoding="utf-8").read()
a = t.index("\\section{A longer reviewed train on MJu26a CH14}")
b = t.index("\\section{Recovery and the gap before it}")
new = r"""\section{A longer reviewed train on MJu26a CH14}
\label{sec:mjuch14train}

The longest reviewed sequence in the thesis is a train of spikes on MJu26a CH14, from 382.5 to 473.2 hours: 90.7 hours, nearly four days (Figure~\ref{fig:ch14bands}a). On this channel a spike is a brief downward deflection, a fall and a fast return. A detector tuned to brief downward spikes\footnote{BEADS baseline removal (2,000\,s period, downward polarity), then a signal threshold at $-0.957$\,mV with a minimum duration of 1.5\,s.} proposed candidates along the whole train, and each was reviewed: 515 of the 559 were accepted. Measured with the event-shape rules of Chapter~\ref{ch:events}, the accepted spans hold 530 individual spikes, with a median depth of 9.2\,mV and a median half-recovery time of 2.5\,s.

Plotted against time, the spikes' depths fall into two distinct bands that both drift upward over the four days (Figure~\ref{fig:ch14bands}b). Each spike was assigned to a band by its depth relative to the local level of the lower band, and the two separate cleanly, the upper band sitting 1.3 to 1.6 times deeper (Figure~\ref{fig:ch14bandmeasures}). A third, small group of 44 shallow spikes, about 2\,mV deep, is kept apart. The lower band runs through the whole train: 334 spikes of about 8.7\,mV that recover halfway in about 2\,s. The upper band appears at about 402 hours and continues to the end: 152 spikes of about 13\,mV that recover far more slowly, halfway in about 13\,s.

Each band on its own is almost perfectly regular. The gap from one lower-band spike to the next shrinks slowly from about 27 to 11 minutes over the train, and the gap between upper-band spikes settles near 23--25 minutes (Figure~\ref{fig:ch14bands}c). Their local variation is 0.10 and 0.03, close to a dripping tap. The two bands also interleave: an upper spike is followed by a lower one 99\,\% of the time, against 64\,\% when the band labels are shuffled ($p<0.001$). Taken together, the 450 spikes from 406 hours on give an LV of 0.77, close to random, so the apparent irregularity of the whole train comes from two regular series running side by side. Before the upper band appears, the train is a single series with an LV of 0.37.

This is the clearest structure in the thesis. One electrode records two distinct, near-periodic series of spikes, which differ in size and in how fast they recover, and which run together for more than two days. Whether they come from two sources near the electrode or from one source in two states cannot be told from one channel. It is one train on one channel, and the detector census shows close-to-random timing elsewhere (Section~\ref{sec:rb_sequences}), so it is a case study rather than a rule.

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{new/ch10_ch14_train_bands.pdf}
\caption[{The reviewed MJu26a CH14 train and its two amplitude bands.}]{The reviewed MJu26a CH14 train and its two amplitude bands. (a) The 90.7-hour signal as one-minute minima and maxima; each spike is a brief downward line. (b) Each of the 530 spikes' depth, onset to trough, against time, coloured by band: the lower band (blue) throughout, the upper band (orange) from about 402 hours (dotted line), and 44 shallow spikes (grey). (c) The gap from each spike to the next spike of the same band: each band is close to periodic, with the lower band's gap shrinking slowly over the four days.}
\label{fig:ch14bands}
\end{figure}

\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{new/ch10_ch14_band_measures.pdf}
\caption[{The two CH14 bands compared.}]{The two CH14 bands compared. Left: each spike's depth divided by the local level of the lower band, which separates the bands cleanly. Centre: half-recovery time, about 2\,s for the lower band and about 13\,s for the upper. Right: the gap to the next spike of the same band, about 16 and 25 minutes at the median.}
\label{fig:ch14bandmeasures}
\end{figure}

"""
t = t[:a] + new + t[b:]
io.open(CH10, "w", encoding="utf-8").write(t)
print("CH14 section replaced")

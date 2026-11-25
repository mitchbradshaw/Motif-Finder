"""Draft the empty sections of Chapters 9 and 10 (9 Nov) from their notes and Chapter 10's summary table, for the
author to edit. Prose goes directly under each section heading/label; the notes stay (hidden in the clean build).
Chapter 9 also gets the binding fallback table of a typical event, and its unjudged-pool figure moves to Appendix I.
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import APPENDIX, THESIS, cut  # noqa: E402

CH9 = os.path.join(THESIS, "chapters", "09_events.tex")
CH10 = os.path.join(THESIS, "chapters", "10_roundb.tex")


def after(text, anchor, prose):
    if text.count(anchor) != 1:
        raise SystemExit(f"anchor not unique: {anchor[:60]!r} ({text.count(anchor)})")
    return text.replace(anchor, anchor + "\n" + prose.strip("\n") + "\n", 1)


t10 = io.open(CH10, encoding="utf-8").read()
t10 = after(t10, "\\section{How the questions were chosen}\n", r"""The studies of this chapter were fixed on 27 October from the questions the earlier chapters left open, under four rules: each had to be answerable on the site with little new building, and to have one null, one figure, and a stated claim and non-claim (Table~\ref{tab:roundb}, Appendix~\ref{app:supp}).""")

t10 = after(t10, "\\section{Sequences and timing}\n\\label{sec:rb_sequences}\n", r"""How are events spaced in time? Each drop-detector event was timed from the moment its fall begins, and the gaps between events on each channel were compared with two references: a random train with the same rate, and the same gaps shuffled into a random order. The measure is the local variation (LV), which compares each gap only with the next one. Raindrops on a roof score about 1, and a dripping tap scores 0. On the 44 channels of five recordings with enough events, no channel's timing differed from random once the many channels tested were accounted for, and only two were more regular by a companion measure, CV2 (Figure~\ref{fig:b1lv}). Neighbouring gaps were, however, more alike than in a shuffled order on 15 channels, and on every recording: the rate drifts, busier for some hours and quieter for others.\footnote{Events are timed from the fall onset the detector marks. The database keeps only the window the detector drew around each event, which starts a median of 9.7 minutes earlier, so every run was recomputed and checked against the database first (Appendix~\ref{app:decisions}).} For the mushrooms, the timing looks random from one event to the next, while the overall level of activity rises and falls over hours to days. Sequences of drops told a similar story: neighbouring drops in a sequence stay alike rather than changing steadily from one to the next (Table~\ref{tab:rbsummary}). A single channel can still produce a long and more regular train, as the next section shows.""")

t10 = after(t10, "\\section{Recovery and the gap before it}\n\\label{sec:rb_models}\n", r"""Does a drop recover more slowly when the gap before it was long, as heart muscle recovers according to how long it has rested? Within the reviewed trains, the apparent link vanished once each drop's depth was taken into account, and the gap after a drop predicted its recovery far more strongly than the gap before, because a recovery is simply cut short when the next drop arrives (Figure~\ref{fig:b3restitution}). Across the longer gaps of the detector census, a weak link remained on the two M2 recordings, halved once the duration of the fall was accounted for. There is therefore no evidence that a drop's recovery depends on the rest before it within trains, and only a bounded hint across long gaps. The excitable-system models first planned for this question were set aside when they fitted surrogate noise as well as the data.""")

t10 = after(t10, "\\section{Shapes and families across recordings}\n\\label{sec:rb_families}\n", r"""Are shapes shared between recordings and species? Of the 42 shape families of the working grouping (Section~\ref{sec:families}), 39 contain events from two or more recordings, and 28 from both species they cover (Figure~\ref{fig:b6species}). Families are not spread at random, though. Each recording leans towards some families, and the lean by species is no larger than the lean by recording. Six simple shape measures of the 716 accepted blind-panel events tell the same story (Figure~\ref{fig:b12shape}): recordings differ a little on most measures, while species differ on only one of fifteen comparisons, the share of falls, against seven of fifteen between two recordings of the same species. The timing of events differs between recordings only at the margin. For the mushrooms, the same shapes occur across recordings and species, and the differences between cultures and setups are at least as large as the differences between species.""")

t10 = after(t10, "\\section{Activity across channels}\n\\label{sec:rb_channels}\n", r"""Does activity travel from one electrode to another? A census of drop-detector events looked for pairs on two channels within 50 seconds of each other, measured each pair's delay and waveform similarity, and compared the count with whole trains shifted in time against each other. On M2\_aug, channels in the same pack co-occurred more often than chance (8 against 1.9 expected), but only one pair survived correction for testing many pairs, and it showed no consistent delay. Across packs, 18 pairs co-occurred against 6.3 expected, all at the same instant, and most fell inside bursts in which almost every channel jumps at once (Figure~\ref{fig:b4stack}). M2\_concat's co-occurrences are copies between four electrodes (CH5--8), CO and LM had none, and MJu26a, SH and SO co-occurred above chance but only at one instant (Figure~\ref{fig:b4bins}). Nothing was seen travelling between electrodes at these spacings and sampling rates. What separate packs share at one moment looks like the setup or the room, not the culture.""")

t10 = after(t10, "\\section{Time scales and methods from other fields}\n\\label{sec:rb_methods}\n", r"""Is there a preferred time scale? A wavelet-ridge method borrowed from mass spectrometry suggested that fungal events have preferred durations, but its AAFT copies, the same values in a scrambled order, gave even more drops with the same durations (Figure~\ref{fig:b9hist}). The apparent preferred durations come from the null, not from the signal. Matrix profiles across window lengths (Figure~\ref{fig:b10motif}) found repeats closer than in AAFT copies at every judged length from 30 seconds up to between 4 and 25 minutes on four recordings, strongest at 30 seconds, with no single length standing out. On MJu26a's span, a steady oscillation of about 20 minutes that AAFT keeps, none did. The CNN templates agree: those reading 10- and 60-minute windows find more on the recordings than on their copies, and those reading 1-minute windows do not. Structure in these signals spans every scale from seconds to minutes rather than sitting at a few characteristic durations, and, as Chapter~\ref{ch:rq1} found for the detectors, the choice of null decides the verdict.""")

t10 = after(t10, "\\section{Summary}\n", r"""Table~\ref{tab:rbsummary} gathers the studies. Read together, they describe signals whose events recur in shared shapes across recordings and species, arrive close to randomly from one to the next while the overall activity drifts over hours to days, show structure at every time scale from seconds to minutes, and do not travel between electrodes. Each verdict rests on a stated null, and several changed when the null changed.""")
io.open(CH10, "w", encoding="utf-8").write(t10)
print("Chapter 10 drafted")

t9 = io.open(CH9, encoding="utf-8").read()
t9 = after(t9, "\\label{fig:acceptedgallery}\n\\end{figure}\n", r"""
Until the boundaries of the expanded inventory are checked, two populations whose events have been measured give a first picture of a typical accepted event (Table~\ref{tab:typicalevent}): the 530 individual spikes of the reviewed MJu26a CH14 train (Section~\ref{sec:mjuch14train}), and the 716 accepted events of the blind detector panels. The full table, of checked individual events on every recording, waits on that boundary review.

\begin{table}[htbp]
\caption[{A first picture of a typical accepted event.}]{A first picture of a typical accepted event, from the two measured populations: medians, with the 5--95\,\% range in brackets. The blind-panel span lengths are largely detector framing (about a quarter are 10-minute windows), not event durations.}
\label{tab:typicalevent}
\small
\begin{tabularx}{\textwidth}{@{}X r l@{}}
\toprule
\textbf{Population and measure} & \textbf{$n$} & \textbf{Median (5--95\,\%)}\\
\midrule
MJu26a CH14 train: depth, onset to trough & 530 & 9.2\,mV (2.5--14.6)\\
\quad half-recovery time & 529 & 2.5\,s (0.8--17.4)\\
\quad interval between spikes & 529 & 603\,s (51--1,359)\\
Blind detector panels, five recordings: swing & 716 & 19.8\,mV (14--30 by recording; top 5\,\% above 122)\\
\quad span length & 716 & 603\,s (40--1,272)\\
\quad share that are falls (fastest-edge rule) & 716 & 91\,\% (76--98\,\% by recording)\\
\bottomrule
\end{tabularx}
\end{table}
""")

t9 = after(t9, "\\section{One recording in detail: spiking families}\n\\label{sec:spikingfamilies}\n", r"""One recording was examined in detail for the shapes and sizes of its spikes: a four-hour excerpt of MJu26a CH14, which lies inside the 90.7-hour train that Chapter~\ref{ch:roundb} analyses for timing (Section~\ref{sec:mjuch14train}); the drop family's spread across the channels of M2\_aug is in Chapter~\ref{ch:rq2}. Matrix profiles at one minute suited single spikes, while at three and ten minutes the windows were mostly baseline. The excerpt holds two amplitude regimes, spikes of about 7--14\,mV peak to peak and a separate family of sub-millivolt ones (about 0.4--0.6\,mV), so ``a spike'' on these recordings is at least two things. Some families are stereotyped in amplitude (a standard deviation of about 0.15\,mV), others are not (1.6--3.1\,mV), and members of a family recur with a median interval of 15--23 minutes. Under the current grouping only one family here holds five or more falls (F-64), while the largest (F-97) holds recoveries (Figure~\ref{fig:rec385}). Every window length from 30\,s to 16 minutes repeats beyond AAFT noise in this excerpt, strongest at 30\,s, so its scale is read from the whole range of lengths, not from one window.""")

t9 = after(t9, "\\section{Events no one has judged}\n\\label{sec:pool}\n", r"""How many events would the Library hold if every candidate on which five or more detector families agree were counted? Merging nested candidates leaves about 64,000 unjudged events at five or more families and 10,600 at nine or more across the five swept recordings, against 1,097 events in the Library (Figure~\ref{fig:pool}). They are smaller than the accepted events, growing towards them as agreement rises, and R4 calls roughly 4,500 of the top tier events, about four times the Library. These are machine proposals; none of them enters the Library.""")

t9 = after(t9, "\\section{Discussion}\n", r"""The typical accepted event on these recordings is a fall in potential of roughly ten to twenty millivolts that recovers more slowly than it fell, from seconds to tens of minutes long, often with smaller deflections riding on it; by the tool's fastest-edge rule, 91\,\% of the accepted blind-panel events are falls. The same kind of fall appears on every recording and species, with differences between recordings as large as those between species (Chapter~\ref{ch:roundb}). This is in line with the sharp depolarisation and slow repolarisation described by Slayman et al.\ \cite{slayman} and with the multi-scale spiking reported by Adamatzky \cite{adamatzky2023}, with differences of size and duration that sampling rate and electrode type would explain. What generalises across recordings is that drops dominate, and the ranges of their sizes and durations; the two amplitude regimes of MJu26a CH14 are a case study. Two cautions apply to any vocabulary built on this catalogue. A Ward cut is an imposed grouping, not a discovered taxonomy, and a normalised shape still carries its recording's resolution, so shape names must be compared at matched sampling rates. Some names already have a measurable counterpart: a drop is what the drop detector finds, a spike what its inverted form finds, and a sharkfin the symbolic pattern of a rise, an optional plateau and a fall. Finally, the catalogue shows what one reviewer accepted from what the tools proposed, so it describes the large, sharp end of the signal better than its quiet background.""")

t9, block = cut(t9, "fig:pool")
io.open(CH9, "w", encoding="utf-8").write(t9)
app = io.open(APPENDIX, encoding="utf-8").read()
heading = "\\section*{From Chapter~\\ref{ch:events}: events}"
at = app.find(heading)
end = app.find("\\clearpage", at)
app = app[:end] + block.rstrip("\n") + "\n\n" + app[end:]
io.open(APPENDIX, "w", encoding="utf-8").write(app)
print("Chapter 9 drafted; pool figure moved")

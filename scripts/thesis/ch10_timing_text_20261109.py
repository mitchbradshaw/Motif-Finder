"""Chapter 10 (9 Nov, author's edits): the events-section close, the timing section's method in plain words (why the
drop detector, the two nulls, how LV is computed), Figure 5.3 moved here; Chapter 9's anatomy caption explains half
depth."""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from move_floats_20261109 import THESIS, cut  # noqa: E402

CH5 = os.path.join(THESIS, "chapters", "05_methodology.tex")
CH9 = os.path.join(THESIS, "chapters", "09_events.tex")
CH10 = os.path.join(THESIS, "chapters", "10_roundb.tex")


def rep(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"{text.count(old)} matches for {old[:70]!r}")
    return text.replace(old, new)


t10 = io.open(CH10, encoding="utf-8").read()
t10 = rep(t10,
          "They add examples rather than sequences, though. A sample of accepted shapes can strengthen a comparison of "
          "shapes, but the gaps between sampled examples say nothing about how often a culture produces events. The "
          "timing studies therefore rest on detector censuses over whole channels, and on the one long train that was "
          "reviewed from end to end (Section~\\ref{sec:mjuch14train}).",
          "They add examples rather than sequences, though. A sample of accepted event shapes does not show how often a "
          "culture produces events. To estimate how often events occur, the timing studies need a census over whole "
          "channels, every event one detector finds from start to end, and they use the drop detector because "
          "Chapter~\\ref{ch:rq1} found its candidates the most often accepted (Section~\\ref{sec:rb_sequences}). The "
          "train of Section~\\ref{sec:mjuch14train} is a 90.7-hour run of 530 spikes on MJu26a CH14, reviewed in full "
          "because its events are particularly clean and its sequence unusually long.")

old = t10[t10.index("How are events spaced in time? Each drop-detector event was timed"):]
old = old[:old.index("The measure is the local variation (LV), which compares each gap only with the next one. "
                     "Raindrops on a roof score about 1, and a dripping tap scores 0.")
          + len("The measure is the local variation (LV), which compares each gap only with the next one. "
                "Raindrops on a roof score about 1, and a dripping tap scores 0.")]
t10 = rep(t10, old, r"""How are events spaced in time? The census uses one detector, the drop detector (v1), because its candidates were the most often accepted of any detector in Chapter~\ref{ch:rq1} (an estimated 92--100\,\% on each of the five recordings), so the events it counts are nearly all events a person would accept. Each event is timed from the moment its fall begins, and the gaps between consecutive events on a channel are measured (Figure~\ref{fig:anatomytrain}). Two references, both standard in the analysis of neural spike trains, say what the gaps would look like by chance. The first is a random (Poisson) train: the same number of events over the same time span, placed at random times. The second keeps the channel's own gaps and shuffles them into a random order, which keeps how long the gaps are but destroys any relation between one gap and the next. The measure is the local variation (LV) of Shinomoto et al.\ \cite{shinomoto2003lv}, which compares each gap $I_i$ only with the next one,
\[ \mathrm{LV} = \frac{3}{n-1}\sum_{i=1}^{n-1}\left(\frac{I_i - I_{i+1}}{I_i + I_{i+1}}\right)^{2}, \]
so a slow drift in the overall rate barely changes it. A random train scores about 1, like raindrops on a roof, a perfectly regular one 0, like a dripping tap, and a bursty one more than 1.""")

t5 = io.open(CH5, encoding="utf-8").read()
t5, train_fig = cut(t5, "fig:anatomytrain")
anchor = "\\section{Sequences and timing}\n\\label{sec:rb_sequences}\n"
i = t10.index(anchor)
j = t10.index("\n\n", t10.index("How are events spaced in time?")) + 2
t10 = t10[:j] + train_fig + "\n" + t10[j:]

t9 = io.open(CH9, encoding="utf-8").read()
t9 = rep(t9, "Chapter~\\ref{ch:events} reports these measures for every accepted event.",
         "The dotted line marks half the depth below the onset level; the time the event spends below it is its full "
         "width at half depth (FWHM), here 327\\,s. Table~\\ref{tab:inventorymeasures} reports these measures for every "
         "accepted single event.")
io.open(CH5, "w", encoding="utf-8").write(t5)
io.open(CH9, "w", encoding="utf-8").write(t9)
io.open(CH10, "w", encoding="utf-8").write(t10)
print("done")

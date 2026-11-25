"""Write Chapter 11's drafted prose in place of its notes (9 Nov), keeping its three tables. For the author to edit.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/draft_ch11_20261109.py
"""
from __future__ import annotations

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH11 = os.path.join(ROOT, "docs", "thesis", "chapters", "11_discussion.tex")
text = io.open(CH11, encoding="utf-8").read()


def replace_block(start_marker, end_marker, new):
    global text
    a = text.find(start_marker)
    b = text.find(end_marker, a)
    if a < 0 or b < 0:
        raise SystemExit(f"block not found: {start_marker[:50]!r}")
    text = text[:a] + new + text[b + len(end_marker):]


replace_block("\\begin{instructions}\nAbout 5 pages; Conclusion is 15", "\\end{instructions}\n\n", "")

replace_block("\\begin{instructions}\nOne paragraph per research question", "\\end{instructions}\n", r"""This thesis asked whether recurring structure in fungal bio-electric recordings can be detected automatically and trusted, and what that structure is (Section~\ref{sec:rqs}). Both halves have an answer. Recurring structures can be found at scale, and with a blind reviewer and a surrogate null they can be trusted to a stated degree (Chapters~\ref{ch:rq1}--\ref{ch:rq3}). Characterising them shows a dominant fall-and-recovery event that recurs across species, irregular timing with slowly drifting activity, and no evidence of activity travelling between electrodes (Chapters~\ref{ch:events} and~\ref{ch:roundb}).

\paragraph{Detectors compared at scale (Chapter~\ref{ch:rq1}).} Thirteen detector families in 45 settings ran over 2,599 hours of recordings and proposed about 3.1 million candidate events, of which 1,959 were judged blind. Agreement between families predicted acceptance on every recording. Where one or two families agreed, 0--5\,\% of candidates were real, and where nine or more agreed, 40--63\,\% were; the held-out M4 showed the same ladder, from 0 to 53\,\%. The choosy drop detectors held their precision across recordings, while the loose detectors fired on the background about as readily as on events. Against 20 surrogate draws, drop v1 and the GADF CNN beat every draw on all 16 channels of M2\_aug.

\paragraph{Seeds (Chapter~\ref{ch:rq2}).} Every seed retrieved matches that were accepted far more often than random windows of the same length, judged blind (100 of 100 drop matches against 9 of 40 random windows, for example; Fisher $p<0.0001$ for each seed), and every earlier positive judgement held when repeated blind. The same drop seed, unchanged, transferred to seven other recordings of three species: 455 of 457 matches were accepted, against 79 of 459 random windows, and on all eight recordings the matches occur one electrode at a time.

\paragraph{Classifiers (Chapter~\ref{ch:rq3}).} MiniRocket trained on the tool's verdicts (R4) reached an AUC of 0.971 on recordings it had not been trained on, against at most 0.49 with shuffled labels, and 0.98 (balanced accuracy 0.93) on the held-out M4, scored once, where the reference CNNs reached 0.59--0.66. A CNN trained on R4's own examples matched R4, so the reference CNNs' gap lay in their training labels rather than their architecture, and labels derived from clusters did not replace human labels.

\paragraph{The events (Chapters~\ref{ch:events} and~\ref{ch:roundb}).} The reviews accumulated 2,959 accepted spans across eight recordings of three species. Most accepted events are falls in potential followed by a slower recovery, from seconds to tens of minutes long and from a few to about a hundred millivolts deep, and one MJu26a channel produced a 90.7-hour train of 530 spikes. From one event to the next the timing is close to random, while activity drifts over hours to days and whole recordings grow busier and quieter together (B1, B5). Shapes recur across recordings and species, each recording leaning its own way more than each species does (B6, B12). There is structure beyond noise at every window length from 30\,s to minutes, with no preferred scale (B10), and no sign of activity travelling between electrodes (B4).
""")

replace_block("\\begin{instructions}\nPoints to link across the chapters:", "\\end{instructions}\n", r"""\subsection{What the results say about fungal signals}

\paragraph{The recordings contain stereotyped, recurring waveforms.} One drop recurs hundreds of times in a 30-day oyster recording, while copies with the same frequency content almost never contain it (Table~\ref{tab:seeds}). Among the studies reviewed in Chapter~\ref{ch:intro}, this is the first surrogate-controlled evidence of recurrence in these signals, and future recordings should report recurrence against such a null as standard.

\paragraph{The same shape occurs across species.} The drop chosen in oyster was found and accepted in lion's mane, shiitake and two other oyster strains, at amplitudes a hundredfold apart (Figure~\ref{fig:transferexamples}). The fast change followed by a slow return, described since Slayman et al.\ \cite{slayman}, appears to be a common feature, and differences between recordings are as large as differences between species (B6, B12). Comparing species fairly will need several recordings of each.

\paragraph{Events are not cleanly separated from the background.} Small falls occur almost continuously, and what a person picks out is the large, sharp end of a continuum (Chapter~\ref{ch:rq1}, Section~\ref{sec:pool}). This is why agreement between methods, and a stated null, matter more here than for a signal such as the ECG, whose events stand clear of the baseline. More reviewers, and the agreement between them, would define that end more firmly.

\paragraph{Timing is irregular, with slowly drifting activity.} No constant period like the 34-minute oscillation of Slayman et al.\ appeared. From one event to the next the timing is close to random, while whole recordings grow busier and quieter over days (B1, B5), though a single channel can still produce a long, more regular train (Section~\ref{sec:mjuch14train}). Logging temperature and humidity alongside the potentials would show whether the drift belongs to the culture or to the room.

\paragraph{No sign of propagation between electrodes.} At these electrode spacings and sampling rates, nothing was seen travelling from one electrode to the next (B4). What separate packs share happens at one instant, which points to the setup or the room. Electrode maps with known spacings, and higher sampling rates, are needed to test propagation directly.

\paragraph{No preferred time scale.} Structure appears at every window length from 30\,s to minutes (B10), and the apparent preferred durations of the wavelet method come from its null (B9). This bears on the multi-scale spiking described by Adamatzky et al.\ \cite{adamatzky2023}: claims of characteristic durations should be tested against a null that keeps the signal's values.

\subsection{What worked, and what did not}

Several techniques proved their worth: the choosy drop detectors, agreement between detector families as a review priority, seed search, MiniRocket, and AAFT copies as the null for measures that read the signal's values. Others were dead ends on these recordings. The whole-signal matrix-profile threshold found nothing that was accepted in the blind samples, the 1-minute CNNs marked almost every minute and served only as negative controls, the fused image encoding did not beat its components, and the early attempt to forecast the next value was dominated by noise. The Dehshibi detector, ported faithfully from its authors' code, was unselective here, and the wavelet-ridge detector found no more structure than its input's values give. One lesson recurs: resampling a shape to a fixed length removes its duration and amplitude but not its resolution, so a normalised shape still carries a trace of how it was recorded (Section~\ref{sec:dropmotifs}). None of the fungal studies of Chapter~\ref{ch:intro} reports detector precision against blind human judgement or against a surrogate, and here doing so changed several conclusions.
""")

replace_block("\\begin{instructions}\nMoved here from Chapter~\\ref{ch:intro} on 5 Nov", "\\end{instructions}\n\n", "")

replace_block("\\begin{instructions}\nWrite the review in your own voice", "\\end{instructions}\n", r"""Table~\ref{tab:rqmap} maps the plan's six research questions to where they are answered, Table~\ref{tab:planreview} compares the plan with what was done, and Table~\ref{tab:schedulereview} compares its schedule with what happened. The main trade of the year was time spent on the instrument. The plan expected a working tool by the end of August and a season of analysis after it. Instead, the first, Panel-based version did not scale and was rebuilt in React, and the tool was still being built until 21 October. That bought comparable runs, blind review queues, a null beside every result, and recipes that can be re-run, and it made the later results quick to obtain: the detector sweep and the classifier took days rather than weeks. It cost the breadth of the plan, since three of its six questions are answered in full and the scale and cross-channel questions only as pilots.

Three decisions changed the project's direction. When the deadline moved on 23 September, the plan became to build first and answer the questions afterwards, which made the remaining weeks of building worthwhile but left less time for the questions. The six planned questions were narrowed to three, because comparing detectors at scale subsumed the questions on bands and symbols and on human and machine divergence, while the scale and cross-channel questions needed judging there was no time to do. And the excitable-system models of Chapter~\ref{ch:roundb} were parked when they fitted surrogate noise as well as they fitted the data, which kept the effort on results that could be tested.

In hindsight, three things would be done differently: freeze the tool earlier, so that more of the year goes to the questions; keep the held-out recording's lock on throughout, rather than switching it off for the demonstrations; and record each CNN's training data and labels from the start, which would have shown sooner that the reference CNNs' weakness lay in their labels.
""")

replace_block("\\begin{instructions}\n\\begin{itemize}\n  \\item A single labeller", "\\end{instructions}\n", r"""All human judgements come from one reviewer, whose repeated verdicts agree 94\,\% of the time; a second, independent reviewer is the most important addition. The recordings come from one laboratory and three species, with oyster dominant, so species comparisons rest on few recordings each. The detector and seed nulls are phase-randomised, which scrambles a sudden fall easily; re-running the seed nulls against AAFT copies, the harder test of Chapter~\ref{ch:roundb}, should come first. Candidates come only from detectors, so there is no estimate of the events every detector missed, and the sweep has one surrogate per run (twenty only on M2\_aug). The groupings into shape families are sensitive to small changes, and shape normalisation does not remove the trace of resolution. The held-out recording was exposed to detector output before its exam (Section~\ref{sec:holdout}). No environment logs were available, so activity could not be compared with temperature or humidity. The later review queues were drawn to fill gaps rather than at random, so the catalogue describes what was looked for, and not all of its event boundaries have been checked. Finally, the timing census rests on one detector's events, and 20 of its 56 channels have fewer than ten; a second detector's census would test it.
""")

replace_block("\\begin{instructions}\nCarried from the plan and updated:", "\\end{instructions}\n", r"""Forecasting comes first. A model that predicts what a culture does next, against a simple baseline such as the most frequent next value, is the precondition for interpretation, because only a structure that predicts what follows is worth decoding. Cross-species validation is half prepared: a second unseen-recording exam, on another laboratory's recording of \emph{Schizophyllum commune}, has a frozen manifest and a drawn blind sample waiting to be judged. Recording the environment alongside the potentials, with covariate series registered with each recording, would test whether activity follows temperature. A classifier over named shape families, with an explicit background class, needs 100--200 verified members per class. Searching across durations was piloted on a 102\,s trough seed at 0.8, 1 and 1.25 times its length. Stretching brought two candidates much closer to the seed, but at the pilot's loose threshold the copies returned more matches than the recording, so each duration needs its own null, and whether a person judges a stretched match to be the same kind of event is untested. The Library needs event extents and a way to merge partial motifs, and the statistics need 20-draw nulls beyond M2\_aug and the interval census on every recording. Two round-B questions, multiscale entropy (B7) and motif prevalence (B8), remain open. Further methods worth adding are the Morse-wavelet component of the Dehshibi detector as a reusable feature, interval temporal logic for sequences of windows, and diffusion models for synthetic training data.
""")

replace_block("\\begin{instructions}\nWrite last. Half a page.", "\\end{instructions}\n", r"""Recurring structure in fungal bio-electric recordings can be detected automatically and characterised, with a stated precision against blind human judgement and a stated null. Three results stand out. Agreement between independent detectors predicts what a person accepts, on every recording, including one held out until the end. A single drop shape chosen in one oyster recording recurs in lion's mane, shiitake and two other oyster strains and is accepted there almost without exception, so the recordings share a repeatable unit from which a vocabulary could be built. And a classifier trained only on judgements gathered with the tool ranks the events of an unseen recording almost as a person would. What these events mean for the fungus is not yet known: their timing is close to random from one event to the next, their rate drifts over days, and nothing travels between electrodes at these spacings. The field's next step is methodological. Detector results should be reported with their precision against blind judgement and against a surrogate as standard, because without both, a detector's output cannot be told apart from the spectrum of the signal it reads.
""")

io.open(CH11, "w", encoding="utf-8").write(text)
print("Chapter 11 drafted; instruction blocks left:", text.count("\\begin{instructions}"))

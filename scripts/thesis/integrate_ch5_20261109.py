"""Integrate Chapter 5 (9 Nov): the author's edits to the drafted sections, resolved notes removed, Table 5.3 to
Appendix I. Exact-string replacements; refuses if any anchor is missing.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/integrate_ch5_20261109.py
"""
from __future__ import annotations

import io
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH5 = os.path.join(ROOT, "docs", "thesis", "chapters", "05_methodology.tex")
APP = os.path.join(ROOT, "docs", "thesis", "appendices", "I_supplementary.tex")

text = io.open(CH5, encoding="utf-8").read()


def replace_block(start_marker, end_marker, new, *, keep_end=False):
    """Replace from start_marker up to (and including, unless keep_end) end_marker."""
    global text
    a = text.find(start_marker)
    if a < 0:
        raise SystemExit(f"start not found: {start_marker[:60]!r}")
    b = text.find(end_marker, a)
    if b < 0:
        raise SystemExit(f"end not found: {end_marker[:60]!r}")
    b = b if keep_end else b + len(end_marker)
    text = text[:a] + new + text[b:]


def replace_once(old, new):
    global text
    if text.count(old) != 1:
        raise SystemExit(f"expected one match for {old[:70]!r}, found {text.count(old)}")
    text = text.replace(old, new)


# Chapter-top note (resolved).
replace_block("\\begin{instructions}\nAbout 4--5 pages. Built from the plan's Chapter 4", "\\end{instructions}\n\n", "")

# 5.1 Corpus: the author's setup paragraph, the photo, the naming paragraph, and the short note after the table.
replace_block(
    "The recordings are long multi-electrode potential measurements from living fungal cultures. All come from",
    "reishi appears only in the early drop study of Chapter~\\ref{ch:early}.",
    r"""The recordings are long multi-electrode potential measurements from living fungal cultures. Each measurement is the potential difference, in volts, between an electrode and a reference point, the ground. For most of the datasets in this thesis, the electrodes were inserted into the fruiting bodies of the cultures and measured against a common ground at the base of the fruiting bodies, which gives a meaningful way of distinguishing relative behaviour across the array of electrodes. Most cultures were grown in grow packs or jars, self-contained systems that give the mycelium all the nutrients and conditions it needs to grow once it is exposed to fresh oxygen (Figure~\ref{fig:setup}). A typical setup has four measurement electrodes per pack; in M2\_aug, 16 channels record four sets of four electrodes, in packs A--D. Absolute levels can differ widely between electrodes, with baseline potentials from about 0 to $-3{,}000$\,mV. This is largely due to the setup, drift and artefacts, so every analysis reads changes in potential, not absolute levels. All recordings in the laboratory are taken inside a Faraday cage, to avoid interference from external electrical signals.

\begin{figure}[htbp]
\centering
\includegraphics[height=7.5cm]{new/ch5_setup.jpg}
\caption[{The recording setup.}]{The recording setup in the Underground Brains laboratory: grow packs on the shelves of a grow tent, with electrodes inserted into their fruiting bodies and wired out of the tent.}
\label{fig:setup}
\end{figure}

All recordings come from the Underground Brains research facility at UQ. The first were \emph{Pleurotus ostreatus} (oyster) arrays of 16 electrodes with a shared ground, followed by recordings of other species and setups. Table~\ref{tab:corpus} lists every recording and its role in this thesis. The recordings keep the names they have in the laboratory's files, which the later chapters use throughout. M2\_aug, for example, is the primary 30-day oyster recording, and MJu26a the lion's mane culture grown in a jar. In the oyster arrays, the letter in a channel's name gives its pack (CH12\_C2 is electrode 12, in pack C). The results chapters draw on three species, oyster (with its chocolate and snow oyster strains), lion's mane and shiitake; reishi appears only in the early drop study of Chapter~\ref{ch:early}.""")

replace_block(
    "\\begin{instructions}\nDataset notes (5 Nov):",
    "B4 (Chapter~\\ref{ch:roundb}) relies on it.\n\\end{instructions}\n",
    r"""Some recordings exist in more than one copy, at another sampling rate or as a subset of another recording's channels. Only one copy of each is analysed as a recording in its own right, so every dataset counted is an independent recording. M2\_aug and M2\_concat, in particular, are separate recordings, not crops of one another.
""")

# 5.2 Preprocessing.
replace_block(
    "\\begin{instructions}\nRewrite. The plan's resampling story",
    "straight or too regular to be signal.\n\\end{instructions}\n",
    r"""Preprocessing is kept light, so that what the detectors see is close to what the electrodes recorded. Each recording keeps its native sampling rate, 1\,Hz for the oyster arrays and 2 or 10\,Hz for the others. To account for drift and uneven sampling from the logger's analogue-to-digital converter, each dataset is linearly interpolated back onto an even grid at its native sampling rate, so that every series is evenly sampled before processing. The 10\,Hz recordings are analysed as 2\,Hz derivations, each sample the mean of five consecutive native samples, with nothing else changed. Units are declared per recording, in volts or millivolts, so that analysis results can accurately compare like units.

Artefacts are not removed automatically. ``Artefact'' is a human verdict (Section~\ref{sec:judging}), given to stretches too straight or too regular to come from a culture, such as the two flagged windows of Figure~\ref{fig:handlabels}. Near-identical waveforms on two channels at the same instant are flagged by the machine for a person to check, and only confirmed artefacts are excluded.
""")

# 5.3 Data representation: the shorter version, with the author's window and span sentences.
replace_block(
    "A central component of the framework is the representation of the time-series data",
    "Figure~\\ref{fig:windowmatrix} shows an early example (Chapter~\\ref{ch:early}).\n",
    r"""The analysis works with two kinds of region. A \emph{window} is a fixed-length stretch cut at regular intervals, to divide a signal into discrete chunks for broad analysis; windows with their labels trained the early classifiers (Chapter~\ref{ch:early}). A \emph{span} is a region of any length, with a specific start and end and an optional label recording its source: a detection, a seed match, or a manually flagged stretch of signal. Windows can be cut from spans, but the two are not interchangeable, and the tool's type system keeps them apart (Section~\ref{sec:types}). Per-window results are collected in a \emph{Window Matrix}, one row per window and one column per feature, from statistics, spectral and entropy features and catch22 to symbolic codes, model scores and cluster labels (Figure~\ref{fig:windowmatrix} is an early example). Figure~\ref{fig:anatomyevent} shows how an event is measured from its span, and Figure~\ref{fig:anatomytrain} how a train of events is summarised.
""")

# 5.4 Judging protocol.
replace_block(
    "\\begin{instructions}\nNew section, about one page, central to every result.",
    "answer is never wrong.\n\\end{instructions}\n",
    r"""Every result reported against human judgement rests on verdicts given by one reviewer, on the tool's Review page.

In reviewing spans or windows as a single researcher, telling an ``interesting'' stretch of signal from a ``not interesting'' one came down to whether there appeared to be evidence of a distinct behaviour in the signal, one unlikely to occur in otherwise broadly flat noise with drifts. Stretches were labelled interesting because they appeared to have sharp drops, sharp peaks, or distinct waveform shapes uncharacteristic of regular noise. Sequences were easily detected as a stretch of repeating waveforms with a level of evolution. Artefacts were flagged where a sequence continued for a long stretch with no evolution or noise, indicating an external oscillating error, or where large spikes or drops occurred across only one or two samples, indicating a glitch rather than an event. Figure~\ref{fig:handlabels} shows interesting, not-interesting and artefact windows side by side.

A verdict is one of five words: interesting, not interesting, unsure, artefact, or seed. A seed is an interesting event worth searching for, and counts as interesting throughout. Each result states how it treats unsure answers; Chapter~\ref{ch:rq1} sets them aside, while the seed panels keep them in the denominator, which is stricter.

Most reviews were blind. Candidates were shuffled, and nothing the machine knew was shown, whether the detector or seed that proposed a candidate, its score, how many detectors agreed on it, or whether it was a match or a random control. Only the signal was shown, with context either side, and a span's extent could be redrawn while judging. Where a sample had to estimate how often candidates are real (the detector panels and the held-out exam), candidates were drawn at random within strata, five bands of detector agreement from one or two families up to nine or more, plus one stratum for each rarely firing detector, so that rare kinds of candidate were seen at all. Each answer is then weighted by its stratum's size (Chapter~\ref{ch:rq1}). A verdict on one detection is copied to the detections of the same event in other runs, so it is not asked again, and these carried copies never count as new judgements. Table~\ref{tab:queues} lists every review.

Two judgements made by the same person on the same span at different times do not always agree, as the verdicts are ultimately subjective. In a total of 144 blind repeats, eight answers changed, five from interesting to not interesting or unsure and three the other way, an agreement rate of 94\,\%. Cohen's $\kappa$, which discounts the agreement that chance alone would give (0 is chance, 1 is perfect), was 0.84 and 0.91 in the two checks that make up these repeats. This largely supports the consistency of the human judgement; further work would compare the accepted events with a blind review by a second researcher. The median time per verdict was 1.4\,s, as most candidates could be identified at a glance as noise or as containing an event. All verdicts come from one reviewer, so every precision in this thesis is precision against that reviewer's judgement.
""")
replace_once("RQ3 blind exam; RQ2 base rate (22\\,\\%)", "RQ3 blind exam; RQ2 base rate (21\\,\\%)")

# 5.5 Controls: surrogate comparison.
replace_block(
    "\\begin{instructions}\nPoint back to Section~\\ref{sec:surrogates}",
    "give its own controls.\n\\end{instructions}\n",
    r"""Section~\ref{sec:surrogates} introduced the two references every result is held against. The first is a surrogate, a copy of the signal that keeps its frequency content but scrambles its timing, so that anything a method finds only by responding to the spectrum turns up in the copy too. Each chapter uses the null suited to its question. The detector sweep (Chapter~\ref{ch:rq1}) runs one phase-randomised copy beside every real run, with 20 copies per channel for six settings on M2\_aug as a check. Seed searches (Chapter~\ref{ch:rq2}) use 200 phase-randomised copies per channel. The classifiers (Chapter~\ref{ch:rq3}) are tested against 200 shuffles of their training labels. Measures that read the signal's values, such as matrix-profile distances (Chapter~\ref{ch:roundb}), use AAFT copies, which keep every value of the recording and, approximately, its spectrum, but change the order in which the values occur, so any shape that depends on when they occur is broken up.

The second reference, used wherever a person judges, is the blind base rate, the share of randomly chosen stretches that are accepted. Of 986 random windows judged blind, 210 were called interesting (21\,\%). Each seed panel also carried its own random windows of matched duration on the same channels.
""")

# 5.5 Cross-channel classification: the clause; Table 5.3 to Appendix I; its note removed.
replace_once("A pair counts only if it beats its own random-time null.",
             "A pair counts only if it beats its own random-time null. Only human-confirmed artefacts are removed, and "
             "pairs where one channel has no pack assigned are counted apart, so on recordings without packs set "
             "(M2\\_concat, MJu26a) no shared-driver or propagation bin can be separated.")
m = re.search(r"\\begin\{table\}\[htbp\]\n\\caption\[Classification of cross-channel matches\].*?\\end\{table\}\n\n",
              text, flags=re.S)
if not m:
    raise SystemExit("cross-channel table not found")
table = m.group(0)
text = text[:m.start()] + text[m.end():]
replace_block("\\begin{instructions}\nThe plan's bins were described qualitatively;",
              "is quoted.\n\\end{instructions}\n\n", "")

# 5.6 The held-out exam: the author's rewrite.
replace_once(
    "This section reports, in the same spirit, how far that record held. In brief, M4's detector output was run and "
    "displayed during the October demonstrations, but apart from one annotation made before M4 was declared held out, no "
    "human verdict, Library entry, model or parameter choice touched it before the exam was frozen; the full dated record "
    "is Table~\\ref{tab:exposure} in Appendix~\\ref{app:exam}.",
    "This section reports, in the same spirit, how far that record held.")
replace_block(
    "\\begin{instructions}\nIn your words, state what the exposure was and was not:",
    "(sha256 \\texttt{5286bac3\\ldots}).\n\\end{instructions}\n",
    r"""The exam dataset, M4, was frozen before any judging (Appendix~\ref{app:exam}) and was exposed to detector output only, which was displayed during the October demonstrations. Apart from one annotation made before M4 was declared held out, no human verdict was given on any M4 detection and no M4 event entered the Library, so no model was trained or tuned on it and no detector parameter was chosen on it; Table~\ref{tab:exposure} gives the dated record. The sweep's 632 detector runs on M4, the CNN templates among them, made 1,186,189 detections, which were merged into 832,136 candidate events. The models under test, MiniRocket R4 and the four reference CNNs, had not been trained or tuned on M4. For judging, 40 candidates were drawn from each of the five agreement strata and 15 from each of six rarely firing detectors, a sample of 290. The 290 were judged blind in one queue, with M4's lock lifted for that queue only, and the verdicts were then used to score the exam once. The manifest fixing the sample, the models, the detectors and the metrics was protected by its hash, recorded before judging, so that no later work on M4 could change what was scored. Chapter~\ref{ch:rq3} reports the result.
""")

# 5.8 Ethics and risk: the risk that materialised.
replace_block(
    "\\begin{instructions}\nAdd the risk that did materialise: data loss.",
    "and the rule to unlink junctions first.\n\\end{instructions}\n",
    r"""One risk not in the plan did materialise: data loss. On 21 September, a routine clean-up command followed a directory link out of a working copy and emptied the project's real database and derived-data folders, 7.8\,GB in all. The database was recovered from a copy the tool had made for a sandbox session, and the derived channel files were regenerated from the raw recordings. Three safeguards followed: development runs use a sandbox copy of the database, the tool backs up the database each time it starts, and links into the data folder are removed before any working copy is deleted.
""")

io.open(CH5, "w", encoding="utf-8").write(text)

# Appendix I: a Chapter 5 group, between Chapter 4's and Chapter 6's.
app = io.open(APP, encoding="utf-8").read()
anchor = "\\section*{From Chapter~\\ref{ch:rq1}: detectors}"
if anchor not in app:
    raise SystemExit("appendix anchor missing")
if "tab:crosschannel" not in app:
    app = app.replace(anchor, "\\section*{From Chapter~\\ref{ch:method}: methodology}\n\n" + table.rstrip("\n")
                      + "\n\n\\clearpage\n\n" + anchor)
    io.open(APP, "w", encoding="utf-8").write(app)
print("Chapter 5 integrated")

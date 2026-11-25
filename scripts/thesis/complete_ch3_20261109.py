"""Complete Chapter 3 behind its notes (9 Nov): each empty section written compactly from its note's facts; notes
removed. Exact anchors; refuses if one is missing."""
from __future__ import annotations

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH3 = os.path.join(ROOT, "docs", "thesis", "chapters", "03_early_work.tex")
text = io.open(CH3, encoding="utf-8").read()


def note(start, new=""):
    """Replace the instructions block that begins with `start` by `new` (prose, or nothing)."""
    global text
    a = text.find("\\begin{instructions}\n" + start)
    if a < 0:
        raise SystemExit(f"note not found: {start[:50]!r}")
    b = text.find("\\end{instructions}\n", a) + len("\\end{instructions}\n")
    if not new and text[b:b + 1] == "\n":
        b += 1
    text = text[:a] + new + text[b:]


def replace_once(old, new):
    global text
    if text.count(old) != 1:
        raise SystemExit(f"expected one match for {old[:60]!r}, found {text.count(old)}")
    text = text.replace(old, new)


note("New chapter (5 Nov).")
replace_once(
    "The year's work began with a large set of unlabelled recordings and no agreed way of describing them. This chapter "
    "follows the experiments that came before \\tool{}, in the order they were made.\n",
    "The year's work began with about 1,000 hours of unlabelled oyster recordings, M2\\_aug and M2\\_concat "
    "(Figure~\\ref{fig:threezooms}), and no agreed way of describing them. This chapter follows the experiments that came "
    "before \\tool{}, in the order they were made, each answering a weakness of the one before. Hand labels gave the first "
    "data. CNNs showed that the labels could be learned, but not yet trusted. Matrix profiles looked for repeats without "
    "labels, but were slow and often found quiet stretches. The window matrix and its dendrograms tried to group windows "
    "without settling on an answer, SAX made shape searchable at any length, and the drop study was the first to follow "
    "one shape across species. The summer project had explored some of these ideas in MATLAB "
    "(Section~\\ref{sec:lituq}); everything in this chapter was implemented anew this year, in the thesis repository.\n")
note("Opening paragraph drafted 5 Nov as a placeholder;")

note("The facts:\n\\begin{itemize}\n  \\item a labelling tool", r"""A labelling tool stepped through the 16 channels of M2\_aug in 10-minute windows of 600 samples, advancing by a third of a window, so that neighbouring windows overlap by two-thirds. Each window was marked interesting, not interesting, or flagged as too straight or too regular to be signal (later imported as artefacts), and saving a label also saved the window's four image encodings. In all, 11,234 windows were labelled: 2,333 interesting, 8,773 not interesting and 128 flagged (Figure~\ref{fig:handlabels}). As far as is known this was the first labelled fungal dataset of its size, but it had clear costs. The labels describe windows rather than events, they come from one labeller who could see each window's context, and four windows in five are not interesting, so a model that always answers ``not interesting'' is already about 80\,\% accurate.
""")

replace_once(
    "Initial experiments in this project tested four encodings as CNN inputs, on about 11,000 hand-labelled 10-minute "
    "windows from the 16 channels of M2\\_aug. The windows were labelled by hand as `interesting' or `not interesting', "
    "meaning behaviour judged unlikely to be noise or chance. That labelling carries a bias the project set out to "
    "address. Chapter~\\ref{ch:rq3} reports what became of those models when they were later scored against blind labels.",
    "These labels trained the first models. Four CNNs, one per image encoding (GASF, GADF, recurrence plot and an RGB "
    "fusion of the three; Section~\\ref{sec:encodings}), each fine-tuned an ImageNet-pretrained EfficientNet-B0 on the "
    "10-minute windows, with early stopping, on an A100 GPU on UQ's rangpur cluster. On a random 80:20 split they scored "
    "91--92\\,\\% accuracy (Table~\\ref{tab:earlymodels}). That number is optimistic. Neighbouring windows overlap by "
    "two-thirds, so most validation windows had a near-twin in training, like a quiz whose answers sit next to the "
    "questions, and the majority-class baseline is already about 81\\,\\%. Scored months later against blind labels "
    "judged on the site, the same models reached a balanced accuracy of 0.78--0.83 and an AUC of 0.93--0.96 at "
    "10 minutes, and fell to chance at one minute (Figure~\\ref{fig:earlycnn}). The same labels trained a baseline of 24 "
    "catch22 and entropy features with a balanced random forest, while a nearest-neighbour classifier using dynamic time "
    "warping failed. The labels, not the architecture, were the limit, and training data and splits must be recorded "
    "(Chapter~\\ref{ch:rq3}).")
note("Spend time here: a CNN trained on ten thousand")
note("Check this table before keeping it.")

note("The facts (\\src{Results/Detection/matrix_profile/_legacy/}", r"""Matrix profiles looked for repeats without any labels. Whole-signal profiles of M2\_concat at 1\,Hz were computed on the cluster's GPUs at window lengths from 1 to 60 minutes (Figure~\ref{fig:mpintuition} shows one). On CH1 at 10 minutes the closest pair of windows lay only minutes apart, while on CH3 at 50 minutes the closest pair was 64 hours apart, and many of the closest repeats were slow recoveries and quiet stretches, so similarity alone did not mean interest. A ``seed chain'' then took one subsequence and followed its nearest neighbours through the recording, the first seeded search; a later version followed one hand-catalogued shape across channels (Figure~\ref{fig:mpseed}). Cost decided what came next. A whole profile takes about 40 hours for M2\_concat and an estimated 260 hours for M2\_aug, against seconds for one seed, so a human-chosen seed was the affordable route to recurring motifs, and became the seed search of Chapter~\ref{ch:rq2}.
""")

note("The facts:\n\\begin{itemize}\n  \\item the window matrix", r"""The window matrix (Section~\ref{sec:representation}) set every feature of every 10-minute window side by side, from CNN scores and random-forest output to entropy and catch22 features (Figure~\ref{fig:windowmatrix}). Clustering a subsample of M2\_concat's windows into dendrograms, with outliers removed and average and complete linkage compared over two to eight clusters, gave a medoid for each cluster but no settled number of clusters (Figure~\ref{fig:dendroplan}). Two lessons followed. A window matrix has one row per window and no alignment to time, so it cannot be thresholded into events, and a cut through a dendrogram is not a taxonomy. These became the time-aligned Scores type, the Discovery Map and the Library's groupings (Chapter~\ref{ch:pipeline}); cluster labels are tested against human labels in Chapter~\ref{ch:rq3}.
""")

note("The facts:\n\\begin{itemize}\n  \\item SAX \\cite{lin2007sax}", r"""Symbolic Aggregate Approximation (SAX) \cite{lin2007sax} reduces a window to a short string of letters (Section~\ref{sec:distance}). Python ports of published SAX variants were written in April, and a directional variant, dSAX, followed in August and was validated on twelve synthetic shapes (Figure~\ref{fig:sax}). The August experiments tried multiscale SAX, seeded search over SAX strings with exact, lower-bound and edit-distance matchers, and detection calibrated against surrogates. Detrending first raised recall on synthetic motifs from 0.22 to 0.85, and without a rolling normalisation 90\,\% of a real channel's symbols fell in one bin, because a few deep falls dominate its range of values. Symbols made shape searchable at any duration, but every script fixed its own thresholds and none carried a null. They became the Analyse page's symbolic route and the symbol-search template, run with surrogates like every other detector.
""")

note("The August--September drop-motif study,", r"""The drop-motif study of August and September, built before the web tool, followed one shape across species. A drop detector found falls followed by a slower recovery, gated by the steepness of the fall, and the study's store holds 4,023 events: 754 from oyster (M2\_aug), 2,425 from reishi (F2A, at 10\,Hz) and 844 from one lion's mane channel (MJu26a CH14, a lower bound). After each event is normalised by its own fall, drops spanning 3.6 orders of magnitude in duration and 4.2 in amplitude share one relative shape (Figure~\ref{fig:scalecollapse}); the species do not share one waveform, but a sharp fall and a slower recovery are common to them all. Normalisation is not invariance, though. The normalised shape still predicts how many samples an event was built from (balanced accuracy 0.75, against a chance of 0.25), and the species can be read back from it too, much as a photograph carries the trace of the camera that took it (Figure~\ref{fig:speciesres}; the full ledger is Appendix~\ref{app:claims}). For the plan's question of identity under scale, this is the reportable negative result: scale is not cleanly a property of the motif, because the representation carries the resolution and context it was recorded at.
""")
note("The findings to state, each with its ledger row")

note("From \\src{docs/rq_roundB/notes/drop-motif-sequences.md}:", r"""The study also looked at sequences, defined as at least five drops on one channel with no gap longer than twice the channel's typical gap, either regular (gap CV at most 0.5) or trending. It found 125 sequences among 1,686 events (oyster 19, reishi 98, lion's mane 8). Of fifteen drawn, four changed shape steadily along the sequence and eleven returned to near where they started (Figure~\ref{fig:sequence}), and trains of near-identical falls could repeat every few minutes for hours (Figure~\ref{fig:droptrio}). Three of these sequences became seeds for the timing studies of Chapter~\ref{ch:roundb}.
""")

note("Close the chapter with the table and one paragraph in your words:", r"""Every experiment worked a little and broke on the same things: results that could not be compared, labels that were not blind, nulls that were missing, and work that could not be repeated (Table~\ref{tab:lessons}). \tool{} is the answer to that list (Chapter~\ref{ch:pipeline}). The experiments had also begun to describe the signal itself, and the later chapters return to each point. About one 10-minute window in five held something judged interesting (2,333 of 11,106 decided windows). The closest repeats in a recording were often slow recoveries and quiet stretches, so similarity alone is not interest. A few deep falls dominate a channel's range of values, so a channel has to be normalised locally before its shapes can be compared. And one fall-and-recovery shape appeared in three species at very different time scales, though how it was recorded leaves a trace in its normalised shape.
""")

io.open(CH3, "w", encoding="utf-8").write(text)
print("Chapter 3 completed; notes left:", text.count("\\begin{instructions}"))

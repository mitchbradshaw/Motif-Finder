"""Complete Chapter 1 behind its notes (9 Nov): motivation paragraph, released-tools sentence, corpus sentence, fourth
gap and the contributions list; resolved notes removed. Exact-string edits; refuses if an anchor is missing."""
from __future__ import annotations

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH1 = os.path.join(ROOT, "docs", "thesis", "chapters", "01_introduction.tex")
text = io.open(CH1, encoding="utf-8").read()


def cut_note(start_marker):
    global text
    a = text.find("\\begin{instructions}\n" + start_marker)
    if a < 0:
        raise SystemExit(f"note not found: {start_marker[:50]!r}")
    b = text.find("\\end{instructions}\n", a) + len("\\end{instructions}\n")
    if text[b:b + 1] == "\n":
        b += 1
    text = text[:a] + text[b:]


def replace_once(old, new):
    global text
    if text.count(old) != 1:
        raise SystemExit(f"expected one match for {old[:60]!r}, found {text.count(old)}")
    text = text.replace(old, new)


cut_note("Restructured 5 Nov.")
cut_note("Review note (8 Nov): this paragraph is the hook")
cut_note("Retyped from the plan's image of this table.")
cut_note("Qualify the last sentence with what this project found.")
cut_note("\\textbf{Framing (5 Nov):}")
cut_note("Consider adding a fourth gap")
cut_note("Rewritten 5 Nov: the RQs are stated as they stand")
cut_note("New section, written by you. Suggested list:")

replace_once(
    "with unique but distinctive patterns of activity.\n",
    "with unique but distinctive patterns of activity.\n\n"
    "This thesis began with about 1,000 hours of raw recordings from two 16-electrode oyster cultures, M2\\_aug (721 hours) "
    "and M2\\_concat (282.5 hours), and no field standard for what to look for in them (Figure~\\ref{fig:threezooms}). "
    "Exploratory algorithms gave wildly different answers that could not be compared: one published detector marks almost "
    "two-thirds of a recording's time as events, while another finds a few hundred drops in the same 721 hours. Each new "
    "combination of ideas became a one-off script that was then lost, and fungal signals have no defined alphabet, let "
    "alone a language. Before anyone can ask what these signals mean, someone has to show which parts of them recur, how "
    "reliably those parts can be found, and what they look like.\n")

replace_once(
    "A further consequence of this is that none of the analysis tools described in these studies have been released as "
    "public software, and preprocessing procedures are rarely described in sufficient detail to reproduce results "
    "independently.",
    "A further consequence is that few of the analysis tools described in these studies have been released as public "
    "software. Adamatzky's four-species recordings are public \\cite{adamatzky2021data}, and Dehshibi and Adamatzky "
    "released the MATLAB code of their detector \\cite{dehshibi2020code}, but porting that code for this thesis showed "
    "that it differs from the printed paper in about ten places. Preprocessing and parameters can rarely be reproduced "
    "from the papers alone.")

replace_once(
    "The mushrooms were grown inside Faraday cages to limit outside interference.",
    "The mushrooms were grown inside Faraday cages to limit outside interference. During this thesis, recordings of "
    "other species and strains from the same laboratory joined them: lion's mane (MJu26a, LM), chocolate and snow oyster "
    "(CO, SO), Asian shiitake (SH) and reishi (F2A), listed in Table~\\ref{tab:corpus}.")

replace_once(
    "They are symbiotic with 90\\% of plants, particularly in the diverse climates of Australia.",
    "They form symbiotic partnerships with most land plants, particularly in the diverse climates of Australia.")

replace_once(
    "a result that cannot be rerun on a new recording cannot be built on.\n",
    "a result that cannot be rerun on a new recording cannot be built on.\n\n"
    "A fourth gap follows from this project's own evidence. Published detectors cannot be compared directly, because on "
    "the same recording they disagree by orders of magnitude, and no study reports a detector's precision against blind "
    "human judgement or against a surrogate. Chapter~\\ref{ch:rq1} measures exactly this.\n")

replace_once(
    "\\section{Contributions}\n\\label{sec:contributions}\n\n",
    "\\section{Contributions}\n\\label{sec:contributions}\n\n"
    "\\begin{enumerate}\n"
    "  \\item \\tool{}, a composable, human-in-the-loop application for long unlabelled bio-electric recordings, with typed "
    "analysis blocks, re-runnable recipes, surrogate nulls, blind review and a held-out lock (Chapter~\\ref{ch:pipeline}).\n"
    "  \\item The first comparison of fungal event detectors against blind, stratified human judgement at scale, with an "
    "agreement ladder that holds on every recording, including a held-out one (Chapter~\\ref{ch:rq1}).\n"
    "  \\item Seeded search that retrieves human-accepted events far above chance, and a drop shape that transfers "
    "unchanged to seven other recordings of three species (Chapter~\\ref{ch:rq2}).\n"
    "  \\item A classifier trained only on the tool's verdicts that transfers to unseen recordings (AUC 0.97) and to the "
    "held-out recording (AUC 0.98, scored once) (Chapter~\\ref{ch:rq3}).\n"
    "  \\item A catalogue of 2,959 human-accepted spans across eight recordings, and the finding that drops dominate and "
    "that a normalised shape still encodes resolution and species (Chapters~\\ref{ch:early} and~\\ref{ch:events}).\n"
    "  \\item Evidence on what the signals do: no propagation between electrodes, structure at every time scale from 30\\,s "
    "to minutes, and event timing close to random with a rate that drifts over days (Chapter~\\ref{ch:roundb}).\n"
    "\\end{enumerate}\n\n")

io.open(CH1, "w", encoding="utf-8").write(text)
print("Chapter 1 completed; notes left:", text.count("\\begin{instructions}"))

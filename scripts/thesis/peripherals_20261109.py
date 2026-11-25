"""Draft the abstract and correct the AI statement's text sentence (9 Nov), for the author to edit and sign."""
from __future__ import annotations

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ABS = os.path.join(ROOT, "docs", "thesis", "frontmatter", "abstract.tex")
AI = os.path.join(ROOT, "docs", "thesis", "frontmatter", "ai_statement.tex")

abstract = r"""\chapter{Abstract}

Fungal mycelium produces slow electrical signals, but recordings of them are long, unlabelled and hard to compare. There is no agreed set of events to look for, and the published detectors, built for single studies or borrowed from other fields, disagree by orders of magnitude on the same signal. This thesis presents \tool{}, a composable, human-in-the-loop application in which every analysis is a re-runnable recipe, every result is compared with a surrogate copy of the signal that keeps its frequency content, and every human judgement is made blind. It applies the tool to nine recordings of four species from one laboratory.

Three answers follow. Agreement between independent detector families predicts what a human reviewer accepts: 0--5\,\% of candidates are real where one or two families agree, and 40--63\,\% where nine or more do, on every recording, including one held out until the end (0 to 53\,\%). A drop chosen in one oyster recording, used unchanged as a search seed, finds matches in seven other recordings of three species, and 455 of 457 were accepted blind, against 79 of 459 random windows. A classifier trained only on the tool's verdicts ranks the events of recordings it never saw almost as a person would (AUC 0.97 across recordings, and 0.98 on the held-out recording, scored once).

The reviews built a catalogue of 2,959 accepted spans across eight recordings. Most accepted events are falls in potential followed by a slower recovery, and the same shape recurs across species, although a normalised shape still carries a trace of how it was recorded. Event timing is close to random from one event to the next, while activity drifts over hours to days; structure appears at every time scale from 30 seconds to minutes; and nothing was seen travelling between electrodes. Fungal recordings contain stereotyped, recurring waveforms that are shared across species and can be found, checked and counted reproducibly.
"""
io.open(ABS, "w", encoding="utf-8").write(abstract)

t = io.open(AI, encoding="utf-8").read()
old = ("This document was scaffolded with AI assistance from my notes, the repository record and my prior assessed work: the "
       "chapter structure, the content notes and the collation of numbers and figures. The prose is my own, and AI was "
       "also used for \\LaTeX{} syntax, grammar and phrasing.")
new = ("This document was scaffolded with AI assistance from my notes, the repository record and my prior assessed work: the "
       "chapter structure, the content notes and the collation of numbers and figures. Much of the prose was drafted by "
       "Claude from my notes, my written responses for each section and the analysis results, and I then reviewed, "
       "corrected and edited it; some passages are my own writing throughout. AI was also used for \\LaTeX{} syntax, "
       "grammar and phrasing. I take responsibility for every sentence and every number in this thesis.")
if t.count(old) != 1:
    raise SystemExit("AI statement sentence not found")
io.open(AI, "w", encoding="utf-8").write(t.replace(old, new))
print("abstract drafted; AI statement sentence corrected")

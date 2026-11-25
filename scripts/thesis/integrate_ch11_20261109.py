"""Integrate the author's Chapter 11 edits (9 Nov), and the electrode-placement point in Chapter 10's B4 section."""
from __future__ import annotations

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CH11 = os.path.join(ROOT, "docs", "thesis", "chapters", "11_discussion.tex")
CH10 = os.path.join(ROOT, "docs", "thesis", "chapters", "10_roundb.tex")


def apply(path, pairs):
    t = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        if t.count(old) != 1:
            raise SystemExit(f"{os.path.basename(path)}: {t.count(old)} matches for {old[:60]!r}")
        t = t.replace(old, new)
    io.open(path, "w", encoding="utf-8").write(t)
    print(os.path.basename(path), "ok", len(pairs))


apply(CH11, [
    ("This thesis asked whether recurring structure in fungal bio-electric recordings can be detected automatically and "
     "trusted, and what that structure is (Section~\\ref{sec:rqs}). Both halves have an answer. Recurring structures can be "
     "found at scale, and with a blind reviewer and a surrogate null they can be trusted to a stated degree "
     "(Chapters~\\ref{ch:rq1}--\\ref{ch:rq3}). Characterising them shows a dominant fall-and-recovery event that recurs "
     "across species, irregular timing with slowly drifting activity, and no evidence of activity travelling between "
     "electrodes (Chapters~\\ref{ch:events} and~\\ref{ch:roundb}).",
     "The goal of this thesis was to examine what recurring structures are in fungal bio-electric recordings "
     "(Section~\\ref{sec:rqs}), and whether they could be automatically detected and trusted, in that they pass human "
     "judgement. Both halves have an answer. Recurring structures can be found at scale, and against a blind reviewer and "
     "surrogate nulls they can be trusted to a stated degree (Chapters~\\ref{ch:rq1}--\\ref{ch:rq3}). Characterising "
     "them reveals a dominant fall-and-recovery behaviour that recurs across species, with irregular timing and slowly "
     "drifting activity, and with no evidence of activity travelling between electrodes "
     "(Chapters~\\ref{ch:events} and~\\ref{ch:roundb}). The electrodes were placed fairly irregularly, on different "
     "fruiting bodies, so the chance of detecting propagation was low from the start."),
    ("and on all eight recordings the matches occur one electrode at a time.",
     "and on all eight recordings a match on one electrode almost never coincides with a match on another (817 of 836 "
     "have none within 50 seconds), so the drops are not disturbances of the whole recording."),
    ("Shapes recur across recordings and species, each recording leaning its own way more than each species does (B6, B12).",
     "Shapes recur across recordings and species, but each recording has its own mix of the shared shape families, and "
     "these differences between recordings are at least as large as the differences between species (B6, B12)."),
    ("One drop recurs hundreds of times in a 30-day oyster recording, while copies with the same frequency content almost "
     "never contain it (Table~\\ref{tab:seeds}).",
     "One drop recurs hundreds of times in a 30-day oyster recording, while surrogate copies with the same frequency "
     "content almost never contain it (Table~\\ref{tab:seeds}). This suggests the existence of waveforms unique to the "
     "composition of the fungal signals, which randomised surrogates cannot reproduce, further suggesting the possibility "
     "of significant biological events."),
    ("Comparing species fairly will need several recordings of each.",
     "In order to further compare species fairly, future work would require several recordings of each."),
    ("claims of characteristic durations should be tested against a null that keeps the signal's values.",
     "claims of characteristic durations should be tested against a null that keeps the signal's values. An AAFT copy "
     "holds exactly the same amplitudes as the recording, with the same distribution of large and small fluctuations "
     "and nearly the same frequency content, but in a scrambled order. If a method finds the same durations in that "
     "copy, those durations come from the sizes and frequencies of the fluctuations, not from events with a "
     "characteristic length."),
])

apply(CH10, [
    ("Nothing was seen travelling between electrodes at these spacings and sampling rates.",
     "Nothing was seen travelling between electrodes at these spacings and sampling rates, although the electrodes were "
     "placed fairly irregularly, on different fruiting bodies, so propagation was never likely to be detected here."),
])

"""Give every figure and table a short list entry: \\caption[short]{long} (9 Nov), so the lists of figures and tables
fit on about two pages each while the floats keep their full captions.

The short entry is the caption's first sentence, cleaned (no \\cite, \\label or footnote); a sentence longer than
LIMIT characters is cut at its first colon, semicolon or parenthesis, or else at a word boundary. OVERRIDES (by
label) replace any entry that reads badly. Captions that already carry a short entry are left alone.

    python scripts/thesis/short_captions_20261109.py          # dry run: prints label, length and entry
    python scripts/thesis/short_captions_20261109.py --apply  # writes the .tex files
"""
from __future__ import annotations

import glob
import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
THESIS = os.path.join(ROOT, "docs", "thesis")
LIMIT = 95
ABBREV = ("e.g.", "i.e.", "et al.", "Fig.", "vs.", "cf.", "approx.", "Eq.", "No.", "Dr.")
OVERRIDES: dict[str, str] = {
    "fig:b1train": "B1 in the signal: drop onsets on four hours of M2\\_concat CH3.",
    "fig:b3restitution": "Restitution: does a drop recover more slowly after a long gap?",
    "fig:dropdistribution": "Where and when the 372 drop-seed matches occur in M2\\_aug.",
    "fig:sequence": "A drop sequence from the drop-motif study (M2\\_aug CH6\\_B1, 387--408\\,h).",
    "fig:b9hist": "B9: how long the wavelet-ridge detector's events last.",
    "tab:seedchannels": "Matches per channel for each seed in M2\\_aug.",
    "tab:detnull": "Real against surrogate detections, by detector family and recording.",
    "fig:reviewscreen": "A Review queue in \\tool{}.",
    "tab:queues": "The reviews that supply the human judgements in this thesis.",
    "tab:seeds": "Seed matches at a common distance threshold.",
    "fig:seeds": "Two Library seeds and what they found in M2\\_aug.",
    "fig:b6species": "B6 in the signal: two g-11 families shared by three cultures.",
    "tab:rbsummary": "The signal studies: each question's null, result and verdict.",
    "tab:rqmap": "Where each research question of the thesis plan is answered.",
    "tab:rq4partialreturns": "The completed 2\\,Hz sweep: detections on the recordings and their copies.",
    "tab:forestblind": "Manual forest A and seven-cluster forest B2 on blind ten-minute windows.",
    "tab:cnnvsr4": "Reference CNNs against MiniRocket R4 on the same judged events.",
    "tab:faircnn": "A CNN trained on R4's data and folds, against R4.",
    "tab:cnns": "Reference CNNs against the blind window labels.",
    "tab:scope": "Planned scope exclusions against the software as built.",
    "fig:dendroplan": "An early dendrogram of 10-minute windows (May 2026).",
    "fig:speciesres": "What a normalised drop still remembers.",
    "fig:b4bins": "The B4 census: drop-detector events on several channels at once.",
    "fig:b12waves": "B12 in the signal: accepted events stretched to a common length.",
    "tab:sharereal": "Estimated share of candidate events that are real.",
    "tab:vocab": "Element tags, with instance counts.",
    "fig:mpintuition": "What a matrix profile shows (M2\\_concat CH1, 10-minute windows).",
    "fig:seedtransferacceptance": "Human acceptance of the drop query on seven other recordings.",
    "tab:surr20": "Six precise settings on M2\\_aug against 20 phase-randomised draws.",
    "fig:encodings": "One 10-minute window and its four image encodings.",
    "tab:lessons": "What each early experiment produced, where it broke, and what it became.",
    "fig:b10motif": "B10 on the site: \\texttt{motif\\_lengths} on eight hours of M2\\_aug.",
}


def balanced(text, i):
    """Index just past the brace group opening at text[i] == '{'."""
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "\\":
            continue
        if c == "{" and (j == 0 or text[j - 1] != "\\"):
            depth += 1
        elif c == "}" and (j == 0 or text[j - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return j + 1
    raise ValueError("unbalanced caption")


def first_sentence(cap):
    depth, math = 0, False
    for k, c in enumerate(cap):
        if c == "{" and (k == 0 or cap[k - 1] != "\\"):
            depth += 1
        elif c == "}" and (k == 0 or cap[k - 1] != "\\"):
            depth -= 1
        elif c == "$" and (k == 0 or cap[k - 1] != "\\"):
            math = not math
        elif c == "." and depth == 0 and not math and (k + 1 == len(cap) or cap[k + 1] in " \n"):
            if any(cap[:k + 1].endswith(a) for a in ABBREV):
                continue
            return cap[:k + 1]
    return cap


def visible_len(s):
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", s)
    return len(re.sub(r"[{}$\\~]", "", s))


def shorten(cap):
    s = first_sentence(cap.strip())
    s = re.sub(r"\\cite\{[^}]*\}", "", s)
    s = re.sub(r"\\footnote\{.*\}", "", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if visible_len(s) > LIMIT:
        for sep in (": ", "; ", " (", ", "):
            cut = s.find(sep)
            while cut > 0:
                if 25 <= visible_len(s[:cut]) <= LIMIT and s[:cut].count("{") == s[:cut].count("}") \
                        and s[:cut].count("$") % 2 == 0:
                    s = s[:cut].rstrip(" ,;:") + "."
                    break
                cut = s.find(sep, cut + 1)
            if visible_len(s) <= LIMIT:
                break
    return s.rstrip()


def captions(path):
    text = io.open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"\\caption(?=\{)", text):
        start = m.end()
        stop = balanced(text, start)
        cap = text[start + 1:stop - 1]
        lab = re.search(r"\\label\{([^}]*)\}", text[stop:stop + 200])
        out.append((m.start(), start, stop, cap, lab.group(1) if lab else "?"))
    return text, out


def main(apply):
    files = sorted(glob.glob(os.path.join(THESIS, "chapters", "*.tex"))
                   + glob.glob(os.path.join(THESIS, "appendices", "*.tex")))
    n = 0
    for path in files:
        text, caps = captions(path)
        if not caps:
            continue
        pieces, last = [], 0
        for begin, start, stop, cap, lab in caps:
            short = OVERRIDES.get(lab) or shorten(cap)
            n += 1
            print(f"{visible_len(short):4d} {lab:28s} {short}")
            pieces.append(text[last:start])
            pieces.append("[{" + short + "}]")
            last = start
        pieces.append(text[last:])
        if apply:
            io.open(path, "w", encoding="utf-8").write("".join(pieces))
    print(n, "captions", "written" if apply else "(dry run)")


if __name__ == "__main__":
    main("--apply" in sys.argv)

"""
detection_symbol_search.py
============================
Encoding (symbolic) → SpanSet: a regular expression over the symbol string
(stage-3 D2, the researcher's answer: symbol search over SAX strings,
generalisable to any string encoding).

The symbols are spelled with the same letters the UI shows: `a b c …` in
symbol order (dSAX at alphabet 3: a = down, b = same, c = up), or a custom
`alphabet` — `dDSUu` for `detection.stage_encoding`'s five stages, in which
case the pattern is written in those letters (`[Uu]+[Dd]*d` = a rise then a
fast fall). Each regex match becomes one span covering the matched
segments; its label is the matched text, its score the match length in
segments. The segment length is `len(x) // n_symbols`, the same rule every
symbolic consumer uses.
"""

import re

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import SpanSet

_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def letter(i, alphabet=""):
    i = int(i)
    if alphabet:
        if i >= len(alphabet):
            raise ValueError(f"symbol {i} is outside the {len(alphabet)}-letter alphabet {alphabet!r}")
        return alphabet[i]
    if i < 26:
        return _LETTERS[i]
    return _LETTERS[i // 26 - 1] + _LETTERS[i % 26]


def _run(x, t, fs, pattern="c+a+", alphabet="", overlapping=False, value=None):
    if value is None:
        raise ValueError("detection.symbol_search requires a symbolic Encoding input from a prior step (input_kind='encoding').")
    if getattr(value, "kind", None) != "symbolic":
        raise ValueError(f"detection.symbol_search reads a symbolic Encoding; got kind {value.kind!r}.")
    syms = np.asarray(value.values).ravel()
    n_symbols = len(syms)
    if n_symbols == 0:
        return AdapterResult(output_kind="spanset", value=SpanSet(starts=(), ends=()), meta={"string": "", "n_matches": 0})
    if not alphabet and syms.max() >= 26 * 27:
        raise ValueError("symbol values too large for the default a-z alphabet; pass `alphabet`.")
    string = "".join(letter(s, alphabet) for s in syms)
    try:
        rx = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"symbol_search: {pattern!r} is not a valid regular expression ({e}).") from e
    sps = max(1, len(x) // n_symbols)
    starts, ends, labels, scores = [], [], [], []
    pos = 0
    while pos <= n_symbols:
        m = rx.search(string, pos)
        if m is None or m.end() == m.start():
            break
        starts.append(m.start() * sps); ends.append(min(len(x), m.end() * sps))
        labels.append(m.group(0)); scores.append(float(m.end() - m.start()))
        pos = m.start() + 1 if overlapping else m.end()
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=tuple(starts), ends=tuple(ends), labels=tuple(labels), scores=tuple(scores)),
        meta={"string": string if n_symbols <= 20000 else string[:20000], "n_symbols": n_symbols,
              "samples_per_symbol": sps, "n_matches": len(starts), "pattern": pattern},
    )


def _derive(x, t, fs, params, value=None):
    try:
        re.compile(params["pattern"])
        rows = [("Pattern", params["pattern"], "")]
    except re.error as e:
        rows = [("Pattern", f"invalid: {e}", "error")]
    if value is None:
        rows.append(("Matches", "run the encoding first", "warn"))
    return rows


SPEC = register(AdapterSpec(
    name="detection.symbol_search",
    display_name="Symbol search (regex over an encoding -> SpanSet)",
    stage="detection",
    category="detect",
    page_name="Symbol search",
    params=[
        ParamSpec("pattern", str, "c+a+", "Regular expression over the symbol letters (dSAX k=3: a down · b same · c up)"),
        ParamSpec("alphabet", str, "", "Letters to spell the symbols with, in symbol order (empty = a, b, c …; dDSUu for the five-stage encoding)"),
        ParamSpec("overlapping", bool, False, "Allow matches to overlap (search resumes one symbol after each match start)"),
    ],
    run=_run,
    derive=_derive,
    input_kind="encoding",
    output_kind="spanset",
    description=(
        "Regular-expression search over the symbol string of any symbolic encoding; "
        "each match is a span over the matched segments."
    ),
))

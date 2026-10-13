# Fixup AM — "peak aligned" as a third window alignment, beside grid and centre

**Written 2026-10-13 from the researcher's list ("peak aligned as another window alignment option in adjusting
window sets"). Not run yet. Opens with a question the researcher must answer first.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `Working/training/shape.py` (`ALIGNS`, `DEFAULT_ALIGN`, `SWING_RULE`, `ALIGN_RULE`, `swing_index`,
`recut_start`, `allowed_interval`, `trace_shapes`, `tree_key`), `Adapters/preprocessing_trace_shape.py` (the `align`
`ParamSpec`), `Adapters/catalogue_shape_cluster.py` (reads `shapes.meta["align"]`), `tests/test_training_shape*.py`,
and `docs/prompts/fixup/reports/AG-*.md` (why `centre` became the default on 2026-10-05).

Commit prefix `fixup-am:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only.**

## In plain words, and the question to put to the researcher before building

A window set cuts a recording into pieces of fixed length. *grid* keeps the pieces where the cutter put them;
*centre* slides each piece so that its biggest swing sits in the middle. Centring already finds the sample that stands
furthest from the window's typical level after the trend is removed — so "the peak" in the sense of "the biggest
excursion" is what `centre` does today.

"Peak aligned" can therefore mean two different things, and they give different piles:

- **(a) Signed, not absolute.** `peak` = the window's *maximum* (the top of a spike) and `trough` = its *minimum*
  (the bottom of a drop) sit in the middle. Today a window that holds a small spike before a big drop is centred on
  the drop whichever you care about.
- **(b) Where the extremum sits.** The extremum is placed not at the centre but at a chosen fraction of the window
  (a third in), so the recovery after a drop fits inside the window instead of being cut off. Many of the piles AG
  measured are "event then long tail", and a centred cut halves the tail.

**Recommendation:** build both as one `align` choice plus one number: `align ∈ {grid, centre, peak, trough}` and
`anchor_frac` (default 0.5; AG's centring unchanged at 0.5). Ask the researcher to confirm, and which default.

## Work (once answered)

1. `shape.py`: a third/fourth entry in `ALIGNS`, an index rule per choice (signed argmax / argmin of the detrended
   window, running-median guarded exactly as `swing_index` is), `anchor_frac` threaded through `recut_start` and
   `allowed_interval`; the `align == "centre"` checks (six of them) become `align != "grid"`. `ALIGN_RULE` gets the
   words for each so the page prints them. `tree_key` must change when alignment or anchor changes — a cached tree
   built on centred windows must not answer for peak-aligned ones.
2. `preprocessing_trace_shape.py`: the `ParamSpec` choices and a new `anchor_frac` param with the rule text.
3. The Shape clustering page shows the alignment and anchor on the tree card (it reads `shapes.meta["align"]`).

## Acceptance

- [ ] A synthetic window with a small spike then a large drop: `peak` centres the spike, `trough` the drop, `centre`
      the drop (unchanged), `grid` moves nothing.
- [ ] `anchor_frac = 1/3` puts the extremum one third in; windows that cannot be placed are shifted as far as allowed
      and counted, as `centre` already does.
- [ ] Two windows that align onto one event keep one (as today), under every rule.
- [ ] The tree key differs between `centre` and `peak` on the same pool.
- [ ] `pytest` passes; the trace-shape block's page shows the chosen rule in words.

## Report

`docs/prompts/fixup/reports/AM-peak-aligned-windows.md`, including the researcher's answer verbatim.

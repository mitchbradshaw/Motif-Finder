# Critic report — W1-G: LV and CV2 in `interrogation.intervals`

Filed by the manager from the critic's returned report, 2026-10-13. Verdict: **merge after fixes** (no blocker).

## In plain words

The block now also gives two neighbour-to-neighbour regularity scores, LV and CV2, so a slow speed-up over the day no
longer looks like randomness. The formulas match the papers and the tests prove the headline claim (tenfold rate rise:
CV 1.33, LV 1.00, CV2 1.00; a slow deterministic speed-up: CV 0.65, LV ≈ 0.0006). The soft spot: a choice made for
coincident onsets is not visible in the output or the rule text.

## Findings

- **should-fix** — `Working/interrogation/intervals.py` `_local_ratios` / `RULES["lv"]`: pairs of two 0-s gaps are
  dropped, so the denominator is the kept-pair count, but the rule still reads `3/(n-1)` and the dropped count is not
  reported (`local_variation([30, 0, 0, 30])` = 3.0 from 2 of 3 pairs vs 2.0 literally). Fix: name it in the module
  docstring and rule strings; add `n_local_pairs`; say the dropped count in `local_note`.
- **nit** — one duplicate onset makes a regular train read as random (`[30,30,0,30,30,30]` → LV 1.20, CV2 0.80); a
  docstring sentence.
- **nit** — few-gap noise (Poisson LV sd 0.89 / 0.59 / 0.37 at 2 / 4 / 9 gaps); show `n_intervals` beside LV/CV2 in
  the UI or grey values under ~10 gaps.
- **nit** — 1 Hz quantisation (CV2 0.20 at a 2.5 s period, 0.016 at 30.5 s, 0.002 at 300 s); a docstring caveat.
- **integration** — the client table (`EventFeatures.tsx:75`) and `api.ts:186` `IntervalStats` are fixed lists;
  `n_groups_local_unmeasured` is not in `_SPANSET_META_VIEWS`, so it does not reach the page (the per-group
  `local_note` does).

## Checked with nothing to report

Every acceptance item met and pinned by a test that would fail on a plausible wrong implementation; LV = Shinomoto 2009
eq. 2, CV2 = Holt 1996, LvR correctly omitted; empty / single / NaN / all-coincident inputs give None with a note,
JSON-safe; 200k events in 0.55 s; no UI imports; first commit 9540e8c tests-only, red reproduced (8 failed, 1 passed);
3 files touched, all in scope. 254 passed across the intervals, block-standard, adapter-spec, import-boundary,
templates and serializer tests.

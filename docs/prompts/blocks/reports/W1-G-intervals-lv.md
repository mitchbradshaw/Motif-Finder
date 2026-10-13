# Report — W1-G: LV and CV2 in `interrogation.intervals` (implementer)

Filed by the manager from the implementer's returned report, 2026-10-13. Branch `worktree-agent-a8c1832f9d0c4611f`
(base 3cc2f62), commits `9540e8c` (tests, red: 8 failed / 1 passed) and `72de888` (implementation).

## In plain words

The Intervals block already measured how regular a run of events is with CV, which looks at all the gaps at once — so
if spikes slowly speed up over the day, CV calls the run irregular even when each spike is evenly spaced relative to
its neighbours (like calling a car's driving erratic because it sped up gradually on a highway). LV and CV2 compare
each gap only with the next one, so a slow speed-up does not fool them; both read about 0 for clockwork and about 1 for
random (Poisson) timing.

On synthetic data: a regular train gives LV = CV2 = 0; a seeded Poisson train (5,000 gaps) gives CV 1.015, LV 1.006,
CV2 1.007; a Poisson train whose rate rises tenfold (10,947 gaps) gives **CV 1.33 but LV 0.997 and CV2 0.999** — the case
the measures exist for; a 2-event group gets no LV/CV2 and says why (never 0).

## Files

- `Working/interrogation/intervals.py`: `local_variation`, `local_cv2`, `MIN_LOCAL_INTERVALS = 2`, helpers
  `_local_ratios` / `_local_note`; `interval_statistics` adds `lv`, `cv2`, `local_note` per group; `RULES` adds both.
- `Adapters/interrogation_intervals.py`: meta `n_groups_local_unmeasured`; docstring and description.
- `tests/test_intervals_lv.py`: 9 tests.

## Algorithm as implemented

Gaps per group (never pooled); non-finite gaps dropped; < 2 gaps → None with a note. ratio = |Iᵢ − Iᵢ₊₁|/(Iᵢ + Iᵢ₊₁);
LV = 3·mean(ratio²) (Shinomoto 2009 eq. 2); CV2 = mean(2·ratio) (Holt et al. 1996). A pair of two zero gaps (0/0) is
left out of the mean (the implementer's choice; the papers have no such case). LvR not added (refractory constant
fitted to cortex). Unit-free, O(n), existing keys unchanged.

## Integration needed (manager)

`webui/client/src/api.ts` (`IntervalStats`) and `webui/client/src/analyse/EventFeatures.tsx:75`
(`IntervalStatsTable` column list) are fixed lists: add `lv`, `cv2`, `local_note` or the numbers reach the browser
but are not shown. `serialize.py` passes `interval_stats` through whole.

## Open questions

With 2–5 gaps LV and CV2 are very noisy (Shinomoto used ≥ 2000 ISIs); only the mathematical minimum (3 events) is
enforced — a "low n" flag may be wanted.

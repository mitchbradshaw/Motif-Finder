# W1-G — LV and CV2 in `interrogation.intervals` (Shinomoto et al. 2003; Holt et al. 1996)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w1-g:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§4 A3 "Salvaged"; facts: `docs/research/analysis-blocks-primary-sources.md` §9.

## In plain words

The Intervals block already says how regular a run of events is with the coefficient of variation (CV). CV has a blind
spot: if events simply speed up slowly over a day, CV reports "irregular" even when every event is perfectly regular
relative to its neighbours. Two standard measures compare each gap only with the next one, so a slow change of rate
does not fool them: **LV** (local variation) and the local **CV2**. Both are about 0 for clockwork and about 1 for
random (Poisson) timing.

## The change

Add to each group's statistics (wherever `Working/interrogation/intervals.py::interval_statistics` builds them, so the
block and every other caller get them):

- **LV** = 3/(n−1) Σᵢ₌₁ⁿ⁻¹ ((Iᵢ − Iᵢ₊₁)/(Iᵢ + Iᵢ₊₁))², n = number of gaps (Shinomoto, Shima & Tanji 2003; formula
  as verified in Shinomoto et al. 2009, eq. 2).
- **CV2** = mean over i of 2|Iᵢ₊₁ − Iᵢ|/(Iᵢ₊₁ + Iᵢ) (Holt, Softky, Koch & Douglas 1996, *J. Neurophysiol.* 75:1806).
- Both need at least 2 gaps (3 events); fewer → null, counted and said, never 0.
- Their rules go into `meta["rules"]` beside CV's, in the same plain style. LvR is **not** added (its refractory
  constant was fitted to cortex).

Keep everything else byte-identical in behaviour (existing columns, CV with ddof=1, R² trend, drift ratio); the
existing tests must pass unchanged. If the Interrogation page or the bridge reads a fixed list of statistic names,
say so in your report (do not edit `webui/`).

## Deliver

- Changes in `Working/interrogation/intervals.py` (and the adapter only if needed); tests in
  `tests/test_adapter_intervals.py` and/or a new `tests/test_intervals_lv.py`.

## Acceptance

- [ ] A perfectly regular train: LV = 0 and CV2 = 0.
- [ ] Exponential (Poisson) gaps, many events, seeded: LV and CV2 within 0.1 of 1.
- [ ] A Poisson train whose rate rises tenfold over the span: CV clearly > 1 while LV and CV2 stay near 1 (the reason
      the measures exist — pin it).
- [ ] Two groups are never pooled; a group of 2 events gets null LV and CV2 with the reason counted.
- [ ] Every existing intervals test passes unchanged; the block passes `tests/test_block_standard.py`.

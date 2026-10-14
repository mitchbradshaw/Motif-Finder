> Filed by the manager session, 2026-10-15 — the final message of critic agent `ad8d8aad71e6d533b`, resumed to
> re-critique W3-C's fix round 1 (`617edc2`, changed parts only), verbatim.

W3-C fix round 1 re-critique (617edc2): merge after two small fixes. The stall rule does nothing through the template, and the summary line still says "suggested". Everything else holds.

## In plain words
- **The noise test is now fair.** The lopsided-noise trap is gone (0/10), and false suggestions on plain noise are about 1 %.
- **The stuck-logger guard never sees a stall in the template.** It only fires on a held value that reaches the block unchanged. The template removes the baseline first, which turns a held value into a gentle curve, so a raw 3–20 min stall still produces a confident suggestion.
- **The "suggested" length still carries no meaning on its own.** On the planted 90 s + 20 min set it lands near either motif in only 2 of 10 new seeds. The band of cleared lengths covers every judged rung in every planted case.

## Verdict: merge after fixes

## Findings, most severe first

**1. Should-fix: the stall rule is bypassed on the template path.**
- Where: `pan.py` `prepare_gaps`. It tests exact equality on the block's input, which in the template is the 2 h rolling-mean residual.
- What I ran: a raw flatline, then the template's detrend, then the block at its defaults (4 h, `stall.py`).

| Raw flatline | Background | `n_stalled` | Result |
|---|---|---|---|
| 3 min | random walk | 0 | suggests 30 s, clears 30–46 s |
| 20 min | random walk | 0 | suggests 30 s, clears 30–409 s (7 lengths) |
| 20 min | AR 0.97 | 0 | suggests 46 s, clears 7 lengths |
| 3 min | AR 0.97 | 0 | quiet |

- The new test passes only because it plants the flatline after the detrend, directly into the block's input.
- Fix (either):
  - mask stalls before the detrend, with a stall option on `preprocessing.detrend` (it is NaN-aware, so the gap carries through) or a small masking step first in the template;
  - or detect stalls in the block on the second difference of its input, which a detrended held value makes near zero.

**2. Should-fix, small: a stall should not share `max_fill_s` (5 s); it can blank real data fed in directly.**
- Q3: a quantised 1 Hz logger (slow AR 0.995, SD 10.6) fed straight to the block:

| ADC step | Longest run of one value | Blanked as "stalled" |
|---|---|---|
| 0.5 | 7 samples | 0.1 % |
| 1.0 | 13 samples | 3.1 % |
| 2.0 (about 1/5 SD) | 21 samples | **24.7 %** |

- The blanked stretches are real slow signal.
- Through the template's detrend, the same quantised logger blanks only 0–0.1 %.
- At 10 Hz (an interpolated 1 Hz AR, quantised) the longest run was 3.4 s, so nothing was blanked. 10 Hz is safe unless the signal is near-flat for more than 5 s.
- Fix: give stalls their own threshold in seconds, `stall_s`, default 60 s, labelled a placeholder. A logger stuck for a minute is a fault; 5–20 identical samples on a coarse ADC are not.

**3. Should-fix: the summary still says "suggested", and the suggestion is not informative (Q4).**
- The summary line reads "clears from A to B s, strongest at C · suggested C s". A page user sees only that. The caveat is in `rules` and the description, not on that line.
- My planted set, seeds 5000–5009, defaults: suggestions 409, 46, 409, 30, 264, 264, 264, 631, 409, 409 s.
  - Within one rung of 90 s (46–171 s): 1/10. Within one rung of 20 min (the 976 s rung or its 631 s neighbour): 1/10.
  - The implementer reported 5/6 on its own seeds.
- The cleared band is 30–976 s, every judged rung, in 8/10 runs (46–976 s in the other two). So the band does not narrow anything either. Only the picture localises.
- Fix:
  - drop "suggested" from the summary;
  - rename the visible field "strongest gap at C s (not an event length)";
  - W3-F should never offer "use this window" from it.
- What to feed FLUSS on a chain: nothing from this block at 8 h. A chain's ~30 min unit is out of judged reach there, and the block returns either nothing or the fall edge. Two options:
  - re-run FLUSS on ≥ 24 h spans at the band's top (longest cleared length) and at 300 s, declared before the run. The band's top is the only part that tracked a chain unit in round 0: 1508 s on random-walk drops at SNR 5;
  - or keep FLUSS at 300 s and record "pan gave no event-scale window".
- Do not use `suggested_window_s`.

**4. Answered: the rising cut costs no power at the longest judged rung here (Q2).**
- The 20 min motif's 976 s rung (14.75 windows on 4 h, cut 8.31) clears in 10/10 planted runs, with gaps 9.4–17.0.
- The margin is thin: three runs were at 9.39, 9.48 and 9.6, within about 1.3 of the cut. A weaker or noisier 20 min motif would be lost there before it would be lost at a flat cut of 6.
- The 90 s motif clears at 111 s in 10/10 (at 72 s in 8/10).

**5. Answered: false suggestions at the defaults (Q1).**

| Span (1 Hz, new seeds 5000+, block's own `pan_matrix_profile`, after the 2 h detrend) | Spans | False suggestions |
|---|---|---|
| 2 h | 120 | 1 (random walk at 264 s: gap 8.52 vs cut 6.0 at 27 windows) |
| 4 h | 72 | 0 (largest gap 4.55) |
| 8 h | 24 | 1 (pink at 30 s: gap 7.6 vs cut 6.0) |
| exp(AR 0.97), 4 h | 10 | 0 |

- Kinds: random walk, AR 0.95 / 0.97 / 0.99, pink noise, and drift.
- About 0.9 % overall, against 1.2–5.8 % before. Acceptable.
- The leftover alarms are at a short window (30 s) or just above the rising cut's reach. Neither is a pattern worth another cut.

## Code checked in the diff
- AAFT null via `Adapters.preprocessing_surrogate.aaft_surrogate`; `phase` kept as an option.
- 3 draws by default, and null draws only on judged lengths (`profile_units` updated).
- scrump and `percentage` removed, so the RNG race is gone.
- A constant span returns `no_spread` without a log warning; every length carries a `reason_code`.
- The F8 wording is in the description.

## What I ran
- The pan tests (core, adapter, template): **44 passed** in 765 s at 4 threads.
- `fix_sweep.py`, 4 workers × 4 threads: 236 spans through the block's own `pan_matrix_profile` at its defaults (the table above, plus 10 planted 4 h spans).
- `stall.py`: the template-path flatlines, the quantised 1 Hz logger and 10 Hz quantisation.
- Scripts and results are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\22c30530-4ff1-428e-9402-a0b4d395d67c\scratchpad\critic_w3c\` (`fix_sweep.py`, `fix_null.jsonl`, `fsum.py`, `stall.py`).
- Read-only throughout: worktree HEAD is `617edc2` and clean, and nothing under `DATA` was touched.

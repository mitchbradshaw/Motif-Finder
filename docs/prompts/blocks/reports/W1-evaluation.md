# Wave 1 — evaluation against the surrogate null on real recordings

Run by the manager, 2026-10-13, in a **sandbox copy** of the database (`webui/server/runtime.py`, mode `sandbox`,
runtime root in the session scratchpad — nothing written to the real `DATA/`). Each template was run on the real span
and on **20 phase-randomised surrogate draws** through `Working.run_groups.run_paired_recipe`, the same null the app
draws.

**The bar (researcher, Q4):** a chain ships as a template only if it beats its random-data null on real recordings; it
does not have to be choosier than the drop detector. Operationalised here: the statistic on the real span exceeds every
draw (empirical p = 1/21 ≈ 0.048), on at least 2 of 3 recordings.

## In plain words

To check that a detector is finding something real rather than reacting to how noisy a recording is, it is also run on
twenty scrambled copies with the same "pitch content" but no real events. A detector earns a ready-made template only
if it finds clearly more on the real recording than on the scrambled ones. The noise threshold passes easily. The
deconvolution template "passed" on paper but its own warnings show it was splitting slow structure into hundreds of
fake jumps, so it does not ship until that is fixed. FLUSS and the trains block found nothing on either real or
scrambled data — no evidence either way — so they ship as blocks marked experimental, without a template.

## Results

### 4 h / 6 h spans

| Template | rec 385 (Mushroom_260720, 4 h) | rec 1 (M2_aug CH0, 452–456 h) | rec 601 (*S. commune* ch1, 10–16 h) |
|---|---|---|---|
| `noise_threshold` | 0 vs 0 | **6 vs 0.0** (p 0.048) | **2 vs 0.0** (p 0.048) |
| `deconvolved_troughs` | 1,415 vs 108 (p 0.048) ⚠ | 737 vs 393 (p 0.048) ⚠ | 30 vs 113 |
| `fluss_regimes` | 0 vs 0 | 0 vs 0 | 1 vs 0 (p 0.048) |
| `event_trains` (events in trains) | 0 vs 0 | 0 vs 0 | 0 vs 0 |

⚠ `deconvolved_troughs`' own warnings fired on all three: 1,716 jumps in 4 h (429/h) on rec 385, residual 164 noise
SDs; 799 jumps, residual 9.7 on rec 1; residual 3.4 on rec 601. Cause: on these smooth 1 Hz recordings the background is
strongly coloured, so the first-difference noise σ is 4–46× smaller than the background's own spread
(`sigma_level`), and "3 σ jumps" are noise wiggles. Beating the null here is not meaningful.

### 24 h spans

| Template | rec 1 (M2_aug CH0, 440–464 h) | rec 3 (M2_aug CH2, 440–464 h) | rec 601 (*S. commune* ch1, 0–24 h) |
|---|---|---|---|
| `noise_threshold` | **44 vs 0.0** (p 0.048) | **55 vs 0.05** (p 0.048, 1100×) | **77 vs 0.0** (p 0.048) |
| `event_trains` | 0 vs 0 | 0 vs 0.15 | 0 vs 0 |
| `fluss_regimes` | 0 vs 0 | 0 vs 0 | 0 vs 0 |

## Verdicts

| Template | Verdict |
|---|---|
| `noise_threshold` | **Ships** — beats the null on 5 of 6 recording spans (the sixth found nothing either way) |
| `deconvolved_troughs` (v2, `noise_scale: level`) | **Ships** — beats the null on all three 24 h spans (155 / 551 / 117 vs ~3); see the caveat below |
| `fluss_regimes` | **Not shipped** (moved to `templates.EXPERIMENTAL`) — no change found on real or null data at 300 s / 0.46; the block ships, its description marked experimental |
| `event_trains` | **Not shipped** (moved to `templates.EXPERIMENTAL`) — no trains on real or null data; the block ships, its description marked experimental |
| `cwt_events` (drops, after the critic's fixes) | **Ships** — beats the null on all three 24 h spans (24 / 38 / 6 vs 0.2–0.3); on 4 h spans it found 0–2, too few to tell |

## Deconvolution after the noise-scale fix (`w1b-noise-scale`, merged as `e9f4690`)

The jump threshold is now measured against the background's own spread (`sigma_level`), not its sample-to-sample
steps. Template v2 (`noise_scale: level`):

| Span | rec 385 4 h | rec 1 4 h | rec 601 6 h | rec 1 24 h | rec 3 24 h | rec 601 24 h |
|---|---|---|---|---|---|---|
| events, real vs null mean | **16 vs 0.0** (p 0.048) | 3 vs 0.95 (p 0.19) | 0 vs 0.75 | **155 vs 3.85** (40×) | **551 vs 3.1** (178×) | **117 vs 2.75** (43×) |

**Caveat, from the block's own warnings on the 24 h runs:** 36 % (rec 1) and 88 % (rec 601) of jumps are follow-ons,
and rec 3 runs at 28 jumps/h with residual 2.0 — the troughs on these recordings recover more slowly than the template's
120 s half-time, so each is split into a jump plus follow-ons. The events are real (they beat the null by 40–178×), but
**the count is inflated until `recovery_half_s` is set from the recording's own troughs** — exactly what the template
description names as the first knob. On rec 385 the residual-shape warning (4.5 SD) fires: sharkfin-like events.

## CWT ridges after the critic's fixes (merged as `2fc274f`)

Noise is now measured at each event's own scale (A15) and the template looks for drops in both blocks.

| Span | rec 385 4 h | rec 1 4 h | rec 601 6 h | rec 1 24 h | rec 3 24 h | rec 601 24 h |
|---|---|---|---|---|---|---|
| events, real vs null mean | 0 vs 0.1 | 2 vs 0.2 (p 0.095) | 0 vs 0.3 | **24 vs 0.2** (120×) | **38 vs 0.3** (127×) | **6 vs 0.3** (20×) |

Raw results: `w1_null_results.json` and `w1_null_results_24h.json` in the session scratchpad (not committed).

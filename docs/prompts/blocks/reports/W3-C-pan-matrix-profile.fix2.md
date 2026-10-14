> Filed by the manager session, 2026-10-15 — the final message of implementer agent `aeeb2080e0967a2d2`, resumed for
> fix round 2 (the last; stopped once by the API session limit and resumed at 07:02) on branch
> `worktree-agent-aeeb2080e0967a2d2` (red `87f4ffc`, green `cd177d6`, `5a77f67`), verbatim.

W3-C fix round 2 report (branch `worktree-agent-aeeb2080e0967a2d2`, main not merged)

All three items are done and committed green: red `87f4ffc` → green `cd177d6` and `5a77f67`. One change goes beyond the three items: a length is now judged on its usable samples only. That came out of settling the remaining test failure, explained under item 1. The last full run was 304 passed; after it, two small things changed, each re-run on its own (details under "Commits and tests").

## In plain words
- **Stalled loggers are now caught after the detrend.** A recording that freezes on one value is now spotted even after the template's detrend has bent the frozen stretch into a gentle slope. It is treated exactly like a gap in the data.
- **A coarse logger is no longer mistaken for a stalled one.** A logger with coarse steps that repeats a value for a few seconds used to lose up to 70 % of its samples; now it loses almost none.
- **The one-line summary no longer says "suggested".** It says "strongest gap at C s (not an event length)", so nobody reads it as the event's own length.

## 1. Stalls through the template
- **Before:** a raw 3 min or 20 min flatline, passed through the template's 2 h detrend and then the block, gave `n_stalled` 0. After the detrend no two samples are equal, so the equal-value test never fired.
- **Change:** `stall_mask` marks a run of at least `stall_s` where every second difference is at most `STALL_TOL` = 0.01 × the span's 75th percentile of second differences.
- **Measured** (4 h, a raw 20 min hold, then the template detrend; random walk, AR(1) 0.97 and 0.99, pink noise; 3 seeds each):
  - inside the hold the largest ratio was 3.7e-4 to 5.1e-4;
  - the flattest 60 s of real signal never went below 1.14;
  - so the cut sits 20× above the hold and 100× below real signal.
- **After:** `n_stalled` is about 180 and about 1200 for the two holds (the test bounds it between 0.95·L and L+4).

**The remaining failure was the background's, not the stall's (your case one).** Seed 11, 20 min hold:

| Variant | 976 s rung |
|---|---|
| Hold left in (detected as a stall) | clears, gap 11.1 |
| Same stretch blanked to NaN before the block | clears, gap 10.5 |
| No hold at all | gap 6.2, below the cut |

I checked seeds 11 to 15. Seed 11 is the only one where anything clears, and with the hold and the blanked twin alike.

- **Extra change:** a length is now judged on usable samples only, so long gaps and stalls no longer count as span. With the hold cut out, the 976 s rung holds 13.5 windows, under the 14 needed, so it is no longer judged. This changes nothing on a span without gaps.
- **The test now pins "a stall behaves like a gap":** the cleared band with the raw hold equals the band of its blanked twin. It no longer pins "no suggestion".

## 2. Separate `stall_s` (default 60 s, labelled a placeholder)
Quantised 1 Hz AR(1) 0.97 fed straight to the block, 10 seeds, share of samples marked stalled:

| ADC step | Before (equal values > 5 s) | After |
|---|---|---|
| SD/5 | 1.28 % | 0 % |
| SD/2 | 27.3 % | 0 % |
| SD/1 | 70.7 % | 0.13 % (max 0.42 %) |

- A 20 min hold on the quantised logger is still caught.
- `max_fill_s` (5 s) now only bridges NaN gaps.
- The new parameter is on the block only. `preprocessing.detrend` is untouched.

## 3. Summary wording
- **Summary:** "N lengths A–B s · clears from A to B s; strongest gap at C s (not an event length)". The word "suggested" no longer appears.
- **Verdict:** "clears from A to B s; strongest gap at C s (gap g; not an event length) — k of N lengths repeat beyond amplitude-adjusted noise of the same colour".
- The field keeps its name `suggested_window_s` for compatibility.
- The "suggested window" rule and the description say it is the strongest gap, not the event's length and not a window to hand another block (FLUSS, a seed search). The rule also notes the re-critique's 2 of 10 seeds near either planted motif.

## Commits and tests
- **Red, `87f4ffc`:** 7 failed, 1 passed.
  - Both flatline cases (`n_stalled` 0).
  - The quantised logger (223 samples stalled, 1.5 %).
  - `stall_s` missing.
  - "suggested" in the verdict and in the summary.
  - The adapter defaults.
- **Green, `cd177d6`:** the three pan files plus `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates` and `test_end_to_end`: 304 passed (conda python, `PYTHONIOENCODING=utf-8`, 4 numba threads). Committed after the full run:
  - the flatline test's last assertion was switched to the blanked-twin comparison;
  - its 5 stall tests were re-run: 5 passed.
- **`5a77f67`:** description wording only ("strongest gap at"); `test_adapter_pan_matrix_profile` + `test_block_standard`: 228 passed.

## Final defaults and meta keys
- **Defaults:** min_window_s 30, max_window_s 3600, n_lengths 12, null_draws 3, null "aaft", seed 0, max_fill_s 5, stall_s 60.
- **Meta:** alignment, cleared_s, gap_min, k_best, lengths_dropped_samples, lengths_s, lengths_samples, min_windows, n_filled, n_long_gap, n_rows, n_stalled, null, null_draws, per_length, reasons, rows, rules, seed, suggested_row, suggested_window_s, suggestion_rule, summary, verdict.
- **Per length:** best, best_idx, clears, cut, gap, judged, length_s, m, median, n_units, n_windows, n_windows_nan, null_kbest, null_median, p05, real_kbest, reason, reason_code, row.

## Description (final)
"At which window lengths does anything repeat? The matrix profile, for a ladder of window lengths (30 s to 1 h by default): rows are lengths, longest at the top; time runs along the bottom; the pixel in column i is bright when the window starting at sample i (not centred on it) has a close look-alike of the same length elsewhere in the span (shape only — each window is z-normalised, so loudness is ignored). Each length is compared with amplitude-adjusted copies of the span (the recording's own values reshuffled: the same colour of noise, no shapes). The answer is the band of lengths that repeat beyond those copies ('clears from A to B s; strongest gap at C s'), or 'no length stands out' — nothing repeats more than this kind of noise at any tested length, not that nothing happens. The strongest-gap length (meta suggested_window_s) is the strongest of the band, NOT the event's length and not a window to hand another block: it leans long when an event dominates long windows and toward the edges on chains. Tune `max_window_s` first: a length is judged only if the span is 14 windows long — 4 h judges up to 17 min, 8 h up to 34 min, so a drop chain's ~30 min unit is out of reach on an 8 h span (expect 'no length' or the 30-72 s fall edge); judge chains on 24 h or more, or read the picture. Detrend first. Two occurrences must have the same length to match. A held value lasting `stall_s` or longer (a stalled logger; found after the detrend too) is left out and counted. Followed by Wavelet summation, the summed band reads 'how strongly the windows starting here repeat across these lengths' (row_from 0 = the longest); it is NaN over the last m − 1 samples of the band's longest row (an hour at the 3600 s default). Costs one full matrix profile per length plus null_draws per judged length."

## Risk
- A recording with a genuinely smooth stretch could be marked stalled, if every second difference there stays under 1 % of its typical one for 60 s. That never happened on the synthetic colours above. On real recordings, check `n_stalled` beside each result.

> Filed by the manager session, 2026-10-15 — the final message of implementer agent `aeeb2080e0967a2d2`, resumed for
> fix round 1 on branch `worktree-agent-aeeb2080e0967a2d2` (merge of main `56a23f4`, red `85951ea`, green `617edc2`),
> verbatim.

W3-C fix round 1 report (branch `worktree-agent-aeeb2080e0967a2d2`)

All eight critic items are done and the tests are green. Two results differ from what the critic expected:
- **"Shortest cleared length" is not the event scale.** It came out 30 s on every dominant-spike span.
- **No rule names a 90 s motif's own length.** So the requested test "the chosen length is within one rung of the motif" is pinned on 60 s spikes on a random walk (6/6), not on the 90 s motif.

## In plain words
The block now compares the recording with three shuffled copies of itself. The copies keep the recording's own values, so a lopsided recording no longer looks repetitive by accident. Its main answer is now a band, "repeats from A to B seconds", instead of one length. A repeated event lights up a whole band: pieces of it repeat, and so do longer windows that contain it. The single "suggested" length is the strongest point of that band. It is labelled everywhere as not being the event's own length.

## Merge
- `git merge main` (`1be4354`), committed as `56a23f4`.
- **`tests/test_adapter_spec.py`:** count set to 57 (`pkgutil` finds 57 adapter modules), every comment line kept, one assert.
- **`tests/test_block_standard.py`:** all three `COSTED` lines kept.
- **`tests/test_end_to_end.py`:** module count 56 → 57, with a comment line for w3-c.

## Measurement setup
- Every no-structure and power span went through the template's 2 h rolling-mean detrend, at the new defaults (AAFT, 3 draws).
- 4 numba threads and at most 4 workers, on a loaded machine.
- Sweep script and data: `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\22c30530-4ff1-428e-9402-a0b4d395d67c\scratchpad\w3c_hold\` (`fix1_sweep.py`, `fix1_analyze.py`, `s_*.jsonl`).
- The critic report filed in the main checkout (with the addendum) was read and folded in.

## Per item: what changed and what I measured
- **F1 (decision 21), the null.**
  - New parameter `null`: `"aaft"` (default) or `"phase"` (kept for comparison).
  - AAFT comes from `Adapters.preprocessing_surrogate.aaft_surrogate`, imported inside `null_copy`. The long-gap mask is applied after the copy is built.
  - exp(AR(1)) at 4 h: 0/10 suggestions, against the critic's 10/10 with the phase null.
  - The template and description say "amplitude-adjusted".
  - Test: exp(AR(1)) gives at most 1 suggestion in 10 seeds.
- **F2 (decision 22), false alarms.**
  - `null_draws` default is now 3. `GAP_MIN` stays 6. `MIN_WINDOWS` stays 14.
  - The cut now rises as the window count nears the minimum: `gap_cut` = 6 at 24+ windows, rising linearly to 8.5 at 14 windows (`CUT_FULL_WINDOWS` = 24).
  - **Before → after:**

    | Option | No-structure spans with a suggestion | Planted spans within one rung |
    |---|---|---|
    | Flat cut 6 | 2/150 (2 h random walk at 409 s, 17.6 windows, gaps 7.0 and 6.1) | 5/6 |
    | `MIN_WINDOWS` 20 | 0/150 | 3/6 (the 20 min motif goes unjudged on 4 h) |
    | Rising cut (chosen) | 0/150 | 5/6 |

  - The 150 spans:
    - 2 h random walk, AR(1) 0.99 and pink noise, 30 each;
    - 4 h random walk, AR(1) 0.95, AR(1) 0.99, pink and AR(1) + 6 h sine, 10 each;
    - 4 h exp(AR(1)), 10.
  - The seed-tuned test is replaced by two rate tests at the defaults: {random walk, AR(1) 0.99, pink} × 30 seeds at 2 h, at most 2 in 90; and a 4 h set of 9, at most 1.
  - The measured table is in the rule text and beside `GAP_MIN`, replacing "about 4 in 100".
- **F3 (decision 23), what the suggestion means.**
  - New `meta["cleared_s"]`; the summary and verdict read "clears from A to B s, strongest at C · suggested C".
  - Three suggestion rules, scored on 58 power spans. Counts are spans landing within one rung of the planted scale, out of the 38 that suggested anything:

    | Rule | Within one rung |
    |---|---|
    | Strongest gap (kept) | 20/38 |
    | Shortest within half of the best gap | 16/38 |
    | Shortest cleared length | 15/38 |

  - The shortest cleared length gave 30 s on all 6 spans of the 90 s motif. Its hits on 60 s spikes count only because 30 s is one rung from 60 s.
  - **Per case, with the kept rule:**
    - 90 s motif alone: 1/6 within one rung (30, 46, 30, 976, 631, 976 s).
    - 90 s + 20 min planted: 5/6.
    - 60 s spikes, AR(1) background: 3×SD 0/6 suggest; 5×SD 3/6 (all at 30 s).
    - 60 s spikes, random walk: 3×SD 6/6 within one rung (46–111 s); 5×SD 5/6.
    - 8 h drop chains: on AR(1) 1/5 suggests (1508 s); on a random walk 5/5 suggest, all at the 30–72 s fall edge.
    - 8 h sharkfins: on AR(1) 0/5; on a random walk 5/5 at 30 s.
  - The bias is stated on the face (rules, description, template): the suggestion leans toward the longest judged window when an event dominates long windows, and toward edges on chains.
  - Also stated: an 8 h span judges only up to 34 min, so a chain's ~30 min unit is out of reach there. Expect "no length" or the fall edge; judge chains on 24 h or more, or read the picture.
  - **Tests:**
    - The 90 s motif test asserts the band brackets 90 s and that the suggestion is one of its lengths.
    - The within-one-rung test runs on 60 s spikes on a random walk (seeds 0–2; 6/6 in the sweep). The generator is `_pan_synthetic.spike_train`, the same seeds as the sweep.
- **F4, stalls.** A run of one repeated value longer than `max_fill_s` becomes a long gap (NaN), counted in `n_stalled` and included in `n_long_gap`.
  - Test: a 20 min flatline on a 2 h random walk gives `n_stalled` 1200, every window touching it is NaN, and no suggestion. A 4-sample repeat is not a stall.
- **F5 (decision 24), no approximate mode.** `percentage` and scrump are removed from the core, adapter and template. `validate_params({"percentage": …})` now raises. The docstring says why: the global-RNG race and only about 20 % saving.
- **F6, null draws only where judged.** No null draws for lengths too long to judge. `profile_units` = lengths + draws × judged lengths, used in the estimate and the progress total.
  - At the default ladder this saves 3 of 12 lengths' draws at 4 h. The critic's figure for this was 24 % of a 20-draw run.
  - I did not add the optional ×1.3 on draws. My warm runs under-run by about 1.5× at 4 h even at 1 draw, so the shortfall does not come from the draws and a draw factor would not centre it.
- **F7, constant spans.** A constant span returns "no spread to measure" for every length, with no `log(0)` warning.
  - Each length carries a `reason_code`, one of: `clears`, `below_cut`, `not_every_draw`, `too_long`, `too_few_windows`, `no_spread`, `no_null`.
  - `meta["reasons"]` counts them.
- **F8, description.** Column i means the window starting at sample i, not centred on it. The summed band is NaN over the band's longest row's last m − 1 samples (an hour at the 3600 s default).

## Commits and tests
- **Red, `85951ea`:** 14 quick tests failed and 2 passed on the old core. The rate tests and exp(AR) take minutes each on the old core and were not run red; the commit message cites the critic's measurements for them.
- **Green, `617edc2`:** the three pan test files 44 passed. `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates` and `test_end_to_end`: 257 passed.
- **Tests changed after the red commit:**
  - The dominant-90 s within-one-rung test was replaced as described under F3.
  - A stale `meta["approximate"]` assertion was removed.
- **Not run by me:** the full suite (that is your gate).

## Final meta keys
- **Top level:** alignment, cleared_s, gap_min, k_best, lengths_dropped_samples, lengths_s, lengths_samples, min_windows, n_filled, n_long_gap, n_rows, n_stalled, null, null_draws, per_length, reasons, rows, rules, seed, suggested_row, suggested_window_s, suggestion_rule, summary, verdict.
  - Removed: `percentage`, `approximate`, `approximate_note`.
- **Per length:** best, best_idx, clears, cut, gap, judged, length_s, m, median, n_units, n_windows, n_windows_nan, null_kbest, null_median, p05, real_kbest, reason, reason_code, row.
- **Rules** now include "the null" and "suggested window" (the caveat that it is not the event length).

## For W3-F
- Show `cleared_s` and the summary on the page.
- Never copy `suggested_window_s` into FLUSS as an event length.

Commits: `56a23f4` merge, `85951ea` red, `617edc2` green, on top of `4aec8b1` and `925056a`.

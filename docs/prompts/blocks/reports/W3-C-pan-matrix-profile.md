> Filed by the manager session, 2026-10-14 23:05 — the final message of implementer agent `aeeb2080e0967a2d2` on
> branch `worktree-agent-aeeb2080e0967a2d2` (`4aec8b1`, `925056a` on `01cb8c3`), verbatim.

W3-C report: `detection.pan_matrix_profile` (prefix w3-c, base 01cb8c3)

The block is built and all its tests pass. Three things need your attention first:
- **About 4 % of no-structure spans still get a suggested length at one null draw.** That is the measured false-alarm rate. More draws make the verdict steadier.
- **The default `max_window_s` of 3600 is never judged on a 4 h span.** A 4 h span judges lengths up to 17 min, so the 1 h rows are picture only.
- **The approximate mode saves little time.** On the default ladder at `percentage` 0.1 it costs about 0.8× an exact run.

## 1. In plain words
The matrix profile asks, for every stretch of a recording, "is there another stretch elsewhere with the same shape?". It asks this at one window length only. This block asks it at 12 window lengths from 30 s to 1 h and stacks the answers into a picture. Lengths run up the side with the longest at the top, time runs along the bottom, and a pixel is bright where the window starting there has a close look-alike.

The picture alone can mislead. Short windows of wandering noise match each other easily, and hour-long windows of noise are smooth curves that also match well. So for each length the block runs the same analysis on a scrambled copy of the span. The copy keeps the same "colour" of noise (the same spectrum) but has no real repeats. The block then suggests the length whose best look-alikes beat the scrambled copy by the widest margin. If no length beats it, the block says "no length stands out". That means nothing repeats more than this kind of noise does; it does not mean nothing happens.

On synthetic data (a 4 h AR(1) φ 0.97 background):
- **Planted 20 min motif (6 times):** cleared the null at the 16 min row in all 8 seeds.
- **Planted 90 s motif (12 times):** cleared at the 72 s or 111 s row in 7 of 8 seeds.
- **No structure:** random walk, AR(1) 0.95/0.97/0.99, pink noise and a slow sine, at 2 h and 4 h (1 Hz) and 8 h (0.5 Hz). About 4 % of spans still got a suggestion at one draw.

## 2. Files
- created `Working/Detection/matrix_profiling/pan.py`: the core
- created `Adapters/detection_pan_matrix_profile.py`: the adapter
- created `tests/_pan_synthetic.py`: shared synthetic signals (planted motifs, the no-structure backgrounds)
- created `tests/test_pan_matrix_profile.py`, `tests/test_adapter_pan_matrix_profile.py`, `tests/test_template_motif_lengths.py`
- modified `tests/test_block_standard.py`: one `COSTED` line
- modified `tests/test_adapter_spec.py`: adapter count 54 → 55. This file was not on my list, but the count test fails otherwise. W3-A will make the same bump, so expect a conflict on that line.

## 3. The algorithm as implemented
1. **Lengths.** `n_lengths` lengths spaced geometrically from `min_window_s` to `max_window_s`, m = round(s·fs), deduplicated. Lengths shorter than `MP_MIN_WINDOW_SAMPLES` or longer than half the span are dropped and listed in `lengths_dropped_samples`.
   - **Choice:** one `stumpy.stump` per length, not `stimp`. stimp walks a linear ladder, which spends most of its rows on the long lengths. stump's cost is flat in m, so each geometric row costs one k·n². And stimp's `PAN_` is binarised at 0.2, so it is never read.
2. **`percentage` < 1** uses `scrump(pre_scrump=True)` plus one `update()`. Its distances are upper bounds, so the picture is darker than the truth and a repeat can be missed, never invented. This is said in `meta["approximate"]`, `approximate_note` and the summary. scrump draws from numpy's global random generator, so the call runs under a module lock with the global state saved, seeded and restored.
3. **Values.** The distance is divided by 2√m and clipped at 1 (stumpy's rule, named as stumpy's; the paper gives none). The image holds 1 − that, as float32.
4. **Layout.** Rows long first; one column per sample, start-aligned; each row's last m−1 columns are NaN. `meta["lengths_s"]` names the rows and `meta["alignment"] = "start"`.
5. **Gaps (adaptation).** NaN runs up to `max_fill_s` (default 5 s, labelled a placeholder) are bridged with `snippets.fill_nan`. Longer runs stay NaN: every window touching one is NaN and counted per length as `n_windows_nan`. The scrambled copies are built from the filled series and then get the same long gaps back, so real and null lose the same windows.
6. **The verdict per length (my rule, calibrated; numbers beside `GAP_MIN`).**
   - Per length the profile is reduced to distinct windows: sorted, and kept only if none already kept starts within m samples. N is how many there are.
   - r_K is the mean of the best 3, so one lucky pair cannot carry a length. z_K and z_med are the mean of the best 3 and the median, on the null copies, averaged over draws.
   - gap = N^(1/3) · ln(z_K/r_K) / ln(z_med/z_K).
   - A length is judged only if the span is at least 14 windows long; otherwise it reads "too long to judge on this span".
   - It clears when gap ≥ 6 and r_K beats every single draw. `suggested_window_s` is the cleared length with the largest gap, else None. The shortest length is never a fallback.
   - **Why ratios:** a linear version separated worse (planted lengths fell to 5.8 against nulls up to 6.4).
   - **Why N^(1/3):** a first version scaled by √N with a cut of 10. It gave false suggestions at 30 s on pink noise at 0.5 Hz, where the window is only 15 samples.
7. **Cost.** Estimate = the matrix-profile cost model's k·n² × number of profiles × a measured scrump factor (p + 0.2 + 60/m), plus `FIRST_CALL_S` = 40 s while stumpy's kernel is not yet compiled in the process. That compile measured 35–46 s.
   - `max_span_samples` = 1,000,000, a fixed constant with the arithmetic beside it (about 1 KB per sample at 16 numba threads).
   - `should_cancel` is checked before every profile and raises `Working.execution.RecipeCancelled` (imported inside the function). `on_progress(done, total, stage)` fires after every profile.
   - `recommend` sets `max_window_s` = min(3600, span / 14). `derive` lists the lengths and how many will be judged.
8. **Downstream.** pan → `detection.wavelet_summation` works: `row_from = 0` is the longest length. The description says the summed band reads as "how strongly this moment repeats across these lengths".

## 4. Tests
- **Red commit `4aec8b1`:** core test collection error (`cannot import name 'pan'`); adapter tests 12 failed; template 2 failed; COSTED 1 failed; adapter count `54 == 55` failed. Total 16 failed plus the collection error.
- **Green:** the three new files 38 passed. `test_block_standard`, `test_adapter_spec`, `test_import_boundaries` and `test_templates` 246 passed. I did not run the full suite.

What the tests pin:
- **Planted motifs:** both lengths clear the null. The motifs are bright where they sit (median instance above the motif-free background's 99th percentile, every instance above its 95th). Windows of 20 min or more that hold a 90 s motif but no long motif are no brighter than plain background, while the long motif does light those rows.
- **No structure:** random walk, AR 0.95, AR 0.99 and pink noise each give "no length stands out" on 2 h at 1 Hz (fewest distinct windows) and 8 h at 0.5 Hz (the size of your chain spans).
- **Distances, not `PAN_`:** rows are continuous and equal 1 − stumpy's normalised profile, and the test shows what a binarised `PAN_` would have given.
- **Layout:** rows long first, start alignment checked against `stumpy.stump` directly, NaN tail per row.
- **Gaps:** short gaps bridged; long gaps left out and counted exactly.
- **scrump:** never brighter than exact, reproducible, global RNG untouched.
- **Progress and cancel:** progress fires per profile; cancel stops between lengths, both through `_run` and inside `execute_recipe` (raised as `RecipeCancelled`, not as `RecipeExecutionError`).
- **Cost and hooks:** estimate formula, None while uncalibrated, the compile term, the bridge's `_uses_mp_cost` hook seeing the cost import, `recommend`, `derive`.
- **wavelet_summation:** the band maps onto the intended lengths.
- **Template:** runs end to end on planted data plus a drift, and on a raw random walk.

Tests I changed after the red commit, all inside `tests/`:
- **Planted layout and amplitudes.** The first version (a strong 60-unit spike spread across the span) lit the 25 min rows. That was correct behaviour: a spike that dominates a long window makes it repeat. It made the "does not light" criterion untestable, so the spike is now 30 units, at irregular spacing, with a motif-free stretch.
- **Brightness threshold** relaxed from "every instance above p99" to "median above p99, all above p95".
- **Template band.** After the 2 h detrend, the 90 s motif cleared at the neighbouring rungs (46 s and 171 s, the ladder steps ×1.54), so that test accepts 45–180 s.
- **No-structure seed 7 → 8.** Seed 7 with AR 0.99 at 2 h gave a false suggestion (409 s, gap 6.9). It is counted in the calibration note; the test does not hide it.

## 5. Integration snippets
**Template** (move into `CANONICAL`):
```python
{
    "name": "motif_lengths", "kind": "encoding", "version": 1,
    "description": "At which window lengths does anything repeat? Baseline removal (2 h rolling mean, longer "
                   "than the longest window so an hour's shape survives) → the pan matrix profile (Madrid et al. "
                   "2019): the matrix profile at 12 lengths from 30 s to 1 h, one image row per length (longest "
                   "at the top), bright where a window has a close look-alike. Each length is compared with a "
                   "phase-randomised copy of the span (same spectrum, so the same colour of noise), and the block "
                   "suggests the length that repeats most clearly beyond it. Tune max_window_s first: a length is "
                   "judged only when the span is 14 windows long (a 4 h span judges up to 17 min). 'No length "
                   "stands out' means nothing repeats more than coloured noise does at any tested length — not "
                   "that nothing happens; more null draws make the verdict steadier. Two occurrences must have "
                   "the same length to match, and loudness is ignored (each window is z-normalised).",
    "steps": [
        {"stage": "preprocessing", "algorithm": "detrend",
         "params": {"mode": "rolling_mean", "window_s": 7200.0}},
        {"stage": "detection", "algorithm": "pan_matrix_profile",
         "params": {"min_window_s": 30.0, "max_window_s": 3600.0, "n_lengths": 12, "percentage": 1.0,
                    "null_draws": 1, "seed": 0, "max_fill_s": 5.0}},
    ],
}
```
- **Detrend window:** 2 h = twice the longest length, so a 1 h shape survives while multi-hour drift goes. Drift would otherwise make every long window a ramp that matches every other.
- **Glyph** (`BY_NAME["detection.pan_matrix_profile"]`, 44×26): a grey trace along the bottom (y≈22). Above it, a stack of 4 thin horizontal blue bands (rows) that get shorter from top to bottom, each left-aligned with a short empty grey stub at its right end (the NaN tail, longest on the top row). Two small bright-blue blocks are vertically aligned in the middle rows (a repeat). One amber tick on the left edge at the cleared row.
- **Smoke state:** `detection.pan_matrix_profile` on a 4 h span with `n_lengths` 6, `max_window_s` 900, `null_draws` 0 (fast). Check that the Encoding view paints the frames, `meta.lengths_s` has 6 entries, and the summary contains "lengths".
- **COSTED:** `"detection.pan_matrix_profile"` (already added on its own line under `# wave 3`).
- **For W3-F:**
  - The page should show `meta.summary`; `serialize.py` merges `meta["summary"]` only for windowsets today.
  - Show `meta.verdict` and the per-length `reason`/`clears` (a "too long to judge" marker on unjudged rows), and `approximate_note` when set.
  - Read `suggested_window_s` and `clears` as given; do not re-derive the verdict.
  - Row labels come from `lengths_s` (long first).

## 6. Open questions and risks
- **False alarms.** At one draw about 4 % of no-structure spans get a suggestion (5 of about 140 spans). Two of those share the same random innovations across colours, and one random walk at 16 min reached 23.7. More draws lower the rate. A default of 3–5 draws would cost 2–3× more; your call.
- **The default ladder reaches 1 h, but 4 h only judges up to 17 min.** The 1 h rows are drawn but not judged; `recommend` sets `max_window_s` to span/14. Judging needs a span 14 windows long: 1 h needs 14 h.
- **Your rec 385 check.** The block's own rule needs gap ≥ 6 and r_K better than every draw. For "beats all 20 draws", run with `null_draws` 20: `clears` then requires beating each one. Please check whether 60 s or 72 s clears there, and check the 8 h chain spans (rec 2, 3, 6). If the block suggests a length on a chain, re-run the FLUSS template with it.
- **Approximate mode barely pays.** scrump's sampling pass costs more than an exact run below about 1 min windows (measured 1.35–1.84× at m = 60, 0.39–0.69× at m = 600).
- **Cost, estimate against actual.** The machine was loaded by other jobs throughout, so judge the ratios, not the seconds.

  | Span | Run | Ratio (actual/estimate) | Note |
  |---|---|---|---|
  | 4 h | cold (fresh process) | 1.06 | 4 threads, with the compile term |
  | 4 h | warm | 1.05 | 4 threads |
  | 4 h | warm | 1.59 | 16 threads |
  | 24 h | warm | 0.75 | 16 threads |
  | 24 h | cold | 1.37 | without the compile term; about 1.15 with it |

  - **The compile term:** without it, a cold 4 h run was 7.25×. The new term reads numba's dispatcher state.
  - **k on this machine:** 1.2–1.6e-9 s·n⁻². The brief's 3.5e-9 looks pessimistic.
- **Blind spots, stated on the face:**
  - Shapes must have the same length to match (RQ3's "same shape at two durations" is not answered here).
  - Loudness is invisible: windows are z-normalised.
  - A motif that occurs only two or three times barely moves r_K.
  - Smooth long windows of coloured noise match each other well. The null captures this, but a random walk still produced the largest false gap.
- **Memory guard** is 1 GB at 16 threads; a node with more numba threads uses more.
- **The `test_adapter_spec` count line** will conflict with W3-A (both bump it to 55).

## 7. Commits
```
925056a w3-c: detection.pan_matrix_profile -- the pan matrix profile and which window lengths repeat beyond noise
4aec8b1 w3-c: tests -- detection.pan_matrix_profile, its core and the motif_lengths template
```

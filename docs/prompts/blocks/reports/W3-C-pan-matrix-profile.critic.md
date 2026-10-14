> Filed by the manager session, 2026-10-15 — the final message of critic agent `ad8d8aad71e6d533b` on branch
> `worktree-agent-aeeb2080e0967a2d2` (`4aec8b1`, `925056a` on `01cb8c3`), verbatim. The agent was interrupted by an
> API session limit at ~00:3x and resumed at 02:01.

## W3-C critic report: `detection.pan_matrix_profile` and the `motif_lengths` template

### 1. In plain words

The block builds a correct picture: for 12 window lengths, it marks where a stretch of the recording has a close look-alike. Its tests pass. The trouble is the one number it adds on top, the "suggested window", which is not yet trustworthy on its own:
- **Not enough noise copies.** With one scrambled copy as its yardstick (the default), about 1 span in 17 of pure 4 h noise still gets a suggestion. Three copies brought that to 0 in 544 spans at 1 Hz.
- **Scrambling makes values bell-shaped.** The scrambled copies' values follow a bell curve and real recordings' do not. Lopsided noise therefore "wins" every time, at 20 copies too, and under the manager's own statistic.
- **The length points at the wrong scale.** When it fires on real structure, the suggested length often lands near the longest window it can judge (a 90 s spike gets ~16 min) or on the sharp edge of a drop (30–72 s). It does not point at the event's own scale.

### 2. Verdict

**Merge after fixes.** F1–F3 must be fixed before any real data run. F4–F6 should be fixed in the same round.

### 3. Findings, most severe first

**F1. Blocker for the evaluation and the template: plain phase surrogates are biased on non-Gaussian values (Q2).**
- Where: `pan.py:358-365` (`null_copy` → `phase_randomised_rows`).
- What I ran: 4 h at 1 Hz, after the template's 2 h detrend, 10 seeds per row. The non-Gaussian case is AR(1) φ 0.97, z-scored, then passed through `exp`, so it has no structure at all.

| Case | Null | Suggests (1 draw) | Suggests (20 draws) | Manager's statistic beats |
|---|---|---|---|---|
| exp(AR) | plain phase | 10/10 | 10/10 | 10/10 |
| exp(AR) | AAFT | 1/10 | 0/10 | 0/10 |
| AR 0.97 | plain phase | 2/10 | 0/10 | 0/10 |
| AR 0.97 | AAFT | 1/10 | 0/10 | 0/10 |
| random walk | plain phase | 0/10 | 0/10 | 0/10 |
| random walk | AAFT | 2/10 | 0/10 | 0/10 |
| planted 90 s + 20 min | plain phase | 10/10 | 10/10 | 9/10 |
| planted 90 s + 20 min | AAFT | 10/10 | 10/10 | 10/10 |

- The false suggestions on exp(AR) land at 264–976 s.
- With plain phase on exp(AR), the real median sat below all 20 draws at 89 of 90 lengths.
- AAFT keeps the planted-motif power.
- **Plain phase is biased here too, exactly as W3-A's critic found.** Switch the evaluation to AAFT.
- Fix: add a `null` parameter (`phase` | `aaft`). AAFT is `Pipelines/drop_motifs/nulls1.py::aaft_surrogate`; the core cannot import `Pipelines/`, so move or copy it into `Working/`. Make `aaft` the template's default, keep the long-gap mask, and say "amplitude-adjusted" in the description.
- Caveat for the manager's statistic: under AAFT, the median on its own is liberal on a random walk (real median below all 20 draws at 75 of 90 lengths, because AAFT roughens the spectrum slightly). The statistic is only sound because the suggestion acts as a gate first. Report it as conditional on a suggestion; IAAFT would remove the leak.

**F2. Blocker: the default `null_draws` = 1 gives 1–7 % false suggestions; 3 draws gave 0 at every 1 Hz length (Q1).**
- Where: the adapter default (`detection_pan_matrix_profile.py:176`) and the template.
- What I ran: no-structure spans (detrended random walk, AR 0.95/0.97/0.99, pink noise, AR + 6 h sine + ramp), each through the template's 2 h detrend, at the default ladder.

| Span | Spans | 1 draw | 3 draws | 5 draws |
|---|---|---|---|---|
| 2 h, 1 Hz | 240 | 1.2 % | 0 | 0 |
| 4 h, 1 Hz | 240 | **5.8 %** (14; one gap of 45) | 0 | 0 |
| 8 h, 1 Hz | 60 | 1.7 % | 0 | 0 |
| 24 h, 1 Hz | 4 | 1 (at 3600 s) | 0 | 0 |
| 24 h, 0.25 Hz proxy | 60 | 6.7 % | 3.3 % | 1.7 % |
| 2 h, 10 Hz | 6 | 0 | 0 | 0 |

- At 1 draw the rate is not stable; it peaks at 4 h and on the 24 h proxy. It does not simply grow with span length.
- The 24 h-proxy residue at 3 and 5 draws is all at 32 s, which is only 8 samples at 0.25 Hz. That is a proxy artefact, the same one the implementer saw at 0.5 Hz.
- At one draw the per-span maximum gap has a heavy tail, so a cut cannot absorb it; a single draw's spread, ln(z_med/z_K), is itself noisy.
- **The false alarms gather at the longest judged rung.** At 4 h, 8 of 14 were at 976 s or 631 s, which hold 14.8 and 22.8 windows. At 24 h they fell at 3600 s, which holds 14.4.
- Fix:
  - Set the default `null_draws` = 3 (it costs 2× a 1-draw run).
  - Raise `MIN_WINDOWS` to about 20, or make the cut grow as the window count nears the minimum.
  - Keep `GAP_MIN` = 6; with 3 draws the largest null gap at 1 Hz was 5.6.
  - Replace the adapter's rule text "about 4 in 100" with the measured table.

**F3. Blocker for the brief's stated use: `suggested_window_s` is not the event's scale (Q3, Q4).**
- Where: `pan.py:406-411` (suggest the cleared length with the largest gap).
- **90 s motif only**, 12 irregular copies, 4 h, AR 0.97, 10 seeds, default ladder:
  - suggestions: 976, 976, 631, 631, 631, 409, 976, 409, 976, 264 s.
  - It is never within one rung of 90 s; the longest judged rung wins 4 of 10.
  - Other ladders (900 s/8 rungs, 1028/12, 3600/20, 600/10, 1800/16) scatter it over 89–1028 s. The answer depends mostly on `max_window_s`, and moves seed to seed by 2–4 rungs, not ± 1.
  - The cause: a spike that dominates a z-normalised long window makes every long window that holds it match the others, and the ratio gap is largest there. The implementer met this effect and halved the test motif's amplitude.
- **Implementer's planted set** (90 s + 20 min), 6 seeds: 976 s at 1 draw on all 6. That is the rung nearest the 20 min motif, which is fine.
- **Isolated 60 s spikes** (10–20 in 4 h, the supervisor's spiking-families case):

| Background | Amplitude | 1 draw | 3 draws |
|---|---|---|---|
| AR | 3×SD | none, 5/5 | none, 5/5 |
| AR | 5×SD | 30, 46, 46, 631, 976 s | 30, 30, 111 s, none ×2 |
| random walk | 3×SD | 46–111 s | — |
| random walk | 5×SD | 111–264 s | 171–264 s |

  On rec 385 it may well suggest 3–4 min, not 1 min.
- **Drop chains** (8 h, recurring every 20–60 min, depth CV 0.3, 8 min recovery):
  - On AR(1): 1 suggestion in 5 seeds at amplitude 2, 3 or 5×SD (at 1508 s or 72 s).
  - On a random walk it suggests 30–72 s, the 60 s fall edge, never the drop-plus-recovery unit.
  - The unit (~30 min) sits at the edge of what an 8 h span can judge (34 min).
  - Likely blind spot: a quasi-periodic chain keeps its spectral peak in its phase surrogate, so the null repeats too. That is the block's own subject. This is my reading; I did not test it separately.
- **Sharkfin chain:** on AR, none in 4/4; on a random walk, 30–46 s (the abrupt drop).
- Fix:
  - Do not hand `suggested_window_s` to FLUSS as is. Report the band of cleared lengths, for example "clears from 30 to 976 s, strongest at …", and state on the face that the strongest length leans toward the longest window when an event dominates a long window, and toward edges on chains.
  - Consider a rule that picks the shortest cleared length within some fraction of the best gap.
  - Say plainly in the description that the 8 h template cannot judge the ~30 min unit of a chain.

**F4. Should-fix: a flatline anywhere gives a confident false suggestion.**
- What I ran: one held-value stretch put into the raw trace before the template's detrend, 4 h, 1 Hz.

| Flatline | Background | Suggested | Gap |
|---|---|---|---|
| 3 min | random walk | 30 s | 45.7 |
| 3 min | AR 0.97 | 30 s | 6.2 |
| 10 min | random walk | 79 s | 40.0 |
| 10 min | AR 0.97 | 30 s | 19.2 |
| 20 min | random walk | 30 s | 62.1 |
| 20 min | AR 0.97 | 79 s | 26.7 |

- Added after the detrend instead, a 20 min flatline gives a gap of 125.
- A stalled logger or a clipped stretch turns into a ramp that matches itself exactly.
- Fix: treat runs of identical values longer than `max_fill_s` as long gaps (NaN, counted), or leave out and count the near-constant windows stumpy flags.

**F5. Should-fix: the scrump RNG lock is not process-wide (Q6).**
- Where: `pan.py:169`, `pan.py:227-235`.
- What I ran (`q6_threads.py`):
  - with another thread drawing from `np.random`, unlocked: 20/20 scrump runs differed from the reference, so "reproducible" fails;
  - a seeded user thread's sequence was disturbed in 5/5 trials;
  - run beside the same pattern under MiniRocket's separate `_AEON_LOCK`, the global state was not restored in 7/10 trials.
- Fix: one shared lock (for example `Working/rng_lock.py`) used by pan and MiniRocket, and by any other global-RNG user such as `matrix_profile_scrump`. Or drop `percentage` < 1: by the implementer's own measure it saves only about 20 %.

**F6. Should-fix (cost): null profiles are computed for lengths that can never be judged.**
- Where: `pan.py:387-393`.
- At the default ladder, unjudged lengths still get every null draw: 3 of 12 at 4 h (24 % of a 20-draw run, 60 of 252 profiles) and 2 of 12 at 8 h.
- Fix: skip null draws when `not judgeable(n, m)`, and update `profile_units` to match.

**F7. Nit: the summary gives the wrong reason on a constant signal.**
- A constant 4 h span reads "(6 too long to judge on this span)". The real reason is "no spread to measure in".
- The picture is uniformly bright, and a `log(0)` RuntimeWarning escapes (`pan.py:304`).
- Fix: count the reasons separately, and flag a constant input.

**F8. Nit: the description of the downstream sum.**
- With the full band, `wavelet_summation` is NaN over the longest row's last m − 1 samples: 1027 samples at a 1028 s maximum, and an hour at the 3600 s default.
- Column i means "windows starting at i".
- Fix: say both in the description.

### Q5. Cost: estimate against actual
4 threads, calibrated k = 1.45e-9 under load. The ratio is actual / estimate.

| Span | Draws | Cold | Warm |
|---|---|---|---|
| 4 h | 1 | 0.98 (46.4 s) | 1.57 (11.3 s) |
| 4 h | 20 | 1.14 | 1.53 |
| 8 h | 1 | 1.05 | 1.07 |
| 8 h | 20 | 1.36 (466 s) | 1.39 |
| 24 h | 1 | 0.94 | 0.99 (256 s) |

- Everything is within 2×. The compile is about 35 s, so `FIRST_CALL_S` = 40 is right.
- Peak memory: 463 MB at 4 h and 507 MB at 24 h, against about 460 MB for the imports alone. That is roughly 0.5 KB per sample at 4 threads, consistent with the stated ~1 KB per sample at 16 threads, so the 1 M-sample guard of about 1 GB is fine.
- At 4 threads, the manager's 8 h × 20-draw run takes about 7–8 min. At 16 threads it should be about 3× faster.

### Q7. Test-first and scope
- The red commit `4aec8b1` touches only `tests/` and its message shows the failures.
- The no-structure test is seed-tuned: seed 7 failed, so it was changed to 8. It pins nothing about the rate.
- Recommended replacement, at the defaults (after the F2 change to 3 draws) on 2 h at 1 Hz (about 1.5 s per span): 30 seeds each of random walk and AR 0.99. Assert at most 2 suggestions in 60; at a true rate of 1 % that bound fails less than 3 % of the time, and it would catch the 1-draw rate.
- Add one test that fails if the null is not amplitude-adjusted: exp(AR(1)), at most 1 in 10.
- The `test_adapter_spec.py` count change is out of list but needed. It will conflict with W3-A on the same line.
- Other out-of-list file: `tests/_pan_synthetic.py` (new; test helper only).

### The five axes
- **Spec:** every acceptance item is met and tested. The tests can fail: start alignment is checked against `stumpy.stump`, `PAN_` is shown to be binary, and the NaN tails are pinned. The no-structure item holds only on its chosen seed (Q7).
- **Faithful to the paper:** the normalisation is stumpy's `_normalize_pan` exactly (d/(2√m), clipped at 1), named as stumpy's. The verdict rule is the block's own and is named.
- **Correct on our data:** see F1–F4. NaN gaps are filled or counted correctly (3 s filled; a 30 min gap plus a 500 s tail counted per length). 80 % NaN gives no false suggestion. A 100 s span is "not judged", 50 s raises in words, and all-NaN raises (through `fill_nan`'s message). `recommend` gives 1028 s at 4 h; `derive` warns "9 of 12 judged".
- **Standards:** no UI imports; the core is a plain function and the adapter thin; `meta["rules"]` present; cancel and progress tested; `_estimate` uses the matrix-profile cost model. The scrump RNG lock is F5.
- **Test-first and scope:** see Q7.

### 4. What I ran
- The implementer's tests plus `test_block_standard.py`, `test_adapter_spec.py` and `test_import_boundaries.py`: **278 passed** (173 s).
- Null sweeps (`nullsweep.py`): 610 no-structure spans, each with the verdict at 1, 3 and 5 draws. The draws were computed once per span with the block's own seeds, through `P.length_verdict`; unjudged lengths were skipped because they cannot clear. Results are in `null_A/B/C.jsonl`.
- `q2.py`: plain phase against AAFT, 100 runs, with 20 draws.
- `q3.py`: 58 power spans (drop chains, sharkfins, spikes).
- `q4.py`: 16 seeds × 6 ladders.
- `q5.py`: cost, in fresh processes.
- `q6_threads.py`: the RNG race.
- `edges.py`, `edges2.py`: edge cases, flatlines, wavelet_summation, recommend and derive.
- All with `NUMBA_NUM_THREADS=4` and at most 4 workers.
- Everything is in the scratch folder `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\22c30530-4ff1-428e-9402-a0b4d395d67c\scratchpad\critic_w3c\`.

---

> Addendum filed by the manager, 2026-10-15 ~03:57: the critic sent a second, fuller copy of its report ("the handback
> slot was already used, possibly by the session that hit the 429"). The branch had not moved. Its findings agree with
> the copy above; what it adds, verbatim in substance:
>
> - **F4 (meaning):** with 3 draws the 90 s motif's suggestions were 976, 976, 171, 171, 976, 409, 409, 409, 631, 171 —
>   only 3 of 20 runs within ±1 rung of 90 s; `max_window_s` 1028 gave 1028, 150, 746, 746, 1028, 392, 1028, None, 1028,
>   284. Fix: report the band of cleared lengths **with the shortest cleared length as the event scale**; caveat on the
>   face and in `rules` that `suggested_window_s` is not the event length; W3-F must not copy it into FLUSS unqualified.
>   Keep a test with a dominant spike that asserts the shortest cleared length is within one rung of the motif.
> - **F5 (power on chains):** 8 h spans of drops every 20–60 min: on AR 0.97 at SNR 2/3/5 a suggestion in 0/5, 1/5, 2/5
>   (1508 s, 72 s); on a random walk 4–5/5, always at 30–72 s (the fall edge), never the ~30 min unit; sharkfins on AR
>   0/4, on a random walk 4/4 at 30–46 s; 60 s spikes ×10–20 in 4 h: AR SNR 3 none, SNR 5 30–111 s; random walk 46–111 s
>   and 171–264 s. Likely cause (not isolated): a spectrum-keeping null preserves a quasi-periodic chain's spacing. An
>   8 h span judges only up to 34 min: expect "no length" or an edge-scale length on the 8 h chain spans; judge chains on
>   ≥ 24 h spans, or as a picture only.
> - **Q5:** many draws under-run the estimate by ~1.4×; a ×1.3 on the draw count would centre it. The compile measured
>   47 s. A cold bridge does not mis-route runs.
> - **Q7 (tests):** at 3 draws, 2 h at 1 Hz, {random walk, AR 0.99, pink} × 30 seeds, at most 2 false suggestions in 90,
>   plus a 4 h case; it cannot flake at the measured 0/240 and fails at the one-draw rate.

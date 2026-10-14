> Filed by the manager session, 2026-10-15 — the final message of critic agent `a5f632b4352ec10f8`, resumed to
> re-critique the changed parts of W3-B's fix round 1 (`b94881b..af4a8cf`), verbatim.

## Re-critique: W3-B fix round 1 (`544ba34` red, `af4a8cf` green on `b94881b`)

**Verdict: merge after fixes.** B1 to B3 hold at the defaults on my own size and power cases. Two small should-fixes remain: a new blind spot (S-A) and a one-line change to how keys are marked (S-B). Two smaller ones (S-C, S-D) are optional.

**In plain words.** The block no longer invents shape families in pure noise when the noise looks the same everywhere. It also says "untested" when a chain fills its span, and the per-draw numbers the evaluation needs are in meta. One gap is left. The noise test compares the cycles with the recording's quiet margins. If the noise under the chain is a different "colour" from the margins, chain-timed noise is called "beyond noise" every time, and sometimes split into 2–3 families.

### Q1. Do B1–B3 hold at the defaults? Yes, with one new way to get K = 2 in noise

Size, whole block at defaults, 15 % noise, CV 0.3 timing (`exp_r2.py size`, 76 stationary runs):

| Case | K > 1 | Verdict |
|---|---|---|
| Chain-timed noise, 120 cycles: rw, AR(0.99), AR(0.95), drift (10 each) | 0/40 | — |
| Same, 400 cycles: rw regular and rw Poisson (3 each) | 0/6 | — |
| Span-filling noise (spans 50 % of each cycle): rw and drift (10 each) | 0/20 | fallback 0.32–0.61; phase null used in 4 of 10 per background; never K = 2 |

- **False passes on stationary noise:** 1/76 whole-stack false pass, on rw seed 604. It passed on eq. 17 (z 4.2, below all 20 draws) but not on σ², and the Intervals key was **unmarked** (`"1"`). See S-B.

Power (`exp_r2.py power`):
- **AR(0.98) and drift, 30 % noise, 50/50 and 80/20, with or without margins:** K = 2, ARI 0.92–1.0.
- **n = 30 at 15 %:** K = 2, ARI 1.0 on rw/AR/drift. **At 30 %:** K = 2 except rw without margins (and that AR(1) case read eq. 17 not beyond).
- **The drifting plateau (3/3) and a single shape (3/3):** K = 1.
- **10 Hz:**
  - span-filling noise gave K = 1 in 4/4; three took the phase path with block-averaging, and those were untested;
  - two shapes gave K = 2, ARI 1.0, with and without margins.

**Power lost against the shipped gate:**
- rw at 30 % noise:
  - 80/20 and 90/10 now give K = 1; the shipped gate gave K = 2 at ARI 0.74 and 0.84;
  - 50/50 gives K = 2 but ARI 0.61–0.67.
- AR(0.98) at 30 % noise, 90/10 with margins: K = 1, because ci 0.876 is below the null minimum 0.89 but not 3 SD below.

This is the price of controlling size. Name it in the docstring.

**New way to get K = 2 in noise (S-A).** Background colour that differs between the margins and the chain (`exp_r2 size` mixed case; `exp_mixed.py`).
- **Setup:** 6 h margins of AR(0.95); random walk under the chain region; no events in it.
- **Background null:** says "beyond noise" in **10/10** on eq. 17 and on σ², z 14–24. Every key is unmarked.
- **K:** 2 or 3 in 2/10. The background half of the K gate passes in 10/10 (ci 0.77–0.81 against a null minimum of 0.83–0.89). Only the mode test holds K = 1.
- **The per-cycle phase null (`phase_cycle_stacks`, pre-chord, local colour) on the same stacks:** inside, 5/5 (z −1.7 to 1.9).
- **Real-like chains (sharkfin, two shapes, plateau; AR(0.98) and rw; 15 / 30 %) against that phase null:**
  - σ² passes 9/9 (z 11–70);
  - eq. 17 fails 4 of 9 (z −2.5 to 2.4).

**Fix S-A (should-fix):**
- Compute σ² for the whole stack against `phase_cycle_stacks` (20 copies; the function exists) and report it in `whole.nulls`.
- When the stack beats the background but not this phase null, set a flag `background_colour_mismatch`, put a warning in the summary, and key the groups `~untested`.
- Optionally gate K on both nulls.
- Do not put eq. 17 against the phase null into the verdict: real chains fail it.
- State the blind spot in the docstring: "beyond the background" means "unlike the margins".

### Q2. Is 2-means on 32 PCs sound? Yes

- `two_means_ci` uses the same PCA projection for the real stack and every null stack. The index is measured in full space for both.
- Node-sized null subsets are used in the bisection.
- The real fit uses 50 starts and the null fits 10. Measured on 8 rw stacks (`exp_starts.py`), the difference is ≤ 1.4e-4 in ci, against a seed-to-seed spread of 3.6e-3. That is negligible.

### Q3. Rank-matched group nulls and the false-positive rate

- **The rank matching is a fair selection-matched null.** It runs the same K-means with the real K on each draw, aligns each null group on its own, and ranks eq. 17 and σ² separately.
- **The residual mismatch is small and conservative:**
  - the real groups come from the bisection, the Lloyd pass and passing the gate;
  - the null groups come from plain K-means.
- **The whole-stack false-positive rate is acceptable as a declared 1-in-20 test.** With 20 draws, "below every draw" alone is nominally 1/21 ≈ 4.8 %. Observed: their 1/30 plus my 1/40 stationary runs, consistent with ≤ 5 %. The 3-SD cut adds little.
- **The consequence is about one noise sequence in 25 gets an unmarked Intervals key.**

**Fix S-B (should-fix, one line):** key a group unmarked only when eq. 17 AND σ² beat the null. That is the manager's own evaluation rule. My false pass (seed 604) failed σ² and would have stayed `~noise_like`. Also add "a 1-in-20 test" to `rules`.

### Q4. Does the S1 meta have what the evaluation needs? Yes

- **Per-draw values:** `sequences[i].whole.nulls.background.eq17.values` and `.squared.values`, 20 each, paired by draw (same loop). Also `draws_dropped`, `min`, `median`, `spread`.
- **Verdict flags:** `whole.verdict.below_every_draw` and `below_every_draw_squared`, plus `tested` and `reason`.
- **Background:** `sequences[i].background.fallback_share`, `longest_free_s`, `draws`.
- **K:** `k_null` {source, draws, values, ci, reason}.
- Each group carries the same blocks, with `matched`.
- Verified: `nvals` = 20 in every tested run.
- **Caveat:** on the fallback path the `values` are random-phase cuts of the chain while `tested` is False. Read `tested` first.

### Q5. Test cost

The block's 4 files plus test_side_inputs: **89 passed, 491 s**, with 3 of my experiment processes running beside them.

The biggest items:

| Test | Time |
|---|---|
| rw 10 seeds | 65 s |
| 1,000-cycle | 61 s |
| phase null, 5 seeds | 47 s |
| ar1 two-family fixture | 39 s |
| 1 Hz / 10 Hz | 25 s |
| per-group null | 23 s |

Cuts that keep what the tests pin (no `slow` marker exists):
1. **1,000-cycle test:** drop it, or run it at `null_draws=10`. Size is pinned by the multi-seed rw test, and scale by `n_cycles == 1000`.
2. **rw multi-seed test:** 10 → 6 seeds. The shipped gate's 40–50 % failure rate is still caught with ≥ 95 % probability (0.55⁶ ≈ 3 %).
3. **Phase-null span-filling test:** 5 → 3 seeds, as the implementer offers.
4. **1 Hz / 10 Hz test:** cut the chain to 60 cycles, which still holds both shapes.

Together these save about 2–2.5 min.

### Smaller findings
- **S-C (should-fix): stale rules text.** The rules' "verdict" text still ends with "its background is a random subset, so a group's own verdict favours the group" (the diff context around line 461). That now contradicts the matched null; update it.
- **S-D (nit): partial fallback is still tested.** With 0 < fallback ≤ 0.5, up to half the pseudo-cycles are random-phase cuts of the chain and the verdict is still tested. In the span-50 % sharkfin case (fallback 0.32) it passed anyway. Fine, but `fallback_share` is the field to check in the evaluation.

### What I ran (≤ 4 processes, as asked)
- **Tests:** `pytest` on the block's 4 files plus test_side_inputs: 89 passed in 491 s.
- **`exp_r2.py size`:** 86 whole-block runs at defaults: stationary noise, span-filling noise, mixed colour, 400 cycles.
- **`exp_r2.py power`:** 42 runs: two shapes with and without margins, plateau, single shape, 10 Hz.
- **`exp_mixed.py`:** 14 runs, background null against the per-cycle phase null.
- **`exp_starts.py`:** 50 against 10 k-means starts.

All scripts are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\22c30530-4ff1-428e-9402-a0b4d395d67c\scratchpad\critic_w3b\`. Timings were taken on a loaded machine.

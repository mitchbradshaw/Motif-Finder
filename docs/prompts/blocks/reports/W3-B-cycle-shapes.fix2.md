> Filed by the manager session, 2026-10-15 — the final message of implementer agent `a7834e530174e1643`, resumed for
> fix round 2 (the last) on branch `worktree-agent-a7834e530174e1643` (`f39ff2d` red, `bc2c0b1`), verbatim.

## W3-B fix round 2 report

All five items are done and committed:
- red `f39ff2d`, tests only: 5 failed against `af4a8cf`, 138 s;
- green `bc2c0b1`.

**Tests:**
- Required set (my 4 files plus `test_side_inputs`, `test_execution`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`, `test_adapter_event_windows`): **365 passed, 7 skipped, 344 s**.
- The block's own 4 files: **77 passed, 216 s**. In round 1 they took 481 s, but on a more loaded machine, so the two times are not strictly comparable.

One new false alarm to know about: on the slow-drift background at 30 % noise, the new colour check marks a genuine two-shape chain `~untested` (2 of 2 runs). It never produces a false pass.

### 1. S-A — a background of another colour

**What changed:**
- The whole aligned stack's σ² is now also read against 20 per-cycle phase copies of its own cycles (`phase_cycle_stacks`, which keep each cycle's local colour). Only σ² is read against these copies, never eq. 17.
- If the stack beats the background null but not these copies:
  - `background_colour_mismatch` is set;
  - the warning reads "the chain's background differs in colour from the quiet margins: beyond the margins, not beyond its own noise";
  - every group is keyed `~untested`.
- The docstring now says "beyond the background" means "unlike the quiet margins".

**K is now gated on both nulls** (`K_GATE_BOTH = True`), because the measurement supported it:

| Case | Before | After |
|---|---|---|
| Mixed-colour noise (AR(0.95) margins, random walk under the chain, 10 seeds) | flagged? no; K = 2 in 5/10 | flagged 10/10; K = 1 in 10/10 |
| Real-like two shapes (random walk / AR(1) / drift; 15 and 30 % noise; with margins and span-filling) | — | K = 2 in 24/24 |
| Two shapes on mixed colour, 15 and 30 % | — | K = 2 in 6/6; not flagged; σ² beats the copies at z 17–51 |

On mixed colour the eq. 17 verdict against the margins read z 17–50 on pure noise, which is why the check is needed.

**The false alarm:** on the drift background (a 10 h sine under AR(0.95)) at 30 % noise, a real two-shape chain did not beat the copies (z 0.2 and 1.2, 2 of 2). Its groups are keyed `~untested`. The sine under each cycle stays in its copies. This is stated in the docstring.

### 2. S-B — the group key

`group_key()`: a key is unmarked only when the group is tested, eq. 17 **and** σ² both beat the background, and there is no colour mismatch. Otherwise it is `~noise_like`, or `~untested` when untested or mismatched.

Measured effect: AR(1) two-shape chains at 30 % noise now key some groups `~noise_like` that eq. 17 alone passed.

### 3. S-C / S-D — the verdict rule text

The verdict rule is rewritten to say:
- "a 1-in-20 test";
- "beyond the background" means unlike the quiet margins;
- the group null is matched by entropy rank (the stale "random subset" sentence is gone);
- the colour check is on σ² only;
- a partial fallback (≤ 0.5) stays tested, and `background.fallback_share` says how many pseudo-cycles were random-phase cuts.

### 4. Power given up for size

Named in the docstring with the re-critique's numbers:
- random walk at 30 % noise with 80/20 or 90/10 shape proportions → K = 1;
- AR(0.98) at 90/10 with margins → K = 1;
- 50/50 at 30 % keeps K = 2 (ARI 0.58–1.0 in my runs).

### 5. Test cost

- Random-walk multi-seed test: 10 → 6 seeds.
- Span-filling phase-null test: 5 → 3 seeds.
- 1 Hz / 10 Hz test: now on a 60-cycle chain.
- **The 1,000-cycle test is dropped**, after the red commit. Even at `null_draws=10` it took about 106 s, because the colour check adds phase copies of every cycle. Size is pinned by the multi-seed test, and round 1 measured K = 1 on that case. Both commit messages say so.
- Block files: 547 s with the 1,000-cycle test still in, 216 s without.

### New meta keys

- `whole.nulls.phase_cycles = {"squared": {median, p05, min, spread, draws, values:[20]}, "beyond_squared": bool, "rule": str}`.
- `whole.verdict`: adds `beyond_phase_cycles_squared` (bool) and `background_colour_mismatch` (bool, or None when untested).
- Each group's `coherence.verdict`: adds `background_colour_mismatch`.
- `sequences[i]`: adds `background_colour_mismatch`.
- `splits[0]`: adds `also = {null_ci_min, null_ci_median, null_draws, below_every_null}`, the phase-copy half of the K gate.
- `background_null`'s report is unchanged from round 1 (it still includes `longest_free_samples` / `longest_free_s`).

### Commits on top of `01cb8c3`

`8ac94c3`, `b94881b` (round 0); `544ba34`, `af4a8cf` (round 1); `f39ff2d`, `bc2c0b1` (round 2).

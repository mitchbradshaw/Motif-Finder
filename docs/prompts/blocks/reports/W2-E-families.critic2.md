> Filed by the manager session, 2026-10-14 15:40 — the final message of critic agent `a313e63b52f0fea0e`, resumed to
> re-critique the changed parts of W2-E fix round 1 (`4a192a9..1301a0f`), verbatim.

# Re-critique: W2-E fix round 1 (`4a192a9..1301a0f`), changed parts only

## 1. In plain words

Both earlier blockers are fixed, and I re-measured them through the block itself rather than the core.

- **Default window:** each event now gets a fixed 10-minute window starting where the detector crossed. On every synthetic two-shape recording I ran, the two shapes land in separate families. Each family's rhythm comes out within 0.4 % of the truth.
- **Pure noise:** a noise-only "family" is now always labelled in Intervals' table, either `~noise_like` or (for Ward) `~untested`. Nothing unlabelled is left to read as a real rhythm.

Two small gaps remain, neither of which makes the block say something false:
- **No overlap warning at the default length:** events closer together than 10 minutes now share windows silently, because the overlap warning only runs when the automatic length is asked for.
- **Ward's estimate refusal:** it never reaches the researcher in words. The Analyse chip shows "uncalibrated" instead.

## 2. Verdict

**merge**. The two items below are should-fix follow-ups and can be done after the merge.

## 3. Findings

### Should-fix 1: the overlap check runs only for the auto length
- **Where:** `Working/Catalogue/shape_families.py`, `auto_length_warnings`; the `float(length_s) != 0.0` early return.
- **What is wrong:** at the new default of 600 s, a chain whose events are under 600 s apart gives windows that each hold several events, and nothing is said.
- **How shown** (`overlap.py`): 350 events every 240 s at the defaults gave "2 families (sizes 175, 175) …" with `warnings: []`.
  - Here the result happened to be right, because the two shapes strictly alternate.
  - The block still never says that every window held about 2.5 events.
- **Fix:** run the `overlaps_next` check whatever the length, and keep the floor/ceiling and recovery checks auto-only.

### Should-fix 2: F7's raise is not a refusal in words
- **Where:**
  - `webui/server/chain.py:187-191`: `estimate` catches the exception into `errors[i]` and marks the step `unknown`.
  - `route_local` (`:249-266`): does not return `errors`, so the words are dropped.
  - Analyse (`ChainPage.tsx:246-259`): shows "unknown cost · 04 uncalibrated".
- **Traced:** POST `/api/runs` routes `unknown`, which runs the chain.
  - If the real event count is ≤ 5,000, the run succeeds. The estimate's raise was a false alarm, because it is based on the assumed one-event-per-300-s count, which trips past roughly 417 h.
  - If the real count is > 5,000, the run raises the core's ValueError ("ward builds a square distance matrix … Use hdbscan"), which reaches the job's error card in words.
- **Is it loud?** The refusal that matters (the run) is loud. The estimate's words are not shown, and the label "uncalibrated" is wrong.
- **Fix, either:**
  - have Ward's `_estimate` return its number and leave the refusal to the run, which sees the real count; or
  - surface `estimate.errors[i]` in the chip in place of "uncalibrated" (a W2-F / bridge change).

### Nit: `coherent_beyond_noise` was renamed `svd_entropy_beyond_noise`
- My old scratch script failed on the missing key. Anything already reading the old name (W2-F) must switch; the fixer's report lists the new names.

### Checked and fine
- **F1, through the block at its new defaults** (no anchor or length passed; `defaults2.py`): the real chain, 48 h; shark+square, drop+square, drop+shark × AR(1) 0.97, AR(1) 0.99, random walk.
  - SNR 40: 9 of 9 runs gave both shapes distinct, unmarked keys, medians within 0.7 %, ARI 1.00.
  - SNR 10: 9 of 9 likewise, medians within 0.4 %, ARI 0.56–1.00. The lower ARIs come from members falling into −1, not from mixing.
  - The template sets `length_s: 600` and its test checks the keys.
- **F2, through the block** (`nostruct2.py`): defaults, n = 200 and 1,000 × AR(1) 0.97 / 0.99 / random walk × hdbscan and ward × 2 seeds, 24 runs. **Not one unmarked Intervals key.**
  - HDBSCAN placed up to 73 % of the random-walk events, every family `~noise_like`; `fraction_confident` was 0.
  - Ward found 1–17 families on the random walk, all `~untested`; `fraction_confident` None.
  - `svd_entropy_beyond_noise` was False for every noise family (it was True in 37 of 46 before).
  - `method="kshape"` is refused by `validate_params` with the choices listed.
  - HDBSCAN with `null_draws=0` keys `<n>~untested`.
- **F2 semantics** (`probe2.py`):
  - `FamilyInfo.confident` is False if noise-like; None if untested or the null is untrusted; True otherwise.
  - k-Shape in `catalogue.shape_families` gives `confident` None, `n_confident` None, and the summary says "kshape's noise null is not trusted: no family is called confident".
  - A mixed HDBSCAN set of two real shapes plus 200 random-walk windows gave two confident families and `n_conf` 100, which is correct.
  - `was_tested` requires both `tested` and `null_trusted`.
  - Ward with no families gives `n_confident` 0 rather than None. This is harmless.
- **Rule text:** `COHERENCE_RULE.format(L, aligned)` renders with no stray braces for hdbscan, ward and kshape. With `resample_length=128` it reads "128 samples", matching the per-family `svd_entropy_rule`.
- **F6:** `ew.omitted_rows` is built per row with no cap (`event_windows.py:285-296`).
  - In a mixed case of 3 past_start, 2 past_end and 10 too_much_nan, the column counts, `meta.omitted` and the summary ("15 of 122 event(s) without a window (past_start 3, too_much_nan 10, past_end 2)") all agree.
- **F8:** the bounds are in place.
- **Test-first:** red `435cf0e` touches only `tests/`.
- **Nothing broken:** the trains / `write_group` path is unchanged.

## 4. What I ran
The machine was loaded, so timings are indicative only.

- `pytest -n 4` on the four W2-E test files, plus `test_adapter_trains`, `test_block_standard`, `test_adapter_spec` and `test_import_boundaries`: **323 passed** in 22 s.
- `defaults2.py`: 18 chain runs through `execute_recipe` at the block's defaults.
- `nostruct2.py`: 24 no-structure runs, then Intervals.
- `probe2.py`: rule rendering, confident semantics and the omission bookkeeping.
- `overlap.py`: dense events at the 600 s default.
- Read the bridge path: `chain.estimate` / `route_local`, `app.py` POST `/api/runs` and `/api/chain` preview, and `ChainPage.tsx`'s estimate chip.

The worktree's `git status` is clean. Scratch files are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\9b41764a-ced2-4e05-857c-547103bce7fb\scratchpad\critic_w2e`.

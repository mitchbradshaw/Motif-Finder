> Filed by the manager session, 2026-10-14 09:42 — the final message of implementer agent `acd4686fda90646ab`,
> resumed for fix round 1 against `W2-D-snippets.critic.md`, verbatim.

## W2-D fix round 1: report

All nine critic items are fixed. The gate (the three snippets files plus block_standard, adapter_spec, import_boundaries, templates and end_to_end) is green: **294 passed**. I did not touch `Working/block_cost.py`, `detrend.py`, `docs/` or main.

### In plain words
The block's "how many kinds of behaviour?" rule no longer uses a fixed bar. It now asks whether the k-th snippet stood out from the ones that came after it on this recording's own curve. That rule is exactly the "high jump" problem the critic described.

**One change from your decision.** c = 3 alone is not safe on long spans:
- On noise, the knee-to-tail ratio grows about as √(number of pieces). The largest ratio over 20–30 seeds of a detrended random walk was 1.7, 2.3, 3.9, 4.4 and 5.8 at 12, 24, 48, 72 and 120 pieces.
- With c = 3, 6 of 30 random walks at 48 h came out as k = 2, and most at 120 h would too.
- So the cut is **c = max(3, 0.65·√W)** for W pieces: 3 up to 21 pieces, 4.5 at 48, 5.5 at 72, 7.1 at 120. c = 3 survives as the floor.
- The real regimes I measured clear it: 6.8–7.4 for three regimes over 48 pieces, 8.6–15 for 8–12 h in 72–96 h, and 8.1–14 for 8–12 h in 120 h.
- **The margin is thin at 120 pieces:** an 8 h regime scored 8.1 against a cut of 7.1.
- Both constants are labelled placeholders for the surrogate check.
- At 12 pieces the rule held: 0 of 30 nulls gave k > 1 (random walk, AR(1) φ 0.999 and pink noise), so I added no refusal.

### Red → green pairs
1. **`54c88da` (tests only, red): 17 failed, 46 passed.**
   - The 8 no-structure tests failed on the missing `knee_ratio`.
   - Tail-relative knee unit test, constant-signal reason, the 12 h random-walk null (k = 2), the 72/8 and 120/12 minority regimes (k = 1), memory peak, the summary's relabel count, the runs_by_k rule, and the template description all failed.
2. **`a2c1bee` (fix, green): 294 passed.**
   - One assertion in it was corrected: the no-structure test now compares against the √W threshold. A raw 48 h random walk reached 4.18, which is above 3 and below 4.5.
   - It adds `test_long_noise_needs_the_cut_to_grow_with_the_pieces[101, 104]`. I verified it red with c = 3 alone (`KNEE_TAIL_PER_SQRT_PIECE = 0`): 2 failed, knee ratios 3.4× and 3.1× against "needs 3.0×". This is recorded in the commit body.

### What changed
- **Knee** (`Working/Detection/matrix_profiling/snippets.py`):
  - `knee_detail` now selects the largest drop and accepts it only if `change_k ≥ c · median(change_{k+1}…change_{k_max+1})`; otherwise k = 1, said in words.
  - `meta` now carries `knee_candidate`, `knee_ratio` and `knee_threshold`.
  - The docstring names the paper's rule (§III.B: k = argmax change_k, no k = 1, which gives k = 2 on the three-regime set) and both of this block's adaptations, with their measurements. The "without a formula" sentence is gone.
- **Constant signal** now reports "constant signal: every distance is 0…".
- **Memory:**
  - The greedy step works row by row on D: no copy and no rows × positions temporary.
  - `memory_peak` counts the profiles, the first-row dot products (same size) and the kernel's blocks.
  - The refusal uses `MEMORY_LIMIT = 4 GB`. Computed peaks: about 1.8 GB at 72 h and 3.0 GB at 7 days (1-hour pieces, 1 Hz); you measured 1.95 GB at 72 h.
- **Tests added:**
  - 12 h and 24 h nulls at the template's scale (6 h detrend; random walk, AR(1) τ = 1000 s, i.e. φ 0.999 at 1 Hz; pink noise; 4 seeds each) give k = 1.
  - 8 h in 72 h and 12 h in 120 h give k = 2.
  - Three regimes still give k = 3, now also asserting `n_exemplar_relabelled == 0`.
  - Pure-quiet AR(1) is pinned as an expected limitation (k ≤ 2).
- **Adapter** (`Adapters/catalogue_snippets.py`):
  - The summary shows "N exemplar window(s) relabelled" when N > 0.
  - The run-length rule says runs_by_k skips the override.
  - The knee rule text is updated; the description says to trust automatic k from 24 pieces and that amplitude-only differences are not separated.

### The template, verbatim as it now stands
```python
TEMPLATE = {
    "name": "recording_snippets", "kind": "training", "version": 1,
    "description": "What kinds of behaviour does this recording hold, and where? Baseline removal (6 h rolling "
                   "mean) → 1-hour pieces → snippets (Imani et al. 2018, matrix profile XIII): the few most "
                   "typical pieces, and every hour coloured by the one it most resembles. k is chosen by the "
                   "paper's knee; k = 1 means no evidence of more than one kind of behaviour. Read the regime "
                   "run lengths beside the labels: a label that flickers hour to hour is not a regime. Run it "
                   "on 24 h or more: on shorter spans the automatic k has too few pieces to judge by. Shapes "
                   "are compared after z-normalisation, so stretches that differ only in amplitude — a quiet "
                   "period of pure noise beside an active one — are not separated. Costs O(n²) — about 25 s "
                   "for 24 h at 1 Hz; refused above 7 days. Gaps: one missing sample blanks the whole "
                   "detrended trace (the rolling-mean baseline removal is a cumulative sum), and the block "
                   "then refuses an all-NaN span; no recording stored today has a gap (all 145 scanned "
                   "2026-10-14). Snippets itself fills short gaps and leaves windows more than half NaN "
                   "unlabelled (−1).",
    "steps": [
        {"stage": "preprocessing", "algorithm": "detrend",
         "params": {"mode": "rolling_mean", "window_s": 21600.0}},
        {"stage": "preprocessing", "algorithm": "sliding_windows",
         "params": {"window_s": 3600.0, "gap_s": 0.0}},
        {"stage": "catalogue", "algorithm": "snippets",
         "params": {"k": 0, "k_max": 6, "subseq_frac": 0.35, "mpdist_percentage": 0.05}},
    ],
}
```

### Smoke suggestion
Run `recording_snippets` on a span of **at least 24 h** (48 h is safer). Then:
- open the Snippets block page;
- expect `[data-testid="block-view"][data-view="grouping"][data-modifier="windowset->grouping"]`, the cluster strip, and one exemplar per label;
- set `"rule9": true`.

### For the surrogate check
Compare `runs_by_k["3"]` (or `["2"]`) on the real recording and on each of the 20 surrogates, on spans of 24 h or more. If the surrogates come out as k > 1 on long spans, `KNEE_TAIL_PER_SQRT_PIECE` is the constant to raise.

### Commits
`git log --oneline 04948e3..HEAD`
```
a2c1bee w2-d: the knee judged against its own tail; limits said on the face (fix round 1)
54c88da w2-d: tests (fix round 1) — the knee against its own tail, limits on the face
8075b8d w2-d: block_cost — an untimed warm-up before a cost model is timed
93a9279 w2-d: test — calibration warms the snippets kernel before timing it
9cadd0b w2-d: catalogue.snippets — the typical pieces of a recording (Imani et al. 2018)
7a754f0 w2-d: tests — catalogue.snippets (Imani et al. 2018) and the recording_snippets template
```

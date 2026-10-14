> Filed by the manager session, 2026-10-14 08:36 — the final message of implementer agent `acd4686fda90646ab`
> (branch `worktree-agent-acd4686fda90646ab`), verbatim.

## W2-D `catalogue.snippets`: report

### 1. In plain words
The block summarises a long recording with its few most typical pieces (an hour each, say) and colours every hour by the piece it most resembles. Think of the handful of thumbnail frames that best represent a film, with a bar underneath showing which frame each scene is closest to. It also decides how many kinds of behaviour there are, using the paper's "knee" rule. When nothing is there it says k = 1.

Results on synthetic data (48 h; 1-hour pieces; three behaviours of 8 h each, laid down twice in two different orders; a strong drift on top):
- **Three regimes (sawtooth drops, a spiky quiet baseline, a slow oscillation):** k = 3 every time, and 100 % of window labels match the true regime (seeds 0–3).
- **The 0.35 default matters.** With `subseq_frac = 1.0` (stumpy's default, i.e. plain whole-piece distance), the same recordings gave k = 2 and only 35–44 % agreement. This happened with and without drift: comparing whole pieces cannot cope with events that are not phase-aligned.
- **No structure** (AR(1) with 60 s and 10 min correlation times, a random walk, pink noise): k = 1, with "no knee" stated in words. At a fixed k = 3 the labels flicker, with runs no longer than shuffled labels would give.
- **An important finding:** pure quiet AR(1) noise, the prompt's own example of a third regime, is **not** found. Shapes are z-normalised, so pure noise has no shape of its own. Its distance to itself (9.97) was the same as its distance to the other regimes (9.85 / 9.93), so it gets absorbed. I swapped in a quiet baseline with brief spikes as the third regime. A raw-amplitude variant (stumpy's non-normalised version) did not fix pure quiet either (62–65 % agreement), so I dropped it.

### 2. Files
- **Created** `Working/Detection/matrix_profiling/snippets.py`: the core (numba MPdist kernel, greedy selection, knee, regimes, window labels, run lengths, NaN handling).
- **Created** `Adapters/catalogue_snippets.py`: WindowSet → Grouping, `page_name="Snippets"`, category `cluster`.
- **Created** `tests/_snippets_synthetic.py`: generators at 0.1 Hz. Durations are real; there are just 10× fewer samples than at 1 Hz.
- **Created** `tests/test_snippets.py`, `tests/test_adapter_snippets.py`, `tests/test_template_recording_snippets.py`.
- **Modified** `tests/test_adapter_spec.py` and `tests/test_end_to_end.py`: adapter counts 49 → 50.
- **Modified** `tests/test_block_standard.py`: only the `COSTED` entry, which my Deliver list names.
- **Modified, outside the declared list:** `Working/block_cost.py`. It is additive: an optional `warm_up` on `register_cost_model`, kept in a side table `WARM_UPS` so `MODELS` keeps its shape. Without it, numba's ~6 s kernel load was timed and the calibration predicted 7× too slow.

### 3. The algorithm as implemented
1. **NaN.** Gaps are filled with straight lines (counted in `n_nan_filled`). A piece more than 50 % NaN is never a snippet and is left out of every area. Its window is labelled −1 and counted in `n_windows_nan`.
2. **Global standardisation** of the series. This changes no distance, because every distance is z-normalised per sub-piece; it keeps the running dot products well conditioned.
3. **MPdist profiles** (paper Table II, using stumpy's rules):
   - Sub-length `s = ceil(subseq_frac·m)`.
   - For each piece against each position, the distance between every sub-piece of one and its closest sub-piece in the other, both ways; MPdist is the `kth` smallest, with `kth = min(ceil(pct·2m), 2j−1)`, where `j = m − s + 1` is the number of sub-pieces per piece.
   - Self-matches are set to 0.
   - **Deviation: the kernel is rewritten.** stumpy's version holds a `j × n` matrix per piece (1.6 GB per piece at 24 h) and took about 30 s for one piece against 10 000 samples. Mine streams columns using the matrix-profile diagonal update and holds two j-column blocks. It runs pieces in parallel under a 1.5 GB budget, and is tested equal to stumpy's `_get_all_profiles` to within 1e-6 (constant stretch, s = m, s < m).
4. **Greedy selection** (paper Table I), one pass to `k_max + 1`. It is tested to match `stumpy.snippets` in indices, areas and fractions.
5. **Knee** (the paper gives no formula, so this rule is mine): `change_k = Area_{k−1}/Area_k − 1`. The knee is the k in 2..k_max with the largest drop `change_k − change_{k+1}`, kept only if `change_k ≥ 0.25`; otherwise k = 1.
   - Why 0.25: with real regimes, change_2 and change_3 were 0.40–0.55 and change_4 at most 0.13. On the nulls the largest change_k was 0.18 (a random walk). 0.25 sits between, and is labelled a placeholder in the code.
6. **Regimes.** Each position is owned by the snippet with the lowest profile there (ties go to the earlier snippet, as in stumpy). Fractions are taken over scored positions only.
7. **Window labels (adaptation).** Position p votes for the window holding its centre `p + m//2`; the majority wins, labels 1..k. A snippet's own window always takes its label (its distance to itself is 0), so the exemplar is always one of its label's windows; overrides are counted in `n_exemplar_relabelled`. Windows with gaps or overlaps still work: pieces are cut at multiples of m and `contiguous` is set False.
8. **Run lengths**, for the manager's statistic: mean and median of runs of the same label (−1 breaks a run). Also `shuffled_mean = n / (1 + (n−1)(1 − Σp²))` and the ratio of the two, where 1 means "no more persistent than chance". `runs_by_k` gives the same at every fixed k = 1..k_max.

**Refusals, in words:** piece longer than half the span; fewer than `2·k_max` usable pieces; an all-NaN span; `k > k_max`; profiles larger than 2 GB; windows outside the span.

**Cost** (this machine, under load from the other agents; 1 Hz, m = 3600):
- **24 h: 24 s.**
- **72 h: 228 s.**
- 7 days is about 20 min by extrapolation.
- Calibrated `k = 3.2e-9` predicts 24 s and 216 s.
- `max_span_samples = 604 800` (7 days at 1 Hz).
- A 26-day channel is out of reach: its profiles alone would need about 15 GB.

### 4. Tests
- **Red commit `7a754f0`:** `test_snippets.py` fails to collect (ImportError: cannot import name 'snippets'). The rest: 9 failed, 212 passed, 11 errors (the adapter is unknown; adapter counts 49 ≠ 50; the COSTED entry is missing).
- **Second red commit `93a9279`:** the warm-up test fails with AttributeError (no `WARM_UPS`).
- **Green:** my three files plus `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates` and `test_end_to_end`: **277 passed**.

What the tests pin:
- stumpy equivalence of the profiles and of the greedy selection.
- `s` reaches the kernel (a spy), and `sub_length(200, 0.35) = 70`.
- Three drifting regimes: k = 3, ≥ 90 % agreement, long runs (mean ≥ 6, ≥ 3× shuffled).
- `subseq_frac = 1.0` is at least 0.25 worse in agreement and its knee is not 3.
- 4 nulls × 2 seeds: k = 1 with "no knee", and at k = 3 the run ratio is below 1.6.
- Exemplar is its own window and equals the snippet's start.
- Dense case (40 h of drops, 8 h of wave): k = 2.
- Windows with gaps between them.
- Knee and run-length arithmetic.
- NaN: a short gap is filled and counted; a 2-h gap gives −1 windows and the regimes are still found.
- Every refusal, in words.
- Adapter: types, bounds, meta keys, the channel-absolute offset (t₀ = 7200 s gives identical labels), the summary line.
- Template: end to end through `execute_recipe`, plus 3 more seeds through the chain.

### 5. Integration snippets
**Template** (from `tests/test_template_recording_snippets.py`, verbatim):
```python
TEMPLATE = {
    "name": "recording_snippets", "kind": "training", "version": 1,
    "description": "What kinds of behaviour does this recording hold, and where? Baseline removal (6 h rolling "
                   "mean) → 1-hour pieces → snippets (Imani et al. 2018, matrix profile XIII): the few most "
                   "typical pieces, and every hour coloured by the one it most resembles. k is chosen by the "
                   "paper's knee; k = 1 means no evidence of more than one kind of behaviour. Read the regime "
                   "run lengths beside the labels: a label that flickers hour to hour is not a regime. Costs "
                   "O(n²) — about 25 s for 24 h at 1 Hz; refused above 7 days. Check NaN gaps first: the "
                   "rolling-mean baseline removal spreads a NaN, and windows more than half NaN are left "
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
Why a 6 h detrend: it is six pieces long, so it leaves a piece's own shape alone while removing drift over half a day or more.

**Glyph** (`BY_NAME["catalogue.snippets"]`, 44 × 26):
- a grey wavy trace across the top;
- two or three short purple rectangles on it marking the snippets;
- beneath, a strip of coloured blocks (blue / green / amber runs) showing the regime bar.

**Smoke state:** run `recording_snippets` on a recording of at least 12 h. Open the Snippets block page and expect `[data-testid="block-view"][data-view="grouping"][data-modifier="windowset->grouping"]`, the cluster strip, and one exemplar per label; set `"rule9": true`.

**COSTED:** `"catalogue.snippets"`, already added.

**For W2-F (serializer):** `meta["exemplar_windows"]` maps label → window index; `meta["exemplar_rule"]` is the string. `serialize._exemplars` should prefer these over the centroid rule, because this window set has no features (only `split`), so the current code would pick each cluster's first window. Label −1 needs a name ("mostly NaN"). Worth putting on the face: `summary`, `fractions` and `run_length_vs_shuffled`.

### 6. Open questions and risks
- **The manager's null statistic breaks at k = 1.** When the knee says k = 1, every window has one label and the mean run equals the whole recording, so a surrogate choosing k = 1 can never be beaten. Compare at a **fixed k** instead: `runs_by_k["3"]["mean"]` or `["ratio"]`, or set `k = 3` by hand on both the real recording and its 20 surrogates. The ratio against shuffled labels is the cleaner measure.
- **What I'd want checked on real data:**
  - run `recording_snippets` with k = 3 forced on the known dense stretches (M2_aug rec 3, 500–530 h; rec 6, 380–460 h; L_LM_Jul_26_J, 380–480 h), each a 3–5-day span;
  - compare `runs_by_k["3"].mean` and `ratio` against 20 phase-randomised surrogates;
  - read `change_k` on real recordings to place the 0.25 floor;
  - check whether quiet stretches get absorbed (my synthetic finding);
  - check whether 1-hour pieces suit drops that recur every 20–60 min.
- **Pre-existing bug, not mine, high impact:** `Working/Preprocessing/detrend.py::_rolling_mean` uses a cumulative sum, so **one NaN turns every later sample into NaN**. I checked: one NaN at sample 100 of 1000 gave 930 NaN. Every detrend-first template (this one, `fluss_regimes`) will blank recordings that have gaps. The FLUSS docs' claim that it "spreads a NaN by about one window" is wrong.
- `numba.set_num_threads` is changed for the duration of a call and restored afterwards; two concurrent snippet runs in one process could step on each other's thread count.
- I did not touch `docs/rq_roundA/`; 00-common says not to. Snippets may bear on RQ3 and RQ6 once it is judged on real data.
- The window labels (centre vote) and the knee rule are my adaptations; both are named in the module docstring.

### 7. Commits
```
8075b8d w2-d: block_cost — an untimed warm-up before a cost model is timed
93a9279 w2-d: test — calibration warms the snippets kernel before timing it
9cadd0b w2-d: catalogue.snippets — the typical pieces of a recording (Imani et al. 2018)
7a754f0 w2-d: tests — catalogue.snippets (Imani et al. 2018) and the recording_snippets template
```
The worktree was at 3cc2f62 on arrival; I fast-forwarded it to 04948e3 before starting.

> Filed by the manager session, 2026-10-14 10:49 — the final message of critic agent `a5c440b67361d69dd`, resumed to
> re-critique the changed parts of W2-D's fix round 1 (8075b8d..a2c1bee), verbatim.

## Re-critique: W2-D `catalogue.snippets`, fix round 1 (8075b8d..a2c1bee)

### 1. In plain words
The "how many kinds of behaviour?" rule no longer uses a fixed height for the bar. It now asks: did the second snippet help clearly more than the ones after it, by a margin that grows with the recording's length? None of my roughly 1,100 noise recordings fooled it, from 12 h to 120 h. It still finds the planted extra behaviours, apart from the hardest case: an 8 h stretch in 120 h is right at the edge and is missed about one time in three. The fix is sound. The constants are placeholders that only the surrogate check on real recordings can settle.

### 2. Verdict
**Merge.** The two items below are a nit and a limitation to keep in mind; neither blocks the merge. The template still needs the detrend NaN fix from round 1, finding 3 (pre-existing code, outside this branch) before it runs on recordings with gaps.

### 3. Findings
- **Note (limitation, already documented): an 8 h regime in 120 h is found only 4 times in 6.**
  - With an 8 h wave inside drops, the ratios against a cut of 7.12 were 6.58, 9.52, 8.49, 7.84, 7.10 and 8.54. The 6.58 and 7.10 runs gave k = 1.
  - An 8 h spike regime inside drops was found 6/6, but with only 3–17 % margin (7.35–8.38).
  - Everything else was found 6/6 with a wide margin:
    - an 8 h or 12 h minority in 72 h (ratios 8.3–14.9 against a cut of 5.52);
    - a 12 h minority in 120 h (8.8–13.7 against 7.12).
  - The docstring's "thin margin at 120 pieces" is accurate. For long spans the template should tell the user to compare at a fixed k, using `runs_by_k`, which is what the manager's surrogate statistic does anyway.
- **Note: the null tail has 13–25 % headroom on the worst nulls.** The detrended random walk is consistently the hardest null. With 40 seeds the highest knee ratio against the cut was:

  | Span | Highest ratio | Cut | Headroom |
  |---|---|---|---|
  | 24 h | 2.53 | 3.18 | 26 % |
  | 48 h | 3.44 | 4.50 | 31 % |
  | 72 h | 4.89 (AR(1) φ = 0.9995: 4.40) | 5.52 | 13 % |
  | 120 h | 5.78 | 7.12 | 23 % |

  - No false k > 1 anywhere.
  - Across 20 surrogates × many recordings, an occasional k = 2 on a surrogate at 72 h is plausible. That is another reason for the manager to compare at a fixed k.
- **Nit: a NaN in the tail leaks into the reason text.**
  - Where: `snippets.py` `knee_detail`, `med = float(np.median(tail))`.
  - What happens: when later areas reach exactly 0 (a span that is mostly constant), the tail holds NaN. The ratio becomes inf and the reason reads "infx the median nan of the changes after it".
  - The decision itself is right: k = 2 for a constant stretch plus a random walk. Only the text is wrong.
  - Fix: use `np.nanmedian` (or drop non-finite values from the tail) and word the zero-area case.
- **The other changes are correct.**
  - **Greedy, row by row:** setting Q to 0 at unscored positions gives the same areas as dropping those columns. The 281 tests pass, including the stumpy-equivalence test.
  - **`memory_peak`:**
    - With 1-hour pieces it gives 1.77 GB at 72 h; I measured 1.95 GB in round 1.
    - Also with 1-hour pieces it gives 2.99 GB at 7 days.
    - With 30-min pieces at 7 days it gives 3.85 GB, still under the 4 GB limit.
    - The refusal now counts the real peak.
  - **Constant signal:** k = 1 with "constant signal: every distance is 0…". `knee_ratio` is None and `knee_threshold` is 3.18.
  - **New meta keys:** `knee_candidate`, `knee_ratio` and `knee_threshold` are also filled when k is set by hand (seen: candidate 2, ratio 2.74 at k = 3 by hand). That is useful for the surrogate comparison.
  - **Docstring:** it now states the paper's rule (k = argmax change_k, no k = 1 outcome) and names both adaptations with their measurements.
  - **Descriptions and the summary line:** they say "trust auto k from 24 pieces", state the amplitude-only limit, and show a non-zero exemplar relabel count.

### 4. What I ran
- **Tests:** the three snippets test files plus `test_block_standard` and `test_adapter_spec` gave **281 passed** (184 s, machine loaded). The red commit 54c88da touches only tests, and its message carries the failure summary.
- **Null sweep at 0.1 Hz with real durations** (`knee2.py`: 6 h rolling-mean detrend, 1 h pieces, k = 0). The nulls were a detrended random walk, AR(1) φ = 0.99 / 0.999 / 0.9995 (taken at 1 Hz), pink noise, and AR(1) on a drift. False k > 1 in every case:

  | Span | Runs | False k > 1 |
  |---|---|---|
  | 12 h | 240 (40 seeds each) | 0 |
  | 24 h | 240 | 0 |
  | 48 h | 240 | 0 |
  | 72 h | 240 | 0 |
  | 120 h | 131 (random walk 40, AR 0.99 40, AR 0.999 40, AR 0.9995 11) | 0 |

  I stopped the 120 h pink and drift runs for time.
- **Null sweep at real scale, 1 Hz:**

  | Span | Runs | False k > 1 | Highest ratio / cut |
  |---|---|---|---|
  | 12 h | 60 (10 seeds × 6 nulls) | 0 | 1.57 / 3.0 |
  | 24 h | 30 (5 seeds × 6 nulls) | 0 | 2.39 / 3.18 |
  | 48 h | 4 (random walk and AR(1) 0.99, 2 seeds each) | 0 | 2.51 / 4.50 |

  - The machine was heavily loaded: a 48 h run took about 5 min. I stopped the 72 h and 120 h runs at 1 Hz.
  - In round 1 and here, the 1 Hz ratios were at or below the 0.1 Hz proxies at the same span. The proxy tail is therefore the conservative evidence.
- **Planted regimes** (`minority2.py`, 0.1 Hz, detrended):
  - Minorities: 6 seeds for each case above.
  - Three-regime set at 48 h: 8/8 seeds k = 3 with 100 % agreement, both raw (ratios 5.3–6.3) and detrended (6.3–7.4), against a cut of 4.5.
  - Three regimes of 4 h each (24 h): 4/4 k = 3, ratios 3.7–4.4 against 3.18.
  - Three regimes of 20 h each (120 h): 4/4 k = 3, ratios 10.9–13.4 against 7.12.
- **Edge script:** the constant signal, the mostly-constant case, `memory_peak` at 72 h and 7 days, and the meta at a hand-set k.

Scripts are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\9b41764a-ced2-4e05-857c-547103bce7fb\scratchpad\critic_w2d\` (`knee2.py`, `summ2.py`, `minority2.py`; data in `p_*.jsonl`, `f1_*.jsonl`). I edited nothing in the repo or the worktree, nothing touched `DATA/`, and all background jobs are stopped.

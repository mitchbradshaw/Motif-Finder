> Filed by the manager session, 2026-10-14 09:29 — the final message of critic agent `a4e5da8e050cafbf5` on branch
> `worktree-agent-ab19ca872abbd930c` (2d64d54, ad160b4), verbatim.

# Critic report: W2-B (`sbd`, `kshape`, `hdbscan`, `svd_entropy`, family coherence)

Branch `worktree-agent-ab19ca872abbd930c`, commits `2d64d54` (red, tests only) and `ad160b4`, base `04948e3`. I edited nothing. My scripts are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\9b41764a-ced2-4e05-857c-547103bce7fb\scratchpad\critic_w2b\` (e1–e7).

## 1. In plain words

The arithmetic is sound:
- The shape distance is computed correctly.
- The home-made k-Shape gives exactly what aeon's k-Shape gives, 15–50× faster.
- HDBSCAN is called the way the docs say.

The problem is what the Library would show when there is nothing to find. It is like a sorting machine that always fills its bins:
- On windows of pure coloured noise, HDBSCAN always reports two families of 40–390 members, and k-Shape always reports k families and leaves nothing out.
- The only warning (an "unstable" flag on HDBSCAN families) is dropped before it reaches the editor or the Library.
- The flag is not reliable anyway: it can mark a real family unstable and score a noise crowd almost as well.

The coherence number follows the paper faithfully. But at realistic noise it cannot tell a pure family from a mixture, and sometimes ranks the mixture as purer.

## 2. Verdict

**Merge after fixes.** The "no structure" blocker must be fixed first: findings 1 and 2, with 3 and 4 alongside.

## 3. Findings, most severe first

**1. Blocker: the noise warning never reaches the editor or the Library.**
- Where: `Working/library/grouping/engine.py:117-128` (`GroupingResult`), `run_grouping` :280-302, `webui/server/library.py` `run_grouping_job` / `save_grouping`.
- What is wrong:
  - `payload["unstable_families"]`, `k_rule`, `k_scores` and `fit_summary` (which rows were fitted and which assigned) all stay on the `FitResult`.
  - `GroupingResult` has no field for them, and its attributes are only `assignments, basis, families, merge_heights, method, params, recipe_hash, unit`.
  - So the preview, the job result and the saved grouping show noise families as ordinary families.
- How I showed it (e2): `run_grouping` on 600 pure AR(1) φ=0.99 windows:
  - hdbscan: 2 families, 419 omitted, labels `F-01`, `F-02`, no flag.
  - kshape (k=6): 6 families, 0 omitted.
- The acceptance item "says the families it found are unstable" holds only inside `fit.payload`, which is the only place the test looks (`test_hdbscan_on_pure_noise_finds_no_confident_family` reads `fit.payload["unstable_families"]`).
- Fix:
  - Add a `fit_summary` dict on `GroupingResult` and a per-`Family` `flags` (e.g. `{"unstable": bool, "noise_like": bool, "why": str}`).
  - Fill them from the method in `run_grouping`.
  - Return them in the regroup job's result and the preview panel.
  - Persist them on save. The params are already stored; the summary needs an additive `groupings.fit_summary_json` column, which is the manager's call.
  - W2-F then draws an amber "no better than noise" badge on the atlas tile and the Family page.
  - Add an end-to-end test: `run_grouping(pure_noise)` exposes the flag.

**2. Blocker: the flag and the default omission rule do not separate families from noise.**
- Where: `hdbscan.py:94` (`UNSTABLE_SEPARATION = 3.0`), `_stability` :124-140; `kshape.py:109` (`DEFAULT_OMIT_D = 0.50`).
- HDBSCAN on pure noise always finds two families, at every size I tried. Separations (e2):

| Pure-noise background | n | Separation range |
|---|---|---|
| AR(1) φ=0.99 | 1,500 | 2.29–2.86 |
| random walk | 600–1,500 | 1.8–2.03 |
| drift | 600–1,500 | 1.87–2.02 |
| AR(1) φ=0.95 | 600–1,500 | 1.72–2.52 |

- Phase-randomised surrogates of 900 event windows with `min_cluster_size=5` gave one noise family at **3.09**, which counts as "confident". It has 9 members, so the engine's 10-member floor happens to drop it.
- The other way round (e4): a real family on a random-walk background at 10 % noise separated at **2.47** and was flagged unstable.
- So the real-family range (2.47 and up) overlaps the noise range (up to 3.09). The ratio's "between" term also takes the median over every outside row, so it depends on how many other families and noise rows exist, not only on the family itself.
- k-Shape:
  - Normalised SBD rarely goes above about 0.45 (two white-noise windows: median 0.423). So `omit_d` 0.5, copied from Ward's scale, almost never fires: 0 omitted on every run I made.
  - Coloured noise sits *closer* to a centroid than noisy real members do (e4, AR(1) φ=0.99 at 0.5 noise: events p50/p90 0.103/0.210, noise p10/p50 0.076/0.147).
  - **No fixed `omit_d` can work.** The implementer's suggested 0.10–0.15 would drop many real members at noise ≥ 0.3 and keep most coloured noise.
- Fix (defensible, colour-aware, the wave-1 lesson): a **surrogate null**.
  1. Make phase-randomised surrogates of the fitted members (each window's amplitude spectrum kept, so the colour is kept; 3–5 draws, seeded, optionally on a 1,000-row subsample).
  2. HDBSCAN: run the same fit on each draw. A family is confident only if its separation and its size exceed the maxima seen across the surrogate draws. Record the null in the fit summary. Cost is about 3–5× a fit (≈15 s each at 3,603 here).
  3. k-Shape: per family, take the surrogates' normalised SBD to that family's centroid. Default `omit_d = "auto"` = the null's 5th percentile, omitting as `past_cut`. Flag the family `noise_like` when its median member distance is not below that value.
  4. If a fixed fallback stays, its help text must say "0.5 ≈ never omits on the SBD scale".

**3. Should-fix: the cost estimate is method-blind, and it arrives after the run.**
- Where: `engine.py:359-375` `_recompute_cost(n, basis)`; `library.py` `run_grouping_job`.
- What is wrong:
  - `preview()` runs the whole grouping and only then attaches `recompute`. So the editor's "local or cluster" decision comes after the bridge has already run the job.
  - The estimate is n² × 2 µs whatever the method.
- How I showed it (e4, loaded machine), n = 1,500:

| Method | Actual | Estimated |
|---|---|---|
| hdbscan | 3.8 s | 3.0 s |
| kshape k=6, `n_init` 3 | 21.5 s | 3.0 s |
| ward | 0.7 s | 3.0 s |

- One k-Shape start on 2,000 rows (e5): 7.9 s at k=3, 4.1 s at k=6, 34.3 s at k=12. The implementer's suggested constant (0.6 s per k per start) is wrong by about 10×. It also contradicts their own measured 1,115 s for 110 starts (≈10 s each).
- Fix:
  - Add `estimate(n, params) -> seconds` to the method protocol. `_recompute_cost(n, basis, method, params)` calls it.
  - kshape: Σ over k of `k × n_init × min(n, 2000) × c`, plus the refit at `min(n, sample)`, with c ≈ 1.5e-3 s per row·centre·start measured here (auto k: Σk = 77, so ≈ 77 × 10 × 2000 × 1.5e-3 ≈ 38 min, i.e. cluster).
  - hdbscan: `min(n, 5000)² × ~1.2e-6` (2,000² SBD took 4.9 s) plus the assignment.
  - Estimate **before** starting the job in `run_grouping_job`. Over `LOCAL_LIMIT_SECONDS`, return 422 and write a SLURM job, as `8ee3cd4` does for Analyse.
  - Change kshape's default `k` from 0 to an explicit value. Auto k is the slow path, and it picked 2 on the three-family set.
  - Also: the regroup job checks cancel only between steps, so a k-Shape run cannot be stopped mid-run.

**4. Should-fix: one or two stragglers decide the alignment window for the whole family in `svd_entropy`.**
- Where: `Working/library/coherence.py:89-107` `_align_to`.
- What is wrong: the window every row keeps is set by the largest shifts of any single member.
- How I showed it (e6), 60 aligned drops (score 0.389, 80 % of the length kept):

| Noise members added | Length kept | Score |
|---|---|---|
| 2 | 62 % | 0.398 |
| 3 (5 % of the family) | under half, so it falls back to zero-padded rows | **0.552** |

- So the jump comes from the alignment rule, not from the shapes.
- Fix: pad each shifted row with its own edge value (replicate) instead of zeros. That removes the artificial step k-Shape's zero padding causes, with no cut. Or cut to the span 95 % of rows cover and count the rest as `misaligned`.

**5. Should-fix: the default coherence score cannot be trusted at realistic noise. Decide what the page claims.**
- Where: `coherence.py`, default `squared=False`.
- Eq. 17 fidelity is correct: the primary-sources file §2 step 4 says "Shannon entropy of the normalised singular values", and the code uses unsquared σ.
- The cost of that (e3, normalised score, drop vs drop/square 50/50, P = 10/40/200/1000):

| Noise | Pure family | 50/50 mixture |
|---|---|---|
| 2 % | 0.38–0.43 | 0.38–0.59 |
| 5 % | 0.59–0.63 | 0.50–0.63 (**the mixture often scores lower**) |
| 10 % | 0.69–0.76 | 0.65–0.82 |

- A "family" of pure AR(1) noise scores 0.79–0.86.
- The squared variant separates pure from mixture up to 10 % noise (e.g. 0.16 vs 0.24 at P=200), and inverts at 30 %.
- So the default is a faithful number, not a defensible coherence claim on our data.
- Fix:
  - Keep eq. 17 for fidelity, but return a null beside it: the same score on phase-randomised surrogates of the members ("noise like these members' would score X"). Also return `top_share`, either squared (share of variance carried by the main shape) or unsquared, labelled.
  - The Family page should say, beside the number: "how much the members are copies of one shape; near 0 = copies; *noise of this kind scores X*; not comparable between families of different noise levels."
  - Squared or unsquared as the headline is the researcher's decision. Put it to them plain-language first.

**6. Should-fix: the HDBSCAN cut parameter means something different from Ward's cut, though it shares the slider's name.**
- Where: `hdbscan.py` params `cut`.
- `cut` here is `cluster_selection_epsilon`. On three families plus noise (e7), cut 0.0 gives 3 families; 0.1–0.6 all give 2.
- If W2-F wires the editor's cut slider (default 0.42) into it, families merge silently.
- Also, `test_hdbscan_cut_selection_and_distance_are_honoured` asserts `merged <= base`, which an implementation that ignores `cut` would pass.
- Fix: rename it `epsilon` (or tell W2-F explicitly), and assert a strict decrease in the test.

**7. Nit: bridge `_family_coherence` (`webui/server/library.py:1279-1326`).**
- Correct as written: medoid index, spans, `notOnDisk`. An error is returned as `{"error", "rule"}`, logged, and not cached. Tested, and the rest of the page still renders.
- Smaller points:
  - The cache key `(rid, start, end, is_medoid)` has no file mtime. After a channel is re-derived (`rederive_channels.py`), the old value is served until restart. Add `st_mtime_ns` of `npy_path` to the key.
  - Members on held-out recordings are silently left out and not counted. Count them, as `notOnDisk` does.
  - When no medoid is among the shown rows, the medoid search is P² SBD. At 2,000 members that is 10.0 s inside a GET, versus 0.5 s with the medoid named. Fall back to the exemplar, or the row of least stored `distance`.
  - The `reason` path (fewer than two members gives values None) must be drawn by W2-F as text, not as a blank.
  - The cache test compares two equal dicts, which passes without a cache. Assert identity or count the calls.

**8. Nit: a stale test docstring.** `tests/test_sbd.py:17` says a negative scores "~2 (~1 on the methods' /2 scale)". The test body (:90-106) correctly asserts the opposite.

**Manager's question 3 (SBD of a shape against its negative), verified.**
- SBD(x, −x) = 1 + min over shifts of x's own normalised autocorrelation.
- For a one-signed pulse that minimum is about 0, so the normalised score is 0.5. For a z-normalised shape it is negative, so the score is below 0.5.
- Measured, normalised SBD (e3):

| Pair | Score |
|---|---|
| drop vs −drop | 0.371 |
| square vs −square | 0.394 |
| sharkfin vs −sharkfin | 0.279 |
| 2-cycle sine vs its negative | 0.125 |
| drop vs square | 0.370 |
| two AR(1) φ=0.99 windows (median) | 0.27 |

- So a drop's mirror image (a fast-rise, slow-decay spike) is as close to a drop as a square pulse is, and further than two noise windows are from each other.
- Consequence: no `omit_d` keeps spikes out of a drop family. They separate only if k is large enough (or HDBSCAN finds them as distinct crowds), because k-Shape's centroid keeps its sign. The real-data check the implementer asks for (do drops and spikes share families on the 3,603?) is needed before the Library offers k-Shape.

**Checked and fine:**
- **Spec, faithfulness, test-first:**
  - k-Shape equivalence holds on inputs the tests did not use (e1): coloured families at L=128 (k=3, 5), random walk at L=96 (k=2, 6), exact duplicate rows (ties) at L=64, odd length L=77. Labels identical, centres within 7e-15, inertia and iteration counts identical. Speed-up 15–50× (aeon 0.1–3.1 s against ours 0.01–0.09 s).
  - The aeon BSD-3 and kshape-python MIT notices are kept.
  - The HDBSCAN −1/−2/−3 mapping is correct.
  - The first commit touches only `tests/`, and its message shows the failures.
  - Scope is respected: the engine change is the omission reasons only, and `library.py` only adds `_family_coherence` beside `_family_detail`.
- **Recorded, not fixed:** `docs/rq_roundA/RQ1` and `LIBRARY_STORAGE.md` §6 (which still says five reasons) were not updated. 00-common forbids it, so the implementer recorded it. The manager should integrate.
- **Real data:** HDBSCAN omits most real events at moderate noise (AR(1) φ=0.99 at 0.3: 76 % of events omitted; random walk at 0.3: 81 %). Measure on the real 3,603 before making it a default.

## 4. What I ran

- **Branch tests (conda, from inside the worktree):** `test_sbd`, `test_library_coherence`, `test_library_grouping_methods`, `test_library_grouping`, `test_distances`, `test_import_boundaries`: **141 passed**, 4 sklearn DeprecationWarnings, 50 s.
- **Family-detail tests, with `webui\.venv\Scripts\python.exe -m pytest tests/test_webui_library.py -q -p no:cacheprovider`:** **46 passed, 3 xpassed**, 93 s. Both new coherence tests pass.
- **e1:** aeon `KShape` against `kshape_fit` on 6 new configurations. All identical (figures in "Checked and fine").
- **e2:** HDBSCAN on pure noise at n=600 and 1,500 × 4 colours × 2 seeds: always 2 families. Phase-randomised surrogates: separation up to 3.09. k-Shape on pure noise: 0 omitted. `run_grouping` exposes no flag.
- **e3:** SBD against negatives, noise pairs; `svd_entropy` against noise level and family size; squared against unsquared; 2,000-member timing (10.0 s without a medoid, 0.5 s with one).
- **e4:** separation and k-Shape distances on three families plus 25 % noise at noise 0.1/0.3/0.5; cost estimate against actual.
- **e5:** k-Shape one start on 2,000 rows: 7.9 / 4.1 / 34.3 s at k = 3/6/12. SBD 2,000² float32: 4.9 s. HDBSCAN fit at 3,603: 14.7 s.
- **e6:** stragglers against the alignment overlap. **e7:** HDBSCAN `cut` against the family count.
- **Timing caveat:** the machine was loaded (other agents and a smoke run), so absolute times read slow. The ratios (estimate against actual, aeon against ours) are the meaningful figures.

# Report — fixup-dsax-seed: one recipe, one string of letters

Run 2026-10-03 in worktree `quirky-hofstadter-ada13a` (base `ba82880`), from the finding in `Z`'s report §6
(`Z-band-scope-and-compare-by-verdict.md`, uncommitted in the main checkout when this ran). Commit prefix
`fixup-dsax-seed:`. The first commit, `daf94e4`, touches only `tests/` (`tests/test_sax_determinism.py`) and failed 6
of its 7 tests on arrival. The seventh, *no seed parameter on the adapters*, passed on arrival on purpose: it pins the
decision in §2, not a change. No bridge was started. No database or step cache was written. The real-data numbers in
§3 come from adapters called directly, in-process, on a channel file opened read-only.

**In plain words, first.** The symbolic encoder (dSAX) turns a signal into letters: *up*, *flat*, *down*. Before it can
do that, it has to decide where *flat* ends and *up* begins. It finds those boundaries with a small clustering step.
That step starts from a random first guess, like dropping a few pins on a map before you start sorting the points.
Nothing fixed that guess. Usually it made no difference, but sometimes it moved a boundary, and then the same recipe
found a different number of regions:
- Z measured 11 · 11 · 13 · 11 on one channel;
- the step cache then kept whichever answer happened to come first.

Now the first guess comes from a fixed, private source of randomness: the same pins are dropped every time, and nothing
else in the program is disturbed. **Same recipe, same letters, same regions.**

---

## 1. What was built

- `Working/Detection/sax/psax_python/kmeanspp.py`:
  - `kmeanspp(X, k, random_state=KMEANSPP_SEED)` takes its two random draws from a **local** generator;
  - `KMEANSPP_SEED = 0`;
  - `as_rng` passes a `Generator` or `RandomState` through, and seeds a new `Generator` from an int (or from `None`,
    for an explicit opt-in to a fresh draw).
  - It **neither consumes nor reseeds** the global `np.random`.
- `lloydmax.py` threads `random_state` into its own `kmeanspp` call and into its fallback draw. Neither runs on the
  pSAX/dSAX paths, which always pass `init`.
- `psax()`, `psax_overlap()` and `dsax()` (through `_learned_cutlines`) take `random_state=KMEANSPP_SEED` and pass it on.
  Neither adapter passes anything, so both get the constant.
- Docs that told callers to "seed `np.random` yourself" now describe what the code does:
  - `dsax.py`'s *Determinism* section and the comment above the post-hoc helpers;
  - `IMPLEMENTATION_NOTES.md` limitation 6;
  - the module docstrings of `tests/test_dsax.py` and `tests/test_sax_details.py`.

  Those test files still reseed `np.random` before each call. That is now redundant but harmless, and cSAX still needs
  it (§4).

`tests/test_sax_determinism.py` pins the contract on a noisy sharkfin train. Before the fix, eight global seeds gave
3 different dSAX strings and 2 different `c+a+` span sets on that train, and 11 different pSAX strings. The tests:
- learned dSAX → `symbol_search` gives **one** string and **one** span set across 8 global seeds;
- the cutlines are identical across two calls;
- pSAX, called directly and through its adapter, gives one string;
- `kmeanspp`, `dsax` and `psax` leave `np.random.get_state()` exactly as they found it;
- an explicit `random_state` (int or Generator) is honoured;
- neither SAX adapter has a `seed` / `random_state` / `rng` param.

## 2. The decision: a fixed constant, not a new setting

**Plain words.** There were two ways to fix the starting guess:
- **A fixed number written inside the code** — always the same pins;
- **A new knob on the block** — "seed = 0", which the researcher could change.

The difference is what it does to the recipe's fingerprint (its *hash*), the label the app uses to recognise "this is
the same experiment as before". A new knob becomes part of every saved chain, so the fingerprint of every saved dSAX or
pSAX chain would change: old and new runs of the "same" chain would stop being recognised as the same.

| Option | Upside | Downside |
|---|---|---|
| **Fixed constant** (built) | No saved chain's hash changes; nothing new to understand on the block | Existing stored runs and step-cache entries are not invalidated automatically (see §5); a seed sweep needs a script |
| **`seed` ParamSpec** | A seed sweep from the UI; changing the code's draw changes the hash, so old caches drop out by themselves | Every chain saved from Analyse lists all params, so its hash changes; a knob that is meaningless to most users sits on the block |

**Recommendation, and what was built: the constant.** A seed sweep is still one line from a script:
`dsax(..., random_state=s)` or `psax(..., random_state=s)`. If the researcher wants seed sweeps in the app, making it a
ParamSpec later is a small change, and its cost (the hash change) is the same then as now.

## 3. Measured on real data, before and after

This reproduces `Z`'s chain:
- bandpass 0.01–0.1 Hz → detrend (rolling mean, 600 s) → `sax_dsax` (20 s per symbol, k = 3, learned) →
  `symbol_search` `c+a+`;
- M2_aug_concat_fs1, 80–84 h;
- adapters called directly on `DATA/derived/channels/M2_aug_concat_fs1/CH0.npy` / `CH1.npy`, opened `mmap_mode="r"`.

"Old behaviour" is the same code with `random_state=None`, a fresh draw each time. That reproduces what an unseeded
global generator did.

| Channel | Old behaviour (8 runs) | Fixed (4 runs) |
|---|---|---|
| CH1_A1 | 13 · 11 · 13 · 13 · 13 · 13 · 13 · 13 | **11 · 11 · 11 · 11** |
| CH2_A1 | 2 · 2 · 2 · 2 · 2 · 2 · 2 · 2 | 2 · 2 · 2 · 2 |

The same two answers Z saw (11 and 13), and CH2_A1 stable as Z found it. **The constant picks one of the possible
answers; it does not pick the right one.** 11 is no more correct than 13: both are local optima of the same Lloyd-Max
fit from different starts. What changed is that the number is now a property of the recipe, not of the run. Whether an
RQ4 count is *robust* to the start is a separate question, and a seed sweep (§2) is how to ask it.

## 4. pSAX checked — same defect, same fix; cSAX has its own

- **pSAX** (`Adapters/detection_sax_psax.py`) shares `kmeanspp`, so it had the identical defect: 11 distinct strings
  from 8 global seeds on the synthetic train. It is fixed by the same change (pinned by two tests). On real data at
  adapter defaults (80–84 h, no band), 8 runs gave **4 distinct strings on CH1_A1 and 3 on CH2_A1** with the old
  behaviour, and **1 each** fixed.
- **cSAX** (`Adapters/detection_sax_csax.py`) does not use k-means++. Its Mean-Shift picks a seed point with the global
  `np.random.rand()` (`hg_meanshift_cluster.py` ~line 83). On real CH1_A1 at adapter defaults, **8 global seeds gave 6
  distinct cSAX strings**. cSAX is in no template, but it is a selectable block. **Not fixed here** (outside the
  brief); raised as its own task, *"Seed cSAX's Mean-Shift like fixup-dsax-seed did"*.
- **Theil-Sen's subsample** (`trend_estimators.py`) is `np.linspace`, so it is deterministic.
- **The "Estimate noise floor" diagnostic** (`surrogate_same_halfwidth`, `random_state=None`) draws fresh surrogates
  each press. It is a diagnostic, not a recipe step, so it changes no stored result. But a `min_same_halfwidth` copied
  from it will differ press to press. Left as is; noted.

## 5. What this does not fix by itself: answers already stored

**Plain words.** The app remembers results in two places so it doesn't recompute them:
- a finished run, recognised by its recipe's fingerprint;
- the step cache, recognised by the fingerprint of the chain up to that step.

Because the fix deliberately leaves fingerprints alone (§2), anything computed **before** this fix is still recognised
and reused. It holds whichever random answer it happened to get, which may not be the one the code now gives.

| Option | What it means |
|---|---|
| **Re-run with *force*** the learned-dSAX / pSAX runs you are about to count (recommended) | Cheap, targeted; the new answer replaces the old one |
| Clear the step-cache entries under `STEP_CACHE_ROOT` for chains containing `sax_dsax` / `sax_psax` | Catches everything, but needs a small script; not built |
| Do nothing | Old runs keep their draw; new runs of a *new* recipe are deterministic |

**Recommendation:** before RQ4's band counts are read for the thesis, re-run them once with *force*. Every run after
that is reproducible. `Z`'s sandbox numbers (§3 of its report: 1 · 75 · 17, union 92) were drawn before this fix.

## 6. Files touched

All of them are inside the brief: the dSAX/pSAX core, its tests and docs, this report and RQ4's file.

| File | Why |
|---|---|
| `Working/Detection/sax/psax_python/kmeanspp.py` | the local generator, `KMEANSPP_SEED`, `as_rng` |
| `Working/Detection/sax/psax_python/lloydmax.py`, `psax.py`, `psax_overlap.py` | thread `random_state` |
| `Working/Detection/sax/dsax_python/dsax.py` | thread `random_state`; *Determinism* rewritten |
| `Working/Detection/sax/dsax_python/IMPLEMENTATION_NOTES.md` | limitation 6 rewritten |
| `tests/test_sax_determinism.py` (new), `tests/test_dsax.py`, `tests/test_sax_details.py` | the contract; two stale docstrings |
| `docs/rq_roundA/RQ4-bands-and-symbols.md` | one *What is known* bullet and a *Log* line |

Nothing in Discovery or Compare was touched. No adapter changed: the adapters pass no seed and get the constant.
`Experimentation/Detection experiments/multiscale_sax.py` also calls `kmeanspp`, so it now gets the constant too.

**Merge note.** `Z`'s edits to `RQ4-bands-and-symbols.md` and `fixup/README.md` were uncommitted in the main checkout
when this ran. RQ4's *What is known* and *Log* here are edited against the committed file, so expect a small text
conflict there. Keep both sides.

## 7. The gate

1. **Module tests** (conda): `test_sax_determinism`, `test_dsax`, `test_dsax_diagnostics`, `test_dsax_engineered`,
   `test_sax_adapters`, `test_sax_details`, `test_t07_adapter_remap`, `test_adapter_symbol_search`,
   `test_drop_motifs_detect`, `test_drop_motifs_detect5`: **160 passed**.
2. **`pytest -n 4`** (conda, 6 m 12 s, in the worktree): **2035 passed, 36 skipped, 1 failed**.
   - The one failure is `test_drop_motifs_nulls1.py::test_detect_kwargs_are_read_from_the_shipped_run_not_retyped`.
     It raises `FileNotFoundError` on `Plots/drop_motifs9_fig2a/run_summary.json`. That file is gitignored: it exists in
     the main checkout but is not provisioned into this worktree. The test **fails identically at the base `ba82880`**
     in a detached checkout. It is environmental, not this change.
   - The extra skips (36 against `AB`'s 20) are the same cause: this worktree has no `DATA/` beyond `library_seed`.
   - **Failure set against the baseline: empty.**
3. No `webui/` file changed, so the UI gate does not apply.

## 8. In short

- Learned dSAX and pSAX now give one answer per recipe. The k-means++ start is drawn from a private generator with a
  fixed seed, so the global `np.random` is untouched. On Z's chain, CH1_A1 reads 11 every time; it used to flip
  between 11 and 13.
- No recipe hash changed.
- Stored runs from before the fix keep their old draw: re-run RQ4's counts once with *force*.
- cSAX has the same defect in a different place (6 strings from 8 runs) and is raised as its own task.

# W2-C — `catalogue.minirocket`: a fast shape fingerprint for every window (Dempster, Schmidt & Webb 2021)

Read [`00-common.md`](00-common.md) first. Commit prefix **`w2-c:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 row 9; facts (verified in the installed code): `docs/research/analysis-blocks-primary-sources.md` §12. Round 1 of
wave 2.

## In plain words

Run every window through about ten thousand tiny fixed pattern detectors and record, for each, how often it fires.
That list of numbers is a fingerprint of the window's shape. A simple classifier can learn from fingerprints in
seconds, on a CPU, with no images. It answers one question cheaply and well: **"can this label be learned from the
raw shape at all?"** — before anyone builds a bigger network. What it cannot do is explain *why*; the features have no
meaning on their own.

## The block

`catalogue.minirocket`, **WindowSet → WindowSet** (a feature block: the same windows, with the fingerprint added to
the feature table). Core in `Working/Catalogue/minirocket.py` (beside the other catalogue cores — check), wrapping
aeon 1.4's `MiniRocket` transform (`aeon.transformations.collection.convolution_based.MiniRocket`; read its source
before you use it — §12 lists the facts that matter).

1. **Where the windows come from.** If the WindowSet has a `shape_file` column (a *Trace shape* step ran — read
   `Adapters/preprocessing_trace_shape.py`), read the vectors from that file by `shape_row` (a pool's windows sit on
   many channels; the block must never try to slice them from `x`). Otherwise slice `x` at `starts − round(t[0]·fs)`
   (channel-absolute starts; see `catalogue.window_images` for the existing slicing — import it if it is a function).
   A pool without `shape_file` is refused in words, naming Trace shape as the fix.
2. **Fit on training windows only.** MiniRocket's biases come from quantiles of a **random training case's**
   convolution output: fit on the `split == "train"` rows when a split column exists (else on all, with a warning in
   `meta` that a held-out score downstream will be optimistic), then transform every window. This is the leakage rule
   the site's Classifier already follows; say so.
3. **Params:** `n_features` (default 10,000 = the paper's; aeon rounds down to a multiple of 84 — report the real
   count), `max_dilations` (32), `seed` (0), `normalise` (default true: z-normalise each window first, so the
   fingerprint is about shape, not level — the paper's UCR data are z-normalised; say so), `max_cells`
   (default 50,000,000: windows × features above this is refused in words, naming `n_features` as the knob — a
   10,000-wide feature table for 20,000 windows is 800 MB).
4. **NaN.** aeon refuses NaN: interpolate gaps of ≤ 5 % of a window linearly and say how many windows; leave out
   windows with more (counted — a feature block may leave windows out, as Trace shape does; keep every upstream
   column on the kept ones). Windows shorter than 9 samples: refuse (aeon raises; say it in words first).
5. **Output:** upstream columns + `mr_0000 …` (float32). `meta`: `n_features`, `n_fit_windows`, `fit_on`
   (`train` | `all`), `n_left_out` by reason, `seed`, timing, and `rules`. Declare `estimate` (it is O(windows ×
   length × features)): time 1,000 windows of 600 samples and 20,000 of 600 and register a cost model
   (`Working/block_cost.py::register_cost_model`).

## The template `minirocket_manual_labels`

`TEMPLATE = {"name": "minirocket_manual_labels", "kind": ..., ...}` in `tests/test_template_minirocket_manual_labels.py`:
`preprocessing.sliding_windows` (600 s, blocked split) → `catalogue.minirocket` → `catalogue.manual_labels` →
`catalogue.classifier` (its `windows` side input bound to the MiniRocket step). Read `catalogue.manual_labels` to see
where its labels come from and give it human labels in the temporary database exactly as its own tests do. Use the
kind `kind_for_steps` implies.

**Do not change `catalogue.classifier`.** The paper pairs MiniRocket with a ridge classifier; the site's classifier is
a random forest. Adding a `model` parameter would change the recipe hash of every saved classifier run (plan §7.4).
Instead, report the holdout accuracy the forest reaches on your synthetic set **and** what aeon's
`MiniRocketClassifier` (ridge) reaches on the same split, so the manager and the researcher can decide.

## Deliver

Core, `Adapters/catalogue_minirocket.py` (`page_name="MiniRocket"`), `tests/test_minirocket.py`,
`tests/test_adapter_minirocket.py`, the template test, a `COSTED` suggestion.

## Acceptance

- [ ] Three synthetic window classes that differ only in shape (same mean and variance — e.g. a drop with slow
      recovery, a symmetric dip, a step) on AR(1) noise: the forest on MiniRocket features reaches clearly higher
      holdout accuracy than on the windows' existing Catch22 features (or say honestly that it does not).
- [ ] **No-structure check:** with labels shuffled, holdout accuracy falls to chance (within the binomial spread) — a
      fingerprint that "learns" shuffled labels means leakage. Test it.
- [ ] Fit-on-train is real: changing only the test windows does not change the train windows' features (same seed).
- [ ] Deterministic for a fixed seed; the feature count is reported as aeon really returns it.
- [ ] Pool path: a WindowSet with `shape_file` / `shape_row` is read from the file, not sliced from `x` (test with a
      tiny pool written to a temp dir, as Trace shape's tests do).
- [ ] NaN, short-window and over-`max_cells` cases refuse or leave out **in words**; never a blank.
- [ ] The template runs end to end; the block passes `tests/test_block_standard.py` and `tests/test_adapter_spec.py`.

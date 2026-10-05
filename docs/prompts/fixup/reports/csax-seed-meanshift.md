# Report — fixup-csax-seed: one cSAX recipe, one string of letters

Run 2026-10-03 in worktree `kind-edison-228a91`, commit prefix `fixup-csax-seed:`. The follow-on raised in §4 of
`dsax-seed-learned-thresholds.md`. The first commit, `90d1a11`, touches only `tests/` (`tests/test_sax_determinism.py`)
and failed 4 of its 5 new tests on arrival, each for the reason it names (3 strings where 1 was required; the global
generator moved; `csax()` had no `random_state`). The fifth, *no seed parameter on `detection.sax_csax`*, passed on
arrival on purpose: it pins the decision, not a change. No bridge was started. No database or step cache was written.
The real-data numbers in §3 come from the adapter and `csax()` called in-process on a channel file opened read-only.

**Base.** `fixup-dsax-seed` was **not merged** when this ran: it sits on `claude/quirky-hofstadter-ada13a`, three
commits directly on top of `main` (`ba82880`). This branch was fast-forwarded onto it (`bf06ca4`) so it could reuse
`as_rng` / `KMEANSPP_SEED` and extend `tests/test_sax_determinism.py` rather than write a second helper. **Merge
`quirky-hofstadter-ada13a` first, or merge this branch alone — it carries those three commits with it.**

**In plain words, first.** cSAX is the encoder that decides for itself how many letters a signal needs. It does that by
looking at the signal's values and finding the places they pile up, like finding the busiest spots in a car park by
walking uphill towards the crowd from a few starting spots. The starting spots were picked at random, and nothing fixed
them. Different starts sometimes found a different number of piles, and so a different alphabet: on one real channel,
eight runs of the same recipe gave six different strings of letters. Now the starting spots come from a fixed, private
source of randomness — the same one the dSAX fix uses — so **the same recipe gives the same letters every time**, and
nothing else in the program is disturbed.

One honest caveat goes with it: on that same channel the answer **does** depend on where you start. Fixing the start
makes the answer repeatable; it does not make it the only answer (§3).

---

## 1. What was built

- `Working/Detection/sax/csax_python/meanshift/hg_meanshift_cluster.py`: `hg_meanshift_cluster(..., random_state=
  KMEANSPP_SEED)`. Each seed point is drawn with `rng.random()` from `as_rng(random_state)` instead of the global
  `np.random.rand()`. The draw formula is otherwise unchanged.
- `Working/Detection/sax/csax_python/csax.py`: `csax(..., random_state=KMEANSPP_SEED)` builds **one** generator and
  hands it to both Mean-Shift passes (the first pass, and the narrower-bandwidth retry when it finds fewer than two
  clusters). One generator rather than one seed per call, so a caller's own `Generator` is consumed as one stream.
- Both import `KMEANSPP_SEED` and `as_rng` from `psax_python/kmeanspp.py`. No second helper, one seed constant for every
  SAX encoder.
- `tests/test_sax_details.py`: the module docstring said `csax()` consumes `np.random`. It now says neither encoder does,
  and that the `np.random.seed(...)` calls in that file are redundant leftovers, kept as harmless.

`tests/test_sax_determinism.py` gains a cSAX section on the same noisy sharkfin train. Before the fix, eight global seeds
gave **3** different cSAX strings at the adapter default (20 samples per symbol at 1 Hz) and **5** at 10 samples per
symbol. The tests:
- `csax()` at both ratios gives **one** string and **one** set of details (alphabet size, fallback flag, cutlines,
  representatives, PAA) across 8 global seeds;
- the `detection.sax_csax` adapter, at its defaults, gives one string and one set of cutlines;
- `csax()` and `hg_meanshift_cluster()` leave `np.random.get_state()` exactly as they found it;
- an explicit `random_state` (int or `Generator`) is honoured by both;
- `detection.sax_csax` has no `seed` / `random_state` / `rng` param (added to the existing dSAX/pSAX test).

## 2. The decision: the same fixed constant, no new setting

The brief settled this, for the reason `dsax-seed-learned-thresholds.md` §2 gives: a new knob on the block would change
the fingerprint (hash) of every saved chain that contains cSAX, so old and new runs of the "same" chain would stop being
recognised as the same. The adapter passes nothing and gets the constant. A seed sweep is one line from a script:
`csax(x, len(x), dim_ratio, random_state=s)`.

## 3. Measured on real data, before and after

M2_aug_concat_fs1 CH1_A1 (`DATA/derived/channels/M2_aug_concat_fs1/CH0.npy`, opened `mmap_mode="r"`), samples
288000–302400 (80–84 h), fs 1 Hz, adapter defaults (20 s per symbol → 720 symbols).

| | Distinct strings over 8 global seeds |
|---|---|
| Before (measured in the brief) | **6** |
| After, through the adapter | **1** — alphabet 4, raw cutlines −0.6442 · −0.6240 · −0.6027; `np.random` untouched every run |

**How much the answer depends on the start** — an explicit sweep, `random_state = 0…31`:

| Alphabet size | Seeds |
|---|---|
| 3 letters | 3 |
| **4 letters** | **24** |
| 5 letters | 4 |
| 6 letters | 1 |

16 distinct strings from 32 seeds. The fixed seed (0) lands on the common outcome, four letters, and the four-letter
outcomes agree on their cutlines to within about 0.001 in raw units (the span itself ranges −0.658 to −0.588, std
0.021). So the variation is mostly *how many piles Mean-Shift finds*, and secondarily small boundary shifts.

**Plain words.** Repeatable is not the same as robust. Before, you could not tell a real difference between two cSAX
results from the dice. Now you can. But on this channel cSAX's alphabet size itself is a fragile number — three times
in four it says four letters, otherwise three, five or six. Any conclusion that leans on cSAX's alphabet size, or on a
count of a cSAX pattern, should be checked with a seed sweep before it is trusted. This is the same caveat the dSAX fix
carries, and it is larger here, because Mean-Shift chooses the alphabet as well as the boundaries.

## 4. What this does not fix by itself: answers already stored

Exactly as in `dsax-seed-learned-thresholds.md` §5: the fingerprints were deliberately left alone, so a cSAX run or
step-cache entry computed before this fix is still recognised and reused, holding whichever draw it happened to get.

| Option | What it means |
|---|---|
| **Re-run with *force*** any cSAX run you are about to read (recommended) | Cheap and targeted; the new answer replaces the old |
| Clear the step-cache entries for chains containing `sax_csax` | Catches everything, needs a small script; not built |
| Do nothing | Old runs keep their draw; new recipes are deterministic |

cSAX is in no shipped template, so the exposure is any chain the researcher built by hand with it.

## 5. Other callers

- `Working/Detection/sax/sax_encoding.py`'s `make_csax_encoder` calls `csax()` without a seed, so it gets the constant.
- `Experimentation/Detection experiments/multiscale_sax.py` calls `hg_meanshift_cluster` directly and now gets the
  constant too (it already got it for `kmeanspp` from the dSAX fix).
- `csax_overlap.py` does not call Mean-Shift.

## 6. Files touched

| File | Why |
|---|---|
| `Working/Detection/sax/csax_python/meanshift/hg_meanshift_cluster.py` | local generator for the seed-point draw |
| `Working/Detection/sax/csax_python/csax.py` | thread one `random_state` through both Mean-Shift passes |
| `tests/test_sax_determinism.py` | the cSAX contract |
| `tests/test_sax_details.py` | stale docstring |
| `docs/rq_roundA/RQ4-bands-and-symbols.md` | one *What is known* sub-bullet and a *Log* line |
| this report | |

No adapter changed. Nothing under `webui/` changed, so the UI gate does not apply.

## 7. The gate

1. **Module tests** (conda): `test_sax_determinism`, `test_sax_details`, `test_sax_adapters`, `test_dsax`,
   `test_dsax_diagnostics`, `test_dsax_engineered`, `test_encoding_cache`, `test_t07_adapter_remap`,
   `test_import_boundaries`: **119 passed**.
2. **`pytest -n 4`** (conda, 10 m 39 s, in the worktree, with the implementation in place): **2039 passed, 36 skipped,
   1 failed**.
   - The one failure is `test_drop_motifs_nulls1.py::test_detect_kwargs_are_read_from_the_shipped_run_not_retyped`:
     `FileNotFoundError` on the gitignored `Plots/drop_motifs9_fig2a/run_summary.json`, which is not provisioned into
     worktrees. It is the same environmental failure `dsax-seed-learned-thresholds.md` §7 showed failing identically
     at `ba82880`. The 36 skips have the same cause (no `DATA/` beyond `library_seed`).
   - **Failure set against the baseline: empty.** 2039 passed is the dSAX ticket's 2035 plus this ticket's four new
     passing tests.
3. No `webui/` file changed, so the UI gate does not apply.

## 8. In short

- cSAX now gives one answer per recipe: Mean-Shift's starting points come from a private generator with the same fixed
  seed as dSAX/pSAX, and the global `np.random` is untouched. On CH1_A1 80–84 h: 6 strings from 8 runs before, 1 after.
- No recipe hash changed. Stored cSAX runs from before the fix keep their old draw: re-run with *force* before reading.
- cSAX's alphabet size on that channel is seed-sensitive (3–6 letters over 32 seeds, 4 in 24 of them): seed-sweep any
  finding that depends on it.
- This branch includes the unmerged `fixup-dsax-seed` commits it builds on.

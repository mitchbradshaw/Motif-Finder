# Fixup AF — window sets at three scales in the Library, and the core that combines them into a pool

**First of five for RQ1 version 2 (`AF` → `AG` → `AH`, `AI` beside `AH`, then `AJ`).** Written 2026-10-05 from the researcher's
reframing after the baseline run; nothing here is run yet.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` ("New scope, version 2" and "The baseline result"),
`docs/prompts/fixup/reports/AB-models-paired-job.md` §2 (what `Working/training/` already does) and
`reports/AA-manual-labels-and-window-sets.md`.

Commit prefix `fixup-af:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only. The
held-out recording (`M4_aug_concat_fs1.mat`) stays locked.**

## In plain words

Today a training window set holds only windows a human already labelled, from one recording, at one length (10 minutes).
The researcher wants a very large heap of **unlabelled** windows instead: 1-minute, 10-minute and 30-minute windows, from
two oyster recordings, saved as separate sets and then combined when a model is set up — with the test regions fenced
off first, so nothing the model is examined on was ever in the heap.

## Decided (the researcher, 2026-10-05). Build these; do not re-open them.

- **Manual labels are ignored when the pool is built.** Windows are cut from the signal, labelled or not.
- **Two recordings:** `M2_aug_concat_fs1.mat` and `M2_concat_fs1.mat` (both oyster; different data, not crops of one
  another).
- **Three scales:** 1, 10 and 30 minutes (60 / 600 / 1,800 samples at 1 Hz). **One window set object per recording per
  scale** — six sets — each saved, listed in Library › Window sets, and reusable.
- **Combining happens in a *Window pool* chain block in Analyse, which `AG` builds** (confirmed by the researcher
  2026-10-05): it picks from **the library of every saved window set** — these six now; later Library families as
  window sets, sets on other datasets — and combines them, with the option to remove duplicates and overlaps. **You
  build the six sets into that library and the UI-free combine function the block will call; the block and its page
  are not yours.**
- **The train / test fence belongs to the pool, not to a set.** A saved set is just windows (recording, channel,
  start, length, scale); the roles are laid over the combined pool once, by the region plan below. That is what lets
  any future set be combined without having been built with this split in mind. A set that already carries a split
  (the baseline's window set 1) keeps it for its own job and is combined as plain windows.
- **Target size:** 50–60 thousand windows or more in the pool. The non-overlapping supply is about 963,000 one-minute,
  96,000 ten-minute and 32,000 thirty-minute windows, so the 1-minute scale is **sampled**; the sample size per scale is
  a parameter with a seed, and the page shows the mix.
- **Artifact regions are left out** and counted.
- **The four packs:** each recording's 16 channels are four mushroom packs of four (CH1–4 A, CH5–8 B, CH9–12 C,
  CH13–16 D). The baseline's exam channels each had pack-mates in training; this version must be able to **hold out a
  whole pack**.

## What to build

1. **Region-first split.** Roles (train / validation / test / exam) are assigned to **stretches of time on a channel**
   before any window is cut, the same stretches for every scale. A window belongs to a role only if it lies wholly
   inside one stretch; windows that straddle a boundary, or sit within the gap, are dropped and counted. This is what
   stops a 30-minute training window from covering a 1-minute test window. Blocked by time as in `AB`
   (`blocked_split`), exam channels by choice, with a *hold out pack* shortcut.
2. **Unlabelled window sets per recording and scale** in `Working/training/` (extend `build_pooled_set` or add a
   sibling — say which and why): windows on a non-overlapping grid at that scale, artifact spans excluded (the human
   `artifact` label and anything the dataset's settings mark), saved through `store.save_window_set` with the scale
   and the counts, no roles. Additive schema only.
3. **Combine — a core function, no page** (`AG`'s block calls it; give it a CLI so it can be walked now). A pool is an
   ordered list of saved sets, a region plan and a rule. Default rule, stated on the page: within a scale no
   two windows overlap; **across scales overlap is allowed** (a 30-minute window and a 1-minute window inside it are
   different objects at different scales) **but never across roles**; exact duplicates are removed. Offer *no overlap
   across scales either* as the second rule (larger scale wins, or smaller — pick one, say which). A set that cannot be placed under the plan (a recording the plan does not cover) is refused with the reason. The saved
   pool is itself a `window_sets` row with its members, its plan and its key.
4. **Leakage guards carried over and extended:** the held-out file refused even with the unlock; the fs1 / fs2 pair of
   one recording never on opposite sides; and now the same check across recordings in one pool.
5. **Library › Window sets — *New window set*:** recording, channels, scale, grid, the artifact exclusion, a sample
   size and seed where the supply is large; progress; the row appears in the list with its scale and counts. Building
   the six is six uses of it (or one *build at 1 / 10 / 30 min* shortcut). Models › Launch and the baseline's
   labelled-only path are not changed here.
6. **Features are not yours** beyond what the pool needs to exist — `AG` decides what the clustering looks at. Store
   window bounds, not arrays (rule 4).

## Leave alone

| Leave alone | Why |
|---|---|
| Clustering, the dendrogram, the cut | `AG` |
| The *Window pool* chain block and its page; a pool as an Analyse source | `AG` — you give it the function and the saved sets |
| Review, blind labelling | `AH` |
| The paired job's scoring and the baseline run's rows (run 79, window set 1 — its cut is frozen) | history; do not rewrite |

## Acceptance — the researcher's walk

1. Library › Window sets → *New window set* → for `M2_aug_concat_fs1.mat` and `M2_concat_fs1.mat`, build the 1-, 10-
   and 30-minute sets → six rows in the list, each with its scale and counts.
2. From the command line (the page is `AG`'s): combine the six with pack D held out and the default time blocks → the
   printout shows windows per recording × scale × role, artifact regions left out, overlaps and duplicates removed,
   and no window of one role inside a stretch of another.
3. The saved pool appears in Library › Window sets. Load it again: the same windows, the same key.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge; `pytest` against the README baseline
(compare failure sets); `tests/test_import_boundaries.py`. Evidence into `webui/screenshots/fixup/AF/`.

## Report

`docs/prompts/fixup/reports/AF-multiscale-window-pools.md`, opening in plain words: the real counts of the six sets and
of one combined pool on the sandbox copy, time taken, the overlap rule as built, what was dropped, items left,
out-of-scope files, the gate. **Before you report, update** `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` per that
folder's README. Any question to the researcher: plain language first, then options, then a recommendation.

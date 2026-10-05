# Fixup AG — cluster the pool on trace shape, in an Analyse chain, with a dendrogram you can read

**Second of five for RQ1 version 2. Runs after `AF`.** Written 2026-10-05 and revised the same day after the
researcher's answers (below); nothing here is run yet. **Expect to split** — "If it splits" says where.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` ("New scope, version 2", "The baseline result"),
`reports/AF-multiscale-window-pools.md`, `reports/AB-models-paired-job.md` (§2 `paired.py` `propose`, the cut freeze;
§4 on Analyse › Training's fixture pages), `reports/AA-manual-labels-and-window-sets.md`,
`Working/library/grouping/` (`engine.py`, `methods/ward.py`), `Working/distances.py`, `docs/LIBRARY_STORAGE.md` §6 and
`Adapters/catalogue_cluster.py`.

Commit prefix `fixup-ag:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only.**

## In plain words

The baseline sorted windows by 24 summary numbers and got blurry piles that did not match what the researcher calls
interesting. The Library already sorts *motifs* by the shape of the trace, and that works well. This prompt uses the
same method on the big pool of windows, across three window lengths at once, so a one-minute sharkfin and a
thirty-minute sharkfin can land in the same pile. The researcher sets it up as blocks in an Analyse chain — window
pool → shape → cluster — and the cluster block's page is the dendrogram: a tree, a cut line, and what each pile looks
like when clicked. Models then trains on whatever that chain produced.

## Decided (the researcher, 2026-10-05). Build these; do not re-open them.

- **Cluster on trace shape, Ward linkage — the Library's method.** `Working/library/grouping/methods/ward.py` is
  "Ward linkage on resampled, z-normalised vectors under the scale-invariant distance", built on
  `Working.distances.resample_to_length` and `z_normalize`. **Reuse it; do not write a second one.**
- **Across scales:** every window, whatever its length, goes through that resample-and-normalise, so windows are
  compared by shape, not by duration. Scale is kept on every window and shown per cluster.
- **Windows under the noise floor are left out by default.** Normalising throws amplitude away, so a 0.1 mV wiggle and
  a 50 mV drop would look alike; there is no point comparing noise with a motif. Each window's raw range is kept beside
  it; the floor is the dataset's (`AE`'s `dataset_floors`); the count left out per recording and scale is shown; the
  switch can be turned off.
- **Ward on a 20,000-window sample locally**, the rest assigned to the nearest cluster centre. A Ward over every
  window is an HPC job whose script is `AI`'s; build so that a tree made elsewhere can be loaded in place of the local
  one (same artifact, same reader).
- **The workflow lives in Analyse, as chain blocks.** Window set → categories is edited in Analyse › Chain; the
  dendrogram and the cluster interaction are the cluster block's own page. Models › Launch reads the result and its
  *Open in Analyse* opens that chain (today it only navigates to the chain page).
- **Label arms on Launch:** the shape clustering is a second kind of arm B — **B.1 cluster labels · summary features**
  (the baseline's) and **B.2 cluster labels · trace shape** (this). An unlabelled pool has no arm A; the manual-label
  comparison comes from `AH`'s reference line.
- **The researcher decides which clusters are interesting / not interesting**; no human labels take part in forming
  the clusters or the mapping. The cut and the mapping are fixed before any test score and frozen after (as `AB`).
- **Random forest first**, trained on the cluster categories; the CNN is `AI`.
- Clusters are formed on **training windows only**.

## One thing to measure before trusting the piles

The Library groups **detected motifs**: each snippet starts where the detector says the event starts. Pool windows sit
on a fixed grid, so the same sharkfin may be at the start of one window and the end of another, and a point-by-point
shape distance calls those two far apart. Measure it on the sandbox pool: do the piles gather by shape, or by where in
the window the event falls? Report it with pictures. If position dominates, put the options to the researcher (plain
words first): e.g. centre each window on its largest excursion before resampling, or cluster detected events in place
of grid windows. Do not pick silently.

## What to build

1. **The *Window pool* block, the chain's source** — the step `AA` left for later ("§6.9 frame 0b — a validator
   change"). A chain may start from window sets in place of a span. The block's page lists **the library of every
   saved window set** (today `AF`'s six and the baseline's; later Library families as window sets and sets on other
   datasets — build nothing that assumes six), each with recording, scale and counts; the researcher ticks the ones to
   combine, sets the region plan (time blocks, exam channels, *hold out pack*) and the overlap rule (`AF`'s two), and
   the page shows the pool: windows per recording × scale × role, what was removed as duplicate or overlap and why.
   All of it through `AF`'s combine function — no second implementation. A saved pool can be re-opened as the source.
2. **The shape block** (WindowSet → WindowSet with vectors): resample to N points (default: the Library's own length —
   read it, do not invent one) and normalise, with the noise-floor filter above. Vectors are bulk arrays: on disk, by
   path (rule 4).
3. **The cluster block on shape.** Either `catalogue.cluster` gains a shape basis and returns its tree, or a sibling
   block — choose, and say why. Ward through the Library's method on a seeded sample (default 20,000, stratified by
   recording × scale); every other training window assigned to the nearest cluster centre at the chosen cut; the page
   says *clustered N, assigned M*. **The linkage matrix is kept as an artifact**, so the dendrogram, any later cut and
   `propose` (per k: sizes, specks, silhouette on a sample) all read one tree. No new dependency.
4. **The cluster block's page — the dendrogram.** Replaces Analyse › Training's fixture block 3 (`AB` report §4). The
   tree truncated to a readable depth; a cut line the researcher moves (k follows); each cluster at the cut is
   clickable and shows: **the medoid** (the most typical real window — a centre in feature space is not a trace), **a
   seeded handful of random members** (default 12), the mean normalised shape with its spread, the member count, the
   mix of scales and recordings, and the raw amplitude range. Members open in Explore. A red card, not a blank, if a
   cluster cannot be drawn. Follow the block drawing standard (`views.py` ↔ `registry.tsx`).
5. **The mapping table,** on the same page: each cluster → a name the researcher types (optional) and interesting /
   not interesting. Specks (`AB`'s rule) are listed and mapped like the rest.
6. **Save template; *Train model* hands it to Models.** On the chain, once a cut and a mapping exist: *Train model*
   saves the template and the pool if they are not saved and opens Models › Launch **prefilled** — the template, the
   pool as the sources (its recordings, channels and roles shown, not re-entered), and section 3 *Label arms* set to
   **B.2 cluster labels · trace shape** with the cut and mapping read-only. Launch's *Open in Analyse* opens that chain
   on that pool, so the two pages are one round trip. Nothing trains until the researcher presses *Train locally* (or
   *Create SLURM script*) on Launch. The
   freeze is enforced where it is today (`store.CutFrozen`): once a run on this pool has a test score, a changed cut or
   mapping is refused, in Analyse as well as in Launch, with the run named.
7. **The forest on the cluster categories,** through the existing job. Its inputs: say what you chose (the shape
   vector, the baseline's catch22 + entropy features, or both) and report how well it reproduces the clustering on
   held-out training windows — **as a diagnostic on the page, labelled as such, never as a result**: a forest imitating
   its own answer key is not evidence.
8. **Test and exam windows** are assigned only by running the trained model on them. They never touch the tree.

## If it splits

(i) the *Window pool* block as a chain source, the shape block and the cluster block with its kept tree — core and
tests, the block pages plain; (ii) the dendrogram page and the mapping table; (iii) *Train model* and Launch prefilled with the B.2 arm, *Open in Analyse*, the freeze, the
forest run. (i) alone is reportable.

## Leave alone

| Leave alone | Why |
|---|---|
| The baseline run (run 79, window set 1) and its frozen cut | history; arm B.1 keeps working as it does |
| Review and the blind queue; any score against a human | `AH` |
| The Library's own groupings and families | you reuse the method, you do not regroup the Library |
| The SLURM script for a full-pool Ward | `AI` |

## Acceptance — the researcher's walk

1. Analyse › Chain → source *Window pool* → tick `AF`'s six sets, hold out pack D, default overlap rule → the pool's
   counts → *shape* → *cluster* → ▶ Run → the cluster block's page shows the dendrogram; the row says how many windows
   were under the noise floor and left out.
2. Move the cut; click three clusters; each shows a medoid, members, scale mix and amplitude range.
3. Name the clusters, mark each interesting / not → *Train model*.
4. Models › Launch opens with the template, the sources and arm B.2 already filled in; *Open in Analyse* returns to
   the chain. Train locally (forest). The run records the tree, the cut, the mapping and the model; changing the cut
   afterwards is refused once a test score exists.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge; `pytest` against the README baseline;
`tests/test_import_boundaries.py`. Evidence into `webui/screenshots/fixup/AG/`.

## Report

`docs/prompts/fixup/reports/AG-shape-clustering-and-dendrogram.md`, opening in plain words: one real clustering of the
sandbox pool — sizes, silhouette, scale mix per cluster, how many windows the noise floor removed, screenshots of the
tree and three clusters, time and peak memory; **the position-in-window measurement**; the defaults you chose and why;
whether the piles look like shapes (say plainly if they do not); which seams were split; items left; the gate.
**Before you report, update** `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md` per that folder's README. Any question
to the researcher: plain language first, then options, then a recommendation.

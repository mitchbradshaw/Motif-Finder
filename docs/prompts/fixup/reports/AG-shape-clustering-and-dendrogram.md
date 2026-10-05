# Report — Fixup AG: cluster the pool on trace shape, in an Analyse chain, with a dendrogram you can read

Run 2026-10-05 on `main`, in the main checkout, alone. Commit prefix `fixup-ag:`. **Seams (i) and (ii) are done; seam
(iii) — *Train model*, Launch prefilled with arm B.2, the freeze, the forest — is not built** (§6 says why I stopped
there). Every bridge ran `--sandbox` on **port 8774** (walks) or **8775** (the gate) with a **private client build**
(`--dist <scratchpad>/dist-ag`); the researcher's bridge on 8765 was not touched and the shared `webui/client/dist`
was not rebuilt. The real database was only read (copied with the sqlite backup API from a `mode=ro` connection).
`M4_aug_concat_fs1.mat` was never read; window set 1 and run 79 were not altered.

## In plain words first

Think of the pool as 60,000 photographs of the signal, taken at three zoom levels (1, 10 and 30 minutes). This
ticket makes the app sort those photographs into piles **by the shape of the line in them**, ignoring how tall the
line is and how long the photograph lasts — the same way the Library already sorts motifs. You set it up in Analyse
as three blocks: **Window pool** (pick the saved window sets and the train / test fence) → **Trace shape** (squash
every window to 256 points and normalise it; throw out windows so flat they are only noise) → **Shape clustering**
(the Library's Ward method on 20,000 training windows, the rest dropped into the nearest pile). The clustering
block's page is a **tree you can cut**: drag the line, the number of piles changes, click a pile and you see its most
typical real window, a dozen random members, how many came from each zoom level and how tall they really were.

**What the piles turned out to be.** Mostly **not events**. On the real data the strongest thing that separates grid
windows is **which way the signal drifts across the window** — up, down, a bowl, a hump, a step half-way. The tree's
first split is "rising window" against "falling window"; at 8 piles, most piles are those same few slow shapes, and
many piles are **the same shape moved along the window** (19 of the 28 pairs of pile averages match far better once
shifted). Where the largest swing sits in the window is mostly **at the very start or the very end** — the edge of a
drift, not an event in the middle. The good news: the three zoom levels mix freely in every pile (a 1-minute and a
30-minute window do land together), and when I re-cut each window **centred on its biggest swing**, real event shapes
appear — sharp drops with a slow recovery, single spikes, V-shapes — at all three zoom levels. That is a choice for
you (§7, question 1), not one I made.

## 1. One real clustering of the sandbox pool

The six sets `AF` described, rebuilt in a sandbox copy of your database with `AF`'s CLI (the same six keys:
`9d704590…`, `c3d49a37…`, `5d228331…`, `7f064176…`, `b6b67273…`, `0433fd66…`); the real database holds only window set
1, so the sets exist in sandboxes only. The pool block's defaults: every unlabelled set, pack D held out, 10 time
blocks, 30-minute gap, `within_scale`, **20,000 per scale, seed 0** → **60,000 windows, key `712f477b262b2fd8` — the
same key as `AF`'s pool**, train 31,460 · validation 4,380 · test 9,050 · exam 15,110. Raw output:
`webui/screenshots/fixup/AG/measure/stage1_printout.txt`, `stage1.json`.

**The noise floor** (0.1 mV, the default for both recordings — Settings › Datasets is empty) left out **2,515**:

| recording | scale | left out | of | share |
|---|---|---|---|---|
| M2_aug | 1 min | 1,797 | 14,415 | 12.5 % |
| M2_aug | 10 min | 2 | 14,454 | 0.01 % |
| M2_aug | 30 min | 0 | 14,459 | 0 |
| M2 | 1 min | 715 | 5,585 | 12.8 % |
| M2 | 10 min | 1 | 5,546 | 0.02 % |
| M2 | 30 min | 0 | 5,541 | 0 |

(per role on the page: train 482 · validation 318 · test 438 · exam 1,277). 0 unmeasured (both recordings declare
volts). **57,485 kept**, of which **30,978 training windows**.

**Clustered 20,000, assigned 10,978** (the sample stratified by recording × scale); 26,507 validation / test / exam
windows not clustered (−1).

| | time | memory |
|---|---|---|
| Window pool (combine + save) | 11.8 s script · 12.9 s in the chain | — |
| Trace shape (60,000 windows read from their channels) | 37.3 s · 38.8 s in the chain | — |
| Ward on 20,000 (the Library's `condensed_distances` + `ward_linkage`) | **57.4 s** (50.7 s in the bridge) | **peak 3.07 GB** for the whole script process (3.8 GB for the bridge process) |
| the proposal, k = 2–20 (silhouette on ≤ 8,000) | 38.1 s | — |
| the whole chain, first run · re-run with the tree re-used | **138 s** · **73 s** | — |

**The cut.** The proposal by the baseline's written rule (best silhouette among cuts with ≥ 2 non-speck clusters;
specks under 155 windows) is **k = 2, silhouette 0.459**: 17,695 / 13,283. Silhouette falls with k: 0.363 (k 3),
0.284 (k 4–5), 0.164 (k 6), **0.165 (k 8)**, 0.14 (k 10), 0.12 (k 13), ≈ 0.05 (k 17–20). No cut has a speck.

Scale mix per cluster (training windows, sampled + assigned):

| k = 2 | n | 1 min | 10 min | 30 min |
|---|---|---|---|---|
| 1 (falls across the window) | 13,283 | 3,890 | 4,592 | 4,801 |
| 2 (rises across the window) | 17,695 | 6,105 | 5,857 | 5,733 |

| k = 8 (the cut I browsed) | n | 1 min | 10 min | 30 min | median raw range | event at (median) |
|---|---|---|---|---|---|---|
| 1 hump, falls at the end | 3,218 | 761 | 1,147 | 1,310 | 2.82 mV | 0.93 |
| 2 falls to the middle then partly recovers | 2,037 | 446 | 737 | 854 | 2.77 mV | 0.20 |
| 3 steps down half-way | 1,596 | 587 | 471 | 538 | 1.68 mV | 0.60 |
| 4 falls steadily | 6,317 | 1,996 | 2,224 | 2,097 | 1.80 mV | 0.17 |
| 5 dips then rises | 1,846 | 450 | 632 | 764 | 2.21 mV | 0.60 |
| 6 flat with spread (noise-like) | 1,965 | 977 | 432 | 556 | 1.04 mV | 0.52 |
| 7 rises steadily | 8,915 | 3,246 | 3,077 | 2,592 | 1.80 mV | 0.27 |
| 8 rises then levels | 5,084 | 1,532 | 1,729 | 1,823 | 1.83 mV | 0.06 |

Evidence: `05_dendrogram_proposed_cut.png`, `06_dendrogram_cut_moved_k8.png` (the tree, the cut at k = 8, the table),
`07_cluster_1_k8.png`, `07_cluster_2_k8.png`, `07_cluster_3_k8.png` (three clicked clusters: medoid, 12 members, mean ±
sd, scales, recordings, raw range, where the event sits), `08_mapping_table.png`, `01`–`04` (the pool page with its
library of sets, the chain after ▶ Run, the pool's recording × scale × role, Trace shape's floor count and the
raw-range histogram). `walk.txt` is the walk's printout: **0 browser console or page errors.**

## 2. The position-in-window measurement

`scripts/ag_shape_pool_report.py` (dev tooling, reads the sandbox copy; output in `measure/stage2_k{2,8,13}.json`,
pictures `position_*`). For every window: **where its largest excursion from the window's median sits**, 0 = the
start, 1 = the end.

| | k = 2 | k = 8 | k = 13 |
|---|---|---|---|
| share of the event-position variance the clusters explain (η²) | 0.016 | **0.161** | **0.201** |
| NMI cluster × position decile | 0.011 | 0.126 | 0.141 |
| NMI cluster × scale · × recording | 0.002 · 0.000 | 0.008 · 0.005 | 0.012 · 0.007 |
| position alone predicts the cluster (1-D nearest neighbour, held-back half) | 0.59 vs chance 0.58 | 0.31 vs 0.28 | 0.28 vs 0.28 |
| pairs of cluster averages that are **shifted copies** (best shifted correlation ≥ 0.8, ≥ 0.3 better than unshifted) | 0 of 1 | **19 of 28** | **50 of 78** |
| re-cut centred on the largest excursion: agreement with the grid piles (ARI) | 0.47 | 0.33 | 0.30 |
| … and η² of event position in the centred piles | 0.008 | 0.055 | 0.088 |

**What it shows.**

1. **Position alone does not decide the piles** — knowing only where the event sits predicts a window's pile no
   better than chance, and the scales and recordings mix freely (NMI ≤ 0.012). So the piles are not "event at the
   start / middle / end" bins.
2. **But the same shape at different positions is split into different piles.** From k = 8 up, most pairs of pile
   averages are one curve slid along the window (e.g. k = 8 clusters 1 and 2 correlate −0.08 as they are and 0.995
   shifted by half a window). A point-by-point distance on grid windows treats "a bowl early" and "a bowl late" as
   different shapes. That is the risk the ticket named, and it is real from k ≈ 8.
3. **The dominant shape is drift, not events.** `position_grid_clusters_k2.png`: the first split is a straight
   falling line against a straight rising line; the largest excursion sits at the very start or very end of most
   windows at every scale (Trace shape's page draws the same U-shaped histogram for 1, 10 and 30 minutes). On the
   k = 8 members (`position_members_k8.png`, `07_cluster_3_k8.png`) real drops sit beside windows that are noise a
   little above 0.1 mV.
4. **Centring each window on its largest excursion changes the piles** (ARI 0.33 at k = 8) and they become event
   shapes: a sharp drop with a slow recovery (three clusters), a single spike, a V, ramps with a notch — each mixing
   all three scales (`position_centred_clusters_k8.png`). Silhouette at k = 8 rises from 0.165 to 0.191.

## 3. Do the piles look like shapes?

**Plainly: they look like slow drift shapes, not like the events you call interesting.** Rising, falling, bowl, hump
and step windows, and the same drift at two positions as two piles. Some piles contain real events (cluster 3 at k = 8
holds drops on CH1 and CH3), mixed with windows of noise just above the floor. As built, I would not hand these piles
to a forest as categories without the decision in §7 question 1.

## 4. Defaults I chose, and why

| default | why |
|---|---|
| Window pool: every unlabelled set (`all unlabelled`), **pack D held out**, 10 blocks / test 0.2 / validation 0.1 / gap 30 min, `within_scale`, **20,000 per scale, seed 0** | the researcher's mix (equal per scale) and `AF`'s plan; pack D is what `AF`'s pool and RQ1's "hold out a whole pack" used. The pool is **saved** and found again by its key, so the same settings never add a second row |
| Trace shape: **256 points** (`ward.RESAMPLE_LENGTH`, read, not invented), floor **on** | the Library's own length; the ticket's floor rule |
| raw range = **peak to peak in mV** by the declared unit; no unit → *unmeasured*, kept and counted | the Library's floor compares a depth in mV; peak-to-peak is the window's equivalent. A recording without a unit has no mV to compare |
| Shape clustering: **a sibling block** `catalogue.shape_cluster`, not a basis on `catalogue.cluster` | `catalogue.cluster` clusters a feature matrix, every window, keeps no tree, and made run 79's frozen cut; this one reads shape vectors by path, trains on training windows only, samples, assigns and keeps the tree — a switch would put an `if` on each path |
| sample **20,000**, stratified by recording × scale (proportional), seed 0; **assign = nearest centre** (mean of the sampled members' vectors) | the ticket; Ward minimises within-cluster variance, so the mean is its own centre |
| cut **k = 0 → the proposal** by the baseline's written rule | the researcher's rule for run 79; the page shows the proposal and lets the cut be dragged |
| medoid among ≤ 1,000 seeded members; **12** random members, seed 0 | the ticket's 12; an exact medoid of 8,000 members is a 0.5 GB matrix for one click |
| the mapping is the block's `mapping` parameter, `{k, clusters}` | so the template and Launch read the same mapping, and a mapping made at another cut says so (`stale`) |
| the tree's file: `tree.npz` (linkage, leaf rows, training rows) + `manifest.json` (shape key, sample, seed, method, time, memory); a tree from `tree_path` is loaded by the same reader and **refused if built on other windows** | "same artifact, same reader" for `AI`'s full-pool Ward |

## 5. What was built

**Seam (i) — the chain, core and blocks.**

| where | what |
|---|---|
| `Working/training/shape.py` (new) | a pool rides on a `WindowSet` as metadata columns; `trace_shapes` (the Library's `shape_vectors`, raw range, event position, the floor counted per recording × scale × role); `cluster_shapes` (stratified seeded sample of training windows, the Library's Ward); `labels_at` (nearest centre; −1 for validation / test / exam); `ShapeTree` save / load, `load_tree_for`; `propose`, `cut_height`, `k_at_height`, `dendrogram`, `cluster_detail`, `clusters_summary` |
| `Adapters/preprocessing_window_pool.py` | **Window pool**, a chain **source** (`AF`'s `combine`, nothing re-implemented); saves the pool or re-uses it by key; `pool` re-opens a saved pool |
| `Adapters/preprocessing_trace_shape.py` | **Trace shape**, WindowSet → WindowSet; vectors on disk by path |
| `Adapters/catalogue_shape_cluster.py` | **Shape clustering**, WindowSet → Grouping; tree kept and re-used; `tree_path`; `mapping` |
| `Adapters/base.py`, `Working/chain_validation.py` | `AdapterSpec.source`; a source block anywhere but step 01 is refused with the reason (`AA`'s "frame 0b") |
| `Working/library/grouping/methods/ward.py` | `fit` is now made of four public pieces (`shape_vectors`, `distance_scale`, `condensed_distances`, `ward_linkage`) so a 20,000-item caller uses the Library's method without the square matrix. Same numbers; the Library's tests pass unchanged |
| `Working/library/grouping/methods/__init__.py` | discovery keyed on whether it has run: importing `ward` directly used to leave `feature_bins` and `labels` unregistered (an order-dependent failure my import exposed) |
| bridge | `GET /api/windowsets/library` (`shape_routes.py`); the card's `source`; validate / compatible apply the position rule; pool, shape and tree payloads (`serialize.py`); the sandbox redirects the three new write paths (`runtime.py`); `views.py` gains `windowset->windowset` |
| client | Analyse › Chain › Source › *Start from a Window pool* (puts the three blocks in, the old chain kept in Undo); the pool page (the library of every saved set with a tick each; the pool's recording × scale × role, removed and why, members, plan, checks); Trace shape's page (floor counts, raw-range histogram with the floor, event-position histograms per scale); chain-row thumbnails for a pool and a tree |

**Seam (ii) — the dendrogram page and the mapping table.** `/api/shape/trees/{key}/cut` and `/cluster` read the kept
tree by key (a new cut never rebuilds it; pinned); `TreePage.tsx` draws the truncated tree with a draggable cut
(k follows), the proposal per k, the clusters at the cut, a clicked cluster (medoid, 12 members with their raw
traces in mV, mean ± sd, scale and recording mix, raw range, where the event sits, *open in Explore*), *Apply this
cut*, and the mapping table (name + interesting / not per cluster, specks listed). Analyse › Training › 03 Cluster
(the fixture page) now links to the live page. Members open the channel in Explore (Explore takes no time
parameter; the same limit `AB` noted).

**Drawing standard:** the pool, shape and tree pages are chosen by payload convention (`pool_windows`, `shape`,
`tree`) and by the `window_sets` parameter, never by block name; the thirteenth modifier `windowset->windowset` is in
`views.py` and `registry.tsx`. Every piece is inside an `ErrorBoundary` (a red card and a console error).

**Tests:** `tests/test_training_shape.py` (16), `tests/test_shape_chain.py` (6), `tests/test_webui_shape_cluster.py`
(3), `tests/test_webui_shape_tree.py` (5). Red commits `3d56946` and `4322d61`. Pins changed on purpose and said in
`3d56946`: 38 → 41 shipped adapters (`test_end_to_end`, `test_adapter_spec`), 12 → 13 modifiers
(`test_block_standard`).

## 6. Items left

- **Seam (iii), not built:** *Train model* (save template + pool, open Models › Launch prefilled), arm **B.2 cluster
  labels · trace shape** on Launch, *Open in Analyse* returning to the chain, the freeze in Analyse and Launch, and the
  forest on the cluster categories with its diagnostic. **Why I stopped at the seam boundary:** §2–§3 show the piles
  are drift shapes and shifted copies, so a forest trained on them now would learn the wrong categories, and the
  forest's inputs depend on question 1. The freeze is not needed yet: nothing scores these clusters (AH's blind
  labels are the only score), and run 79's `CutFrozen` is untouched.
- The mapping table maps the cut **of the last run**; after *Apply this cut* the chain must be re-run (≈ 73 s with the
  tree re-used) before the table lists the new clusters. The table says so (`stale`).
- *Members open in Explore* opens the channel, not the window (Explore has no time parameter).
- The position measurement's "centre on the largest excursion" is a measurement script, not a block option; a
  re-cut window may cross its role's fence (the script clamps only to the channel). If you choose it, the block must
  clamp to the window's own stretch.
- The proposal reads silhouette on the sample; `propose` costs 38 s per run — cached per tree would be a cheap win.
- Known and not mine: the Library ignores `?grouping=`.

## 7. Questions for you

**1. How should a window be lined up before its shape is compared?** *In plain words:* the windows are cut on a fixed
grid, like photographing a parade every ten seconds — the same float can be at the left edge of one photo and the
right edge of the next. Comparing photos point by point then calls them different. On your data two things happen:
the photos are mostly sorted by **which way the street slopes** (the slow drift), and the same shape in two positions
lands in two piles.

- **(a) Centre each window on its largest swing before resampling** — measured here: event shapes appear (drops with
  recovery, spikes, V-shapes), all three scales mixed, silhouette at k = 8 0.165 → 0.191. Cost: one option on Trace
  shape, plus clamping the re-cut window inside its role's stretch.
- **(b) Remove each window's straight-line trend before normalising** — takes out the up/down split that dominates
  now. Not measured.
- **(c) Cluster detected events instead of grid windows** — the Library's way, each snippet aligned by the detector;
  needs a detector run over the pool's recordings and stops being "every window".
- **(d) Keep the grid as it is.**

*My recommendation:* **(a), with (b) measured beside it before you choose** — (a) is measured to give event-like piles
and stays "every window"; (b) is cheap to add and may matter as much, because the drift is the strongest signal.

**2. Where should the noise floor sit for M2_aug and M2?** *In plain words:* windows whose whole swing is smaller
than the floor are thrown out as noise. The default is 0.1 mV and removed about one 1-minute window in eight and
almost no longer ones; but many kept 1-minute windows between 0.1 and about 1 mV still look like noise in the piles
(the raw-range histogram is on Trace shape's page).

- **(a)** keep 0.1 mV; **(b)** set a higher floor per dataset in Settings › Datasets (e.g. 0.5 or 1 mV) and look at
  the piles again; **(c)** a floor per scale.

*My recommendation:* **(b)** — look at the histogram on Trace shape's page and set each dataset's floor where the
noise hump ends; the block reads it with no rebuild.

**3. Train the forest now, or after question 1?** *In plain words:* the forest learns to imitate the piles. If the
piles are "which way the window slopes", the model will learn slope, and the blind check (AH) will measure that.

- **(a)** build seam (iii) now on the piles as they are; **(b)** decide question 1, re-run the chain, look at the piles,
  then build seam (iii).

*My recommendation:* **(b).**

## 8. Files

**In the ticket's area:** `Working/training/shape.py` (new), the three new adapters, `webui/server/shape_routes.py`
(new), `webui/client/src/analyse/views/ShapeViews.tsx`, `TreePage.tsx`, `analyse/shape.css`, `api/shape.ts` (new),
`analyse/views/registry.tsx`, `ChainPage.tsx`, `BlockPage.tsx`, `toolbar.tsx`, the smoke file
`webui/smoke_pages/zzzzzz_ag_shape_clusters.json`, `scripts/ag_shape_pool_report.py` (evidence), tests.

**Outside it, and why:**

| file | why |
|---|---|
| `Working/library/grouping/methods/ward.py` | `fit` split into four public pieces so a 20,000-item caller reuses the Library's Ward without the square matrix (the ticket: reuse it, no second one) |
| `Working/library/grouping/methods/__init__.py` | discovery ran only when the registry was empty, so importing `ward` first left two methods unregistered |
| `Adapters/base.py`, `Working/chain_validation.py` | `source` and the step-01 rule ("a validator change", `AA`) |
| `webui/server/app.py` | one `include_router` |
| `webui/server/chain.py`, `serialize.py`, `views.py`, `runtime.py` | the card's `source` and the position rule; the three payloads; the thirteenth modifier; the three new write paths redirected in a sandbox |
| `webui/client/src/state.tsx` | `SourceSpan.kind` (`'pool'`) |
| `webui/client/src/training/ClusterPage.tsx` | a link from the fixture page to the live dendrogram |
| `tests/test_end_to_end.py`, `test_adapter_spec.py`, `test_block_standard.py` | the pins (41 adapters, 13 modifiers) |

`webui/smoke.py`, `api.ts` and every other ticket's files were not touched.

## 9. The gate

1. **`npx tsc -b`: clean. `npm run build`'s two steps as `npx tsc -b` + `npx vite build --outDir
   <scratchpad>/dist-ag-gate` — green** (a private build of the committed tree; the shared `client/dist` was not rebuilt
   because the researcher's bridge was on 8765).
2. **`pytest -n 4` (conda, 26 m 27 s): 2,343 passed, 27 skipped, 0 failed** — failure set empty against the README
   baseline. `tests/test_import_boundaries.py` passes, and `test_training_shape.py` pins that `shape.py` imports no UI
   library. (It ran beside the route tests below, hence the time.)
3. **Every `tests/test_webui_*.py` under `webui/.venv` (`-n 4`, 16 m 50 s): 423 passed, 3 xpassed, 1 failed** — the
   standing `test_the_scoreboard_cells_are_the_tables_own_numbers`. My 8 route tests pass.
4. **`webui/smoke.py`, one full walk on a fresh `--sandbox` bridge (port 8775, private build), 19:41–20:12: 653
   screenshots, 20 failures. All 4 of my states pass** (`zzzzzz_ag_shape_clusters`: Start from a Window pool and the
   library of sets; ▶ Run → the dendrogram, a moved cut and a clicked cluster with its medoid, members, scale mix and
   raw range, the mapping table; Trace shape's floor count; the pool's recording × scale × role). The 20, sorted
   (`smoke/smoke-full.log`):
   - **5 standing** — `discovery.runs--default` and the four Settings registration Check states;
   - **4 Interrogation cold-start misses** — the README's three plus `analyse.interrogation.slope--fixup-k-all-marks-
     names-what-is-not-drawn`, the same "loading the events…" pattern; **all 58 Interrogation states pass on a re-walk**;
   - **9 outside the baseline, none on a page this ticket touched, every one passing on a re-walk against the same
     bridge** (`smoke/rewalk_*.log`: Explore 54/0, Library 54/0, Review 25/0, `zzzz_ad` 7/0):
     `explore.corpus--default`, `library.recurrence--default`, `library.grouping--frequency-content`,
     `library.window-sets--empty-or-listed`, `review.inspector--1-candidate`, `review.inspector--3-queue-rail`,
     `settings.audit-log--empty-filter`, and `AD`'s two (`review.inspector--fixup-ad-send-suspected-artifacts-opens-the-queue`,
     `library.family--fixup-ad-the-queue-is-sent-once`);
   - **2 walk-level checks**, one cause: `POST /api/library/family/F-130/suspected-artifacts` returned a 500,
     `sqlite3.OperationalError: database is locked` (`AD`'s route, `Working/review/artifact_queue.py`), which is the 4
     unexpected traceback lines and the 1 console error. Nothing of this ticket writes at that point of the walk (my
     states run last).
   **Said plainly:** this was not a clean walk. The machine was not quiet: another agent's full smoke walk (port 8791)
   ran until 19:41, and an unidentified `C:\Python313\python.exe -` process used about one core throughout my walk.
   The re-walk of `settings` alone gave the four standing plus two different timeouts (`settings.shell--save-writes-
   the-settings-table`, `settings.nulls--unsaved`), which passed in the full walk. I read the 11 as load and timing, not
   as this ticket's, because each passes warm and none is on a page or route I changed — but a second full walk on a
   quiet machine would settle it, and I did not run one.

**Evidence:** `webui/screenshots/fixup/AG/` — `01`–`08` the browser walk (`walk.txt`), `position_*` the measurement
pictures, `measure/` the measurement's printouts and JSON, `smoke/` my four smoke states, the full log and the
re-walk logs, `pytest-summary.txt`.

**Commits:** `3d56946` (red, seam i) · `c435bee` (seam i) · `4322d61` (red, seam ii) · `ffd21c1` (seam ii) · the report
commit.

---

# Part 2 — 2026-10-05 (evening): lining the windows up, measured

The researcher answered §7: (1) **centre each window on its largest swing**, with a straight-line **detrend measured
beside it** — and a worry, in their words: this is *"risky as noise with large swing now gets directly compared to
events. Should be ok for at min 1 minute windows though."*; (2) **a floor per dataset**, set by the researcher in
Settings › Datasets after reading Trace shape's histogram; (3) settle the alignment, re-run, **look at the piles, and
only then** seam (iii). Seam (iii) is still not built. Commits: `494348d` (red tests), `4f37188` (the build), `278aeb6` (the measurement
and its pictures), `d742874` (a layout fix found on the gate), and the report commit.

## In plain words first

Two switches are now on the Trace shape block. **Align**: *grid* keeps each photograph as the grid cut it; *centre*
re-cuts it, the same length, so its biggest swing is in the middle. **Detrend**: *linear* takes away the window's
straight-line slope before comparing shapes, so a window that simply drifts up is no longer "a shape". I ran all four
combinations on the same 60,000 windows and looked at the piles.

- With **centre + detrend**, every one of eight piles is an event shape — a hump, a peak, a V, a drop with a slow
  recovery, a slow rise and a sharp drop (the sharkfin), a sharp drop in the middle. With the grid as it was, about half
  of the piles were just "goes up" or "goes down".
- **Your worry is right, and the other way round.** The noise problem is at **1 minute**, not at 10 or 30: with the
  0.1 mV floor, a third of the 1-minute windows look like pure noise (their whole swing is under 8 times the
  recording's sample-to-sample noise), against 1 in 20 at 10 minutes and 1 in 100 at 30. Those noise windows do **not**
  gather in a pile of their own: they sit in every pile, 4–23 % of each.
- **Raising the floor to 0.3 mV** removes most of them (1-minute noise-like 34 % → 14 %; every pile ≤ 14 %) and keeps
  the three scales roughly balanced. At **1 mV** the noise is gone, but so is almost half the pool, most of it the
  1-minute windows (1-minute training windows: 9,957 → 2,064).
- My recommendation: **centre + detrend** (now the default) with **a 0.3 mV floor** on both M2 datasets, then look.

## 1. What was built

- **`align`** on Trace shape — `grid` | `centre` — and **`detrend`** — `off` | `linear`. Defaults **centre, linear**
  (`shape.DEFAULT_ALIGN`, `DEFAULT_DETREND`); grid and no detrend stay available. The page states which are on, the
  rule for each, and the re-cut counts.
- **The largest swing** (`shape.SWING_RULE`): the window's least-squares straight line is removed, a running median of
  k samples is taken (k odd, at least 5, about a sixtieth of the window: 5 at 1 min, 11 at 10 min, 31 at 30 min), and
  the swing is the sample where that departs furthest from its own median. A one- or two-sample glitch cannot be it
  (pinned: a glitch eight times the event's depth is ignored), and nor can the drift (the line is removed first). The
  first report's definition (the largest departure from the median, no smoothing) pointed at a window edge in most
  windows because of the drift.
- **The fence** for a re-cut window: wholly inside its own role's stretch on its own channel (the pool's plan now
  rides on every window as stretch bounds), inside the recording, clear of every artifact span (human labels and
  Settings exclusions). Where the centre is out of reach the window is **shifted as far as allowed** — never left out
  for it — and counted as *clamped*. `check_recut` raises `LeakageRefused` if any re-cut window leaves its bounds
  (pinned, with a deliberately moved window).
- **Near-duplicates:** two windows that centre onto one event — a re-cut overlapping a kept window of the same scale on
  the same channel by more than half — keep the first; the rest are dropped and counted. A smaller overlap is kept and
  counted.
- **The floor per dataset**: read from Settings › Datasets when set, 0.1 mV otherwise; the page says which was used
  for which recording, and now draws **one raw-range histogram per recording × scale on shared log bins, each with its
  recording's floor line** — the picture to choose a floor from.
- **The cut proposal is cached** beside its tree (`propose.json`; 38 s saved on every re-run with the same tree).

## 2. The four combinations, one pool, one seed

Pool `712f477b262b2fd8` (60,000; `AF`'s), floor 0.1 mV, Ward on 20,000 training windows, seed 0
(`scripts/ag_alignment_report.py`; `measure2/alignment.json`, `printout.txt`). Pictures: `align_sheet_<combo>_k8.png`
— per pile its medoid (brown) and 11 seeded members.

| | grid · off | grid · linear | **centre · off** | **centre · linear** |
|---|---|---|---|---|
| silhouette k = 2 / 4 / 8 / 12 | 0.459 / 0.284 / **0.165** / 0.119 | 0.161 / 0.100 / 0.029 / −0.000 | 0.432 / 0.346 / 0.079 / 0.063 | 0.192 / 0.107 / 0.033 / 0.037 |
| proposal (the baseline's rule) | k 2 | k 2 | k 2 | k 2 |
| pile sizes at k = 8 | 3,218 · 2,037 · 1,596 · 6,317 · 1,846 · 1,965 · 8,915 · 5,084 | 4,729 · 2,803 · 3,390 · 3,679 · 4,484 · 2,915 · 3,838 · 5,140 | 1,967 · 2,801 · 3,914 · 4,717 · 2,275 · 2,111 · 5,354 · 6,231 | 2,815 · 5,747 · 2,905 · 4,291 · 2,008 · 2,704 · 2,915 · 5,985 |
| scale mix (NMI pile × scale; 0 = even) | 0.008 | 0.029 | 0.009 | 0.021 |
| shifted copies, a slide ≤ ¼ window (of 28 pairs) | 5 | 8 | **1** | 7 |
| … a slide ≤ ½ window (the first report's count) | 19 | 17 | 15 | 16 |
| what the piles are, by eye | drift: rising, falling, bowls, a step | humps, bowls, Vs — still off-centre, noisy | **4 drift piles** (two falling, two rising) + 4 event piles (peak, drop-and-recover ×2, drop in the middle) | **8 event piles**: hump, peak, V, drop-and-recover, sawtooth (sharkfin), sharp drop in the middle; noise in several |
| training windows (floor, near-duplicates out) | 30,978 | 30,978 | 29,370 | 29,370 |

Centring moved 53,931 windows; **86 clamped** (1 at 1 min, 20 at 10, 65 at 30), **0 pinned** by an artifact span,
**3,245 near-duplicates dropped** (66 at 1 min, 807 at 10, 2,372 at 30 — the 30-minute grid is sampled densely, so
neighbours centre onto one event) and 4,464 smaller within-scale overlaps kept and counted.

**A correction to Part 1, §2.** The "19 of 28 pairs are shifted copies" there allowed a slide of up to half a window;
at that slide half of any two smooth curves correlate well, so the count is loose. With the stricter slide (≤ a
quarter, three quarters of each curve still overlapping) grid · off has **5 of 28**, not 19. The conclusion that the
grid piles are drift shapes stands (the contact sheets show it); the claim that *most* piles are shifted copies of one
another does not. RQ1's line is struck through and corrected.

**Silhouette falls with detrending**, as expected: the up / down drift is the most separable thing in these windows,
and removing it leaves shapes that overlap more. Silhouette measures separation, not whether a pile is an event; it
is lowest for the combination whose piles look most like events. The proposal by the baseline's rule is k = 2 in every
combination and says little here — **choose the cut on the dendrogram by eye.**

## 3. The researcher's worry, measured

*Noise-like* = a window whose raw range is under **8 ×** its dataset's median sample-to-sample noise (σ from the
median absolute first difference). Also shown: raw range under 1 mV.

**After centring + detrend, floor 0.1 mV (the default):**

| | 1 min | 10 min | 30 min |
|---|---|---|---|
| noise-like | **34.4 %** | 4.9 % | 1.0 % |
| raw range < 1 mV | 79.3 % | 23.3 % | 5.2 % |

Per pile at k = 8 (noise-like, all scales · among the pile's 1-minute members): 7 % · 19 % | 18 % · 37 % | 7 % · 23 % |
7 % · 24 % | 9 % · 30 % | 4 % · 17 % | 20 % · 41 % | 23 % · 43 %. **No pile is mostly noise** (none ≥ 50 %): the noise
windows spread through every pile, most into the piles of drops in the middle (7, 8) and peaks (2). Grid · off is no
better (10–28 % per pile). Centring does not create the noise problem — it is there on the grid too — but it does
put a noise window's biggest wiggle in the middle, where an event's would be.

**Raising the floor** (centre + detrend, set in Settings › Datasets for both recordings):

| floor | left out | training windows (1 / 10 / 30 min) | noise-like, 1 min · 10 · 30 | worst pile | silhouette k 8 | shifted (¼) |
|---|---|---|---|---|---|---|
| 0.1 mV | 2,474 | 29,370 (9,957 / 10,057 / 9,356) | 34.4 % · 4.9 % · 1.0 % | 23 % | 0.033 | 7 |
| **0.3 mV** | 12,961 | 24,843 (5,690 / 9,807 / 9,346) | **13.7 % · 4.6 % · 1.2 %** | 14 % | 0.081 | 7 |
| 1 mV | 26,589 | 18,668 (2,064 / 7,725 / 8,879) | 0.1 % · 0 · 0 | 0 % | 0.095 | 6 |

At 0.3 mV the remaining noise begins to gather (piles 2 and 7 hold most of it, `align_sheet_centre-linear-floor0.3_k8.png`)
and pile 8 is a clean sawtooth / sharkfin pile across all three scales. At 1 mV the piles are clean but the 1-minute
scale is a fifth of its share: the scale balance the pool was built for is gone.

**Do the centred piles still mix scales evenly?** Yes, broadly: NMI pile × scale 0.021 (centre + detrend), 0.009
(centre, no detrend), against 0.008 on the grid. Some piles lean: at 0.1 mV two piles hold 2,408 and 2,913 one-minute
windows against ~1,400–1,500 at 30 min — those are the noise-heavy piles.

## 4. What I would use, and what the piles look like

**Centre + linear detrend, with a 0.3 mV floor on M2_aug and M2**, and the cut chosen on the dendrogram by eye
(k ≈ 8–10 to start). The piles are then event shapes — humps, peaks, Vs, drops with a slow recovery, a sawtooth
(sharkfin) pile, a sharp-drop-in-the-middle pile — each holding all three scales, with noise in two piles rather than
spread through all. **I set the default to centre + linear**; the floor stays the researcher's (Settings ›
Datasets) as decided, and the block reads it with no rebuild.

## 5. Items left

- Seam (iii) — *Train model*, arm B.2, the freeze, the forest — **not built, as instructed**; it waits for the
  researcher to look at the piles.
- The noise rule is in mV; most noise windows are 1-minute (question below).
- Near-duplicates are judged per recording row and scale; an fs1 and an fs2 file of one recording are not compared
  (the M2 pools here use fs1 files only).
- Two windows of one scale overlapping by less than half are kept (4,464 here, counted): within-scale overlap after
  centring is no longer zero, unlike the grid pool.
- The first report's position measurement (`ag_shape_pool_report.py`) still uses the old swing definition; Part 2's
  numbers come from `ag_alignment_report.py`.

## 6. A question for the researcher

**Should the noise floor depend on the window's own noise rather than one number in mV?** *In plain words:* a floor in
millivolts treats a 1-minute and a 30-minute photograph alike, but almost all the noise-only windows are the short
ones — over a minute the signal has had little time to move, over thirty minutes it nearly always has. A floor of
0.3 mV cleans most of them out; a floor of 1 mV cleans all of them but also throws away four in five 1-minute windows.

- **(a)** keep the per-dataset mV floor you chose, at about 0.3 mV — built, works today;
- **(b)** add a second, scale-aware rule: leave out a window whose swing is under N times its own sample-to-sample
  noise (measured here with N = 8) — one more switch on Trace shape;
- **(c)** a higher floor for 1-minute windows only.

*My recommendation:* **(a) at 0.3 mV now**, look at the piles, and ask for **(b)** only if the 1-minute members of the
event piles still look like noise — it is the rule that matches what the measurement found, but it is one more number
to choose.

## 7. The gate

1. **`npx tsc -b` clean; the build green**, into private directories from `git archive HEAD` (the main checkout held
   another session's uncommitted client edits — Discovery's seed page — so the gate's client is this branch's alone).
2. **`pytest -n 4` (conda, 22 m): 2,353 passed, 28 skipped, 0 failed** — failure set empty.
3. **Route tests (`webui/.venv`, every `tests/test_webui_*.py`, `-n 4`, 13 m): 424 passed, 3 xpassed, 7 failed** — the
   standing `test_the_scoreboard_cells_are_the_tables_own_numbers`, and **six in `tests/test_webui_seed_page_repairs.py`,
   an untracked file of the other session's work in progress** (its routes are in its uncommitted `discovery.py` /
   `library.py`). None of mine; my route tests pass.
4. **Smoke, two full walks on fresh `--sandbox` bridges** (port 8775, private build of HEAD). **All 4 of my states pass
   in both**, and again after the layout fix below (`--only zzzzz`: AF's 3 + my 4, 7 screenshots, 0 failures, 0
   console errors, 0 tracebacks; `smoke-part2/smoke-ag-states-after-fix.log`).
   - **First walk (22:44–23:21): 652 screenshots, 25 failures**, including the `database is locked` 500 on `AD`'s
     `POST /api/library/family/F-130/suspected-artifacts` again (2 walk checks + `AD`'s two states).
   - **Second walk on a quiet machine (23:23–23:58), the gate: 654 screenshots, 22 failures.** A process sampler
     (`smoke-part2/sampler.txt`) shows only my bridge and my walk running, CPU 1–26 %. **The `database is locked` 500
     did not recur** (0 unexpected tracebacks). The 22 (`smoke-part2/smoke-full-quiet.log`):
     - **the 8 of the baseline** — `discovery.runs--default`, the four Settings registration Check states, and the
       three Interrogation cold-start states (`--fixup-d-sequence-rose`, `.slope--fixup-k-marks-are-the-payloads`,
       `--fixup-k-marks-on-a-trough-family`);
     - **3 in the core Analyse flow** (all rows completed · every row painted · *Pass N to Review* enabled): the example
       chain's matrix profile was still running when checked. The bridge log puts *stumpy JIT warm* at 23:24:31, 73 s
       after start — the walk began 1.5 min after the bridge and the run collided with the warm-up. (My first walk of the
       day, which passed these, started 20 minutes after its bridge.)
     - **11 other states**, none on a page this ticket touched; re-walked warm against the same bridge
       (`smoke-part2/rewalk3_*.log`): **Explore 0 and Interrogation 0 failures** (so `explore.cross-channel--as-recorded`,
       `analyse.interrogation--default`, `.slope--default`, `.slope--fixup-k-all-marks-names-what-is-not-drawn` are
       cold-start); **still failing warm:** `discovery.runs--modal-slurm` (1 console error), `discovery.seed--default` —
       and on the re-walk also `discovery.compare--default`, `discovery.stages--default` — *the Discovery pages the other
       session's uncommitted `webui/server/discovery.py` changes, which this bridge ran, served to this branch's client*;
       `library.grouping--frequency-content` (the Edit grouping modal still a skeleton at 2.5 s; its editor read answers
       in 38 ms warm — it failed on the afternoon walk too, then passed warm); `review.inspector--3-queue-rail (click
       toggle)` and `--queue-picker popover lists the live queues` (the queue list depends on what the store holds);
       `settings.datasets--held-out-locked` and `settings.storage-backups--default` (the storage read walks the real
       `DATA/` trees, 0.4–0.6 s warm; the Settings-only re-walk also timed out `settings.shell--save-writes-the-settings-
       table`, `settings.datasets--review-item-carries-its-source-file`, `settings.nulls--unsaved`).
     - 1 walk check: 1 browser console error (`discovery.runs--modal-slurm`'s).
   **Said plainly:** on a quiet machine the walk is **not** at the 8-failure baseline, and load does not explain it. I
   can tie 3 to the stumpy warm-up and 4 to cold start; I cannot clear the Discovery, Library-grouping, Review-queue and
   Settings states without a walk of HEAD alone, which this checkout could not give while another session's
   uncommitted server edits sat in it (`webui/server/discovery.py`, `webui/server/library.py`). No state that failed
   touches a file this ticket changed, except through shared code: `serialize.py` (my branch is taken only by a pool
   WindowSet or a Grouping with a tree), `chain.py` (the step-01 rule), `runtime.py` (three more redirected paths) and the
   grouping-method discovery fix — I found nothing in those that reaches the failing pages, but that is a reading, not a
   walk.
   - **The `database is locked` 500 on `AD`'s suspected-artifacts route** (its own item): it occurred on the afternoon
     walk and on tonight's first walk, both while other walks or jobs were running, and not on the quiet walk. Every
     route opens its connection through `init_db`, which runs the migrations — the log prints ~300 *legacy detections:
     refusing run …* lines on each open — so two requests at once may contend for the write lock. A hypothesis, not
     checked; `AD`'s route and `init_db` are not this ticket's.
5. **Found and fixed on the gate:** the Trace shape page's re-cut tiles ran under the parameters panel, and the small
   histograms' tick labels collided (`d742874`; screenshot `09_trace_shape_options_and_histograms.png`).

## 8. To see the piles yourself — PROJECT mode on the real database

Your bridge writes to the real database in this mode (a backup is written first): the six window sets, the pool, a
run, and the shape vectors and tree under `DATA/derived/`.

1. Start the bridge: `webui\start.ps1` (PROJECT mode on http://127.0.0.1:8765), or
   `webui\.venv\Scripts\python.exe webui\run_server.py --project`. The banner says *MODE = PROJECT*.
2. **Library › Window sets › New window set** → recording **M2_aug_concat_fs1** → all 16 channels (default) → **1, 10,
   30 min** ticked (default) → stride one window → artifact exclusion on → no sample → **Build 3 sets**. About 4 s.
3. The same for **M2_concat_fs1**. About 4 s. Six rows appear (690,837 / 69,021 / 22,947 and 271,184 / 27,104 / 9,024
   windows).
4. **Settings › Datasets** → *noise floor* for M2_aug_concat_fs1 and M2_concat_fs1: **0.3** (mV). (Leave it empty for
   0.1 mV; you can change it later and re-run from step 02.)
5. **Analyse › Chain** → the source chip ▾ → **⌗ Start from a Window pool (saved window sets, in place of a span)**. The
   chain becomes *Window pool → Trace shape → Shape clustering* (your previous chain is kept in Undo).
6. **Open the Window pool** (01): every unlabelled set is ticked (the baseline's window set 1 is listed but not
   ticked), pack D held out, 20,000 per scale, seed 0. Nothing to change.
7. **▶ Run chain.** About **3 minutes** the first time (pool ~15 s, Trace shape ~1 min centred + detrended, Ward on
   20,000 ~1 min, the proposal ~40 s); the same chain again re-uses the pool and the tree (~1.5 min).
8. **02 Trace shape**: the options in force (*align centre · detrend linear*), the re-cut counts, how many windows the
   floor left out per recording × scale, and the raw-range histograms per recording × scale with the floor drawn. If
   you change the floor in Settings, **↻ Re-run from 02** (~2.5 min: a new floor is a new tree).
9. **03 Shape clustering**: drag the cut (try k = 8–10; the proposal, k = 2, says little here), click each pile — its
   medoid, a dozen members with their raw traces in mV, the scale mix and the raw range; *open in Explore* on a member.
   The mapping table can be filled, but **Train model is not built yet**.

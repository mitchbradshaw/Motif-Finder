# Report — Fixup AF: window sets at three scales in the Library, and the core that combines them into a pool

Run 2026-10-05 on `main`, in the main checkout, alone (the first of Stage 6). Commit prefix `fixup-af:`. The first
commit, `60bf586`, touches only `tests/` and is red: 21 core tests under conda (no `Working.training.pool`, no
`window_set_channels`) and 4 route tests under `webui/.venv` (no New window set routes). Every bridge ran `--sandbox` on
**port 8773** with a **private client build** (`--dist <scratchpad>/dist-af`; the banner said *a private build*). The
researcher's bridge was listening on 8765 throughout and was not touched; the shared `webui/client/dist` was not
rebuilt. The real `DATA/db/annotations.sqlite` was only read (copied with the sqlite backup API from a `mode=ro`
connection, and copied by the sandbox bridges). `M4_aug_concat_fs1.mat` was never read.

## In plain words first

Think of each recording as a very long roll of film, sixteen strips side by side (the channels). Until now a training
set was a handful of frames *you* had already marked. RQ1 version 2 wants the whole roll cut into frames of three sizes
— 1-minute, 10-minute and 30-minute — whether anyone marked them or not, so a clustering can sort them by shape.

What now exists:

1. **Six window sets in the Library**, one per recording per size. Library › Window sets › *New window set* cuts a
   recording into back-to-back windows (none overlapping), leaves out every window that touches a stretch a human
   marked *artifact*, counts what it left out, and saves the result. Ticking 1, 10 and 30 minutes (the default) builds
   all three sizes in one go — about **4 seconds per recording**. A set is just windows: which recording, which
   channel, where it starts, how long. It does **not** say which windows are for training and which are for the test.
2. **A combine function** (no page yet — that is `AG`'s *Window pool* block, which will call this). You give it a list
   of saved sets and a *plan*, and it builds one pool. The plan is the fence between training and testing, and it is
   drawn **on the time line first, before any window is placed**: the first 70 % of each recording is training, then a
   30-minute no-man's-land, then validation, another gap, then the last 20 % is test; and a whole mushroom pack (pack
   D, CH13–16) can be set aside as the exam. A window only gets a job if it sits entirely inside one fenced field; a
   window lying across a fence is thrown out and counted. Because the fence is the same for every size, a 30-minute
   training window can never cover a 1-minute test window.
3. **Duplicates and overlaps are removed and counted**, and a final check proves no window of one job sits in another
   job's field. Then a sample of each size is drawn with a fixed seed so the pool has the size you want.

**The real numbers (a sandbox copy of your database):** the six sets hold **1,090,117 windows** (690,837 + 69,021 +
22,947 from M2_aug; 271,184 + 27,104 + 9,024 from M2); **1,643 windows were left out for artifact**, all on M2_aug (M2
has no artifact labels). Combined with pack D held out and **20,000 windows drawn per size** (seed 0), the pool is
**60,000 windows**: 31,460 train · 4,380 validation · 9,050 test · 15,110 exam. Building the six took about 8 seconds
of clicking; combining took 7 seconds.

**One question for you** is at the end (§7): how the 60,000 should be split between the three sizes.

## 1. The six sets (acceptance 1)

Built in the browser walk on the sandbox bridge (Library › Window sets › *New window set* → M2_aug, all 16 channels,
1 / 10 / 30 min, stride = one window, artifact exclusion on, no sample → *Build 3 sets*; the same for M2). Evidence:
`webui/screenshots/fixup/AF/02_new_window_set_m2aug.png`, `03_built_*.png`, `04_six_rows.png`,
`05_rail_m2aug_1min.png`, raw output `walk_build.txt`.

| set | scale | on the grid | artifact (human label) | excluded by Settings | non-finite | **kept** | key |
|---|---|---|---|---|---|---|---|
| `ws_M2_aug_concat_fs1_1min` | 1 min (60 samples) | 692,160 | 1,323 | 0 | 0 | **690,837** | `9d704590377daf70` |
| `ws_M2_aug_concat_fs1_10min` | 10 min (600) | 69,216 | 195 | 0 | 0 | **69,021** | `c3d49a3775166770` |
| `ws_M2_aug_concat_fs1_30min` | 30 min (1,800) | 23,072 | 125 | 0 | 0 | **22,947** | `5d22833189e1027c` |
| `ws_M2_concat_fs1_1min` | 1 min | 271,184 | 0 | 0 | 0 | **271,184** | `7f0641769696991d` |
| `ws_M2_concat_fs1_10min` | 10 min | 27,104 | 0 | 0 | 0 | **27,104** | `b6b67273e9802195` |
| `ws_M2_concat_fs1_30min` | 30 min | 9,024 | 0 | 0 | 0 | **9,024** | `0433fd66adc67fd3` |

**Time:** M2_aug's three sets **4.0 s** and M2's **3.5 s**, click to *saved* in the browser (including job polling);
the CLI took 1.6 + 0.2 + 0.2 s and 1.1 + 0.1 + 0.1 s. Nothing is measured — a set stores window bounds (rule 4), so
building one is arithmetic on the grid plus one pass over the signal for non-finite samples (none in either recording).

**What "left out" means** (printed on the modal and in each set's row): any window *touching* a span a human marked
`artifact` (annotations and window verdicts; soft-deleted ignored); any window touching a span Settings › Channels &
events excludes (*exclude span*, or *exclude · mark channel bad* from the event's start to the end); any window holding
a non-finite sample. Every other label is ignored. The 128 artifact spans on M2_aug cover 76,800 s; 1,323 one-minute
windows touch them. **No Channels & events exclusions are saved in the real database**, so that column is 0; the reader
is pinned by tests (an *exclude span* on every channel, a *mark bad* from 8 h, a *show on plots* that excludes nothing).

Each set is a `window_sets` row: recording and channel NULL, `window_length` = the scale, `stride` = the grid,
**no roles** (`split_json.rule = "none"`, *the fence is laid over the pool*), the counts and the exclusion rule in
`coverage_json` (`set_kind: "unlabelled"`, `scale_min`), the content key in `recipe_hash`; its channels in the new
`window_set_channels` table (no role); bounds on disk in `unlabelled_windows.npz` + `manifest.json`. The Library row
says **roles at pool** (blue) with the reason, the scale on its kind line, and the counts in the rail. *Train in Models*
is disabled with the reason (Models › Launch reads labelled sets; not changed here, as the ticket says).

## 2. One combined pool (acceptance 2)

```
python -m Working.training combine --db <sandbox>/annotations.sqlite --root <sandbox> \
  --sets ws_M2_aug_concat_fs1_1min,ws_M2_aug_concat_fs1_10min,ws_M2_aug_concat_fs1_30min,ws_M2_concat_fs1_1min,ws_M2_concat_fs1_10min,ws_M2_concat_fs1_30min \
  --hold-out-pack D --sample 1=20000,10=20000,30=20000 --seed 0 --name pool_six_packD
```

Full printout: `webui/screenshots/fixup/AF/cli_combine_packD.txt`. **6.9 s** (8.0 s wall with Python start-up).

**The plan:** blocked by time as `AB` (10 blocks; last 2 test, the one before validation, the rest train), a **30-minute
gap** carved at every role change, pack D (CH13–16) the exam on both recordings, whole.

| recording | train | gap | validation | gap | test | exam |
|---|---|---|---|---|---|---|
| M2_aug (721.0 h) | 0.0–504.7 h | 30 min | 505.2–576.8 h | 30 min | 577.3–721.0 h | CH13–16, 0–721 h |
| M2 (282.5 h) | 0.0–197.7 h | 30 min | 198.2–226.0 h | 30 min | 226.5–282.5 h | CH13–16, 0–282.5 h |

**Windows per recording × scale × role** (pool `pool_six_packD` v1, key `712f477b262b2fd8`):

| recording | scale | train | validation | test | exam | total |
|---|---|---|---|---|---|---|
| M2_aug | 1 min | 7,565 | 1,035 | 2,160 | 3,655 | 14,415 |
| M2_aug | 10 min | 7,559 | 1,082 | 2,179 | 3,634 | 14,454 |
| M2_aug | 30 min | 7,609 | 1,059 | 2,182 | 3,609 | 14,459 |
| M2 | 1 min | 2,911 | 412 | 849 | 1,413 | 5,585 |
| M2 | 10 min | 2,891 | 402 | 841 | 1,412 | 5,546 |
| M2 | 30 min | 2,925 | 390 | 839 | 1,387 | 5,541 |
| **all** | | **31,460** | **4,380** | **9,050** | **15,110** | **60,000** |

**What was dropped when combining:** in a gap **1,512** · straddling a role boundary **240** (the block edges fall on
the 1-minute grid but not on the 10- or 30-minute one) · artifact, checked again **0** · exact duplicates **0** · overlap
within a scale **0** · sampled out **1,028,365** (the whole fenced supply is 1,088,365: 571,889 train · 80,961
validation · 162,900 test · 272,615 exam — `cli_combine_all_unsampled.txt`, 10–22 s for 1.09 million windows; the same key, `0e6c2d033fa82a2b`, on two separate copies of the database). Left out when the sets were built:
artifact **1,643**.

**The checks** (each one raises if it is not zero): windows inside another role's stretch **0** · overlaps across roles
**0** (on one recording's time, so the fs1 and fs2 files of one recording are checked together) · overlaps within a
scale **0** · overlaps across scales **42,528** windows — *allowed* under the default rule, all within one role.

**The second rule** (`--rule no_overlap`, `cli_combine_packD_strict.txt`): the same plan and sample give **41,570**
windows — every sampled 1-minute window kept, 18,430 larger windows dropped for touching a smaller one; across-scale
overlaps 0.

**Duplicates and overlaps, shown on real sets** (`cli_combine_duplicates.txt`): the 10-minute M2_aug set, then the
baseline's window set 1 (`ws_M2_aug_concat_fs1_12tr4ex`, labelled, combined as plain windows), then the 10-minute set
again → **72,241 exact duplicates** and **6,742 overlaps within a scale** removed; window set 1 contributes 0 windows
(each of its windows is on the 10-minute grid or overlaps it), the second listing 0.
**Found in passing: 4 windows of window set 1 touch a human artifact span** — `AA`'s rule excludes a window *inside* an
artifact span, not one that only overlaps one. They are dropped here; run 79's set and scores are history and were not
touched.

## 3. The saved pool loads back the same (acceptance 3)

`python -m Working.training show-pool --pool pool_six_packD` (`cli_show_pool.txt`): *the key in the row is
`712f477b262b2fd8`, recomputed from the files `712f477b262b2fd8` — the same*, and the same 60,000 windows. Library ›
Window sets lists it (`07_pool_listed.png`): **train-safe**, *pool · 1 / 10 / 30 min · 6 sets*, the role counts, the
recording × scale × role table, the drops, the plan's stretches, the rule and the members. A pool is a `window_sets` row
(plan in `split_json`, key in `recipe_hash`, counts and checks in `coverage_json`) with its members in order in the new
`window_pool_members` table and its channels in `window_set_channels`; bounds and roles on disk in `pool_windows.npz`.
Changing a file under a saved set or pool makes it refuse to load (key mismatch; pinned).

## 4. What was built

**`Working/training/pool.py` (new) — a sibling of `windows.build_pooled_set`, not an extension.** `build_pooled_set` is
the paired job's set: labelled windows only, thinned labelled-first, split at build and measured with features. An
unlabelled set ignores the labels, carries no roles and stores bounds only; branching the baseline's builder on all
three would put an `if` on every path run 79 relies on. `pool.py` re-uses `refuse_held_out`, `recording_identity`,
`blocked_split`, `HeldOutRefused` and `LeakageRefused`, and `catalogue.manual_labels.human_spans` for the artifact spans.

| function | what |
|---|---|
| `build_unlabelled_set` | one recording, one scale, its channels; a grid (stride ≥ the window, else refused; offset); artifact / Settings / non-finite exclusions counted per channel; an optional seeded sample |
| `plan_for` / `make_plan` | the region plan per recording **identity** (fs1 and fs2 share one entry, one set of stretches); `hold_out_pack` A–D or explicit exam channels; refuses a pack a recording does not have, all-exam, a gap ≤ 0 |
| `assign_roles` | the stretch a window lies wholly inside, else `gap` / `straddle` |
| `combine` | the seven steps in the module docstring; refuses a set on a recording the plan does not cover (*"… holds windows of X, which the region plan does not cover (it covers …). Lay the plan over that recording too, or leave the set out."*) and a gap shorter than the longest window in the pool |
| `check_pool` | the four counts above; raises `LeakageRefused` on a misplaced window or a cross-role overlap |
| `set_windows`, `list_sets` | any saved set as plain windows (unlabelled, pool, `AB`'s set across channels, `AA`'s one-channel set); every saved set with its kind and scale — what `AG`'s block lists |
| `save_unlabelled_set`, `save_pool`, `load_set`, `load_pool` | through `store.save_window_set` (it dispatches on the type) |

**The overlap rule as built.** Default `within_scale`: within a scale no two windows overlap; across scales overlap is
allowed but never across roles; exact duplicates removed; the first set listed wins. Second rule `no_overlap`: **the
smaller scale wins.** Larger-wins was rejected because the six sets are grids that tile the recording: the 30-minute grid
covers every minute, so larger-wins would quietly turn a three-scale pool into a one-scale pool. Sampling runs before the
cross-scale step, so every sampled small window survives and the larger ones around it go. Two choices of mine, said
here: an fs2 window over an fs1 window of the same scale **is** an overlap (one recording's time), so it is dropped, not
kept beside it; and the per-scale sample is drawn **after** the fence and the de-duplication, uniform over everything
left, so each role keeps its share.

**CLI:** `python -m Working.training build-set · build-sets · combine · show-pool` (the old `save-set · propose · run ·
show` unchanged).

**Bridge** (appended to `webui/server/training_routes.py`): `GET /api/windowsets/unlabelled/sources` (every recording
but the held-out one, which is listed only as a locked slot; channels, packs, supply per scale) and `POST
/api/windowsets/unlabelled` (a `training` job, one set per scale; held-out → 423, a bad scale or stride → 422).

**Library › Window sets:** *New window set* (`library/NewWindowSet.tsx`): recording (the held-out one disabled with its
reason), channels with a one-click checkbox per pack, 1 / 10 / 30 min ticked by default, stride in windows, the
artifact exclusion with its rule printed, the supply per scale and an optional seeded sample, the names it will save,
progress from the job, the result. **The sample is off by default**: every window is saved as bounds (690,837 one-minute
windows are 2 MB on disk) and the pool samples after the fence; a sample here is for a set used on its own.

**Schema (additive, `CREATE TABLE IF NOT EXISTS` in `_LIBRARY_SCHEMA`, `init_db` idempotent — pinned):**
`window_set_channels` (a set's channels with no role) and `window_pool_members`. Not `window_set_members`: its `role` is
`train | exam` and Models › Launch reads every set with members as a paired-job set.

## 5. Items left

- **`AG`:** the *Window pool* chain block and its page (it calls `combine` and `list_sets`; the mix it shows is
  `meta.counts.by`), the noise floor (*left out by default* is `AG`'s per the README; no window is dropped for it here),
  the features, a pool as an Analyse source.
- *Send N unlabelled to Review*, *Export* and *Delete* on a set's rail are the page's existing demo actions; they are
  not wired for the new kinds either (690,837 one-minute windows would not be a review queue).
- *Used by* is still not recorded for any set.
- A pool records which sets it combined (`window_pool_members`); a set does not yet show which pools use it.
- The Settings › Channels & events reader is new and honoured by the build and by `combine`; the page itself saves its
  events as settings drafts, and the real database holds none.

## 6. Files

**In the ticket's area:** `Working/training/pool.py` (new), `store.py` (dispatch), `__main__.py`, `__init__.py`; Library
› Window sets — `webui/client/src/library/WindowSetsPage.tsx`, `library/NewWindowSet.tsx` (new),
`webui/client/src/api/windowsets.ts` (new); tests `tests/test_training_pool.py`, `tests/test_webui_window_pools.py`;
smoke `webui/smoke_pages/zzzzz_af_window_pools.json` (new).

**Out of the expected area, and why:**

| File | Why |
|---|---|
| `Working/database/schema.py` | two additive tables (`window_set_channels`, `window_pool_members`) |
| `webui/server/training_routes.py` | the two New window set routes, appended beside `AB`'s window-set routes (the job manager and the sandbox root are there) |
| `webui/server/library.py` | a row's channels from `window_set_channels`; the `roles at pool` / pool checks; `setKind`, scale, counts, members, plan on the row |
| `webui/client/src/fixtures/library.ts` | `WindowSetRow` gains optional fields and `SetCheck` gains `roles at pool` (the type lives there) |

No other ticket's files were edited. `webui/client/src/api.ts` and `webui/smoke.py` were not touched.

## 7. A question for you

**How should the 60,000 be shared between the three sizes?** *In plain words:* the 1-minute size has ten times as
many windows as the 10-minute one and thirty times the 30-minute one. If the pool simply took everything, it would be
nine parts 1-minute to one part the rest, and a clustering would mostly be sorting 1-minute windows. So the pool draws a
fixed number of each size, like taking the same number of small, medium and large photos from three boxes of very
different sizes.

- **(a) Equal shares** — 20,000 per size, 60,000 in all (what the pool above did). Each size has the same say.
- **(b) Everything at 10 and 30 minutes, plus a 1-minute sample** — e.g. all 127,808 ten- and thirty-minute windows
  after the fence plus 20,000 one-minute ones (≈ 148,000). More data, but the 10-minute size dominates.
- **(c) Shares in proportion to time covered** — each size gets the same total hours, which means far fewer 30-minute
  windows than 1-minute ones.

**My recommendation: (a)**, because the question is whether a shape is the same thing at different sizes, and that
needs each size equally represented; `AG` can still cluster a 20,000 sample of it as planned. It is one parameter
(`sample`) with a seed, so it can be changed at any time without rebuilding a set.

## 8. The gate

1. **`npx tsc -b`: clean. `npm run build`'s two steps run as `npx tsc -b` + `npx vite build --outDir <scratchpad>/dist-af`
   — green.** Built into the private directory because the researcher's bridge was listening on 8765 the whole time;
   the shared `webui/client/dist` was not rebuilt.
2. **`pytest -n 4` (conda, 8 m 08 s): 2,312 passed, 25 skipped, 0 failed** — failure set empty, against the README
   baseline (empty). `tests/test_import_boundaries.py` passes, and `test_training_pool.py` pins that `pool.py` imports
   no UI or web library.
3. **Under `webui/.venv`, every `tests/test_webui_*.py` (`-n 4`, 10 m 20 s): 414 passed, 3 xpassed, 2 failed.** My 4
   route tests pass. The two failures are not mine:
   - `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` — the README's standing one;
   - `test_webui_library.py::test_a_cell_never_looked_at_differs_from_one_looked_at_and_empty` — the Recurrence cell
     now carries `confirmedMembers` (added by `fixup-ad`, `88670b5`) and this test's key-set assertion was not
     extended. I did not touch Recurrence; it is `AD`'s file and test, so I left it and say so here.
4. **`webui/smoke.py`, full walk, fresh `--sandbox` bridge on 8773 (private build of the committed tree), nothing else
   running (11:09–11:47): 624 screenshots, 64 failures. 0 browser console/page errors, 0 unexpected server
   tracebacks. All 3 of my states pass** (`zzzzz_af_window_pools`: the modal opens; *Build 3 sets* on M2 saves three
   sets as a job; the rows are listed with scale and counts). The 64, sorted (`smoke/smoke-result.json`):
   - **7 standing** — the five in the README and the two `review.inspector--padding` screenshot writes that overrun the
     Windows path limit under a scratchpad `SMOKE_SHOTS` (`AD`, `V`, `W` saw the same two).
   - **52 in the Library (atlas, family, recurrence and `W`'s / `AD`'s / `AE`'s Library states) and Discovery
     compare / stages**, all *missing a named element* (`family-card-F-03`, `F-05`, `F-130`, `cell-F-01-…`, a stage
     card, a pick button). **The real database changed under them today:** the Library shows the newest grouping of
     single motifs (`library.py:_default_grouping`, `ORDER BY id DESC`), and the researcher made three groupings this
     morning (ids 7–9, 09:21–09:28; the newest, *motifs · amplitude*, has 6 families), so the shape families those
     states name are no longer the default; and the discovery runs the compare / stages states pick changed (runs 3
     and 4, 2026-10-04 23:36). `AD`'s walk, before these, failed only the 7 standing states. I touched neither page.
   - **5 that assume an empty store:** `library.window-sets--none`, `--filter-deep-link-still-none`,
     `--import-modal-opens-while-empty` and `models.results--no-run-yet`, `models.compare--no-run-yet`. Since the
     baseline run the real database holds window set 1 and run 79, so these fail on any bridge from today. The three
     Window sets ones are on my page, but they fail on the data, not the code: the list they expect to be empty is not.
   - **Not done, and said:** a before/after walk with the pre-`AF` code on today's database, which would show the 57
     data-driven failures on both sides. Rebuilding the old tree needs a worktree with a `DATA/` junction, which is the
     risk this repo's rules warn about; I judged the database evidence above enough, and the person who re-points these
     states (or makes them seed their own data) should confirm it.

**Evidence:** `webui/screenshots/fixup/AF/` — `01`–`05` and `07` the browser walk (New window set on both recordings,
the six rows, a set's rail, the pool's rail), `walk_build.txt` / `walk_pool.txt`, the CLI printouts
(`cli_combine_packD.txt`, `cli_combine_packD_strict.txt`, `cli_combine_all_unsampled.txt`, `cli_combine_duplicates.txt`,
`cli_show_pool.txt`), `pytest-summary.txt`, and `smoke/` (my three smoke states, the log, the result JSON).

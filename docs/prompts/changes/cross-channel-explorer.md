# cross-channel-explorer — Explore › Cross-channel becomes the multichannel explorer that answers B4

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` ("Where you are", the interpreters, the
toolchain, smoke files, shared files); `docs/prompts/changes/cross-channel-explorer-decisions.md` (the decisions,
D1–D25, and why); then **this file's common part and your own slice only**. Each slice is one implementer agent (Opus,
medium effort, an isolated worktree cut from `main`). The manager runs at most **three at once**.

Commit prefix `xc-S<n>:` (e.g. `xc-S1: census pairs co-occurrences within the propagation ceiling`). Every commit
ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never `git stash` (the stash is shared between
worktrees); never push, merge, switch branches or remove a worktree.

## Why (the researcher, 2026-10-26 → 27)

Round-B question **B4** (Chapter 10, `tab:roundb`, fixed 27 Oct) asks, framed openly: *is there evidence of a
propagation lag between channels that is not artefact?* Co-occurring activity across electrodes has three readings:
a **shared-ground artefact** (common mode), **one event propagating through the mycelium**, or **independent
activity**. Today's page measures one window against one reference and stores nothing, and its "propagation" badge
is not evidence (RQ6: 49 of 300 pairs of unrelated random walks bin propagation on a 640 s window).

The researcher also wants the page to become the site's **multichannel explorer**: an overlay you can scroll, zoom,
add channels to (from any dataset, later environment series), slide lanes on, and that grows into **spatial** and
**environment** relationships. In their words: "the idea of the cross-channel page I think I want to evolve into
exploring not only propagation, but spatial and environment relationships too."

## The design in one paragraph

**Look, then test.** Three layers:
1. **Candidates.** A *census* lists every co-occurrence of detector events across channels, and the page steps
   through them.
2. **Measure on demand.** Bold some channels, box a span and measure lag, r and breadth against the span's own null.
   These results are labelled **looked for**.
3. **The claim.** The census numbers, every one beside its null. B4's numbers come only from here.

**The physical model.**
- M2's channels sit on **four separate mushroom packs A–D** (from the electrode name's letter). Propagation is judged
  only within a pack.
- A **cross-pack copy** (the same waveform at the same instant) is an artefact. So is every within-pack copy at that
  instant (common mode).
- A **cross-pack co-occurrence that is not a copy** is a **shared driver**: both packs reacting to one stimulus. It is
  kept for the environment work and never counted as propagation.

## Facts (measured 2026-10-26/27, read-only)

**Datasets** (the seven the researcher calls good, as registered):

| Dataset | Channels | Rate | Hours | Real detector runs |
|---|---|---|---|---|
| `M2_aug_concat_fs1.mat` | 16 | 1 Hz | 721.0 | yes, every channel |
| `M2_concat_fs1.mat` | 16 | 1 Hz | 282.5 | yes, every channel |
| `CO_fs2.mat` | 4 | 2 Hz | 480 | yes, every channel |
| `LM_fs2.mat` | 4 | 2 Hz | 480 | yes, every channel |
| `MJu26a_fs2.mat` (recordings 692–707) | 16 | 2 Hz | ~636 | **none yet** (the researcher runs them) |
| `SH_fs2.mat` (708–711) | 4 | 2 Hz | 480 | **none yet** |
| `SO_fs2.mat` (712–715) | 4 | 2 Hz | 480 | **none yet** |

M4 (recordings 49–64) is the held-out recording: never read, never listed, refused on every route while its lock is
on. Review queues 35 and 36 are never read or written.

**`drop_detection_v1` census.** It is the default detector, 92–100 % precise in the blind estimate. Each listed
channel has exactly one real run, and every run covers the whole recording.

| Dataset | Run group | Events per channel (CH1 → CH16) | Total |
|---|---|---|---|
| M2_aug | g20 | 44, 51, 75, 127, 47, 30, 119, 14, 15, 17, 45, 41, 9, 5, 9, 40 | 688 |
| M2_concat | g206 | 6, 19, 87, 13, 26, 40, 24, 26, 9, 1, 13, 3, 4, 19, 9, 11 | 310 |
| CO_fs2 | g114 | 10, 1, 24, 2 | 37 |
| LM_fs2 | g68 | 13, 30, 38, 44 | 125 |

- **v5** covers every channel of M2_concat (g207, 504 events), CO (g115, 187) and LM (g69, 409), but **only CH1–2 of
  M2_aug**.
- `wavelet_encoded` fires far more on its surrogate than on the signal (~2,700 against 5–147 per channel). It must
  never be a census detector.
- **Selection rule:** `Working/discovery/candidate_events.py::load_sweep_detections` (its Rule 1). The template comes
  from `discovery_runs`, by exact name: a group naming one template, not removed, not superseded. Runs must be
  completed, not superseded, `q.not_surrogate`, `q.not_window_part`. `run_methods()` cannot tell templates apart.
  Reuse that function; do not write a second selector.

**Events are long, and the stored start is not the onset.**
- v1 events run a median of ~1,150 s. `detections.start_idx` is the **padded window start**: `window_pad_frac` 0.25
  fall durations before the bracket (`Adapters/detection_drop_detection.py`).
- The block's label `onset=<i>;trough=<j>;…` is **not** in `detections.meta_json`, which is NULL on these runs.
- The census must recover the onset. Use the run's stored labels if `runs.artifact_path` or the step-cache payload
  holds them. Otherwise use the steepest fall inside the detection's first half, on a 5 s moving average. Never use the
  padded start.
- Record which method was used, per event, in the census.

**Costs** (M2_aug CH1, free RAM 1.3 GB of 14.7):
- the whole channel is 21 MB float64; an mmap open takes 1.5 ms and a full read 21 ms when cached;
- `cross_correlation_peak` takes 0.12 ms on 600 samples and 0.40 ms on 6,000;
- `chance_null` (K = 100) takes 13 ms on a 300-sample window.

Chance co-occurrence is rare. At ~43 events per channel over 721 h, two channels share an onset within ±50 s about
0.07 times per pair by chance. That is why the timetable null is not a rotation (D18).

**What the database holds today.**
- `motif_edge` and `motif_member_cooccurrence` have **0 rows**; there is no Suspected-artifact queue. The RQ6 numbers
  (64 flagged, 123 near-copies, 97 beat chance) were measured on a sandbox copy on grouping g-05 (4–5 Oct). They are
  history, not data.
- Grouping **g-11** (all active recordings, 42 families) is round B's working grouping; g-10 is kept for Chapter 9.
- No electrode position is stored anywhere. The only shared-ground pair is hard-coded in the page (CH3_A2 ↔ CH4_A2).
- Settings › Channels & events saves through page `channels-events` with keys `ground.<rec>.<ch>`, `gain.<rec>.<ch>`
  (`webui/client/src/fixtures/settings.ts`); none is saved yet.
- `tag_vocabulary` holds the categories corpus, element, framing, provenance, quality, species, status and structure.

## The code you start from

- **The page:** `webui/client/src/explore/CrossChannelPage.tsx` (584 lines).
  - It draws stacked rows and the overlay, has a window picker (`?window=motif-n`, `?pad=`) and a classification card.
  - It reads `GET /api/cross/{id}`, which measures lag and r for every pair against the reference on every fetch.
  - Helpers: `Overlay.tsx` (props-only; lanes, shared gain, ÷N, bold, brush, align), `overlayModel.ts`,
    `crossModel.ts`, `crossScale.ts`, `SpanActions.tsx` (the shared action strip).
- **Signal's two-level view:** `Overview.tsx` (a whole-channel envelope with a blue box, two grips, a coverage ribbon
  and a density ribbon; "the box IS the tier-2 viewport") and `SpanView.tsx:158` (wheel zoom about the cursor,
  pointer pan).
- **The route:** `webui/server/explore_routes.py::get_cross_channel`. Envelopes come from `corpus.window` →
  `decimate.envelope`, computed from the mmap on every request, with no saved levels.
- **The core:** `Working/cross_channel.py`.
  - `CrossChannelRule` holds the Settings keys: artifact |lag| ≤ 1 s and |r| ≥ 0.98, propagation 1–50 s and |r| ≥
    0.5, `null_k` 100, the 95th percentile, `min_samples` 30.
  - Functions: `bin_for`, `chance_null`, `chance_summary`, `cross_correlation_peak` (it searches **every** lag),
    `classify_waveforms` with detrend, `drift_suspect`.
- **Library's member classifier:** `Working/library/matching.py::classify_family_across_channels` →
  `motif_edge`/`motif_member_cooccurrence` → `family_recurrence` (Recurrence's one definition). **It is unchanged by
  this work** (D21) except S5's two-line addition.
- **Review:** `Working/review/artifact_queue.py` (the per-member Suspected-artifact queue), `queues.py`
  (`create_queue`, `find_open_queue`, `_resolve` dispatches on `source_kind`), `family_queue.py`.
- **Helpers to import, never copy:**
  - `Working.library.view_filter.dataset_floors` (noise floors);
  - `Working.discovery.channels.channel_name`, `M2_STYLE_NAMES`;
  - `Working.discovery.seeded_search.corrected_levels` (**Benjamini–Hochberg** already exists);
  - `webui/server/jobs.py::start_job` (jobs with progress);
  - `Working.database.vocabulary.set_annotation_tags`.
- **Existing tests:** `tests/test_cross_channel*.py`, `tests/test_webui_cross_*.py`, `tests/test_webui_site_x_cross.py`,
  `tests/test_webui_suspected_artifact.py`.
- **Existing smoke units:** `webui/smoke_pages/zzz_w_cross_channel.json`, `zzzzzzzzzzz_aq_cross_channel.json`,
  `zzzzzzzzzzz_overlay.json`.

## Rules for every slice

- **Test-first, verified.** Your first commit touches only `tests/` and holds a test that **fails**; the manager runs
  it red before anything else. Then make it pass with the simplest change, refactor, and commit, one seam at a time.
- **Stay in your file list.** Every out-of-scope file goes in your report with the reason. If you need a file another
  slice owns and it is not merged, stop and say so.
- **Shared files** (`webui/client/src/api/*.ts`, `kit/*`, `explore.css`, `webui/server/app.py`, `webui/smoke.py`,
  `Working/database/schema.py`) are **append-only**: new exports, new cases, new tables. Never reorder or rewrite an
  existing one. List each such edit in your report.
- **Mount lines.** S2 turns `CrossChannelPage.tsx` into a thin shell with named slots
  (`{/* slot: census */}`, `{/* slot: measure */}`, `{/* slot: candidates */}`, `{/* slot: space */}`).
  - A later slice puts its UI in its **own component file**.
  - Its only edit to the shell is **one mount line in its slot**, plus the URL parameters it reads. The manager merges
    those lines.
  - S1 runs before the shell exists, so it mounts `CensusCard` with one line below the current plot; S2 keeps that
    line in the census slot.
- **The rules that are not negotiable** (CLAUDE.md):
  - The core imports no UI library.
  - Plain SQL; schema changes are additive and idempotent in `init_db()`.
  - **Bulk arrays never enter the database**: null draws go to `.npz` under the step-cache root
    (`Working.config.STEP_CACHE_ROOT`, which the sandbox bridge redirects). Never add a new output root.
  - **Detections are machine-only; annotations are human-only.** Nothing here writes a verdict except a human's
    click, through the human door.
- **Five verdict words only** (artifact, interesting, not_interesting, unsure, seed). "Propagation" and "shared
  driver" travel as **tags** plus a note, never as a sixth verdict.
- **Loud failure.** A render error is a red card plus a console error; a server error is a 500 with its traceback.
  Never catch an error into a blank. Every disabled control says why, on the page.
- **Numbers say what they are.** Every count on the page sits beside its null and its rule, printed from the bridge,
  never restated in the client. "Looked for" results say so wherever they are shown.
- **Long work shows real progress and a time estimate** (done/total × elapsed), never an indeterminate bar.

## The gate, per slice (CLAUDE.md "The UI gate")

1. `tsc -b` and `vite build` from your worktree's `webui/client`, with the main checkout's toolchain
   (UX-1015-common.md gives the exact commands).
2. Your own tests, the test files your slice names, and `tests/test_import_boundaries.py`. Use the conda interpreter
   for core tests and `webui/.venv` for `tests/test_webui_*`, and say which interpreter ran each file.
   - **S0, S1 and S5 touch the shared core** (`schema.py`, `cross_channel.py`, `matching.py`), so the manager also runs
     the **full pytest suite** before merging them.
3. Your smoke states in `webui/smoke_pages/zzzzzzzzzzz_w2_xc_s<n>.json` (eleven z's): late in the walk, but before
   `zzzzzzzzzzz_w3_cancel.json`, whose cancel state must run last (`tests/test_webui_w3f_ui.py`; S1's first name,
   twelve z's, sorted after it and failed that test, renamed 2026-10-28). You cannot
   walk them: no database in a worktree. Describe, state by state, what each should show. The manager walks your units
   on a fresh `--sandbox` bridge on its own port, **never 8765**.
4. **A critic** reviews your branch; you get one fix round.

**Report:** `docs/prompts/changes/reports/xc-s<n>-report.md`. Include:
- **Assumed** (every choice the prompt left open, and what you chose);
- the files touched, with append-only edits listed;
- the tests (red commit sha, then green);
- the smoke states;
- timings on synthetic data where the slice names a target;
- what is left.

## The decisions each slice rests on

D-numbers refer to `cross-channel-explorer-decisions.md`. The ones most slices need:

- **D2, D9 — packs.**
  - M2-style names (`CH3_A2`) take pack = the letter. Other datasets are one **unassigned** pack until set.
  - Propagation is judged only within a pack.
  - A cross-pack **copy** is an artifact, and so is every copy at that instant (common mode).
  - A cross-pack co-occurrence that is not a copy is **shared driver**: never propagation, listed for the environment
    work.
  - Recurrence exclusion still needs a human verdict.
- **D16 — the census.**
  - Detector: choosable, default `drop_detection_v1`. It is "full" on a recording only when every channel has one real
    run.
  - Two events **co-occur** when their onsets are within the propagation ceiling (Settings, 50 s).
  - Lag and r are measured on **the same absolute samples on both channels**, from 60 s before to 180 s after the
    earlier onset (Q40a).
  - **The lag search is restricted to ±50 s.** Unrestricted, unrelated drifting channels peak at a median |lag| of
    114 s.
  - The noise floor applies to both swings, as in fixup-AD.
- **Bins** (`census_bin`):
  - **artifact:** a copy, i.e. |lag| ≤ 1 s and |r| ≥ 0.98, beats chance, both swings over the floor. Any packs.
  - **shared_driver:** cross-pack and not a copy.
  - **propagation:** within-pack, 1 s < |lag| ≤ 50 s, |r| ≥ 0.5, beats chance, over the floor.
  - **independent_recurrence:** within-pack, everything else.
- **D7 — common mode.**
  - An **instant** is a connected set of events joined by copy pairs. Its breadth is its number of distinct channels.
  - It is marked **common mode** when the breadth is more than half the recording's channels and every copy's
    amplitude ratio is within ×2, or when it spans two or more packs.
  - It is a mark inside `artifact`, never a bin.
- **D18 — the nulls.** Each test's statistic and null:

  | Test | Statistic | Null | K |
  |---|---|---|---|
  | Co-occurrence excess, per within-pack pair and overall | onsets within ±50 s | rotation: one channel's onset train circularly shifted by a uniform offset at least 1 h from zero | 1,000 |
  | Waveform | \|r\| at the restricted-lag peak | random-time (`chance_null`, restricted lag): windows ≥ 60 s away, never over a human-marked artifact; 95th percentile | 100 |
  | **Timetable**, per within-pack pair | the largest number of its non-copy co-occurrences whose lags fall within ±δ = 2 s of one lag L, 1 s < \|L\| ≤ 50 s; their median lag and MAD reported | n held fixed; each draw resamples n lags from a pool of ≥ 2,000 lags measured between the pair's onset windows and the partner channel at random other times | 1,000 |
  | Breadth | an instant's breadth | rotation: the number of other channels with any onset within ±50 s of a random instant (conservative) | 1,000 |
  | Shared driver, per pack pair and overall | cross-pack non-copy co-occurrences | rotation | 1,000 |

  - p = (1 + #null ≥ observed) / (K + 1).
  - Draws are seeded from the census hash.
  - Per-pair p-values are corrected with **Benjamini–Hochberg, q = 0.05, per recording**, using `corrected_levels`,
    and the correction is printed.
  - The one-draw phase-randomised detector runs are **not** used.
  - **The timetable null deviates from Q19**, which named rotation. Rotation draws almost never contain a co-occurrence
    on events this sparse, so a lag spread cannot be formed from them. The researcher confirmed this on 2026-10-27
    (decisions note, X1).
- **Census constants.** The onset window (−60 s, +180 s), δ, both K values, the minimum rotation offset, the breadth
  fraction, the ×2 amplitude band and q are **named constants recorded on every census** (and in its hash), not new
  Settings keys (X5). The bin lines stay the existing Settings keys.

---

## S0 — the channel layout reader (manager, directly, before wave 1)

**Why:** S1 (packs in the census), S2 (pack chips) and S3 (Settings columns) all need one definition of a channel's
pack and position.

**Files:**
- `Working/channel_layout.py` (new);
- one route in `webui/server/explore_routes.py` (appended);
- `webui/client/src/api/explore.ts` (appended);
- `tests/test_channel_layout.py`, `tests/test_webui_channel_layout.py`.

**The work:**
- **Keys:** `pack.<rec>.<ch>`, `x_mm.<rec>.<ch>`, `y_mm.<rec>.<ch>` on settings page `channels-events`, with
  **exactly** the `<rec>` and `<ch>` the page already uses for `ground.<rec>.<ch>`. Read `ChannelsEventsPage.tsx`; a
  test pins the format.
- **`channel_layout(conn, source_file)`** returns, per recording id: name, `pack`, `pack_from`, `x_mm`, `y_mm`.
  - `pack_from` is `settings`, `name` (the M2 letter via `M2_STYLE_NAMES`) or `unassigned`.
  - Also return `layout_known` (every channel has a pack from settings or name) and `positions_known` (every channel
    has x and y).
- **`same_pack(layout, a, b)`.** Two `unassigned` channels count as the same pack, so propagation stays allowed on
  unknown layouts, and every result says "packs not set — layout unknown".
- **`GET /api/layout/{source_file}`** returns that dict. It answers 423 for the held-out file.

**Tests:**
- M2 letters, an unassigned 4-channel recording, a settings override winning over the letter, positions round-trip;
- the held-out file refused.

---

## S1 — the census: core, storage, job, read routes, the B4 card and the thesis script (wave 1)

**Files:**
- `Working/cross_census.py` (new);
- `Working/cross_channel.py`, append-only:
  - a `SHARED_DRIVER = "shared_driver"` constant (outside `BINS`, which the Library path keeps);
  - an optional `max_lag` (samples) on `cross_correlation_peak` and `chance_null`. The default is None, the old
    behaviour, and a test pins it;
- `Working/database/schema.py` (two tables, additive);
- `webui/server/cross_routes.py` (new) and one `include_router` line in `webui/server/app.py`;
- `webui/client/src/api/cross.ts` (new);
- `webui/client/src/explore/CensusCard.tsx` (new) plus its one mount line;
- `scripts/thesis/b4_cross_channel.py` (new);
- tests: `tests/test_cross_census.py`, `tests/test_cross_census_nulls.py`, `tests/test_webui_cross_census.py`,
  `tests/test_b4_script.py`;
- smoke: `webui/smoke_pages/zzzzzzzzzzz_w2_xc_s1.json`.

### Core (`Working/cross_census.py`, no UI imports)

- **`census_events(conn, source_file, detector)`.**
  - Selects through `load_sweep_detections`, filtered to the detector's exact template name.
  - It is **full** only if every active channel has one real run. Otherwise it returns which channels lack one and
    the census refuses, with those words.
  - Each event: detection id, recording id, channel, fs, start/end, **onset** and `onset_from` (label or
    steepest-fall).
  - Refuses the held-out file.
- **`co_occurrences(events, ceiling_s)`.** Pure: every cross-channel pair of events with |onset difference| ≤
  ceiling.
- **`measure_pair(x, y, onset_a, onset_b, fs, rule, consts)`.**
  - Takes the onset window on both channels' same samples and the restricted-lag peak.
  - Runs `chance_null` with the restricted lag on the partner channel, and the floor check (`dataset_floors`, units by
    `recordings.units`).
  - Returns lag_s, r, chance summary, floor and amplitude ratio.
  - One function, so Measure (S4) reuses it.
- **`census_bin(pair, layout, rule)`** applies D9/D16 and returns the bin and `cross_pack`.
- **`instants(pairs)`** uses union-find over copy pairs, giving breadth, packs spanned and the common-mode mark (D7).
- **The nulls** (D18), each a small function with a fixed seed derived from the hash: `rotation_counts`,
  `timetable_scan` plus `timetable_null` (the random-time lag pool), `breadth_null`, `shared_driver_null`. BH comes
  through `corrected_levels`.
- **`census_hash(...)`.** Canonical JSON of: source file, detector, the real run ids and their `finished_at`, the
  rule, the layout's packs, the constants and a `CENSUS_VERSION`.
- **`is_stale(conn, census_row)`** recomputes the hash from today's inputs and returns which input changed.
- **`run_census(conn, source_file, detector, *, progress, cancel)`.**
  - Computes everything first, then writes in **short transactions**. fixup-dblock's lesson: holding the write lock
    across null computations made concurrent writes fail with `database is locked`.
  - `progress(done, total, message)` is called per pair-batch, with real counts.

### Storage (`schema.py`, additive, idempotent)

- **`cross_census`**: id, source_file, detector, hash (unique), run_ids_json, layout_json, rule_json, consts_json,
  status, summary_json, null_path, created_at, finished_at, actor.
  - `summary_json` holds, per within-pack pair: n, the null's mean and 95th percentile, p, q, timetable L, count,
    median lag, MAD, p and q.
  - It also holds the bin counts, breadth rows and per-pack-pair shared-driver numbers.
- **`cross_cooccurrence`**: id, census_id, det_a_id, det_b_id, rec_a_id, rec_b_id, onset_a_s, onset_b_s, lag_s, r,
  bin, cross_pack, instant_id, common_mode, chance_json, floor_json, amplitude_ratio.
  - Index on (census_id, bin) and (census_id, rec_a_id, rec_b_id).
- Machine rows only: nothing here is a verdict.

### Bridge (`webui/server/cross_routes.py`)

- **`POST /api/cross/census {source_file, detector?}`** starts a `cross_census` job (`start_job`) with real
  progress.
  - 423 on the held-out file.
  - 422 when the detector is not full on the recording, in words: "drop_detection_v5 has a real run on 2 of 16
    channels".
- **`GET /api/cross/census?source_file=&detector=`** returns the latest census.
  - Fields: summary, hash, `stale` and `staleWhy`, `layoutKnown`, the rules in words, and the detectors offered, each
    `full` or with its reason.
  - Or `{census: null}`.
- **`GET /api/cross/census/{id}/cooccurrences?bin=&a=&b=&instant=&limit=&offset=`** returns rows, for S7.

### Client (`CensusCard.tsx`)

- States: **none** (a Run census button), **running** (real progress and estimate), **done**, **stale** (why, plus
  Re-run).
- A detector dropdown: non-full detectors are listed disabled, with their reason.
- The bin counts. Every within-pack pair's row shows co-occurrences against its null, p and q, the timetable lag and
  count with p and q, plus the breadth table, the shared-driver rows and the hash.
- "Packs not set — layout unknown" when `layoutKnown` is false.
- Every number's rule comes from the bridge.

### Thesis script (`scripts/thesis/b4_cross_channel.py`)

- `--db` (opened `mode=ro`), `--out docs/thesis/data/ch10_b4/`. Never reads M4.
- Reads the latest census per source file and writes `b4_summary.json`, `b4_pairs.csv`, `b4_bins.csv`.
- Figures (matplotlib): per-pair lag histograms with their null, bin counts per recording, and lag against distance
  **only when positions are known** (otherwise `b4_lag_vs_distance_NOTE.txt` says why).
- Each figure carries the census hash.

### Tests

Synthetic multichannel recordings in a temp `init_db()`, with planted events:

| Case | Planted | Expected |
|---|---|---|
| (a) | the same waveform at lag 0 on all four packs | an artifact instant, cross-pack, common mode, breadth 16 |
| (b) | an event that arrives on the pack's next channel 12 s later, 30 times, within one pack | propagation pairs, a timetable at L = +12 s that beats its null after BH |
| (c) | the same planted wave between packs | never propagation: copy → artifact, non-copy → shared_driver |
| (d) | independent Poisson events | co-occurrence excess p not small, timetable p not small |
| (e) | an unassigned 4-channel recording | propagation allowed, layout-unknown flag |
| (f) | | onset recovery: a padded start → the steepest fall, said in `onset_from` |
| (g) | | `cross_correlation_peak` default unchanged; `max_lag` restricts |
| (h) | | the hash is stable, and `stale` when a run, the rule or a pack changes |
| (i) | | a held-out file is refused |
| (j) | | a non-full detector is refused in words |
| (k) | | the job reports done/total |
| (l) | | the script writes its files from a synthetic census |

**Timing target:** ≤ 2 min for 16 channels × 721 h at 1 Hz with ~700 events, including every null, on synthetic
data. Report the measured time.

**Stop and report if:**
- `load_sweep_detections` cannot be filtered to one template without rewriting it;
- the onset label is nowhere recoverable and the steepest-fall rule misplaces planted onsets by more than 5 s;
- the step-cache root is wrong for the null `.npz`.

---

## S2 — the overlay page: the shell, the timeline, zoom, channels and lanes (wave 1)

**Files:**
- `webui/client/src/explore/CrossChannelPage.tsx` (rewritten as the shell);
- `Overlay.tsx`, `overlayModel.ts`;
- new `explore/CrossTimeline.tsx` and `explore/ChannelMenu.tsx`;
- `explore.css` (append-only);
- `crossModel.ts` and `crossScale.ts`: delete what becomes dead, with its tests;
- `tests/test_webui_cross_page.py`, `tests/test_webui_site_x_cross.py`, plus new `tests/test_webui_cross_shell.py`;
- smoke: `zzzzzzzzzzz_w2_xc_s2.json`, and the three existing cross-channel smoke units (retire or re-point states).

### Remove

- the stacked view, its y-scale menu and its align seg;
- the window dropdown, ‹ ›, "span n of N" and `?pad=` / `?window=motif-n`;
- the disabled "lag computed on whole channel" menu;
- "Open design questions";
- the Classification tiles card (returns as S4's panel).

Tests that encode removed behaviour are updated, and **the commit message says which and why** (CLAUDE.md rule 2).

### Keep

- `?t0=&t1=` (now the domain);
- click and shift-click to bold, all and none;
- the brush box and the shared action strip (`SpanActionStrip`) with its align-aware channel rules;
- the detections chip (every channel's detections, as the overlay already draws);
- *Apply a template across these channels*;
- the held-out `LockedCard`;
- the not-found empty state;
- edge links from Library (`?t0&t1&family&grouping` open that window with the edge's two channels bold).

### Build

- **The shell.** URL state:
  - `?t0&t1` (domain), `?channels=` (ids in view, in order), `?bold=`, `?pos=` (lane offsets), `?yz=` (y-zoom);
  - the reference is the path id (`explore/cross-channel/{id}`), and **make reference** (on a name's menu) navigates
    to the new id, keeping the rest;
  - named slots, as in "Mount lines" above.
- **The timeline strip (D12).**
  - Reuse `Overview` for the **first bold channel**, else the reference; its blue box is the domain.
  - Its coverage ribbon already shows human artifact verdicts. Add nothing to `Overview` except, if needed, an
    append-only optional prop (S7 adds candidate ticks the same way).
- **The detail plot.**
  - Envelopes per channel in view via the existing per-channel window read (`getWindow`), in parallel. **No lag fetch.**
  - **Wheel zoom about the cursor** and pointer pan, as `SpanView.tsx:158`, writing `?t0&t1` (debounced), with the
    minimum span from `util.MIN_SPAN_S`.
  - Any domain from about a minute to the whole recording.
- **Lanes (D14).**
  - Drag a channel's name or trace vertically to move its baseline; the block grows or shrinks to fit every lane.
  - Double-click snaps the channel onto the first bold channel's baseline. **Reset lanes** undoes it.
  - The shared gain stays, plus one **y-zoom** control.
  - A channel gets its own gain (÷N) only when it cannot fit, as today.
- **Channels.**
  - × on a name removes it from the view.
  - **+ channel** lists this recording's channels grouped by pack (`GET /api/layout`, S0). "From another dataset…"
    is shown **disabled**, with its reason: "arrives with S9".
  - **Pack chips** (A B C D, or "unassigned") toggle a whole pack in or out.
  - The default is every channel of the recording; at most 24 series, refused in words past that.
- **Align by lag** is disabled until S4, with its reason on the page: "measure a span first: lags come from Measure".
  The lag beside each name is blank until then.

**Tests:**
- The shell's URL model is a pure `.ts` with Node tests, as the repo's other pure models do (MEMORY: a pure `.ts` may
  import a pure sibling with `.ts`): domain from the wheel, clamped, minimum span; lane offsets, snap, reset; add,
  remove and pack toggles; the 24 cap; make reference keeps the parameters; edge links open both channels bold.
- Venv tests for anything served.

**Smoke states:**
- the default overlay (every channel, the strip and box);
- a narrowed domain via `?t0&t1`;
- a lane moved via `?pos`;
- a pack toggled off;
- a channel removed;
- an edge link;
- the held-out card;
- 16 channels × the whole of M2_aug painted, with the elapsed time printed in a `data-` attribute.

**Target:** first paint ≤ 2 s for 16 × 721 h, measured on the sandbox by the manager. Without S6's pyramid it may
miss; say what you measured.

---

## S3 — packs and positions in Settings › Channels & events (wave 1)

**Files:**
- `webui/client/src/settings/ChannelsEventsPage.tsx` (three columns);
- `webui/client/src/api/settings.ts` and `fixtures/settings.ts` (append-only key helpers);
- the server-side validation for page `channels-events`. Find where that page's PUT is validated and append there;
- `tests/test_webui_layout_settings.py`;
- smoke `zzzzzzzzzzz_w2_xc_s3.json`.

**The work:**
- **pack**: a select of A–H plus "unassigned", the M2 default shown as a placeholder.
- **x mm**, **y mm**: numbers, relative to the pack's origin. The origin is whichever channel sits at (0, 0); there is
  no extra key.
- Values stage and save like every other cell on that page (the audited path).
- The bridge refuses a pack that is not a short token, or a position that is not finite or lies outside ±10,000 mm,
  with the reason.
- A short note on the page: "positions are millimetres within a pack, read off the photos; they feed Cross-channel's
  pack map and lag against distance."

**Tests:** round-trip through `channel_layout` (S0); refusals in words; the M2 default not saved unless edited.

---

## S4 — Measure on demand and the median-reference view (wave 2; after S1 and S2)

**Files:**
- `Working/cross_census.py` (append `measure_span`; it reuses `measure_pair` and `census_bin`, one definition);
- `webui/server/cross_routes.py` (append);
- `webui/client/src/api/cross.ts` (append);
- new `explore/MeasurePanel.tsx` plus its mount line;
- `Overlay.tsx` (align and lag labels fed by Measure);
- tests `tests/test_cross_measure.py`, `tests/test_webui_cross_measure.py`;
- smoke `zzzzzzzzzzz_w2_xc_s4.json`.

**The work:**
- **`POST /api/cross/measure`** with body `{reference_id, channel_ids, t0, t1, detrend}`. Channel ids are the bold
  channels, all from the reference's recording.
  - It is a short job with real progress.
  - It refuses a box longer than 2 h or more than 8 channels (28 pairs), in words.
  - For every bold pair it returns:
    - lag_s (restricted ±50 s) and r on the detrend chosen;
    - the as-recorded reading and `drift_suspect`, as the window route does today;
    - the census bin and cross-pack flag;
    - the **span's own null**: K = 100 windows of the box's length on the same two channels at random other times, ≥ 60
      s away, never over a human-marked artifact, at the 95th percentile;
    - the breadth among the bold channels.
  - Every result carries `"looked_for": true`.
- **`MeasurePanel`.**
  - A table of pairs: lag, r, bin, beats its null (percentile), drift mark. A **looked for** badge, with the tip "a
    span picked by eye; B4's numbers come from the census".
  - The detrend control (raw / linear / cubic) moves here.
  - Edge mode (opened from a Library edge): the first row is the edge's stored reading from the **unchanged**
    `GET /api/cross/{id}` route, measured as recorded, so the edge still recomputes (fixup-W).
- **Align by lag.** Lags against the reference from the last Measure. The reference must be bold, else the toggle
  says so. Lags show beside the names.
- **Median reference (D7).**
  - The route `GET /api/cross/{recording}/median-ref?t0&t1&px&channels` returns, per channel, the envelope of
    (x − its own median over the domain) − (the across-channel median of those, per sample).
  - A **median reference** toggle in the plot header swaps the envelopes in, with a tip: "an event that vanishes here
    was common to all channels."
  - Same domain cap as Measure.

**Tests:**

| Case | Planted | Expected |
|---|---|---|
| planted lag | a 12 s lag | found; an unrelated pair's span is not called propagation by its own null more often than its percentile allows |
| common mode | a common-mode event | vanishes under the median reference |
| limits | | the caps are refused in words |
| edge | | edge mode reproduces the stored edge |
| flag | | `looked_for` is on every row |

**Target:** ≤ 5 s for 8 channels × 2 h at 1 Hz on synthetic data.

---

## S5 — the by-instant artifact queue and the marks (wave 2; after S1)

**Files:**
- `Working/review/instant_queue.py` (new);
- `Working/review/queues.py` (append a case to `_resolve`);
- the Review bridge route that starts a queue (append);
- `CensusCard.tsx` (append one button);
- `explore/SpanActions.tsx` (two buttons, Cross-channel origin only);
- `webui/server/explore_routes.py` (append the mark route);
- the vocabulary seed (additive);
- `Working/library/matching.py`: **two lines** in `family_recurrence`, calling `instant_queue`;
- tests `tests/test_instant_queue.py`, `tests/test_webui_instant_queue.py`, `tests/test_webui_cross_marks.py`;
- smoke `zzzzzzzzzzz_w2_xc_s5.json`.

**The work:**
- **The queue.** Source kind `suspected-artifact-instant`, one per census, started from the card: "Send n suspected
  artifacts to Review".
  - **Items are instants**: cross-pack ones first, then by breadth, largest first.
  - The card draws every channel of the instant on one true-mV axis; reuse the suspected-artifact card's drawing.
  - A verdict (`artifact` / `interesting` / `not_interesting` / `unsure`) writes **one annotation per channel over
    that channel's event span**, source `cross_channel_instant_review`. Each carries a note saying the instant was
    flagged, and by what: channels, lags, r, breadth, cross-pack, census hash.
  - Re-judging re-describes in place, as `artifact_queue` does, and undo withdraws.
- **The Library link (D21).** `instant_queue.members_confirmed(conn, member_ids)` returns the members whose span is at
  least 50 % covered by an `artifact` verdict of this source. `family_recurrence` adds them to the excluded set with
  one call. Recurrence's rule text names it.
  - Test: a member under a confirmed instant leaves *excluding artifacts*. A member under an unjudged or rejected
    instant stays.
- **The marks (D19).** On Cross-channel's strip, **Mark as propagation** and **Mark shared driver** act on the bold,
  unshifted channels and the box.
  - Each writes, per channel, an annotation over the box with verdict `interesting`, the tag
    `cross_channel:propagation` or `cross_channel:shared_driver`, and a note: lag, r, channels, "looked for" or the
    census hash.
  - Source `explore-cross-channel-mark`, through the human door.
  - Seed the `cross_channel` category and its two values additively and idempotently, where the existing categories
    are seeded.

**Tests:**
- items ordered as stated;
- one verdict → n annotations, and never a machine row;
- undo;
- the Library exclusion;
- marks write the tag and refuse shifted channels;
- the vocabulary seeds idempotently;
- the held-out file refused.

---

## S6 — the envelope pyramid (wave 2; bridge only)

**Files:**
- `webui/server/decimate.py`, `webui/server/corpus.py` (`window` reads the pyramid);
- `tests/test_webui_envelope_pyramid.py`.

**The work:**
- Per channel, min/max levels at 1 s, 10 s and 60 s buckets, in samples from fs.
- Built lazily on the first long read, **streamed in chunks** (MJu26a's 10 Hz file is 2.9 GB for 16 channels against
  ~1.3 GB of free RAM).
- Cached at `<runtime root>/cache/envelope/<sha1(npy_path, mtime)>.npz`, beside the coverage cache, so it is sandbox
  safe.
- `window()` uses the coarsest level with at least 2 × px buckets in the domain. A short domain reads the raw
  samples as today.
- **Exactness test:** the per-pixel min and max from the pyramid equal those from the raw samples whenever bucket
  edges align, and otherwise lie within one level-bucket of the raw.

**Target:** a whole-recording read of 16 channels × 721 h at 1 Hz is ≤ 1 s warm and ≤ 5 s cold, on synthetic memmaps.

---

## S7 — candidates: the list, ‹ › stepping, ticks on the strip and family labels (wave 3; after S1, S2)

**Files:**
- new `explore/CandidateBar.tsx` plus its mount line;
- `Overview.tsx` (an append-only optional `marks` prop);
- `cross_routes.py` and `api/cross.ts` (append a `family` field and `?grouping=`);
- tests `tests/test_webui_cross_candidates.py`, plus a pure `.ts` model test;
- smoke `zzzzzzzzzzz_w2_xc_s7.json`.

**The work:**
- A bar above the plot: **‹ n of N ›**, plus filters for bin (propagation candidates, artifacts, shared driver,
  independent), pack pair and family.
- Order: within-pack propagation candidates by r, then artifact instants by breadth, then shared driver.
- Stepping sets the domain to the pair's onset window padded to 10 min, bolds the pair, and marks both onsets.
- The strip shows a tick per candidate in the current filter.
- **Family labels (D16).** A census event that overlaps a Library member by ≥ 50 % of the event takes the member's
  family in the chosen grouping.
  - The default is the grouping Library's own default resolves to (`library.py::_resolve_grouping`): g-11 today.
  - The grouping is selectable. Recordings with no members show "no Library members on this recording".
  - The old *Classify every F-xx member in Library* card's job stays reachable as a link: "Classify F-xx's members in
    Library ↗".

**Tests:** ordering, the filters, family overlap ≥ 50 %, stepping's domain, an empty census state.

---

## S8 — the pack map and lag against distance (wave 3; after S1, S3)

**Files:**
- new `explore/PackMap.tsx` and `explore/LagDistance.tsx` plus their mount lines (slot `space`);
- `cross_routes.py` (append a lag-vs-distance read, if the census summary does not already carry it);
- tests and smoke `zzzzzzzzzzz_w2_xc_s8.json`.

**The work:**
- **PackMap.**
  - One small SVG per pack; electrodes are dots at (x, y) mm in the overlay's colours.
  - Drag a dot (snap 1 mm) or type into its popover. The value saves through the audited settings PUT on drop: one
    audit row per drop, debounced.
  - The origin channel at (0, 0) is marked.
  - Click is bold, synced with the overlay both ways.
  - With no positions, the dots sit in a row with "drag to place (millimetres from the photos)".
- **LagDistance (D11).**
  - Points: every within-pack co-occurrence's lag against its pair's distance, coloured by bin.
  - A band shows the central 95 % of the timetable null's lag pool, pooled. With fewer than 50 pooled lags, no band,
    and it says so.
  - A line through the origin (slope = 1 / speed) is drawn only through propagation pairs that pass BH. It prints the
    speed in mm/s, and draws no line with fewer than 3 such pairs.
  - "Needs positions" until every channel of a pack has x and y.

**Tests:** distance from positions; the band rule; the no-line rule; a drop writes one audited setting.

---

## S9 — channels from other datasets (wave 3, merged last)

**Files:**
- the shell (series model);
- `ChannelMenu.tsx` (enables "From another dataset…");
- `Overlay.tsx` (series `recording`, `offset_s`, `unit`; one gain per unit group);
- tests (a pure `.ts` model) and smoke `zzzzzzzzzzz_w2_xc_s9.json`.

**The work (D13):**
- **The menu.** Pick a dataset (never the held-out one, which is refused) and a channel.
- **The offset.** The default aligns by wall clock when both datasets have a start time in Settings › Datasets,
  otherwise by time since each recording's start. Each foreign lane has an offset handle (drag its name chip
  sideways, or type +Δ h).
- **What a foreign lane does and doesn't do.**
  - It carries a badge, "other recording — no shared clock".
  - It is excluded from Measure, align, Send and Mark, each excluded control saying why.
  - It is drawn on its own gain group when its unit differs, so non-mV series (°C, %RH, kg) work from the start.
  - URL: `?ext=<recording_id>@<offset_s>,…`.
- Environment series are **not** registered here (`docs/prompts/fixup/future/Z-environment-series.md`). This slice
  only makes the overlay able to hold them.

**Tests:** wall-clock against elapsed defaults, offset math, exclusions, the held-out file refused.

---

## Waves (D23)

| Wave | Slices, in parallel | Merge order | Notes |
|---|---|---|---|
| 0 | S0 (manager, direct) | — | full suite (core) |
| 1 | S1 · S2 · S3 | S3 → S1 → S2 | S2 keeps S1's mount line in the census slot |
| 2 | S4 · S5 · S6 | S6 → S5 → S4 | S5 runs the full suite (`matching.py`) |
| 3 | S7 · S8 · S9 | S7 → S8 → S9 | S9 last: it changes the shell's series model |

## After each merge (the manager)

- The project bridge on **8765** runs the real database with no reload. A merge with Python changes needs a restart,
  so **tell the researcher before restarting it**, as their standing rule says.
- After S1 merges, run the census, through the page on 8765, on M2_aug, M2_concat, CO_fs2 and LM_fs2. Run it on
  MJu26a_fs2, SH_fs2 and SO_fs2 once the researcher's v1 runs exist.
- Then run `scripts/thesis/b4_cross_channel.py` against a **bridge backup** (`--db-source`: a plain copy of the live
  database misses its WAL).
- Update `docs/rq_roundB/B4-cross-channel.md` and RQ6's log with the numbers.
- After S5, send each census's suspected artifacts to Review. **The researcher judges them**; nobody else writes those
  verdicts.

## Stop and report (any slice) if

- the work contradicts a decision in the decisions note;
- a slice you depend on is not in your base;
- you need a file another slice owns;
- you need a new dependency;
- you have round-tripped the same failing test for more than a third of your time.

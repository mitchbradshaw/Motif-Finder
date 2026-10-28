# xc-S1 — the census: core, storage, job, read routes, the B4 card and the thesis script

Branch `worktree-agent-a043f90b4de2c0702`. The prompt is `docs/prompts/changes/cross-channel-explorer.md` (S1).

## In plain words

When two electrodes show activity at about the same time, it can be the wiring (one disturbance seen everywhere at
once), the fungus passing a signal along (it arrives next door a little later, by the same delay each time), or
coincidence. The census now looks at **every** event the detector found on **every** channel, with nothing picked by
eye. For each pair of events that start within 50 s of each other on two channels it measures the delay and the shape
match, and puts the pair in a bin. Then, like checking whether two people's diaries share a dinner date more often
than chance would allow, it reshuffles each channel's events in time a thousand times and asks how often the same
count turns up by luck. B4's numbers come from this card and the thesis script. Nothing has been run on the real
database yet: that is the manager's step after the merge.

## Fix round (the critic, 2026-10-28)

In plain words: two of the critic's findings could have made B4 look more significant than it is.
- **The burst bug.** When one event on a channel was followed by a burst of three on its neighbour, the timetable
  counted the same measured delay three times. It was like counting one train three times because three passengers
  got off it.
- **The common-mode leak.** A pair of electrodes caught up in one shared-ground instant could still be read as
  propagation.

Both are fixed, with a test each. The other items make the census say more about what it is.

Red `72ea275` (conda, 11 failed, 35 passed); green `cacdb8a`. These **supersede the matching items under Assumed
below**:

| # | Finding | What the census does now |
|---|---|---|
| 1 | Duplicate timetable lags | **One lag per distinct measured window** (`timetable_inputs`). I chose dedupe over re-centring each pair's window on its own onset difference: D16 fixes the window to the earlier onset, so the pairs that share it are one measurement. The timetable's n is the count of distinct windows, and its pool is drawn from those windows. Pinned by a burst of 3 on CH2 after one event on CH1, twice: 6 co-occurrences, 2 timetable lags. |
| 2 | Common-mode instants leaking into propagation | After `instants()`, every pair whose two events sit in one instant **is an artifact**, marked `absorbed`. Its own bin is kept as `own_bin` in `floor_json`. It never feeds a timetable or a propagation count. The card says how many pairs joined an instant. Pinned by the critic's exact example: A1≈B1, A2≈B1, A1–A2 at 1.5 s and r 0.97. |
| 3 | The breadth null was a random-instant null | **Now under rotation**, on the excess test's own joint draws (same seed, same K). For each draw it takes a random rotated event and counts 1 + the other channels with a rotated onset within ±50 s (circular). **Stated deviation:** an instant cannot be re-formed exactly under rotation, because a copy needs the waveform match and a rotation moves only onsets. So the null's neighbourhood is the co-occurrence window, which is looser than a copy, and that makes it conservative. The card prints the null's words under the instants table. Two-channel copies still beat it easily, because chance coincidence within ±50 s really is rare at ~43 events per channel; that is not an artefact of the null. Pinned: three coinciding single events never meet under rotation. |
| 4 | The hash missed the floor and the human artifact spans | `census_inputs` adds `floor` (`dataset_floors`: mV and whether it was set) and `artifact_spans` (a count and a sha256 of the channels' human-marked artifact spans). `is_stale` names which one changed, and says "an input changed" whenever the hash differs for any other reason. The inputs are kept in `summary.inputs`. |
| 5 | A short timetable pool was tested | `timetable_test`: a pool short of 2,000 lags is **not testable**, with no p or BH and its reason; the card shows the reason. |
| 6 | The thesis script did not check freshness | It calls `cross_census.is_stale` on the read-only connection. `stale` and `staleWhy` go into `b4_summary.json`, `stale` and `stale_why` into both CSVs, and "STALE: …" onto every figure. A census whose freshness cannot be checked is marked stale, with the error. |
| 7 | The bin badges had no null beside them | The card heads them "**Per co-occurrence classifications** — what each pair looked like, with no null of their own. The claim is the co-occurrence excess and the timetable tests below". The tip is `rules.bins_note` from the bridge. |
| nit | An unmeasurable pair counted as a shared driver | It is a sixth census bin, **`unmeasured`**, on any packs. |
| nit | Rotation counted pairs linearly across the wrap | Rotation draws count with **circular** distance (`count_co(…, period=T)`). Observed counts stay linear: the real recording does not wrap. |
| nit | The estimate weighted unlike steps alike | The card says "roughly … left (the steps differ in cost)". |

**Known limitation, kept as designed (X1, the researcher's choice):** the timetable pool measures the partner channel
at random times, which mostly hold no event. The critic's suggestion, recorded for later, is a pool drawn from the
partner's own *other* events, which would ask whether the lag is specific to these pairings.

One red test was corrected in the green commit. `test_fix3`'s third channel sat at 20000 s, where it can legitimately
meet the others under rotation, so it now coincides with them. That was a test bug, not a code one.

**Green, after the fix round:**

| Files | Interpreter | Result |
|---|---|---|
| `test_cross_census.py`, `test_cross_census_nulls.py`, `test_b4_script.py`, `test_cross_channel*.py` (4), `test_channel_layout.py`, `test_import_boundaries.py`, `test_candidate_events.py` | conda, `-n 2` | 186 passed |
| `test_webui_cross_census.py`, `test_webui_channel_layout.py`, `test_webui_cross_channel.py`, `test_webui_cross_page.py`, `test_webui_cross_window.py`, `test_webui_site_x_cross.py`, `test_webui_suspected_artifact.py`, `test_webui_jobs.py` | webui/.venv | 75 passed |

`tsc -b` and `vite build` pass.

**Timing re-measured:** 22.2 s on the same synthetic 16 channels × 721 h (735 events, 1,229 co-occurrences). The planted
+12 s pair now reads 21 distinct windows, L 12.0 s, p 0.001, passing BH.

## Assumed (every choice the prompt left open)

(Items 2, 8 and 9 are superseded by the fix round above: unmeasurable pairs, the breadth null, and the timetable's
lags and pool.)

1. **Base.** The worktree was cut at `a399e4c`, 37 commits behind `main`, without S0 or the prompt. The branch had no
   commits of its own and a clean tree, so I moved it to `main` (`git reset --hard main`, which is not a merge or a
   branch switch). Then I cherry-picked S0's fix round, `760a718` and `9e9d77c`, as the manager asked
   (`dbf7c1c`, `3c25b3b` here). Both S0 test files pass after the picks: `test_channel_layout.py` 16 passed (conda) and
   `test_webui_channel_layout.py` 5 passed (venv).
2. **A copy** is the artifact rule in full: |lag| ≤ 1 s, |r| ≥ 0.98, beats chance and is over the floor
   (`bin_for(...) == artifact`). A cross-pack pair that is not a copy is `shared_driver`. An unmeasurable cross-pack
   pair (flat window) also counts as `shared_driver`, because it is a co-occurrence that is not a copy.
3. **Pack unknown** (S0's `same_pack` → None): the bin `pack_unknown`, a fifth census bin, with `cross_pack` NULL. A
   copy is still `artifact` on any packs. The card prints the count beside "packs not set — layout unknown".
4. **Pair orientation.** `a` is the event on the lower recording id, so a lag reads as b relative to a.
5. **The waveform null** uses `CensusConstants.waveform_k` (100, X5) through `dataclasses.replace(rule, null_k=…)`. The
   percentile stays the rule's Settings key (95).
6. **Rotation is joint.** Each draw rotates every channel, with every pair of channels at least 1 h apart on the circle
   (drawn exactly, not by rejection). So each pair's relative shift is ≥ 1 h, as D18 says, and the per-pair, per
   pack-pair and overall counts all read the same draws. A recording shorter than n_channels × 1 h is refused in
   words.
7. **The shared-driver null** counts every cross-pack co-occurrence under rotation, while the observed count holds
   non-copies only. This is conservative.
8. **The breadth null.** One distribution per recording: at K random instants, 1 + the number of channels other than
   a random anchor with any onset within ±50 s. Each instant's p is read against it.
9. **The timetable** is tested only when a pair has ≥ 2 non-copy, measurable co-occurrences (`timetable_min_n`, a named
   constant). Its pool comes from those co-occurrences' onset windows on `a` against `b` at random other times
   (≥ 60 s away, never over a human-marked artifact of `b`).
   - `L_s` is reported as the **median of the lags inside the best ±2 s window**, not the window's centre. Otherwise
     a planted +12 s reads as +14.
   - Ties go to the smaller MAD.
   - `window_centre_s` is stored too.
10. **The BH "q" is the level a test was held to** (`corrected_levels`' output), None when it fails. I did not compute
    adjusted q-values, which would have needed a second BH. Each family is corrected separately per recording:
    excess (all within-pack pairs), timetable (testable pairs), breadth (instants), shared driver (pack pairs).
11. **Onset labels.**
    - `detections.meta_json`'s `label` (`onset=<i>`) is read when present.
    - I did not read the step-cache payload: no run-id-keyed path to it was clear, and the real v1 runs have neither
      that nor `meta_json`.
    - The steepest fall puts planted onsets within 5 s (the test pins it), so it is the method in use. `onset_from` is
      stored per event and counted in the summary.
12. **`wavelet_encoded*` is never a census detector.** The detector list shows it disabled, with the reason.
13. **The hash** includes the channels-events page's `settings_updated_at`, as the manager asked. `is_stale` tells the
    two causes apart: "a channel's pack changed" and "the page was saved since (packs unchanged)".
14. **One row per hash.** Re-running the same inputs deletes and rewrites that census's own rows.
15. **A census job already running** for the same file and detector gives 409, and `GET` returns it as `running` so a
    reload picks the job up again.
16. **Audit.** A finished census writes an audit row of kind `explore`, a new kind.
17. **Bridge refusal.** The bridge refuses the held-out file with 423 by name, whatever the lock says, because the core
    refuses it by name, as `candidate_events` does.

## Files

Created:
- `Working/cross_census.py` — the core.
- `webui/server/cross_routes.py` — the three routes.
- `webui/client/src/api/cross.ts` — the typed reads and the start call.
- `webui/client/src/explore/CensusCard.tsx` — the card.
- `scripts/thesis/b4_cross_channel.py` — the thesis script.
- `tests/test_cross_census.py`, `tests/test_cross_census_nulls.py`, `tests/test_webui_cross_census.py`,
  `tests/test_b4_script.py`.
- `tests/_cross_census_synthetic.py` — a fixture helper, not in the prompt's list; the four test files share it.
- `webui/smoke_pages/zzzzzzzzzzzz_xc_s1.json`.
- this report.

Modified, **append-only** (shared):
- `Working/cross_channel.py`: `SHARED_DRIVER` (outside `BINS`), and an optional `max_lag=None` on
  `cross_correlation_peak` and `chance_null`. Three lines change inside the two functions (the signature, the
  restriction, the pass-through). The default is the old behaviour, and a test pins it.
- `Working/database/schema.py`: `_CROSS_CENSUS_SCHEMA` and `_migrate_cross_census_tables`, plus one call at the end of
  `init_db`.
- `webui/server/app.py`: one import, and one `include_router(cross_router)` placed **before** `explore_router`.
  `/api/cross/{recording_id}` would otherwise take `/api/cross/census`, so this is an insertion, not an append at the
  end.
- `webui/server/jobs.py`: a seventh entry in `KINDS`, `cross_census`. This file is not in the prompt's list; `start_job`
  refuses an unknown kind.
- `webui/client/src/api/jobs.ts`: one `KIND_LABEL` entry.
- `webui/client/src/explore/CrossChannelPage.tsx`: one import and one mount line, `<CensusCard sourceFile={data.file} />`,
  below the plot (above `ex-cross-bottom`).

Out of scope, with the reason:
- `tests/test_webui_jobs.py`: its fixed set of KINDS gains `cross_census`. This is the behaviour the slice deliberately
  changes.
- `docs/rq_roundB/B4-cross-channel.md` (What is known, the needed-steps row, Log) and
  `docs/rq_roundA/RQ6-recurrence-across-channels.md` (one Log line): the CLAUDE.md rule on research-question files.

## Tests

- **Red:** `28d0129`.
  - conda: three collection errors (`No module named 'Working.cross_census'`, then `b4_cross_channel`).
  - venv: `test_webui_cross_census.py` 4 failed, 2 passed. The two that passed (an unknown census 404, and the old
    window route) answer today without the router.
- **Green:**

  | File | Interpreter | Result |
  |---|---|---|
  | `test_cross_census.py` + `test_cross_census_nulls.py` | conda | 32 passed |
  | `test_b4_script.py` | conda | 2 passed |
  | `test_webui_cross_census.py` | venv | 6 passed |
  | `test_cross_channel.py`, `_chance`, `_simultaneous`, `_window`, `test_channel_layout.py`, `test_import_boundaries.py`, `test_candidate_events.py` (+ the S1 files) | conda, `-n 2` | 174 passed |
  | `test_webui_cross_channel.py`, `_cross_page`, `_cross_window`, `_site_x_cross`, `_channel_layout`, `_suspected_artifact`, `_jobs`, `_jobs_board`, `_plot_domain` | venv | all passed |
  | `test_library_schema.py`, `test_review_schema.py`, `test_legacy_detections_migration.py`, `test_motif_migration.py`, `test_night_disc.py`, `test_site_runs_scope_link.py` | conda | 98 passed |

  - `test_webui_site_x_cross.py` first failed on my smoke states, which lacked `?view=`. They now carry
    `?view=overlay`.
  - The full suite was not run (the manager runs it: S1 touches `schema.py` and `cross_channel.py`).

What the tests pin:

| Case | Test | Pins |
|---|---|---|
| (a) | `test_a_…` | one waveform on all 16 channels at three instants: 360 artifact pairs, three instants of breadth 16 spanning A–D, common mode |
| (b) | `test_b_…` | CH1_A1 → CH2_A1 at +12 s, 30 times: 30 propagation; the pair's excess p ≤ 0.01 and passes BH; timetable count 30, L 12 ± 1 s, MAD ≤ 1, p ≤ 0.01, passes BH |
| (c) | `test_c_…` | between packs A and B: copies are artifact, the delayed ones shared driver, never propagation; the A·B shared-driver row beats rotation; the two-pack instants are common mode |
| (d) | `test_d_…` | independent Poisson events on 4 channels: every pair's excess p > 0.05 and no timetable p ≤ 0.05; overall p > 0.05 |
| (e) | `test_e_…` | an unassigned 4-channel recording: propagation allowed, "packs not set — layout unknown", no pack-unknown pair |
| pack unknown | `test_a_pair_with_exactly_one_unassigned_channel_…` | `census_bin` returns `(pack_unknown, None)`; a copy stays artifact; two unassigned channels are within-pack |
| (f) | two tests | the padded start becomes the steepest fall within 5 s, and `onset_from` says so; a stored `onset=` label wins |
| (g) | three tests | `cross_correlation_peak` and `chance_null` are unchanged by default; `max_lag` restricts; `SHARED_DRIVER` sits outside `BINS` |
| (h) | two tests | the hash is stable; one row per hash; stale with "rule" when a Settings rule changes (and fresh when it is put back), with "pack" when a pack changes, with "run" when a run is superseded and replaced |
| (i) | `test_i_…` | the held-out file is refused by `census_events` and `run_census` |
| (j) | `test_j_…` | the not-full refusal is in words, and the offered list carries the reasons |
| (k) | three tests | `progress` is monotonic and ends at done == total; status `done`; the `.npz` lies under the redirected `STEP_CACHE_ROOT`; the constants are recorded; a cancel writes nothing |
| (l) | `test_b4_script.py` | read-only (an `sqlite3.connect` spy and an unchanged mtime); `b4_summary.json`, `b4_pairs.csv` and `b4_bins.csv` carry the hash; the held-out census row is skipped by name; the figures are written; the distance NOTE replaces the figure without positions |
| nulls | `test_cross_census_nulls.py` | the p formula, the constants, rotation offsets ≥ 1 h pairwise and seeded, the too-short refusal, the counts, the timetable scan (never centred inside the artifact line), the timetable null and pool, the breadth null, BH through `corrected_levels` |
| routes | `test_webui_cross_census.py` | `census: null` before a run; 423, 422 in words and 404; the job runs to done == total; the census is read back with stale False; the rows can be filtered and paged; the old `/api/cross/{id}` still answers |

## Smoke states (`webui/smoke_pages/zzzzzzzzzzzz_xc_s1.json`)

All three are on `explore/cross-channel/4?view=overlay` (recording 4, M2_aug):

1. **`xc-s1-census-card-paints`.**
   - The census card is below the plot.
   - Its detector dropdown reads `drop_detection_v1`, and the Run census button is present.
   - It shows no error and no layout-unknown line (M2_aug's packs come from the names).
   - On a fresh sandbox it is `data-state="none"` with "No census of this recording by drop_detection_v1 yet".
2. **`xc-s1-detector-not-full-is-disabled`.**
   - Opening the dropdown lists `drop_detection_v5` disabled, reading "drop_detection_v5 has a real run on 2 of 16
     channels".
   - Check this on the real data: if v5's template name is not exactly `drop_detection_v5`, the option is named
     differently and the state fails on the selector, not on the behaviour.
3. **`xc-s1-run-census`** (it writes, so it sorts last).
   - Clicking Run census shows a progress bar that reads "N of M · message · about … left".
   - Within 4 minutes it shows the body: the five bin badges, the within-pack pair table, instants, the shared-driver
     table, and the census hash.
   - Worth a look on M2_aug: the number of co-occurrences, how many are common mode, and whether any within-pack pair's
     timetable passes BH.

Check by hand on CO_fs2 or LM_fs2 (I did not know a channel id there):
- the card should show "packs not set — layout unknown · 0 pairs … pack unknown";
- the pair table should list the six pairs under pack `unassigned`.

## Timings (synthetic)

`C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\ee7dfe78-0c27-48d6-91e6-dd2ef2948732\scratchpad\census_timing.py`
ran on 16 channels × 721 h at 1 Hz, with M2_aug's v1 counts (688 events) plus a 20-event +12 s timetable on CH1→CH2:
735 events in all, of which 10 are common-mode instants on all 16 channels.

- **The census took 19.9 s** with every null, against a target of ≤ 2 min. That covers 1,229 co-occurrences:
  1,140 artifact, 23 propagation, 54 shared driver and 12 independent.
- The planted pair reads L = 12.0 s, count 22 of 22 non-copy co-occurrences, timetable p 0.001 (passes BH), against a
  null mean of 4.0.
- The machine was loaded (the researcher's bridge was running).
- Measuring costs about 10–15 ms per co-occurrence, almost all of it the 100-window waveform null. A recording with
  10,000 co-occurrences would take about 2.5 min.

## What is left

- **The manager:**
  - the full pytest suite (S1 touches `schema.py` and `cross_channel.py`);
  - walk the smoke unit on a sandbox;
  - after the merge, run the census on M2_aug, M2_concat, CO_fs2 and LM_fs2 through the page;
  - then `scripts/thesis/b4_cross_channel.py --db <bridge backup>`;
  - and the B4 and RQ6 numbers.
- **M2_concat has no pack letters.** `channel_name` keys the M2 electrode names on `M2_aug*` file names only, so
  M2_concat's channels are `CH1…CH16`: its census is one unassigned pack, "layout unknown". Every within-pair is then
  "within pack", and nothing is ever a shared driver. If M2_concat has the same A–D electrodes, set its packs in
  Settings › Channels & events (S3) before reading its B4 numbers. I flagged this in the B4 file.
- **MJu26a_fs2, SH_fs2 and SO_fs2** have no v1 runs: the card says "This recording has no full census by
  drop_detection_v1: … has a real run on 0 of N channels".
- **Not done:** onset labels from the step-cache payload (see Assumed 11). The step-cache read is not implemented.
- **For S4:** `measure_pair` takes whole channels and an onset pair. Measure on a span needs a span-window variant, or a
  call with `onset_window_s` replaced through `CensusConstants`.
- **For S7:** `GET …/cooccurrences` filters by bin, pair and instant, and pages with limit/offset.

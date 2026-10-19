# discovery-coverage-and-gauge: report

WORKTREE: `C:\Users\mmebr\Documents\CNN\.claude\worktrees\coverage`
BRANCH: `changes/coverage` (base `0f2c394`)

## 1. Assumed

- **Extend works on plain template runs only.** Band, windowed and seed runs are refused with a sentence: their scope is more than their channels. A discarded run, a run still running, and a run with no finished channel are refused too.
- **"Same parameters" is decided against what the run actually executed.** The template's current steps go through `make_recipe` and are compared with the steps in the run's `configs` row, using the detection map's `steps_key`. A `rebind` template is first bound to the exemplar the run executed with.
- **The extend reuses the run's own null and section.** It takes the null from `params.null` (paired, params, draws) and the section from the run's member rows, not the current session's null or section. The added channels are therefore the same question as the first ones.
- **An empty `channels` list means every scope channel the run has not run on.** A channel outside the scope must still be a real channel of the recording.
- **Over the local ceiling, the extend is refused** ("apply the template as a new run and create a SLURM script"). There is no cluster extend.
- **A failed, cancelled or lost extend leaves the run `done` with `extendError`.** The row's line says what happened. It never turns the original run into `failed`.
- **Coverage also has a `discarded` state** (grey) for a discarded run's channels. It comes from the detection map's vocabulary.
- **The fires card's `ran: false` covers `not_run` only.** A failed channel keeps its zero row, because "failed here" already shows on the strip.
- **The gauge counts every `discovery_runs` row of the template**, including removed and discarded ones and every session. A verdict on a detection is a human verdict whatever became of the run. Carried rows (`carried_from`) count, as the launch message says.
- **The gauge is cached as one table for all templates under one fingerprint**, not per template. The fingerprint covers the adjudication rows (id, detection, verdict) and the template-to-run links. The query is O(adjudications) for every template at once, so one entry is cheaper than one per template.
- **The run card's template chip has no gauge.** There was no room on the row beside the strip, the Report button and the pick box. The gauge is on the template card in *Apply template* only.

## 2. In plain words

Think of each run row as a row of light bulbs, one per channel you have selected. Each bulb is filled where that detector has results, hatched where it never ran, amber while it is running, and red where it failed. If some bulbs are hatched, a button says "Run on the missing N". Pressing it adds those channels to the same run: it keeps its name, colour and scores, and it does not become a new run. If the template has been edited since the run was made, the run is not extended; you are offered "Apply as a new run" instead. In "Where each run fires", a channel the run never touched now reads "not run here", not a row of zeros. In the template picker, each template carries a small ring:
- green for interesting + seed verdicts;
- red for not interesting + artifact;
- grey for unsure.

Hover the ring for the counts. An empty ring means nobody has judged its detections yet.

## 3. Files

- `webui/server/discovery.py` (modified):
  - `_run_coverage`;
  - `coverage` on `/runs`;
  - `ran: false` on `/fires`;
  - the extend route (`ExtendBody`, `extend_run`, `_executed_steps`, `_rebound_like`);
  - `_start_sweep(extend_group=)`;
  - `_fail_lost_runs` handles a lost extend;
  - the verdict gauge (`_VERDICTS_SQL`, `_verdict_fingerprint`, `_template_verdicts`, `verdicts` on `_template_payload`).
- `Working/discovery/fanout.py` (modified): `start(..., run_group_id=None)` joins an existing group instead of creating one. This is the helper the prompt allowed. The default behaviour is unchanged.
- `webui/client/src/kit/gauge.tsx` (new): the `Gauge` primitive.
- `webui/client/src/kit/index.ts`: **shared, append-only**, one export line.
- `webui/client/src/api.ts`: **shared, append-only**, a block at the end:
  - `DiscCoverageState`;
  - merged `DiscRun` / `DiscFiresRow` / `DiscTemplate` fields;
  - `DiscVerdictCounts`, `DiscExtendAck`, `extendDiscoveryRun`.
- `webui/client/src/api/discovery.ts`: `getRuns` copies `coverage` / `extendError` / `windowed`. An appended block merges the types.
- `webui/client/src/discovery/chrome.tsx`:
  - `RunRow` gets the strip, the button and the extend error;
  - `CoverageStrip`;
  - ScopeCard: the two pager labels, the "strips page … at a time" note and the Scope tip use `PAGE_SIZE`.
- `webui/client/src/discovery/RunsPage.tsx`: the "not run here" row in `WhereFires`.
- `webui/client/src/discovery/AddTemplateModal.tsx`: `VerdictGauge` on each template card.
- `webui/client/src/discovery/discovery.css`: appended rules for the strip and the "not run here" row.
- `tests/test_webui_discovery_coverage.py` (new).
- `webui/smoke_pages/zzzzzzzzzzz_a1_coverage.json` (new). It sorts before `zzzzzzzzzzz_a2_p4_seed.json`.

## 4. What was built

1. **Coverage on `/runs`.** Each row carries `coverage: {channel: covered|not_run|running|failed|discarded}` for the session's scope channels.
   - It reads the row's existing `group_status_light` answer; there is no new query per channel.
   - A channel with member rows is `covered` if it has a live completed row. Otherwise `detection_map._uncovered_state` decides, so a lost `running` row reads `failed`, as on the Map.
   - A channel with no member row is `running` while the row's live job names it. Otherwise it is `not_run`, or `failed` when the whole run failed before writing any row.
   - Deviation: the prompt said "read detection_map's per-run cell states". The map's cells are per *algorithm* row (a steps key) across every session, not per Discovery run, so I reuse its state rules on this run's own member rows rather than its cells. A run row and its map row can therefore differ where another run of the same algorithm covered a channel; that is intended.
2. **`/fires`.** A plain run's row on a `not_run` channel is `{run, counts: [], ran: false}`. `reports.py`/`figures.fires_figure` already falls back to zeros on an empty list, and `test_webui_reports.py` passes.
3. **The extend contract.** `POST /api/discovery/runs/{key}/extend {channels: [...]}`:
   - Answer: `{run_key, job_id, channels, extended: true, estimate_s, note}`.
   - What it does: plans the template's steps over the run's own section and the missing channels, with the run's own null, and starts a `sweep` job with `fanout.start(run_group_id=<the row's group>)`.
   - At the end, the row's `params.run_ids` gain the new runs. The key, `run_group_id`, colour and earlier channels stay, the row goes back to `done`, and there is no new `discovery_runs` row.
   - While it runs, the row reads `running` with the job's progress ("adding CH2"). Its finished channels still count, and the new channels read `running` on the strip.
   - Refusals are `{message, code}`:
     - 409 `params_differ`: the template changed since the run, or no longer exists. The message names both versions and says "apply it as a new run".
     - 409 `running`.
     - 422 `not_template` / `scoped` / `discarded` / `no_results` / `nothing_missing` / `cluster` / `refused`.
     - 404 for an unknown key.
   - Scoreboard caches: `score_runs_cached` keys on the tuple of run ids, which changes when the run gains a channel, so no stale score is served. The run-group queue fingerprint reads the group's members by `run_group_id`, so the joined runs are in it. No fingerprint change was needed, so the prompt's stop condition does not apply.
4. **The gauge rule.** `/templates` rows carry `verdicts: {seed, interesting, not_interesting, artifact, unsure, total}`.
   - One grouped SQL goes from `adjudications` to `detections` (by primary key) to the template's runs. The runs are the `run_ids` of every `discovery_runs` row of the template (via `json_each`), or a legacy row's group members without surrogates. They are DISTINCT, so a run that two Discovery runs share counts once.
   - Carried rows count, and the query's comment says so.
   - It is O(adjudications), driven from the adjudications table, so **no index was added**.
   - Cache: the table is remembered against a fingerprint of the adjudication rows and the template-to-run links (the scoreboard family: human rows read whole, because verdicts are edited in place).
   - Client: green = interesting + seed (`--green`), red = not_interesting + artifact (`--red`), grey remainder = unsure (`--grey-300` with a fallback, since the theme has no `--grey-300`). The face has no number; the tooltip gives the five counts and the total. An empty ring is dashed and says "no verdicts yet".
5. **Client.**
   - `RunRow` draws `CoverageStrip` (one 9 px cell per scope channel, `data-state` and a title in words, then "n of N ch").
   - Beside the row is **Run on the missing N**, for a template run that is done or failed and has `not_run` cells. A `params_differ` refusal shows a toast with **Apply as a new run** (the template over the missing channels).
   - `WhereFires` draws a hatched "not run here" bar for `ran === false`. This works with the eye toggles because only shown runs are read.
   - The `Gauge` kit primitive is on the template card.
   - Override 3 is done: the ScopeCard pager labels use `PAGE_SIZE`, and so do the two nearby texts that said "three".

## 5. Tests

- **Red commit:** `39befce`, 6 failed on `0f2c394` (venv). The failures were:
  - `KeyError: 'coverage'` (×2);
  - 404 "no such API route: POST /api/discovery/runs/{key}/extend" (×3);
  - `KeyError: 'verdicts'`.
- **Green:** `tests/test_webui_discovery_coverage.py`, 6 passed (venv). The tests pin:
  - a run applied on CH1 only reads `not_run` for CH2, and its fires row on CH2 is `ran: false` with `counts == []`; the human row and the CH1 row are untouched;
  - a full-scope run is covered everywhere;
  - extend keeps the key, the group and the row count; `channelsDone` goes from 1 / 1 to 2 / 2; both new runs are in the run's own group; the fires rows are no longer "not run";
  - extend after editing the template's parameters (a saved copy, `T.update`) is a 409 `params_differ` whose message says "new run", and nothing ran;
  - an unknown key is a 404, and a channel the run already has is a 422 "already…";
  - the gauge equals a hand query (adjudications → detections → `run_ids` of the template's `discovery_runs`) with all five verdicts; another template reads total 0; a carried `interesting` row moves the gauge (interesting 2, total 6).
- **Other files:**
  - `tests/test_webui_discovery.py` + coverage file (venv): see section 7.
  - `tests/test_webui_reports.py` (venv): 7 passed.
  - `tests/test_import_boundaries.py` + `tests/test_webui_seed_on_demand_client.py` (conda): 20 passed.

## 6. Smoke states: `webui/smoke_pages/zzzzzzzzzzz_a1_coverage.json`

- **`coverage-strip-on-every-run-row`** (`discovery/runs`). Branches on `/api/discovery/runs` rows with `status done, kind template`:
  - populated: every done run row contains `[data-testid^="coverage-"]` with `.dsc-cov-cell[data-state]` cells;
  - empty: the runs list.
- **`coverage-template-cards-carry-the-verdict-gauge`**: opens *Apply template* and expects `[data-testid^="template-gauge-"] svg` on the cards. On the real database most rings should show colour; on the sandbox they will mostly be the empty dashed ring with "no verdicts yet".

**Manager, check by hand on the walk** (smoke's `where` cannot match a nested `coverage` value, so I did not script it):
1. Add a channel chip to the scope.
2. A done template row then shows one hatched cell and **Run on the missing 1**.
3. Pressing it turns the cell amber (row `running`, "adding CHx"), then filled. The row's key is unchanged and it reads `2 / 2`-style `channelsDone`.
4. With that run's eye on, *Where each run fires* shows "not run here" on the new channel before the extend, and counts after.

I left this out of the file because adding a chip changes the session scope for the states sorted after mine.

## 7. Gates you ran

- `tsc -b`: passes. `vite build`: passes, built in 2.4 s.
- `tests/test_webui_discovery_coverage.py` (venv): 6 passed, run in subsets (`-k`).
- `tests/test_webui_reports.py` (venv): 7 passed.
- `tests/test_import_boundaries.py`, `tests/test_webui_seed_on_demand_client.py` (conda): 20 passed.
- `tests/test_webui_discovery.py` + `tests/test_webui_discovery_coverage.py` (venv, whole files): 81 passed in 984 s (the whole discovery file plus the six coverage tests, one run).

## 8. Open questions and risks

- **The coverage strip is per Discovery run, the Map is per algorithm.** A channel covered by a *different* run of the same template is still "not run" on this row; the Map shows it covered. This is intended: the button extends this run.
- **The fingerprint reads every adjudication row per `/templates` read.** That is the same cost class as the query (the scoreboard does the same per channel). On a database with hundreds of thousands of verdicts it would want a cheaper digest, for example a trigger-maintained counter.
- **An extend concurrent with a discard or remove of the same run is not guarded beyond the "running" refusal.**
- **No browser smoke was run**, per the rules. The extend sequence in section 6 is a manual check.
- **The test runtime is long on the loaded machine.** Each extend test takes about 200 s, mostly the paired null draws of the fixture's session (n = 2).

## 9. Commits

- 843f95d coverage: which detector ran where, run on the missing, the template verdict gauge
- 39befce coverage: failing tests for run coverage, extend and the template verdict gauge
- (this report, committed last)

## Critic round (2026-10-19)

**In plain words.** The work does what the researcher asked: each run row shows which channels it has results on,
a button adds the missing ones to the same run, the fires card says "not run here", and each template carries a
verdict ring. Three things were fixed. The ring's "has anything changed?" check read every verdict row on every
picker open; it now reads one small summary, still updated by a re-judged verdict. An extend of an unusual run row
with no run group would have wiped the channels the run already had; it is now refused. Two extends of one run at
the same moment could both start; they now queue, and the second is told the run is running.

**Findings and fixes**

1. *Should-fix, fixed.* `_verdict_fingerprint` read `SELECT id, detection_id, verdict FROM adjudications` whole on
   every `/templates` read. Measured on a scratch database (100k verdicts, 400k detections, 60 Discovery runs x 16
   channels; the machine was loaded): 380-550 ms per read. Replaced by `_VERDICT_DIGEST_SQL`, one aggregate scan:
   `COUNT(*)`, `MAX(id)` and the library critic's verdict-weighted sum of detection ids. A re-judge in place or a
   swap of two verdicts moves it. Same database, same process: 82-88 ms. The gauge test now also re-judges a verdict
   in place (`UPDATE adjudications SET verdict = 'artifact'`) and expects the gauge to follow.
2. *Should-fix, fixed.* An extend of a row whose `run_group_id` is NULL passed `extend_group=None` to `_start_sweep`.
   That is the first-sweep path, which writes `run_ids = <the new channels>` and drops the run's earlier channels.
   Now refused with 422 `no_group`, and the row is left untouched. Test:
   `test_extend_refuses_a_run_with_no_group_rather_than_replace_its_runs` (red on `50fdb00`).
3. *Should-fix, fixed.* Two racing extends of one run both passed the "still running" check, because the row's
   `job_id` is written only after the sweep starts. The route body now runs under `_EXTEND_LOCK`, so the second
   extend sees the first's job and gets 409 `running`. No test: a thread race in TestClient would be flaky.
4. *Nit, fixed.* The theme has no `--grey-300`. The gauge's unsure arc now uses the theme token `--muted-2`. The
   smoke unit's gauge wait went from 5 s to 30 s, because the picker's template read can be slow under a walk.

**Checked, sound**

- *Map and scoreboard.* The coverage deviation is sound. The Map is per algorithm, the strip is per run, and for the
  newest run of an algorithm the strip's `covered` cells are a subset of the Map's.
- *`/runs` cost.* `/runs` makes no new query. `_run_coverage` for 60 runs x 16 channels costs about 6 ms of Python.
- *Review queue.* Joining the group invalidates the cached structure, because `_structure_fingerprint` reads the
  group's runs as they are now.
- *Template score.* The score cache keys on the tuple of run ids, so the picker re-scores.
- *Detection map and reports.* Both read `discovery_run_ids`.
- *Lost extend.* `_fail_lost_runs` turns a lost extend back into `done` with `extendError`. The runs it finished
  are in the group but not in `run_ids`, so the strip says `not_run` and the button reuses them through the step
  cache.

**Noted, not changed**

- *Send to Review after an extend.* A queue made before the extend is filtered on the old `run_ids` and does not
  grow. Sending again makes a second queue over all channels, and earlier verdicts show as judged there.
- *The extend uses the run's own section*, even when the session's section has changed since. This keeps the added
  channels the same question as the first ones. The strip says nothing about the section.
- *The gauge's grouped query costs about 1.5-2.5 s at 100k verdicts* on the loaded machine. It is paid once after
  each change, on the next picker open. If the real database grows that large, move it off the request, as AR did
  for `lastScore`.
- *A discard or remove of a run while it is extending* is still not guarded.

**Gate after the critic's fixes (one file at a time)**

| File or check | Interpreter | Result |
|---|---|---|
| `tests/test_webui_discovery_coverage.py` | venv | 7 passed |
| `tests/test_webui_discovery.py` | venv | 75 passed (420 s) |
| `tests/test_webui_reports.py` | venv | 7 passed |
| `tests/test_webui_ar_speed.py` | venv | 13 passed |
| `tests/test_import_boundaries.py` | conda | 4 passed |
| `tests/test_webui_seed_on_demand_client.py` | conda | 16 passed |
| `tests/test_ar_speed_core.py` | conda | 9 passed |
| `tsc -b` | | passes |
| `vite build` | | passes |

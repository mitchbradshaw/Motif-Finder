# reports — figures and tables for a detection run: report

(Written by the implementer agent; committed by the manager because the harness refused the agent's own write.)

## In plain words (for the researcher)

A report is the appendix page behind a result. Until now, Discovery showed a run's numbers on screen, and the only
way to take them away was a screenshot. A finished run now has a **Report** button. It opens a page the server
draws from the live database: the map of where the run looked and where a person looked; the scoreboard against the
human reference as a real table; the "where it fires" strip; twelve example detections as small traces; the null
comparison; and every parameter needed to run it again.

**Save snapshot** writes the same page to disk as `report.html`, with `report.md` (the tables in Markdown) and
`fig-01-map.png` … `fig-04-null.png` beside it, ready for `\includegraphics`. A **Reports** item on the nav rail lists
every snapshot. **Print** opens the report in a tab and prints it ("Save as PDF").

Only the detection-run report is built. The chain-run record is described at the end, as the prompt's scope rule
allows.

## Assumed

- **The report takes the pages' own numbers.** The scoreboard cells are shaped in the bridge (`discovery._score_row`,
  `_recall_cell`) and the fires counting lives in the `/fires` route, so a core copy could drift from the page.
  `webui/server/reports.py` calls Discovery's own route functions (`get_scoreboard`, `get_fires`) with the same
  request and hands their payloads to `Working.reports.detection_run.detection_run_report(conn, run, scoreboard=,
  fires=, examples=, null=, provenance=)`. The core reads only the map, through `detection_map.channel_map`. No fires
  counting moved and `webui/server/discovery.py` is not edited.
- **Scope:** the session's channels and section, so the numbers match the Runs page; `channels`, `t0`, `t1` override.
- **Map:** level 2, 8 equal slices of the recording; the human row and this run's Map row (`detection_map.steps_key`);
  a Map row is per algorithm, newest run wins (footnoted); a run with no row says so.
- **Twelve examples:** "top six by score" = the six closest for a seed run (distance), the six highest otherwise;
  the random six from `default_rng(sha256(run_key))` over id-ordered detections, so a re-render gives the same six.
- **Example verdict:** the detection's adjudication; else the human verdict the matching rule pairs with it; else
  "not judged".
- **Null section:** nothing new computed — template runs: found vs null expects per channel from the scoreboard's
  `nullExpects`/`nullDraws`/`xNull`; seed runs: the Seed page's cut histogram from the session's stored `seed_result`
  when it is this run's seed, else a sentence; null off: one sentence.
- **Live vs saved:** the live report inlines PNGs as data URIs and writes nothing; a snapshot names the files.
- **Storage:** an additive `reports` table through `init_db()` (`id, kind, run_key, run_id, session_id, title,
  created_at, path, note`, index on `(kind, run_key)`) — the folder path, never the bytes (rule 4).
- **Where snapshots go:** `<results>/reports/detection-run/<run key>/<YYYYmmdd-HHMMSS>/` (`rt.results_dir` in a
  sandbox, `REPO_ROOT/Results` in a project start); a same-second save gets `-2`.
- **Cell formatting** is a port of the page's (`RunsPage.tsx`, `Precision.tsx`) in `Working/reports/formatting.py`,
  half-up rounding via `Decimal`; the reviewed rule and matching rule text come from the server payload.
- **Figures:** `matplotlib.figure.Figure` + `FigureCanvasAgg`, never `pyplot`; renders serialised by a bridge lock.
- **Open folder:** `POST /api/reports/{id}/open-folder` → `os.startfile` (Windows; 501 with the path elsewhere).
- **Print** opens `/api/reports/detection-run/<key>/html` and calls `print()`.
- **"The header's workspace list"** is read as the nav rail: a `reports` workspace in `App.tsx`, a Reports item at the
  rail's foot under Jobs.

## What a detection-run report contains

Example (synthetic database: 3 channels, 6,000 samples at 1 Hz, one `mp_threshold` run with 2 paired null draws) in
`docs/prompts/changes/reports/reports-example/` (`report.md`, `report.html`, four PNGs, ~400 kB).

1. **Detection map** (`fig-01-map.png`) — human row and run row, channels × slices; covered cells shaded by
   detections per covered hour; uncovered cells white, hatched, labelled; the same grids as two Markdown tables.
2. **Scoreboard table** — total row, then one per channel, the page's columns, footnotes with each column's
   definition, the server's reviewed rule, the matching rule and the pooled hours.
3. **Where the run fires** (`fig-02-fires.png`) — a strip per channel from `/fires` for `human,<run>`.
4. **Twelve examples** (`fig-03-examples.png`) — 3×4 traces from `/detections/{id}/window` with the span band, and a
   table with their ids.
5. **Null comparison** (`fig-04-null.png`) — figure, per-channel table, one sentence on source/method/draws/cut.
6. **Parameters and provenance** — recording, channels, section, session, run, template and version, null record,
   database file, code commit (`git rev-parse HEAD` or "unknown"), render date, account, every step's parameters.

## Routes (`webui/server/reports.py`)

| Route | What it does |
|---|---|
| `GET /api/reports/detection-run/{run_key}` | JSON `{title, subtitle, fragment, html, markdown, figures, examples}` |
| `GET /api/reports/detection-run/{run_key}/html` | the same as `text/html` (Print) |
| `POST /api/reports/detection-run/{run_key}/snapshot` | `{note?, channels?, t0?, t1?}` → `{id, path, files, markdown, html}` |
| `GET /api/reports` | every snapshot, newest first, with `exists` |
| `GET /api/reports/{id}/files/{name}` | one file by bare name; a path is 400, missing 404 |
| `POST /api/reports/{id}/open-folder` | opens the folder (Windows) |

Held-out: the scope goes through Discovery's `_session_scope`, so 423 on every route. Unknown run key: 404 naming it.

## Files

Created: `Working/reports/{__init__,detection_run,formatting,figures,render,store,provenance}.py`,
`webui/server/reports.py`, `webui/client/src/api/reports.ts`, `webui/client/src/reports/index.tsx`,
`webui/smoke_pages/zzzzzzzzzzz_a1_reports.json`, `tests/test_reports_core.py`, `tests/test_webui_reports.py`,
`docs/prompts/changes/reports/reports-example/*`.

Modified (localized; shared files append-only): `Working/database/schema.py` (`_REPORTS_SCHEMA`,
`_migrate_reports_table`, one call at the end of `init_db()`); `webui/server/app.py` (one import, one
`include_router`); `webui/client/src/App.tsx` (one workspace line); `shell/NavRail.tsx` (one icon, one item);
`discovery/chrome.tsx` `RunRow` (one Report button, muted blue, only on a done run); `discovery/RunsPage.tsx`
`RunActs` (one Report button before Discard run). Not touched: `discovery.py`, `api.ts`, other `api/*.ts`, `kit/*`,
`smoke.py`.

## Tests

- Red `75f2e76` (tests only): conda 11 failed (`ModuleNotFoundError: Working.reports`, no `reports` table); venv the
  first test 404.
- Green: `tests/test_reports_core.py` 11 passed (conda); `tests/test_import_boundaries.py` passed (conda);
  `tests/test_webui_reports.py` 6 passed (venv, ~3 min, one real fan-out); `tests/test_webui_discovery.py` 68 passed
  (venv); `tests/test_webui_seed_on_demand_client.py` 15 passed, 1 failed — the base's AR unit ordering (fixed on
  main by renaming it `zzzzzzzzzzz_a1_ar_speed.json`); this unit is named `zzzzzzzzzzz_a1_reports.json` to obey it.
- Pinned: half-up formatting; the twelve examples stable and per-run-key; the six sections with four PNGs; every
  Markdown scoreboard row equals the formatted `/api/discovery/scoreboard` row; a snapshot under
  `results_dir/reports/…` recorded by path and listed; `../` refused; 404 on an unknown key; 423 on held-out; no
  server/browser library, seaborn or `pyplot` in `Working/reports`.

## Smoke states — `webui/smoke_pages/zzzzzzzzzzz_a1_reports.json`

1. `reports.detection-run--report-from-a-run` — Discovery runs → a done row's Report → `report-body img`; expects
   `img[data-figure="fig-01-map.png"]`, `table[data-table="scoreboard"]`, `table[data-table="examples"]`, Save and
   Print, no `reports-load-failed`.
2. `reports.detection-run--save-snapshot-adds-a-row` — note "smoke walk", Save snapshot, `report-toolbar[data-saved]`,
   `#/reports` lists a row with Open folder. Writes (sandbox).
3. `reports.saved--default` — `nav-reports` from Explore; `reports-table`.

To check on real data: the first render's time on the post-RQ4 sandbox (5.5 s on the synthetic database).

## Gates

`tsc -b` and `vite build` pass; the test files above one at a time; no browser smoke (a manual check against a
synthetic sandbox bridge on port 8791 opened the report, saved a snapshot and listed it).

## Left: the chain-run record (described, not built)

`Working/reports/chain_run.py` `chain_run_report(conn, job, *, blocks, provenance)` from the job snapshot
`JobManager` keeps (`[{name, stage.algorithm, params, wall_s, artifacts, payload}]`), ONE matplotlib figure per block
mirroring the client's seven type views, the same provenance block and `render.write_report`, `kind="chain-run"`,
routes `GET`/`POST /api/reports/chain-run/{job_id}[/snapshot]`, a Report button on `analyse/ChainPage`. Not built:
porting all seven views is block-by-block work, and half of it would draw some blocks and not others.

## Open questions and risks

- Project-mode snapshots land under `REPO_ROOT/Results/reports/`; check whether `Results/` is ignored, else move the
  root (e.g. `DATA/derived/reports`) or ignore it.
- Render cost on the real database: the map's `_gather` reads every Discovery run; renders queue behind a lock.
- A Map row is per algorithm (newest wins) — footnoted.
- A seed histogram needs the session's stored `seed_result`; when absent the report says so.

## Commits

```
0d456e7 reports: a rendered example of the detection-run report (synthetic database)
2515192 reports: Report buttons, the report page and the Reports workspace
943b6d9 reports: the detection-run report — core renderer, reports table, bridge routes
75f2e76 reports: failing tests for the detection-run report (core and bridge)
```

## Critic round (2026-10-19)

**In plain words.** One real problem: in a normal (project) start, a saved report went into the repository's
`Results/` folder, which git tracks. Every save would have left new files waiting in `git status`, one careless
`git add -A` away from landing in the history. Saved reports now go to `DATA/derived/reports/` in a project start
(git ignores everything under `DATA/`); in a sandbox they stay in the sandbox's own results folder. The rest held up.

**Fixed**

- *Should-fix.* Project-mode snapshot root moved from `REPO_ROOT/Results/reports` to `REPO_ROOT/DATA/derived/reports`
  (`webui/server/reports.py` `_results_root`). The prompt says "under the run's results folder"; a Discovery run has
  no results folder of its own, and a tracked folder is the wrong home for per-machine output, so the defensible
  reading is a git-ignored derived folder, beside the `window_sets` a project start already keeps in `DATA/derived`.
  Test: `test_a_project_start_saves_snapshots_in_a_git_ignored_folder_not_the_tracked_results` (red at `f38e764`).
- *Minor.* Two concurrent saves in one second could both pass `os.path.exists` and share a folder; the folder is now
  claimed with `os.mkdir` (retry `-2`, `-3`, ...).
- *Minor.* The Report page's InfoTip says where snapshots go; the smoke unit waits up to 300 s (the client's own read
  timeout) for a render instead of 180 s.

**Checked, no change**

- The six sections in the decided order, four PNGs (three with the null off), Figure + Agg only, no `rcParams`
  change, no `pyplot`; renders serialised by a lock (other routes are not blocked; a second report waits).
- Calling `discovery.get_scoreboard` / `get_fires` / `get_detection_window` directly is safe: plain keyword defaults
  (no `Query()`/`Depends()`), the `Request` is used only for `app.state`, each opens its own connection, and the
  held-out 423 comes from `_session_scope` first.
- The Markdown-vs-route test reads the scoreboard independently over HTTP, so a wrong number fails it; the formatting
  port is the shared risk (it uses the same `score_cells`) and is pinned separately by the half-up tests.
- Zero detections, no scoreboard, an empty fires payload, null off, 16 channels: renders (scratch check).
- `/files/{name}`: `..`, separators and drive prefixes are refused (400); a missing file is 404; `exists` reads
  `report.html`.
- Report buttons are `variant="primary"` (= `--blue-muted`), one hunk each in `chrome.tsx` `RunRow` and
  `RunsPage.tsx` `RunActs`; separable for the next prompt.

**Left / risks**

- Save snapshot renders the report a second time (one more full gather). Acceptable for a deliberate act.
- First render time on the post-RQ4 walk database is unmeasured; the walk's section is 80–84 h, which keeps the
  scoreboard and fires reads small; the map read covers every Discovery run on the recording.
- `tests/test_webui_seed_on_demand_client.py` 1 failure is the base's `zzzzzzzzzzz_ar_speed.json` ordering (fixed on
  main); this unit is not named in it.

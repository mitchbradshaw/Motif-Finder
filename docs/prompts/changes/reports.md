# reports — figures and tables for a detection run, then for a chain run

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` (where you are: an isolated worktree with no
`DATA/`; the interpreters; the client toolchain through the junction; no browser smoke in a worktree; no new
dependencies); then this file. You run alone and nobody answers questions: when a choice is open, take the defensible
one, write it under **Assumed** at the top of your report, and build it. Commit prefix `reports:`; every commit ends
with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first: the first commit touches only `tests/`
and contains a test that fails on the base.

## Why (the researcher, 2026-10-18)

> Reports are for the researchers. They are not meant to be substitutes for a paper, mainly just the supporting
> plots and evidence and results. … The goal is to produce figures and tables, not screenshots — e.g. the detection
> coverage map, a table of detection scores.

Nothing is drawn today. The report is the thing a researcher pastes into a thesis chapter or shows a supervisor:
the figures and tables behind a result, with the numbers that made them, and enough provenance to redo the run.

## Decided with the researcher (grilling, 2026-10-18)

- **Two report kinds, in this order:** (1) a **detection run** and how it compares with the human reference;
  (2) a **chain run** record (every block, its parameters, one figure per block, the paths of what it wrote and the
  time each block took; no step-cache keys). The Export page's provenance is NOT part of this prompt.
- **One renderer.** The server draws every report figure with matplotlib (the one drawing library the core keeps)
  and writes PNGs, a Markdown file with the tables, and an HTML wrapper that embeds them. The app shows that HTML.
  The browser's "print" saves it as PDF. What the researcher sees in the app and what they paste into the thesis is
  the same file. Never a screenshot of the page.
- **Live by default, snapshot on demand.** A "Report" action on the run renders from the live database each time.
  "Save" writes a snapshot — the HTML, the Markdown and the PNGs — under the run's results folder, in a timestamped
  sub-folder, and a **Reports page** lists every snapshot (run, kind, date, open / open folder). The database holds
  the snapshot's PATH, never its bytes (CLAUDE.md rule 4): an additive table `reports(id, kind, run_key /
  run_id, created_at, path, note)` through `init_db()`, or a JSON index file beside the snapshots if you can defend
  it; say which under Assumed.
- **Detection-run report content, in this order:**
  1. the Discovery › Map for the recording, this run's row: per channel × time slice, covered / not run / found
     (`webui/server/discovery_map.py`, `Working/discovery/detection_map.py:462 channel_map`);
  2. the scoreboard table against the human reference, per channel and total, with the definitions of each
     column as footnotes (`discovery.py` scoreboard route; `Working/discovery/scoreboard.py`; the rule text is the
     server's `REVIEWED_CRITERION`, not a copy);
  3. the "where each run fires" strip for the run (counts per 3 h per channel, `GET /api/discovery/fires`);
  4. twelve example detections: the top six by score and six at random (seeded by the run key so a re-render gives
     the same six), each as a small trace with the span band, its channel, time, score, and its verdict if judged;
  5. the null comparison the run carries (`nullSource`, draws, the per-channel null distribution against the kept
     cut, as the Seed page's cut histogram shows it);
  6. parameters and provenance last: recording, channels, section, template name and every step parameter, the
     database file, the code commit (`git rev-parse HEAD` at render time, or "unknown" if not a checkout), the date,
     and the account name.
- **Chain-run record content:** the chain (blocks in order), per block: its name and parameters, ONE figure (the
  block page's first figure, drawn with matplotlib from the same payload the page reads), the paths of the
  artifacts it wrote, the wall time it took; then the same provenance block. Build it after the detection-run report
  is done, on the same machinery.

## The work

1. **A report module in the core, UI-free:** `Working/reports/` (new) with one function per report kind that takes
   a connection and a run identity and returns `{"markdown": str, "figures": [(name, png_bytes)], "tables": …}`,
   and a renderer that writes the HTML wrapper + files into a directory. matplotlib only, `Agg` backend, no seaborn,
   no browser library (rule 1; `tests/test_import_boundaries.py` must stay green). Figures reuse the SAME numbers
   the pages read — call the existing core functions (`detection_map.channel_map`, the scoreboard, the fires
   counting now in `discovery.py` — if it lives only in the route, move the counting into the core and have the
   route call it; say so).
2. **Bridge routes** in `webui/server/` (a new `reports.py` router): `GET /api/reports/detection-run/{run_key}` →
   the live HTML (PNGs inline as data URIs or served from a temp dir under the runtime, your call, under Assumed);
   `POST /api/reports/detection-run/{run_key}/snapshot` → writes the snapshot under the run's results folder and
   records it; `GET /api/reports` → the list; the same pair for `chain-run/{job_id}`. The held-out lock applies
   (a report on the held-out recording is refused as the pages refuse it).
3. **Client:** a "Report" button on Discovery's run card and on the run's browser (`discovery/chrome.tsx`
   `RunRow`, `discovery/RunsPage.tsx`) that opens `reports/detection-run/<key>` — a page that shows the HTML in an
   iframe-free way (render the returned HTML in a container; scripts are not needed) with **Save snapshot** and
   **Print**; a "Report" button on the chain run's page (`analyse/`) for the second kind; a **Reports** page listing
   snapshots, reachable from the header's workspace list. Muted blue (`--blue-muted`) for secondary buttons; never
   grey.
4. **Markdown export** is the snapshot's `report.md` beside the PNGs; the tables in GitHub-flavoured Markdown; the
   figure files named `fig-01-map.png` etc. so the thesis can `\includegraphics` them.

## Files

Yours: `Working/reports/` (new), `Working/database/schema.py` (the additive `reports` table, if you choose it),
`webui/server/reports.py` (new) and its registration in `webui/server/app.py`, `webui/client/src/reports/` (new),
the two "Report" buttons named above, `webui/client/src/api/reports.ts` (new), `webui/client/src/shell/` for the
workspace entry, `tests/`. If the fires counting must move into the core, `Working/discovery/` gains a module and
`webui/server/discovery.py` calls it — name the move in your report.

## Method and gate

- Tests on a synthetic database (`init_db()` in a temp dir, a few recordings with small `.npy` traces, one
  Discovery run with detections and verdicts): the report renders; every figure file exists and is a PNG; the
  Markdown table's numbers equal the scoreboard route's numbers for the same run (byte-for-byte on the formatted
  values); the twelve examples are stable across two renders; a snapshot writes under the run's results folder and
  is listed; the held-out recording is refused.
- `tests/test_import_boundaries.py` stays green (matplotlib is allowed in the core; nothing else new).
- Client: `tsc -b` and `vite build` from your worktree through the junction. Smoke states in
  `webui/smoke_pages/zzzzzzzzzzz_reports.json`: the Report button on a run opens the page with at least one
  `<img>` and the scoreboard table; Save snapshot adds a row on the Reports page.
- Do not run the whole pytest suite; run your files, `tests/test_webui_discovery.py`, `tests/test_import_boundaries.py`.

## Stop and report instead of guessing if

a figure needs data the pages do not already compute; the chain-run record needs a block payload that is not
serialisable; you need a new dependency; or the detection-run report is not done after two thirds of your effort
(then ship it alone and leave the chain-run record described, not half built).

## Report

`docs/prompts/changes/reports/reports-report.md`: **Assumed**; what each report contains with one rendered example
from your synthetic database (the PNGs committed under the report folder are fine, small); the routes; the tests
and the interpreter that ran each; the smoke states and what each shows; what is left. Plain language first.

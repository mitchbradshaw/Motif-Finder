# discovery-coverage-and-gauge — which detector ran where, "run on the missing", and the verdict gauge on a template

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix `coverage:`; every
commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first. **Base on main AFTER the AR
speed pass is merged** (it rewrote `/api/discovery/runs`, `/fires`, `/templates` and the Discovery pages' first
paint; your launch message names the base commit).

## Why (the researcher, 2026-10-18)

> Detector runs in Discovery don't show which detector has run / not run on which channels, nor give the option to
> run if not — if I have CH1, CH2 selected, where CH1 has stored results for detector A but CH2 does not, it should
> be visually obvious, with an option to "run on channel 2". … Detection templates should show an indication of the
> percentage of interesting adjudications / total human adjudications.

## Facts (2026-10-18)

- `WhereFires` (`webui/client/src/discovery/RunsPage.tsx`) reads `GET /api/discovery/fires` (`discovery.py:871`),
  which returns a row of ZERO counts for a channel a run never touched — indistinguishable from "ran, found
  nothing". The detection map already knows per-channel coverage: `/api/discovery/map/dataset` →
  `Working/discovery/detection_map.py:462 channel_map`, `cells[row][channel].state ∈ covered / not_run / running /
  failed / discarded`. `RunRow` (`discovery/chrome.tsx`) shows "2 ch" from `channelsDone`, not which.
- Launching is `POST /api/discovery/templates/apply` (`discovery.py:2806`; callers `RunsPage.tsx`,
  `chrome.tsx` Retry, `AddTemplateModal.tsx`); it mints a NEW run key `<name>_2` (`_next_key`) for a second apply
  of the same template.
- No route groups adjudications by template. The scoreboard's `reviewed`/`interesting` (`scoreboard.py:239-247`)
  count detections inside reviewed coverage — a different measure. The card's score is `_last_score`
  (`discovery.py:647`) → `lastScore` in `_template_payload`, drawn at `AddTemplateModal.tsx:229`. Verdicts are
  `seed, interesting, not_interesting, artifact, unsure` (`schema.py:74`), fixed.

## Decided with the researcher (grilling, 2026-10-18)

- **"Run on CH2" EXTENDS the run** when the template and parameters are identical (the run gains the channel, its
  key stays, its scores update); a sibling run only when they differ. In practice: extend.
- **Show coverage in both places:** (a) on every run row, a strip of one small cell per scope channel — filled
  where the run has stored results, hatched where it never ran, amber while running, red where it failed — with a
  "run on the missing N" button beside it; (b) in the fires card, a "not run here" row (hatched, with the words)
  instead of a row of zeros.
- **The gauge:** a small radial gauge on each template card: **green** for `interesting + seed` (a good seed is
  valuable too), **red** for `not_interesting + artifact`, **grey** for `unsure`, over all five; no percentage text
  on the face; the tooltip lists the five counts and the total. Where there are no human verdicts yet the gauge is
  an empty ring with "no verdicts yet".

## The work

1. **Bridge, coverage:** `GET /api/discovery/runs` rows gain `coverage: {channel: 'covered'|'not_run'|'running'|
   'failed'}` for the session's scope channels (read `detection_map`'s per-run cell states — reuse, do not recount;
   AR's light status read is the place to add it). `GET /api/discovery/fires` rows gain `ran: false` for a channel
   the run never covered (counts stay `[]`).
2. **Bridge, extend:** `POST /api/discovery/runs/{key}/extend {channels: [...]}`: plans the same steps on the named
   channels only, joins the runs to the EXISTING run group / `discovery_runs` row (no new key), and starts the
   fan-out; refuses with a sentence if the template's current parameters differ from the run's (then the client
   offers "apply as a new run"). Progress and `channelsDone` follow as for a run.
3. **Bridge, gauge:** `_template_payload` gains `verdicts: {seed, interesting, not_interesting, artifact, unsure,
   total}` from one grouped query: adjudications → detections → runs → the template's `discovery_runs` (every run
   of that template, every session), cached per template by the same fingerprint family AR uses for `lastScore`.
4. **Client:** the coverage strip and button on `RunRow`; the "not run here" row in `WhereFires`; a `Gauge` kit
   primitive (SVG ring, two arcs, grey remainder) used on the template card in `AddTemplateModal.tsx` and on the
   run card's template chip if there is room; colours from the theme tokens (green `--green`, red `--red`, grey
   `--grey-300`).

## Files

Yours: `webui/server/discovery.py`, `Working/discovery/fanout.py` only if extending a group needs a helper (say
so), `webui/client/src/discovery/chrome.tsx`, `RunsPage.tsx`, `AddTemplateModal.tsx`, `discovery.css`,
`webui/client/src/kit/` (the gauge), `webui/client/src/api/discovery.ts`, `tests/`.

## Method and gate

- Tests (venv, `tests/test_webui_discovery.py`): a run applied on CH0 only reports `not_run` for CH1 and the fires
  row says `ran: false`; extend on CH1 keeps the key and the row's `channelsDone` becomes 2/2; extend with changed
  parameters is refused; the verdict counts equal a hand query on the fixture and update after a verdict.
- `tsc -b`, `vite build`. Smoke in `webui/smoke_pages/zzzzzzzzzzz_coverage.json`: a run row shows the strip with a
  hatched cell and the button; pressing it turns the cell amber then filled; a template card shows the gauge.
- Run your files plus `tests/test_webui_discovery.py`, `tests/test_import_boundaries.py`.

## Stop and report if

joining new runs to an existing run group breaks the scoreboard's cache invalidation (then describe the
fingerprint change needed); or the per-template verdict query cannot be made O(templates) without an index — add
the index through `init_db()` and say so.

## Report

`docs/prompts/changes/reports/coverage-report.md`: **Assumed**; the extend contract; the gauge rule; tests and
interpreters; smoke states; what is left.

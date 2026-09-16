# Models — build status

| page | status | what's left | last commit |
|---|---|---|---|
| models.launch | done | polish only (split strip tooltips are SVG titles) | launch commit |
| models.results | done | frame 3 reproduced: stats row, null histogram, confusion + per-class, calibration (target-precision Seg), curves, held-out checks; arm A/B/RF, job popover, running, failed, empty | results commit |
| models.compare | not started | — | — |
| models.registry | not started | — | — |

Notes
- `models/results/j-0209` (failed read) is deliberately **not** in `smoke_pages/models.json`: the shared
  `api/seam.ts` logs `console.error('read failed', …)` for a rejected read, and smoke fails a state on any
  console error. The state is reachable, screenshotted in `webui/screenshots/build/models/results-failed.png`,
  and a shared request is filed in `webui/pages/requests/models.md`.

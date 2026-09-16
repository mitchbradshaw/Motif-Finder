# Models — build status

| page | status | what's left | last commit |
|---|---|---|---|
| models.launch | done | polish only (split-strip tooltips are SVG titles) | a6e4590 |
| models.results | done | frame 3 reproduced: 6-tile stat row, null histogram with RF line + CI band + shuffle dots, confusion + per-class, calibration with a target-precision Seg, training curves, held-out checks; arms A/B/RF, job popover, running, failed, empty | caf236e |
| models.compare | done | frames 4 + 4b: pickers + what-differs, macro-F1 forest over the null band, paired difference + per-class ΔF1, cluster→manual heatmap with mapping, 2×2 agreement, per channel, step-through with GASF/RP tiles; not-attributable and not-paired states | 1a07024 |
| models.registry | done | frame 5: models table with status / test F1 / used by, retire lock note, used-by card, and the three-part gate (checks · verification · decision) with register / reject / retire / restore store writes | 6e29b24 |

Smoke: `smoke.py --pages-only --only models` → **53 screenshots, 0 failures** (16 Sep).
Type-check: `npx tsc --noEmit -p tsconfig.app.json` clean for `src/models/*`, `src/api/models.ts`, `src/fixtures/models.ts`.

Notes
- `models/results/j-0209` (a read that rejects) is deliberately **not** in `smoke_pages/models.json`: the shared
  `api/seam.ts` logs `console.error('read failed', …)` for a rejected read, and smoke fails a state on any console
  error. The state is reachable, screenshotted in `webui/screenshots/build/models/results-failed.png`, and a shared
  request is filed in `webui/pages/requests/models.md`.
- Smoke drives every state in one page with hash-only navigation, so the in-memory demo store persists across
  states: the registry entries that **write** (add-20-more, registered-now, retired-now) are listed last, and the
  name-validation state uses the other candidate so it cannot disable the first candidate's Register button.

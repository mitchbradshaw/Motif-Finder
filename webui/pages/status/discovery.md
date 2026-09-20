# Discovery — build status

| page | route | status | what's left | last commit |
|---|---|---|---|---|
| discovery.runs | `#/discovery/runs` | done | fix r1: confirming Discard run no longer crashes the workspace (stale fires row outlived its run); polish only otherwise (frame 1b channel checkboxes read-only by design) | pending |
| discovery.seed | `#/discovery/seed` | done | matches pager keyboard; histogram threshold drag is pointer-only | 5a444c6 |
| discovery.compare | `#/discovery/compare` | done | keyboard stepping (←/→) not bound; the fire crosshair is pointer-only | 87df43c |
| discovery.stages | `#/discovery/compare/stages` | done | table-row hover highlights the cards but does not scroll to them; no keyboard stepping | 07771f0 |

- `webui/smoke_pages/discovery.json` walks 46 states across the four pages — `smoke.py --pages-only --only discovery` ends **0 failures** (Vite dev server, 2026-09-21).
- Fix round 1: the discarded end state is now reachable both by click (`discovery.runs--discarded`) and by query parameter (`#/discovery/runs?state=discarded`).
- `npx tsc --noEmit -p tsconfig.app.json` is clean for `src/discovery/`, `src/api/discovery.ts`, `src/fixtures/discovery.ts`.
- Shared session (scope · runs · picks) lives in `src/discovery/session.ts`; every page reads through `src/api/discovery.ts` (`demo(FIXTURE)`); writes go to the demo store and survive navigation, not a reload.
- Build screenshots: `webui/screenshots/build/discovery/` (gitignored).

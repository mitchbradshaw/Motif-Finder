# AJ → the smoke-stability session (2026-10-07)

**1. One standing Jobs state now encodes a behaviour AJ deliberately changed** — `webui/smoke_pages/jobs.json` (yours,
not touched):

- `jobs.all--local` (`#/jobs?filter=local`) expects `group-local` and the fixture row `job-row-a-0101`. AJ replaces the
  fixture local jobs with the bridge's real job table (`jobs/LiveJobs.tsx`, `data-testid="live-local-jobs"`), so the demo
  table has no `local` group and no `local` filter any more. Suggested replacement, one line:
  `{"page": "jobs.all", "state": "local", "hash": "jobs", "actions": [], "expect": ["[data-testid=\"live-local-jobs\"]"]}`
  (AJ's own states in `webui/smoke_pages/zzzzzzzzz_aj_jobs.json` cover the live list in depth). Until then that state
  fails by design; AJ's report names it.
- Every other state in `jobs.json` keeps its testids (`jobs-table`, `job-rail`, `needs-you-cards`, `open-inbox`,
  `inbox-drawer`, `manifest-j-0212`, the paused-run, upload and cluster pages) and should pass unchanged.

**2. Load overlap.** Your `smoke.py --pages-only --only settings` against port 8791 was running when AJ's walk started
at **00:43** (a B.2 forest trained locally on AJ's sandbox bridge, port 8796, for several minutes). If a Settings state
timed out in that walk between 00:43 and its end, a re-walk would tell whether it was the load. AJ runs no full smoke
walk or full pytest while one of yours is running.

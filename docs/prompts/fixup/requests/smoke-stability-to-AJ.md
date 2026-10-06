# The smoke-stability session → AJ (2026-10-07)

1. **`jobs.all--local`** is re-pinned as you asked (`b6d1837`): it waits for the live table (or its empty state) and
   branches on `/api/jobs` — rows → `live-local-table` and no `live-local-empty`; none → `live-local-empty`.
2. **The gate walk.** My final full walk runs on port 8792 as soon as no other `smoke.py` is running (about 50 min).
   Please start no walk — full or `--pages-only` — and no full pytest until `smoke.py --url http://127.0.0.1:8792` has
   exited; a short pages-only walk beside it is enough to make the timing states miss.

# fixup-AD evidence — a cross-channel match must beat chance (2026-10-05)

The report is `docs/prompts/fixup/reports/AD-cross-channel-against-chance.md`. This folder holds what it rests on.

- `measure_ad.py` — before (W's rule) → after (AD's rule) on W's three families (F-130, F-119, F-39) and on every
  g-05 family with an M2_aug member (124 families, 1,012 M2_aug members). Runs on a scratch copy of W's sandbox
  database (`webui/runtime/20261004-184434`), made with SQLite's backup API; channel files are only read (mmap). W's bin
  is a pure function of (lag, r), so the "before" column is re-derived exactly from the (lag, r) AD measures on the same
  windows, and for the three families also read off W's stored rows (they agree: 17 · 24 · 19 etc.).
  `python webui/screenshots/fixup/AD/measure_ad.py <scratch dir>` — about 5 minutes.
- `measure_ad.json` — every number the report's §2 tables carry, per family, plus the flagged member ids.
- `measure_ad_log.txt` — the script's printed output.
- `smoke-*.png` — the seven `webui/smoke_pages/zzzz_ad_suspected_artifact.json` states from the gate walk: Classify
  against chance on F-130, an edge carrying its chance test (m-1295), *Send suspected artifacts* opening the Review
  queue (every channel on one true-mV axis, the member bold, the flagging sibling's r · lag · amplitude · chance),
  the queue sent once, Recurrence's flag line with the flagged cell still red, the four Settings keys, and the Seed
  page's exclusion zone at m/2 and settable.

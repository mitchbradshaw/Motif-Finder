# fixup-AE evidence

- `pages/` — the twelve AE smoke states (`webui/smoke_pages/zzzz_ae_library_view.json`) from the gate walk, a fresh
  `--sandbox` bridge on a copy of the real database (port 8771, private build).
- `backfilled-copy/` — the same twelve states against a bridge on the scratchpad copy AFTER the backfill (`is_pure`,
  the window's fall count and `scale_band` stored): the scale-band badges, the `[2 falls]` flags and *pure only* doing
  something. This is what the real database shows once the researcher runs the backfill.
- `measure_floor.py` / `measure_floor.json` — what the floor hides per store and per dataset, families before → after,
  *judged* by exact span equality vs the resolver, and the rose reference, on a backfilled COPY of the real database
  (`scripts/fixup_d_backfill_features.py --db <copy>`; the real file was only read, through the sqlite backup API).
  Run: `python measure_floor.py <db>`.

Report: `docs/prompts/fixup/reports/AE-library-floor-and-indexes.md`.

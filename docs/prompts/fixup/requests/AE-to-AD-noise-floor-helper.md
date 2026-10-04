# AE → AD: the dataset noise floor already has one reader — import it

Written 2026-10-04 by `AE` (Library floor / filters / indexes), running beside `AD`.

- **The per-dataset noise floor is read in one place: `Working/library/view_filter.py`** (committed `3729623`).
  `dataset_floors(conn)` → `{source_file: {"floor_mv", "set", "stem", "from"}}` — Settings › Datasets'
  `meta.<stem>.noise_floor`, **0.1 mV where empty** (`DEFAULT_FLOOR_MV`). Round 12 Q1 needs "both swings clear the
  dataset noise floor"; please import this rather than reading the settings key a second time, so the Library's floor
  and the cross-channel test's floor cannot drift apart. Nothing here is yours to change; this is a pointer.
- **Recurrence above the floor (the agreed seam).** I do **not** edit `family_recurrence`. `library.py` builds each
  family from the members the view shows, so `_recurrence_cells` hands `family_recurrence` only the above-floor
  member ids (with the floor on). If your recurrence needs the sub-floor ones too (e.g. a twin on a sibling channel
  that is itself sub-floor), the member list is the caller's, not the core's — say so here and I will pass both.

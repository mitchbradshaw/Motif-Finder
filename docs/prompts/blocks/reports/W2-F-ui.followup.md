> Filed by the manager session, 2026-10-14 16:52 — the final message of implementer agent `adc5c4378118b320a`,
> resumed for the families follow-up (both family blocks drawn, block-level smoke states), verbatim.

# W2-F families follow-up — report

Both family blocks, `catalogue.shape_families` and `interrogation.event_families`, are now drawn, with glyphs and four block-level smoke states. Type-check, production build and the venv test set all pass; smoke itself has not been run (no database here).

The exemplar check you asked for holds on the real blocks. Every exemplar window W2-E's Shape families names has its own label equal to the family it is named for. Every exemplar event Event families names belongs to that family by the `family` column. Nothing in W2-E needed changing.

## In plain words

Each family block now shows a table with one row per family: how many members it has, a verdict badge, and how alike the members are next to what noise of the same colour scores. The badge is one of:
- **"no better than noise"** (amber);
- **"untested"** (grey) — Ward draws no noise null;
- **"null not trusted"** (grey) — k-Shape; hovering shows the block's own reason (`null_caveat`);
- **"beyond noise"** (green) — only when the block says it passed a trusted null.

Event families also draws each event on the trace in its family's colour:
- Events in no family are grey with a red dashed outline, and hovering shows why, including `no_window:<reason>`.
- Each family's typical event is marked with a small purple triangle.
- The legend shows the group keys exactly as Intervals will see them: `<n>~noise_like`, `<n>~untested`, `-1`.
- When the step before found no events, the page says so instead of showing a blank.

Every verdict comes from the block itself; the page never recomputes one.

## What changed

**Server: `webui/server/serialize.py`**
- **Shape families (Grouping):**
  - Sends `families` (each family's fields read straight from the block) and `family_summary` (fractions placed and confident, omissions, warnings, notes).
  - Names `-1` "in no family".
  - Exemplars use the existing `exemplar_windows` checks.
- **Event families (SpanSet):**
  - Sends per event `family`, `family_omit_reason`, `family_noise_like` and `group` (capped the same way the spans are), plus `families`, `family_summary` and the block's own summary line.
  - Sends `exemplar_events`, checked loudly. Each of these raises an error instead of drawing a quiet substitute:
    - an index outside the events;
    - an event of another family;
    - a non-whole index;
    - anything other than `{"<family>": <event index>}`.

**Client**
- **`GroupingView.tsx`:** `FamilyTable`, `FamilyBadge`, the coherence cell (verdict from `svd_entropy_beyond_noise`), and `familyColour` with grey for −1.
- **`SpanSetView.tsx`:** `EventFamiliesView` and `EventFamiliesKey`.
- **`registry.tsx`:** the Grouping page shows the family table under the sizes; the SpanSet-to-SpanSet page leads with the families when the payload carries them.
- **`glyphs.tsx`:** one glyph per block.
- **`api.ts`:** `FamilyRow` and `FamilySummary` types.

**What I left alone:** `views.py` needed no new row, because both conversions (`windowset->grouping`, `spanset->spanset`) already exist. `webui/server/templates.py`, the adapters and `Working/` are untouched.

## Red → green

- **Red `bc6b54a`, tests only:**
  - `tests/test_webui_family_views.py`, venv, running the two real blocks on `_event_families_synthetic`'s two-shape recording through `to_payload`: 5 failed, 1 passed. The one that passed already is the shape-exemplar label check, which W2-E's medoids satisfy.
  - Two client pins in `test_webui_w2f_ui.py` failed.
- **Green `d01bd62`:**
  - `tsc -b` and `vite build` clean, run on the scratch copy; the junction was inside the scratch copy only and has been removed.
  - venv `-n 4`, 9 files: `test_webui_family_views`, `test_webui_block_views`, `test_webui_library`, `test_block_standard`, `test_webui_serialize`, `test_webui_w2f_ui`, `test_import_boundaries`, `test_templates`, `test_webui_run_routing` — **343 passed, 3 xpassed**.

## The smoke states as they stand (`zz_analyse_run.json`, all block-level, unverified)

Where a span may honestly produce either result, the state accepts either one (an either-or selector).

- **`w2-shape-families-thumbnails`** (chain):
  - Builds the chain from the noise_threshold template: keep its detrend step, delete its detector, insert Sliding windows and set them to 60 s, then insert Shape families at its defaults (HDBSCAN). Runs on the 2 h example span.
  - I chose 60 s windows rather than the 600 s default so the span always has windows (about 120), enough for HDBSCAN's minimum family of 10.
  - Should show: row 2 a WindowSet, row 3 a Grouping, and no SLURM refusal.
- **`w2-shape-families-table`** (`analyse/block/2`):
  - Should show: the `windowset->grouping` view, the cluster strip and `family-table`.
  - Then either a badge per family plus the block's exemplar-rule caption, or `family-table-empty` ("no family was made").
- **`w2-event-families-thumbnails`** (chain):
  - Steps: noise_threshold template on the example span, then Event shape, then Event families.
  - About 2 h of work, well under the 15-minute routing limit.
  - Should show: rows 3 and 4 as SpanSets, and no SLURM refusal.
- **`w2-event-families-on-the-trace`** (`analyse/block/3`):
  - Should show: the `spanset->spanset` view, `event-families-lead` and `family-table`.
  - Then either the `event-families` plot or `event-families-none` ("the step before found none").

## `git log --oneline` (new commits since fix round 1)

```
d01bd62 w2-f: the families -- Shape families' table and Event families on the trace, glyphs, block-level smoke states
bc6b54a w2-f: tests (red) -- the families: Shape families and Event families serialised and drawn
ddf323e w2-f: merge main (3940aa7)
9f30161 w2-f: merge W2-E families (fix round 1, 1301a0f)
```

## Risks

- If W2-E's fix round 2 renames any key in `FAMILY_KEYS`, or the per-event column names, the serializer passes that field as null without an error, so the matching badge or number goes blank. The pin test catches the main keys. Tell me what moved and I will update both sides.
- On a 2 h example span both family states may well land in the "no family" or "no events" branch. They still check the views render, but they do not prove the badge rows draw. The synthetic tests cover the rows.

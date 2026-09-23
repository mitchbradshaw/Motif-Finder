# Report — Fixup D: per-event features as analysis blocks

Run 2026-09-23 on `main`, in the main checkout, in parallel with prompt `C` (different files; shared docs
staged hunk by hunk). Commit prefix `fixup-d:`. The first commit, `06b767b`, touches only `tests/` and fails
52 tests plus two collection errors. The bridge ran in `--sandbox` throughout, on a private port (8766)
serving a private client build. Nothing wrote to the real `DATA/db/annotations.sqlite`; it was read once,
read-only, to count sequences.

**What exists now, in one paragraph.** A detector's events can be measured and timed in one chain:
`drop_event_features` = the drop detector → **Event shape** (every shape measure, polarity-neutral, each
defined rule printed beside the numbers, the steepest-slope rose in meta) → **Intervals** (the interval
before and after every event, per group, with the train's regularity statistics). `spike_event_features` is
the same after **Invert**. The Library carries each motif's features in **`motif_features`**, keyed by
content hash, with the detector's own `drop_depth_mv` beside them. **Interrogation › Sequence** reads any
stored sequence and draws the rose across its events. No eighth type: `SpanSet` gained an optional
`features` table, mirroring `WindowSet`'s.

---

## 1. The measures, and the exact rule for each one I had to define

All in `Working/interrogation/event_shape.py`. Each event is **oriented** (a drop as it stands, a spike as
`-x`), its anatomy is found with **detect5's own functions**, it is measured, and signed quantities go back
to the recorded frame. So a spike's height and a drop's depth are one column (`event_amplitude_mv`), and a
spike's steepest rise is a positive `max_slope_mv_s`.

**Anatomy, reused.** Two sources, in this order:

1. **An upstream block that already located the event.** Upstream `onset_idx` / `extremum_idx` columns, or
   a store's own onset / trough for a Library motif, *are* the event.
2. **Otherwise, detect5's rules.** The steepest sample of `np.gradient`. Then the knee:
   `detect.find_trough`, three samples shallower than `knee_frac` (0.05) of the steepest. Then
   **extremum** = the lowest sample between the steepest and the knee. Then **onset** =
   `detect5.refine_onset`, then `walk_back_to_shoulder` bounded by the window start.

The one addition is the extremum snap. On a V-shaped bottom the knee lands one sample *past* the minimum,
because the rising sample is the first "shallow" one.

| measure | rule (printed in `meta["rules"]` and on the page) | defined here? |
|---|---|---|
| `event_amplitude_mv` | \|x[onset] − x[extremum]\| — a drop's depth, a spike's height | reused (detect5's depth) |
| `precursor_height_mv` | x[onset] − min of the window before it: a drop's rise, a spike's dip. **Not** detect5's `rise_height_mv`, which is 0 unless rise-triggered (85.8 % of `drop_motifs10`) | **defined** |
| `event_width_s` | onset → extremum. For a drop, detect5's `fall_duration_s` | reused, made polarity-neutral |
| **`recovery_time_s`** | extremum → the first return to **extremum + `recovery_frac` × amplitude** (default **0.5**, half recovery), linearly interpolated. Searched past the window's end, but never into the next event's window and never further than `recovery_max_mult` (10) event widths. Not reached → **NaN, counted** (`meta.n_not_recovered`), never 0 | **defined** |
| `duration_s` | onset → recovery | **defined** |
| **`fwhm_s`** | full width at half maximum. The baseline is the onset level, so the half level is x[onset] − amplitude/2. FWHM runs from the last crossing on the way out to the first crossing on the way back, both interpolated, with the same search bound as recovery | **defined** |
| `max_slope_mv_s`, `onset_slope_mv_s`, `chord_slope_mv_s`, `peakedness` | `gradients.fall_gradients` over [onset, extremum]: `np.gradient × fs` once, in mV/s | reused |
| `span_ptp_mv` | peak-to-peak over the window (detect5's `fall_dominance` denominator) | reused |
| `polarity` | `drop` (default), `spike`, or `auto`. `auto` takes the window's fastest edge. Its rule says where it fails | **defined** |
| `interval_before_s` / `_after_s` | onset-to-onset, per group, never pooled; anchored on the upstream `onset_idx` when there is one, else the span start | consolidated (§3) |

**Why recovery defaults to 0.5.** It is the level FWHM already uses, so `duration` and FWHM end on the same
landmark. And fungal drops recover over tens to hundreds of seconds, often into the next event, so a 90 %
level is often never reached. It is a parameter (0.01–1.0), and the rule prints the value used.

**Units.** The core takes `x` as volts (detect5's convention) and multiplies by 1000. The `units` rule says
so. The serializer adds `features_unit_note` when the recording's declared unit is not V. `L_LM_Jul_26_J` (mV)
reads 1000× large through this block exactly as it does through detect5, which is open question Q-X2.8.

## 2. The seed-store comparison: 410 events against `events.csv`

`scripts/fixup_d_evidence.py` → `webui/screenshots/fixup/D/seed-comparison.json`. Each event is measured on
the store's own `detrended_mv` snippet: the trace the detector measured on, and the one the Library's
content hash covers. So any disagreement is a disagreement of rule, not of input.

| | events | depth = `drop_depth_mv` | width = `fall_duration_s` | max slope = `max_slope_raw × 1000` | FWHM measured | recovery measured |
|---|---|---|---|---|---|---|
| **detector's own anchors** (the Library path) | 410 | **410 / 410** (max diff 1.4e-14 mV) | **410 / 410** | **408 / 410** | 240 | 240 |
| own anatomy, `walk_onset_back` on (the chain default) | 410 | 69 exact; median diff 0.28 mV, p90 1.6 mV | 85 exact; median 1 s | **393 / 410** | 239 | 239 |
| own anatomy, `walk_onset_back` off (the seed's flags) | 410 | 134 exact; median 0.20 mV | 149 exact | 393 / 410 | 239 | 239 |

The slope check doubles as the unit check: `max_slope_raw` is V/s with `fs` applied once, so mV/s is
`raw × 1000` with no second factor. That holds on 408/410 from the detector's anchors.

**Where I disagree with the detector, and which is right.**

- **The onset: 297 of 400 same-event cases put it earlier, by a median of 1 sample (p5: 16 samples). Mine is
  right about depth; the seed's number is the older rule.** The seed store (`drop_motifs5`) predates
  detect5's `walk_back_to_shoulder` fix. Its onset is the first sample steeper than 8σ of noise, which on a
  rounded shoulder is part-way down the fall. detect5's own docstring calls this "drop_motifs10 defect 4":
  *"without this the depth the gates read is measured from part-way down the fall."* Measured from the
  shoulder, depths run a median 3.6 % larger (p95 +41 %). Turning the walk back off halves the disagreement
  (134 exact), but does not remove it. My onset is the knee read back from the steepest sample; the seed's
  is the later of that knee and its first noise crossing.
- **The extremum: 271 on the same sample, 57 one sample earlier, the rest within 3 samples on all but 10.**
  Of the 57, `find_trough` lands the trough one sample past a V-shaped minimum, and I take the minimum.
  Neither choice is wrong. The detector's is the end of the steep part; mine is the lowest point. The
  difference is one sample of width.
- **10 events: a different fall entirely. The detector is right.** A stored snippet carries minutes of
  context (pre-context up to 443 s), and on these 10 the steepest fall in the snippet is a neighbour. Four
  examples: `id024_r2_1615590` measures 2.3 mV where the event is 23.2 mV; `id024_r2_1577612`;
  `id024_r2_1599908`; `id034_r16_166430`. (The next-largest depth disagreements, `id028_r6_1426649` and
  `id028_r6_1462042`, are the SAME fall: the onset walks back ~97 samples to the shoulder, so 14.8 → 20.8 mV,
  which is the onset case above.) **This is why Library features use the detector's anchors**: where
  a detector said which fall it meant, that is the event. Own anatomy is for spans nobody anatomised. In a
  chain those are the detector's own tight windows, not minutes of context.
- **Max slope, 2 of 410 from the detector's anchors (`id010_r4_1370559`, `id022_r1_1048273`).** The onset sits
  on the snippet's first sample, where `np.gradient` is one-sided. The detector took the gradient on the
  whole channel. The detector is right, by at most 0.10 mV/s; this is a snippet-edge artefact.
- **Polarity: `auto` called 50 of the 410 seed drops spikes (45 sharkfins, 43 of them in `id029`). The
  default is therefore `drop`.** A window holding a slow rise and a fast fall of similar size defeats any
  whole-window polarity rule. The median-excursion rule (`grouping/bases.polarity`) was tried first and
  failed on a third of a synthetic sharkfin train; fastest-edge failed on these 50. Every registered
  detector finds drops, and the spike route is **Invert + `upstream_inverted`**, which is exact.
- **Recovery: 170 of 410 not reached, all on sharkfin spans** (`id029`, `id024`, `id028`, `id001`,
  `id003`). A sharkfin falls and stays low until the next rise, so half recovery lies beyond the snippet or
  the next event. That is a measurement, not a failure: NaN and counted, never 0.

## 3. What I reused, and the "why not reuse" sentence for what I did not

| reused as-is | where |
|---|---|
| `gradients.rose_data`, `fall_gradients`, circular statistics, KS uniformity (not Rayleigh), `scale_caption` | the rose in the block's meta and in Interrogation › Sequence. Unchanged; `rose_data`'s group key takes the sequence key |
| `detect.find_trough`, `detect5.refine_onset`, `walk_back_to_shoulder` | the anatomy |
| `sequences11._regularity` / `_drift` | **moved** to `Working/interrogation/intervals.py` as `regularity` / `drift_ratio`; `sequences11` binds its old names to them |
| the three interval implementations | `store11.interval_stats`, `clusterk1.isi_by_channel` and the aggregate route now call `inter_event_intervals`; none deleted; their outputs are pinned in `tests/test_adapter_intervals.py` |
| `identity.content_hash`, `importers.event_store.read_event_store` | `motif_features` keys and snippets |
| `MAX_SLOPE_UNIT_NOTE` (store11) | as the detector-slope conversion (`raw × 1000`, one `fs`) |

| not reused | why not |
|---|---|
| `data_analysis.half_width` | it finds the most prominent **peak** with `find_peaks` and returns `min(left, right)` **in samples**: the narrower half, not the full width. FWHM is defined beside it |
| `store11.py` / `figures11_s2.py` angles | a second, parallel rose implementation for report figures. One rose rule in the tree: `gradients` |
| the UI fixture `recovery_s` (`webui/pages/inventory/…`) | a prototype number, not a definition |
| the drop detector's label string `onset=…;trough=…` | the pattern this prompt must not extend. Anatomy is columns |
| **the browser's recovery** (`client/src/api/interrogation.ts`) | found late. It is a second definition (90 %, on a 400-point *decimated* snippet) that returns **0 s** for an event that never recovers. Not changed here: it is the Interrogation page's code. Flagged in §8 and in `03` I1 |

## 4. `SpanSet.features`, and what it might break

`Working/types/spanset.py`: `features: Optional[pd.DataFrame] = None`, with the one-row-per-span invariant,
`features.parquet` beside `spanset.json`, and `__eq__` comparing frames, all exactly as in `WindowSet`.
Rewriting a directory in place removes a stale parquet. Every existing caller constructs with
`features=None` and serialises the same JSON as before (pinned).

**What it might break, checked:**

- `SpanSet` is now `eq=False` with its own `__eq__`, so it is **no longer hashable**. Nothing hashes one: the
  full suite passes, and a grep found no use as a key or set member. A future `set(spansets)` would raise.
- **The executor now skips writing detections for a SpanSet whose block took a SpanSet in**
  (`Working/execution.py`). Before, a detector followed by two feature blocks would have written every event
  three times. Only blocks with `input_kind="spanset"` are affected, and before this prompt there were none.
- `Working.recipes.STAGES` gains `interrogation` (with its display name and file abbreviation in
  `artifacts.py`). Additive.
- `pandas` is now imported by `Working/types/spanset.py`, as `windowset.py` already did.

## 5. The rose over a real sequence

`webui/screenshots/fixup/D/sequence-1-rose.png`: sequence 1, `oyster_id10_ch3_1362824s`, M2_aug CH3,
67 events, unit V. All 67 were read from `motif_features` after the sandbox backfill. Scale raw, 45° = 1 mV/s.
**Mean direction −31.7°, R = 0.991, circular sd 7.7°, KS p = 8.9e-17** against uniform over the quadrant: this
train's falls are strikingly alike in steepness. `sequence-20-rose.png` shows `reishi_id903_ch3_606s`
(Fig2A, 114 events): mean −47.6°, R 0.973. Its unit is undeclared, and the page says so beside the mV.

Also `block-event_shape.png`, `block-intervals.png` and `chain-drop_event_features*.png`: the template
imported and run from the UI on the example span (M2_aug CH1, 336–338 h). It finds 4 events, measured and
rosed. Event 2's extremum is exactly the seed store's trough for `id001_r1_1213252`, and its depth is 15.2 mV
against the seed's 15.06 mV.

## 6. `motif_features`, the table

`schema.py::_MOTIF_FEATURES_SCHEMA`, created by `init_db` (additive, idempotent). Columns: `content_hash`,
`fs`, `source` (`interrogation.event_shape` | `detector`), `feature`, `value`, `rule_version`,
`computed_at`, with UNIQUE(`content_hash`, `fs`, `source`, `feature`). It is long, not wide, so the next feature
block adds rows rather than columns. The only writer is `Working/library/features.py::backfill_library`:
idempotent, it counts every skip with a reason, and it refuses to file a measurement under a hash its
snippet does not reproduce. Recorded as a versioned amendment in `docs/LIBRARY_STORAGE.md` §3.4 (L8b).

**Run on the sandbox copy only** (`webui/runtime/20260923-221617/`): 3,599 entries measured, 4 annotation
entries skipped (`no_store_snippet`), 71,980 values. The detector's `drop_depth_mv` puts **1,095 of
`drop_motifs10`'s 3,189 imported entries (34.3 %) under 0.1 mV, and 0 of the seed store's 410.** That is the
number Q-X2.5's floor filter must filter on. **To fill the real database** (the researcher's call):

    python scripts/fixup_d_backfill_features.py --real

A chain run writes nothing to it, on purpose. A chain's detrend differs from the store's, so its waveform
would not hash to the Library's H, and a feature filed under H would describe a different waveform than H
names. Comparisons (the rose, interval statistics) are never stored.

## 7. Defaults taken

| default | value | why |
|---|---|---|
| polarity | `drop` | every registered detector finds drops; `auto` misread 50/410 |
| `recovery_frac` | 0.5 | §1 |
| `recovery_max_mult` | 10 event widths, never past the next window's start | bounded, like detect5's `window_cap_mult` |
| anchors | upstream columns / the store's own when present, else detect5's rules | §2 |
| rose | `raw`, 45° = 1 mV/s (`gradients.DEFAULT_SLOPE_REF_MV_S`) | the module's own default; the scale is a parameter |
| intervals anchor | measured onset when upstream, else span start | printed as `anchor_used` |
| stage / category | `interrogation` / `control` | `STAGES` gains one; `control` is the tab the concept frames filed interrogation blocks under |
| cost | calibrated linear models via `block_cost.register_cost_model` (all three O(n)) | `COSTED` gains the three |

## 8. Items left

1. **The Interrogation Aggregate page fabricates features.** For the live `spike-shape` upstream,
   `featureOf` returns `half_width_s = duration × 0.84`, `rise_s = × 0.31` and `isi_s = × 4.2`, drawn as
   measurements. `api/interrogation.ts` computes recovery in the browser and reports a never-recovered event
   as 0 s. The core now measures all of these, except rise time, which no block measures. **Not changed
   here** (page code, and a half-fix would put NaN attributes into React, which the smoke gate reads as
   console errors); raised as a follow-up task and in `03` I1. This is the highest-value item left: it is
   the per-event statistics path both readers use.
2. **The real `motif_features` is empty** until `--real` is run (§6).
3. **No Library filter / sort / group over `motif_features` yet** (Q-X2.5 / Q-X2.7 own it).
4. **No gesture writes a train** (Q-X3). Sequences come from `drop_motifs11/sequences.csv` and 30 human
   `needs_extraction` rows with no members.
5. **Fan-out (Q-B-CHAIN) not built.** The linear chain Event shape → Intervals already gives shape and
   timing of the same events in one run, which may answer part of the researcher's case.
6. **The block page draws the feature table, rose and rules, but no scatter** (width vs recovery). The
   Interrogation Aggregate page is where that belongs, once item 1 is fixed.
7. **Q-X2.8 applies to this block** (mV recordings read 1000× large); the page says so via
   `features_unit_note`.

## 9. Files touched outside a strict reading of the prompt

- `Working/execution.py`: the skip rule, §4. Needed, or every feature block duplicates detections.
- `Working/recipes.py`, `Working/artifacts.py`: the new stage.
- `Pipelines/drop_motifs/{store11,clusterk1,sequences11}.py`: the consolidation the prompt asked for.
- `webui/server/interrogation_routes.py`: the aggregate route's interval now uses the core; two sequence
  routes added.
- `webui/client/src/interrogation/{SequencePage.tsx (new), index.tsx, SourcePage.tsx}`: the sequence page,
  its route, and one header link from the Interrogation source page.
- `tests/test_adapter_spec.py`, `tests/test_end_to_end.py`: hard-coded adapter counts 33 → 36. They encode
  "the shipped adapters", which this prompt deliberately changes.
- Two slips in my own red-commit test arithmetic, fixed in the implementation commit: the sign of a
  hand-worked onset slope, and a helper called with too short a length. Also a deliberate change to the
  red tests' polarity default (`auto` → `drop`), made after the seed comparison, with its reason in §2.

## 10. The gate

| gate | result |
|---|---|
| `pytest -n 4` (conda), after the implementation commit, which includes prompt C's `a9d346a` | **1775 passed, 6 skipped, 0 failed**, against the 1660 / 6 / 0 baseline. No failure set to compare: nothing fails |
| `tests/test_webui_*.py` under `webui/.venv` | **259 passed, 1 failed, 3 xpassed**. The one failure is `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`, the pre-existing failure the prompt names |
| `npx tsc -b`, `npm run build` | clean |
| `webui/smoke.py`, full, against a `--sandbox` bridge restarted immediately beforehand (port 8766, private dist, `SMOKE_SHOTS` in the scratchpad) | **548 screenshots, 4 failures**: the four Settings registration-state states (`datasets--import-check-fails-fs-unknown`, `datasets--import-check-passes-MJu26a`, `models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`), which fail the same way on every bridge. 0 browser console or page errors. One server error line, the deliberately provoked run-13 failure (allowed). All five fixup-d states pass: the feature template imported, the Event shape block page, the three blocks' cards in the insert modal (two states), and the sequence rose |

A first full smoke run also showed Windows asyncio `WinError 10022` socket-teardown lines, which did not
recur on the rerun. It also failed my own glyph state: the Glyphs page is demo-only and lists no registered
adapters, so the state now checks the insert modal instead.

## 11. In short

Every per-event measure the researcher named now comes out of one block. Each measure I had to define
prints its rule beside its number. The intervals come out of a second block, and the linear chain gives both
for the same events in one run. The Library carries each motif's features and the detector's own depth,
keyed by content hash. The rose compares slopes across a real sequence.

The comparison against the seed store is exact where it should be: depth and width 410/410, slope 408/410
from the detector's anchors. Where it isn't, the report says which answer is right and why. The seed's onsets
start part-way down the fall; 10 own-anatomy events lock onto a neighbouring fall in the context; 2 slope
misses are snippet-edge artefacts.

The biggest item left is outside this prompt's files: Interrogation's Aggregate page still fabricates three
features and reports never-recovered events as 0 s.

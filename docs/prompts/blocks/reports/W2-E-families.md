> Filed by the manager session, 2026-10-14 14:29 — the final message of implementer agent `a5a91c3213452c835`
> (branch `worktree-agent-a5a91c3213452c835`, base `c2e6e05`), verbatim.

# W2-E report: `catalogue.shape_families` and `interrogation.event_families`

**Base.** I fast-forwarded to `c2e6e05` first, as instructed. Both commits sit on top of it.

## 1. In plain words

The Library can already sort events into families of similar shape with Ward, k-Shape or HDBSCAN. These two blocks let an Analyse chain do the same thing, with the very same code, on the events the chain itself just detected.

- **`catalogue.shape_families`** turns a set of windows into a family label per window.
- **`interrogation.event_families`** is the one that matters:
  - It cuts a window around each event, sorts the windows into families, and writes each event's family onto the event.
  - By default it also writes the family as the event's *group*. So the Intervals block after it times each family separately: "family 1 comes every 40 min, family 2 every 3 h", in one straight chain.

Every family also carries two signs of whether it is real:
- **The noise flag** (W2-B's): did the family beat phase-randomised copies of its own members, i.e. noise of the same colour?
- **The SVD entropy**: how far the members are copies of one shape, shown beside what that noise scores.

Both appear in `meta` and in the summary line.

**What it found on synthetic data:**
- **The template recording:** inverted sharkfins every 40 min and square dips every 3 h, on an AR(1) background, over 48 h.
  - The template found every event (88 of 88).
  - It sorted them into the right two families (ARI 1.00, on two seeds).
  - Intervals' median gap was 2,389 s and 2,394 s against 2,400 s, and 10,807 s and 10,794 s against 10,800 s: under 1 % off.
- **Two clear-cut shapes** (drops and squares) on four coloured backgrounds: HDBSCAN and k-Shape both give ARI 1.0 and two families, neither flagged noise-like. Both families' SVD entropy sits below its noise null.
- **No structure** (events that are phase-randomised AR(1) or random-walk noise): HDBSCAN places at most 30 % of them, and usually none. In the tested cases Intervals reports no family rhythm.

**One finding the manager should know.** Event shape's `onset_idx` is unreliable on flat-bottomed or ramped events. On square dips it landed up to 230 s late, at the dip's end.
- Anchoring windows on it ruins the families: ARI 0.13–0.27, against 1.00 when anchored on the span start.
- So `event_families` defaults to `anchor="start"`, which departs from W2-A's default. `anchor` is still a parameter.

## 2. Files

Created:
- `Working/Catalogue/shape_families.py` — the core. Imports no adapter and no UI.
- `Adapters/catalogue_shape_families.py` — WindowSet → Grouping. Also holds the shared param builder and meta helpers.
- `Adapters/interrogation_event_families.py` — SpanSet → SpanSet + family columns.
- `tests/_event_families_synthetic.py` — the two-rhythm recording, the noise events and the two-shape families.
- `tests/test_shape_families.py` (33 tests), `tests/test_adapter_shape_families.py`, `tests/test_adapter_event_families.py`, `tests/test_template_event_families.py`.

Modified:
- `Working/interrogation/intervals.py` — new shared `write_group_columns(upstream, keys)`.
- `Adapters/interrogation_trains.py` — now uses that helper instead of its inline copy. Behaviour is unchanged and its tests pass. This file is outside my list, but the prompt asked for the helper to be shared.
- `Working/types/windowset.py` — `BOOKKEEPING_COLUMNS` gains `family`, `family_omit_reason`, `family_distance`, `family_noise_like` and `group_upstream`.
- `tests/test_adapter_event_windows.py` — the pinned bookkeeping set gains those five, on purpose.
- `tests/test_adapter_spec.py`, `tests/test_end_to_end.py` — adapter count 52 → 54.

## 3. The algorithm as implemented

**The public function for the manager's shape null:** `Working.Catalogue.shape_families.shape_families(waveforms, *, method="hdbscan", params=None, max_nan_frac=0.1, seed=0, coherence_null_draws=5)`.
- It takes the cut waveforms as an (n × L) array or a list of 1-D waveforms.
- It returns `ShapeFamilies` with:
  - `.labels` (1..K, −1 = none), `.omit_reason`, `.distance`;
  - `.families` — each with `.flags` (W2-B's) and `.coherence` (W2-B's `svd_entropy` dict, including `null_median`, `null_p05` and the squared variant);
  - `.fraction_placed`, `.fraction_confident`, `.fit_summary`.
- `event_families(x, fs, spans, *, anchor, length_s, pre_frac, max_nan_frac, method, params, seed)` is the exact path the adapter runs. It calls W2-A's `event_windows` and `cut`, then `shape_families`. A test pins that the adapter's per-event `family` equals `shape_families(EW.cut(...))`.

Steps:
1. **Screening.** A row with an inf is `infinite_values`. A row with no samples, or more missing samples than `max_nan_frac`, is `missing_values`.
   - **Adaptation:** a row with a few NaNs (no more than the cutter itself admits) is linearly interpolated and counted in `n_gap_filled`. The Library's methods would otherwise silently drop any window holding one missing sample.
2. **Grouping.** `engine.run_grouping(items, unit="single_motifs", basis="shape-distance", method, params)`. Each item is honestly `{member_ref: row, values: waveform}`, which is all a shape-distance grouping reads.
   - The engine prepares the vectors (`ward.shape_vectors`) and applies `min_group = 10`.
   - Flags and `fit_summary` are read from `Family.flags` and `GroupingResult.fit_summary`. Nothing is re-derived.
3. **Numbering.** Families are renumbered 1..K by size, largest first. The engine's label rides along as `library_label`.
4. **Distance.** `family_distance` is the engine's distance from a member to its family's medoid, on the method's 0–1 scale.
5. **Coherence.** W2-B's `svd_entropy` on each family's members, aligned to the medoid, with its null. `coherent_beyond_noise` means `svd_entropy_norm < null_p05`.
6. **Exemplars.** Each family's exemplar is the engine's medoid: a member, at distance 0.
7. **Caps.** HDBSCAN and k-Shape fit at most their `sample` and assign the rest, as W2-B does. Ward is refused past 5,000 waveforms, in words naming hdbscan and kshape.

**Params.** `method` takes its choices from the registry's `methods_for("shape-distance")`. Every method parameter is flattened as `<method>_<param>`, because the Analyse form renders flat `ParamSpec`s. `min_group` and `resample_length` appear once, unprefixed. Only the chosen method's params are passed on.

**`event_families` columns:**
- `family`;
- `family_omit_reason` — "" when placed, `no_window` for events the cutter left out;
- `family_distance`;
- `family_noise_like`.

`write_group` (default on) writes `group = family` via the shared helper (`<upstream>/<family>` plus `group_upstream` when an upstream group exists).
- **My call:** a noise-like family's key is `<n>~noise_like`, so Intervals' per-group table says so on its face.

**`shape_families` inputs.** It uses the Trace shape vectors (`shape_file` / `shape_row`) when present. Otherwise it slices windows from `x` using channel-absolute starts; a window outside the span is counted as `outside_span`.

**Why not extend `shape_cluster`:** the reason is in the core's module docstring. That block is RQ1's split-aware, tree-keeping, mapping-carrying, freezable training-pool clusterer.

## 4. Tests

**Red:** `e194e43`.
- The three core and adapter test files errored at collection (ImportError: no `Working.Catalogue.shape_families`).
- The template test: 2 failed, 2 errors (unknown adapter `interrogation.event_families`).

**Green:** `e7ef98b`.
- The four new files: 33 + 19 + 4 passed.
- With `block_standard`, `adapter_spec`, `import_boundaries`, `templates`, `end_to_end`, the trains/intervals/event_windows tests, `grouping_adapter`, `library_grouping_methods` and `library_coherence` (run with `-n 4`): 490 passed, 1 failed.
  - The failure was `test_adapter_trains::test_many_groups_and_many_events_run_in_linear_time`: 2.0 s against a 1.5 s limit, under load. It passes alone (16/16). That test does not use `write_group`.

One expectation from my red commit was wrong and is fixed in the green commit, as its message says: `meta["omitted"]` is `{}` when nothing is omitted.

What the tests pin:
- method choices are the registry's;
- the flattened params round-trip;
- **Ward through this block reproduces `run_grouping`'s Ward exactly** — partition, omission reasons, medoids and distances;
- two clear-cut shapes × 4 backgrounds × {hdbscan, kshape}: ARI ≥ 0.9, flags tested and not noise-like, coherence below its null;
- the no-structure case: fraction placed < 0.5 (3 colours × 2 seeds);
- exemplars equal the engine's medoid, are members, and sit at distance 0;
- coherence equals `svd_entropy` called directly;
- a mixed set scores less coherent than a pure family;
- gap filling and the missing/inf reasons, with counts that add up;
- the sample cap passes through;
- the Ward refusal;
- determinism;
- the rules text;
- the estimate;
- the core's imports;
- the adapter specs and bounds;
- channel-absolute slicing, `outside_span`, Trace shape vectors used when present;
- the meta keys, and the noise-like flag reaching the summary and warnings;
- the empty inputs;
- the family columns, `no_window`, and that the columns are bookkeeping;
- `write_group` on/off with an upstream group;
- trains and families share the same helper object;
- the template's acceptance criteria.

`tests/test_webui_*` skip under conda, so the bridge's serialisation of these outputs is not tested here. Run `test_webui_block_views` / `test_webui_serialize` with `webui/.venv`. I did check that the SpanSet round-trips through `to_path` / `from_path` and that the meta passes `json.dumps(allow_nan=False)`.

**Cost.** Estimate against actual for `event_families`: 120 h at 1 Hz with 1,434 events. The machine was loaded by other agents.

| Method | Estimate | Actual |
|---|---|---|
| hdbscan | 27.8 s | 23.9 s fresh; 65–114 s under load |
| kshape (auto k) | 237 s | 107–200 s |
| ward | 5.7 s | 2.4–3.2 s |

- The estimate cannot see the upstream events. It assumes one event per 300 s of span (minimum 50), which is denser than the real dense chains.
- The grouping part uses W2-B's coefficients (1,400 windows: 27 s actual against 23.5 s estimated).
- Coherence was measured at 1–3 ms per member; the model uses 2 ms.

## 5. Integration snippets

**Template** (verbatim from `tests/test_template_event_families.py`):
```python
{
    "name": "event_families", "kind": "interrogation", "version": 1,
    "description": "Families of detected events, each timed on its own — 'do family A events come every 40 "
                   "minutes and family B every 3 hours?' in one chain: baseline removal → noise threshold (every "
                   "stretch more than 4 σ_n below the detrended trace's median, as the noise_threshold template) → "
                   "Event shape → Event families (a window around each event, grouped by shape with the Library's "
                   "HDBSCAN; events in no dense family are left out, and a family no better than phase-randomised "
                   "noise of the same colour is flagged; each event's family becomes its group) → Intervals (the "
                   "gaps between events of the SAME family: one rhythm per family). Tune Event families' minimum "
                   "family size first; read each family's noise flag and SVD entropy beside its null before its "
                   "rhythm.",
    "steps": [
        _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
        _step("detection", "noise_threshold", {"k_sigma": 4.0, "direction": "below",
                                               "min_duration_s": 30.0, "merge_gap_s": 60.0}),
        _step("interrogation", "event_shape", {}),
        _step("interrogation", "event_families", {"method": "hdbscan"}),
        _step("interrogation", "intervals", {}),
    ],
}
```

**Glyphs** (44 × 26):
- `catalogue.shape_families`: three grey window outlines in a row, each holding a small trace. The first two traces are the same blue dip and the third is a different blue square dip. A thin amber bracket joins the first two, and a green dot sits under each family's first (medoid) window.
- `interrogation.event_families`: a grey trace with four dips — two V-dips and two square dips. Each dip has a tick under it, blue under the V-dips and green under the squares (the family colour). An amber arc joins the two blue ticks (the per-family gap).

**Smoke state:** the `event_families` template on the smoke recording, stopped at step 4.
- The pane should paint with `meta.summary` reading "K families (sizes …) of N event window(s) by hdbscan; … SVD entropy …".
- `meta.families[]` should be listed with `noise_like`.
- Step 5 should show `interval_stats` keyed by family.

**COSTED:** add both `"catalogue.shape_families"` and `"interrogation.event_families"`. Both declare `estimate`.

**What W2-F should show:**
- Per family: `meta.families[]`.
  - Amber badge "no better than noise" when `noise_like`, with tooltip `why`.
  - "Not tested" when `tested` is false (Ward).
  - `svd_entropy_norm` beside `svd_entropy_null_p05`, and "no more coherent than noise" when `coherent_beyond_noise` is false.
  - `svd_entropy_squared_norm` and `top_share`, labelled.
- Elsewhere in `meta`:
  - `warnings[]` and `notes[]`;
  - `omitted` (new reasons: `no_window`, `outside_span`);
  - `fraction_placed` and `fraction_confident`;
  - `exemplar_windows[]` / `exemplar_events[]`, each `{family, window|event, start, start_s}`;
  - for `event_families`, `window`, which holds the cutter's length, anchor and omissions.

## 6. Open questions and risks

- **W2-B's HDBSCAN noise flag misses some noise crowds at n = 200.** On 200 phase-randomised AR(1) φ = 0.95–0.97 events, 3 of 6 runs gave 22–39 events in two families that were *not* flagged.
  - My no-structure tests use n = 80, where nothing is placed, so they hold under either rule.
  - At larger n, Intervals would report a rhythm for such a family; the only thing that would mark it is its key, and only once the flag fires.
  - Please include n ≥ 200 in your 20-draw surrogate evaluation after W2-B's fix round 2.
- **At 300–480 s windows, the 16-member square family was flagged noise-like under the current size rule; at 140 s it was not.** This is the size-matched issue W2-B is fixing. Re-run the template after fix round 2.
- **Anchor default.** I chose `start` over W2-A's `onset`, based on synthetic evidence only. Please check on real drops (M2_aug rec 3, 500–530 h; L_LM_Jul_26_J, 380–480 h) whether `start` or `onset` gives the tighter families.
- **The auto window length** (2 × the median duration, here 140 s) covers onset to about half recovery (W2-A's caveat). The sharkfin/square separation held at 140–480 s and degraded at 900 s.
- **Ward** is untested against noise, so `fraction_confident` is None for it.
- **`docs/rq_roundA/` was not updated** because it is on the do-not-touch list. This gives the spiking-families question (RQ3, and the supervisor's report) a ready chain; please note it there.
- **Two design calls to confirm:**
  - `event_families` category is `cluster`, not `control`;
  - the `~noise_like` group-key suffix.

## 7. Commits
```
e7ef98b w2-e: catalogue.shape_families and interrogation.event_families - the Library's clustering inside a chain
e194e43 w2-e: tests - catalogue.shape_families, interrogation.event_families and the event_families template
```

> Filed by the manager session, 2026-10-14 15:33 — the final message of implementer agent `a5a91c3213452c835`,
> resumed for fix round 1 against `W2-E-families.critic.md`, verbatim.

# W2-E fix round 1: report

**Status:** all eight critic findings (F1–F8) are fixed, each test-first. I merged main again first, without conflicts (merge `4a192a9`, bringing in `4db3684` and `800d0d9`). One red→green pair covers F1–F8:
- **Red `435cf0e`** (tests only): 23 failed, 51 passed on the four W2-E files. Its body lists the failures: `KeyError: 'confident'`, the missing `UNTESTED_SUFFIX` / `EVENT_FAMILIES_EXCLUDED`, `length_s` 0 ≠ 600, `no_window` ≠ `no_window:past_end`, DID NOT RAISE for Ward's estimate and for k-Shape in `event_families`, and unmarked Intervals keys for Ward on a 1,000-event random walk.
- **Green `1301a0f`:**
  - The four W2-E files: 74 passed in 30 s (`-n 4`).
  - The neighbouring files — trains ×2, `intervals_lv`, event_windows ×2, `block_standard`, `adapter_spec`, `import_boundaries`, `templates`, `end_to_end`, `template_event_trains`, `library_coherence`, `library_grouping_methods`: 493 passed.

## What changed

**F1 (window length)**
- `interrogation.event_families` now defaults to `length_s = 600` (`SF.DEFAULT_EVENT_LENGTH_S`), labelled a placeholder. The template step sets `"length_s": 600.0` explicitly.
- `anchor="start"` stays the default. The adapter docstring carries the critic's sweep numbers for both choices: start + 600 s was 18/18 at SNR 10 and at SNR 40; the auto length was 5/18 and 4/18; onset and extremum anchors managed 7–12/18 at best.
- When a caller sets `length_s = 0`, `SF.auto_length_warnings` puts W2-A's coverage checks into `meta.warnings` and the summary:
  - the length clamped to the 60 s floor or the 7,200 s ceiling;
  - more than a quarter of windows overlapping the next;
  - more than a quarter of windows ending before their event's recovery.

**F2 (unmarked families in pure noise)**
- `group_key(family, noise_like, tested)` now marks Ward's families as `<n>~untested`, and the group rule says so. An unmarked key means a family that was tested and passed.
- k-Shape is removed from `event_families`:
  - Its method choice and its parameters are off that block's form.
  - The core `event_families` refuses it, giving the reason (its plain-phase null missed random-walk crowds: 132 + 108 members at n = 1,000) and the follow-up (a trend-kept k-Shape null in the Library methods, W2-B's to build). The text is in `SF.EVENT_FAMILIES_EXCLUDED`.
- `catalogue.shape_families` keeps k-Shape but never calls its families confident:
  - `FamilyInfo.confident` is `None` (`null_trusted` is false and `null_caveat` carries the reason).
  - `fraction_confident` and `n_confident` are `None`.
  - The reason appears in `notes`, the summary ("kshape's noise null is not trusted: no family is called confident") and a `confident` rule.

**F3 (coherence verdict):** `family_summary` now reads `svd_entropy`'s own `beyond_noise`, `null_margin` and `rule` into `svd_entropy_beyond_noise`, `svd_entropy_null_margin` and `svd_entropy_rule`. `coherent_beyond_noise` is gone. The `svd_entropy` rule prints `coherence.RULE`, which carries the 0.9 margin and the smooth-shape caveat.

**F4 (template):** the template test asserts that neither real family's key contains `~noise_like` or `~untested`, and that no event of either family has `family_noise_like` set. It passes at 600 s.

**F5 (no-structure tests):** these now run at the block's defaults, for each method it offers (hdbscan, ward). Each asserts that Intervals has no key except `-1` without a mark.
- n = 200 on AR(1) φ 0.95, 0.97 and 0.99 and on a random walk.
- n = 1,000 on the random walk only. The suite has no slow marker; these take 3.3 s for hdbscan and 1.6 s for ward.
- The old n = 80 / 140 s test is replaced.

**F6 (hidden cutter reason):** `family_omit_reason` is now `no_window:<past_start|past_end|too_much_nan>`, and the summary names the reasons with their counts.

**F7 (estimate):** `SF.estimate_seconds` raises for Ward past `WARD_MAX_ITEMS` (5,000), so both adapters' estimates refuse in words that name hdbscan.

**F8 (bounds):** `ward_cut` max is 2, `hdbscan_min_cluster_size` min is 2, `kshape_n_init` min is 1.

**One test change in the green commit:** in `test_adapter_event_families::test_the_spec`, k-Shape's params are now asserted absent from this block's form, because they went with the method.

## The template as it now stands (`tests/test_template_event_families.py`)
```python
TEMPLATE = {
    "name": "event_families", "kind": "interrogation", "version": 1,
    "description": "Families of detected events, each timed on its own — 'do family A events come every 40 "
                   "minutes and family B every 3 hours?' in one chain: baseline removal → noise threshold (every "
                   "stretch more than 4 σ_n below the detrended trace's median, as the noise_threshold template) → "
                   "Event shape → Event families (a 600 s window around each event from its span start - a placeholder "
                   "length, measured on synthetic shapes - grouped by shape with the Library's "
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
        _step("interrogation", "event_families", {"method": "hdbscan", "length_s": 600.0}),
        _step("interrogation", "intervals", {}),
    ],
}
```

## The meta keys W2-F must draw (both blocks)

**`meta.families[]`, one per family:**
- `family`, `size`, `library_label`.
- `noise_like` → amber badge "no better than noise", tooltip `why`.
- `tested == false` → grey "untested" badge (Ward).
- `confident`:
  - `true` = tested against a trusted null and passed;
  - `false` = noise-like;
  - `null` = untested, or the null is not trusted. In the untrusted case `null_caveat` holds the reason (k-Shape in `catalogue.shape_families`).
- `unstable`, `flags`.
- Coherence: `svd_entropy_norm` beside `svd_entropy_null_p05` / `svd_entropy_null_median`, plus `svd_entropy_beyond_noise`, `svd_entropy_null_margin` and `svd_entropy_rule`. When `beyond_noise` is false, show "no more coherent than noise". Also `svd_entropy_squared_norm` and `top_share`, labelled.

**Exemplars:**
- `meta.exemplar_windows = {"<family>": window index}` for `catalogue.shape_families`.
- `meta.exemplar_events = {"<family>": event index}` for `interrogation.event_families`.
- `meta.exemplar_rule` is a string.
- The richer list is in `meta.exemplars[]`: `{family, window | event, start, start_s}`.

**Marks on keys and columns:**
- `group` keys in Intervals' table: `<n>~noise_like` and `<n>~untested` are marked; `-1` means in no family; an unmarked key passed its null.
- The per-event column `family_noise_like`, and `family_omit_reason` (including `no_window:<reason>`).

**Also in `meta`:** `warnings[]` (noise-like families, coherence, and the auto-length coverage warnings), `notes[]`, `omitted`, `fraction_placed`, `fraction_confident` (may be `None`), `n_noise_like`, `window` (length, anchor and the cutter's omissions), `fit_summary` and `summary`.

## `git log --oneline 2fd26b8..HEAD`
```
1301a0f w2-e: fix round 1 (F1-F8) - 600 s default, auto-length warnings, ~untested, k-Shape out of event_families, beyond_noise read off svd_entropy
435cf0e w2-e: tests (fix round 1, F1-F8) - 600 s default, auto-length warnings, ~untested, no k-Shape in event_families, beyond_noise read off svd_entropy, no-structure at defaults
4a192a9 Merge branch 'main' into worktree-agent-a5a91c3213452c835
800d0d9 blocks-w2: minirocket_manual_labels ships; event_clusters and recording_snippets are experimental
55973f7 blocks-w2: tests (red) -- the wave-2 templates are the ones webui/server/templates.py ships
2c016e3 w2-e: exemplar_windows / exemplar_events in the serializer's format; rules follow W2-B's fix round 2
4db3684 blocks-w2: coherence's beyond_noise carries the 0.9 margin; both trend-kept nulls say smooth shapes are not judged fairly
2e98666 w2-e: tests (exemplar format) - exemplar_windows / exemplar_events as {"<label>": index} + exemplar_rule
cdcc3e7 blocks-w2: tests (red) -- coherence's verdict carries a margin; both nulls say smooth shapes are not judged fairly
3fd0742 Merge branch 'main' into worktree-agent-a5a91c3213452c835
e7ef98b w2-e: catalogue.shape_families and interrogation.event_families - the Library's clustering inside a chain
e194e43 w2-e: tests - catalogue.shape_families, interrogation.event_families and the event_families template
```

**Not run here:** `tests/test_webui_*` skip under conda. The serializer's handling of the exemplar dicts and the new keys needs `webui/.venv`.

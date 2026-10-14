> Filed by the manager session, 2026-10-15 02:2x — the final message of implementer agent `a17192b65fcf2dd72` on
> branch `worktree-agent-a17192b65fcf2dd72` (`f36ef75` red, `2a4ca0e` on `6bd3e40` = `wave3-round2-base`), verbatim.
> The agent was interrupted by an API session limit at ~00:3x and resumed at 02:01.

## W3-G report: the quiet-stretch null and k-Shape's trend-kept null

### 1. In plain words

To decide whether a family of shapes is real, the Library builds fake families out of noise and checks that the real one is tighter. Until now each fake member was the real member scrambled, with its slow curve kept. For a smooth shape (a broad hump, a slow ramp) the slow curve *is* the shape, so the fakes looked like the real thing and good families read "noise-like".

The fakes are now cut from the recording itself, from stretches where no event lies: the same colour, drift and artefacts as the real members, but none of the shapes.

**Most important finding: you cannot just swap in the quiet windows.** A family is a crowd that was *picked out* for being close together. A random quiet window was not picked, so pure noise crowds beat it easily. The old fakes avoided this by accident: they inherit their member's own curve, so they sit as close to the centre as the member does.

The new test matches the picking. A family of m members found among n must sit closer to its centre than the closest m/(2n) share of quiet windows (capped at 5 %). Put simply: "could the quiet background supply as many windows as the family has, this close to its centre?"

Under that test pure noise lands at about 1×, so the safety margin is all the protection, and 0.9 was too thin:
- 124 pure-noise families on strongly coloured noise (AR(1) φ 0.98–0.99) went down to 0.80×; 14 of the 124 were below 0.9.
- So the margin for the quiet-stretch null is **0.7** (placeholder, measured). The trend-kept null keeps 0.9.

What it found on synthetic data:
- **Humps and ramps now pass.** Against the quiet null they score 0.01–0.54×; the trend-kept null calls them noise-like (1.15–3.0×).
- **Pure-noise families still fail.** Random walk: 1.4× and up. AR(1) φ 0.95–0.99: 0.84× and up in a 52-family sweep with the code as shipped (none called confident).
- **k-Shape is offered in Event families again.** Its plain-scrambling null is replaced by the trend-kept one, and it flagged every no-structure family at the defaults (random walk and AR(1) 0.95/0.97/0.99, 200 and 1,000 events, both null kinds). It leaves the excluded and untrusted lists, which are now both empty.

### 2. Files

- `Working/background_null.py`: added `MemberBackground`, which cuts windows for members spread over many recordings (each from its own recording, at its own length). It is additive; W3-B's `sample_background` is unchanged. Also added `MemberDraws`, `QUIET_MIN_SHARE` (0.5) and `QUIET_MIN_DISJOINT` (20).
- `Working/library/grouping/methods/kshape.py`:
  - shared quiet-null helpers (`quiet_quantile`, `quiet_draws`, `quiet_distances`, `quiet_verdict`, `background_words`, `batched_shape_vectors`);
  - `QUIET_MARGIN` 0.7, the cost model (`C_QUIET_WINDOW`, `quiet_windows_estimate`);
  - k-Shape's null rewritten: trend-kept beside, quiet as the verdict; `fit(..., background=)`.
- `Working/library/grouping/methods/hdbscan.py`: per-family quiet null with the trend-kept one beside it; `fit(..., background=)`; the estimate prices the quiet windows.
- `Working/library/coherence.py`:
  - `svd_entropy(..., background=, n_set=)`: the quiet null (the m windows nearest the medoid, from a pool of the set's size), `nulls`, `background`, `why`;
  - `null_squared_p05` and `beyond_noise_squared` (σ² against its own null, reported only);
  - `variants` lists σ² first, eq. 17 second; eq. 17 keeps the verdict.
- `Working/Catalogue/shape_families.py`:
  - `UNTRUSTED_NULLS` and `EVENT_FAMILIES_EXCLUDED` emptied, with the measurement written in the comment;
  - `shape_families(..., background=, background_note=)`; `event_families` builds the background from the span; new `span_background`;
  - summary line puts σ² first and names the null; a fallback warning per family; `family_summary` gains `null_kind`, `background_s`, `background`, `svd_entropy_variants` and the σ² verdict fields; rules and docstring updated.
- `Adapters/catalogue_shape_families.py`: quiet background from `x`. When the vectors come from Trace shape it falls back and says why (a quiet window cut from the trace would not go through Trace shape's alignment, noise floor and detrend). Descriptions updated.
- `Adapters/interrogation_event_families.py`: description and docstring updated; k-Shape offered again.
- `webui/server/library.py`:
  - `_grouping_items` now carries each member's `start_idx` and `end_idx`;
  - new loader `_library_background` with `_library_spans` and `LIBRARY_AVOID_WORDS`;
  - `_family_coherence(index, rows, conn=None, n_set=None)`; its cache key now includes `n_set` and whether a connection was given.
- **Outside the Deliver list, minimal:**
  - `Working/library/grouping/engine.py`: `run_grouping` and `preview` take `background=`, passed to a method whose `fit` accepts it (as `.subset(taking_part)`). It is not part of the recipe hash.
  - `webui/server/library.py`: one line in `_family_detail` (passes `conn` and `n_set=len(state["rows"])`) and one in `run_grouping_job` (builds the loader and passes it to `preview`).
- Tests:
  - `tests/test_library_background_null.py` (new, 31 tests);
  - deliberate updates to `test_library_grouping_methods.py`, `test_shape_families.py`, `test_adapter_event_families.py`;
  - two tests added to `test_webui_library.py`.

### 3. The algorithm as implemented

1. **Cutting quiet windows.** For each member, windows of its own length are cut from its own recording at seeded uniform positions inside free stretches. A free stretch holds no avoided span and no NaN. The free stretches are cached once per recording.
   - **What is avoided.** In the Library: every Library member (any entry, any scale) and every sequence on that recording. In a chain: every event span and every cut window.
   - **Detections are not avoided.** Detection runs at many settings (sliding windows among them) cover most of a recording, so avoiding them would leave no quiet signal. A window that holds an uncatalogued event makes the null tighter, so the verdict errs towards "noise-like".
2. **Room and borrowing.** A recording has room for a member only when at least 20 non-overlapping member-length windows fit in its quiet stretches.
   - Without this guard, W2-E's dense noise events had one 1,020-sample free tail, and every quiet window was a near-copy cut from it. The null crowded like a family; a k-Shape noise family scored 0.68.
   - A member with no room, or whose recording is not on disk, borrows a window from another member's recording and is counted. There is never a random cut through events.
   - **Fallback.** When fewer than half a family's members got a window from their own recording, the family is judged on the trend-kept null instead. Its `null_kind`, `why`, `background.reason` and a block warning say so.
3. **The method test (HDBSCAN and k-Shape).**
   - d_F is the members' median distance to the medoid (HDBSCAN) or to the centroid (k-Shape).
   - q = min(5 %, m/2n). Draws are set so the quantile rests on about 40 windows: at least 10 per member, at most 20,000 per family. Windows go through the same preparation as the members, using a batched, numerically identical version of `shape_vectors`.
   - A family is confident iff d_F < 0.7 × the q-quantile of the quiet windows' distances; it is unstable when d_F is not below their median.
   - k-Shape's automatic `omit_d` is the quiet windows' 5th percentile.
   - The trend-kept test always travels beside it, in `nulls.trend_kept`.
4. **Coherence.** Per draw (5 draws), a pool of quiet windows is cut with the members cycled through to reach the pool size.
   - Pool size is the set the family was found in (n_set), capped at 2,000 with m scaled down by the same share.
   - The m windows nearest the medoid by SBD are kept, aligned to the medoid as the members were, and scored with eq. 17 and σ².
   - `beyond_noise` = eq. 17 < 0.9 × the p05 of whichever null judges (the 0.9 margin is unchanged for the coherence).
5. **k-Shape's trend-kept null** replaces the plain phase null; it uses the same landed-surrogate structure as before.

**Departures from the prompt, each measured:**
- **Margin 0.7 instead of 0.9** for the quiet-stretch null (measurement above).
- **A selection-matched quantile instead of a plain p05.** A family-of-m-in-n selection test alone (with only 3 draws) let pure random-walk crowds reach 0.68×.
- **σ² at 0.9 against the quiet null is not safe as a verdict.** It gave 1 false pass in 52 pure-noise families (lowest ratio 0.89×). eq. 17's lowest ratio was 0.98×, with none beyond noise. The σ² verdict is therefore reported only.

### 4. Tests

**Red commit `f36ef75`.** The HEAD tree was exported and the new tests copied in:
- the new file: collection error, `ImportError: QUIET_MIN_SHARE`;
- the updated existing files: 17 failed and 132 passed — the k-Shape trust, offered, no-structure and null-kind cases.

After the red commit I fixed two bugs in the new test file itself: a misplaced block, and a not-on-disk share that sat exactly at 50 %.

**Green, conda python:**
- 556 passed across the new file, `test_library_grouping_methods`, `test_library_coherence`, `test_shape_families`, `test_adapter_shape_families`, `test_adapter_event_families`, `test_template_event_families`, `test_template_event_clusters`, `test_background_null`, `test_cycle_shapes`, `test_adapter_cycle_shapes`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`, `test_grouping_adapter` and `test_mpdist_distance`.
- The new file's slowest case is k-Shape through `event_families` at n = 1,000: 91 s.

**Webui tests, venv interpreter** (`webui/.venv/Scripts/python.exe`, run from my worktree root):
- `test_webui_library`, `test_webui_family_views`, `test_webui_w2f_ui`, `test_webui_library_edges`, `test_webui_mpdist_edges`: 85 passed, 3 xpassed, before my two webui tests were added.
- The coherence and quiet subset of `test_webui_library`, after adding them: 12 passed.

**What the new tests pin:**
- the sampler: own recording, own length, no overlap with spans or NaN, seeded; borrowing and its counts; the share rule; the 20-window room guard; W3-B's sampler keys unchanged;
- humps and ramps pass the quiet null while the trend-kept null flags them, both numbers asserted, for HDBSCAN, k-Shape and the coherence;
- no structure at the defaults: random walk and AR(1) 0.99 at n = 200 and 1,000 (HDBSCAN), k-Shape with k chosen at n = 200, and `event_families` with HDBSCAN and k-Shape giving no unmarked Intervals key;
- the fallback for a recording that is mostly events, and for members not on disk;
- every `why` names its null and its background seconds;
- the recipe hash is unchanged by the background;
- σ² is first in `variants` and in the summary line;
- both chain blocks judge against the chain's own quiet stretches;
- the estimates price the quiet windows.

**Deliberate test changes:**
- k-Shape's null kind is now "trend-kept phase-randomised", and its families are confident when they pass;
- k-Shape is offered in Event families and joins its no-structure runs;
- the HDBSCAN estimate bounds moved from 60 s to 120 s.

### 5. Integration snippets

There is no new block or template. For **W3-F**:
- Lead with `coherence.variants[0]` (σ²).
- Show `null_kind`, `why` and `background_s` on each family badge.
- The grey "null not trusted" badge (`GroupingView.tsx`) no longer fires for k-Shape: `null_caveat` is None now. Remove it or leave it dormant.

No glyph or smoke-state changes. No `COSTED` entry: the block estimates gained the quiet-null terms internally.

**Cost, measured on a loaded machine with a synthetic Library-size set** (3,616 items on 8 recordings of 2 M samples, the bridge's envelope items, the bridge's loader):

| Method | Without the quiet null | With it | Estimate |
|---|---|---|---|
| HDBSCAN (defaults) | 41 s | 57 s | 67 s |
| k-Shape, k = 20 | 661 s | 533 s | 607 s |
| Ward | 6.5 s | 6.0 s (no null) | 15 s |

The k-Shape pair differs within the machine's load noise; the quiet part is small next to the fit.

**Family-detail coherence, 2,000 members, n_set 3,616:** 7.2 s cold, 0.3–0.7 s cached. The cached time is building the cache key: one file stat per member.

**Estimate changes:** HDBSCAN at 3,616 items went from 39 s to 77 s; k-Shape with k chosen from 483 s to 520 s. Event families over 48 h: 33 s with HDBSCAN, 124 s with k-Shape.

**MPdist follow-up (note 5).** `mpdist_null` could use `_library_background(conn, index, members, prepare="raw")` to draw same-recording quiet windows at each matched member's length, with the same quantile selection. That is about 20 lines in `post_run_matches`. MPdist costs milliseconds per window, so cap the windows at about 2,000.

### 6. Open questions and risks

- **The margin 0.7 and the room guard of 20 are placeholders** measured on synthetic data. Please check on real data:
  - the Library table (Ward, HDBSCAN eom and leaf, k-Shape k = 20) with the new null;
  - `event_families` on rec 6's and rec 542's chains. Rec 542's 131-member smooth family is the target case. Rec 543's dense span should fall back and say so.
- **eq. 17 and σ² disagree** at realistic noise. On AR(1) φ 0.95 humps, σ² was 0.30 against a quiet p05 of 0.68 (beyond noise), while eq. 17 was 0.85 against 0.91 (not beyond at the 0.9 margin). This is eq. 17's noise floor again. Choosing σ² as the verdict would need its own margin, and 0.9 let 1 pure-noise family in 52 through.
- **Cold Family-page GET:** about 7 s for a large family, and also seconds for a small one, because the pool is sized by the grouping's member count, not the family's.
- **Saved groupings keep their stored fit summary.** Live coherence badges and new regroups use the new null, so some badges will change.

### 7. Commits

```
2a4ca0e w3-g: the recording's own quiet stretches as the families' null; a trend-kept null for k-Shape
f36ef75 w3-g: tests — the quiet-stretch null for families, and a trend-kept null for k-Shape
```

The worktree is clean at `2a4ca0e`.

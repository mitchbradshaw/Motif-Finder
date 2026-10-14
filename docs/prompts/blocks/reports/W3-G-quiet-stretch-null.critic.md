> Filed by the manager session, 2026-10-15 — the final message of critic agent `a8f15e6dcd6951107` on branch
> `worktree-agent-a17192b65fcf2dd72` (`f36ef75`, `2a4ca0e` on `6bd3e40`), verbatim.

## W3-G critic report: the quiet-stretch null and k-Shape's trend-kept null

### 1. In plain words
The new noise test works as claimed in the main cases. It now cuts its fake families from the recording's own quiet stretches. Pure noise was never called a confident family in any real run of the methods I made. Broad humps and slow ramps now pass where the old test failed them. k-Shape can be offered again.

There are three problems:
- **The safety margin is thin.** Under this test pure noise sits at about 1×, and the cut is at 0.7×. Small, tight noise crowds reach 0.71× in a worst-case selection, and 0.64× when the quiet stretches hold uncatalogued events.
- **"Detections are not avoided" is wrong in both directions.** Uncatalogued events of another shape make the null looser, so pure noise looks better than it is. Uncatalogued events of the family's own shape make real sharp families fail outright, where the old null passed them.
- **The Family page's coherence null is not like-for-like.** It scores the fake family on fewer rows than the real one, and selects it from a set whose size changes with the view filter.

### 2. Verdict
**merge after fixes.** Fixes 1–4 are small code changes. Fix 5 is a sentence in the docstring, the rule and the report, plus a decision for the manager.

### 3. Findings, most severe first

**F1 — should-fix — the coherence quiet null compares a different number of rows.**
- Where: `Working/library/coherence.py:335`, `take = max(2, round(m * pool / n_set))`.
- What is wrong: whenever n_set is above the 2,000 pool cap (always, at the real Library's 3,616), the null scores `take` rows while the family scores m rows. The score is normalised by ln min(P, L), so the two numbers are not like-for-like.
- How shown (`coh_cost.py`, pure-noise k-nearest families on a random walk, n_set 3,600):

| family | pool cap | rows the null scores | eq. 17 / p05 | σ² / σ² p05 |
|---|---|---|---|---|
| 20 members | 2,000 (shipped) | 11 | 1.014 | 0.825 |
| 20 members | 500 | 3 | 1.137 | 0.67 |
| 20 members | 250 | 2 | 1.137 | 0.59 |
| 200 members | 2,000 (shipped) | 111 | 0.985 | 0.931 |

  The bias runs opposite ways: eq. 17 becomes more conservative and σ² more lenient. At the shipped settings σ² already calls a pure-noise family beyond noise (0.825 < 0.9).
- Fix: score the family on random subsets of `take` members, the median of a few, so both sides have the same row count. Or keep pool = n_set up to about 4,000; the cost is linear and small (F6).

**F2 — should-fix — the Family page passes the wrong n_set, and it changes with the view.**
- Where: `webui/server/library.py:1544`, `n_set=len(state["rows"])`.
- What is wrong: `state["rows"]` holds only the *assigned* members that are *shown under the view filter* (`_build_view_state`). The family was found among every item that took part, and 40–60 % of items are omitted. So the selection is weaker than the one the family went through, and the verdict moves when the user changes the noise-floor or "pure" filter.
- How shown, pure-noise families, n_set 3,600 → 1,440:

| family | eq. 17 ratio | σ² ratio |
|---|---|---|
| 20 members | 1.014 → 0.935 | 0.825 → 0.761 |
| 200 members | 0.985 → 0.979 | 0.931 → 0.745 |
| 2,000 members | 1.009 → 0.98 | 1.032 → 0.847 |

- Fix: pass the grouping's item count. Use `fit_summary["rows"]` minus `screened_out` (HDBSCAN's summary has both), or the count of member rows including omitted ones, without the view filter.

**F3 — should-fix — "Detections are not avoided … only makes the null tighter" is false.**
- Where: `webui/server/library.py:1371` (docstring), the report's §3.1, and `LIBRARY_AVOID_WORDS`.
- **Size** (`lib_scale.py` / `sim_select_unc.py`): 200 uncatalogued sharp drops per recording were placed in the quiet stretches; the members were pure noise.
  - HDBSCAN's largest random-walk noise family went from 1.164 to 0.839, and its σ² read beyond noise.
  - In the worst-case selection (k-nearest families around the densest centres), 10-member families reached 0.643 on a random walk: 2 of 12 under 0.7, so called confident. On AR(1) 0.99 they reached 0.78.
- **Power:** when the uncatalogued events have the family's own shape, the family is called noise-like although the trend-kept null passes it clearly:

| case | quiet-stretch ratio | trend-kept ratio |
|---|---|---|
| drops on a random walk | 1.29 | 0.196 |
| drops on AR(1) 0.99 | 1.30 | 0.365 |
| sharkfins on AR(1) 0.97 | 1.31 | 0.274 |

  These are sharp families that the old null judged correctly. On real recordings the Library catalogues only a subset of the events, so this situation is likely.
- Fix:
  - correct the claim in the docstring, the rule and the report;
  - report the share of quiet windows that overlap any machine detection (in `background`);
  - avoid event-like detections, not the sliding-window runs that motivated skipping them;
  - for the manager to decide: either keep the quiet null, or call a family confident if it passes **either** null. Each null's measured size is small, and "either" removes the power regression for spiky families.
  - Ask the manager to measure detection coverage of the quiet stretches on rec 6 and rec 542.

**F4 — should-fix — σ² carries a field named `beyond_noise` that is True on pure noise.**
- Where: `coherence.py:397` (`variants[0]["beyond_noise"]`).
- What is wrong: the report tells W3-F to "lead with `coherence.variants[0]`". That entry carries `beyond_noise: True` for pure-noise families:
  - HDBSCAN's 307-member random-walk noise family at Library scale (0.135 against a p05 of 0.152);
  - the 379-member family on the contaminated recording (0.78×);
  - noise20 in F1 (0.825×).
- Fix: put None there and keep the number under a name like `squared_vs_null_ratio`, so no page can draw it as a verdict. Wave 2's lesson was "never re-derive a verdict"; a field named like one invites exactly that.

**F5 — should-fix — the 0.7 margin is on evidence, but thin for small tight families.**
- Through the real engines, the lowest pure-noise ratio was:

| run | lowest ratio |
|---|---|
| HDBSCAN eom, Library scale (n = 3,600) | 0.966 (random walk) |
| k-Shape k = 20, Library scale | 0.833 (random walk, 30 % noise level); 1.00 (AR(1) 0.99) |
| `event_families`, nostruct | 0.982 (k-Shape, AR(1) 0.95, n = 1,000) |

- Worst-case selection (`sim_select.py`, the densest k-nearest families among 3,600): the lowest ratio falls as the family gets smaller, so the margin is tightest for 10–20 member families.

| family size | random walk | AR(1) 0.99 |
|---|---|---|
| 10 | 0.714 | 0.769 |
| 20 | 0.787 | 0.884 |
| 100 | ≥ 0.94 | ≥ 0.94 |

- Power at 10 % noise: every shape family HDBSCAN isolated scored 0.13–0.39 (the one exception, a mixed 63 %-pure ramp crowd, was rightly noise-like). So a margin of 0.6 would cost nothing there.
- Fix: a smaller margin (0.6), or a margin that tightens for small m. The report's own 124-family sweep never reached the small-dense case.

**F6 — nit / cost (Q5).**
- Measured on a loaded machine, cold, svd_entropy with the background:

| family size | without the background | with it |
|---|---|---|
| 20 | 0.07 s | 2.0 s |
| 200 | 0.28 s | 2.1 s |
| 2,000 | 21.7 s | 13.6 s (load noise) |

- The pool is the whole extra cost for small families. For large ones the members' own work dominates.
- The cost is needed for a selection-matched test (F1 needs pool = n_set for a like-for-like comparison).
- Cheaper without losing correctness:
  - cache each recording's free stretches (`_Recording`) and `_library_spans` across GETs, keyed on path, mtime and the Library-member fingerprint;
  - cut the quiet null to 3 draws.
- A 2-member floor on `take` is too low for an SVD entropy; use about 10.

**F7 — nit — the smooth-shape caveat shows when the quiet null judged.**
- Where: `webui/server/library.py:1349` sets `smooth_caveat` unconditionally, and FamilyPage prints it.
- Fix: set it only when `null_kind` is the trend-kept one.

**F8 — nit — borrowed windows are not named in `why`.**
- `why` names the seconds of background and the number of recordings, but not `n_borrowed` when the null is usable.
- A confident Library family that fell back to the trend-kept null shows nothing on the face; only noise-like badges carry `why` as a tooltip. Hand this to W3-F.

### Answers to the manager's questions

1. **The selection-matched quantile.** It is sound: the quiet distances are measured to the family's own centre, and q = m/2n matches "the median of the m nearest of n". It does not correct the winner's curse of the *densest* centre among n, which is why small tight families get close to the cut (F5).
   - Size: no confident pure-noise family in any real-engine run (HDBSCAN at 4 colours plus drift, k-Shape k = 20 on AR(1) 0.99 and random walk, all at n = 3,600).
   - Power at 10 % noise: drops, sharkfins and humps were confident at 0.13–0.39 on every colour; ramps at 0.24–0.37 where HDBSCAN isolated them. The trend-kept null called the humps 1.34–2.23 and the ramps 1.77–2.34.
   - At 30 % noise HDBSCAN found no shape family at all; that is the method, not the null.
   - k-Shape k = 20 at Library scale isolated almost none of the planted families: the drop family (135 members, 63 % drops) scored 0.749 and was called noise-like; one mixed family of 100 was called confident.
   - 0.7 is evidence-based. The thinnest case is 0.71 (random walk, 10-member densest family), and 0.64 with uncatalogued events.
2. **Detections not avoided.** Wrong in both directions (F3). Size: the noise ratio fell from 1.16 to 0.84, and worst cases dropped below 0.7. Power: own-shape contamination turns real drop and sharkfin families noise-like (1.29–1.31), where the trend-kept null scored 0.20–0.37.
3. **Borrowing.**
   - Bias is negligible. In `borrow.py`, mixed families (25–50 % borrowers) on a room recording plus a packed recording (AR 0.9 / random walk and AR 0.95 / AR 0.99, both ways) gave borrowed ratios within ±0.04 of an oracle that had the members' own colour; the mean shift was about +0.01.
   - The fallback is said per family: in `null_kind`, in `why`, and in `warnings_for` for the Analyse blocks. On the Library face it shows only as the noise-badge tooltip (F8).
4. **k-Shape re-offered.**
   - No-structure test: W2-E's own `nostruct.py` generator at the defaults through `event_families` and Intervals. Random walk and AR(1) 0.95, 0.97 and 0.99; n = 200 (3 seeds) and n = 1,000 (2 seeds, 1 for AR(1) 0.97); k-Shape and HDBSCAN.
   - Result: **no unmarked Intervals key in any run**, and every family was judged by the quiet-stretch null. k-Shape's lowest ratio was 0.982; HDBSCAN's was 1.001. No coherence verdict was "beyond noise".
   - Power (`power_ef.py`, n = 200): at 10 % noise, sharkfin + square and sharkfin + hump were found pure and confident (0.045–0.18) on the random walk and AR(1) 0.99. At 30 % noise, the two kinds were mixed or called noise-like (0.75–0.94).
5. **Coherence null.** Its selection (m nearest of n) matches the methods' test in spirit, but F1 (rows not like-for-like) and F2 (the wrong n) break it. Cost and a cheaper path are in F6.
6. **Scope and contracts.**
   - The recipe hash is unchanged (tested). Saved groupings keep their stored `fit_summary`; nothing re-computes it. `_background` stays out of `fit_summary`.
   - The `engine.py` and `_family_detail` / `run_grouping_job` edits are as reported.
   - Merge with W3-B's fixer: a three-way `git merge-file` of `Working/background_null.py` (base `6bd3e40`, W3-G HEAD, W3-B's uncommitted working tree) **merges cleanly** once line endings are normalised.
   - W3-G leaves `sample_background` and `free_runs` untouched, and its contract test uses a key *subset* (`<=`), so W3-B's `longest_free_*` keys break nothing.
7. **σ² against eq. 17.** Confirmed: σ² at 0.9 is unsafe.
   - My pure-noise σ² ratios reached 0.888 (HDBSCAN, Library scale), 0.78 (contaminated recording) and 0.825 (shipped coherence settings).
   - It would need a margin of about 0.7 even when clean. Only after F1 is fixed, since σ² is the variant the row-count mismatch pushes towards lenient.
   - eq. 17's lowest pure-noise ratio was 0.935, and only at the view-dependent n_set of F2.

### Five axes
- **Spec:** every acceptance item is met and tested with both numbers asserted. One gap: the Family page does not show `why`, and the prompt said no client file, so that goes to W3-F.
- **Faithful:** the departures (0.7, the quantile, σ² reported only) are named with measurements. The quiet-window claim (F3) is not.
- **Correct:** see F1–F5.
- **Standards:** no UI import in the core; the estimate prices the quiet windows. I left Library-scale k-Shape timing open: it took 833–985 s on a heavily loaded machine against the report's 607 s estimate; re-time when the machine is quiet. Also note that the HDBSCAN "leaf" run gave results identical to "eom" on my set (the parameter is wired, so the tree probably has no finer split there).
- **Test-first and scope:** `f36ef75` touches only `tests/` and its message shows the failure. The post-red test-file fixes are benign. The out-of-list edits are minimal and reported.

### 4. What I ran
Scripts and outputs are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\22c30530-4ff1-428e-9402-a0b4d395d67c\scratchpad\critic_w3g\`.
- **Tests, conda, `-n 3`:** `test_library_background_null`, `test_library_grouping_methods`, `test_library_coherence`, `test_shape_families`, `test_adapter_shape_families`, `test_adapter_event_families`, `test_background_null`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`: **456 passed** in 226 s.
- **Webui tests, venv:** `test_webui_library`, `test_webui_family_views`, `test_webui_w2f_ui`, `test_webui_library_edges`, `test_webui_mpdist_edges`: **87 passed, 3 xpassed** in 705 s.
- **`nostruct.py`:** 37 runs. Q4.
- **`lib_scale.py`:** 8 recordings, 3,600 items, planted drops 100 / sharkfins 30 / humps 60 / ramps 15, coherence included.
  - HDBSCAN: random walk, AR(1) 0.95 / 0.97 / 0.99 and drift, each at noise levels 0.1 and 0.3;
  - HDBSCAN leaf: 4 runs;
  - k-Shape k = 20: 2 runs;
  - uncatalogued-event variants: 4 runs.
- **`sim_select.py` / `sim_select_unc.py`:** worst-case selection, n = 3,600, m = 10–500, 4 colours, plus contaminated quiet stretches.
- **`borrow.py`:** 4 colour pairs, 180 families.
- **`power_ef.py`:** k-Shape through `event_families`, 8 runs.
- **`coh_cost.py`, `coh_time.py`:** coherence pool cap and n_set, and timing.
- **Merge check:** `git merge-file` of `background_null.py` against W3-B's working tree.
- No file in the repo or the worktree was edited, and `DATA/` was not touched.

> Filed by the manager session, 2026-10-14 23:06 — the final message of critic agent `a380d497100469282` on branch
> `worktree-agent-a5a78efe8b36c0a92` (`2b88421`, `6bc380e`, `c88a236` on `64db0da`), verbatim.

# W3-D (`mpdist`) critic report

## 1. In plain words

The new distance computes MPdist exactly as the paper and `stumpy.mpdist` define it, so the arithmetic is right. Leaving out flat pieces changes nothing on normal members. What doesn't hold up is everything built on top of the number:

- **The page will show a wrong verdict.** Every MPdist edge is marked "within the seed cut", and the server drops the list of pairs MPdist refused.
- **The noise test that is supposed to say "this is more than chance" can't tell real shared shapes from noise.** That is worst for troughs, and for long random-walk members.
- **At realistic noise, MPdist barely tells a drop from a square dip.** The tests that show "far apart" use near-noiseless white noise.

## 2. Verdict

**Merge after fixes.** Fixes 1–2 are each a few lines in `webui/server/library.py` and must land before the Family page shows four edges. Fixes 3–4 are wording and the null's verdict, and must land before W3-F wires the null to a page.

## 3. Findings, most severe first

**F1 — should-fix (before merge): every MPdist edge reads "within the cut" on the Family page.** `webui/server/library.py:1601` computes `within = value <= threshold` against the seed run's cut, which is on the native-length footing.
- MPdist can never exceed √2, and real cuts are about 4–6, so the verdict is always true.
- `Edges.tsx:40` prints `≤ 6.00` beside each MPdist edge today.
- **Shown through the route** (venv python, a temp-DB `TestClient`; my test reuses the `client` fixture from `test_webui_library_edges`):
  - `EDGE m-3 mpdist 0.0905 threshold 6.0 within True`, and the same for m-4 and m-5.
  - `scale_readout` itself is correct (`within: None`, `footing` set).
- **Minimal fix inside `_edge_payload`:**
  ```python
  off = e["distance_function"] in matching_mod.OFF_CUT_FOOTING
  "threshold": None if off else threshold,
  "within": None if off else (threshold is not None and value <= threshold),
  **({"footing": matching_mod.OFF_CUT_FOOTING[e["distance_function"]]} if off else {}),
  ```
  - `Edges.tsx:40` then prints "—".
  - `Edges.tsx:39` colours a falsy `within` purple ("beyond the cut"). W3-F should treat `null` as neutral.
- The symbolic distance has the same mismatch (`symbolic_sax 0.0 … within True`). Adding it to `OFF_CUT_FOOTING` is a separate, deliberate call.

**F2 — should-fix (before merge): *Add N matches* throws the refusals away.**
- `resolve_run_matches` returns `edges_refused`, but `post_run_matches` (`library.py:3121-3135`) does not pass it on. The response keys I measured were `edgesByFunction, edgesKept, edgesNew, entryId, entryLabel, membersNew, membersResolved, summary, threshold`.
- With 21 % of real members under 16 samples, about one MPdist edge in five will go missing with no word on the page.
- **Fix:** add `"edgesRefused": out["edges_refused"]` to the response and `len(edges_refused)` to the audit `detail`.

**F3 — should-fix (before W3-F): `mpdist_null`'s `beyond_noise` is not usable as a verdict, per pair or per family.** Measured in `nullfp.py`: noise pairs at lengths 30–3,600, member length × U(0.8, 1.25), 19 seeded draws per pair. The first 5 draws reproduce `mpdist_null` exactly (checked).

False positives on pure noise:

| Rule | Share of noise pairs called beyond noise |
|---|---|
| Current: value < 0.9 × p05, 5 draws | 11 % overall; coloured noise 10–24 % at 30–900 samples; detrended random walk at 1,800 samples 6/12 (50 %) |
| value < min of 5 draws | 26 % |
| value < min of 19 draws | 8.6 % |
| value < 0.9 × p05 of 19 draws | 4.6 % |

- **The null is biased.** On coloured noise the value sits below its own null median in 65–70 % of pairs (median ratio 0.93–0.95); white noise sits at 49 %. The trend-kept surrogate comes out slightly *less* alike than real coloured noise.
- **So the family-level read is no rescue.** "Median value < 0.9 × median null" over families of 10 noise pairs called 14–50 % of pure-noise families beyond noise at 30–300 samples, and 100 % of random-walk families at 1,800 and 3,600 samples.
- **Power at realistic noise** (shared shape, noise sd 0.2 / 0.4 of the event's depth, current rule): 40–49 % / about 20 %. That is barely above the false-positive rate.
- **The smooth-shape blind spot (`SMOOTH_CAVEAT`) bites.** For the trough, the repo's main shape, the hit rate at sd 0.2 is 6 % — the noise rate. Its value is 0.33 against a null of 0.34: the cubic trend keeps the trough in its own surrogate.
- **Fix:**
  - Drop `beyond_noise` from `mpdist_null`, or rename it to something non-verdict.
  - Remove "read it across a family's pairs" from `MPDIST_RULE`.
  - Show the null median beside the value as context only.
  - If a verdict is wanted later, use an empirical null instead: MPdist from the exemplar to random windows of the same recording at the member's length. It keeps real colour without the cubic-trend blind spot.
  - If the surrogate stays, use 19 draws and "value < min of the null" (8.6 % false positives, still above the nominal 5 % because of the bias).

**F4 — should-fix: different shapes are not "far" at realistic noise, and the tests only show it at signal-to-noise 20.** Measured in `pct.py`: 30 pairs per cell, coloured noise (AR(1) φ 0.97, detrended random walk), lengths 38, 150 and 454.

At noise sd 0.2 of the depth, percentage 0.05:

| Pair | Ratio to same shape | Share of pairs at or under the same-shape 75th percentile |
|---|---|---|
| drop vs square | 1.13–1.43× | 20–63 % |
| drop vs spike | 1.28–1.62× | 3–40 % |
| sharkfin vs trough | 0.96–1.14× | 57–73 % |

- At sd 0.4, every pair sits at 0.94–1.11× — indistinguishable from the same shape.
- **Percentage 0.25 vs 0.05:**
  - At sd 0.2 and 150–454 samples, 0.25 helps. Drop/square confused 3–33 % instead of 20–63 %; drop/spike 3–30 % instead of 10–40 %.
  - At 38 samples and at sd 0.4 it makes no real difference.
  - The +30 % extra-baseline case is unchanged at both (0.83–1.13× of same).
- **Recommendation: default percentage 0.25,** named in the docstring as an adaptation. Library members are cut tight, so the paper's permissiveness (made for long series that share a few patterns) buys nothing here and costs discrimination. Keep 0.05 only if the researcher prefers the paper's value; either way, the page must not suggest MPdist tells shapes apart.
- `tests/test_mpdist_distance.py::test_two_different_shapes_are_far_apart` and the extra-baseline test use white noise of sd 0.05. Add an AR(1) and random-walk version that pins what it really does (`00-common.md`, wave-1 lesson).

**F5 — should-fix (page text): "5 %" is misdescribed.** The paper's k is 5 % of the *sample count* |A|+|B|, not of the pool. At the default sub-length (half the shorter member) that is the 9–11 % order statistic of the pool; at percentage 0.25 it is 45–50 % (measured k/pool for every case). `MPDIST_RULE` says "the value below which 5 % of the pool falls", which is wrong by about 2×. Fix the wording in `MPDIST_RULE` and in docstring step 5.

**F6 — nit: `missing` lumps "refused" together with "never computed".** On a family accepted before this change, `scale_readout` reports mpdist `missing = 3` for 3 pairs that were simply never computed. The implementer's suggested W3-F text ("k pairs could not be compared") would then be false.
- Re-running *Add N matches* fills them correctly and idempotently: `edges_new=3, kept=9, refused=0`, a third run writes 0, no duplicate edges (`test_critic_rerun.py`).
- **Fix:** document `missing` as "no MPdist edge: refused, or added before MPdist — run *Add N matches* again", or count the refusals on the fly.

**F7 — nit: the compile-cost claims are overstated for the bridge, and the dense budget is conservative.**
- The bridge already pre-warms `stumpy.stump` at start (`webui/server/app.py:112-121`), and that covers the AB-join. In a fresh process, after the bridge's warm-up call (36.8 s), the first stumpy-engine `mpdist_detail` call took about 0.0 s.
- `post_run_matches` is a sync `def`, so FastAPI runs it in the threadpool. During a cold compile (144.8 s, loaded machine), asyncio tick lateness was median 6 ms, p99 44 ms, max 341 ms. The event loop is not blocked, and the request just waits (the client `post` has no timeout).
- No job and no extra warm-up is needed; the only exposure is the first ~40 s after bridge start.
- Dense engine against stumpy engine (single runs, loaded):

| Length | Dense | Stumpy |
|---|---|---|
| 930 | 0.56 s, 7 MB | 0.83 s |
| 1,800 | 0.27 s, 26 MB | 1.65 s |
| 3,600 | 1.09 s, 104 MB | 1.45 s |
| 10,000 | 6.5 s, 800 MB | 28 s |

- Optional: set the budget by memory, or chunk A's rows, rather than by 1e8 multiply-adds.
- The docstring line "40–106 s once per process" should mention the bridge warm-up.

**F8 — nit: two loose ends.**
- `Working/distances.py:522` still says the registry "names the three distances".
- `Pipelines/import_drop_motifs/importer.py:233/312` now accepts `mpdist`, and an `MPdistRefused` would abort that import uncaught. Today nothing passes it.

## 4. The manager's seven questions

1. **Fidelity.**
   - `raw` equals `stumpy.mpdist` and my brute-force version of the paper's P_ABBA / k-th-value algorithm. Worst relative difference 7e-15, both engines, on coloured-noise, white-noise, drop and drop-vs-square pairs, at lengths 20/900 and 38/45, `sub_frac` 0.2/0.35/0.5 and percentage 0.05/0.25.
   - The flat-piece exclusion fired on 0 of 200 ordinary pairs, including ADC-quantised members (step 0.05–1 × the noise sd), so it changes no value on ordinary members.
   - Every departure is named in the docstring: sub_frac 0.5, the exclusion, the floor of 8, the footing. The one misstatement is the "5 %" wording (F5).
2. **The noise null.** Not usable as a verdict (F3).
   - Recommended rule: no per-pair verdict, and no family verdict from this surrogate.
   - Show value beside null median as context.
   - If a verdict is kept: 19 draws, value < min of the null, labelled per pair as about 9 % false positives, or switch to an empirical same-recording window null.
   - The smooth-shape blind spot bites: troughs read as noise.
3. **`within` on the face.** Confirmed through the route; fix in F1.
4. **Latency.** Covered in F7: the route runs in a thread, the bridge's existing stump warm-up covers the join, and no job is needed.
5. **Refusals at real proportions.**
   - *Add N matches*: invisible (F2).
   - `scale_readout`: `missing` is correct for refusals but also counts never-computed pairs (F6).
   - Family page: three edges instead of four, with no reason shown, and `Edges.tsx` has no MPdist read-out column (W3-F).
   - **The 16-sample floor is weak but defensible.** At 20 samples (sub-length 10), shared-shape power was 40 % at sd 0.2 and 21 % at 0.4, against 12–18 % false positives at 30 samples. Below 16, z-normalised pieces of under 8 points carry nothing. Keep the refusal, worded, and let the scale-invariant and native-length distances carry those members rather than a fallback rule.
   - An exemplar under 16 samples refuses every pair; say so once per family, not per pair.
   - Re-running *Add N matches* adds only the MPdist edge, idempotently (F6).
6. **The permissive 5 %.** See F4: 0.25 is recommended, with its reason.
7. **Scope and test-first.**
   - First commit `2b88421` touches only `tests/`. I re-ran it from a `git archive` export: 3 collection errors, `ImportError DISTANCE_MPDIST`. That is red, though only at import.
   - The red commit's message states all three deliberate test changes (registry 3→4, edges 9→12, 3→4 per member). `matching.py` is inside the allowed `Working/library/` scope, and `library.py` is the one handed line.
   - **The flat-stretch rewrite is acceptable.** The original premise (drop vs square on noiseless baselines comes out far) was false: they share the onset step, 0.08. The new case is stricter (> 0.8, where stumpy reads 0). The rewrite and the added engine-agreement test are disclosed in the report, not in commit `6bc380e`'s message. Nit: it is the branch's own new file.

## 5. What I ran

Machine: CPU load 73 %, later about 99 % from a peer session. After the manager's note I killed my one uncapped stumpy process and restarted it with `NUMBA_NUM_THREADS=4 OMP_NUM_THREADS=4`; never more than 4 processes. Timings are only meaningful as ratios.

- **Implementer's tests, conda python:** `test_mpdist_distance`, `test_distances`, `test_library_seed_edges`, `test_library_edges`, `test_import_boundaries` — 61 passed, 108 s.
- **Implementer's tests, venv python:** `test_webui_library_edges.py` — 11 passed, 333 s (the teardown "event loop closed" warnings only).
- **Red commit:** 3 collection errors, as stated.
- **My scratch scripts and tests:**
  - `fidelity.py` — exact agreement, k/pool shares.
  - `nullfp.py` — 1,746 noise pairs and 1,500 shared-shape pairs, 19 draws each.
  - `pct.py` — percentage 0.05 vs 0.25.
  - `latency.py` — compile in a worker thread with asyncio tick lateness; dense vs stumpy time and memory.
  - Warm-up check — the bridge's own warm call, then the first mpdist call.
  - `test_critic_route.py` (venv) — `within` and the response keys.
  - `test_critic_rerun.py` (conda) — re-running on pairs accepted before this change.

All are in `C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\22c30530-4ff1-428e-9402-a0b4d395d67c\scratchpad\critic_w3d\`.

**One mistake of mine to disclose.** A stray `git -C <worktree> checkout -q 2b88421 --` detached the implementer's worktree HEAD at 2b88421. The tree was clean and nothing was changed or lost. I restored it right away with `git checkout worktree-agent-a5a78efe8b36c0a92`; it is back on its branch at c88a236, clean (confirmed with `git status`). Nothing else in the repo or the worktree was written, and DATA was never touched.

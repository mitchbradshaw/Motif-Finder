> Filed by the manager session, 2026-10-14 22:39 — the final message of implementer agent `a5a78efe8b36c0a92` on
> branch `worktree-agent-a5a78efe8b36c0a92` (`2b88421`, `6bc380e`, `c88a236` on `64db0da`), verbatim.

# W3-D report: `mpdist`, a fourth Library distance

## 1. In plain words

The Library already had three ways to compare two members:
- **Scale-invariant:** stretch both members to one length, then compare.
- **Symbolic:** a coarse letter-code (SAX) comparison.
- **Native-length control:** compare the two from their starts, as they are.

MPdist is the fourth. Think of two recordings of the same song, one with an extra 30 seconds of silence at the start. MPdist cuts both into short overlapping clips. For each clip it looks for the closest-sounding clip anywhere in the other recording. If enough clips have a close partner, the two count as alike. The silence does not count against them.

So it answers "do these two members share their sub-shapes, each at its own speed?". The other three distances don't answer that.

It does **not** answer "is one a stretched copy of the other". This is how it behaved on synthetic data (300 samples, light noise; six draws per row, median, range in brackets). 0 means identical sub-shapes and 1 means no more alike than unrelated pieces:

| Pair | MPdist | Scale-invariant, same footing | Its own noise null (median / 5th percentile) | Called beyond noise |
|---|---|---|---|---|
| same shape | 0.16 | 0.19 | 0.50 / 0.38 | 6/6 |
| 30 % extra baseline | 0.16 | 0.96 | 0.50 / 0.46 | 6/6 |
| drop vs square dip | 0.41 [0.39–0.42] | 0.84 | 0.47 / 0.41 | 0/6 |
| drop squeezed to 0.8× | 0.17 | 0.17 | 0.48 / 0.44 | 6/6 |
| ringing shape, same | 0.11 | 0.16 | 0.38 / 0.32 | 6/6 |
| ringing shape, 0.8× | 0.40 | 0.14 | 0.48 / 0.37 | 0/6 |
| AR(1) noise, φ 0.99 | 0.54 [0.37–0.67] | 1.20 | 0.56 / 0.49 | 1/6 |
| detrended random walk | 0.44 [0.35–0.70] | 1.02 | 0.50 / 0.42 | 0/6 |

What the table shows:
- **Extra baseline:** near 0 under MPdist, far under the scale-invariant distance (first acceptance check passes).
- **Different shapes:** a drop against a square dip lands at noise level, so MPdist says "not alike".
- **Squeezed copies:** a squeezed smooth drop still reads as identical, while a squeezed ringing shape reads as different. So a small MPdist must never be read as "survives rescaling".
- **Noise:** smooth noise pairs score about 0.35–0.7. MPdist ignores amplitude, so every value has to be shown beside its own noise null.

## 2. Files

- `Working/distances.py` (modified):
  - Constants: `DISTANCE_MPDIST = "mpdist"`, `MPDIST_SUB_FRAC/PERCENTAGE/MIN_SUB_LENGTH/MAX_NAN_FRACTION/DENSE_MAX_WORK/NULL_DRAWS/NULL_MARGIN`.
  - Error type `MPdistRefused(ValueError)`.
  - Functions `mpdist_distance`, `mpdist_detail`, `mpdist_null`.
  - Text constants `MPDIST_FOOTING`, `MPDIST_RULE`, `MPDIST_TOOLTIP`.
  - Registry entry added.
- `Working/library/matching.py` (modified):
  - `EDGE_DISTANCES` gains mpdist (last), plus `OFF_CUT_FOOTING`.
  - `_distance_params` records `{sub_frac, percentage}` on the edge recipe.
  - `resolve_run_matches` catches `MPdistRefused` per pair: no edge, and a new `edges_refused` list.
  - `scale_readout` adds a `missing` count per function; for mpdist it sets `within`/`threshold` to None and adds `footing`.
- `webui/server/library.py`: one line, `DISTANCE_LABELS[matching_mod.DISTANCE_MPDIST] = "shared sub-shapes (MPdist)"`. I took the name from `matching_mod` so it stays one line with no import change.
- `tests/test_mpdist_distance.py` (new, 17 tests).
- `tests/test_distances.py`: the registry pin goes from 3 to 4 names, on purpose.
- `tests/test_library_seed_edges.py`: 9 → 12 edges, and each pair's set gains mpdist, on purpose.
- `tests/test_webui_library_edges.py`: 9 → 12 edges and 3 → 4 per member, on purpose.

## 3. The algorithm as implemented

1. Each member is standardised once over its finite samples. This is exact, because every piece is z-normalised anyway. A member is refused in words (`MPdistRefused`) if it is:
   - more than 50 % NaN (the snippets rule);
   - flat;
   - so short that the shorter member is under 2 × 8 = 16 samples, or the sub-length would be under 8.
2. The sub-length is `s = snippets.sub_length(shorter member, 0.5)`, the same function snippets uses, so "the sub-length" means one thing in both blocks.
   - **The default 0.5 departs from snippets' 0.35.** It was measured: at 0.5 the drop-vs-square gap was 2.5×; at 0.35 it was 1.9×, and the squeezed ringing shape went unseen (0.26 against 0.39).
   - 0.5 is also the ceiling, so the shorter member always holds two pieces.
   - The floor of 8 is a placeholder; at s = 10 the separation still held.
3. P_AB (each piece of A to its nearest piece of B) and P_BA are computed exactly as `stumpy.mpdist` does. There are two engines that give the same numbers (pinned by a test):
   - **dense:** a numpy matrix of piece-to-piece correlations, used up to j_A·j_B·s ≤ 1e8, i.e. members up to about 15 min at 1 Hz;
   - **stumpy:** `stumpy.stump` AB-joins both ways, used above that.
4. **Adaptation: pieces with no shape are left out.** A flat piece, or one touching a gap, is neither read nor allowed as anyone's partner.
   - Plain `stumpy.mpdist` scores two flat pieces 0 apart, so a hump and its mirror on flat baselines read as identical (pinned). Ours reads 0.88.
   - stumpy also scores a shaped piece against a flat one at √s (0.71, "half correlated"). Pieces whose best partner came back flat are re-measured with `stumpy.mass`.
   - Without this, gap pieces score infinite and stumpy quietly reads a lower order statistic.
5. The value read is k = min(ceil(0.05 × n_eff), pool − 1), the k-th smallest of the pool. This is stumpy's rule exactly when nothing is left out.
   - 0.05 is the paper's 5 % and stumpy's default. It reads the distance below which about 5 % of pooled closest-piece distances fall.
   - So two members are close when about 5 % of their pieces have a good partner. That is permissive by design.
6. **Footing:** value = raw / √(2s) = √(1 − r) of the piece pair read. 0 is identical, 1 is uncorrelated, √2 is a mirror. This is not the seed cut's footing, nor any length's. Pinned: a ramp against itself gives 0, against its mirror √2, and the value agrees with `stumpy.mpdist/√(2s)`.
7. **Null (`mpdist_null`):** the same distance between the Library's shared trend-kept surrogates of both members (`kshape.trend_kept_surrogates`), 5 seeded draws. `beyond_noise = value < 0.9 × null_p05`, following coherence's convention and placeholder margin. Gaps are filled for the surrogate only, then put back.

**Why not `stumpy.mpdist` itself:**
- It cannot leave pieces out (step 4).
- Its first call compiles numba code with no cache: 40–106 s in a fresh process here, under load.
- After that it costs about 12 ms per pair.

Its pairwise form does not hold the j × n per-piece matrix W2-D measured (that is the snippets path), so memory is not the issue.

**Why not the snippets kernel:** it computes a piece's profile against a whole series, not one number between two members.

## 4. Tests

- **Red commit `2b88421`:** `ImportError: cannot import name 'DISTANCE_MPDIST'`, 3 collection errors (test_mpdist_distance, test_distances, test_library_seed_edges).
- **Changes to the test file after the red commit:**
  - **Corrected:** the flat-stretch test. I had expected √2 for drop-vs-square on noise-free baselines, but the two genuinely share an onset step (0.08). I replaced it with a hump against its mirror: stumpy alone reads 0, ours reads above 0.8.
  - **Added:** a test pinning that the two engines agree.
- **Green (conda python):** `test_mpdist_distance` (17) plus test_distances, test_library_seed_edges, test_library_edges, test_block_standard, test_adapter_spec, test_import_boundaries, test_templates, test_sbd, test_import_drop_motifs: **339 passed**.
- **`tests/test_webui_library_edges.py`:** run with `"/c/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest tests/test_webui_library_edges.py -q -p no:cacheprovider`, **11 passed**, run twice. Its warnings are `RuntimeError: Event loop is closed` in background sweep-job threads at teardown. That comes from the test harness and has nothing to do with this change.
- **What the tests pin:**
  - extra baseline: near 0 against a far scale-invariant distance;
  - drop vs square: far;
  - squeezed drop close but squeezed ringing shape far, plus the tooltip wording;
  - the footing (against stumpy, and ramp/mirror giving 0 and √2);
  - the two engines agree;
  - symmetry;
  - refusals in words (NaN, flat, too short, bad parameters);
  - flat stretches and gaps left out;
  - the null: at most 2 of 8 pure-noise pairs called beyond noise, and every shared-shape pair beyond noise at under 0.5 × p05; the null is seeded;
  - the temp database: three accepted pairs, one only 12 samples long. MPdist edges are written for 2 of them; the third is refused with "too short" in `edges_refused` (again on a second call, which stays idempotent) while its other three edges are written. `scale_readout` shows mpdist `missing` = 1 and `within` = None.

## 5. Integration snippets

**Template:** none (this is a distance, not a block). **Glyph:** none. **Smoke state:** the Family page after *Add N matches* should show four edges per matched member, the fourth labelled "shared sub-shapes (MPdist)". **COSTED:** none (no adapter).

**Cost**, measured fresh and under heavy load from other agents:
- Imports: about 7 s.
- 200 members against a medoid:

| Member length | Time | Per pair |
|---|---|---|
| 60 | 0.8 s | 4 ms |
| 300 | 1.3 s | 7 ms |
| 900 | 16 s | 78 ms |
| 1,200 | 22 s | 112 ms |
| 3,600 | 59 s | 295 ms |

- The null costs about 6× a single value (300 samples 0.08 s; 3,600 samples 2.4 s per pair).
- *Add N matches* costs one MPdist per accepted pair. 50 pairs of 5 min cost well under a second, plus the stump compile (40–106 s, once per process) if any pair is longer than about 15 min.

**For W3-F, paste-ready:**
- **Within the cut:** `webui/server/library.py::_edge_payload` computes `within = value <= threshold`, and the threshold is the seed run's cut on the native footing. An MPdist edge would therefore always read "within", which is wrong. For `function == "mpdist"`, show no "within"; show its footing instead (`Working.distances.MPDIST_FOOTING`). The symbolic distance has the same footing mismatch today.
- **The scale read-out table:** `webui/client/src/library/Edges.tsx` hardcodes three columns (`r.scale_invariant`, `r.native_length`, `r.symbolic_sax`), and `api.ts:1170` types only those three. Add an `mpdist` column read from `rows[i].mpdist` (`n`, `median`, `min`, `max`, `missing`, `footing`; `within` is None). Show `missing` ("k pairs could not be compared") whenever it is above 0. The server's `distances` list already contains mpdist with its label.
- **Tooltip:** read `Working.distances.MPDIST_TOOLTIP` verbatim; don't re-word it. The longer rule text is `MPDIST_RULE`.
- **Noise null beside the value:** the Family page should call `mpdist_null(exemplar, member, seed=0)` on demand and show `null_median` / `null_p05` beside the value. Read the core's `beyond_noise` field rather than re-comparing. Per pair the false-positive rate on pure noise is about 10–20 %, so show it at family level: the median of the values beside the median of the nulls, and the share beyond noise. For a 200-member family of 5-minute members this is about 20 s, so compute on demand and cache.
- **The Add N matches result:** it gains `edges_refused: [{detection_id, member_id, function, reason}]`. Show the count and reasons on the result toast/card. Today they are invisible.
- The edges histogram (`_edges_label`) counts per pair, so it is unaffected; its "N edges" figure simply grows by a third.

**RQ3 file, the new line in plain words:** "A fourth distance now exists, MPdist (w3-d). It asks whether two members share their short sub-shapes at their own speed, so extra baseline or a tighter cut does not count against them. *Add N matches* writes it as a fourth edge per accepted pair. It is not a scale test: on synthetic data a 0.8× squeezed smooth drop scored as close as an unsqueezed copy (0.17 against 0.16), while a squeezed ringing shape scored far (0.40 against 0.11). The scale question is still the scale-invariant distance against the native-length control. Each MPdist value must be read beside its own noise null: smooth noise pairs score about 0.35–0.7 where a shared shape scores about 0.1–0.3."

## 6. Open questions and risks

- **Percentage 0.05 is permissive.** About 5 % of pieces with a good partner is enough, so two shapes sharing only a sharp onset can read alike. In noise-free data a drop against a square scored 0.08 for exactly that reason. With noise, drop vs square sits at the noise level (0.41). I kept the paper's 0.05; a higher value such as 0.25 trades this off against the extra-baseline case. The researcher may want to decide.
- **Per-pair `beyond_noise` is noisy** (about 10–20 % false positives on pure coloured-noise pairs, measured). The rule text says so, but the verdict should be read across a family. If W3-F shows it per pair, it must carry that caveat.
- **Surrogate blind spot:** the trend-kept surrogate keeps a cubic trend, so a member that is one slow curve keeps it in its own null (`SMOOTH_CAVEAT`).
- **Amplitude-blind:** a quiet member against an active one is not told apart.
- **Stump compile:** the first stumpy-engine call in a bridge process costs 40–106 s, for pairs above the dense budget (members over about 15 min). I did not pre-warm it.
- **Not tuned on real data. To check on real recordings:**
  - MPdist values on a few real trough families (for example E-0697's accepted pairs) beside `mpdist_null`, to see whether real members sit clearly below their nulls;
  - how often real Library members are refused (too short under 16 samples, or more than half gap);
  - whether exactly-flat pieces (clipped or held values) occur in real channels.

## 7. Commits

```
c88a236 w3-d: the stump compile cost as measured (40-106 s)
6bc380e w3-d: MPdist as the Library's fourth edge distance
2b88421 w3-d: tests — MPdist as the Library's fourth edge distance
```
(on top of base `64db0da`)

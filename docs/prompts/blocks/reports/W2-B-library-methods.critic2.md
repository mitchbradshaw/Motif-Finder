> Filed by the manager session, 2026-10-14 13:39 — the final message of critic agent `a4e5da8e050cafbf5`, resumed to
> re-critique the changed parts of W2-B's fix round 1 (a83c0bb..d68f84d) and to judge the manager's proposed
> size-matched HDBSCAN rule, verbatim.

# Re-critique: W2-B fix round 1 (`a83c0bb..d68f84d`)

## 1. In plain words

Most of the fix works:
- The "no better than noise" flags now travel with every family to the editor and are saved with the grouping.
- The cost is estimated before a job starts.
- The coherence score now comes with a noise reference beside it.
- k-Shape's noise test behaves well.

HDBSCAN's noise test is still wrong in both directions, and the size-matched rule you propose would make it worse:
- It already calls one pure-noise family confident at 1,500 windows.
- Your rule would call almost every pure-noise family confident, at every size I tried.

The root cause is the "fake noise" the null is built from. Each window's frequencies are kept and their timing shuffled (phase randomisation). That wipes out the slow drift-up or drift-down that makes coloured-noise windows look alike. So the fake noise crowds less than real noise does, and any rule that compares crowd sizes is fooled.

## 2. Verdict

**Merge after fixes.** One blocker remains: the HDBSCAN null rule (finding 1). The rest are should-fix or nits.

## 3. Findings

**1. Blocker: the HDBSCAN null rule fails both ways, and your size-matched rule makes pure noise confident** (`Working/library/grouping/methods/hdbscan.py`, `_null`).

Data: pure noise (AR(1) φ 0.95/0.99, drift, random walk; n = 600 and 1,500; 2 seeds at 1,500), three shifted families plus 25 % noise at 10/20/30 % background noise on three backgrounds (n = 600), and two Library-size sets (n = 3,603).

How the rules score:

| Rule | Pure-noise families called confident | Real families flagged noise-like |
|---|---|---|
| Branch rule (beat the null's largest separation AND largest size) | 2 of 26 | 7 of 22, including both at Library size |
| Your rule (noise-like only if a surrogate family at least half its size is as well separated, or it does not out-size the null) | 16 of 26, including both at Library size | none |
| Proposed rule (below) | 0 of 26 | none (the two-shape merges pass) |

Cases behind those numbers:
- **Branch rule, pure noise:** the AR(1) φ 0.99 run at n = 1,500 (seed 0) has a family of 158 with separation 2.86. That beats the null's 2.82 and 94, so it is called confident. The branch's test only uses n = 300, which is why this was missed. I saw the same thing through `H.fit` in `f1_null.py`.
- **Branch rule, real families:**
  - AR(1) φ 0.99 at 20 % noise: 123 members at separation 2.70 against the null's 2.74.
  - AR(1) φ 0.99 at 30 % noise: families of 33 and 62 fail on size against the null's 63.
  - Random walk at 20 %: 250 members at separation 1.54.
  - Drift at 20 %: 273 members at 1.95.
  - Library size: 219 members at separation 2.77 and 1,860 at 2.30, against the null's 3.05.
- **Your rule, pure noise:** the phase-randomised crowds are always small, 11–141 members, while the real-noise crowds are 73–553.

  | Pure-noise set | Real-noise families | Largest null crowd |
  |---|---|---|
  | AR(1) φ 0.99, 600 | 91 at separation 2.37, 90 at 2.35 | 51 at 2.34 |
  | random walk, 1,500 (both seeds) | 135–160 | at most 50 |
  | drift, 600 and 1,500 | 162–388 | at most 106 |
  | AR(1) φ 0.99, 3,603 | 533 at 2.44, 553 at 2.41 | at most 141 |

- **Why:** a window of strongly coloured noise is mostly a trend, and crowds of trends are what HDBSCAN finds in noise. Phase randomisation turns each trend into a periodic wiggle. With a linear trend kept instead (fit a line per row, phase-randomise what is left, add the line back), the null crowds are 122–417 members at 600–1,500 and 707–783 at 3,603. That matches the real-noise crowds.

**My recommendation for the HDBSCAN rule (for fix round 2):** use k-Shape's own test, run per family, with trend-kept surrogates.
1. For family F, take its medoid m (the member with least summed distance among its fitted members).
2. Compute d_F = median normalised SBD from F's members to m.
3. Make R = 3 draws of trend-kept phase-randomised surrogates of F's own members, z-normalise them, and take their distances to m. Call the 5th percentile p05.
4. F is confident iff d_F < 0.9 × p05. Otherwise it is `noise_like`.

Why this rule:
- It does not depend on size or on separation.
- It compares a family against noise of its own colour.
- It is the same rule k-Shape uses.

Results on the data above (ratio = d_F / p05, using the trend-kept p05):

| Case | Ratio | Outcome |
|---|---|---|
| All 26 pure-noise families | ≥ 0.99 | flagged |
| AR(1) and drift noise | 1.5–2.6 | flagged, wide margin |
| Random walk noise (detrended, so trend-kept equals phase) | 1.001–1.07 | flagged, thin margin |
| Real single-shape families | 0.11–0.65 | confident |
| Library-size families | 0.44 and 0.59 | confident |
| Noise rows in mixed families | 0.89–0.92 | still confident at the 0.9 margin (missed by 0.002) |

- The 0.9 margin is a placeholder, chosen because the selection effect puts noise crowds right at p05 on a random-walk background. Label it as one.

Cost and memory:
- The rule needs |F| × R SBDs against one row per family: milliseconds.
- It removes the three stored n² null matrices. `payload["D_null"]` holds 3 float64 matrices, about 600 MB at `sample` = 5,000, on top of `D_fit`.
- It removes the three extra HDBSCAN fits, so the 3,603 estimate drops from about 156 s to about 40 s.

Tests to add: pure AR(1) φ 0.99 and random walk at n = 1,500 and 3,603.

**2. Should-fix: the coherence null has the same trend blind spot** (`Working/library/coherence.py`).
- 100 pure AR(1) φ 0.99 windows score eq. 17 = 0.813 against the null's p05 0.821.
- So the W2-F rule "below p05 means more coherent than noise" would call pure noise coherent, by a hair.
- Real families clear the null easily: pure drops 0.44–0.57 at 5–10 % noise.
- The squared variant reads correctly (noise 0.473 against a null median 0.463).
- Fix: use the same trend-kept surrogates here.
- The k-Shape null passed every case I ran with plain phase surrogates:
  - Pure noise at 1,500 (k = 4): every family `noise_like`, 84–87 % omitted.
  - Real families at 10 % noise: confident, 1–2 % of events omitted.
  - At 30 % noise it flags 2–3 families and omits 37–74 % of events. That is conservative but honest.
- Switching k-Shape to trend-kept surrogates too would keep one surrogate kind across the Library. Not required.

**3. Nit: `n_misaligned` is high on clean families.** It counts 33 of 100 pure drops (events shifted up to ±20 %) as shifted past ¼ of the length. On the page that reads as a fault in a clean family. Raise the threshold, or show it only when it is a large share of members.

**4. Nit: an unidentified thread exception in the gate run.** The gate output carries a `PytestUnhandledThreadExceptionWarning`. I did not identify its source; please check that it is not the regroup job's cancel path.

**Checked and fine:**
- **Flags reach the Library.** `GroupingResult.fit_summary` and `Family.flags` (`tested: false` for Ward) go through the regroup job result (`fitSummary`, `families[].flags`), the save route (`fit_summary`) and `groupings.fit_summary_json`.
- **Schema.** The column is additive through `_migrate_columns`. It is tested on an old table across two `init_db` calls; old rows stay NULL.
- **Cost before the job.** Members are counted by SQL, the method's own `estimate` is used, and over 15 min the route returns 422 with `cheaper[]` before any job starts.
  - The k-Shape coefficients are consistent with what the implementer measured (explicit k = 3 at 3,603: estimate 87 s, actual 80 s).
  - `cheaper_settings` sorts most expensive first, though its docstring says "cheapest first". A nit.
- **One-start k sweep and cancel.** The sweep is recorded in `k_scores[].starts` and `final_starts`. `GroupingCancelled` is raised between starts and between draws, and the job returns.
- **Edge-padded alignment.** The straggler jump is gone: 60 drops score 0.419, rising gradually to 0.478 with 3 noise members and 0.508 with 6. It used to jump 0.40 → 0.55.
- **`epsilon`.** Renamed; the tree cut is ignored; the test asserts a strict decrease.
- **`_family_coherence`.** The mtime is in the key; held-out members are counted; an unknown or missing file is `continue`d before `os.stat`, so no 500. The anchor is the medoid, else the exemplar, else the least stored distance, so there is no P² search in a GET. The error is a card, and the cache test counts calls.

## 4. What I ran

Experiments are in `...\scratchpad\critic_w2b\`: `f1_null.py`, `f3_rules.py`, `f3_lib.py`, `f4_kshape.py`, `f5_coh.py`. The machine was very heavily loaded (another agent's `eval_snippets` at 100 % CPU), so wall times are inflated.

- **Gate,** with `webui\.venv` python at `d68f84d`, 9 files (`test_sbd`, `test_library_coherence`, `test_library_grouping`, `test_library_grouping_methods`, `test_library_schema`, `test_database`, `test_webui_library`, `test_distances`, `test_import_boundaries`): **282 passed, 3 xpassed, 0 failed** in 95 min.
- **`f1`:** the branch's own HDBSCAN null on pure noise, giving the confident pure-noise family at n = 1,500 (158 members, separation 2.86 against the null's 2.82 / 94).
- **`f3`:** per family, size, separation, d_F, and the phase and trend-kept p05, plus the null crowds for both surrogate kinds, on 12 pure-noise sets and 9 real-family sets. The rule tallies in finding 1 come from this output.
- **`f3_lib`:** the same at n = 3,603 on pure AR(1) φ 0.99 and on three families at 15 % noise.
- **`f4`:** k-Shape `omit_d` = 0 null on real families and on pure noise.
- **`f5`:** coherence null on pure, mixed and noise families, and the straggler check.

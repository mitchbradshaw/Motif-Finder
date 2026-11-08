# Thesis numbers ledger (2026-10-26)

## Completed-review and recovery update — 8 November evening

Later author-requested follow-up (all proposal counts are distinct from human judgements):

| New quantity | Verified value | Source |
|---|---|---|
| CNN continuation cap | Pack 10,800 s (3 h), task 9,900 s; one concurrent task, five-hour scheduler allocation retained for margin | `scripts/thesis/recovery_cnn_longwall.py`; regenerated main DATA resume folder/archive |
| Family hierarchy | 127 parent observations: 78 single-proposal, 35 multi-proposal sequence parents, 14 unresolved; 229 distinct individual proposals, max 15 per parent | `data/event_hierarchy_20261108/family_hierarchy.json` |
| CH14 longer-case extraction | 534 own positive observations -> 530 supported individual trough proposals; 13 multi-extremum observations, 19 unresolved; 1 mV floor, 0.5 s smoothing, 3 s separation | `data/event_hierarchy_20261108/ch14_case.json` |
| CH14 proposal measurements | Median depth 9.220 mV (5–95% 2.467–14.645), median peak interval 602.9 s (51.28–1,358.98), median half recovery 2.491 s (0.829–17.443); 1/530 half recovery missing, 25/530 95%-recovery censored | same case JSON / `ch14_individual_proposals.csv` |
| CH14 timing sensitivity | Floors 0.5/1/2 mV retain 542/530/503 supported extrema; LV 0.712/0.708/0.682; random-timing p 0.002 at each; shuffled-gap p 0.002/0.006/0.885 | same case JSON; core interval nulls, 1,000 draws |
| New blind review | Queue 47: 850 separate items initially unjudged = 750 diversity proposals +54 matched controls +46 planned RQ2 repeats. New proposals SH200/SO200/MJu150/M2concat75/CO75/LM25/M425 | `data/diversity_review_20261108/REPORT.md`; private main DATA key; zero human verdicts written by preparation |

This update supersedes the incomplete-review/recovery statuses in K1–K3 below; those rows preserve the earlier audit.

| Current claim | Verified value | Source |
|---|---|---|
| Blind cross-recording drop panel | 455/457 accepted search presentations (99.6%, Wilson 98.4–99.9%); 79/459 controls (17.2%, 14.0–20.9%); all 916 frozen presentations have own verdicts. Live count 915 excludes a later prior-labelled unsure control. 46 repeats reserved | `data/reviews_completed_20261108/rq2_acceptance.csv` |
| Complete seed null | 64 channels x 200 draws; 464 fixed-cut real matches. MJu26a: 71 real, nine surrogate matches / 200 = 0.045 per draw over all 16 channels. No fixed-cut cap; recalibrated MJu26a 48 matches | `data/recovery_return_20261108/seed_summary.csv` |
| Complete 2 Hz recovery returns | 831/1,014 tasks; MJu26a 587/674, SH 122/170, SO 122/170; 97/129 whole settings. 102 new tasks verified/restored; 183 CNN tasks remain. CPU and MP recovery finished | `data/recovery_return_20261108/audit.json` |
| Current fixed g-11 judgements | 1,014 accepted, 55 not, six artefacts, 17 unsure, five unresolved. 752 accepted assigned / 42 families = 17.9; largest 60. 262 accepted omitted shapes. This is not regrouping of all 2,718 accepted spans | `data/reviews_completed_20261108/historical_g11_verdicts.json` |
| Focused family context inspection | 127 source-linked spans; existing audit flags 84, including 30 with multiple extrema. 22 catalogue components retain saved human extent edits. Flags are not validated splits | `data/accepted_catalogue/family_context_review_summary.json` |

## Working accepted catalogue — 8 November follow-up, not final Chapter 9 statistics

| Quantity | Saved value | Interpretation/source |
|---|---:|---|
| Thesis accepted-span inventory, g-12 | 2,718 | Completed-review update, +956 from the earlier 1,762 snapshot. Eight recording groups; overlaps combined, boundaries pending. `data/accepted_catalogue/summary.json` / `published.json`. |
| MJu26a entries in that inventory | 815 | Physical five-channel/excerpt/full-recording coordinates reconciled; 165 components link more than one copy. |
| CH15 long train proposed spikes | 143 | 206–283 h; 2 mV prominence floor; researcher train-level acceptance; machine extents. |
| CH14 four-hour excerpt proposed spikes | 32 | 1 mV prominence floor; same distinction between bulk acceptance and checked boundaries. |
| Positive fixed-window labels | 2,568 | Retained for event extraction; not 2,568 individually bounded accepted events. |
| Boundary-editor windows/regions | 2,595 | Excludes the two train parents already transcribed into 175 proposed members. |
| Queue 38 frozen review panel | 916 / 916 | 455/457 search presentations accepted; 79/459 controls. Live counter 915 after one later annotation; use frozen membership. |

The 716 blind accepted spans, g-11 morphology snapshot, and historical classifier scores below retain their original
meaning. g-12 groups by recording and is not a new set of waveform-family labels. Its count must not replace 716
as though it had the same sampling/review design. Full audit and refresh method: `data/accepted_catalogue/REPORT.md`.

One row per number the thesis is likely to quote. **Status:** *verified* = recomputed here or read from a
machine-written results file; *as-written* = found only in prose; *inconsistent* = two sources disagree (the
resolution is in the second table); *stale* = true when written, no longer true. Recomputation scripts:
`scripts/thesis/ledger_checks.py` (→ `docs/thesis/data/ledger_checks.json`), `rq1_v2_blind.py`, `catalogue_stats.py`,
`detectors_vs_surrogates.py`, `miss_rate.py`. Every DB read was `mode=ro`; M4_aug (recordings 49–64) and Review
queue 35 were never read. Human-label counts use own looks only (`carried_from IS NULL`) and a cut-off of
2026-10-26 00:00 UTC.

## A. The corpus and the tool

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| A1 | registered source files | **29** on 10-27 (26 + MJu26a_fs2, SH_fs2, SO_fs2); 26 on 10-26 | — | DB `recordings` | DB query; ledger_checks.py | 10-27 | verified |
| A2 | active source files | **20** on 10-27: 23 on 10-26, minus 6 deactivated that day (F2B, Fig2A, L_LM fs2, M2_aug fs2, MJu26a 7.25 Hz, rec 385; audits 541–546), plus the 3 new 2 Hz copies; inactive also M1, M100, M101_t | — | DB | DB query; ledger_checks.py | 10-27 | verified (A3–A4 predate the change) |
| A3 | active channels (without M4) | 167 | — | DB | ledger_checks.py | 10-26 | verified |
| A4 | active channel-hours (without M4) | 69,286 (includes the fs2/fs10 copies) | — | DB | ledger_checks.py | 10-26 | verified |
| A5 | "13 usable recordings, 129 channels, ~52,000 channel-hours" | — | — | RQ4b-detector-sweep.md, *Data and units* | prose (10-17) | 10-17 | stale (A2–A4) |
| A6 | species declared in Settings › Datasets | 5 (oyster, lion's mane, split gill, Cordyceps, enoki); reishi (Fig2A) undeclared | — | DB `datasets` | ledger_checks.py | 10-26 | verified |
| A7 | M2_aug length | 721.0 h × 16 ch at 1 Hz, V | — | DB | ledger_checks.py | 10-26 | verified |
| A8 | M2_concat length | 282.49 h × 16 ch at 1 Hz, V | — | DB | ledger_checks.py | 10-26 | verified |
| A9 | "≈1,000 hours" of oyster recording | 1,003.5 h (721 + 282.5) is M2_aug + M2_concat, per channel, and both are oyster (the researcher, 5 Nov; the 11-03 'lion's mane' label was wrong). With the held-out M4 (505 h) the oyster recordings total about 1,500 h | — | A7 + A8; datasets table (species set 11-03) | ledger_checks.py | 11-03 | corrected |
| A19 | species of the UQ sets | M2_aug, M2_concat and M4 oyster (*Pleurotus ostreatus*); CO chocolate oyster and SO snow oyster, both strains of *P. ostreatus*; SH Asian shiitake (*Lentinula edodes*); LM and MJu26a (including its five-channel copy and its CH14 excerpt) lion's mane (*Hericium erinaceus*); F2A reishi (*Ganoderma lingzhi*). Species claims are made at the Latin level; common names are strains. Supersedes the 11-03 labels (M2_concat as lion's mane; SH, SO unknown), which were also set in DB `datasets` | — | the researcher's labels, 11-05 | — | 11-05 | corrected |
| A10 | shipped analysis blocks | **59** adapter modules | — | `Adapters/`, `tests/test_end_to_end.py` (asserts 59) | file count | 10-26 | verified |
| A11 | detection templates in the sweep | 13 base + 12 CNN (4 models × 3 scales) = 25; 24 volts variants; 45 settings on M2_aug | — | DB `templates`; RQ4b log 10-17 | ledger_checks.py | 10-26 | verified |
| A12 | human judgements, own looks | **15,385** = 12,619 annotations (11,234 imported 2025–26 10-min windows, 1,100 blind showings, 247 Library reviews, 38 other) + 2,766 adjudications; 35,073 carried copies excluded; 0 window_verdicts | — | DB | ledger_checks.py | to 10-25 | verified |
| A13 | judgements given in the tool | 4,151 (A12 minus the 11,234 imported) | — | DB | ledger_checks.py | to 10-25 | verified |
| A14 | old 10-min labels | 2,333 interesting · 8,773 not · 128 artifact (600 samples each; source `imported_10min`) | 11,234 | DB; RQ1 file | miss_rate.py | 10-26 | verified |
| A15 | demo's examiners' copy | 4 h × 5 ch of M2_aug (377–381 h), ids 1001–1005 | — | DEMO_DAY.md | prose | 10-20 | as-written |
| A16 | L_LM is MJu26a | L_LM CH0–4 = MJu26a_fs10 CH10, CH13–16 (1-based) × 1000 plus a constant offset (−25.8, −73.0, +299.3, −304.0, −406.8 mV); whole-length r 1.00000, lag 0 | 5 ch | `docs/datasets/NEW_RAW_2026-10.md` | newsets_fs2.py llm-map | 10-27 | verified |
| A17 | recording 385 is MJu26a | a 4 h, 1 Hz, **volts** excerpt of MJu26a CH14 (via L_LM CH2 at 10 Hz sample 15,777,590): slope 1.0009, r 0.9995 against MJu26a_fs10 CH13's 10-sample means | 14,401 samples | DB arrays | check of 10-27 (this ledger) | 10-27 | verified |
| A18 | the 2 Hz copies | MJu26a_fs2 (ids 692–707, 16 ch, 635.9 h), SH_fs2 (708–711), SO_fs2 (712–715; 4 ch, 480.0 h each); means of 5, V, active | 24 ch | DB; `NEW_RAW_2026-10.md` | newsets_fs2.py derive | 10-27 | verified (MJu26a_fs2 CH9 equals the 5-sample mean exactly) |

## B. RQ2 — seeded search

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| B1 | dip id010 (105 s) accepted | 256 / 263 = **97.3 %** (7 not) | 263 | RQ2b table; DB run group 9 | ledger_checks.py | 10-26 | verified |
| B2 | dip id010 recurrence | 263 matches over 721 h (30.0 days) on 3 channels | 263 | DB | ledger_checks.py | 10-26 | verified |
| B3 | long dip id020 (816 s = 13.6 min) accepted | 94 / 103 decided = **91.3 %**; 104 judged incl. 1 unsure (90.4 %) | 104 | RQ2b; poster; DB run group 12 | ledger_checks.py | 10-26 | inconsistent → R1 |
| B4 | long dip accepted on every channel | 16 / 16 channels, 2–16 accepted each | 94 | DB | ledger_checks.py | 10-26 | verified |
| B5 | spike37 (run 68, seed bdd3d0) own verdicts | 61: 51 accepted (47 int + 4 seed), 7 not, 2 unsure, 1 artifact → 51/58 = **88 %** (51/59 = 86 % if artifact counts as not) | 61 | RQ2b 10-26; DB run group 67 | ledger_checks.py | 10-26 | verified (R5) |
| B6 | drop30 (run 67) | 3,200 detections; 15 verdicts, all carried, 0 own looks | — | DB run group 66 | ledger_checks.py | 10-26 | verified |
| B7 | trough_search | 9 matches, not judged | 9 | DB run group 18 | ledger_checks.py | 10-26 | verified |
| B8 | random-window base rate (RQ1 blind queue) | 235 / 1,084 showings = 21.7 %; first showings 210 / 986 = 21.3 % | 986 | RQ2b; run1613_blind_score.json | rq1_v2_blind.py | 10-26 | verified |
| B9 | nulls at the seeds' lines | drop30 372 real vs 0.01/draw; spike37 16 vs 0.00; long dip 124 vs 0.04; dip 64 vs 0.01 (263 vs 0.8 at the judged cut) | 200 draws | rq2-blind-2026-10-26.md (from result.json) | scripts/rq2_blind.py | 10-26 | as-written (machine files, not re-read) |
| B10 | blind panel queue 35 | **scored 10-28**: drop30 100/100 vs matched random 9/40 (+78 pts, +62 to +88); spike37 28/29 vs 2/16 (+84); dip id010 re-judged 20/20 vs 1/12 (+92); long dip id020 re-judged 20/20 vs 3/12 (+75); all Fisher p < 0.0001; random windows 15/80 (19 %, 12–29 %); earlier yeses still yes blind 51/51 (93–100 %) | 249 | `docs/rq_roundA_2/findings/rq2-blind-2026-10-28.md` | rq2_blind.py score --real | 10-28 | verified |
| B11 | earlier unblinded seed-search assessments | **428** = 263 short dip + 104 long dip + 61 spike; includes unsure/artifact, excludes carried copies; assessments, not a claim of unique events | 428 | B1, B3, B5; RQ2b | sum of recorded own reviews | 11-07 | verified |
| B12 | one-query timing on M2_aug CH2_A1 | 105-s seed, 721 h at 1 Hz (2,595,600 samples): MASS profile 0.385 / 0.409 / 0.443 s; query plus best 200 matches 0.842 s; after warm-up, excluding loading and all surrogate draws | 1 channel | `data/seed_query_timing_20261107.json`; dip_search_3ch spec | STUMPY 1.14.1 on Intel Core i7-1360P | 11-07 | measured; query time only |

| B13 | exact surrogate counts at the common seed thresholds | Short dip 64 real / 2 surrogate matches in 200 draws (mean 0.010); long dip 124 / 7 (0.035); spike 16 / 0 (0.000); drop 372 / 1 (0.005). Surrogate draws are summed over the same channels; B9 rounded the means to two decimals. No channel reaches the 200-match cap at these common thresholds (maximum 111 for drop). | 200 draws per channel | `data/seed_null_verified_20261107.json` | saved HPC results + recommended_cut_corrected(alpha=0.01, correction=none) | 11-07 | verified from full-precision thresholds |

| B14 | distribution of the main drop search | 372 returns across 16 channels: CH2_A1 111, CH4_A2 66, CH1_A1 54; remaining channels 1–34 each; 0.03225 matches per channel-hour over 721 h x 16 | 372 | `data/seed_drop_matches.csv`; B13 | full-precision cut extraction; figs_repo.py seed_distribution | 11-07 | verified; search returns, not all newly discovered or human-reviewed events |
| B15 | scale-pilot trough returns and nulls | Seven returns: 4 at 0.8x, 1 at 1x, 2 at 1.25x. Loose cut 7; surrogate means 16.68 / 8.36 / 10.38. The 3 accepting labels were software-test placeholders, not researcher verdicts | 7 | V-library-edges-and-scale.md sections 3–4 | historical implementation walk | 11-07 | verified from report; illustrative pilot only |

## C. RQ3 poster chart and classifiers

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| C1 | MiniRocket, leave-one-recording-out | AUC **0.973**, BA 0.918 (queue candidates); 0.95–0.99 per recording | 1,689 | manifest.json `robustness_best` | file read | 10-20 | verified |
| C2 | detector agreement on the same candidates | AUC 0.857 | 1,689 | manifest.json `agreement_context` | file read | 10-20 | verified |
| C3 | MiniRocket preliminary (queue 25) | 0.79 vs agreement 0.83 — superseded by C1 | 722 | rq1b-minirocket-preliminary.md | prose | 10-20 | stale |
| C4 | CNN plain accuracy, 10-min blind windows | GASF 0.918 · fusion_cnn_2 0.916 · recurrence 0.907 · GADF 0.904 · fusion_cnn_3 0.900 (majority baseline 0.814) | 429 | run1613_blind_score.json `reference`; W4-A | rq1_v2_blind.py | 10-26 | verified; poster inconsistent → R9 |
| C5 | CNN balanced accuracy, 10 min, cut 0.5 | 0.78–0.83 (0.86–0.88 at cut 0.05–0.1) | 429 | W4-A-evaluation.md | W4-A scripts (not committed) | 10-18 | as-written |
| C6 | CNNs at 1 min | BA 0.39–0.51, AUC 0.30–0.46; call 95–96 % of 1-min windows interesting | 185 | W4-A | prose | 10-18 | as-written (accuracies 0.22–0.39 re-read, verified) |
| C7 | CNNs out of sample (M2_concat, 10 min) | BA 0.63–0.68 at 0.5, AUC 0.81–0.91, only 13 interesting | 129 | W4-A | prose | 10-18 | as-written |
| C8 | RF on human labels (run 79), exam (ii) | macro F1 **0.793** [0.764, 0.819]; BA 0.785 | 2,530 | results.json run 79 | file read | 10-05 | verified |
| C9 | run 79 ΔF1 A − B | exam (ii) +0.159 [0.120, 0.197]; exam (i) +0.276 [0.203, 0.347] | — | RQ1 file | results.json | 10-05 | verified (arms), as-written (Δ) |
| C10 | RF on cluster labels (B.2 run 1613), blind, exam (ii) | macro F1 **0.450** [0.404, 0.495] vs null 0.368 (p 0.001); BA **0.625** [0.586, 0.664]; κ 0.128; P 0.256; R 0.908 | 490 | rq1-v2-blind-2026-10-26.md | rq1_v2_blind.py (app's `blind.score`) | 10-26 | verified |
| C11 | same, exam (i) | macro F1 0.482 [0.426, 0.536], null 0.382 (p 0.001); BA 0.641; P 0.295; R 0.929 | 496 | same | same | 10-26 | verified |
| C12 | human self-agreement | 92 / 98 = 94 %, κ 0.84 | 98 pairs | same | same | 10-26 | verified |
| C13 | arm A vs B.2 on the same blind 10-min windows, no earlier label | A macro F1 0.702 / BA 0.659 vs B.2 0.439 / 0.642; ΔF1 [0.164, 0.357] | 328 | same | rq1_v2_blind.py | 10-26 | verified |
| C14 | "RF cluster labels 0.63 provisional" | 0.625 BA, final (queue 3 fully judged, 1,100 / 1,100) | — | poster | — | — | stale ("provisional") |
| C15 | M4 held-out exam (queue 36) | R4 AUC **0.98** (0.97–0.99), BA **0.93** (0.88–0.97) unweighted (primary); weighted AUC 0.96, BA 0.77; CNNs AUC 0.59–0.66 (R4 minus CNN 0.33–0.40); agreement-as-score AUC 0.85; share real 10 % (6–14); ladder 0/3/16/35/53 %; v1 precision 64 % (n 14); 276 answered of 290, 14 unsure, 12 spans unreadable by R4 | 290 | `docs/rq_roundA_2/findings/m4-exam-2026-10-28.md`, `DATA/derived/exam/M4/results.json` | m4_exam_score.py --real (once) | 10-28 | verified |
| C16 | fair CNN arm: EfficientNet-B0 on R4's rows and folds | pooled AUC GASF **0.971** (0.965–0.977), GADF 0.970 (0.964–0.975), fusion 0.973 (0.967–0.978) vs R4 0.971; R4 minus CNN 0.000 / +0.001 / −0.002, each paired interval within ±0.007; no per-recording interval excludes zero; BA 0.915–0.916 vs 0.919 | 2,456 | `docs/rq_roundA_2/findings/rq1b-fair-cnn-2026-10-29.md` (+ `.json`), `DATA/derived/models/rq1b_cnn_vs_minirocket/fair/` | rq1b_cnn_vs_minirocket.py import | 10-29 | verified |
| C17 | Chapter 8 population corrections | CNN BA 0.78–0.83 / AUC 0.93–0.96 is the **pooled 429 ten-minute blind windows**, not M2_aug alone. M4 has 276 answered for candidate estimates, but **257 classifier cases**: seven seed verdicts unmapped by frozen scorer, 12 unreadable; 59 positive, 198 negative including five artefacts. R4 confusion TP52 / FP6 / FN7 / TN192 | 429 / 257 | W4-A-evaluation.md; M4 manifest metrics.y, results.json; wave1 exam_items.csv; data/ch08_verification.json | chapter-end source audit; no rescoring | 11-07 | verified; corrected captions and example-figure cohort |
| C18 | saved forest settings and paired blind comparison | run79 A/B: **100 trees, 24 retained features**; run1613 B2: **300 trees, 26 features**, 24,843 training windows. Same blind ten-minute windows: manual A F1/BA/P/R 0.748/0.701/0.89/0.41; cluster B2 0.440/0.630/0.24/0.93. No-earlier-label subset C13; M2_concat A F1 0.591, B2 0.380 | 429; M2_concat 129 (13 interesting) | saved paired/shape-forest results.json; data/rq1_v2_blind/run79_armA_vs_run1613_10min.json; data/ch08_verification.json | read-only saved-result audit | 11-07 | verified; later comparison assesses complete pipelines, not label source alone |

## D. R3 — how many candidates are real (blind stratified queues 25 and 28)

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| D1 | M2_aug, unjudged candidates interesting | 24.6 % [21.3, 28.0] | 754 answered, 46 unsure | estimate.json (M2_aug) | rq1b_candidate_events.py; re-read | 10-20 | verified |
| D2 | four new recordings | CO 9.8 % [6.5, 13.4] · M2_concat 13.2 % [9.7, 17.1] · L_LM fs2 14.1 % [9.9, 18.6] · LM 16.0 % [12.0, 20.5] | 1,159 / 1,160 | estimate.json ×4 | re-read | 10-21 | verified |
| D3 | 1–2 families agree | 0–5 % (0, 0, 0, 3.8, 5.1 %) | 39–95 per rec | estimate.json | ledger_checks.py | 10-26 | verified |
| D4 | 9+ families agree | **40–63 %** (CO 40, L_LM 40, M2_aug 59, LM 61, M2_concat 63) | 66–248 per rec | estimate.json | ledger_checks.py | 10-26 | verified; "50–67 %" → R2 |
| D5 | drop_detection_v1 precision | 92–100 % on all five (M2_aug 95.5 %) | 13–49 per rec | estimate.json | ledger_checks.py | 10-26 | verified |
| D6 | drop_detection_v5 | 81–100 % | 18–57 | same | same | 10-26 | verified |
| D7 | wavelet_encoded | 86–100 %, except M2_concat 31 % | 13–59 | same | same | 10-26 | verified |
| D8 | deconvolved_troughs · matrix profile | 1–7 % · 0 % everywhere | — | same | same | 10-26 | verified |
| D9 | candidate table, M2_aug | 2,015,081 detections → 1,502,319 events; carried labels 24,911 int / 108,645 not / 3,758 artifact | — | rq1b-candidate-events.md; estimate.json (`positives_before` 24,911, judged 137,314) | re-read | 10-18 | verified (24,911), rest as-written |
| D10 | agreement AUC | 0.874 (loose agreement, 133,556 labelled events) | — | rq1b-candidate-events.md | prose | 10-18 | as-written |
| D11 | researcher's miss rate per look | 11.5 % (4.6–23 %), from 6 changed answers in 98 repeats | 98 | rq1b-candidate-events.md | prose | 10-18 | as-written |
| D12 | durations of the five judged-sweep recordings | 2,599.4 recording-hours; 23,075.3 channel-hours; 45 channels | 5 recordings | `data/ledger_checks.json` recording metadata (M2_aug, M2_concat, LM, CO, MJu26a CH10 and 13-16 at 2 Hz) | sum of hours and hours x channels | 11-07 | verified |

## E. Catalogue (chapter 9)

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| E1 | accepted swing, pooled blind queues | min 0.17 · median **19.8** · p95 **122** · max 541 mV; 8.8 % > 95 mV; 2.5 % < 1 mV | 716 | catalogue-stats-2026-10-26.md | catalogue_stats.py | 10-26 | verified |
| E2 | median swing per recording | 14.0 (L_LM) – 30.1 (M2_concat) mV | 79–341 | same | same | 10-26 | verified; poster "12–20" partly → R11 |
| E3 | accepted duration | median 603 s, 5–95 % 40 s – 1,272 s (21.2 min), max 7,200 s | 716 | same | same | 10-26 | verified (poster reproduces; "several hours" overstated) |
| E4 | share of accepted events that fall | 68 % pooled, 57–80 % per recording (median-excursion rule) | 716 | same | same | 10-26 | verified; poster "73 % (56–86 %)" → R12 |
| E5 | Library accepted members | 210 members = 152 distinct events by the audit's pairwise ≥ 50 % rule (**144** under the events rule, I1 — quote 144); swing median 13.8 mV | 210 | same | same | 10-26 | verified |
| E6 | Library audit "197 accepted members = 142 distinct events" | — | — | library-fragments-and-duplicates.md | library_fragment_audit.py | 10-17 | stale (E5: 210 / 152 now) |
| E7 | interval between accepted dips (id010) | median 53 min, 5–95 % 3.4 min – 13.5 h, CV 2.2–4.1 (bursty) | 253 intervals | same | same | 10-26 | verified |

## F. Detectors against their surrogates, and the miss rate

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| F1 | "in 255 of 552 tasks the real signal gave no more detections than its phase-randomised copy" | 255 / 552, **batch 3 only** (LM_fs2, CO_fs2, L_LM fs2; 1 draw) | 552 | RQ4b log 10-19 | detectors_vs_surrogates.py | 10-26 | verified |
| F2 | same over every session read (M4 excluded) | 849 / 1,880 | 1,880 | same | same | 10-26 | verified |
| F3 | families always above their null | OASIS, deconvolved_troughs, noise_threshold (× 39–283) | — | same | same | 10-26 | verified |
| F4 | families always at or below | symbol_search, wavelet_encoded (× 0.00–0.11) | — | same | same | 10-26 | verified |
| F5 | interesting 10-min windows no non-CNN detector touches | 18 / 2,333 = 0.8 % (4.6 % of not-interesting) | 2,333 | miss-rate-2026-10-26.md | miss_rate.py | 10-26 | verified |
| F6 | best lift | signal_threshold −10 mV 21.3 (12 % touched); drop detectors ≈ 5; OASIS 1.4; mp_threshold 6 0.53 | — | same | same | 10-26 | verified |
| F7 | "only ~6 % of M2_aug caught by no detector" | — | — | rq1b-candidate-events.md | prose | 10-18 | as-written |
| F8 | six precise variants against a 20-draw null, M2_aug, 16 channels each | real beat all 20 draws on drop v1 16/16 (pooled × 23.4), CNN GADF 10-min 16/16 (× 6.5), CNN recurrence 10-min 14/16 (× 2.7), drop v5 same-fraction 0.7 14/16 (× 2.2); fell below all 20 on wavelet-encoded level 5 16/16 (× 0.075) and drop v1 slope σ 4 12/16 (× 0.58); chance 16/21 ≈ 0.8 channels; every pooled ratio within 4 % of its 1-draw value | 96 tasks × 21 runs | `docs/rq_roundA_2/findings/surrogates20-2026-10-29.md`, `docs/thesis/data/ch06_20draw/` | scripts/thesis/surrogates20_readout.py (the returned task records) | 10-29 | verified |
| F9 | overlap table for every stored setting | 46 rows (34 non-CNN, 12 CNN). The 16-channel rows use 2,333 interesting and 8,773 uninteresting windows; the two-channel rows use 272 and 1,058. Undefined 0/0 lift displayed as a dash. Full table in Appendix H | 46 settings | `docs/thesis/data/miss_rate/per_variant.csv` | miss_rate.py (26 Oct output) | 11-07 | verified |

## G. Demo day (DEMO_DAY.md, 2026-10-20/21)

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| G1 | W1 spike route | run 7177: **9 spans** (each lumps ~10 spikes; 67 of ~90 spikes covered) | 9 | DB run 7177; DEMO_DAY W1 | ledger query | 10-26 | verified → R7 |
| G2 | W1 wavelet route · W2 drops | 11 events (run 7178) · 6 drops (run 7179) | — | DB | ledger query | 10-26 | verified |
| G3 | demo drop detector, 5 ch × 721 h | **365** detections (run group 308) | 365 | DB; report.md | ledger query | 10-26 | verified |
| G4 | Review queue 30 | **325** items (overlap sets as one item); 3 judged, carried | — | `queue_counts` | ledger query | 10-26 | verified → R6 |
| G5 | demo precision | containment 83 % (45 / 54), extent 2 %; × null 14.9 | 54 | report.md snapshot | bridge report | 10-20 | verified → R3 |
| G6 | seed 056a5d | 1000 matches, **155** kept by the null's cut; queue 31 **149** items on 10-20, 148 today; 0 judged | 155 | DB; backup deck | ledger query | 10-26 | verified → R6 |
| G7 | F-30 family | 79 members, medoid m-191 on CH2_A1 at 442 h | — | DEMO_DAY | prose | 10-20 | as-written |

## H. Block evaluations and the drop_motifs reports

| # | claim | value | source | status |
|---|---|---|---|---|
| H1 | noise_threshold beats its 20-draw null | 5 of 6 spans (e.g. 44 vs 0.0 on M2_aug CH0 24 h) | W1-evaluation.md | as-written (scratch results not committed) |
| H2 | deconvolved_troughs v2 | 155 / 551 / 117 vs ~3 on three 24 h spans; counts inflated by follow-ons | W1-evaluation.md | as-written |
| H3 | cwt_events | 24 / 38 / 6 vs 0.2–0.3 | W1-evaluation.md | as-written |
| H4 | W3: complexity_fingerprint, chain_cycles, motif_lengths ship | 3/3, 3/3, 2/3 recordings beat the null | W3-evaluation.md | as-written |
| H5 | W3: datasets separate on complexity curves | silhouette 0.428 vs AAFT 0.22–0.37 (p 0.048) | W3-evaluation.md | as-written |
| H6 | species from absolute scale vs normalised shape | 0.781 vs 0.614 balanced accuracy (chance 0.333); resolution alone 0.575; both 0.741 | CLAIMS.md rows 12–15; DECODE_species.json | verified (JSON) |
| H7 | shape vector predicts samples-per-event | 0.753 BA (chance 0.25) | CLAIMS.md row 9; DECODE_species.json | verified (JSON) |
| H8 | family vs species / resolution (Cramér's V) | 0.087 (p 0.094) vs 0.277; pooled 0.250 vs 0.250 | CLAIMS.md rows 6–8 | as-written (null medians verified in JSON) |
| H9 | drop_motifs12b store | 4,023 events (oyster 754, reishi 2,425, lion's mane 844, region B only) | FIGURES.md | as-written |
| H10 | S3.1 morphs | 4 of 15 sequences morph; 13 of 15 end in a different family | FIGURES.md | as-written |
| H11 | lion's mane close-pair depth ratio | 1.16×, p 0.111 over 421 pairs: no effect | FIGURES.md | as-written |
| H12 | A100 matrix profile, one 721-h channel | 12.3 min (736 s); ~18× the 16-core PC | RQ4b, gpu_stump outputs | as-written |

## I. Library events and groupings (chapters 9–10)

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| I1 | events table (all members) | 3,603 non-Review members → 1,116 events; 590 outside Fig2A; the 210 accepted members are 144 events | 3,603 | `docs/thesis/data/library_events/summary.json` | library_events.py | 10-26 | verified (re-running now also reads the 600 promoted members) |
| I2 | grouping g-10 | 590 items → 25 families, 410 assigned, 180 omitted; 8 hold both recordings (M2_aug, rec 385); ARI 0.96 / 0.93 at 1 % / 2 %; cophenetic 0.66 | 590 | `library_events/events_grouping.json` | make_events_grouping.py | 10-26 | verified |
| I3 | verdict-free promote | 716 accepted own looks (queues 25, 28) → 600 promoted (M2_aug 321, LM 106, CO 96, M2_concat 77), 30 skipped as duplicates, 86 refused (L_LM fs2 inactive); adjudications, annotations, review_audit unchanged (37,839 / 12,622 / 4,385) | 716 | `library_events/promote_blind_accepted.json` | promote_blind_accepted.py | 10-27 | verified |
| I4 | events table (active recordings) | 1,689 members → 1,097 events (M2_aug 830, LM 100, CO 93, M2_concat 74); 678 hold an accepted member | 1,689 | `library_events_all_active/summary.json` | library_events.py --active-only | 10-27 | verified |
| I5 | grouping g-11 | 42 families, 817 assigned, 280 omitted; 39 hold 2+ recordings, 14 all four; ARI 0.93 (0.90–0.95) / 0.88 (0.86–0.91) at 1 % / 2 %; cophenetic 0.649; accepted events 519 assigned in 41 families | 1,097 | `library_events_all_active/events_grouping.json` | make_events_grouping.py --active-only | 10-27 | verified |

## J. Round B, first reads (chapter 10)

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| J1 | B1 intervals, M2_aug drop v1 | against random timing most channels sit inside the band; CH3 more regular (LV 0.72, band 0.82–1.20, p 0.004; borderline after 16-channel correction); against shuffled gaps LV below the band on 11 of 16 channels (slow rate drift) | 16 ch | `Working/interrogation/intervals.py::interval_nulls` | B1 build (headless, read-only) | 10-28 | verified (agent run; not BH-corrected) |
| J1b | B1 intervals, final read (5 Nov), drop v1 on 56 channels (M2_aug 16, M2_concat 16, LM 4, CO 4, MJu26a_fs2 16; MJu26a replaces L_LM), 44 measurable (3+ events) | against Poisson: LV p < 0.05 on 9/44, none after BH; CV2 2 after BH, both more regular (M2_aug CH3 n 127 CV2 0.78; LM CH1 n 30 LV 0.47 CV2 0.60; q 0.044); against shuffled gaps: LV below after BH on 18/44 (M2_aug 9/16, M2_concat 2/15, LM 2/4, CO 1/2, MJu26a 4/7), above on 1 (M2_concat CH6); median LV 1.04 (M2_aug 0.99, M2_concat 1.42, LM 0.82, CO 1.06, MJu26a 0.84); 20 channels < 10 events | 56 channels | `docs/thesis/data/ch10_b1/`, `docs/rq_roundA_2/findings/b1-intervals-2026-11-05.md` | `scripts/thesis/b1_intervals.py` (interval_nulls, 1,000 draws; BH per measure x null over measurable channels) | 11-05 | verified |
| J2 | B2 morph | 0 of 5 testable sequences beat their shuffle (0.2 expected); 99 of 118 sequences sit on inactive recordings (98 Fig2A); p floor ≈ 0.05 at 20 elements | 118 | `Working/library/morph.py` | B2 build | 10-28 | verified (agent run) |
| J2b | B2 step size (companion) | 5 of 19 testable sequences have neighbours more alike than shuffled at p < 0.05 (0.9 expected; 4 survive BH); ratios 0.58–0.84 (sq-1, 7, 9, 4, 12). Persistence or gradual change, not told apart; sq-1 and sq-4 (also fraction-testable) do not morph by the fraction, so persistence. 5 go the other way (ratios 1.15–1.33, p > 0.97), four visibly alternating (observation only) | 19 | `morph.sequence_morph` (headless, full-resolution samples) | step-size companion | 10-28 | verified (re-run) |
| J3 | B3 restitution | sequences: raw Stouffer z +2.94, given depth +0.60, given order +0.70, against the gap after +9.88; census M2_aug +5.02, M2_concat +3.08 (halved by fall width: +2.46, +1.14) | 74 seqs, 987 pairs | `docs/thesis/data/ch10_fhn/b3_restitution.json` | `Pipelines/fhn/run_b3.py restitution` | 10-28 | verified (re-run identical) |
| J4 | B3 held-out-cycle ratios | real cycles 0.995–2.06 (no model below the neighbours' mean); fake cycles 0.91–1.04 | 6 datasets × 4 models | `b3_track.json` | `run_b3.py track` | 10-28 | verified (agent run); **parked 4 Nov: not in the thesis** (model half of B3, researcher) |
| J5 | B3 drift | kernel recovery fraction: chain 542 ρ +0.83 (p 0.001), chain 6 +0.55 (p 0.024); FHN α no drift (p ≥ 0.11); FHN-osc and Izhikevich tracks fail the fake-cycle check (17–25 % false positives) | 6 tracks | `b3_track.json` | `run_b3.py track` | 10-28 | verified (agent run); **parked 4 Nov: not in the thesis** (model half of B3, researcher) |
| J6 | B4 census (drop v1) | M2_aug: 688 events, 26 co-occurrences (artifact 3, propagation 1, independent 4, shared driver 18); within-pack 8 vs rotation 1.9 (p 0.002); after BH over 24 pairs only CH15_D2–CH16_D2 survives (n 2), timetable p 1.0 (no lag); cross-pack non-copies 18 vs 6.3 (p 0.001). M2_concat: 91 co-occurrences, 90 copies, CH5–CH8 pairs 12–19 each vs < 0.11. CO, LM: 0 | 4 recordings | `docs/thesis/data/ch10_b4/` (b4_summary.json, b4_pairs.csv; census hashes 227f9401, 4e586b9a, 9063f461, 9cb136f2) | scripts/thesis/b4_cross_channel.py on backup 20261028-220239 | 10-28 | verified |
| J6b | B4 census on MJu26a_fs2 (drop v1, census 5, hash f83f97f2; packs not set) | 463 events, 16 co-occurrences vs rotation 3.2 (p95 7; p 0.001); 10 pairs pass BH (q 0.004) on 1-3 each; bins artifact 7, propagation 1, independent 8; timetables CH1-CH2, CH1-CH6 median lag 0 s (p 0.25, 0.23), none beats the lag null; no evidence of propagation | 16 channels, 120 pairs | `docs/thesis/data/ch10_b4/`, `docs/rq_roundA_2/findings/rq4n-partial-2026-11-05.md` | site POST /api/cross/census; `scripts/thesis/b4_cross_channel.py` on backup 20261105-130347 | 11-05 | verified |
| J7 | B6 families across recordings and species (g-11) | 39/42 families span ≥ 2 recordings (14 all four), 39/42 ≥ 2 species, 36 both oyster-type and lion's mane; shuffled labels 41.3 (p 0.023); MI recording 0.219 vs 0.128 bits, species 0.165 vs 0.083 (p 0.0001); single-recording F-35, F-53, F-80 (all M2_aug) | 804 members, 10,000 draws | `docs/rq_roundA_2/findings/b6-families-species-2026-11-03.md`, `docs/thesis/data/ch10_b6/` | scripts/thesis/b6_families_species.py (the Recurrence page's payload) | 11-03 | verified |
| J7b | B6 re-run with corrected species (5 Nov) | 28/42 g-11 families hold both P. ostreatus and H. erinaceus (38/42 ≥ 2 strains); shared by species 28 vs null 33.8 (p 0.005); MI species 0.078 vs 0.042 bits (p 0.0002), strain 0.155 vs 0.085 (p 0.0001); within P. ostreatus recordings 0.156 vs 0.094; H. erinaceus = LM only (76 of 804 members) | 804 members | `docs/thesis/data/ch10_b6/summary_species_5nov.json` | `scripts/thesis/species_rerun_b6_b12.py` | 11-05 | verified (re-run of J7's table) |
| J8 | B5 Map timing (3 h bins) | co-modulation per channel, median by recording: M2_aug 0.35, M2_concat 0.33, CO 0.26, LM 0.30, L_LM 0.21 vs 0.00 shifted; beyond shifts on 45/45 channels; paired surrogates 0.02–0.04; channel bands M2_aug 0.29, CO 0.20, L_LM 0.23 (p ≤ 0.04), LM 0.00 (p 0.46), M2_concat 0.19 with its surrogate 0.18 (copies) | 45 channels | `docs/rq_roundA_2/findings/b5-map-timing-2026-11-03.md`, `docs/thesis/data/ch10_b5/` | scripts/thesis/b5_map_timing.py (binning = the page's, 39/39 on M2_aug CH6) | 11-03 | verified |
| J8b | B5 Map timing on the 2 Hz sets' first 31 jobs (13 settings MJu26a, 9 SH, 9 SO) | co-modulation median MJu26a 0.33, SH 0.46, SO 0.42 vs 0.00 shifted; surrogates 0.08-0.13; beyond shifts on 24/24 channels; channel bands SO 0.40 (p 0.005; surrogate 0.04), SH 0.07 (p 0.24), MJu26a 0.15 (p 0.005) but its surrogate 0.28 | 24 channels | `docs/thesis/data/ch10_b5_newsets/`, `docs/rq_roundA_2/findings/rq4n-partial-2026-11-05.md` | `scripts/thesis/b5_map_timing.py` (unchanged, RECORDINGS set to the three) | 11-05 | verified |
| J9 | B12 shapes and intervals across recordings and species | shapes: recordings differ (11/15 features pass BH; 9/14 within duration bands; 7/10 on the duration residual; waveform R² 0.020, p 0.0005; max ε² 0.062); species not shown (R² 0.005, p 0.064; within lion's mane 0.035); intervals LV by dataset p 0.057, CV2 0.070, by species 0.38; fastest-edge falls 91 % (76–98 %) | 716 events; 45 channels | `docs/rq_roundA_2/findings/b12-shapes-intervals-2026-11-03.md`, `docs/thesis/data/ch10_b12/` | scripts/thesis/b12_shapes_intervals.py | 11-03 | verified (helper's run, numbers read from its outputs) |
| J9b | B12 re-run with corrected species (5 Nov) | species (517 P. ostreatus vs 199 H. erinaceus): 1/15 features pass BH (drop share 93 % vs 85 %, carried by LM 76 %); 1/14 within duration bands, 0/9 residual; waveform R² 0.004, p 0.03 (fails BH); within P. ostreatus recordings 7/15, within H. erinaceus 7/15 (waveform R² 0.039); strain 7/15; intervals by species LV p 0.09, CV2 0.16; within P. ostreatus datasets 0.047, 0.036 | 716 events; 40 channels | `docs/thesis/data/ch10_b12/shape_tests_5nov.csv`, `interval_tests_5nov.csv` | `scripts/thesis/species_rerun_b6_b12.py` | 11-05 | verified (re-run of J9's measurements) |
| J10 | B9 cwt_events durations vs AAFT (negative) | 20 one-day spans: real 632 drops (260 clean) vs AAFT 1,087 (517); 6/20 spans beat their copy, no recording overall; durations KS real vs AAFT p 0.39–0.83 per recording, pooled 0.59 (M2_concat longer, p 0.007); GMM modes 17 s and 87 s, stronger in AAFT (ΔBIC 172 vs 79); site check M2_aug 348.5–372.5 h: real 93, AAFT 51, phase 0 (jobs 841–843) | 20 spans × 3 | `docs/rq_roundA_2/findings/b9-cwt-durations-2026-11-03.md`, `docs/thesis/data/ch10_b9/` | scripts/thesis/b9_cwt_durations.py, b9_modes.py; site jobs 841–843 | 11-03 | verified (helper's run) |
| J11 | B10 scales beyond AAFT (motif_lengths, 8 h spans) | lengths clearing AAFT: M2_aug 30 s–16.3 min, M2_concat 30 s–4.4 min, CO 30 s–25.1 min, LM 30 s–16.3 min, MJu26a none (a ~20 min oscillation that AAFT keeps); strongest gap at the shortest length; CNNs vs one phase copy: 10 min on 5/5 recordings, 60 min on 3, 1 min on 0 | 5 spans (site jobs 836–840) | `docs/rq_roundA_2/findings/b10-scales-2026-11-03.md`, `docs/thesis/data/ch10_b10/` | site (Analyse runs) + b10_readout.py, b10_cnn_scales.py | 11-03 | verified (helper's run; M2_aug screenshot read) |

## The disagreements, settled

| # | disagreement | correct figure | why |
|---|---|---|---|
| R1 | 94/103 vs 94/104 | **94 of 103 decided (91 %)**, 1 unsure excluded | DB: 91 int + 3 seed, 9 not, 1 unsure. Every other precision in the thesis (R3, the blind queues) leaves unsure out; 94/104 puts it in the denominator. Say "91 % (94 of 103; 1 unsure)". |
| R2 | top rung 40–63 % vs 50–67 % | **40–63 %** | The five estimate.json files give 40, 40, 59, 61, 63 %. The raw sampled shares are 36–61 %; nothing reproduces 50–67 %. |
| R3 | drop_detection_v1 92–100 % vs the demo's 83 % | both true, different measures. Quote **92–100 %** | 92–100 %: a blind, stratified, event-by-event sample (13–49 per recording). 83 % (45/54): containment of the demo run's detections inside old 10-minute windows a human had marked, on 5 channels, not blind. |
| R4 | 16 vs 23 vs 26 recordings; "1000 hours" vs 721 h | **26 registered source files, 23 active** (22 / 25 without M4); about **18 distinct physical recordings** (15 if the four mfs2 logger sessions are one) once copies are merged (M2_aug fs2, L_LM fs2, MJu26a / fs10 and the Mushroom excerpt are copies). "16" matches no definition (it is M2's channel count); state the definition used. **721 h** is M2_aug alone; **≈1,000 h** is M2_aug + M2_concat (721 + 282.5), per channel. |
| R5 | spike seed "not judged" vs 51/58 | **51 / 58 (88 %)**, 61 own verdicts | The "not judged" lines (RQ2b table, 10-18 log) predate the queue-24 judging and the table row is trough_search. 51/58 leaves out 2 unsure and 1 artifact. If artifact counts as not, as in R3, it is 51/59 (86 %): say which. |
| R6 | 365 vs 325; 155 vs 149 | **365 detections → 325 Review items; 155 kept matches → 149 items** (148 today) | Review shows overlapping detections of one run as one item. It hides matches that are the same event as an already-judged human span. Both numbers are right; label them "found" and "to review". |
| R7 | "9 spikes" vs "9 spans" | **9 spans** | Run 7177 holds 9 detections, each lumping ~10 spikes. The backup deck's slide 5 "9 spikes" is wrong. |
| R8 | CNN 0.91–0.92 accuracy vs balanced accuracy 0.78–0.83 | quote **balanced accuracy 0.78–0.83** (10 min, cut 0.5), with plain accuracy 0.90–0.92 beside the 0.81 majority baseline | Only 19 % of the blind 10-minute windows are interesting, so "always no" scores 0.81. Plain accuracy flatters. |
| R9 | the poster's CNN numbers | GASF 0.92 ✓; **GADF 0.90**, **recurrence 0.91**; fusion 0.90 (fusion_cnn_3) or 0.92 (fusion_cnn_2) | Re-read from the reference rows (C4). The poster's GADF and recurrence are rounded up, and the fusion checkpoint is unnamed. |
| R10 | 60 vs 59 blocks | **59** | 59 shipped adapter modules; `tests/test_end_to_end.py` asserts 59. |
| R11 | "24 detection algorithms" | **25 detection templates** (13 base + 12 CNN) in **12 families**; 24 is the count of the volts sweep *variants* | The DB holds 13 base detection templates (drop v1/v5, dehshibi, Wavelet prototype, wavelet_encoded, mp_threshold, mp_motifs, symbol_search, signal / noise threshold, deconvolved_troughs, OASIS, BEADs) and 12 CNN templates. cwt_events is an interrogation template. |
| R12 | "≈13,000 human labels" | **≈15,400 own human judgements** (15,385 before 2026-10-26). 11,234 of them are imported 2025–26 window labels; ≈4,150 were given in the tool | 13,000 is close to the annotations table alone (12,619). It leaves out 2,766 own Review adjudications. The 35,073 carried copies are not human looks and are excluded. |
| R13 | catalogue poster figures | see `findings/catalogue-stats-2026-10-26.md` | Duration (10 min; 40 s–21 min) and "top 5 % > 95 mV" reproduce. "Median 12–20 mV" is 14–30 mV per recording (20 pooled). "73 % falls (56–86 %)" is **68 % (57–80 %)** by the median-excursion rule; its original rule is not recorded. "Several hours" is at most 2 h. |

## K. Follow-up returns and prose revision, 8 November 2026

| # | claim | value | n | source | produced by | date | status |
|---|---|---|---|---|---|---|---|
| K1 | fixed-cut drop transfer beyond M2_aug | Complete targets: M2_concat 76 real / null mean 0.005; M4 66 / 0.005; LM 195 / 0.015; CO 15 / 0; SH 21 / 0.005; SO 20 / 0. 393 matches in those six recordings. MJu26a: 65 / 0.045 on 11 completed channels, 71 real across all 16. All-target real total 464. Same cut 2.2080859509008204 and physical duration 377 s; no fixed-cut channel is capped | 59/64 null comparisons complete, 200 draws/channel | data/hpc_return_20261108/seed_summary.json and verification.json; original transfer specs/returns | read-only hash-checked return analysis | 11-08 | verified; MJu26a full null and human acceptance pending |
| K2 | new blind transfer review | 464 raw matches; exclude five earlier adjudications; Review merges two overlapping LM proposals → **457 match presentations + 459 random controls = 916** in queue 38. **46 repeats** held outside the app until primary review is complete | 916 + 46 reserved | private DATA/derived/rq2_blind/20261108-drop-transfer/key.json; live API counts | transfer_review_20261108.py, existing blind panel and Review queue APIs | 11-08 | queue ready; no acceptance result claimed |
| K3 | 2 Hz sweep return state | **729/1,014 complete**, 258 missing, 27 refused; MJu26a 497/674, SH 116/170, SO 116/170. **79/129 whole settings** (25/26/28); 280 completed tasks imported on PC, 449 usable returned tasks not yet imported. Remaining: 29 CPU, 250 CNN, six matrix-profile tasks | 1,014 tasks | data/hpc_return_20261108/audit.json, rq4_summary.csv | logical-task/specification-hash audit, existing import/cache lookup | 11-08 | verified; full candidate/agreement census pending |
| K4 | example family sizes for revised 8.4 | g-11: 817 assigned events / 42 families = **19.5 per family**; human-accepted assigned subset 519 / 41 = **12.7**. Old manual fixed-window labels are separate. No universal 500-per-family minimum established | g-11, 1,097 total events | data/library_events_all_active/events_grouping.json | saved grouping, arithmetic | 11-08 | verified |

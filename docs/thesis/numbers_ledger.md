# Thesis numbers ledger (2026-10-26)

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
| A9 | "≈1,000 hours" of oyster recording | 1,003.5 h (721 + 282.5), per channel, two recordings | — | A7 + A8 | ledger_checks.py | 10-26 | verified (see R4) |
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
| J2 | B2 morph | 0 of 5 testable sequences beat their shuffle (0.2 expected); 99 of 118 sequences sit on inactive recordings (98 Fig2A); p floor ≈ 0.05 at 20 elements | 118 | `Working/library/morph.py` | B2 build | 10-28 | verified (agent run) |
| J2b | B2 step size (companion) | 5 of 19 testable sequences have neighbours more alike than shuffled at p < 0.05 (0.9 expected; 4 survive BH); ratios 0.58–0.84 (sq-1, 7, 9, 4, 12). Persistence or gradual change, not told apart; sq-1 and sq-4 (also fraction-testable) do not morph by the fraction, so persistence. 5 go the other way (ratios 1.15–1.33, p > 0.97), four visibly alternating (observation only) | 19 | `morph.sequence_morph` (headless, full-resolution samples) | step-size companion | 10-28 | verified (re-run) |
| J3 | B3 restitution | sequences: raw Stouffer z +2.94, given depth +0.60, given order +0.70, against the gap after +9.88; census M2_aug +5.02, M2_concat +3.08 (halved by fall width: +2.46, +1.14) | 74 seqs, 987 pairs | `docs/thesis/data/ch10_fhn/b3_restitution.json` | `Pipelines/fhn/run_b3.py restitution` | 10-28 | verified (re-run identical) |
| J4 | B3 held-out-cycle ratios | real cycles 0.995–2.06 (no model below the neighbours' mean); fake cycles 0.91–1.04 | 6 datasets × 4 models | `b3_track.json` | `run_b3.py track` | 10-28 | verified (agent run) |
| J5 | B3 drift | kernel recovery fraction: chain 542 ρ +0.83 (p 0.001), chain 6 +0.55 (p 0.024); FHN α no drift (p ≥ 0.11); FHN-osc and Izhikevich tracks fail the fake-cycle check (17–25 % false positives) | 6 tracks | `b3_track.json` | `run_b3.py track` | 10-28 | verified (agent run) |
| J6 | B4 census (drop v1) | M2_aug: 688 events, 26 co-occurrences (artifact 3, propagation 1, independent 4, shared driver 18); within-pack 8 vs rotation 1.9 (p 0.002); after BH over 24 pairs only CH15_D2–CH16_D2 survives (n 2), timetable p 1.0 (no lag); cross-pack non-copies 18 vs 6.3 (p 0.001). M2_concat: 91 co-occurrences, 90 copies, CH5–CH8 pairs 12–19 each vs < 0.11. CO, LM: 0 | 4 recordings | `docs/thesis/data/ch10_b4/` (b4_summary.json, b4_pairs.csv; census hashes 227f9401, 4e586b9a, 9063f461, 9cb136f2) | scripts/thesis/b4_cross_channel.py on backup 20261028-220239 | 10-28 | verified |

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

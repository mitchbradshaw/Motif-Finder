# Prose context and instruction coverage

## Later 8 November: three-hour CNN budget, event hierarchy and Round B

The author requested a three-hour maximum CNN pack budget, a full CH14 case study, an assessment of how the
enlarged Library affects Round B, and a useful review of at most 1,000 items. They additionally required that
distinct events remain separate and combined spans be treated as trains/sequences. Completed: regenerated CNN
continuation (10,800-s pack, 9,900-s task, five-hour scheduler margin), an expanded Chapter 10 case study, a
question-by-question impact report, explicit parent/child proposals and a split importer that preserves separate
individuals and sequence membership. Queue 47 contains 850 blinded looks; no CNN completion is required before
review. Its selected labels cannot replace population-wide precision or prevalence. The old B1/B6/B12 cohorts
remain labelled as historical. The 127-parent boundary view contains unchecked separate selections; accepted
parents are not silently converted into new independent child judgements. No thesis PDF build or model training.

## 8 November evening: three completed queues and recovered cluster outputs

The author requested interpretation/integration of queues 38, 45 and 46 and wider context for cropped Library
members, then supplied the recovery folder and Slurm logs. Their subsequent WinSCP copy supplied the five missing
seed checkpoints. Chapters 6–10 now include the verified source-specific results, the completed 64-channel seed
comparison and the combined 2,718-span inventory. Figures were visually inspected; the thesis PDF was not rebuilt.
Full methods/limits: `data/reviews_completed_20261108/REPORT.md` and `data/recovery_return_20261108/REPORT.md`.
Historical cohorts, g-11 morphology assignments and classifier scores retain their original meanings. The new
inventory is source-linked accepted material, with boundary work and a subsequent morphology regrouping still
required; prominence proposals are not human redraws. A focused 127-item family boundary view was generated.
Recovery compute remaining: 183 CNN tasks only. The author requests folder paths for WinSCP, no collection commands.

## 8 November: accepted catalogue and MJu26a follow-up

The author paused 9.2 to reconcile all accepted material and explicitly requested splitting multi-event spans,
extending incomplete spans, including the spikes of both MJu26a trains, and treating both as Chapter 10 case-study
candidates. The new source-preserving inventory is Library g-12: **1,762 accepted-span representatives** across the
eight thesis recordings, grouped by recording rather than morphology. Its **175 train members** (143 long CH15,
32 CH14 excerpt) have explicit train-level acceptance and proposed machine boundaries, not new blind verdicts.
The boundary editor includes those spans plus 2,595 labelled windows/regions for extraction. A repeatable refresh
will add the remaining queue-38 judgements after completion; the saved cutoff has 164/916 presentations judged.
Do not freeze Chapter 9's counts, durations or remade statistics figure until the final review/boundary population
is settled. Keep the historical 716 blind accepted spans and g-11 results as their original cohorts.

Full method, source mapping, database backup/integrity checks, editor, scripts and Chapter 10 context:
`docs/thesis/data/accepted_catalogue/REPORT.md`. The explicit current-human-revision verdict fix is saved in main
and this worktree; the live site has restarted since the change. Both trains are noted in Chapter 10's purple
instructions. No classifier training or full thesis PDF build was performed.

Checked 7 November 2026 against the purple instructions in the chapter sources at the worktree's base revision, the current prose, the numbers ledger and the cited result files. Scope: Chapters 6, 7 and 8, including the author's chapter-end integration decisions and the explicitly approved Chapter 8 discussion. This records the author's request to integrate the notes into the writing, rather than using only each rough paragraph as the brief.

## Writing process going forward

Workflow updated by the author on 7 November 2026: present the context for one section, record the author's response, then immediately present the next section's context. Defer full prose review and TeX integration until the end of the chapter. At that point review the chapter's responses together, integrate them with the purple recommendations and verified evidence, and then move to the next chapter. Do not resume the earlier per-section rewrite-and-confirm loop unless the author asks.

Reinforced after section 8.1: keep the interval between sections short. Save the response and only brief initial notes; defer further source investigation and processing to chapter end. Chapter 8 responses are in `CHAPTER_08_RESPONSES.md`.

Each writing packet should explain the purpose of the section, its recommended paragraph or subsection structure, every relevant recommendation in its purple note, the necessary background in plain language, and the results to reference. Include denominators, controls, uncertainty and limitations with the numbers. During collection, note the response without rewriting it; record material factual issues for the chapter-end review. At integration, preserve the author's wording and cadence while filling gaps and state substantive factual corrections plainly.

Treat the purple notes as recommendations to check against the evidence and the author's later decisions. They contain some outdated numbers, overly strong interpretations and instructions that the author has superseded. Keep a source comment after finished prose; retain purple recommendations for sections still awaiting the writing loop. Update TeX without routinely rebuilding the thesis PDF. The handoff's commit/push directions are not user authorization.

## Chapter 6

| Area | Recommendation and disposition |
|---|---|
| Scope and methods | Five judged recordings; 13 voting families; 45 settings on M2_aug, comprising 41 candidate-producing settings and four non-voting 1-minute CNN controls. M4 was excluded from the historical Chapter 6 sweep and used for the original Chapter 8 exam; the author now explicitly permits M4 in the later seed-transfer experiment. SH, SO and full MJu26a have no blind candidate results in Chapter 6. Existing labels are held fixed, the new blind sample covers the remaining unjudged pool, and weighted estimates and bootstrap intervals combine the two. |
| Scale, candidate share, agreement | Retained the completed author prose and tables: 4.82 M detections, 3.10 M candidates; 1,959 blind reviews with 95 unsure; agreement ladder and AUC 0.874 on 133,556 candidates carrying an earlier label. The AUC reference is distinct from the blind acceptance sample. |
| Choosy and loose detectors | Added M2_aug CNN-10-minute, symbol-search and signal-threshold estimates. Rebuilt Table `tab:precision` from `data/ledger_checks.json` for all 13 families, showing M2_aug sampled counts and bootstrap intervals, plus the range across available recordings. Retained OASIS threshold 3 versus 5 and noise-threshold setting examples. |
| Correcting old precision guidance | The note's blanket “13–20 sampled events per detector” is outdated: M2_aug family sample counts range from 2 to 344. The weighted estimator uses stratified bootstrap intervals, so the instruction to substitute ordinary Wilson intervals was not followed. Wilson intervals remain appropriate for the simple acceptance proportions in Chapter 7. Wavelet's full recording range includes M2_concat's 31%; noise-threshold family ranges are distinguished from individual-setting ranges. |
| Matrix-profile scope | Qualified the zero-detection statement as the default threshold on two tested channels in each M2 recording. Other settings, including local cached-profile variants, appear in the broader comparisons and include the threshold-6 window-touch result. |
| One-draw surrogates | Added the broad ratio pattern and 849/1,880 task-record result. A footnote distinguishes the earlier 255/552 batch result and the extra historical 10 Hz MJu26a version; these are task counts, not a count of unique settings in the main five-recording analysis. |
| Twenty-draw follow-up | Added GADF CNN 16/16, recurrence CNN and drop v5 14/16; the 1/21 rank-test floor; approximate 0.8/16 chance expectation; Benjamini–Hochberg outcome and binomial tails; dependence between channels; and agreement of pooled one-draw and twenty-draw ratios within 4%. Limit the stability claim to these six variants on M2_aug with phase randomisation. |
| Surrogate interpretation | The notes' claim that a detector matching its surrogate “measures the spectrum, not events” is too categorical. The prose instead explains that surrogate response and human acceptance measure different properties. A high ratio alone does not establish event quality. |
| Misses and morphology | Retained 18/2,333 untouched interesting windows and 95.4% coverage of uninteresting windows; the selected-setting table and full 46-setting Appendix H; CNN training-label caveat; and the window-overlap versus event-precision distinction. Added lift near one for 1-minute CNNs, lift 0.53 for matrix-profile threshold 6 on two channels, and the reinspection list. No morphology miss analysis is possible from these labels; the 800 M2_aug blind items also lacked shape-class labels. |
| Reviewer reliability | Added six changed answers in 98 repeated windows (four positive-to-negative, two negative-to-positive). The 11.5% miss-per-review estimate and 4.6–23% interval come from a model assuming no false-positive interesting judgements and only six disagreements. They are not an independently measured error rate. |
| Discussion and literature | Added the limits from small/unequal samples, lack of exhaustive event reference, mostly one-draw surrogates, one reviewer, and precision against subjective labels. Explained the contribution of a common comparison across recordings and rates relative to detector-specific studies. Do not claim universal absence of such evaluation across all published literature, or unit invariance as an independently tested property. |
| Author's explicit cut | The band-and-symbol pilot remains removed. Do not reintroduce it to satisfy the older purple note. |

Main evidence: `data/ledger_checks.json`; `data/miss_rate/`; `data/ch06_20draw/per_variant.csv`; `../rq_roundA_2/findings/rq1b-candidate-events.md`, `detectors-vs-surrogates-2026-10-26.md`, `surrogates20-2026-10-29.md` and `miss-rate-2026-10-26.md`.

## Chapter 7

| Area | Recommendation and disposition |
|---|---|
| Motivation and algorithm | Kept the author's progression from similar shapes noticed manually to matrix-profile experiments and a standalone query search. A distance profile compares one query with every window; a matrix profile records each window's nearest neighbour. MASS profile complexity is O(n log n); the complete all-pairs profile is not O(n log n). Chapter 2 was corrected accordingly. |
| Query timing | New timing check: actual 105-s seed, one 721-h channel at 1 Hz, best 200 matches in 0.842 s after warm-up. Excludes loading and surrogate searches; not a historical runtime of the full experiment. Provenance: `data/seed_query_timing_20261107.json`. No new full matrix profile was computed. |
| Seeds, scope and computation | Four main seeds: 105, 816, 148 and 377 s. Short dip covered three channels; the others all 16. Up to 200 matches/channel, approximately half-length exclusion, 200 phase-randomised draws/channel, and cluster route above an estimated ten minutes. Identifiers refer to the search-time Library snapshot. Added the supplementary 327-s trough search (nine candidates, two channels, unjudged), outside the main evaluation. |
| Reviews and scoring | Included 428 earlier assessments and the full 249-item blind queue composition. Random controls match duration and channel proportions and avoid matches. Source and scores hidden; the waveform can still be recognised. Primary blind rates use every reviewed item; decided-only rates are a sensitivity check. |
| Exact surrogate counts | Re-read the four saved HPC results using the full-precision recommended thresholds. Short dip: 64 real, 2 surrogate matches in 200 draws (mean 0.010); long dip: 124, 7 (0.035); spike: 16, 0 (0.000); drop: 372, 1 (0.005). Surrogate draw counts are summed across the same searched channels. Earlier 0.01 and 0.04 means were rounded. See `data/seed_null_verified_20261107.json` and ledger B13. |
| Interpreting thresholds and caps | Thresholds were selected from the surrogate output, so tiny null counts partly follow from the rule. The useful result is the many real matches passing the same cut. None of the channels reaches 200 at the reported common cuts (maximum 111 for the drop). A cap can matter at looser cuts; do not claim it truncated these reported strict-cut counts. Only one recording, phase randomisation and native seed lengths were tested in the main comparison. |
| Known family recovery | Added the search-time catalogue check from `../rq_roundA_2/RQ2b-second-seed.md`: 60/65 CH2_A1 drop-family members retrieved, including 41/46 accepted members; six members elsewhere not retrieved, spanning 182–1443 s. This is coverage of a known family subset, not global recall. |
| Human acceptance | Split the mixed table into a surrogate-count table and a clear blind-acceptance table. Added each seed's matched control, Wilson intervals, Newcombe differences and Fisher tests, plus the pooled 15/80 controls and decided-only sensitivity. The earlier mixed-duration 235/1,084 random baseline is not the matched control for this experiment. |
| Sampling distinctions | Drop: 100 sampled eligible matches under the common cut. Spike: 29 eligible matches under channel-specific cuts after exclusions, not the 16 under the common cut. Dips: 20 previously accepted examples each; these do not estimate acceptance of unseen dip matches. Eleven spike items also had earlier positive verdicts. |
| Repeat review | All 51 earlier positives remained accepted (95% Wilson interval 93–100%). Forty were repeated dips and eleven spikes. This supports consistency of these positives for the same reviewer, not absence of unblinded bias, agreement among researchers or an objective event/noise boundary. Cohen's kappa is undefined because both assessments are all positive. |
| Figures | Corrected waveform-figure denominators to count unsure verdicts, matching the primary table. Removed the legacy bar-plot figure from the chapter: the spike bars both hit 200 and the exports do not document the reported common-cut comparison. Source images remain available. The waveform figure remains. |
| Channel distribution | At the author's request, added Results section 7.3.4 with all 16 channels against the four seeds, then a drop-query time raster and per-channel totals. The scale pilot moves to 7.3.5. These are search returns at the common cuts, not counts of accepted biological events. |
| Scale pilot | Integrated the response as an illustrative seven-return implementation walk, explicitly not human-validated. Added the longer-query mean 10.38, native mean 8.36 and short-query mean 16.68 at the loose cut 7, distinguished from the stringent main-search cuts. Included the historical F-130 example with the different-metric qualification. |
| Discussion | Integrated practical review prioritisation, the different meanings of the controls, single-reviewer consistency limits, query-dependent recurrence rates and future cross-recording/duration/reviewer tests. Moved empirical channel counts and the plot into Results. |
| Authorised new computation | Prepared a fixed 377-second drop-seed transfer bundle for seven recordings including M4, with 64 channels and 200 phase draws/channel. Uses native sample rates with seed resampling and distance-footing correction, preserves a frozen-cut primary comparison and separately reports target recalibration. No job is submitted by the assistant, no new judging queue is created and no unreturned result enters the thesis. |

Main evidence: `../rq_roundA/RQ2-exemplar-seeded-search.md`; `../rq_roundA_2/RQ2b-second-seed.md`; `../rq_roundA_2/findings/rq2-blind-2026-10-28.md`; the saved HPC result files; and wave-1 queue 35 exports.

## Chapter 8

| Area | Recommendation and disposition |
|---|---|
| Author's workflow | Saved the responses through 8.3.2. The author then asked for the remaining chapter in their prose, inspected the full proposed discussion and approved continuing. Completed the chapter-end review and integration rather than continuing the per-section collection loop. |
| Aims and labels | Preserved the author's three-source progression, but clarified that reviewed detector/seed candidates receive human binary labels rather than automatically forming named exemplar classes. Accepted and rejected examples are both needed; representative variation replaces the impossible requirement to include every possible case. |
| Model descriptions | Kept Aims brief and placed inputs in Methods. Corrected learned forest thresholds, distinguished GAF from recurrence, and described MiniRocket filter-response features plus ridge weights. Saved run79 results show 100 trees and 24 retained features; run1613 shows 300 trees, 26 features and 24,843 training windows. Current defaults do not replace these historical settings. |
| Training exclusions | Described model-specific artefact and duplicate handling. R4 excludes carried copies, duplicates/conflicts, unsure, artefacts and unreadable spans; seed is positive in its training data. Avoided claiming identical filters for every historical model. |
| Evaluation sequence | Explained later blocks, unseen channels, blind window judgements, recording-group folds and the frozen M4 examination. A blind judgement is not sufficient to make the underlying signal unseen. Labelled windows train R4 but only held-out events contribute to its reported event metrics. |
| Controls | Distinguished 200 initial forest training-label shuffles with refits, 1,000 fixed-prediction blind-label permutations, and 200 R4 ridge refits. The computational R4 null is unweighted, with a matched unweighted real-label comparator, while the principal model is class-balanced. Explained pooled null AUC 0.420 through cross-fold score intercepts and class proportions. |
| Forest results | Added the same-window table (429 total, 328 with no earlier label, 129 M2_concat). Precision and recall explain opposite errors. The first cluster mapping rejects 979/1,271 human-interesting training windows before learning. The later pipelines also differ in training population, trees and retained features; do not interpret this as an isolated label-source experiment. |
| CNN results | Corrected the table's 0.78–0.83 balanced accuracy population to 429 pooled blind ten-minute windows. Included recurrence entries and explicit sample sizes. Kept random 80:20 overlapping-window accuracy distinct from blind-window plain accuracy. Explained majority baseline, M2_aug exposure, incomplete checkpoint provenance, sparse M2_concat positives, threshold inspection, failed one-minute inputs and the absence of a direct one-hour labelled test. |
| R4 and simpler baselines | Included pooled/per-recording results, 1,689 sampled-candidate AUC near 0.97 versus detector agreement 0.86 and scalar-only 0.90, within-family AUC 0.88–0.99, and whole-channel-record bootstrap intervals. The 0.84 scalar baseline belongs to a different event-only comparison. Within-family results do not by themselves prove that shape is the only learned property. |
| Matched-data CNN comparison | Included AUC 0.970–0.973 versus R4 0.971 with paired differences including zero, one seed and no tuning. This qualifies the reference-CNN gap; architecture alone cannot explain it. R4 requires no GPU but no hardware-matched cost benchmark was performed. Retrained CNNs were not part of the original M4 exam. |
| Recording dependence | Both model families inherit the MJu26a five-channel/excerpt overlap. Omitted the excerpt's 12-event fold as a separate row, stated that the pooled 2,456 includes it, and reported the 12 overlapping training events when the five-channel group was held out. The 200-shuffle p-value floor applies to the five main groups, not the excerpt. |
| Original M4 exam | Kept the frozen model, scorer and labels unchanged. Read back its exact mapping: 290 reviews, 14 unsure, seven unmapped seed verdicts, 12 unreadable spans, leaving 257 classifier cases. Five artefacts are negative under the exam mapping. The 276 answered items remain the acceptance-estimation population with seed accepted. Corrected the table, figure cohort and appendix to TP52/FP6/FN7/TN192. |
| M4 interpretation | Reported both unweighted BA 0.93/AUC 0.98 and weighted BA 0.77/AUC 0.96, agreement baseline and reference CNN gap. Added M4-specific acceptance, agreement and family estimates without inserting them retrospectively into the five-recording Chapter 6 study. Restated prior researcher exposure, frozen training exclusion and the score-neutral voltage metadata correction. |
| Figures | Replaced the older model diagram with a native vector diagram retaining the waveform-over-three-model layout, with production GAF/recurrence/fusion encodings and explicitly schematic waveform, response and feature bars. Regenerated and inspected R4 examples under the original binary mapping. The M4 before/after signal figure remains linked to its exact blind examples. |
| Approved discussion | Inserted the approved seven paragraphs, preserving wording apart from TeX formatting. Single-reviewer self-agreement is uncertainty in the reference, not a numerical ceiling on a different metric. Candidate scoring is not continuous-scan recall; named classes need verified families and background examples. |
| Verification | Compared tables to saved forest and M4 JSON and paired-window data; checked TeX structure, references, citations and figure paths. Saved compact provenance and verified counts in data/ch08_verification.json. No models were trained, historical metrics recomputed or full thesis PDF rebuilt. |

Main evidence: the saved run79/run1613 results; W4-A-evaluation.md; rq1b-minirocket-2026-10-20.md; rq1b-minirocket-null-2026-10-26.md; rq1-v2-blind-2026-10-26.md; rq1b-fair-cnn-2026-10-29.md and JSON; the frozen M4 manifest/results; the wave-1 exam-item export. Author responses and integration decisions are in CHAPTER_08_RESPONSES.md.

## Context for the next chapter

Update, 8 November: the author replaced 8.4 and supplied 9.1. The replacement discussion is integrated; the 9.1 response and factual/scope notes are saved for Chapter 9's later chapter-end review. The writing loop is temporarily held before 9.2 at the author's request while HPC returns and recovery are handled.

The drop transfer has 59/64 completed surrogate comparisons and all 64 completed real searches. Chapter 7 now includes complete results for six target recordings plus an explicitly partial 11-channel MJu26a comparison. A new blind transfer review was authorised by the author's offer to review about 1,000 candidates today: queue 38 has 916 presentations after prior-review exclusion and Review overlap grouping, with 46 later repeats reserved outside the app. M4's previously authorised release was applied through the audited Settings route after a database backup. The original frozen M4 classifier examination remains historical and unchanged.

The 2 Hz sweep audit found 729/1,014 completed tasks, 258 missing and 27 refused. There are 79 whole settings, with 48 newly complete settings available beyond the earlier imported subset. Chapter 10 includes selected complete-coverage real/surrogate counts and retains the earlier B5 timing analysis's original scope. No full B11 agreement result or new candidate census is inferred from a partial return.

Recovery launcher correction, 8 November: the first sbatch was rejected because the initial scripts requested explicit 16G memory, contrary to the existing CPU-profile documentation. Launcher revision 2 omits explicit memory, reuses Working.hpc.job_export._profile, reserves eight CPUs for the three-worker CPU pack, and restores the established CUDA module setup. It also repairs a malformed chain-index expression missed by syntax-only checks. Thirty-three executed shell-control-flow cases now cover resubmission, completion, chain caps, worker errors, scheduler errors and submission preflight. All resource requests are checked with sbatch --test-only before the first real submission. A seven-file, 4.7 KB launcher/documentation patch leaves scientific specifications, checkpoints, runtime and inputs untouched; the full archive is refreshed as well. See data/hpc_return_20261108/slurm_fix_validation.json and slurm_fix_archive.json.

Recovery uses an isolated runtime snapshot and fresh detector output/scratch locations, unchanged scientific specs and checkpoints, unique atomic JSON temporaries, and hash-verified cleanup limited to 334 complete cache folders already present on the PC. Remaining work is five seed channels (420 draws), 29 CPU detector tasks, 250 CNN tasks and six matrix-profile tasks; the profiles retain five-hour A100 requests. The assistant does not submit jobs. See hpc/recovery_20261108/README.md and data/hpc_return_20261108/.

The Chapter 7 responses, factual questions, author corrections and chapter-end integration decisions are recorded in CHAPTER_07_RESPONSES.md; Chapter 8 is now integrated in full, including the author's 8 November replacement discussion. Chapter 9's 9.1 response is saved; 9.2 is held until the current HPC work is processed. Then continue presenting context one section at a time and defer full Chapter 9 review and integration until its final section.

The new cross-recording search is a follow-up to the original experiments. M4 need not stay reserved, by explicit author instruction, but the classifier exam reported in Chapter 8 was performed before this follow-up. Do not retroactively describe the seed-transfer run as training or tuning the classifier. The original cross-recording bundle is documented in hpc/rq2_drop_transfer_20261107/README.md and the return/recovery work in hpc/recovery_20261108/README.md. The author subsequently authorised reviewing the transfer candidates and finishing the outstanding 2 Hz jobs, including their six originally specified matrix profiles. New unrelated computation or further queues are not inferred from that scope.

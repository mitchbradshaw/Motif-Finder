# Thesis, research results and application handoff — 8 November 2026

This is the continuation record for the long thesis-writing chat, including the
Review → Explore boundary correction requested at its end. Start here, then read
`numbers_ledger.md`, `PROSE_CONTEXT_AUDIT.md` and the linked reports before changing
claims. `HANDOFF.md` describes the earlier 5–6 November work; some of its restrictions
have since been explicitly superseded by the author. Dates and counts below identify
snapshots, not promises that a running job or review queue has remained unchanged.

## Author's scope, writing preferences and decisions

The initial read-only repository review evolved, with explicit author instructions,
into thesis prose, figures, HPC continuation, human-review queues, accepted-catalogue
reconciliation and application fixes. The reference documents were
`Thesis structure and ideas.md` (original Google Drive project) and the downloaded
`HANDOFF.md`. Their historical instructions must be distinguished from the author's
subsequent requests in this chat.

- Keep the eleven-chapter structure established at the start of the thread: 1
  introduction/background, 2 time-series theory, 3 early experiments, 4 MycoWave,
  5 methods, 6 detectors, 7 exemplar search, 8 classifiers, 9 accepted events,
  10 signal analyses/remaining research questions, 11 discussion/conclusions.
- Use the author's direct, explanatory prose. Explain what was measured, its
  denominator and implication, without turning agreement with one reviewer into
  biological validation. Integrate the purple instructional prose as well as the
  author's draft. Do not silently remove unresolved recommendations.
- The writing loop now gathers consecutive section responses with initial notes,
  then integrates and reviews the whole chapter at its end. Supply detailed context,
  useful subsections, numerical evidence and images before the next section.
  `CHAPTER_07_RESPONSES.md`, `CHAPTER_08_RESPONSES.md` and
  `CHAPTER_09_RESPONSES.md` preserve responses and editorial decisions.
- Chapters 6–8 have been integrated. Chapter 9.1 was drafted; 9.2 was paused when
  the author questioned its 716-event population. Finish the catalogue/boundary
  work before freezing new population statistics. The old 716 remains a valid
  historical blind-detector cohort, not the complete current Library.
- Edit TeX without rebuilding the thesis PDF each time. The original two-sided
  book layout stays. Captions should be long enough to explain selection, units,
  shading, scale and limitations. Figures never address the reader as “you”.
- Drop the early band-and-symbol pilot from Chapter 6. Seed channel distribution
  belongs in Chapter 7 Results, not its Discussion.
- M4 is now available for later work. Preserve the chronology of the original
  frozen classifier exam: later labels cannot improve that earlier exam retroactively.
- Both MJu26a spike trains are wanted: the long CH15 selection around 206–283 h
  and CH14 (including its familiar four-hour excerpt). Distinct spikes are separate
  events; a parent span containing several is an observation/sequence, not one spike.
- Eight thesis recording groups: M2_aug, M2_concat, M4, LM, CO, MJu26a, SH, SO.
  The first three are oyster; CO and SO are chocolate/snow oyster strains of
  *P. ostreatus*. LM/MJu26a are *H. erinaceus*; SH is *L. edodes*.
  F2A/reishi remains early work. Excluded external recordings are not reintroduced
  into thesis populations merely because their labels still exist in the DB.
- No new matrix-profile computation on this laptop. Use existing results.
  For returned HPC data the author prefers folder paths to copy in WinSCP,
  rather than collection commands. Keep raw arrays, models, DBs and private
  blind-review keys out of this public repository.

## Chapters 6–8: prose and interpretation completed

### Chapter 6 — detector candidates

Expanded aims/methods/results/discussion around candidate prioritisation, detector
agreement and phase-randomised references. Distinguish base algorithms, parameter
settings, machine detections and overlap-grouped candidates; do not describe their
counts as interchangeable. A detector firing on scrambled data is not automatically
useless: its reference rate and accepted yield matter. Increasing a threshold changes
selectivity; it does not itself prove statistical or biological significance.

Added a compact per-setting manual-window overlap table and the full comparison in
`appendices/H_detector_overlap.tex`. For M2_aug, 34 non-CNN settings touched all but
18 of 2,333 interesting ten-minute windows, but also touched 95.4% of 8,773
uninteresting windows; 128 artefact windows were excluded. “Any overlap” is window
coverage, not event precision. Example contrasts: OASIS threshold 3 touches
90.6%/65.6% of interesting/uninteresting windows; threshold 5 touches 48.7%/11.2%.
The blind-review agreement trend supports prioritisation, with one reviewer and a
deliberately sampled queue, rather than a universal event/noise boundary.

### Chapter 7 — exemplar search

Explained motivation and the distance-profile calculation separately from computing
an entire matrix profile. A later query-only timing was measured and recorded in
`data/seed_query_timing_20261107.json`; it is not the historical runtime of the full
real-plus-surrogate experiment. Search/surrogate counts were re-read from saved
results (`data/seed_null_verified_20261107.json`), correcting rounded values and cap
claims. Native seed durations are 105, 816, 148 and 377 s.

At common thresholds the short dip/long dip/spike/drop return 64/124/16/372 matches;
the short dip searched only three channels. The drop has one surrogate match in
total across 200 draws per channel: 0.005 matches per draw summed over 16 channels,
not a 0.01 per-channel biological false-positive probability. No channel reaches
the 200-return cap at these common thresholds. The channel table and drop time
raster show 111 matches on CH2_A1, 66 on CH4_A2 and 54 on CH1_A1.

The earlier blind panel retains its own source-specific results, including 100/100
accepted drop looks versus 9/40 random windows and 51/51 previously positive repeat
looks retaining acceptance. These are within-reviewer consistency, not independent
reviewer agreement. The duration pilot remains a small implementation illustration:
seven returns/placeholder labels, not a completed scale-generalisation experiment.
Its larger surrogate means are from a different threshold/pilot, not a contradiction
of the strict common seed thresholds. See Chapter 7 response notes for exact scope.

The completed cross-recording transfer is a new result, described below and inserted
in Chapter 7; relevant classifier/catalogue implications also appear in Chapters 8–10.

### Chapter 8 — labels and classifiers

Completed model inputs, controls/scoring, results and discussion, reducing duplicated
theory and explaining statistical features, image encodings and MiniRocket accurately.
`fig_model_inputs.py` illustrates a waveform, GASF/GADF/recurrence/fused images and
the three model routes. Training labels are human windows, adjudicated cluster
labels and reviewed machine proposals; these are different label-generating processes.

The manual random forest's unseen-channel macro F1 is 0.793 versus 0.635 for the
cluster-labelled version. 979/1,271 interesting training windows (77%) landed in
clusters mapped to not interesting. This exposes disagreement in the target labels,
not simply an architecture failure. Expanded precision/recall trade-offs and the
later seven-shape-cluster experiment without conflating protocols.

Earlier CNN image encodings scored 91–92% on an 80:20 random split with potential
shared signal content. Later independent tests are the more conservative evidence.
MiniRocket R4 gives pooled AUC 0.971 and balanced accuracy 0.919 on held-out recording
groups; the frozen blind M4 exam gives approximately 0.98/0.93. The queue's selected
composition differs from weighted population estimates (about 0.96 AUC/0.77 balanced
accuracy): predictions are scored against withheld human labels, not all subsequently
reviewed afresh. Matched-training CNNs attain pooled AUC 0.970–0.973, so the earlier
CNN/R4 gap cannot be attributed to architecture alone. R4 remains practical on CPU
and was frozen before M4 labels. Current models predict interesting/not interesting,
not named waveform families. There is no justified universal “500 examples per family”
minimum; use representative variation and held-out learning curves.

## New completed reviews and what they change

Full source-specific audit: `data/reviews_completed_20261108/REPORT.md` and
`scripts/thesis/reviews_completed_20261108.py`.

| Review | Frozen/served scope | Outcome and implication |
|---|---|---|
| 38: cross-recording drop transfer | 916 frozen presentations: 457 matches, 459 matched-duration controls; 918 underlying detections | 455/457 matches accepted (99.6%, Wilson 98.4–99.9%) versus 79/459 controls (17.2%, 14.0–20.9%). Strong transfer for this exemplar and threshold, conditional on one reviewer and this selection. |
| 45: MJu26a CH14 long train | 600 distinct source targets; served queue later 559, all answered | 515 accepted, 43 not, one unsure in the served view; 534 positive own source observations link 509 reconciled parent components. These are not 509 certified individual spikes. |
| 46: formerly unjudged Library shapes | 322 M2_aug representatives: 219 assigned-family members plus 103 omitted shapes | 280 interesting, 24 not, 17 unsure, one artefact. These answers link 127 parent observations after overlap reconciliation; not 280 additional independent events. |

Queue 38's frozen manifest is the reporting denominator. A later saved annotation can
make the live queue show 915 rather than 916; do not silently change the experiment.
Its new 46 repeat checks have been assigned to queue 47 and are still pending.
M4 transfer labels occurred after the frozen classifier exam and do not alter it.

## Accepted catalogue: identity, boundaries and families

`accepted_catalogue.py` compiles actual human claims, excludes carried copies from
independent looks, separates fixed windows/regions from event spans, and canonicalises
physical recording copies before overlap reconciliation. `publish_accepted_catalogue.py`
publishes source-linked representatives idempotently, with backup and original
provenance retained. It does not manufacture human verdicts for unreviewed proposals.

The g-12 snapshot after these reviews has **2,718 accepted span/observation
representatives**, grouped by recording, not a new morphology taxonomy:

| M2_aug | M2_concat | M4 | LM | CO | MJu26a | SH | SO |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,123 | 147 | 121 | 356 | 107 | 815 | 27 | 22 |

This supersedes the earlier incomplete 1,762 inventory. Another 55 wider-project
components remain outside thesis scope. Positive fixed windows (2,568) and accepted
regions (29) are extraction material; each is not automatically one individual event.
The earlier 175 train-level accepted members (143 CH15, 32 CH14 excerpt) have explicit
author acceptance with proposed machine boundaries, not 175 new blind judgements.

g-11's morphology assignments remain intact. Its current status audit resolves
1,014/1,097 representatives accepted, 55 not, six artefact, 17 unsure and five
unresolved. Of accepted members, 752 are assigned across 42 families (mean 17.9,
largest 60), with 262 omitted. These are distinct from frozen historical family
snapshots (519/41 or 817/42); do not overwrite an earlier analysis's denominator.

**Physical duplicate rules are essential.** MJu26a native 10 Hz, its 2 Hz block-mean
copy and L_LM represent the same recording. L_LM channels 0–4 map to physical CH10,
13–16 (one-based). The four-hour CH14 excerpt is another projection of that recording
(parent offset 15,777,590 native samples). Native units are V; L_LM is mV. The 2 Hz
means use five native samples (centre +0.2 s). Verified active-window correlations
are at least 0.9999817 for L_LM/native comparisons. Do not count the copies or the
excerpt as independent recordings, events or classifier folds.

### Individual events versus accepted parent observations

`reviewed_event_hierarchy.py` examines the 127 family-review parents: 78 have one
proposal, 35 contain proposed sequences and 14 remain unresolved. There are 229
distinct individual proposals, up to 15 in one parent. Peak identity, not overlapping
recovery tails, keeps individuals distinct. These are unchecked proposals, not new
independent positive human labels. The machine shoulder/recovery rule may still omit
a preceding rise or other full-shape context.

`accepted_boundary_review.py` plus `boundary_review.html` supplies wider context,
separate editable segments, explicit checked status and a validated JSON importer.
Shift-drag adds segments; dragging replaces a segment. Checked children become
individual `catalogue_boundary_review` annotations. A separate sequence stores their
ordered membership and onset intervals. Overlapping checked recoveries remain
separate individuals. Earlier broad observations remain provenance and cannot bridge
the children back together. No boundary export has yet been applied to the real DB.

The focused review file on this PC is
`DATA/derived/accepted_catalogue_review/family_context_review.html` (127 parents;
manifest `439066490847cfff3521`). Prefilled segments are unchecked. Do not infer
completion from suggestions or erase browser-saved human choices when regenerating.

## Chapter 10: dedicated CH14 case and effects on the research questions

The long CH14 selection spans 382.5–473.2 h (90.66 h), native recording 663, physical
CH14. Threshold detection followed a BEADS baseline, retaining the exact settings
and provenance in the report; it includes the older four-hour excerpt.

`data/event_hierarchy_20261108/REPORT.md`, `ch14_case.json` and individual-proposal
CSV document **530 supported extremum proposals** at a 1 mV floor, 0.5 s smoothing
and 3 s minimum separation. The 534 positive observations include 13 multi-proposal
observations and 19 unresolved ones. Depth median is 9.22 mV (5th–95th 2.47–14.65);
event-order thirds have medians 6.57/9.13/10.08 mV. Peak interval median is 602.9 s
(51.3–1,359); half-recovery median 2.49 s (0.83–17.44), one missing. Twenty-five
95% recoveries are censored at a subsequent detected onset.

LV 0.708 and CV2 0.785 fall below the homogeneous Poisson reference; 1,000-draw
two-sided p=0.001998 for both. The shuffle comparison is p=0.005994, but changes
to 0.885 at the 2 mV floor. Retain the 0.5/1/2 mV sensitivity table: this supports
local regularity in a selected train, not a proven oscillator or robust fine-order
effect. It is not a complete recording-wide census. Full-waveform boundaries and
additional reviewers remain limitations.

Chapter 10 now has a dedicated case section and an expanded-Library implications
section. Historical B1 full-census, B6 g-11 morphology and B12 716-span results retain
their original scope. B2/B3 need checked, ordered individual events. B4 still needs
paired-channel controls. More MJu26a coverage adds material, but B12 already included
its five-channel copy: it is not a new independent recording there. B5/B11 await the
complete CNN sweep. B10's CNN scales were corrected to 1/10/**60** min.

An optional B1 extension found missing exact SH/SO onset geometry: a successful cheap
task count is not enough to reconstruct intervals. `roundb_interval_extension_20261108.py`
leaves the old census unchanged and records `data/roundb_extension_20261108/missing_geometry.json`.
If the author wants it, copy these retained scratch folders to matching PC locations:

```
/home/Student/s4699158/CNN/docs/thesis/hpc/rq4_newsets_20261027/SH_fs2/drop_detection_v1_4ch_0-3456000_bff1bb_out/work/
/home/Student/s4699158/CNN/docs/thesis/hpc/rq4_newsets_20261027/SO_fs2/drop_detection_v1_4ch_0-3456000_233593_out/work/
```

## HPC state: CNN continuation is currently in progress

See `data/hpc_return_20261108/`, `data/recovery_return_20261108/REPORT.md`,
`hpc/recovery_20261108/README.md` and the generated continuation README.
Last verified PC return: **831/1,014 sweep tasks complete; 183 CNN applications
remaining** (MJu26a 587/674; SH and SO each 122/170). These apply existing reference
checkpoints; they are not classifier training or a rerun of the frozen M4 exam.
The author has continued the CNN jobs on the HPC. The exact current remote remainder
is unknown until new returns/logs arrive; do not say the work is finished.

All five recovered seed tasks, 29 CPU tasks and six matrix-profile tasks completed.
Seed coverage is now 64 channel searches × 200 draws = 12,800 channel-draws; all input,
runtime and model hashes were verified. There are 464 fixed-cut drop matches beyond
M2_aug. For MJu26a, 71 real versus nine surrogate matches/200 draws gives 0.045 per
draw summed over 16 channels, at fixed cut 2.2080859509008204. The 48 matches at the
separately recalibrated cut 2.0182372834533737 are exploratory and not the fixed-cut
transfer result. None reaches the 200-match cap.

Returned logs showed three one-minute fusion tasks repeatedly interrupted at the
20-minute budget (task indices 11/13/15), followed by the no-progress guard. CNN
inference cancels between batches but **does not persist within-step window scores**;
completed steps/run caches are reusable. An earlier README's checkpoint claim was
corrected. The incidental optional `ruptures` import warning was also present on
successful tasks and was not the cause. No new memory/quota/OOM cause was established.

At the author's request the continuation now has **10,800 s maximum pack budget
(three hours)** and 9,900 s per task, one concurrent CNN, a 2,400 s minimum launch
margin, with five-hour A100 scheduler wall time as extra margin. A process already
running retains the helper it loaded. The operational limits change no frozen
scientific spec, model or input. Earlier sbatch memory-specification rejection was
fixed by omitting explicit memory and using the partition default.

Generator: `scripts/thesis/build_cnn_resume_20261108.py`; worker:
`scripts/thesis/recovery_cnn_longwall.py`. Local upload artifact:
`DATA/derived/hpc/recovery_20261108_cnn_resume.tar.gz`, SHA256
`b26661b7b0624aed0449ae7c45d8f8a74e5785c6729c802fd8e359acd3809e95`.
Its expanded directory contains `cnn_longwall.py`, `.sh`, `pc_verified_returns.json`
and README. The current remote recovery folder is
`/home/Student/s4699158/CNN/DATA/derived/hpc/recovery_20261108/`.
`retry-stalled` archives only the three confirmed stale state files; caches/results
stay. Optional verified-cache release validates exact file sets and hashes; it was
not executed locally. The output guard remains 8 GiB. No jobs were submitted by the
assistant. Do not rerun completed seed/CPU/matrix-profile work.

For the next return the author should copy `rq4/` and `logs/` under that remote
recovery folder, plus `~/CNN/logs/rec1108_cnnL_*.out`/`.err` to the PC. Audit with the
existing recovery scripts before importing or changing B5/B11.

## Reviews still awaited: what X, Y and Z mean

**Queue 47**, `http://127.0.0.1:8765/#/review/queue/47`, has 850 presentations;
the final-turn read found **0 judged, 850 remaining**. It can be reviewed before
the remaining CNNs finish. `diversity_review_20261108.py` selects verified real
classical geometries and hides source identity/scores from the review view.

1. **Diversity/coverage:** 750 new proposals — SH 200, SO 200, MJu26a 150,
   M2_concat 75, CO 75, LM 25, M4 25. They target underrepresented recordings,
   channel/time coverage and waveform variation for future family comparisons and
   classifier labels. Prior human-reviewed spans, aliases and the known long CH14/
   CH15 selections on their physical channels were excluded.
2. **Background comparison:** 54 matched random-window controls. Score outcomes
   by source after completion. The proposal filters, recording allocation and mixed
   pipelines mean this queue cannot estimate whole-sweep precision or prevalence.
3. **Repeat consistency:** 46 prespecified repeats from queue 38, with frozen first
   answers stored privately. Exclude them from new-event counts and independent
   classifier evaluation. Assess within-reviewer repeatability after completion.

Separately the **127-parent boundary review** awaits checked full-shape extents and
splits before final individual-event duration/amplitude statistics. Queue 47 plus
that view is 977 presentations, but several parent items contain multiple events.
There is still only one reviewer. Private manifests/answer keys live under ignored
`DATA/derived/library_diversity_review_20261108/` and `DATA/derived/rq2_blind/`.
`--release-repeats` reuses the queue-47 assignment instead of creating a duplicate.

## Figures: where they come from and how to regenerate

Scientific figures use matplotlib, `scripts/thesis/figstyle.py` (consistent thesis
width, fonts, palette and recording colours), vector PDFs in `figures/new/` and PNG
previews. The latter are for visual inspection; the TeX uses PDFs. Native waveforms
require local data, so committed aggregates and provenance reports matter.

| Generator | Outputs/work in this thread | Inputs and interpretation |
|---|---|---|
| `figs_repo.py` | Updated `ch6_real_vs_surrogate`, `ch7_seeds`; added `ch7_drop_distribution` | Stored detector/seed returns, verified thresholds and per-channel drop matches; no new full matrix-profile computation. |
| `figs_bundle.py` | Updated `ch8_m4_before_after`, `ch8_r4_examples`, `ch10_b4_stack` and waveform galleries | Existing export bundle and signal excerpts; explicit human acceptance and recording colours. |
| `fig_model_inputs.py` | `ch8_model_inputs` | Waveform → GASF/GADF/recurrence/RGB fusion, plus feature/image/kernel classifier diagram. |
| `completed_review_figures.py` | `ch7_transfer_acceptance`, `ch9_combined_catalogue`, `ch9_context_examples`, `ch10_mju_ch14_reviewed_train` | Frozen transfer manifest with Wilson intervals; 2,718 parent-span inventory; wider raw context without claiming suggested boundaries are checked; 90.7 h envelope/raster with older excerpt marked. |
| `reviewed_event_hierarchy.py` | `ch9_event_sequence_hierarchy`, `ch10_ch14_separate_events`, `ch10_ch14_event_measures` | Unchecked separate event proposals, selected train measurements and interval/recovery distributions. Child colours denote identities, not waveform families. |

The earlier `HANDOFF.md` records the already committed Chapter 1–5 and Round B
signal-figure work (dataset gallery, event/train anatomy, six detectors on one signal,
matrix-profile example, drop-family overlays, B1 null examples, B6/B12 shapes).
This session retained that work and revised the later prose/figures described above.
New figures were visually inspected. The overlapping Chapter 9 statistics figure
should be rebuilt after the final individual-event population is settled; do not
redraw it with a larger count while retaining the old 716-event statistics.

## Application changes and final boundary-save fix

Earlier in the thread, Review was slow after a verdict because small queues repeatedly
read all adjudications/tags. `Working/review/queues.py` now scopes reads to wanted IDs,
with bounded chunks and a single filtered scan for very large sets. The controlled
save median fell from 0.1847 to 0.0351 s (5.26×); live counts/details improved too.
No persistent verdict cache or schema was introduced for this speed work. Client
prefetch stays bounded (five ahead, 12-entry LRU), and geometry invalidation stays
explicit. `--no-warmup` skips expensive optional startup warmups while analyses
remain available on demand. The server was restarted hidden on port 8765. Chrome
and ChatGPT were substantial RAM consumers; no training job was identified on the PC.

`Working/library/verdicts.py` now honours the annotation explicitly linked to a
member's current human revision instead of overriding it with an older machine-span
judgement. This explains why accepted/unjudged family counts changed after review.

The final requested fix addresses **Review → Edit span in Explore → Save → Review**:

- Saving a corrected extent explicitly accepts it as **interesting**, including an
  event previously rejected. The machine detection remains immutable.
- The additive `review_span_edits` table links a detection identity to its current
  human annotation. Repeated edits supersede the previous live annotation; history
  is retained, not counted as another overlapping event. Library members retain
  their existing revision identity and history.
- Detection queue rows/details/traces resolve the current extent, including overlap
  sets, after reload or server restart. An event's own redraw does not remove it as
  a supposedly new rediscovery. Reopening Explore also reads that current extent.
- Saving clears prefetched Review geometry and stale session verdict overrides,
  then refreshes rows/counts before returning. Library family verdict changes reuse
  the current human revision's annotation, so later rejection does not revert bounds.
- Catalogue refresh uses the current extent, not an original padded union; distinct
  redraws retain separate identities if their recoveries overlap. Historical plain
  annotations made before explicit detection links cannot be retroactively assigned
  to detections by guessing from overlap alone.

The actual research DB remains at `DATA/db/annotations.sqlite` in the main checkout.
Never replace it with an old review snapshot: the author may have added answers.
Use SQLite backup API before publication/migration. Do browser writes on a synthetic
sandbox, never by inventing verdicts in the project DB.

## Verification and next-agent order

Final span/API regressions, Review/explore/startup tests passed (74 tests), including
same-identity repeated shrink edits, automatic acceptance, current Review shape,
family re-review and single-entry catalogue refresh. TypeScript and the production
Vite build passed using the main checkout's existing node_modules. The thesis
worktree has no node_modules; do not fetch/install a substitute compiler with npx.
Additional final validation is recorded in `data/span_edit_20261108/REPORT.md`.

Earlier validations: catalogue/hierarchy/CNN-worker focused tests (11); import/core
and API speed tests; synthetic browser save/advance/undo for queues 38/46; boundary
editor two-segment check with zero auto-completions; recovery shell syntax and
frozen hashes. The legacy full Review smoke was **not clean**: 12 stale queue/fixture
failures, no browser/server errors, with current-queue focused checks passing. Do
not relabel that old smoke as a clean full pass. No thesis PDF rebuild was requested.

Next: accept queue-47 verdicts and the checked boundary export, score controls and
repeats without exposing their keys early, reconcile canonical event identities,
refresh/publish the catalogue, then finish Chapter 9 statistics and morphology work.
Audit the next CNN returns before updating B5/B11 or complete-sweep claims. Preserve
the older frozen cohorts, distinguish individual events from reviewed observations,
and continue the author's section-context writing loop from the settled Chapter 9
population. No automatic new model training is implied by receiving more labels.

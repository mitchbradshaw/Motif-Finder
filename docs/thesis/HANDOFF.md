# Thesis handoff: where the 5–6 Nov session left off

> **Continuation:** read [SESSION_HANDOFF_20261108.md](SESSION_HANDOFF_20261108.md)
> first for the subsequent prose, results, catalogue, figures, HPC continuation,
> pending reviews and application fixes. Later author instructions supersede this
> historical file's g-11-only/no-new-queues/M4 restrictions.

Written 6 Nov 2026 for the next agent. The thesis (METR4911, "MycoWave") is due **Mon 9 Nov 2026, 3 pm**. Branch:
`claude/hopeful-knuth-kh8u38` (pushed; working tree clean at `79cfdc6`). Read this file, then `README.md`,
`COMPLETION_CHECKLIST.md` (5 Nov, partly superseded by the decisions below) and `numbers_ledger.md` in this folder.

---

## 1. What the author asked for

Source: the author's brief `Thesis_structure_and_ideas.md` (uploaded to the session, not in the repo). Three asks:

1. **A new story/structure**: the year's arc from ~1,000 h of raw recordings → early experiments (hand labels, CNNs,
   SAX, matrix profile, window matrix, drop motifs) → MycoWave as the natural result → the research questions.
2. **Many more intuitive figures that show the signal itself**, not only distributions: example trains with intervals,
   event anatomy, dataset excerpts, website screenshots per RQ, the held-out M4 before/after detection, a signal
   figure per round-B study. The author's attached style references were: a seeded cross-channel search, a
   dendrogram with thumbnails, a catalogue-family trough overlay, species rose plots, an interval strip.
3. **A writing loop** to finish the prose (section 5 below).

## 2. Decisions settled in three grilling rounds (do not re-ask)

**Structure (11 chapters, implemented):**
1. Introduction and background (old Ch1 + the fungal half of old Ch2 + "Prior research at UQ").
2. Time-series analysis: background and theory (old Ch2's time-series half merged with old Ch3 theory; entropy cut to
   one paragraph; matrix profiling trimmed; excitable-models section cut).
3. Early experimental work (new; gathers the scattered early work, ends with the lessons table `tab:lessons`).
4. MycoWave ("Motivation" became "From experiments to MycoWave" with a lineage figure; new "Detectors as templates"
   section; poster workflow panels cut).
5. Methodology. 6–8. RQ1–RQ3. 9. An overview of the events (+ "Events no one has judged", the pool).
10. Analysing the signals (round B; "Round B" dropped from reader-visible text, B-numbers kept).
11. General discussion and conclusions (the plan mapping table `tab:rqmap` moved here into the critical review).

**Other decisions:**
- Deadline unchanged. Cut order if time runs short: (1) the unreviewed-pool analysis → a count and a paragraph,
  (2) signal plots for the weaker round-B studies (B2, B3, B10, B11), (3) extra screenshots, (4) Ch3 depth. Never cut
  the prose of Ch6–10.
- **Layout: the original two-sided book layout** (`\documentclass[12pt,openany,a4paper]{book}`, `\cleardoublepage`).
  A one-sided/tight-title change was tried and **reverted at the author's request** (it saved only 2 pages).
- **Summer project** framing: separate prior work. "In summer the SAX idea was explored; this year the SAX algorithms
  were implemented." No summer result is a thesis result.
- **CNN honesty**: report the 91–92 % training accuracy, explain the overlapping-window leak (random **80:20** split,
  not 9:1), give the blind re-test (balanced accuracy 0.78–0.83, AUC 0.93–0.96 at 10 min) as the honest number.
- **Datasets kept**: M2_aug, M2_concat, M4 (exam), LM, CO, MJu26a, SH, SO; reishi F2A only in Ch3.
  **Removed**: Dwij, all Adamatzky recordings (*S. commune* incl. its unjudged exam → one future-work line),
  *C. militaris*, enoki, M1/M100/M101, F2B, L_R. B7 and B8 → future-work lines. Modelling (FHN etc.) cut.
- **One name for the jar recording: MJu26a.** L_LM is written "MJu26a (CH10, 13–16)"; rec 385 is "the MJu26a CH14
  excerpt (4 h)". Never both names.
- **Species**: M2_aug, M2_concat, M4 = oyster (*P. ostreatus*); CO = chocolate oyster and SO = snow oyster, both
  strains of *P. ostreatus*; SH = Asian shiitake (*L. edodes*); LM, MJu26a = lion's mane (*H. erinaceus*); F2A = reishi
  (*G. lingzhi*), petri dish. All recorded in the lab's Faraday cage; M2/M4 in grow packs, MJu26a in a jar. Electrode
  type and A1/A2 are "not recorded". Species claims at Latin level, common names are strains.
- g-11 is the final Library grouping (g-12 cut). The 2 Hz sweep's round 2 (MJu26a/SH/SO) is running on the cluster;
  when it returns: import, update B1, B4, B5, B11, and build pool tables for those sets. **No new judging queues.**
- RQ1 judged results stay on five recordings (SH/SO/full MJu26a only via surrogate ratios and Ch10 B5/B11).
- **Figures and captions never say "you"/"your"** (author's instruction, 6 Nov): write "the human verdict",
  "the blind verdict", "the researcher".
- **No new matrix-profile computation** (needs the cluster). Use `Results/Detection/matrix_profile/_legacy/*.npz` or
  the author's existing plots.
- The repo is **public**: raw data bundles come as chat attachments, never pushed to a branch.

## 3. Environment notes (this cloud container)

- No database or recordings here (`DATA/` holds only `library_seed/`). Signal data arrive as the wave-1 bundle (§6).
- TeX was installed with apt (CTAN/yihui are blocked; Ubuntu mirrors work):
  `apt-get install -y --no-install-recommends latexmk texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended texlive-pictures texlive-science texlive-publishers texlive-bibtex-extra lmodern poppler-utils`
- Python: `pip install matplotlib numpy scipy pandas pyarrow stumpy pytest` (stumpy is needed only because
  `b12_shapes_intervals.bh` imports `Working.discovery.seeded_search`).
- Build from `docs/thesis`: `latexmk -interaction=nonstopmode main.tex` (with notes → `build/main.pdf`, 167 pp) and
  `latexmk -interaction=nonstopmode -jobname=main-clean -usepretex='\def\hideinstructions{}' main.tex`
  (without notes → `build/main-clean.pdf`, 125 pp). Check `grep -ciE "warning.*(undefined|reference)" build/main.log`
  is 0 after every change (it was 0 at handoff).
- Commit messages start with `thesis:`; end with the session's attribution trailers; push with
  `git push -u origin claude/hopeful-knuth-kh8u38`. Never push to another branch.

## 4. What was done (commits `577c07a` … `79cfdc6`)

| Area | Done |
|---|---|
| Restructure | 11-chapter map; `chapters/03_theory.tex` deleted, `03_early_work.tex` new; `main.tex` inputs updated. Script used: `scratchpad/restructure.py` (one-off, not in repo) |
| Datasets/species | Sweep of every `.tex` by a sub-agent per §2 rules; corpus table `tab:corpus` rewritten (9 recordings, "Grown in" column); ledger A9, A19 updated |
| B6/B12 re-run | `scripts/thesis/species_rerun_b6_b12.py` (no DB; reads the 3 Nov CSVs). Results in Ch10 and ledger J7b, J9b; findings `docs/rq_roundA_2/findings/b6-b12-species-rerun-2026-11-05.md`. B6: 28/42 families on both species, lean by species no larger than by recording. B12: species 1/15 features (drop share, carried by LM) vs 7/15 between recordings of one species |
| Ch6 prose | §6.1 Aims, §6.2 Methods, §6.3.1–6.3.3 written in the author's voice (packets 1–2 confirmed). Table 6.1 rebuilt per recording (4.82 M detections → 3.10 M candidates). `tab:detnull` filled from `data/detectors_vs_surrogates/family_recording_pivot.csv` |
| Ch7 | Seed-null caption corrected; note flags the spike panel's 200/200 (probably a cap; drop it if so) |
| Ch9 | Pool section note carries the wave-1 pool numbers (1,720,104 → 64,114 merged at ≥5 families; 230,817 → 10,620 at ≥9; R4 calls 24–66 % of the top tier events; ~4,500 if R4 is right; 27 % of M2_aug pool events overlap a seed match) |
| PC tooling | `scripts/thesis/wave1/` export (+ `tests/test_thesis_wave1.py`, 27 pass), `docs/thesis/pc_waves/WAVE1_PROMPT.md`; `docs/thesis/pc_waves/wave3_shots.json` + `WAVE3_PROMPT.md` (23 site screenshots, not yet run) |
| Figures | 31 new vector figures in `figures/new/`, all placed with captions (§7) |

## 5. The writing loop (the author's method — follow it exactly)

Per section, in this order: **Ch6 → 7 → 8 → 9 → 10, then 4–5, then 3, then the gaps in 1–2, then 11 and the abstract.**
1. Send a packet: *what the section must say* (from its purple note), *background explained simply* (an everyday
   analogy first — CLAUDE.md's standing request), *the points their version must cover*, and any quick choices with
   a recommendation.
2. The author replies with their own version (often rough).
3. Return a **final version in their wording and cadence**, filling gaps; list "where your version was off" and teach.
4. On "confirm", write it into the `.tex` (replace the purple note with prose; leave a one-line note citing sources
   and "Written <date> (writing loop, packet N)"), build, commit, push.

**State at handoff:** packets 1 and 2 are in the thesis. **Packet 3 was sent and is awaiting the author's version**:
Ch6 §6.3.4 "Choosy and loose detectors" + §6.3.5 "Detectors against their surrogates", with choice (a): add 95 %
intervals to `tab:precision` (recommended yes; the per-family `ci` values are in
`data/ledger_checks.json → ladder.<table>.groups.family:<name>`). Packet 3's content is reconstructable from the notes
in those two subsections plus ledger D5–D8, F8. **Packet 4** = §6.3.6 "What detectors miss" (the miss rate; note
`sec:misses`), §6.3.7 the band-and-symbol pilot, and §6.4 Discussion — all still purple notes. Then Ch7 onward.

Facts settled for Ch6 that a packet must keep: 13 voting detector families (the 1-minute CNNs are a negative control
without a vote; CNN scales are 1, 10 and **60** min), 45 settings on M2_aug, 1,959 judged blind (800 queue 25 +
1,159 queue 28; 95 unsure), AUC 0.874 was computed on M2_aug's 133,556 candidates carrying an earlier label, OASIS
comes from **calcium imaging** (not ECG), the matrix-profile threshold made no detections on M2_aug/M2_concat (2
channels each) and fired 34–42/ch-h elsewhere at 0 % precision.

## 6. The wave-1 data bundle

- Made on the author's PC by `scripts/thesis/wave1/run_wave1.py` (read-only on the DB; 1.8 min), delivered as six
  zips (`wave1_part01..06.zip`) attached to chat. All 14 steps ok; see its `REPORT.md`.
- **It is not in the repo and the scratchpad is ephemeral.** Unpacked at
  `/tmp/claude-0/-home-user-Motif-Finder/e418602b-8a7a-51e5-8a3f-042fd4b94823/scratchpad/bundle` in this session. A new
  session must ask the author to re-attach the six zips (they are at
  `C:\Users\mmebr\Documents\CNN\DATA\derived\thesis_bundle\wave1\` on the PC) and unpack them into a fresh folder
  with path checks (`python3 -I`, reject members escaping the folder).
- Format (see `REPORT.md` → "Reading the files"): float32 mV `.npz` + `.json` sidecar (`t0_s`, `dt_s`, `fs`,
  `channel`, `channel_name`, …); stacks of windows as `values` + `offsets` with `<stem>_index.csv`; tables as CSV.
  Folders under `data/`: `meta, overviews (60-s means, all channels), full_channels (M2_concat CH0/2/13, rec 385,
  Fig2A), windows (gallery, b1_trains, b4_stack, agreement, cnn_scores, explicit), detections_in_windows
  (__detections/__candidates/__verdicts per window), drop_v1_all, queues (25, 28, 35, 36 windows + queue_items.csv),
  library_events (g-11 events + windows; rec385_members_g05.csv), hand_labels, misses, drop_motifs_store (motifs.csv +
  motifs.npz), existing_plots (Plots/Detection/mp, Plots/family_search, Plots/Classification/*), pool, m4_exam`.
- Known facts from the bundle: M2_aug "CH4_A2" is `channel` index **3**; drop v1 has **no** sweep detections in
  CH4_A2 377–381 h (the Analyse demo's 6 drops came from an edited chain); MJu26a_fs2 had no candidate table, so the
  pool used the five-channel copy; SH_fs2/SO_fs2 had no complete drop v1 run yet (2 Hz round 2 pending).

## 7. How figures are produced

**Style module** `scripts/thesis/figstyle.py`: `apply()` (9-pt text, 1.5-pt lines, light grid, no top/right spines,
vector PDF with `pdf.fonttype 42`), `figure(width, height, nrows, ncols)` (`"full"` = 6.3 in), `save(fig, stem)` →
`docs/thesis/figures/new/<stem>.pdf` + a `.png` preview (PNGs are git-ignored; only PDFs are committed).
Colours follow species/strain, never figure order (validated for colour-blind separation with the dataviz skill's
`validate_palette.js`): oyster `#2a78d6` (M2_concat shade `#164b8f`, M4 `#7fb0ea`), lion's mane `#eb6834` (MJu26a
`#b33f12`), reishi `#1baf7a`, chocolate oyster `#a4511c`, Asian shiitake `#6250d6`, snow oyster `#e87ba4`.
`fs.colour(rec)`, `fs.label(rec)` (maps any file/table name, e.g. `L_LM_Jul_26_J_raw_fs2_6e58f5b2` →
"MJu26a (CH10, 13–16)"), `fs.CATEGORICAL` (non-species series), `fs.NEUTRAL`, `fs.INK`, `fs.INK_2`, `fs.MUTED`.

**From repo data only** — `python scripts/thesis/figs_repo.py [names]`:

| Function | Output (`figures/new/`) | Label / chapter | Data |
|---|---|---|---|
| `ladder` | ch6_ladder | `fig:ladder` Ch6 | `data/ledger_checks.json` ladder |
| `cnn` | ch3_cnn_blind | `fig:earlycnn` Ch3 | `data/rq1_v2_blind/run1613_blind_score.json` (two exams pooled, n=429) |
| `catalogue` | ch9_catalogue | `fig:catalogue` Ch9 | `data/ch9_catalogue/events.csv` |
| `b12` | ch10_b12_shape | `fig:b12shape` Ch10 | `data/ch10_b12/events_shape.csv` |
| `b12wave` | ch10_b12_waveforms | `fig:b12waves` Ch10 | `data/ch10_b12/waveforms_64.npy` |
| `b1` | ch10_b1_lv | `fig:b1lv` Ch10 | `data/ch10_b1/b1_channels.csv` |
| `surr20` | ch6_surr20 | `fig:surr20` Ch6 | `data/ch06_20draw/per_channel.csv` (∞ ratios drawn as top triangles) |
| `b4` | ch10_b4_bins | `fig:b4bins` Ch10 | `data/ch10_b4/b4_bins.csv` |
| `detrates` | ch6_detrates | `fig:detectorheat` Ch6 | `data/detectors_vs_surrogates/by_family_recording.csv` + ledger family precisions |

**From the bundle** — `python scripts/thesis/figs_bundle.py --bundle <unzipped folder> [names]`
(reader: `scripts/thesis/bundle_io.py` → `Bundle.series`, `.stack`, `.csv`, `.ls`, `.time_h`; `Stack.window(i)`):

| Function | Output | Label / chapter | Notes |
|---|---|---|---|
| `threezooms` | ch1_three_zooms | `fig:threezooms` Ch1 | M2_aug CH12_C2 overview + gallery day + busiest 30 min |
| `mpintuition` | ch2_mp_intuition | `fig:mpintuition` Ch2 | legacy `1_mp_M2_concat_fs1_CH0.npz` (m=600) + full channel; closest pair ≥6 h apart |
| `surrogates` | ch2_surrogate_example | `fig:surrogateexample` Ch2 | AAFT and 30-min block shuffle drawn for the figure |
| `handlabels` | ch3_hand_labels | `fig:handlabels` Ch3 | 4 interesting / 4 not / 2 flagged |
| `cnntrace` | ch3_cnn_trace | `fig:cnnscoretrace` Ch3 | fusion3 10-min scores from the stored sweep run |
| `sax` | ch3_sax | `fig:sax` Ch3 | 3 h, rolling-median detrend, 3-min PAA, alphabet 4 |
| `dropfamily` | ch3_drop_family | `fig:droptrio` Ch3 | drop-motif store, catalogue 22 (24 base + 23 fine pass) |
| — | `early/search_cat04_crestedwave.pdf` | `fig:mpseed` Ch3 | the author's own PDF from `Plots/family_search`, copied as-is |
| — | `drop_motifs/S2_1_fall_angle.png` | `fig:dropangles` Ch3 | existing repo image (the rose plots) |
| `sixdetectors` | ch4_six_detectors | `fig:sixdetectors` Ch4 | agreement window, 69.2–73.2 h; Dehshibi row uses ε 0.02 (default found none) |
| `gallery` | ch5_gallery | `fig:gallery` Ch5 | 8 recordings, a day + busiest 30 min |
| `anatomyevent` | ch5_anatomy_event | `fig:anatomyevent` Ch5 | `Working.interrogation.event_shape.measure_events` on accepted EV-00361 |
| `anatomytrain` | ch5_anatomy_train | `fig:anatomytrain` Ch5 | M2_concat CH2, drop v1 default (14 onsets; CV 0.90, CV2 0.73, LV 0.55) |
| `agreement` | ch6_agreement_excerpt | `fig:agreementexcerpt` Ch6 | M2_aug index 8, 12 h; candidates ≤30 min by n_agree + blind verdicts |
| `realsurr` | ch6_real_vs_surrogate | `fig:realvssurr` Ch6 | real vs the sweep's own surrogate-run spans; panel (b) copy drawn for the figure |
| `seeds` | ch7_seeds | `fig:seeds` Ch7 | queue 35: drop30 100/100 vs random 9/38; spike37 28/28 vs 2/16 |
| `m4` | ch8_m4_before_after | `fig:m4beforeafter` Ch8 | M4 CH3_A2 155–203 h; R4-positive candidates ≤30 min after NMS (233); all 24 exam items agree |
| `r4_examples` | ch8_r4_examples | `fig:r4examples` Ch8 | 59 hits / 6 FA / 7 misses / 192 TN of 264 scorable |
| `accepted` | ch9_accepted_gallery | `fig:acceptedgallery` Ch9 | 6 random accepted events per recording, scale bars |
| `rec385` | ch9_rec385 | `fig:rec385` Ch9 | g-05 families on the CH14 excerpt (top three coloured) |
| `pool` | ch9_pool | `fig:pool` Ch9 | counts, cumulative swing/length vs accepted, R4 share by level |
| `b6species` | ch10_b6_species | `fig:b6species` Ch10 | families F-37, F-38 (≥4 members on each strain) |
| `b1train` | ch10_b1_train | `fig:b1train` Ch10 | recorded vs Poisson vs shuffled gaps, LV each |
| `b4stack` | ch10_b4_stack | `fig:b4stack` Ch10 | 16 channels, 35.6–41.6 h, the census's 7 co-occurrences |

Helpers in `figs_bundle.py`: `_nms` (greedy non-max suppression by score), `_thumb`, `_thumb_scaled` (real-scale
thumbnail with mV bar), `_window` (a `windows/` series), `_spans` (raster rows), `_busiest` (window with the widest
range), `_train_window` (the b1 window with most drop v1 onsets).

**Workflow for a figure:** write the function → run → `Read` the PNG preview and fix overlaps → insert into the
chapter (replace the `\figplaceholder` figure environment by locating its `\label{}` and swapping the whole
`figure` block, or add after an existing figure) with a stand-alone caption → build → check undefined refs → commit →
push. **Pitfalls met:** `ax.text` inside a `tight_layout` figure squeezes columns (use `subplots_adjust` instead);
`set_in_layout(False)` also drops the text from `bbox_inches="tight"`; when splicing code by string markers, the
marker `# --- Chapter 10 --` occurs twice in `figs_bundle.py` (a bad splice once duplicated the file — check
`grep -c "^def "` for duplicates); raw strings with `\\n` print a literal backslash-n.

## 8. What is still to do

**Waiting on the author**
- Packet 3 reply (§5), then packets 4 onward through all chapters.
- 2 Hz sweep round 2 return → write a wave-2 PC script/prompt: import the jobs (the PC's own tools:
  `scripts/rq4_overnight.py adopt`, see `docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/README.md`), rerun
  B1 (`scripts/thesis/b1_intervals.py`), B4 (`b4_cross_channel.py`), B5 (`b5_map_timing.py`), B11, build candidate
  tables (`scripts/rq1b_candidate_events.py build --real --file MJu26a_fs2.mat` etc.) and re-run the pool step
  (`run_wave1.py --only pool`). Then update Ch10 rows, `tab:rbsummary`, `tab:rqmap` (it still says MJu26a/SH/SO wait),
  the Ch9 pool note, and the ledger.
- Wave 3 screenshots (Sunday): the author runs `docs/thesis/pc_waves/WAVE3_PROMPT.md`. Two shots press "Run chain"
  (write one Analyse run each) and four switch the open Discovery recording — the author was told. Then fill the
  three remaining placeholders: `fig:lineage` (Fig 4.1, lineage grid), `fig:templatepages` (Fig 4.3), `fig:pages`
  (Fig 4.4); re-shoot existing `screens/*.jpg` users (`fig:reviewscreen`, `fig:atlasscreen`, `fig:analysescreen`).

**Can be done now (no author input)**
- T2 figures (cut order): B2 sequence strip, B3 gaps/recovery, B10 30-s motif vs AAFT, B11 compare (needs wave 3),
  Ch5 preprocessing before/after, Ch6 "what detectors miss" thumbnails (`misses/`; only 3 on swept channels),
  Ch9 one family in its source traces, Appendix C vocabulary thumbnails.
- Packets for later chapters can be pre-drafted from each section's purple note.
- Bibliography: 38 entries marked `% VERIFY` in `bib/thesis.bib`; cite source papers for every detector in Ch2 §2.6.
- Ledger rows still carrying old labels (A2, A6, A16–A17, D2, I2, J2, J7, J9, R4) — reword to the §2 names.
- Small text checks: Ch3 "lion's mane 844" is one channel (MJu26a CH14, region B); Ch11 environment future-work item
  kept deliberately; `tab:ledgerfix` "number of recordings" now 9.

**Final checks (COMPLETION_CHECKLIST §7)** before 3 pm Monday: notes off (`\showinstructionsfalse`, preamble line
~58), search the clean PDF for leftover "Write/Add/Fill/[/?", no undefined refs/citations, no `\src{}` outside
Appendix A, read-through, tag the submission commit for Appendix A, push.

## 9. Files to know

`docs/thesis/`: `chapters/01..11`, `appendices/A..G`, `frontmatter/`, `preamble.tex` (macros `\figplaceholder`,
`\src`, `\tool`, the `instructions` environment), `numbers_ledger.md`, `COMPLETION_CHECKLIST.md`, `TASKS.md`,
`data/` (analysis outputs), `figures/new/` (this session's figures), `figures/early/`, `pc_waves/`.
`scripts/thesis/`: `figstyle.py`, `figs_repo.py`, `figs_bundle.py`, `bundle_io.py`, `species_rerun_b6_b12.py`,
`wave1/`, plus the older per-study scripts (`b1_intervals.py`, `b12_shapes_intervals.py`, `catalogue_stats.py`, …).

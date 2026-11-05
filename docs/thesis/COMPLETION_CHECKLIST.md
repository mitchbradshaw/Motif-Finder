# Finishing the thesis: the checklist (5 Nov 2026)

Due **Mon 9 Nov, 3 pm**. This list assumes **no more results arrive**: the 2 Hz sweep, B7, B8, B11 and the
*S. commune* exam are written up as not run, unless they come back in time.

**In plain words:** almost every result is already in the document. Each one sits in a purple note with its numbers
and where they came from. What's left is mostly turning those notes into your own sentences. A few loose ends need a
decision from you, and then come the final checks before you submit.

**How the marks are split** (keep the effort roughly in proportion):
- approach and execution, 45 (Chapters 4–10);
- background, 20 (Chapter 2);
- conclusion, 15 (Chapter 11);
- definition, 10 (Chapter 1);
- writing, 10.

The guideline is 50–60 body pages at 1.5 spacing, and longer is allowed. The build without notes is 100 pages
today, front matter and appendices included.

**Which build to use:**
- **With notes:** `latexmk main.tex` in `docs/thesis` gives `build/main.pdf`.
- **Without notes:** `latexmk -jobname=main-clean -usepretex='\def\hideinstructions{}' main.tex` gives
  `build/main-clean.pdf`.

The detailed running list is `docs/thesis/TASKS.md`; this file is the finishing order.

---

## 1. Decide the loose ends first (each changes what you write)

- [ ] **The *S. commune* exam (queue 37, 263 items, partly judged).** Pick one; there is no other way to score it.
  - Finish judging it, then I score it once and fill Chapter 8, Chapter 10's last section and Appendix F.
  - Or report it as frozen but not scored: the exam was prepared (manifest, sha256 `e11ec64a…`), and judging it is
    future work.
- [ ] **The 2 Hz sets (MJu26a, SH, SO).** Only a partial cluster run returned. Unless the rest arrives, write them
      as registered but not swept. That has three knock-ons:
  - B11 is "not run";
  - B4 covers four recordings, not seven;
  - **g-11 stays the final grouping.** The g-12 rebuild is cut, so remove "rebuilt once as g-12" from Chapter 10's
    first note, B2's note and Chapter 9 (line 130).
- [ ] **B7 (multiscale entropy) and B8 (motif prevalence):** one line each in Chapter 10 saying they were not run,
      and add them to future work. B7 keeps its first read (Adamatzky's species, silhouette 0.43 against AAFT
      0.22–0.37) as a pilot, if you want it.
- [ ] **The environment section** (Chapter 10, `sec:rb_environment`): there are no usable logs, so cut it and say
      so in one line in Chapter 11's limitations.
- [ ] **Modelling** (parked 4 Nov), keep or cut. If you keep it:
  - Chapter 11 gets the "Modelling, only if of interest" paragraph;
  - Chapter 2 keeps `sec:litmodels` (half a page, with the FHN, Izhikevich and Wilshin citations);
  - Chapter 1 keeps its one-line scope note.

  If you cut it, delete all three notes and those citations. The parked material is in
  `docs/thesis/parked/ch10_b3_models.tex`.
- [ ] **Facts only you know** (Chapter 5's corpus table):
  - the species for SH, SO, Dwij A–D and reishi;
  - the rig, cage, substrate and electrode type for LM, CO, SH, SO and Dwij;
  - the reishi file's units;
  - what A1 and A2 mean on M2;
  - the number of distinct physical recordings.

  You can also write "not recorded" where you don't know.

## 2. Write the result chapters (Chapters 6–10): about 45 % of the mark

Each of these chapters is almost all notes today (50–90 words of prose each). Write Aims → Methods → Results →
Discussion from the notes; the numbers in them are checked and ledgered.

- [ ] **Chapter 6, RQ1 detectors** (9 notes).
  - **Headline:** the agreement ladder, 0–5 % real at 1–2 agreeing families against 40–63 % at 9 or more, on
    every recording.
  - **Also cover:** the 20-draw result; the M2_aug-only setting precisions; the miss rate; plan RQ4's sandbox run.
  - **Check:** the note asks for every count to be re-checked against the database before quoting.
- [ ] **Chapter 7, RQ2 seeds** (5 notes).
  - **Headline:** blind panel queue 35, every seed 97–100 % against 8–25 % for random windows of its length; all 51
    earlier yeses held.
  - **Also cover:** the scale pilot (plan RQ3) as a pilot.
- [ ] **Chapter 8, RQ3 classifiers** (10 notes).
  - **Headline:** R4 AUC 0.97 leave-one-recording-out and 0.98 / BA 0.93 on the M4 exam.
  - **Also cover:** the fair CNN matching R4 (so the gap was the labels); the honest note on cluster labels; the
    *S. commune* paragraph, depending on the decision in §1.
- [ ] **Chapter 9, the events** (8 notes): the catalogue numbers, which are the recomputed ones, not the poster's.
  - **Headline:** 91 % falls by the fastest-edge rule.
  - **Also cover:** the rec 385 spiking-families case study; the Library families (g-05); the drop-motif study with
    its claims ledger (Appendix E); sequences of drops.
- [ ] **Chapter 10, round B** (13 notes; the summary table `tab:rbsummary` is already final).
  - Write each study as half a page: question, why it matters, data, null, result, what it does not show.
  - The answered studies are B1 (final 5 Nov), B2, B3 (restitution only), B4, B5, B6, B9, B10 and B12.
  - **Cut** the "Study template" section; it is a note only.
  - **Keep or cut figures:** one per study is planned. B2 has no figure; it can go without one.
  - **Chapter conclusion:** the note at the end of `sec:rb_methods` says the choice of null decides the verdict. B9
    fails against AAFT, while B10 passes.

## 3. Write the framing chapters

- [ ] **Chapter 4, MycoWave** (12 notes, ~820 words; the engineering that the 45 % sees). In order:
  - requirements (½ p);
  - the import boundary and sandbox;
  - the study chains;
  - **rewrite the type-system section**, because the plan's claims don't hold (no sklearn fit/transform, no Param);
  - the five-word verdict vocabulary;
  - recipe hashes and the step cache;
  - the built-in controls;
  - the correction about persisted similarity edges;
  - the workflow through the pages (~1 p, with screenshots: see §5);
  - how it was built, after Pocock (~1.5 p);
  - evaluation (~1.5 p).
- [ ] **Chapter 5, methodology** (10 notes; the queue counts are filled in).
  - **Rewrite** the preprocessing (the plan's 18 Hz story is not what the software does).
  - **Write** the judging protocol (~1 p) and say which null each result chapter used.
  - **Add** the implemented agreement bins, the M4 exposure paragraph (what it was and was not), and the data-loss
    risk that happened (21 Sep).
  - **Re-export** the dark-theme figure in light, or label it historical.
- [ ] **Chapter 3, theory** (8 notes).
  - **Add** one sentence on uneven sampling (MJu26a).
  - **Settle** which entropy variants are kept, and which scale-invariant distance is used.
  - **State** the realisation counts: 1 draw per sweep task, and 20 draws for M2_aug.
  - **Write** the new MiniRocket section (½ p) and the statistics section (~1 p).
  - **Redraw or keep** the CNN example figure.
- [ ] **Chapter 2, background** (11 notes; 20 % of the mark).
  - **New sections:**
    - detectors borrowed from other fields (~1 p);
    - MiniRocket / ROCKET (½ p);
    - surrogates (½ p);
    - human labels as ground truth (½ p);
    - excitable models (only if kept, §1).
  - **Smaller additions:**
    - the corpus table's final row for this thesis;
    - qualify the sentence on public data;
    - add the matrix-profile cost sentence (40 h for M2_concat, 260 h for M4);
    - the fourth gap, if you use it in Chapter 1.
  - **Rewrite** "about 1,000 hours of *P. ostreatus*": M2_concat is lion's mane, and the oyster recordings are M2_aug
    721 h + M4 505 h.
  - **Check** the 38 references marked `% VERIFY` in `bib/thesis.bib`.
- [ ] **Chapter 1, introduction** (6 notes, ~1,400 words):
  - a paragraph on motivation in your words;
  - the paragraph explaining why the six plan RQs became three;
  - the fourth gap (optional);
  - the new Contributions section;
  - keep or cut the modelling scope note (§1).
- [ ] **Chapter 11, discussion and conclusions** (7 notes, no prose yet; 15 % of the mark). Write it last but one.
  - **Summary:** one paragraph per RQ, plus Chapter 9 and round B. The headline numbers are filled in its note.
  - **Discussion:** the cross-chapter links; useful techniques against dead ends.
  - **Critical review against the plan:** in your own voice, two or three paragraphs, with the plan table
    `tab:planreview`.
  - **Limitations:** add "no environment logs".
  - **Future work:** the round-B studies not run, the *S. commune* exam if not scored, and the 2 Hz sets.
  - **Conclusions:** half a page.

## 4. Front matter

- [ ] **Abstract.** Write it last. Its note has the headline numbers filled in (5 Nov). State what was found, not
      what was attempted.
- [ ] **AI statement.** Check every factual sentence: the Claude model families and dates, the DeepSeek end date,
      and the orchestrator facts. It also has three overfull lines to fix (lines 77–93).
- [ ] **Acknowledgements.** Name the technical and administrative staff and the data providers: the Adamatzky
      Zenodo data, the Dehshibi code, and the Wilshin et al. PRC release.
- [ ] **Title page, letter and declaration.** Check the name, student number, date and supervisor.

## 5. Figures and screenshots

- [ ] **Re-shoot the site screenshots on 8765**, because they now count as the final state. `scripts/thesis/site_shots.py`
      takes a JSON list of pages. Chapter 4's workflow section needs Explore → Analyse → Discovery → Review → Library.
      Never include *S. commune* until queue 37 is scored.
- [ ] **Check every figure is cited** in the text and has a caption that stands alone. Drop any you don't discuss.
- [ ] **Check the units and species names** match across figures: oyster, chocolate oyster and lion's mane.

## 6. Appendices (8–10 pages in total)

- [ ] **A, repository:** tag the submission commit and give its hash, plus the commands that rebuild every figure
      (`scripts/thesis/`).
- [ ] **B, blocks:** replace the hand list with the table from `scripts/manual_tables.py`, or keep the hand list.
- [ ] **C, vocabulary:** one line of morphology per tag, a typical duration, and a thumbnail. Fix its two overfull
      lines.
- [ ] **D, numbers ledger:** a headline table of the ~30 most-quoted numbers, from `numbers_ledger.md`.
- [ ] **E, claims ledger:** check only.
- [ ] **F, exam record:** M4 is complete. Add *S. commune* only if it is scored. Fix its four overfull lines.
- [ ] **G, decision log:** check against `docs/prompts/fixup/QUESTIONS.md`.

## 7. Final checks (Mon 9 Nov morning)

- [ ] Turn the notes off: set `\showinstructionsfalse` in `preamble.tex` (line 58) and rebuild.
- [ ] **No leftover notes:** search the PDF for "Write", "Add", "Fill", "[" and "?" left over from the notes.
- [ ] **A clean log:** no `??` references, no undefined citations, and only harmless overfull boxes (`build/main.log`).
- [ ] **Internal paths:** none of `\src{…}` should be in the prose, outside Appendix A.
- [ ] **Bibliography:** every entry is cited, and every `% VERIFY` is resolved.
- [ ] **Read it through once**, without notes, for page count and flow. Then spell-check.
- [ ] **Commit and push:** commit the final source and push to GitHub (nothing after `a668044` is pushed yet), then
      tag it for Appendix A.
- [ ] **Submit** the PDF before 3 pm.

---

## What's already done (no action needed)

- **Every completed queue is in the thesis:**
  - queues 25 and 28: the candidate events, R4's training data and the catalogue;
  - queue 35: Chapter 7;
  - queue 36: Chapter 8 and Appendix F.
- **Round B:** B1–B6, B9, B10 and B12 have results in Chapter 10 with their figures, and a summary table.
  - B1's final read across 45 channels was run on 5 Nov.
  - B3 keeps only its restitution test.
- **The 20-draw surrogates and the fair CNN** are in Chapters 6 and 8.
- **Every reported number** has a row in `numbers_ledger.md`, with its source and script.

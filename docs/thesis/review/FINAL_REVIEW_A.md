# Final review A: front matter and Chapters 1-5

Scope: abstract, AI statement, acknowledgements, declaration, names, Chapters 1-5. Line numbers are source lines in the .tex file. Ordered by importance within each category.

## 1. Methodological and logical errors

**A1. abstract.tex:3** "It applies the tool to eight recordings of four species from one laboratory."
Problem: the eight results recordings cover three species (oyster incl. CO/SO strains, lion's mane, shiitake); four species is true only of the nine-recording corpus that includes reishi F2A (Table 5.1, Ch11:14 says "eight recordings of three species").
Replace: `It applies the tool to eight recordings of three species from one laboratory.`

**A2. abstract.tex:5** "0--5\,\% of candidates are real where one or two families agree, and 40--63\,\% where nine or more do, on every recording, including one held out until the end (0 to 53\,\%)."
Problem: "real" claims ground truth where the measure is acceptance by one reviewer; "every recording" overstates (the ladder was run on the five swept recordings plus M4, not all eight); the bracket "(0 to 53 %)" has no stated referent.
Replace: `0--5\,\% of candidates are accepted where one or two families agree, and 40--63\,\% where nine or more do, on each of the five swept recordings; on a sixth recording, held out until the end, the same ladder runs from 0 to 53\,\%.`

**A3. abstract.tex:7** "Fungal recordings contain stereotyped, recurring waveforms that are shared across species and can be found, checked and counted reproducibly."
Problem: generalises from eight recordings, one laboratory and one reviewer to fungal recordings in general.
Replace: `These recordings contain stereotyped, recurring waveforms that are shared across species and can be found, checked and counted reproducibly.`

**A4. 01_introduction.tex:140** "no propagation between electrodes"
Problem: an absence of evidence is stated as evidence of absence; the abstract says "nothing was seen travelling", and Ch11:57 says "no propagation beyond chance on M2_aug" (with a shared-driver finding).
Replace: `no evidence of propagation between electrodes beyond chance`

**A5. 01_introduction.tex:140** "event timing close to random with a rate that drifts over days"
Problem: the abstract says activity "drifts over hours to days"; pick one.
Replace: `event timing close to random with a rate that drifts over hours to days`

**A6. 04_mycowave.tex:113 vs 05_methodology.tex:112** Ch4: "Cross-channel pairs are binned as artefact (...), propagation (...) or independent recurrence"; Ch5: "classified into four bins".
Problem: Ch4 lists three bins, Ch5 and Ch10:386 use four (artefact, propagation, shared driver, independent).
Replace (Ch4:113): `Cross-channel pairs are binned as artefact (lag within 1\,s and $|r|\ge0.98$), propagation (1--50\,s and $|r|\ge0.5$, within a pack), shared driver (across packs) or independent recurrence, and each bin must beat its own random-time null.` (check the pack condition against Ch10:385 before pasting)

**A7. 05_methodology.tex:135** "on two tested assertions. A recipe rerun gives the same output, and no machine-derived label enters the human label store"
Problem: Ch4:149 says the suite tests three things (identical output, no machine label in the human store, a surrogate never counted as a detection).
Replace: `and on three tested assertions: a recipe rerun gives the same output, no machine-derived label enters the human label store, and a surrogate's output is never counted as a detection (Section~\ref{sec:tooleval}).`

**A8. 05_methodology.tex:72** "Where a sample had to estimate how often candidates are real"
Problem: the panels estimate how often candidates are accepted by the reviewer, not how often they are real (precision vs acceptance).
Replace: `Where a sample had to estimate how often candidates are accepted`

**A9. 03_early_work.tex:14** "The labels, not the architecture, were the limit, and training data and splits must be recorded (Chapter~\ref{ch:rq3})."
Problem: the evidence given (leaky overlapping split, fixed 10-minute scale, forest similar to CNNs) supports "the labels and split were a larger limit than the architecture", not a categorical claim; the second clause is a non sequitur.
Replace: `The forest came close to the CNNs, which points to the labels and the leaky split, more than the architecture, as the limit; it also showed that training data and splits must be recorded (Chapter~\ref{ch:rq3}).`

**A10. 03_early_work.tex:9 vs :14** "a model that always answers ``not interesting'' is already about 80\,\% accurate" / "the majority-class baseline is already about 81\,\%"
Problem: two different baselines two paragraphs apart (8,773/11,234 = 78 %; the 711-window test set is 81 %).
Replace (line 14): `and the majority-class baseline is already about 80\,\%.`

**A11. 03_early_work.tex:61 and :85** "a sharp fall and a slower recovery are common to them all" / "one fall-and-recovery shape appeared in three species"
Problem: the supporting figure (Fig. scalecollapse caption) says the panels end after the trough "so recovery is not compared here", so the recovery part is not shown by that evidence.
Replace (line 85): `And one sharp-fall shape appeared in three species at very different time scales, though how it was recorded leaves a trace in its normalised shape.` Replace (line 61, clause): `the species do not share one waveform, but a sharp fall after a slower approach is common to them all`

**A12. 03_early_work.tex:61** "drops spanning 3.6 orders of magnitude ... share one relative shape ...; the species do not share one waveform"
Problem: "share one relative shape" and "do not share one waveform" read as a contradiction in one sentence.
Replace: `drops spanning 3.6 orders of magnitude in duration and 4.2 in amplitude collapse onto a similar relative fall (Figure~\ref{fig:scalecollapse}); the species do not share one exact waveform, but ...`

**A13. 04_mycowave.tex:89** "A region flagged by eye that no algorithm detected, stored in \texttt{annotations}, has equal standing with a rejected detection."
Problem: equal standing with a *rejected* detection makes a manual flag worthless; the intended sense is equal standing with a detection.
Replace: `A region flagged by eye that no algorithm detected, stored in \texttt{annotations}, has equal standing with a machine detection.`

**A14. 05_methodology.tex:105** "Section~\ref{sec:surrogates} introduced the two references every result is held against."
Problem: Section 2.4 introduces only surrogates; the blind base rate is not introduced there.
Replace: `Every result is held against one of two references.`

**A15. 05_methodology.tex:54** "Each recording keeps its native sampling rate ... The 10\,Hz recordings are analysed as 2\,Hz derivations"
Problem: contradicts itself within the paragraph; also interpolation does not "account for drift".
Replace first two sentences' core: `Each recording is first interpolated onto an even grid at its native sampling rate, 1\,Hz for the oyster arrays and 10\,Hz for the others, to remove the uneven sample spacing of the logger's analogue-to-digital converter.`

**A16. 02_background.tex:94** "This is uncertainty in the reference, a different measure from a classifier's balanced accuracy, not a ceiling on it."
Problem: label inconsistency does bound how well any classifier can appear to agree with those labels; "not a ceiling" is overstated.
Replace: `This is uncertainty in the reference itself, a different measure from a classifier's balanced accuracy, and only a loose bound on it.`

**A17. 05_methodology.tex:142** "Data handling follows appropriate practices ..., as per the Privacy Act of 1988 \cite{privacyact}."
Problem: the data contain no personal information, so citing the Privacy Act is a non sequitur.
Replace: `No personal data are involved. Data handling follows practices that keep the analysis reproducible: raw recordings are never modified, and every result records the recipe that produced it.` (or delete the sentence)

**A18. 01_introduction.tex:79** "the best performing systems were ensemble and transformer-based classifiers"
Problem: Bagnall et al.'s 18-algorithm bake-off (2017) found ensembles (COTE) best; it did not test transformer classifiers. Check the bib year; if 2017, this is a factual error.
Replace: `the best performing systems were ensembles, such as COTE, that combined multiple feature representations`

**A19. 01_introduction.tex:110 and 02_background.tex:104** "no study reports a detector's precision against blind human judgement" / "no published work has applied matrix profiling or image-based CNN classification to mycelium recordings"
Problem: universal negatives that the review cannot prove.
Replace: `no study found in this review reports ...` / `no published work found in this review has applied ...`

**A20. 01_introduction.tex:7 (caption)** "sixteen electrodes like this one, in each of several recordings, make up the 1,000-hour problem"
Problem: the 1,000 hours are two 16-electrode recordings (line 15); the later recordings have 4 electrodes.
Replace: `sixteen electrodes like this one, in each of two recordings, make up the 1,000-hour problem this thesis starts from.`

**A21. 01_introduction.tex:15** "one published detector marks almost two-thirds of a recording's time as events"
Problem: could not find this figure in Ch6 (Ch6:173 gives OASIS touching 65.6 % of *uninteresting windows*, not of recording time); Fig 4.x says OASIS and the CNN mark "almost everything". Check the source number before submission.
Replace if it is the window figure: `one published detector touches about two-thirds of the uninteresting windows of a recording`

## 2. Inconsistencies across the thesis

**B1. 04_mycowave.tex:87** "\texttt{artifact}"
Problem: prints the American spelling of a verdict word that is "artefact" everywhere else (house rule), and the order differs from Ch5:70.
Replace: `\texttt{seed}, \texttt{interesting}, \texttt{not\_interesting}, \texttt{unsure} or \texttt{artefact}` (or add "(stored as \texttt{artifact})" if the code value must be shown)

**B2. 04_mycowave.tex:123 (caption)** "the shape families of grouping g-05"
Problem: names.tex:27 says g-11 is the grouping used for results; a reader will ask why the screenshot shows g-05.
Replace: append `Grouping g-05 is an earlier cut; the results use g-11 (Section~\ref{sec:families}).`

**B3. 04_mycowave.tex:32** "rather than as a reason for an eighth type"
Problem: "eighth" before the reader is told there are seven.
Replace: `A small, closed set of seven interchange types gates which blocks can connect, and a question that cannot be expressed as a chain of them is treated as out of scope, not as a reason for an eighth type.`

**B4. 01_introduction.tex:152** "Every reported detection result is set against a null."
Problem: Ch4:113 says 2,587 of 2,936 real runs carry a null, so the claim needs to be about reported results only (it is, but reads as all runs). Optional.
Replace: `Every detection result reported in this thesis is set against a null.`

**B5. ai_statement.tex:90** "25/08/26 -- 09/26"
Problem: date format differs from every other row.
Replace: `25/08/26 -- 21/09/26` (or the actual last orchestrator date)

**B6. acknowledgements.tex:1** "\chapter{Acknowledgments}"
Problem: American spelling (house rule British).
Replace: `\chapter{Acknowledgements}`

**B7. 01_introduction.tex:84** "16 electrodes distributed across the fruiting bodies ... about 1,000 hours"
Problem: line 15 says two 16-electrode cultures; here it reads as one 16-electrode recording.
Replace: `The recordings were made with two arrays of 16 electrodes in the fruiting bodies, each sharing a common ground, and logged at 1\,Hz.`

## 3. Grammar, typos, wrong words

**C1. 05_methodology.tex:68** "In reviewing spans or windows as a single researcher, telling ..."
Problem: house rule (author never "the researcher"); dangling modifier.
Replace: `With a single reviewer, telling an ``interesting'' stretch of signal from a ``not interesting'' one came down to whether ...`

**C2. 01_introduction.tex:70** "calcium ions Ca\textsuperscript{+}, Ca\textsuperscript{2+} and potassium ions K\textsuperscript{+}"
Problem: Ca+ is not a biological ion.
Replace: `calcium ions Ca\textsuperscript{2+} and potassium ions K\textsuperscript{+}`

**C3. 01_introduction.tex:17** "transient permeabilization to enhance local uptakes of drugs"
Problem: American spelling; "uptakes" is wrong.
Replace: `transient permeabilisation to enhance local uptake of drugs`

**C4. 01_introduction.tex:13** "with unique but distinctive patterns of activity"
Problem: "unique but distinctive" is not a contrast.
Replace: `with patterns of activity that differ between species`

**C5. 01_introduction.tex:86** "Github" ; "the files, code and algorithms remain separated and unique"
Replace: `GitHub` ; `the files, code and algorithms are separate and were written anew`

**C6. 02_background.tex:42** "The in-house detectors, the drop detector (v1 and v5), deconvolved troughs, the noise and signal thresholds, ..., have no outside source."
Problem: appositive list reads as more items in the list.
Replace: `The in-house detectors (the drop detector v1 and v5, deconvolved troughs, the noise and signal thresholds, the wavelet-encoded detector and the CNN window scores) have no outside source.`

**C7. 02_background.tex:82** "The number of draws was set by cost, one per task in the detector sweep with 20 as a check, 200 per channel ..."
Problem: comma splice.
Replace: `The number of draws was set by cost: one per task in the detector sweep, with 20 as a check; 200 per channel for seed searches; and 200 label shuffles for every classifier null. With $N$ draws the smallest rank-based $p$-value is $1/(N+1)$, or 0.005 at 200.`

**C8. 02_background.tex:76** "evidence of structure not explained by spectral content alone, the relevant null here, since slow drifts ..."
Problem: run-on appositive.
Replace: `evidence of structure not explained by spectral content alone. That is the relevant null here, since slow drifts and broad oscillations are known to be present and are not what is claimed.`

**C9. 05_methodology.tex:54** "so that analysis results can accurately compare like units"
Replace: `so that results are always compared in like units.`

**C10. 05_methodology.tex:68** "Sequences were easily detected as a stretch of repeating waveforms with a level of evolution."
Replace: `Sequences were recognised as stretches of repeating waveforms that changed gradually.`

**C11. 05_methodology.tex:119** "The models under test, MiniRocket R4 and the four reference CNNs, had not been trained or tuned on M4."
Problem: repeats the previous sentences ("no model was trained or tuned on it").
Replace: `The models under test were MiniRocket R4 and the four reference CNNs.`

**C12. 04_mycowave.tex:142** "seeded search over whole profiles"
Problem: ambiguous ("over" reads as "applied to").
Replace: `seeded search instead of whole-signal profiles`

**C13. 01_introduction.tex:97** "electro-magnetic properties" ... "vital applications"
Replace: `electromagnetic properties` ... `important applications`

## 4. Machine-sounding prose

**D1. 01_introduction.tex:42** "It is worth noting that sampling rates ... as used notably in Adamatzky's language analysis"
Replace: `Sampling rates are not consistently reported across the literature, and where they are, resampling to 1\,Hz appears to have become an implicit standard, as in Adamatzky's language analysis \cite{adamatzky2022}.`

**D2. 01_introduction.tex:79** "The consequence is concrete and is worth stating plainly, because it motivates the structure of this thesis."
Replace: `This consequence shapes the structure of this thesis.`

**D3. 01_introduction.tex:19, 21, 72** "Most notably, ... leveraging this knowledge"; "leveraging the increase in processing power"; "most notably those of Andrew Adamatzky"
Replace: line 19 `The main questions are what the signals mean for the growth and function of a network, whether responses can be predicted from current recordings or stimuli, and whether that knowledge can be used to steer growth and behaviour.`; line 21 `using the processing power and memory available today`; line 72 `in particular those of Andrew Adamatzky and Matteo Buffi`.

**D4. 01_introduction.tex:104** "have yielded exciting results"
Replace: `have produced useful results`

**D5. 01_introduction.tex:77** "is most likely a significant contributor to the stall in progress"
Problem: speculative claim dressed as likely.
Replace: `has plausibly contributed to the stall in progress`

**D6. 04_mycowave.tex:61** "The seven types survived every block added during the project, and no eighth type was needed."
Problem: repeats line 32; with B3 applied, cut the second clause.
Replace: `The seven types survived every block added during the project.`

## 5. Repetition

**E1. 03_early_work.tex:61 and :73 (caption)** the photograph/camera analogy appears in both the text and the figure caption.
Replace (caption, last sentence): `delete`

**E2. 05_methodology.tex:119** "no model was trained or tuned on it" + line repeated (see C11).

**E3. 03_early_work.tex:14** "Scored months later against blind labels judged on the site"
Problem: "on the site" is unexplained jargon (used again in the Fig. caption at :39).
Replace: `judged blind in \tool{}'s Review page`

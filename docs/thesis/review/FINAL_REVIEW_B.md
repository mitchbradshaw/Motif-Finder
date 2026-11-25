# Final review B: Chapters 6-11 and Appendix J

Reviewer B, 9 Nov 2026. Scope: chapters/06-11, appendices/J_background.tex. Text inside `instructions` and comment
lines ignored. Line numbers are source-file lines. All `\ref`s in scope resolve to an existing `\label`, so no
broken cross-references were found.

## 1. Methodological and logical errors, contradictions

1. **10_roundb.tex:564** (B5, rewritten). The text says "OASIS, the deconvolved troughs, the noise and matrix-profile thresholds, the drop detector and the 60-minute CNNs found from about twice to over a hundred times more on the recordings than on their copies". This contradicts Ch 6: at 06:151 "Drop-detector ratios varied with recording and setting", at 06:153 the drop v1 4σ setting fired *less* on the recording than on every copy on 12 of 16 channels, and at 06:157 drop v5 gave 820 against 1,277 on MJu26a.
   Replace: "OASIS, the deconvolved troughs, the noise and matrix-profile thresholds and the 60-minute CNNs found from about twice to over a hundred times more on the recordings than on their copies, the drop detectors more or fewer depending on recording and setting, while the wavelet-encoded setting, ..."

2. **10_roundb.tex:675** (Table tab:rbsummary, B6 verdict). It says "in different recordings and in both species", but the result cell in the same row and the prose at 10:296 say "11 on all three species".
   Replace: "the same shapes occur in different recordings and in all three species, each recording with its own leanings"

3. **10_roundb.tex:578** (Fig. b9hist caption). The caption says "neither shows separate peaks at preferred durations", but the prose at 10:573 and the table say both show "the same apparent clusters" and "the 'modes' appear in AAFT too". The caption and the text disagree about whether clusters exist.
   Replace: "...with the same spread of durations from about ten seconds to minutes and the same apparent peaks, so the peaks are not a property of real events."

4. **11_discussion.tex:26**. It says "No constant period like the 34-minute oscillation of Slayman et al.\ appeared." Ch 10 reports a near-periodic CH14 train (gaps of 25-26 min, LV 0.03-0.10) at 10:202, and at 10:573 calls MJu26a's stretch "a steady oscillation of about 20 minutes".
   Replace: "No constant period like the 34-minute oscillation of Slayman et al.\ appeared across recordings."

5. **10_roundb.tex:573** and **11_discussion.tex:14, 30**. B10's conclusion, "So on no recording ... structure spans every scale from seconds to minutes", and Ch 11's "There is structure beyond noise at every window length from 30\,s to minutes" both overgeneralise. The same paragraph says MJu26a showed no length beyond AAFT, and the null is AAFT, not "noise".
   - 10:573 replace the last sentence with: "So on no recording did one time scale stand out: on four recordings structure spans every length from 30 seconds to several minutes, and, as for the detectors, the verdict depends on the choice of null."
   - 11:14 replace with: "On four of five recordings there is structure beyond the AAFT copies at every window length from 30\,s to several minutes, with no preferred scale (B10)"
   - 11:30: "Structure appears at every window length from 30\,s to minutes on four of five recordings (B10)".

6. **09_events.tex:97** (sec:pool). It says "against 1,097 events in the Library" and "about four times the Library". The same chapter says the inventory is now 2,959 spans (2,459 single events); 1,097 is the g-11 grouping (09:85). This sentence is stale against its own chapter.
   Replace: "...against the 2,459 accepted single events of the inventory (Figure~\ref{fig:pool}). ... R4 calls roughly 4,500 of the top tier events, nearly twice the inventory." (If the figure still shows 1,097, say "against the 1,097 Library events of g-11".)

7. **11_discussion.tex:20**. "This suggests the existence of waveforms unique to the composition of the fungal signals, which randomised surrogates cannot reproduce, further suggesting the possibility of significant biological events." This stacks hedges, and it overstates the null: 11:115 itself says phase randomisation "scrambles a sudden fall easily", and Ch 10 B9 shows that a phase-randomised null can make a method look selective.
   Replace: "Phase-randomised copies, which keep the frequency content, do not reproduce this waveform, although they are an easy null for a sudden fall (Section~\ref{sec:review}); an AAFT test is the next step."

8. **11_discussion.tex:124**. "and nothing travels between electrodes at these spacings" states an absence as a fact. Ch 10:367 says propagation "was never likely to be detected here".
   Replace: "and nothing was seen travelling between electrodes at these spacings."

9. **06_rq1_detectors.tex:65, 72, 88, 95, 99, 101; 11:8; J:77-78; 10:564**. Throughout, acceptance is written as "real" ("judged real", "Share real", "0--5\,\% of candidates are real", "the real one has more agreeing algorithms"). This conflates precision-as-acceptance with ground truth, which 06:189 says the thesis does not have. Fix at least these:
   - 06:72 caption: "Estimated share of candidate events accepted", and column header "Share accepted".
   - 06:99: "the likelihood that a candidate is accepted increases sharply ... 0--5\,\% of candidates are accepted; where nine or more agree, 40--63\,\% are".
   - 11:8: "0--5\,\% of candidates were accepted, and where nine or more agreed, 40--63\,\% were".
   - 06:101: "picking one accepted and one rejected candidate at random, the accepted one has more agreeing algorithms 87\,\% of the time".

10. **11_discussion.tex:12**. "so the reference CNNs' gap lay in their training labels rather than their architecture" is stronger than J:115, which says "could not be attributed to CNN architecture alone". The retraining changed both the labels and the examples (fixed windows against spans with context).
    Replace: "so the reference CNNs' gap came from what they were trained on, not from their architecture alone"

11. **10_roundb.tex:564** and the B11 row at **10:678**. The text says "against 2--4\,\% on their copies", but Table tab:rbsummary B11 gives 1.6\,\% for the MJu26a copies.
    Replace: "against 2--4\,\% on the judged recordings' copies and 1.6--3.7\,\% on the newer ones".

12. **10_roundb.tex:564** "Across the eight recordings". The thesis's eight recordings (Fig. combinedcatalogue) include M4, which is excluded from the sweep statistics (06:13), while B5 counts 45 + 24 channels: five judged recordings plus the three newer 2 Hz sweeps (MJu26a in full, SH, SO). "Eight" therefore means different sets in Ch 9 and Ch 10.
    Replace: "Across the five judged recordings and the three newer 2\,Hz sweeps (M4 excluded), ..."

13. **10_roundb.tex:564** and **06:157**. "the three 2\,Hz recordings" against "the judged ones" is ambiguous, because LM\_fs2, CO\_fs2 and the judged MJu26a (CH10, 13--16) are also 2 Hz (Table tab:sweepscale).
    At 10:564, replace "On the 2\,Hz recordings, as on the judged ones," with "On the three newer, unjudged sweeps (MJu26a in full, SH, SO), as on the judged recordings,". At "on the three 2\,Hz recordings", use "on the three newer sweeps".

14. **11_discussion.tex:101** (Table tab:schedulereview). It gives "the studies of Chapter~\ref{ch:roundb} (29 Oct -- 3 Nov)", but tab:rqmap (11:57) says B4 was run on 28 Oct and Ch 10:59 says the studies were fixed on 27 Oct.
    Replace: "the studies of Chapter~\ref{ch:roundb} (27 Oct -- 3 Nov)".

15. **11_discussion.tex:115** against **10:109**. Ch 11 says "20 of its 56 channels have fewer than ten [events]", so 36 have ten or more, but B1 reports "44 channels ... with enough events". The reader cannot reconcile 36 with 44.
    Replace: either state B1's threshold at 10:109 ("On the 44 of 56 channels with at least N intervals...") or correct Ch 11 to the matching count.

16. **06_rq1_detectors.tex:60** against **06:177**. At 06:60, "The sweep's default matrix-profile threshold made no detections on the two channels tested in each of M2\_aug and M2\_concat". At 06:177, "On the two channels where it ran, the matrix-profile threshold at 6 touched 46.7\,\% of interesting windows". If threshold 6 is the default, these contradict each other. If it is not, say so.
    Replace at 06:177: "On the two M2\_aug channels where a non-default matrix-profile threshold of 6 ran, it touched ..."

17. **09_events.tex:36**. "A review of 322 earlier Library proposals ... accepted 280, rejected 24 and marked 17 unsure": 280 + 24 + 17 = 321.
    Replace: either "321 earlier Library proposals", or add the missing verdict ("and 1 artefact").

18. **09_events.tex:36**. "Of the proposals, 231 were accepted, against 5 of the random windows, adding 237 spans": 231 + 5 = 236. Check the count.
    Replace: "adding 236 spans" (or explain the extra span).

## 2. Inconsistencies of numbers, names and terms

19. **10_roundb.tex:202**. "the 450 spikes from 406 hours on" conflicts with 10:200, which says the upper band "appears at about 402 hours", and with the 402 h dotted line in the Fig. ch14bands caption.
    Replace: either "from 402 hours on" with the matching count, or add "(the first full cycle of both bands)".

20. **10_roundb.tex:296**. "On the full inventory's 2,459 accepted single events and their twelve shape families" is not quite right: 09:85 says 2,454 events had a usable cut and were grouped.
    Replace: "On the full inventory's 2,459 accepted single events (2,454 of them grouped into twelve shape families, Section~\ref{sec:families})".

21. **10_roundb.tex:564** "BEADs" against **10:198** "BEADS" and **06:132** "BEADS (inverted)".
    Replace: "BEADS".

22. **11_discussion.tex:120**. "Two round-B questions, multiscale entropy (B7) and motif prevalence (B8)": "round B" is never introduced in the printed Chapter 10, which calls them "the questions of this chapter".
    Replace: "Two questions of Chapter~\ref{ch:roundb}, multiscale entropy (B7) and motif prevalence (B8), remain open."

23. **11_discussion.tex:8** "Thirteen detector families in 45 settings" against **10:564** "about 40 detector settings ran on every channel". 06:13 gives 45 on M2\_aug and 38--44 on the others; it is fine, but Ch 10 could say "38--45 detector settings".

24. **appendices/J_background.tex:117**. "the MJu26a overlap described above": the overlap is described in Chapter 8 (08:89, 08:112), not above in this appendix. This is a dangling antecedent left by the move.
    Replace: "The shared recording folds also shared the overlap between the MJu26a groups noted in Chapter~\ref{ch:rq3}, and ..."

25. **appendices/J_background.tex:4**. "the methods background of Chapter~2" is hard-coded.
    Replace: "the methods background of Chapter~\ref{ch:background}" (or whatever Chapter 2's label is).

26. **appendices/J_background.tex:77**. "Precision ... with a Wilson interval", but Ch 6's precision intervals are stratified bootstrap intervals (06:19).
    Replace: "is the share of a detector's candidates judged interesting, with a Wilson interval for simple samples and a stratified bootstrap interval for the sweep (Chapter~\ref{ch:rq1})."

## 3. Grammar, typos, unclear sentences

27. **10_roundb.tex:223**. "Although across the longer gaps between events flagged by the detector census there seemed to be a weak link on the two M2 recordings, this was halved once the duration of the fall was accounted for." The sentence is tangled.
    Replace: "Across the longer gaps of the detector census, the two M2 recordings showed a weak link, but it halved once the duration of the fall was accounted for."

28. **10_roundb.tex:367**. "although the electrodes were placed fairly irregularly, ..., so propagation was never likely to be detected here". "Although" is the wrong connective, because the clause explains the null result rather than contrasting with it.
    Replace: "Nothing was seen travelling between electrodes at these spacings and sampling rates; the electrodes were placed fairly irregularly, on different fruiting bodies, so propagation was never likely to be detected here."

29. **11_discussion.tex:6**. "to examine what recurring structures are in fungal bio-electric recordings".
    Replace: "to examine what recurring structures exist in fungal bio-electric recordings".

30. **10_roundb.tex:634** (summary; flagging only the clear error). "are numerically random" is not meaningful and contradicts the 15 channels with correlated neighbouring gaps.
    Replace: "are close to random from one event to the next".

31. **06_rq1_detectors.tex:17**. "the 3.1 million candidates ... were randomly sampled from bins" says the candidates were sampled, but a sample was drawn from them.
    Replace: "For human judgement, a sample of the 3.1 million candidates (1.5 million on M2\_aug alone) was drawn at random from bins defined by ..."

32. **06_rq1_detectors.tex:60**. "fires consistently on fungal signals, but with lower accuracy". Accuracy is the wrong measure here.
    Replace: "but with lower precision".

33. **06_rq1_detectors.tex:88**. "a detection algorithm built in one context does not map effectively across the larger time-series signal of another" is vague.
    Replace: "a detector built for one kind of signal does not transfer well to these long fungal recordings."

34. **09_events.tex:50** (Fig. anatomyevent caption). "full width at half depth (FWHM)" is defined twice.
    Replace the first mention "and the full width at half depth (FWHM)" with "and the FWHM", or delete the second definition.

35. **appendices/J_background.tex:69**. `\cite{adamatzky2023}, \cite{dehshibi}` prints two bracket groups.
    Replace: `\cite{adamatzky2023,dehshibi}`.

## 4. Machine-sounding prose

36. **06_rq1_detectors.tex:58**. "This drastically reduces the significance of a single detection event." "Significance" is used loosely, and "drastically" is repeated at 06:99.
    Replace: "A single detection therefore says little on its own."
    At 06:99, replace "drastically increases" with "rises sharply".

37. **06_rq1_detectors.tex:60**. "Both extremes reveal information, about the effectiveness of an algorithm on fungal bio-electric signals and about the signals themselves."
    Replace: "Both extremes say something about the detector and about the signal."

38. **06_rq1_detectors.tex:6**. "Currently, research into fungal signals provides many novel but ultimately distinct detection algorithms."
    Replace: "Studies of fungal signals have each proposed their own detection algorithm."

39. **10_roundb.tex:95**. "notably shiitake, snow oyster and more of MJu26a" uses a stock phrase. The same paragraph also repeats the reason for using the drop detector, which 10:107 then gives again.
    At 10:95, replace "notably" with "chiefly". Then replace "and they use the drop detector because Chapter~\ref{ch:rq1} found its candidates the most often accepted (Section~\ref{sec:rb_sequences})" with "from the drop detector (Section~\ref{sec:rb_sequences})".

40. **10_roundb.tex:109, 296** "For the mushrooms, ..." (twice). This is colloquial, and the cultures are mycelium rather than mushrooms.
    Replace: "For the cultures, ..." (or delete "For the mushrooms," and start the sentence at "The timing").

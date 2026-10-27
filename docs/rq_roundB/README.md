# rq_roundB: research questions, round two (rough notes)

Started 2026-10-03. **This is deliberately mostly empty.** Round B's questions depend on what round A
(`docs/rq_roundA/`) finds. The plan is about 18 questions over about three rounds, each answered with the
website as it stands at the time, each round developing the site for the next.

When round A has results, turn the notes below into one file per question, using round A's shape: in plain words,
what is known, decisions, what is needed, how it gets answered, open decisions, log.

## Capabilities parked for after round A (decided out of scope 2026-10-03)

- **Branching chains** (Q-B-CHAIN): one motif train feeding a width analysis *and* an interval analysis in one
  chain. Today it's one chain per intent, and the step cache makes the shared steps free.
- **Multivariate analysis**: several channels or several feature sets analysed together, rather than one signal at
  a time.
- **Polar and cube (3-D) plots of families** (Q-L5): only if a question needs them.

## Candidate questions and ideas (unranked, unrefined)

*Seeds for discussion, not commitments. Add freely; delete freely.*

- **The sharkfin plateau.** A sharkfin sits on its floor, drifting slightly lower, for half to two-thirds of the
  interval, then climbs back. A trough is mostly back by the quarter point. Nothing measures this yet
  (`fixup/QUESTIONS.md` "Q26, REVISED"). Is the plateau length a stable signature per organism or condition?
- **Recovery once extent is fixed.** After `future/N-event-extent.md`: does width predict recovery time? `E`'s
  id010 β 0.28 was never tested against a real null.
- **Motif trains.** What populates a train (Q-X3: a Review gesture, then a detector scored against it)? Are
  inter-event intervals regular, and do slopes within a train change in order (the rose)?
- **Spikes as well as drops.** Running the drop detector on an inverted signal (`preprocessing.invert`) to find
  spikes: are spike families as recurrent as drop families?
- **Dehshibi tuned vs untuned** (Q34): does tuning `epsilon_factor` / `min_separation_s` / `window_s` make it
  selective on these recordings, or is it a weak baseline whatever?
- **Conditions and organisms.** Settings › Datasets now carries species, organism id, condition and notes. Do
  families or rates differ by condition (e.g. Faraday cage vs outside)?
- **Blind labelling agreement.** RQ1's yardstick (B): how often does a blind human agree with the cluster
  vocabulary, and on which classes?
- **The interrogation null** (`future/R-interrogation-null.md`): which interrogation statistics survive matched
  random windows?

## Log

- 2026-10-03 · grilling · folder created with parked capabilities and seed ideas.
- **A CNN trained on the Library motifs (the researcher, 2026-10-07).** A model that sifts a whole dataset and flags
  sharkfins, troughs, sequences etc. with a confidence. Discussed the same day: it needs an explicit *background* class
  (noise and plain drift, sampled from stretches holding no member, several times the motif count, with near-misses
  included) — a softmax network trained on motif classes alone forces noise into a motif class with high confidence;
  classes must be the researcher's **verified** named families, not raw Ward families; roughly 100–200 verified
  members per class to start, 500+ to be comfortable, classes under ~50 merged or dropped; positives jittered in
  position and taken at the three scales; a held-out pack and a blind check as in RQ1; confidences calibrated on
  validation. Today (g-05): 3,239 members in 149 families, the largest 79, thirty families with 30 or more, and
  one human verdict on a member — so the first job is a vocabulary of 5–8 named classes and verifying members.
- 2026-10-13 · blocks-w1 · tools for three seed ideas now exist: *motif trains* → `interrogation.trains` (logISI / MaxInterval / Adamatzky words; experimental: no trains found beyond the null on the spans tried); *the sharkfin plateau* → `detection.deconvolve`'s residual and follow-on warnings measure how far an event departs from a jump + exponential recovery; *spikes as well as drops* → `detection.noise_threshold` and `detection.cwt_ridges` take a polarity. Interval regularity now includes LV and CV2. See `docs/prompts/blocks/reports/`.
- 2026-10-15 · blocks-w3 · *conditions and organisms* → `catalogue.multiscale_entropy` and the shipped `complexity_fingerprint` template (a complexity curve per 72 h window, judged against AAFT noise with the recording's own values and spectrum): the four Adamatzky species separate on it beyond that noise (silhouette 0.43 vs 0.22–0.37), but most of the separation is noise colour, and M2_aug differs by setup as much as by organism — compare within one setup; the preprint's √t "mean MSE 0.0028" collapse does not reproduce. *Motif trains and the sharkfin plateau* → `interrogation.cycle_shapes` and the shipped `chain_cycles` template (each drop-to-drop cycle of a chain warped to one length, stacked, aligned, grouped; judged against pseudo-cycles from the recording's own quiet stretches): three long chains are far more coherent than that, each with one cycle shape; rec 2's labelled sharkfins recover half their depth in ~40 s and then sit 2–15 % of the depth below the start, drifting lower — the plateau needs its own floor measure (the block's floor band sees the drop's bottom). *The window behind the spiking-families scale* → `detection.pan_matrix_profile` and the shipped `motif_lengths` template (the matrix profile at 12 lengths from 30 s to 1 h, judged against AAFT noise): on rec 385 every judged length from 30 s to 16 min repeats beyond noise, the strongest at 30 s rather than 1 min, so the pan picture — not its one-line answer — is where a window choice is read; on chains every judged length repeats too. Also: families judged against quiet stretches of their own recording (W3-G); MPdist the Library's fourth distance (RQ3). See `docs/prompts/blocks/reports/W3-evaluation.md`.
- 2026-10-26 · thesis-events-grouping · round B's Library grouping is **g-10** (cite it by id): one representative per de-duplicated event, M2_aug (529 events) and Mushroom rec 385 (61); Fig2A pieces and the 50 Review entries excluded; Ward at g-05's settings; 25 families (8 hold both recordings), stability ARI 0.88-1.00 / 0.91-0.95 at 1 % / 2 % jitter, in its `fit_summary_json`. Events table: `docs/thesis/data/library_events/` (3,603 non-Review members -> 1,116 events; 590 outside Fig2A; the 210 accepted members are 144 events, 113 outside Fig2A). CO_fs2, LM_fs2, L_LM and M2_concat have no Library members beyond 8 Review entries: the accepted blind events of queues 25/28 were NOT imported, because the only existing route (Review's promote) re-writes the verdict.
- 2026-10-27 · thesis-promote-blind · round B's all-recordings Library grouping is **g-11** "thesis · events · all active datasets (2026-10-27)" (g-10 kept; g-11, the newest motif grouping, is now the Atlas's default). Before it, the 716 accepted own looks of blind queues 25/28 went through a new verdict-free promote (`Working/review/promotion.py::promote_to_library`, no `adjudications`/`annotations` row, one `audit_log` row `library-promote` each, undone by `unpromote_to_library`; `scripts/thesis/promote_blind_accepted.py`): 600 promoted (entries 3660-4259, source_kind `review-accepted`; M2_aug 321, LM_fs2 106, CO_fs2 96, M2_concat 77), 30 skipped as exact/near duplicates of held spans, 86 refused (L_LM fs2, inactive). Events table on active recordings only (never M4, L_R): `docs/thesis/data/library_events_all_active/` (1,689 members -> 1,097 events; 678 hold an accepted member). g-11: 1,097 items, Ward at g-10's settings, 42 families (817 assigned, 280 omitted), 39 families hold 2+ recordings and 14 hold all four, 38 mix an M2 recording with CO_fs2 or LM_fs2; species are set only for M2_aug (oyster), so no family can yet be called cross-species from the database. Stability ARI 0.90-0.95 (1 %) / 0.86-0.91 (2 %), cophenetic 0.649, in its `fit_summary_json`. Caveat: on CO, LM and M2_concat every Library member is an accepted detector event, so recurrence there is of what the detectors found and the researcher kept.
- 2026-10-28 · round 5 · **B3** runs both tests: the restitution test (recovery against the preceding gap, gaps shuffled within each sequence) and per-cycle model tracking (fall + recovery, FHN excitable and oscillatory, Izhikevich), judged by held-out-cycle prediction with drift against shuffled order; both are backend computation on the site's Event shape, Intervals and cycle stacks. FHN stays backend for now. The fair CNN stays out of the M4 exam. Round B works on **g-11**, rebuilt once as **g-12** after the 2 Hz sweep is imported and its blind sample judged, then frozen for Chapters 9 and 10. B4's earlier 64/123/97 figures were sandbox numbers (`B4-cross-channel.md`). The researcher's task list: `docs/thesis/TASKS.md`.

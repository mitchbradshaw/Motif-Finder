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

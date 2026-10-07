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

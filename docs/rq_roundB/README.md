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

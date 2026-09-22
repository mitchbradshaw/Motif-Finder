# Fixup stage — questions that must be answered before the prompts can be written

Each question is one that changes *what the work is*, not how it is done. Answers are recorded here
under the question, dated, and then quoted in the prompt that depends on them.

Round 1 is in progress (see the chat of 2026-09-22). Nothing here is answered yet.

---

## Scope and shape of the stage

**Q-0.1** Is a fixup prompt **per page** (11 files as built) or per **symptom cluster** — e.g. one prompt
for "the plot-domain rule everywhere", one for "spike trains end to end", one for "Models + Jobs from
scratch"? The 11-file layout follows the pages; the work does not.

**Q-0.2** Do Models and Jobs get *fixup* prompts or *wiring* prompts? They were never wired. Their
symptom lists are "the whole workspace" and their size is likely larger than every other file combined.

**Q-0.3** Feature freeze is **28 August 2026** and today is 2026-09-22. Which of these are in scope at
all, and which are explicitly out?

---

## The plot-domain rule (X2, R1, L1, L2, L3)

**Q-X2.1** Is PRD D5 — one shared unnormalised mV domain per page — still the rule?

**Q-X2.2** If it stays: is the 75th-percentile domain right, or should it be per-family-measured with
the shared scale printed as a reference?

**Q-X2.3** Should the Family page's **shape sketch** be dropped and the real waveform fetched for the
member cards (L3)? The sketch exists because that read does not carry waveforms — so this is "add a
waveform read", not "change a domain".

**Q-R1.1** Review's `[-0.44, 0.44]`: data-driven per candidate, or per queue, or a settings key?

---

## Morphology as data (I1, I2, L12, X3)

**Q-I1** Should width, amplitude, depth, recovery time and slope be **stored per motif**, against
Library §4.4 which rejects measured features on Library rows? If yes, §4.4 is being changed and that
is a versioned act.

**Q-I2** Is "drop width vs recovery time" a **plot on the Aggregate page** or a **stored feature set**
you can group, filter and sort the whole Library by?

**Q-X3** The supervisor's workflow — *find a spike train → analyse its spikes*. What populates a spike
train? A detector block, a Review gesture that marks a span as a train, or an importer?

---

## Ground truth (D2)

**Q-D2** Precision is 0 by construction because 11,234 of 11,269 annotations are 600-sample windows,
not event spans. Wiring's three options, unchosen: (a) score `imported_10min` rows by **containment**
rather than IoU; (b) **re-cut the ground truth** as event spans; (c) scope precision to the 35
event-shaped annotations. Which?

---

## Review's remaining gaps (R2, R3, R4, R7)

**Q-R2** Tags and classes: one fix, or two? Tags have a working core path and no component; classes
have neither a store nor a table.

**Q-R4** Is the extract-events editor in scope? 30 sequences are waiting on it and the route works.

**Q-R7** A rediscovery can be put to the researcher twice. Fix by carrying the prior verdict, or by
filtering the candidate out of the queue entirely?

---

## The things that block other things

**Q-T4** `window_sets` has zero rows. Three pages, two Review queue kinds and Models › Launch are all
blocked on one *Save window set* click working. Is this the first thing in the stage?

**Q-L4** Hand edits: the routes and core are tested and the controls are toasts. Same shape as T4 —
a small wire with a lot behind it.

---

## The large new asks

**Q-X5** "Code your own algorithm" — Settings surface, scaffolding generator, or refused? It has the
biggest security and gate surface of anything here.

**Q-L5** Polar and cube plots — what question do they answer that the Atlas grid does not? `charts/`
has no polar or 3-D primitive.

**Q-L6 / Q-E6** "Click into a cluster and see the waveforms" — which plots, and does clicking navigate
(to the Family page) or expand in place?

---

## Diagnosed (2026-09-22, read-only investigation — no longer questions for the user)

**Q-A2 → answered.** The Dehshibi template fails three ways, none of them a type mismatch: a `.mean()`
where `nanmean` is required over a NaN-by-construction matrix (black stage-1 image at any real span
length), no `max_span_samples` on a block that allocates 1.33 GB + 2.66 GB on a whole channel, and a
serializer with no case for `pseudo_spikes`. See `02-analyse-chain.md` A2.

**Q-D1 → answered.** The Discovery add-template glitch is a 600 px loading card rendered as a sibling
of the page content, re-raised by a 2-second reload poll for the whole life of the run you just added —
plus a modal whose default selection names templates that do not exist, and a template that becomes
un-selectable after one use. See `05-discovery.md` D1.

**Q-A3 → answered.** `catalogue.cluster` drops the linkage matrix, `silhouette`, `cophenetic_r` and
`df_membership` that `cluster_window_matrix` computes, so no dendrogram can be drawn and k has no
criterion; `catalogue.classifier`'s joblib is write-only and its whole evaluation is one accuracy
number. See `04-analyse-training.md` T3.

**What this changed about the stage:** three of the user's ten feedback items turned out to be plain
bugs with a known line and no decision attached. The stage is therefore *not* uniformly
design-question-blocked — a "just fix it" prompt can start before `QUESTIONS.md` is resolved.

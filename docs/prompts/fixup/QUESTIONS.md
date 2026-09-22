# Fixup stage — questions that must be answered before the prompts can be written

Each question is one that changes *what the work is*, not how it is done. Answers are recorded here
under the question, dated, and then quoted in the prompt that depends on them.

**Round 1 answered 2026-09-23.** Answers are recorded inline below, marked **A:**.

---

## Scope and shape of the stage

**Q-0.1** Is a fixup prompt **per page** (11 files as built) or per **symptom cluster**?

**A: hybrid (c).** Cluster prompts for the cross-cutting rules — one owner each, so a rule is not
implemented three ways — and page prompts for the residue, which is genuinely parallel.

**Q-0.2** Do Models and Jobs get *fixup* prompts or *wiring* prompts?

**A: in scope, cut to one page each.** Jobs › All jobs and Models › Registry. Launch / Results /
Compare are a research surface with no results to fill them yet.

**Q-0.3** The freeze date.

**A: changed.** 28 August 2026 is spent. The constraint is **21 October 2026, ~4 weeks, to a polished
and reliable Pipeline UI**, after which the tool answers research questions rather than being extended.
`CLAUDE.md`, `docs/PIPELINE_PRD.md` and `Claude outputs/UI_FUNCTIONAL_SPEC.md` updated 2026-09-23.

**Q-0.4 (new, answered with Q-0.3)** Whose workflow ranks?

**A: the researcher drives, the supervisor reads.** The supervisor is expected to keep using the tool
after this project, so **where the two overlap, that path must be the most reliable in the app.**
Priority order, binding: **workflow friction first, legibility second, completeness last.**

**Q-0.5 (new, answered with Q-0.3)** What is the single most wanted capability?

**A: statistical measures of spike trains and individual spike events** — inter-spike intervals,
amplitude, drop width, drop depth, recovery time, rose plots. Wanted by both researcher and supervisor,
so by Q-0.4 it is the most load-bearing path in the app. The researcher's own read is that these belong
as **new analysis blocks**; see Q-I1/Q-I2/Q-X3, all answered below, and prompt `B-`.

---

## The plot-domain rule (X2, R1, L1, L2, L3)

**Q-X2.1 / Q-X2.2** Is PRD D5 — one shared unnormalised mV domain per page — still the rule?

**A: per-card measured domain, with the shared scale drawn as a reference bar.** D5's purpose (a
micro-volt family must not be made to look like a millivolt one) is kept by the reference bar; the
shape becomes legible because each card gets its own domain. **No motif may be clipped in its own
thumbnail** — that is the acceptance test, not a nicety.

**Q-X2.3** Should the Family page's **shape sketch** be dropped and the real waveform fetched?

**A: yes, fetch the real waveform for the member cards.** A member card that does not show the
member's waveform is not worth its space on a page whose job is looking at every member. The cost is
a payload-size question, to be measured and reported, not a design one.

**Q-R1.1** Review's `[-0.44, 0.44]`: data-driven per candidate, or per queue, or a settings key?

**A: follows Q-X2.1** — per-candidate measured, reference bar for the shared scale. One rule across
Review, Library and Explore; that is the whole point of making it a cluster prompt.

**Q-X2.4 (new, raised by the researcher 2026-09-23) — THE UNITS QUESTION, AND IT OUTRANKS ALL OF THE
ABOVE.** The Library's shared domain reads ±0.0043 "mV". The researcher states the recording noise
floor is ~0.1 mV and that real drop motifs run 1 mV to 20 mV or more. 0.0043 mV is therefore ~23x
*below* the noise floor and ~250-4600x below a real motif. Three possibilities, mutually exclusive:
**(a)** the values are volts labelled mV — a 1000x error, and every amplitude the app prints is wrong;
**(b)** the values are mV but something upstream rescaled them; **(c)** the numbers are right and the
Library is full of sub-noise-floor events, i.e. its contents are noise rather than motifs.
**A (2026-09-23, settled bit-exactly): (a). The derived channels are in VOLTS and the entire web UI
labels them "mV" without ever converting.** The researcher's instinct was right. `±0.0043 "mV"` is
**±4.3 mV** — 43x above the 0.1 mV noise floor, squarely in the stated motif band.

**The proof**, reproduced independently rather than taken on report:

    events.csv row id001_r1_1213252  ·  drop_depth_mv = 15.0617
    npy  CH0.npy[1212809:1213520][:3] = [-0.45839212 -0.45842311 -0.45842109]
    npz  id001_r1_1213252__raw_mv[:3] = [-458.39212 -458.42311 -458.42109]
    allclose(npy * 1000.0, npz) -> True      max|ratio - 1000| = 1.14e-13

Two artefacts in this repo — one tracked as source data with a written units contract, the other the
file the app reads — related by exactly 1000.

**Corroboration, all independent of each other:** `detect5.py:81` states *"`x` is in the recording's
native units (volts); amplitudes on the returned events are in mV"* and multiplies by 1000.0 at
`:833-836`; `store.py:113,129` says the same and writes `__raw_mv = x * 1000.0`;
`wavelet_analysis.py:102` independently says *"signal in volts"*; `detect5.py:927` names the
*"0.1 mV instrument floor"*.

**Where the conversion goes missing:** nowhere between `np.ptp` on the memmap and the character "mV"
on screen is there a factor of 1000. `webui/server/library.py::_span_amplitude` and `::_trace` read the
memmap raw under docstrings that say "mV"; `corpus.load_channel` is a bare `np.load`; `corpus.y_range`
returns raw min/max. **Explore, Review and Library all have the identical error**, so the app is
internally consistent and there is no intra-app disagreement to find.

**The error is fossilised in the source comments, each a true number shrunk 1000x:** *"the real depths
run about 0.006 to 0.015 mV"* (really 6–15 mV); *"the motifs riding on them are micro-volts"* (really
millivolts); *"F-01's exemplar spans −1.148…−1.131 mV … a real 17.6 µV drop rendered as a dead-flat
line"* (really −1.148…−1.131 **V**, and a **17.6 mV** drop — dead centre of the researcher's band).
Review's `Y_MV = [-0.44, 0.44]` is a *correct centred domain in volts*, hand-measured off the same
unconverted data. Every one of these is a developer meeting the bug, explaining it away, and adjusting
an axis instead.

**The unit is recorded nowhere on the data.** `materialize_channels.py` writes a sidecar manifest with
no `units` key, while `Working/registration/kinds.py:310` already reads `man.get("units")` — the reader
expects a field the writer never emits. `recordings` has no units column. That absence is the root
cause, not the missing `× 1000`.

**Option (c) is refuted for the seed store and CONFIRMED for the rest of the Library — a separate
finding the units bug was hiding.** Measured over a 600-span random sample of `motif_member`
(peak-to-peak off the memmap, converted to mV):

| Source store | n | p25 | median | p75 | max | under 0.1 mV |
|---|---|---|---|---|---|---|
| `DATA/library_seed/drop_motifs5/motifs` (410 entries) | 72 | 5.14 | **13.31** | 16.93 | 119.6 | **0.0 %** |
| `Plots/drop_motifs10/motifs` (3,189 entries) | 528 | 0.117 | **0.324** | 0.912 | 135.9 | **22.2 %** |

The seed store is exactly the physics the researcher describes. But **88 % of the Library is
`drop_motifs10`, whose median motif is 41x smaller than the seed store's and 22 % of which is at or
below the instrument floor.** That is not a units bug; that is a detector run whose output is largely
noise, and it is the real answer to "too many flat families" (L2). It has been invisible because the
axis said 0.0043 and everything looked equally tiny.

**Q-X2.5 (new, blocking for the Library): what happens to `drop_motifs10`?** Re-run its detector with a
floor at 0.1 mV, filter the existing entries, keep them and mark them, or drop the store from the
Library? That is a research call, not an engineering one. Round 2.

---

## Morphology as data (I1, I2, L12, X3)

**Q-I1** Should width, amplitude, depth, recovery time and slope be **stored per motif**, against
Library §4.4?

**A: yes — change §4.4 additively.** A `motif_features` table keyed by **content hash**, recomputable
from the snippet, never authoritative. §4.4's real fear is a stale measurement outliving its waveform;
a content-hash key kills that. This is a versioned change to the spec and must be recorded as one.

**Q-I2** Is "drop width vs recovery time" a plot, or a stored feature set?

**A: a stored feature set** you can group, filter and sort the whole Library by. The plot falls out of
it. Follows from Q-I1.

**Q-I3 (new, answered 2026-09-23)** How do the new statistics reach the app?

**A: as new analysis blocks**, through the existing generalised wiring structure — the researcher's own
judgement, and it is the right one: a block is typed, costed, cached, testable, re-runnable and
composable into a chain, which a page-local computation is none of. The measures wanted, named:
**inter-spike interval, amplitude, drop width, drop depth, recovery time, rose plots**, "etc." — the
"etc." is itself a question (Q-B1, round 2).

**Q-X3** What populates a spike train?

**A: a Review gesture first, then a detector.** But **not only** a Review gesture — **Explore must be
able to send a span for review carrying a `train` flag, a note and its morphology**, at the moment the
researcher spots it while reading a dataset. That is the friction Q-0.4 puts first. The human gesture
produces the ground truth; the proximity-grouping detector is then scored against it. A detector
without the gesture has nothing to check it against.

---

## Ground truth (D2)

**Q-D2** Precision is 0 by construction because 11,234 of 11,269 annotations are 600-sample windows,
not event spans.

**A: (a) and (c) together, reported as two numbers, each printing its own rule.** Containment over the
window labels answers *"does the detector fire where a human saw something"*; the event-shaped rows
answer *"does it get the extent right"*. (b) — re-cutting the ground truth by hand — is the only option
that gives both properly and costs weeks of the researcher's own time, so it is not taken now.

**What the two populations actually are** (counted read-only against `DATA/db/annotations.sqlite`,
2026-09-23; the researcher guessed this almost exactly right):

| Source | Verdict | n | Width, samples (min / mean / max) |
|---|---|---|---|
| `imported_10min` | `not_interesting` | 8,773 | 600 / 600 / 600 |
| `imported_10min` | `interesting` | 2,333 | 600 / 600 / 600 |
| `imported_10min` | `artifact` | 128 | 600 / 600 / 600 |
| `excel_catalog` | `interesting` | 30 | 126 / 46,193 / 324,000 |
| `excel_catalog` | `artifact` | 1 | 21,600 |
| `manual_ui` | `interesting` | 4 | 14,746 / 94,509 / 172,350 |

So **11,234 = the interesting / not-interesting / artifact window labels**, every one exactly 600
samples — the 10-minute CNN training set. And **35 = 31 from the excel catalogue + 4 drawn by hand in
the UI**, not 35 from the catalogue.

**A caveat that matters for (c), and that nothing has said before now:** the 35 "event-shaped" rows are
not event-shaped either. They run **126 samples to 324,000 samples** — at 1 Hz that is two minutes to
**ninety hours**. A 324,000-sample "interesting" span is a region a human marked as worth looking at,
not an event with an extent a detector could be scored against. So (c)'s denominator is not just small,
it is heterogeneous, and a precision computed over it will be dominated by whichever handful of rows
happen to be genuinely event-sized. **The prompt that implements (c) must report the width distribution
of its denominator beside the number**, or (c) becomes the same kind of uninterpretable figure as the
0.00 it replaces.

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

**Q-X5** "Code your own algorithm" — Settings surface, scaffolding generator, or refused?

**A: out of scope, explicitly, and not deferred-with-a-plan — dropped for this stage.** A nice feature
for future users; for now every new analysis algorithm is added to the backend by an agent through the
generalised wiring structure (`docs/BLOCK_INTEGRATION.md`), which is the same path prompt `B-` uses.
Do not build a scaffolding generator either. Remove `X5` from `00-cross-cutting.md`'s live list.

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

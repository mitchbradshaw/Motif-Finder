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

**Implemented by prompt `C` (2026-09-23, `reports/C-one-plot-domain-rule.md`).** The one rule is
`webui/client/src/charts/domain.ts` (`measuredDomain` / `padDomain`, run under Node by
`tests/test_webui_plot_domain.py`); `makeY` (Explore), the kit's `Trace` and `MiniTrace` defaults, and
every Library and Review plot go through it, and no second rule is left in the tree. The reference bar
is **logarithmic**, a tick per decade, computed once per page from every card's peak: on a linear bar
every sub-mV family of a page whose largest is 100 mV sits at zero, which is D5's flat line moved into
the bar. `MiniTrace` no longer clamps; smoke measures that no trace leaves its plot box on the Atlas,
the Family page and the Review inspector.

**Q-X2.3** Should the Family page's **shape sketch** be dropped and the real waveform fetched?

**A: yes, fetch the real waveform for the member cards.** A member card that does not show the
member's waveform is not worth its space on a page whose job is looking at every member. The cost is
a payload-size question, to be measured and reported, not a design one.

**Implemented by prompt `C`.** `members[].trace` / `removed[].trace` on the family read, at the
exemplar's resolution (~120 points). Largest family (F-30, 79 members): 41 KB → 130 KB, warm read
~0.27 s → ~0.35 s. Not decimated; `library.py::MEMBER_TRACE_PX` is the knob if a family ever makes
the read slow.

**Q-R1.1** Review's `[-0.44, 0.44]`: data-driven per candidate, or per queue, or a settings key?

**A: follows Q-X2.1** — per-candidate measured, reference bar for the shared scale. One rule across
Review, Library and Explore; that is the whole point of making it a cluster prompt.

**Implemented by prompt `C`.** `Y_MV` / `THUMB_Y` deleted; the Shape card's bar is the queue's shared
scale (every candidate's peak by the same measure as the Library's).

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

**Implemented by prompt `B` (2026-09-23, `reports/B-units-and-amplitude.md`).** The unit is recorded on the
data — `recordings.units` / `units_note`, and a `units` key both manifest writers now always emit — and the bridge
converts to mV at one seam (`webui/server/corpus.py::display_channel`; the core keeps `load_native`, the stored
samples). For 38 of 38 seed-store spans the amplitude the app prints now equals the store's own mV peak-to-peak to
1e-4 mV. **Not every file is volts:** M2_aug fs1/fs2, M2_concat and Mushroom_260720 are V; **L_LM_Jul_26_J is mV**
(998.2 × the Mushroom excerpt it contains); **Fig2A, M1, M100, M101_t, MJu26a and M4 could not be verified and are
recorded as undeclared** — the pages say "unit undeclared" instead of "mV", and the researcher declares each in
Settings › Datasets. Fig2A is 67 % of the Library, so most Atlas cards wait on that one declaration. Two things
found, both for round 3: **L_LM hands the core mV** where detect5 expects V (any web-UI chain on it reads 1000x
large; no such run exists yet), and the §2b slope note is **verified** — `max_slope_raw` is V/s with `fs` applied
once (338/338 events at 10 Hz).

**Q-X2.8 (new, from prompt `B`) — should the core convert L_LM (and any future mV file) to volts on load?** The
core's loaders read stored samples; for a millivolt recording the drop detector gets mV where it expects V.
Converting in `execution._load_signal` from `recordings.units` fixes it, but changes the core's input for that
recording and the meaning of its step-cache entries — a decision, not a default.

**Q-X2.5 (Q11 of round 2) — what happens to `drop_motifs10`?**

**A (2026-09-23): filter now, re-run later. The floor becomes a per-dataset editable setting in
Settings, defaulting to 0.1 mV for every dataset for now** — every recording may have its own noise
floor, and the floor decides which detected motifs are viable, so it belongs beside the dataset, not in
a constant.

**The researcher challenged the measurement, and was half right — the correction matters more than the
original claim.** The challenge: a `drop_motifs10` span may cover only the steepest part of the slope
rather than max-to-min, so peak-to-peak over the *stored span* would understate the event. Measured
over 400 spans (median stored width **31 samples**):

| Window | p25 | median | p75 | under 0.1 mV |
|---|---|---|---|---|
| stored span | 0.108 | 0.301 | 1.034 | **24.0 %** |
| ± 1x width | 0.313 | 0.662 | 2.409 | 6.8 % |
| ± 3x width | 0.545 | 0.985 | 2.841 | 0.8 % |
| ± 10x width | 1.000 | 1.557 | 4.431 | 0.0 % |

Widening does clear the floor — 72 % of sub-floor spans clear it at ±1x, 97 % at ±3x — **but that is
not evidence the events are bigger.** A wider window catches baseline drift and neighbouring events, so
peak-to-peak grows whatever is there. The test that settles it is the detector's own measurement, and
`Plots/drop_motifs10/motifs/motifs.csv` carries it:

    drop_depth_mv    median 0.219 mV   p25 0.069   31.6 % under 0.1 mV
    peak_to_peak_mv  median 0.290 mV   p25 0.099   25.2 % under 0.1 mV
    snippet width median 29 samples · onset->trough median 7 samples

The detector's own depths agree with the stored-span measurement, and the snippet is already ~4x the
onset-to-trough extent. **So the span is not too narrow; the events really are that small.**

**The actual cause is the floor, and the answer to "where is the 0.1 mV coming from":** it comes from
`detect5.py:927`, which names the *instrument* floor in a comment. **`drop_motifs10` never used it.**
Every one of its 3,511 rows carries `floor_rule = derived_3x_amplitude_MAD` with `depth_floor_mv`
median **0.0127 mV** — a floor derived from the residual's own noise, ~8x below the instrument floor.
And the residual was small because the run was aggressively detrended:

| | slope_sigma | detrend_window_s (median) | segment_seconds (median) | depth median | sub-floor |
|---|---|---|---|---|---|
| `drop_motifs5` (seed, 410) | 8.0 flat | 240.0 | 4.8 | **9.06 mV** | **0.0 %** |
| `drop_motifs10` (3,511) | 8.0, down to 1.5 | **7.9** | **0.2** | **0.219 mV** | **31.6 %** |

A 7.9 s detrend window at 1 Hz is ~8 samples: it removes everything slower than ~8 s, which is most of
a real drop. **`drop_motifs10` is a deliberately permissive micro-scale sweep** — four passes
(`base`/`fine`/`micro`/`sens`), eight `scale_band`s whose medians run 0.115 mV (band 1) to 1.813 mV
(band 7) — not a broken run. It is answering a different question at a different scale, and the units
bug made its output indistinguishable from the seed store's.

**Consequence for the filter:** filtering on peak-to-peak over the Library's stored span is the wrong
measure. Filter on the **detector's own `drop_depth_mv`**, which means `motif_features` (Q-I1) has to
carry it — the Library imported only span indices and dropped every amplitude the detector computed.
`scale_band` and `is_pure` (2,960 of 3,511 pure) are the other two axes worth exposing.

**Q-X2.6 (new, not blocking): `rise_height_mv` is 0.000 for 85.8 % of `drop_motifs10`**, and
`signal_sign` is 1 for all 3,511 with the manifest's `inverted` pass false. Worth knowing before
anything is built on rise height.

---

## Morphology as data (I1, I2, L12, X3)

**Q-I1** Should width, amplitude, depth, recovery time and slope be **stored per motif**, against
Library §4.4?

**A: yes — change §4.4 additively.** A `motif_features` table keyed by **content hash**, recomputable
from the snippet, never authoritative. §4.4's real fear is a stale measurement outliving its waveform;
a content-hash key kills that. This is a versioned change to the spec and must be recorded as one.

**Implemented by prompt `D` (2026-09-23, `reports/D-event-features.md`).** Recorded as a versioned amendment in `LIBRARY_STORAGE.md` §3.4 (decision L8b). Long rather than wide (`content_hash, fs, source, feature, value`), so a new feature block adds rows, not columns; `fs` is in the key because the hash is fs-blind and every duration is not. Measured on the snippet the hash was taken over, from the detector's own onset / trough, so the stored depth equals the detector's (410 / 410 seed events). Caveat recorded: the hash is amplitude-blind, so two same-shape motifs of different depth would share a row — none of the 3,603 live members do.

**Q-I2** Is "drop width vs recovery time" a plot, or a stored feature set?

**A: a stored feature set** you can group, filter and sort the whole Library by. The plot falls out of
it. Follows from Q-I1.

**Implemented by prompt `D`** as far as the data: `motif_features` holds every measure per motif, with the detector's `drop_depth_mv` beside ours (34.3 % of `drop_motifs10`'s 3,189 imported entries fall under 0.1 mV on it; 0 of the seed store's 410) — the number Q-X2.5's floor filter needs. The Library filter / sort / group UI over it is not built (Q-X2.5 / Q-X2.7 own it).

**Q-I3 (new, answered 2026-09-23)** How do the new statistics reach the app?

**A: as new analysis blocks**, through the existing generalised wiring structure — the researcher's own
judgement, and it is the right one: a block is typed, costed, cached, testable, re-runnable and
composable into a chain, which a page-local computation is none of. The measures wanted, named:
**inter-spike interval, amplitude, drop width, drop depth, recovery time, rose plots**, "etc." — the
"etc." is itself a question (Q-B1, round 2).

**Implemented by prompt `D`**: `interrogation.event_shape`, `interrogation.intervals`, `preprocessing.invert`, stage `interrogation`, the first two `interrogation` templates. The rose is `gradients.rose_data` unchanged, per event in the shape block's meta and per sequence in Interrogation › Sequence.

**Q-X3** What populates a spike train?

**A: a Review gesture first, then a detector.** But **not only** a Review gesture — **Explore must be
able to send a span for review carrying a `train` flag, a note and its morphology**, at the moment the
researcher spots it while reading a dataset. That is the friction Q-0.4 puts first. The human gesture
produces the ground truth; the proximity-grouping detector is then scored against it. A detector
without the gesture has nothing to check it against.

**Prompt `D` built the analysis side, not the gesture**: a stored sequence can be measured and rosed (Interrogation › Sequence), and a detector's events measured and timed in one chain. The Review / Explore `train` gesture and the proximity-grouping detector are still to build.

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


---

## Round 2, answered 2026-09-23

**Q11 — `drop_motifs10`.** Answered in Q-X2.5 above (filter now, re-run later; the floor becomes a
per-dataset Settings value defaulting to 0.1 mV).

**Q12 — is a "spike" the same as a "drop"?**

**A: neither, quite — and the vocabulary was the problem.** The researcher's correction, verbatim in
substance: *"spike train" / "spike events" is misleading; my professor and I use these to mean **motif
trains**, applicable to sequences of spikes AND sequences of drops.* So:

- **A train is a sequence of motifs of either polarity.** Name it a **motif train**, never a spike train.
- **Drops and spikes are genuinely different events**, not one phenomenon under two names. The
  `drop_motifs` detector detects drops only (`signal_sign = 1` on all 3,511 rows of `drop_motifs10`).
- **Feature blocks are polarity-neutral**: drop depth / rise height / recovery for a drop, and
  amplitude / return time / spike height for a spike, are the same measurements about opposite signs.
  One block with polarity handled internally, not two.
- **A separate spike *detector* is a real gap**, and there is a promising cheap route: the researcher
  has already experimented with running the drop-motif algorithm on an **inverted signal** to find
  spikes, with some success. **An `preprocessing.invert` block is worth building** — it makes every
  existing drop detector a spike detector for one block's work. `drop_motifs10`'s manifest already has
  an `inverted` pass flag (set false), so the idea is partly plumbed in the core.

**Q13 — the measure list, and the rose plot.**

**A, first part: one block outputs all the shape measures**, so a researcher does not run three blocks
to characterise one event. Named explicitly: **duration** (onset → recovery), **half width** (the
standard electrophysiology FWHM), **event width** (onset → trough for a drop, onset → peak for a
spike), plus depth/height, rise height/return time, and recovery time. Splitting is allowed if it is
structurally better, but the default is one block.

**A, second part: the rose plot is (iii) — max slope.** Not circadian. The angular variable is the
**maximum slope of each event**, and the plot compares **slopes across the events in a sequence**. This
already exists in the drop-motif plotting code in this repo and **must be reused, not reinvented**
(CLAUDE.md). `motifs.csv` already carries `max_slope_raw` and `onset_slope_raw` per event.

**"etc." means:** any other per-event feature extraction, and any other cross-event comparison within a
sequence of the rose plot's kind. **The named techniques are a generalisable template for later ones**
— so the prompt's job is as much to establish the shape as to deliver the six measures.

**Chain integration is an open design question the researcher wants to think about further.** The case:
given a train of motifs, apply a width block to it, *and simultaneously* pass the same motifs to an
ISI block. For now **assume each analysis type is its own chain with its own intent**; do not build
fan-out. Flagged as **Q-B-CHAIN**, round 3.

**Q14 — where features attach.**

**A: (c), with the split stated precisely.** The block consumes any `SpanSet` so it composes into any
chain, **and** writes to `motif_features` (content-hash keyed) for any span that has a hash.
**Per-event features are stored on the motif** (each motif carries its own `max_slope`, depth, width).
**Cross-event comparison results exist only in the analysis run** and are never stored. This is what
lets a researcher assemble a `SpanSet` of Library motifs **that are not from the same sequence**, run a
feature comparison over it, and see the result — the comparison is a view, the features are the data.

**Q15 — is `window_sets` next?** **A: yes, immediately after `B`.**

**Q16 — which Review gaps.**

**A: (i) classes, (iii) the rediscovery prior verdict, and (iv) the "sorted by score" contradiction are
in. (ii) the extract-events editor gets its OWN prompt**, later, with concept-page design and another
round of questions before implementation — the 30 waiting sequences are not critical. Recorded as the
researcher's view: extracting events from a sequence is properly the job of a *detection algorithm* in
Analyse, and the editor's real value is for sequences that a detector found automatically.

**Q17 — dataset naming.** **A: all of it.** Derive what is derivable (channels, fs, duration) by
default, then editable columns in Settings › Datasets: **species, organism id, experiment date,
condition, display name** — where a filled display name replaces the file name **across the whole
site** — **and notes** (e.g. "recorded outside", "in a Faraday cage"). Eleven rows to fill by hand is
acceptable, and the editor is wanted permanently for future datasets.

---

## Round 3 — open

**Q-B-CHAIN** How do per-event analysis blocks compose? The researcher wants, from one train of
motifs, a width analysis *and* an ISI analysis without running the chain twice. Today a chain is
linear. Options: a fan-out node; a block that emits several feature sets; or accept one chain per
intent (the assumption prompt `D` is built on). Needs the researcher's thinking, not a default.

**Q-X2.7** Per-dataset noise floors (Q11) — where does the floor apply? Only as a Library/Atlas display
filter, or does it also gate what a detector block writes at run time? The first is a view, the second
changes what lands in the database.

**Q-D2b** `drop_motifs10`'s `scale_band` (eight bands, medians 0.115 to 1.813 mV) and `is_pure`
(2,960 / 3,511) are richer than a single floor. Should the Library expose them as filters?


---

## Round 3, answered 2026-09-24

**Q18 — Fig2A's unit.** **A: volts.** Declared through the UI. The researcher also ran the project-mode
start and the `--real` feature backfill. Verified in the real database 2026-09-24: `recordings.units`
= **54 V, 5 mV, 71 undeclared**; `motif_features` = **71,980 values over 3,599 hashes** (50,386 from
`interrogation.event_shape`, 21,594 from the detector). The 71 undeclared are M1/M100/M101_t/MJu26a
and the held-out M4 — none of which the Library draws from.

**Q19 — the fabricated features.** **[CLOSED — fixup-e, run 2026-09-30, `reports/E-aggregate-stops-fabricating.md`. The three constants are deleted; every value on the page is read from the store's slope measures or from `interrogation.event_shape` (GET `…/families/{key}/shape`, from `motif_features` by content hash or measured on the store snippet); never-recovered and a drop's rise time are null, counted and explained, never 0. `rise_time_frac` is a parameter of the shape block (default 0.1, the 10–90 % rise time), `rise_time_s` a column and a stored measure, NaN for a drop. The size of the error is tabulated in the report: half_width read 0.43× the measured FWHM (median), the browser's recovery read 0 s on 305 of 410 seed events.]** **A: new prompt (`E`).** *Clarification the researcher asked for:*
the fabrication is **not** in the event-shape block, which measures honestly. It is in the
**Interrogation › Aggregate page** (`#/analyse/interrogation/block/2`), whose
`api/interrogation.ts::featureOf` returns `half_width_s = duration x 0.84`, `rise_s = duration x 0.31`
and `isi_s = duration x 4.2` — constants multiplied by duration and drawn as if measured. Prompt `D`
now measures all of them for real; `E` replaces the fabrication with those measurements.

**Also decided:** **rise time joins the shape block as a parameter, null for detected drop events.**
It is the one measure `D` left unmeasured. Null rather than zero, so a drop's missing rise is
distinguishable from a rise of no height.

**Q20 — convert mV recordings to volts in the core (Q-X2.8).** **A: yes, convert, and record it.**
`execution._load_signal` converts from `recordings.units`, so the core always receives volts and one
recording is not permanently special. This changes the core's input for `L_LM_Jul_26_J` and the
meaning of any L_LM step-cache entries — the prompt that does it must say so and invalidate them.

**Q21 — where the per-dataset noise floor applies.** **A: a VIEW filter only.** The Library hides
sub-floor motifs; the rows stay. A run-time gate would silently change what lands in the database and
leave no way to tell later whether a detector found nothing or was gagged.

**Q22 — `scale_band` and `is_pure` as Library filters.** **A: yes — but `scale_band` cannot be used
as its index, and this corrects what was recommended in round 3.**

Measured 2026-09-24: **`scale_band` is a WITHIN-SPAN octave index of `fall_duration_s`, not a global
scale.** `Pipelines/drop_motifs/passes6.py:368 scale_bands()` splits *one span's* motifs into octaves
from that span's own shortest fall, and only when the spread exceeds `MAX_UNSPLIT_RATIO`. So band 1
means a median fall of **174 s** in span `id001` and **4 s** in span `id021` — a 43x difference under
the same label. Filtering "band 1" across the Library would pool unrelated timescales.

| band | n | median fall | range | median depth | pure |
|---|---|---|---|---|---|
| 0 | 352 | 3.0 s | 0.1–114 | 0.272 mV | 95 % |
| 1 | 1455 | 0.6 s | 0.2–252 | 0.115 mV | 92 % |
| 2 | 823 | 1.0 s | 0.4–311 | 0.208 mV | 72 % |
| 3 | 150 | 13.0 s | 0.8–284 | 0.483 mV | 69 % |
| 4 | 457 | 1.0 s | 0.5–241 | 0.682 mV | 89 % |
| 5 | 247 | 0.8 s | 0.3–356 | 0.163 mV | 66 % |
| 7 | 27 | 73.0 s | 3.0–155 | 1.813 mV | 93 % |

**So: filter on `fall_duration_s` directly** — globally comparable, and `motif_features` now carries
it for every entry — and show the band's *label* (its duration range, in `scale_band_labels`) as
provenance on a card rather than as a filter axis. **`is_pure` is a genuine global flag** (2,960 of
3,511) and becomes a filter as recommended.

**Q23 — order.** **[BUILT — fixup-f, 2026-10-01: the six columns exist on Settings › Datasets (the `datasets` table, keyed by `source_file`) and the display name replaces the file name across the site through one seam. Filling them on the real database is the researcher's; nothing was written to it. `reports/F-datasets-and-naming.md`.]** **A: dataset naming first**, done by the researcher. *Clarification asked for:* it
means both — the editable columns (`species`, `organism id`, `experiment date`, `condition`,
`display name`, `notes`) have to be built before they can be filled, and the display name then
replaces the file name across the site. Derived fields (channels, fs, duration) come for free.

---

## Round 4 — new symptoms from use, 2026-09-24

Nine from the researcher, with screenshots. Recorded here; ownership assigned as prompts are written.

| # | Symptom | Owner |
|---|---|---|
| U1 | **[FIXED — fixup-g, 2026-09-30.** Two things under one word. The context card's zigzag WAS a bug: each envelope bucket's min and max, meant to sit on nearly the same x, were drawn a whole "second" apart because the bridge discarded `t`; the trace now carries its axis and, at the card's measured width, the 660-sample context is served raw (`data-decimated=0`). The Shape card's staircase is NOT a bug: 60 samples at 1 Hz, undecimated, and it now dots every sample so the rate is legible rather than read as a rendering fault; nothing is smoothed. With source resolution on (Q24) the same 60 s is drawn from the 10 Hz parent — 600 samples, a curve. `reports/G-review-axis-and-resolution.md`.**] **Review plots are pixelated** — the trace renders as a time-quantised staircase, not a curve | `G` |
| U2 | **[FIXED — fixup-g, 2026-09-30.** The detection was right; the trace was on a compressed axis (Round 4 findings, below). Measured in the browser: before, the drop was drawn at 2266 s (0.629 h) against a band at 2333–2393 s; after, at 2383 s (0.662 h), inside the band, the true sample. `webui/smoke.py` now measures this on every run (`feature_in_band`). Review also shifts a legacy span-relative row through `absolute_bounds` now — a no-op on the migrated database, belt and braces for a restored backup. `reports/G-review-axis-and-resolution.md`.**] **Review's candidate highlight misses the actual event** — item 102 on Mushroom CH14 highlights a flat stretch at ~0.656 h while the obvious drop is at ~0.626 h. **Suspected the same legacy span-relative/absolute defect wiring 01 found, in a fourth reader nobody shifted** | `G`, P0 if confirmed |
| U3 | **[FIXED — fixup-g, 2026-09-30.** The client sliced envelope POINTS as though they were seconds. The bridge now serves the context over exactly the padding asked for (`pad_s`) and the client slices by time; measured left/right padding for item 102 is 287/287 px at ±30 s, 459/459 at ±120 s, 522/522 at ±300 s, and a 600 s candidate whose band used to run off the right edge (0 px) is centred. `band_centred` in the smoke gate. `reports/G-review-axis-and-resolution.md`.**] **Review padding is one-sided** — `±30/±120/±300 s` should pad both sides of the candidate | `G` |
| U4 | **Explore needs fine span adjustment** — the slider cannot move a span by seconds or minutes; it needs typed/stepped controls | `I` |
| U5 | **[FIXED — fixup-f, 2026-10-01.** The segmented tab strip (nine of eleven recordings visible at 1440 px, five at 900 px, no scroll) is a picker at the start of the card header: bounded width, a scrolling menu, each row the dataset's name with its file and channel count. `reports/F-datasets-and-naming.md` §5.**]** **Settings › Channels & events: the recording tab list runs off the page** with no scroll affordance | `F` |
| U6 | **[CLOSED — fixup-j, 2026-10-01.** The implementation diverged from the paper in four places; it is now a port of the authors' own MATLAB, tested against that MATLAB, with every sample analysed and the funnel on the block page. It finds 17 of 20 known synthetic events — and on M2_aug CH0 marks 91 % of the *interesting* windows and 86 % of the *not interesting* ones, so it is faithful and not selective here. `reports/J-dehshibi-vs-the-paper.md`.**] **The Dehshibi template still does not read as detecting anything.** Prompt `A` fixed its black image; the thumbnails are now legible but the researcher cannot tell what the algorithm is doing or whether it works. **Wants it checked against the paper**, by an agent reading the paper alongside the code | `J` — its own prompt, and it needs the paper |
| U7 | **[CLOSED — fixup-h, 2026-10-02, `reports/H-blocks-show-their-work.md` §2: a feature block (`spanset → spanset`) leads with a histogram per measure, the rose and the interval statistics; its per-event table is folded away, and what was not measured stays on the face of each card. `interrogation.intervals`, whose whole output was a ten-column table, is plotted.]** **Analysis blocks answer with tables where they should answer with pictures.** The whole point of the UI is to avoid large tables. The researcher supplied an exemplar figure (the drop-motif "how a fall becomes an angle" plate: anatomy of one event, the same construction across the depth range, the rose beside it) | `H` |
| U8 | **[CLOSED — fixup-h, 2026-10-02, `reports/H-blocks-show-their-work.md` §4: every SpanSet-emitting block draws `kit/Slideshow.tsx` — real samples at their own times, per-panel y with a scale bar, the red `[2 falls]` impurity flag counted by sample range, selection shared with the plot above, read-only with one action (*Send to Review*, which creates a real queue). The Interrogation member grid is the same component on the seed store.]** **Anything that outputs a SpanSet should offer a slideshow of its spans** on the block page | `H` |
| U9 | **[CLOSED — fixup-h, 2026-10-02, `reports/H-blocks-show-their-work.md` §1, §7: seven type views and twelve modifiers draw all 36 blocks from their type signature; `GenericProcess` and its caption are deleted, zero blocks resolve to a generic view, and `tests/test_block_standard.py` fails if one does.]** **Every existing analysis block needs a bespoke process view** — a drawing of what that block did, not a generic payload dump | `H` |

U7, U8 and U9 are one theme: **a block must show its work.** They are the "legibility" pillar of
`CLAUDE.md`'s priority order, and the exemplar figure the researcher supplied is the standard to hit.


---

## Round 4, answered 2026-09-28

**Q24 — read the higher-resolution parent in Review?** **A: yes, with the toggle defaulted ON.** Few
datasets are decimated subsets of a higher-resolution parent, so it is an edge case and the cost of
defaulting it on is small. (Recording 385 is a 10:1 decimation of `L_LM_Jul_26_J_raw` at 10 Hz;
Review has been judging event shape on a tenth of the available detail.) Owner: `G`.

**Q25 — the 115 legacy rows: fix the reader or the rows?** **A: both, in that order — and the
migration is its own prompt, run FIRST.** `M-migrate-legacy-detections.md` written 2026-09-28.
`absolute_bounds` and its readers stay regardless: a database restored from an old backup still holds
relative rows. **`M` ran 2026-09-28** (`reports/M-migrate-legacy-detections.md`): the re-run audit
matched the 2026-09-24 table to the row (56 / 18 / 8 runs, 115 rows, none ambiguous, none mixed);
backup `DATA/db/backups/20260928-211406-fixup-m.sqlite` passed `integrity_check` first; the rewrite is
`audit_log` id 482; a second pass plans 0 rows; and re-running each run's own recipe on its span
reproduces the migrated rows exactly for 114 of 115 (the last is a whole-span catalogue window, now
exactly its span). The migration lives in `init_db()`, so a restored backup migrates itself on open.
`G` is still to add Review's `absolute_bounds` call.

**U5** folds into the dataset-naming prompt `F` (same page). **U6** — the researcher has the Dehshibi
PDF locally and will attach it with `J`; **`J` is to include a grilling session of its own** to
confirm the site's implementation against the paper before changing anything.

---

## Round 4 findings — measured, 2026-09-28

### U2 is NOT a wrong detection. The highlight is right; the trace is on a compressed x-axis.

`webui/server/review.py:111` `_trace` discards `env["t"]` and returns only `env["v"]`, on a docstring
contract that the x axis is implied. The client honours it literally — `parts.tsx:70-75` treats
`context.values` as one value per second. But `decimate.envelope` returns **fewer, non-uniformly
spaced** points once a span exceeds `2 x px`. Reproduced exactly for item 102:

    context [2033, 2693) = 660 samples -> envelope at px=320 -> 440 points
    client draws 440 points at 1/s from t0=2033 -> 0.5647 h .. 0.6867 h   [screenshot: 0.565 .. 0.687]
    the drop is DRAWN at 0.6294 h  [screenshot: ~0.626 h]
    its TRUE position is 0.6619 h  -- INSIDE the highlight 0.6481-0.6647 h

Everything right of `t0` is compressed by 440/660 = two thirds. The band is drawn in true absolute
seconds, so **band and trace are on two different x-axes.** The detector was right all along.

**U1's context-card zigzag is the same root cause**: each envelope bucket emits its min *and* max,
meant to land on the same x and draw as a vertical tick; with `t` discarded they sit a full second
apart, so every bucket becomes a diagonal.

**U3 is probably the same.** `parts.tsx:71` computes `off = CONTEXT_PAD_MAX - pad` and slices
*envelope points* as though they were seconds; at +/-120 s that strips 180 of 440 from each end. The
padding is not one-sided by design — it is computed against the wrong array length.

**U1's Shape card is NOT a bug.** `SHAPE_PX = 60` over a 60-sample candidate at fs = 1 Hz returns 60
raw samples undecimated, ~6 px between vertices at stroke width 2. Real data resolution; value
quantisation ruled out (smallest non-zero step 2.2e-9 V, no plateaus). **Latent:** `SHAPE_PX` never
sees the card's width, so a 3600 s candidate gets 120 points over ~380 px; `CONTEXT_PX = 320` likewise
discards a third of the samples that would fit on an ~816 px plot.

**U1, U2 and U3 are largely one fix**: carry `t`, make the axis real, size decimation to the width.

### U10 (new) — Resolve spans and Spike shape are the same block wearing two names

**[CLOSED — fixup-e. The second upstream is now `event-shape` = `interrogation.event_shape`, a block whose features are measured by different code from the slope block's and which declares only what the core measures; `spike-shape` is read as an alias so old links open the shape block. Every navigation between the three pages goes through `draft.ts::interrogationHref`, which carries the family AND the upstream — the ribbon chip that dropped it was the revert.]**

`api/interrogation.ts:142,156`: `getSlopeBlock` and `getAggregateBlock` both call
`familyAndMembers(familyId)` — the same data — and swap only `UPSTREAMS[upstream]` and
`CHAIN_SPIKE`/`CHAIN_SLOPE`, i.e. the labels. The features list claims Spike shape declares
"amplitude, half-width, rise, decay"; the members and their features are the slope block's either way.
The revert the researcher saw is `useUpstreamQuery()` defaulting to slope when the query param is not
carried. **Same class as Q19's fabrication, so `E` owns it.**

### U11 (new) — the members-overlaid plot is drawn in too narrow a time window

**[CLOSED — fixup-e. Source settings › context padding defaults to *the stored context* (what the store kept around each event: median ≈ 1 min each side, up to 46 min), with ± 60 / 300 / 1000 s and the proportional options beside it; the Source page's overlay of id001 now runs −679 … +863 s and shows the sharkfin's rise. The overlays draw the store's own samples (nothing held past a snippet's end), are taller (340 px), and their y is `charts/domain.ts::measuredDomain` over the traces drawn, so the 40 mV headroom over 25 mV data is gone. The synthetic medoid curve drawn over real members is removed.]**

The app's overlay spans **-20 to +40 s** from onset and the members look flat; the researcher's
matplotlib plate spans **-1000 to +1500 s** and the sharkfin shape is obvious. The window comes from
Source settings `context padding = +/- 0.5 x span`, far too narrow for a short event to show the rise
that precedes the drop. Plus excess y headroom (axis to 40 mV, data to ~25) and an aspect that should
be narrower and taller. **The time window is the main cause, not the aspect ratio.**

### U12 (new) — the bridge reports a Ctrl-C on first start with no input

`webui/run_server.py` installs no SIGINT/SIGBREAK handler and calls `uvicorn.run()` directly. Prompt
`D` also recorded Windows asyncio `WinError 10022` teardown lines on a first smoke run that did not
recur. **Not diagnosed — needs reproduction, not a guess.**

### U13 (new) — global search is not wired

The header's "Search spans, runs, families" box is on every page and does nothing. Future prompt.

---

## Round 5 — what wave 1 left, 2026-10-01

`E` and `G` both ran clean on 2026-09-30 and both closed every row they were given (U1/U2/U3,
U10/U11, Q19, `03` I1/I4, `07` R1). What follows is what their reports left behind: two decisions
that are the researcher's, one infrastructure fix that is nobody's ticket and blocks clean parallel
waves, and a handful of items with an owner already.

### Q26 — the sharkfin has no recovery, and that is a research decision, not a rendering one

> **[SUPERSEDED, 2026-10-02 — read "Q26, REVISED" below first.** The researcher's reframe plus a
> measurement on the real channel shows a sharkfin **does** recover: 121 of 154 reach half recovery
> by their next onset, at a median 199 s against a stored post-context of 121 s. The premise of
> everything in this entry and in "Q26, measured" — that recovery does not exist for the
> morphology — is an artifact of the measurement window and is withdrawn. The three options below
> are kept because the reasoning is the record of how the error was found.**]

**The most important thing either report found.** `E` measured it on the data:

| store | events | no `recovery_time_s` | no `fwhm_s` |
|---|---|---|---|
| the seed store `drop_motifs5` (the 16 families Interrogation reads) | 410 | **170 (41 %)** | 170 |
| the real Library `motif_features` | 3,599 | **1,238 (34 %)** | 1,238 |

And it is **all-or-nothing by family**, which is the tell: id001 17/17, id003 16/16, id021 14/14,
id024 40/40, id026 2/2, id028 19/19, id029 48/48 never recover — against id008, id033, id385 where
every event does. Those are the **sharkfin** spans against the **trough** spans. On a sharkfin the
trace falls and stays low until the next rise begins, so it never re-crosses its half level: under
`D`'s definition (recovery at 50 % of depth, within 10 event widths, never past the next window)
*recovery and FWHM do not exist for that morphology*, and the researcher's default family is one of
them.

The page is honest about it now — it draws nothing and says why — but "honest and empty" is not the
answer for the one statistic the supervisor reads. **Three options, and the researcher picks:**

1. **Measure a sharkfin's recovery to the next onset** instead of to a level. It is the natural
   reading of "how long until the next event" for a morphology that does not return, and `D` already
   measures `interval_before_s` / `interval_after_s`, so the number exists — it would be a
   *different measure under a different name*, not a redefinition of recovery.
2. **Lower `recovery_frac`** (it is already a parameter). Cheap, but it does not help: the sharkfin
   does not return to *any* fraction before the next rise. Measurable, not recommended.
3. **Accept it and say so on the page** — recovery is a trough-morphology measure, and the
   sharkfin's regularity is carried by `interval` instead. This is what the app does today.

The width-vs-recovery relationship the researcher named in round 2 exists on troughs and `E` drew it:
**id010, β 0.28 [0.16–0.40], R² 0.23, n 83**, against a null β of 0.25 — so it does *not* clear its
null. That is worth knowing before any more is built on it.

#### Q26, measured — 2026-10-02, before asking the researcher to decide

> **[Its measurements are sound but its window is wrong: every number here is bounded by the
> STORED SNIPPET. See "Q26, REVISED" below.]**

The three options above were written from `E`'s counts. Two of their premises were **assertions**, so
`scripts/q26_recovery_probe.py` measured them on all 410 seed events
(`webui/screenshots/fixup/Q26/recovery-probe.json`). Both survive, but the number splits into **two
different failures that were being reported as one**:

| | n | post-context stored | … in event widths | how far back up it got, median | p90 |
|---|---|---|---|---|---|
| **sharkfin, no recovery** | **156** | 118 s | 1.62 | **0.7 % of depth** | 15.5 % |
| **trough, no recovery** | **14** | 94 s | 2.33 | **35.2 %** | 47.2 % |
| trough, recovered | 240 | 43 s | 4.00 | 86.6 % | 108 % |

1. **No sharkfin recovers — 156 of 156, not one.** It is not a data pattern, it is what the morphology
   is: the trace falls and sits on the floor until the next rise. Q26's "all of it sharkfin" is
   **92 %** (156 of 170), not all; the other 14 are troughs and are a *different* problem (below).
2. **Option 2 is dead, and now measurably.** Lowering `recovery_frac` rescues 53 of 170 at 0.1, 17 at
   0.2, 12 at 0.25. Worse, those 53 would report *"climbed back a tenth of the way"* in a column named
   recovery — a smaller lie than the old browser's 0 s, but the same kind.
3. **The `recovery_max_mult = 10` cap is innocent.** 167 of the 170 are bounded by the **end of the
   stored snippet**, not by the ten-width cap — and letting the search run to the end of the whole
   snippet changes the count by **one event** (53 → 53 at 0.1; one event reaches 0.5). So neither
   bound is what is stopping these.
4. **The 14 troughs are a near-miss, not a floor.** Eight of them reached 0.35–0.48 — climbing back and
   cut off just under the line, with a median 2.3 widths of post-context against 4.0 for the troughs
   that do recover. `id022_r1_1055945` has **3 s** of post-context after a 58 s fall (0.1 widths): it
   was never measurable. That is a storage question (`future/N-event-extent.md`), not a definition one.
5. **Option 1 has its data.** `interval_after_s` exists for 160 of the 170 (the other 10 are the last
   event in their span): median **525 s**, p10 81 s, p90 5834 s — a median **6.2×** the event's own fall.

**So Q26 is three decisions, not one.** They are independent and the first is the one that matters:

- **Q26a — is any statistic ever reported across both morphologies?** If the supervisor reads one
  recovery distribution for the corpus, a column that is 100 % null for one morphology makes it
  silently a trough-only statistic. If everything is reported split by morphology, the nulls are
  correct and option 3 is the answer.
- **Q26b — what goes in a sharkfin's box?** `time_to_next_onset` under its own name (option 1,
  data above), or nothing (option 3). **Never** a relabelled `recovery_time_s`.
- **Q26c — is 48 % recovered "not recovered"?** A one-column suggestion: store
  `max_recovery_frac` beside `recovery_time_s`, so a null is self-explaining — 0.007 for a sharkfin
  that never moved, 0.48 for a trough that ran out of recording. It separates the two populations in
  the data instead of in a footnote, and it is the number the probe already computes.

#### Q26, REVISED — 2026-10-02, the researcher's reframe, measured: a sharkfin DOES recover

**The researcher's hypothesis:** a sharkfin is not rise-then-fall. Every sharkfin sequence begins with a
drop, so what is being called one event is a **trough whose slow rise back up is its recovery** — and
the detector has attributed that rise to the *next* fall as its precursor (`up_region_start_idx`).

**It is right, and both my probes above were measuring an artifact.**
`scripts/q26_sharkfin_recovery.py` searches from the trough to the **next event's onset** on the real
channel (read-only, `mode=ro` + `mmap_mode='r'`, raw mV by `recordings.units`) instead of to the end of
the stored snippet:

| | n | reach 50 % recovered | reach 90 % | half-recovery | … in its own fall widths | stored post-context |
|---|---|---|---|---|---|---|
| **sharkfin** | 154 | **121** | 113 | **199 s** | 1.71 | 121 s |
| trough | 254 | 247 | 219 | 16 s | 1.32 | 44 s |

**The stored snippet ends at a median 121 s; the recovery happens at a median 199 s.** That is the whole
of the "0 of 156". And of the 33 sharkfins that still did not reach half, **32 were cut off by this
probe's own 20-fall-width bound, not by the next onset** (`frac_max` median 0.0, searched a median
601 s; 26 of the 33 are id024, whose recovery is slower than that). **Exactly one of 154 genuinely
failed to recover before its next onset.**

So the earlier entry's "no sharkfin recovers — it is what the morphology is" is **withdrawn**. It was
an artifact of the measurement window, twice over.

**What is still a real difference — timing, not existence.** The recovered fraction of depth at
quarter / half / three-quarters of the way to the next onset:

| | 25 % | 50 % | 75 % |
|---|---|---|---|
| **sharkfin** | **−0.04** | **−0.01** | 0.45 |
| trough | 0.63 | 0.88 | 0.99 |

A sharkfin sits on its floor — and drifts slightly **lower**, p10 −0.36 — for roughly half to
two-thirds of the interval, then climbs. A trough is most of the way back by the quarter point. That
plateau is the sharkfin's real distinguishing feature and **nothing in the repo measures it.**

**Two second-order findings, both load-bearing:**

1. **The detrend window is shorter than the recovery on two families.** id029's is 110 s against a 40 s
   half-recovery (19 of 48 events flagged), id024's 780 s against 476 s (10 of 38). So even with a
   longer stored snippet, the **stored detrended values have part of the recovery subtracted out**.
   Recovery has to be measured on the parent trace, or with a detrend window set from the recovery
   scale rather than the fall scale. This is why the probe above deliberately did not detrend — and it
   is also the caveat on it: some of what it measured as recovery could be slow baseline drift. That is
   the one thing still worth measuring before any of this is built on.
2. **The detector's trough is not the bottom of the excursion.** The trace keeps drifting down after it
   (median −0.04 of depth by the quarter point). `trough_idx` marks the end of the *fast fall*. That
   affects `drop_depth_mv` and where a recovery clock should start.

**What this does to Q26a–c.** Q26b is answered: a sharkfin's box holds *recovery*, measured properly —
not `interval_after_s` under another name. Q26a drops in urgency, because the column is no longer 100 %
null for one morphology, but the question stands for any figure drawn before this is fixed. Q26c
(`max_recovery_frac`) is still worth storing, now as the diagnostic that would have caught this in the
first place: a null beside a `frac_max` of 0.009 is a floor, beside 0.48 it is a cut-off window.

**And it opens the real question, which is the researcher's, not mine:**

- **Q26d — does the slow rise belong to the event before it or the event after it?** The detector has
  it as the *next* fall's precursor (`up_region_start_idx`, and `choose_morphology` is literally "is
  each fall preceded by its own substantial rise"). The researcher's reading is that it is the
  *previous* fall's recovery. **Both cannot be true of the same samples.** Whichever it is, one event's
  extent is currently wrong, every sharkfin's `precursor_height_mv` and the previous event's
  `recovery_time_s` are the same climb counted once in the wrong column, and the sharkfin/trough
  discriminator rests on the answer.

That is not a UI question and it is not a fixup. It is `future/N-event-extent.md`, and it is now the
first thing in it: redefining a sharkfin's extent re-hashes its Library rows.

### Q27 — the Aggregate page's null says "matched random windows · 200×" and is a seeded jitter

**[CLOSED — fixup-h, 2026-10-02, `reports/H-blocks-show-their-work.md` §6.** Both nulls deleted, not relabelled: the scatter's jitter, the
histograms' summed uniforms, the method selector, the null-β tile, and the toolbar chip's claim on all three
Interrogation pages (it now reads *no null*). The page says once, on its face, that nothing on it is tested
against chance. Building P10 is `future/R-interrogation-null.md`.**]**

`E` §8.1. The null **β** is now honestly recomputed from the points drawn, but the points behind it
are a jitter of the data, not 200 matched random windows, and the label still claims they are. It is
the last unearned claim on a page this stage has just spent two prompts making honest.

**Relabel or build?** Relabelling is a line. Building the real null (P10's machinery) is page-wide
and would be prompt `H`'s or its own. Recommend **relabel now, build later** — a wrong label on a
page that has just been cleaned is worse than a missing feature.

### The infrastructure fix neither prompt owned: `run_server.py --dist`

**[DONE 2026-10-01.** `run_server.py --dist DIR` (env `WEBUI_DIST`), threaded to the `Runtime(client_dist=…)` that already existed. Two traps pinned by `tests/test_webui_run_server_dist.py`: a relative `--dist` is made absolute **before** `Runtime.setup()` chdirs to the repo root (otherwise it would silently name the repo's own `client/dist`, which exists, so the mistake would serve a real-looking stale bundle rather than failing); and a `--dist` that is not a directory is refused like a busy port, rather than falling through to `app.py`'s JSON note and starting a bridge that looks alive and serves no app. A bridge on a private build announces it — `CLIENT = … (a private build, not the shared client/dist)` in the banner, and `client_dist` in `/api/runtime`. Verified end to end: a probe bundle served at `/`, the shared default unchanged.** The account below is kept because it is why the flag exists.]**

Both wave-1 agents needed a private client build and **neither could have one**. `Runtime(client_dist=…)`
exists (`webui/server/runtime.py:63,71`) and `run_server.py` does not expose it, so there is one
shared `webui/client/dist` and whoever builds last owns it. What actually happened:

- `E` built the shared dist three times (13:33, 13:37, 13:45), **compiling `G`'s uncommitted sources
  into it** each time (`E` §8.6);
- `G` had been using that dist as its *pre-change* client for the before/after evidence; when it
  changed underneath, `G` had to build the old client from `faaefca` in a scratch directory with a
  temporary `node_modules` junction (`G` §10) — a junction, in this repo, on the week of the
  `git worktree remove` data loss;
- `G` could not run `npm run build` at all for most of the run, because `tsc -b` was red on `E`'s
  in-flight Interrogation files and the script is `tsc -b && vite build`. It served
  `npx vite build --outDir <scratch>` instead and ran the real script at the end.

None of that corrupted anything and both gates passed, but it is luck rather than design, and
**wave 2 runs two agents again**. The fix is about four lines: an `--dist` argument passed to
`Runtime(client_dist=…)`. It is a no-decision change and it should land **before** `F` and `J` start,
not inside either of them.

Two things follow for every future parallel wave, and both prompts in wave 2 carry them:

- **build to your own `--outDir` and serve it with `--dist`; never touch `webui/client/dist`;**
- **`npm run build` is a shared gate** — it type-checks the whole tree, so the other agent's in-flight
  errors will block it. Run it for the gate, at the end, and use `npx vite build --outDir …` to get a
  bundle to serve meanwhile. Say in your report if the other agent's files were red while you ran it.

### Reassigned, with an owner

| item | from | owner |
|---|---|---|
| **[CLOSED — fixup-k, 2026-10-02, `reports/K-slope-anatomy-figure.md`: every mark is the store's — the detector's onset and trough samples, the sample `gradients.fall_gradients` found steepest (`max_slope_idx`, new, served as `steepest_offset`), and the snippet's own height at each. `eventMarks` is deleted, the window follows Source settings › context padding, a mark the store did not measure is not drawn and is named on the card, and smoke measures the drawn marks against the payload. On the 410 seed events the steepest sample is a median 5 % into the fall, not 50 %; 372 are in the first quarter.]** **The Slope page's anatomy figure still draws its chord, tangent and "steepest" marker from `fixtures/interrogation.ts::eventMarks`** (steepest = duration / 2) over a real trace, and opens 10 s before the onset whatever the padding says. **The same class as the fabrication `E` just removed, on a figure instead of a number** | `E` §8.2 | ~~`H`~~ → **`K`**, done. `H` still owns the figure's visual language |
| **[CLOSED — fixup-h, 2026-10-02, `reports/H-blocks-show-their-work.md` §9: the medoid is drawn in its own panel on its own samples with a scale bar, not stretched across the candidate — the bridge serves it no time axis (and, live, serves no medoid at all today).]** The Shape card's medoid overlay is index-stretched across the candidate's duration (unchanged semantics; a medoid carrying its own `t` would now be honoured) | `G` §11 | `H`, done |
| **[CLOSED — fixup-f, 2026-10-01: one-based won, through `channel_name`. The M2 electrode names are already one-based, saved Discovery sessions store channel names, and Explore and Review already printed it; Settings › Datasets, the import modal, the scoreboard and Interrogation no longer print the raw index, and the stored index and file (`recordings.channel = 2 · CH2.npy`) are shown beside the name. `reports/F-datasets-and-naming.md` §4.]** **`channel_name` says `CH3` for `recordings.channel = 2`** (`Working/discovery/channels.py:30`, `CH{channel+1}`) and Settings › Datasets prints the raw index as `CH2`. One convention must win | `G` §10 | **`F`** — it owns Settings › Datasets |
| Coherence `r` in the other-channels popover is still not computed — it now says so instead of throwing a TypeError on a `null` | `G` §11 | `07-review.md`, the Review *behaviour* prompt |
| **[CLOSED — fixup-h, 2026-10-02: `Working/interrogation/intervals.py::kendall_trend` behind `POST /api/interrogation/trend`; the timeline prints τ, p and n per recording for whichever measure is plotted, and a lane that cannot be tested says why. `TIMELINE_TREND` is deleted.]** Fixture τ per recording (`TIMELINE_TREND`) is keyed by fixture recording names; a live recording prints "n N · no trend test", which is honest and useless. A Kendall τ from the core is a two-line route | `E` §8.3 | `H`, done |
| `motif_features` predates `rise_time_s`, so the route measures it per request. `--only-missing` would store 3,599 nulls (every stored event is a drop); `RULE_VERSION` in `Working/library/features.py` does not mention `rise_time_frac` and should, when a spike store is first backfilled | `E` §8.4 | the Library prompt |
| `discovery.runs--default` fails in smoke on **both** the pre-change and post-change bridges (missing `browser-trace svg`; `E` measured it settling in 4.4 s against a 900 ms allowance under load) — **pre-existing, and now the fifth standing smoke failure beside the four Settings registration states** | `E` §9, `G` §9 | `05-discovery.md` |

### Still open from earlier rounds

**Q-B-CHAIN** (fan-out: one train of motifs → a width analysis *and* an ISI analysis without running
the chain twice) is unanswered and now blocks nothing that is written. **Q-X2.7** is answered by Q21.
**U4** (fine span adjustment) has no prompt. **U12** (the phantom Ctrl-C) is undiagnosed. **U13**
(global search) has no prompt.

---

## Round 6 — `J`, the Dehshibi detector against the paper, 2026-10-01 — answered and built

The grilling round `J` was told to open with. Read and measured first; nothing changed. The
evidence, and the clause-by-clause table, are in `reports/J-dehshibi-vs-the-paper.md`; the plots are
`webui/screenshots/fixup/J/grilling-asis-vs-trial-*.png` (look at `-720000` first).

**What it is.** The implementation diverges from the paper, in four places that each change the
output. The template and the monolith agree exactly on five real spans — they share the faulty code.

1. The wavelet transform keeps only the real part of an analytic transform (`phi.imag` is exactly 0).
2. It has no boundary handling, so the wrap-around jump is the largest event in every window; the
   scalogram is a bowl, Ω a bathtub, and the "spikes" a staircase of nested spans from sample 5.
3. Slicing keeps only the time the signal spends below the midpoint of the span's own histogram.
   **That is the 87 %** — 87.3 % in no chunk at all, 0.0 % in a too-short one. On 0–18 h it is 99.8 %.
4. Algorithm 3 pairs by value, as the paper literally prints, and returns regions that end before
   they start — every region, in 5 of 10 four-hour runs.

With 1, 2 and 4 removed in a scratch trial, Ω peaks on the events a reader can see. Algorithms 2–4
then still confirm few of them (1, 2, 0, 0 spikes over four 3000 s windows; an 8 mV sharkfin gets Ω's
one dominant peak and no spike). The paper reports 76 % true-positive on its own data.

### Q28 — fix it to the paper, or stop here?

The table is the deliverable and it exists. Fixing 1, 2 and 4 is three small changes to one core file
with a red test each, and makes the detector *the paper's*. It does not make it a good detector for
these recordings — the trial says it will still miss most of what the drop detectors find.
**Recommended: fix them.** A detector labelled Dehshibi that is not Dehshibi is the kind of lie
`CLAUDE.md` ranks below ugliness, and the comparison against the other detectors (the prompt's
question 3) means nothing until it is the real method.

### Q29 — what should slicing do on a span?

The paper slices a whole recording once and then works on 3000 s pieces; it never says the high-state
time is thrown away, and its Slice2 would not survive this code's reading. Three options:
**(a) recommended — default `slice_by_state` off and analyse the span in fixed windows** (3000 s,
the paper's own figure scale; the per-scale normalisation and the 5 % ε are relative to the window,
so window length is the method's real parameter), with the histogram slicing kept as an option;
(b) keep the slicing but analyse both sides of every transition; (c) leave it and explain the grey.

### Q30 — the nested spikes

Algorithm 4 as printed emits `(6, 85) (6, 205) (6, 325) …` when several envelope regions fall in one
wavelet region. Faithful, and useless on a page. **Recommended: keep the paper's output in `meta`
for the funnel, and emit merged spans** (one per wavelet region, ending at the last envelope end) as
the SpanSet, said in words on the block. Or keep it literal and let the page show the staircase.

### Q31 — may I fetch the authors' MATLAB code?

The paper cites it: Zenodo, `10.5281/zenodo.3997031`. It settles the two readings the text cannot —
whether the envelopes are splines through the peaks of |z| or of L itself (`envelope(L, 60, 'peak')`),
and what "intersection point" is in Algorithm 4 — and confirms the scale set and the padding. It is a
download, so it needs a yes. Without it those rows stay `reading` and the code's choices stand.

### Q32 — sample counts or seconds?

`n_p = 60`, 30 and 60 are seconds in the paper and samples in the code; on the 10 Hz recordings the
defaults mean 6 s, 3 s and 6 s. **Recommended: the blocks take seconds and convert with `fs`.**
It changes two blocks' parameter names, so an old saved recipe needs the old names honoured.

### On the Morse constants

No case for exposing β, γ or η yet: the basis was never the problem, the transform around it was.
Revisit only if Q28 is yes and the fixed Ω still reads wrong.

### Round 6, answered 2026-10-01

**Q28–Q32: yes to every recommendation.** Fix to the paper; slicing off by default with fixed
3000 s windows; merged spans as the SpanSet with the literal output in `meta`; the blocks take
seconds; **Q31: yes, fetch the authors' code.**

**The authors' MATLAB was fetched and read** (Zenodo `10.5281/zenodo.3997031`,
`FungiSpikeDetectionAnalysis.rar`, 91 MB, kept outside the repo; only the `.m` files were extracted).
It is not the printed paper. Where they differ:

| | printed paper | authors' code (`imMain.m` and the `i*.m` it calls) |
|---|---|---|
| slicing | chunks "enclosed between" transitions | `pulsesep` start points are **cut points**: the recording is partitioned and nothing is discarded (`iSplitSignal`) |
| transform | Eq. (2) | `cwt(chunk, Fs)` — MATLAB's default Morse(3, 60), L1, 10 voices per octave, reflection padding; modulus |
| Eq. (3) | `η(κ − min)/max` | `1 + fix(240·(κ − min)/max(κ − min))`, per frequency — the repo's denominator was right |
| Ω | the sum over scales | `method = 2`: the sum over **only the frequencies ≤ a quarter of the frequency range** — Step 1's "sum of the scales below the threshold" |
| Alg. 1 extrema | prominence ε | `findpeaks` with prominence ε **and** minimum distance 60 **and** minimum width 30; each region's start is then moved earlier by up to 30 samples |
| Alg. 2 | regions longer than 30; spline extrema | regions of **60 or more**; `islocalmin` / `islocalmax`, no spline |
| envelope | analytic signal, `\|z\|` | `envelope(del2(chunk), 60, 'peak')` — spline envelopes of **L itself**; no analytic signal anywhere |
| Alg. 3 pairing | minimum i with maximum j, in lockstep | first maximum dropped, minima and maxima sorted together and paired consecutively, as in Alg. 1 |
| Alg. 3 threshold | mean − std | mean − std if std < mean, else the mean |
| Alg. 4 | three subset cases over C ∪ D → F_s, F_p; drop < 60 | uses **C only**; each wavelet region is widened to the hull of the envelope regions it intersects, overlapping results merged; no F_p, no length filter. With no intersection at all, the wavelet regions are returned as they are |
| pseudo-spikes | F_p | D is computed and never used |

### Q33 — which is the detector: the printed algorithms or the authors' code? — **A: the authors' code** (2026-10-01)

They cannot both be implemented as one block chain. **Recommended: the authors' code**, with every
departure from the print in the report's table. It is what produced the paper's figures and its 76 %;
it never emits a region that ends before it starts; and its Algorithm 4 is already the merged-span
output Q30 asked for.

**Also confirmed before building (2026-10-01):** three blocks, the same three types; the third takes
ANY per-sample `Scores`, so another summation — or a `Signal → Scores` block replacing the first two
stages — drops in front of it unchanged. The band of the scalogram that is summed is a fraction of
its rows (an `Encoding` has no frequency axis). The existing STFT block cannot replace the transform
as it stands: one column per hop, not per sample.

### What `J` leaves open

- **Q34 — [A, 2026-10-02: keep it for now, untuned.]** **keep the Dehshibi detector in the comparison set?** It is now a faithful baseline and a
  weak one on these recordings (spans cover 53 % of M2_aug CH0's labelled time). Keep as a baseline,
  tune (`epsilon_factor`, `min_separation_s`, `window_s`), or retire from the detect tab?
- The funnel strips do not share the x-axis of the plot above them — `H`.


---

## Round 7 — the `H` grilling, 2026-10-02 — answered, and `H` written from it

The researcher asked to be grilled before `H` was written. Three rounds, two sub-agent surveys, and
**two of my own recommendations corrected by measurement** (Q3 below, and the 50 s window). The
result is `H-blocks-show-their-work.md`. Recorded here because the prompt is the implementation and
this is the reasoning.

### The framing the researcher set, which is not what I proposed

I opened by proposing the nine drawing rules of `Pipelines/drop_motifs/drawing_rules.py` as the
standard. **That was rejected, and the replacement is better:** the thesis figure rules are for
thesis figures. What the UI needs is

> **a plot rule per data TYPE, and a plot rule per block CONVERSION (input→output), so that current
> and future algorithms all have an expected view.**

Some thesis rules do carry over (a drop must look like a drop; no resampling on the settings page —
though resampling *is* fine for a chain thumbnail; colour-by-time only where order is the subject).
The rest do not.

**Scope boundary set by the researcher:** `H` is the UI's analysis pages. **How plots come out on
generated reports is a separate prompt** — which must *inherit* this standard rather than invent a
second one, or the app re-earns prompt `C`'s four-padding-rules problem in a new place.

### Q9 — the organising principle — **A: as recommended**

> The OUTPUT type decides what kind of picture. The INPUT type decides what one "thing" is in it, and
> whether there is a before/after to show.

7 × 7 collapses to seven views plus twelve modifiers. It matches where the code already is: both
dispatch tables are keyed on interchange type (`serialize.py:378`, `Renderer.tsx:32`).

### Q10 — the seven minimums — **A: as drafted, with a thumbnail defined for each**

| Output | n | settings page | thumbnail (the researcher's own spec) |
|---|---|---|---|
| Signal | 6 | before/after overlaid, input grey beneath; **both axes, left and right, when the scale changes** (normalise, baseline removal) | the overlaid plot |
| Scores | 3 | curve + source signal above on the same x + value histogram + threshold | the scores plot alone |
| SpanSet | 11 | slideshow + every span on the full trace + duration distribution | every span marked on the full trace |
| Encoding | 12 | 3 sampled images, scan the rest, real-range colour bar, no-data grey | 3 images side by side across the thumbnail bar |
| WindowSet | 2 | windows on the time axis + feature matrix as a heatmap | heatmap stretched to width, **on the source signal's visual time axis**, grey where no window |
| Grouping | 1 | clusters over time + sizes + one exemplar per cluster | heatmap distribution of clusters |
| Model | 1 | accuracy per class as bars | low priority; a card is acceptable |

### Q11 — thumbnail vs settings page — **A: (b)**

Thumbnail = the shape only; settings page = the shape plus the evidence. **One component,
interaction as a flag.** For sets too large to plot (window-matrix features over many windows), the
thumbnail buckets them into discrete chunks — the pattern of the detection-density ribbon on Explore
(`explore/Overview.tsx:143`) and the Library.

### Q12 — "no resampling" vs a 2.6 M-sample channel — **A: (a)**

Never interpolate; **decimate by min/max envelope** when samples exceed pixels, and say so on the
card. Nothing is invented and a one-sample spike still reaches full height. Pair with `G`'s dotting
rule so real resolution is distinguishable from drawn resolution.

### Q13 — where thumbnails render — **A: (b)** browser SVG, non-interactive. matplotlib stays for
multi-panel export plates. A thumbnail is drawn most often and must be cheapest; and one component
with interaction off is what keeps Q11(b) from drifting into two pictures of one thing.

### Q14 — enforcement — **A: (c)** written in `BLOCK_INTEGRATION.md` + a test that no block falls
through to "no bespoke process view yet" + **rule 9 ported into the smoke gate** (a drawn trace
varies, nothing is flattened, no axis clips). Precedent: smoke already measures Review's band
containing its event (`G`) and non-overlapping axis labels (`A`); both caught real defects.

### Q15 — shared y or per-panel scale on small multiples — **A: (c)**

Per-panel measured domain **+ aspect lock + an explicit scale bar**. Not shared-y: the researcher's
own figures tried it and rejected it (`figures12b_s3.py:50-65`), because clustering is
scale-invariant — a 0.014 mV and a 0.39 mV motif can be siblings, so a shared axis draws most of a
family flat. The scale bar is what stops "legible" and "comparable" being a trade-off.

### Q16 — the slideshow's affordances — **A: the UI set, plus the impurity flag, plus the shuffle**

The researcher meant the **UI** one: "Each kept detection" on block 04 of `drop_motifs9`
(`analyse/demo/blocks/DetectionBlock.tsx:90`) — cards sorted by score/time/depth, paged, and
**click-to-centre in the plot above, bidirectionally.** It is **fixture-backed** (six hard-coded
detections, `demo data` chip), so this is **wiring, not design**.

Add from its matplotlib ancestor (`Plots/drop_motifs5/id385_contact.png`): **a panel whose window
holds more than one fall turns red and says `[2 falls]`** — an automatic "suspect" marker the UI
version lost. Build on `SmallMultiples` (`kit/plots.tsx:534`), which already has the pager and adds a
seeded resample shuffle. Read-only; the one action is *send to Review*.

The rationale for panels over an overlay, from `figures5.py:7`: *"an overlay hid the defect — a
window holding three spikes drawn on top of four others that also hold three looks like a busy
family; it takes seeing the panels side by side to notice that every one of them is a train."* That
is U7 in one sentence, written by the researcher about their own data.

### Q17 — **A: confirmed, `H` draws only.** The stored extent **is** the Library's identity (the
content hash covers the whole snippet, `event_store.py:571`), so redefining it re-hashes 3,603 rows.
That is `M`-class migration work and never belongs in a visual-language prompt. → `N-event-extent.md`.

### Q18 — mark a capped edge — **A: yes, behind an info icon**

`detect5.window_bounds`' morphology bracket loses to a scale-free `6 × fall` cap on **46 % of seed
events (left edge), 49 % of oyster**, and the row does not record which rule set its edge. Draw a
capped edge differently; count it behind the icon.

### Q19 — which frame to draw — **A: (c)**

Single event → the stored window (`E`'s default, correct). Sequence or overlay → the
`sequence_frames` rule (`drawing_rules.py:146`): back to **the previous event's trough**, capped at
14 falls. **Never `1.2 / 1.8` falls for a sharkfin** — its own author says so: *"an Oyster event is a
6 s fall on the end of a 55 s rise … a frame of 1.2 falls before the onset shows the last tenth of
that rise, which is a shoulder rather than a sharkfin."*

### Q20 — the modifier table — **A: as drafted.** Twelve rows, all 36 blocks, in `H` §"The twelve
modifiers". The two load-bearing rows: **spanset → spanset**, which inverts the rule (an
interrogation block outputs spans but the measures are the point), and **signal → windowset**, where
the two producers need different thumbnails because `sliding_windows` carries no features at all.

### Q21 — the text budget — **A: (b), with absence always visible**

Explanation behind an info icon, one short line on the face. **But an absence is never hidden:**
*"17 of 17 events have no recovery"* stays on the card, because that is the result, not commentary.
Hiding it would re-create by omission the fabrication `E` removed by invention.

### Q27 — the Aggregate page's null — **A: delete now, build later**

There are **two** fabricated nulls, not one. The scatter null (`AggregatePage.tsx:310`) multiplies
each real point by random factors three times; the histogram null (`:82`) is three summed uniforms
centred on the observed range. Both are labelled "matched windows" / "shuffled onsets" and cite
**P10**, which specifies *"matched random windows (200×) and shuffled onsets"* and is still
`ticketable now` — **specified, never built.**

Consequence worth keeping: the scatter null is the data with independent noise on x and y, so its
exponent is a **regression-diluted copy of the real one** and lands below it by construction. `E`'s
id010 result — **β 0.28 against a null of 0.25** — was therefore never a meaningful comparison; that
null can be neither cleared nor failed. `H` deletes both and the P10 claim; → `R-interrogation-null.md`.

---

## Round 7 corrections — two things I had wrong

Recorded because both were stated to the researcher as evidence before being measured.

**1. The "50 s window for a 0.7 s fall" is the wrong column.** `drawing_rules.py:51-66` uses it to
argue that drawing the whole stored snippet is a trap. Measured on disk: the stored Reishi snippet is
**3.10 s against a 0.725 s fall (4.3×), max 13.2 s** — not 50 s. The 50 s is
`passes9.DEFAULT_WINDOW_S`, the **sliding detection-pass window**, a different quantity stored in
separate `window_start_idx`/`window_end_idx` columns that exist only in `drop_motifs10/12a`.

**The repo has three different things that have been called "the window"**: the `detect5` bracket
(stored as `snippet_*`), the 50 s sliding pass window, and the figure frame. `drawing_rules.py`'s
rule-2 note conflates the first two. **Do not anchor a decision on that number.**

Consequence: I had recommended that rule 2 overrule `E`'s "whole stored context" default and that `H`
re-open `E`'s overlays. **Withdrawn.** `E`'s default is better supported than I said; `H` adds the
sequence frame beside it (Q19) rather than replacing it.

**2. `detect5` already does what the researcher asked for.** `window_bounds` (`detect5.py:507`) is
morphology-aware by design — sharkfin: its own preceding rise → the next rise; trough: previous
recovery → **its own recovery end**, with the stated reason that *"a trough spike's RECOVERY is an UP
run and is part of the motif, so a naive 'stop at the next UP run' would end the window at the bottom
of the trough and discard the right half of every event."* The researcher's "I want the drop and the
rise to recovery stored too" is the existing design. The failure is the `6 × fall` backstop (Q18),
not the rule.

### Measured, for whoever needs it later

Stored snippet against fall duration, by corpus:

| corpus · morphology | fs | n | snippet s | fall s | ratio |
|---|---|---|---|---|---|
| reishi_10hz · trough | 10 | 2194 | 3.10 | 0.725 | 4.3 |
| reishi_1hz · trough | 1 | 190 | 15.1 | 4.06 | 3.7 |
| oyster · sharkfin | 1 | 338 | 992 | 85.9 | 11.5 |
| oyster · trough | 1 | 416 | 271 | 28.0 | 9.7 |
| sp385 · sharkfin | 1 | 52 | 124 | 12.2 | 10.2 |

Seed store (410 events, 1 Hz): sharkfin median **240 s pre / 116 s post** (its own rise is in frame);
trough **42 s / 43 s** (roughly symmetric). That asymmetry is evidence the morphology rule works.

### Three findings `H` carries, which would otherwise bite silently

1. **Select spans by SAMPLE RANGE, never window index** (`DETECTION_AND_FIGURES.md` §5b, verbatim:
   *"Any UI panel showing 'the motifs in this window' must use the range."*). Measured undercounts:
   CH4 showed **11 where 21 exist**.
2. **30 of 1058 store rows have `len(detrended_mv) != snippet_end_idx - snippet_start_idx`** — slice
   by stored indices and those render as a 1-sample "fall".
3. **Overlapping snippet context is not double-counting**: 261 of 1058 snippet spans overlap while
   only 1 onset→trough pair does.

### What the survey found about the surface being fixed

- **31 of 36 blocks** fall through to `GenericProcess`, captioned *"this signature has no bespoke
  process view yet"* (`BlockPage.tsx:567`). Three bespoke views exist, selected by a hard-coded `if`
  chain on block name; two more unlock from a `meta` key.
- Blocks per output type: **Encoding 12, SpanSet 11, Signal 6, Scores 3, WindowSet 2, Grouping 1,
  Model 1.**
- **`analyse/` imports zero plot components from the kit.** `kit/plots.tsx` has thirteen, used by six
  other workspaces; `BlockPage.tsx:386` hand-rolls its own histogram. `Scatter`, `NullBand` and
  `SmallMultiples` have no caller outside the component gallery. **Wiring `analyse/` to the kit is
  most of `H`.**
- **Two rose implementations**: `RoseFan` (`analyse/EventFeatures.tsx:77`, real) and
  `interrogation/Rose.tsx:21` (prototype on fixtures, header says *"the kit has no polar plot"*).
- `interrogation.intervals`' entire visual output is a 10-column table. No plot of any kind.
- 47 per-block algorithm glyphs already exist (`analyse/glyphs.tsx:50`) — every block has bespoke
  artwork for *what it does*, none for *what it found*.

### The prompts Round 7 produced

| prompt | what |
|---|---|
| `H-blocks-show-their-work.md` | **run and reported 2026-10-02** (`reports/H-blocks-show-their-work.md`) — the standard and the views |
| `K-slope-anatomy-figure.md` | **run and reported 2026-10-02** (`reports/K-slope-anatomy-figure.md`) — Q8: the Slope page's fabricated anatomy figure |
| `N-event-extent.md` | stub — redefine extent + re-hash the Library (Q17) |
| `R-interrogation-null.md` | stub — build P10 properly (Q27) |
| `P-persist-recovery-index.md` | stub — `recovery_idx` is computed and discarded |
| `Q-extent-corrections.md` | stub — `motif_member_revision` is written and nothing calls it |
| the reports prompt | stub — inherits `H`'s standard, does not invent one |

---

## Round 8 — `H`, 2026-10-02 — not opened

`H` was told it could open its own grilling round and stop if anything was ambiguous or contradicted the prompt.
Nothing contradicted it, so it ran through. Where the prompt left a choice it took a default; the twelve are listed
in `reports/H-blocks-show-their-work.md` §9 and any of them can be overturned without touching the others. Three are worth a
researcher's eye, because they are findings rather than preferences:

1. **Only one of the three `scores → spanset` blocks has a cut to drag.** `detection.threshold` cuts at an
   absolute level; `summation_threshold` cuts by prominence relative to each window and `mp_motifs` takes the k
   lowest groups. The view is generalised to all three; the draggable line is drawn only where a level exists.
2. **No seed family spans two orders of magnitude.** The widest (id025) spans one, and the detector's
   `min_depth_frac = 0.10` makes that a ceiling. The per-panel-scale evidence is therefore on a 10× family; on it
   the old shared y drew two of ten members under 20 % of their panel.
3. **The Slope page computed its own rose angle** — `arctan(|slope| / 0.1 mV/s)` — against the core's reference
   of 1 mV/s, so one event read about −82° there and −35° on the Sequence page and the block page. With one rose
   the page shows the core's. If 0.1 mV/s was the intended convention, change `rose_reference_mv_s` in the core.

---

## Round 9 — the research prompts, 2026-10-03 — open

`docs/RESEARCH_READINESS.md` (research prompt 00) found that none of the six PRD questions can be answered
in the app today, and nine prompts were written from it (`README.md`, "Stage 5 — prompts from the readiness
pass"). Most need no decision. These do. **Each carries a recommended default, and the prompt that owns it
takes the default if the row is still open when it runs — except `W`, which must wait for Q40.** Answer
inline, as before.

### Q35 — how many surrogate draws does a template run get? — `T`

Today a template run across channels is scored against **one** phase-randomised realisation per channel
(scoreboard *"… / 3"*), while the session chip says *"200×"* and a seeded search really draws 200. Spec §9.4
says 200 for detection chains. Each draw costs a whole extra sweep. Options: (a) **N draws, N a Settings ›
Nulls key per run kind, default 20 for template runs and 200 for seed searches, every surface printing the
count that run drew**; (b) 200 everywhere, routed to SLURM past the ceiling; (c) keep 1 and make the chip
say so. **Recommend (a).** Whatever is chosen, a chip that names a count the run did not draw is the thing
being removed.

### Q36 — the null method Settings offers — `T`

Settings › Nulls names *circular shift*; `preprocessing.surrogate` implements `phase_randomize` and
`block_shuffle`. **Recommend: the page offers what the block implements** (wiring's note: a circular shift
is a degenerate null for a shape search). Adding the method to the block is a test and a day, if wanted.

### Q37 — the multiple-comparison correction behind the recommended cut — `T`

`cut_rule()` prints α = 0.01 and *"correction: none"* honestly; the Settings keys do not reach it. Options
per §9.4: none / Holm / Benjamini–Hochberg, applied per channel. **Recommend: wire the keys, default stays
`none`, and the sentence beside the cut is generated from the values used** — the choice itself is yours
and can change later without touching the prompt.

### Q38 — does an Analyse chain run carry a paired surrogate? — `T`

The PRD says every run carries a surrogate toggle, on by default; the toolbar says *"surrogate · not in
this slice"*. **Recommend: wire the toggle, default off in Analyse** (the tuning loop there is seconds,
and Discovery is where a claim is made), with the terminal row reading detected-versus-surrogate when it
is on. If you would rather Analyse stay null-free, say so and `T` makes the chip say exactly that.

### Q39 — when does a seed-search match become a Library member? — `V`

A `motif_member` is the identity of a motif, so an edge should not be written for a span a human has
rejected. Options: (a) **only matches with an accepting verdict (`interesting` / `seed`), on an explicit
*Add N matches to E-xxxx* act, with *include unjudged* as a flag that is off** (the Family page already
marks unjudged members as a proposal, not a finding); (b) every kept match, judged or not; (c) only on
promotion in Review. **Recommend (a).** The rejected matches keep their distance on the detection row, so
the accepted-versus-rejected distance distribution is still a query.

### Q40 — the cross-channel rule — `W` (blocking; `W` does not build until this is answered)

Three parts, all measured in `W` Part 1–2 before you need to answer:

- **Q40a — what is lag?** The Library's `classify_cross_channel_edges` cross-correlates two member
  *snippets* wherever in the recording each sits; Explore's route compares the **same absolute window** on
  two channels. Only the second measures a lag between electrodes. **Recommend: the same absolute window,
  always**; the Library action classifies a member against its sibling channels at the member's own time.
- **Q40b — the thresholds.** Today: artifact = |lag| ≤ 1 sample **and** r ≥ 0.99 (signed); propagation =
  |lag| ≤ 50 samples; else independent. On a real window five zero-lag pairs at |r| 0.70–0.82, three of
  them negative, all read *propagation*. Is a zero-lag pair at r = 0.8 contamination, propagation, or a
  fourth thing (*common-mode*)? Is an inverted copy (r = −0.99 at lag 0) an artifact? **Recommend: |r| for
  the artifact test, a zero-lag band from a Settings key, and a fourth bin `common_mode` for zero-lag pairs
  under the artifact line**, each printed with its rule. The PRD's three bins stay the vocabulary on the edge;
  the fourth is additive.
- **Q40c — a co-occurrence with no member.** When the sibling channel has no family member at that time, is
  the pair recorded (as an edge to nothing), counted on the family, or dropped? **Recommend: counted on the
  family as *co-occurrence without a member*, not written as an edge.**

#### Q40, measured — 2026-10-03 (W Parts 1–2, read-only; scripts, `part2_pairs.csv` and the scatter in `webui/screenshots/fixup/W/`)

**Part 1, synthetic (60-sample biphasic pulse, fs 1):**

| case | Explore (same absolute window) | Library (each member's own snippet) |
|---|---|---|
| +5 offset, no noise | lag +5, r 1.00, propagation | lag 0, r 1.00, **artifact** |
| +5 offset, noise sd 0.02 | lag +5, r 0.95, propagation | lag 0, r 0.989, propagation |
| +1 h, no noise | lag +299 / +3600 (window-dependent), independent | lag 0, r 1.00, **artifact** |

The Library path's lag is only the difference in where the two snippets were cut — it cannot see an hour
from a sample. It recovers +5 only when both spans are the same absolute samples, i.e. Explore's
computation. Unequal snippet lengths are resampled to a common length (120 vs 80 → lag 0, r 0.88).
**The propagation bin has no r floor**: a window with no event on B returned lag −26, r 0.16 → propagation.

**Part 2, real:** 300 `interesting` windows on M2_aug (298 of 600 samples), each against its 15 siblings
= **4,500 pairs**: artifact 12 · propagation 2,219 · independent 2,269.

| |r| at |lag| ≤ 1 (1,517 pairs) | r > 0 | r < 0 | today's bin |
|---|---|---|---|
| < 0.5 | 55 | 33 | all propagation |
| 0.5–0.7 | 183 | 174 | all propagation |
| 0.7–0.9 | 367 | 340 | all propagation |
| 0.9–0.99 | 202 | 146 | all propagation |
| ≥ 0.99 | 12 | 5 | 12 artifact, 5 (the negative ones) propagation |

**1,412 pairs** sit at |lag| ≤ 1 with 0.5 ≤ |r| < 0.99, every one called propagation. Lag ±1 is almost
entirely negative r (184 of 185). Non-zero |lag| median 105 samples, max 1,377; 407 of the independent
pairs have |lag| over half the window — possibly edge/drift effects of full-mode correlation (inferred,
not tested). Explore's lag is in strided samples against sample thresholds — harmless at stride 1, wrong
past 200,000-sample windows.

### Q41 — the manual-label vocabulary and the window-to-verdict rule — `AA`

The labels are 11,234 600-sample windows on a 200-sample stride: `interesting` 2,333 · `not_interesting`
8,773 · `artifact` 128. Options: (a) **binary — `interesting` vs `not_interesting`, `artifact` windows
excluded from training and counted**; (b) three classes including `artifact`; (c) the Review classes 1–9
(none stored yet, R3). Window-to-verdict rule: exact grid match when the chain's windows are 600 s on the
same stride; otherwise containment of the window's centre in a labelled window, as a parameter. **Recommend
(a) and the rule as stated.**

### Q42 — which classifier answers Q1, and what "generalises" means — `AB`

The PRD's classifier is the CNN on encodings; the template that runs today is `catalogue.classifier`, a
random forest on window-matrix features, local in seconds. Options: (a) **RF arms first — the paired
comparison with the same split, baseline and null, local, this month; the CNN arm as a second job on the
cluster once Jobs can bring a result back**; (b) CNN only, on the cluster, now. "Generalises": (i) the
time-blocked test block within the reviewed channels; (ii) channels never trained on; (iii) the held-out
recording, once, after the freeze. **Recommend (a) and all three of (i)–(iii) reported separately**, never
pooled.

### Q43 — which bands? — `Z`

No frequency-band list exists anywhere in Settings (the `band_*` keys on Analysis defaults are artifact
likelihood bands). `preprocessing.bandpass` defaults to 0.01–0.1 Hz. **Recommend: a Settings › Analysis
defaults list of named bands, seeded with three log-spaced bands below Nyquist for a 1 Hz recording, each
band naming its `low_hz`/`high_hz`**, editable, recorded in every band run's recipe. The bands themselves
are a research choice this round cannot make for you.

---

## Round 9, answered 2026-10-03 (grilling session, part 1)

**Q35 — A: (a).** N surrogate draws per run, N a Settings › Nulls key per run kind — **20 for template
runs, 200 for seed searches** — and every surface prints the count that run actually drew.

**Q36 — A: the page offers what the block implements** (`phase_randomize`, `block_shuffle`); *circular
shift* is dropped. **The researcher's follow-up, and it is right for one of the two methods:** *if a motif
sits wholly inside a piece that is merely moved, won't the detector still find it?* Yes —
`block_shuffle` cuts the signal into blocks of `block_s` seconds and deals them in a new order, so any
motif shorter than a block survives intact and a shape detector finds it again. **Block shuffle is a null
for *timing and order* (trains, intervals, sequences), not for *shape*.** `phase_randomize` keeps no
window intact: it keeps the signal's frequency content and scrambles every local shape, so it is the null
for "would this detector fire this often on a signal with the same spectrum and no real events". So:
**phase randomisation is the default null for every detection chain**; block shuffle stays on offer with
that sentence beside it and `block_s` as a visible Settings value. Found in passing: `block_s` defaults to
**1.0 s** (`preprocessing_surrogate.py`, `seeded_search.py:143`), which at 1 Hz is a one-sample block — a
sample shuffle that destroys spectrum *and* shape, i.e. neither null. `T` must make the default a block
length that means something (a multiple of the longest motif under test) or refuse `block_s · fs < 2`.

**Q37 — A: as recommended.** Wire the keys; default `none`; the sentence beside the cut is generated from
the values used.

**Q38 — A: as recommended.** The toggle is wired, **default off in Analyse**; when on, the terminal row
reads detected-versus-surrogate.

**Q39 — A: (a).** Only accepted matches (`interesting` / `seed`), on an explicit *Add N matches to
E-xxxx* act, *include unjudged* a flag that is off.

**Q40a — A: the same absolute window, always.** The researcher's words: *two motifs on sibling channels
that occur at time points a large amount apart can no longer be considered lag.* Measured above: the
Library path returns lag 0 for events an hour apart.

**Q40c — A: as recommended.** Counted on the family as *co-occurrence without a member*, never written as
an edge.

## Round 9, answered 2026-10-03 (grilling session, part 2)

**Q40b — A: THREE bins, not four; common-mode folds into artifact.** The researcher's rule: *any events
on different electrodes at the exact same time are artifacts; anything with lag over 1 s is more likely a
real propagation through the mushroom* — and a sub-second propagation is out of reach at 1 Hz anyway; it
would need a dedicated study at a higher sampling rate. So the sign of r does not rescue a simultaneous
pair (an inverted copy at lag 0 is an artifact too); the sign is stored on the edge, not given a bin.
Sub-points (the lag unit, an r floor, the propagation ceiling) are Round 10 below.

**Q41 — A: binary, with labels from ANY human span and a containment rule** (the Q41 recommendation was
expanded into four answers):
- *The classes* — `interesting` (with `seed`, a subset of it) vs `not_interesting`; `artifact` excluded
  and counted (too few to learn: 128). The researcher already has models trained this way on the
  existing set (`MODELS/`: GADF, GASF, recurrence and fusion CNNs, and `catch22_rf_prelabeled`).
- *Which labels* — any human-labelled span of any length (the 600-sample set, the Excel catalogue, a span
  drawn in Review or Explore). Machine labels never enter the human store (PRD's one-way door).
- *Matching rule* — **a window takes a label only if it wholly CONTAINS at least one labelled span, and
  every span it wholly contains agrees.** Partially overlapped spans do not label it. The researcher's
  reason: an `interesting` span whose event sits at its far end must not label a window that misses the
  end. Windows containing spans that disagree are left out and counted. (Spans LONGER than the window
  are Round 10, Q-W1.)
- *Unlabelled is unlabelled* — time nobody labelled is never "not interesting"; excluded and counted.

**Q42 — A: both arms trained identically, only the label source differs** (that the existing models are
a reference line rather than an arm is proposed — Round 10, Q-W4). And the researcher's framing of Q1, recorded because it sharpens it: the
NEW model is trained on **machine labels — a window-matrix dendrogram clustering at a chosen cut**, whose
classes may be morphological (sharkfin / trough / drop / noise). Two yardsticks, **both used**:
- **(A) the primary comparison** — cluster classes translated to the human vocabulary (sharkfin / trough
  / drop → interesting, noise → not), both arms scored on windows neither saw, on each of exam (i) later
  time, (ii) unseen channels, (iii) the held-out recording once after the freeze — **reported separately,
  never pooled**. The translation table is fixed and recorded in the recipe **before** any test score
  exists. Stated caveat: (A) is marked in the manual arm's own language, so it is tilted toward it.
- **(B) validation** — the researcher labels a sample of windows **blind** in the cluster vocabulary;
  this scores the cluster arm on its own terms and checks the translation table.
- **The dendrogram cut is chosen on training windows only** (by eye, silhouette as a guide), frozen into
  the recipe, and refused a change once a test score exists.
- **Blind labelling in Review is LATER** (the Review-behaviour prompt, with classes R3), not `AB`.
  **First priority is training a model.**

**Q43 — A: as recommended** — a named band list in Settings › Analysis defaults, used as `Z`'s band scope
and as every bandpass block's presets; seeded ~0.001–0.01, 0.01–0.1, 0.1–0.5 Hz; editable; recorded in
each run's recipe. **The researcher also wants Q4 to cover wavelet decompositions** — Round 10, Q-W3.

**Q-Null-1 (from Q36) — block shuffle's block length — A: as recommended.** Default twice the longest
motif under test; refused under 2 samples; shown in Settings › Nulls.

**Standing instruction from the researcher (2026-10-03):** every question put to the researcher is
explained in simple terms first ("like I'm five"), then the options, then a recommendation. Recorded in
`CLAUDE.md`.

---

## Round 10 — the 2026-10-03 grilling, part 3 — open

Follow-ups from Round 9's answers, plus every older row still open. Each is asked in plain words in the
session; the short form is here.

- **Q-W1 — labels on spans longer than the window.** Under Q41's containment rule a window can only take a
  label from a span it wholly contains, so a 60 s window can never take the label of a 600-sample span.
  Proposed: inside a `not_interesting` span → `not_interesting` (nothing is anywhere in it); inside a longer
  `interesting` span → unlabelled (the event could be anywhere). And RQ1's first windows sit on the labels'
  own 600/200 grid.
- **Q-W2 — one clustering over the pooled training windows of all training channels** (not one per channel),
  so a cluster means the same thing everywhere.
- **Q-W3 — a wavelet-decomposition block for RQ4.** No block turns a wavelet decomposition back into a
  band-limited Signal. Proposed `preprocessing.wavelet_bands` (Signal → Signal, one stationary-wavelet level
  reconstructed; `pywt` 1.8.0 is already installed), offered as a second band source on `Z`'s band scope.
- **Q-W4 — the existing `MODELS/` as a reference line** on Results, scored on the same exams, labelled as
  trained differently — not one of the two arms.
- **Q-W5 — the Q40b sub-points:** lag threshold in seconds (1 s, so 10 samples at 10 Hz); an r floor below
  which a pair is `independent` whatever its lag (0.5); propagation ceiling (50 s, a Settings key).
- **Q-B-CHAIN** — still open (fan-out).
- **Q26c / Q26d** — `max_recovery_frac`; whose is the sharkfin's slow rise.
- **Rose reference** (Round 8 #3) — the core uses 1 mV/s, the old Slope page 0.1 mV/s; the thesis figures use
  the pooled median steepest slope (`Pipelines/drop_motifs/store11.py:175`), so the median event sits at 45°.
- **Q-L5** polar and cube plots; **Q-L6 / Q-E6** click a cluster to see its waveforms.

## Round 10, answered 2026-10-03 — every row above is closed

- **Q-W1 — A: as recommended, plus non-overlapping training windows.** Inside a `not_interesting` span →
  `not_interesting`; inside a longer `interesting` span → unlabelled. RQ1's windows sit on the labels'
  600/200 grid **but the training set is non-overlapping** (the researcher: it is better to train on
  non-overlapping windows): of any two overlapping windows only one is kept, so the set is a stride-600
  subset of the grid, the phase offset chosen to keep the most labelled windows, the dropped and the
  unlabelled both counted. Owner: `AA` (the window set), used by `AB`.
- **Q-W2 — A: as recommended.** One clustering over the pooled training windows of every training channel.
  The researcher's note: what is specific to the training data is the **mushroom** — training and exams (i)
  and (ii) are one organism; exam (iii), the held-out `M4`, is a different one. Owner: `AB`.
- **Q-W3 — A: yes, its own prompt** (`AC-wavelet-bands.md`). The decomposition yields several signals; the
  block's parameter chooses **which level goes on down the chain**, and its view shows every level. In
  `Z`'s band scope a wavelet level is a band.
- **Q-W4 — A: as recommended.** The existing `MODELS/` are a reference line on Results, not an arm.
- **Q-W5 — A: as recommended.** Lag in seconds; artifact |lag| ≤ 1 s and |r| ≥ 0.5 (either sign);
  propagation 1 s < |lag| ≤ 50 s and |r| ≥ 0.5; independent otherwise; all three numbers Settings keys.
  Owner: `W`.
- **Q-B-CHAIN — A: out of scope.** Branching chains is a new capability; one chain per intent, the step cache
  makes shared steps free. Revisit with **multivariate analysis** after the first research-question results
  (`docs/prompts/rq_roundB/`).
- **Q26d — A: the researcher's reading** — a sharkfin's slow rise is the previous event's recovery. Built in
  `future/N-event-extent.md` after the fixups (it re-hashes Library rows); until then RQ3 prefers troughs.
- **Q26c — A: yes**, `max_recovery_frac` stored beside `recovery_time_s` — `future/P-persist-recovery-index.md`.
- **Rose reference — A: the thesis rule, restricted to accepted motifs.** The 45° slope is the median
  steepest slope over **human-reviewed, accepted** Library motifs (so sharp noise and artifacts do not skew
  it), computed once and printed on every rose. Until enough accepted motifs exist the rose says which
  population its reference came from. Owner: the Library prompt (unwritten).
- **Q-L5 — A: dropped for this stage**; maybe research round B.
- **Q-L6 / Q-E6 — A: as recommended.** A click opens the cluster's members in place in the `H` slideshow,
  with *Open family page →*. Owner: the Library prompt (unwritten).

**The researcher's plan for after the fixups (2026-10-03):** about **18 research questions over about three
rounds** (A, B, C), each answered with the website *as it currently stands*, each round developing what
the site can do. Round A is the six PRD questions (`docs/prompts/rq_roundA/`); round B's notes are in
`docs/prompts/rq_roundB/`.

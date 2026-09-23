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

**Q19 — the fabricated features.** **A: new prompt (`E`).** *Clarification the researcher asked for:*
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

**Q23 — order.** **A: dataset naming first**, done by the researcher. *Clarification asked for:* it
means both — the editable columns (`species`, `organism id`, `experiment date`, `condition`,
`display name`, `notes`) have to be built before they can be filled, and the display name then
replaces the file name across the site. Derived fields (channels, fs, duration) come for free.

---

## Round 4 — new symptoms from use, 2026-09-24

Nine from the researcher, with screenshots. Recorded here; ownership assigned as prompts are written.

| # | Symptom | Owner |
|---|---|---|
| U1 | **Review plots are pixelated** — the trace renders as a time-quantised staircase, not a curve | `G` |
| U2 | **Review's candidate highlight misses the actual event** — item 102 on Mushroom CH14 highlights a flat stretch at ~0.656 h while the obvious drop is at ~0.626 h. **Suspected the same legacy span-relative/absolute defect wiring 01 found, in a fourth reader nobody shifted** | `G`, P0 if confirmed |
| U3 | **Review padding is one-sided** — `±30/±120/±300 s` should pad both sides of the candidate | `G` |
| U4 | **Explore needs fine span adjustment** — the slider cannot move a span by seconds or minutes; it needs typed/stepped controls | `I` |
| U5 | **Settings › Channels & events: the recording tab list runs off the page** with no scroll affordance | `F` |
| U6 | **The Dehshibi template still does not read as detecting anything.** Prompt `A` fixed its black image; the thumbnails are now legible but the researcher cannot tell what the algorithm is doing or whether it works. **Wants it checked against the paper**, by an agent reading the paper alongside the code | `J` — its own prompt, and it needs the paper |
| U7 | **Analysis blocks answer with tables where they should answer with pictures.** The whole point of the UI is to avoid large tables. The researcher supplied an exemplar figure (the drop-motif "how a fall becomes an angle" plate: anatomy of one event, the same construction across the depth range, the rose beside it) | `H` |
| U8 | **Anything that outputs a SpanSet should offer a slideshow of its spans** on the block page | `H` |
| U9 | **Every existing analysis block needs a bespoke process view** — a drawing of what that block did, not a generic payload dump | `H` |

U7, U8 and U9 are one theme: **a block must show its work.** They are the "legibility" pillar of
`CLAUDE.md`'s priority order, and the exemplar figure the researcher supplied is the standard to hit.

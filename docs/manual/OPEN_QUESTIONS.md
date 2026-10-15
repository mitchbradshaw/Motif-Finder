# Open questions from writing the manual

The writers who drafted `docs/manual/` (2026-10-15/16) read the code behind every block and
page. This file collects what they could not settle without you, and what they found that
looks wrong. Each question starts with what is at stake in plain words, then the options,
then a recommendation. Claims the writers could not check are also marked in the PDF itself
(orange, "[unverified]"), and counted on its title page.

Nothing here has been changed in the code: these are reports, not fixes.

## Read this first

Most of what follows is detail. These are the findings that matter most before 21 October,
in order:

1. **A calibration file escapes the sandbox** (confirmed): a sandboxed bridge can write
   `DATA/db/wm_calibration.json` into the real `DATA/` (see "Found while writing Jobs…").
2. **Screens that say something happened when it did not.** Explore's Save span toasts "span
   saved" for an in-memory demo write; Save template says "throwaway database copy" when it
   wrote the real one; the blind popover says the blind state is stored with every verdict,
   but it is not (E2), and model registration relies on it; Review shows a "6.1× null" that is
   a fixture number; the "demo data" chip shows on every live channel; Discovery shows
   simulated previews and timings; the Settings pages say values "travel into every recipe
   hash" (R1), and many saved settings are never read (N3, R2).
3. **The CNN block's default network scores everything 1.0** (C1), and its own test passes
   because of it.
4. **Saved matrix profiles overwrite each other**: the file name omits the span (see "Found
   while writing the matrix-profile family").
5. **Training data can leak into its own test**: no buffer between training and test windows
   (G1), clustering that sees test windows (G3), a classifier that ignores the blocked split
   (C2).
6. **The spike-train path you share with your supervisor**: interval statistics have no null
   yet (N1); Adamatzky words appear in random timing (I5); block shuffling can return the
   signal itself as its null (I1); one missing sample blanks a phase-randomised surrogate (I2);
   bursts collapse to one spike (N5).
7. **The Dehshibi template sums the right band only at 1 Hz** (W1).
8. **Two encoders may hang or crash on gaps** (S8, worked out from the code, unverified).

Resolved while the manual was being written, by work other sessions merged on 2026-10-16:
the spike block now takes its threshold in millivolts and hands on spikes rather than gaps
(O1, N2), and the cross-channel tooltip no longer claims tests it does not run.

**Left to write:** two screenshots in the Review chapter (`chapters/07-review.tex`), because
the smoke walk has no live state for a blind queue or a cluster. **Marked unverified:** 63
claims, shown in orange in the PDF.

**References to check:** these bibliography entries were written from the writers' own
knowledge rather than a source in the repository: `yeh2016matrix`, `law2019stumpy`,
`theiler1992testing`, `holt1996comparison`, `liu2008statistical`, `kimes2017statistical`,
`dehshibi2021electrical` (DOI), `anden2014deep`, `andreux2020kymatio`,
`malinowski2013onedsax` (no pages or DOI), `sun2014improvement` (authors given as "Sun and
others"), `madrid2019matrix` (no DOI), `wang2015imaging`, `eckmann1987recurrence`,
`richman2000physiological`, `breiman2001random`, `tan2019efficientnet`, `lubba2019catch22`,
`bandt2002permutation`, `pincus1991approximate`, `ward1963hierarchical`, `roberts2017cross`,
`rousseeuw1987silhouettes`, `azami2017refined` (no volume or pages). The orchestrator
checked them against what it knows and found nothing wrong, but a check against the papers
is worth a few minutes before the thesis cites the manual.

## Questions for you

### Filters and baselines (`preprocessing.bandpass`, `.highpass`, `.lowpass`, `.detrend`, `.beads`, `.wavelet_bands`, `.invert`)

**F1. Should the Butterworth filters switch to the more robust form?**
A filter can be stored as one long recipe (transfer-function form, `b, a`) or as a chain of
small steps (second-order sections). For very slow cut-offs on a fast recording, the long
recipe can pile up rounding errors, like doing a long sum on a cheap calculator. The default
slowest band, 0.001–0.01 Hz on 1 Hz data with an order-8 filter, is the riskiest case.
- (a) Switch `make_*_filter` in `Working/Detection/analysis/freq_analysis.py` to
  `butter(..., output="sos")` with `sosfiltfilt`.
- (b) Keep the current form and add a test of the frequency response at the default bands.
- (c) Leave it.

*Recommendation:* (a) and (b). The change is small, but it shifts outputs, so cached step
results would differ.

**F2. Should the filters refuse missing values loudly?**
One missing sample silently turns a whole filtered span into blanks. The wavelet-bands
block refuses such spans with a message; detrend and BEADS skip the gaps.
- (a) Refuse with a message.
- (b) Skip the gaps, as detrend does.
- (c) Leave it.

*Recommendation:* (a), which matches wavelet bands and the project's loud-failure rule.

### Orientation chapters (why, first session, core ideas, glossary)

**O1. ~~What spike threshold should the first session use?~~ Resolved by fixup-ak (merged
2026-10-16), with a smaller question left.** The spike block now takes `delta_mv` in
millivolts and converts it by the recording's declared unit, so the old trap (0.01 meaning
10 mV on a recording stored in volts) is gone; chapter 2 is rewritten to match. What remains:
the 1 mV default is a placeholder suited to M2's noise and fires on noisier channels (the
Block page's read-out turns amber below four times the span's noise), and a recording with no
declared unit is read as volts, so one actually stored in millivolts gets a threshold a
thousand times too small (the chain row says "read as volts"). *Recommendation:* declare the
unit of every registered recording; then the only tuning left is the noise level.

**O2. Who picks a family's exemplar?**
A family has a typical member the computer picks (the medoid) and a representative (the
exemplar). The manual needs to say who picks the exemplar: always a person, or a person or an
importer (an imported event-store entry seems to get its exemplar from the import).
*Recommendation:* confirm, and the `\unverified` marks in chapter 3 and the glossary come off.

**O3. Are "dataset" and "recording" the same thing in the app?**
The glossary says so, marked unverified. Confirm or correct.

**O4. Should the smoke walk capture the empty "Start a chain" card?**
The newest code opens Analyse on an empty "Start a chain" card, but no smoke screenshot shows
it, so chapter 2 describes it from the code next to pictures of older states.
*Recommendation:* add a smoke state for it, then swap the screenshot in.

### Interrogation and controls (`interrogation.trains`, `.intervals`, `.event_shape`, `.event_families`, `.cycle_shapes`, `preprocessing.surrogate`)

These sit on the spike-train path you and your supervisor share, so they come first.

**I1. Block shuffling can quietly hand back the original signal.**
A surrogate is a scrambled copy used as a "nothing here" baseline, like shuffling a deck to
check a card trick is not luck. If the span is shorter than two blocks,
`_block_shuffle` in `Adapters/preprocessing_surrogate.py` returns the signal unscrambled, with
no warning. The trick is then compared with itself, and the null matches exactly.
- (a) Refuse the run, with a reason.
- (b) Warn in `meta`.
- (c) Leave it.

*Recommendation:* (a), the same policy the block already applies to a block under two samples.

**I2. One missing sample wipes out a phase-randomised surrogate.**
One NaN anywhere in the span turns the whole phase-randomised surrogate into NaN; AAFT
instead scatters the NaNs to random positions.
- (a) Refuse spans containing NaN.
- (b) Fill the gaps before scrambling and put them back afterwards.
- (c) Document only.

*Recommendation:* (b), which matches the "skip the gaps" NaN policy you chose on
2026-10-14; (a) as a fallback if (b) is too much work now.

**I3. Event shape counts every failure as "no fall".**
An event whose window holds a single NaN, or is under 3 samples long, is counted in
`n_no_fall` with every measure set to NaN. The real reason (`why` in `measure_event`) never
reaches the output, so a reader sees "no fall" where the cause is a gap in the data.
- (a) Add a per-event reason column and separate counts.
- (b) Interpolate a few NaNs, as event families already does.

*Recommendation:* (a) now, (b) later.

**I4. Intervals drop events whose onset could not be measured.**
With the anchor set to onset, an event whose `onset_idx` is NaN is silently left out of the
timing, so the gap either side of it spans two real intervals.
*Recommendation:* fall back to the event's span start, and count the fallbacks, as
`catalogue.event_windows` already does.

**I5. "Words" in structureless timing.**
In `Working/interrogation/trains.py::adamatzky_words`, the gap threshold θ is a multiple of
the group's own mean gap. On random (Poisson) timing about 63% of gaps fall at or below the
mean, so "words" will be found in data with no structure at all, and nothing tests them
against a null. (The writer's inference from the code; written into the entry's failure
modes.) Should a null be added for words, as other measures have?

### Analyse, Discovery and Models chapters

Page status as written: **live**: `analyse.chain`, `analyse.block`, all four Discovery
pages, `models.launch`, `models.results`, `models.compare`. **Preview**: `analyse.glyphs`,
the three Interrogation pages, the six Training pages, `models.registry`. Interrogation is
mixed: families, members, measures and the rose come live from the seed store, but the run
is a client-side timer (`useSim`), Save template keeps it in memory, and the clustering menu
and the Review/Explore picker tabs are not wired.

**A1. Which screenshots should show failure states?**
A manual's pictures should show what you will actually see. No smoke screenshot shows a
live invalid junction or a live failed block; the only ones come from the built-in
demonstration chain, which a separate component draws.
- (a) Keep the demo screenshots, captioned as the demonstration chain (as written).
- (b) Add live smoke states for both.

*Recommendation:* (b), as two new states in `smoke_pages/analyse.json`.

**A2. Which route to cluster-label training is the main one?**
There are two doors into the same room: the paired A-against-B job on Models › Launch, and
B.2 from a window pool via Train model. The chapter documents the paired job first and B.2
second. *Recommendation:* confirm that order suits research question one.

**A3. The six Training preview pages.**
Six sections describe pages that show example data only.
- (a) Keep short sections pointing to the live chain (as written).
- (b) Drop them from the manual.
- (c) Wire the pages.

*Recommendation:* (a) until the pages are retired.

### Explore, Review and Library chapters

Page status as written: Explore's Corpus, Signal and Cross-channel are **live**, Span edit
**preview**; Review's Queue (inspector) **live**, Cluster **unchecked**; all seven Library
pages **live** (every read in `api/library.ts` goes to the bridge).

**E4. Should Explore › Cross-channel let you choose a cubic detrend?** (After fixup-aq.)
The page straightens each channel's window with a ruler before comparing channels, which
removes a slope but not a bend: if two electrodes both sag and recover over the window, they
still look like "the same event at the same time" and bin as artifact (the fix round's own
simulation found this almost every time). The bridge can fit a cubic instead, but the page
never asks for it; such rows are only marked "may be curved drift".
- (a) Leave it, with the mark only.
- (b) Add a page control for straight line versus cubic.
- (c) Make cubic the page's default.

*Recommendation:* (b): a cubic also removes an event as long as the window, so it should not
be the silent default, but you need to see whether a bin survives it before trusting it.

**E5. The cross-channel screenshot predates fixup-aq.** `explore.cross-channel--default.png`
dates from 2026-09-16 and shows the old page. *Recommendation:* regenerate it at the next full
smoke walk (the caption is written to hold for both versions).

**E1. Is the Review › Cluster page worth finishing before 21 October?**
It would let you judge a whole group of similar candidates with one key press, like marking a
stack of identical forms at once. Today no queue source in `Working/review/` gives its items a
cluster number, so no real queue has clusters, and the bridge's cluster record lacks the
cohesion limit and family the page draws.
- (a) Make the seed-search queue's resolver group its matches and fill those fields.
- (b) Hide the page until then.

*Recommendation:* (b) for now; one-at-a-time review already works end to end.

**E2. Should the blind setting be stored with each verdict?**
A blind check only counts as independent if the record shows it was done blind, the way a
blind-marked exam must say it was marked blind. The blind popover says the state is "stored
with every verdict from now on", but no write sends it, and model registration reads blind
verdicts as the independent check.
- (a) Add a `blind` column and send it with each verdict.
- (b) Change the popover's text.

*Recommendation:* (a).

**E3. Should the Atlas legend stop saying "exemplar (human seed)"?**
The exemplar is a family's showcase example, and the legend implies a person chose it. The
bridge picks a hand-made exemplar if there is one, otherwise the member nearest the medoid
(often the medoid itself). Discovery searches for the exemplar, so the difference matters.
- (a) Relabel it "exemplar (chosen, else nearest the medoid)".
- (b) Show "computed" until someone uses Make exemplar.

*Recommendation:* (b). (This also bears on O2.)

### Drops and events (`detection.drop_detection`, `.stage_encoding`, `.deconvolve`, `.impulse_events`, `.noise_threshold`, `.signal_threshold`)

**D1. Should the two copies of `slope_sigma` be checked against each other?**
The drop detector is two blocks in a row. The first labels each piece of the trace "falling
fast" when it falls more than `slope_sigma` times the background jitter; the second uses its
own `slope_sigma` to decide where each drop starts. It is like two people measuring with
rulers that are supposed to match: change one and not the other, and the result is quietly
wrong. Nothing compares them today; each block page prints only its own cut. The same goes
for `noise_estimator`.
- (a) Leave it; the manual warns (done).
- (b) Have the detection block read `slope_sigma` from the encoding it receives.
- (c) Warn in the detection block's read-out when the two differ.

*Recommendation:* (c); cheap, and keeps the two blocks independent.

**D2. Should the signal threshold's default level change?**
`detection.signal_threshold` defaults to level 0, direction "above": insert it without
typing a level and you get every stretch above zero, which is meaningless.
- (a) Keep it; the manual warns (done).
- (b) Default to a clearly placeholder level.
- (c) Refuse to run while the level is still exactly 0.

*Recommendation:* (a) for now; not on the critical path before 21 October.

### The Dehshibi detector and wavelets (`preprocessing.wavelet_transform`, `detection.wavelet_summation`, `.summation_threshold`, `.dehshibi_spikes`, `.cwt_ridges`, `.wavelet_scattering`)

What the evidence says, as the entries now report it (`webui/screenshots/fixup/J/known-events.json`,
`tests/test_dehshibi_authors.py`, `docs/prompts/fixup/reports/J-dehshibi-vs-the-paper.md`): on the
synthetic recording with 20 known events, 17 found, 19 spans, none on empty signal; on the
authors' three MATLAB reference recordings, 5/6, 3/4 and 8/8 found; on M2_aug CH0, a span in
91% of windows labelled interesting and 86% of those labelled not interesting, with spans
covering 53% of the time.

**W1. The template sums a fixed band that is only right at 1 Hz.**
The middle block adds up only the "slow" rows of the wavelet picture, and the template tells
it how many as a fixed fraction, 0.7586. That matches the authors' choice only when the
picture has 87 rows, i.e. a 3000-sample window. It is like a recipe that says "use
three-quarters of the jar" when jars come in different sizes: at 10 Hz, or with another
window, the template quietly sums a different band, while the deprecated one-block version
picks the band correctly at any rate.
- (a) Leave it, and rely on the manual's warning.
- (b) Have the transform block emit a per-sample score directly.
- (c) Let the summation block take the band in Hz.

*Recommendation:* (c), or at least a warning in the transform's read-out when its fraction
differs from the summation's.

**W2. `window_s` is set in two places.**
The window length is set on both the transform and the threshold block; if they differ, the
threshold judges windows that do not match how the picture was scaled, and nothing warns.
`docs/BLOCK_INTEGRATION.md` §6 says chains should never need a value kept equal in two places.
- (a) Add a check that warns.
- (b) Have the threshold read its windows from the score itself.

*Recommendation:* (a) for now.

**W3. The deprecated one-block detector has no span cap.**
`detection.dehshibi_spikes` has no `max_span_samples`, unlike the transform block (320,000
samples), so a long span could allocate gigabytes (about 0.9 GB for 2.6 million samples at 87
rows, worked out by hand). *Recommendation:* add the same cap; it is one line.

### Workflows, questions and answers, nulls

**N1. What should the interval statistics be called until they have a null?**
The app can say "this detector finds more spikes than random noise would", but not yet
"these spikes are more regular, or more bursty, than chance". That check (shuffled spike
times) was specified and never built (`docs/prompts/fixup/future/R-interrogation-null.md`).
This is on the path you and your supervisor share.
- (a) The manual calls LV, CV and train counts descriptive only (as written).
- (b) Build the interrogation null before 21 October.
- (c) Use block shuffle as a stop-gap timing null.

*Recommendation:* (a) now with (b) scheduled. (c) does not work: a detection run's null
compares only counts, never interval statistics.

**N2. ~~Spike detection (v1) hands on gaps~~ Resolved by fixup-ak.** The block now outputs
one short span per spike, with the spike's moment marked inside, so Trains and Intervals
receive events. Residual, noted in the block's entry: blocks that time events by span start
read the spike minus half the span length; that cancels between spikes, except that a span
clipped at the start of the recording span shortens the first gap by up to half a span.

**N4. Steps and slow bends can pass as spikes** (new block, worked out from the code, not yet
tested). The block asks "is this sample far from the average of its neighbours?". A sudden
permanent shift in level, like a shelf moving up a notch, makes the samples beside it look
far from that average, so the block reports one "spike" at the shift, called up or down by
noise; the steep bends at the start and end of a fast drop can do the same (an "up" at its
shoulder, a "down" at its foot).
- (a) Document only (done).
- (b) Add a test that pins the behaviour.
- (c) Reject clusters whose two outside baselines differ by more than delta.

*Recommendation:* (b) now, so the behaviour is measured rather than derived; (c) only if it
shows up on real M2 spans.

**N5. Bursts collapse to one spike.** Like counting raindrops but treating any drops closer
together than d as one drop, however long the shower: candidates closer than d samples chain
into one cluster with no length limit, so burst statistics in Trains and Intervals lose every
spike inside a tight burst. (a) Keep it (the paper's refractory idea); (b) cap a cluster's
length; (c) split clusters at each local extreme. *Recommendation:* (a) for now, with the
advice to lower d (in the workflows chapter); revisit if spike-train statistics depend on
bursts.

**N3. Settings › Nulls has controls that do nothing.**
Several rows look like settings but nothing reads them, so changing them changes nothing:
the five null kinds other than Detection and Seed search, the seed column, "show × null"
and "reuse draws".
- (a) Mark them "not yet in effect" on the page.
- (b) Wire them to the code.
- (c) Remove them.

*Recommendation:* (a); Appendix B already says so.

### The matrix-profile family (`detection.matrix_profile`, `.mp_motifs`, `.threshold`, `.seed_matches`, `.fluss`, `.pan_matrix_profile`, `catalogue.snippets`)

**M1. Threshold keeps only values above the cut, so `mp_threshold` finds oddities, not repeats.**
A matrix profile gives each window a number that is low when the window happens again
somewhere and high when nothing else looks like it. The Threshold block keeps only the high
numbers, so the `mp_threshold` template (matrix profile, then threshold 8.0) finds one-off
oddities (discords), not motifs. A reader expecting motifs would be surprised.
- (i) Leave it and say so (as written).
- (ii) Add a `direction` setting, as `detection.signal_threshold` has.
- (iii) Rename or redescribe `mp_threshold` as an oddity finder.

*Recommendation:* (iii) now; (ii) if a "repeats below a distance" use comes up.

**M2. Gaps in a recording become "oddities".**
stumpy gives any window that touches a missing sample an infinite distance, not a blank, and
Threshold treats infinity as above every cut, so every gap becomes a detection one window
wider than the gap.
- (i) Have `detection.matrix_profile` turn infinity into NaN before padding.
- (ii) Have Threshold ignore infinite values.
- (iii) Document only.

*Recommendation:* (i); one line, and FLUSS and the pan profile already do it.

**M3. Spans cut from a matrix-profile or FLUSS score mark where windows start, not what they cover.**
Each value describes the window starting at that sample, so a Threshold span stops up to one
window (m − 1 samples) before the end of the signal those windows cover: the old report
tool's window-versus-event offset.
- (i) Widen spans by m − 1 when the score is start-aligned (needs the window length carried
  with the Scores).
- (ii) Document only (done in the threshold, matrix-profile and FLUSS entries).

*Recommendation:* (i) eventually.

**M4. Motif groups keep the overlapping-matches artefact.**
Within one group, look-alikes need only be a quarter window apart, so one event can be listed
twice, slightly shifted, and later groups can re-list windows already in earlier groups. The
old report tool fixed this by enforcing a full window of separation.
- (i) Enforce a separation of m in `build_motif_groups`, and exclude earlier groups' members.
- (ii) Document only.

*Recommendation:* (i), behind a setting, because the motif browser's existing group sets
rely on the current behaviour.

### Symbols, spectra and change points (`detection.sax_csax`, `.sax_psax`, `.sax_dsax`, `.symbol_search`, `.freq_stft`, `.rupture`)

**S1. cSAX's fallback is invisible.** cSAX looks for the levels a signal sits at; if it finds
only one, it quietly switches to ordinary ten-letter SAX, a different encoding. The code has a
red warning row for this (`diagnostic_rows` in `Adapters/_sax_common.py`), but the web UI never
shows it and the bridge does not send `fallback_used`; the only clue is "alphabet 10" in the
summary. (a) Show the post-run diagnostic rows on the Block page; (b) at least send and show
`fallback_used`; (c) leave it. *Recommendation:* (b) now, (a) later.

**S2. dSAX's noise warnings and noise-floor button are missing from the web UI.** In dSAX's
default learned mode, pure noise comes out roughly balanced across down, same and up (the
notes measured 53.5% up-or-down on pure noise). The code has a noise-floor estimator and a
warning (`surrogate_same_halfwidth`, `trend_diagnostic_rows`), but the web UI calls neither,
and the `min_same_halfwidth` help text points to an "Estimate noise floor" button that does not
exist there. (a) Bring the button and warnings to the Block page; (b) reword the help text;
(c) make the noise floor the default. *Recommendation:* (b) now; (c) is your scientific call
about how many false positives to accept.

**S3. Span-aware defaults are declared but never applied.** The three SAX blocks have a rule
for defaults fitted to span length, but the web UI says "recommend hook declared · not
computed in this slice", so the fixed 20 s per letter always applies (and the rule returns a
`preprocess_window_s` key that is not a setting of any of them). Should it be wired in?

**S4. pSAX allows up to 64 letters; anything over 26 breaks symbol search.** Letters past z are
spelt with two characters, and symbol search counts characters, not symbols, so every span
after the first two-character symbol is misplaced in time. Options: cap pSAX at 26; map
character positions back to symbols; or refuse two-character symbols in symbol search.
*Recommendation:* cap at 26.

**S5. An empty match stops symbol search.** A pattern that can match nothing, such as `c*`,
ends the search the first time it matches nothing, even when later real matches exist.
*Recommendation:* step past empty matches by one symbol.

**S6. The STFT block reports false zeros.** It averages away the time axis (one spectrum per
span, not a spectrogram), and at the slow end many log-spaced bands contain no frequency at
all and report exactly 0 power. Options: mark empty bands NaN; merge too-narrow bands;
document only. *Recommendation:* NaN, so a later block cannot read a missing measurement as
zero power.

**S7. The SAX "too flat to scale" threshold depends on the unit.** cSAX, pSAX and dSAX skip
scaling when the spread is below 0.001 in the stored unit, which on a recording stored in
volts means anything with a spread under 1 mV. Should the threshold be relative to the signal?

**S8. Missing values can hang or crash two encoders** (worked out from the code, marked
unverified in the manual): with a NaN in the span, cSAX's Mean-Shift loop has no exit when
every distance is NaN, so the block may never return; pSAX stops with an `IndexError` from
k-means++. Should these refuse spans with gaps, as wavelet bands does?

### Jobs, Settings, Architecture, Extending, data formats

**R1. Are settings really "recorded with every run"?**
Think of a lab notebook that copies the oven temperature onto every sample label, so you can
later prove what every result used. The code does not do that: settings are stored once, in
the database's `settings` table, and reach a run only where some code reads them (the local
limit, the null method and draws, the matching rule, the bands). Some are not in the recipe
hash even though the Settings pages say they are ("These travel into every recipe hash" on
Analysis defaults; "Method, count and seed travel into the recipe hash" on Nulls), and an
Analyse run with its null on stores only `recipe["surrogate"]=True`, not the method or draws.
- (a) Keep the manual as written: settings are stored in the database and reach a run only
  through the code that reads them.
- (b) Write a snapshot of the settings onto each run's row.
- (c) Reword the pages' introductions.

*Recommendation:* (a) now, plus (c); consider (b) for the spike-statistics path, because the
supervisor reads its output.

**R2. Are the many saved-but-unread settings meant to do something?**
A switch on the wall that is not wired to any light: Settings › Blocks on/off, the cluster
profiles on Compute & HPC (the job writers use constants in `Working/config.py`), the
step-cache threshold on Analysis defaults, and most Review-queue, Models and Library-grouping
defaults are saved, but no code reads them (see also N3 for Settings › Nulls). Options: wire
them, label them "not yet used", or hide them. *Recommendation:* label them "not yet used"
before 21 October, so nobody trusts a setting that does nothing.

**R3. Should a recipe name its recording by content?**
A recipe names its recording by database row id, so the same recipe on another copy of the
database (the cluster's, say) hashes the same but can mean a different channel; Library
exemplars are already hashed by content (source file and channel). Options: leave it, with
the watch-out in chapter 16; or hash recordings by source file and channel.
*Recommendation:* leave it for now; it matters only if cluster databases drift from the
laptop's.

### Windows, shapes and grouping (`preprocessing.sliding_windows`, `.window_pool`, `.window_matrix`, `.trace_shape`, `catalogue.event_windows`, `.shape_families`, `.shape_cluster`, `.cluster`, `.manual_labels`)

These bear on research question 1 (do cluster labels train a better classifier than hand
labels?), because they decide what a model is allowed to see.

**G1. Sliding windows leaves no buffer between training and test.**
Imagine splitting a diary into "study" and "exam" chapters: if the last study page and the
first exam page describe the same afternoon, the exam is partly a repeat. In Sliding windows
(and Event windows, which reuses its split) the last training window can end exactly where
the first test window starts, and a window can run on into the test block's time, because a
window's role follows its start. The training pool leaves an empty strip between roles.
- (a) Drop windows within one window of each block border, as
  `Working/training/windows.py::blocked_split` does.
- (b) Add a gap setting.
- (c) Leave it and document it.

*Recommendation:* (a).

**G2. Sliding windows' block counts can round to zero.**
With 5 blocks, "10% validation" rounds to no validation block; fractions adding to more than
1 leave nothing to train on; no error is raised. (a) Reuse `blocked_split`'s rules (at least
one test block; refuse a plan with no training block); (b) only warn.
*Recommendation:* (a).

**G3. Clustering blocks that ignore training and test roles.**
Hierarchical cluster and Shape families group test windows with training ones, and
Hierarchical cluster also rescales its measures using the test windows. Labels made that way,
then used to train a model, have peeked at the exam.
- (a) Warn when the input carries a split or pool roles.
- (b) Cluster only training rows, as Shape clustering does.
- (c) Document only.

*Recommendation:* (a) for Shape families, which is descriptive; (b), or a refusal, for
Hierarchical cluster when its output feeds a classifier.

**G4. A window pool fed straight into Hierarchical cluster, Shape families or Manual labels.**
A pool holds windows from many recordings, but these three treat it as one recording:
Hierarchical cluster would use the pool's bookkeeping numbers (channel, start, length) as
measurements; Shape families, without Trace shape in between, would cut windows from the wrong
trace; Manual labels would read labels from the root recording only. None refuses a pool,
while MiniRocket and Multiscale entropy do. *Recommendation:* refuse a pool in all three, with
the reason, as `multiscale_entropy._is_pool` does, and add the pool's metadata columns to the
bookkeeping list.

**G5. "Approximate entropy" is not the textbook one.**
The column is computed slightly differently from Pincus's formula, so its numbers cannot be
compared with the literature. (a) Fix it, which changes every stored matrix's column; (b)
rename the column; (c) document only. *Recommendation:* (a), with a note on matrices built
before the fix.

**G6. Missing samples silently become zeros.**
A gap makes spectral entropy and approximate entropy read 0 ("perfectly regular") instead of
"unknown", so gaps can form their own cluster. (a) Return NaN when the window holds a NaN; (b)
skip such windows. *Recommendation:* (a); the matrix's computed-mask design already treats NaN
as an honest answer.

### Images, fingerprints and models (`catalogue.gramian_gasf`, `.gramian_gadf`, `.gramian_recurrence`, `.gramian_fusion`, `.window_images`, `.minirocket`, `.multiscale_entropy`, `.classifier`, `.cnn_score`)

**C1. The CNN block's default network scores everything 1.0.**
The Model stage (CNN) block is like a judge who rates each window "how interesting, 0 to 1".
The judge it uses by default (`MODELS/fusion_cnn.pth`) only knows one answer, so it says 1.0
to every window, and a threshold after it marks the whole span. Reports AB and AH found this
and refused that network elsewhere, but this block still defaults to it, with no error.
- (i) Change the default `model_path` to `fusion_cnn_2.pth` or `fusion_cnn_3.pth`.
- (ii) Refuse a checkpoint that does not have exactly two classes.
- (iii) Both.

*Recommendation:* (iii). And say which of `_2` and `_3` is "the" fusion model (AH's
question 2 already asks this).

**C2. The classifier's held-back score ignores the blocked split.**
The classifier checks itself on a random quarter of the windows. On the labels' overlapping
600/200 grid, each window shares samples with four neighbours, so the "exam" holds
near-copies of what it studied. The windows already carry a `split` column (training and test
blocks in time), but the classifier throws it away.
- (i) Keep it, and rely on the Models pages for honest scores (the manual says so).
- (ii) Use `split == test` as the holdout when the column exists (changes saved recipe hashes
  and model files).

*Recommendation:* (ii) if the block's numbers are shown to your supervisor; otherwise (i).

**C3. Multiscale entropy recommends one surrogate but is tested with another.**
Its description advises judging a curve against amplitude-adjusted (AAFT) surrogates, but the
test showing real structure beats its surrogates uses plain phase-randomised ones, which the
same description warns against. *Recommendation:* add an AAFT version of the test.

**C4. Window images has no limit on window length.**
Each window is first drawn one pixel per sample, then shrunk: a one-hour window at 10 Hz is
about 10 GB per picture before shrinking. The four single-span image blocks refuse anything
over 5,000 samples; this one checks only the number of windows. *Recommendation:* refuse
windows longer than `WM_GRAMIAN_MAX_SAMPLES`.

## Possible bugs and stale documentation

### Found while writing the image, fingerprint and model blocks
- **`Adapters/catalogue_cnn_score.py`: the default model is the one-class checkpoint** (C1).
  `DEFAULT_MODEL = MODELS/fusion_cnn.pth`; `score_stack` takes `softmax[:, 0]` without checking
  the class count. `tests/test_adapter_cnn_score.py::test_cnn_score_lays_probabilities_onto_the_time_axis`
  uses the same checkpoint and passes with every value at 1.0, so it cannot catch this.
  `Working/Catalogue/cnn/apply_cnn.py`'s own default is `fusion_cnn_3.pth`.
- **`Adapters/catalogue_classifier.py`**: `_feature_matrix` drops `split` as bookkeeping, then
  `_split` makes its own random stratified holdout (C2). This defeats the MiniRocket warning in
  `Working/Catalogue/minirocket.py` (`fingerprint`), which tells you to put a blocked split
  before MiniRocket.
- `Working/types/windowset.py` `BOOKKEEPING_COLUMNS` leaves out `pool_*`, `shape_row`,
  `shape_orig_start` and `shape_clamped`, which `minirocket.py`'s own list treats as
  bookkeeping; numeric ones would reach the classifier as features (`pool_start` is a position
  in time).
- `Working/Catalogue/gramian/gramian_calc.py`: no PAA before building the image (Wang & Oates
  shrink with PAA first); `_polar_encode` divides by `max − min` unguarded, so a flat span or any
  NaN makes the GASF and GADF images entirely NaN (in fusion, silently all black);
  `compute_recurrence` fails or returns an empty image when the span is `(m−1)·tau` samples or
  shorter; `plot_gramian_suite` calls `plt.show()`. None of these is tested.
- `Adapters/catalogue_window_images.py`: no window-length guard (C4). Its docstring says it
  builds images "exactly as the CNN training set was"; the 8-bit conversion matches, but the
  resize differs (PIL bilinear here, torchvision `Resize` in training).
- `Working/Catalogue/cnn/cnn_rangapur.py`: `EEG_CNN.__init__` requests ImageNet weights
  (`EfficientNet_B0_Weights.DEFAULT`) even when only loading a checkpoint to score, so scoring
  needs a cached or downloaded torchvision file.

### Found while writing the window, shape and grouping blocks
- `Working/Detection/analysis/entropy_analysis.py`: `_approximate_entropy` (around lines
  145–160) computes phi as log(sum of counts / (N−m+1)), not Pincus's mean of per-template
  log(C_i), though its docstring says "Approximate Entropy (ApEn)" (G5); a NaN window returns 0
  (both phi set to 0.0). `_spectral_entropy` (around line 102) is not divided by its maximum and
  does not remove the mean, though its docstring says "Normalised Shannon entropy"; a NaN window
  returns −0.0 (G6).
- Two roundings of the window length: `Adapters/preprocessing_window_matrix.py` `_run` uses
  `round(window_min*60*fs)`, `Working/Preprocessing/window_matrix/matrix_calc.py`
  `create_matrix_at_timescale` uses `int(fs*timescale*60)`; they can differ by one sample, and
  the WindowSet's length then disagrees with the length the measures were computed on.
- `Adapters/preprocessing_sliding_windows.py` `assign_split` (lines 61–89) lacks the
  minimum-one-test-block rule, the nothing-left-to-train refusal and the border gap that
  `blocked_split` (lines 151–179) has; its docstring's "a window is never split across roles"
  is untrue (G1, G2).
- The `pool_*` columns in `Working/training/shape.py` (`POOL_META`, line 78) carry the comment
  "every reader drops them", but `Adapters/catalogue_cluster.py` drops only
  `BOOKKEEPING_COLUMNS`, so it would cluster them (G4); `catalogue_shape_families.py` and
  `catalogue_manual_labels.py` `_run` have no pool guard.
- `Working/training/paired.py` `_silhouette` (line 240) samples with `replace=True` above 8,000
  rows; the duplicate points nudge the silhouette up, and the suggested k is chosen on it.

### Found while writing Jobs, Settings, Architecture and the data appendix
- **A calibration file escapes the sandbox** (confirmed by the orchestrator, 2026-10-16).
  `Working/Preprocessing/window_matrix/cost.py:54` sets
  `CALIBRATION_PATH = os.path.join("DATA", "db", "wm_calibration.json")`, a relative path, and
  `webui/server/runtime.py` redirects, and checks for escape, only the matrix-profile
  (`mp_calibration.json`, line 169) and block-cost paths (lines 172 and 228–231). A sandboxed
  bridge that calibrates the window-matrix cost model therefore writes a small timing file into
  the real `DATA/db`. Not destructive, but it breaks the sandbox's promise that nothing a run
  writes leaves `webui/runtime/`. Not checked: whether the bridge ever triggers that
  calibration on its own.
- The 422 message in `webui/server/app.py` `post_run` (the `max_span_samples` branch) still
  says "route it to HPC (out of slice scope)"; over-limit runs now write a SLURM job.
- `webui/client/src/fixtures/settings.ts:390` (`LOCAL_LIMITS`) says the Analyse limit applies to
  "one stage on one channel"; the bridge (`app.py` `post_run` → `chain.route_local`) routes on
  the whole chain's estimate, null draws included. The limits themselves: Analyse
  `CLUSTER_ROUTING_CEILING_S = 900` s (`Working/config.py`), while the comment at
  `Working/discovery/fanout.py:60` quotes the spec as "Analyse 20 min, Discovery 20 min".
- `docs/DATA_REGISTRATION.md:97` says "Detection code expects volts and multiplies by 1000
  itself"; stale since 2026-10-15 (unit-aware blocks are told the unit and use `read_as_mv`).
- `docs/BLOCK_INTEGRATION.md:342` names `JobManager.start(kind, fn, meta)`; in
  `webui/server/jobs.py`, `start()` takes a recipe and the generic call is
  `start_job(kind, fn, meta)`. Its list of job kinds (line 337) omits `cross_channel`.
- The Display page (`settings/DisplayPage.tsx:68`) offers a dark theme whose caption says it
  "is not drawn yet".
- `Working/database/schema.py`: `_migrate_annotations_verdict` and
  `_migrate_review_queues_kinds` rebuild their tables, so "schema changes are additive"
  (CLAUDE.md rule 3) is not absolute; documented as forced by SQLite, and the manual says so.

### Found while writing the matrix-profile family
- **Saved matrix profiles overwrite each other.** `Pipelines/matrix_profile/run_matrix_profile.py`
  `build_mp_artifact_path`: the file name carries the recording, channel and window but not the
  span, so a second run on another span of the same channel and window overwrites the first
  run's `.npz` while both `artifacts` rows remain. Also, the stored `n_samples` is the whole
  channel's length while `mp` is the span's (`Adapters/detection_matrix_profile.py`, `_persist`).
- **The seeded search changes a setting every stumpy call shares.**
  `Adapters/detection_seed_matches.py` `match_exemplar` changes stumpy's global
  `stumpy.config.STUMPY_EXCL_ZONE_DENOM` under a lock only seed searches take, so a matrix
  profile, FLUSS, pan profile or `stumpy.match` (in
  `Working/Detection/matrix_profiling/motif_groups.py`) running on another thread at that
  moment would use m/2 instead of m/4.
- **A seed exemplar's sampling rate is never checked.** Same file: `_run` stores
  `meta["exemplar_fs"]` but never compares it with the span's rate, and
  `Working/side_inputs.py` `_resolve_library_exemplar` does not resample.
- **Motif groups swallow failures.** `build_motif_groups` has `except Exception: continue` around
  `stumpy.match`, so fewer groups than asked can come back with no message (against the
  loud-failure rule). Also `n_neighbors` counts the seed's own match, so the default 3 gives at
  most 2 look-alikes; the setting's text does not say so.
- **Motif groups do not check what score they are given.** `Adapters/detection_mp_motifs.py`
  `window_from_profile` recovers m from any Scores' NaN tail; a FLUSS score (tail m − 1 plus a
  blanked end of 5m windows) would give a wrong m with no error.
- **The matrix-profile span cap is fixed when the bridge starts.** `max_span_samples` for
  `detection.matrix_profile` and `detection.fluss` is computed once, at import, from the relative
  path `DATA/db/mp_calibration.json`; it stays unlimited if the bridge started before
  calibration, and `route_local` calibrating later does not refresh it.
- **The snippets "7 days" limit is "7 days at 1 Hz".** `Adapters/catalogue_snippets.py`:
  `MAX_SPAN_SAMPLES = 604800` counts samples, so at 10 Hz the cap is about 16.8 h.
- Minor: the MPdist rule text in `catalogue_snippets.py` `RULES` says k = ceil(pct × 2m), but
  the code caps it at 2j − 1 and uses it as a 0-based index; `detection_pan_matrix_profile.py`
  `profile_units` judges lengths on the full n while the run uses usable samples.

### Found while writing the symbol, spectrum and change-point blocks
- `Working/Detection/sax/csax_python/csax.py`, `csax` docstring (Notes, around lines 58–63):
  says the inner normalisation is "not a no-op" because of trimming, but the data are trimmed
  before the outer normalisation (lines 77–97), so the inner one is the identity up to rounding;
  `psax.py` points to the same reasoning.
- `Adapters/detection_sax_dsax.py`, `min_same_halfwidth` help (around line 182): refers to an
  "Estimate noise floor" button that is not in the web UI; the module comments describing it
  (lines 41–61) have no caller.
- `dsax_letters` in `dsax.py` spells the default three letters D/S/U, but the bridge
  (`webui/server/serialize.py` `_encoding`) and symbol search spell them a/b/c, so the D/S/U
  example patterns in its docstring do not work in the app.
- `Adapters/detection_symbol_search.py` `_derive` only checks the pattern is valid; it never
  counts matches, even when the encoding is available.
- `Working/Detection/sax/dsax_python/dsax.py` header [2] attributes SAX-TD (Neurocomputing
  2014) to "Y. Sun, J. Li, J. Wang, X. Xia"; possibly wrong, not confirmed.
- Cosmetic: stray duplicated comments in the `_run` blocks of `detection_sax_dsax.py` and
  `detection_sax_psax.py`; `Adapters/_sax_common.py` docstrings still mention the retired Panel
  `UI.plots` and HoloViews.

### Found while documenting Decompose, Trace shape's alignment and the new Cross-channel page
- `webui/client/src/analyse/ParamsPanel.tsx:86`: the hint says "the step re-runs like any
  edit", but a click on a Decompose layer only marks the step stale (`BlockPage.tsx:63–66` →
  `store.ts:85` `markStale`); nothing re-runs until you press Re-run from. The fixup-ao commit
  message and the `registry.tsx` comment in `DecompositionLayers` repeat the hint.
- `webui/client/src/explore/CrossChannelPage.tsx`: the Classification tip (`:372`) says
  shared-ground pairs come from Settings › Channels & events, but the chip is hard-coded to
  CH4_A2/CH3_A2 (`:414`) and the bridge returns `sharedGround: []` (`api/explore.ts:210`);
  changing max lag still runs a simulated progress bar (`useSim`, `:249`, `:127`), not a
  computation.
- Decompose's `SignalSplitNote` gives the reconstruction error in the stored unit while the
  layers are drawn in the display unit; the note says so, but it can confuse.

### Found while updating the manual for the new spike block (fixup-ak)
- The "blind to slower changes" wording in `Adapters/detection_spike_v1.py` (help and
  description, lines 61–62, 164 and 179) is too strong: it holds inside a slow change, but
  steps and the bends of steep drops can still fire (N4).
- The timing (~0.2 s) in the `spike_analysis.py` module docstring and the noise-rate figures in
  the adapter docstring (0 per hour against 61–64 per hour; 106 and 713 spikes in 12 h) come
  from the fix's critic review; no evidence script or report holds them, and there is no AK
  report under `docs/prompts/fixup/reports/` although the AK prompt asked for one.
- `Working/Detection/analysis/spike_analysis.py` `cluster_spikes` takes the extreme over every
  sample from a cluster's first candidate to its last, candidates or not; the help's
  "candidates closer than d are one spike" is slightly loose. Harmless.
- `compute_spike_statistics` (`spike_analysis.py`, around line 172) is an empty stub.
- Commit 0be45c0 also makes `detection.drop_detection` write `units_note`, so its chain-row
  summary now carries the "read as volts" note too.

### Found while writing the workflows, the questions and answers, and the nulls appendix
- **Settings › Nulls stores values nobody reads** (N3): `webui/client/src/settings/NullsPage.tsx`
  with its defaults in `webui/client/src/fixtures/settings.ts` (`NULL_KINDS`, around line 321)
  saves `null.{distributions,intervals,baseline,full-model,groupings}.*`, `null.*.seed`,
  `show_x_null` and `reuse_draws`, but nothing in `Working/` or `webui/server/` reads them. The
  training job takes its 200 shuffles from its own recipe (`Working/training/paired.py`); draw
  reuse is by recipe hash whatever the toggle says; and the page's α check counts the draws of
  the unread kinds.
- **Every null uses base seed 0.** `webui/server/app.py:288` and `webui/server/discovery.py:2420`
  pass `{"seed": 0}`, so every run's surrogates are the same draws: reproducible, but a result's
  sensitivity to the seed is never shown. Documented as a watch-out.
- **The seed search's "p" is a rate, not a probability.** `Working/discovery/seeded_search.py`
  `recommended_cut_corrected`: it is the number of null matches per draw at or below the
  closest match, capped at 1, and Holm or Benjamini–Hochberg is then applied to it. Fine when
  small, but not a probability; Appendix B says so.
- **Interrogation templates cannot be run across channels with a null.** Discovery's Apply
  template lists only detection templates (`webui/server/discovery.py` `get_templates`, around
  line 648), so a template such as `spike_event_features` cannot be applied across channels;
  the manual tells readers to apply the detector-only template instead.
- **Ten minutes or twenty?** `docs/rq_roundA/RQ2-exemplar-seeded-search.md` says a seed search
  over ten minutes becomes a SLURM job. The code has both: the seed search's own
  `SEED_CEILING_S = 600` s (`webui/server/discovery.py`) and the template fan-out's
  `DEFAULT_CEILING_MIN = 20` (`Working/discovery/fanout.py`, line 62). Analyse uses 900 s.
- The live Block page has no null sweep (see also the Analyse findings): the sweep charts exist
  only in the demonstration components under `analyse/demo/blocks/`.

### Found while writing the Dehshibi and wavelet blocks
- `Working/Detection/analysis/dehshibi_authors.py` `locate_spikes` (the merge loop) sets
  `roi[i][1] = roi[i+1][1]` without taking the larger end, so a merged span could be cut
  short. Possibly copied from the authors' MATLAB; not confirmed. Separately, a candidate that
  meets no envelope region is dropped whenever any other candidate meets one (faithful to the
  code, now documented).
- `Adapters/detection_dehshibi_spikes.py`: its description says the template "reproduces this
  pipeline exactly", which holds only at 1 Hz with 3000 s windows (W1); `_plot` hard-codes
  `fs` to 1.0.
- `Adapters/detection_cwt_ridges.py`, module docstring ("Why not reuse"): calls
  `preprocessing.wavelet_transform` "a Morlet scalogram"; it is a Morse scalogram.
- `docs/rq_roundA/RQ4-bands-and-symbols.md` (around line 51) and
  `docs/prompts/fixup/AC-wavelet-bands.md` (line 33) still say wavelet scattering's kymatio is
  broken; `docs/prompts/wiring/reports/01-analyse-blocks.md` (line 50) says it was fixed, and
  the code agrees (it imports kymatio's 1-D part, avoiding the 3-D part that needed the removed
  `scipy.special.sph_harm`).
- The fixup-J report counts 3 of 4 events found on reference case b, while
  `tests/test_dehshibi_authors.py` requires at least 4: they use different "found" rules (half
  coverage versus any overlap), so both hold; the manual states both.

### Found while writing the drop and event detectors
- **"d" is stricter than the onset gate it is said to match.** `Adapters/detection_stage_encoding.py`
  (docstring and registry description) imply a "d" segment and the detector's onset gate are
  "the same threshold". They are not the same quantity: the encoder compares a segment's
  fitted average slope with `slope_sigma × σ`, the detector compares one sample's
  `np.gradient` with the same number, and σ is the noise of a single-sample slope. On long
  segments "d" is therefore much stricter than the gate; this bears on under-detection. The
  stage-encoding entry says so.
- `Working/Detection/analysis/noise_level.py`, module docstring ("Why not a second copy…"):
  says `robust_sigma` "is not NaN-aware"; since 2026-10-14 `robust_sigma` in
  `drop_motifs/detect.py` drops non-finite values. Stale, harmless (`noise_level` filters
  NaNs first).
- dSAX quantile mode folds its cut-lines symmetric after taking the quantiles (`dsax.py`,
  `_symmetrise`), so on a skewed signal the share of "flat" segments is not exactly
  `same_fraction`; the setting's help says "Occupancy of the SAME band" without that caveat
  (`meta` reports `same_fraction_observed`).
- `Adapters/detection_signal_threshold.py` `_run`: `n_nan` counts `np.isnan` only, so an
  infinite sample is not counted. Trivial.
- Two drop-detector figures rest on docstrings and an evaluation comment rather than a test:
  the "16 of 16" match against annotation 11266 (`slope_noise_sigma`, `autoparams.py`), and the
  ID 26 / ID 28 slope-gate measurements (comment above `SENSITIVE_SIGMAS` in
  `Pipelines/drop_motifs/passes6.py`). The entries say so.

### Found while writing Explore, Review and Library
- ~~**Cross-channel bins claim tests they skip.**~~ **Made honest by fixup-aq (merged
  2026-10-16).** The bins still skip the chance and noise-floor tests (`classify_waveforms`,
  `Working/cross_channel.py:444`, calls `bin_for` with both left at True, `:234`), but the
  route now returns `rule.describe_window(detrend)` (`webui/server/explore_routes.py:211`),
  which says those tests are not run on a window, and the page's Classification tip agrees
  (`CrossChannelPage.tsx:372`); `tests/test_cross_channel_window.py` and
  `tests/test_webui_cross_window.py` pin it. `CrossChannelRule.describe()` (`:162`) still
  claims both tests, but is now used only by the Library family classification, which runs
  them. The manual calls a cross-channel bin "a lead, not a finding".
- **The blind popover's claim is false.** `webui/client/src/review/Shell.tsx` (around line
  128) says the blind state is stored with every verdict; `postVerdict` and `postBatch` in
  `api/review.ts` send no blind field (E2).
- **A fixture number on live data.** The "6.1× null" readout in Review is hard-coded for queue
  `q-12` (`Inspector.tsx`, around lines 220 and 259); `clusterQueue` (`api/review.ts`) still
  reads fixture clusters; `QueueEndView` (`review/common.tsx`) links to `review/queue/q-12`,
  which does not exist on live data.
- **"Demo data" chip on live data.** `webui/client/src/explore/SignalPage.tsx` passes
  `demo={!!demo}` to the header, where `demo` is the live `getSignalLive` result, so the chip
  shows on every channel. `CorpusPage.tsx` (reviewed-coverage caption, around line 248) still
  shows a demo tag though the hatching is live.
- **Writes that are not written.** The family chosen after a seed promotion
  (`review/Inspector.tsx` `confirmPromotion`, `ClusterView.tsx`) only goes to
  `recordDemoWrite`. Library › Import's "send to Review" tick box (`ImportPage.tsx`, around
  line 144) toasts "not wired yet" while the done card (around line 262) still says "queue
  created for Review". Atlas's "Send N unjudged to Review" (`AtlasPage.tsx` `MotifRail` →
  `chrome.tsx` `useQueueToast`) only shows a toast; the Family page's equivalent works.
- **"Edit span in Explore" is a dead end.** `review/parts.tsx` `editInExplore` opens
  `explore/span-edit/<detection id>`, which only knows the fixture span `m-1846`, so real
  candidates land on "No span … in the demo data".
- **Template run counts are approximate.** `webui/server/library.py` `get_templates` counts
  runs with `LIKE '%"name"%'` over `configs.config_json`, so a name that appears anywhere in
  another config's JSON is counted too.
- Stale comments: `explore/CrossChannelPage.tsx` header (around line 10) says the artifact
  rule is "|r| ≥ 0.5"; the code default `CROSS_CHANNEL_ARTIFACT_MIN_ABS_CORRELATION` is 0.98.
  `library/index.tsx` header says "Every page reads fixtures through api/library.ts"; every
  read there is live.
- Screenshots: every `review.cluster--*` screenshot dates from before Review was wired, and
  the smoke walk's blind and cluster states still use fixture queue ids (`q-15`, `q-19`).

### Found while writing Analyse, Discovery and Models
- **Save template says "throwaway" when it is not.** `webui/client/src/analyse/ChainPage.tsx`
  and `BlockPage.tsx` (`saveAsTemplate`): the toast always says "saved to the throwaway
  database copy", but in `--project` mode the bridge writes the real database
  (`webui/server/runtime.py`, `MODES`).
- **Discovery shows simulated numbers as if measured.** `discovery/chrome.tsx` `ScopeCard`:
  "Preview on a 4 h sample" is a simulation with fixed text ("3 spans · null gives 1").
  `StagesPage.tsx`/`ComparePage.tsx`: the "≈ 1 s" re-run chip and the re-running veil are a
  fixed 900 ms animation (`useSim`). `CostChip` computes each run's cost as
  `perChannelMin × channels × sectionH / 174`, with the 174 h hard-coded.
- `discovery/StagesPage.tsx` and `ComparePage.tsx` say "40 s window", but `api/discovery.ts`
  calls `compare/window` and `compare/stages` with 240 (server default `windowS=240.0`,
  `discovery.py` `get_compare_stages`).
- The live Block page has no per-parameter null sweep: `BlockPage.tsx`'s null card says the
  null is per chain run; the sweep exists only on the demo pages, though `pages.ts` lists
  "null sweep" as one of the page's regions.
- `ChainRow.tsx`: the grip, bypass and duplicate icons are inert on the live chain page. On
  the hard-ceiling HPC card in `ChainPage.tsx`, "Create SLURM script" and "Upload computed
  artifact" are disabled ("out of slice scope"), while the time-based route writes a SLURM job
  automatically. `docs/RESEARCH_RUNBOOK.md` Q1 still says Analyse's Create SLURM script is
  disabled.
- `GlyphsPage.tsx`: the header's page label reads "Insert a stage" instead of "Algorithm
  glyphs", and it lists the demo blocks (`getGlyphRegistry` is fixture data), not the live
  registry.
- Stale header comments: `api/discovery.ts` says Discovery writes still go to the in-memory
  demo store (the pages now call live routes; only "Analyse events" and "Open in Analyse"
  still use `notWired`); `api/models.ts` says every read is fixture data (`getModelsSetup`,
  `getPairedRuns`, `getPairedRun` and `getPairedCompare` are live).
- Three different local time limits: seed search `SEED_CEILING_S = 600` s (`discovery.py`),
  fan-out `fanout.ceiling_s` = 20 min, Analyse `CLUSTER_ROUTING_CEILING_S = 900` s. Not a bug,
  but confusing; the manual states each where it applies.
- `models.registry` (marked unverified in the manual): the design says a registered model's
  calibration thresholds become the threshold stage's recommended values (`REGISTRY_NOTE` in
  `fixtures/models.ts`); no live code does it.

### Found while writing the interrogation and control blocks
- `Adapters/preprocessing_surrogate.py::_block_shuffle` returns its input unchanged when
  `n_blocks <= 1` (I1).
- `Adapters/interrogation_cycle_shapes.py`, registry description: says "EXPERIMENTAL: not
  yet run on a real recording", but `docs/prompts/blocks/reports/W3-evaluation.md` reports
  `chain_cycles` beating its null on three real long chains, and it shipped as a template.
- `Adapters/interrogation_intervals.py`, registry description: calls its statistics "the
  regularity gate that says when a run of events is a motif train"; the block applies no
  threshold, it only reports CV, R², drift, LV and CV2.
- `Adapters/interrogation_intervals.py::_run`: once an `onset_idx` column exists, events with
  a NaN onset are excluded rather than falling back to their span start; neither the code
  comments nor the description say so (I4).
- `interrogation.trains` description: says MaxInterval uses "five fixed thresholds" (four are
  seconds, the fifth is `min_events`), and that the three rules give "comparable cuts", which
  no test or report backs.
- Not a bug: `preprocessing.surrogate` seeds `np.random.RandomState(seed)` while
  `Pipelines/drop_motifs/nulls1.py::make_surrogate` uses `np.random.default_rng(seed)`, so the
  same seed gives different surrogates on the two paths. Worth knowing when comparing old
  nulls with the app's.

### Found while writing the orientation chapters
- **`webui/client/src/explore/SpanActions.tsx`: Save span is a demo write that claims to
  save.** It calls `recordDemoWrite`, an in-memory demo write that stores only tags and a
  note, but its toast says "span saved". A user would believe the span is in the database.
  This is the kind of surface the project's rules say must not lie.
- `webui/client/src/analyse/ChainPage.tsx` is a vertical list of rows on a shared time axis
  (its header comment, lines 1–3, says so), while PIPELINE_PRD Part 2 describes a horizontal
  block canvas. Not a bug; Part 2's description no longer matches the shipped page.
- The 20 and 200 surrogate counts quoted in chapter 3 come from `docs/RESEARCH_READINESS.md`
  and `docs/rq_roundA/RQ4-bands-and-symbols.md`; not re-checked against `webui/server/`.

### Filters and baselines
- `Adapters/preprocessing_lowpass.py`, module docstring (around lines 7–12): says "there is
  no resampling or detrending function anywhere in the repo"; stale, since
  `Working/Preprocessing/detrend.py` exists.
- `Adapters/preprocessing_detrend.py`, docstring: refers to the retired Panel run panel's
  `_on_run` and "Preprocessing (applied first)"; no such prepend exists in
  `Adapters/_sax_common.py`.
- `Adapters/preprocessing_detrend.py`, registry description, omits the
  `rolling_mean_nearest` mode; the `make_detrend_filter` docstring in
  `Working/Preprocessing/detrend.py` lists only three of the four modes.
- `Working/Preprocessing/detrend.py`, `rolling_z`: divides by the root mean square of the
  residuals about each sample's own trend. That is close to, but not exactly, the "centred
  rolling std" its docstring claims.
- The order-1 leakage figures disagree: `Adapters/preprocessing_beads.py` (`filter_order`
  help) says 7% of a drift three times slower than the period gets through;
  `Working/Preprocessing/beads.py` (module notes, adaptation 5) says about 10%.
- `Adapters/preprocessing_wavelet_bands.py`, module docstring: says the layers come from
  `pywt.mra(..., transform="swt")`; the code (`decompose`) builds them by hand with
  `pywt.iswt`, one coefficient set at a time. The result should be equivalent; only the
  description is wrong.
- Documentation gap, not a bug: the filter descriptions say "filtfilt" but not that the
  double pass puts the band edges at −6 dB and effectively doubles the order.

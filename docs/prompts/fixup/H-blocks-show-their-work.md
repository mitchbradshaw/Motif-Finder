# Fixup H — a block shows its work

**Ready to run, alone.** This is the last big prompt of the stage and the "legibility" pillar of
`CLAUDE.md`'s priority order. It is cross-cutting — `charts/`, `kit/`, `serialize.py`, `Renderer.tsx`,
`BlockPage.tsx` and every block page — so **nothing else runs beside it.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/BLOCK_INTEGRATION.md`,
`docs/prompts/fixup/QUESTIONS.md` **Round 7** (the grilling that produced this prompt — the whole
section; every rule below was decided there with the researcher), and
`Pipelines/drop_motifs/DETECTION_AND_FIGURES.md` §5b and §6.7.

Commit prefix `fixup-h:`. Test-first; first commit touches only `tests/` and must fail.

**You may open your own grilling round.** If anything below is ambiguous, or you find a fact that
contradicts it, put the questions in `QUESTIONS.md` under a `Round 8 — H` heading and stop there
rather than guessing. Round 7 already corrected two of my own wrong recommendations by measuring;
expect to do the same.

## The one-sentence brief

**Thirty-one of thirty-six registered blocks currently render through one `GenericProcess` view whose
caption literally reads *"this signature has no bespoke process view yet"*** (`BlockPage.tsx:567`).
Your job is not to write thirty-six bespoke views. It is to write **seven type views and twelve
modifiers**, so that every block — including ones nobody has written yet — is drawn correctly from
its type signature alone.

## The organising principle

> **The OUTPUT type decides what kind of picture you get. The INPUT type decides what one "thing" is
> in that picture, and whether there is a before/after to show.**

This collapses 7 × 7 to seven views plus a short modifier list, and it matches where the code already
is: both dispatch tables are keyed on the interchange type — `serialize.py:378` `_DISPATCH` (7
functions) and `Renderer.tsx:32` (one switch). **You are deepening the seam that exists, not adding
one.**

Blocks per output type: **Encoding 12, SpanSet 11, Signal 6, Scores 3, WindowSet 2, Grouping 1,
Model 1.** Encoding and SpanSet are 23 of 36 between them — weight your effort accordingly.

## Two tiers, and they are not the same picture

| | chain thumbnail | block settings page |
|---|---|---|
| job | *did this step do roughly what I expected* | *why did it decide that* |
| content | **one glanceable shape** | the shape **plus the evidence** — markers, distributions, parameters |
| size | ~180 px tall | full width, tall |
| interaction | none | hover, click, drag |
| decimation | fine | min/max envelope only (below) |
| drawn by | the same component, interaction off | the same component, interaction on |

**One component per view, interaction as a flag.** Two implementations of one picture is how this
app got four y-padding rules that prompt `C` had to go and unify.

## The seven views

Each row is the **minimum**. The thumbnail column is the researcher's own specification.

| Output | n | settings page, minimum | thumbnail |
|---|---|---|---|
| **Signal** | 6 | **before and after overlaid**, input grey/transparent beneath. When the block changes the scale (normalise, baseline removal) **draw both axes, original left and new right** | the overlaid plot |
| **Scores** | 3 | the score curve, **the source signal above it on the same x**, the value histogram, the threshold if one exists | the scores plot alone |
| **SpanSet** | 11 | **the slideshow** (below) + every span marked on the full trace + a duration/count distribution | every span marked on the full trace |
| **Encoding** | 12 | **3 sampled images, scan through the rest**, a colour bar carrying the real value range, no-data in grey (never painted at the bottom of the ramp) | 3 images side by side, spanning the thumbnail bar |
| **WindowSet** | 2 | windows on the time axis + the feature matrix **as a heatmap, not a truncated table** | the heatmap stretched to the thumbnail width, **on the same visual time axis as the source signal**, grey where no window |
| **Grouping** | 1 | clusters over time + cluster sizes + **one exemplar drawn per cluster** | heatmap distribution of clusters |
| **Model** | 1 | accuracy per class as bars. `Renderer.tsx:306` currently says *"a model has no natural plot"*; that is only true of the joblib | low priority, a card is acceptable |

All six Signal blocks are preprocessing, so today a detrend, a bandpass and an invert all draw as
"a trace" and you cannot see what the block did. **Before/after is the cheapest large win in the
prompt.**

## The twelve modifiers

| conversion | n | what the settings page adds |
|---|---|---|
| signal → signal | 6 | before/after overlay; dual axes when the scale changes |
| signal → scores | 1 | the source signal above the curve, same x |
| encoding → scores | 2 | the image above, curve below, same x, **the summed band marked on the image** |
| scores → spanset | 3 | **the cut drawn on the score curve, draggable** |
| encoding → spanset | 2 | which cells/symbols fired, marked on the encoding itself |
| signal → spanset | 4 | spans on the trace — no intermediate exists to show |
| **spanset → spanset** | 2 | **the features, NOT the spans** — a histogram per measure, plus the rose. An interrogation block outputs spans but the spans are not the point |
| signal → encoding | 11 | 3 sampled images + which chunk of signal each came from |
| windowset → encoding | 1 | 3 sampled images + which window each is |
| **signal → windowset** | 2 | **the two producers differ**: `window_matrix` has an attached feature matrix → heatmap. `sliding_windows` has **no features at all** → window bands coloured by train / validation / test, which is the leakage guard you actually want to check |
| windowset → grouping | 1 | clusters over time + one exemplar per cluster |
| grouping → model | 1 | accuracy per class |

`detection.threshold`'s draggable cut line already exists (`BlockPage.tsx:334`) and is the best view
in the app. **Generalise it to all three `scores → spanset` blocks rather than rewriting it.**

## The drawing rules that carry over

From `Pipelines/drop_motifs/drawing_rules.py`, the researcher's own module. **Not all nine apply** —
these do, and they were chosen deliberately in Round 7:

1. **Never interpolate.** A drawn curve implying samples the recording does not have is a
   fabrication; this stage has already removed two. On the **settings page** nothing is resampled;
   on a **thumbnail** resampling is fine.
2. **Decimate by min/max envelope, and say so.** A 721-hour channel at 1 Hz is 2.6 M samples against
   ~1200 px. `G` built this: each pixel column carries the true min and true max of its samples, so a
   one-sample spike still reaches full height and nothing is invented. Print what was drawn —
   `G`'s `ResolutionNote` already says *"660 samples · 1 Hz · every sample drawn"* — and **dot the
   vertices when samples are ≥ 3 px apart** so the eye can tell real resolution from drawn
   resolution.
3. **A drop must look like a drop.** Rule 9, `check_drop_shape`. Port it: a drawn trace must actually
   vary, nothing may be flattened to a line, no axis may clip its data. **This becomes a gate
   check** (see below).
4. **Per-panel measured domain, aspect lock, and an explicit scale bar** on small multiples — *not*
   a shared y. The researcher's figures tried shared-y and rejected it
   (`figures12b_s3.py:50-65`): clustering is scale-invariant, so a 0.014 mV and a 0.39 mV motif can
   be siblings, and a shared axis draws most of a family as flat lines. The scale bar is what keeps
   "legible" and "comparable" from being a trade-off. Consistent with prompt `C`'s rule.
5. **Colour graded by time where the analysis is about order**, and not otherwise. Context-dependent,
   the researcher's call per view.

## The text budget

**Avoid walls of text. Put explanation behind an info icon**, which the app already does
(`interrogation_routes.py:118-123` prints a `rules` list; `E` carried those rules onto the page).

The rule, decided in Round 7: **one short line visible, the full definition behind the icon —
but an absence is never hidden.** "half-width · FWHM" on the face; the complete rule on hover; and
**"17 of 17 events have no recovery" stays on the face of the card**, because that is not
explanatory text, it is the result. Hiding an absence re-creates by omission the fabrication `E`
removed by invention.

## The slideshow (U8)

It already exists and it is **fixture-backed** — so this is **wiring, not design.**

`analyse/demo/blocks/DetectionBlock.tsx:90-107`, the "Each kept detection" strip on block 04 of the
`drop_motifs9` chain: one card per detection surviving the floors, carrying id, family chip, score, a
sparkline, depth/duration and adjudication state; sorted by score / time / depth; paged `1–6 of 6
‹ ›`; **clicking a card centres that event in the full-signal plot above, and clicking a band above
selects the card.** Six hard-coded detections and a `demo data` chip.

Build the real one on **`SmallMultiples`** (`kit/plots.tsx:534`), which is already written, already
has the pager, and adds a **seeded "resample" shuffle** that `DetectionBlock` does not use — for
hundreds of events that shuffle is the better default than in-order paging.

Take all of it, plus **the impurity flag from the matplotlib ancestor**: in
`Plots/drop_motifs5/id385_contact.png` a panel whose window holds more than one fall **turns red and
its title says `[2 falls]`**. That is an automatic "this detection is suspect" marker and it is the
fastest thing on the sheet. The UI version lost it.

Copy the keyboard pattern from `review/ClusterView.tsx:222`, where **selection drives the page**
rather than the reverse.

**It is read-only.** The one action is *send to Review*. The moment it writes a verdict it *is*
Review and you have two tools that disagree.

Why small multiples rather than an overlay, in the researcher's own words (`figures5.py:7`):

> an overlay *hid the defect* — a window holding three spikes drawn on top of four others that also
> hold three looks like a busy family; it takes seeing the panels side by side to notice that every
> one of them is a train.

## Frames: which extent to draw (Q19)

**You draw the extent. You never redefine it** — the stored extent *is* the Library's identity (the
content hash covers the whole snippet), so changing it is a 3,603-row re-hash and its own migration
prompt.

- **A single event** → the stored window, which is `detect5.window_bounds`' morphology-aware bracket
  (sharkfin: its own preceding rise → the next rise; trough: previous recovery → its own recovery
  end). This is what `E` already defaults Interrogation to and it is correct.
- **A sequence or an overlay of many events** → the `sequence_frames` rule
  (`drawing_rules.py:146`): reach back to **the previous event's trough**, capped at 14 falls. Its
  docstring is the U11 complaint stated in advance: *"an Oyster event is a 6 s fall on the end of a
  55 s rise … a frame of 1.2 falls before the onset shows the last tenth of that rise, which is a
  shoulder rather than a sharkfin."*
- **Never `1.2 / 1.8` falls for a sharkfin.** `framed_trace`'s constants are for single trough-like
  events.

**Mark a capped edge (Q18).** `detect5`'s morphology bracket loses to a scale-free `6 × fall` cap on
**46 % of seed events (left edge), 49 % of oyster**, and the stored row does not say which rule set
its edge. A capped edge and a measured edge look identical on screen and one of them is a backstop.
Draw them differently — a dashed frame edge — and count it behind the info icon: *"23 of 47 events
capped at 6 × fall"*. Without this, "the overlay shows the extent of the event and nothing more" is a
claim the data cannot back half the time.

## Delete the two fabricated nulls (Q27)

The Aggregate page carries **two** nulls and neither is one:

- **the scatter null** (`AggregatePage.tsx:310`) takes each real point and multiplies it by random
  factors, three times — the "null" is the researcher's own data with noise on it;
- **the histogram null** (`:82`) is three uniforms summed, centred on the midpoint of the observed
  range — a bell curve drawn behind the bars.

Both are labelled "matched windows" / "shuffled onsets" and the card cites **P10**, which specifies
*"matched random windows (200×) and shuffled onsets"* and whose status is still `ticketable now` —
**specified, never built.** The page inherited the spec's wording over a placeholder.

A consequence worth stating in your report: because the scatter null is the data with independent
noise on x and y, its fitted exponent is a *regression-diluted copy of the real one*. It lands below
the real β by construction. So `E`'s finding that id010 gives **β 0.28 against a null of 0.25** was
never a meaningful comparison — that null can be neither cleared nor failed.

**Delete both, and the P10 claim with them.** Do not relabel: a page that says "for visual reference
only" beside a grey cloud that looks exactly like a null is worse than a page with no null. The real
P10 is `R-interrogation-null.md`, its own prompt, in the core with a test. `kit/plots.tsx:496`
`NullBand` is already written for when it arrives.

## Three findings that will bite you silently

1. **Select spans by SAMPLE RANGE, never by window index.** `DETECTION_AND_FIGURES.md` §5b,
   verbatim: *"Any UI panel showing 'the motifs in this window' must use the range."* A drop in two
   overlapping windows is stored once against whichever window won the best-framed rule — often the
   neighbour. Measured undercounts: CH4 showed **11 where 21 exist**; CH2 showed 1 where 2 exist.
2. **30 of 1058 store rows have `len(detrended_mv) != snippet_end_idx - snippet_start_idx`.** Slice
   by the stored indices and those thirty render as a 1-sample "fall" — a flat card that looks like a
   bad detection and is a bad slice. Detect it and say so on the card.
3. **Overlapping snippet context is not double-counting.** Snippets carry 1.2 falls before onset and
   1.8 after, so **261 of 1058 snippet spans overlap while only 1 onset→trough pair does**. Do not
   visually dedupe it.

## Use the machinery that is already built

`analyse/` imports **zero** plot components from the kit. `kit/plots.tsx` holds thirteen, used by
Training, Models, Library, Review and Explore — and `BlockPage.tsx:386` hand-rolls its own histogram
instead. `Scatter` (:376), `NullBand` (:496) and `SmallMultiples` (:534) have no caller outside
`kit/Gallery.tsx`.

**Wiring `analyse/` to the kit is most of this prompt.** Also already built and unused or duplicated:

- `Histogram` :289, `Bars` :324, `Heatmap` :419, `BandStrip` :467 — the four the seven views need;
- `Pager` (`kit/nav.tsx:100`), `usePagedList` (`kit/hooks.ts:30`);
- `charts/domain.ts::measuredDomain` (prompt `C`'s rule), `charts/useSize.ts`, `charts/timeAxis.ts`;
- the detection-density ribbon (`explore/Overview.tsx:143`) — the researcher's answer for a
  thumbnail of too many items to plot: bucket them and draw intensity;
- **two separate rose implementations**: `RoseFan` (`analyse/EventFeatures.tsx:77`, real, fed by
  `meta["rose"]`) and `interrogation/Rose.tsx:21` (prototype, fixtures, header says *"the kit has no
  polar plot"*). **One of them should survive, and it should be in the kit.**
- 47 per-block algorithm glyphs (`analyse/glyphs.tsx:50`) — every block already has bespoke artwork
  for *what it does*; this prompt gives it bespoke artwork for *what it found*.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **Redefining an event's extent** | The extent is the Library's identity; changing it re-hashes 3,603 rows. `N-event-extent.md` |
| **Building the real P10 null** | `R-interrogation-null.md`. Here you only delete the fake one |
| **Persisting `recovery_idx`** | `P-persist-recovery-index.md` — a core/schema change |
| **The human extent-correction path** | `Q-extent-corrections.md` — `motif_member_revision` exists and nothing writes it |
| **How reports/exports are drawn** | A separate prompt, which **inherits this standard** rather than inventing a second one |
| **Re-opening `E`'s overlay-window default** | It is correct (Round 7 corrected the record). You add the sequence frame beside it |
| **Review's behaviour** (classes, extract editor, rediscovery) | `07-review.md` R3/R4/R7 |
| **Wiring Jobs, Models, Training off fixtures** | They wear the `demo data` chip for a reason |
| **The Slope anatomy figure** | Prompt `K`, which runs first. If `K` has landed, draw its real marks; do not re-fabricate them |

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client` — **into your own dist** (`run_server.py --dist`,
   and check the `CLIENT = …` banner line before trusting a screenshot);
2. `webui/smoke.py` against a `--sandbox` bridge on **port 8765**, restarted immediately beforehand,
   **never while `pytest -n auto` is running**;
3. `pytest -n 4` against the **1874 passed / 8 skipped / 0 failed** baseline, comparing failure
   **sets**, which are empty.

**Standing failures that are not yours:** under `webui/.venv`,
`test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`. In smoke, the four
Settings registration `Locator.click` timeouts, `discovery.runs--default`, and
`analyse.interrogation--fixup-d-sequence-rose` (a cold-bridge settle flake: it passes on a warm
re-walk, and the route it waits on answers in 20–55 ms).

**The standard must be enforced, not merely written (Q14).** Three levels, all three required:

- **written** in `docs/BLOCK_INTEGRATION.md` beside the existing block contract;
- **tested** — `tests/test_block_standard.py` grows a drawing clause: every registered block resolves
  to a view, and **no block falls through to "no bespoke process view yet"**. That caption is the
  acceptance criterion: when it cannot appear, you are done;
- **measured in the gate** — rule 9 ported into `webui/smoke.py`, asserting in a real browser that a
  drawn trace actually varies, that nothing is flattened to a line, and that no axis clips its data.
  The precedent works: smoke already measures that Review's highlight contains its event (`G`) and
  that no two time-axis labels overlap (`A`), and both caught real defects.

**Evidence.** Before/after of **one block per output type — all seven** — into
`webui/screenshots/fixup/H/`, at both tiers (thumbnail in the chain, and the settings page). Plus the
slideshow on a real store with the impurity flag firing, and a family whose members span two orders
of magnitude drawn with per-panel domains and scale bars (the shared-y case Q15 rejected).

## Report

`docs/prompts/fixup/reports/H-blocks-show-their-work.md`: the seven views and twelve modifiers as
built, and any you changed and why; how the thumbnail and settings tiers share one component; what
rule 9 checks in the gate and what it caught; the two nulls deleted and what the page says now; how
many blocks still resolve to a generic view (it should be zero) and the test that pins it; which rose
survived; the capped-edge marking and its counts on the real store; defaults taken; items left;
out-of-scope files touched; the gate; a chat summary.

Then close `QUESTIONS.md` U7, U8, U9, Q27 and the Round 5 reassignment rows, and `03`'s I6/I7/I8 and
`07`'s R17.

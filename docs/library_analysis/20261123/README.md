# Whole drops, the sequence-review queue, and the 10-minute windows (23 Nov 2026)

## In plain words

**What a drop is, now.** The tool used to measure only the steep core of a drop: from its steepest point to where
the slope eased off. You agreed a new rule on the diagram `whole_drop_vs_steep_core.png`. A drop event is one
unbroken fall, and a pause (the trace goes flat) or a rebound (it climbs back) ends it. Its whole drop runs from its
top to the bottom of its tail. So:

- a steep start with a slow tail is one event;
- a slow decline, a pause and then a sharp drop are two;
- a staircase is two;
- falls separated by rebounds are separate events.

The rule lives in the core as `Working/interrogation/whole_drop.py` (tests: `tests/test_whole_drop.py`). Auto-detect
imports the same function, so its candidate boxes and the Library measure one thing. The event-shape block (the
steep core) is unchanged, because the detectors rely on it.

**A sequence queue to review.** Queue 48, *Sequences · candidates (23 Nov)*, holds 500 candidate sequences, each
asked once: "is this a sequence?". An accepted one is stored in the Library as a sequence (a human sequence), its
single events still to be resolved. Resolving them is the next queue (see *What comes next*).

## 1. The whole-drop rule on the accepted library

*(The rule as approved, commit `5e07deff`. It was revised the same evening after Auto-detect's checks: see 1b.)*

Over the 2,914 accepted spans that could be measured:

| | Steep core (before) | Whole drop (now) |
|---|---:|---:|
| Spans measured on under 30 % of their own range | 411 | 35 |
| Spans with no event found | 0 | 55 |
| Spans holding two or more drop events | not counted | 622 (4,025 events in all) |
| Spans with a measured width (half recovery reached) | 1,858 | 2,115 |
| Depth agrees with the steep core within 10 % | | 1,365 (median ratio 1.10) |

How the rule works:

1. **Pieces.** A Gaussian copy of the trace (at least one sample, 0.5 s) is cut into straight pieces by a
   vertical-distance Ramer-Douglas-Peucker fit, with tolerance 4 × the robust sample noise.
2. **Pieces become events.** Falling pieces in a row form one event, and a flat or rising piece ends it.
3. **Floors.** Events shallower than 6 × the noise, or than 15 % of the span's deepest event, are dropped.
4. **Which events belong to a span.** An event belongs to a span when at least half of its *depth* falls inside it.
   This handles a span drawn round the start of a long fall, and windows that start mid-fall.

Every span is measured as a drop. The 156 whose biggest, fastest movement is a rise are flagged
(`rise_dominated`), not flipped.

Files:

- `whole_drop.csv`: both measurements for every span, with the event list as JSON.
- `whole_drop_summary.json`.
- `scripts/library_analysis/fig_whole_drop_vs_core_20261123.py`.

## 1b. Revised after Auto-detect's checks (23 Nov, evening)

**In plain words.** You asked the Auto-detect session to check its candidates against the rule. It found four
problems:

- **Slow drops cut into pieces.** On a quiet channel a slow drop's small wobbles counted as "it climbed back", so M4
  CH1's 50 mV decline, which you circled as one drop, came out as four.
- **The answer depended on the box.** The same fall measured in a short box and in a long box got different tops and
  bottoms.
- **Small machine boxes failed the depth floor.** A machine box next to a deeper drop could not be measured, because
  the 15 % floor was set by the deeper drop.
- **Sharp falls lost their width.** The search for the half-way recovery stopped after ten fall times. A fall of 3 s
  that recovers half-way after 43 s therefore got no width.

Fixing the first problem showed a deeper one. The approved rule only kept separate drops apart because tiny wobbles
happened to sit between them. Once the wobbles were ignored, two kinds of separate drop ran together: a slow decline
flowing straight into a sharp drop, and a drop's slow tail flowing into a second sharp drop. You ruled that joining
out. So the revised rule says what makes a new drop: a fall that suddenly becomes much steeper than the stretch
before it.

An analogy: walking downhill, a gentle slope that ends at a cliff edge is two things, a walk and a fall, even
though you never stopped. A path that steepens gradually into the cliff is one descent.

What changed, in `Working/interrogation/whole_drop.py` (25 tests):

1. **Separate drops stay separate, even with no pause between them.** A fall about 5× steeper than the slow stretch
   before it starts a new drop when it falls at least 15 % of the drop so far. This covers a slow decline running
   into a sharp drop, and a tail, slowed to a fifth of its own steep part, running into a second drop.
   - A slow lead-in shallower than 35 % of the drop it runs into is that drop's **shoulder** and stays with it.
     Examples are M4 CH1's six minutes before its fall, the SO CH2 case you approved (17 %), and the first of your
     four rebound-separated falls (28 %). The slow declines that are drops of their own run 42–200 %.
2. **A wobble does not end a drop; a clear climb ends any drop.** A drop is now followed only while it reaches new
   lows. A climb ends it when it is 10 % of its depth or 10 × the noise, whichever is less. One M2_aug span showed
   why the noise limit is needed: a 105 mV artifact spike in the context had swallowed the real 1.2 mV drop.
3. **A pause is a stretch where the trace has stopped descending.** A slow tail still creeping down through noise is
   part of the drop.
   - A stall that ends in a slow creep, rather than a sharp fall, must also last at least 30 s. This is Auto-detect's
     drop B: one noise-flat second right after a 3 s fall had split off its 4-minute settle.
   - A quick staircase is still split: there a short flat ends in a fall as sharp as the first.
4. **One fall gets one answer whatever box measures it.** The noise is read from a fixed hour around the box. Every
   box is read with at least 10 minutes of context, widened while a drop is cut by the edge of the read.
   `span_events` reads the same way.
5. **A span holds the drop whose steepest moment it holds,** as well as any drop with half its depth inside. A sharp
   drop whose tail runs on far past the span is that span's event.
6. **Auto-detect's boxes can name their moment.** `measure(..., anchor=index)` measures the drop at that moment, with
   the 15 % floor taken against it, even next to a deeper drop.
7. **The half-way recovery is searched up to the next drop's top, at most 2 h.** The ten-fall-times limit is gone.

On the accepted library (`revised/`; the approved run is left as it was):

| | Approved rule | Revised rule |
|---|---:|---:|
| Spans with a drop measured | 2,859 | 2,867 |
| Spans with no event found | 55 | 47 |
| Spans holding two or more drop events | 622 (4,025 events) | 618 (3,992 events) |
| Spans with a measured width | 2,115 | 2,267 |
| Spans measured on under 30 % of their own range | 35 | 34 |

- **Depth.** It is within 5 % of the approved depth on 2,356 of the 2,853 spans both rules measure.
- **Deeper.** 37 spans got more than 1.5 × deeper, mostly sharp drops whose long tail the approved rule cut off at the
  edge of its read.
- **Shallower.** 36 got shallower than 0.67 ×, mostly slow declines now split off a sharp drop.
- **Your 12 diagram cases.** They keep their events. Tops and bottoms moved a few seconds onto where the fall leaves
  its top and arrives at its bottom (within one noise-width), rather than the single highest or lowest sample.
- **M4 CH1, 281:24–283:00 h.** One event, 281:22.5 → 282:43.0, 49.4 mV. You circled 281:25 → about 282:45.

`revised/whole_drop_revision.png` shows the cases that moved: the approved rule (orange) against the revised one
(blue). It is drawn by `scripts/library_analysis/fig_whole_drop_revision_20261123.py`, which loads the approved rule
from its commit. `revised/whole_drop_vs_steep_core.png` is your 12-case diagram under the revised rule.

**Three questions for you** (the OPEN panels of the figure). Each one is about where a drop *ends* when nothing stops
it cleanly.

1. **A step on a slow drift** (LM CH3, `99f61fa6`). The trace was already drifting down before a 2 mV step, and it
   drifts on afterwards at the same pace. Read literally, "to the bottom of the tail" runs the step on to the end of
   the drift, 9 mV an hour later.
   - Options:
     - (a) keep that;
     - (b) end the drop when its fall is back to the pace the trace had *before* the drop: the drop is over when
       the trace is back to what it was doing;
     - (c) end it when the pace falls to a fixed fraction of the drop's steepest.
   - **Recommendation: (b).** It changes only drops that sit on a drift that was already there.
2. **A sharp drop, then a decline lasting two hours** (LM CH1, `2a1dc6b4`). Nothing was drifting before. The bottom of
   the tail is two hours later, 19 mV down.
   - Options:
     - (a) keep it (M4 CH1's 80-minute tail, which you circled, behaves the same way);
     - (b) end the tail where it stops slowing down;
     - (c) cap the tail at a multiple of the steep part's length.
   - **Recommendation: (a)**, with the long-tail events flagged in the Library so a plot can leave them out.
3. **A fall that eases off and plunges again** (M2_concat CH10, `082f06a6`). After its first steep part it slows to a
   fifth of that pace for two minutes, then plunges. The revised rule calls that two drops (46.6 and 43.3 mV); the
   approved rule called it one (89.9 mV).
   - Options:
     - (a) two (now);
     - (b) one, unless the fall slows to a tenth or pauses.
   - **Recommendation: (a)**, since it follows "separate drops are never joined", but this is a case your eye should
     decide.

Queues 48 and 49 were built with the approved rule. Their event bands are context only, so they are left as they
are. The candidate-event queue (below) will be built with the revised rule.

## 2. The 10-minute windows

The 11,234 ten-minute windows of M2_aug, imported on 3 August, break down as:

| Verdict | Windows |
|---|---:|
| interesting | 2,333 |
| not interesting | 8,773 |
| artifact | 128 |

None of them is one of the 2,959 accepted spans: the catalogue keeps fixed windows as context, never as events
(`scripts/thesis/accepted_catalogue.py`). Only 97 interesting windows contain an accepted event's onset. That leaves
about **2,236 interesting windows (≈373 h) with no individually accepted event**. They are the largest untapped pool.

**Added to the pipeline (you said yes, 23 Nov).** Windows that touch on a channel were merged into one region (2,333
windows → 2,110 regions), and the whole-drop rule listed the drops inside each:

| Drops in a region | Regions | Where they went |
|---|---:|---|
| none | 4 | nowhere |
| one | 628 | kept for the candidate-event queue: `window_single_events.json` (one drop is not a sequence) |
| two to five | 1,162 | queue 49 (below) |
| six or more | 316 | queue 49 |

88 multi-drop regions already lay mostly inside a queue-48 candidate and were left out. A random sample was checked
by eye before writing. Script: `scripts/library_analysis/window_candidates_20261123.py`.

## 3. Queue 48: *Sequences · candidates (23 Nov)*

| Kind | Items | Events drawn inside | Where from |
|---|---:|---:|---|
| Hand-labelled sequences | 27 | none yet | the September Excel catalogue (judged interesting or seed; the 3 judged not interesting are left out) |
| Chains of neighbouring accepted events | 126 | 1,671 | every drop event of the accepted spans on one channel, while the next top follows within 1 h, at least 5 events (median 1.06 h; the longest, MJu26a CH14, is 90.5 h) |
| Multi-event spans | 347 | 835 | accepted spans holding two or more drop events (251 hold two) |

A chain lying mostly inside a hand-labelled sequence (21), and a multi-event span lying mostly inside a chain or a
hand-labelled sequence (275), were left out because they are already asked about.

**Reviewing it.** Start the website as usual (`webui\start.ps1`) and open Review › queue 48. The migration runs once,
on that start, and has already run on the database. Each item shows:

- the whole span ("Sequence in context");
- its events as numbered bands;
- a line saying how many events it has, where it came from and, for a hand-labelled one, what the catalogue said.

| Key | Means | What it writes |
|---|---|---|
| I | interesting: it is a sequence | a human annotation over the span, plus a human `sequences` row (`needs_extraction = 1`) |
| N | not interesting: not a sequence | the annotation only |
| A / U | artifact / unsure | the annotation; unsure takes no side |
| S | refused: a seed is a single event | nothing |

Ctrl Z undoes a verdict, including the stored sequence. On a hand-labelled sequence the verdict re-describes its own
annotation.

**What it wrote.** Writing the queue added only machine rows: the 473 candidates (`sequences` with
`origin = 'machine'`) with their events (`sequence_members`), plus the queue. No verdict was written. Until you
accept a candidate, the Library neither lists, counts nor groups it (its key starts `candidate:`).

**Backups:**

- `DATA/db/backups/before_sequence_review_20261123_143252.sqlite`;
- `DATA/db/annotations.sqlite.pre-review-queues-rebuild-20261123-143302.bak` (the migration's own).

**Code:**

- `Working/review/sequence_queue.py`: the queue kind and the entry point `send_to_sequence_review`, also
  `POST /api/review/sequence-review`, which Auto-detect will use.
- `Working/review/queues.py`, `verdicts.py`: the wiring.
- `Working/database/schema.py`: the kind in the queue table's CHECK.
- `webui/server/review.py`: the route.
- `webui/server/library.py`: leaves candidates out.
- `webui/client/src/review/Inspector.tsx`, `api/review.ts`: the sequence item.
- `scripts/library_analysis/sequence_candidates_20261123.py`: built the candidates; `--apply` made the queue.

## 4. Queue 49: *Sequences · interesting 10-min windows (23 Nov)*

This holds **1,390 items with 5,980 drops** marked inside: the interesting windows (merged where touching) that hold
two or more drops. It works exactly like queue 48: I means it is a sequence and is stored as one, and an item marked
N, A or U stores nothing. It is a separate queue so that queue 48's 500 keep a clean progress count. Do 48 first, or
either; nothing depends on the order.

Writing it added only machine rows (1,390 candidates with their events) and the queue; no verdict was written.
Backup: `DATA/db/backups/before_window_candidates_20261123_153310.sqlite`.

## What comes next: the candidate-event queue

Once queue 48 is reviewed:

1. **Find the events.** Run `whole_drop.span_events` inside every accepted sequence, which lists its drop events.
2. **Skip what is already judged.** Drop every event that is already an accepted (or rejected) event, by the
   Review matching rule.
3. **Send the rest to Review.** The remaining events go as machine detections in one run, served by the existing
   detection Inspector in a listed order, grouped by sequence and time. Overlap sets, verdict carrying and promotion
   all work there already.
4. **Make them members.** Accepted events become the sequence's members, and the sequence is marked complete.

Queue 49's accepted regions join step 1 the same way. The 628 one-drop windows join at step 2: each is already a
single event, so it needs only the "already judged?" check.

## Two questions you asked: superimposed events, and rises before drops

**Superimposed events.** In plain words: when four small drops sit on a falling background, either one slow drop
runs underneath four small ones, or there are four separate drops in a row. One channel alone often cannot tell
these apart. My view is to record both levels rather than choose:

- **Events** are each unbroken fall, as the rule now does.
- **The background** is measured per sequence, as the trend of the events' tops (and of their bottoms).

Two signs point to superposition:

- each recovery stops lower than the last;
- the same slow decline shows on neighbouring channels at the same time. A cross-channel shared driver was already
  found on M2_aug in round B (B4).

Recommendation: keep events separate (done), and add "background trend across the sequence" as a sequence measure,
with an optional second depth measured above that background.

**Rises before drops.** Two different things:

- **(a) A recovery.** The rise is the previous drop recovering. In a train each cycle is fall, recover, fall, so the
  rise belongs to the previous event.
- **(b) A precursor.** A rise from a flat baseline, then a fall: a rise-then-drop shape (sharkfin-like), possibly a
  different family.

What is immediately before the rise tells them apart: the previous event's bottom (a), or a flat baseline (b).

Recommendation: keep drops as the unit, and give each event two descriptors:

- **precursor rise height**;
- **lead-in**: flat, recovery of the previous event, or rise from baseline.

The shape map can then be split by lead-in, and grouping will show whether rise-then-drop events form their own
family. The 156 rise-dominated spans are the first examples to look at.

## Checks

- **Tests.**
  - `tests/test_review_sequence_queue.py` (14) and `tests/test_whole_drop.py` (13), plus the review, verdict,
    promotion, catalogue and boundary test files: 334 passed.
  - One failure, `test_review_family_queue.py::test_an_extent_edit_moves_the_drawn_span_and_keeps_the_verdict`, fails
    on the committed code too (checked on a clean copy). It is not from this work.
  - `tests/test_webui_sequence_review.py` (5) and the Review and Library bridge files: all pass.
- **Client.** `npx tsc -b` and `npm run build` pass.
- **Smoke.** The Review smoke unit on a sandbox bridge had the same 9 failures and 3 timeouts as the 21 Oct baseline,
  with no console errors and no server tracebacks.
- **By eye.** Queue 48 on the sandbox: a hand-labelled sequence, a chain and a multi-event span all render, with
  bands and lines.
- **The revision (1b), same evening.**
  - `tests/test_whole_drop.py`: 25 pass. Eight of them fail on the approved rule (they are the new behaviour).
  - `tests/test_import_boundaries.py` passes.
  - Your 12 diagram cases keep their events, and M4 CH1 is one drop.
  - Every span that lost or gained an event, and the 12 that moved most each way, were looked at against the
    approved rule by eye.
  - Not run: the full suite and the smoke walk. No web UI file changed.

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
- **Nothing is committed.**

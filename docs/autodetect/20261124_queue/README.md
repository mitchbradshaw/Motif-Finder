# The Auto-detect review queue (24 Nov 2026)

You asked: "build a review queue from the auto-detected events across the channels you have been using. Review
queue should only include events I have not yet reviewed, prioritised by the highest confidence scores, including
both spikes and drops, prioritised also by sequences potentially like that of M4, aiming for clean candidate windows
with clear events, somewhere between 5000-8000 or so total."

## In plain words

Review now has a queue called **"Auto-detect · unreviewed drops and rises, 4 channels (24 Nov)"** (queue 57). It holds
**5,291 events**: 4,440 drops and 851 sharp rises. They come from the four channels Auto-detect has been tuned on.
Every one is an event you have not judged before, on any copy of its channel. Each has a clean window around it.

The best come first. "Best" means Auto-detect is most sure of it, and an event that belongs to a run of events
resembling M4's runs is moved up a notch. Half the queue is above 0.94 confidence; the last items sit just above
0.6, the floor. Of the first 1,000, 461 belong to runs like M4's.

It is a normal Review queue. Your verdicts go into Review as always, and the events themselves stay the machine's
suggestions (CLAUDE.md rule 5). You don't need to rebuild anything to open it on your usual bridge; it is already in
your database.

## What is in it

| Channel | Drops | Rises | All | In runs like M4's |
|---|---:|---:|---:|---:|
| M2_aug CH7_B2 (0–528 h, 1 Hz) | 2,702 | 188 | 2,890 | 56 |
| MJu26a CH14 (300–564 h, the 2 Hz copy) | 1,201 | 635 | 1,836 | 140 |
| MJu26a CH15 (120–384 h, the 2 Hz copy) | 271 | 7 | 278 | 232 |
| M4 CH1_A1 (whole channel, 1 Hz) | 266 | 21 | 287 | 226 |
| **All** | **4,440** | **851** | **5,291** | **654** |

- **Confidence:** lowest 0.60, 10th percentile 0.72, median 0.95, 75th percentile 0.99.
- **"The channels you have been using"** means the four reference channels of the 19–23 Nov runs. The candidates are
  those runs' v4 results (`docs/autodetect/20261123_v4/`), made with the whole-drop rule at commit 79d0243e.
- **M4** is the recording usually held out. Its lock is off in your database today, and M4 has been an approved
  reference since 19 Nov. If you turn the lock back on, Review hides M4's 287 items, as it does every M4 item.

## What was left out, and why

Each of the 15,142 candidates from the four runs is counted once, under the first reason that applies:

| Reason | Left out |
|---|---:|
| confidence below 0.6 | 5,408 |
| **already reviewed**: you judged that event, on any copy of the channel | 1,555 |
| no detector, seed or rule vouched for it (R4 alone, or R4's window scan) | 625 |
| not clear against the noise in its own window | 601 |
| it is the recovery of the drop just before it, or the way back down of the spike just before it | 552 |
| its box is longer than the channel allows (see below) | 368 |
| **waiting in an open queue** (54, 55 or 56), so it is not asked twice | 364 |
| its box overlaps a better candidate's | 197 |
| a slow rise, not a spike (box over 3 minutes) | 85 |
| a jump far bigger than the event, which no detected event explains, sits in its window | 54 |
| its box runs on into a bigger event the other way | 35 |
| a span you judged an artifact sits in its window | 7 |

The rules, in order of how much they matter:

- **"Already reviewed" looks across copies of a channel.**
  - Your MJu26a verdicts sit on the 10 Hz copy and these runs use the 2 Hz copy. Review's own check cannot see
    across copies (see `docs/autodetect/CHANNEL_COPIES.md`), so this was settled before the queue was written.
  - It uses every judged event span from the thesis catalogue's reader (`collect()`): annotations and Review
    verdicts on detections alike.
  - A candidate counts as reviewed when a judged span covers at least half of the shorter of the two, the same test
    the Auto-detect viewers use to label "accepted"/"rejected".
  - **One exception:** a judged span longer than an hour and more than 4× the candidate does not count. Those are
    whole trains you accepted in one go: CH15's 21 train acceptances run up to 45 h. They say nothing about each
    event inside, so 31 events inside such trains are in the queue (27 on CH15, 4 on M4).
  - The imported 10-minute and blind-test windows are labels on windows, not on events, so they never hold anything
    back.
- **Not asked twice.** Events still waiting in the open queues made this week (54, 55 and 56) are left out.
  Archived and closed queues don't count.
- **Clean windows.** Review shows each event with ±120 s around it by default, and that whole window has to be clean:
  - no gap in the data;
  - no dropout, meaning one value repeated for a minute;
  - no span you judged an artifact;
  - no one-sample jump more than 3× the event's own steepest step that no detected event explains;
  - and the box itself must not run on into a bigger event the other way.
- **Clear events.**
  - The event's depth must be at least **15×** the noise in its own window: the spread of the signal about a
    10-second running median, outside the box. Noise-sized CH14 dips and M4 rises in noisy stretches scored 4–15;
    clear events score 26 to over 1,000.
  - Rises must be sharp, so a rise whose box runs past 3 minutes is a slow climb or a recovery.
  - Boxes may not be longer than 19 in 20 of the boxes that landed on events you accepted on that channel, nor
    longer than 20 minutes. That gives 9.5 min on M2_aug, 2.7 min on CH14, and 20 min on CH15 and M4.
- **Recoveries are not events of their own.** A rise counts as a drop's recovery when it starts within 30 s of the
  end of a drop at least 0.8× as deep. A drop counts as a spike's way back down when it starts within 30 s of a
  spike's end and is no more than 1.25× its height. The pipeline folds a return only when it starts almost
  immediately, so slower ones had stayed as candidates.
- **Each event is asked about on its own.** Review folds detections of one run that overlap into a single item, one
  key press for all of them. So two candidates whose boxes overlap are written to different runs ("lanes"). Review
  serves exactly one item per event: 5,291 for 5,291.
- Review's own same-recording check holds back **4** more, which leaves **5,287** to ask. These are events matching
  a span on the same recording that the rules above treated as a different event.

## "Runs like M4's": what that means here

M4's Auto-detect run found **38 runs** (sequences) of events:
- 29 are runs of drops and 9 of sharp rises;
- 5 to 55 events each (median 9.5), typically 7.5 minutes apart (10–90 %: 1 to 27 minutes);
- the gaps are fairly irregular (spread of the gaps about 0.9× their mean);
- each event lasts about 37 s and is 0.7 mV deep (medians).

Each run on every channel gets a profile of six numbers: how many events, how far apart, how regular the spacing,
how long each event lasts, how deep, and how sharp. All six are put on log scales where the quantity spans decades.

A run counts as **"like M4's"** when its profile is as close to one of M4's runs of the same kind (drops with drops,
rises with rises) as three in four of M4's own runs are to their nearest neighbour. Distance is measured in units of
M4's own spread on each number; the threshold is 1.76.

- M4's own 38 runs count by definition.
- So do 16 of M2_aug's 50 runs, 17 of CH14's 41 and 16 of CH15's 18. CH15's slow trains of drops 10–20 minutes apart
  are the closest to M4's.

An event in a run like M4's ranks as if it were **0.1 more confident**. So a 0.85 in an M4-like run comes before a
0.9 on its own.

**If this is not what you meant by "like M4", say what to look for.** For example, it could be the trains of sharp
rises, or one particular M4 stretch you had in mind; the order can be redone in seconds. The profile of every run,
and its distance to M4's, is in `sequences_m4_likeness.csv`.

## What was written to the database

Everything written is machine rows; nothing is a verdict.

- **Backups first**, with the sqlite backup API so the WAL comes along:
  - `DATA/db/backups/before_autodetect_queue_20261124_090532.sqlite`, the database before anything was written;
  - `…_091217.sqlite`, before the one correction below.

  Each is 874 MB. The second can go once you're happy with the queue.
- **Config 9694** (kind `autodetect`), whose settings record every threshold above.
- **Runs:** 9064–9071 hold two lanes per channel, and 9072–9073 hold the 11 added by the correction.
- **5,308 detections**, ids 13389236–13394543. Their `meta_json` holds:
  - the candidate's id in the v4 result;
  - its confidence, priority and clarity;
  - whether it is in a run like M4's;
  - its sources.
- **Queue 57**: a listed discovery-run queue that writes adjudications, in priority order.
- **One correction, made minutes after the first write.** The first write's item 36 turned out to be a 0.6 mV rise
  whose box ran on into a 12 mV drop. Hence the "runs into a bigger event the other way" rule. Applying it:
  - took 17 events off the queue's list; none had a verdict, and their rows remain, unqueued, like most detections
    in the database;
  - brought in 11 that had lost to them on overlap.

  `written.json` records both steps.
- Checked on a fresh sandbox copy (port 8823): the queue opens in Review at "0 / 5,287", the first item and an added
  one draw correctly, and there are no console errors.

## Files

- `scripts/autodetect/build_review_queue.py` chooses. By default it reads only, and writes `selected.csv`,
  `all_candidates.csv`, `sequences_m4_likeness.csv` and `plan.json` here.
  - `--write` makes the queue: it backs up first and refuses to make it twice.
  - `--update "why"` brings the existing queue in line with a new plan: it takes off what the plan dropped (unless
    judged), writes what it added, and re-orders.
- `scripts/autodetect/write_review_queue.py` is the write half. It uses `Working/autodetect/service.py`'s
  `write_detections`, now shared with the app's Send to Review, so both write the same rows the same way.
- `selected.csv`: the 5,291 in queue order, with each one's rank, channel, candidate id, box, polarity, confidence,
  priority, clarity, sequence and M4-likeness.
- `all_candidates.csv`: all 15,142, with the reason each was left out.
- `written.json`: what was written, and the correction.

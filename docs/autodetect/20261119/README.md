# Auto-detect — first prototype (19–20 Nov 2026)

**Open `index.html` in a browser** (double-click it, or serve this folder: the `autodetect-pages` entry in
`.claude/launch.json` runs `python -m http.server 8791` here). It links one interactive page per reference channel,
plus the first M2_aug run kept for comparison. In each page you can scroll
to zoom, drag to pan, shift-drag to zoom into a range, drag the box in the strip underneath to scan across the whole
stretch, and step through candidates with **Next / Prev** (or `n` / `p`). Hover or click a shaded region to see how
its confidence was built and what it lands on in your reviews.

## In plain words

You press one button and three kinds of witness look at the channel:

1. **Seed searches** ask "does anything here look like a shape you have already accepted?". There is one seed per
   shape family of your accepted catalogue: 64 families, each searched at its typical durations.
2. **Four precise detectors** (drop v1, drop v5, wavelet-encoded, BEADS-inverted) ask "is there a sharp fall here?".
3. **R4**, the classifier trained on your verdicts, judges every stretch the others point at. It also slides
   windows of 2, 6, 10 and 30 minutes along the channel, looking for anything the others all missed.

Where witnesses point at the same stretch, that is one **candidate**. Its **confidence** starts at R4's score and
rises with each other witness that agrees, and more so for a witness that has been right more often. Candidates
that are more likely than not, and that come in runs, form **sequences**.

No surrogates and no nulls are used: the aim is a fast, accurate first pass for review, not a significance test.

## What it found

Each reference is about 1.9 M samples, the size of a typical channel. "Found" counts how many of the accepted catalogue's events on the stretch a candidate at confidence ≥ 0.5 covers. "Hit rate" means: of the candidates that land on anything you reviewed, the share that land on an accepted event. Unreviewed stretches count neither way.

| Reference | Run time | Candidates at ≥ 0.5 | Found at ≥ 0.5 | Hit rate | Without R4's scan: candidates · found · hit rate |
|---|---:|---:|---:|---:|---|
| M2_aug CH7_B2, 528 h at 1 Hz | 84 s | 3,192 | 208 of 212 | 90 % | 1,483 · 194 of 212 · 96 % |
| MJu26a CH14, 264 h at 2 Hz | 61 s | 2,854 | 517 of 528 | 98 % | 931 · 507 of 528 · 99 % |
| MJu26a CH15, 264 h at 2 Hz | 50 s | 663 | 172 of 186 | 93 % | 465 · 166 of 186 · 94 % |
| M4 CH1_A1, 505 h at 1 Hz (R4 never saw M4) | 52 s | 719 | 44 of 47 | 83 % | 272 · 41 of 47 · 96 % |

**Speed.** About a minute per channel on this PC, against the 30–60 minute budget. R4's window scan and the seed searches take most of it. The first runs, made while other work was running, took 3–5 minutes.

**On M2_aug's 10-minute windows** (201 interesting, 294 not), candidates at ≥ 0.5 touch 94 % of the interesting windows and 46 % of the not-interesting ones. At ≥ 0.9 the figures are 89 % and 26 %.

## What the runs taught us

1. **Searching every seed family floods the channel.** The first run (kept as the comparison page, `M2_aug_CH7_B2__every_family`) searched all 64 families and gave 48,165 seed matches, 91 an hour, reaching all 27 rejected spans. Families whose own members differ from their medoid (r 0.69–0.93) match ordinary drift: comparing shapes after scaling them to the same size makes any smooth slope look like a slow drop. A stricter correlation line didn't fix it (r ≥ 0.98 still gave about 5,000 matches), and neither did a channel-relative amplitude rule. What worked is using only **tight** families, those where 90 % of members correlate with the medoid at r ≥ 0.95. That leaves 17 of the 64, which gave 1,754 matches (3.3 an hour). Of the 17, seven are families of seed-search matches (one fixed duration each: 377, 105, 816 or 21.5 s), eight are MJu26a CH14's narrow drops, and two are mixed. They reached 186 of the 212 accepted events and only 4 of the 27 rejected spans.
2. **R4's window scan floods channels R4 trained on, but not the one it hasn't seen.** It scores 32 % of M2_aug's windows and 43 % of MJu26a CH14's at ≥ 0.5, against 12 % on CH15 and 6 % on M4. Its own candidates (the ones no detector or seed found) reach few accepted events: 20 of 212 on M2_aug from 1,709 candidates, and 26 of 528 on CH14 from 1,923. The exceptions are CH15, whose train members are long (42 of 186 reached from 198 candidates), and M4. There, its top candidate is a run of regular upward spikes after the large drop at about 53 h. No detector proposed it, because they look for falls, and nobody has reviewed it, so it's worth a look. On busy channels the scan mostly fills the gaps between real events.
3. **Sequences only make sense without the scan.** logISI found no usable valley in the gaps on any of the four channels. On M2_aug and CH14 the deepest valley was too shallow (void 0.12 and 0.34, against the 0.7 it needs); on CH15 and M4 the gaps had a single hump. So the 1-hour rule did the work everywhere. With the scan's candidates filling the gaps, that rule chains busy channels into a few giant sequences (CH14: two, of 2,169 and 685 members). **Without the scan, CH14's largest sequence is 825 candidates from 382.6 to 474.2 h: the known 90-hour train, recovered as one sequence.** Untick "R4 scan" in a page and the band switches to these sequences.
4. **Some events are still drawn twice.** A detector box around two or more events is kept beside the tight seed matches inside it. Drop v5's boxes last about 4 minutes, while CH14's drops last about 10 s and come about every 4 minutes, so one box often spans two. Folding such a box into its events would need a new rule. A test of the simple version (accepting boxes up to 50× the event) lost 8 of CH14's accepted events, so it was not applied.
5. **This is a demonstration, not a validation.** R4 and the seeds learned from your verdicts on M2_aug and MJu26a, and several seeds are medoids of the very events they are graded on. M4 is the only fair test for R4. There, without the scan, 41 of 47 accepted events were found from 272 candidates (0.5 an hour) at a 96 % hit rate.

## Changed after the first run: these need your OK

- **Only tight seed families propose** (`Working/autodetect/seeds.py`, `MIN_FAMILY_LINE = 0.95`). You asked for a seed search for every family. The loose families are still listed on each page ("Seed families on this channel") with the reason they were not searched. Setting the value to `None` restores the first rule.
- **Near-duplicate folding in the merge** (`candidates.NEAR_DUPLICATE_RATIO = 2.5`). Two candidates of similar length that overlap by half of the shorter count as one event, for example two seed families matching one 10 s drop a few samples apart.

Left exactly as agreed, so you can judge them: R4's scan at 0.5, and sequences built with the scan's candidates included. Each page's "R4 scan" checkbox shows the result without them.

## The method, decision by decision (agreed in the 19 Nov grilling)

| Decision | What was built |
|---|---|
| What a signal is | One channel at 2 Hz or less, its full length. The references are cut to about 1.9 M samples, the size of a typical channel (both the mean and the median across the active recordings). |
| Seeds | Shape families rebuilt from the accepted catalogue's **2,283 single-event spans**, using g-11's recipe (shape distance, Ward, cut 0.6, at least 10 members, on the Library's 64-px envelope). The result is **64 families** covering 2,061 events. g-12 groups by recording, not by shape, so it has no shape medoids. The rebuild is kept in `seed_bank/` and is not saved to the Library. |
| Seed match line | No surrogates. A stretch matches when it correlates with the medoid at least as well as 90 % of the family's own members do; the lines range from r ≥ 0.69 to r ≥ 0.995. Each medoid is searched at the family's 25th, 50th and 75th percentile durations, with repeated durations searched once. Matches smaller than the dataset's noise floor are dropped: Settings › Datasets gives 0.3 mV for M2_aug and 0.03 mV for MJu26a; M4 has none set, so the Library's 0.1 mV is used. **Changed after run 1:** only families whose own line is at least 0.95 are searched (17 of 64). |
| Detectors | drop v1, drop v5, wavelet-encoded and BEADS-inverted, each at its default template setting. They run in memory through the same block calls as Discovery; nothing is written. |
| Models | R4 (the frozen 20 Oct MiniRocket model: events and windows, 4,992 features, Platt probabilities) scores every candidate's own span, using its own input rule: the span plus a quarter either side. It also scans 2, 6, 10 and 30-minute windows that each overlap the next by three quarters. A window becomes a candidate only if it scores at least 0.5 and is the best of the windows overlapping it. No CNNs. |
| Merging | The tool's own same-event rule (`candidate_events.build_events`, §4.6), then two new steps. First, **near-duplicates fold**: candidates of similar length (within 2.5×) that overlap by half of the shorter count as one event drawn at a small offset. This was added after run 1, and the survivor keeps its own span, so a train cannot chain into one candidate. Second, **loose boxes fold**: a box that holds exactly one tighter candidate (at least a tenth of its length) is drawn by the tighter box. Drop v1's windows start on a 98-second grid, often minutes before the fall, so without this every such drop would appear twice. |
| Confidence | `1 − (1 − R4) × Π (1 − ½ × precision)` over the sources that agree, where agreeing means covering at least half of the shorter of the two spans. Precisions: drop v1 0.955, drop v5 0.812, wavelet 0.862, BEADS 0.675 (thesis Table 6, M2_aug), seed 0.9. R4's scan never reinforces a proposal, because R4 has already scored that proposal's own span. |
| Shown | Every detector and seed proposal is shown; by construction its confidence is at least about 0.34. R4-scan windows are shown when they score 0.5 or more. Shading runs from faint at 0.3 to solid at 1.0. |
| Sequences | The logISI train finder (automatic mode) over candidates with confidence ≥ 0.5, needing at least 5 members. When it finds no valley in the gaps, the 1-hour gap rule takes over. |
| Grading | **Found**: one of your accepted catalogue spans is covered by a candidate, each covering at least half of the shorter of the two. **Hit rate**: of the candidates landing on reviewed material, the share landing on an accepted event. On M2_aug the 10-minute windows are also counted: the share of interesting and not-interesting windows touched. |

## Files

- `index.html`: the four references.
- `<reference>/viewer.html`: the interactive page. It is self-contained, and its samples are embedded at 16 bits, far finer than the noise.
- `<reference>/candidates.csv`: every candidate, with absolute sample bounds (`start_idx`, `end_idx`), `confidence`, `p_r4`, the sources that agreed, how the confidence was built (`lifts`), the seed families that matched, what it lands on (`known`) and its sequence. It is ready to become a review queue.
- `<reference>/sequences.csv`, `proposals.csv` (every raw detector or seed proposal), `scan_hits.csv` (R4's kept windows), `known_*.csv` (the answer sheet) and `run.json` (timings, counts, the grading table, the seed report).
- `seed_bank/`: the 64 medoids (`seed_bank.npz`), their durations, lines and provenance (`seed_bank.json`).

Code: the engine is `Working/autodetect/` (UI-free: chains, seeds, scan, blend, candidates, sequences, pipeline) with
tests in `tests/test_autodetect.py`. The prototype scripts are in `scripts/autodetect/`: `build_seed_bank.py`,
`run_references.py` and `make_viewer.py`.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/build_seed_bank.py
    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/run_references.py
    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/make_viewer.py

Read-only throughout. The database is opened `mode=ro`, the channel files are memory-mapped, and a guard refuses
any write under `DATA/`.

# Drop events and sequences: experimental plots (23 Nov 2026)

You asked for this before heading off: take everything reviewed so far, plus the whole-drop analysis, and make
experimental plots. That means box plots per species, a finer and uneven waveform map, one figure per sequence (the
CH14 sequences and the hand-labelled ones), and a try at separating interleaved kinds of drop (the CH14 train first).

**Open [`index.html`](index.html)** (every figure with its caption, in order) or browse the folders. The script is
`scripts/library_analysis/drop_plots_20261123.py`. It reads the database read-only, writes only this folder, and
nothing is committed.

> **24 Nov update.**
>
> - **New** (finding 7 below and the "Shape grids" section of the gallery):
>   - uniform 10 x 10 waveform grids: fall time x amplitude, with how common each cell is shown two ways;
>   - three grids on time-free shape measures: steepness, recovery speed, and where in the fall the drop happens;
>   - species fingerprints for six pairs of measures.
> - **Changed**, at your request: every plot now treats every drop alike, judged or not. Only the few drops you
>   judged noise are left out, silently.
>   - The "accepted only" versions are gone.
>   - The CH14 numbers below are recomputed on the train's big drops, chosen by size, not by verdict.

---

## In plain words: what came out

**1. The CH14 train has two kinds of big drop, and they take turns.** *(the headline;
[`types/kinds_seq_254_MJu26a_CH14.png`](types/kinds_seq_254_MJu26a_CH14.png))*

Think of a heartbeat that alternates a strong beat and a weak one. The 90-hour MJu26a CH14 train's big drops (491 of
them) fall into two clear kinds:

- **thin drops** (266): about 9 mV deep, about 7 s wide. They snap down and snap back.
- **wide drops** (225): about 12 mV deep, about 24 s wide. They snap down the same way, but climb back slowly in two
  stages.

From about hour 20 the two kinds run as two parallel bands through the whole train, both slowly deepening. And among
the big drops they alternate:

- A wide drop follows a wide one only **0.68 times** as often as chance.
- A thin drop follows a thin one 0.77 times as often as chance.
- Thin→wide and wide→thin each happen **1.26 times** as often as chance.

"Chance" here keeps each drop within its own stretch of 10 drops and shuffles the order only inside it, so the slow
deepening cannot fake the result. All four have p < 0.001.

The pattern is sharper still in the ~500 drops you accepted (23 Nov): wide→wide 0.29 times, thin↔wide 1.4 times. That
is because the size-chosen set also takes in some slower drops.

You can see the alternation by eye in two places:

- the close-ups of the trace in that figure: the colours alternate;
- the kymograph [`extra/kymograph_seq_254.png`](extra/kymograph_seq_254.png): long and short dark bands alternate row
  by row, and sorted by depth there is a sharp step where thin gives way to wide.

The wide (and deeper) drops also come *sooner* after the drop before them: a median wait of about 470 s, against about
790 s for thin drops. The 18 Nov prototype hinted at this alternation (49 % against 37 % switching); it is now clear.

**2. CH14 also has a third, small kind that nobody has reviewed.** *([`types/kinds_seq_254_MJu26a_CH14.png`](types/kinds_seq_254_MJu26a_CH14.png))*

All drops of at least 15 times the noise were included, without the rule's "15 % of the biggest drop" floor. That
turns up **232 small sharp drops**: about 1.8 mV, about 2 s wide. They form a third smooth band that rises with the
other two, so they look like a regular population rather than noise.

They never reached a review queue, because the candidate queues kept the relative floor. A fourth group (about 0.7 mV,
slow, 443 drops) clusters in two noisy stretches (hours 12–14 and 20–25) and looks like wander or noise.

**3. In the oyster hand-labelled sequences, drops tend to come in runs, not to take turns.**
*([`types/`](types/), [`types_summary.csv`](types_summary.csv))*

Each drop was called big or small against its own neighbourhood (the 21 drops around it). Then the test asked whether
neighbours switch kind more or less often than locally shuffled drops. In 10 of the 15 long oyster sequences (M2_aug
and M2_concat), big drops follow big ones, or wide follow wide, more often than chance. That is at p < 0.05 locally,
unadjusted; one or two would be expected by chance.

CH14 is the only sequence that alternates. So the CH14 train looks like a different kind of process from the oyster
trains.

**4. "Longer wait, bigger drop?" There is no single rule.** *([`extra/wait_vs_depth.png`](extra/wait_vs_depth.png))*

The idea was a capacitor that charges and then discharges. With every drop included (24 Nov):

- In all eight long sequences, a deeper drop is followed by a longer rest: ρ +0.14 to +0.63, strongest in seq 136.
- The wait *before* a drop says much less (ρ −0.14 to +0.29).
- One wait predicts the next (ρ +0.16 to +0.37): slow and fast stretches persist.

Careful: this depends on which drops are counted. Small drops crowd into noisy stretches, and that alone links
"small" with "short wait".

On your accepted drops only (23 Nov), CH14 went the other way. There, deeper drops came with *shorter* waits (ρ −0.31
before, −0.23 after), and one wait did not predict the next (ρ 0.00). That is the alternation again: wide drops come
early.

So the honest reading is that the big drops' own timing differs from the timing of the mixture. We'll take this
sequence by sequence.

**5. The species differ in shape, but each species really means "its best-reviewed channel".**
*([`species_boxplots.png`](species_boxplots.png), [`species_typical_shape.png`](species_typical_shape.png),
[`species_fall_vs_recovery.png`](species_fall_vs_recovery.png))*

| species | drops | median amplitude | median width | median recovery | median fall (steep part) |
|---|---:|---:|---:|---:|---:|
| oyster | 2,067 | 7.3 mV | 71 s | 37 s | 43 s (21 s) |
| chocolate oyster | 137 | 6.4 mV | 55 s | 41 s | 14 s (10.5 s) |
| snow oyster | 88 | 3.2 mV | 76 s | 42 s | 38 s (12 s) |
| lion's mane | 993 | 9.3 mV | 22 s | 12 s | 10 s (4 s) |
| Asian shiitake | 69 | 2.5 mV | 176 s | 99 s | 86 s (19.5 s) |

- **Lion's mane drops are square.** Scaled to the same size, they fall, sit flat at the bottom, then snap back. The
  others are V- or U-shaped with a slow climb back.
- **Lion's mane recovers about as fast as it fell** (median recovery ÷ fall 0.9). The oysters and shiitake climb back
  1.6–2.4 times slower than they fell.

But 504 of MJu26a's 656 drops are on CH14 (mostly the train), so "lion's mane" here largely means "the CH14 train". LM,
the other lion's mane recording, looks very different: median width 380 s against MJu26a's 14 s. Likewise oyster is
mostly M2_aug (1,789 of 2,067).

Widths in oyster and chocolate oyster have two peaks (about 40 s and about 700 s): two time scales of drop.

**6. The finer map.** *([`map_width_medoids.png`](map_width_medoids.png), [`map_width_heatmaps.png`](map_width_heatmaps.png),
[`map_width_medoids_zoom.png`](map_width_medoids_zoom.png))*

The width–amplitude plane is now cut into 184 cells (193 on the fall-time map). A cell splits in four while it holds
more than 36 drops, up to six times, so the grid is finest where drops crowd.

- The crowded middle (5–30 s wide, 5–15 mV) is almost uniform: square drops, blue, meaning they agree.
- Wide cells (over 300 s) and very small drops (under 1 mV) are red: their shapes disagree. Some of that is real and
  some is what happens after the drop (another drop, or drift).
- The heat-map version overlays every drop in the cell, so you can see whether a cell is one shape or a mixture (a
  crisp dark line, or a smear).

**7. Shape without time: drops morph from spikes to square wells to steps (24 Nov).**
*([`grid10_steepness_recovery_shaded.png`](grid10_steepness_recovery_shaded.png) and the other `grid10_*` figures)*

Imagine putting every drop on a stretchy film so that each one takes exactly "one unit" to fall and is exactly "one
unit" deep. What is left is pure shape. Two numbers describe that shape without any clock:

- **Steepness**: how much steeper the fall's steepest moment is than its average slope. A gentle straight ramp scores
  about 1; a sudden cliff scores 10 or more.
- **Recovery speed**: how long the drop takes to climb half-way back, divided by how long it took to fall. 1 means it
  climbs back as fast as it fell; small numbers mean it snaps back; the last column holds drops that never climbed
  half-way back.

On a 10 x 10 grid of those two, the median drop of each cell changes smoothly across the page:

- **Top middle (the commonest):** gentle V-shaped dips that climb back in one or two fall-times.
- **Bottom middle:** sudden cliffs that sit flat at the bottom and then snap back. These are square wells, mostly the
  CH14 train; one cell holds 211 drops.
- **Bottom left:** needle spikes, a sudden plunge straight back up.
- **Right:** steps that go down and stay down. 733 of 3,354 drops (22 %) never climbed half-way back. That ranges from
  15 % of the lion's mane drops to 32 % of the shiitake ones.
- **Top left is empty:** no drop is both a gentle ramp *and* quick to recover. Gentle falls always recover gently.

A second grid ([`grid10_steepness_position_shaded.png`](grid10_steepness_position_shaded.png)) asks *where* in the
fall the plunge happens:

- Most steep drops plunge in the first fifth of their fall and then creep down the rest of the way.
- Gentle drops fall evenly.
- A separate group of 92 sharp drops (bottom right; MJu26a 45, M2_aug 35) creeps first and then plunges at the very
  end, recovering almost at once. That is a slow sag followed by a needle spike. The whole-drop rule counts the sag as
  the start of the drop, so these are worth a look by eye.

The third grid ([`grid10_position_recovery_shaded.png`](grid10_position_recovery_shaded.png)) shows the same thing as
a diagonal: drops that plunge at the end of a sag recover fastest, and drops that plunge at once tend not to recover.

The uniform fall-time map ([`grid10_fall_amplitude_shaded.png`](grid10_fall_amplitude_shaded.png),
[`grid10_fall_amplitude_opacity.png`](grid10_fall_amplitude_opacity.png)) is the adaptive map on an even 10 x 10
grid. Its shading, or the darkness of each waveform, is how common that cell is.

**8. Species fingerprints for six pairs of measures.** *([`species_fingerprints.png`](species_fingerprints.png))*

| species | median steepness | half-way down at | median recovery ÷ fall | never half-recovered |
|---|---:|---:|---:|---:|
| oyster | 2.7 | 0.45 of the fall | 1.6 | 25 % |
| chocolate oyster | 2.0 | 0.53 | 2.4 | 20 % |
| snow oyster | 2.6 | 0.38 | 2.0 | 23 % |
| lion's mane | 5.7 | 0.29 | 0.9 | 15 % |
| Asian shiitake | 3.0 | 0.36 | 1.6 | 32 % |

- **Lion's mane is the outlier on every time-free measure:** its falls are cliffs (steepness 5.7 against 2–3), they
  plunge earliest, and they recover fastest. Again, that largely means the CH14 train.
- **Chocolate oyster falls most evenly:** half-way down at 0.53 of its fall, the closest to a straight ramp. It also
  climbs back slowest.
- On amplitude against fall time, the oysters and shiitake lie along a diagonal (bigger drops take longer to fall).
  Lion's mane's main patch sits apart, big and fast (that is CH14). A second, smaller patch from LM sits with the
  oysters.

---

## One question for you: answered, queue 56 built (24 Nov)

You chose (a). **Queue 56, "Events · CH14 small drops, sample of 50 (24 Nov)"**, is live in Review.

- What was left before sampling:
  - 25 of the 232 kind-B drops were already among your judged drops.
  - Of the other 207, 8 were already queued or judged. That left 199.
  - Review's own matching rule caught none.
- The 50 are spread evenly from hour 383 to 472 of the train, in time order, 0.5–2.2 mV deep. Their boxes do not
  overlap, so each is its own item.
- Built by `scripts/library_analysis/ch14_small_drops_queue_20261124.py`. The selection is in
  [`ch14_small_drops_queue.json`](ch14_small_drops_queue.json). The database backup is
  `DATA/db/backups/before_ch14_small_drops_20261124_055136.sqlite`.
- Re-running the plots picks up your verdicts from this queue.

The question as it was put:

**Should the 232 small CH14 drops (kind B, about 1.8 mV, about 2 s) be reviewed?**

They were found because these plots dropped the "15 % of the biggest drop" floor. They form a smooth band through 90
hours, which noise usually does not do. But no one has looked at them. If they are real, the CH14 train is three
kinds, not two, and the small ones sit between the big ones in a pattern worth testing.

- **(a) A sample queue of about 50 (recommended):** a quick look tells us whether the whole band is real, before the
  analysis leans on it.
- **(b) All 232 in a queue:** complete, but about 20 minutes of review.
- **(c) Leave them out:** the two-kind result above stands on your accepted drops alone either way.

My recommendation is (a). Nothing has been written to the database; I'll build it if you say so.

---

## What the plots are made from

**Drops (3,354; [`events.csv`](events.csv))**

- **2,573** accepted catalogue spans (individual spans), each represented by its main drop under the whole-drop rule
  (`docs/library_analysis/20261123/revised/whole_drop.csv`, rule 79d0243e).
- **781** drops you accepted (interesting or seed) in today's candidate-event queues (52–55), each measured by the same
  rule at its own top.
- Spans whose fastest movement is a rise are left out. Queue drops that overlap a catalogue drop are counted once.
- Widths exist for 2,621 drops; the rest never climbed half-way back before the next drop or two hours.

**Sequences (41; [`sequences.csv`](sequences.csv), [`sequence_events.csv`](sequence_events.csv))**

- 11 CH14 candidate sequences of queue 48: the MJu26a train (seq 254), one short MJu26a chain (255), five MJu26a
  multi-event spans (569–573) and four M2_aug multi-event spans (382–385).
- The 30 hand-labelled sequences (ids 119–148), approved or not.
- Their drops were found afresh by the whole-drop rule over the whole sequence. Floors: at least 15 times the local
  noise, and a core of at least 5 samples (the candidate queues' floors). There is no relative floor, so small drops
  next to big ones are kept.
- From 24 Nov every drop is treated alike, judged or not. The few you judged noise or artefact are left out of the
  figures.
- The M2_aug CH14 interesting 10-minute windows (queue 49) are too short for trends one by one, so they are on one
  contact sheet: [`sequences/ch14_m2aug_windows.png`](sequences/ch14_m2aug_windows.png).

## Figure guide

**How a drop is measured**: [`anatomy_example.png`](anatomy_example.png). One ordinary drop with amplitude, fall
time, width and recovery drawn on it.

**Drops by species**

- [`species_boxplots.png`](species_boxplots.png): amplitude, width, recovery, fall time and the steep part of the fall,
  one box per recording, grouped by species. The last panel shows how often drops half-recovered, and how often the
  fall ran on as a long tail.
- [`species_rainclouds.png`](species_rainclouds.png): the same, one row per species (density, box, dots).
- [`species_width_amplitude.png`](species_width_amplitude.png): each species in the width–amplitude plane, each
  recording's median, and every species' 50 % and 90 % outline overlaid.
- [`species_fall_vs_recovery.png`](species_fall_vs_recovery.png): fall time against recovery. Is a drop fast down and
  slow up?
- [`species_typical_shape.png`](species_typical_shape.png): the median drop of each species, scaled by its fall time
  and by its width.
- [`species_summary.csv`](species_summary.csv): medians and quartiles per recording.
- [`species_fingerprints.png`](species_fingerprints.png): each species' densest half for six pairs of measures,
  including the time-free shape measures.

**Shape grids (uniform 10 x 10)**

- [`grid10_fall_amplitude_shaded.png`](grid10_fall_amplitude_shaded.png): fall time against amplitude on an even grid.
  Each cell is shaded by its share of all drops, and its medoid is coloured by how much its drops agree.
- [`grid10_fall_amplitude_opacity.png`](grid10_fall_amplitude_opacity.png): the same, with each waveform as dark and
  thick as its cell is common.
- [`grid10_steepness_recovery_shaded.png`](grid10_steepness_recovery_shaded.png) (and `_opacity`): steepness
  (shallow at the top) against recovery speed (quick at the left, never at the right). Each glyph is the cell's median
  drop scaled to its own fall time and amplitude.
- [`grid10_steepness_position_shaded.png`](grid10_steepness_position_shaded.png): steepness against where in the fall
  the plunge happens (the anatomy of the fall).
- [`grid10_position_recovery_shaded.png`](grid10_position_recovery_shaded.png): where the plunge happens against
  recovery speed.
- `event_shapes.npz`: each drop's scaled waveform, steepness and plunge position, cached.

**Shape map** (each in a width and a fall-time version)

- `map_*_medoids.png`: each cell's medoid (its most typical real drop), coloured blue where the cell's drops agree and
  red where they differ.
- `map_*_heatmaps.png`: every drop in each cell overlaid as a heat map, with the median in orange.
- `map_*_medoids_zoom.png`: the crowded middle, enlarged.
- `map_*_cells.png`: the cells over the drops, and each cell's majority species.

Each glyph is scaled to its own drops' amplitude; its place on the map gives the size. The glyph runs from half a cell
width before the top to 2.5 widths after (5 fall times on the fall map).

**Sequences, one by one**

- [`sequences/seq_<id>_<recording>_CH<n>.png`](sequences/): one figure per sequence.
  - At the top, the trace with every drop's fall drawn in blue.
  - Below, depth, fall time, width, fall rate and interval along the sequence, each with Kendall's tau (+1 a steady
    rise, −1 a steady fall, 0 no trend). The black line is a rolling geometric mean, which runs between interleaved
    bands rather than jumping from one to the other.
  - The last panel shows all five measures on one scale.
- [`sequences_overview.png`](sequences_overview.png): all 41 as barcodes (each tick a drop, red deeper and blue
  shallower than that sequence's median), with their trends.
- [`sequence_summary.csv`](sequence_summary.csv): drops and every tau.

**Two kinds of drop in one sequence**

- `types/types_seq_*.png` (every sequence with 40+ drops): big against small and wide against thin, each drop judged
  against the 21 around it. Each split shows:
  - what follows what, against shuffles of the whole order and within blocks of 10;
  - each drop against the next (taking turns fills the top-left and bottom-right corners);
  - the typical drop of each kind;
  - the waits before and after each kind.
- `types/kinds_seq_*.png` (sequences with 150+ drops that have a width): a mixture model finds the kinds in the
  depth–width plane, with BIC choosing how many. The figure shows three close-ups of the trace coloured by kind, the
  "what follows what" table against local shuffles, and the waits round each kind.
- [`types_summary.csv`](types_summary.csv), [`kinds_summary.csv`](kinds_summary.csv),
  [`kinds_transitions.csv`](kinds_transitions.csv) hold the numbers.

**Experiments**

- `extra/kymograph_seq_*.png`: every drop of a sequence as one row of colour, in time order (and sorted by depth, and
  scaled to its own depth). The sequence's shape history in one image.
- [`extra/wait_vs_depth.png`](extra/wait_vs_depth.png): charge and release? Depth against the wait before and after,
  and one wait against the next.
- [`extra/drop_raster.png`](extra/drop_raster.png): every reviewed drop on its channel's timeline. It shows where the
  review has looked as much as where drops happen.
- [`extra/size_distributions.png`](extra/size_distributions.png): the share of drops at least a given size, on
  log–log axes (is there a typical size?).
- [`extra/shape_space.png`](extra/shape_space.png): principal components and a t-SNE map of every drop's shape.
  - Component 1 (66 %) is mostly what the trace does after the half recovery (keeps climbing, or falls again).
  - Lion's mane forms its own arm of the t-SNE map: the stereotyped CH14 drops.

## Be careful with

- **This is a review sample, not a census.** The drops are the ones you reviewed. Recordings and channels with long
  trains (M2_aug CH1/CH2/CH4/CH6, MJu26a CH14) dominate their species.
- **Fall time includes the slow shoulder or tail** before and after the steep part. Its median is 1.1–4 times the
  steep part, depending on the recording (LM and M4 most). That is why the steep part has its own box plot. Recovery ÷
  fall time is therefore partly a shoulder measure.
- **The 15x noise floor is small at 10 Hz.** CH14's noise is about 0.027 mV, so 15x is 0.4 mV. The smallest CH14 drops
  (kind A) are likely noise; kind B is the open question above.
- **Kinds and splits are statistical cuts.** The mixture's ΔBIC says whether two groups fit better than one: see each
  figure's title, and `size_note` / `width_note` in [`types_summary.csv`](types_summary.csv). In many oyster sequences
  the answer is "a continuum cut in two".
- **p-values are not adjusted** across the many sequences and tests. The CH14 alternation (p < 0.001 on 495 drops) is
  robust. A single p ≈ 0.03 in a 50-drop sequence is not.
- Kendall's tau over sequences that mix small and big drops reflects the mix as well as any trend. Read it with the
  running medians, which are drawn per group.

## Regenerate

    PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=1 "/c/ProgramData/anaconda3/python.exe" scripts/library_analysis/drop_plots_20261123.py

The stages are `events species map grids sequences types extra`, and the default runs all of them. `events` rebuilds the
drop table from the database (about 20 s); the grids rebuild their shape cache (`event_shapes.npz`, about 35 s) by
themselves whenever the drops change. `sequences` re-finds the sequences' drops (about 10 s). The whole run takes about 8 minutes.

# Targeted diversity and consistency review — 8 November 2026

Queue **47** is ready at `http://127.0.0.1:8765/#/review/queue/47`. It contains **850 presentations**, initially all
unjudged: **750 new individual-event proposals**, **54 matched background windows**, and the **46 preplanned
RQ2 repeat checks**. Together with the separate existing 127-parent boundary view, that is 977 review items;
some boundary items contain several individual events. The CNN recovery is not required before reviewing.

| New proposal recording | Number | Main purpose |
|---|---:|---|
| SH | 200 | Broaden the currently 27-span shiitake collection |
| SO | 200 | Broaden the currently 22-span snow-oyster collection |
| MJu26a | 150 | Other channels/periods beyond the already reviewed long CH14/CH15 selections |
| M2_concat | 75 | More waveform/scale variety beyond source-seed matches |
| CO | 75 | Broaden the chocolate-oyster material |
| LM | 25 | Complement its larger existing reviewed population |
| M4 | 25 | New spans after the frozen classifier exam; that historical exam is unchanged |

These are plausible proposals, not promised accepted events. Provisional fastest-edge orientation gives 413
fall-oriented and 337 rise-oriented items; these labels are sampling descriptors and are not human waveform-family
labels. A rising segment may still prove to be a recovery or part of a compound waveform. Surrounding context is
visible, and the researcher can correct extents before treating a window as one complete event.

## Selection and identity

Input pool: registered real, completed, non-superseded, nearly full-channel classical runs, plus verified real
SpanSet geometries from completed returned tasks. CNN and seed-search proposals are excluded from new-candidate
selection. Root recipe `surrogate: true` requests a paired reference; `runs.surrogate_of_run_id` identifies the
actual null run. For returned caches, only keys in the real target's prefix list are read, and geometry length
must match the declared real detection count. No surrogate geometry is sampled.

The raw sampled inputs contain 87,694 registered detections and 6,014 returned geometries. Canonical physical
recording/channel coordinates are resolved before duplicate or prior-review checks, including all MJu26a aliases.
Previously reviewed spans of every verdict and known train regions are excluded from new proposals. Full-context
expansions are checked again against those exclusions. The existing reviewed long CH14 selection and CH15
206–283-hour selection are explicitly excluded on their own physical channels.

Quality/extent rules are operational sampling filters: finite native signal; sufficient swing versus local noise;
an extremum inside the detector window; 0.5-second smoothing; a prominence above the sampling floor; proposed
95%-prominence extents clipped between neighbouring substantial extrema. Three-second to 20-minute windows are
eligible. These shape proposals are not certified full-event boundaries. Retained raw shapes can be broad,
compound or recovery fragments, which is why the review and its wider context remain necessary.

Eligible distinct anchor pools: SH 899, SO 727, MJu26a 4,883, M2_concat 5,179, CO 1,703, LM 1,904 and M4 4,014.
Sampling balances provisional polarity, duration bands, within-recording prominence bands and channels, with
seeded random selection within strata and no more than one selected event per physical channel-hour. Selected
spans do not overlap. The source pipelines available differ across recordings, so this is not a matched
detector-performance comparison or a representative prevalence sample.

Background controls match a selected item's duration and physical channel and avoid already judged/selected
spans. The 46 repeats preserve the original panel's recording, coordinates and first answer, frozen privately
before creating the new queue. Their identities and answers are not shown during review. Assignment is recorded
in the original panel's ignored `repeat_assignment.json`; the old release script will not create duplicate repeats.

## What this can improve

- Accepted shape diversity and dataset/channel coverage for the next B6/B12 analyses and future classifiers.
- Additional rejected/background examples from the same recording groups.
- RQ2 within-reviewer repeat consistency across the transferred-drop panel.
- Examples of where extent correction or sequence extraction is still needed.

It cannot by itself establish species-specific physiology, exhaustive event recall, propagation or inter-reviewer
agreement. Keep its review outcomes separate from the earlier stratified detector precision estimates. Exclude
the repeats from counts of newly found events and from any later independent classifier evaluation. No verdict
is written automatically; accepted answers enter the next catalogue refresh through the existing adjudication path.

## Preparation and checks

Script: `scripts/thesis/diversity_review_20261108.py`, seed 2026110802. All source/selection keys and frozen first
answers stay under main's ignored `DATA/derived/library_diversity_review_20261108/`. No private answer key is
copied into the thesis repository. The public report contains aggregate design only.

SQLite backup: main `DATA/db/backups/before_diversity_review_20261108_201548.sqlite`. Creation wrote fresh machine
presentation detections and one blind queue, with scores/meta empty. **Zero human judgements were written by
preparation**. All 850 raw presentations remain separate served items, with zero judged at creation. Internal
signal QA inspected three proposals per recording; it was not shown to the reviewer. The server remains the
existing project server; no extra browser or training process is left running.

# Z — re-point Library's *Classify across channels* at the census core

**From:** the cross-channel workshop, 2026-10-27, Q22 (`docs/prompts/changes/cross-channel-explorer-decisions.md`,
D21). **Not in the build:** Library's member classifier stays unchanged while the census is built and read.

## The finding

`Working/library/matching.py::classify_family_across_channels` classifies a family member against every sibling
channel over the **member's own span**. It uses `cross_channel.cross_correlation_peak`, which searches **every** lag.
M2_aug members run to ~7,000 samples, so over a long span a shared slow drift can set the peak (RQ6: unrelated
drifting channels peak at a median |lag| of 114 s when the search is unrestricted). The random-time chance test
controls for this statistically, but the measurement itself is not the census's.

The census (`Working/cross_census.py`, S1 of `cross-channel-explorer.md`) does two things differently:
- it measures on an **onset window** (−60 s, +180 s);
- it searches the lag only within **±50 s**.

It also adds the pack rule: a cross-pack copy is an artifact, and a cross-pack non-copy is a shared driver.

## What re-pointing would take

- Feed `classify_family_across_channels` through `cross_census.measure_pair` and `census_bin`, so there is one
  measurement and one set of bins. A member's onset is the member's start, or its own onset if it carries one.
- **Stored meaning changes.**
  - Re-run the classification on the families in use (g-11), and Recurrence's counts move.
  - Tests that pin the member-span behaviour (`tests/test_cross_channel_simultaneous.py`,
    `tests/test_webui_cross_channel.py`, `tests/test_webui_suspected_artifact.py`) change on purpose, and the commit
    says so.
- The per-member Suspected-artifact queue (`artifact_queue.py`) could then be retired in favour of the by-instant
  queue (S5).

## When

After the census has been run and read on M2_aug, and only if the census and the member classifier disagree enough to
matter: compare their artifact flags member by member first.

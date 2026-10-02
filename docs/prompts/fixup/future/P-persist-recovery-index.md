# Stub — P: `recovery_idx` is computed and discarded

**From Round 7.** Small, and it unblocks `N-event-extent.md` and bears on **Q26**.

## The finding

`Working/interrogation/event_shape.py` computes where an event recovers — *"first return to extremum
+ 0.5 × amplitude after the extremum, interpolated; searched past the window end but not into the
next event's window, and at most 10 event widths; not reached → NaN"* (`:160-162`) — and assigns it
at `:360` as `recovery_idx`.

Then `MEASURES` drops it (`:124-126`):

    # The measures a stored motif carries (`motif_features`): everything but the indices,
    # which only mean something against one trace.
    MEASURES = tuple(c for c in COLUMNS if not c.endswith("_idx"))

So **`recovery_time_s` (a duration) is persisted and `recovery_idx` (a boundary) is not.** The
reasoning is sound in general — an index means nothing without its trace — but this is the one index
that says *where an event ends*, which is exactly what nothing downstream carries.

`onset_idx` / `trough_idx` are not imported to the Library either (`docs/LIBRARY_STORAGE.md:442`
lists them under "**nothing** on the Library rows"); they are recovered by going back to the source
store row through `Working/library/features.py:85-91::detector_anchor`.

## Why it matters

- **`N-event-extent.md` has nowhere to put a morphology-aware end** without it.
- **Q26** — 41 % of the seed store and 34 % of the Library have no recovery under the current
  definition, all of it sharkfin morphology. Deciding whether a sharkfin's "recovery" should instead
  be measured to the next onset needs the boundary, not just the duration.

## What it would take

A channel-absolute recovery boundary stored beside the content hash, or a documented rule for
recovering it. Additive, through `init_db()`. The hard part is not the column — it is deciding what a
recovery boundary *means* for a morphology that never returns, which is Q26, and which is the
researcher's call.

"""
Working.library
===============
The motif library: how a shape becomes an entry, how an occurrence becomes a
member, and how the catalogue is grouped. `docs/LIBRARY_STORAGE.md` is the
standard this package implements — read section 2 before changing `identity`.

Nothing here imports a UI library; the package is callable from a bare script
exactly like the rest of `Working/` (CLAUDE.md rule 1).

Layout
------
`identity`      the shape-first content hash and the occurrence key
`dedupe`        exact duplicates (same hash) and near-duplicates (spec 4.6)
`revisions`     a member's current span pointer and its revision list (4.2)
`hand_edits`    edits keyed by content hash, so they survive a regroup
`matching`      the older matching half (ticket 36) — span -> entry, and edges
`importers/`    event stores, the catalogue, annotations, sequences
`grouping/`     the engine, the bases, and the registered clustering methods

`matching` was this package's whole content when it was the single module
`Working/library.py`. Its four public functions are re-exported here unchanged
so `from Working.library import match_span_to_entry` keeps working — it is
called by `Working.cross_channel` and by three test modules.
"""

from Working.library.matching import (
    classify_cross_channel_edges,
    match_span_to_entry,
    recurrence_count,
    search_entry_across_durations,
)

__all__ = [
    "classify_cross_channel_edges",
    "match_span_to_entry",
    "recurrence_count",
    "search_entry_across_durations",
]

# Stub — Q: nothing can correct a motif's extent

**From Round 7.** The machinery exists, is tested, and is called by nothing.

## The finding

`docs/LIBRARY_STORAGE.md:133-149` and `Working/library/revisions.py:10-35` specify "a human redrew
its extent" as a `motif_member_revision` row with `origin='human'` plus an `annotations` row, with
`stale_edges()` returning the `motif_edge` ids the change invalidates.

**No UI and no script calls `add_revision` with `origin='human'`.** The only writer is
`Working/library/importers/event_store.py:773-778` — machine, revision 1, at import.
`webui/server/library.py:1239-1245` *reads* revisions; nothing writes them.

So if a detection's bounds are wrong — and `N-event-extent.md` shows roughly half of
catalogue-corpus events have an edge set by a backstop rather than by morphology — **there is no way
to fix it in the app.**

## What it would take

A route and a surface. The core half is written and tested (`tests/test_library_revisions.py`), and
rule 5 holds: a human correction is an annotation, never a machine row.

The natural home is wherever `H`'s span slideshow lands, since flipping through events is when a
wrong extent gets noticed — but the slideshow is deliberately **read-only** (Round 7 Q16, so that it
does not quietly become a second Review), so this is a separate surface and a separate decision about
where a correction is made.

Note the interaction with `N`: correcting an extent changes the content hash, so a correction path
and a re-hash strategy are the same problem.

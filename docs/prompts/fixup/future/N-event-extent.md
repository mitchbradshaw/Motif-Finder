# Stub — N: an event's extent, made morphology-aware in fact

**From Round 7 Q17.** Not scoped. `H` draws the extent and explicitly does not redefine it.

## The finding

`detect5.window_bounds` (`Working/Detection/drop_motifs/detect5.py:507`) **already brackets an event
by morphology** — sharkfin: its own preceding rise → the next rise; trough: previous recovery → its
own recovery end. Its docstring states the reason: *"a trough spike's RECOVERY is an UP run and is
part of the motif, so a naive 'stop at the next UP run' would end the window at the bottom of the
trough and discard the right half of every event."*

**But a scale-free `6 × fall` cap is applied first and clamps every morphology branch**
(`detect5.py:165-169`, applied at `:550, :554-555, :564, :567, :571, :574`). Measured, the cap — not
morphology — sets the edge on:

| store | left edge capped | right edge capped | both |
|---|---|---|---|
| seed store (410 events) | **46 %** | 31 % | 24 % |
| oyster, drop_motifs10 (754) | **49 %** | 32 % | |
| sp385 (76) | 43 % | 41 % | |
| reishi_10hz (2425) | 5 % | 3 % | |

And **the stored row does not record which rule set its edge.** `H` marks a capped edge on the
drawing (Q18); it cannot fix the data.

## Why this is not a small change

**The stored extent IS the Library's identity.** The content hash covers the whole snippet
(`Working/library/importers/event_store.py:84, :571`), so two detections of one event with different
bounds hash as different motifs. Changing the extent rule re-hashes **all 3,603 entries / members /
revisions**.

That makes this `M`-class work: a backup, a migration through `init_db()`, an `audit_log` row, and a
verification pass that re-runs each recipe and compares. `M-migrate-legacy-detections.md` and its
report are the template.

## What it would take

1. Record **which rule set each edge** on the detector's own dataclass and through the store — the
   one bit of provenance everything downstream needs and nobody has.
2. Decide whether the `6 × fall` cap should exist at all, be per-morphology, or be a warning.
3. Re-hash. The migration must be idempotent and must plan zero rows on a second pass.
4. Related and probably first: **`P-persist-recovery-index.md`** — without a persisted end there is
   nothing to put a morphology-aware extent *in* below the detector's own dataclass.

Also unresolved and relevant: **Q26** (the sharkfin that never recovers — 41 % of the seed store,
34 % of the Library have no recovery and no FWHM under the current definition). A morphology-aware
extent and a morphology-aware recovery are the same question asked twice.

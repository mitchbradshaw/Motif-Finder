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

---

## Step 0 (added 2026-10-02) — does the slow rise belong to the fall before it or the fall after it?

**This now comes before everything else in this stub, because it decides what an event *is*.**

The researcher's reframe, measured (`QUESTIONS.md` "Q26, REVISED", `scripts/q26_sharkfin_recovery.py`,
`scripts/q26_rise_provenance.py`):

- A sharkfin's slow rise is recorded by the detector as the **next** fall's precursor
  (`up_region_start_idx` / `up_region_end_idx`, `detect5.py:827`), and `choose_morphology` is literally
  *"is each fall preceded by its own substantial rise"*.
- The researcher reads the same samples as the **previous** fall's **recovery** — every sharkfin
  sequence opens with a drop, so the shape is trough → floor → slow rise, not rise → fall.
- Measured on the real channel to the next onset: **121 of 154 sharkfins reach half recovery** (median
  199 s), against a stored post-context of 121 s. Exactly one of 154 genuinely does not recover.

**Both readings cannot be true of the same samples.** Today that climb is counted once, as
`precursor_height_mv` on the later event, and the earlier event's `recovery_time_s` is null — so one
event's extent is wrong whichever reading is right, and the sharkfin/trough discriminator rests on it.

Consequences this stub already carries apply in full: **extent is the Library's identity**, so changing
it re-hashes the affected rows (3,603 in `motif_features`).

Two findings to carry with it:

- **The detrend window is shorter than the recovery on two families** — id029 110 s against a 40 s
  half-recovery, id024 780 s against 476 s. So a longer stored snippet alone does not fix the numbers;
  the detrend window has to be set from the recovery scale, or recovery measured on the parent trace.
  It is also the open caveat on the measurement above: some of what was measured as recovery on the
  undetrended channel could be slow baseline drift, and separating those two is the first real task.
- **`trough_idx` is not the bottom of the excursion** — the trace keeps drifting down after it (a median
  −0.04 of depth by the quarter point, p10 −0.36). It marks the end of the fast fall. That affects
  `drop_depth_mv` and where a recovery clock starts.


## Decided 2026-10-03 (`QUESTIONS.md` Round 10, Q26d)

**The researcher's reading wins:** a sharkfin's slow rise is the **previous** event's recovery, not the next event's precursor. Build it after the fixups. It re-hashes Library rows, so it is an `M`-class migration with a backup first. Until then, RQ3 prefers trough families.

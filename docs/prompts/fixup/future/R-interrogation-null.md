# Stub — R: build P10's null properly

**From Round 7 Q27.** `H` deletes the two fake nulls; this builds the real one.

## The finding

The Aggregate page carried **two** fabricated nulls:

- **the scatter null** (`webui/client/src/interrogation/AggregatePage.tsx:310`) multiplied each real
  point by independent random factors, three times — the "null" was the data with noise on it;
- **the histogram null** (`:82`) was three summed uniforms centred on the midpoint of the observed
  range — a bell curve drawn behind the bars.

Both were labelled "matched windows" / "shuffled onsets", and the card cited **P10**, which specifies
*"matched random windows (200×) and shuffled onsets, with every fitted exponent shown beside the null
exponent"*. Its status in `docs/wayfinder/fog-of-war.md` (A22) is still `ticketable now` — **it was
specified and never built**, and the page inherited the spec's wording over a placeholder.

**The consequence worth carrying forward:** because the scatter null was the data with independent
noise on x and y, its fitted exponent was a *regression-diluted copy of the real one* — it lands
below the real β by construction. So prompt `E`'s reported id010 result, **β 0.28 against a null of
0.25**, was never a meaningful comparison. That null could be neither cleared nor failed. Any
conclusion drawn from it should be re-derived once a real null exists.

## What it would take

- **In the core, with a test.** A null is a statistical claim; it does not belong in a React
  `useMemo`. Matched random windows drawn from the same recordings, matched on whatever the claim
  needs matching on (duration, channel, recording, time of day), and genuine shuffled onsets.
- 200× is the specified count; confirm it is affordable on the real store before committing to it.
- **`kit/plots.tsx:496` `NullBand`** — *"a series drawn over its null p5–p95 band"* — is already
  written and has no caller. The drawing is done; the statistics are not.
- Re-state `E`'s width-versus-recovery finding against the real null once it exists.

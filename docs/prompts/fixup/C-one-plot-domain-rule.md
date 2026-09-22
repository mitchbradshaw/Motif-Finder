# Fixup C — one plot-domain rule, across Review, Library and Explore

**Blocked on prompt `B` landing.** `B` fixes the volts-labelled-mV error; every number below moves by
1000x when it does. Running `C` first would scale a mislabelled quantity beautifully, which is worse
than the current state because it is more convincing. **Check that `B`'s report exists and its gate is
green before starting.**

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; Bash tool = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md` — every rule binds you, especially the
priority order it now carries: **workflow friction first, legibility second, completeness last.** Then
read `docs/prompts/fixup/QUESTIONS.md` **Q-X2.1 / Q-X2.3 / Q-X2.4 / Q-R1.1** (the decisions this prompt
implements), `docs/prompts/fixup/reports/B-units-and-amplitude.md`, and the symptom rows this closes:
`00-cross-cutting.md` X2, `07-review.md` R1, `08-library.md` L0–L3.

Commit prefix `fixup-c:`. Test-first; your first commit touches only `tests/` and must fail.

## The decision you are implementing

PRD **D5** — one shared unnormalised mV domain per page — **is replaced.** The researcher's call,
recorded 2026-09-23:

> **Per-card measured domain, with the shared scale drawn as a reference bar.**

D5 existed for a real reason: family peaks span four decades, and normalising each card destroys the
evidence that one family is micro-volts and another is millivolts — which PRD §"Storage" says
explicitly is evidence of scaling laws for depolarisation events. **The reference bar keeps that.**
Each card gets a domain measured from its own trace, so the *shape* is legible; a bar drawn to the
page's shared scale on every card says how big this card is *relative to the others*. Nothing is
normalised and nothing is hidden — the comparison moves from the axis to the bar.

**The acceptance test, and it is not a nicety: NO MOTIF MAY BE CLIPPED IN ITS OWN THUMBNAIL.** Today
`MiniTrace` clamps silently, so a trace outside the domain renders as a line along the frame and reads
as data. After this prompt, a card's own domain contains its own trace, and the word "clipped" should
not need to appear on a card at all.

## Work (test-first per seam)

### 1. One rule, one implementation, three consumers

The point of this prompt being a cluster rather than three page prompts is that **there must be exactly
one function that decides a domain.** Put it where all three workspaces can import it. Today the logic
is scattered and inconsistent:

- `webui/client/src/library/chrome.tsx:301` — `sharedMvDomain`, the 75th-percentile rule (D5).
- `webui/client/src/library/AtlasPage.tsx:128-133` — the shared domain and the clipped-count note.
- `webui/client/src/library/FamilyPage.tsx:190-199` — **two** domains, sketch vs measured (see §3).
- `webui/client/src/review/parts.tsx:12` `Y_MV`, `review/Shell.tsx:18` `THUMB_Y` — hard-coded
  constants, corrected in magnitude by `B` but still constants.
- `webui/server/corpus.py::y_range` — Explore's per-channel min/max, server-side.

Decide where the seam is and say why in your report. **Do not leave two rules in the tree.**

The rule needs at least: a domain measured from the trace with a sane pad; a floor for a trace that is
genuinely flat (a zero-range domain must not divide by zero or render a degenerate axis); and the
page's shared reference value, computed once per page, passed to every card.

### 2. Review's constants become measured

`Y_MV` and `THUMB_Y` are per-candidate measured after this. Note what `B`'s investigation found about
them: **±0.44 was a correct centred domain for a whole-channel swing in volts** — a candidate's own
trace is a small fraction of that, which is exactly why every Review plot reads flat. A per-candidate
domain is the fix, and the reference bar is what stops the reviewer losing the sense of how big this
candidate is against the channel.

Review's own framing matters here: a reviewer is judging *whether this is a real event*, so the
amplitude relative to the channel's noise is part of the evidence, not decoration.

### 3. The Family page fetches real waveforms for its member cards

**Decision (Q-X2.3): drop the shape sketch.** Today the overlay plot draws the real stored snippet
while the member cards and the rail plot draw a *sketch* — amplitude and duration measured, waveform
not carried by that read — which is why the researcher sees the exemplar look like two different
things on one page. Both captions say so honestly, and it is still wrong: a member card that does not
show the member's waveform is not worth its space on a page whose job is looking at every member.

Fetch the waveforms. **The cost is a payload-size question to be measured and reported, not a design
one** — measure the family payload before and after, put both numbers in your report, and if a large
family becomes unacceptably slow, decimate the member traces (say so) rather than reverting to a
sketch.

### 4. Delete the accommodations the old rule needed

The `clipped` badge, the clipped-count note, the "shared mV scale · ±N mV" captions and the
explanatory `InfoTip`s are all scaffolding for D5. Where the new rule makes them false, remove them;
where a card still needs to say something about scale, let it say what the reference bar means. A
caption explaining why the plots are unreadable is worse than plots that are readable.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **Anything about units, `× 1000`, or the `units` column** | Prompt `B` owns it. If you find a display path `B` missed, report it, do not fix it |
| **`Plots/drop_motifs10`'s sub-floor entries, the per-dataset noise floor, `scale_band`, `is_pure` filters** | Q-X2.5 / Q-X2.7, owned by the Library prompt. **You will make these entries visible — that is correct and intended. Do not filter, hide or flag them** |
| **Library hand edits, `motif_features`, the Atlas/Recurrence click-through** | later prompts |
| **Polar and rose plots** | prompt `D` |
| **`DEFAULT_CHAIN`, the demo chain, Review classes, the cluster/classifier redesign** | unchanged |

## A thing you will see, and must not mistake for your bug

When per-card domains land, **the `drop_motifs10` entries — 88 % of the Library — will stop looking
like everything else.** Their median event is 0.219 mV against the seed store's 9.06 mV, and 31.6 % of
them sit below the 0.1 mV instrument floor, because that run used a derived `3x amplitude MAD` floor
(median 0.0127 mV) and a 7.9 s detrend window. Giving each card its own domain will draw those tiny
events large and legible.

**That is the rule working, not failing.** Do not add a floor, a filter or a minimum domain to make the
page look tidier. Making that population visible is a research finding the researcher wants; hiding it
inside a display rule would bury it again.

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client`;
2. `PYTHONIOENCODING=utf-8 … webui/smoke.py --url http://127.0.0.1:8765` against a `--sandbox` bridge
   **restarted immediately beforehand** — the page walk is not idempotent against its own writes and a
   second run gives three extra Settings failures (prompt `A` report §7);
3. `pytest` — baseline **1660 passed / 6 skipped / 0 failed**, not the 969 in
   `webui/PYTEST_GATE_FINAL.txt`. Compare failure **sets**. FastAPI files run under `webui/.venv`,
   where `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails
   pre-existing and is not yours.

**The acceptance evidence.** Add a smoke check that measures, in a real browser, that **no trace's
rendered path leaves its plot box** on the Library Atlas, the Library Family page and the Review
inspector — the machine version of "no motif is clipped in its own thumbnail". Prompt `A` did this for
axis-label collisions (`getBoundingClientRect` over three surfaces); follow that pattern. Screenshot
the same Library family, the same Review candidate and the same Explore channel before and after into
`webui/screenshots/fixup/C/`.

## Report

`docs/prompts/fixup/reports/C-one-plot-domain-rule.md`: the seam you chose and why; the family payload
size before and after (§3); every place a second domain rule was removed; what the `drop_motifs10`
population looks like now that it is legible, with a screenshot; defaults taken; items left;
out-of-scope files touched with reasons; the gate output; a short chat summary.

Then update `00-cross-cutting.md` X2, `07-review.md` R1, `08-library.md` L1–L3 and `QUESTIONS.md`
Q-X2.1/Q-X2.3/Q-R1.1 to say so.

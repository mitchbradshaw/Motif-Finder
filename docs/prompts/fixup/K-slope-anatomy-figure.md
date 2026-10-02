# Fixup K — the Slope page's anatomy figure stops making its marks up

**Ready to run, and it runs before `H`.** Small, one page, one cause.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`,
`docs/prompts/fixup/reports/E-aggregate-stops-fabricating.md` **§8.2** (which found this and could
not take it) and **§1** (the rules `D` measured), and `docs/prompts/fixup/QUESTIONS.md` **Round 7**
Q8.

Commit prefix `fixup-k:`. Test-first; first commit touches only `tests/` and must fail.

## The defect

**Analyse › Interrogation › 01 Slope (`analyse/interrogation/block/1`) draws an anatomy figure of one
event — onset, steepest point, trough, the chord, the tangent, the depth line, the baseline band —
and the marks come from `webui/client/src/fixtures/interrogation.ts::eventMarks`, over the event's
real trace.**

`SlopePage.tsx:138-185` builds the geometry; `:256-337` draws it; `:269` is the `LineChart` call.
"Steepest" is literally **`duration / 2`**.

This is the same lie prompt `E` spent a whole prompt removing from the numbers on the next page over,
surviving on the figure beside them — and it is **more** convincing as a figure, because a marked-up
picture reads as a measurement. A reader cannot tell a drawn tangent from a measured one.

It also opens **10 s before the onset whatever the padding setting says**, which is a second, smaller
fabrication: the frame claims to be the one the control selected.

## What to replace it with

**The real values exist and are stored.** `Working/Detection/drop_motifs/gradients.py` measures the
max slope and where it occurs; prompt `D` put the measures in `motif_features` (71,980 values over
3,599 content hashes on the real database) and prompt `E` added the route that serves them:
`GET /api/interrogation/families/{key}/shape` (`webui/server/interrogation_routes.py`), which reads
`motif_features` by content hash where the Library carries it and otherwise measures on the store's
own snippet from the detector's anchors — **never writing**.

The detector's own anchors are `onset_idx` and `trough_idx`, and the bridge already serves them as
offsets into the snippet: `interrogation_routes.py:151-153` — `onset_offset`, `trough_offset`.

So: **every mark on this figure is available.** Draw those.

**Where a mark genuinely is not available for an event, do not draw it**, and say so — the pattern
`E` established: an absence is counted and named on the face of the card, never rendered at a
plausible-looking position. A figure that omits a tangent is honest; one that draws it at
`duration / 2` is not.

**Carry the rule.** `interrogation_routes.py:118-123` already prints a `rules` list beside its
numbers and `E` carried those onto the page. The rule behind "steepest" is the one `D` measured by;
print it, behind an info icon per Round 7 Q21, with the measured value visible.

## A warning about the size of this

**The page is a prototype on fixture geometry and is not wired to any adapter payload.** So this is
not a one-line change — it is wiring the figure to the route `E` already built. Scope it honestly: if
it turns out to be larger than one page's worth of work, **stop and say so** rather than
half-wiring it, because a half-wired figure puts `NaN` into React attributes and the smoke gate reads
that as a console error.

## Two things to leave alone

| Leave alone | Why |
|---|---|
| **The visual language of the figure** — what it should look like, the aspect, the scale bar, the per-panel domain | Prompt `H`, running next, owns the idiom. Change the *source of the marks*, not the design. `H` will redraw this figure against the standard and two idioms is the failure mode |
| **`interrogation/Rose.tsx`** — the second, prototype rose on the same page (`SlopePage.tsx:352, :377`), fed by fixtures, whose header says *"the kit has no polar plot"* | `H` decides which of the two roses survives and where it lives |

Everything else about Interrogation is `E`'s and is done.

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client` — **into your own dist** (`run_server.py --dist`;
   check the `CLIENT = …` banner line before trusting a screenshot);
2. `webui/smoke.py` against a `--sandbox` bridge, restarted immediately beforehand, **never while
   `pytest -n auto` is running**. The Slope page's existing states must keep passing and you should
   add one that asserts the marks come from the payload — grepping the client for `eventMarks` is the
   cheap pin, measuring a drawn tangent's position against the served `max_slope` is the real one;
3. `pytest -n 4` against the **1874 passed / 8 skipped / 0 failed** baseline, comparing failure
   **sets**, which are empty.

**Standing failures that are not yours:** under `webui/.venv`,
`test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers`. In smoke, the four
Settings registration `Locator.click` timeouts, `discovery.runs--default`, and
`analyse.interrogation--fixup-d-sequence-rose` (a cold-bridge settle flake — it passes on a warm
re-walk).

**Evidence.** Before/after of the anatomy figure on the same event into `webui/screenshots/fixup/K/`,
and **a table in your report of where each mark was drawn against where it actually is**, for a
handful of events — the same shape of evidence `E` and `G` produced. If "steepest" moved a long way
on real events, that number is the point of the report.

## Report

`docs/prompts/fixup/reports/K-slope-anatomy-figure.md`: the drawn-versus-measured table; which marks
had no measurement and what the figure does instead; whether the padding setting is now honoured;
how big the wiring turned out to be; defaults taken; items left; out-of-scope files touched; the
gate; a short chat summary.

Then close `QUESTIONS.md` Round 5's Slope-figure row and `03-analyse-interrogation.md` **I6**.

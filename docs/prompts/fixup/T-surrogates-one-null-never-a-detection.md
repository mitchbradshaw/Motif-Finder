# Fixup T — the surrogate: the page names the null it used, and a surrogate is never a detection

**Q35–Q38 were answered in the 2026-10-03 grilling (below); no grilling round.** *(Original note:* opens with its own short grilling round, `QUESTIONS.md` Round 9, Q35–Q38.) Each question carries a
recommended default; if the researcher has not answered, **take the default and say so in the report** —
do not wait. Part A below needs no decision and can start at once.

**This is not `future/R-interrogation-null.md`.** `R` is Interrogation's null — matched random windows
and shuffled onsets (P10), neither of which exists. This prompt is the **signal surrogate**
(`preprocessing.surrogate`, phase-randomised) that Discovery already draws. The symptoms have been
sitting in `05-discovery.md` as **D3, D4 and D5** since wiring; `docs/RESEARCH_READINESS.md`
(cross-cutting item 2) measured them again, and found Part A.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md`,
`docs/prompts/fixup/05-discovery.md` D3–D5, `docs/prompts/wiring/reports/04-discovery.md` ("Left"),
`prototyping/UI_FUNCTIONAL_SPEC.md` §7.3, §7.6 and §9.4, and `docs/PIPELINE_PRD.md` "Surrogates".

Commit prefix `fixup-t:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only.** Runs after `L`; it is cross-cutting, so **it runs alone**.

## Decided — `QUESTIONS.md` Q35–Q38 and Q-Null-1 (2026-10-03). No grilling round needed.

- **Q35:** N surrogate draws per run, N a Settings › Nulls key per run kind — **20 for template runs, 200 for seed searches** — and every surface prints the count that run actually drew.
- **Q36:** Settings offers only what the block implements; *circular shift* is dropped. **`phase_randomize` is the default null for every detection chain.** `block_shuffle` stays on offer with this sentence beside it: *block shuffle keeps any motif shorter than a block intact, so it tests timing and order (trains, intervals), not shape.*
- **Q-Null-1:** `block_s` defaults to **1.0 s** today (`Adapters/preprocessing_surrogate.py`, `Working/discovery/seeded_search.py:143`), which at 1 Hz is a one-sample block — a sample shuffle, neither null. New default: **twice the longest motif under test**; the block **refuses `block_s · fs < 2`**; the length is shown in Settings › Nulls. Add, do not change, the two existing methods' tested behaviour beyond this default and refusal.
- **Q37:** wire the α / correction keys through to `cut_rule()`; default stays `none`; the sentence beside the cut is generated from the values used (none / Holm / Benjamini–Hochberg, per channel).
- **Q38:** wire the Analyse toggle, **default OFF in Analyse**; when on, the terminal row reads detected-versus-surrogate.

## Running alone (2026-10-03)

**Wave 3: nothing else runs while you do.** `AB` (wave 2) is told to finish or report a part before you start. Check `git status` and the worktree list before you begin; if another agent's uncommitted work is present, stop and say so.

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/rq_roundA/RQ1…RQ6 (all six)` per that folder's README.

## Part A — a surrogate detection is being read as a detection (no decision; do this first)

A paired surrogate run is a real `runs` row (`surrogate_of_run_id` set) in the same run group as the run
it shadows, and the executor writes its spans to `detections` like any other run's. The PRD's promise is
that *"nothing surrogate-derived can enter the library"*. Nothing enforces the wider version of that:

- **The real database holds 6 surrogate runs carrying 30 of its 1,205 detections** (read-only count,
  2026-10-03; runs 66 and 68 carry 2 and 28).
- No reader outside the scoreboard knows. `webui/server/corpus.py` (`:263`, `:296`, `:320`, `:343`,
  `:365`) counts and draws them on Explore's corpus map, spans list and channel summary;
  `queries.queue_candidates` (`Working/database/queries.py:448`) would serve them to Review;
  `divergence_annotations_without_detection` (`:414`) treats one as "the machine found something here".
  Neither `corpus.py`, `explore_routes.py` nor `Working/review/` contains the word *surrogate*.

**Give the exclusion one home in the core** — a predicate or a helper every reader goes through — rather
than a `WHERE` clause pasted into nine queries. Then make every reader that means "what the machine
found" use it: Explore's coverage, spans and counts; Review's queues and the header's *N need you*;
the divergence queries; Library promotion (`Working/review/promotion.py:111`); the run history's
`n_detections` where it is shown as a result. **The scoreboard and the seed page's null are the only
readers that want them.** Report the count each surface showed before and after on the sandbox copy.

`L` adds a `run_ids` filter to Review's queues for the same reason; keep it, and make your predicate the
thing it rests on.

## Part B — the page names a null it did not use (D4)

Measured 2026-10-02: the session chip on Discovery › Runs and Compare reads *"null phase_randomize
200×"*; a template run's scoreboard row reads *"154 / 3"* — **one** surrogate realisation per channel
(`Working/run_groups.py::run_paired_recipe`, :62). A seeded search really does draw 200 per channel
(`null.draws 200`, `drawChannels 600`). Two different nulls under one chip.

After Q35: either a template run draws the N that Settings › Nulls says (N× the sweep — cost it, route it
to SLURM past the ceiling like any other estimate, and reuse draws while the recipe is unchanged, §9.4),
or it keeps fewer and **every surface says the true number for that run** — chip, scoreboard header,
Compare's *× null* tile. The chip must never state a count the run did not draw.

## Part C — Settings › Nulls offers a method the block does not have (D3)

§9.4 names *circular shift*; `preprocessing.surrogate` implements `phase_randomize` and `block_shuffle`,
and `seeded_search.resolve_null` (:87) refuses the third out loud. After Q36: the page offers what the
block implements, or the block gains the method with a test. Wiring's own note was that a circular shift
is a degenerate null for a shape search.

## Part D — α and the correction never reach the cut (D5)

`seeded_search.cut_rule()` holds α = 0.01 and *"correction: none"* in one place and prints both — that
part is honest. The Settings keys still do not reach it. After Q37: wire the keys through, so the marker
is computed under the stated α and correction and the sentence is generated from the same values.

## Part E — the Analyse chain's toggle (Q38)

`analyse/toolbar.tsx:54` renders *"surrogate · not in this slice"* and every run footer ends *"no
null"*. The PRD says every run carries a surrogate toggle, on by default. After Q38: wire the toggle to
`run_paired_recipe` and show detected-versus-surrogate on the terminal row, or leave it and make the
chip say plainly that Analyse runs carry no null and Discovery is where a null is drawn.

## Leave alone

| Leave alone | Why |
|---|---|
| Interrogation's null | `future/R-interrogation-null.md` |
| The precision and recall rule | `X-divergence-read-properly.md` (it implements Q-D2) |
| `preprocessing.surrogate`'s two existing methods | they are tested; add, do not change |

## Acceptance — in a browser

1. Explore › Corpus on `M2_aug_concat_fs1.mat`: the detections total no longer includes a surrogate
   run's rows; the number it dropped by equals the surrogate detections on that file.
2. Discovery › Runs: for a template run and a seed run, the chip, the scoreboard's *null expects / draws*
   and Compare's *× null* state the same draw count, and it is the count the run drew.
3. Settings › Nulls lists no method `resolve_null` refuses.
4. A Review queue over a run with a paired surrogate holds only the real run's detections.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge, alone on the machine,
finishing on the **full** walk; `pytest -n 4` against **1952 passed / 17 skipped / 0 failed** after `H`
(re-measure; compare failure sets). Standing failures that are not yours are listed in `README.md`.

Evidence into `webui/screenshots/fixup/T/`.

## Report

`docs/prompts/fixup/reports/T-surrogates-one-null-never-a-detection.md`: the before/after count per
reader; the draw count each run kind now uses and what it costs; which of Q35–Q38 were answered and which
took the default; items left; out-of-scope files touched; the gate. Then close `05-discovery.md` D3–D5
in place.

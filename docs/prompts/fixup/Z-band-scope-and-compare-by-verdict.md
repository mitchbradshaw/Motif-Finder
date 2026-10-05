# Fixup Z — a band is a scope, and Compare says what a human made of the remainder

**Runs after `L`.** **Wave 2, beside `AB`.** Q43 is answered (below).
**Q4 already runs by hand today** (`docs/RESEARCH_READINESS.md` §Q4); this prompt removes the hand work
and supplies the last clause of the question — *hand adjudication of the remainder*.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md` §Q4,
`docs/PIPELINE_PRD.md` "Band decomposition" and the decision-log row *"no fan-out inside a chain"*,
`prototyping/UI_FUNCTIONAL_SPEC.md` §7.3, §7.5 and §7.7, and `Working/run_groups.py:1–30` and `:118–138`.

Commit prefix `fixup-z:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only.**

## Decided — `QUESTIONS.md` Q43 and Round 10 Q-W3 (2026-10-03)

- **A named band list in Settings › Analysis defaults**, used both as this band scope and as the presets of every bandpass block. Seed it with three log-spaced bands for a 1 Hz recording: **0.001–0.01, 0.01–0.1, 0.1–0.5 Hz**, each naming its `low_hz` / `high_hz`; editable; recorded in every band run's recipe.
- **Wavelet decomposition is now wanted for RQ4**, but in its own prompt, `AC`, after you. **Design the band scope so a band is a typed entry** (e.g. `{kind: "bandpass", low_hz, high_hz}`), so `AC` can add `{kind: "wavelet", level}` without reshaping your work. Do not build the wavelet kind yourself.

## Running in parallel (2026-10-03)

**Wave 2: you run beside `AB`** (`AB-models-paired-job.md`), another agent in the same checkout. The README's **"Running two prompts at once"** rules apply in full: your own port and a private client build served with `run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your report when you took the machine for smoke; shared files are **append-only and committed immediately with your own hunks only** (`git add -p`). If you need a file the other agent owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `Working/run_groups.py`, `Working/recipes.py`, Discovery › Runs *Apply template* and Compare pages, `queries.queue_candidates`, Settings › Analysis defaults |
| **`AB`'s — do not edit** | Models tree, the training-job core, `Adapters/catalogue_classifier.py`, `Working/hpc/job_export.py`, `Working/manifest.py`, `webui/server/training_routes.py` |
| **shared** | `webui/server/discovery.py` — **`AB` touches only the `/slurm` script writer**; you touch the apply-template and compare routes. Also `webui/client/src/api.ts`, `webui/smoke.py` |

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/rq_roundA/RQ4-bands-and-symbols.md` per that folder's README.

## Where it stands

By hand, on 2026-10-02: insert `preprocessing.bandpass` (0.01–0.1 Hz, order 4) ahead of the
`symbol_search` template in Analyse, save it under a name that carries the band, apply it and a
raw-signal template in Discovery over 452–456 h × 3 channels, open Compare. Result: *"Set overlap ·
matched at IoU ≥ 0.5"* — **only A 3 · both 0 · only B 74**. That is one band, one saved template, one
pair. Three things are missing.

1. **No band scope.** The core has had one since ticket 25 — a recipe `fan_out` of `kind: "bands"`
   (`Working/recipes.py:174–223`) and `materialize_target`, which prepends a bandpass step per target
   (`Working/run_groups.py:118`) — and nothing in `webui/server/` sends it. The PRD forbids fan-out
   *inside* a chain; it does not forbid a band **scope**, and names one: *"the band list is a fan-out
   scope exactly like the channel list."*
2. **Compare takes two runs.** The question is about the bands taken together — what any band found
   that the raw-signal run did not. §7.3: *"Comparison is n-way for counts, pairwise for inspection."*
3. **The remainder cannot be adjudicated as a remainder.** After `L` the whole of run B can go to Review;
   Compare still cannot say how many of its *only B* spans a human accepted, which is the answer.

## What to build

1. **A band scope on *Apply template*.** Beside *Channels in scope*, a band list — none (today's
   behaviour) or one or more `low–high Hz` bands. Each band becomes **one Discovery run across the
   channels in scope**: the template's steps with a bandpass prepended, built through the core's own
   materialisation so the recipe a band run records is the recipe a hand-built chain would. The run's
   label and its row carry the band; the template stays one template. Cost is N bands × the sweep —
   estimate it, and past the ceiling the primary action is *Create SLURM script* as for any run.
2. **Each band run is paired with its surrogate** exactly as an unbanded run is, the surrogate bandpassed
   the same way. After `T`, the draw count shown is the count drawn.
3. **A side of Compare can be a set of runs.** The band runs of one application are offered as one side,
   compared as their **union**, de-duplicated by the page's matching rule; the per-band counts sit under
   the union. *Step through the disagreements* names the band that fired.
4. **Set overlap by verdict.** Under *only A · both · only B*: for each, **judged · accepted · rejected
   · unjudged**, read live from `adjudications`. Then the act the question asks for: ***Send only-B
   unjudged to Review*** — a queue over exactly those detections (an additive `detection_ids` filter on
   `queries.queue_candidates`, beside `L`'s `run_ids`), opened the way `L` opens one.
5. **Say what cannot be attributed.** A banded template differs from the raw-signal detector in more
   than its band (measured: *"3 of 5 roles differ"*). Compare already says so; keep it on the union view,
   and recommend the like-for-like comparison — the same template with and without the band — where it
   exists (measured: `symbol_search` against its banded twin reads `attributable: true`).

## Leave alone

| Leave alone | Why |
|---|---|
| Fan-out inside an Analyse chain (Q-B-CHAIN) | still open, and forbidden by the PRD; a scope is not a fork |
| Wavelet band decomposition | `AC`, after you (Q-W3) — keep the band entry typed so it can be added |
| The precision rule and the *disagree* count | `X` |
| The filter itself (`preprocessing.bandpass`, order 4 by default) | tested; a band is a pair of numbers to it |

## Acceptance — the researcher's walk for Q4

1. Discovery › Runs → set the scope → *Apply template* → tick `symbol_search` (or any `→ SpanSet`
   template) → choose three bands → *Add and run* → three band runs appear, each `N found · 3 ch`, each
   with its null.
2. Apply `drop_detection_v1` with no band.
3. Tick the raw-signal run as A and the band set as B → *Compare* → the union's *only A · both · only B*,
   the per-band rows beneath.
4. *Send only-B unjudged to Review* → judge them → back in Compare the *only B* row reads
   *judged n · accepted k*.
5. That sentence — *of the n regions only a band found, a human accepted k* — with the null count beside
   it, is the answer to Q4 on that scope.

## The gate

`npx tsc -b` + `npm run build` (own `--outDir` and `--dist` if another prompt is in the checkout);
`webui/smoke.py` on a fresh `--sandbox` bridge, alone, finishing on the **full** walk; `pytest -n 4`
against the baseline in `README.md` (re-measure; compare failure sets).

Evidence into `webui/screenshots/fixup/Z/`.

## Report

`docs/prompts/fixup/reports/Z-band-scope-and-compare-by-verdict.md`: the recipe a band run records beside
the hand-built one (they must hash the same); the union and per-band counts on the sandbox scope; the
verdict split after judging a handful; Q43 answered or defaulted; items left; out-of-scope files touched;
the gate.

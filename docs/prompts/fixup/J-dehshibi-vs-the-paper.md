# Fixup J — the Dehshibi detector, checked against the paper that defines it

**Scaffold. One thing is missing and the researcher supplies it: the paper.** Attach the Dehshibi &
Adamatzky (2021) PDF with this prompt. Everything else below is written and measured.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/BLOCK_INTEGRATION.md`,
`docs/prompts/fixup/QUESTIONS.md` **U6** and **Round 5**, and
`docs/prompts/fixup/reports/A-no-decision-fixes.md` §3 (the measured evidence for the template's
current behaviour, with screenshots).

Commit prefix `fixup-j:`. Test-first; first commit touches only `tests/` and must fail.

## Before you change anything: the grilling session

**This prompt opens with questions, not code, and the researcher asked for that explicitly.** The
symptom is not "it is broken" — it is *"the researcher cannot tell what the algorithm is doing or
whether it works"*, which has at least four different causes with four different fixes:

- the implementation diverges from the paper;
- the implementation is faithful and the **paper's method does not suit this data** (1 Hz fungal
  recordings over hundreds of hours, against whatever the paper was built on);
- both are right and the **parameters** are wrong for these recordings;
- everything is right and only the **presentation** hides it, which makes it prompt `H`'s problem
  wearing `J`'s clothes.

**Read the paper and the code first, decide which of those it is, and come back with a grilling round
before implementing.** Put the questions in `docs/prompts/fixup/QUESTIONS.md` under a `J` heading and
stop there if the answer changes what you would build. A prompt that detects nothing is worth an hour
of questions.

The one thing you may do before that round: **run it and look.** `scripts/fixup_a_dehshibi_evidence.py`
already drives the template through a running sandbox bridge over two spans and screenshots the
result — extend or copy it rather than writing a third harness.

## Running in parallel

**Prompt `F` (`F-datasets-and-naming.md`) runs in the same checkout at the same time.** It owns
dataset identity: the schema, registration, Settings and the display name wherever it is printed.
You own the Dehshibi template and its block pages.

| | you (`J`) | `F` |
|---|---|---|
| core | `Adapters/preprocessing_wavelet_transform.py`, `detection_wavelet_summation.py`, `detection_summation_threshold.py`, `detection_dehshibi_spikes.py`, `Working/Detection/analysis/dehshibi_detection_analysis.py` | `Working/database/schema.py`, `Working/discovery/channels.py` |
| server | the template's serialisation, if it needs one | `registration.py`, `corpus.py` (naming only) |
| client | the Dehshibi block page and its process view | `settings/DatasetsPage.tsx`, `settings/ChannelsEventsPage.tsx`, `api/settings.ts` |
| smoke | `webui/smoke_pages/analyse.json` | `webui/smoke_pages/settings.json`, `explore.json` |
| port / dist | **8766** | 8765 |

**`F` owns `Working/database/schema.py` this wave.** If you need a column, ask `F` in
`docs/prompts/fixup/requests/J-to-F.md` — do not add one.

**Shared files — small hunks, commit immediately with explicit `--` paths, never `git add -A`:**
`webui/client/src/api.ts` (append only), `webui/smoke.py` (extend only).

**The build rules wave 1 learned the hard way** (QUESTIONS Round 5):

- **Build to your own `--outDir` and serve it with `run_server.py --dist`. Never build
  `webui/client/dist`.** The flag landed 2026-10-01 (`tests/test_webui_run_server_dist.py`):

      cd webui/client && npx vite build --outDir ../../<scratch>/dist-j
      python webui/run_server.py --sandbox --port 8766 --dist <scratch>/dist-j

  The bridge prints `CLIENT = …` in its banner when it is on a private build; **check that line
  before you trust a screenshot.** If it is missing, you are on the shared dist and `F` can
  overwrite you.
- **`npm run build` is `tsc -b && vite build`** and type-checks the whole tree, so `F`'s in-flight
  files can make it red. Run it for the gate at the end; `npx vite build --outDir <yours>`
  meanwhile. Report it if `F`'s files were red while you ran it.
- **`pytest -n auto` and `webui/smoke.py` must not run together** (prompt `B` §9: 23 spurious smoke
  failures). Use `pytest -n 4` and **announce in your report when you took the machine for smoke**.

---

## What is already true, measured

**There are TWO implementations of this detector in the repo and you must check they agree.**

1. **The template `dehshibi_spikes`** — four typed blocks, the stage-3 decision that a multi-stage
   detector is a *template*, not one adapter (`memory`: `dehshibi-detection-template`):

   | block | types | the paper |
   |---|---|---|
   | `preprocessing.wavelet_transform` | Signal → Encoding (image, scales × time) | Sect. 3.1 `slice_signal`, Sect. 3.2 Eq. 2, normalised per scale by Eq. 3 |
   | `detection.wavelet_summation` | Encoding → Scores | Ω(τ) = Σ_s g(τ, s) |
   | `detection.summation_threshold` | Scores → SpanSet | Algorithms 1–4, plus the Sect. 3.3 analytic-signal envelope |

2. **The monolith `detection.dehshibi_spikes`** — one adapter over
   `Working.Detection.analysis.dehshibi_detection_analysis.detect_spikes`, which returns
   `(spikes, pseudo_spikes, info)` directly.

Both claim to implement the same paper. **Do they produce the same spans on the same input?** Nothing
in the test suite asserts it (`tests/test_template_dehshibi.py`, `test_adapter_wavelet_*.py`,
`test_adapter_summation_threshold.py` test the blocks, not the equivalence). That is the first
measurement to make, and if they disagree, *which one is right* is the whole prompt.

**What prompt `A` already fixed** (`reports/A-no-decision-fixes.md` §3, items 1–3) — do not re-fix:

- the stage-1 pane painted a **uniform black image** on any real span, because every output cell
  caught a NaN and the range was reported as `[0, 1]`. It now paints real values with a separate NaN
  mask in grey: on a 4 h span of `M2_aug_concat_fs1.mat` CH1_A1, `values 0.099 … 238.476`, and
  `14,016 of 16,128 cells have no data`;
- `wavelet_transform` now declares `max_span_samples` from the Gramian memory budget — **it caps
  local runs at 65,000 samples**, so a 170 h span says in words that it needs HPC rather than
  failing;
- the two detection blocks disagreed on the end-index convention; they now agree
  (`SpanSet` is half-open `[start, end)`, the paper's algorithms are inclusive, converted at the
  seam).

**The number that should bother you: 87 % of the cells on a real 4 h span have no data.** That is the
histogram-chunk slicing (Sect. 3.1) declining to analyse most chunks of a 1 Hz fungal recording. It
is *honestly marked* rather than painted — prompt `A`'s achievement — but it is also, plausibly, the
answer to "why does this not read as detecting anything". **Find out whether that is the paper's
behaviour on this kind of signal or a parameter mismatch.** It is the single most promising thread.

Note also that `detection.dehshibi_spikes` exposes only `n_p`, `min_spike_duration`,
`min_roi_wavelet` and `epsilon_factor`, leaving the Morse constants (`beta`, `gamma`, `eta`) at
paper-fixed defaults deliberately. If the grilling round concludes the wavelet basis is wrong for
1 Hz data, those stop being "physics internals nobody adjusts" and the decision to hide them has to
be revisited — **say so, do not just expose them.**

## What the researcher wants to be able to tell

Three questions, in order, and the deliverable is that a reader can answer them from the page:

1. **Is it running?** — which stages ran, on what, how long, what came out.
2. **What did it decide, and why?** — the Ω(τ) curve against the signal, the candidate regions, which
   became spikes and which became pseudo-spikes, and at which algorithm each was dropped. The
   paper's Algorithms 1–4 are a *funnel*; the page should show the funnel.
3. **Is it right?** — against the researcher's own judgement on a span they know, and against the
   other detectors in the app on the same span.

**The boundary with prompt `H`:** `H` owns the visual language for how *every* block shows its work.
If what you need is a Dehshibi-specific process view, build the honest minimum here — the funnel and
its counts — and leave the idiom to `H`. If you find yourself designing a reusable figure component,
stop: that is `H`'s, and two idioms is the failure mode.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **A redesign of how blocks present results**, reusable process-view components, span slideshows | Prompt `H`, U7–U9 |
| **Dataset names, the `datasets` table, Settings** | Prompt `F`, running in parallel |
| **Any other detector** (`detect5`, `drop_motifs`, `detection.threshold`, rupture, spike_v1) — except to *compare against* on the same span | Comparison is evidence; changing them is not this prompt |
| **Running anything on the real `DATA/`**, or the held-out `M4_aug_concat_fs1.mat` (refused on every route) | `CLAUDE.md`. Work on the sandbox |
| **Adding a dependency** (a wavelet library, a different CWT) | Stop and report it. `CLAUDE.md`, Environment |
| **The eighth interchange type** | `Working/types/__init__.py:5-6` forbids it. Four blocks over three existing types is the shape |

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client` — **into your own dist**;
2. `webui/smoke.py` against a `--sandbox` bridge on **port 8766** serving your dist, restarted
   immediately beforehand, **and not while `F` is running `pytest`**;
3. `pytest -n 4` against the **1799 passed / 7 skipped / 0 failed** baseline (`E` §9, `G` §9),
   comparing failure **sets**, which are empty. `tests/test_block_standard.py` enforces the
   `BLOCK_INTEGRATION.md` contract on every block you touch. Under `webui/.venv`,
   `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails pre-existing;
   five smoke states are standing failures and not yours (four Settings registration states and
   `discovery.runs--default`).

**Evidence.** The template run end to end on a span the researcher knows, before and after, into
`webui/screenshots/fixup/J/`; the template-versus-monolith comparison as a table of spans; and **a
clause-by-clause table of the paper against the code** — section or equation, what it says, what the
block does, agree or not. That table is the artefact this prompt exists to produce, and it outlives
any fix in it.

## Report

`docs/prompts/fixup/reports/J-dehshibi-vs-the-paper.md`: the grilling round and its answers; the
paper-versus-code table; whether the two implementations agree; what the 87 % uncovered cells turned
out to be; what you changed and what you deliberately did not; whether the Morse constants should be
exposed; when `F`'s files were red; when you took the machine for smoke; defaults taken; items left;
out-of-scope files touched; the gate; a chat summary.

Then close `QUESTIONS.md` U6 and the Dehshibi rows in `02-analyse-chain.md`.

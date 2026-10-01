# Report — Fixup J: the Dehshibi detector against the paper

Run 2026-10-01 on `main`, in the main checkout, beside prompt `F`. Commit prefix `fixup-j:`.
`550314b` (red, tests only) → `d2ff3f8` (green: core, blocks, server) → `0484abc` (the funnel view,
smoke state, evidence) → the docs commit this file is in.

Paper: Dehshibi & Adamatzky, *Electrical activity of fungi: Spikes detection and complexity
analysis*, BioSystems 203 (2021) 104373. Sect. 4.2 (complexity) was left out on the researcher's
instruction. The authors' code: Zenodo `10.5281/zenodo.3997031`, fetched with the researcher's
permission, kept outside the repo.

## 1. The answer

**The detector in the app was not the paper's, and it is now.** Of the four causes the prompt
names it was the first — the implementation diverged — in four places that each changed the output
(§3). The printed paper and the authors' own code also disagree with each other (§4), and the code
is what was implemented (Q33): it produced the paper's figures, and it was run here, unmodified, in
MATLAB R2025b as the reference the port is tested against.

**Is it right for these recordings? No, and that is now a measurement rather than a suspicion** (§6).
On a synthetic recording with 20 known events it finds 17 and marks nothing else. On M2_aug CH0 it
puts a span in 91 % of the windows the researcher labelled *interesting* and in 86 % of the windows
labelled *not interesting*, and its spans cover 53 % of the time. It is faithful and it is not
selective: on a real fungal trace nearly every stretch has an extremum of Ω at 5 % prominence and
a wiggle that leaves the range of its ends. That is the second of the prompt's four causes, and it
is a property of the method, visible only once the first was removed.

## 2. The grilling round and its answers

`QUESTIONS.md` Round 6. Q28 fix it to the paper — **yes**. Q29 slicing — **off by default, fixed
3000 s windows; state slicing kept as an option**. Q30 nested spikes — **merged spans** (the
authors' code already does this). Q31 fetch the authors' code — **yes**. Q32 — **seconds, old
names still accepted**. Q33 printed algorithms or authors' code — **the authors' code**. The block
layout was confirmed before building: three blocks, same types, the third takes any per-sample
score.

## 3. What was wrong before (measured in the grilling round)

In memory, read-only, on `M2_aug_concat_fs1` CH0 (`scripts/fixup_j_measure.py`,
`scripts/fixup_j_trial.py`; `webui/screenshots/fixup/J/grilling-*`).

1. **The template and the monolith agreed** — identical on five real 4 h spans. They shared the
   faulty code.
2. **The 87 % was the slicing, not short chunks.** `slice_signal` kept only the time the signal
   spends below the midpoint of the span's own histogram: 87.3 % of the 0–4 h span was in no chunk
   at all, 0.0 % in a too-short one; 99.8 % of 0–18 h. The authors partition — nothing is discarded.
3. **The transform kept only the real part** (`phi.imag` exactly 0, from `irfft`): 376 raw local
   maxima of Ω in a 3000 s window against 27 for the modulus.
4. **No boundary handling**: the wrap-around jump was the largest event in every window, so the
   scalogram was a bowl, Ω a bathtub, and the first candidate region started at sample 5 or 6 in
   four of six windows.
5. **Algorithm 3 returned regions that ended before they started** — every region, in 5 of the 10
   four-hour runs — from reading step 5's "value" literally.
6. **The spans were a staircase**: `(6, 85) (6, 205) (6, 325) …`, the printed Algorithm 4 fed by the
   artefacts above.

## 4. The paper, the authors' code, and the blocks — clause by clause

`=` the block does what that column says. Core: `Working/Detection/analysis/dehshibi_authors.py`.

| Clause | Printed paper | Authors' MATLAB | The blocks now | Before fixup-J |
|---|---|---|---|---|
| Rate, units | 1 sample/s; lengths in seconds | `Fs = 1`; lengths as sample counts | **seconds**, converted with `fs`; old sample-count names accepted | sample counts; wrong at 10 Hz |
| 3.1 state levels | histogram halves, their **mean** | `pulsesep` → `statelevels`, histogram **mode** | = code | mean |
| 3.1 transitions | cross the low state's upper and the high state's lower boundary | `pulsesep`: IEEE 181 bands, 2 % tolerance | = code | any sign change about the midpoint: 39–55 chunks, median length 2–3 samples |
| 3.1 chunks | "enclosed between" a fall and the next rise | the separations' start points are **cut points**: a partition (`iSplitSignal`) | = code, as the `slice_by_state` option; default is fixed 3000 s windows (Q29) | fall→rise intervals only; the rest discarded |
| 3.1 scope | the whole recording | the whole recording | the span the chain was given | the span |
| Eq. (1) wavelet | Morse, γ = 3, βγ = 60 | `cwt` default | = | = |
| Eq. (2) transform | analytic, complex | `cwt(chunk, Fs)`: modulus, reflection padding, L1, 10 voices/octave, its own scale grid | = code; frequencies to 1e-13, modulus to 5e-8 of MATLAB's | real part only; no padding; 64 scales |
| Eq. (3) | `η(κ − min)/max`, zeros → 1 | `1 + fix(240·(κ − min)/max(κ − min))`; a flat frequency → 1 | = code; values 1…241 | `η(κ − min)/(max − min)`, zeros → 1 |
| Ω | "the sum of the scales below the threshold"; Fig. 6's axis | `method = 2`: frequencies ≤ a quarter of the frequency range (66 of 87 rows at 3000 s) | = code; the band is `row_to = 0.7586` on the summation block, set by the template | every scale |
| Alg. 1 extrema | "local maximum within ±ε", ε = 5 % of the range | `findpeaks`: prominence ≥ ε, distance ≥ 60, half-prominence width ≥ 30 | = code (own `findpeaks`, MATLAB's order of filters) | prominence only |
| Alg. 1 pairing | sort, pad an odd count, pair (1,2), (3,4)… | same; then each start moved back by up to 30 samples | = code | = paper |
| Alg. 2 length | `ub − lb > 30` | `≥ 60` | = code | = paper |
| Alg. 2 extrema | spline interpolation | `islocalmin` / `islocalmax` | = code | splines |
| Alg. 2 test | below both ends or above both ends → C, else D | same | = | = |
| 3.3 curvature | `L = ∂²f/4∂t²` | `del2` | = code (ends extrapolated) | ends replicated |
| 3.3 envelope | analytic signal, `ξ = |z|`, Eqs. (4)–(6) | `envelope(del2(x), 60, 'peak')`: splines through the peaks and troughs of **L itself**; no analytic signal | = code | splines through the peaks of `|z|` |
| Alg. 3 extrema | at least `n_p` apart | `islocalmin` / `islocalmax` of the mean envelope, no distance | = code | distance `n_p` |
| Alg. 3 pairing | minimum i with maximum j, by value, in lockstep | first maximum dropped; minima and maxima sorted together, paired consecutively | = code; no region can end before it starts | = paper, literally; inverted regions |
| Alg. 3 threshold | ρ = mean − std | mean − std if std < mean, else the mean | = code | = paper |
| Alg. 4 inputs | C ∪ D | **C only** | = code | C ∪ D |
| Alg. 4 rule | three subset cases → F_s, F_p | each C region widened to the hull of the envelope regions it meets; overlaps merged; no intersection anywhere → the C regions as they are | = code | = paper; nested spans |
| Alg. 4 length | drop < 60 | none | = code | = paper |
| Pseudo-spikes | F_p | D computed, never used | D in `meta["pseudo_spikes"]` and in the funnel | F_p in meta, never drawn |
| 4.1 | 76 % true-positive, 16 % false-positive on one 36,000 s piece | — | §6 | — |

Three things the port does that neither source says, each forced by the block shape:
**one frequency grid per span** (the grid `cwt` builds for the nominal window; a tail window up to
half as long again reuses it), **a tail shorter than half a window joins the window before it**,
and **the band is a row fraction** (an `Encoding` has no frequency axis).

## 5. What was built

**Core — `dehshibi_authors.py` (new).** The port, every function naming the `.m` file it follows.
`tests/test_dehshibi_authors.py` (42 tests) holds it to `tests/fixtures/dehshibi/reference.json`:
what the authors' unmodified functions returned in MATLAB on three synthetic recordings. It
reproduces Ω to the count and every region set and spike exactly.

**The blocks — same three types.**

| Block | In → out | Parameters | Notes |
|---|---|---|---|
| `preprocessing.wavelet_transform` | Signal → Encoding (image, rows low→high, one column per sample) | `window_s` 3000, `slice_by_state` off, `beta`, `gamma`, `eta` | every sample analysed; built one frequency at a time, float32, so the span cap rises from 65,000 to **320,000 samples** (624 B/sample against the 200 MB budget); a window needing more than 128 rows is refused in words |
| `detection.wavelet_summation` | Encoding → Scores | `row_from` 0, `row_to` 1 | sums a band of rows; the template passes the authors' band |
| `detection.summation_threshold` | Scores (+ the signal) → SpanSet | `epsilon_factor` 0.05, `min_separation_s` 60, `window_s` 3000, `slice_by_state` off | takes **any** per-sample score and windows it itself; disjoint half-open spans; the whole funnel in `meta["funnel"]` |

`detection.dehshibi_spikes` (deprecated) now calls the same core. `min_chunk_samples`, `n_p`,
`min_spike_duration` and `min_roi_wavelet` are still accepted so an old recipe validates; only
`n_p` still does anything.

**Can another block replace the summation?** Yes: `test_any_per_sample_score_can_stand_in_for_omega`
runs the third block on a crude rolling-range score. The two contracts are written into
`docs/BLOCK_INTEGRATION.md` §6. The existing STFT block cannot replace the *transform* as it stands
(one column per hop, not per sample).

**Server.** `serialize.py` ships the funnel in absolute seconds. The `dehshibi_spikes` template is
version 2; `seed_canonical` now brings an outdated **builtin** row up to the code's version and
never touches a saved copy — without it every existing database would keep summing all rows.
**The real database's builtin row will be upgraded on the next `--project` start.**

**Client.** `analyse/DetectorFunnel.tsx`: one strip per stage on the span's time axis, counts, and
the share of the span the spikes cover. The honest minimum; the idiom is `H`'s.

## 6. Is it right? — against events whose number is known

`scripts/fixup_j_figure.py` → `webui/screenshots/fixup/J/known-events-*.png`, `known-events.json`.
An event counts as found when one span covers at least half of it and is no longer than three
times its length.

| | events | found | spans | on no event | span analysed |
|---|---|---|---|---|---|
| Synthetic, 12,000 s, 20 injected events — **before** | 20 | **0** | 0 | 0 | 46 % |
| the same — **after** | 20 | **17** | 19 | 0 | 100 % |
| The three MATLAB reference recordings — after | 6 / 4 / 8 | 5 / 3 / 8 | 5 / 4 / 8 | | |

The researcher's 10-minute labels on M2_aug CH0 (683 windows), each run in the 3000 s grid window
it falls in:

| | *interesting* windows with a span | *not interesting* windows with a span | spans | time inside a span |
|---|---|---|---|---|
| before | 18 of 143 (13 %) | 64 of 540 (12 %) | 504 | 15 % |
| **after** | **130 of 143 (91 %)** | **466 of 540 (86 %)** | 2,846 | **53 %** |

The synthetic says the port works as a detector of the paper's kind of event on a quiet baseline.
The labels say that on this recording it cannot tell an interesting ten minutes from an
uninteresting one: with half the time inside a span, a window is hit almost whatever it holds.
`known-events-real.png` shows why — 38 candidate regions in four windows and all 38 pass the
excursion test, because a real trace always leaves the range of its ends.

## 7. The Morse constants

Still no case for treating them as the problem. They are exposed on the transform block (they
always were); the basis was never what was wrong. What governs selectivity is `epsilon_factor`,
`min_separation_s` and `window_s`, and the excursion test, which has no parameter at all.

## 8. Changed deliberately, and not changed

- Tests replaced because they encoded the old behaviour (named in `550314b`): the 64-scale
  real-part transform, `min_chunk_samples`, sample-count parameters, nested inclusive spans, the
  3072 B/sample cap.
- **Not changed:** `dehshibi_detection_analysis.py`'s functions — `wavelet_analysis.py` and
  `Experimentation/Detection experiments/run_dehshibi.py` import them. It carries a notice at its
  head. `detection.freq_stft`. Any other detector. The `Encoding` type.
- **Not done:** a tuning pass to make the detector selective here — that is a research decision
  (§10). A cost-model calibration for the new transform (`estimate` answers `None` until
  `Working.block_cost.calibrate()` is run on this machine, as before).

## 9. Out-of-scope files touched

`Working/Detection/analysis/dehshibi_authors.py` (new core module, so the old reading stays
importable); `webui/server/templates.py` and `tests/test_webui_templates.py` (the builtin-row
upgrade); `docs/BLOCK_INTEGRATION.md`; `scripts/fixup_j_*.py`; `tests/fixtures/dehshibi/`.
`webui/client/src/api.ts` and `webui/smoke.py` were **not** touched. No request to `F` was needed;
no schema change.

## 10. Left for a decision

1. **Whether to keep this detector in the comparison set at all**, and if so with which parameters.
   It is now a faithful baseline; §6 says it is a weak one here.
2. **The block page draws the funnel under a plot whose x-axis it does not share** (the strips start
   to the right of their labels). Aligning them is `H`'s process-view work.
3. The transform reuses one frequency grid for a tail window; state slicing transforms a long chunk
   on the nominal window's grid, where MATLAB would add lower frequencies. Both are said in §4.

## 11. The gate, the machine, and `F`

1. **Type-check and build** — `npx tsc -b` clean; `npx vite build --outDir <scratch>/dist-j` (the
   private build; the shared `webui/client/dist` was never built). `F`'s in-flight client files were
   in the tree for both and type-checked clean at the time.
2. **`pytest -n 4`** — **1874 passed / 8 skipped / 0 failed** (conda python), against the
   1799 / 7 / 0 baseline; the failure set is empty. The count includes `F`'s in-flight tests.
3. **`webui/smoke.py`** against a `--sandbox` bridge on **port 8766** serving the private build
   (banner checked: `CLIENT = …/dist-j`), restarted immediately beforehand: **573 screenshots, 7
   failures.** Five are the standing ones (`discovery.runs--default` and the four Settings
   registration states). One is `F`'s in-flight state
   (`settings.datasets--naming-a-dataset-saves-and-renames-the-row`). **One was mine:**
   `discovery.seed--source-explore` failed because my new smoke state takes the example span and the
   walk keeps `sessionStorage` between states, so Discovery no longer saw "no span from Explore".
   Fixed by moving that state into its own file, `webui/smoke_pages/zz_analyse_run.json`, which
   sorts last; `analyse.json` is back to exactly what it was. Re-walked: `--only zz` 0 failures;
   `--only discovery` passes `source-explore` again.
   **That re-walk was not a full run**, and it hit two `[Errno 22]` errors writing screenshots into
   the shared `webui/screenshots/pages/discovery/` — another process had those files open, most
   likely `F`'s smoke. The pages themselves rendered. A full smoke on a quiet machine is still owed.

**The machine was taken for smoke** from 17:51 to 18:10 on 2026-10-01 (full run to 18:07, the two re-walks after), after my `pytest` had
finished at 17:49. I could not see whether `F` was running `pytest` during it; two other sandbox
runtimes were created at 17:50 and 17:56, and the `[Errno 22]`s above say
`F` was at least writing screenshots during my re-walk.

**Defaults taken without asking:** the event-found criterion in §6; a tail shorter than half a
window joins the previous window; `min_separation_s` also serves as the shortest region kept (the
authors use one number for both); the 128-row ceiling on the transform.

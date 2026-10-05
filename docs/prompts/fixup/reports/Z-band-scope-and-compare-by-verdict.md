# Report — Fixup Z: a band is a scope, and Compare says what a human made of the remainder

Run 2026-10-03 on `main`, in the main checkout, **beside `AB`** (wave 2). Commit prefix `fixup-z:`. The first commit,
`5578ea6`, touches only `tests/` and failed 19 core tests under conda and 7 route tests under `webui/.venv` (no
`band_recipes` / `band_step` / `normalize_band` / `bands_from_settings`, no `detection_ids` filter, no
`union_span_sets` / `verdict_split`, no band routes). Every bridge ran in `--sandbox` on a private port (**8771**) and a
private client build (`run_server.py --dist <scratchpad>/dist`, banner *"CLIENT = … (a private build, not the shared
client/dist)"*). Nothing wrote to the real `DATA/db/annotations.sqlite`. Shared files (`api.ts`, `smoke.py`) were
appended and committed on their own, path-scoped, with only my hunks.

**In plain words, first.** RQ4 asks whether splitting a recording into slow, middle and fast layers (like separating
the bass from the treble in a song), and then searching each layer for letter patterns, finds events that the plain
recording hides — and whether a human, looking at those extra finds, agrees they are real. Before today that took a
template built and saved by hand for every layer and a Compare of two runs at a time, and the extra finds could not be
counted by verdict. Now it is: pick the layers once on *Apply template*; compare the plain run against **all layers
together**; send exactly the extra finds to Review; read back *"of the n regions only a band found, a human accepted
k"*, with the chance level beside it.

---

## 1. What was built

| # | The prompt asked | Now |
|---|---|---|
| 1 | A band scope on *Apply template* | **Bands** beside *Channels in scope*: `none` (today's behaviour) or the Settings list, one checkbox per band; a band reaching the recording's Nyquist is offered disabled with the reason. Each band is **one Discovery run across the channels in scope**, the template's steps with that band's step prepended, built by the core's own materialisation (`run_groups.band_recipes` → `materialize_target`). The run's label and row carry the band (`symbol_search · 0.01–0.1 Hz`, `params.band`); the template stays one template (`template_name`). The band runs of one application share a `bandSet`. Cost is N bands × the sweep — the footer and the estimate multiply, *Preview* measures the first band's chain, `/plan` with `bands` totals it, and over the ceiling every band run is added and none started (*Create SLURM script*) |
| 2 | Each band run paired with its surrogate, bandpassed the same way | `run_paired_recipe` prepends `preprocessing.surrogate` **ahead of** the band step, so the null is phase-randomised then filtered exactly as the real signal (pinned at core and route level). The per-band rows print the count drawn (`… / 3 draws`); after `T` that count is whatever `T` makes it |
| 3 | A side of Compare can be a set of runs | `set:<bandSet>` is a side: the **union** of the band runs, de-duplicated by the page's matching rule (`compare.union_span_sets`); the region is drawn as the first band's span and names every band that fired it. A band-set row in the runs list picks it as A or B. The per-band counts sit under the union (found · also A · not A · alone · null expects). The stepper names the band that fired; *Compare every stage* opens that band's own chain |
| 4 | Set overlap by verdict; *Send only-B unjudged to Review* | Under *only A · both · only B*: **judged · accepted · rejected · other · unjudged**, live from `adjudications` (`compare.verdict_split`; a region is judged when any detection it is made of carries a verdict). ***Send only-B unjudged to Review*** → `POST /api/discovery/compare/review` → a `review_queues` row filtered by `detection_ids` (new, additive on `queries.queue_candidates`, beside `L`'s `run_ids`), one detection per region, opened the way `L` opens one; a second send returns the same queue |
| 5 | Say what cannot be attributed; recommend like for like | *What differs* stays on the union view (cells drawn from the first band's chain, and it says so). A `likeForLike` note names the unbanded run of the same template and switches A to it in one click; on that comparison it reads *"like for like: … only the band differs"* |
| Q43 | A named band list in Settings › Analysis defaults, used as the band scope and every bandpass block's presets, recorded in each run's recipe | **Bands** card (rename, edit edges, add, remove; key `bands`); `GET /api/discovery/bands`; Analyse's bandpass block offers the list as presets. The band is recorded in each band run's recipe **as its bandpass step** — the label lives on the Discovery run row, because putting it in the recipe would hash the band run apart from the hand-built chain (§2) |
| Q-W3 | Keep the band entry typed so `AC` can add a wavelet kind | A band is `{kind, label, low_hz, high_hz}`; no kind = `bandpass`; an unknown kind is refused **by name** (`"band kind 'wavelet' is not one this core can build; known kinds: bandpass"`). `AC` adds `"wavelet"` to `recipes.BAND_KINDS` and one builder to `run_groups._BAND_STEPS`; nothing else reshapes |

## 2. The recipe a band run records, beside the hand-built one — they hash the same

The hand route of 2026-10-02 was: in Analyse, *+ insert* `preprocessing.bandpass` ahead of `symbol_search` (the block
arrives with the adapter's defaults filled — `POST /api/chain/params` with `{}` → `{low_hz 0.01, high_hz 0.1, order 4}`),
set its edges, save as a template, apply it in Discovery. The core's old band materialisation wrote only
`{low_hz, high_hz}` — **no `order`** — so a band run would have hashed apart from that chain. `run_groups.band_step`
now fills the bandpass through the adapter's own `validate_params`, the same call Analyse makes.

Measured on the sandbox (`webui/screenshots/fixup/Z/band-run-vs-hand-built-twin.json`), scope M2_aug 452–456 h ×
CH2_A1 · CH6_B1 · CH7_B2:

| | run key | runs it is made of | recipe hash (stored config of its first run) |
|---|---|---|---|
| band scope, 0.01–0.1 Hz | `symbol_search_0.01_0.1Hz` | 82 · 88 · 94 | `1e2f356728a1c81bf4c284b29bd0f33fa86b723ef10ff68ba98b789f1ed1c42e` |
| hand-built twin (inserted as Analyse inserts it, saved, applied) | `band_symbol_search_0p01_0p1_twin` | **82 · 88 · 94** | `1e2f356728a1c81bf4c284b29bd0f33fa86b723ef10ff68ba98b789f1ed1c42e` |

`execute_recipe` is idempotent on the recipe, so the twin did not run at all — it **is** the band run's runs. The
recipe both record:

```
steps: preprocessing.bandpass {high_hz 0.1, low_hz 0.01, order 4}
       preprocessing.detrend  {mode rolling_mean, window_s 600.0}
       detection.sax_dsax     (symbol_search's own params)
       detection.symbol_search {pattern c+a+ …}
surrogate: true   (the paired-run control every Discovery run records)
```

Pinned three ways: `test_band_scope.py::test_a_band_recipe_hashes_the_same_as_the_hand_built_chain` (core, dict and
hash), `::test_a_band_runs_stored_recipe_is_the_hand_built_one` (executed, stored), and
`test_webui_discovery.py::test_a_band_run_is_the_run_the_hand_built_twin_would_make` (through the routes: the twin is
made of the band run's runs).

## 3. The union and per-band counts on the sandbox scope

`symbol_search` × the three seeded bands, M2_aug 452–456 h × 3 channels, A = `drop_detection_v1` (raw signal):

| band | found | also in A | not in A | alone in the union | null expects / draws |
|---|---|---|---|---|---|
| 0.001–0.01 Hz | 1 | 0 | 1 | 1 | 8 / 3 |
| 0.01–0.1 Hz | 75 | 0 | 75 | 74 | 249 / 3 |
| 0.1–0.45 Hz | 17 | 0 | 17 | 16 | 40 / 3 |
| **union** | **92 regions** (93 detections; one region found by two bands) | | | | **297** |

Set overlap, union vs A: **only A 3 · both 0 · only B 92** (CH2_A1 3 / 0 / 3 · CH6_B1 0 / 0 / 77 · CH7_B2 0 / 0 / 12).
*What differs*: 3 of 5 roles (Preprocess, Encode, Detect) — not attributable; the page recommends `symbol_search`
with no band, and on that comparison it reads 1 of 5 (Preprocess) — attributable. For reference the readiness pass's
hand-built 0.01–0.1 Hz run read *74 found* and *only A 3 · both 0 · only B 74*; the band run here finds 75 (the same
recipe on the same scope — the difference is the run, not the band: see §6).

**The null still out-finds the signal**: the bands' surrogates expect 297 on this scope against 93 band detections.
One surrogate per band per channel is `T`'s to fix; the number on the page is the number drawn.

## 4. The verdict split after judging a handful

*Send only-B unjudged to Review* → toast *"92 unjudged of 92 regions in 'Compare · only B · A drop_detection_v1 vs B
symbol_search · 3 bands' · verdicts write adjudications"* → *Open Review* → `#/review/queue/3/1206`, *rank 1 of 92*.
Five verdicts by keyboard — **mine, entered to exercise the split, in the sandbox copy; they are not the researcher's
judgement and mean nothing about the data**: I · N · I · U · N → `adjudications` 1–5 on detections 1206, 1207, 1208
(run 82, 0.01–0.1 Hz) and 1302, 1303 (run 86), none on a surrogate; `annotations` untouched (11,269 before and after).

Back in Compare (`compare-drop-vs-bandset-after-5-verdicts.txt`):

| | regions | judged | accepted | rejected | other | unjudged |
|---|---|---|---|---|---|---|
| only A | 3 | 0 | 0 | 0 | 0 | 3 |
| both | 0 | 0 | 0 | 0 | 0 | 0 |
| **only B** | **92** | **5** | **2** | **2** | **1** | **87** |

and the sentence under it: *"Of the 92 regions only a band found, a human has judged 5 and accepted 2. The bands' nulls
expect 297 on this scope (9 draws)."* That sentence, on a real scope with the researcher's verdicts and `T`'s null, is
the answer to Q4.

*other* is there so the four always add up: `artifact` and `unsure` are verdicts but neither accepted
(`interesting`, `seed`) nor rejected (`not_interesting`) under the review queues' own sets.

## 5. Q43 — answered, with one deviation

Built as decided (2026-10-03): the named list in Settings › Analysis defaults, used as the band scope and as every
bandpass block's presets, editable, recorded in each band run's recipe. **One deviation, explained plainly:** a
recording sampled once a second can only hold rhythms up to half a cycle per second (0.5 Hz — its *Nyquist* limit), and
the filter cannot put an edge exactly on that limit (scipy's Butterworth refuses `Wn = 1`). So the seeded third band is
**0.1–0.45 Hz**, not 0.1–0.5 Hz; the decision's "~" allows it, and it is editable. A band reaching a recording's
Nyquist is refused when it is applied, naming the band, before any run is written.

## 6. Found on the way

- **Compare said "0 of 5 roles differ" for a template against its banded twin.** A role cell draws the *last* stage in
  that role, and the bandpass sits in Preprocess ahead of the baseline removal, so both columns drew *Baseline
  removal · rolling_mean · 10 min* and `_same_cell` called them equal — for the plain hand-built twin too, not only the
  set. A role holding a different number of stages now differs, and the chip says *"+1 stage before"*
  (`test_a_role_holding_one_more_stage_differs`, red at `587e62b`). The readiness pass recorded *"one role differs"* for
  this pair; the current code read none.
- **Compare's counts and the advertised matching rule could disagree.** The payload has always carried
  `rule_from_settings`, but the pairing ran on the module default. Compare now pairs, totals and de-duplicates the union
  under the Settings rule — identical while Settings holds the defaults.
- **The symbolic chain is not deterministic: one recipe, different spans.** This is the finding that matters most for
  RQ4, explained plainly first: the encoder that turns the signal into letters (`detection.sax_dsax`) decides where
  "up", "flat" and "down" begin by a small clustering step that starts from a random guess, and nothing fixes that
  guess. It is like drawing the boundaries of a map with a different ruler each time — mostly the same map, but not
  always. So the same recipe, with the same hash, can find a different number of regions on a different run. Measured:
  the 0.01–0.1 Hz band of `symbol_search` on M2_aug CH1_A1, 80–84 h, executed four times with `force=True` in a throwaway
  database, one process, nothing else running in it: **11 · 11 · 13 · 11** spans (CH2_A1: 2 · 2 · 2 · 2). Across the
  two smoke walks the same band on the same scope found 15 then 13, and its null 32 then 31; the readiness pass's 74
  against today's 75 is the same thing. The cause is documented in the encoder itself (`dsax.py`, "Determinism":
  `threshold_mode="learned"` consumes the global `np.random` via `kmeanspp`; seed it if you need reproducibility) and
  the adapter defaults to `learned` and never seeds. The step cache then freezes whichever draw came first. **Not
  fixed here** — it is the detector, not the band scope — and flagged as its own task (*"Seed sax_dsax's learned
  thresholds"*). That task has since run on its own branch (`fixup-dsax-seed`, `bf06ca4`, and `fixup-csax-seed`, `4f5fee7`),
  **not merged to `main` when this report was written**; both also edit `RQ4-bands-and-symbols.md`, so their merge
  meets this prompt's edit to that file. Until it lands, a band-vs-raw count on this chain carries a few regions of run-to-run noise, and the
  hash equality in §2 means "same experiment", not "same answer".
- **The SLURM modal writes the script of the first pending run only** (pre-existing, for any multi-run add). The modal
  now passes the band, so that script is the banded chain, but an over-ceiling application of N bands gets one script,
  not N. Left: the `/slurm` writer is `AB`'s this wave.

## 7. Items left

| Item | Owner |
|---|---|
| True surrogate count (one per band per channel today) | `T` |
| `detection.sax_dsax` learned thresholds are unseeded: one recipe, different spans (§6) | its own task, chip raised |
| Wavelet kind of band (`{kind: "wavelet", level}`) — the seam is `recipes.BAND_KINDS` + `run_groups._BAND_STEPS` | `AC` |
| One SLURM script per pending run in the modal | next owner of `chrome.tsx::SlurmModal` / `/slurm` |
| A set's precision and × null as one number | deliberately not built: pooling the band runs' precision would double-count a region two bands found; the union is read by verdict instead, and each band's precision stays on the Runs page |

## 8. Files touched outside the prompt's named list

| File | Why |
|---|---|
| `Working/database/queries.py`, `Working/review/queue_state.py`, `Working/review/queues.py` | `detection_ids` must be accepted by `ReviewQueue` and compared as a set by `find_open_queue`, as `L` did for `run_ids` |
| `Working/discovery/compare.py` | `union_span_sets`, `verdict_split` — the numbers stay in the core, as `discovery.py`'s docstring requires |
| `webui/client/src/discovery/chrome.tsx`, `discovery.css`, `api/discovery.ts` | the band-set row and its pick; the SLURM modal passes the band; the adapter carries the new fields |
| `webui/client/src/settings/AnalysisDefaultsPage.tsx`, `settings.css`, `fixtures/settings.ts` | the Bands card and its default (= the core's `DEFAULT_BANDS`) |
| `webui/client/src/analyse/ParamsPanel.tsx` | Q43's "every bandpass block's presets" |
| `webui/smoke_pages/band_scope.json` (new), `webui/smoke.py` | the walk and three page states |
| `tests/test_run_groups.py` | one assertion: a band target is now typed (`kind: "bandpass"`), stated in `5578ea6` |
| `docs/rq_roundA/RQ4-bands-and-symbols.md` | the RQ rule |

## 9. The gate

| Step | Result |
|---|---|
| `npx tsc -b`, `npm run build` in `webui/client` | **clean** on HEAD after `AB` had committed its Models work (the shared `dist` was built only for this); every walk served a private build from `npx vite build --outDir <scratchpad>/dist` |
| `pytest -n 4` under conda | **2045 passed, 20 skipped, 0 failed** (13 m 48 s) — failure set empty, as the baseline re-measured before my first edit (**1990 passed, 19 skipped, 0 failed**, 5 m 58 s, with `AB` in flight). The first attempt lost an xdist worker at 91 % (*"node down: Not properly terminated"*, no test failed before it; `pytest-n4-run1-worker-died.txt`); the rerun is the gate |
| `webui/.venv` — `test_webui_discovery.py`, `test_webui_review.py`, `test_webui_routes.py` | **93 passed, 1 failed** — the one is the standing `test_the_scoreboard_cells_are_the_tables_own_numbers`. Eight band-scope route tests added, all green |
| `webui/smoke.py`, full, on a fresh `--sandbox` bridge, **alone on the machine** (started 17:22, `AB` holding its load on request) | **597 screenshots, 32 failures, 0 browser console errors.** The Z walk (§3–§4 on the smoke scope) and all three `band_scope` page states **passed**. The 32 are not Z's — see below |

**The smoke on this machine today, and why its failures are not Z's.** The machine was loaded by the researcher's own
applications (Ableton Live among them; ~55–70 % CPU with one walk running), and every walk timed out somewhere
different. So I measured the same smoke on the **pre-Z code** (`2c2667b`, a detached worktree with its own build and
bridge on port 8773, no DATA junction, removed afterwards) under the same conditions:

| walk | code | screenshots | failures | Z walk + Z states |
|---|---|---|---|---|
| run 1 (15:42) | Z | 609 | 53 | all passed — **contended**: `AB`'s `pytest -n 4` and forest training overlapped it (`requests/AB-to-Z-smoke-overlap.md`) |
| runs 2, 3 | Z | — | — | stopped: `AB`'s walk on 8772 overlapped them |
| **gate** (17:22) | Z | 597 | **32** | **all passed** |
| re-walk, pages only, warm bridge | Z | 569 | 23 | all passed |
| **baseline** (18:15) | **pre-Z** | 573 | **117** | — |

Every state that failed in the gate and not in the baseline passed in at least one other walk of the Z code, except
two, both explained: *queue-picker popover lists the live queues* waits 1.5 s for the picker, which loads every queue
with its rows — the baseline passed it only because its own Review walk had timed out and left two queues, where the Z
walk leaves six (my remainder queue costs 0.07 s to load; `L`'s 400-row seed queue 0.77 s cold); and *Slope ·
marks on a trough family* drew its steepest mark 8 px from the payload's on the warm re-walk — nothing that serves or
draws Interrogation changed between `2c2667b` and HEAD, in either prompt. The standing five (`discovery.runs--default`
and the four Settings registration states) failed as usual. Logs and results: `webui/screenshots/fixup/Z/smoke-logs/`,
`smoke-result-*.json`; flow screenshots `discovery-9…14`, `settings-bands.png`; page states `states/`.

**I took the machine** for the gate walk (from 17:22), the pages-only re-walk, the baseline walk (from 18:15) and
both `pytest -n 4` runs (~14 min each); `AB` held its load for those on request and then ended its session.

## 10. In short

A band is now a scope: *Apply template* takes a list of bands from Settings and makes one run per band, each across
the channels in scope, each recording exactly the recipe of the chain a researcher would build by hand (same hash,
same runs) and each paired with its own bandpassed null. Compare takes the band runs as one side — their union — and
splits the overlap by what a human said, and *Send only-B unjudged to Review* sends exactly the remainder. On the
sandbox scope the bands found 92 regions the raw detector did not, and their nulls expected 297: Q4 is answerable in
the app now, and not yet answered in favour of the bands.

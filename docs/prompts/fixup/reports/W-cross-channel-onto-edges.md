# Report — Fixup W: cross-channel classification reaches an edge

Run 2026-10-04 on `main`, in the main checkout, **beside `AC`** (wave 5). Commit prefix `fixup-w:`.

The first commit, `3aebd08`, touches only `tests/`. On arrival `tests/test_cross_channel_simultaneous.py` failed all 27
tests (no rule in seconds, no `classify_family_across_channels`, no `family_recurrence`), `tests/test_cross_channel.py`
failed at import (the renamed constants), and 8 of the 9 route tests in `tests/test_webui_cross_channel.py` failed —
among them Explore binning an inverted simultaneous copy (r −0.999 at lag 0) as *propagation*.

Every bridge ran `--sandbox` on **port 8777**, serving a **private client build** (`--dist <scratchpad>/dist-w`). Nothing
wrote to the real `DATA/db/annotations.sqlite` (it was opened read-only once, for a count).

## In plain words first

The same event can show up on several electrodes. Seen **at the same instant** on two of them it is contamination —
one wire picking up another, like one bird's song heard on two microphones — not two events. Seen **a little later** on
the next electrode it is the event travelling through the mushroom. Otherwise the shape is recurring on its own. The
question for RQ6 is: once the first two are taken out, how much recurrence is left?

Until today the Library's classifier could not answer that, because it compared the wrong things. It cut each event's
own snippet out of the recording — wherever in time it sat — and slid one snippet over the other. Two events an **hour**
apart came back as "lag 0, artifact". Now each event is compared with its neighbouring electrodes **over the same
seconds**, the bins follow the rule you decided (Q40, Q-W5), the result is written onto the pair's edge, and the
Recurrence matrix can count with the artifacts taken out and a travelling event counted once.

**One thing needs your decision (Q40d, §6)**: whether an event seen at the same instant on an electrode where the family
has *no* member also counts as contamination. It changes the answer from "about half the members are artifacts" to
"almost all of them are".

---

## 1. Part 1 — the two paths on a synthetic pair (measured 2026-10-03, now pinned by tests)

Reused from `QUESTIONS.md` "Q40, measured" (`webui/screenshots/fixup/W/part1_synthetic.py`); a 60-sample biphasic pulse,
fs 1:

| case | Explore (same absolute window) | Library before `W` (each member's own snippet) | Library after `W` |
|---|---|---|---|
| +5 offset, no noise | lag +5, r 1.00, propagation | lag 0, r 1.00, **artifact** | lag **+5 s**, propagation (`test_an_injected_five_sample_offset_is_recovered_and_binned_propagation`) |
| +5 offset, noise sd 0.02 | lag +5, r 0.95, propagation | lag 0, r 0.989, propagation | as above |
| +1 h, no noise | lag +299 / +3600 (window-dependent) | lag 0, r 1.00, **artifact** | **not simultaneous** — no lag measured; an existing edge is `independent_recurrence` with lag and r NULL (`test_members_an_hour_apart_are_never_lag`) |

**The first finding stands: the Library path could not recover the injected offset** — its lag was only where the two
snippets were cut. It is gone: `classify_cross_channel_edges` is now the entry-scoped form of the new function.

The synthetic lagged-pair test the PRD insists on now passes for every bin: artifact at lag 0 (and inverted at lag 0),
propagation at +5 and at +10 s, independent under the r floor and past the ceiling, the fs conversion at 10 Hz (8
samples = 0.8 s → artifact, 15 samples = 1.5 s → propagation), and the one-hour case.

## 2. Part 2 — lag against r on real windows

Reused (`part2_real_windows.py`, `part2_pairs.csv`, `part2_lag_vs_r.png` in `webui/screenshots/fixup/W/`): 300
`interesting` windows on M2_aug, each against its 15 siblings, **4,500 pairs**.

| \|r\| at \|lag\| ≤ 1 (1,517 pairs) | r > 0 | r < 0 | old bin | new bin |
|---|---|---|---|---|
| < 0.5 | 55 | 33 | all propagation | independent (under the floor) |
| 0.5–0.7 | 183 | 174 | all propagation | artifact |
| 0.7–0.9 | 367 | 340 | all propagation | artifact |
| 0.9–0.99 | 202 | 146 | all propagation | artifact |
| ≥ 0.99 | 12 | 5 | 12 artifact, 5 propagation | artifact (either sign) |

**The same 4,500 pairs re-binned under the decided rule** (arithmetic on the stored lag and r; fs 1, stride 1):

| | artifact | propagation | independent |
|---|---|---|---|
| old rule (samples, signed r ≥ 0.99, no floor) | 12 | 2,219 | 2,269 |
| **decided rule** (1 s, \|r\| ≥ 0.5, 50 s) | **1,429** | **586** | **2,485** |

1,417 pairs moved propagation → artifact (the simultaneous ones), 216 propagation → independent (under the floor). No
conclusion about biology; counts only.

## 3. Q40, as answered — and how it was built

- **Q40a — the same absolute window, always.** `matching.classify_family_across_channels` compares each member with every
  other channel of its recording over the same samples. A sibling **member** within the propagation ceiling of it →
  the pair is classified on the **union of the two spans**, cut from both channels, so both events are wholly inside
  the window; the bin, lag (samples; seconds via fs) and signed r go onto **every** edge joining the two (a seed match
  carries three, one per distance — each row's lag sign turned to its own a→b), and when none joins them one
  `cross_correlation` edge is written (distance 1 − |r|, threshold 1 − the floor). An existing cross-channel edge
  between members further apart than the ceiling is `independent_recurrence` with no lag: they are not simultaneous.
- **Q40b + Q-W5 — three bins in seconds with an r floor.** `Working/cross_channel.py`: `CrossChannelRule` (artifact 1 s,
  |r| ≥ 0.5, propagation 50 s — named constants), `bin_for` the one place a (lag, r) becomes a bin, `describe()` each
  bin's rule in words from the values in use. The three numbers are **Settings › Analysis defaults** keys
  (`cross_channel.artifact_max_lag_s`, `.min_abs_r`, `.propagation_max_lag_s`), refused if they do not make a rule.
  Every edge records the rule it was computed under (`motif_edge.classification_json`, with the window and fs); the
  Family page badges *computed under a different rule* when Settings has moved since.
- **Fix while there:** Explore's lag was in strided samples against sample thresholds. The route now hands the core
  `fs / stride`, and cuts a decimal window tolerant of float error (322.6 s × 10 Hz was sample 3225.9999…).
- **Q40c — counted, never an edge.** No member on the sibling → `motif_member_cooccurrence` (one row per member ×
  sibling channel, latest classification, machine-only). Artifact and propagation rows are counted on the family as
  *co-occurrence without a member*; nothing is written to `motif_edge` or `motif_member`.

**Recurrence with the bins taken out — one definition**, `matching.family_recurrence`, read by the Family card and by
every Recurrence cell; `recurrence_count` delegates to it:

- *every member* — nothing taken out;
- *excluding artifacts* — a member in an artifact pair is not counted, **neither copy** (Q40b: simultaneous events are
  contamination, so neither is a recurrence); the cell stays red and visible (§8.4);
- *propagation counted once* — artifacts out as above, then members joined by propagation count once, on the member
  with the earliest onset.

**`recurrence_count` changed meaning** (said in commit `3aebd08`): it counted non-artifact *edges*; it now counts
members under a mode. No caller outside tests used it.

## 4. Counts per bin on three real families

Sandbox `webui/runtime/20261004-184434`, default rule, grouping g-05. The three families with the most members on
sibling channels within 50 s of each other (measured read-only on the real database: 1,315 such pairs across 119 of
149 families). All three sit mostly on `Fig2A_dt0p1.csv` (5 channels, 10 Hz) with a few members on M2_aug (16 channels,
1 Hz). About a second per family.

| family | members | channels | pairs: artifact · propagation · independent | negative r | without a member: artifact · propagation | recurrence: all · excl. artifacts · propagation once |
|---|---|---|---|---|---|---|
| F-130 | 55 | 8 | 17 · 24 · 19 | 21 of 60 | 228 · 22 | 55 · **33** · **29** |
| F-119 | 40 | 6 | 25 · 18 · 13 | 24 of 56 | 109 · 6 | 40 · **17** · **14** |
| F-39 | 40 | 7 | 13 · 23 · 19 | 17 of 55 | 70 · 8 | 40 · **22** · **18** |

Some pairs as stored (F-130): m-1295/m-2921 +1.0 s r 0.61 artifact; m-1295/m-3323 +11.1 s r 0.71 propagation;
m-1342/m-2348 +0.1 s r 0.85 artifact; m-1443/m-2486 −41.6 s r 0.52 propagation; m-1342/m-3391 +23.1 s r 0.40 independent
(under the floor).

**Surrogate counts beside them: none exist for these families, and the page says so.** Their members were imported
(the reishi/oyster stores), not found by a run, so no paired null was drawn; the card prints *"no run produced these
members … no count here can be read against chance"*. For a family built from a run, the card prints the producing
runs' detections and their nulls per draw (the true draw count, after `T`) side by side, and tests nothing.

## 5. Acceptance — the walk (sandbox bridge, port 8777, private build)

1. **Library › Family F-130 → *Classify across channels*** → a `cross_channel` job; progress per channel
   (*"Fig2A_dt0p1.csv · CH3 · 16 members against 4 sibling channels"*, 8 channels; channel names one-based, as fixup-F), a toast with the counts at the end.
2. **The family rail's cross-channel line** reads *artifact 17 · propagation 24 · independent 19*; the card prints each
   bin's count with its rule behind an info icon, the Q40c counts, the three recurrence counts with their rules, and the
   null line. **m-1295's edge list** shows *+1.0 s · r 0.61 · artifact* to m-2921 and *+11 s · r 0.71 · propagation* to
   m-3323, each with *Explore ›*.
3. **Library › Recurrence**, *excluding artifacts*, count, recordings 4–6: F-130's Fig2A cells are red with `!`, still
   visible — CH1 reads *! 0* (all 5 of its members are in artifact pairs), CH3 *! 7* of 16; the row's total reads 33
   (55 under *every member*, 29 under *propagation counted once*); the rule sits beside the toggle.
4. **Explore › Cross-channel** from m-1295 → m-3323's *Explore ›*: the edge's window, unpadded (*"edge window at 0.09 h ·
   unpadded"*), CH5 against CH1 reads **+11.1 s · 0.71 · propagation** — what the edge stores. *Classify every F-130
   member in Library* is live there (it was `notWired`); opened without a family it is disabled and says why.

Screenshots: `webui/screenshots/fixup/W/` (`smoke-*.png`, the eight states of `webui/smoke_pages/zzz_w_cross_channel.json`).

## 6. Q40d — the one open decision

*In plain words.* `W` takes a sighting out when **both** microphones have it on the family's list. Often the second
microphone hears the song and nobody put that recording on the list. Is the first sighting still "heard twice"?

| family | members | in an artifact pair (as built) | with an artifact co-occurrence without a member | artifact if either counts |
|---|---|---|---|---|
| F-130 | 55 | 22 | 46 | **54** |
| F-119 | 40 | 23 | 40 | **40** |
| F-39 | 40 | 18 | 28 | **39** |

- **(a) No — as built**, the literal reading of Q40c: counted beside the family, nothing else changes.
- **(b) Yes** — Q40b applied to the event: any simultaneous correlate on any sibling makes the member an artifact.
  These three families all but vanish.
- **(c) Both, as a toggle** on Recurrence, each with its rule.

**Recommendation: (c).** The gap between the two numbers is the finding an examiner will ask about; neither reading
should be hidden. It is small to build — the per-member rows are already stored. Whether 0.5 is a floor that separates
contamination from shared slow drift on a 5-channel 10 Hz recording is the question underneath, and Part 2's 1,429 of
4,500 simultaneous pairs on M2_aug says it is not a 10 Hz peculiarity. Recorded in `QUESTIONS.md` as Q40d and in RQ6.

## 7. Left

- **Q40d** (above).
- **A family with a null.** No family in the Library today was built from a run with paired surrogates, so no
  recurrence count has a null beside it yet. RQ6's runbook step 1 makes one.
- **The window is the members' spans, unpadded.** Full-mode correlation normalised by the window length caps r at
  (n − |lag|)/n, so a lag near the window length is under-read; the union of two spans holds both events whole, but a
  co-occurrence without a member is measured on the member's own span. Stated, not padded: padding adds context that
  correlates on its own (drift), which is exactly what the artifact bin is sensitive to.
- **Co-occurrences without a member are counted per member × sibling channel**, so one sibling event seen by three
  members counts three times. The card says so.
- **The rule a stored bin was computed under is recorded; re-binning after a Settings change needs *Classify* again.**
  The page says when the stored rule differs.
- **Jobs workspace**: the client's `JobKind` union does not name `cross_channel` (a type alias cannot be merged); the
  row still lists, kind printed raw.

## 8. Files

**Declared:** `Working/cross_channel.py`, `Working/library/matching.py`, `webui/server/explore_routes.py`,
`webui/client/src/explore/CrossChannelPage.tsx`, Library › Recurrence (`RecurrencePage.tsx`), and the new
`library/CrossChannel.tsx`.

**Shared, my hunks only, committed at once:** `webui/client/src/api.ts` (appended, `8cb9596`), Settings
(`settings/AnalysisDefaultsPage.tsx`, `fixtures/settings.ts`: the three keys). `webui/smoke.py` was not edited; my
states are `webui/smoke_pages/zzz_w_cross_channel.json`.

**Out of the declared list — the reviewer should justify each:**

| file | why |
|---|---|
| `Working/database/schema.py` | `motif_edge.classification_json` (nullable) and `motif_member_cooccurrence` — Q40c needs a place that is not an edge; additive, through `init_db()` |
| `webui/server/library.py` | the job route, the Family card's payload, the per-cell counts, the edge's lag/r/window — the Library's bridge (V's file; my hunks are separate functions) |
| `webui/server/jobs.py` | `cross_channel` added to `KINDS` (one tuple entry) |
| `webui/client/src/library/FamilyPage.tsx`, `library/Edges.tsx` | the Family page *is* the acceptance walk's first two steps |
| `webui/client/src/api/explore.ts` | the Explore adapter: an explicit window and the rule's words |
| `tests/test_cross_channel.py`, `tests/test_webui_jobs.py`, `tests/test_webui_library.py` | changed deliberately (renamed constants and same-window semantics; a sixth job kind; two new cell counts) — each said in its commit |
| `docs/prompts/fixup/QUESTIONS.md`, `docs/prompts/rq_roundA/RQ6-…`, `README.md` | Q40d, RQ6's state, the README row |

## 9. The gate

| check | result |
|---|---|
| `npx tsc -b` + `npm run build` (`webui/client`) | **pass**, the whole tree type-checked including `AC`'s in-flight files at the time |
| `webui/smoke.py`, full walk, fresh `--sandbox` bridge on 8777 (private build), **machine taken for smoke alone** (I waited for `AC`'s `pytest -n 4` to finish first) | **627 screenshots, 7 failures — none mine.** The five standing (`datasets--import-check-fails-fs-unknown`, `datasets--import-check-passes-MJu26a`, `models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`, `discovery.runs--default`) and the two `review.inspector--padding ±30 s / ±120 s is symmetric` states, whose screenshot path overruns Windows' path limit under the long scratchpad `SMOKE_SHOTS` directory (`[Errno 2]`; `V` saw the same two). **0 browser console/page errors, 0 unexpected server tracebacks.** All 8 `zzz_w_cross_channel` states pass |
| `pytest -n 4` (conda) | **2210 passed, 22 skipped, 2 failed** in 7 m 32 s. The two failures are **`AC`'s, not mine**: `test_end_to_end.py::test_discover_adapters_registers_the_expected_count` and `test_adapter_spec.py::test_every_shipped_adapter_registers_without_modification` pin 37 shipped adapters and `AC` added the 38th (`preprocessing_wavelet_bands`, `5ea0140`). Against the baseline after `X` (2134 / 21 / 0) nothing that passed before fails because of this change. Three tests were changed on purpose (§8) |
| route tests under `webui/.venv` | `test_webui_cross_channel.py` 9 passed; `test_webui_library_edges.py`, `test_webui_library.py`, `test_webui_routes.py`, `test_webui_jobs.py` pass |

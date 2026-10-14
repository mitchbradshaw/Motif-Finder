# Wave 2 — evaluation against each template's null on real recordings

Run by the manager, 2026-10-14, in a **sandbox copy** of the database (`webui/server/runtime.py`, mode `sandbox`,
runtime root in the session scratchpad — nothing written to the real `DATA/`). Scripts: `eval/` in the session
scratchpad (`w2common.py`, `eval_event_clusters.py`, `eval_minirocket.py`, `eval_snippets.py`, `eval_library.py`,
`eval_families.py`); raw results `w2_*.json` beside them (not committed).

**The bar (researcher, Q4):** a chain ships as a template only if it beats its random-data null on real recordings.
Operationalised as in wave 1: the statistic on the real recording exceeds every one of 20 null draws (empirical
p = 1/21 ≈ 0.048), on at least 2 of 3 recordings. The statistic and the null differ by template (`W2-manager.md`).

## In plain words

Wave 2 built six things. Each template was run on real recordings against a version of the same data with the
pattern destroyed: shuffled labels, or noise with the same "colour" (the same mix of slow and fast wiggles). A
template ships only if it beats that every time, on at least two of three recordings. Think of a dog that must find
the hidden treat more often than it finds the empty cups.

| What was built | In one line | Template verdict |
|---|---|---|
| **Event windows** (`catalogue.event_windows`) | A frame cut around each detected event, so later blocks can compare events like photos cropped to their subject | its template `event_clusters` is **experimental**; the block itself ships, since every window chain uses it |
| **Library methods** (k-Shape, HDBSCAN, coherence) | Two new ways to sort the Library's shapes into families, and for each family two checks: could noise of the same colour make a crowd this tight, and how far are its members copies of one shape? | no template; in the Library now |
| **MiniRocket** (`catalogue.minirocket`) | A shape fingerprint of every window (thousands of tiny pattern detectors), fed to the classifier that learns your interesting / not verdicts | `minirocket_manual_labels` **ships**: it learns the verdicts on all three channels tried, also when tested on a later stretch of time, at least as well as the Catch22 arm |
| **Snippets** (`catalogue.snippets`) | The few most typical hours of a recording and which hour looks like which, like the thumbnail frames that sum up a film | `recording_snippets` is **experimental**: on most spans its "regimes" were no more lasting than on noise. On one 72 h chain they were real, but its automatic chooser said "one kind only" |
| **Families** (`catalogue.shape_families`, `interrogation.event_families`) | Sort detected events into families by shape, then time each family's rhythm on its own | `event_families` is **experimental**: it beat its null on 1 of the 5 spans that held events; on 24 h spans it found no families |
| **The UI** | All of the above drawn in Analyse and the Library, each verdict shown as the block gave it | — |

So one new template ships, and three are kept as experimental, the way FLUSS and Trains were in wave 1. Each
experimental block's description starts "EXPERIMENTAL: …" with the reason. The three experimental ones fail for
different reasons, set out below. Two of those reasons have a concrete next step: a better noise test for smooth
shapes, and a different way to choose how many snippets there are.

## `event_clusters` — Event windows → hierarchical clustering of the events' measures

**Statistic:** the silhouette of `catalogue.cluster`'s three clusters (Ward) on the Event-shape measures each window
carries — how well separated the groups are (1 = perfectly, 0 = not at all). The cluster block now reports it
(W2-A's fix round). **Null:** the brief's first choice was the same chain on 20 phase-randomised surrogates, but at
4 σ the noise threshold finds **no events at all** in any surrogate, so the brief's fallback was used — the **shape
null**: the same real events, each event's window of the trace replaced by a phase-randomised copy of itself (same
spectrum, no shared shape; the copy keeps its end-to-end line so it joins its neighbours), then Event shape → Event
windows → Cluster re-run on that trace with the real spans. 20 draws.

| Recording | Events | Silhouette (real) | Shape null (20 draws) | p | Beats? |
|---|---|---|---|---|---|
| rec 385 · Mushroom_260720 CH14 · 4 h | 0 | — (no events at 4 σ; the cluster step refuses in words) | — | — | — |
| rec 1 · M2_aug CH0 · 440–464 h | 44 | 0.41 | 0.34–0.59 (mean 0.44) | 0.71 | no |
| rec 3 · M2_aug CH2 · 440–464 h | 55 | 0.37 | 0.35–0.73 (mean 0.56) | 0.95 | no |
| rec 3 · known chain 500–530 h (information) | 68 | 0.48 | 0.30–0.55 (mean 0.45) | 0.33 | no |
| rec 6 · known chain 380–460 h (information) | 89 | 0.36 | 0.32–0.60 (mean 0.45) | 0.90 | no |

**Verdict: not shipped — `EXPERIMENTAL`.** Three Ward clusters of these events' measures are no better separated than
three clusters of noise-shaped events. The block itself (`catalogue.event_windows`) ships: it is the bridge every
window block now uses, and its own claims (geometry, offsets, omissions) were verified by its critic.

**Warnings read:** on rec 1 the event-windows block warned that 16 of 44 windows end before their event has recovered
(the automatic length was 70 s; the noise-threshold spans are short), naming `length_s` as the knob — the warning
W2-A's fix round added did its job. The cluster step reported its feature columns (amplitude, width, duration,
recovery, slopes, peakedness, span peak-to-peak) and none of the bookkeeping columns.

## `minirocket_manual_labels` — a shape fingerprint per window → the researcher's verdicts → classifier

**Statistic:** the classifier's holdout accuracy on M2_aug's interesting / not-interesting verdicts (whole channel,
10-minute windows on the labels' 600/200 grid). **Null:** label permutation — 20 forests trained with the labels
shuffled within the training split, scored on the true holdout. Reported beside it, for the researcher: balanced
accuracy and the majority baseline, the same on a **blocked-by-time** holdout (5 blocks, the last fifth held out —
the classifier's own holdout is a random split, and neighbouring windows are correlated), and the existing Catch22
arm (`manual_labels_model`) on the same windows.

| Recording (labelled windows) | Accuracy (null max) | Balanced acc. (majority) | Blocked: balanced acc. (null max) | Beats? |
|---|---|---|---|---|
| rec 3 · CH2 (635: 313 interesting) | **0.868** (0.654) | 0.868 (0.509) | **0.856** (0.632) | yes, both |
| rec 16 · CH15 (669: 207 interesting) | **0.774** (0.696) | 0.677 (0.690) | **0.675** (0.529) | yes, both |
| rec 4 · CH3 (636: 203 interesting) | **0.836** (0.686) | 0.776 (0.679) | **0.847** (0.607) | yes, both |

**Verdict: ships** — it beats its null on all three recordings, on both holdouts; the random-split and blocked-split
numbers agree, so the score is not leaking time.

MiniRocket against the Catch22 arm on the same windows (balanced accuracy, random / blocked):

| Recording | MiniRocket | Catch22 (`manual_labels_model`) |
|---|---|---|
| rec 3 | 0.868 / 0.856 | 0.869 / 0.848 |
| rec 16 | 0.677 / 0.675 | 0.658 / 0.627 |
| rec 4 | 0.776 / 0.847 | 0.762 / 0.691 |

Both arms beat their nulls everywhere; MiniRocket is at least as good on every recording and clearly better on rec 4's
blocked holdout. On rec 16 both are only modestly above the majority baseline (the interesting class is recalled
0.42 / 0.38 of the time).

## `recording_snippets` — the few typical hours of a recording, and which hour resembles which

**Statistic:** how long regimes last — the mean run length of the hour labels, divided by what shuffled labels would
give — compared at a **fixed k = 3** (`runs_by_k["3"]`). The brief named "mean regime run length" at the automatic
k; W2-D and its critic showed why that cannot work: when the knee says k = 1 every hour has one label and the run is
the whole recording, which no surrogate can beat. **Null:** 20 phase-randomised surrogate draws of the span.

| Recording | Auto k (the knee) | Run ratio at k = 3, real | Surrogates (20 draws) | p | Beats? |
|---|---|---|---|---|---|
| rec 385 · 4 h | — refused in words: 4 one-hour pieces, the knee needs ≥ 12 | — | — | — | — |
| rec 1 · M2_aug CH0 · 440–464 h | 1 | 1.11 (mean run 2.0 h) | 0.75–1.46 (mean 1.01) | 0.19 | no |
| rec 3 · M2_aug CH2 · 440–464 h | 1 | 0.92 | 0.83–1.47 (mean 1.01) | 0.90 | no |
| rec 3 · known chain, 490–540 h | 1 | 0.90 | 0.90–1.28 (mean 1.07) | 0.95 | no |
| rec 6 · known chain, 380–452 h (72 h) | 1 | **3.01** (mean run 4.5 h) | 0.89–1.20 (mean 1.03) | 0.048 | **yes** |

**Verdict: not shipped — `EXPERIMENTAL`** (it beats its null on 1 of 4 spans it can run on). By eye, on rec 3's chain it labelled every hour the same: the 30 h drop chain was not told apart from its
quiet margins — the limit W2-D measured, z-normalised shapes cannot see a quiet stretch as a shape of its own.
**One span where something is there:** on rec 6's 72 h chain (the span sits wholly inside the chain), the k = 3
regimes last three times as long as shuffled labels would and beat all 20 surrogates — but the knee rejected them
(k = 1; every surrogate's knee also said k = 1), so the template as it stands would show the researcher one kind of
behaviour there too. Set k by hand on a span like that, and read the run lengths. The block's description says so.

## Library methods on the real Library (single motifs, shape distance)

Run on main after W2-B's merge (`2fd26b8`) and the coherence margin (`4db3684`), in a sandbox copy, on exactly the items
the Library's grouping editor hands the engine (`server.library._grouping_items`): **3,616 events** today (the stored
Ward grouping g-05, "shape families", was saved on 3,603). Coherence is eq. 17 (`svd_entropy_norm`, aligned) per
family, with the σ²-weighted variant and the count of families more coherent than their own trend-kept noise with the
0.9 margin (`beyond_noise`).

| Method | Families | Placed | Left out (reason) | Flagged noise-like | ARI vs stored Ward g-05 (common / all) | Coherence eq. 17: median [p10–p90] | σ² variant median | Beyond noise | Seconds |
|---|---|---|---|---|---|---|---|---|---|
| Ward, re-run (cut 0.6, min 10, omit 0.5) | 151 | 3,296 | 8.8 % (316 group too small, 4 past cut) | not tested | 0.57 / 0.41 | 0.574 [0.440–0.702] | 0.122 | 113 of 151 | 4 |
| HDBSCAN (defaults, eom) | 19 | 687 | 81.0 % not in a dense family | 3 of 19 (153 events) | 0.45 / 0.01 | 0.348 [0.290–0.414] | 0.037 | 19 of 19 | 36 |
| HDBSCAN (leaf) | 23 | 582 | 83.9 % not in a dense family | 2 of 23 (61) | 0.44 / 0.01 | 0.331 [0.197–0.414] | 0.031 | 23 of 23 | 25 |
| k-Shape, k = 20 (omit_d auto) | 20 | 1,996 | 44.8 % past cut | 8 of 20 (326) | 0.23 / 0.06 | 0.482 [0.430–0.563] | 0.105 | 20 of 20 | 712 |
| k-Shape, k auto → 4 | 4 | 1,065 | 70.5 % past cut | 3 of 4 (549) | 0.05 / 0.02 | 0.488 | 0.105 | 4 of 4 | 330 |

What it says, plainly:

- **HDBSCAN finds a small core of tight families and leaves most events out.** Its 19 families are much more
  alike inside (median coherence 0.35) than Ward's (0.57), and every one is more coherent than noise of its members'
  colour; but it places only a fifth of the Library. Where HDBSCAN and Ward both place an event they agree moderately
  (ARI 0.45): HDBSCAN's families are mostly the dense cores of Ward families.
- **Ward places nearly everything**, into 151 looser families; 38 of them are not more coherent than their own noise
  with the margin. It is the method that "forces every event into some family" (the plan's §5 row 8).
- **k-Shape** at k = 20 sits between (55 % placed, middling coherence, 8 families noise-like). Its automatic k chose
  4 on a weak silhouette (0.31; the curve is flat from k = 3 to 12) and three of the four are noise-like — an explicit
  k is the better use of it.
- **Today's Ward does not reproduce the stored g-05** (ARI 0.57 on the 3,119 events both place). The items are what
  the editor reads now — after the 2026-09-21 data loss the channels were re-derived — so either the waveforms or the
  item set changed since g-05 was saved. Worth a look before g-05 is cited as a result.

## `event_families` — Event shape → families (HDBSCAN) → intervals per family

**Statistic (brief):** the fraction of events HDBSCAN places in a family, **and** the families' median SVD entropy
(eq. 17, `svd_entropy_norm`). **Null (brief):** the shape null. The same real events are used, and each event's cut
window is replaced by a phase-randomised copy of itself (same spectrum, no shared shape). The copies are grouped by
the code path the block uses (`Working.Catalogue.shape_families.shape_families`), 20 draws. The real chain beats the
null when it places more events than every draw **and** its median entropy is lower than every draw's. A draw that
forms no family has no entropy, and counts as beaten on that half. Run from the W2-E branch's code after its fix
round, with the template as it now stands: anchor at the span start, **600 s** windows (W2-E fix round 1; the
critic's 432-run synthetic sweep found it the one length that kept two shapes apart in every case).

| Span (events) | Families (sizes) | Placed, real (null max) | Median SVD entropy, real (null min) | Beats? |
|---|---|---|---|---|
| rec 385 · Mushroom_260720 CH14 · 4 h (0) | — no events at 4 σ; the block says so | — | — | — |
| rec 1 · M2_aug CH0 · 440–464 h (44) | none | 0 (0) | — | no |
| rec 3 · M2_aug CH2 · 440–464 h (55) | none | 0 (0) | — | no |
| rec 3 · known chain, 490–540 h (116) | none | 0 (0.22, one draw) | — (0.85) | no |
| rec 6 · known chain, 370–470 h (115) | 2 (53, 13) | 0.57 (**0.63**; mean 0.36) | **0.33** (0.72) | no: the placement half fails |
| rec 542 · L_LM_Jul_26_J CH2 · known chain, 370–490 h at 10 Hz (163) | 2 (131, 11) | **0.87** (0) | **0.79** (no null family) | **yes** |

**Verdict: not shipped — `EXPERIMENTAL`** (decision 22). It beats its null on 1 of the 5 spans that held events.
The two block files ship. `catalogue.shape_families` is the Library's methods inside a chain; its own claims were
re-measured by its critic. `interrogation.event_families`' description starts "EXPERIMENTAL: …".

What the numbers say, plainly:

- **On 24 h M2_aug spans it finds no family at all.** The real events are not placed, and neither are their noise
  copies. Forty to fifty dips a day, each of its own shape, do not make a crowd HDBSCAN can see.
- **On rec 6's drop chain the families are real by every test the block makes, but the brief's statistic does not
  see it.**
  - Both families pass their per-family trend-kept noise test (ratios 0.21 and 0.34, where 1 is noise).
  - Both are far more coherent than noise of their members' colour (0.30 against a noise 5th percentile of 0.64;
    0.35 against 0.53).
  - But HDBSCAN also gathers phase-randomised copies of the same events into crowds, in 17 of 20 draws. One draw
    placed 63 %, more than the real 57 %.
  - The block flags those noise crowds itself: in 18 of the 20 draws not one copy sat in a family that passed its
    noise test (null max 0.12, against the real 0.57).
  - The brief counts every placed event, so rec 6 fails. Counting only events in families that pass their own test
    would pass it. **That reading was chosen after seeing the result, so it is reported here and not used for the
    verdict;** it is a question for the researcher.
- **On rec 542's chain it beats the null cleanly.** 87 % of the events fall into two families; no draw placed any.
  But the larger family (131 events) is not more coherent than noise by the 0.9 margin (0.82 against 0.9 × 0.90),
  and the block warns so. Its members share a broad, window-filling shape, the case the coherence caveat names.
- **The earlier settings did no better.** At the automatic window length (60–350 s here) and at 300 s, it beat its
  null only on rec 542 too. At 300 s both rec-6 families were flagged noise-like: the smooth-shape blind spot.

**Warnings read:** no auto-length warning (the length is set). The rec-542 coherence warning is above. Since the W2-E
re-critique, the overlap warning also fires at a set length; no evaluated span came near it (the events are 20 min to
hours apart).

## The gate

Run on `main` at `3d8bfbf`, after all six merges and the integration commits. The machine was loaded throughout:
the researcher's controller software held the CPU at about 85 %. Three peer sessions were present, all holding
their own gates; one ran small serial test files in its own worktree.

- **pytest** (`-n 4`, main checkout, conda python): **3353 passed, 38 skipped, 0 failed** (44 min). W1's last gate
  was 2904 passed, 0 failed. The failure set is empty, so nothing that passed then fails now; 449 tests were added
  since. The pre-gate on `800d0d9`, before W2-E and W2-F merged, was 3243 passed, 0 failed.
- **Per merge** (block tests + `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`,
  `test_templates`, serial):

  | Merge | Commit | Result |
  |---|---|---|
  | W2-A | `2efec8b` | 282 passed |
  | W2-C | `9a942a1` | 380 |
  | W2-D | `dd69db0` | 301 |
  | W2-B | `2fd26b8` | 519 + 3 xpassed (venv python, which runs the webui tests) |
  | W2-E | `b40b000` | 583 |
  | the families integration | `63cb033` | 319 |

- **Client:** `npx tsc -b` clean; `npm run build` clean (4.7 s).
- **The UI tests** (venv python, after the W2-F merge): `test_webui_family_views`, `test_webui_block_views`,
  `test_webui_library`, `test_webui_serialize`, `test_webui_w2f_ui` and `test_webui_run_routing`, plus the
  standard three: **345 passed, 3 xpassed**.
- **Smoke** (full walk, own sandbox bridge on port 8791; its database is a copy under
  `webui/runtime/20261014-173845/`): 663 screenshots, **0 browser console or page errors**, 25 failures.
  - **Every wave-2 state passes**: the two Library states (`w2-method-hdbscan-no-tree`, `w2-method-ward-unchanged`)
    and the ten Analyse states (event windows, MiniRocket, snippets, shape families, event families: thumbnails
    and block pages). Wave 1's three states pass too.
  - **The 25 failures, against the committed baseline** (`webui/screenshots/smoke-result.json`: 3 Discovery
    failures, all three still failing):

    | Failures | Pages | Known? |
    |---|---|---|
    | 12 | Discovery: runs default / modal-slurm / discarded, the seed save-template state, five compare states, the divergence compare state, and the flow checks "the run acts offer to send" (it offered 0) and "compare opens with what differs" | W1's gate recorded "Discovery runs/compare" and "the divergence compare state" |
    | 3 | Review inspector | W1: 3 |
    | 5 | Settings: click timeouts on a disabled button | W1: 5–6 |
    | 2 | explore corpus, a load flake; `explore.cross-channel--max-lag-10`, data drift | memory `webui-smoke-baseline-2026-10-13` |
    | 2 | `analyse.interrogation--fixup-d-sequence-rose`; `discovery.seed--fixup-y-picker-filters-by-kind` | **pass when re-run alone** (`--pages-only --only interrogation`: 58 states, 0 failures; `--only seed_sources`: 0 failures). The sequence route took 24.5 s under load against a 4 s settle |

    Of the 12 Discovery failures, three are the committed baseline's (runs default, runs modal-slurm, the seed
    save-template state). With the traceback check below, 12 + 3 + 5 + 2 + 2 + 1 = 25.
  - **"No unexpected server tracebacks" failed on one event.** `webui/server/jobs.py::_persist` hit
    `sqlite3.OperationalError: database is locked` during the Discovery flow (17:41). That is lock contention in the
    sandbox copy under load; wave 2 does not touch `jobs.py`. The other two error lines were the walk's own
    deliberate failures: the too-short span, and the manifest inbox refusing a missing folder.
  - **None of these pages runs code wave 2 changed.** Wave 2's webui changes are in `serialize.py`, `library.py`,
    `views.py`, `templates.py`, one line of `runs.py`, the Analyse views and the Library pages.

The bridge was started with `webui/.venv/Scripts/python.exe`, not the conda python the brief names: conda has no
FastAPI (`ModuleNotFoundError`). The venv is the bridge's own interpreter (`webui/run_server.py`'s docstring).

## What the researcher should decide

Each question below gives the plain picture first, then the options, then a recommendation.

1. **How to judge `event_families`.**
   - *Plain picture.* Think of sorting photos into albums. The test asks whether the real photos make more albums than
     scrambled photos do. On rec 6 the scrambled photos also made albums, so the template "failed". But the block
     labels each album with its own check, "could scrambled photos make one this tight?", and it marked almost every
     scrambled album as noise, while both real albums passed.
   - *Options:*
     - (a) Keep the brief's count, every placed event: the template stays experimental.
     - (b) Declare "events in families that pass their own noise test" as the statistic now, then re-test it on known
       chains not used here.
     - (c) Switch to (b) and judge on the spans already run: it would ship.
   - *Recommendation:* **(b)**. Choosing the statistic after seeing it pass is how a test fools itself; a fresh set of
     spans keeps it honest.
2. **Snippets' "how many kinds?" chooser.**
   - *Plain picture.* The block adds typical hours one at a time. It keeps a second (or third) only if that explains
     much more of the recording than noise would. To be safe on long spans, the bar rises with the square root of the
     number of hours. On rec 6's 72 h chain the bar threw away three regimes that each lasted three times longer than
     chance.
   - *Options:*
     - (a) Leave it, and set k by hand when looking for regimes, reading the run lengths. The description says so.
     - (b) Re-tune the chooser against the run-length test, a wave-3 item.
   - *Recommendation:* **(a) now, (b) in wave 3.**
3. **Today's Ward is not the stored g-05.**
   - *Plain picture.* Re-running the same sorting recipe on today's Library gives families that only half-match the
     saved ones (adjusted Rand 0.57).
   - *Likely cause:* after the 2026-09-21 data loss the channels were re-derived, and 3,616 events are read today
     against the 3,603 g-05 was saved on.
   - *Options:*
     - (a) Compare the waveforms of the common events first, then decide.
     - (b) Save a fresh Ward grouping from today's items, keeping g-05 for the record.
     - (c) Leave it.
   - *Recommendation:* **(a), then (b), before any RQ3 claim is read off g-05.**
4. **The coherence headline.**
   - *Plain picture.* Coherence says how far a family's members are copies of one shape (0 = copies). The paper's
     formula (eq. 17) is shown now. W2-B measured that it stops telling a pure family from a mixed one once a few per
     cent of members are noise, and is sometimes inverted. The squared variant (σ²) keeps telling them apart.
   - *Options:*
     - (a) Keep eq. 17 as the headline, with σ² beside it (as now).
     - (b) Make σ² the headline, with eq. 17 beside it for comparison with the paper.
   - *Recommendation:* **(b)** for judging a family. The beyond-noise verdict stays on eq. 17 until it is re-measured
     on σ².
5. **A fairer noise test for smooth shapes.**
   - *Plain picture.* The noise test builds fake members by scrambling each member while keeping its slow trend.
     For a broad hump or a ramp that fills its window, the trend is the shape, so the fakes look like the real thing
     and the family reads "noise-like". The block says so on its face.
   - *Options:*
     - (a) Build a null from the recording's own quiet stretches (windows with no event).
     - (b) Live with the caveat.
   - *Recommendation:* **(a)** as a wave-3 item, together with a trend-kept null for k-Shape. k-Shape's present noise
     test missed crowds of random-walk events, so the families block does not offer it.
6. **MiniRocket in the paired training job.**
   - *Plain picture.* The fingerprint works in Analyse, at least as well as Catch22 everywhere and clearly better on
     one channel's later-time test. RQ1's main comparison runs in Models › Launch, which does not offer it yet.
   - *Options:*
     - (a) Add it as a feature option there, keeping Catch22 the default until the exams compare them.
     - (b) Leave it to the Analyse chain.
   - *Recommendation:* **(a)**, as a small ticket.

Smaller follow-ups, no decision needed:
- Analyse shows "uncalibrated" for any estimate that raises; the bridge drops the estimate's own words
  (`webui/server/chain.py::route_local`).
- The jobs manager's "event loop closed" warning (`webui/server/runs.py::_emit`) appears after the test loop shuts.
- Every timing in this file was measured on a loaded machine (two peer sessions, and an hour asleep). Re-calibrate the
  cost models on a quiet one.
- The detrend session found that `drop_detection_v1` silently returns no events on a span holding a NaN. Its
  NaN-safe fix is under way in a separate session.

## Decided by the researcher (2026-10-14, evening)

The researcher took every recommendation above ("q1. rec, q2. rec, q3. … rec is fine, q4. rec, q5. rec, q6. rec"):

1. **`event_families`: (b).** The statistic below is declared *before* the re-test. It is run on the researcher's
   known chains that this evaluation has not used.
2. **Snippets' chooser: (a) now, (b) later.** For now, set k by hand; the block's description already says so. The
   re-tune itself is **not in wave 3**: when wave 3 was planned the same day, the researcher chose only follow-up 5
   for it (`docs/prompts/blocks/README.md`). So it waits for a later wave unless the researcher moves it in.
3. **g-05: (a), then (b).** First find why today's Ward differs from the stored g-05. Then save a fresh Ward grouping
   from today's items, keeping g-05 for the record. The researcher "doesn't have a huge attachment to g-05".
4. **Coherence headline: (b).** σ² leads wherever a family's coherence is shown; eq. 17 sits beside it. The
   beyond-noise verdict stays on eq. 17 until it is re-measured on σ².
5. **A fairer noise test: (a).** This is wave 3's `W3-G` (a quiet-stretch null, and a trend-kept null for k-Shape).
6. **MiniRocket in Models › Launch: (a), as a small ticket.** It is added as a feature choice, with Catch22 staying
   the default.

### `event_families` re-test — declared before the run

**Statistic.** The template as shipped (anchor at the span start, 600 s windows, HDBSCAN at its defaults) gives two
numbers on each span:
- the **fraction of event windows in families that pass their own noise test**, `fraction_confident` of the grouping;
- the **median SVD entropy (eq. 17) of those same families**.

**Null.** The same shape null as above: each event's cut window is replaced by a phase-randomised copy of itself, and
the copies are grouped by the same code. 20 draws, seeds 0–19.

**A span beats the null when all three hold:**
- the real fraction is above every draw's;
- at least one real family passes its noise test;
- the real median entropy is below every draw's. A draw with no passing family counts as beaten on this half.

**Spans.** Only two of the researcher's named chains have not been used here:
- L_LM_Jul_26_J **rec 543, 370–490 h** (10 Hz, 176 `noise_threshold` events);
- M2_aug **rec 2, 294–304 h** (13 events).

**Ship rule.** The template ships only if it beats on **both**. With two fresh spans, the brief's 2 of 3 cannot be
met, so 2 of 2 is the strict reading. The earlier spans are reported under the new statistic for information only:
they were seen before it was chosen.

### `event_families` re-test — the result (run after the declaration, `8324d3d`)

Run on main (`8324d3d`) in a sandbox copy, with the shipped template from `webui/server/templates.py`. Script:
`eval_families_retest.py` (session scratchpad).

| Span (events) | Families | In passing families, real (null max) | Median SVD entropy of passing families, real (null min) | Beats? |
|---|---|---|---|---|
| **rec 543** · L_LM_Jul_26_J · 370–490 h at 10 Hz (176) — fresh | none | 0 (0.11; 5 of 20 draws had a passing family) | — (0.71) | **no** |
| **rec 2** · M2_aug · 294–304 h (13) — fresh | none | 0 (0) | — | **no** |
| rec 6 · 370–470 h (115) — earlier, information only | 2 (53, 13) | 0.57 (0.12) | 0.33 (0.74) | yes |
| rec 542 · 370–490 h (163) — earlier, information only | 2 (131, 11) | 0.87 (0) | 0.79 (no passing null family) | yes |
| rec 3 · 490–540 h (116) — earlier, information only | none | 0 (0.11) | — (0.85) | no |

**Verdict: `event_families` stays EXPERIMENTAL.** It beats on 0 of the 2 fresh spans:
- **rec 543** is the sister channel of rec 542, the one span where the template did well. HDBSCAN places none of its
  176 events, while scrambled copies of the same events formed small families that passed their noise test in 5 of
  20 draws.
- **rec 2** has too few events (13) to make a family.

The new statistic does what it was chosen to do on the earlier spans, where the noise crowds stop counting. But on
fresh chains the template mostly finds nothing to count. What it finds is specific to a recording, not a property
of drop chains in general. The block's description stands.

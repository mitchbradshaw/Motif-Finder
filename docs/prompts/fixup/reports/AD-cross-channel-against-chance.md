# Report — Fixup AD: a cross-channel match must beat chance, and a human decides what is an artifact

Run 2026-10-04 → 05 on `main`, in the main checkout. Planned beside `AE`; **`AE` had already finished and merged when
this ran**, so it ran alone on the machine and built on `AE`'s view filter. Commit prefix `fixup-ad:`.

The first commit, `d8b7281`, touches only `tests/`. On arrival `tests/test_cross_channel_chance.py` failed at its first
test (no 0.98 constant), `tests/test_review_suspected_artifact.py` failed at import (no `artifact_queue`), and the
edited `W` / seed tests failed on the behaviour this ticket replaces. Every bridge ran `--sandbox` on **port 8779** with
a **private client build** (`--dist <scratchpad>/dist-ad`). Nothing wrote to the real `DATA/db/annotations.sqlite`; it
was opened read-only for counts.

## In plain words first

`W` called two electrodes "the same event" whenever their short clips looked alike at the same moment. The Q40d plots
showed the same rule passes just as often when the second electrode is cut at a **random other moment** — short clips
of slow drift look alike whatever you compare them with. It was like deciding two microphones heard the same bird
because both recordings were mostly wind.

Now:

1. **A match has to beat chance.** Each pair is compared with the same second electrode at 100 random other moments;
   the real match counts only if it is more alike than 95 of those 100.
2. **A suspected artifact must be a near-copy** (r ≥ 0.98, your number) **and both clips must be real events** —
   bigger than the dataset's noise floor.
3. **Clips under 30 samples are "too short to tell"**: counted, never judged. That is most of Fig2A.
4. **The machine only flags; you decide.** *Send suspected artifacts to Review* opens a queue whose card shows every
   electrode on one true-millivolt axis, like the Q40d gallery. Recurrence leaves a member out only when **you** have
   said it is an artifact.

**The fall the Q40d measurement predicted happened.** On M2_aug, the members flagged went from **673 of 1,012** under
`W`'s rule to **64**. F-130 went from 54 flagged of 55 to 10 — none of them on Fig2A. And the flags that remain are
real outliers: of 123 near-copies on M2_aug, 97 beat their own random null, where chance alone would pass about 6.

**One thing you asked about, decided during the run (2026-10-05):** a "no, not an artifact" answer is recorded with
the existing five words — *interesting* if it is a real event worth it, *not_interesting* if not — and every row carries
a note that the span was flagged as a suspected artifact. No sixth word.

---

## 1. What was built

**The rule** (`Working/cross_channel.py`; Settings › Analysis defaults, seven `cross_channel.*` keys, W's three plus four):

| bin | condition (all must hold) |
|---|---|
| suspected artifact | \|lag\| ≤ 1 s · \|r\| ≥ **0.98** · beats chance · both swings ≥ the noise floor |
| propagation | 1 s < \|lag\| ≤ 50 s · \|r\| ≥ 0.5 · beats chance · both swings ≥ the noise floor |
| independent | everything else |
| *too short to tell* | a member under **30** samples: not classified, counted, never binned, never padded |

- **The chance test** (`chance_null`, `beats_chance`, `chance_summary`): the statistic `classify_waveforms` computes
  (\|r\| at the cross-correlation peak), on the **same sibling** at **K = 100** random windows of the member's length,
  each ≥ 60 s from the member, inside the recording, never over a human `artifact` annotation on the sibling; drawn with
  `np.random.default_rng([member id, sibling recording id])`, so a re-run reproduces it. A match counts only if its \|r\|
  is **strictly above** the 95th percentile. The percentile it reached, the threshold, K and whether it beat it are
  stored in the edge's / co-occurrence row's `classification_json`. No room for one window → no null → does not beat
  chance, and says why.
- **The noise floor**: peak-to-peak of each channel over the classified window, in mV by `recordings.units`, against
  `view_filter.dataset_floors` (AE's one reader — imported, per AE's request in `requests/`). An undeclared unit cannot
  clear the floor.
- `classify_family_across_channels` applies all of it; **stale bins on a too-short member are cleared** (its
  co-occurrence rows deleted; the classifier's own edge deleted; a seed match's edge keeps its distance and loses only
  the classification).
- `cross_correlate` now uses `scipy.signal.correlate(method="auto")` — the same values, FFT when long: an M2_aug member
  runs to 7,178 samples and the chance test correlates 100 windows per pair.

**Recurrence** (`matching.family_recurrence`, same signature — AE's seam kept): *excluding artifacts* removes only
members **a human marked artifact**, plus the other member of a member–member artifact pair a human confirmed (Q40d-2)
unless a human said otherwise of that one. Beside it: *machine-flagged n · confirmed k · rejected j · unsure s ·
unjudged u*. *Propagation counted once* merges only pairs whose stored classification beat chance (a W-era bin, with no
chance test on it, merges nothing until re-classified).

**The queue** (`Working/review/artifact_queue.py`): a `suspected-artifact` source kind, unit `member`, made through
`create_queue` (a second send returns the same queue). Its items are resolved live: the family members the classifier
flags. Library › Family *Send N suspected artifacts to Review* queues the members **the page shows** (AE's view: floor,
fall duration, purity), so the button's number and the queue's are one number. Review's card
(`review/SuspectedArtifact.tsx`) draws every channel over the member's span ± one span, in true mV on one shared axis,
each minus its own median, the member bold, each flagging sibling's r, lag, amplitude ratio and chance percentile
printed. The verdict buttons are the five words; the queue offers *artifact / interesting / not_interesting / unsure*
and the core refuses *seed* here.

## 2. Before (W's rule) → after (AD's rule)

`webui/screenshots/fixup/AD/measure_ad.py` on a scratch copy of W's sandbox database (`webui/runtime/20261004-184434`),
grouping g-05, default rule; `measure_ad.json` holds every number. W's stored numbers reproduce exactly (F-130 17 · 24 ·
19, 228 · 22, 55 · 33 · 29), which pins the "before" column.

**W's three families:**

| | F-130 (55) | F-119 (40) | F-39 (40) |
|---|---|---|---|
| member pairs, before: artifact · propagation · independent | 17 · 24 · 19 | 25 · 18 · 13 | 13 · 23 · 19 |
| member pairs, after | 0 · 0 · 10 | 0 · 0 · 1 | 0 · 0 · 0 |
| without a member, before: artifact · propagation | 228 · 22 | 109 · 6 | 70 · 8 |
| without a member, after | 17 · 0 | 3 · 0 | 0 · 0 |
| **too short to tell** (after) | 26 (22 of 38 Fig2A, 4 of 17 M2_aug) | 32 (all Fig2A) | 34 (all Fig2A) |
| members flagged, before (any artifact row) → after | 54 → **10** (all M2_aug) | 40 → **2** (M2_aug) | 39 → **0** |
| recurrence before: all · excl. artifacts · propagation once | 55 · 33 · 29 | 40 · 17 · 14 | 40 · 22 · 18 |
| recurrence after, no human verdict yet | 55 · 55 · 55 | 40 · 40 · 40 | 40 · 40 · 40 |
| … if every flag were confirmed | 45 | 38 | 40 |

**The M2_aug members** (1,012 in 124 families of g-05; every one of those families classified, 5 min 19 s in all, the
slowest family 26 s):

| | W's rule | AD's rule |
|---|---|---|
| members flagged | **673** | **64** |
| too short to tell | — | 34 |
| co-occurrences without a member: artifact · propagation | 3,356 · 4,182 | 97 · 495 |
| member pairs | 0 (no M2_aug member has a sibling member within 50 s) | 0 |

"Before" for M2_aug is W's bin re-derived from the same (lag, r) on the same windows — W's bin is a pure function of
those two — so the 34 too-short members (no AD row) are missing from the before column.

**Did the predicted fall happen? Yes.** The Q40d control predicted that almost every W flag was coincidence; 673 → 64
on M2_aug and 133 → 12 across the three families.

**Are the 64 real?** Of 14,670 M2_aug member × sibling comparisons, **123 are near-copies** (\|r\| ≥ 0.98 within 1 s,
both over the floor); **97 of them beat** their own null, where a 95th-percentile test passes about 6 by chance. 55 of
the 64 flagged members beat **all 100** random windows. The thresholds themselves are high — median 0.976, IQR
0.897–0.987 — because 1 Hz M2_aug windows of slow drift correlate highly anywhere; that is exactly what the test is for.

**No propagation survives** on these families: every 1–50 s pair either failed its chance test or fell under 0.5.

**On the members AE's floor shows** (the default view), F-130 has 11 members, 2 too short, **4 flagged**.

## 3. The acceptance walk (sandbox, port 8779, private build)

1. **Library › Family F-130 → *Classify across channels*.** One `cross_channel` job: *done · 10 pairs classified
   across 8 channels · 26 too short to tell* — the measurement's numbers. The card reads *too short to tell 2* (of the
   11 shown), *machine-flagged 4 · confirmed 0 · rejected 0 · unjudged 4*, and every bin's chance rule; m-1295's edge to
   m-2921 (W: +1.0 s, r 0.61, artifact) reads +1.0 s · r 0.61 · chance 99th pct of 100 · **independent**.
2. ***Send 4 suspected artifacts to Review*** opened *Suspected artifact · F-130* (queue 3). m-621's card: 16 channels,
   one mV axis, the member bold, *CH3_A2: r +0.980 · lag +0.0 s · amp ×0.59 · chance 95th pct of 100 · no member there*
   — a borderline flag over a shared ramp, which is why a person looks.
3. Marked **m-621 artifact, m-808 artifact, m-828 not_interesting** (keys A, A, N). The family card: *every member
   11 · excluding artifacts **9** · propagation counted once 9 · machine-flagged 4 · confirmed 2 · rejected 1 ·
   unjudged 1*, and *Open in Review · 3 of 4 judged*. Recurrence's row for F-130 carries the same numbers. Three
   `annotations` rows (source `cross_channel_review`) over the members' spans, each noted *"flagged as a suspected
   artifact by cross-channel classification (F-130 · m-621): CH3_A2 lag +0.0 s r +0.980 amplitude ×0.59 95th
   percentile of 100 random times"*; 0 adjudications written; 3 `review_audit` rows.
4. **Discovery › Seed search**: *exclusion zone m/2 = 63 s* (m 126), the slider live; moved to 32 s the caption reads
   *below m/2 lets trivial matches through* and the apply bar *exclusion zone 32*; *Run seed search* made `seed_c34624`,
   whose row says *exclusion 0.254·m* and whose recipe's `detection.seed_matches` step carries `exclusion: 0.254`.

Smoke states: `webui/smoke_pages/zzzz_ad_suspected_artifact.json` (7); screenshots in `webui/screenshots/fixup/AD/`.

## 4. Where the human verdict lives, and why

**In `annotations`, over the member's span, for every member** — imported or from a run.

The prompt said to choose by what the member is: a member from a run has a detection, an imported one does not. An
imported member (all of F-130, F-119, F-39) has nowhere else to go. A member from a run *does* have a detection — but
by Q39 that detection already carries the **accepting** adjudication that made it a member (`interesting` or `seed`),
and `adjudications` holds one verdict per detection (`UNIQUE (detection_id)`). Writing *artifact* there would overwrite
the judgement the membership rests on, and a later *not artifact* could not restore it. An annotation over the same span
is a new human observation of that span, which is what this is. Nothing writes `motif_member`, `motif_edge` or
`motif_member_cooccurrence` (a test counts all four tables around a verdict).

A member's verdict is the latest live `cross_channel_review` annotation over exactly its span. Undo of a first verdict
withdraws the inserted row (`deleted_at`), like every human row.

**The vocabulary** (the researcher, 2026-10-05): five words, no `not_artifact`. A *no* is *interesting* or
*not_interesting* — whichever is true — so it also counts as that human verdict everywhere else (X's divergence reads
it), and the note says why the span was asked about.

## 5. The exclusion change

`detection.seed_matches` takes `exclusion`, a fraction of m in (0, 2], default **0.5** (§7.6), and passes it to
`stumpy.match`. `stumpy.match` takes no zone argument (it reads `config.STUMPY_EXCL_ZONE_DENOM`), so the block sets that
denominator to `1 / exclusion` for the call under a lock and restores it; a test pins that the global is put back. The
null draws use the same zone. `seed_steps` always names it, so **every seed recipe's hash changed**: the real database
holds **0** seed runs (Round 11), so nothing stored is orphaned — said in commit `d1e3b2d`. `recommended_params` reports
the zone that runs (m/2, `exclusionSettable: true`); the "the block and the spec differ" note is gone. The Seed page's
slider, the result key, the run identity and the run row carry it.

## 6. Left

- **Explore › Cross-channel bins without the chance test or the floor.** It classifies an arbitrary window across every
  channel live; drawing 100 nulls per channel per window is affordable on a member's span, not on a 200,000-sample
  window. It still uses the 0.98 artifact line (through `bin_for`), so its bins are an upper bound on the Library's.
  W's promise "Explore on an edge's window recomputes what the edge stores" now holds for lag and r, not always for the
  bin. Not mine to change (`explore_routes.py`); it should say so on the page.
- **K = 100 resolves the 95th percentile but not much finer**: 55 of the 64 flags beat all 100 windows, and "100th
  percentile" means p < 0.01, no better. Raising K is a Settings change; classification time grows with it.
- **A member is tested against every sibling** (15 on M2_aug), so per member the chance of one false flag is higher
  than 5 %. Measured, it does not dominate (97 of 123 near-copies beat chance vs ~6 expected), and a human sees every
  flag. Not opened as a question; a per-member correction is a Settings-free change if wanted later.
- **Settings › Analysis defaults still carries a decorative *exclusion zone* (m/4 · m/2 · m) control** that nothing
  reads. The Seed page's slider is the real one. Found, not changed.
- **The real database's `review_queues` will be rebuilt** the next time a non-sandbox bridge (or `init_db`) opens it,
  to widen its CHECK. It is backed up beside the database first (`…pre-review-queues-rebuild-<stamp>.bak`), done in one
  transaction, and the row and reference counts are verified before COMMIT; it is two rows today.
- **Fig2A's three families cannot answer RQ6** (Round 12 Q5 expected this): 22–34 of each family's 38 Fig2A members are
  too short to tell, and none of the rest is flagged. RQ6 needs a family built from a run on M2_aug-scale members.
- **64 M2_aug flags are unjudged** across 124 families; only F-130's queue exists (made in a sandbox).

## 7. Files

**Declared (mine):** `Working/cross_channel.py`, `Working/library/matching.py` (`classify_family_across_channels`,
`family_recurrence`, helpers beside them), `webui/client/src/library/CrossChannel.tsx`, `Edges.tsx`,
`Adapters/detection_seed_matches.py`, `Working/discovery/seeded_search.py`, the Seed page
(`discovery/SeedPage.tsx`), the suspected-artifact queue in `Working/review/` (`artifact_queue.py` new; `queues.py`,
`verdicts.py` gain the kind and unit).

**Shared, my hunks only:** `webui/server/library.py` (the send route, the card's fields, an edge's chance, Recurrence
cells' flagged/confirmed), `RecurrencePage.tsx` (the flag line), `webui/client/src/api.ts` (appended, declaration
merging; the two seed-result polls name the zone), Settings (`AnalysisDefaultsPage.tsx`, `fixtures/settings.ts`: four
keys), `webui/smoke_pages/zzzz_ad_suspected_artifact.json` (own file). `FamilyPage.tsx` was not edited.

**Out of the declared list — the reviewer should justify each:**

| file | why |
|---|---|
| `Working/database/schema.py` | `review_queues`' CHECK names the new kind and unit; an idempotent, backed-up rebuild for existing databases (the `annotations`-verdict pattern); `_backup_database` takes a label |
| `webui/server/review.py`, `webui/client/src/review/Inspector.tsx`, `review/SuspectedArtifact.tsx` (new), `api/review.ts` | the queue's card is a Review surface; held-out refusal knows the `member` unit; the score pill names a family member |
| `webui/server/discovery.py`, `webui/client/src/api/discovery.ts` | the exclusion zone reaches the seed routes, result key and run identity |
| `webui/server/library.py` — `_view_fingerprint` (AE's helper) | **a bug**: the Library's view cache did not include the cross-channel tables, so after *Classify* the family cards and Recurrence cells kept pre-classification bins (W's route test read 0 · 0 · 0). Two lines added to the fingerprint |
| `tests/test_cross_channel.py`, `test_cross_channel_simultaneous.py`, `test_webui_cross_channel.py`, `test_discovery_seeded_search.py`, `test_webui_discovery.py`, `test_export.py` | changed deliberately — units declared so the floor can be read; W's 0.95 / 0.5 / 0.7 simultaneous pairs are no longer artifacts; recurrence no longer drops a machine flag; the seed card says m/2; `test_export`'s "artifact" pair was two identical pure sines, which match themselves at every time and so cannot beat chance — now a pulse on independent noise (found by the gate run, `c44e5a1`) — each said in its commit |
| `webui/smoke_pages/zzz_w_cross_channel.json` | one expectation re-pointed: W's red Fig2A cell is not flagged any more (too short); F-130's M2_aug CH7_B2 cell is |
| `docs/rq_roundA/RQ6-…`, `RQ2-…`, `docs/prompts/fixup/README.md`, `QUESTIONS.md` | the RQ files' rule; the README row; the vocabulary decision recorded |

## 8. The gate

| check | result |
|---|---|
| `npx tsc -b` + `npm run build` (`webui/client`) | **pass** — the whole tree; `AE` had finished, so nothing in flight |
| `webui/smoke.py`, full walk, fresh `--sandbox` bridge on 8779 (private build), **machine taken for smoke alone** | **646 screenshots, 7 failures — none mine**: the five standing (`datasets--import-check-fails-fs-unknown`, `datasets--import-check-passes-MJu26a`, `models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`, `discovery.runs--default`) and the two `review.inspector--padding ±30 s / ±120 s is symmetric` screenshot writes that overrun Windows' path limit under the scratchpad `SMOKE_SHOTS` (`[Errno 2]`; `V` and `W` saw the same two). **0 browser console/page errors, 0 unexpected server tracebacks.** All 7 `zzzz_ad_suspected_artifact` states pass, and all 8 of `W`'s (one re-pointed, §7). A partial `--only zzz` walk earlier failed `zzz_surrogates`' Settings › Nulls state; it passed in the full walk (H: a partial walk is not the gate) |
| `pytest -n 4` (conda) | **2,291 passed, 24 skipped, 0 failed** (14 m 14 s). The first full run found 2 failures in `test_export.py` — its "artifact" pair was two identical sines, which cannot beat chance; the fixture now builds a real simultaneous copy (`c44e5a1`), and the re-run is clean. Against the baseline (2,212 / 22 / 0) the failure set is empty |
| route tests under `webui/.venv` | `test_webui_suspected_artifact.py` 4 passed, `test_webui_cross_channel.py` 9 passed; `test_webui_discovery.py` all pass but the documented pre-existing `test_the_scoreboard_cells_are_the_tables_own_numbers` |

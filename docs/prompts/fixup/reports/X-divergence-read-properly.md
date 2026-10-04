# Fixup X — divergence between the human record and a run, counted so that it means something

Run 2026-10-04, beside `V` (wave 4). Commits `446fa75` (red) → `a8aa37e` and the report commit. Prefix `fixup-x:`.

## In plain words first

Think of the human labels as stickers on stretches of tape — "something interesting here", "nothing here" — and of a
detector as someone dropping pins on the same tape. Before this prompt, Explore counted a **disagreement** every time a
sticker had no pin on it or a pin had no sticker, whatever the sticker said and whether or not anyone had dropped pins
on that stretch at all. So a "nothing here" sticker with no pin — which is agreement — counted as disagreement, and so
did every sticker on the ten channels no detector has ever run on. That gave 11,221 "disagreements" on M2_aug, which
meant nothing.

Now there are four boxes and a pile beside them:

| | the human said yes | the human said no |
|---|---|---|
| **the detector fired** | agree | **disagree** |
| **the detector was silent (and had run there)** | **disagree** | agree |

…and the pile is **not comparable**: places no detector covered, or that no human reviewed. The pile is counted and
shown, but never called a disagreement. On M2_aug the 11,221 becomes **55 + 543 = 598 disagreements**, with **8,852 not
comparable**.

And **precision** — "when the detector fires, how often is the human with it?" — was 0 % by construction, because the
human stickers are 10-minute windows and a detection is a two-minute event that can never "overlap" a window well
enough under the old rule. It is now two numbers, each saying how it was counted:

- **containment** — does the detector fire inside windows a human called interesting? (by the windows the detection
  falls in)
- **extent** — when there is a human-drawn event, does the detector get its start and end right? (the old overlap rule,
  but only against the 35 event-shaped rows, with how wide those rows are printed beside the number)

**One decision came up and you made it** (2026-10-04): what "a detection falls in a window" means. Requiring it to fit
*wholly* inside a window (the rule you chose for training windows, Q41) scored only 16 of 562 detections; scoring by
where its **middle** is scored 91. You chose **both, as a setting**: middle by default, *wholly inside* selectable in
Settings › Analysis defaults. Recorded as `QUESTIONS.md` Q-D2c.

**What this does not fix:** there are still no Review verdicts in the real database, and most detections fall outside
every reviewed window (the windows cover only a few hours per channel per day). RQ5 now has an instrument that counts
properly; it needs your Review hours to have something to count.

## What was built

1. **`Working/discovery/divergence.py`** — the one module the scoreboard, Compare and Explore read.
   `channel_divergence(conn, recording_id, run_ids, *, span, containment)` resolves each detection's human verdict
   **adjudication → extent (§4.6 against the event-shaped rows) → containment (the reviewed windows it falls in, all
   agreeing)**, and says which rule did it (`by`). Machine-yes cells count detections; machine-no cells count the
   human labels the run was silent on, only where a run completed over a span wholly containing the label. Not
   comparable carries its reason (`no run covered it`, `no window near it`, `centre outside the windows`, `windows
   disagree`, `longer than a window` / `straddles a window edge` under *wholly inside*, `unsure …`). Surrogate runs are
   never machine findings (`T`). "Human yes" = interesting / seed; "human no" = not_interesting / artifact.
2. **Q-D2's two figures**, each with its rule text on the payload (`precision.containment`, `precision.extent`); the
   extent figure carries `widths` (n / min / quartiles / median / max of the event rows inside the run's span). Both
   count a verdict given in Review first (`L`'s handed-on finding: *precision means what it says*).
3. **The two core queries have callers and condition on what they must.** `divergence_rejected_detections(...,
   run_ids=, verdicts=)` and `divergence_annotations_without_detection(..., run_ids=, verdicts=)` — the second now
   only counts an annotation wholly inside a completed run's span. The bare forms are unchanged for their old tests.
4. **Explore › Corpus.** `coverage()`'s `disagree` is the two disagreement cells; each row's counts carry the
   divergence; the payload's `divergence.scope` says what it pools ("no run picked — pooling every run on this
   recording — 45 runs" / "the 1 run picked"). The bottom bar reads *N machine yes · human no · M machine no · human yes
   · K not comparable* (reasons on hover). Channels with nothing comparable stay grey and say why.
5. **Discovery › Runs scoreboard.** *reviewed* / *interesting* / *precision* are the containment figure, so precision
   is still the ratio of the two cells beside it; the precision cell shows **both** figures, each with its rule (and
   for extent the denominator's widths) behind its ⓘ. The template card reads the containment figure. The old
   §4.6-over-every-annotation numbers stay on the wire as `iou`, for the record.
6. **Discovery › Compare with *human annotations* as a side** pairs by the divergence (`divergence.human_pairing`),
   says so ("paired by the divergence · Review verdict, extent, containment"), and carries **the breakdown** below the
   set overlap: the two cells by channel, a per-channel density strip by time (the Corpus map's amber quantile ramp),
   and by morphology (human `element` tags; the machine side's absence stated). It says there is no test of
   structure and no null.
7. **Settings › Analysis defaults › window-label containment** (`containment`: `centre` | `whole`), beside the IoU and
   onset keys; read by `divergence.containment_from_settings`; every containment figure prints `mode`.

## The old *disagree* beside the new cells — three channels (M2_aug, every run pooled, centre rule)

Read from a copy of the real database (scratchpad, 2026-10-04 11:01); the old count is the pre-`X` formula over every
verdict.

| channel | annotations | detections | old *disagree* | machine yes · human no | machine no · human yes | yes · yes | no · no | not comparable |
|---|---|---|---|---|---|---|---|---|
| CH1_A1 | 708 | 109 | **691** | 10 | 151 | 1 | 540 | 98 (88 no window near · 10 centre outside) |
| CH4_A2 | 698 | 248 | **642** | 40 | 8 | 8 | 39 | 795 (595 no run covered · 128 no window near · 72 centre outside) |
| CH7_B2 | 683 | 104 | **714** | 3 | 178 | 13 | 458 | 96 (70 no window near · 18 centre outside · 8 no run covered) |
| all 16 | 11,265 | 546 | **11,221** | 55 | 543 | 33 | 2,180 | 8,852 |

Ten channels (CH3, CH5, CH8, CH10–CH16) have no run: every one of their annotations is *not comparable* and their
*disagree* is 0 where it used to equal their annotation count. Under *wholly inside* CH4_A2 reads 8 / 8 / 0 / 39 with
835 not comparable (96 detections longer than a window, 16 straddling one).

## Both precision figures for every run in the sandbox session

Sandbox `webui/runtime/20261004-111504` (the walk's) — the session's three runs at its default scope, and the run I
applied over a densely reviewed section to walk acceptance 3–4.

| run | scope | found | containment (yes / judged, by Review) | extent (yes / judged) | extent's event rows |
|---|---|---|---|---|---|
| `dehshibi_spikes` | 452–456 h × CH2_A1, CH6_B1, CH7_B2 | 3 | — nothing judged (0 / 0) | **0 %** (0 / 3) | 1 row, 4,320 samples |
| `drop_detection_v1` | same | 3 | **0 %** (0 / 1) | **0 %** (0 / 3) | 1 row, 4,320 samples |
| `drop_detection_v1_2` | 192–216 h × CH4_A2, CH8_B2, before Review | 16 | **100 %** (3 / 3, 0) | — (0 / 0) | none in the span |
| `drop_detection_v1_2` | same, after five verdicts | 16 | **62.5 %** (5 / 8, 5) | **40 %** (2 / 5, 5) | none in the span |

Pooled over all M2_aug runs: containment **33 / 88** (centre) or **2 / 16** (wholly inside); extent **0 / 375** over
**25** covered event rows of **126 – 324,000 samples, median 9,000, middle half 3,874 – 108,000**. That 0 / 375 is Q-D2's
caveat made visible rather than a verdict on the detectors: 375 detections lie inside catalogue "regions" up to ninety
hours long that no event could match.

## Acceptance — the walk (sandbox bridge, port 8771, private build)

1. **Explore › Corpus, M2_aug, colour by disagree, one run picked** (`#63`, drop detection, CH2_A1): only CH2_A1 lights;
   the caption reads *"the 1 run picked · only places a run covered and a human reviewed"*; the bar reads *"132
   annotations · 47 detections · 0 machine yes · human no · 121 machine no · human yes · 52 not comparable"*. ✔
2. **Discovery › Runs**: two figures per run, each with its rule behind its ⓘ and, for extent, the denominator's width
   distribution (*"1 event row inside the span · 4,320 samples – 4,320 samples"*). ✔
3. **Discovery › Compare, *human annotations* as A**: on the session's 4 h section the overlap still reads *both 0* —
   by the data now, not by construction (none of the three detections falls in a reviewed window; Compare says it
   paired by the divergence). Over 192–216 h it reads **only A 26 · both 3 · only B 13**, the breakdown below it. ✔
4. **Five detections judged in Review** (queue opened by *Send 15 unjudged to Review*; N, I, N, A, I) → *yes · yes* 3 → 5,
   *yes · no* 0 → 3, *not comparable* 13 → 8, overlap *both* 3 → 5; the scoreboard's containment 3 / 3 → 5 / 8. The cells
   moved by exactly those five (all five had been *not comparable*). ✔

## The breakdown for one run — `drop_detection_v1_2`, 192–216 h, after the five verdicts

| channel | machine yes · human no | machine no · human yes | yes · yes | no · no | not comparable |
|---|---|---|---|---|---|
| CH4_A2 | 3 | 18 | 5 | 7 | 7 (4 centre outside the windows · 3 no window near) |
| CH8_B2 | 0 | 2 | 0 | 20 | 1 (no window near) |

By time (1 h bins): the 3 *yes · no* sit at 192, 197 and 198 h; the 20 *no · yes* spread over 15 of the 24 hours (most
2 per hour). **By morphology: nothing** — none of the 23 disagreements rests on a tagged human label.

## What the morphology column could and could not show

- **Human side:** `annotation_tags` of category `element` — **34 links in the whole database** (sharkfin 17, halfdome 3,
  …) against 11,234 window labels. A disagreement is tagged only when a label it rests on carries one, so on real data
  the column is almost always empty (0 of 23 above; 1 of 8 on the session's default scope — one *machine no · human
  yes* window tagged *sharkfin*). The page says how many disagreements carry a tag and how many links exist. An
  adjudication's own `element` tags are read too, so tags given in Review will show here once Review stores them.
- **Machine side:** no detector writes a morphology into `detections.meta_json` (the keys present are `neighbours`,
  `rank`, … for the MP runs), and a class given in Review is not stored (R3, the Review-behaviour prompt). The column is
  replaced by a sentence saying so, not drawn empty.

## Left

- **Recall is still §4.6 over every annotation** — 0 by construction on window labels, exactly what precision was. It
  wants the same containment rule (positives = human-yes windows the run covered; found = those a detection falls in).
  Not in this prompt's list; the scoreboard's recall cell is unchanged.
- **The live verdict counts are the researcher's to make.** `adjudications` has 0 rows in the real database.
- **"Structured" has no test** (no null for clustering of disagreements) — an RQ5-round decision, said on the page.
- **Extent over the catalogue's region-sized rows** reads ~0 and will keep doing so; the widths make that legible, they
  do not cure it. Re-cutting the ground truth (Q-D2 (b)) stays not taken.
- `already judged` is untouched (pre-run verdicts by definition, `L`).

## Files outside the declared list

| file | why |
|---|---|
| `Working/discovery/divergence.py` (new) | the "one module" item 1 asks for |
| `Working/discovery/scoreboard.py` | the scoreboard's precision cells' core — adds `precisions` / `divergence` to each row; the old fields and their 27 tests unchanged |
| `tests/test_surrogate_never_a_detection.py` | **deliberate behaviour change:** its Explore test read `disagree == 2` because a detection under no human label counted as a disagreement; it is now *not comparable* and the assertion reads 1 (commit `321a217` says so) |
| `webui/client/src/settings/AnalysisDefaultsPage.tsx`, `webui/client/src/fixtures/settings.ts` | the containment setting the researcher asked for |
| `webui/client/src/explore/Heatmap.tsx` | Explore › Corpus's disagree definition and degenerate-row rule |
| `webui/client/src/discovery/{Precision,Divergence}.tsx` (new), `ComparePage.tsx`, `discovery.css`, `api/discovery.ts` | the scoreboard cell and Compare's breakdown; in the shared `RunsPage.tsx` only the precision cell body and one import |
| `docs/prompts/fixup/QUESTIONS.md`, `05-discovery.md`, `rq_roundA/RQ5-…` | Q-D2c recorded, D2 closed in place, RQ5 updated |

Shared files (`discovery.py`, `api.ts`, `api/discovery.ts`, `RunsPage.tsx`) were committed with this prompt's hunks only
while `V` had uncommitted hunks in two of them (staged from HEAD with a scripted patch rather than `git add -p`, which
this shell cannot drive).

## The gate

| check | result |
|---|---|
| `npx tsc -b` + `npm run build` | clean, with `V`'s finished tree in it (writes the shared `client/dist`; every smoke walk served a private build of the same tree) |
| `pytest -n 4` (conda) | **2134 passed, 21 skipped, 0 failed** in 6 m 46 s; the failure set is empty, as at baseline. The README's 1952 / 17 was after `H`; the waves since added the rest. One test was changed on purpose (`test_surrogate_never_a_detection.py`, above) |
| `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` (`webui/.venv`) | still fails, **on the same assertion with a different string**: it pins `reviewedCriterion == "onset inside reviewed coverage"`; that was already `"…, or matching an annotation that is"` before me, and is now the containment criterion. The other 49 discovery route tests pass |
| `webui/smoke.py`, full walk, fresh `--sandbox` bridge, alone | **616 screenshots, 7 failures, 0 browser console/page errors, 0 unexpected server tracebacks** (runtime `20261004-175151`, 17:52–18:14). The five standing failures, and the two `review.inspector--padding +/-… s` states that only pass in the tracked screenshot tree (their `/` makes a sub-directory under any other `SMOKE_SHOTS`; `V` found this). All five `zzz_x_divergence` states pass |

**I took the machine for smoke four times** (14:00, 14:47, 17:28 page-only, 17:52), and once more for a baseline walk on
a temporary branch with every `fixup-x` commit reverted (deleted afterwards; `main` untouched). `V` had finished at 12:05,
so nothing else ran during any of them.

**The first two full walks read 20 and 21 failures, and that is recorded here rather than dropped.** The extra ~13
states (Discovery Seed/Stages, Explore Cross-channel, the Interrogation rose and Slope, the Review queue rail, Settings
Datasets/Storage) had all screenshotted on their loading skeletons: the bridge was busy, with *Jobs · 3* in the header.
To find out whether that was my code, I walked the same tree with `fixup-x` reverted: **7 failures**. Then I walked
`fixup-x` again with a probe timing the bridge every 2 s: **7 failures, and the bridge never took more than 1 s to
answer.** Per run, the divergence costs 10–100 ms and Explore's coverage 0.4–1.6 s (it was well under a second before).
None of my routes is ever called by a job. My best reading is that the two bad walks met a machine that was busy for
reasons outside the walk (the first ran with my in-app browser tab still polling a stopped bridge). But I did not prove
that, so the 1.3 s coverage is the first thing to suspect if it comes back. The cheap fix is ready: replace the
correlated `NOT EXISTS` in `divergence_annotations_without_detection` (0.5 s of the 1.3 s) with the Python overlap the
module already computes, or cache the divergence per data fingerprint.

Evidence: `webui/screenshots/fixup/X/` — `01`–`02` Explore's disagree pooled and on one run, `03` the scoreboard's two
figures with the extent rule open, `04` Compare against the human record (paired by the divergence), `05` the containment
setting. The acceptance walk's numbers are in the sections above.

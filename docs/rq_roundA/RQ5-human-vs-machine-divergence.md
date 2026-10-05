# RQ5 — Where do human and analytical judgement diverge, and is the divergence structured?

**Status (2026-10-04): the instrument is built; the data is not there yet.** After fixup `X` the divergence conditions on
verdict and on where a run actually ran, precision is Q-D2's two figures, and a breakdown by channel, time and
morphology sits on Discovery › Compare. What is missing is verdicts: `adjudications` still has 0 rows in the real
database, and only 33 + 55 detections on M2_aug fall inside a reviewed window at all. Owners now: the researcher's
Review hours, and the Review-behaviour prompt for stored classes. (Was, 2026-10-03: not answerable — no adjudication
verdicts, and the live "disagree" number was not a divergence.)

## In plain words

Sometimes you say "interesting" where the detector saw nothing, and sometimes the detector fires where you'd say "not
interesting". Where do those disagreements happen? Do they bunch up on certain channels, times or shapes? Or are they
scattered randomly? If they bunch up, that tells you something about either the detector or about how people judge.

## What is known

- **`adjudications` has 0 rows** in the real database. The "machine yes, human no" direction has no data.
- **"Disagree" is not a real divergence count.** Explore's *disagree* counts every annotation with no overlapping
  detection, whatever its verdict, even on channels where no detector ran. That gives 11,261 of 11,265.
- **The units don't match.** Human labels are 600-sample windows and detections are events, so IoU ≥ 0.5 rarely holds.
  That's why *both* reads 0.
- **The two divergence queries** (`Working/database/queries.py` :384, :414) have no caller.
- **Morphology is thin on the human side:** 34 human `element` tag links, against Library tags on the machine side
  (`trough` 2,827, `sharkfin` 772). Classes given in Review are not stored (R3).
- `L` landed on 2026-10-03, so queues from Discovery now open and verdicts can accumulate.

- **Surrogate detections are out of every count** (`T`, 2026-10-03, `docs/prompts/fixup/reports/T-surrogates-one-null-never-a-detection.md`). One predicate in the core
  (`queries.not_surrogate`) and every reader goes through it. On M2_aug: Explore's detections 576 → 546, *disagree*
  11,234 → 11,221, and *annotations with no detection* 11,109 → 11,117 — **eight human spans had been counted as
  "the machine found this" only because a null draw happened to overlap them.** Both core divergence queries
  exclude surrogate runs, so `X` builds on clean inputs.

- **Built by `X` (2026-10-04, `docs/prompts/fixup/reports/X-divergence-read-properly.md`):**
  - **One module, `Working/discovery/divergence.py`,** read by Explore › Corpus, the Discovery scoreboard and Compare.
    Four cells and a fifth that is not a cell: *machine yes · human yes / no* count detections, *machine no · human
    yes / no* count the human labels the run was silent on, and **not comparable** counts what no run covered or no
    human reviewed — never a disagreement. A detection's human verdict comes from a verdict given on it in Review
    first, then the event row it matches (§4.6), then the reviewed windows it falls in.
  - **Explore › Corpus *disagree*** is the two disagreement cells, on the runs picked (or every run, pooled, and the
    page says so). On M2_aug: the old count **11,221** becomes **55** machine yes · human no + **543** machine no ·
    human yes, with **8,852** not comparable (10 of 16 channels have no run at all).
  - **Precision is two figures:** containment **33 / 88** detections judged on M2_aug (centre rule; **2 / 16** under
    *wholly inside*), extent **0 / 375** over 25 event rows of **126–324,000 samples, median 9,000** — Q-D2's caveat,
    printed beside the number.
  - **The breakdown** (Compare with *human annotations* as a side): the two cells by channel, by time bin (a density
    strip) and by human `element` tag; the machine side has no morphology to show (no detector stores one; R3). It
    says there is no test of structure and no null.
  - **Adjudications count:** judging five detections in Review moved the cells by exactly five (sandbox walk).

## Decisions already made

- **Q-D2:** precision is reported as two numbers, each with its own rule. Containment over the window labels; extent
  over the event-shaped rows, with their width distribution printed beside it.
- **Q16:** Review classes (R3) and the rediscovery prior verdict (R7) are in scope for the Review-behaviour prompt.
- **Q41:** unlabelled is never "not interesting". The same principle applies here: an uncovered span is not a
  disagreement.
- **Containment mode (the researcher, 2026-10-04, during `X`): both, as a setting.** A detection is scored by the
  reviewed windows its **centre** lies in by default; *wholly inside* (Q41's rule, mirrored) is selectable in
  Settings › Analysis defaults beside the IoU keys, a versioned act. Every figure prints the mode it used. Recorded in
  `QUESTIONS.md` under Q-D2.

## What is still needed

| Step | Owner |
|---|---|
| ~~*Disagree* conditions on verdict and on where a run actually ran~~ | `X`, done 2026-10-04 |
| ~~Q-D2's two-number precision~~ | `X`, done 2026-10-04 |
| ~~A breakdown by channel, time and morphology over the two core queries~~ | `X`, done 2026-10-04 |
| Recall is still §4.6 over every annotation (0 by construction on windows) — it wants the same containment rule | unscoped; `X`'s report, *Left* |
| ~~Surrogate detections kept out of every count~~ | `T`, done 2026-10-03 |
| Classes / tags given in Review stored | Review-behaviour prompt |
| Adjudication hours on real queues | the researcher |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q5. Apply templates over a scope, send the unjudged to Review, judge, then read the
breakdown of the two disagreement cells beside the map. No null exists for "structured", and the page says so. Whether
one is needed is an open research decision for the RQ5 round.

## Open decisions

None blocking. For the RQ5 round: what counts as "structured" (a null for clustering of disagreements). Worth knowing
before then: under either containment mode most detections fall outside every reviewed window (the windows cover a
few hours per channel per day), so RQ5's machine-yes cells will be filled mostly by Review verdicts, not by the
existing window labels.

## Log

- 2026-10-03 · grilling · file created.
- 2026-10-03 · fixup-t · surrogate runs' spans excluded from Explore, Review and both divergence queries (8 false
  "machine found it" on M2_aug removed).
- 2026-10-04 · fixup-x · the divergence module, Explore's two cells, Q-D2's two precision figures, Compare's breakdown;
  containment mode made a setting (centre default) on the researcher's answer.

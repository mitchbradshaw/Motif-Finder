# RQ5 — Where do human and analytical judgement diverge, and is the divergence structured?

**Status (2026-10-03): not answerable.** There are no adjudication verdicts, and the live "disagree" number is not a
divergence. Owners: fixup `X` (after `L`, `T`), the researcher's own Review hours, and the Review-behaviour prompt for
stored classes.

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

## Decisions already made

- **Q-D2:** precision is reported as two numbers, each with its own rule. Containment over the window labels; extent
  over the event-shaped rows, with their width distribution printed beside it.
- **Q16:** Review classes (R3) and the rediscovery prior verdict (R7) are in scope for the Review-behaviour prompt.
- **Q41:** unlabelled is never "not interesting". The same principle applies here: an uncovered span is not a
  disagreement.

## What is still needed

| Step | Owner |
|---|---|
| *Disagree* conditions on verdict and on where a run actually ran | `X` |
| Q-D2's two-number precision | `X` |
| A breakdown by channel, time and morphology over the two core queries | `X` |
| ~~Surrogate detections kept out of every count~~ | `T`, done 2026-10-03 |
| Classes / tags given in Review stored | Review-behaviour prompt |
| Adjudication hours on real queues | the researcher |

## How it gets answered

Follow `RESEARCH_RUNBOOK.md` Q5. Apply templates over a scope, send the unjudged to Review, judge, then read the
breakdown of the two disagreement cells beside the map. No null exists for "structured", and the page says so. Whether
one is needed is an open research decision for the RQ5 round.

## Open decisions

None blocking. For the RQ5 round: what counts as "structured" (a null for clustering of disagreements).

## Log

- 2026-10-03 · grilling · file created.
- 2026-10-03 · fixup-t · surrogate runs' spans excluded from Explore, Review and both divergence queries (8 false
  "machine found it" on M2_aug removed).

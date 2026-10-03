# RESEARCH_RUNBOOK.md — the clicks, per question

The explicit walk through the app for each of the six PRD questions, written 2026-10-03 from the
readiness pass (`docs/RESEARCH_READINESS.md`). Every step is marked: **works** means it was driven on
real data on 2026-10-02; **`L`**, **`T`**, … names the Stage 5 prompt (`docs/prompts/fixup/README.md`)
that has to land before the step exists. A question is answerable when none of its steps carries a
prompt letter.

Run the real thing in **`--project`** (`webui\start.ps1 -Project`, or
`webui\.venv\Scripts\python.exe webui\run_server.py --project`); it backs the database up first. Nothing
below reads the held-out recording.

**Decisions first.** `docs/prompts/fixup/QUESTIONS.md` Round 9 holds nine open rows (Q35–Q43). The
prompts take the recommended default on any left open — except `W`, which waits for Q40.

---

## Q4 — band decomposition + symbolic encoding vs raw-signal methods

Closest. Today the whole walk works with one template per band, saved by hand.

1. **works** Analyse › Chain → ⤓ *Import* → `symbol_search` (or `drop_detection_v1` if drops are the
   raw-signal baseline you want).
2. **works** `+ insert` above 01 → *Bandpass filter* → *Insert* → open its row (the settings button) →
   set `low_hz` / `high_hz` → ▶ *Run chain* on an Explore span (*Send span to Analyse*) or *Use the
   example span*.
3. **works** ▢ *Save template* → name it with the band. Repeat 2–3 per band. — **`Z`** replaces 2–3 with a
   band list on *Apply template*.
4. **works** Discovery › Runs → *Scope* (recording · channels · section) → *Apply template* → tick the
   band templates and the raw-signal template → *Add and run*.
5. **works** Tick two runs → *Compare* → *Set overlap*: only A · both · only B, per channel. — **`Z`**
   lets B be the set of all band runs (their union).
6. **`L`** Runs → select the band run → *Send N unjudged to Review* → *Open Review* → judge with
   `I` / `N` / `A` / `U`. — **`Z`** narrows this to *Send only-B unjudged to Review*.
7. **`Z`** Compare → the *only B* row reads *judged n · accepted k*. That sentence, with the null count
   beside it (**`T`** for the true draw count), is the answer on that scope.

## Q2 — a human-adjudicated exemplar as a matrix-profile seed

1. **works** Review › a detection queue (e.g. queue 2, 130 detections of `drop_detection_v1` on
   Mushroom_260720 CH14, or one made by step 6 of Q4) → `S` on a span worth searching for → it becomes a
   Library entry (`source_kind = 'review'`).
2. **`Y`** *Seed search in Discovery →* from that promotion, or Discovery › Seed search → *change seed* →
   filter *review* → pick it. (Today the picker shows the first 24 of 3,603 entries, all machine-made.)
   Alternative seed, also **`Y`**: Explore › Signal → brush a span → *Take span for Review* → it appears
   under *Explore selection*.
3. **works** Seed page: *Scope* → *Run seed search* → the histogram with the 200-draw null behind it →
   drag the cut → *Run seed search* again. **`V`** adds the scale bank (*3 lengths*).
4. **`Y`** *Open in Runs* lands on the run (today the link names the wrong key).
5. **`L`** Runs → *Send N unjudged to Review* → *Open Review* → judge every match.
6. **works once 5 exists** Runs → *Refresh after reviewing* → the seed run's row: *already judged ·
   reviewed · interesting · precision · recall · null expects / draws · × null*. — **`X`** makes
   *precision* mean what it says (containment over the window labels, extent over the event rows).
7. The answer is that row, read with its null. Nothing on it claims to beat chance unless *× null* does.

## Q5 — where human and analytical judgement diverge

1. **works** Explore › Corpus → recording → *colour by · disagree*, *Verdict* and *Morphology tag*
   filters. — **`X`** makes *disagree* condition on verdict and on where a run actually ran (today it
   counts every annotation with no detection, on every channel, 11,261 of 11,265).
2. **works** Discovery › Runs → *Apply template* over a scope → the scoreboard's precision / recall
   against the human record. — **`X`** for the two-number rule; **`T`** to keep surrogate detections out.
3. **works** Discovery › Compare with *human annotations* as A → *only A · both · only B* and *Step through
   the disagreements*. (Today *both* is 0 by construction: 600-sample review windows against event
   spans under reciprocal IoU.)
4. **`L`** then **works** Runs → *Send N unjudged to Review* → judge. Each verdict is an `adjudications`
   row — the "machine yes / human no" direction, which has 0 rows in the real database today.
5. **`X`** The breakdown of the two disagreement cells by channel, time and morphology, beside the map.
   No null exists for "structured"; the page says so.
6. For morphology on the machine side a class or tag given in Review has to be stored — the Review
   *behaviour* prompt (`README.md`, R3), still waiting on Q-R2.

## Q6 — recurrence across channels and recordings, with contamination and propagation taken out

1. **works** Discovery › Runs → *Apply template* across channels (one run group, a paired surrogate per
   channel) → the scoreboard's *null expects / × null*. **`T`** for the true draw count.
2. **works** Library › Recurrence → families × recording × channel, per hour or count; a cell with no
   reviewed coverage reads `?`.
3. **works** Explore › Cross-channel → reference channel, window, *lag-aligned* → lag, r and bin per
   pair for **that window**, computed live, stored nowhere.
4. **`V`** then **`W`** Library › Family → *Classify across channels* → bins stored on edges; the rail's
   *cross-channel* counts; Recurrence's red artifact cells and its count toggle *excluding artifacts* /
   *propagation counted once*.
5. **`W`** needs **Q40** answered first: what lag is (simultaneous windows, not snippet alignment), and
   whether a zero-lag pair at r = 0.8 is contamination.

## Q3 — motif identity under scale normalisation

1. **works** Library › Edit grouping → basis *shape distance* (the scale-invariant one; the only distance
   offered) → cut → *Apply*. Library › Family shows a family's members and their durations.
2. **`Y`** then **`V`** Library › Family → *Seed search in Discovery →* → scale bank *3 lengths* → run →
   each match carries its scale factor.
3. **`L`** judge the matches; **`V`** Runs → *Add N matches to E-xxxx* → members with an edge **per
   distance function** (scale-invariant, symbolic, native-length control).
4. **`V`** Library › Family → the scale read-out: per scale factor, matches · judged · accepted, and the
   same pairs' distance under the scale-invariant function and the control. That table is the question.
5. Read it with the Q26 caveat: on a sharkfin exemplar the native length is itself in question
   (`future/N-event-extent.md`).

## Q1 — cluster-derived vs manually-derived labels

**Does the clusters-across-channels-on-HPC workflow exist today?** Partly, and not where it would be
used.

- **works** Analyse › Chain → ⤓ *Import* `windows_model` → delete *Classifier (model)* → ▶ *Run chain*
  on a span → ▢ *Save template*. Measured: *"3 clusters · sizes 42, 6, 72"*, saved as kind `training`
  although the footer says *"terminal Grouping — add a stage to reach a template type"*.
- **no page** applies it across channels or writes its script: Discovery's *Apply template* lists only
  detection templates; Models › Launch is a fixture page; Analyse's *Create SLURM script* is disabled.
- **the bridge can**, by hand: `POST /api/discovery/plan`, `/slurm` and `/templates/apply` accept the
  template. Measured: a `--array=0-2` script was written and a local fan-out ran — **one clustering per
  channel**, so cluster 1 on one channel is not cluster 1 on the next, which is not a label vocabulary;
  and the script bakes `C:/Users/...` paths under a cluster `--chdir`, so it would not run as written.
- **outside the UI**, `Pipelines/hpc_export/export_wm_scales.py` writes resumable SLURM jobs for the
  heavy step (the window matrix) per channel and scale, and `Pipelines/import_wm_artifacts` brings them
  back; clustering those is a script, not a page.

The operation Q1 needs is **not** "apply the cluster template per channel"; it is **one clustering over
the pooled windows of several channels, fitted on training windows only**, which is what Models ›
Launch's *Sources · channels* means. The walk, once `AA` and `AB` land:

1. **works** Analyse › Chain → ⤓ *Import* `windows_model` → ▶ *Run chain* on a span to tune `window_min`,
   `k` and the classifier's parameters → ▢ *Save template*.
2. **`AA`** The manual arm exists as a block (`catalogue.manual_labels`, `WindowSet → Grouping`) and
   *Save window set* is on every WindowSet row. Decide **Q41** (binary `interesting` /
   `not_interesting`, `artifact` excluded, is the default).
3. **`AB`** Models › Launch → template → *Sources · channels* on `M2_aug_concat_fs1.mat` (the page shows
   hours, windows, human verdicts, classes seen per channel) → *Save window set* → arms A (manual) and
   B (cluster) with the RF baseline → *Evaluation*: time-blocked split with a gap ≥ one window (the
   labels overlap on a 200-sample stride; a random split leaks) → *Before launch* checks → *Train
   locally* (RF, minutes) or *Create SLURM script* (CNN arm, after **Q42** and after Jobs is wired).
4. **`AB`** Models › Results → arm A, arm B, RF baseline, the label-shuffle null. Models › Compare → one
   difference, *label source*, attributable → ΔF1 with CI, McNemar, per class, per channel, the
   cluster→class contingency.
5. **works** The held-out lock: every route refuses `M4_aug_concat_fs1.mat` (423). The generalisation
   run on it is one act in Settings › Datasets after the freeze, by you, once.

---

## What every question shares

- **A queue that opens** (`L`) — three of the six stop at the same hand-off.
- **The null the page names is the null it drew, and a surrogate detection is never a detection** (`T`).
- **Edges** (`V`) — Q3 and Q6 both stand on `motif_edge`, which has 0 rows.
- Everything above is read in `--project`; the runs you make there cannot be undone, which is the point.

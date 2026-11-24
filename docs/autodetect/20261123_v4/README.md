# Auto-detect v4 — your event rule (23 Nov 2026, evening)

**Open `index.html`**, or use the `autodetect-pages` entry in `.claude/launch.json` (port 8791) and go to
`/20261123_v4/index.html`. Earlier pages are kept for comparison: `../20261123_v3/`, `../20261123/` (v2) and
`../20261119/` (v1). Type an hour into **go to** (for example `396:42`), or open a page at a time with
`viewer.html#t=396:42`.

**Whole-drop rule:** the latest **committed** version, as you asked. That is HEAD `79d0243e`, committed 20:31 by the
NeurIPS session with your three tail-end decisions. The run loads it from git, not from the working copy, and each
`run.json` names the commit it used.

## What changed, and why (from your v3 screenshots)

| Your screenshot | What was wrong | What v4 does |
|---|---|---|
| 1. M2_aug 282:37–283:35: a long box over a smaller event, and the dip at 283:24 missed | The 35-minute slow decline's box ran 3.5 minutes past its bottom, over the sharp drop after it. The 1 mV dip was measured only as a rise: auto-detect looked one way and stopped at the climb after the dip | **Box margins stop at the neighbouring event**: the decline's box now ends at 282:57:53. **Every box is measured both ways**: the 283:24 dip is found (1.02 mV, confidence 0.93) |
| 2. CH14 395:36–395:49: long blue boxes over the spikes, and the "?" spike | Each spike's fall back came out a hair deeper than the spike (1.29 against 1.23 mV). So it was not folded in as the spike's return, and stood as a 3–7-minute "drop". The "?" spike itself was lost | **A return may be up to 1.25× as deep as its event**, and must start where the event peaks or bottoms out (within one fall). The fall-backs fold in. The "?" spike is a rise (1.16 mV, confidence 1.00), and both 395:48 spikes are found |
| 4. CH14 396:38–397:05: the 26-minute pink box | The rise back after a 5.9 mV drop measured 6.1 mV, so it was not folded in, and its box covered the whole train | Folded in as the drop's return; the box is gone |
| 3, 4, 5. CH14 396:15–396:33, 396:40–397:05, 397:31–397:45: missed trains | No detector proposed 0.2–0.4 mV events; the few found came from R4's window scan | **Your rule as a finder** proposes every place that meets it. Those windows now hold 76, 45 and 16 candidates (v3: 10, 4 and 3). The spikes come out as rises. The two-phase ones come out as a rise plus the fall below baseline after it |
| 6, 7. CH14 470:57 and 479:04: 3–4-sample events | 0.08–0.11 mV dips in wander. Two windowed drop detectors agreed on them, which lifted them to confidence 0.72–0.81 | **Your rule** removes them: no candidates left in either window |

## Your rule, as built

A **drop** counts when it can be told from noise. Either:
- it is **sharp**: its steepest 1-second step is at least 10 times the channel's 1-second step noise (the bar
  sharp rises already use); or
- it **falls steadily**, at least **5 samples each lower than the last**, to a bottom at least **6 times the fine
  noise below the average of the points 10 s either side**. That last part is "a significant depth greater than the
  rolling average of the surrounding points". The fine noise is how far those points stray from their own 2-second
  average.

A **rise** counts when it is sharp, as before. It has no 5-sample minimum: the small CH14 spikes jump in 1–2 samples.

Why it is built this way:
- **Why sharp drops are exempt from the 5 samples.** Without the exemption, your rule would have lost 11 events you
  accepted, 10 of them on CH14. These are narrow, deep drops, such as CH14 395:46:12 (1.3 mV in 1.5 s), 30–90
  times the noise. With the exemption, it loses none on any reference.
- **Why "fine" noise.** A first version measured the spread of the surrounding points as a whole. In a train the
  neighbours are as big as the event, so it lost 60–70 accepted CH14 train events.
- **The bar.** Bars of 4, 5, 6 and 8 all keep every accepted event. At 6, all four of your noise screenshots go
  (CH14 470:57 and 479:04). 6 is also the whole-drop rule's own depth bar.

The rule is used three times:
1. To set aside non-events before events are joined, so a non-event can't absorb a real one.
2. As a gate on what is shown.
3. As a **finder** ("event rule"): it proposes every place that meets the rule, so the trains no detector proposed
   are found. Its precision in the blend is 0, so it proposes but never raises a confidence.

## Results (confidence ≥ 0.5 unless noted)

| Reference | Run time | Candidates: ▼ drops / ▲ rises | Found (v3) | Hit rate (v3) | At ≥ 0.9: candidates · found · hit rate |
|---|---:|---|---:|---:|---|
| M2_aug CH7_B2, 528 h | 9.4 min (v3: 4.9) | 5,016 (9.5/h): 4,334 / 682 | 208 of 212 (206) | 90 % (93 %) | 3,232 (6.1/h) · 202 · 94 % |
| MJu26a CH14, 264 h | 12.3 min (v3: 3.7) | 4,262 (16.1/h): 3,047 / 1,215 | 519 of 528 (518) | 97 % (98 %) | 2,170 (8.2/h) · 517 · 97 % |
| MJu26a CH15, 264 h | 4.5 min (v3: 2.8) | 553 (2.1/h): 523 / 30 | 176 of 186 (176) | 93 % (94 %) | 453 (1.7/h) · 171 · 93 % |
| M4 CH1_A1, 505 h | 5.6 min (v3: 3.5) | 795 (1.6/h): 637 / 158 | 47 of 47 (47) | 80 % (88 %) | 303 (0.6/h) · 41 · 85 % |

- **Run time.** Each run is still well inside your 30–60 minutes a channel. The machine was busy during the CH14 run;
  CH14 alone took 6.2 minutes earlier.
- **Found.** More accepted events are found on M2_aug and CH14 than in v3, and as many on CH15 and M4.
  - Gained: 4 on M2_aug, 2 on CH14, 1 on CH15. Two of the M2_aug gains (22:19 and 525:10) are spans v3 lost to
    "sharp rises only"; they are now found as drops.
  - Lost: 2 on M2_aug, 1 on CH14, 1 on CH15; M4 is unchanged. Where checked, each is a box that moved (for example, an
    8 mV drop whose box now starts just after your span) or a candidate right on 0.50.
- **Hit rate.** It falls a little at ≥ 0.5, for two reasons:
  - The finder proposes every place that meets your rule, including spans you reviewed and rejected. On M2_aug, the
    event-rule-only candidates at ≥ 0.5 land on 73 accepted and 17 rejected spans.
  - On M4, six more candidates land on rejected spans. Most are slow declines with long boxes (1–8 mV over 26
    minutes to 2.5 hours), which easily cover a rejected span.

  At ≥ 0.9 the hit rates are within a point or two of v3, except on M4.
- **Checked against the whole-drop rule (79d0243e).** I re-measured each candidate's own box with the rule. It gives
  the same top and bottom, within 2 s, for 96 % of candidates on M2_aug, 96 % on CH14, 88 % on CH15 and 90 % on M4.
  For comparison: v3 94 / 94 / 87 / 86 %, v2 73 / 64 / 54 / 42 %.

## Still open

1. **Two-phase spikes** in the CH14 trains come out as two events. Each is a sharp 0.26 mV rise, then a 0.41 mV fall
   to below the baseline. The fall is more than 1.25× the rise, so it is not folded in. One event or two?
2. **Some train spikes stay drops.** Their rise is just under the sharpness bar: a 1-sample jump at 2 Hz reads as
   sharpness 7–10. Their falls show without the rise.
3. **Sequences.** On busy channels the 1-hour gap rule chains a whole day into one sequence ("S8 · 1977 drops" on
   CH14). A rule that sees a regular train (a steady pace of similar events) would set the trains apart.
4. **Slow declines.** Your drop rule counts them, for example M2_aug 282:19–282:57 (3.8 mV over 35 minutes), and so
   does the whole-drop rule. Their boxes no longer cover their neighbours, but they are long, and on M4 they are what
   lands on your rejected spans.
5. **Margins between back-to-back events.** A drop's box can still start a few seconds before its top and overlap
   the rise just before it, as in the two-phase spikes.

## In the app (23 Nov, night)

Auto-detect is now a page of the web app. Open a channel in **Explore › Signal** and press **Auto-detect** in its top
bar (route `#/explore/autodetect/<channel id>`). The line-up is the one above.

- **Run.** Leave the stretch boxes empty for the whole channel, or give a stretch as h:mm or hours (for example
  396:00 to 400:00). The page shows an estimate before you press Run: about 20 min for the whole of MJu26a CH14
  (4.6 M samples), about 22 s for four hours. The run is a job with a real progress bar, the stage it is on and the
  time left. Cancel stops it after the stage it is in (about 20–40 s on a whole channel), and nothing is saved. The
  run also shows on the Jobs page, with a link back. The held-out recording is refused, as everywhere. A channel
  sampled faster than 2 Hz gets a note: the rule was tuned at 1–2 Hz, so its 5-sample minimum spans less time there.
- **Look.** It is the same viewer as the HTML pages, drawn on a canvas inside the app:
  - candidates shaded by confidence, ▼ drops and ▲ rises, with the sequences in their own band;
  - zoom with the wheel or a shift-drag, pan by dragging, and an overview with a draggable window;
  - step through with n / p, filter by confidence, type and source, and click a candidate for its detail.
  - A sortable table lists every candidate shown. Earlier runs stay in a menu.
- **Send to Review.** Pick a lowest confidence and drops, rises or both; the sequences can go too.
  - Each candidate becomes a machine detection in a new Review queue, in time order. The queue is named
    "Auto-detect · <file> <channel> · job <n>".
  - Each candidate is asked about on its own. Review folds detections of one run that overlap into a single item,
    one key press for all of them. So a send puts candidates whose boxes overlap in separate runs ("lanes"), for
    example a drop whose box runs into the next rise. Before this fix, 63 of the 222 candidates on CH14 396–400 h
    would have been folded into a neighbour. Now all 222 reach Review, in 3 runs.
  - Each sequence that two or more sent candidates make goes to sequence review.
  - Nothing is sent twice, so a second send adds only what is new.
  - Review holds back a candidate that matches a span you already judged **on the same recording**, and the
    message after a send says how many. It cannot see verdicts given on another copy of the channel.
    - Your MJu26a verdicts are on the 10 Hz copy (CH14 = recording 663), but Auto-detect runs on the 2 Hz copy
      (705). On MJu26a, events you already judged therefore come up again.
    - The Send panel says this, with the number of judged spans it can match.
    - Matching across copies needs the copy mapping, which today lives only in
      `scripts/thesis/accepted_catalogue.py`.
  - Your verdicts stay yours, and the candidates stay the machine's (CLAUDE.md rule 5).
- **Where results live.** Each run's result is three files on disk, never in the database:
  `DATA/derived/autodetect/job_<n>/` holds candidates.csv, sequences.csv and run.json. run.json records:
  - the whole-drop rule's fingerprint;
  - the timings;
  - what was sent.

  A sandbox bridge keeps them in its own runtime folder.
- **The rule it uses.** The app imports the whole-drop rule from the working copy, `Working/interrogation/
  whole_drop.py`; run.json records its sha. Tonight that copy is the same as the committed 79d0243e. The scripts
  above still pin the committed version from git.

**Live since 24 Nov, 09:38**, on your usual bridge (8765):
- I rebuilt the client and restarted the bridge with `.\webui\start.ps1 -Project -NoOpen`. It runs in the Terminal
  panel tab "MycoWave bridge 8765"; Ctrl+C there stops it.
- It was first checked on a sandbox bridge (port 8823) with its own build.
- Nothing is committed.

## The review queue (24 Nov)

These four runs' results became Review queue 57, "Auto-detect · unreviewed drops and rises, 4 channels (24 Nov)".
It holds 5,291 events (4,440 drops, 851 sharp rises) you have not judged on any copy of their channel, with clean
windows, best first, and runs like M4's moved up. What was left out and why, and how "like M4" is measured:
`docs/autodetect/20261124_queue/README.md`. How the app could learn which recordings are copies (a note, not built):
`docs/autodetect/CHANNEL_COPIES.md`.

## Files

- `Working/autodetect/`:
  - `finder.py` (new): the event rule as a finder.
  - `gates.py`: `steady_run`, `significance` and `distinct`.
  - `anchor.py`:
    - `anchor_events` measures both polarities;
    - `fold_returns` and `fold` (`RETURN_TOL` 1.25, `RETURN_GAP` 1.0);
    - `clip_margins`.
  - `pipeline.py`: `drop_rule=` and `use_finder=`.
  - `blend.py`: `event_rule` precision 0.
- `scripts/autodetect/common.py`: `pin_whole_drop` loads the committed rule from git. Set
  `AUTODETECT_WHOLE_DROP_REV=working` to use the working copy.
- Tests: `tests/test_autodetect.py`, 58 tests (62 with the import-boundary test). They pass on the working copy and
  on the committed rule.
- The app (night):
  - `Working/autodetect/`:
    - `r4.py`: R4 inference, the same numbers as `scripts/rq1b_minirocket.py`.
    - `service.py`: set-up, run with progress and cancel, results on disk, the page's payload, and the send to Review.
    - `seed_bank/`: the seed bank, shipped with the code.
  - `webui/server/autodetect_routes.py`: the `/api/autodetect/*` routes.
  - `webui/server/jobs.py`: adds the job kind `autodetect`.
  - `webui/client/src/api/autodetect.ts`.
  - `webui/client/src/explore/`:
    - `AutoDetectPage.tsx`, `AutoDetectViewer.tsx`, `autoDetectModel.ts`, `autodetect.css`;
    - the button in `SignalPage.tsx` and the route in `index.tsx`.
  - Tests:
    - `tests/test_autodetect_service.py` (11, including the lanes);
    - `tests/test_webui_autodetect.py` (4);
    - `tests/test_webui_jobs.py`, whose job-kind list now includes `autodetect`.
  - `webui/client/src/api/jobs.ts`: the Jobs page names the kind and links back to the page.
  - Smoke walk: `webui/smoke_pages/zzzzzzzzzzz_w2_autodetect.json`, three states (the empty page, the Signal button,
    a two-hour run).

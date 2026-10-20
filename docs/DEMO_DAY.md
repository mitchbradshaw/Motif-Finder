# Demo day, 21 October 2026

Two sites run on the day:

- **The talk** runs live on your everyday site, **8765** (the real database, full data). It is described in
  the first half of this file.
- **The examiners' playground** runs on **8800**, on a 4-hour slice of the data. It is described in the
  second half.

## Part 1: the live talk on 8765

### In plain words

Every step of the three walkthroughs was cooked once on 20 October, on the full data, so in the talk
each click reheats a dish that is already made. A chain run is answered from the step cache in about
1 s. A Discovery run, a seed search and a Review queue already exist and only need opening. Nothing in
the talk computes anything heavy.

Everything made for the talk is named "demo ·" so it can be found and removed afterwards (see
*Cleanup*). If the site fails, `docs/demo/UndergroundBrains_backup.pptx` holds a screenshot of every
step, plus R3 and R4, which have no page in the site.

### Before the talk

1. **Main freezes at 09:00 on 21 October.**
   - Overnight fixes may land before then, and 8765 may be restarted onto the newer main with a fresh
     `npm run build` of `webui/client/dist`. WEBSITE CHANGES asks first.
   - After 09:00: no merge, no dist rebuild and no restart of 8765 until the talk is over.
   - A restart keeps the step cache, the runs and the demo artefacts, which all live on disk or in the
     database. It does lose the in-memory warmth, so **if 8765 was restarted, the warm-up below must run
     again after it.**
   - Check the restart time in the [project bridge 8765](#terminal/c1) tab, or
     `curl -s http://127.0.0.1:8765/api/runtime`.
2. **Warm it after the 09:00 freeze**, about 15 minutes before the talk. It takes about 1 minute and
   visits pages only. Re-run it after any later restart:

       cd /c/Users/mmebr/Documents/CNN
       PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/demo_rehearsal.py --url http://127.0.0.1:8765 --allow-project --talk --slow 2

   **If 8765 was restarted since 20 October, also run the three chains once:**

       PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/demo_screenshots.py --url http://127.0.0.1:8765 --out "$TEMP/demo-warm" --only w1
       PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/demo_screenshots.py --url http://127.0.0.1:8765 --out "$TEMP/demo-warm" --only w2-1

   Why: it re-warms the step-cache reads after a restart.
   - The block cost timings, whose first run can stall the site for minutes, are kept on disk in
     `DATA/db/block_calibration.json` and survive a restart. The demo's blocks are timed already.
   - A chain with a block that has never been timed would stall once. The fix is on a branch, so don't
     add new blocks live.
   - The runs this adds are ordinary Analyse run rows.
   - Discovery's scoreboard in "demo · talk" (5 channels, 6 runs) took 3 s cold after the 20 October
     restart, against about 8 min for a 16-channel, 52-run session. The `--talk` warm-up visits it.

   Run the warm-up close to the talk. With RAM tight, Windows pages an idle bridge out of memory: it read
   38 MB at 16:10 on 20 October. The first requests after a quiet spell are then slow while it pages back
   in. Close other heavy programs, and keep the agents' sandbox bridges stopped, during the talk.
3. **Open one browser tab per stop below, in order, before you start.** This is the single best defence
   against the waits that are left. A tab that has already loaded shows instantly; switching tabs costs
   nothing.
4. **Nothing heavy** on the machine during the talk: no smoke walk, no pytest, no HPC import.

### The click script

Times are warm, measured on 20 October with three other agents loading the machine. Expect less on a
quiet machine.

**W1: open a span in Explore, analyse it**

| # | click | what appears | time |
|---|---|---|---|
| 1 | Explore › Corpus › M2_aug_concat_fs1 › CH4_A2 › *Open* | Signal, 0–721 h | 2–5 s |
| 2 | *Annotations* (drawer) › *clear* the filters › id **12640** › click the row › *collapse* | the saved span "demo · W1/W2 span" (377–381 h) as the motif | 1 s |
| 3 | *Send motif to Analyse* | Analyse, source "CH4_A2 · 377.00–381.00 h" | 1 s |
| 4 | *Import* › `spike_event_features` › *Run chain* | invert → detrend → encoding → drop detection → event shape → **intervals**: 9 spikes and their inter-spike intervals | 1–2 s (cache) |
| 5 | *Import* › `cwt_events` › *Run chain* | wavelet route: CWT ridges → event shape → intervals, 11 events | about 1 s (cache) |

- **Recovery:** Analyse › *History* reopens any of these runs.
- **Report:** reports exist for Discovery runs, not Analyse chains. W1's report is the W2 report below.

**W2: build a detector, save it, apply it, judge it**

| # | click | what appears | time |
|---|---|---|---|
| 1 | still on the W1 source: *Import* › `drop_detection_v1` (or add Baseline removal → Symbolic encoding → Drop detection by hand) › *Run chain* | 6 drops | about 1 s |
| 2 | *Save template* | it already exists as **demo · drop detector** (template 75); say so and show it in Library › Templates rather than saving a second | 1.5 s |
| 3 | Discovery › Runs (session **demo · talk**: M2_aug, 5 channels, 0–721 h) | run **demo · drop detector**: 365 found on 5 channels, 20-draw null | 2 s |
| 4 | that run's *Report* | the detection map against the human reference and its null | **5–7 s live**; instant as the saved snapshot in Reports |
| 5 | *Send unjudged to Review* (already done) › Review › queue **30** "Discovery · demo · drop detector" | one detection at a time | 2–3 s |

If you apply the template live instead, it takes about **2.5 min** on 5 channels × 721 h (the page
estimates 31 s). Do not.

**W3: a Library family to new instances**

| # | click | what appears | time |
|---|---|---|---|
| 1 | Library › Atlas › group *by shape distance* (grouping **g-05**, "shape families") | families | 1.5–2.5 s |
| 1b | *Edit grouping* › *Build the tree* | the Ward dendrogram of all ~3,600 motifs, with the cut line at 0.6 that makes the families; drag the line to show how the families split or merge | about 6 s: it reuses the kept tree `38ca0755`, built on 20 October. **Close without *Apply* or *Save*.** Either one writes a new grouping and renumbers the families |
| 2 | family **F-30** (`#/library/family/F-30?grouping=g-05`) | 79 members, all judged; medoid m-191 on CH2_A1 at 442 h | about 1 s warm, 13 s cold |
| 3 | *Seed search in Discovery* | opens on the kept run **seed 056a5d** (step 4): the same search returns the same run | 2 s |
| 4 | step 2/3 | 1000 matches, the null's recommended cut, 155 kept | instant |
| 5 | Review › queue **31** "demo · talk · picked from Discovery" | the matches | 2–3 s |

- **Check the scope chip says "5 channels · 0–721 h" before step 3.** If it does not, the search is a new
  one on a different scope.
  - On 20 October at 22:37 the "demo · talk" scope was changed to 3 channels and 0–174 h, so the walk
    found 49 matches instead of 155. It was set back at 23:10.
  - To set it back by hand: Discovery › Runs › Scope, channels CH3_A2, CH4_A2, CH6_B1, CH7_B2, CH8_B2,
    section 0–721 h.
- **Do not press *Run with the rigorous null*.** It is about 14.5 h and goes to the cluster.
- **On main 3d4bef1 or later, do not use Cross-channel's *Apply template* link on M2_aug before the
  talk.** It writes the scope of the newest M2_aug session, which is "demo · talk".
- A fresh preview of F-30 over the full data took 1.6 min on 20 October (estimated 13 min).

**Results**

| | where | time |
|---|---|---|
| R1 | Discovery › Map (all datasets), then click a dataset | 1–1.5 s; a dataset 2–5 s (M2_aug the slowest) |
| R2 | Discovery › Runs in **demo · talk**: `dip_search_allch`, `trough_search`, `seed aba099` and `seed bdd3d0` were *adopted* from your M2_aug session (read, not copied). Their *Report*s, or the snapshots in Reports | report 5–7 s; snapshot instant |
| R3 | backup deck only: queue 25's estimate. About 24.6 % of unjudged candidates are interesting (CI 21–28 %), and the rate rises with detector agreement | — |
| R4 | backup deck only: MiniRocket AUC 0.79 against 0.83 for the agreement count | — |

### Steps still over 2 s, and what to do

| step | warm | cause | workaround today | fix after the talk |
|---|---|---|---|---|
| Explore › Corpus | 5 s | the corpus page reads every recording | pre-opened tab | a cached corpus read |
| A run's Report | 5–7 s | matplotlib draws it on every visit | open the saved snapshot from Reports, or a pre-opened tab | cache the rendered report per run |
| Every Review page, and the "need you" chip | 2–3 s | `GET /api/review/queues` and `/counts` count about 5,000 unjudged items | pre-opened tabs | cache the counts |
| Discovery › Runs, Seed | about 2 s | the same counts, plus `/api/discovery/templates` | pre-opened tabs | — |
| Map, M2_aug dataset | 3–5 s | 16 channels × about 60 algorithms | pre-opened tab | — |
| Library family, first visit | 13 s | cold read | the warm-up visits it | — |

### Cleanup after 21 October

Everything below was made on 2026-10-20 between 04:14 and 05:00 UTC on the real database:

- **Discovery session 9 "demo · talk"**, with its runs `demo · drop detector` (310), `seed 056a5d`
  (311), and the four adopted R2 rows. Adoption does not touch session 2.
  - While session 9 exists, switching Discovery to M2_aug opens it rather than your
    "M2_aug_concat_fs1 screen" (session 2). History › *Open* adopts a run into it; deleting session 9
    restores the old behaviour.
- **Template 75** "demo · drop detector".
- **Review queues 29** (Explore spans, holding the demo span), **30** and **31**.
- **Annotation 12640**, the seed span "demo · W1/W2 span".
- **Run rows 7177–7298**: Analyse chain runs on the span, and the two Discovery runs with their null
  fan-out. Three of these (7291–7293) ran on 276.4–278.4 h by a scripting mistake. They are harmless but
  belong to no step.
- **Report snapshots** under `DATA/derived/reports/detection-run/` (demo · drop detector, seed_056a5d,
  dip_search_allch, seed_bdd3d0).
- **Also on 20 October:** the restart of 8765 at 14:14 local killed run **d-309** `cnn_gadf_1min` in session
  LM_fs2_rq4, which was still running. Its finished channels are kept, and *run it again* finishes the rest.

# Part 2: the examiners' playground on 8800

## In plain words

The examiners get their own copy of the website, running on a small slice of the data: 4 hours of 5
channels of M2_aug, instead of 721 hours of everything. Think of it as a test kitchen next to the real one.
They can cook whatever they like, every dish is ready in seconds, and nothing they do touches the real
pantry. Every page in that copy loads in about a second, even on the first visit. The slowest thing an
examiner can do is a seed-search preview, at about 30 seconds.

The copy is a separate folder, `C:\Users\mmebr\Documents\CNN-demo`. It is a plain export of `main`, not a
git worktree and not a junction, so deleting it can never reach the real `DATA/`. It holds its own
`DATA/`, written by `scripts/build_demo_data.py`. The bridge runs in sandbox mode, so even the demo
database is only ever copied, never written.

## Checklist for tomorrow

Already done on 2026-10-20: `CNN-demo` exported from `main` at ff02112, its `DATA/` built, a default
grouping saved, and the demo client built to `CNN-demo\webui\client\dist-demo`.

1. **Nothing heavy on the machine** in the hour before the session: no full smoke walk, no `pytest`, no
   seed-search job on the project bridge. Leave the project bridge on 8765 running; it is a separate
   process.
2. **Start the demo bridge** in a PowerShell window you leave open:

       cd C:\Users\mmebr\Documents\CNN-demo
       C:\Users\mmebr\Documents\CNN\webui\.venv\Scripts\python.exe webui\run_server.py --sandbox --port 8800 --dist webui\client\dist-demo

   Wait for `Uvicorn running on http://127.0.0.1:8800`.
3. **Warm it** from Git Bash. This takes about 30 s and prints any page over 1.5 s:

       cd /c/Users/mmebr/Documents/CNN
       PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/demo_rehearsal.py --url http://127.0.0.1:8800 --slow 1.5

   Then do one seed-search preview by hand: Library › Atlas › F-01 › *Seed search in Discovery* ›
   *Run preview*. It takes about 30 s, the slowest step there is.
4. **Check the browser** at <http://127.0.0.1:8800>:
   - The header banner says SANDBOX.
   - Settings › Datasets lists only *M2_aug · hours 377-381 (demo)*.
   - Explore › Signal has no *Cross-channel* switch.
5. **Do not restart the bridge** once it is warm. A restart throws away everything examiners did, which
   is the way to reset between examiners if you want one. The pages are fast even cold, so a restart
   costs about 10 s plus the warm-up.

The bridge listens on 127.0.0.1, so it can only be reached from this machine. If examiners will use
their own laptops, that needs `--host 0.0.0.0` and a firewall rule: decide that before the session, not
during it.

### Rebuilding the copy (only if something goes wrong)

    cp -r /c/Users/mmebr/Documents/CNN-demo/webui/client/dist-demo /c/Users/mmebr/Documents/dist-demo-keep
    rm -r /c/Users/mmebr/Documents/CNN-demo && mkdir /c/Users/mmebr/Documents/CNN-demo
    git -C /c/Users/mmebr/Documents/CNN archive main | tar -x -C /c/Users/mmebr/Documents/CNN-demo
    "/c/ProgramData/anaconda3/python.exe" scripts/build_demo_data.py --root C:/Users/mmebr/Documents/CNN --out C:/Users/mmebr/Documents/CNN-demo
    cp -r /c/Users/mmebr/Documents/dist-demo-keep /c/Users/mmebr/Documents/CNN-demo/webui/client/dist-demo

The demo client build is kept aside and copied back because its flag (`npm run build:demo`, below) lives on
branch `claude/eager-khorana-7c8811`, not on main.

The rebuilt database has no Library families until a grouping is saved: Library › Edit grouping ›
compute › save, on a `--project` bridge started in `CNN-demo`. A sandbox would throw the grouping away.
Close that bridge cleanly afterwards, because the sandbox copies the main database file and not its WAL.

## What is in the demo data

| | |
|---|---|
| Recording | `M2_aug_demo_377-381h.mat`, shown as *M2_aug · hours 377-381 (demo)* |
| Window | hours 377 to 381 of M2_aug, the busiest four hours for catalogue motifs |
| Channels | 2, 3, 5, 6 and 7, labelled CH3, CH4, CH6, CH7 and CH8 in the UI as on M2_aug; recording ids 1001 to 1005 |
| Library | 151 entries with their members; one grouping, *motifs · shape-distance (demo)*, Ward with default settings: 7 families, 107 members, 44 left out as too small |
| Annotations | the 33 that fall inside the window |
| Seed catalogue | the 84 drop-motif events inside the window, re-indexed onto the slice |
| Empty | runs, review queues, templates beyond the 31 built-ins, models |

Every sample index is shifted to the slice, and every recording id starts at 1001. An id that reached
the demo from the real database cannot name a demo channel, so it fails as "no recording" instead of
reading the wrong one. That failure mode was real before the renumbering: the seed page asked the real
seed catalogue for recording 3, which in the first demo database was a different channel.

## Rehearsal, 2026-10-20 (demo bridge on 8800, fresh sandbox)

All pages, measured by `scripts/demo_rehearsal.py` on a cold start:

| page | cold | warm |
|---|---|---|
| Explore › Corpus | 1.1 s (4.7 s on the very first start) | 0.4 s |
| Explore › Signal, each channel | 0.6–0.7 s | 0.5 s |
| Analyse, Discovery, Library, Review, Jobs, Reports, Settings | 0.3–0.9 s | 0.3–0.5 s |

The workflows, by hand in the browser:

| step | time |
|---|---|
| W1: Signal › *Open in Analyse* › example chain (baseline removal, matrix profile, threshold) › *Run chain* | about 2 s; 34 spans |
| W2: Discovery › *Apply template* › `drop_detection_v1` on 3 channels (20-draw null) | about 12 s; 7 found |
| W3: Library family F-01 › *Seed search* › *Run preview* (200-draw null, 3 channels) | **about 28 s**; the page estimated 67 s |
| W3: *Use these as detections* › *Send unjudged to Review* › open the queue | under 3 s each; 28 events in the queue |

### Slow steps and what to do about them

- **The seed-search preview (about 28 s)** is the one wait an examiner will notice. Run it once during
  the warm-up (step 3). If an examiner runs it live, say it takes about 30 seconds because it compares
  the shape against 200 random versions of the signal, which is what makes a match meaningful. Its
  printed estimate of 67 s overstates the wait; that is worth knowing in advance rather than explaining
  live.
- **Discovery's scope opens on 3 of the 5 channels** (CH3, CH4, CH6). That is not slow, but an examiner
  may ask why. `+ channel` adds the others, and the preview time grows with them.
- **Not measured**: saving a chain as a template from Analyse (W2's middle step), and the report step of
  W1. Both are quick writes in normal use; walk them once by hand tomorrow before the session.

## The client flag (`npm run build:demo`, branch claude/eager-khorana-7c8811 only)

- **What it does:** `vite build --mode demo` writes `webui/client/dist-demo/`. A demo-only Vite plugin
  hides the Signal/Cross-channel switch and Corpus's *Cross-channel from …* button, and sends a typed
  `#/explore/cross-channel/<id>` link to `#/explore/signal/<id>` before the app sees it.
- **Normal build unchanged:** nothing under `src/` changed, so `npm run build` is byte-for-byte what it
  was. Checked with an empty `diff -r` of `dist/` before and after.
- **Gate:**
  - `npx tsc -b` passes, both builds succeed, and `tests/test_import_boundaries.py` passes.
  - Smoke `--only explore` was run on the demo build against a sandbox of the real database (port 8823).
    - Every Cross-channel state fails, by design: the page is redirected.
    - The two `--held-out` states fail as they do on the final database.
    - `explore.signal--default` failed: `signal-span` and `no-motif` were missing on the first Signal load
      of a fresh sandbox. The demo build serves the same app code as the normal one, so this is a load
      flake or a baseline gap, not the flag. Re-check it in tonight's walk.

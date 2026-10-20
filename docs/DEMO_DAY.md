# Demo day, 21 October 2026: the examiners' copy of the tool

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

    rm -r /c/Users/mmebr/Documents/CNN-demo && mkdir /c/Users/mmebr/Documents/CNN-demo
    git -C /c/Users/mmebr/Documents/CNN archive main | tar -x -C /c/Users/mmebr/Documents/CNN-demo
    "/c/ProgramData/anaconda3/python.exe" scripts/build_demo_data.py --root C:/Users/mmebr/Documents/CNN --out C:/Users/mmebr/Documents/CNN-demo
    cd webui/client && npm run build:demo && cp -r dist-demo /c/Users/mmebr/Documents/CNN-demo/webui/client/

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

## The client flag (`npm run build:demo`)

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

# Night pass C — polish and load, site-wide (2026-10-19 → 20)

Branch `worktree-agent-af7422a3b2e498014`, base `7d2d695`. Agent C. Port 8769, sandbox bridge on the full scale
fixture (`tests/perf_fixture.py`: 16 channels × 721 h, 60 Discovery runs, 5,001,200 detections, a 9,743-event
review queue). Edited only `kit/`, `shell/`, `theme.css`, `tests/` and `scripts/night/`.

## In plain words

Think of the app as a building: tonight I checked the corridors and the doors (the header, the frame every page
sits in, the shared parts kit), and walked into every room to note what is slow or crooked — but the rooms
themselves belong to agents A and B, so for those I wrote down the fix instead of making it.

- **Fixed (the frame):** on a 1024-px-wide window the whole app used to slide sideways (it insisted on 1200 px);
  it now fits. The header's search box no longer breaks onto two lines and the page titles no longer wrap and
  jolt the page. The "N need you" counter asked the server the same 2.5-second question several times per page
  and flashed "0" each time; it now asks once and remembers. The parts-kit showcase no longer ships inside every
  page's first download (−31 kB). Keyboard-key badges no longer get squeezed so their text spills out.
- **The three worst things I could not fix (they belong to A and B):**
  1. **Explore › Signal never shows its middle tier for 30+ seconds** on a busy channel (310 k detections): it
     waits for every span on the whole 721-hour channel (a 150-second read on the bridge) before drawing anything
     below the overview.
  2. **Opening a Review queue takes 7–17 s**: the page downloads all 9,743 rows (7 MB) before showing the first
     candidate.
  3. **Discovery's run list is unreadable once a session has more than ~15 runs**: the rows are squashed to 18 px
     tall, the names are cut in half and the Report buttons sit on top of them. A one-line CSS fix (below).

## Assumed

- **Body min-width 1200 → 1024 px.** The brief asks for 1024×700; at 1200 every route scrolled sideways as a whole
  (nav rail and header too). I walked the 1024 build before committing: no route scrolls the document sideways;
  three page toolbars clip their last item (reported below to their owners). I did not remove the floor entirely
  (below 1024 the pages were never designed).
- **The global search pill stays** although it is wired only on Settings (everywhere else a click says "not wired
  yet"). Removing it is a behaviour change; I folded its label to an icon + `Ctrl K` under 1240 px so it stops
  costing 280 px. Reported as a finding.
- **The need-you count is refreshed at most every 15 s** across headers (it was "on every header mount"). In-app
  navigation therefore shows the last count at once; a verdict's effect on the count shows on the next page
  visited after 15 s. `api/needYou.ts` (`useReviewNeedYou`) is untouched; the header now reads
  `shell/needYouShared.ts`.
- **Timings are upper bounds.** The machine ran at 100 % CPU all night (other sessions; 2.3 GB free RAM). I give
  the bridge's numbers, an in-process number for the slow reads (`scripts/night/profile_routes_c.py`), and the
  structural fact (bytes, request count, what waits on what), which does not depend on load.
- Walk 1 (the `7d2d695` build) was perturbed by a long whole-channel span read I issued myself with curl while it
  ran (minutes 5–12); walk 2 (this branch's build, fresh bridge, the two heavy Explore pages walked last) is the
  table of record.

## What I drove (re-runnable against the real database)

- `scripts/night/walk_c.py --url http://127.0.0.1:<sandbox port> --out <dir> [--vp 1440x900,1024x700] [--only …] [--quick]`
  — every route of `App.tsx` and each workspace `index.tsx` (56 pages incl. the add-block pop-up, 16 settings pages,
  the kit) plus 23 bad-id routes. Per route and viewport: time to the main card, time until no skeleton is left,
  `/api` requests in 10 s (and 5–10 s, the polling signal), console errors/warnings, page errors, failed and ≥ 400
  responses, layout shifts after first paint (PerformanceObserver with their source nodes), visible ⚠ icons and
  characters, grey caption nodes in `.main`, enabled grey-filled buttons, text that spills its box, document /
  main sideways scroll, tables with no rows, and the red card / empty state a bad id gets. Screenshots
  `<out>/shots/<vp>/<slug>.png` and `_t1.png` one second later. It refuses ports 8765/8766 and never clicks a write.
- `scripts/night/time_routes_c.py` — the busiest pages' first-paint reads one at a time on the bridge.
- `scripts/night/profile_routes_c.py <db>` — the same reads in process (TestClient), cold and warm.
- Evidence left under `webui/runtime/night/` (gitignored): `walk1/`, `walk2_1440/`, `walk2_1024/`,
  `walk_mw1024/` (the min-width trial), `routes_quiet.txt`, `discovery_runs_fixed.png`, `signal_painted.png`.

## What I fixed (my files)

| # | Finding | Fix | Commits |
|---|---|---|---|
| 1 | At 1024×700 every route's document was 1200 px wide: the whole app scrolled sideways, need-you / held-out chips and every page's right edge off screen | `theme.css` body `min-width: 1024px` | 217aaf9 red · 8437e64 |
| 2 | Header search pill wrapped onto two lines in Review, Discovery, Jobs, Interrogation headers at 1440 (`.hdr-right` shrank) | `.hdr-right { flex: none }`, pill `nowrap`, its label hidden under 1240 px | 495522b red · 3a1c80b |
| 3 | Header page titles wrapped ("All / jobs", "Library / family"): `.hdr-left` grew 10 px after first paint on Jobs (a layout shift) | `.hdr-ws`/`.hdr-page` nowrap, `.hdr-sub` `min-width: 0` (it already ellipsises) | bce3552 red · 1ed54bf |
| 4 | Header read `/api/review/counts` (2.5–4.7 s at scale) on every mount — 2–4 times per page in 10 s; chip flashed "0 need you" grey on remount | `shell/sharedRead.ts` (pure, Node-tested) + `shell/needYouShared.ts`: one in-flight read, 15 s ttl, last answer kept, failure logged and the last value kept | 495522b red · 3a1c80b |
| 5 | `kit/index.ts` re-exported `KitGallery`, so the gallery and the fixture canon shipped in the entry chunk (vite: INEFFECTIVE_DYNAMIC_IMPORT) | barrel export removed (App.tsx already lazy-loads it): entry 472.7 → 441.9 kB (148.5 → 138.4 kB gz) | 495522b red · 3a1c80b |
| 6 | `.k-kbd` shrank in flex rows ("Ctrl Z" 34 px in a 30 px cap) | `.k-kbd { flex: none }` | e68ecb2 red · c36bec6 |

Measured after (walk 2 vs walk 1, 1440): `/api/review/counts` 1 request per page (was 2–4); no header wraps in any
screenshot; at 1024 no route scrolls sideways (walk 1: all 78 did, 1200 > 1024).

## Findings — reported, not fixed (ranked by how often the researcher's path crosses the page)

Severity: **H** = blocks or misleads on the main path · **M** = slows or confuses · **L** = cosmetic.

| Page | Finding | Sev | One-line fix | File |
|---|---|---|---|---|
| Review › Inspector | Queue open = all 9,743 rows in one read: `GET /api/review/queues/1?thumbs=0` 7.0 MB, 8.8–12.5 s cold / 2.4 s warm in process, 7–17 s to the inspector on the bridge | H | serve the rows in pages around the current unit (or a slim row: drop `member_spans`, `memberBands`, `prior_*`, `carried_from_detection` until a row is opened) | `webui/server/review.py:771` `get_queue`; `review/index.tsx` `QueueRoute` |
| Review › Inspector | `GET /api/review/queues` is 78 kB for one queue: every queue carries `filters.detection_ids` (9,743 ids); 1.3 s in process, 9.7 s on the bridge; the landing waits for it before it can redirect | M | strip `detection_ids` from the list route (send its length) | `webui/server/review.py:742` |
| Review › Inspector | A bad queue id waits 5–14 s (behind the queue list) and then shows a red card flush to the window edges (no page padding) | M | render the error inside the page padding; decide "unknown queue" from the single-queue 404 without waiting for the list | `review/index.tsx` (`queues.error` / `QueueRoute`) |
| Review › Inspector | At 1024: the toolbar does not wrap — the queue picker collapses under "machine opinion visible", Shortcuts clipped; main 965 > 960 | M | `.rv-toolbar { flex-wrap: wrap; height: auto; min-height: 54px }` | `review/review.css:14` |
| Review › Inspector | Verdict cards and class buttons are light-grey filled while enabled (12 per page) — they read like disabled controls | L | white card with a coloured key cap, the fill only on hover/selected | `review/review.css` (`.rv-vcard`, `.rv-class`) |
| Discovery › Runs (also Compare, Seed) | **Run rows squashed to 18 px** with 60 runs: names cut, Report over the name. `.dsc-runs-list` is a flex column with `max-height: 600px`; `.dsc-run` (overflow hidden) shrinks. Verified by injecting the fix: heights 18 → 62/130 px | H | `.dsc-run { flex: none; }` — and put the Report button on the row's second line (with the fix it still squeezes the text column, "16 of 16 ch" wraps per word: see `webui/runtime/night/discovery_runs_fixed.png`) | `discovery/discovery.css:70`, `discovery/chrome.tsx:619` |
| Discovery › Runs | 4.8–12 s to the runs card: `/api/discovery/runs` 4.5 s cold in process (9 s on the bridge), `/templates` 12 s on the bridge (0.17 s in process: queued behind the background scorer / the counts read), `/seeds` 3.2 s, `/history` 3.2 s | M | let the card paint from `/session` + `/runs` and stream templates/seeds/history in after | `discovery/RunsPage.tsx`, `webui/server/discovery.py` |
| Discovery › Runs | Scoreboard is a header row with no body and no empty-state line when no run has verdicts | L | an empty row "no run has a reviewed overlap yet — review a run's detections" | `discovery/Precision.tsx` / scoreboard table |
| Discovery › Runs | At 1024 the toolbar drops the dataset pill to a bare icon and clips Run | L | let the toolbar wrap | `discovery/discovery.css` |
| Discovery › Runs | `?run=<unknown>` shows an amber ⚠ "No run named … Showing scale_00 instead" — correct, but it is an info note, not a warning (polish rule 2) | L | muted ⓘ callout | `discovery/RunsPage.tsx` |
| Explore › Signal | **Tier 2 waits for the whole channel's spans**: `getSignalLive` awaits `/api/channels/4/spans` over 0–721 h (525 kB, 153 s on the bridge) before the span tier / drawer render; a 420 px skeleton until then. Fresh bridge: overview at 10 s, tier 2 at 33.7 s; in the walks never within 20 s | H | read spans for the viewport (`t0/t1` of `vp.view`), paint the tiers from the window read, fetch the drawer's full list lazily when it opens | `webui/client/src/api/explore.ts:97`, `explore/SignalPage.tsx:119,320` |
| Explore › Signal | `GET /api/channels/{id}` 4.6 s in process every time (ribbons over 310 k detections, no cache); 69–89 s on the bridge behind the span read | H | cache `corpus.ribbons` by (recording, detections fingerprint) as the coverage map does | `webui/server/app.py:209`, `webui/server/corpus.py:899` |
| Explore › Signal | The bridge keeps computing an abandoned whole-channel read: every page opened after Signal is timed behind it (Review 32–37 s at 1024 in walk 1) | M | answers the two rows above; else cap the route's span count | `webui/server/app.py` `get_spans` |
| Explore › Cross-channel | Skeleton > 20 s (same span read), and the header shows the **"demo data" chip while loading** a live page (polish rule 5) | M | chip only when the read came back `demo`; same viewport-span fix | `explore/CrossChannelPage.tsx` |
| Explore › Cross-channel | A bad channel id says "No cross-channel view for channel 999999 **in the demo data**" on a live page | L | "no channel 999999 in this project" | `explore/CrossChannelPage.tsx` |
| Explore › Corpus | "computing the map for the first time…" for 5–10 s while every count reads **0** (verdicts 0, runs all · 0, matching 0 spans) — reads as measured zeros | M | "…" (or a skeleton) on counts until the map answers | `explore/CorpusPage.tsx` |
| Explore › Corpus | 16 `/api/channels/<n>/tags` reads on open (one per channel) | L | one batched read | `explore/CorpusPage.tsx` |
| Analyse › Chain | `#/analyse/chain?template=<name>` → `getTemplate(Number(name))` → `GET /api/templates/NaN` → a red toast reading only "422 Unprocessable Content" | M | resolve a non-numeric template by name (or say "no saved template called …") | `analyse/ChainPage.tsx:210` |
| Analyse › Chain | At 1024 the toolbar clips "Save template" and the "no source · send …" chip | L | let the toolbar wrap | `analyse/analyse.css` |
| Analyse › Block | With an empty chain the header reads "02 —" (no block name) above the empty state | L | header page "no stage 02" | `analyse/BlockPage.tsx` |
| Analyse › add-block pop-up | Meets polish rule 6: right panel = name, one-line purpose, signature, parameters; "About this block" closed. No finding | — | — | — |
| Library › Templates | 30 grey caption nodes on the list | L | AP rule: one caption per card | `library/TemplatesPage.tsx` |
| Analyse › Interrogation | `?family=nope` silently opens id001 — no "no family nope" notice | M | an amber/ⓘ callout like Discovery's unknown run | `interrogation/*` |
| Jobs | Layout shift 0.11–0.19 at 1024: "Waiting in review" paints one line ("reading jobs…") then grows by its queue list (behind the 1–10 s `/api/review/queues`) | M | a skeleton of the card's final height | `jobs/*` |
| Settings › Channels & events | Console error on every open: "no registered recording called M2_aug_concat_fs1 · known: npy" — the page defaults `rec` to a fixture name | M | default to the first recording `/api/recordings` serves | `settings/ChannelsEventsPage.tsx:29` |
| Settings › Analysis defaults | Layout shift 0.066 (1440): the cross-channel card shrinks 32 px after first paint | L | skeleton of final height | `settings/*` |
| Settings › Blocks | 206 grey nodes (every table cell `.muted`) | L | grey only for the adapter path column | `settings/*` |
| Settings › About | 7.6 s until its last skeleton goes | L | — (machine facts warm) | `webui/server/registration.py` |
| Analyse › Training 1–5 | 2–3 amber ⚠ per block page, layout shift 0.05–0.11 on block 2 (groups card collapses 561 px after paint) | L | ⚠ only where training is blocked; skeleton height | `training/*` |
| Shell | The global search pill is a dead control everywhere but Settings ("not wired yet") | L | hide it where `onSearch` is absent, or wire a route search | `shell/Header.tsx` (Assumed: kept, folded under 1240 px) |
| Kit | `.k-radio-card` text spills (112 px in 73 px) for a long mono name at 1024 (gallery) | L | `overflow-wrap: anywhere` on the card's title | `kit/kit.css:544` |

### Bad-id routes (what a wrong link shows) — 1440, walk 2

Red card / empty state with a sentence (good): review cluster, review item ("No 99999999 in queue 1"), signal
(404 and NaN), span-edit, block, map, seed, family, library page, grouping, models page, settings page, unknown
workspace. **Silent or wrong:** `analyse/chain?template=<name>` (raw "422" toast), `analyse/interrogation?family=nope`
(opens another family), `analyse/training/block/99` (opens a block, no notice), `discovery/compare?a=nope&b=nope`
(the "pick two runs" empty state, no "run nope not found"), `discovery/nope` (the Runs page, no notice).
Slow: bad review queue 8 s, bad review item 12 s (both behind the queue reads).

## Load times (walk 2, this branch's build, fresh bridge, full scale fixture, machine at 100 % CPU)

Time to the main card (ms) · settled = no skeleton left · `/api` requests in the first 10 s (in the second half).
Walk 1 column = the `7d2d695` build (perturbed, see Assumed). Anything over 2 s is a finding (marked).

| Page | walk 1 main | **walk 2 main** | settled | requests 10 s (late) | 1024 main |
|---|---|---|---|---|---|
| Review landing | 16,746 | **6,713** ✗ | 6,723 | 16 (6) | 7,534 ✗ |
| Review queue | 10,305 | **7,395** ✗ | 7,406 | 17 (11: thumbs/peaks/next item, not a poll) | 13,388 ✗ |
| Discovery › Runs | 4,806 | **5,531** ✗ | 5,555 | 17 (7) | 14,158 ✗ |
| Explore › Signal | > 20,000 | **> 20,000** ✗ (tier 2 at 33.7 s on a fresh bridge) | — | 6 | > 20,000 ✗ |
| Analyse › Chain | 1,436 | 450 | 457 | 7 | 515 |
| Analyse › add-block pop-up | 1,019 | 721 | 735 | 8 | 791 |
| Analyse › Block 0 / 1 / 2 | 504 / – / 1,792 | 456 / empty-chain card / 478 | | 6 | ok |
| Discovery › Seed | 4,836 | **2,503** ✗ | 2,511 | 16 | |
| Discovery › Compare | 4,781 | **3,072** ✗ | 3,097 | 10 | |
| Discovery › Stages | 4,863 | **2,406** ✗ | 2,411 | 9 | |
| Discovery › Map | 573 | 484 | 493 | 5 | |
| Explore › Corpus | 521 | 479 | **5,033** ✗ (map computing) | 24 (17: coverage poll + 16 tag reads) | |
| Explore › Cross-channel | > 20,000 | **> 20,000** ✗ | — | 7 | |
| Library › Recurrence / Atlas / Family / Grouping | 600 / 519 / 546 / 560 | 485 / 562 / 454 / 464 | 1,490 / 772 / 894 / 837 | 15–23 | |
| Library › Import / Window sets / Templates | 511 / 629 / 838 | 475 / 770 / 724 | | 6–10 | |
| Interrogation (3) / Training (6) / Glyphs | 457–613 | 401–770 | | 4–9 | |
| Jobs / Reports | 455 / 987 | 570 / 507 | | 9 / 5 | |
| Models (4) | 448–816 | 499–759 | | 4–6 | |
| Settings (16) | 457–706 | 428–792 | About 7,580 | 5–8 | |

The slow reads, one at a time (`time_routes_c.py` on the bridge, then `profile_routes_c.py` in process, cold/warm):

| Read | bytes | bridge | in process cold / warm |
|---|---|---|---|
| `/api/review/counts` (every header) | 77 | 4.7 s | 3.6 / 0.15 s |
| `/api/review/queues` | 78 kB | 9.7 s | 1.3 / 0.5 s |
| `/api/review/queues/1?thumbs=0` | **7.0 MB** | 9.0 s | **8.8–12.5 / 2.4 s** |
| `/api/review/queues/1/counts` | 83 | 11.9 s | 0.3 / 0.2 s |
| `/api/discovery/runs` | 35 kB | 9.0 s | 4.5–5.2 / 0.9–2.3 s |
| `/api/discovery/templates` | 91 kB | 12.2 s | 0.17 / 0.07 s |
| `/api/channels/4` | 5 kB | 69 s | **4.6–6.9 / 2.8–4.7 s (no cache)** |
| `/api/corpus/…/coverage` | 15 kB | 9.9 s | — |
| `/api/channels/4/spans` (whole channel) | 526 kB | **153.5 s** | — |

The gap between the two columns is the bridge serialising on one process while its background workers (the
template scorer, the corpus-map hand-off, queue peaks) and the walk's own reads run; on the real database's quieter
machine it will be smaller, but the three reads marked bold are slow on their own.

## Tests added

`tests/test_night_c_shell.py` — 13 tests, **conda python** (`/c/ProgramData/anaconda3/python.exe`; the four
shared-read tests run `shell/sharedRead.ts` under Node 25, which strips types natively; they skip without `node`):
the barrel does not re-export the gallery and nothing imports it through the barrel; App lazy-loads it; the
header's right cluster does not shrink, the pill does not wrap, its label folds under ≥ 1200 px; titles nowrap and
the subtitle gives way; the app's min-width ≤ 1024; the kbd does not shrink; the shared read asks once for many
mounts, keeps its answer and refreshes after its ttl, keeps the last value on failure and reports why; the header
reads need-you through it. `tests/test_import_boundaries.py` passes (same interpreter: 17 passed together).

## Gates

- `node …/typescript/bin/tsc -b` from `webui/client`: pass.
- `node …/vite/bin/vite.js build` from `webui/client`: pass (entry 441.9 kB; the INEFFECTIVE_DYNAMIC_IMPORT warning
  for the gallery is gone).
- Smoke: not run (the brief's walk replaces it tonight). The header change keeps every `data-testid`
  (`header-search`, `need-you`, `held-out-chip`, `header-page`, `path-strip`); `need-you` still shows `● N need you`.
  The manager's smoke at 1440 is unaffected by the min-width change (it only bites under 1200 px).

## Open risks

- Pages were laid out against a 1200 px floor. At 1024 the walk found three toolbars that clip their last item;
  between 1024 and 1200 nothing else showed, but a page with a fixed-width grid could still crowd. Revert is one
  line in `theme.css` if the morning walk dislikes it.
- The need-you chip can now be up to 15 s stale after a verdict when moving between pages.

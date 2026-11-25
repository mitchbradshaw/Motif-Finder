# NeurIPS demo site: decisions (2026-11-25)

The researcher set the brief on 2026-11-25. Two grilling rounds followed. Round 1 was answered in full. For round 2,
the researcher wrote "I accept all recs for round 2, I am AFK, continue with the build", so every round-2 line below is
the recommendation, taken as accepted. **Read round 2 first when you are back.** Anything here can be changed in the
morning; the build is designed so that most of these are one config edit.

## The brief (researcher, 2026-11-25)

The demo is a stripped-down MycoWave for the NeurIPS booth (Sydney, 11-12 Dec 2026). It should be simplified, fast
and intuitive, and show the best results:

- It runs on 3-4 hand-picked datasets, or subsets of them.
- Every possible result is pre-cached.
- Only the most revealing blocks and templates are offered, and fewer discovery runs.
- The Library shows the events and sequences of those datasets.
- There are no Models or Jobs pages.
- There is less grey text, and only a few actions, highlighted.
- Auto-detect works in Explore.

A visitor can explore → analyse → build a detector → run it in Discovery → browse the Library → seed search → analyse
the spike events. It has next to no lag and a first-visit tutorial. Several devices can use it at once, each on its own
instance, and nothing can break.

## Round 1 (answered)

| # | Decision |
|---|---|
| Q1 | The three unmerged October feature branches (`claude/interesting-cohen-b11c93` ux-1018 uncut seed import, `mp/backend-alias`, `claude/hungry-jang-18e110` seed-parallel) stay on their branches until after NeurIPS. `claude/peaceful-sutherland-22bdf8` and `rq4/sweep-code` are superseded on main. |
| Q2 | This laptop serves everything offline. Visitors' laptops and tablets join the laptop's own hotspot by QR code. Phones get a "best on a bigger screen" page with a short preview. The design should allow a cloud host later. |
| Q3 | Six private copies ("stations") are started in advance. A copy resets on "Start over" or after 10 minutes without input. A seventh visitor sees a short wait screen. |
| Q4 | Three datasets, each a ~24 h slice × 4 channels, with the windows picked by event density: oyster (M2_aug), lion's mane (MJu26a 2 Hz, CH14 + CH15), split gill (Adamatzky's public *S. commune*). M4 stays out (held out). |
| Q5 | Eight stops: Explore (+ Auto-detect) → Analyse → Build → Discovery → **Judge five** → Library → Seed search → Spike statistics. Removed: Models, Jobs, Reports, Settings, Cross-channel, Map/Compare, Window sets, grouping editor, Import, History. |
| Q6 | A short menu: three slots (Clean → Find events → Describe), with 2-4 choices per slot and knobs as notched sliders. Every combination on every demo channel is computed in advance, and free typing is impossible. |
| Q7 | Seed search uses a shelf of curated seeds searched in advance, plus any span a visitor marks, searched live, provided the live search measures under ~3 s on the slices. |
| Q8 | A new Spike statistics page assembled from views the site already has: rate, intervals (CV, LV), depth × duration, every event overlaid at its own scale (the "icicles"), the steepest-slope rose, the trains. |
| Q9 | A welcome screen, then a guided tour that highlights the next button with a one-line hint. It can be skipped and restarted from "?". |
| Q10 | The MycoWave name. Titles only, an (i) on each chart, one bright primary button per page, and secondary actions recede. |

## Round 2 (recommendations, accepted while AFK)

1. **Windows.** Picked by researcher-accepted events per 24 h (the 9 Nov accepted catalogue, plus queue 37's
   "interesting" verdicts for split gill):
   - Oyster: M2_aug 402-426 h, CH2/CH4/CH6/CH7 (0-based 1, 3, 5, 6), with 68 accepted events (28/19/18/3).
   - Lion's mane: MJu26a 2 Hz 438-462 h, CH5/CH13/CH14/CH15 (0-based 4, 12, 13, 14). This is the densest day of the
     CH14 train, with 185 accepted drops.
   - Split gill: *S. commune* 0-24 h, the four channels with the most verdicts (0-based 0, 3, 5, 6), 309 accepted.
2. **The builder menu.** Clean offers drift removal (rolling-mean window: 5, 20 or 82 min) × look for (drops as
   recorded, or rises by flipping the signal). Find events offers one of the thesis drop detector (segment length
   5/20/98 s × steepness gate 4/8/12 σ), a noise threshold (3/4/6 σ × minimum duration 10/30 s) or wavelet ridges
   (smallest scale 2/10/30 s). Describe always runs event shape + intervals. That gives 6 × 18 = 108 settings per
   channel. No trained-network detector is offered: the models were trained on these recordings, so it would show
   leakage, not skill. Auto-detect, which includes the R4 classifier, appears in Explore and Discovery as a reference.
3. **Discovery** shows the visitor's run on all 12 demo channels next to three runs prepared by the researcher: the
   thesis drop detector at its defaults, the noise threshold at its defaults, and Auto-detect (v4, drops). Each run
   gets a "chance level" from 10 noise copies (surrogates) of every channel, so it reads as "beats chance ×N".
4. **Judge five.** After a Discovery run, the visitor is shown five of their detections, one at a time, each with
   three buttons: "Yes, an event", "No" and "Not sure" (stored as interesting / not_interesting / unsure). A summary
   follows: how many they said yes to, and, where the researcher judged the same event, how often they agreed. The
   verdicts stay in the visitor's private copy.
5. **Library scope.** The researcher-accepted events inside the three slices, grouped into shape families, plus the
   sequences there (the CH14 train). Every Library event opens in Explore. The headline numbers of the whole
   catalogue (2,959 accepted spans, six species) are printed once on the Library's front.
6. **The seed shelf** holds about 9 curated seeds from the slices: the medoids of the biggest shape families of each
   dataset, a CH14 thin drop and a wide drop, and an oyster drop. Each is searched in advance over all 12 channels,
   across species.
7. **The tour story** is led by lion's mane CH14 (the "heartbeat" train):
   - Explore it and Auto-detect its drops.
   - Analyse a span with the thesis drop detector, then change a knob.
   - Run it in Discovery over all three species and judge five.
   - Find the train in the Library.
   - Seed-search a CH14 drop, finding similar drops in oyster and split gill.
   - End on Spike statistics comparing the three species.
8. **Spike statistics** puts the three species side by side, one column each, for every measure. A source switch
   chooses between "your detector", "the researcher's accepted events" and "Auto-detect".
9. **If time runs short, cut in this order:** the phone preview becomes a plain message; then the live seed search
   (keep the shelf); then null draws 10 → 5; then knob notches 3 → 2; then copies 6 → 4. The must-have by morning is
   the eight stops working end to end on three datasets with the tour, private copies and no errors.
10. **Code location.** Branch `demo/neurips`, worktree `C:\Users\mmebr\Documents\CNN-neurips`. The changes are
    additive, so the branch can merge into main after review; it is not merged tonight. The demo's data and caches
    live in the worktree's own `DATA/neurips_demo/`: real files built from the real DATA read-only, never a junction.
    The hub is on port 8900 and the six copies on 8901-8906. The 8765 site and the shared `webui/client/dist` are
    never touched.

## Architecture (how the build meets "instant" and "nothing breaks")

- **Pre-cooked store.** `scripts/neurips_demo/` runs the real core once, overnight, on the slices:
  - every builder setting × channel, with its 10 surrogate draws;
  - the reference runs and Auto-detect (from the 24 Nov drop pool);
  - the seed shelf, the Library, and the statistics.

  It writes compact JSON/NPZ files to `DATA/neurips_demo/store/`. The station server only reads those files, plus the
  slice arrays for the signal view, so almost every request is a file read.
- **Stations.** Each copy is a small FastAPI app (`webui/server/demo_station.py`) on its own port. Its only mutable
  state is one JSON file: the visitor's runs, verdicts and tour progress. A reset deletes that file. Nothing a
  visitor does touches the store or any database.
- **Hub.** `webui/server/demo_hub.py` serves the welcome page and the QR code. It hands a free station to each new
  device (a redirect to that station's port) and polls the stations for idle time, resetting a station after 10 min.
  A station knows its current visitor by a claim token. An old tab on a reassigned station says so and links back to
  the hub.
- **Client.** It is a separate entry in the same Vite project (`webui/client/demo.html`, `src/demo/`), built with
  `--mode neurips` into `dist-neurips/`. It reuses `theme.css` and the kit, so it looks like MycoWave. The normal
  build does not import it.

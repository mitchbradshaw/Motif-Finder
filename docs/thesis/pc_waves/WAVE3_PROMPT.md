# Wave 3: the final site screenshots (run on the PC, Sunday)

## In plain words

This is a camera script for the website. It opens 23 pages of the live site one at a time and photographs one card or
panel on each, the way you would crop a screenshot by hand. Each picture feeds a thesis figure. If a page throws an
error, or the thing it is waiting for never appears, that picture is skipped and named in the log. A bad picture is
never saved.

**Two things it does change** (details in "What the run writes" below):
- the last two shots press **Run chain** in Analyse, so each adds one Analyse run with no detections;
- four Discovery shots set the open recording in the Scope card, the same as picking it by hand. Two of them do
  nothing if M2_aug is already open, one moves to MJu26a, and the last moves back to M2_aug.

**My recommendation:** run all of it. If you want a run that writes nothing, delete the last two entries
(`analyse_symbolic`, `scores_view`) from `wave3_shots.json` first. You then have no Scores view and no symbolic-route
picture.

## README: each shot, its figure, and what to check

Ids marked **`<<CHECK>>`** come from the live database. I could not see them from here, so they are taken from the
round-B reports and `docs/DEMO_DAY.md`.

| # | shot (PNG name) | thesis figure | what it shows | ids to check | confidence |
|---|---|---|---|---|---|
| 1 | `explore_signal` | 4.1 lineage, 4.4 tour | Explore › Signal, M2_aug CH1_A1, 314–318 h (motif 458 is at 316.2 h); every `drop_detection` run's detections drawn (picker "by template") | channel id **1** = CH1_A1 `<<CHECK>>` (the shot checks the name itself and fails if it is wrong) | medium-high |
| 2 | `explore_signal_motif` | optional, 4.1 | the same, with the first motif after 316.1 h opened in the motif tier (the `]` key) | — | medium-low |
| 3 | `discovery_map` | 4.4 tour | Discovery › Map, dataset M2_aug, one cell per channel, rows by most detections | key `M2_aug_concat_fs1` | high |
| 4 | `discovery_compare` | 4.4 tour | Compare › "Where A and B fire" on one channel (CH4_A2): A = **demo · drop detector** (drop_detection_v1 saved as template 75), B = **seed bdd3d0** (the dip seed) | Discovery session 9 "demo · talk" holds both runs `<<CHECK>>` | medium |
| 5 | `discovery_compare_full` | spare | the same comparison, whole right column (what differs, where they fire, overlap, the stepper) | as 4 | medium |
| 6 | `discovery_seed` | 4.4 tour | Seed search, step 3: the F-30 seed (Library entry 191, kept as **seed 056a5d**), the cut histogram and the 155 kept matches | entry **191** `<<CHECK>>`; session 9's scope must still be 5 ch × 0–721 h | medium |
| 7 | `ch7_seed_kept_matches` | 7.2 | the matches card alone from shot 6 | as 6 | medium |
| 8 | `discovery_seed_report` | fallback for 6/7 | Reports › the detection-run report for **seed_bdd3d0** (tall: crop in LaTeX) | run key `seed_bdd3d0` in session 9 `<<CHECK>>` | medium-high |
| 9 | `review_queue` | 4.4 tour; replaces `screens/review_queue.jpg` (`fig:reviewscreen`) | Review, blind queue **25** (M2_aug, finished): one candidate with the verdict keys. It opens the first item in the queue rail, so it shows a judged item | queue **25** `<<CHECK>>` (never 36 = M4, never 37 = *S. commune*) | medium-high |
| 10 | `models_page` | 8.3, 4.4 | Models › Results, paired run **79** (M2_aug forests, arm A), exam (ii) unseen channels | run **79** `<<CHECK>>` | high |
| 11 | `models_b2_blind` | 8.3 spare | Models › Results › B.2 run **1613** against the blind human (queue 3) | run **1613** `<<CHECK>>` | medium-high |
| 12 | `library_grouping` | 4.4 tour | Library › Edit grouping on **g-11**: the Ward tree, its cut at 0.6 and the family cards. It never presses Save or Apply | grouping **g-11**, cut **0.6** `<<CHECK>>` | medium |
| 13 | `library_atlas` | 4.4 tour; replaces `screens/library_atlas.jpg` (`fig:atlasscreen`, which still says g-05) | Library › Atlas, g-11, the whole page (tall: crop in LaTeX) | g-11 | high |
| 14 | `interrogation_event_shape` | 4.4 tour | Interrogation › 02 Aggregate, upstream Event shape, seed family **id385** (lion's mane, 24 drops; FWHM and recovery are measured) | family **id385** `<<CHECK>>` | high |
| 15 | `interrogation_intervals` | 4.4 tour | Interrogation › 02 Aggregate, slope upstream, family **id024** (oyster, M2_aug CH2, 40 drops): depth, inter-event interval and slope | family **id024** `<<CHECK>>` | high |
| 16 | `interrogation_intervals_hist` | spare | the inter-event-interval histogram card alone (id024) | as 15 | high |
| 17 | `template_drop_detection_v1` | 4.3 | Library › Templates rail: stages and locked parameters | name `drop_detection_v1` | high |
| 18 | `template_oasis_deconvolution` | 4.3 | the same for `OASIS_Deconvolution` | name `OASIS_Deconvolution` | high |
| 19 | `template_cnn_fusion3_10min` | 4.3 | the same for the CNN window-score template `cnn_fusion3_10min` | name `cnn_fusion3_10min` | high |
| 20 | `b11_compare_mju26a` | 10 B11 (optional) | switches Discovery to **MJu26a_fs2** (its own session 13, "MJu26a_fs2_rq4"), then compares `drop_detection_v1` with `OASIS_Deconvolution` | both runs whole in session 13 `<<CHECK>>` | medium-low |
| 21 | `zz_discovery_back_on_m2aug` | none: a check | switches Discovery back to M2_aug and photographs the Scope card. It should read 5 channels, 0–721 h | — | medium-high |
| 22 | `analyse_symbolic` | 4.1 lineage, 4.4 | Analyse › Chain: the builtin `dsax_encoding` route (baseline removal, then dSAX letters, 20 s per symbol, alphabet 3) on CH1_A1 314–318 h. **Presses Run chain** | channel id 1 (as 1) | medium-high |
| 23 | `scores_view` | 8.3, 4.1 | Analyse › block 02 "CNN window scores": `cnn_fusion3_10min`'s first two blocks (10-min windows → fusion CNN, `MODELS/fusion_cnn_3.pth`) on CH1_A1 312–320 h. The scores are drawn under the source signal, with their histogram. **Presses Run chain** | model file present `<<CHECK>>` | medium |

Notes on the choices:
- **Compare on M2_aug (4–5).** Session 9 ("demo · talk") is the session M2_aug opens. It does not hold `drop_detection_v1`
  or `OASIS_Deconvolution` runs, so A and B are its own detector and seed runs. That is the pairing the Compare page
  was built for: a template run against a seed run. The detector-against-detector pair is shot 20, on MJu26a,
  where session 13 holds both. To compare them on M2_aug instead, Discovery would have to open session 2, which has
  to be done by hand.
- **Scores view (23)** leaves out the template's Threshold block, so the run writes no detections. The histogram card
  therefore reads "no stage after this one cuts these scores", and no cut line is drawn.
- **No R4 page exists.** R4 (MiniRocket) was trained by script, so the Models workspace has no page for it. Shots 10–11
  are the trained models the site holds. Models › Registry is demo data: never use it.
- **Event shape and Intervals (14–16)** are the Interrogation pages, as in `figures/roundb/b12_ig_*`. They read seed
  families (drops), not a spike train. A spike-train version needs the W1 chain re-run, which writes about 85
  detections, so it is left out.
- **Tall pictures.** The app scrolls inside its own panels, so each tall crop has a tall window instead of 1500×950:
  the map 2400 px, the atlas 4200 px, the report 6000 px. Trim them in LaTeX (`trim`, `clip`) or crop the PNG.

## What the run writes to the real database

- **`analyse_symbolic`, `scores_view`:** each presses Run chain. Each adds one Analyse run row plus its job row, with
  **no detections**: the chains end in an Encoding and in Scores. The runs are on M2_aug CH1_A1 at 314–318 h and
  312–320 h. Analyse › History will list them. Nothing in Discovery, Review or the Library changes.
- **`discovery_compare`, `discovery_compare_full`, `b11_compare_mju26a`, `zz_discovery_back_on_m2aug`:** each sets the
  open recording in the Scope card, exactly as picking it by hand.
  - If Discovery is already on that recording, nothing is written.
  - Otherwise the recording's own session opens as it was left. No channel, section or run is changed.
  - Discovery ends on M2_aug, session 9, where the 5 Nov notes say it is now.
- **`discovery_seed`, `ch7_seed_kept_matches`:** the address names entry 191, so session 9's seed draft is set to that
  seed if it was on another. That is what the Library's *Seed search in Discovery* button does.
- **`library_grouping`:** it only opens the editor. If g-11's tree is not stored, the editor builds it as a preview: a
  job that writes no grouping, only its own job row. Save and Apply are never pressed.
- **Everything else** only reads. No key is pressed in Review, so no verdict can be written.

## The prompt for the local Claude session (paste everything in the box)

```text
Please take the thesis screenshots from my live website. Do exactly these steps in Git Bash, from the repo root
C:\Users\mmebr\Documents\CNN (cd /c/Users/mmebr/Documents/CNN). Do not edit any file, do not install anything, do not
debug or retry. Report at the end.

1. Bring in only this folder (do NOT switch branch, merge, pull, commit or stash):
     git fetch origin claude/hopeful-knuth-kh8u38
     git checkout origin/claude/hopeful-knuth-kh8u38 -- docs/thesis/pc_waves
   If scripts/thesis/site_shots.py does not exist, also run:
     git checkout origin/claude/hopeful-knuth-kh8u38 -- scripts/thesis/site_shots.py

2. Check the bridge on 8765:
     curl -s http://127.0.0.1:8765/api/runtime
   It must answer with "mode": "project". If nothing answers, start it in the background from the repo root:
     powershell.exe -NoProfile -ExecutionPolicy Bypass -File webui/start.ps1 -Project -NoOpen
   Then poll http://127.0.0.1:8765/api/health every 15 s until it says "ok": true (it backs the database up
   first, which can take a few minutes). Never start a second bridge if one already answers.
   If it answers with "mode": "sandbox", STOP and tell me.

3. Check that M4 is locked:
     curl -s http://127.0.0.1:8765/api/held-out
   It must say "locked": true. If not, STOP and tell me.

4. Take the screenshots. This takes 15 to 45 minutes. Run it in the background and wait for it to end; do not start
   it twice:
     mkdir -p docs/thesis/figures/screens_final
     PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/site_shots.py docs/thesis/pc_waves/wave3_shots.json --out docs/thesis/figures/screens_final 2>&1 | tee docs/thesis/figures/screens_final/run.log

5. Zip the folder into parts of at most 24 MB (run.log goes in part 01). Run this block exactly as written, starting
   at the left margin (the EOF line must start the line):

"/c/ProgramData/anaconda3/python.exe" - <<'EOF'
import os, zipfile
d = 'docs/thesis/figures/screens_final'
cap, parts, cur, size = 24 * 1024 * 1024, [], [], 0
for f in sorted(os.listdir(d), key=lambda f: (f != 'run.log', f)):
    n = os.path.getsize(os.path.join(d, f))
    if cur and size + n > cap:
        parts.append(cur); cur, size = [], 0
    cur.append(f); size += n
if cur:
    parts.append(cur)
for i, fs in enumerate(parts, 1):
    out = f'docs/thesis/figures/screens_final_part{i:02d}.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
        for f in fs:
            z.write(os.path.join(d, f), f)
    print('PART:', out, len(fs), 'files')
EOF

6. Report, and nothing else:
   - how many "saved" lines and how many "FAILED" lines are in docs/thesis/figures/screens_final/run.log;
   - every FAILED line, pasted verbatim (grep FAILED docs/thesis/figures/screens_final/run.log);
   - the full paths of the zip parts (the PART: lines).
   Do not commit anything.
```

### Without Claude: one line

With the bridge already running on 8765. In Git Bash:

    cd /c/Users/mmebr/Documents/CNN && git fetch origin claude/hopeful-knuth-kh8u38 && git checkout origin/claude/hopeful-knuth-kh8u38 -- docs/thesis/pc_waves && PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/site_shots.py docs/thesis/pc_waves/wave3_shots.json --out docs/thesis/figures/screens_final

In PowerShell, once the files are there:

    $env:PYTHONIOENCODING = "utf-8"; & "C:\ProgramData\anaconda3\python.exe" scripts\thesis\site_shots.py docs\thesis\pc_waves\wave3_shots.json --out docs\thesis\figures\screens_final

The pictures land in `docs\thesis\figures\screens_final\`. A line starting `FAILED` names a picture that was not
taken, and the reason.

## Your manual checklist (what the script cannot judge)

**Before the run (5 minutes):**
- [ ] The header chip reads **"M4 held out"**, not "M4 unlocked".
- [ ] **Settings › Datasets:** confirm the species column. M2_concat says **oyster**, M2_aug oyster, CO chocolate oyster,
      MJu26a lion's mane.
- [ ] **Discovery › Runs:** the toolbar names **demo · talk**. The Scope card reads M2_aug_concat_fs1.mat, channels
      CH3_A2, CH4_A2, CH6_B1, CH7_B2, CH8_B2, section 0–721 h.
  - If the channels or section differ, shots 6–8 will fail or show another search. Set them back in the Scope card
    first (`docs/DEMO_DAY.md`, W3 notes).
  - If another recording is open, do nothing: shot 4 switches it.
- [ ] **Optional:** open `#/discovery/seed?entry=191`. If the step strip says "1000 matches · 5-draw null" and
      "155 kept", shots 6–7 will work. If it says "not run yet", the stored preview is gone. Shots 6–7 will then fail
      and shot 8 is the fallback. A fresh preview took 1.6 min on 20 Oct; whether to run it is your call.
- [ ] **No *S. commune* step is needed.** No shot opens an all-recordings view, so leave *S. commune* registered.
      Unregistering it in Settings › Datasets would set its rows inactive while queue 37 is still unscored.

**After the run:**
- [ ] Look at every PNG for the words *Schizophyllum*, *commune* or *M4*. None should appear. Drop any picture where
      one does.
- [ ] `review_queue.png` shows queue 25 in its toolbar chip and an M2_aug item.
- [ ] `zz_discovery_back_on_m2aug.png` shows M2_aug, 5 channels, 0–721 h. If it failed, open Discovery and check by
      hand.
- [ ] `analyse_symbolic` and `scores_view` are only valid if `explore_signal` was saved. That shot proves channel 1 is
      CH1_A1, and the two Analyse shots trust the same id.
- [ ] Crop the tall PNGs (`library_atlas`, `discovery_seed_report`, `discovery_map`) to the part the figure needs.
- [ ] Light theme: nothing to do. Dark is not drawn, and every shot is light.

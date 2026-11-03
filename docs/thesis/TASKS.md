# Your outstanding tasks (as of Thu 29 Oct 2026)

**Dates:** experiments freeze **Tue 3 Nov** · full draft **Thu 5 Nov** · thesis due **Mon 9 Nov, 3 pm**.

Everything in sections 1–6 is yours; tick the boxes as you go. Section 7 lists what I am doing and which of your steps
each part waits on. Commands are for Git Bash in `C:\Users\mmebr\Documents\CNN`, except where a line says *rangpur*.
Queue counts were read from the database this morning (own looks only).

---

## 1. First: start the 8765 bridge

The bridge was not running this morning. Its log ends without an error, so the PC most likely restarted overnight.
Review, the imports and every page need it.

- [x] In PowerShell, from the repo root: `webui\start.ps1 -Project`. Project mode uses the real database, and the
      script builds the client only if none exists. Or ask me to start it. *(3 Nov: down after the PC restarted; I
      started it at 14:04, logs `webui/runtime/bridge-8765-20261103-140441.*.log`.)*
- [ ] Wait about two minutes for the warm-up (the log says "template scores warmed").

---

## 2. Queues to judge

In plain words: these are the blind piles of events that only you can sort. Each takes about 15 minutes at 3–4 seconds an item.

| Order | Queue | Left | What it answers | Score it afterwards with |
|---|---|---|---|---|
| 1 | **35** RQ2 blind panel | 249 of 249 | RQ2: do Library seeds find real motifs, against duration-matched controls? | `"/c/ProgramData/anaconda3/python.exe" scripts/rq2_blind.py score --real --key DATA/derived/rq2_blind/20261026-rq2blind/key.json` |
| 2 | **36** M4 held-out exam | 290 of 290 | RQ3: does the frozen classifier work on a recording it has never seen? | `"/c/ProgramData/anaconda3/python.exe" scripts/m4_exam_score.py --real` |
| 3 | **37** *S. commune* exam | 263 of 263 | RQ3 again: does it work on a second unseen recording, from another lab? | I run it once, when you say it's done (README step 6) |

**Done 28 Oct:** queues 35 and 36 judged and scored. RQ2 is answered blind, and the M4 exam gives MiniRocket an AUC
of 0.98 and a balanced accuracy of 0.93 (Chapters 7 and 8).

- [ ] **Queue 37, the *S. commune* exam (drawn 29 Oct).** It is 263 items, not 290, because two detector families
      found only 1 and 2 events there. *S. commune* is not held out, so there is no lock to switch: keeping the exam
      blind is up to you.
  1. In Review, open **only** queue 37.
  2. Open no Discovery Map, Library page or other queue that shows *S. commune* until it is done. Its runs are in the
     database now, so they would show there.
  3. Judge all 263, then tell me. The score runs once, and it refuses any verdict older than the freeze.

- [x] **Queue 35 first, before any other seed queue.** Seeing seed matches first would break its blindness.
- [x] **Queue 36, step by step:**
  1. In Settings › Datasets › *Held-out recording*, switch the lock off (it asks you to type the name).
  2. In Review, open **only** queue 36. Open no Discovery Map, Library page or other queue while M4 is visible.
  3. Judge all 290.
  4. Switch the lock back on.
  5. Run the score.

  The fair CNN is not part of this exam (Round 5 Q3), so nothing here waits on the cluster.
- [ ] *Optional, 2–3 minutes in all:*
  - queue 25 has 1 item left, and queue 28 has 3;
  - queue 7 (the long-dip census) has 11 left. Finishing it completes that census, from 104 to 115 of 115.

**Coming later.** I create these; each is about 15 minutes of judging:
- [x] The *S. commune* exam queue: it is queue 37, above.
- [ ] The 2 Hz blind sample of MJu26a, SH and SO, after their sweep is imported (§3d). It feeds **g-12**, the grouping
      frozen for Chapters 9 and 10 (Round 5 Q4).
- [ ] B4's artifact queue, only if the cross-channel build reaches its slice S5 (§5).

**Not needed for the thesis** (leave them unless you want them):

| Queue | Items left |
|---|---|
| 24 seed_bdd3d0 | 3,139 |
| 23 deconvolved_troughs #1896 | 1,320 |
| 30 and 31, the demo queues | 365 and 155 |
| 21 noise_threshold #1888 | 147 |
| 2 drop v1 on recording 385 (inactive) | 110 |
| 32 drop v1 #7299 | 29 |
| 20 | 10 |
| 4, 5, 10 and 12 | 1–2 each |

Queues 1, 3 and 29 hold sequences, test windows and Explore spans; their counts need the bridge, so check them in
Review.

---

## 3. Cluster jobs (rangpur)

In plain words: four bundles were built. (a) and (b) are done: home and imported on 29 Oct. They share the 30 GB quota,
so bring each big one home, and clean up, before starting the next big one. Clear (a)'s and (b)'s folders on rangpur
first; (b)'s `cache/` alone is about 1.4 GB.

**Recommended order:**
1. ~~(a) and (b) together, now.~~ Done.
2. (d) next: g-12 and four round-B questions wait on it.
3. (c) last.

| | Bundle | Size of the run | Comes back | Full steps |
|---|---|---|---|---|
| a | *S. commune* sweep, the second unseen recording | 296 tasks; 1–3 CPU core-hours, at most 1 A100-hour; about 30–40 min wall | 0.2–0.8 GB | `docs/thesis/hpc/rq4_scommune_20261026/README.md` |
| b | Fair CNN against MiniRocket (RQ1b) | 18 training tasks; about 1.6 GPU-hours | small (`out/` only) | `DATA/derived/hpc/rq1b_cnn_loro_20261026/README.txt` |
| c | 20-draw surrogate re-runs on M2_aug | 96 tasks; 5–18 CPU core-hours plus 1–3 GPU-hours | 10–30 GB | below (no README) |
| d | MJu26a, SH and SO at 2 Hz | 1,014 tasks; 40–60 CPU core-hours, 12–16 A100-hours; 5–8 h wall | about 10 GB (up to about 35) | `docs/thesis/hpc/rq4_newsets_20261027/README.md` |

### (a) *S. commune* — done (home and imported 29 Oct)
- [x] Copy:
  `scp DATA/derived/hpc/rq4_scommune_20261026/rq4_scommune_upload.tar.gz s4699158@rangpur.compute.eait.uq.edu.au:~/`
- [x] *rangpur*, in `~/CNN`:
  1. `sha256sum ~/rq4_scommune_upload.tar.gz` should print `7128fe033eecd38b78431820a1bd4d84199ace388ab605b88582e7ac53d15e4f`;
  2. `tar xzf ~/rq4_scommune_upload.tar.gz`;
  3. the environment checks in README step 2;
  4. `quota -s`.
- [x] Submit: `bash docs/thesis/hpc/rq4_scommune_20261026/submit_rq4s.sh`
- [x] Bring it back and import. The archive came home on 29 Oct (296 of 296 tasks), and I ran the PC side that morning:
  1. the archive went to `DATA/derived/hpc/rq4_scommune_20261026/` and was unpacked;
  2. the backup is `DATA/db/backups/pre-scommune-import-20261029.sqlite`;
  3. the Discovery session on *S. commune* is session 12;
  4. `adopt` imported 43 of 43 jobs, plus the 3 matrix-profile copies: 46 runs;
  5. Discovery is back on M2_aug (session 9).
- [x] Then the exam:
  - the candidate table, `Schizophyllum_commune_5b54500c`: 32,453 events;
  - the frozen manifest: sha256 `e11ec64a…5393bf9f0`, audit 1166;
  - queue 37, 263 items: audit 1167 (§2).

  The score runs once, after you judge.

### (b) Fair CNN — done (trained 28 Oct, imported 29 Oct)
The result: the CNN matches R4 on R4's folds (Chapter 8, Table *faircnn*).
- [x] Copy: `scp -r DATA/derived/hpc/rq1b_cnn_loro_20261026 s4699158@rangpur.compute.eait.uq.edu.au:CNN/DATA/derived/hpc/`
- [x] *rangpur*:
  1. `git pull`. The code it needs is already on GitHub. If the pull refuses because an unpacked archive changed files,
     skip it: the archive's code is newer.
  2. Once, on the login node, to download the pretrained weights:
     `conda activate torch_env && python -c "from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights as W; efficientnet_b0(weights=W.DEFAULT)"`
- [x] Submit: `ENC=$(sbatch --parsable DATA/derived/hpc/rq1b_cnn_loro_20261026/encode.sh)`, then
  `sbatch --dependency=afterok:$ENC DATA/derived/hpc/rq1b_cnn_loro_20261026/train.sh`
- [x] Copy `out/` back into the same folder here; leave `cache/` on the cluster (about 1.4 GB of pictures). Then:
  `"/c/ProgramData/anaconda3/python.exe" scripts/rq1b_cnn_vs_minirocket.py import --job DATA/derived/hpc/rq1b_cnn_loro_20261026`

### (c) 20-draw surrogate re-runs — home 29 Oct (96 of 96 tasks); statistics done, database import pending
This bundle uses the cluster's own copy of the code, so run it after (a) or (d) has been unpacked there.
- [x] Copy: `ssh s4699158@rangpur.compute.eait.uq.edu.au "mkdir -p CNN/docs/thesis/hpc"`, then
  `scp -r docs/thesis/hpc/surrogates20_M2_aug s4699158@rangpur.compute.eait.uq.edu.au:CNN/docs/thesis/hpc/`
- [x] *rangpur*:
  1. check that the 16 `DATA/derived/channels/M2_aug_concat_fs1/CH*.npy` files are present;
  2. `quota -s` (10–30 GB comes back);
  3. `bash docs/thesis/hpc/surrogates20_M2_aug/submit_th20.sh`
- [x] Bring every `*_out/return/` folder home, keeping the paths. The six folders came to 6.6 GB.
- [x] The Chapter 6 statistics were read straight from the returned records, with no database step (§7). Chapter 6
      `tab:surr20` and `fig:surr20`.
- [ ] Optional, for the site: import the runs into M2_aug's **session 2**, not session 9 ("demo · talk"). Choosing
      M2_aug reopens its newest session, which is 9, so session 2 has to be made the open one first; I can do that.
  Import after queue 37 is judged, because it loads 8765 for several minutes. It also copies about 6.6 GB of caches
  onto a disk with 36 GB free.
  - A dry run first:
    `"/c/ProgramData/anaconda3/python.exe" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/surrogates20_M2_aug`
  - Then the same command with `--apply --allow-project` added.

### (d) MJu26a, SH and SO at 2 Hz
- [ ] Copy:
  `scp DATA/derived/hpc/rq4_newsets_20261027/rq4_newsets_upload.tar.gz s4699158@rangpur.compute.eait.uq.edu.au:~/`
- [ ] *rangpur*, in `~/CNN`:
  1. `sha256sum ~/rq4_newsets_upload.tar.gz` should print `c6c7a1ec15bc7f1e0ed9c03d0ffd66e8eb3315a6b7056d3922388bbd23fce7e1`;
  2. `tar xzf ~/rq4_newsets_upload.tar.gz && rm ~/rq4_newsets_upload.tar.gz`;
  3. the checks in README step 2;
  4. `python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_newsets_20261027` should show 1,014 tasks
     missing;
  5. `quota -s` needs at least 15 GB free.
- [ ] Submit: `bash docs/thesis/hpc/rq4_newsets_20261027/submit_rq4n.sh`
- [ ] Watch the returned size (README step 5).
- [ ] Bring back the three return archives, open three Discovery sessions and adopt each (README steps 6–8). Or tell me
      when the archives are home.
- This sweep also runs `drop_detection_v1` on the three recordings, which B4's census needs.

*Later, only if needed:* long seed searches for B8. A search over about 10 minutes goes to the cluster as a seed job.

---

## 4. Labels and details only you know

In plain words: the tool cannot compare species or electrodes it hasn't been told about.

- [ ] **Species**, in Settings › Datasets, for:
  - ~~CO_fs2, LM_fs2 and M2_concat_fs1~~ *done 3 Nov from your labels: CO chocolate oyster; LM and M2_concat lion's
    mane. M2_concat is not oyster, so the "≈1,000 h of oyster" lines are corrected, and Chapter 2's prose sentence is
    flagged for you;*
  - SH and SH_fs2; SO and SO_fs2;
  - MJu26a_fs10 (its 2 Hz copy already says lion's mane);
  - Dwij A–D;
  - reishi (Fig2A).

  B6 and B12 need these: without them no family can be called cross-species. Or tell me the species and I'll set them.
- [ ] **Setup** of each UQ dataset for Chapter 5's corpus table: rig, cage, substrate and electrode type, for LM, CO,
      SH, SO and Dwij. Add one line each for F2B and L_R, which are excluded.
- [ ] **The reishi file's units** (Chapter 5 asks).
- [ ] **What A1 and A2 mean on M2** (it may split a pack into two sites), and the **electrode positions** from photos.
      B4's lag against distance needs both (`docs/rq_roundB/B4-cross-channel.md`).
- [ ] **Deactivate the copies** in Settings › Datasets, so that no "all recordings" count includes one recording twice:
  - L_LM_Jul_26_J_raw now: it is five MJu26a channels, and the 2 Hz sweep covers them again;
  - L_R now, if you want it out of the pickers (my scripts already skip it);
  - MJu26a_fs10, SH and SO (the 10 Hz originals) once the 2 Hz sweep is imported.
- [ ] **Environment logs** from your supervisor. This study is parked; Chapter 10 cuts the section if no logs arrive
      before the freeze.

---

## 5. Decisions waiting on you

- [x] **The cross-channel explorer build (B4).** Yes, S0 and S1 (28 Oct). Both are built and merged: S0, the layout
      reader (`44861b1`), and S1, the census and its nulls (`a68a1ff`). The rest waits until after the thesis.
      The original question, for the record:
  - *Plain version:* B4 asks whether activity travels from electrode to electrode, or whether shared wiring just makes
    channels move together. It can't be answered until the explorer page exists.
  - The workshop wrote ten slices in four waves (`docs/prompts/changes/cross-channel-explorer.md`, commit `82f4fa4`).
    None has started.
  - A first answer needs two slices: S0, the layout reader (mine), and S1, the census and its nulls (one agent). S2
    and S3 add the overlay page and the packs; S5 adds the artifact queue; S8, lag against distance, needs electrode
    positions.
  - Two agents are running now, and the limit is three.
  - *My recommendation:* S0 and S1 now, which is enough to answer B4 with its nulls; S2, S3 and S5 if they fit before
    3 Nov; the rest after the thesis.
- [x] **B2's morph statistic: add a step-size companion?** Yes (28 Oct), and it's built. In 5 of 19 sequences,
      neighbouring events are more alike than shuffled, against 0.9 expected by chance. That is persistence or a
      gradual morph; the score can't tell which.
- [ ] **Push to GitHub?** Every commit since 26 Oct exists only on this PC (`git status -sb` shows how many). Pushing backs the work up off
      this PC. Your call.

---

## 6. Writing

- [ ] Turn the purple notes into prose, chapter by chapter. They carry the numbers and their sources.
- [ ] Check the 38 references marked `% VERIFY` in `docs/thesis/bib/thesis.bib`, and where Chapter 2 uses them.
- [ ] Fill in Chapter 5's corpus table: the "?" species left (SH, SO, F2B; CO and LM are filled) and the count of
      distinct physical recordings.
- [ ] Rewrite Chapter 2's "about 1,000 hours of bio-electric recordings on *Pleurotus ostreatus*": M2_concat is lion's
      mane (its note says so).
- [ ] To read the thesis without the purple notes, change `\showinstructionstrue` to `\showinstructionsfalse` in
      `docs/thesis/preamble.tex` (line 58), or build `build/main-clean.pdf` with
      `latexmk -jobname=main-clean -usepretex='\def\hideinstructions{}' main.tex` in `docs/thesis`.
- [ ] Check Appendix G's decision log against `docs/prompts/fixup/QUESTIONS.md`.
- [ ] Re-shoot the screenshots on 8765 after the freeze.
- [ ] Write the abstract (notes only so far), and give the AI statement a final read.

---

## 7. What I'm doing, and what it waits on

| My task | Status, or what it waits on |
|---|---|
| **B3:** the restitution test (recovery against the gap before it, with a shuffled-gap null), and per-cycle model tracking (fall + recovery, FHN, Izhikevich) judged by held-out cycles (Round 5 Q1, A + B) | **done** 28 Oct (`7ab5071`). There is no within-train restitution, but a modest relation across census gaps on oyster. No model beats the neighbouring-cycle mean. Results are in Chapter 10 |
| **B1 and B2:** Intervals' LV and CV2 against Poisson and shuffled nulls; the sequence morph readout (Round 4 Q3) | **done** 28 Oct (`ffc909c`). The shared client is rebuilt, so 8765 shows both once it starts |
| Score queues 35 and 36, and put the results into Chapters 7 and 8 | **done** 28 Oct |
| *S. commune* exam: the candidate table, the frozen manifest and the blind queue; then the single score | imported, frozen and drawn 29 Oct (session 12, sha256 `e11ec64a…`, queue 37). Waits on your judging of queue 37 (§2) |
| The 2 Hz blind sample, then the verdict-free promote, then g-12, frozen for Chapters 9 and 10 | §3d imported, then your judging |
| The fair-CNN comparison write-up (RQ1b) | **done** 29 Oct (`a73afd2`). Trained on R4's rows and folds, the CNN matches R4: pooled AUC 0.970–0.973 against 0.971. Chapter 8, ledger C16 |
| The 20-draw surrogate statistics (Chapter 6) | **done** 29 Oct, from the returned records. Drop v1 and the 10-min CNNs beat all 20 draws on 14–16 of 16 channels. Wavelet-encoded level 5 and v1 slope σ 4 fall below all 20, though they are 0.92 and 0.99 precise. Every ratio is within 4 % of its 1-draw value. Chapter 6, ledger F8 |
| **B4:** S0, the channel layout reader (packs and positions) | **done** 28 Oct (`44861b1`) |
| **B4:** S1, the census of co-occurring events and its nulls. Then I walk its smoke states and run its thesis script on a bridge backup | **done** 28 Oct: merged (`a68a1ff`) and run on M2_aug, M2_concat, CO and LM. No evidence of propagation on M2_aug; M2_concat's co-occurrences are copies on CH5–8. MJu26a, SH and SO wait for the 2 Hz sweep |
| The full test suite for S1's merge | **done** 28 Oct. S1 broke two tests; both are fixed. One was a guard that keeps null-run events out of every count: a label lookup tripped it, and no census number changes. The other was the smoke walk's order. Four map tests had been failing since 19–20 Oct, before S0 and S1, because they read the map once and it now answers "counting…" before it counts. They now wait for the finished map (`b0e09fa`, 29 Oct), and the maps match the core's own computation cell for cell. One seed-estimate test is a timing flake under load |
| Register the ghost fungus (B7) | the bridge (§1) |
| Run B5 and B7–B12 on the site and draft the Chapter 10 studies | **B5, B6, B12 done** 3 Nov (`1fcb75f`, `bb0528b`, Chapter 10 `c88ec5f`), each with website screenshots in `docs/thesis/figures/roundb/`. B9 and B10 running (a helper on the site). B7 waits on the ghost fungus; B8's long searches go to the cluster; B11 waits on the 2 Hz sweep |
| Chapter 9's drop-share figure | **fixed** 3 Nov (`868df61`): a sign error showed rises as falls. The fastest-edge rule gives 91 % falls, not 9 % |
| Recompile the thesis and commit after each step | — |

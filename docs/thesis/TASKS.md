# Your outstanding tasks (as of Wed 28 Oct 2026)

**Dates:** experiments freeze **Tue 3 Nov** · full draft **Thu 5 Nov** · thesis due **Mon 9 Nov, 3 pm**.

Everything in sections 1–6 is yours; tick the boxes as you go. Section 7 lists what I am doing and which of your steps
each part waits on. Commands are for Git Bash in `C:\Users\mmebr\Documents\CNN`, except where a line says *rangpur*.
Queue counts were read from the database this morning (own looks only).

---

## 1. First: start the 8765 bridge

The bridge was not running this morning. Its log ends without an error, so the PC most likely restarted overnight.
Review, the imports and every page need it.

- [x] In PowerShell, from the repo root: `webui\start.ps1 -Project`. Project mode uses the real database, and the
      script builds the client only if none exists. Or ask me to start it. *(Running: restarted 28 Oct 20:25 with
      the B2 step score and a fresh client; logs `webui/runtime/bridge-8765-20261028-202539.*.log`.)*
- [ ] Wait about two minutes for the warm-up (the log says "template scores warmed").

---

## 2. Queues to judge

In plain words: these are the blind piles of events that only you can sort. Each takes about 15 minutes at 3–4 seconds an item.

| Order | Queue | Left | What it answers | Score it afterwards with |
|---|---|---|---|---|
| 1 | **35** RQ2 blind panel | 249 of 249 | RQ2: do Library seeds find real motifs, against duration-matched controls? | `"/c/ProgramData/anaconda3/python.exe" scripts/rq2_blind.py score --real --key DATA/derived/rq2_blind/20261026-rq2blind/key.json` |
| 2 | **36** M4 held-out exam | 290 of 290 | RQ3: does the frozen classifier work on a recording it has never seen? | `"/c/ProgramData/anaconda3/python.exe" scripts/m4_exam_score.py --real` |

- [ ] **Queue 35 first, before any other seed queue.** Seeing seed matches first would break its blindness.
- [ ] **Queue 36, step by step:**
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
- [ ] The *S. commune* exam queue (about 290 items), after its sweep is imported (§3a). The blind rules are the same:
      open only that queue until it is done.
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

In plain words: four bundles are built and waiting. None is confirmed submitted. They share the 30 GB quota, so bring
each big one home, and clean up, before starting the next big one.

**Recommended order:**
1. (a) and (b) together, now.
2. (d) next: g-12 and four round-B questions wait on it.
3. (c) last.

| | Bundle | Size of the run | Comes back | Full steps |
|---|---|---|---|---|
| a | *S. commune* sweep, the second unseen recording | 296 tasks; 1–3 CPU core-hours, at most 1 A100-hour; about 30–40 min wall | 0.2–0.8 GB | `docs/thesis/hpc/rq4_scommune_20261026/README.md` |
| b | Fair CNN against MiniRocket (RQ1b) | 18 training tasks; about 1.6 GPU-hours | small (`out/` only) | `DATA/derived/hpc/rq1b_cnn_loro_20261026/README.txt` |
| c | 20-draw surrogate re-runs on M2_aug | 96 tasks; 5–18 CPU core-hours plus 1–3 GPU-hours | 10–30 GB | below (no README) |
| d | MJu26a, SH and SO at 2 Hz | 1,014 tasks; 40–60 CPU core-hours, 12–16 A100-hours; 5–8 h wall | about 10 GB (up to about 35) | `docs/thesis/hpc/rq4_newsets_20261027/README.md` |

### (a) *S. commune*
- [ ] Copy:
  `scp DATA/derived/hpc/rq4_scommune_20261026/rq4_scommune_upload.tar.gz s4699158@rangpur.compute.eait.uq.edu.au:~/`
- [ ] *rangpur*, in `~/CNN`:
  1. `sha256sum ~/rq4_scommune_upload.tar.gz` should print `7128fe033eecd38b78431820a1bd4d84199ace388ab605b88582e7ac53d15e4f`;
  2. `tar xzf ~/rq4_scommune_upload.tar.gz`;
  3. the environment checks in README step 2;
  4. `quota -s`.
- [ ] Submit: `bash docs/thesis/hpc/rq4_scommune_20261026/submit_rq4s.sh`
- [ ] Bring it back and import (README steps 6–8), or tell me when the archive is home and I'll run the PC side:
  1. one return archive;
  2. a backup;
  3. a Discovery session on *S. commune*;
  4. an `adopt` dry run, then `--apply --allow-project`;
  5. Discovery back on M2_aug.
- Then I build its candidate table, freeze the manifest and draw the queue (§2). The score runs once, after you judge.

### (b) Fair CNN
- [ ] Copy: `scp -r DATA/derived/hpc/rq1b_cnn_loro_20261026 s4699158@rangpur.compute.eait.uq.edu.au:CNN/DATA/derived/hpc/`
- [ ] *rangpur*:
  1. `git pull`. The code it needs is already on GitHub. If the pull refuses because an unpacked archive changed files,
     skip it: the archive's code is newer.
  2. Once, on the login node, to download the pretrained weights:
     `conda activate torch_env && python -c "from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights as W; efficientnet_b0(weights=W.DEFAULT)"`
- [ ] Submit: `ENC=$(sbatch --parsable DATA/derived/hpc/rq1b_cnn_loro_20261026/encode.sh)`, then
  `sbatch --dependency=afterok:$ENC DATA/derived/hpc/rq1b_cnn_loro_20261026/train.sh`
- [ ] Copy `out/` back into the same folder here; leave `cache/` on the cluster (about 1.4 GB of pictures). Then:
  `"/c/ProgramData/anaconda3/python.exe" scripts/rq1b_cnn_vs_minirocket.py import --job DATA/derived/hpc/rq1b_cnn_loro_20261026`

### (c) 20-draw surrogate re-runs
This bundle uses the cluster's own copy of the code, so run it after (a) or (d) has been unpacked there.
- [ ] Copy: `ssh s4699158@rangpur.compute.eait.uq.edu.au "mkdir -p CNN/docs/thesis/hpc"`, then
  `scp -r docs/thesis/hpc/surrogates20_M2_aug s4699158@rangpur.compute.eait.uq.edu.au:CNN/docs/thesis/hpc/`
- [ ] *rangpur*:
  1. check that the 16 `DATA/derived/channels/M2_aug_concat_fs1/CH*.npy` files are present;
  2. `quota -s` (10–30 GB comes back);
  3. `bash docs/thesis/hpc/surrogates20_M2_aug/submit_th20.sh`
- [ ] Bring every `*_out/return/` folder home, keeping the paths.
- [ ] Before importing, check that the open M2_aug Discovery session is **session 2**, not session 9 ("demo · talk").
- [ ] A dry run first:
  `"/c/ProgramData/anaconda3/python.exe" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/surrogates20_M2_aug`
- [ ] Then the same command with `--apply --allow-project` added.

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
  - CO_fs2, LM_fs2 and M2_concat_fs1;
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

- [x] **The cross-channel explorer build (B4).** Yes, S0 and S1 (28 Oct). S0, the layout reader, is done
      (`44861b1`). S1, the census and its nulls, is running in its own worktree. The rest waits until after the thesis.
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
- [ ] Fill in Chapter 5's corpus table: the "?" species (from §4) and the count of distinct physical recordings.
- [ ] Check Appendix G's decision log against `docs/prompts/fixup/QUESTIONS.md`.
- [ ] Re-shoot the screenshots on 8765 after the freeze.
- [ ] Write the abstract (notes only so far), and give the AI statement a final read.

---

## 7. What I'm doing, and what it waits on

| My task | Status, or what it waits on |
|---|---|
| **B3:** the restitution test (recovery against the gap before it, with a shuffled-gap null), and per-cycle model tracking (fall + recovery, FHN, Izhikevich) judged by held-out cycles (Round 5 Q1, A + B) | **done** 28 Oct (`7ab5071`). There is no within-train restitution, but a modest relation across census gaps on oyster. No model beats the neighbouring-cycle mean. Results are in Chapter 10 |
| **B1 and B2:** Intervals' LV and CV2 against Poisson and shuffled nulls; the sequence morph readout (Round 4 Q3) | **done** 28 Oct (`ffc909c`). The shared client is rebuilt, so 8765 shows both once it starts |
| Score queues 35 and 36, and put the results into Chapters 7 and 8 | your judging (§2), or run the two commands yourself |
| *S. commune* exam: the candidate table, the frozen manifest and the blind queue; then the single score | §3a imported |
| The 2 Hz blind sample, then the verdict-free promote, then g-12, frozen for Chapters 9 and 10 | §3d imported, then your judging |
| The fair-CNN comparison write-up (RQ1b) | §3b imported |
| The 20-draw surrogate statistics (Chapter 6) | §3c imported |
| **B4:** S0, the channel layout reader (packs and positions) | **done** 28 Oct (`44861b1`) |
| **B4:** S1, the census of co-occurring events and its nulls. Then I walk its smoke states and run its thesis script on a bridge backup | running in its own worktree |
| Register the ghost fungus (B7) | the bridge (§1) |
| Run B5 and B7–B12 on the site and draft the Chapter 10 studies | the imports above |
| Recompile the thesis and commit after each step | — |

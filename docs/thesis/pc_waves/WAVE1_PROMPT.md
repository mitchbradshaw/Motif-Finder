# Wave 1 — the thesis data export (paste everything below the line into the PC's Claude session)

---

Please run one read-only export for my thesis. Do exactly these steps in Git Bash, from the repo root
`C:\Users\mmebr\Documents\CNN` (`cd /c/Users/mmebr/Documents/CNN`). Do not edit any file, do not install anything.

1. Bring in only the export script and this folder (do NOT switch branch, merge, pull, commit or stash):

       git fetch origin claude/hopeful-knuth-kh8u38
       git checkout origin/claude/hopeful-knuth-kh8u38 -- scripts/thesis/wave1 docs/thesis/pc_waves

2. Run the one command (it takes roughly 15–45 minutes; it only reads the database; let it finish):

       PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/wave1/run_wave1.py --out DATA/derived/thesis_bundle/wave1

3. When it ends, reply with the last 25 lines of the console (they include a `finished in ... min: N ok, M not ok`
   line and one `PART:` line per zip), and the full paths of the zip parts
   (`DATA/derived/thesis_bundle/wave1/wave1_part01.zip`, `wave1_part02.zip`, ...).

4. If a step fails, or the command stops with an error: do NOT debug, retry or change anything. Just paste the output
   of these two commands:

       tail -n 40 DATA/derived/thesis_bundle/wave1/REPORT.md
       tail -n 40 DATA/derived/thesis_bundle/wave1/wave1.log

---

## For the author (no Claude needed)

The same thing in one line, from the repo root in Git Bash:

    cd /c/Users/mmebr/Documents/CNN && git fetch origin claude/hopeful-knuth-kh8u38 && git checkout origin/claude/hopeful-knuth-kh8u38 -- scripts/thesis/wave1 docs/thesis/pc_waves && PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/wave1/run_wave1.py --out DATA/derived/thesis_bundle/wave1

(PowerShell, once the files are there: `& "C:\ProgramData\anaconda3\python.exe" scripts\thesis\wave1\run_wave1.py --out DATA\derived\thesis_bundle\wave1`.)

Then attach every `DATA\derived\thesis_bundle\wave1\wave1_partNN.zip` to the chat, part 01 first (it holds
`REPORT.md`, which says what worked and what every other part holds). Each part is at most 24 MB.

Notes: the database is opened read-only and nothing in it changes; the web UI may stay open. M4_aug is exported on
purpose (its exam was scored on 26 Oct); *S. commune* is never read. Re-running is safe; `--only pool,m4_exam` re-runs
some steps and re-zips, `--zip-only` only re-zips.

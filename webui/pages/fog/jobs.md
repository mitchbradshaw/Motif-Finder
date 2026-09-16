# Jobs — frontend-design fog

Where a frame assumes something the core or the data cannot provide, or the spec is ambiguous.
Written while building jobs.all / jobs.paused / jobs.upload / jobs.cluster (16 Sep).
Each bullet: question · why it matters · source.

## Rows and counts the canon does not carry

- **The frame's table has rows §0 does not name.** `a-0101` (image encoding, Analyse, 62 %), `l-0009`
  (regroup g-09, Library, 30 %), and the seven "finished and cancelled today" rows (`a-0099`, `a-0100`,
  `r-0429`, `r-0430`, `l-0008`, `q-11`, cancelled `a-0096`) are invented in `fixtures/jobs.ts` to make the
  groups non-empty. If another workspace later mints ids in those ranges they will collide · matters because
  ids are the page's primary key and the deep links `?sel=` use them · source: frame jobs-1, §0 Jobs row.
- **"4 review queues · 1 idle" — which queue is idle is never said.** I made `q-18` (training windows) idle
  because it is the only one with no pace in the frame. The Review inventory proposes a fifth queue `q-16`
  (Explore spans) that jobs-1 does not list at all · matters because the chip count and the queue group
  disagree with Review if Review ships q-16 · source: frame jobs-1, review inventory F1.
- **`DEMO_NEED_YOU = 3` is a constant, not a derivation.** The page derives its own "N need you" from the
  rows (paused waiting + result arrived + overdue cluster job = 3), so the two agree today; they diverge the
  moment a demo write adds a fourth (e.g. a manifest waiting to import, which §7c.1 explicitly counts as
  "needs you") · matters because the header chip adds `DEMO_NEED_YOU` to the live count and would then be
  wrong · source: `fixtures/canon.ts`, §7c.1.
- **`j-0214` is "running for 3.3 h" and `j-0217` "since 11:40 / 2 h" — both are wall-clock strings, not
  timestamps.** Nothing recomputes them, so the page cannot say "3.4 h" a minute later, and the 3× rule is
  evaluated against a frozen number · matters if the real page is expected to age its own rows · source:
  §0 Jobs, frame jobs-1.

## Where the result is, and what "arrived" means

- **Two different "result arrived" states are drawn for the same run.** jobs-1's rail says r-0431's result is
  "not there yet"; jobs-2 draws r-0431 with "result arrived 14:31"; jobs-4's inbox lists "r-0431 · stage 3 ·
  result arrived 14:31". I made `waiting` the default for r-0431 (jobs-1 is the entry point) and `?state=arrived`
  the deep link jobs-2 draws · matters because it decides whether Continue is enabled on arrival · source:
  frames 1, 2, 4.
- **Who decides a result "arrived"?** §7c.2 says it is recognised "already in its root or in the manifest
  inbox", but nothing says how often the root is polled, or what happens if a file is half-written when the
  poll runs · matters because *Look again* is the only manual trigger in the UI · source: §7c.2, §9.6.
- **The expected path is built by a naming convention nobody has specified here.** `./PROFILES/M2_aug_fs1_CH2-4_1Hz_m120_9b24e1f0.npz`
  encodes recording, channel range, fs, `m` and the recipe hash. §9.11 is cited but the grammar is not given,
  so a channel set that is not contiguous (CH2, CH7, CH11) has no drawn form · matters because the path is
  shown locked and the upload modal refuses anything placed elsewhere · source: frames 2 and 3.
- **The two frames disagree on the sample count for the same run.** jobs-2 (found in place) says "162,600
  samples each (45.2 h at 1 Hz, less m)"; jobs-3 (uploaded) says "2,595,481 samples per channel (721 h at
  1 Hz, less m)" for the same r-0431 · matters because one of them is checking the wrong scope, and the check
  is the thing that protects the recipe. Both strings are kept verbatim in the fixture · source: frames 2, 3.
- **r-0431's scope is "3 channels · 45.2 h" in the stage card but "721 h" in the meta line.** Same conflict as
  above, inside one frame · source: frame jobs-2.

## Checks and refusals

- **The two check lists are different lists.** In place (frame 2): place · recipe hash · one per channel ·
  length · finite · null draws. Uploaded (frame 3): readable · one per channel · length · finite · parameters ·
  null draws. "In the place the run expects" cannot apply to a file you are about to place, and "readable"
  is absent from the in-place list · matters because P24 names one set of checks · source: frames 2, 3, P24.
- **A file with no null draws passes, and its null "goes to the cluster" — as what?** The amber note says the
  null (200 circular shifts, ~25 min) is over the 20 min limit so it goes to the cluster, but no new cluster
  job id is drawn, and the run's state while that null is out is not designed. The shell records a demo write
  and says so in a toast · matters because it is a second pause on the same run · source: frame jobs-3, §7c.3.
- **"Start a new run with m = 60 s" has no destination.** It would have to open Discovery (or Analyse) with the
  template pre-filled from the *rejected file's* metadata — a flow no frame draws. Not wired · source: frame jobs-3.
- **A held-out (M4_aug) upload is not drawn anywhere.** D6 says every route refuses M4; I added a `held-out`
  file to the picker with a refusal naming D6, but the exact copy is invented · source: D6, §0.

## Cluster jobs

- **"Mark finished / Mark failed" are only drawn on the overdue reminder.** §7c.4 makes them general, so a job
  marked running *within* its estimate has no drawn way to be marked finished. I added a plain "running" note
  with the same two buttons · matters because otherwise a job that finished early is stuck · source: §7c.4,
  frame jobs-4.
- **"Still running · remind me in 3 h" has nowhere to live.** There is no persistence in this build and no
  scheduler in the core; the snooze is in-memory and the reminder returns on reload · source: frame jobs-4.
- **The cluster job id is an editable text field with no validation drawn.** SLURM ids are integers, and an
  array job is `4418093_3`. Nothing says whether the field is used for anything (it cannot be queried) ·
  source: frame jobs-4.
- **Marking a job failed does not say what happens to the run waiting on it.** r-0431 waits on j-0217; if
  j-0217 is marked failed, jobs-1's rail for r-0431 still reads "waiting on j-0217". The only offered exit is
  *New SLURM script* · matters because it is the most likely real path · source: frames 1, 2, 4.
- **A new script "replaces" the old job — what happens to the old one's record?** The shell keeps the failed
  job with a `replaced by j-0218 →` link. Whether the replacement inherits the estimate, the profile and the
  calibration is not stated · source: frame jobs-2 "the new job replaces it".
- **The estimate is "1 h · calibrated 12 Sep" and locked.** Where calibration comes from, and what happens
  when a job runs 3.3× it, is not fed back — the next estimate is still 1 h · source: frame jobs-4, §9.6.

## Inbox

- **The manifest inbox is drawn inside the cluster-job page and (implicitly) as a global "Manifest inbox · 1"
  button on jobs.all.** Whether they are the same surface is not stated; I used one component in a drawer on
  jobs.all and a card on jobs.cluster · source: frames 1, 4.
- **"1 imported" counts imported manifests, not waiting ones.** So the button reads `Manifest inbox · 1` when
  nothing needs doing, which reads like a badge for attention · matters because §7c.1 lists "a manifest waiting
  to import" as a needs-you item · source: frame jobs-1.
- **Import is all-or-nothing and its checks are listed but not sourced.** "test windows identical across arms"
  and "no test window in training" compare against the launch record; if a check failed, nothing is drawn ·
  source: frame jobs-4, §7c.4.

## Cross-workspace

- **`recordDemoWrite('jobs', 'add-job', …)` gives an added job no estimate, profile or script of its own.**
  The shell fills in `not calibrated yet · from the stage estimate` and a generic script. A real Create-SLURM-script
  in Analyse/Discovery/Models would carry all three · source: kit README cross-workspace contract.
- **Cancelling a run does not cancel its cluster job**, and the site cannot. The shell says so in the confirm
  modal; no frame draws it · source: §7c.4 "the site cannot see the queue".

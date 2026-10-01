# Report — Fixup F: a dataset has an identity, and the whole site calls it by name

Run 2026-10-01 on `main`, in the main checkout, from base `6994b55`. Commit prefix `fixup-f:`. The first commit,
`d5a3bc9`, touches only `tests/` and fails (9 of 9 in `tests/test_dataset_identity.py`; 6 of 7 in
`tests/test_webui_dataset_naming.py`; the two `tests/test_webui_library.py` expectations it changes on purpose).
The implementation is `60008a8` (core), `9ee9686` (bridge), `7c6be58` (client), `83d4261` (smoke states, one more
test, the Sequence page, the registration doc) and `5d7eb95` (a defect my own new smoke state found, §7). Prompt `J` ran in the same checkout throughout — its Dehshibi
tests, fixtures, scripts and `QUESTIONS.md` hunks were uncommitted and mid-edit the whole time. The two prompts
shared no source file; every commit here is path-scoped.

**What the researcher sees.** Settings › Datasets has the six fields Q23 names. Give a dataset a display name
there and it is that name in Explore's recording menu and breadcrumbs, in Analyse's source chip, in Discovery's
scope chip and recording picker, on every Review item, on every Library card and in Interrogation — and the file
it really is sits one hover away, and under the name on the Datasets page. Leave the name empty and the dataset is
called by its source file, everywhere, with nothing prettified.

---

## 1. The `datasets` table, and why it is keyed by `source_file`

`recordings` is one row per channel (`UNIQUE (source_file, channel)`). The real database holds 130 channel rows
across **11 source files**; what the researcher calls a dataset is the set of rows sharing a `source_file`. Species,
organism, date, condition, name and notes are properties of that set, so repeating them on sixteen channel rows is
the wrong shape — sixteen places to disagree.

```sql
CREATE TABLE IF NOT EXISTS datasets (
    source_file      TEXT PRIMARY KEY,
    display_name     TEXT,
    species          TEXT,
    organism_id      TEXT,
    experiment_date  TEXT,              -- ISO YYYY-MM-DD
    condition        TEXT,
    notes            TEXT,
    updated_at       TEXT NOT NULL,
    actor            TEXT
);
```

Additive, `CREATE TABLE IF NOT EXISTS`, through `init_db()` (`_create_datasets_table`), idempotent, plain SQL
(rule 3). A row is created the first time a field is filled; a source file with no row has no metadata and is
called by its file name. `Working/database/datasets.py` is the whole access layer: `get_dataset`, `list_datasets`,
`put_dataset` (validates, returns what changed), `display_name` / `display_names` (the rule), `species_values`.

**`recordings.notes` is not migrated.** It is per-channel text (the real database has it on four files — the fs
provenance on M1 / M100 / M101_t and "ch 14 Xmas red; single-channel export…" on Mushroom). The dataset's `notes`
is a second field; the Datasets page shows the per-channel text read-only under "read from the data · channel
notes" and says in the tooltip of each which is which. `tests/test_dataset_identity.py` pins that an `init_db()` on
a database with channel notes leaves `datasets` empty.

**I looked for a reason the shape is wrong and did not find one.** Checked against the real database, read-only:

| question | answer |
|---|---|
| a source file that is two datasets? | No. `M1.mat` and `M100.mat` were both derived from the raw file `M1_M100.mat`, but they were registered as two `source_file` values, so they are two rows here — which is right, they are two organisms |
| a dataset spanning two files? | `M2_aug_concat_fs1.mat` and `M2_aug_concat_fs2.mat` are the same recording resampled, and `Mushroom_260720_0509_4hrs_CH14_fs1.mat` is a 10:1 excerpt of `L_LM_Jul_26_J_raw.mat`. Each pair is two files of **one organism**, not one dataset: they differ in rate, length and which runs reference them. That is exactly what `organism_id` is for — give both the same id and the Datasets page lists "same organism: …" under the field |
| `M2_aug` vs `M2_concat`? | Different data under similar names (`memory/m2-datasets-and-seeds.md`). Two rows, two names, and the table refuses to let either be called by the other's name **or the other's file name** |

## 2. The fields

On Settings › Datasets, in three groups (screenshot `after-settings-datasets.png`):

- **Identity** — editable, saved to `datasets`: display name, species, organism id, experiment date, condition,
  dataset notes.
  - *display name* is optional. Empty means "called by its file", and the placeholder is the file name. At most 60
    characters; may not be another dataset's name or another dataset's file (client says so before the save; the
    bridge refuses with 422).
  - *species* is a free text field with the species already in use on other datasets offered as one-click chips
    under it — not a locked vocabulary.
  - *organism id* — when another dataset carries the same id the field says "same organism: …".
  - *experiment date* validates as `YYYY-MM-DD` on the client and in the core (`2026-02-30` is refused).
- **Read from the data** — shown, locked, each with the reason on hover: source file, channel count and row ids,
  sampling rate and where it came from, duration, the stored unit (prompt `B`'s column and its Declare control,
  unchanged), registration provenance (`registered_at` / `registered_by`; a file whose rows predate the registry
  says "before the registry · not recorded"), whether the recording has a higher-resolution parent (prompt `G`'s
  link), and the per-channel notes.
- **Recording conditions** — the settings that were already there (substrate, electrode config, start time, time
  zone, noise floor, temperature, humidity), still in the `settings` table.

**Writing goes through the audited settings path.** The page saves `meta.<stem>.<field>` through
`PUT /api/settings/datasets` exactly as before — same draft store, same save bar, same "differs from default"
dots. The bridge routes the six identity fields into `datasets` and leaves the rest in `settings`
(`registration.py::_split_dataset_keys`, `_put_datasets`). A save is all-or-nothing (one transaction, rolled back
on any refusal), and the audit entry is written **by file name**:
`Dataset L_LM_Jul_26_J_raw.mat: display name not set → Lion's mane J · species not set → …`.
The held-out dataset's identity is refused (423) while the lock is on, matching the page's read-only card.

The real database had **no** `meta.*` settings rows (checked read-only), so there was nothing to carry over from the
old settings-table display name and no migration was written for it.

## 3. The naming seam, and every call site that goes through it

> a dataset is printed by its display name when it has one, and by its source file when it does not; the source
> file is always reachable.

One implementation on each side of the bridge:

| side | the seam | what it is |
|---|---|---|
| core | `Working/database/datasets.py::display_name` / `display_names` | the fallback itself. There is no other |
| bridge | `webui/server/corpus.py::dataset_name` / `dataset_names` | the bridge's only door to it; `corpus.recordings()` puts `display_name`, `named`, `stem`, `dataset` on every file |
| client | `webui/client/src/naming.tsx` — `<DatasetName file>`, `datasetName(names, file)`, `useDatasetName`, `datasetTitle` | one read (`GET /api/datasets`), shared by every page, re-read when Settings › Datasets saves. Takes an *identifier* (source file or directory stem) and prints the name with `title="source file … · species · organism · date · n ch · Hz · h"` |

Call sites, and what each printed before:

| workspace | where | before | now |
|---|---|---|---|
| Explore | recording menu trigger and rows (`RecordingMenu.tsx`) | `source_file` | `<DatasetName>`; the filter matches the name **and** the file |
| Explore | Signal / Cross-channel / Span-edit breadcrumb | `source_file` (a fixture label on Span edit) | `<DatasetName>` |
| Analyse | source chip (`toolbar.tsx::SourceChip`) | `Signal span · CH…` — no dataset at all | `<name> · CH… · hours`; the hover keeps the file, row id and samples |
| Analyse | source popover (`ChainPage.tsx`) | `source_file` | `<DatasetName>` |
| Analyse › Interrogation | family and member recording / channel (`api/interrogation.ts`, bridge `_named`) | the seed store's channel **file** and raw index — it printed `CH0.npy · CH0` | the dataset name and the channel name, resolved from `recording_id`; the store's own fields stay on the row as provenance |
| Analyse › Sequence | header subtitle and picker (`SequencePage.tsx`) | `source_file` | `datasetName` |
| Discovery | scope chip, History subtitle, "recording changed" toast, channel popover (`chrome.tsx`) | `stem` | the name (`<DatasetName>` on the chip) |
| Discovery | recording picker | `file` | the name, with the file in the row's hint when it differs |
| Discovery | seed cards (`SeedPage.tsx`), default seed title (bridge `_seed_info`) | `source_file` minus `.mat`/`.csv`; `stem` | `<DatasetName>`; `corpus.dataset_name` |
| Review | every item's meta line, the queue rows, the held-out refusal (bridge `_index`) | `rec_label`: `M2_aug fs1` — a file name prettified in the bridge | the name; `recordingFile` is carried beside it and is the meta line's hover |
| Review | Shape card "drawn from …" (`parts.tsx::drawnFrom`) | `rec_key` | `datasetName(names, source_file)` |
| Library | recurrence matrix rows, member cards, family detail, import preview, window sets (bridge `_recordings_index`, `_rec_groups`) | `rec_label`, a second copy of the same prettifier | the name; `file` / `recordingFile` beside it |
| Settings | Datasets table and card, Channels & events picker / subtitle / event log, held-out select | the directory stem | the name, the file under it |

**Three prettifiers are gone**: `review.rec_label` and `library.rec_label` (each `re.sub(r"_(fs\\d+)$", …)` over a
`_concat`-stripped stem) now delegate to `corpus.dataset_name`, and the client's two `.replace(/\\.mat$/, '')`
label sites are replaced. So an unnamed `M2_aug_concat_fs1.mat` is printed as exactly that, not as `M2_aug fs1` —
two tests that asserted the prettified form were changed on purpose in the red commit.

**Labels changed; keys did not.** `rec_key` (Review, Library), Discovery's `key` / `stem`, the registry's `name`
(the directory stem), `meta.<stem>.<field>`, `?rec=<stem>` and every `source_file` join are untouched, and
`tests/test_webui_dataset_naming.py` asserts Discovery's `(key, stem, file)` triples are identical before and after
a rename. While doing this I found **two places that matched on a label** and moved both onto identifiers:

- `api/review.ts` filtered held-out rows with `HELD_OUT.includes(r.recording)` — a list of fixture *labels*. It now
  reads the bridge's own `heldOut` flag on the row.
- `api/discovery.ts::isHeldOut` accepted `r.label === recording`. It now matches `key`, `file` and `stem` only.

Interrogation is the one place a printed name is still used as a client-side grouping value (`m.recording` splits
intervals and colours by recording; it was the file string before). It stays correct because two datasets cannot
share a name, but it is a grouping on a label and is listed under items left.

## 4. The channel convention: one-based won

`channel_name` (`Working/discovery/channels.py`) is the seam and it already said `CH{channel + 1}`. **One-based
wins**, for three reasons:

1. the sixteen-channel M2 files — most of the corpus's annotations — are already one-based by electrode name:
   `recordings.channel = 0` is `CH1_A1`. Zero-based for the other files would have meant two conventions on one
   page the moment two datasets are compared;
2. Discovery stores channel *names* in a saved session (`discovery_sessions.channels_json`) and resolves scope by
   name; flipping the convention would have broken every saved session with a non-M2 channel in it;
3. it was already what Explore, Review and `G`'s source-resolution line print. The outliers were fewer.

What printed the raw index and no longer does: Settings › Datasets' excerpt link and callout (`CH2` → `CH3`,
`excerpt_of.channel_name` from the bridge), the import modal's excerpt lines, `Working/discovery/scoreboard.py`
(two rows of `f"CH{channel}"` → `_channel_name`), Interrogation (`CH${f.channel}` → the resolved name), and Settings
› Channels & events, whose "electrode · position" column printed `CH2 · CH2.npy` beside a row named `CH3`.

**The stored index is not hidden.** The files on disk are zero-based (`CH2.npy`) and a researcher reading a log
needs the mapping, so it is shown *beside* the name and never instead of it: `channel_index_note(2)` →
`recordings.channel = 2 · CH2.npy`, as the excerpt link's hover and as the Channels table's "stored index · file"
column (`index 2 · CH2.npy`).

## 5. The tab strip (U5)

The recording selector on Settings › Channels & events was a segmented control with one tab per recording,
in the card header. At 1440 px it showed nine of eleven and a clipped tenth; at 900 px five, with the selected tab
itself cut off (`before-settings-channels-wide.png`, `-narrow.png`). There was no scroll affordance and the later recordings were
unreachable without editing the URL.

It is now a picker (`Dropdown`, `data-testid="rec-picker"`): one control of bounded width whose menu scrolls, each
row the dataset's name with its file and channel count beside it, and it sits at the **start** of the header beside
the title, because right-aligned was the first thing a narrow window pushed out of reach. A list that keeps
growing is a picker, not a row of tabs. `after-settings-channels-picker-narrow.png` / `-wide.png` show it open.
The picker's value is the directory stem; its label is §3's name; the channel rows are §4's convention.

## 6. `--dist`, `J`'s files, and when I took the machine

`--dist` already existed (it landed before this wave); I did not add it. Every client build of this run went to
`<scratch>/dist-f` (`npx vite build --outDir …`, and `npm run build -- --outDir …` for the gate), every bridge was
started `--sandbox --port 8765 --dist <scratch>/dist-f`, and I checked the `CLIENT = … (a private build…)` banner
line and `/api/runtime.client_dist` before trusting a screenshot (the evidence script prints it and refuses a
non-sandbox bridge). **The shared `webui/client/dist` was never built.** The "before" screenshots are from a
bridge on the untouched tree at `6994b55` with its own private build, taken before the first edit.

`J`'s files were **not red** whenever I ran `npx tsc -b` or `npm run build` (five times across the run) — `J` had
no client file in flight that I saw.

**When I took the machine** (local time, 2026-10-01). `J` had a bridge on 8766 and a Playwright evidence script
running during some of these; I saw no `pytest` of `J`'s in the process list before any smoke run.

| what | when |
|---|---|
| `pytest -n 4`, conda, whole suite | ≈ 17:16 – 17:24 (8 min 21 s) |
| `pytest -n 4`, `webui/.venv`, the bridge files | ≈ 17:25 – 17:31 (6 min 26 s) |
| smoke, full, run A | 17:32 – 17:49 |
| smoke, Settings only (fresh bridge) | 17:51 – 17:55 |
| smoke, full, run B | 17:56 – 18:13 |
| smoke, Discovery only | ≈ 18:13 – 18:15 |
| smoke, full, run C | 18:16 – 18:33 |

Never `pytest` and smoke together. My smoke runs wrote their screenshots to the scratchpad (`SMOKE_SHOTS`), so
they did not rewrite the tracked `webui/screenshots/` set.

**Run B overlapped a smoke run of `J`'s.** The tracked `webui/screenshots/` files were rewritten between 17:50 and
18:10 (they include a `fixup-j-dehshibi-funnel` state, and `smoke-result.json` changed), which is a second
Playwright walk against `J`'s bridge during my 17:56 – 18:13 run — two browsers and two bridges on one machine.
That is where run B's two flakes came from, and it is why run C, alone on the machine, is clean. Those rewritten
screenshots are `J`'s working state; I left them untouched and uncommitted.

## 7. The gate

**1. Type-check and build.** `npx tsc -b` clean; `npm run build -- --outDir <scratch>/dist-f` (`tsc -b && vite
build`) green — into my own dist.

**2. pytest.** Baseline 1799 passed / 7 skipped / 0 failed.

| interpreter | result | failure set |
|---|---|---|
| conda, `pytest -n 4`, whole suite | **1857 passed, 8 skipped, 0 failed** | empty. The eighth skip is `tests/test_webui_dataset_naming.py` (FastAPI lives only in the venv); the rest of the growth is this prompt's 9 headless tests and `J`'s in-flight ones |
| `webui/.venv`, `pytest -n 4`, the 18 bridge files + the two core files this prompt touches | **290 passed, 3 xpassed, 1 failed** | `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` — the standing one (it asserts an old `reviewedCriterion` string; nothing to do with channel names, I checked the message) |

Three existing expectations were changed deliberately and say so in their commit messages: the two
`test_webui_library.py` labels (`M2_aug fs1` → `M2_aug_concat_fs1.mat`) and
`test_registration_settings.py::test_the_typed_name_is_the_display_name_when_one_is_set` (the name now lives in
`datasets`).

**3. Smoke**, against a `--sandbox` bridge on 8765 serving `<scratch>/dist-f`, restarted immediately before each
full run. I am reporting every run, because no two had the same failure set and the differences are the point:

| run | states | failures | beyond the five standing |
|---|---|---|---|
| A, full | 572 | 9 | **one of mine** — the new state `naming-a-dataset-saves-and-renames-the-row`: after a save the row still said "not named" until reload (fixed in `5d7eb95`); and three first-read timeouts, `storage-backups--default`, `about--default`, `about--packages` |
| Settings only, fresh bridge, fixed build | 121 | 4 | none — the four standing registration states and nothing else; the fixed state and the three first-read states pass |
| B, full, fixed build | 573 | 7 | `discovery.seed--source-explore` (missing `seed-explore-empty` at a 900 ms settle) and one aborted request counted as a console error, `requestfailed: /api/runs/29/events`, in the Analyse chain flow |
| Discovery only | 46 | 1 | none — `discovery.runs--default` only; `seed--source-explore` passes |
| **C, full, fixed build** | **573** | **5** | **none — exactly the five standing failures, no console or page error, no unexpected server traceback** |

Run C is the gate. So: the **five standing failures are present in every run and nothing I changed made one of them
worse**; the one
failure that was mine was found by my own new state and is fixed; and the remaining four are settle-time or
aborted-request flakes that each appeared in exactly one full run and passed when re-run — the same class as the
standing `discovery.runs--default` (`E` measured that one settling in 4.4 s against a 900 ms allowance). They are
on pages whose code this prompt did not touch (`/api/storage`, `/api/about`, the run-events stream) or touched only
in a branch the state does not reach (`SeedPage`'s Explore-span row; the state expects the *empty* card).

**The four standing Settings registration failures — the cause, found in passing.** They are not timeouts in any
real sense. Each state names a specific *unregistered candidate* and clicks its Check button, and each of those
candidates **has since been registered in the real database**, which the sandbox copies:

- `datasets--import-check-fails-fs-unknown` opens `?modal=import&path=M100`, and
  `datasets--import-check-passes-MJu26a` opens `&path=MJu26a`. Both were registered on 2026-09-21. The import
  modal lists only what is *not* registered — today `F2B` and `M1_M100`, both raw — so `path=` selects nothing,
  Check stays disabled, and `Locator.click` waits 30 s for a disabled button.
- `models-registration--check-a-joblib` and `storage-backups--scan-check-a-matrix-profile` click
  `check-model-catalogue_classifier_16750c76ade64016.joblib` and
  `scan-check-mp_v2_Mushroom_260720_0509_4hrs_CH14_fs1_CH0_WIN1min.npz` — same shape: a Check control that exists
  only for an unregistered file. I did not open those two pages to confirm it.

The first is a one-word fix (`path=F2B`: no fs in the file, so the check fails on `fs` exactly as the state
wants). The "passes" state has no candidate left that passes without typed input (`M1_M100` needs an fs), so it
needs either a fixture candidate or a different assertion. I did not change them — they are not this prompt's and
a fix that quietly re-points a standing failure deserves its own line in someone's report.

## 8. Defaults taken

| default | why |
|---|---|
| An unnamed dataset is printed as its full source file (`M2_aug_concat_fs1.mat`), not the old prettified `M2_aug fs1` | The prompt's rule, literally. A prettified file name is a third thing that is neither the name nor the file |
| Display name: optional, ≤ 60 characters, unique against other names **and other files**, case-insensitive | Uniqueness is what makes a name safe to read; a name equal to another dataset's file is the M2_aug / M2_concat confusion itself |
| The identity fields keep the page's `meta.<stem>.<field>` keys and its save bar; the bridge routes them | "Writing through the audited settings path like every other Settings page" — one save, one audit trail, no second form |
| `experiment date` is a date; the existing `start time` (YYYY-MM-DD HH:MM, with a time zone) stays beside it under Recording conditions | They answer different questions — which experiment, versus where clock-time readouts are anchored. Merging them is a design decision, not a fixup |
| The held-out unlock is typed against the bridge's `held_out.name`: the dataset's display name if it has one, else the directory stem `M4_aug_concat_fs1` as before | The existing contract and smoke states type the stem; the modal says exactly what to type. The page no longer derives that name itself |
| The held-out dataset's identity cannot be edited while the lock is on (423) | The page already drew those fields read-only; the bridge now agrees |
| Stored default titles are left alone: Review queue names (`drop_detection_v1 - Mushroom_260720 CH14`) and Discovery session names (`M2_aug_concat_fs1 screen`) are strings the user can rename, written at creation | Rewriting a stored title on a rename would make the name an input to stored state. New default seed titles do use the name |
| One-based channel names (§4) | — |

## 9. Items left

- **Review's single-channel exception.** `review.py::_channel_label` prints the electrode named *in the file*
  (`CH14` for `Mushroom_260720_0509_4hrs_CH14_fs1.mat`) where Explore prints the within-file name (`CH1`). It is
  deliberate (its docstring argues it) and it is not the `CH2`/`CH3` disagreement, so I left it — but it is still
  one channel under two names on two pages. Now that the dataset can carry a display name ("… · Ch14 Xmas red"),
  the cleaner fix is to drop the exception. A researcher decision.
- **Jobs** prints `M2_aug fs1` from fixtures (the page wears the `demo data` chip; X1's six Jobs fixture reads).
  The live job rows carry `recording_id` only. When Jobs is wired its label must come from `corpus.dataset_name`.
  Models and Training are fixture pages for the same reason.
- **Interrogation groups by the printed recording string** (§3). Carrying `dataset_file` as the grouping key and
  the name as the label is a small change across `E`'s three pages; not done here.
- **The four standing Settings registration smoke failures**: the cause is in §7 (the states name candidates that
  have since been registered). Not fixed here.
- **Smoke's settle-time flakes.** Four states failed in exactly one full run each and passed on re-run (§7). With
  two agents on the machine a 900 ms settle is not enough for a first read; `05-discovery.md` already owns the
  standing one.
- **The event-log strip on Channels & events** draws its row label at x = 0 over the strip's own first text
  (visible in both the before and after screenshots). Pre-existing; the prompt limits me to the tab strip on that
  page.
- **The real database's metadata is empty and filling it is the researcher's.** Nothing was written to
  `DATA/db/annotations.sqlite`. The `datasets` table is created by `init_db()`, which the bridge runs on its first
  request — so the first `webui\\start.ps1 -Project` (or any `init_db()` call) adds the empty table to the real
  database, additively. **I did not run it.**

## 10. Files

Declared: `Working/database/schema.py`, `Working/discovery/channels.py`, `webui/server/registration.py`,
`webui/server/corpus.py`, `webui/client/src/settings/DatasetsPage.tsx`, `settings/ChannelsEventsPage.tsx`,
`api/settings.ts`, `naming.tsx` (the seam, new), `api.ts` (append-only: one block at the end, existing interfaces
extended by declaration merging), `webui/smoke_pages/settings.json`.

Out of the declared list, each for the naming seam or the channel convention and nothing else:

| file | why |
|---|---|
| `Working/database/datasets.py` (new) | the table's access layer and the rule; `schema.py` holds schema only |
| `Working/discovery/scoreboard.py` | printed the raw channel index (§4) |
| `Working/registration/settings.py` | the held-out lock read its typed name from a `meta.*.display_name` settings row |
| `webui/server/review.py`, `library.py`, `discovery.py`, `interrogation_routes.py` | labels only (§3); keys untouched |
| `webui/client/src/explore/{RecordingMenu,SignalPage,CrossChannelPage,SpanEditPage}.tsx`, `analyse/{toolbar,ChainPage}.tsx`, `discovery/{chrome,SeedPage}.tsx`, `review/{parts,Inspector}.tsx`, `interrogation/SequencePage.tsx`, `api/{discovery,review,interrogation}.ts` | the call sites of §3 |
| `webui/client/src/settings/{store.ts,settings.css}`, `fixtures/{settings,review}.ts` | re-read the names on save; the card's sub-heads; the field list and row type |
| `tests/test_registration_settings.py`, `tests/test_webui_library.py` | expectations changed on purpose (said in the commit messages) |
| `docs/DATA_REGISTRATION.md`, `scripts/fixup_f_evidence.py` | the doc section; the evidence script |

`webui/smoke.py` was not touched. Nothing under `Adapters/`, `Pipelines/` or the Dehshibi pages was touched.

## Evidence

`webui/screenshots/fixup/F/`, all from a `--sandbox` bridge on a private build:

| | before | after |
|---|---|---|
| Settings › Datasets | `before-settings-datasets.png` | `after-settings-datasets.png` (named), `unnamed-settings-datasets.png` (the fallback) |
| Settings › Channels & events, wide / narrow | `before-settings-channels-wide.png`, `-narrow.png` | `after-settings-channels-wide.png`, `-narrow.png`; the picker open: `after-settings-channels-picker-wide.png`, `-narrow.png` |
| the one-based convention on a non-M2 file | `before-settings-channels-L_LM.png` | `after-settings-channels-L_LM.png` |
| the same dataset in three workspaces — `Mushroom_260720_0509_4hrs_CH14_fs1.mat` named "Lion's mane · 20 Jul · 4 h excerpt" | `before-review-queue.png`, `before-explore-corpus.png` | `after-review-queue.png`, `after-explore-corpus.png` |
| …and `M2_aug_concat_fs1.mat` named "M2 August · 1 Hz" | `before-discovery-runs.png`, `before-explore-recording-menu.png`, `before-library-recurrence.png` | `after-discovery-runs.png`, `after-explore-recording-menu.png`, `after-library-recurrence.png` |

Also `after-interrogation-source.png`: the scope table reads `M2 August · 1 Hz` × `CH1_A1` where it read
`CH0.npy` × `CH0` (no "before" was taken of that page; the old strings are in §3).

The names in the "after" shots are illustrative and exist only in the sandbox copy: three written by
`scripts/fixup_f_evidence.py --name`, and "Figure 2A reference" by the smoke state that had just run on that
bridge. `unnamed-settings-datasets.png` is a fresh sandbox with nothing named.

## Chat summary

Fixup F is done and the gate passes. A dataset now has an identity — a `datasets` table keyed by `source_file`
holding display name, species, organism id, experiment date, condition and notes — authored on Settings › Datasets
through the audited settings path. Give a dataset a display name and every workspace calls it that, through one
seam on each side of the bridge, with the source file one hover away; leave it empty and the dataset is called by
its source file. Channels are named one-based everywhere, with the stored index shown beside the name. The
Channels & events tab strip that ran off the card is a picker.

- **Gate:** `tsc -b` and `npm run build` clean (private dist). pytest 1857 passed / 8 skipped / 0 failed under
  conda; 290 passed and the one standing failure under the venv. Smoke run C: 573 states, the five standing
  failures and nothing else. Two earlier full runs each showed load flakes that passed on re-run, and run A found
  one real defect of mine, fixed.
- **Not done, on purpose:** nothing was written to the real database; filling the metadata is yours. The empty
  `datasets` table appears there the next time `init_db()` runs (any `-Project` start).
- **Yours to decide:** Review still calls the Mushroom export's channel `CH14` (from its file name) where Explore
  says `CH1`; now that the dataset can carry that in its name, the exception could go.
- **Found in passing:** the four standing Settings registration smoke failures click Check on candidates that have
  since been registered, so the button is disabled. The first is a one-word fix (`path=F2B`).
- **Still printing file-derived names:** Jobs, Models and Training, which are fixture pages.

# Fixup F — a dataset has an identity, and the whole site calls it by name

**Ready to run.** The researcher chose this as the next piece of work (Q23: *dataset naming first*),
and it is the only prompt in the stage that makes the app easier to *read* rather than more correct.
Every workspace header, queue title, card and menu currently prints a file name.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/prompts/fixup/QUESTIONS.md` **Q23**
and **Round 5** (the parallel-build rules in particular), `docs/DATA_REGISTRATION.md`, and
`docs/prompts/fixup/10-settings.md` S1 + `00-cross-cutting.md` X4.

Commit prefix `fixup-f:`. Test-first; first commit touches only `tests/` and must fail.

## Running in parallel

**Prompt `J` (`J-dehshibi-vs-the-paper.md`) runs in the same checkout at the same time.** It owns the
Dehshibi wavelet template — core detection code and the Analyse block page that draws it. You own
dataset identity: the schema, registration, Settings, and the *name* wherever it is printed.

| | you (`F`) | `J` |
|---|---|---|
| client | `settings/DatasetsPage.tsx`, `settings/ChannelsEventsPage.tsx`, `api/settings.ts`, the naming seam you add | the Dehshibi block page and its process view |
| server | `registration.py`, `corpus.py` (naming only) | the Dehshibi adapter's routes, if any |
| core | `Working/database/schema.py`, `Working/discovery/channels.py` | `Adapters/` Dehshibi wavelet + summation + detection, `Pipelines/` |
| smoke | `webui/smoke_pages/settings.json`, `explore.json` | `webui/smoke_pages/analyse.json` |
| port / dist | **8765** | 8766 |

**You own `Working/database/schema.py` this wave.** `M` migrated that file nine days ago and `J`
does not touch it. If `J` needs a column, it asks you.

**Shared files — small hunks, commit immediately with explicit `--` paths, never `git add -A`:**
`webui/client/src/api.ts` (append only), `webui/smoke.py` (extend only).

**The build rules wave 1 learned the hard way** (QUESTIONS Round 5, `E` §8.6 and `G` §10):

- **Build to your own `--outDir` and serve it with `run_server.py --dist`. Never build
  `webui/client/dist`** — wave 1 had no `--dist` and the two agents overwrote each other's bundle.
  If `--dist` is not in `run_server.py` when you arrive, **that is your first commit** (it is about
  four lines: an argument passed through to `Runtime(client_dist=…)`, which already exists at
  `webui/server/runtime.py:63,71`) — commit it on its own, path-scoped, and say so in your report so
  `J` can use it.
- **`npm run build` is `tsc -b && vite build`, so it type-checks the whole tree** and `J`'s in-flight
  files can make it red through no fault of yours. Run it for the gate at the end; use
  `npx vite build --outDir <yours>` to get something to serve meanwhile. Report it if `J`'s files
  were red while you ran it.
- **`pytest -n auto` and `webui/smoke.py` must not run together** — prompt `B` §9 recorded 23
  spurious smoke failures from exactly that. Use `pytest -n 4`, and **announce in your report when
  you took the machine for smoke**.

---

## 1. What a dataset *is*, and the one modelling decision

`recordings` is **one row per channel**: `UNIQUE (source_file, channel)`
(`Working/database/schema.py:71`). What the researcher calls a dataset — *Mushroom_260720*,
*M2_aug*, *L_LM_Jul_26_J* — is the **set of rows sharing a `source_file`**. The real database holds
about 70 such rows across a dozen source files.

So the attributes Q23 names — **species, organism id, experiment date, condition, display name,
notes** — are properties of the *file*, not the channel, and repeating them on fourteen channel rows
is the wrong shape. **Add a `datasets` table keyed by `source_file`**, additive, through
`init_db()`, idempotent, plain SQL (rule 3). A `recordings` row joins to it by `source_file`; a
source file with no row yet simply has no metadata, and its display name falls back to the file name.

**Do not** migrate `recordings.notes` into it silently — that column is per-channel and may hold
per-channel text. Leave it; the dataset's `notes` is a second, different field, and the Datasets page
should make clear which is which.

If you find a reason this shape is wrong — a source file that is genuinely two datasets, or a dataset
that spans two files — **stop and say so**. `memory`/`docs` record that `M2_aug` and `M2_concat` are
different data under similar names, which is precisely the confusion this table exists to end.

## 2. The columns exist before they can be filled

Build the editable fields, on Settings › Datasets, writing through the audited settings path like
every other Settings page (`every save is audited` — `10-settings.md`). Derived fields come free and
must be shown but **not editable**: channel count, `fs`, duration, `units` (prompt `B`'s column),
registration provenance, and whether the recording has a higher-resolution parent (prompt `G` uses
it).

`experiment date` is a date and should validate as one. `species` will be a short closed-ish list in
practice but the researcher is still discovering it — **a free text field with the existing values
offered**, not a locked vocabulary. `organism id` identifies the individual organism across
recordings and is the thing that makes "the same mushroom, three weeks apart" answerable; it is the
field most worth getting right.

## 3. The display name replaces the file name across the site

This is the half the researcher actually feels. One seam, used everywhere — **do not let fourteen
call sites each do their own fallback.** The rule:

> a dataset is printed by its display name when it has one, and by its source file when it does not;
> **the source file is always reachable** — on hover, in provenance, in the audit trail — because it
> is what the files on disk are called and what every log line says.

A name that hides its provenance trades one confusion for another. Prompt `B` found a unit error that
survived two years because the label and the stored thing disagreed; do not build a second one.

Where it has to land: every workspace header, Explore's corpus and recording menu, queue titles in
Review, Discovery's run rows and seed pages, Library cards, Jobs, and the Analyse chain's source
chip. `grep -rn "source_file" webui/client/src webui/server` is 137 hits in the server alone — most
are joins and filters, not labels. **Change the labels; leave the keys.** A display name is never an
identifier: nothing keys, joins, filters, caches or routes on it.

## 4. The channel-naming convention, one winner (`G` §10)

`Working/discovery/channels.py:30` returns `CH{channel + 1}`, so `recordings.channel = 2` prints
**CH3** on Explore, in Review's other-channels popover and in `G`'s new source-resolution line.
Settings › Datasets prints the raw index, **CH2**, for the same channel. Both pages are now yours.

Pick one and make it true everywhere, through `channel_name` — which already exists, already handles
the 16-channel M2 naming (`M2_STYLE_NAMES`), and is the seam. State in your report which you chose
and why. The researcher reads both pages; whichever wins, nothing may print the other.

## 5. The channel tab list runs off the page (U5)

Settings › Channels & events: the recording tab list overflows with no scroll affordance, so the
later recordings are unreachable. `ChannelsEventsPage.tsx` is 580 lines and the tab strip is the only
part of it this prompt touches. With a dozen datasets and seventy channels this is a real workflow
block, not a cosmetic one — and the fix should assume the list keeps growing.

While you are there: whatever that strip prints must be §3's name and §4's convention.

## Explicitly NOT in scope

| Not in scope | Why |
|---|---|
| **Renaming the files on disk, or any `source_file` value in the database** | A display name is a label. The files, the `npy_path`s and the keys are untouched |
| **The other fifteen Settings pages' symptoms** (S2–S10: the nulls method chip, inert α, library-grouping defaults, blocks on/off, F2B's unknown fs, the theme repaint) | `10-settings.md`, after its own questions |
| **Registering, unregistering or importing anything**, or the held-out M4 unlock | `docs/DATA_REGISTRATION.md` owns that path and it works |
| **The Dehshibi template, the wavelet blocks, `Adapters/` detection** | Prompt `J`, running in parallel |
| **Block process views, span slideshows, figures instead of tables** | Prompt `H` |
| **Converting mV recordings to volts in the core** | Q20's own prompt. You read `units`; you do not change what the core is handed |

## The gate

1. `npx tsc -b` and `npm run build` in `webui/client` — **into your own dist, not the shared one**;
2. `webui/smoke.py` against a `--sandbox` bridge on **port 8765** serving your dist, restarted
   immediately beforehand, **and not while `J` is running `pytest`**;
3. `pytest -n 4` against the **1799 passed / 7 skipped / 0 failed** baseline (`E` §9, `G` §9),
   comparing failure **sets**, which are empty. Under `webui/.venv`,
   `test_webui_discovery.py::test_the_scoreboard_cells_are_the_tables_own_numbers` fails pre-existing.
   **Five standing smoke failures** are not yours: the four Settings registration states
   (`datasets--import-check-fails-fs-unknown`, `datasets--import-check-passes-MJu26a`,
   `models-registration--check-a-joblib`, `storage-backups--scan-check-a-matrix-profile`) and
   `discovery.runs--default`.

Note that **four of the five standing smoke failures are on the page you are changing.** They are
`Locator.click` timeouts in the registration states, present on every bridge since prompt `B`. You
are not asked to fix them — but you will be in that file, and if you find the cause in passing, say
so. If your change makes any of them *worse*, that is yours.

**Evidence.** Before/after of Settings › Datasets and Settings › Channels & events into
`webui/screenshots/fixup/F/`, plus **a before/after of the same dataset's name in three different
workspaces** (a Review queue title, an Explore header and a Discovery run row), which is the thing
the researcher asked for. Screenshot the overflowing tab strip and its fix at a narrow and a wide
viewport.

## The real database

The metadata is empty until the researcher fills it, and **filling it is theirs, not yours.** Build
it, prove it on the sandbox, and leave the real database alone. If a migration has to touch
`DATA/db/annotations.sqlite`, it goes through `init_db()` like `M`'s did, and the researcher runs it —
say so in your report rather than running it. **Never point the bridge, pytest or an adapter at a
junction to the real `DATA/`.**

## Report

`docs/prompts/fixup/reports/F-datasets-and-naming.md`: the `datasets` table and why it is keyed by
`source_file`; the naming seam and every call site that now goes through it; which channel convention
won; the overflow fix; whether you added `--dist` and when `J`'s files were red; when you took the
machine for smoke; defaults taken; items left; out-of-scope files touched; the gate; a chat summary.

Then close `10-settings.md` S1, `00-cross-cutting.md` X4, and `QUESTIONS.md` U5, Q23 and the
channel-label row in Round 5.

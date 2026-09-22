# Fixup A — the fixes that need no decision

You are working in `C:\Users\mmebr\Documents\CNN` (Windows; the Bash tool is Git Bash; python is
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md` first — every rule in it binds you, in
particular rule 1 (no UI library in the core), rule 2 (no regressions against the suite), and the
Web UI gate. Then read `docs/prompts/fixup/README.md` and the three skeletons this prompt draws from:
`01-explore.md` (E1, E3, E5, E8), `02-analyse-chain.md` (A2, A3, A5), `04-analyse-training.md` (T3),
`05-discovery.md` (D1, D5), `07-review.md` (R1, R2, R6, R8, R9). Read `docs/CODING_STANDARDS.md` and
`docs/BLOCK_INTEGRATION.md` before touching an adapter.

Commit prefix `fixup-a:`. Work autonomously; take the default over asking; record every question you
answered yourself, with the default taken, in your report.

## Why this prompt exists, and what it must not become

The Fixup Wave is mostly blocked on design decisions the user has not yet made (`QUESTIONS.md`). This
prompt is the part that is **not** blocked: defects with a known cause, a known line, and exactly one
defensible fix. Everything here was diagnosed on 2026-09-22 by a read-only investigation; the file:line
references are from that investigation and were correct then.

**If a fix in this list turns out to need a design decision, stop, leave it, and say so in your report.**
An item silently widened into a redesign is worse than an item left undone — the user is answering
`QUESTIONS.md` in parallel and a decision taken here collides with one taken there.

## Explicitly NOT in scope

Do not touch these, even though they are adjacent and tempting. Each is waiting on a user decision.

| Not in scope | Why |
|---|---|
| **Review's hardcoded y domains** (`review/parts.tsx:12` `Y_MV`, `review/Shell.tsx:18` `THUMB_Y`) and **Library's shared percentile domain** | `QUESTIONS.md` Q-X2.1/Q-X2.2/Q-R1.1 — whether PRD D5 stands is the user's call, and these three surfaces must be fixed under **one** rule or not at all |
| **The Family page's shape sketch** vs its overlay waveform | Q-X2.3 |
| **Classes (1/2/3/4/9) in Review** | Q-R2 — there is no table to store one in; tags **are** in scope (see R2 below), classes are not |
| **`catalogue.cluster`'s dropped linkage matrix / silhouette / `df_membership`**, the dendrogram, the k-sweep, the members-of-cluster list | Q-0.1 and Q-T4 — this is a block-plus-page redesign, not a fix. Only the three bounded truthfulness items in T3-part-2 below are in scope |
| **The classifier joblib being write-only**, and any new evaluation output (confusion matrix, feature importances, shuffle null) | same |
| **Explore › Cross-channel** — `CrossChannelPage.tsx`, `crossScale.ts`, `getCrossChannel` in `api/explore.ts`, and the cross branch of `webui/server/explore_routes.py` | The user worked this surface by hand in commit `ab86d3a` (anchor-span ranking, the 600 s clamp, per-channel scaling, the error-path fix). Leave it alone. Explore items **13–15 below are in scope**; the cross-channel window control (E4) is not — it is Q-0.1 |
| **The two remaining `demo(` reads in `api/explore.ts`** | They are the Span-edit page and the keyboard map, and the module docstring is right that nothing computes them yet. Honest, not broken |
| **`DEFAULT_CHAIN`** (`state.tsx:77`) | Q-0.1 — wanted, but it changes the empty-chain validation path and ~40 smoke states |
| **The `demo.*` chain, `DEMO_TEMPLATES`, the eleven orphan glyph keys** | entangled with the demo-chain removal, which is a sized piece of work, not a fix |
| **Re-importing the four untagged type-specimen Library rows** | a write against the real database; the user approves that, not you |
| **Settings › Nulls offering `circular shift`** | Q-S2 — change the chip or change the block is a decision |

## Safety, before you start

- The working tree was clean at `ab86d3a` when this prompt was written, but **never `git add -A`,
  `git stash`, `git reset` or `git checkout .`** regardless. Commit only with explicit `--` paths you
  have edited, and do not commit a screenshot you did not regenerate on purpose.
- **Never point the bridge, pytest or an adapter at a junction into the real `DATA/`.** Run the bridge
  in `--sandbox` (the default) for everything here; nothing in this prompt needs `--project`, and
  `--project` writes to the real database.
- Set `PYTHONIOENCODING=utf-8` for both the bridge and `smoke.py`.
- Do not rebuild `webui/client/dist` while a smoke run is in flight, and restart the bridge after any
  edit under `webui/server/`.
- Do not install anything or change a dependency.

## Work (test-first per seam)

The loop, per item: write the failing test → make it pass with the simplest change → refactor → commit.
**Your first commit must touch only `tests/` and must contain a test that fails.** Take the Dehshibi
`nanmean` item first — it has the cleanest red test.

Items are ordered by value. Do them in order; if you run out of budget, stop at a commit boundary and
say where you stopped.

### 1. The Dehshibi template paints a black image on any real span  (`02-analyse-chain.md` A2-i)

`Adapters/preprocessing_wavelet_transform.py:51-59` allocates `g_all = np.full((64, n), nan)` and fills
only the columns a chunk covers — roughly half the signal is NaN **by design** (`slice_signal` builds
each chunk as falling-edge → next rising-edge, so every rising → next-falling interval is never covered).
`webui/server/serialize.py:241` block-averages that matrix with `.mean()`. At n = 626,400 the block
width is 2,447 columns, so every output cell contains at least one NaN, the whole averaged image is NaN,
`_finite_range` returns `None`, the range falls back to `[0.0, 1.0]`, and
`np.clip(nan, ...).astype(np.uint8)` yields zeros. The pane paints a uniform black 64 × 255 image and
reports `value_range: [0, 1]` — a number that is not true of the data.

Fix: `nanmean` over the block, and an all-NaN block must produce a **marked** cell, not a zero. If the
whole image is NaN the payload must say so in words and the pane must show that, not a black rectangle
(CLAUDE.md: never catch an error into a blank).

The test must use an image wide enough to force a block factor > 1 with NaN columns inside it — that is
precisely what the existing tests cannot see, because every one of them uses a 300-sample synthetic
with `min_chunk_samples` overridden to 20, where the block factor is 1.

### 2. `preprocessing.wavelet_transform` declares no `max_span_samples`  (A2-ii)

`Adapters/preprocessing_wavelet_transform.py:90`. On a 2,595,600-sample channel `g_all` alone is
64 × 2.6 M × 8 = 1.33 GB, and `compute_morse_wavelet_transform` allocates
`phi = np.zeros((64, N), dtype=complex)` = 2.66 GB for a long chunk on top of it. `slice_signal` emits
one chunk per falling edge, each running to the next rising edge, so the chunks overlap heavily and a
noisy real trace transforms far more total samples than the signal contains. Then
`Working/execution.py:384` caches the step (`STEP_CACHE_WRITE_THRESHOLD_S = 1.0`) and
`np.savez_compressed` re-serialises the 1.33 GB mostly-NaN array to disk on every run.

**This is a convention to follow, not a number to invent.** `Adapters/catalogue_gramian_gasf.py:48`
caps at 5,000 samples for a 200 MB matrix; derive this block's cap from the **same memory budget**,
declare it through the existing `max_span_samples` mechanism so the bridge refuses the span loudly with
the reason, and state the number and the arithmetic behind it in your report. Add
`preprocessing.wavelet_transform` to `webui/server/discovery.py::_complexity`'s heavy list so a plan
containing it carries a cost warning.

### 3. Two detection blocks disagree on the end-index convention  (A2, last line)

`Adapters/detection_summation_threshold.py:88` emits **inclusive** end indices (`xs[s:e+1]`);
`Adapters/detection_threshold.py:31-35` emits **half-open**. Span durations from the two blocks
therefore differ by one sample for the same event. Half-open is the repo's convention everywhere else,
so align `summation_threshold` to it. Grep for every consumer of its spans before you change it, and
pin the convention with a test asserting both blocks agree on a shared fixture.

### 4. Discovery's Runs page jumps 600 px every two seconds after you add a template  (`05-discovery.md` D1)

`webui/client/src/discovery/RunsPage.tsx:60` renders the loading card as a **sibling** of the page
content rather than an else-branch:

    {dx.loading && !dx.error && <Loading height={600} label="loading the session" />}
    {dx.scope && ( …toolbar, scope card, runs list… )}

`Loading` is a fixed-height card and `useSourced` (`api/seam.ts:39`) keeps `data` while setting
`loading: true` on reload — so the content is **not** replaced, a 600 px block is inserted above it, and
the page is shoved down and back. `discovery/session.ts:116-122` polls `base.reload()` every 2 s while
any run is `running`/`queued`, so this repeats for the entire life of the run. Fix the distinction
between a **first load** (no data yet — show the card) and a **reload** (data in hand — show a quiet
in-place indicator that does not change layout height). The same pattern is in `ComparePage.tsx:91`,
`SeedPage.tsx:116` and `StagesPage.tsx:78`; fix all four the same way.

### 5. Three faults in Discovery's Add-template modal  (D1, secondary)

- `AddTemplateModal.tsx:19-20`: `sel` is initialised to `['mp_discord_v3', 'spike_shape_v1']` and
  `focusQ` to `'mp_discord_v3'` — **fixture-era names that exist in no live registry** (the canonical
  nine are in `webui/server/templates.py`). The modal opens reading "0 templates selected" with both
  action buttons disabled, and the phantom names are never cleared.
- `sel` is never reset after a successful add (`add()` at :81-99 resets `busy` only), so reopening the
  modal shows previously-added templates in `sel`, silently un-checked at :156.
- `AddTemplateModal.tsx:30`: `inSessionReason` matches `r.key === t.name`, and
  `webui/server/discovery.py:1449-1455` gives a template's first run the bare template name as its run
  key — so **applying a template once makes it un-selectable for the rest of the session**, even against
  a different scope. The reason string it shows is therefore also wrong.

### 6. The header's "N need you" is a hardcoded constant, for the second time  (`07-review.md` R6)

`GET /api/review/counts` exists and says 160; the header renders a fixture `3`. This was found by a
critic in round 1, **reported fixed, and found again in round 2** — so the fix is not complete without a
test that fails if the constant comes back. Wire the header to the route and pin it.

### 7. Every Review inspector subtitle prints the literal words `run undefined · rank undefined`  (R8)

Visible in the user's screenshot: `run undefined · rank undefined of 30 by score`. Either supply the run
id and rank (the seeded discovery-run queue's run id **is** in the database — the provenance panel's
missing run id, round-2 P3, is the same gap) or omit the clause. Do not print `undefined` to a reader.

### 8. Review's pace is hardcoded `null`  (R9)

So "pace not yet measured" is permanent. Measure it — it is arithmetic over `review_audit.created_at`
for the queue's own un-undone rows. If you find that the timestamps cannot support it, remove the
affordance rather than leaving a permanent excuse on the page, and say which you did.

### 9. Tags never reach the database from Review  (R2)

`docs/prompts/wiring/reports/05-review.md` §12.1: the core and bridge paths are fixed and tested (a bare
list is routed to the category that defines each term), and **no component passes them**, so the
Annotate card's tags are a session label. Wire the component. **Rule 5 binds you**: tags on a human
annotation go through the human door, and nothing here may write a human verdict into a machine row.
**Classes are not in scope** — they have no store and that is Q-R2.

### 10. Three truthfulness fixes on the training blocks' payloads  (`04-analyse-training.md` T3)

These are bounded and carry no design decision. The cluster/classifier **redesign** is out of scope
(see the table above); these three are about a payload lying.

- `Adapters/catalogue_classifier.py:259` spreads `**params` flat into meta, while
  `webui/server/serialize.py:281-282`'s `keep` tuple whitelists a key `"params"` that is never present —
  so `n_estimators`, `class_weight`, `holdout_frac` and `random_state` are silently dropped from the
  model card. Carry them.
- `catalogue_classifier.py:143-149`: `_split` returns "train on everything" when a class has fewer than
  two members or the holdout would be smaller than the class count; `holdout_accuracy` becomes `None`
  and `Renderer.tsx:268` prints `holdout accuracy —` with no reason. Carry the reason and print it.
- `serialize.py` ships `labels[:5000]` with `capped: true`, and `GroupingR` (`Renderer.tsx:241-262`)
  never surfaces it — so past 5,000 windows the strip truncates silently. Surface it.

### 11. Analyse's cancel button has no `cancelling…` state  (`02-analyse-chain.md` A5)

Critic P1-6, left unfixed. Cancel is checked between steps and never mid-step, so there is a real
interval in which the user has clicked and nothing has happened yet. Say so.

### 12. Discovery's null marker prints no α and no correction  (`05-discovery.md` D5)

The marker is computed at a hard-coded α = 0.01 with no multiple-comparison correction, while Settings ›
Nulls holds keys the seeded search never reads. **Wiring the setting is out of scope** (it is a decision
about what the correction should be). **In scope: print the α actually used and the words
`correction: none`,** so the figure states its own rule. A statistic whose rule is unstated cannot be
falsified.

### 13. Explore's Morphology tag filter claims the database has no tags. It has 11,319.  (`01-explore.md` E1)

This is the worst factual claim on the list, and it was found while checking the user's "make it a
dropdown" note — the note is the symptom, this is the cause.

`getCorpusLive` (`api/explore.ts:47-70`) already builds the tag vocabulary and the per-channel tag
counts from `GET /api/channels/{id}/tags`, which it calls for **every channel**, and returns them with
`source: 'live'`. The rail then renders them while asserting they are fixtures. Verified against
`DATA/db/annotations.sqlite` on 2026-09-22 (read-only): `tag_vocabulary` holds **36 terms across 8
categories** (14 `element`, 4 `structure`, 4 `quality`, 3 each `corpus`/`species`/`provenance`/`status`,
2 `framing`), `annotation_tags` holds **11,319 rows** and `motif_entry_tags` **13,349**.

Four separate places say otherwise, and all four are false:

- `RightRail.tsx:51` renders a `<DemoTag />` chip beside "Morphology tag";
- its `info` text: *"This database has no tags yet: the counts are §0 demo canon."*;
- `RightRail.tsx:55` caption: *"no tags in this database · demo counts"*;
- the module docstring at `RightRail.tsx:3-4`: *"Detections from and Morphology tag have no bridge
  endpoint and are demo-backed"*.

Fix all four. The prop is named `demo` and typed `CorpusDemo` for historical reasons — **renaming it is
optional and cosmetic; do not let it grow into a refactor of the Corpus page.** Check `matching.demo`
and the `Header`'s `demo` prop on this page for the same staleness while you are there. If any part of
the tag path turns out genuinely not to be live, say which and leave that part's marker alone — a
`demo` chip that is true is the one thing here worth keeping.

### 14. The Morphology tag filter should be a dropdown  (E1, the user's original note)

`RightRail.tsx:52-54` renders one `Checkbox` per tag. Over a 36-term vocabulary that is unusable, which
is what prompted the note. **Use the existing `MultiPick`** (`explore/bits.tsx:13`) — the select-like
chip the same rail already uses for Runs (`:37`) and Methods (`:39`), with the same `allLabel` /
`N of M` behaviour. Reuse it; do not write a second picker (CLAUDE.md: prefer importing an existing
helper to writing a second one). Keep the per-tag counts visible in the open list, and group by
`tag_vocabulary.category` if `MultiPick` already supports grouping — if it does not, **do not add
grouping to it**; a flat sorted list is the no-decision outcome.

### 15. The Corpus coverage map ignores the run and method filters the route already serves  (`01-explore.md` E3)

`GET /api/coverage` takes `run=` and `method=`, the rail's run and method lists are live, and the Corpus
page fetches the unfiltered map anyway — with a note beside the filters admitting it. Pass them, and
delete the note. If the refetch-on-filter-change interacts badly with the verdict refetch that is
already wired (`verdicts=`), follow that existing pattern rather than inventing a second one.

### 16. `coverage.rows[].both` is a sum, labelled as an intersection  (`01-explore.md` E5)

`webui/server/corpus.py:187`: `"both": (ah + dh).tolist()` — annotation spans **plus** detection spans
per bin. A reader takes "both" to mean bins where both are present. The page's colour-by genuinely
means the sum, so **the number is right for the colour and wrong as a label**.

**Change the label, not the computation.** Changing what the `both` layer counts would change what the
Corpus map shows, and that is a design decision (Q-0.1) — this item is only about the map no longer
naming a sum after an intersection. Fix the field's docstring at `corpus.py:143` too, which makes the
same claim, and the client's `ColourBy` label in `explore/util.ts:10-11`.

### 17. Time-axis labels collide when no end ticks are requested  (`01-explore.md` E8)

`charts/primitives.tsx:14-36`: `TimeAxis` de-collides **only** when `ends` is true, and then only
against the two ends (a 48 px guard). In the default path (`ends = false`) there is no collision test at
all — `d3`'s `.ticks(n)` chooses positions without knowing how wide `fmtAxis` will render them, so on a
narrow surface with wide labels (hours to one decimal, e.g. `291.9 h`) adjacent labels overlap. The
`anchor` logic at `:28` stops a label rendering half off the surface; it does nothing about
label-versus-label.

Generalise the guard the `ends` branch already establishes so it applies on every axis: drop a tick
whose label would collide with the one before it. This is a shared primitive used by Explore **and**
Analyse, so re-run both workspaces' smoke states, not just Explore's.

## The gate

A change under `webui/` is done when all three pass (`CLAUDE.md`, "The UI gate"):

1. `npx tsc -b` and `npm run build` in `webui/client`;
2. `PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" webui/smoke.py --url http://127.0.0.1:8765`
   against a bridge started with `--sandbox`. It fails on any browser console or page error, any pane
   that did not paint, any unexpected server traceback, and a broken core flow;
3. the headless `pytest` suite, for anything Python outside `webui/`.

**Compare failure *sets*, not counts** — the baseline is `webui/PYTEST_GATE_FINAL.txt` and every merged
ticket adds tests. The gate is "nothing that passed before now fails". Item 3 changes a span convention
and item 1 changes a payload, so both will move tests that encode the old behaviour; if a test breaks
because you deliberately changed the behaviour it pins, **say so explicitly in the commit message**.

For items 1–3 also run the real evidence, not just the unit tests: run the Dehshibi template through
the bridge in `--sandbox` over a **short span (~4 h)** and over a **long one (~170 h)** from the same
channel, and put both stage-1 images in `webui/screenshots/fixup/A/`. Before the fix the long one is
uniformly black with `value_range: [0, 1]`; after it, it either paints or says in words why it cannot.
That pair of screenshots is the claim this prompt exists to make.

## Report

Write `docs/prompts/fixup/reports/A-no-decision-fixes.md`, in the house style of
`docs/prompts/wiring/reports/`:

- what was fixed, item by item, with the commit and the test that pins it;
- **the memory budget and the cap you derived for item 2**, with the arithmetic;
- **every item you left**, with the reason — especially any that turned out to need a decision after
  all, because that is a new entry for `QUESTIONS.md` and the user is answering it in parallel;
- any out-of-scope file you touched and why (CLAUDE.md requires each one justified);
- the gate output: the pytest failure set against the baseline, tsc/build, and the smoke result;
- a short chat summary at the end.

Then update the symptom rows you fixed in `docs/prompts/fixup/0*.md` to say so — a symptom list that
still lists a fixed symptom is the same lie this prompt is about.

# Report — Fixup AE: the Library hides what is under the noise floor, filters by what matters, and every plot is an index

Run 2026-10-04 on `main`, in the main checkout, written to run **beside `AD`** (wave 6). `AD` had not started while this
ran: no other bridge, no other commits, a clean tree throughout, so nothing here was built around in-flight files. Commit
prefix `fixup-ae:`.

The first commit, `c7ee4f4`, touches only `tests/`: **23 tests, all red on arrival** (no `view_filter`, no
`verdicts`, no `rose_reference`, no `resolve_spans`, `RULE_VERSION` silent on `rise_time_frac`).

Every bridge ran `--sandbox` on **port 8771** serving a **private client build** (`--dist <scratchpad>/dist-ae`). The
real `DATA/db/annotations.sqlite` was only ever read: once copied with the sqlite backup API into the scratchpad for the
measurements below, and copied by the sandbox bridges. Nothing was written to it.

## In plain words first

The Library is an album of motifs sorted into families. Most of it — the `drop_motifs10` import — is full of tiny
wiggles at or under the instrument's noise floor; looking at those is like looking at static on a radio. This prompt
did four things:

1. **The Library now hides what is under the noise floor, without deleting it** — like a photo album that tucks the
   blurry shots behind the good ones and tells you how many are tucked away. A bar at the top of Atlas, Recurrence and
   Family says *961 sub-floor members hidden*, splits that by where they were imported from, and has a *show sub-floor
   (961)* link that brings them all back.
2. **You can filter by the two things that really separate motifs**: how long the fall takes (a range, in seconds) and
   whether a window holds one fall or several (*pure only*).
3. **Every plot is clickable.** Click a family card and its members' real waveforms open right there, one small panel
   each; click a number in the Recurrence grid and you get exactly those members. *Open family page →* is one more click.
4. **Hand edits are saved.** *Remove from family*, *Make exemplar* and *+ tag* used to only pretend; they now write to
   the database, survive a reload, and survive a regroup.

Also: *judged* now uses the same verdict rules as Discovery (it read 0 % before), and every rose says what its 45° is.

**One thing needs your decision (§5, plain words first there).** The rose's 45° is meant to come from motifs a person
*accepted*. By the verdict rules you chose, 166 Library motifs count as accepted today — not 0 as the prompt expected —
because they sit inside 10-minute windows someone labelled *interesting*. Nobody has said yes to any motif one at a time
(0 Review verdicts). Is "inside a window a person called interesting" acceptance enough for setting the rose's scale?

---

## 1. What the floor hides, per store and per dataset

The rule (Q21, Q-X2.5): a member is hidden when **the detector's own `drop_depth_mv`** — else
`interrogation.event_shape`'s `event_amplitude_mv` — is under **its dataset's noise floor** (Settings › Datasets ›
*noise floor*; **0.1 mV** where empty, which is every dataset today). A member with neither depth is **unmeasured**:
shown, counted and badged. Nothing is deleted.

**One thing the prompt did not say and the data forced:** both depths were measured on the store's snippet, which the
store wrote as *samples × 1000* and called mV — true only for a recording in volts (Q-X2.8). The filter converts by the
recording's declared unit (`recordings.units`), and a member whose recording declares none is unmeasured, saying why.
Every Library dataset is declared V today, so the numbers below do not move; an mV file would have been compared 1000×
too large.

Measured on a backfilled copy of the real database (scratchpad; `measure_floor.py` / `.json` in the evidence folder),
the newest motif grouping **g-05**:

| import store | members | sub-floor (hidden) | unmeasured (shown) |
|---|---|---|---|
| `drop_motifs10` | 2,857 | **961 (33.6 %)** | 0 |
| `drop_motifs5` (the seed store) | 379 | **0** | 0 |
| not imported from a store | 3 | 0 | 3 |
| **all** | 3,239 | 961 | 3 |

| dataset | members | sub-floor |
|---|---|---|
| `Fig2A_dt0p1.csv` | 2,162 | **925 (42.8 %)** |
| `M2_aug_concat_fs1.mat` | 1,012 | 35 |
| `Mushroom_260720_…_fs1.mat` | 65 | 1 |

That is what Q-X2.5 predicted: about a third of `drop_motifs10`, none of the seed store. Over **every** Library member
(not only a grouping's): 1,095 of 3,603 sub-floor, all of them `drop_motifs10` (1,095 of 3,189 = 34.3 %, matching
`QUESTIONS.md`'s 34.3 % to the decimal); g-04: 771 of 2,545.

## 2. Families before → after

| | g-05 | g-04 |
|---|---|---|
| families before the view | 149 | 151 |
| after the floor | **145** | 143 |
| entirely under the floor (hidden from the grid, counted on the bar) | **4** (F-118, F-183, F-201, F-202) | 8 |
| after the floor + fall 10–300 s + *pure only* (the acceptance example) | 116 | 115 |
| members shown, that example | 705 of 3,239 (fall hid 1,460, impure hid 113) | 581 of 2,545 |

Families keep their colour whatever the view hides (the colour index is the family's place among all of them). The
three Fig2A families RQ6 was measured on shrink sharply: **F-130 55 → 11, F-119 40 → 7, F-39 40 → 26.**

`scale_band` is not a filter (Q22): a card shows its commonest band and that band's duration range as provenance
(`band 2 · 163-311 s`), with the rest behind the badge's title. The range is recomputed from the store's own events per
(span, band) — the label `passes6._band_label` writes — because the stored `scale_band_labels` are listed by span
*position* in a summary file, not beside the events.

**The backfill.** `is_pure`, the window's fall count (`purity`), `scale_band` and its range, and `rise_time_s` are not in
the real `motif_features` yet. `features.backfill_library` now completes a row that lacks a current measure instead of
skipping it (it used to test only "has any shape measure"); on the scratchpad copy it took 8.4 s for 3,599 entries and
wrote 92,344 values. **Filling the real table is yours** (`python scripts/fixup_d_backfill_features.py --real`, which
refuses the real file without `--real`). Until then *pure only* shows every member and counts them *purity not
recorded*, and the slideshow has no `[N falls]` flags; the floor and the fall range work today (those numbers are
already stored).

## 3. Every plot is an index

- **Atlas:** a click on a card opens that family's members **in place**, over the grid, in H's `EventSlideshow` — each
  member's own samples (from `/api/channels/{id}/window`, the stored span shaded with context either side), its own y
  and a scale bar, the `[N falls]` flag and red card where the window holds more than one fall, and each card's verdict
  with the rule that gave it. *Open family page →* and *close*. The grid and the rail do not move (`?members=F-03`).
- **Recurrence:** a click on a number opens that cell's members the same way (`?cellm=F-01|M2_aug_fs1:CH6_B1`); F-01's
  35 on CH6_B1 opened 35. Ticking a channel is the column header's checkbox (it always was; the cell click used to
  duplicate it).
- **Explore's maps (E6):** not done — left (§7).

## 4. *Judged*, before → after

*Judged* is now the one resolver's (L7): `Working/discovery/divergence.py::resolve_spans`, added beside
`channel_divergence` with the same helpers in the same order — **a verdict given in Review on the member's detection,
then the event-shaped row it matches under §4.6, then the reviewed windows its centre falls in** (Settings' containment
mode). It is imported by `Working/library/verdicts.py`; there is no second resolver. A test pins that a detection's span
resolves exactly as `channel_divergence` resolves the detection. The rule is printed beside the figure on the Family
page, each member says which rule judged it, and a card's tooltip says it.

| | exact span equality (before) | the resolver (after) |
|---|---|---|
| g-05, members judged | **3** of 3,239 | **197** (containment 194, extent 3) |
| g-04 | 3 of 2,545 | 168 (165 · 3) |
| every Library member | — | 206 (202 · 4); 166 human yes, 40 human no (32 not interesting, 8 artifact) |

All of them are M2_aug members inside the imported 10-minute CNN windows; there are **0 Review verdicts** in the real
database. A family's `artifact` badge now counts members whose resolved verdict is *artifact* (F-01: 2).

## 5. The rose reference — and the decision it needs

One core function (`Working/library/rose_reference.py`) computes the median |steepest slope| (event shape's
`max_slope_mv_s`, converted by the recording's unit) over **accepted** Library motifs, falling back below N accepted
(Settings › Analysis defaults `rose.min_accepted`, default 30) to every motif **above the noise floor**. It is stored as
four Analysis-defaults keys with its population (value, population, n, date) only when someone presses **Recompute and
store** on Settings › Analysis defaults (written to the audit log); until then roses read the computed value and say *not
stored yet*. Every rose prints it: the Slope page, the Sequence page and the `interrogation.event_shape` block (its
`rose_reference_mv_s` default is now 0 = *the stored reference*). With nothing to read (a headless run, a cluster job)
the rose uses its own events' median and says so — never `gradients.py:89`'s 1.0 mV/s silently. The bridge points the
module at the database it serves, so a sandbox bridge never reads the real file.

On the real data it reads:

> **45° = 0.788 mV/s · median steepest slope over human-accepted Library motifs, n = 162**

and the fallback would be **0.637 mV/s over 2,504 motifs above the floor**.

**In plain words.** The rose is a compass for how steep each fall is; its 45° line is the "typical" steepness, so you
can see at a glance which falls are sharper or gentler than usual. You decided the typical steepness should come only
from motifs a person said yes to, so noise and artifacts cannot drag it around. The prompt expected nobody had said yes
to any motif yet. But by the verdict rules you chose for *judged*, a motif that sits inside a 10-minute window someone
labelled *interesting* counts as a yes — and 166 do. It is like counting every photo taken in a room someone called
"nice" as a photo they liked.

- **(a) Keep it (as built).** Accepted = resolved to *interesting* or *seed* by the one resolver. The reference is
  0.788 mV/s from 162 M2_aug motifs, and it is consistent with *judged* everywhere else.
- **(b) Accepted = a verdict given on the motif itself** (Review, or an event-shaped row that matches it), not a window
  it falls in. Today that is at most 4 motifs (the four an event row resolves), so the rose falls back to 0.637 mV/s over everything above the floor and says
  so, until you have reviewed 30. A one-line change in `rose_reference.compute`.

**Recommendation: (b).** A 10-minute window labelled interesting says *something* in those ten minutes was worth a look,
not that every fall in them is a good example; and the population is one recording (M2_aug), which would set the scale
for Fig2A too. Not changed without your word; recorded under *Left*.

## 6. Hand edits written (L4)

*Remove from family* (rail and batch), *Restore*, *Make exemplar*, `+ tag` (rail and batch), an untag of a tag added by
hand, and an added member's *Undo* go through `POST` / `DELETE /api/library/hand-edits`, and the family is read again.
The `not wired yet:` toasts and the page's in-memory copy of the edits are gone; the removed strip and the hand-edit
counts are the read's. A tag the importer wrote cannot be taken off here (it is the entry's own). The class select and
the batch *Assign class* are disabled and say why: they wait for the Review-behaviour prompt's classes.

**Found and fixed: hand edits did not survive a regroup.** The regroup job only *counts* edits
(`engine._hand_edit_outcome`) and a saved grouping holds the computed assignments, while the reads applied only edits
recorded against the same grouping — so a member removed in g-05 came straight back in a regrouped g-07 (walked: the
job reported *applies 1* and the member was still the medoid of its new family). The reads now apply **every** active
edit through `hand_edits.apply_to_assignment`, which matches an edit's family by its medoid's content hash (labels are
renumbered by every grouping) and orphans the rest. Route test: a removal follows F-01 into a regrouping that relabels
it F-07. Walked in the browser: remove → `hand_edits` row #1 → gone from the grid, in the removed strip → still gone after
a reload → *Restore* sets `active = 0` and it is back.

**A corner worth knowing:** removing a family's *medoid* makes the edit's family key that same member's hash (a family is
identified by its medoid). Across a regroup the edit then applies to whichever family that member is the medoid of — the
same family by identity, so the behaviour is right, but the family loses its medoid on the page.

## 7. `RULE_VERSION` and `rise_time_s` (E §8.4)

`features.RULE_VERSION` names `rise_time_frac=0.1`. The backfill completes rows missing `rise_time_s` (null for a drop),
so once it is run on the real table the Interrogation route stops measuring it per request — its fill-the-gap branch is
left in place for rows the backfill has not reached.

## 8. Items left

1. **The accepted population for the rose** (§5) — your decision; (b) recommended.
2. **The real backfill** (§2) — `scripts/fixup_d_backfill_features.py --real`, yours to run. Until then *pure only* and
   the `[N falls]` flag have nothing to read.
3. **Explore's maps (E6)** do not open members in place. They draw windows and spans, not families; the in-place
   component takes a family id (and optionally a cell), so wiring Explore needs a member-list read keyed by span — not a
   small step from this component.
4. **Sequence families** still count *judged* by exact span equality (`_one_sequence_family`), and the Library's
   *matched members* (`_matched_members`, `V`'s) too. Not on the Atlas/Family/Recurrence path this prompt owns.
5. **The step cache keys `interrogation.event_shape` on `rose_reference_mv_s = 0`**, so a chain run cached before a
   *Recompute* keeps its old rose until the step re-runs. The rose prints the reference it used, so it is visible, not
   silent.
6. **The Atlas's *≥ 10 members* filter** now applies after the view, so a family that the floor shrinks under ten drops
   out of the grid under that filter (it is counted in the scope caption: "37 hidden by ≥ 10 members"). This is the
   existing L8 default, not new.
7. The view lives per viewer (session state); `?floor=0`, `?fall=10-300`, `?pure=1` set it from a link.

## 9. Out-of-scope files touched

| file | why |
|---|---|
| `Working/discovery/divergence.py` | `resolve_spans` added beside `channel_divergence` (additive): the one resolver's door for a span that is not a run's detection. Nothing existing changed |
| `webui/server/runtime.py` | points `rose_reference.DB_PATH` at the database the bridge serves (and restores it), like the step-cache redirect — otherwise the block's default would read the real file under a sandbox bridge |
| `webui/server/interrogation_routes.py` | the family and sequence roses use the stored reference and print it ("every rose prints it") |
| `webui/client/src/kit/Rose.tsx` | prints `rose.reference` when the payload carries it |
| `webui/client/src/library/MemberSlideshow.tsx` | new; the in-place slideshow the Atlas and Recurrence share |
| `webui/client/src/settings/AnalysisDefaultsPage.tsx` | the Settings rose keys (in the prompt's list as "Settings › Analysis defaults' rose keys"; named here because it is a page) |
| `tests/test_library_view_filter.py`, `test_library_verdicts.py`, `test_rose_reference.py`, `test_webui_library_view.py` | new |

Shared files, append-only: `webui/client/src/api.ts` (one appended block, its own commit `b66298b`),
`webui/client/src/api/library.ts` (three reads take an optional view; one new read), `webui/server/library.py`
(appended helpers and routes; `_families_for` now delegates to the view state, `_family_detail` reads it, the three
read routes take the view parameters, and the two exports stay unfiltered — *a record, not a view*; none of `AD`'s
functions touched). `family_recurrence` is untouched: the seam is the caller, which now hands it above-floor member ids.
A request to `AD` (`requests/AE-to-AD-noise-floor-helper.md`) points it at `view_filter.dataset_floors` so the Library's
floor and the cross-channel test's floor cannot drift apart.

## 10. The gate

The machine was mine throughout (no `AD` bridge or process), so smoke and pytest never overlapped.

| gate | result |
|---|---|
| `npx tsc -b` + `npm run build` (shared `dist`, at the end) | clean |
| `webui/smoke.py`, full walk, fresh `--sandbox` bridge on a copy of the real database, port 8771, private build | **639 screenshots, 8 failures, 0 console/page errors, 0 unexpected tracebacks** |
| the 8 | the **5 standing** (four Settings registration states, `discovery.runs--default`); **2 screenshot-path errors** — `review.inspector--padding +/-30 s …` and `+/-120 s …` carry a `/` in the state name, so the PNG path names a folder that does not exist (`V` reported the same pair; not this prompt's); **1 cold-start flake**, `analyse.interrogation.slope--default` (500 ms allowance, no wait) |
| that flake | partly mine: before a rose reference is stored every Slope read recomputed it (~0.5 s). Fixed (`5e8b7ef`, cached until its inputs move), then a **cold walk of all 58 interrogation states on a fresh bridge: 0 failures**, and the `zzz*` states (W, X and AE's 12) on the same fresh bridge: **30 / 30** |
| earlier walk (before the fixes) | W's `fixup-w-member-edges-show-lag-and-r` and `fixup-w-excluding-artifacts` failed **because of this prompt, deliberately**: `m-1295` and F-130's artifact-pair members are under the floor, so the default view hides them. W measured every member, so those W states now set `?floor=0` (`a7167c6`, says so in the message). AE's first state wrongly required scale-band badges, which exist only after the backfill |
| `pytest -n 4` (conda) | **2,236 passed / 23 skipped / 0 failed** in 5 m 18 s, against 2,212 / 22 / 0; failure set empty. +24 = this prompt's core tests; +1 skip = `test_webui_library_view.py`, which needs FastAPI |
| under `webui/.venv` | `test_webui_library_view.py` 9 passed; `test_webui_library.py` + `_edges.py` 52 passed (3 xpassed, pre-existing); interrogation shape / slope anatomy / sequence shape 20 passed |
| `test_import_boundaries.py`, `test_block_standard.py` | 150 passed |

Evidence: `webui/screenshots/fixup/AE/` — the twelve AE smoke states from the gate walk, the browser walk's shots, and the
measurement script with its output.

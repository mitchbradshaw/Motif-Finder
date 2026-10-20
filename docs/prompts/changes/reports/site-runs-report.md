# site-runs — report (branch `site/runs`, from main f445468)

## In plain words

The Discovery Runs page now tells the truth while it is still working things out. "Send 0 unjudged" was wrong:
the page put up an empty answer it got before the runs had loaded, and kept it there for the eight minutes the real
scores took. Now the scoreboard says "working out the scores…", and the Send button gets its count from a quick
separate read (about 0.2 s). Each run row has a fixed layout, so names are readable and the buttons no longer
overlap. The ~50 eye links are now one "Runs drawn: N of M" button. The scoreboard scrolls after ten runs. Cross-channel's
*Apply a template* opens Discovery on the right recording and channels. The session name follows the recording.

## Assumed

- **Item 5, which links are written.** Only a link that names channels (`?channels=`, optionally with
  `?recording=`) is written to the session. A `?recording=` on its own stays a view, as before. Why: the
  `held-out-refused` smoke states open `?recording=M4_aug…`, and with the held-out lock OFF (it is off in the real
  DB copy) writing that link would move the whole walk's session onto M4. A held-out recording is never written.
- **Item 5, the section.** A link to *another* recording sends no section, so the session the bridge opens there
  keeps its own section (the bridge clamps it to the recording). Sending the old recording's hours would overwrite
  that session's section; it did on the first version (`demo · talk` became 0–480 h on my copy). A link to the same
  recording keeps the current section.
- **Item 5, during the write.** While a link is being written, and after a write that opened another session
  until that session's runs are read, the page shows its loading layout. It mounts no card. Otherwise reads go
  out on a scope the bridge is leaving and come back 404.
- **Item 6, the name.** A new session is called the dataset's display name (Settings › Datasets). When there is
  none, it is the file stem (`CO_fs2`, not `CO_fs2.mat`). Existing rows keep their names.
- **Item 4, what the count counts.** It counts the run's real detections (paired surrogates left out) that carry no
  adjudication, over the **whole run**. That is what *Send* puts in the queue, because the queue is a filter over the
  run ids. The scoreboard's figure is limited to the scope, so the two can differ when the scope is smaller than the
  run. Review's own count after the send (overlap sets, verdicts carried over) is still the one in the toast.
- **Item 2, ids.** The popover's checkboxes are `fires-check-<key>`. A drawn row keeps its eye, `fires-eye-<key>`.
  `fires-show-all` and `fires-hide-all` live in the popover. A second `fires-show-all` ("show all N") sits on the
  line under the rows while nothing is drawn, so `smoke.py`'s discovery flow, which clicks it without opening
  anything, works unchanged. `fires-hidden` is now that line.

## Item by item

### 5 — Apply template from Cross-channel (`ecfd26b`, follow-up `c2a0a71`)
- **Found:** the link sent channel **ids** and no recording. `useDiscovery` only overlaid the query on the client's
  copy of the scope, so every read asked the session's recording for channels named `667…`.
- **Changed:**
  - The `act-template` line in `CrossChannelPage.tsx` (the one line this agent owns there) sends
    `recording=<key>&channels=<names>`.
  - New pure `discovery/scopeLink.ts` (`resolveScopeLink`, `scopeFromSession`) checks the link: every name must be
    a channel of the recording, otherwise it refuses in words.
  - `session.ts` writes the link through `putScope` (the Scope card's write; `putScopeLink` is the same write with
    an optional section) and then clears `recording` and `channels` from the URL.
  - The Apply-template modal waits until the write has landed.
  - A refused link shows `scope-link-refused` ("667, 668 are not channels of CO_fs2.mat — the link was not applied;
    the session keeps its scope") and nothing is sent.
- **Checked on the copy:** M2_aug → CO_fs2 → M2_aug through the link. No 404, the modal opens on the new scope,
  the URL is cleared, and the toolbar names the opened session (`CO_fs2_rq4`, `demo · talk`).

### 6 — The session's name (`ecfd26b`)
- `setScope` takes `putScope`'s answer (`scopeFromSession(p.session)`) instead of merging its patch into its own
  copy, so a change of recording shows the opened session's name.
- The bridge names new sessions after the dataset (`_session_name`, `webui/server/discovery.py`).
- The scope summary chip has lost its chevron. It is still a button that jumps to the Scope card.

### 3 — Scoreboard scroll (`1335445`)
- `SCORE_ROWS_VISIBLE = 10`. The table sits in `.dsc-score-scroll` (`data-testid="scoreboard-scroll"`). Its
  max-height is measured from the drawn header plus ten times the first run row's height. The header is sticky.
  Expanded channel rows scroll with the rest, and sorting is untouched.
- **On the copy (52 runs):** 496 px visible of 2468 px. After scrolling 200 px the header is still at the top
  (offset 0).

### 4 — "Send 0 unjudged" (`1335445`)
- **Cause: suspect 1.** The scoreboard read itself returns every run: 52 rows for 52 runs on the copy. On the first
  render the runs are not loaded yet, so the read goes out with no run keys and answers `[]` in 0.4 s. `useSourced`
  keeps the last answer on screen while the next read is out. That `[]` stood for the whole cold read, so the page
  showed "no finished run on this scope yet" and "Send 0".
- **Timings,** on the backup copy of the real database (way 1), with session 2 (`M2_aug_concat_fs1 screen`:
  16 channels, 52 done runs, section 0–721 h) opened on the copy:

  | read | time |
  |---|---|
  | `/api/discovery/scoreboard`, no run keys | 0.38 s → `[]` |
  | `/api/discovery/scoreboard`, 52 runs × 16 ch, **cold** (fresh bridge; the corpus-map and template warms running alongside) | **461 s** |
  | the same, warm | 3.3 s |
  | a later cold read in the browser, warms finished | ≈ 2–3 min |
  | **new** `/api/discovery/runs/{key}/unjudged`, cold and warm, five runs | 0.17–0.42 s |
  | Send button counted, from page load | 4–9 s (page load included; the count itself ≈ 1 s) |

- **Fix:**
  - No scoreboard read goes out before the runs are in.
  - Every answer is tagged with the key it was read for (new pure `discovery/scoreRead.ts`), and any other key
    reads null. A refresh with the same key keeps its rows.
  - The table shows a `scores-working` row ("working out the scores — … can take minutes the first time") above any
    other rows, never "no finished run".
  - The Send count comes from the new route: two COUNTs, no scoring, and no existing route was changed. While the
    count is out, the button is disabled with "counting the unjudged detections…" (`data-counting="1"`). Once it
    lands, it reads e.g. "Send 11 unjudged to Review".

### 1 — Run rows (`cf0e423`)
- The row is a grid:
  - line 1: the glyph, the name (two lines at most, then an ellipsis, the full name in `title`), then the A/B box
    and × at the right;
  - lines 2–4: the kind badge and detail, the status, the coverage strip (it wraps);
  - line 5 (`.dsc-run-actions`, only when there is one): Run on the missing N, Import results, Retry, Report,
    Open in Jobs, left-aligned and compact.
- The band-set row and the Seed page's draft row share the classes and take the same layout. **No SeedPage edit
  is needed.** I could not look at the draft row: Seed search needs signals, and the DB copy has none.
- **Checked on the copy** (53 rows, the 274 px list at 1376 and 1024 px windows): no part of any row overlaps
  another or leaves the row.

### 2 — Runs drawn picker (`f26ffd3`)
- One `PopoverButton` in the card head, "Runs drawn: N of 52 ▾" (`fires-picker`). It opens a popover
  (`fires-picker-popover`) with:
  - a search box (`fires-picker-search`);
  - show all and hide all;
  - the runs grouped as templates, seed searches, and one folded `<details>` per band set (new pure
    `discovery/firesPicker.ts`);
  - per run, a checkbox with its colour swatch and found count. Two runs with the same label also show their key.
- **On the copy:** two groups of 52 runs; "drop" filters to 7; show all draws 18,538 bins in 8.8 s; hiding a row by
  its eye reads "Runs drawn: 51 of 52".

## Tests (red commit, then green)

| file | interpreter | red | green |
|---|---|---|---|
| `tests/test_site_runs_scope_link.py` (node runs the pure `.ts` helpers; the rest are source pins) | conda | `18a1955`: 15 failed; `27d8624`: 4 failed; `c8d8b16`: 2 failed; `6d64361`: 4 failed | 24 passed |
| `tests/test_webui_site_runs.py` (session name; unjudged count found − judged, no scoring, surrogates out; unknown run 404) | webui/.venv | `18a1955`: 1 failed (`"other screen"`); `27d8624`: 1 failed (no such route) | 5 passed |
| `tests/test_import_boundaries.py`, `tests/test_webui_night_b_links.py` | conda | — | pass (36 with the first file) |
| `tests/test_webui_discovery.py`, `tests/test_webui_discovery_runlist.py` | webui/.venv | — | 83 passed, 1 failed — see below |

The one failure, `test_webui_discovery.py::test_the_map_lists_the_applied_run_as_one_row_over_every_channel_of_the_dataset`
(`m["datasets"] == []`), **also fails with main's `discovery.py` put back**. So it comes before this branch,
almost certainly from the level-3 map cache (7ceea4f: the first answer is the stale one). That is MAP's area.

`node …/tsc -b` and `node …/vite.js build` pass from `webui/client`.

## Smoke states

`webui/smoke_pages/zzzzzzzzzzz_site_runs.json` (new):
- `site-runs-run-row-actions-on-their-own-line`: with a done template run, `.dsc-run-actions [data-testid^="report-"]`
  inside the row, and the name `b[title]`.
- `site-runs-runs-drawn-picker`: the button opens a popover with search, show all, hide all, and `fires-check-*`
  rows. No old `.dsc-fires-eye.off` wall.
- `site-runs-send-count-is-its-own-read`: `send-to-review[data-counting="0"]` within 30 s.
- `site-runs-scoreboard-scrolls-under-a-sticky-header`: waits up to 600 s for score rows (or the empty line), then
  shows `scoreboard-scroll` with its header. `scores-working` is gone.
- `site-runs-link-with-channel-ids-is-refused`: `?modal=add-template&channels=667,668,669,666` shows
  `scope-link-refused` and no modal.
- `site-runs-session-chip-without-chevron`: the session and scope chips are present.

`webui/smoke_pages/zzzzzzzzzzzz_site_runs_link.json` (new, twelve z's, so it sorts after every other file because it
**writes** the session scope):
- `site-runs-apply-template-link-moves-the-session`: on `explore/cross-channel/4`, click `act-template`. The
  Apply-template modal opens on Discovery with no `scope-link-refused` and no load-failed card. **The session is then
  on channel 4's recording.**
- Note: `--only zzzzzzzzzzz_site_runs` does not match this file, so walk it with
  `--only zzzzzzzzzzzz_site_runs_link`.

Edited in place:
- `discovery.json`, `discovery.runs/default`: it now clicks `fires-picker`, then `fires-show-all` inside
  `fires-picker-popover`, then presses Escape, before it expects drawn bins. Show all now lives in the popover.

### Walked on my sandbox bridge over the real-DB copy (`--pages-only`)

- **My unit:** 5 of 6 states ok. The run-row state renders, but the copy has no `.npy`, so the scope strips 500 on
  first load. The same missing-signal errors fail `a1_coverage`'s first state on the same copy.
- **`a1_ar_speed`:** `ar-templates-open-under-a-second` times out. The template rows take 4–5 s to appear on the
  real-DB copy. Neither the templates route nor AddTemplateModal is touched by this branch, and the state was
  written against the walk DB. Please judge it on the gate sandbox.
- **`a1_polish_discovery`:** the seed state needs signals. The runs state passes apart from the `.npy` console
  errors.

## Shared-file edits (all append-only)

- `webui/client/src/api.ts`: adds `DiscRunUnjudged` and `getDiscoveryRunUnjudged`.
- `webui/client/src/api/discovery.ts`:
  - appended `putScopeLink`, `RunUnjudged` and `getRunUnjudged`, and one import line;
  - `scopeLink.ts` replaces the `fixtureScope` literal in `session.ts`, not anything in this file.
- `webui/server/discovery.py` (RUNS-owned for session, scoreboard and apply):
  - `_session_name` is new; `_new_session` uses it;
  - the route `GET /api/discovery/runs/{run_key}/unjudged` is new;
  - no existing route's behaviour changed.
- `CrossChannelPage.tsx`: the one `act-template` line.

## For the manager

- **Demo path (W2: save a template, then Discovery › Apply template on M2_aug channels, then Review):**
  - The apply route, the run keying and `Working/` are untouched.
  - The modal behaves as before unless the URL carries a channels link.
  - The Send button now counts on its own (≈ 0.2 s) instead of waiting for the scoreboard.
- **Apply-template estimate about 5× low (FYI, not changed):**
  - For a non-windowed plan, `Working/discovery/fanout.py` `preview()` (≈ line 639) returns
    `estimate_s = per_channel * n_channels`, which leaves out the null draws.
  - The windowed branch (≈ line 619) multiplies by `1 + draws`.
  - With a 20-draw null on 5 channels, the run also does 100 surrogate runs, which the estimate does not count.
- **Seed page draft row:** not looked at (no signals on the copy). It shares the run-row markup, so it should show
  the new layout.
- **Existing race, not fixed:** a Scope-card change of recording can still send reads that are already in flight to
  the new session. The page now shows its loading layout until the new session's runs land, which covers the reads
  that start after the write.

## Commits
```
c4e8376 site-runs: smoke states - zzzzzzzzzzz_site_runs (six) and zzzzzzzzzzzz_site_runs_link (the link write, sorted last)
c2a0a71 site-runs: item 5 follow-up - no read on a scope the bridge is leaving, and the opened session keeps its section
f26ffd3 site-runs: item 2 - Runs drawn: N of M, a picker instead of a wall of eye links
6d64361 site-runs: red - item 2, the runs-drawn picker
cf0e423 site-runs: item 1 - a run row is five lines, its small actions on a line of their own
c8d8b16 site-runs: red - item 1, a run row's actions on their own line and a two-line name
1335445 site-runs: items 3 and 4 - the scoreboard scrolls past ten runs, says when it is working, and Send counts on its own
27d8624 site-runs: red - items 3 and 4, the scoreboard's stale empty answer, the Send count and the scroll
ecfd26b site-runs: items 5 and 6 - a deep-linked scope becomes the session's, and the session shown is the bridge's
18a1955 site-runs: red - items 5 and 6, the deep-linked scope and the session's name
```

## Fix round (the critic's F1–F5)

Commits: `949bb22` red, `5538031` F1, `2926589` F2–F5.

- **F1: the Send count is now exactly what Send would queue.**
  - `GET /api/discovery/runs/{key}/unjudged` returns `queue_counts` of the run's open queue when there is one. It finds it with `find_open_queue` and the send's own kind and filter `{"run_ids": ids}`.
  - When there is no open queue, it returns the same count from the new `Working/review/queues.py` `unwritten_counts`. That uses the same `_detection_structure` (overlap sets, with items a human verdict already covers left out), the same cap and the same rule for "judged". It writes nothing: no `review_queues` row and no structure row.
  - The structure is cached in memory the way a written queue's is. `_cached_structure` gains an optional `cache_key`; the queue id is still the default. Both edits are additive and outside my declared files (`Working/review/queues.py`), and no run reads that file.
  - The answer is `{total, judged, unjudged, queueId}`. The button's words are now "N events Review would put to you · M judged", and a true 0 reads "Review would ask about none" with the button disabled.
  - Test: the route's answer before a send equals the send's own count, on a case with an overlap set, a prior human verdict and an adjudication; the count wrote no queue; after the send the route answers from the open queue. Run with webui/.venv. `tests/test_review_queue*.py` and `test_review_carry_core.py` pass (94, conda).
  - **On the real-DB copy, all 52 done runs:**
    - `dip_search_allch` reads 0 (it has open queue 7, so 102 events, all 102 judged).
    - Cold reads take 0.4–2 s for most runs. The largest runs take 18–42 s (`deconvolved_troughs__recovery_half_s_60` 41.6 s, `OASIS_Deconvolution__threshold_3` 41.4 s, `deconvolved_troughs_2` 25.9 s). Median 1.7 s; a warm repeat takes 0.4 s. "counting…" covers the wait.
    - **Risk:** each cold count keeps a structure in the in-memory queue-structure cache, which is bounded by `_STRUCTURE_CACHE_MAX`. On a 1 GB-free machine, the 100k+ runs' structures are real memory.
- **F2: a rejected link write no longer hangs the page.**
  - A rejected `putScopeLink` is held as `linkError` and said through the `scope-link-refused` callout. Its button keeps the session's scope and clears the URL keys and the error.
  - `linkWriting` is false while the error is held, so the page stops showing its loading layout.
  - Test: source pins in `test_site_runs_scope_link.py`.
  - Checked in the browser with the PUT forced to 500: the callout reads "the bridge did not take the link's scope — forced — the session keeps its scope". The toolbar mounts, the modal stays shut and the pending line is gone. The button clears the keys and the callout.
- **F3: `webui/smoke.py` waits for the count before reading the Send label.** This file is outside my list; the manager allowed the edit. In the discovery → review flow it waits for `[data-testid="send-to-review"]:not([data-counting="1"])` (60 s) before reading the label, at the first send and at the seed run's send. That is two added lines; nothing else changed.
- **F4: the smoke states now measure, not pin.**
  - New state `site-runs-run-row-geometry-at-1024` narrows the page to a 1024 px window's width (960 px beside the rail). An `eval` then checks every run row: no two of its parts (name, meta, status, coverage, pick, ×, action buttons) overlap, and none leaves the row. It marks `runs-list[data-geometry=ok|bad]`, with the reasons in `data-geometry-detail`. Nine `no_overlap` pairs measure the walk's own `{run:a}` row.
  - The scoreboard state gains an `eval` that marks `scoreboard-scroll[data-check=ok|bad]`. It checks that more than ten runs scroll in a box no taller than the header plus ten rows, and that the header stays at the top after a scroll.
  - Only existing check kinds are used (`eval`, `expect`, `no_overlap`). The other states in the file restore the page width first, and it also goes when the page unmounts.
  - **On the copy:** geometry `ok` over 53 rows at 960 px. The scroll eval was **not** run end to end: the cold scoreboard did not land within 15 min on the loaded machine (the template warm took 547 s alongside it). The earlier manual measurement (496 of 2468 px, header at offset 0 after a 200 px scroll) is what it checks.
- **F5:** restored the indent in `RunsPage.tsx`; removed the dead `.dsc-run-jobs`, `.dsc-run-retry` and `.dsc-run-jobs-link` rules; dropped the unused `scoresLoading` export.

Gates: `tests/test_site_runs_scope_link.py` 27 passed (conda); `tests/test_webui_site_runs.py` 5 passed (webui/.venv); `tsc -b` and `vite build` pass. Bridge stopped.

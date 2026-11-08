# Library review and faster verdict saves — 8 November 2026

The unanswered shape proposals are now in one [review queue, 46](http://127.0.0.1:8765/#/review/queue/46).
It contains **322 g-11 representatives**, of which the queue resolver recognises five as already covered by earlier
human labels, leaving **317 to adjudicate**. No new human verdict was invented when making the queue.

## Selection and statistics

The selection is the unanswered representatives from the historical, deduplicated g-11 grouping: 219 assigned
shape-family members and 103 omitted shapes. All are on M2_aug. Family links and original recording/span coordinates
are retained in `C:/Users/mmebr/Documents/CNN/DATA/derived/library_unjudged_review/members.csv`.

Using the event representatives avoids presenting repeated fall/bottom/recovery fragments from the old motif stores
as independent events. Inactive reishi imports are outside the previously agreed thesis scope. This queue is a
review of selected Library proposals; it is not a random recording sample or another blinded detector experiment.

Use **interesting** to accept a member, or not interesting / artifact / unsure as appropriate. These members are
already in the Library. The existing family-review writer saves the answers as `library_review` annotations.
`scripts/thesis/accepted_catalogue.py` already collects these accepted labels, so the normal catalogue refresh
will include them, merge repeated observations of the same physical occurrence, and retain the queue/source links.
Boundary checks still precede final waveform-duration statistics. Keep this cohort identifiable in pooled summaries
and separate from the blind panel when reporting acceptance rates.

The existing RQ2 queue 38 is preserved: the final verification still reads 164 judged / 916 presentations. Its data
are on other recording groups, so creating the M2_aug Library queue does not label its unfinished presentations.

Queue creation is reproducible with `scripts/thesis/review_unjudged_library.py`. It used a consistent SQLite backup
before writing queue metadata: `DATA/db/backups/library_unjudged_20261108_152650.sqlite`. The queue's review answers,
as with other family queues, land in annotations rather than machine detections.

After finishing the reviews, refresh with the commands in `../accepted_catalogue/REPORT.md`. Do not continuously
recompute the thesis statistics after individual keypresses.

## What was slowing the saves

The Review core read every adjudication, class and carried-source relationship for each candidate and prefetched
candidate. Its count endpoint also read every adjudicated detection, even for a queue containing only 918 detections.
A profile attributed about 0.25 of a 0.43-second candidate read to that unrelated history overlay.

The overlay, tags and count reads now seek the current queue's detection IDs through the existing database index.
Carried sources outside the queue remain linked correctly. Changes and undo are read fresh; no human verdict cache
was introduced. Large queues retain a single-scan fallback rather than generating thousands of tiny queries.

In a controlled copy of the current database, three save/undo repetitions per version gave:

| Measurement | Before | After |
|---|---:|---:|
| Median verdict-save response | 0.1847 s | 0.0351 s |
| Relative improvement | | 5.26× |

The before/after saves produced identical queue counts. Synthetic judgements and undo records existed only in the
sandbox copy. This is a small local benchmark, not a promise of the same end-to-end speed on every laptop load.

Live HTTP checks after deployment read representative candidates in 0.10–0.15 s, versus 0.42–0.54 s warm before;
the count requests fell from about 0.24 s to 0.03–0.06 s. Memory pressure also improved during the session, so the
controlled save comparison is the cleaner estimate of the code change.

## Startup load and laptop processes

Initially Windows reported only about 0.5 GB available out of roughly 14 GB. Chrome had several large renderer
processes. The website also normally starts optional corpus-map/template-score warming and a matrix-profile JIT
warm-up; a previous startup log showed template warming taking over eight minutes.

The website was restarted with:

```powershell
webui/.venv/Scripts/python.exe webui/run_server.py --project --port 8765 --no-warmup
```

This skips those optional startup jobs for the review session. Analyses and maps remain available on demand. The
normal startup behaviour is unchanged when the new flag is absent. The production server is running, and the
temporary benchmark/browser-test sandbox has been stopped. The boundary viewer on port 8767 is a small idle helper.

If memory pressure recurs, Chrome's Task Manager (**Shift+Esc**) can identify unused tabs by memory footprint.
Close unused plot/chart/browser tabs rather than stopping the MycoWave Python server. No model training or local
HPC job was found to stop during the process audit. The app reported zero running jobs at final verification.

## Verification

- Core queue/cache/carry/verdict tests: **122 passed**.
- Review API, undo, startup flag and private-build selection tests: **41 passed**.
- Additional family-queue, import-boundary and queue tests: **27 passed**, overlapping the core coverage above.
- TypeScript type-check and a private Vite production build passed. The shared production frontend bundle was not
  overwritten; this change affects the backend.
- Focused browser checks on both current queues passed: the waveform rendered, a sandbox verdict saved and advanced,
  and Ctrl-Z restored the original counts. Observed save-to-next-card times were 0.184 s for queue 38 and 0.315 s for
  queue 46, with no page errors. These synthetic browser judgements never touched the project database.
- The full legacy Review page-state manifest still reports 12 failures around its historical deep links/extraction
  fixtures. It has no browser errors or unexpected server tracebacks. Representative old links return identical
  item/rank/count data under the original and changed core; several historical detections now have no served rank.
  The current queues are covered by the separate focused check rather than claiming that the legacy manifest passed.

Detailed evidence is kept under `C:/Users/mmebr/Documents/CNN/DATA/derived/review_speed/`:
`baseline_http.json`, `after_http.json`, `save_benchmark.json`, `focused_browser_check.json`,
`legacy_smoke_baseline.json`, `smoke_shots/smoke-result.json` and `final_status.json`.

The implementation and tests are saved in the thesis worktree and deployed to main's working files. No commit,
classifier training or thesis PDF build was made for this follow-up.

# Fixup AQ — finish Explore › Cross-channel: the rows must plot, the window picker must pick

**Written 2026-10-13 from the researcher's screenshot and list ("implement channel compare in explore page":
by that they mean *finishing this page* — "the channels don't appear to be plotting, the span selector doesn't
work, etc."). Not run yet.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `webui/client/src/explore/CrossChannelPage.tsx` (its header, every line), `webui/client/src/explore/crossScale.ts`
(read its header before changing how a row is drawn — it says why `centred` is the default), `webui/server/explore_routes.py`
(`GET /api/cross/{id}`), `Working/cross_channel.py` (`classify_waveforms`) and `docs/rq_roundA/RQ6-recurrence-across-channels.md`.

Commit prefix `fixup-aq:`. Test-first; the first commit touches only `tests/` and must fail. **Smoke against your own
sandbox bridge on your own port and a private dist** (`webui/run_server.py --port 87NN --sandbox --dist …`); never
against the researcher's `--project` bridge on 8765.

## In plain words

This page is meant to show the same stretch of time on several channels, one above the other, so you can see whether
an event on one channel also happened on the others — and if so, which one moved first. The researcher opened it and
saw six nearly flat lines, a window picker that did nothing, and a table of numbers that disagree with the picture.
The job is to make the page tell the truth and respond to its controls, not to add anything to it.

## What the screenshot shows (2026-10-13, CH2_A1 reference, 6 of 16 channels, "interesting span at 0.78 h ± 20 s")

| # | Symptom | Where to look |
|---|---|---|
| X1 | **Every row is drawn almost flat.** The y note says *shared gain · 20.74 mV per row*, yet each row prints its own range as 5–10 mV (e.g. `-1532.00 … -1526.64 mV`). So each trace uses a quarter of its row at best. 20.74 matches no row's printed range: find where the gain comes from (padded window? stored volts × factor? the reference row's unclipped extent?) and make the gain and the printed ranges agree. The rule to keep: *waveforms never normalised*, one gain shared by the drawn rows, each row on its own baseline. | `crossScale.ts` `stackGeom`, the per-row range labels in `CrossChannelPage.tsx` |
| X2 | **The window picker does not pick.** "window · interesting span at 0.78 h ± 20 s" is a dropdown; choosing another entry does not change the window. Also the header says ± 20 s while the axis runs 0 … +600 s over a 640 s window — say what the window IS (the span plus its pad) in one phrase the axis agrees with. The deep links `?window=motif-<n>`, `?pad=`, `?t0=&t1=` must all drive the same state. | `useQueryState('window', …)`, `getCrossChannel` |
| X3 | **lag 0.0 s on every pair with r ≈ −0.97, binned *independent*.** Six pairs at exactly zero lag and |r| near 1 is what a shared slow drift produces, not a propagating event: check whether `classify_waveforms` detrends before correlating, and whether the bin the row prints is the bin the rule produced (the page says artifact = |lag| ≤ 1 s and |r| ≥ 0.5 either sign — by that rule these rows would be *artifact*, not *independent*). Either the numbers or the rule text is wrong; make the row's tooltip print the rule it was binned by, from the bridge. | `Working/cross_channel.py`, the bin tooltips |
| X4 | **`align · lag-aligned`** must visibly shift rows by their lag; with every lag at 0 nothing can move, so X3 first. | `?align=lag` |
| X5 | **"Take it further" — the first card is greyed with no reason on the page** (Classify a Library family across channels). Print the disabled reason under the card, as the Jobs import button now does (`import-why-*`). | the hand-off cards |
| X6 | **The reference row is locked** (padlock) — say in one hover why, and how to change the reference (the `reference` dropdown does it; the lock suggests it cannot be). | the row header |

## Work

1. Reproduce each row above in the browser against your sandbox, with the researcher's state: `#/explore/cross-channel/<CH2_A1 id>?channels=…&y=centred`. Screenshot before.
2. X1 first — it is the page. Then X2, X3, X4 in that order; X5 and X6 are an hour together.
3. Every number the page prints must come from the bridge, never be recomputed in the browser from a different array.
4. Add a smoke walk: pick a window → the axis changes; the gain note equals the largest drawn row's range; a bin tooltip names its rule.

## Acceptance

- [ ] A row's trace spans its row: the shared gain equals the largest per-row range among the drawn rows, and the note says so with the same number.
- [ ] Choosing a window in the picker changes the plotted window, the axis and the URL; `?window=` / `?t0=&t1=` reproduce it.
- [ ] Each pair's lag, r and bin come from one call of the core's classifier on the plotted window; the tooltip prints the rule that produced the bin; X3's zero lags are explained (detrended) or shown to be real.
- [ ] Lag-aligned mode moves rows by their lag.
- [ ] Disabled hand-off cards print their reason.
- [ ] `tsc -b`, `npm run build`, smoke (with the new walk) and `pytest` pass; before/after screenshots under `webui/screenshots/`.

## Report

`docs/prompts/fixup/reports/AQ-cross-channel-finish.md`: the screenshot pair, where 20.74 came from, what X3 turned out
to be, and anything you had to leave (say so, do not narrow silently). Update `docs/rq_roundA/RQ6-…md` if what the page
can now show changes what RQ6 can answer.

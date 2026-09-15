# Library — frontend-design fog

Each bullet: question · why it matters · source. Shell decisions are marked **shell:**.

## Motifs · atlas (library-2, 2b)
- Card axes read ±0.4 mV but four families are deeper (F-05 +0.65, F-08 −0.52, F-09 +0.48, F-02 ±0.45) · a shared, never-normalised scale (D5) cannot honour both; the tick label or the depths are wrong · frame 2 vs §3 D5. **shell:** one computed domain for every card, rail plot, overlay and sparkline (±0.7 mV).
- `sort: members in scope` but the cards are in family-id order (F-09, 71 in scope, would lead) · a sort label that does not match the order misleads · frame 2. **shell:** default `sort: family id`; the Select offers members in scope, judged, duration, hand edits.
- Family totals do not sum to the catalogue: 838 members + 38 omitted ≠ 1,402 · either small families are hidden by `≥ 10 members` (nothing says so) or the numbers are placeholders · frame 2, rail `families 10`. **shell:** frame numbers; changing `≥ N members` reports how many families it hides.
- `prop. 4` / `ind. 1` channel chips are not defined anywhere · the rail claims cross-channel counts without a glossary · §8.5. **shell:** InfoTip guesses "propagated copy" / "independent occurrence".
- Sequence arithmetic does not close: S-03 `F-02 × 4` × 18 needs 72 F-02 motifs (F-02 has 42); S-02 `~22 s` cannot hold a 21 s sharkfin + 14 s gap; `Send 21 unjudged motifs` vs judged 23 of 42 (= 19) · B28 class · frame 2b. **shell:** 19.
- A sequence family page (`Open all 21 sequences →`) is not drawn · the primary action of 2b has no destination · frame 2b, §8.6. **shell:** `#/library/family/S-02` shows an honest placeholder listing the sequence ids.
- Spec §8.2 says 1,188 single motifs omitted under g-08; frame and backlog say 1,018 · §8.2 vs frame 2b. **shell:** 1,018.
- What the atlas shows for a feature-bin or label grouping (g-09 after Apply; g-01 first import): group names, exemplar (no human anchor), medoid of a bin · after Apply the user lands on a page no frame draws · §8.2, frame 4. **shell:** an EmptyState naming the grouping with `Switch back to g-07`; nothing is invented.

## Motifs · family (library-3)
- Distance sort puts m-1850 (d 0.47, past the cut) on page 1 of 112 · with 102 more members at d ≥ 0.31 it would sort to page 12 · frame 3. **shell:** members kept past the cut by hand are pinned to the end of page 1 (InfoTip says so).
- m-1850 `onset · duration 196.6 h · 1.62 s` in a ~21 s family drawn over 21 s · B28 class · frame 3. **shell:** 21.6 s.
- `recordings 3 · 5 channels` while recurrence shows F-03 on 11 channels · which count is "channels" · frames 1 vs 3.
- `hand edits 2 added` but only m-1850 is visible · where the second added member lives is undrawn · frame 3. **shell:** m-1971 on a later page.
- Undo on an *added* member: delete the hand edit (member leaves) or restore a moved member's previous family · §8.6 only says "hand-edit record with Undo". **shell:** member leaves, toast offers Redo.
- Make exemplar: does the old seed keep its `seed` verdict; does the recipe hash change or the family go partially stale (§4.2 last rule) · consequences unstated. **shell:** badge `edges partially stale` after the change.
- Revision annotation id of m-1850 is not in the frame. **shell:** `a-2091`.

## Motifs · recurrence (library-1)
- Per-hour values do not reconcile with member counts (0.61/h on CH3_A2 over 721 h ≈ 440 members; F-03 has 112) · the matrix and the atlas cannot both be right · frame 1. **shell:** per-hour shows frame values; count mode shows an integer split that sums to the atlas.
- Rail `hours 128.4 h` reconciles with no reading (not channel-hours 1,722, not recording-hours 1,001) · frame 1. **shell:** labelled `channel-hours`, computed.
- M2_aug fs1 caption `45.2 h` vs §0 721 h · frame 1 vs §0. **shell:** 721 h.
- 16-channel recordings do not fit three per page; the frame draws 6 / 4 / 5 channels · which channels are hidden and how to reach them · §8.4. **shell:** the first N drawn, caption `+10 ch` with a tooltip; no expander.
- Recordings 4–5 of 5 are undrawn: `M2_aug fs2` (a resample of fs1, B30) and `M4_aug` (held out, D6) · frame 1 pager. **shell:** fs2 drawn with checkboxes disabled while fs1 is selected (and vice versa); M4 a locked block.
- Shared-ground warning names a family (`share ground for F-03`) but shared ground is channel metadata · per family or per channel pair · frame 1, Settings › Channels & events.
- Members found on a channel nobody reviewed (L_LM CH1/CH2) show a value with no marker · "found but never looked at" is indistinguishable from reviewed · §8.4.
- The matrix for the sequences unit is not drawn · §8.4. **shell:** S-01…S-06 reuse the F-01…F-06 cells.

## Motifs · grouping (library-4)
- Eight of nine parameter panels are undrawn and B17 says the bases themselves are undefined (sequence similarity, frequency feature, timescale, default cuts/bins/minimum size) · every per-basis control is an extrapolation · frame 4, B17.
- What a `spike trains` unit groups by, and whether any atlas draws it · B17. **shell:** Apply disabled for spike trains ("save it instead").
- Library regroups have no local limit in Settings (Analyse 20 min, Discovery 20 min, Models 2 h) yet the preview says `~10 min, local` · §0. **shell:** 20 min; shape distance on sequences (~46 min) turns Apply into `Create SLURM script`.
- `sequences 350` reads as a sequence count but only reconciles as a motif count (139 sequences) · frame 4 vs 2b.
- Does Apply also clear the filters (`adjudicated only`, `≥ 10 members`) as well as the scope · §8.2. **shell:** filters kept.
- Route vs modal: the page is prescribed as a route; the frame is a modal over the atlas · pages.ts vs frame 4. **shell:** the route renders the page named by `?from=` behind the modal.

## Motifs · import (library-5)
- Frame bundle `DATA/library_seed/drop_motifs`; the tracked bundle is `drop_motifs5` · frame 5 vs repo. **shell:** `drop_motifs5`.
- The library after a demo import should be 410 motifs in g-01; there is no fixture for it · §8.7. **shell:** a toast says the canon catalogue is shown.
- A dry run on a populated library is undrawn · frames 1–3 toolbar Import. **shell:** "410 already in the library · re-import skips", Import disabled "nothing new".
- Whether provisional durations (inferred fs) should block the import or only warn · frame 5 warns.
- Which 2 recordings / 7 channels the bundle covers is not stated · frame 5. **shell:** M2_aug fs1 CH3_A2, CH4_A2 + L_LM_Jul26_J CH1–CH5.
- The inventory calls the empty library "sticky for the session"; that makes every later deep link show an empty catalogue · inventory decision. **shell:** empty is derived from `?library=empty` and carried by the empty page's own links.

## Window sets (library-6)
- Class bars 410 + 380 + 330 + 250 + 38 = 1,408 vs `2,140 windows` labelled (§0) · frame 6. **shell:** canon-consistent 612 · 568 · 492 · 430 · 38.
- Delete "removes bounds from disk" or archives · unspecified · §8.8.
- Split fractions per row and hour ranges of the split plan are not in any spec · frame 6. **shell:** frame proportions.
- `ws_M2aug_fs2_300s` is an fs2 set; nothing guards a training job combining it with fs1 sets · B30.
- `Send unlabelled to Review` above the P13 cap (20,000) is undrawn · P13. **shell:** disabled with the cap as reason.
- The frame shows no version though §0 names `ws_M2aug_3ch_600s` v1 and Models saves v2 · §0. **shell:** `v1` chip in row and rail.

## Templates (library-7)
- What `× null` means (observed / null p95? mean?) · a number without a definition · §4.8.
- "Latest score" on a card: most recent run or widest scope · unstated · §8.9. **shell:** most recent run.
- Archive semantics (hidden vs deleted; applying an archived version from an old run) · §8.9.
- Training templates score "jobs" (`1 job`) while the rail table header says `run` · frame 7. **shell:** header `job` for training.
- `mp_drops_v3` is not among §0's named templates (§0 says "including", so allowed) · §0.
